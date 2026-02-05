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
    SourceDocResultResponse,
    SourceDocStatus,
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
        error_message=run.error_message,  # Include error message from DB
        generators=[GeneratorType(g) for g in config["generators"]],
        document_count=len(config["document_ids"]),
        model_count=len(config["models"]),
        iterations=config["iterations"],
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
                pairwise_deviations=pw.get("pairwise_deviations") or {},
                total_cost=pw.get("total_cost", 0.0),
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
                    doc_id=elo["doc_id"],
                    wins=elo["wins"],
                    losses=elo["losses"],
                    elo=elo["rating"],
                ))
            pc_comparisons = []
            for res in (pce.get("results") or []):
                pc_comparisons.append(PairwiseComparison(
                    doc_id_a=res["doc_id_1"],
                    doc_id_b=res["doc_id_2"],
                    winner=res["winner_doc_id"],
                    judge_model=res["model"],
                    reason=res["reason"],
                    score_a=None,
                    score_b=None,
                ))
            post_combine_pairwise = PairwiseResults(
                total_comparisons=pce["total_comparisons"],
                winner_doc_id=pce.get("winner_doc_id"),
                rankings=pc_rankings,
                comparisons=pc_comparisons,
                pairwise_deviations=pce.get("pairwise_deviations") or {},
                total_cost=pce["total_cost"],
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
                # Handle both 'reason' and 'reasoning' field names (backend uses 'reasoning', schema expects 'reason')
                scores = []
                for s in (eval_data.get("scores") or []):
                    score_reason = s.get("reason") or s.get("reasoning") or ""
                    scores.append(CriterionScoreInfo(
                        criterion=s["criterion"],
                        score=int(s["score"]),
                        reason=score_reason,
                    ))
                evaluations.append(JudgeEvaluation(
                    judge_model=eval_data["judge_model"],
                    trial=eval_data["trial"],
                    scores=scores,
                    average_score=eval_data["average_score"],
                ))
            pre_combine_evals_detailed[doc_id] = DocumentEvalDetail(
                evaluations=evaluations,
                overall_average=detail["overall_average"],
            )
    except Exception as e:
        logger.warning(f"Failed to parse pre_combine_evals_detailed for run {run.id}: {e}")
        pre_combine_evals_detailed = {}
    
    post_combine_evals_detailed = {}
    try:
        for doc_id, detail in (results_summary.get("post_combine_evals_detailed") or {}).items():
            evaluations = []
            for eval_data in (detail.get("evaluations") or []):
                # Handle both 'reason' and 'reasoning' field names
                scores = []
                for s in (eval_data.get("scores") or []):
                    score_reason = s.get("reason") or s.get("reasoning") or ""
                    scores.append(CriterionScoreInfo(
                        criterion=s["criterion"],
                        score=int(s["score"]),
                        reason=score_reason,
                    ))
                evaluations.append(JudgeEvaluation(
                    judge_model=eval_data["judge_model"],
                    trial=eval_data["trial"],
                    scores=scores,
                    average_score=eval_data["average_score"],
                ))
            post_combine_evals_detailed[doc_id] = DocumentEvalDetail(
                evaluations=evaluations,
                overall_average=detail["overall_average"],
            )
    except Exception as e:
        logger.warning(f"Failed to parse post_combine_evals_detailed for run {run.id}: {e}")
        post_combine_evals_detailed = {}
    
    # Parse per-source-document results (multi-doc pipeline)
    source_doc_results = {}
    try:
        post_combine_evals = results_summary.get("post_combine_evals") or {}

        def _parse_pairwise_results_maybe_legacy(pw: dict) -> Optional[PairwiseResults]:
            """Parse either GUI-format pairwise results or legacy PairwiseSummary dict.

            Multi-doc pipelines persist PairwiseSummary via dataclass serialization, which
            yields keys like `elo_ratings` and `results`. The GUI expects `rankings` and
            `comparisons`. This function normalizes both.
            """
            if not isinstance(pw, dict):
                return None

            try:
                # Legacy format: { total_comparisons, winner_doc_id, results: [...], elo_ratings: [...] }
                if pw.get("elo_ratings") is not None or pw.get("results") is not None:
                    rankings: list[PairwiseRanking] = []
                    for er in (pw.get("elo_ratings") or []):
                        if isinstance(er, dict):
                            rankings.append(
                                PairwiseRanking(
                                    doc_id=er.get("doc_id", ""),
                                    wins=int(er.get("wins", 0) or 0),
                                    losses=int(er.get("losses", 0) or 0),
                                    elo=float(er.get("rating", 0.0) or 0.0),
                                )
                            )

                    comparisons: list[PairwiseComparison] = []
                    for r in (pw.get("results") or []):
                        if isinstance(r, dict):
                            comparisons.append(
                                PairwiseComparison(
                                    doc_id_a=r["doc_id_1"],
                                    doc_id_b=r["doc_id_2"],
                                    winner=r["winner_doc_id"],
                                    judge_model=r["model"],
                                    reason=r["reason"],
                                    score_a=None,
                                    score_b=None,
                                )
                            )

                    return PairwiseResults(
                        total_comparisons=pw["total_comparisons"],
                        winner_doc_id=pw.get("winner_doc_id"),
                        rankings=rankings,
                        comparisons=comparisons,
                        pairwise_deviations=pw.get("pairwise_deviations") or {},
                    )

                # GUI format: { total_comparisons, winner_doc_id, rankings: [...], comparisons: [...] }
                rankings = [PairwiseRanking(**r) for r in (pw.get("rankings") or [])]
                comparisons = [PairwiseComparison(**c) for c in (pw.get("comparisons") or [])]
                return PairwiseResults(
                    total_comparisons=pw.get("total_comparisons", 0),
                    winner_doc_id=pw.get("winner_doc_id"),
                    rankings=rankings,
                    comparisons=comparisons,
                    pairwise_deviations=pw.get("pairwise_deviations") or {},
                )
            except Exception:
                return None

        for source_doc_id, sdr in (results_summary.get("source_doc_results") or {}).items():
            # Parse generated docs for this source
            sdr_generated_docs = []
            for doc_info in (sdr.get("generated_docs") or []):
                if isinstance(doc_info, dict):
                    parsed_id = doc_info.get("id") or doc_info.get("doc_id") or ""
                    sdr_generated_docs.append(GeneratedDocInfo(
                        id=parsed_id,
                        model=doc_info.get("model", ""),
                        source_doc_id=doc_info.get("source_doc_id", source_doc_id),
                        generator=doc_info.get("generator", ""),
                        iteration=doc_info.get("iteration", 1),
                        cost_usd=doc_info.get("cost_usd"),
                    ))
            
            # Parse pairwise results for this source doc
            sdr_pairwise = None
            if sdr.get("pairwise_results"):
                sdr_pairwise = _parse_pairwise_results_maybe_legacy(sdr["pairwise_results"])
            
            # Parse post-combine pairwise for this source doc
            sdr_post_combine_pairwise = None
            if sdr.get("post_combine_eval_results"):
                sdr_post_combine_pairwise = _parse_pairwise_results_maybe_legacy(sdr["post_combine_eval_results"])
            
            # Parse combined docs - support both singular and plural formats
            sdr_combined_docs: list[GeneratedDocInfo] = []
            sdr_combined_doc = None
            
            # First try combined_docs (array)
            for cd in (sdr.get("combined_docs") or []):
                if isinstance(cd, dict):
                    combined_id = cd.get("id") or cd.get("doc_id") or ""
                    doc_info = GeneratedDocInfo(
                        id=combined_id,
                        model=cd.get("model", ""),
                        source_doc_id=cd.get("source_doc_id", source_doc_id),
                        generator=cd.get("generator", ""),
                        iteration=cd.get("iteration", 1),
                        cost_usd=cd.get("cost_usd"),
                    )
                    sdr_combined_docs.append(doc_info)
            
            # Fallback to singular combined_doc for backward compatibility
            if not sdr_combined_docs and sdr.get("combined_doc"):
                cd = sdr["combined_doc"]
                combined_id = cd.get("id") or cd.get("doc_id") or ""
                sdr_combined_doc = GeneratedDocInfo(
                    id=combined_id,
                    model=cd.get("model", ""),
                    source_doc_id=cd.get("source_doc_id", source_doc_id),
                    generator=cd.get("generator", ""),
                    iteration=cd.get("iteration", 1),
                    cost_usd=cd.get("cost_usd"),
                )
                sdr_combined_docs.append(sdr_combined_doc)
            
            # Set legacy combined_doc to first item for backward compat
            if sdr_combined_docs:
                sdr_combined_doc = sdr_combined_docs[0]
            
            # Parse timeline events for this source doc
            # First try from source_doc_result, then filter from run-level timeline_events
            sdr_timeline = []
            sdr_timeline_raw = sdr.get("timeline_events") or []
            
            # Only use source-doc timeline if it has events, otherwise filter from run-level
            if sdr_timeline_raw and len(sdr_timeline_raw) > 0:
                for te in sdr_timeline_raw:
                    try:
                        sdr_timeline.append(TimelineEvent(**te))
                    except Exception:
                        pass
            else:
                # Filter from run-level timeline events using the same logic as execution.py
                sdr_suffix = source_doc_id.split('-')[-1] if '-' in source_doc_id else source_doc_id
                logger.info(f"[TIMELINE] Filtering for source_doc {source_doc_id[:8]}..., suffix={sdr_suffix}, run-level events={len(timeline_events)}")
                matched_count = 0
                for te in timeline_events:
                    try:
                        # timeline_events are already TimelineEvent objects, not dicts
                        te_source_doc_id = te.details.get("source_doc_id") if te.details else None
                        te_doc_id = te.details.get("doc_id", "") if te.details else ""
                        doc_id_prefix = te_doc_id.split(".")[0] if te_doc_id else None
                        # Match by explicit source_doc_id or if the suffix ends with the prefix
                        if te_source_doc_id == source_doc_id or (doc_id_prefix and sdr_suffix.endswith(doc_id_prefix)):
                            sdr_timeline.append(te)
                            matched_count += 1
                    except Exception as e:
                        logger.warning(f"[TIMELINE] Failed to parse timeline event: {e}")
                logger.info(f"[TIMELINE] Matched {matched_count} events for source_doc {source_doc_id[:8]}...")
            
            # Parse single eval scores - check both possible key names for compatibility
            # execution.py uses dataclass field name "single_eval_results"
            # presets.py was saving as "single_eval_scores"
            sdr_single_eval_scores = {}
            single_eval_data = sdr.get("single_eval_results") or sdr.get("single_eval_scores") or {}
            for doc_id, summary in single_eval_data.items():
                if isinstance(summary, dict):
                    sdr_single_eval_scores[doc_id] = summary.get("avg_score", 0.0)
                elif isinstance(summary, (int, float)):
                    sdr_single_eval_scores[doc_id] = float(summary)
                else:
                    sdr_single_eval_scores[doc_id] = getattr(summary, "avg_score", 0.0)

            # Derive per-source-doc detailed evals from the run-level ACM1 detailed structure.
            # This keeps multi-doc buckets compatible with the heatmap UI without requiring
            # separate persistence for every nested field.
            sdr_single_eval_detailed = {}
            try:
                for gen_doc in sdr_generated_docs:
                    if gen_doc.id in pre_combine_evals_detailed:
                        sdr_single_eval_detailed[gen_doc.id] = pre_combine_evals_detailed[gen_doc.id]
            except Exception:
                sdr_single_eval_detailed = {}

            # Derive per-source-doc post-combine eval scores (multi-judge) from run-level mapping
            sdr_post_combine_eval_scores: dict[str, float] = {}
            try:
                if sdr_combined_doc and sdr_combined_doc.id:
                    raw_scores = post_combine_evals.get(sdr_combined_doc.id) or {}
                    if isinstance(raw_scores, dict):
                        for judge_model, score in raw_scores.items():
                            try:
                                sdr_post_combine_eval_scores[str(judge_model)] = float(score)
                            except Exception:
                                continue
            except Exception:
                sdr_post_combine_eval_scores = {}
            
            # Map status string to enum
            status_str = sdr.get("status", "pending")
            try:
                status = SourceDocStatus(status_str)
            except ValueError:
                status = SourceDocStatus.PENDING
            
            # Extract deviation data - first try top-level field, then reconstruct from summaries
            sdr_eval_deviations = sdr.get("eval_deviations")
            
            # If no top-level deviations, reconstruct from single_eval_results summaries
            # This enables past runs to display deviations that were calculated but not stored at top level
            if not sdr_eval_deviations:
                try:
                    # Get single_eval_results from either key name
                    single_eval_results = sdr.get("single_eval_results") or sdr.get("single_eval_summaries") or {}
                    
                    # Extract deviations from any summary that has them
                    # All summaries should have the same deviation dict (it's calculated once for all docs)
                    for summary_data in single_eval_results.values():
                        if isinstance(summary_data, dict):
                            summary_deviations = summary_data.get("deviations_by_judge_criterion")
                            if summary_deviations:
                                sdr_eval_deviations = summary_deviations
                                break  # All summaries have same deviation dict, so we only need one
                except Exception:
                    pass  # Keep sdr_eval_deviations as None
            
            # Build per-document cost breakdown
            sdr_generated_doc_costs: dict[str, float] = {}
            for doc in sdr_generated_docs:
                if hasattr(doc, 'cost_usd') and doc.cost_usd is not None:
                    sdr_generated_doc_costs[doc.id] = doc.cost_usd
            
            source_doc_results[source_doc_id] = SourceDocResultResponse(
                source_doc_id=source_doc_id,
                source_doc_name=sdr.get("source_doc_name", source_doc_id),
                status=status,
                generated_docs=sdr_generated_docs,
                single_eval_scores=sdr_single_eval_scores,
                single_eval_detailed=sdr_single_eval_detailed,
                pairwise_results=sdr_pairwise,
                winner_doc_id=sdr.get("winner_doc_id"),
                combined_doc=sdr_combined_doc,
                combined_docs=sdr_combined_docs,
                post_combine_eval_scores=sdr_post_combine_eval_scores,
                post_combine_pairwise=sdr_post_combine_pairwise,
                timeline_events=sdr_timeline,
                errors=sdr.get("errors") or [],
                cost_usd=sdr.get("cost_usd", 0.0),
                duration_seconds=sdr.get("duration_seconds", 0.0),
                started_at=sdr.get("started_at"),
                completed_at=sdr.get("completed_at"),
                eval_deviations=sdr_eval_deviations,
                generated_doc_costs=sdr_generated_doc_costs,
            )
    except Exception as e:
        logger.warning(f"Failed to parse source_doc_results for run {run.id}: {e}", exc_info=True)
        source_doc_results = {}
    
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
        error_message=run.error_message,  # Include error message from DB
        generators=[GeneratorType(g) for g in config["generators"]],
        models=models,
        document_ids=config["document_ids"],
        iterations=config["iterations"],
        log_level=config["log_level"],
        gptr_settings=GptrSettings(**config.get("gptr_config")) if config.get("gptr_config") else None,
        evaluation=EvaluationSettings(enabled=config["evaluation_enabled"]),
        pairwise=PairwiseSettings(enabled=config["pairwise_enabled"]),
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
        combined_doc_ids=results_summary.get("combined_doc_ids") or [],
        pre_combine_evals_detailed=pre_combine_evals_detailed,
        post_combine_evals_detailed=post_combine_evals_detailed,
        eval_deviations=results_summary.get("eval_deviations") or {},
        criteria_list=results_summary.get("criteria_list") or [],
        evaluator_list=results_summary.get("evaluator_list") or [],
        timeline_events=timeline_events,
        generation_events=generation_events,
        source_doc_results=source_doc_results,  # NEW: Per-source-document results
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
