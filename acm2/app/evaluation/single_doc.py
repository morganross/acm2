"""
Single-document graded evaluation service.

Evaluates documents against criteria and stores results.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional

import yaml

from .criteria import CriteriaManager
from .judge import Judge, JudgeConfig, FpfStatsTracker
from .models import CriterionScore, EvaluationCriterion, SingleEvalResult

logger = logging.getLogger(__name__)

# Callback fired after each individual judge evaluation completes
# Args: (doc_id, model, trial, result)
EvalCompleteCallback = Callable[[str, str, int, SingleEvalResult], Awaitable[None]]


@dataclass
class SingleEvalConfig:
    """Configuration for single-document evaluation."""
    
    iterations: int = 1
    judge_models: List[str] = field(default_factory=list)  # REQUIRED - must be set by preset
    criteria_path: Optional[str] = None
    temperature: float = 0.0
    max_tokens: int = 16384
    concurrent_limit: int = 3  # Max concurrent evaluations
    timeout_seconds: int = 600  # Per-call timeout (GUI EvalPanel)
    retries: int = 0
    strict_json: bool = True
    # NOTE: enable_grounding removed - FPF always uses grounding, non-configurable
    
    # Custom instructions from Content Library
    custom_instructions: Optional[str] = None
    custom_criteria: Optional[str] = None
    
    def to_judge_config(self, model: str) -> JudgeConfig:
        """Create JudgeConfig for a specific model."""
        return JudgeConfig(
            model=model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            timeout_seconds=self.timeout_seconds,
            retries=self.retries,
            strict_json=self.strict_json,
        )


@dataclass
class DocumentInput:
    """Input for single-document evaluation."""
    
    doc_id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SingleEvalSummary:
    """Summary of single-document evaluation results."""
    
    doc_id: str
    avg_score: float
    scores_by_criterion: Dict[str, float]
    num_evaluations: int
    results: List[SingleEvalResult]
    
    @classmethod
    def from_results(
        cls,
        doc_id: str,
        results: List[SingleEvalResult],
    ) -> "SingleEvalSummary":
        """
        Create summary from list of evaluation results.
        
        Args:
            doc_id: Document identifier
            results: List of evaluation results
            
        Returns:
            Summary with aggregated statistics
        """
        if not results:
            return cls(
                doc_id=doc_id,
                avg_score=0.0,
                scores_by_criterion={},
                num_evaluations=0,
                results=[],
            )
        
        # Aggregate scores by criterion
        criterion_scores: Dict[str, List[int]] = {}
        for result in results:
            for score in result.scores:
                if score.criterion not in criterion_scores:
                    criterion_scores[score.criterion] = []
                criterion_scores[score.criterion].append(score.score)
        
        # Calculate averages per criterion
        scores_by_criterion = {
            crit: sum(scores) / len(scores)
            for crit, scores in criterion_scores.items()
        }
        
        # Calculate overall average
        all_scores = [s for scores in criterion_scores.values() for s in scores]
        avg_score = sum(all_scores) / len(all_scores) if all_scores else 0.0
        
        return cls(
            doc_id=doc_id,
            avg_score=avg_score,
            scores_by_criterion=scores_by_criterion,
            num_evaluations=len(results),
            results=results,
        )


ProgressCallback = Callable[[str, int, int], None]  # (doc_id, completed, total)


class SingleDocEvaluator:
    """
    Service for single-document graded evaluation.
    
    Evaluates documents against criteria using multiple iterations
    and judge models, then aggregates results.
    """
    
    def __init__(
        self,
        config: Optional[SingleEvalConfig] = None,
        criteria_manager: Optional[CriteriaManager] = None,
        stats_tracker: Optional[FpfStatsTracker] = None,
    ):
        """
        Initialize the evaluator.
        
        Args:
            config: Evaluation configuration
            criteria_manager: Criteria manager instance
            stats_tracker: Optional FPF stats tracker for live monitoring
        """
        self.config = config or SingleEvalConfig()
        self.criteria = criteria_manager or CriteriaManager(self.config.criteria_path)
        self.stats = stats_tracker
        self._judges: Dict[str, Judge] = {}
        
        # Parse custom_criteria YAML string from Content Library if provided
        if self.config.custom_criteria:
            try:
                data = yaml.safe_load(self.config.custom_criteria)
                if data and "criteria" in data:
                    parsed_criteria = []
                    for item in data["criteria"]:
                        if isinstance(item, str):
                            parsed_criteria.append(EvaluationCriterion(
                                name=item,
                                description=f"Evaluate the {item} of the document.",
                            ))
                        elif isinstance(item, dict) and "name" in item:
                            parsed_criteria.append(EvaluationCriterion(
                                name=item["name"],
                                description=item.get("description", f"Evaluate the {item['name']}."),
                            ))
                    if parsed_criteria:
                        self.criteria.set_criteria(parsed_criteria)
                        logger.info(f"Loaded {len(parsed_criteria)} criteria from Content Library custom_criteria")
            except Exception as e:
                logger.error(f"Failed to parse custom_criteria YAML: {e}")
        
        # DEBUG: Log stats tracker initialization
        logger.info(f"[STATS-DEBUG] SingleDocEvaluator.__init__ stats_tracker={stats_tracker is not None}")
    
    def _get_judge(self, model: str) -> Judge:
        """Get or create judge for a model."""
        if model not in self._judges:
            judge_config = self.config.to_judge_config(model)
            logger.info(f"[STATS-DEBUG] Creating Judge for model={model}, passing stats_tracker={self.stats is not None}")
            self._judges[model] = Judge(
                config=judge_config,
                criteria_manager=self.criteria,
                custom_prompt=self.config.custom_instructions,
                stats_tracker=self.stats,
            )
        return self._judges[model]
    
    async def evaluate_document(
        self,
        doc: DocumentInput,
        progress_callback: Optional[ProgressCallback] = None,
        on_eval_complete: Optional[EvalCompleteCallback] = None,
    ) -> SingleEvalSummary:
        """
        Evaluate a single document.
        
        Runs all iterations across all judge models and aggregates results.
        
        Args:
            doc: Document to evaluate
            progress_callback: Optional callback for progress updates
            on_eval_complete: Optional async callback fired after each judge evaluation
            
        Returns:
            Summary of evaluation results
        """
        results: List[SingleEvalResult] = []
        total_evals = self.config.iterations * len(self.config.judge_models)
        completed = 0
        
        for model in self.config.judge_models:
            judge = self._get_judge(model)
            
            for trial in range(1, self.config.iterations + 1):
                try:
                    result = await judge.evaluate_single(
                        doc_id=doc.doc_id,
                        content=doc.content,
                        trial=trial,
                    )
                    results.append(result)
                    logger.info(
                        f"Single eval completed: {doc.doc_id} | "
                        f"model={model} trial={trial} avg={result.average_score:.2f}"
                    )
                    
                    # Fire per-judge callback if provided
                    if on_eval_complete:
                        try:
                            await on_eval_complete(doc.doc_id, model, trial, result)
                        except Exception as e:
                            logger.error(f"on_eval_complete callback failed: {e}")
                except Exception as e:
                    logger.error(
                        f"Single eval failed: {doc.doc_id} | "
                        f"model={model} trial={trial}: {e}"
                    )
                
                completed += 1
                if progress_callback:
                    try:
                        progress_callback(doc.doc_id, completed, total_evals)
                    except Exception:
                        pass
        
        return SingleEvalSummary.from_results(
            doc_id=doc.doc_id,
            results=results,
        )
    
    async def evaluate_documents(
        self,
        docs: List[DocumentInput],
        progress_callback: Optional[Callable[[str, int, int, int, int], None]] = None,
        on_eval_complete: Optional[EvalCompleteCallback] = None,
    ) -> Dict[str, SingleEvalSummary]:
        """
        Evaluate multiple documents with concurrency control.
        
        Args:
            docs: List of documents to evaluate
            progress_callback: Callback(doc_id, doc_completed, total_docs, eval_completed, total_evals)
            on_eval_complete: Optional async callback fired after each individual judge evaluation
            
        Returns:
            Dict mapping doc_id to evaluation summary
        """
        results: Dict[str, SingleEvalSummary] = {}
        semaphore = asyncio.Semaphore(self.config.concurrent_limit)
        total_docs = len(docs)
        completed_docs = 0
        
        async def eval_with_limit(doc: DocumentInput) -> tuple[str, SingleEvalSummary]:
            nonlocal completed_docs
            async with semaphore:
                summary = await self.evaluate_document(doc, on_eval_complete=on_eval_complete)
                completed_docs += 1
                if progress_callback:
                    try:
                        progress_callback(
                            doc.doc_id,
                            completed_docs,
                            total_docs,
                            summary.num_evaluations,
                            self.config.iterations * len(self.config.judge_models),
                        )
                    except Exception:
                        pass
                return doc.doc_id, summary
        
        # Run all evaluations concurrently (with limit)
        tasks = [eval_with_limit(doc) for doc in docs]
        for coro in asyncio.as_completed(tasks):
            doc_id, summary = await coro
            results[doc_id] = summary
        
        return results
    
    def rank_documents(
        self,
        summaries: Dict[str, SingleEvalSummary],
    ) -> List[tuple[str, float]]:
        """
        Rank documents by their evaluation scores.
        
        Args:
            summaries: Dict mapping doc_id to summary
            
        Returns:
            List of (doc_id, score) tuples sorted by score descending
        """
        rankings = []
        for doc_id, summary in summaries.items():
            score = summary.avg_score
            rankings.append((doc_id, score))
        
        rankings.sort(key=lambda x: x[1], reverse=True)
        return rankings
    
    def get_top_n(
        self,
        summaries: Dict[str, SingleEvalSummary],
        n: int,
    ) -> List[str]:
        """
        Get top N document IDs by score.
        
        Args:
            summaries: Dict mapping doc_id to summary
            n: Number of top documents to return
            
        Returns:
            List of top N doc_ids
        """
        rankings = self.rank_documents(summaries)
        return [doc_id for doc_id, _ in rankings[:n]]
