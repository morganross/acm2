"""
LLM Judge for document evaluation.

Uses FPF adapter to call LLMs for single-doc and pairwise evaluation.
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
from uuid import uuid4

from ..adapters.fpf.adapter import FpfAdapter
from ..adapters.base import GenerationConfig
from ..services.rate_limiter import RateLimitedRequest
from .criteria import CriteriaManager, format_criteria_for_prompt
from .models import (
    CriterionScore,
    EvaluationCriterion,
    PairwiseResult,
    SingleEvalResult,
)

logger = logging.getLogger(__name__)


@dataclass
class FpfStatsTracker:
    """Tracks live FPF call statistics."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    retries: int = 0
    current_phase: Optional[str] = None
    current_call: Optional[str] = None
    last_error: Optional[str] = None
    _on_update: Optional[Callable[["FpfStatsTracker"], None]] = field(default=None, repr=False)
    
    def record_call_start(self, phase: str, description: str):
        """Record the start of an FPF call."""
        logger.info(f"[STATS-DEBUG] record_call_start called: phase={phase}, desc={description}")
        self.current_phase = phase
        self.current_call = description
        self._notify()
    
    def record_success(self):
        """Record a successful FPF call."""
        self.total_calls += 1
        self.successful_calls += 1
        self.current_call = None
        self.last_error = None  # Clear previous errors on success
        self._notify()
    
    def record_failure(self, error: str):
        """Record a failed FPF call."""
        self.total_calls += 1
        self.failed_calls += 1
        self.last_error = error
        self.current_call = None
        self._notify()
    
    def record_retry(self, attempt: int, error: str):
        """Record a retry attempt."""
        self.retries += 1
        self.last_error = f"Retry {attempt}: {error}"
        self._notify()
    
    def _notify(self):
        """Notify listener of stats update."""
        cb_name = getattr(self._on_update, '__name__', 'NO_NAME') if self._on_update else 'NONE'
        cb_self = getattr(self._on_update, '__self__', None)
        cb_self_type = type(cb_self).__name__ if cb_self else 'NO_SELF'
        logger.info(f"[STATS-DEBUG] _notify: callback={cb_name}, bound_to={cb_self_type}, id={id(self._on_update) if self._on_update else 0}")
        if self._on_update:
            try:
                logger.info(f"[STATS-DEBUG] Calling _on_update callback")
                self._on_update(self)
                logger.info(f"[STATS-DEBUG] _on_update callback completed")
            except Exception as e:
                logger.error(f"[STATS-DEBUG] _on_update callback failed: {e}", exc_info=True)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "retries": self.retries,
            "current_phase": self.current_phase,
            "current_call": self.current_call,
            "last_error": self.last_error,
        }


@dataclass
class JudgeConfig:
    """
    Configuration for LLM judge.
    
    Note: timeout_seconds and retries are set here as reasonable defaults.
    In future, these should be loaded from evaluation config or preset.
    """
    
    model: str = ""  # REQUIRED - must be set by caller
    temperature: float = 0.0
    max_tokens: int = 16384
    timeout_seconds: int = 600  # Increased from 120s to handle slow models
    retries: int = 3  # Increased from 2 for better resilience
    
    # Prompt settings
    strict_json: bool = True
    # NOTE: enable_grounding removed - FPF always uses grounding, non-configurable


def _parse_json_response(text: str) -> Dict[str, Any]:
    """Parse JSON from LLM response."""
    text = text.strip()
    
    # Remove markdown code blocks if present
    if text.startswith("```"):
        lines = text.split("\n")
        start = 1 if lines[0].startswith("```") else 0
        end = len(lines)
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].strip() == "```":
                end = i
                break
        text = "\n".join(lines[start:end]).strip()
    
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Try to find JSON object in text
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        return json.loads(match.group(0))
    
    raise ValueError(f"No valid JSON found in response: {text[:200]}...")


