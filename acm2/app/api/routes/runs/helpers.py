"""
Helper functions for run data transformation.

Contains serialization and conversion utilities for runs.
"""
import logging
from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import inspect

from ...schemas.runs import (
    RunDetail,
    RunProgress,
    RunSummary,
    RunStatus,
    TaskSummary,
    TaskStatus,
    GeneratorType,
    FpfStats,
    ModelConfig,
    GptrSettings,
    EvaluationSettings,
    PairwiseSettings,
    CombineSettings,
    GeneratedDocInfo,
    PairwiseResults,
    PairwiseRanking,
    DocumentEvalDetail,
    JudgeEvaluation,
    CriterionScoreInfo,
    PairwiseComparison,
    TimelineEvent,
    GenerationEvent,
)

logger = logging.getLogger(__name__)


def serialize_dataclass(obj: Any) -> Any:
    """
    Recursively convert a dataclass to a dict, serializing datetime objects to ISO strings.
    """
    if obj is None:
        return None
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, (list, tuple)):
        return [serialize_dataclass(item) for item in obj]
    if isinstance(obj, dict):
        return {k: serialize_dataclass(v) for k, v in obj.items()}
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: serialize_dataclass(v) for k, v in asdict(obj).items()}
    return obj


def calculate_progress(run) -> RunProgress:
    """Calculate progress for a run.
    
    NOTE: This function requires tasks to be eagerly loaded. Use get_with_tasks()
    or get_all_with_tasks() to fetch runs before calling this.
    """
    # Check if tasks is loaded without triggering a query
    insp = inspect(run)
    if 'tasks' not in insp.dict:
        # Tasks not loaded, return estimate from run's stored counts
        return RunProgress(
            total_tasks=run.total_tasks or 0,
            completed_tasks=run.completed_tasks or 0,
            running_tasks=0,
            failed_tasks=run.failed_tasks or 0,
            pending_tasks=max(0, (run.total_tasks or 0) - (run.completed_tasks or 0) - (run.failed_tasks or 0)),
            progress_percent=((run.completed_tasks or 0) / run.total_tasks * 100) if run.total_tasks else 0.0,
        )
    
    tasks = run.tasks or []
    total = len(tasks)
    
    # If no tasks yet, estimate from config
    if not tasks:
        return RunProgress(
            total_tasks=0,
            completed_tasks=0,
            running_tasks=0,
            failed_tasks=0,
            pending_tasks=0,
            progress_percent=0.0,
        )
    
    completed = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)
    running = sum(1 for t in tasks if t.status == TaskStatus.RUNNING)
    failed = sum(1 for t in tasks if t.status == TaskStatus.FAILED)
    pending = total - completed - running - failed
    
    return RunProgress(
        total_tasks=total,
        completed_tasks=completed,
        running_tasks=running,
        failed_tasks=failed,
        pending_tasks=pending,
        progress_percent=(completed / total * 100) if total > 0 else 0.0,
    )


def to_summary(run) -> RunSummary:
    """Convert DB run to summary response."""
    config = run.config or {}
    return RunSummary(
        id=run.id,
        name=run.title or "Untitled",
        description=run.description,
        status=run.status,
        generators=[GeneratorType(g) for g in (config.get("generators") or [])],
        document_count=len(config.get("document_ids") or []),
        model_count=len(config.get("models") or []),
        iterations=config.get("iterations", 1),
        progress=calculate_progress(run),
        total_cost_usd=run.total_cost_usd or 0.0,
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
        tags=config.get("tags") or [],
    )


def get_fpf_stats_from_summary(run_id: str, results_summary: dict) -> Optional[FpfStats]:
    """Extract FPF stats from results_summary with robust error handling and logging."""
    try:
        stats_data = results_summary.get("fpf_stats")
        if not stats_data:
            logger.debug(f"[STATS] No fpf_stats in results_summary for run {run_id}")
            return None
        
        if not isinstance(stats_data, dict):
            logger.warning(f"[STATS] Invalid fpf_stats type for run {run_id}: {type(stats_data)}")
            return None
        
        fpf_stats = FpfStats(**stats_data)
        logger.debug(f"[STATS] Successfully retrieved fpf_stats for run {run_id}: total={fpf_stats.total_calls} success={fpf_stats.successful_calls}")
        return fpf_stats
        
    except Exception as e:
        logger.error(f"[STATS] Failed to parse fpf_stats for run {run_id}: {e}", exc_info=True)
        return None


