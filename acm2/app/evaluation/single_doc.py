"""
Single-document graded evaluation service.

Evaluates documents against criteria and stores results.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .criteria import CriteriaManager
from .judge import Judge, JudgeConfig, FpfStatsTracker
from .models import CriterionScore, EvaluationCriterion, SingleEvalResult

logger = logging.getLogger(__name__)


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
    enable_grounding: bool = True
    
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
            enable_grounding=self.enable_grounding,
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
    weighted_avg_score: float
    scores_by_criterion: Dict[str, float]
    num_evaluations: int
    results: List[SingleEvalResult]
    
    @classmethod
    def from_results(
        cls,
        doc_id: str,
        results: List[SingleEvalResult],
        weights: Optional[Dict[str, float]] = None,
    ) -> "SingleEvalSummary":
        """
        Create summary from list of evaluation results.
        
        Args:
            doc_id: Document identifier
            results: List of evaluation results
            weights: Optional criterion weights
            
        Returns:
            Summary with aggregated statistics
        """
        if not results:
            return cls(
                doc_id=doc_id,
                avg_score=0.0,
                weighted_avg_score=0.0,
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
        
        # Calculate weighted average
        if weights:
            weighted_sum = 0.0
            total_weight = 0.0
            for crit, avg in scores_by_criterion.items():
                w = weights.get(crit, 1.0)
                weighted_sum += avg * w
                total_weight += w
            weighted_avg_score = weighted_sum / total_weight if total_weight > 0 else avg_score
        else:
            weighted_avg_score = avg_score
        
        return cls(
            doc_id=doc_id,
            avg_score=avg_score,
            weighted_avg_score=weighted_avg_score,
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
    ) -> SingleEvalSummary:
        """
        Evaluate a single document.
        
        Runs all iterations across all judge models and aggregates results.
        
        Args:
            doc: Document to evaluate
            progress_callback: Optional callback for progress updates
            
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
            weights=self.criteria.weights,
        )
    
    async def evaluate_documents(
        self,
        docs: List[DocumentInput],
        progress_callback: Optional[Callable[[str, int, int, int, int], None]] = None,
    ) -> Dict[str, SingleEvalSummary]:
        """
        Evaluate multiple documents with concurrency control.
        
        Args:
            docs: List of documents to evaluate
            progress_callback: Callback(doc_id, doc_completed, total_docs, eval_completed, total_evals)
            
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
                summary = await self.evaluate_document(doc)
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
        use_weighted: bool = True,
    ) -> List[tuple[str, float]]:
        """
        Rank documents by their evaluation scores.
        
        Args:
            summaries: Dict mapping doc_id to summary
            use_weighted: Use weighted average (True) or simple average (False)
            
        Returns:
            List of (doc_id, score) tuples sorted by score descending
        """
        rankings = []
        for doc_id, summary in summaries.items():
            score = summary.weighted_avg_score if use_weighted else summary.avg_score
            rankings.append((doc_id, score))
        
        rankings.sort(key=lambda x: x[1], reverse=True)
        return rankings
    
    def get_top_n(
        self,
        summaries: Dict[str, SingleEvalSummary],
        n: int,
        use_weighted: bool = True,
    ) -> List[str]:
        """
        Get top N document IDs by score.
        
        Args:
            summaries: Dict mapping doc_id to summary
            n: Number of top documents to return
            use_weighted: Use weighted average
            
        Returns:
            List of top N doc_ids
        """
        rankings = self.rank_documents(summaries, use_weighted)
        return [doc_id for doc_id, _ in rankings[:n]]