class Judge:
    """
    LLM-based document judge using FPF adapter.
    
    Supports both single-document graded evaluation and pairwise comparison.
    
    IMPORTANT: No default prompts are provided. Custom instructions MUST be
    supplied from the preset's Content Library. This is by design to ensure
    all evaluation behavior is explicitly configured.
    """
    
    def __init__(
        self,
        config: Optional[JudgeConfig] = None,
        criteria_manager: Optional[CriteriaManager] = None,
        fpf_adapter: Optional[FpfAdapter] = None,
        custom_prompt: Optional[str] = None,
        stats_tracker: Optional[FpfStatsTracker] = None,
    ):
        """
        Initialize the judge.
        
        Args:
            config: Judge configuration
            criteria_manager: Criteria manager instance
            fpf_adapter: FPF adapter instance (created if not provided)
            custom_prompt: Custom evaluation prompt from Content Library (REQUIRED for eval)
            stats_tracker: Optional stats tracker for live FPF call monitoring
        """
        self.config = config or JudgeConfig()
        self.criteria = criteria_manager or CriteriaManager()
        self._fpf = fpf_adapter
        self.custom_prompt = custom_prompt
        self.stats = stats_tracker  # Use the tracker as-is, don't create fallback
        
        # DEBUG: Log stats tracker initialization
        logger.info(f"[STATS-DEBUG] Judge.__init__ for model={self.config.model}, stats_tracker={stats_tracker is not None}")
    
    @property
    def fpf(self) -> FpfAdapter:
        """Get or create FPF adapter."""
        if self._fpf is None:
            self._fpf = FpfAdapter()
        return self._fpf
    
    async def evaluate_single(
        self,
        doc_id: str,
        content: str,
        trial: int = 1,
        criteria: Optional[List[EvaluationCriterion]] = None,
        custom_prompt: Optional[str] = None,
    ) -> SingleEvalResult:
        """
        Perform single-document graded evaluation.
        
        Args:
            doc_id: Document identifier
            content: Document content to evaluate
            trial: Trial number for multi-iteration runs
            criteria: Optional custom criteria (uses manager's if not provided)
            custom_prompt: Custom evaluation prompt (overrides instance prompt)
            
        Returns:
            SingleEvalResult with scores for each criterion
            
        Raises:
            RuntimeError: If evaluation fails after retries or no prompt provided
        """
        from datetime import datetime
        
        # Determine prompt to use: parameter > instance > ERROR
        prompt_template = custom_prompt or self.custom_prompt
        if not prompt_template:
            raise RuntimeError(
                "No evaluation prompt provided. Single eval requires custom_instructions "
                "from the preset's Content Library. Configure single_eval_instructions_id "
                "in your preset."
            )
        
        started_at = datetime.utcnow()
        crit_list = criteria or self.criteria.criteria
        criteria_text = format_criteria_for_prompt(crit_list)
        
        # Format the prompt with document and criteria
        # Support {document}, {content}, {criteria} placeholders
        prompt = prompt_template
        try:
            prompt = prompt.replace("{document}", content)
            prompt = prompt.replace("{content}", content)
            prompt = prompt.replace("{criteria}", criteria_text)
        except Exception as e:
            logger.warning(f"Error formatting prompt placeholders: {e}")
        
        last_error = None
        raw_response = None
        
        # DEBUG: Log entry into evaluate_single
        logger.info(f"[STATS-DEBUG] evaluate_single CALLED for {doc_id}, trial={trial}, stats={self.stats is not None}")
        
        for attempt in range(self.config.retries + 1):
            try:
                # Track call start
                logger.info(f"[STATS-DEBUG] Attempt {attempt}, about to record_call_start, stats={self.stats is not None}")
                if self.stats:
                    self.stats.record_call_start("single_eval", f"Evaluating {doc_id} (attempt {attempt + 1})")
                
                # Extract provider from model name (format: "provider:model_name")
                if ":" in self.config.model:
                    provider, base_model = self.config.model.split(":", 1)
                else:
                    # Default to openai if no prefix (legacy format)
                    provider = "openai"
                    base_model = self.config.model
                
                # Build config for FPF adapter
                eval_task_id = f"{doc_id}.single_eval.{trial}.{self.config.model}.{uuid4().hex[:6]}"
                gen_config = GenerationConfig(
                    provider=provider,
                    model=base_model,
                    extra={
                        "max_completion_tokens": self.config.max_tokens,
                        "temperature": self.config.temperature,
                        "json_output": True,  # Eval responses are JSON, skip 3KB minimum check
                        "timeout": self.config.timeout_seconds,
                        "task_id": eval_task_id,
                    },
                )
                
                # INSTRUMENTATION: Log before FPF dispatch
                logger.info(f"[EVAL-DISPATCH] About to call FPF for single_eval: task_id={eval_task_id}, provider={provider}, model={base_model}, timeout={self.config.timeout_seconds}s")
                
                # Call FPF for evaluation with hard timeout to prevent indefinite hangs
                # Apply provider-level rate limiting before making API call
                # NOTE: FPF has its own retry logic for API errors (429, 500s) - don't retry those here
                try:
                    async with RateLimitedRequest(provider):
                        result = await asyncio.wait_for(
                            self.fpf.generate(
                                query=prompt,
                                config=gen_config,
                            ),
                            timeout=float(self.config.timeout_seconds + 30),  # Add buffer over FPF's internal timeout
                        )
                except asyncio.TimeoutError:
                    logger.error(f"[EVAL-DISPATCH] HARD TIMEOUT: FPF single_eval call for {eval_task_id} exceeded {self.config.timeout_seconds + 30}s")
                    # Timeout is fatal - FPF already timed out internally, don't retry
                    raise RuntimeError(f"Single eval call timed out after {self.config.timeout_seconds + 30}s for {eval_task_id}")
                except RuntimeError as fpf_err:
                    # RuntimeError from FPF means API failure after FPF's own retries - don't retry again
                    logger.error(f"[EVAL-DISPATCH] FPF API error (not retriable): {fpf_err}")
                    if self.stats:
                        self.stats.record_failure(str(fpf_err))
                    raise
                
                logger.info(f"[EVAL-DISPATCH] FPF single_eval completed for {eval_task_id}")
                
                raw_response = result.content
                
                # Parse JSON response - THESE errors ARE retriable (malformed LLM output)
                try:
                    data = _parse_json_response(raw_response)
                    
                    # Extract scores
                    evaluations = data.get("evaluations", [])
                    if not evaluations:
                        raise ValueError("No evaluations in response")
                    
                    scores = []
                    for eval_item in evaluations:
                        scores.append(CriterionScore(
                            criterion=eval_item["criterion"],
                            score=int(eval_item["score"]),
                            reason=eval_item.get("reason", ""),
                        ))
                except (ValueError, KeyError, TypeError, json.JSONDecodeError) as parse_err:
                    # Parse/validation errors - these ARE retriable at eval level
                    last_error = parse_err
                    if attempt < self.config.retries:
                        if self.stats:
                            self.stats.record_retry(attempt + 1, f"Parse error: {parse_err}")
                        logger.warning(f"Single eval attempt {attempt + 1} parse error for {doc_id}: {parse_err}")
                        continue  # Retry with a fresh FPF call
                    else:
                        if self.stats:
                            self.stats.record_failure(f"Parse error: {parse_err}")
                        raise RuntimeError(f"Single evaluation failed after {self.config.retries + 1} attempts: {parse_err}")
                
                # Track success
                if self.stats:
                    self.stats.record_success()
                
                completed_at = datetime.utcnow()
                return SingleEvalResult(
                    doc_id=doc_id,
                    model=self.config.model,
                    trial=trial,
                    scores=scores,
                    started_at=started_at,
                    completed_at=completed_at,
                    duration_seconds=(completed_at - started_at).total_seconds(),
                    raw_response=raw_response,
                )
                
            except RuntimeError:
                # Already handled above - propagate up
                raise
            except Exception as e:
                # Unexpected errors - log and propagate
                logger.error(f"Unexpected error in single_eval for {doc_id}: {e}")
                if self.stats:
                    self.stats.record_failure(str(e))
                raise
        
        raise RuntimeError(
            f"Single evaluation failed after {self.config.retries + 1} attempts: {last_error}"
        )
    
    async def evaluate_pairwise(
        self,
        doc_id_1: str,
        content_1: str,
        doc_id_2: str,
        content_2: str,
        trial: int = 1,
        criteria: Optional[List[EvaluationCriterion]] = None,
        custom_prompt: Optional[str] = None,
    ) -> PairwiseResult:
        """
        Perform pairwise comparison between two documents.
        
        Documents are anonymized as A and B to prevent bias.
        
        Args:
            doc_id_1: First document identifier
            content_1: First document content
            doc_id_2: Second document identifier
            content_2: Second document content
            trial: Trial number for multi-iteration runs
            criteria: Optional custom criteria
            custom_prompt: Custom pairwise prompt (overrides instance prompt)
            
        Returns:
            PairwiseResult with winner and reason
            
        Raises:
            RuntimeError: If comparison fails after retries or no prompt provided
        """
        from datetime import datetime
        
        # Determine prompt to use: parameter > instance > ERROR
        prompt_template = custom_prompt or self.custom_prompt
        if not prompt_template:
            raise RuntimeError(
                "No pairwise prompt provided. Pairwise eval requires custom_instructions "
                "from the preset's Content Library. Configure pairwise_eval_instructions_id "
                "in your preset."
            )
        
        started_at = datetime.utcnow()
        crit_list = criteria or self.criteria.criteria
        criteria_text = format_criteria_for_prompt(crit_list)
        
        # Format the prompt with documents and criteria
        # Support {doc_a}, {doc_b}, {criteria}, {document_a}, {document_b} placeholders
        prompt = prompt_template
        try:
            prompt = prompt.replace("{doc_a}", content_1)
            prompt = prompt.replace("{doc_b}", content_2)
            prompt = prompt.replace("{document_a}", content_1)
            prompt = prompt.replace("{document_b}", content_2)
            prompt = prompt.replace("{criteria}", criteria_text)
        except Exception as e:
            logger.warning(f"Error formatting pairwise prompt placeholders: {e}")
        
        last_error = None
        raw_response = None
        
        for attempt in range(self.config.retries + 1):
            try:
                # Track call start
                if self.stats:
                    self.stats.record_call_start("pairwise_eval", f"Comparing {doc_id_1} vs {doc_id_2} (attempt {attempt + 1})")
                
                # Extract provider from model name (format: "provider:model_name")
                if ":" in self.config.model:
                    provider, base_model = self.config.model.split(":", 1)
                else:
                    # Default to openai if no prefix (legacy format)
                    provider = "openai"
                    base_model = self.config.model
                
                # Build config for FPF adapter
                pairwise_task_id = f"{doc_id_1}.vs.{doc_id_2}.pairwise.{trial}.{self.config.model}.{uuid4().hex[:6]}"
                gen_config = GenerationConfig(
                    provider=provider,
                    model=base_model,
                    extra={
                        "max_completion_tokens": self.config.max_tokens,
                        "temperature": self.config.temperature,
                        "json_output": True,  # Eval responses are JSON, skip 3KB minimum check
                        "timeout": self.config.timeout_seconds,
                        "task_id": pairwise_task_id,
                    },
                )
                
                # INSTRUMENTATION: Log before FPF dispatch
                logger.info(f"[EVAL-DISPATCH] About to call FPF for pairwise_eval: task_id={pairwise_task_id}, provider={provider}, model={base_model}, timeout={self.config.timeout_seconds}s")
                
                # Call FPF for pairwise evaluation with hard timeout
                # Apply provider-level rate limiting before making API call
                # NOTE: FPF has its own retry logic for API errors (429, 500s) - don't retry those here
                try:
                    async with RateLimitedRequest(provider):
                        result = await asyncio.wait_for(
                            self.fpf.generate(
                                query=prompt,
                                config=gen_config,
                            ),
                            timeout=float(self.config.timeout_seconds + 30),
                        )
                except asyncio.TimeoutError:
                    logger.error(f"[EVAL-DISPATCH] HARD TIMEOUT: FPF pairwise_eval call for {pairwise_task_id} exceeded {self.config.timeout_seconds + 30}s")
                    # Timeout is fatal - FPF already timed out internally, don't retry
                    raise RuntimeError(f"Pairwise eval call timed out after {self.config.timeout_seconds + 30}s for {pairwise_task_id}")
                except RuntimeError as fpf_err:
                    # RuntimeError from FPF means API failure after FPF's own retries - don't retry again
                    logger.error(f"[EVAL-DISPATCH] FPF API error (not retriable): {fpf_err}")
                    if self.stats:
                        self.stats.record_failure(str(fpf_err))
                    raise
                
                logger.info(f"[EVAL-DISPATCH] FPF pairwise_eval completed for {pairwise_task_id}")
                
                raw_response = result.content
                
                # Parse JSON response - THESE errors ARE retriable (malformed LLM output)
                try:
                    data = _parse_json_response(raw_response)
                    
                    # Extract winner
                    winner_letter = data.get("winner", "").upper()
                    if winner_letter not in ("A", "B"):
                        raise ValueError(f"Invalid winner: {winner_letter}")
                    
                    # Map A/B back to actual doc IDs
                    winner_doc_id = doc_id_1 if winner_letter == "A" else doc_id_2
                    reason = data.get("reason", "")
                except (ValueError, KeyError, TypeError, json.JSONDecodeError) as parse_err:
                    # Parse/validation errors - these ARE retriable at eval level
                    last_error = parse_err
                    if attempt < self.config.retries:
                        if self.stats:
                            self.stats.record_retry(attempt + 1, f"Parse error: {parse_err}")
                        logger.warning(f"Pairwise eval attempt {attempt + 1} parse error: {parse_err}")
                        continue  # Retry with a fresh FPF call
                    else:
                        if self.stats:
                            self.stats.record_failure(f"Parse error: {parse_err}")
                        raise RuntimeError(f"Pairwise evaluation failed after {self.config.retries + 1} attempts: {parse_err}")
                
                # Track success
                if self.stats:
                    self.stats.record_success()
                
                completed_at = datetime.utcnow()
                return PairwiseResult(
                    doc_id_1=doc_id_1,
                    doc_id_2=doc_id_2,
                    winner_doc_id=winner_doc_id,
                    model=self.config.model,
                    trial=trial,
                    reason=reason,
                    started_at=started_at,
                    completed_at=completed_at,
                    duration_seconds=(completed_at - started_at).total_seconds(),
                    raw_response=raw_response,
                )
                
            except RuntimeError:
                # Already handled above - propagate up
                raise
            except Exception as e:
                # Unexpected errors - log and propagate
                logger.error(f"Unexpected error in pairwise_eval: {e}")
                if self.stats:
                    self.stats.record_failure(str(e))
                raise
        
        raise RuntimeError(
            f"Pairwise evaluation failed after {self.config.retries + 1} attempts: {last_error}"
        )