def to_detail(run) -> RunDetail:
    """Convert DB run to detail response."""
    config = run.config or {}
    results_summary = run.results_summary or {}
    
    # Debug logging for generated_docs issue
    logger.info(f"[to_detail] run_id={run.id} results_summary keys: {list(results_summary.keys())}")
    logger.info(f"[to_detail] run_id={run.id} generated_docs raw: {results_summary.get('generated_docs')}")
    
    combine_settings = None
    if config.get("config_overrides") and "combine" in config["config_overrides"]:
        combine_settings = CombineSettings(**config["config_overrides"]["combine"])
    
    # Parse generated docs info
    generated_docs = []
    try:
        for doc_info in (results_summary.get("generated_docs") or []):
            generated_docs.append(GeneratedDocInfo(**doc_info))
        logger.info(f"[to_detail] run_id={run.id} parsed {len(generated_docs)} generated_docs")
    except Exception as e:
        logger.warning(f"Failed to parse generated_docs for run {run.id}: {e}")
        generated_docs = []
    
    # Parse pairwise results (including comparisons)
    pairwise_results = None
    try:
        pw = results_summary.get("pairwise_results") or results_summary.get("pairwise")
        if pw:
            rankings = [PairwiseRanking(**r) for r in (pw.get("rankings") or [])]
            comparisons = [PairwiseComparison(**c) for c in (pw.get("comparisons") or [])]
            pairwise_results = PairwiseResults(
                total_comparisons=pw.get("total_comparisons", 0),
                winner_doc_id=pw.get("winner_doc_id"),
                rankings=rankings,
                comparisons=comparisons,
            )
    except Exception as e:
        logger.warning(f"Failed to parse pairwise for run {run.id}: {e}")
        pairwise_results = None
    
    # Parse post-combine pairwise results (combined doc vs winner)
    post_combine_pairwise = None
    try:
        if results_summary.get("post_combine_eval"):
            pce = results_summary["post_combine_eval"]
            pc_rankings = []
            for elo in (pce.get("elo_ratings") or []):
                pc_rankings.append(PairwiseRanking(
                    doc_id=elo.get("doc_id", ""),
                    wins=elo.get("wins", 0),
                    losses=elo.get("losses", 0),
                    elo=elo.get("rating", 1000.0),
                ))
            pc_comparisons = []
            for res in (pce.get("results") or []):
                pc_comparisons.append(PairwiseComparison(
                    doc_id_a=res.get("doc_id_1", ""),
                    doc_id_b=res.get("doc_id_2", ""),
                    winner=res.get("winner_doc_id", ""),
                    judge_model=res.get("model", ""),
                    reason=res.get("reason", ""),
                    score_a=None,
                    score_b=None,
                ))
            post_combine_pairwise = PairwiseResults(
                total_comparisons=pce.get("total_comparisons", 0),
                winner_doc_id=pce.get("winner_doc_id"),
                rankings=pc_rankings,
                comparisons=pc_comparisons,
            )
    except Exception as e:
        logger.warning(f"Failed to parse post_combine_eval for run {run.id}: {e}")
        post_combine_pairwise = None
    
    # Parse generation events (ACM1-style)
    generation_events = []
    try:
        generation_events = [
            GenerationEvent(**ge) for ge in (results_summary.get("generation_events") or [])
        ]
    except Exception as e:
        logger.warning(f"Failed to parse generation_events for run {run.id}: {e}")
        generation_events = []
    
    # Parse timeline events (ACM1-style)
    timeline_events = []
    try:
        timeline_events = [
            TimelineEvent(**te) for te in (results_summary.get("timeline_events") or [])
        ]
    except Exception as e:
        logger.warning(f"Failed to parse timeline_events for run {run.id}: {e}")
        timeline_events = []
    
    # Parse detailed evaluation data (ACM1-style with criteria breakdown)
    pre_combine_evals_detailed = {}
    try:
        for doc_id, detail in (results_summary.get("pre_combine_evals_detailed") or {}).items():
            evaluations = []
            for eval_data in (detail.get("evaluations") or []):
                scores = [CriterionScoreInfo(**s) for s in (eval_data.get("scores") or [])]
                evaluations.append(JudgeEvaluation(
                    judge_model=eval_data.get("judge_model", ""),
                    trial=eval_data.get("trial", 0),
                    scores=scores,
                    average_score=eval_data.get("average_score", 0.0),
                ))
            pre_combine_evals_detailed[doc_id] = DocumentEvalDetail(
                evaluations=evaluations,
                overall_average=detail.get("overall_average", 0.0),
            )
    except Exception as e:
        logger.warning(f"Failed to parse pre_combine_evals_detailed for run {run.id}: {e}")
        pre_combine_evals_detailed = {}
    
    post_combine_evals_detailed = {}
    try:
        for doc_id, detail in (results_summary.get("post_combine_evals_detailed") or {}).items():
            evaluations = []
            for eval_data in (detail.get("evaluations") or []):
                scores = [CriterionScoreInfo(**s) for s in (eval_data.get("scores") or [])]
                evaluations.append(JudgeEvaluation(
                    judge_model=eval_data.get("judge_model", ""),
                    trial=eval_data.get("trial", 0),
                    scores=scores,
                    average_score=eval_data.get("average_score", 0.0),
                ))
            post_combine_evals_detailed[doc_id] = DocumentEvalDetail(
                evaluations=evaluations,
                overall_average=detail.get("overall_average", 0.0),
            )
    except Exception as e:
        logger.warning(f"Failed to parse post_combine_evals_detailed for run {run.id}: {e}")
        post_combine_evals_detailed = {}
    
    # Parse models safely
    models = []
    try:
        models = [ModelConfig(**m) for m in (config.get("models") or [])]
    except Exception as e:
        logger.warning(f"Failed to parse models for run {run.id}: {e}")
        models = []
    
    return RunDetail(
        id=run.id,
        name=run.title or "Untitled",
        description=run.description,
        status=run.status,
        generators=[GeneratorType(g) for g in (config.get("generators") or [])],
        models=models,
        document_ids=config.get("document_ids") or [],
        iterations=config.get("iterations", 1),
        log_level=config.get("log_level", "INFO"),
        gptr_settings=GptrSettings(**config.get("gptr_config")) if config.get("gptr_config") else None,
        evaluation=EvaluationSettings(enabled=config.get("evaluation_enabled", False)),
        pairwise=PairwiseSettings(enabled=config.get("pairwise_enabled", False)),
        combine=combine_settings,
        progress=calculate_progress(run),
        tasks=[TaskSummary(
            id=t.id,
            name=t.name,
            status=t.status,
            generator=t.generator,
            duration_seconds=t.duration_seconds,
            cost_usd=t.cost_usd,
            error=t.error_message
        ) for t in (run.tasks or [])],
        eval_scores=results_summary.get("eval_scores") or {},
        winner=results_summary.get("winner"),
        generated_docs=generated_docs,
        pre_combine_evals=results_summary.get("pre_combine_evals") or {},
        post_combine_evals=results_summary.get("post_combine_evals") or {},
        pairwise_results=pairwise_results,
        post_combine_pairwise=post_combine_pairwise,
        combined_doc_id=results_summary.get("combined_doc_id"),
        pre_combine_evals_detailed=pre_combine_evals_detailed,
        post_combine_evals_detailed=post_combine_evals_detailed,
        criteria_list=results_summary.get("criteria_list") or [],
        evaluator_list=results_summary.get("evaluator_list") or [],
        timeline_events=timeline_events,
        generation_events=generation_events,
        total_cost_usd=run.total_cost_usd or 0.0,
        cost_by_model={},
        cost_by_document={},
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
        total_duration_seconds=None,
        tags=config.get("tags") or [],
        fpf_stats=get_fpf_stats_from_summary(run.id, results_summary),
    )
