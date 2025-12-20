"""
Runs API Routes.

Endpoints for managing evaluation runs (presets, executions).
"""
import logging
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4

from dataclasses import asdict, fields, is_dataclass
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.session import get_db, async_session_factory
from app.infra.db.repositories import RunRepository, ContentRepository
from app.services.run_executor import RunConfig, RunExecutor

# Track active executors for cancellation support
_active_executors: Dict[str, RunExecutor] = {}
from app.adapters.base import GeneratorType as AdapterGeneratorType
from ..schemas.runs import (
    RunCreate,
    RunDetail,
    RunList,
    RunSummary,
    RunProgress,
    RunStatus,
    TaskSummary,
    TaskStatus,
    GeneratorType,
    FpfStats,
)
from ...utils.json_utils import serialize_for_ws
from ...config import get_settings
from ...evaluation.reports.generator import ReportGenerator
from ..websockets import run_ws_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/runs", tags=["runs"])


def _serialize_dataclass(obj: Any) -> Any:
    """
    Recursively convert a dataclass to a dict, serializing datetime objects to ISO strings.
    """
    if obj is None:
        return None
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, (list, tuple)):
        return [_serialize_dataclass(item) for item in obj]
    if isinstance(obj, dict):
        return {k: _serialize_dataclass(v) for k, v in obj.items()}
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _serialize_dataclass(v) for k, v in asdict(obj).items()}
    return obj


async def execute_run_background(run_id: str, config: RunConfig):
    """
    Background task to execute a run and update DB.
    """
    from pathlib import Path
    
    # Set up file logging for this run
    log_dir = Path("logs") / run_id
    log_dir.mkdir(parents=True, exist_ok=True)
    run_log_file = log_dir / "run.log"
    
    # Create a file handler for this run
    file_handler = logging.FileHandler(run_log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    ))
    
    # Add handler to root logger to capture all app logs
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)
    try:
        root_logger.debug(f"Added file handler for run {run_id} -> {run_log_file}")
        # Emit a quick test message to ensure handler is writable
        logger.debug(f"RUN_LOG_TEST start for run {run_id}")
    except Exception:
        logger.exception("Failed to write initial run log test entry")
    
    logger.info(f"Starting background execution for run {run_id}")
    
    try:
        # Create a fresh executor instance for this run so state (eg. cancel)
        # does not leak between runs.
        # Inject ws_manager to avoid circular import issues in stats broadcasting
        executor = RunExecutor(ws_manager=run_ws_manager)
        # Register executor for cancellation support (log previous value)
        prev_executor = _active_executors.get(run_id)
        _active_executors[run_id] = executor
        logger.debug(f"Registered executor for run {run_id}; previous_executor_exists={bool(prev_executor)}")
        
        result = await executor.execute(run_id, config)
        
        # Update run in DB
        async with async_session_factory() as session:
            run_repo = RunRepository(session)
            
            if result.status.value == "completed":
                # Build generated docs list for frontend display
                generated_docs_info = []
                generation_events = []  # ACM1-style generation events
                
                for gen_doc in result.generated_docs:
                    generated_docs_info.append({
                        "id": gen_doc.doc_id,
                        "model": gen_doc.model,
                        "source_doc_id": gen_doc.source_doc_id,
                        "generator": gen_doc.generator.value if hasattr(gen_doc.generator, 'value') else str(gen_doc.generator),
                        "iteration": gen_doc.iteration,
                    })
                    
                    # Add generation event for timeline (include start/end for ACM1 style)
                    generation_events.append({
                        "doc_id": gen_doc.doc_id,
                        "generator": gen_doc.generator.value if hasattr(gen_doc.generator, 'value') else str(gen_doc.generator),
                        "model": gen_doc.model,
                        "source_doc_id": gen_doc.source_doc_id,
                        "iteration": gen_doc.iteration,
                        "duration_seconds": gen_doc.duration_seconds,
                        "cost_usd": gen_doc.cost_usd,
                        "status": "completed",
                        "started_at": gen_doc.started_at.isoformat() if hasattr(gen_doc, 'started_at') and gen_doc.started_at else None,
                        "completed_at": gen_doc.completed_at.isoformat() if hasattr(gen_doc, 'completed_at') and gen_doc.completed_at else None,
                    })
                
                # Add combined docs to generated_docs_info for display
                for combined_doc in (result.combined_docs or []):
                    generated_docs_info.append({
                        "id": combined_doc.doc_id,
                        "model": combined_doc.model,
                        "source_doc_id": combined_doc.source_doc_id,
                        "generator": "combine",  # Mark as combined doc
                        "iteration": 1,
                    })
                
                # Build pre-combine evaluation scores for heatmap display
                # NEW FORMAT: Full criteria-level detail for ACM1-style heatmap
                # { "gen_doc_id": { "evaluations": [...], "overall_average": float }, ... }
                pre_combine_evals = {}
                pre_combine_evals_detailed = {}
                all_criteria = set()  # Collect all criteria names
                all_evaluators = set()  # Collect all evaluator model names
                
                if result.single_eval_results:
                    for gen_doc_id, summary in result.single_eval_results.items():
                        # Skip combined doc evaluations (handle in post_combine_evals)
                        if result.combined_doc and gen_doc_id == result.combined_doc.doc_id:
                            continue
                        
                        # Build detailed evaluations with full criteria breakdown
                        evaluations = []
                        judge_scores = {}
                        for eval_result in summary.results:
                            judge_model = eval_result.model
                            all_evaluators.add(judge_model)
                            
                            # Track for legacy format
                            if judge_model not in judge_scores:
                                judge_scores[judge_model] = []
                            judge_scores[judge_model].append(eval_result.average_score)
                            
                            # Build detailed scores with criteria
                            criteria_scores = []
                            for cs in eval_result.scores:
                                all_criteria.add(cs.criterion)
                                criteria_scores.append({
                                    "criterion": cs.criterion,
                                    "score": cs.score,
                                    "reason": cs.reason,
                                })
                            
                            evaluations.append({
                                "judge_model": judge_model,
                                "trial": eval_result.trial,
                                "scores": criteria_scores,
                                "average_score": eval_result.average_score,
                                "started_at": eval_result.started_at.isoformat() if hasattr(eval_result, 'started_at') and eval_result.started_at else None,
                                "completed_at": eval_result.completed_at.isoformat() if hasattr(eval_result, 'completed_at') and eval_result.completed_at else None,
                                "duration_seconds": eval_result.duration_seconds if hasattr(eval_result, 'duration_seconds') else None,
                            })
                        
                        # Store detailed format
                        pre_combine_evals_detailed[gen_doc_id] = {
                            "evaluations": evaluations,
                            "overall_average": summary.avg_score,
                        }
                        
                        # Legacy format: average scores per judge model
                        pre_combine_evals[gen_doc_id] = {
                            judge: sum(scores) / len(scores)
                            for judge, scores in judge_scores.items()
                        }
                
                # Build post-combine evaluation scores (if combine was enabled)
                post_combine_evals = {}
                post_combine_evals_detailed = {}
                if result.combined_doc and result.single_eval_results:
                    combined_id = result.combined_doc.doc_id
                    if combined_id in result.single_eval_results:
                        summary = result.single_eval_results[combined_id]
                        evaluations = []
                        judge_scores = {}
                        for eval_result in summary.results:
                            judge_model = eval_result.model
                            all_evaluators.add(judge_model)
                            
                            if judge_model not in judge_scores:
                                judge_scores[judge_model] = []
                            judge_scores[judge_model].append(eval_result.average_score)
                            
                            # Build detailed scores with criteria
                            criteria_scores = []
                            for cs in eval_result.scores:
                                all_criteria.add(cs.criterion)
                                criteria_scores.append({
                                    "criterion": cs.criterion,
                                    "score": cs.score,
                                    "reason": cs.reason,
                                })
                            
                            evaluations.append({
                                "judge_model": judge_model,
                                "trial": eval_result.trial,
                                "scores": criteria_scores,
                                "average_score": eval_result.average_score,
                                "started_at": eval_result.started_at.isoformat() if hasattr(eval_result, 'started_at') and eval_result.started_at else None,
                                "completed_at": eval_result.completed_at.isoformat() if hasattr(eval_result, 'completed_at') and eval_result.completed_at else None,
                                "duration_seconds": eval_result.duration_seconds if hasattr(eval_result, 'duration_seconds') else None,
                            })
                        
                        post_combine_evals_detailed[combined_id] = {
                            "evaluations": evaluations,
                            "overall_average": summary.avg_score,
                        }
                        post_combine_evals[combined_id] = {
                            judge: sum(scores) / len(scores)
                            for judge, scores in judge_scores.items()
                        }
                
                # Build pairwise results if available
                pairwise_data = None
                comparisons = []
                if result.pairwise_results:
                    # Build head-to-head comparisons list for ACM1-style matrix
                    for pr in (result.pairwise_results.results or []):
                        comparisons.append({
                            "doc_id_a": pr.doc_id_1,
                            "doc_id_b": pr.doc_id_2,
                            "winner": pr.winner_doc_id,
                            "judge_model": pr.model,
                            "trial": pr.trial,
                            "reason": pr.reason,
                        })
                    
                    pairwise_data = {
                        "total_comparisons": result.pairwise_results.total_comparisons,
                        "winner_doc_id": result.pairwise_results.winner_doc_id,
                        "rankings": [
                            {"doc_id": r.doc_id, "wins": r.wins, "losses": r.losses, "elo": r.rating}
                            for r in (result.pairwise_results.elo_ratings or [])
                        ] if result.pairwise_results.elo_ratings else [],
                        "comparisons": comparisons,  # ACM1-style head-to-head list
                    }
                
                # Legacy eval_scores format for backwards compatibility
                eval_scores = {}
                if result.single_eval_results:
                    for gen_doc_id, summary in result.single_eval_results.items():
                        gen_doc = next((d for d in result.generated_docs if d.doc_id == gen_doc_id), None)
                        if gen_doc:
                            source_doc_id = gen_doc.source_doc_id
                            model = gen_doc.model
                            if source_doc_id not in eval_scores:
                                eval_scores[source_doc_id] = {}
                            eval_scores[source_doc_id][model] = summary.avg_score
                
                # Build timeline events from run execution data
                timeline_events = []
                
                # Add run start event
                if result.started_at:
                    timeline_events.append({
                        "phase": "initialization",
                        "event_type": "start",
                        "description": "Run started",
                        "model": None,
                        "timestamp": result.started_at.isoformat() if result.started_at else None,
                        "duration_seconds": None,
                        "success": True,
                        "details": None,
                    })
                
                # Add generation phase events from generation_events
                for gen_event in generation_events:
                    timeline_events.append({
                        "phase": "generation",
                        "event_type": "generation",
                        "description": f"Generated doc using {gen_event['generator']}",
                        "model": gen_event.get("model"),
                        "timestamp": gen_event.get("started_at"),  # Use actual start time
                        "completed_at": gen_event.get("completed_at"),  # Add completion time
                        "duration_seconds": gen_event.get("duration_seconds"),
                        "success": gen_event.get("status") == "completed",
                        "details": {"doc_id": gen_event.get("doc_id")},
                    })
                
                # Add detailed evaluation events (one per doc per judge model)
                if result.single_eval_results:
                    for doc_id, summary in result.single_eval_results.items():
                        for eval_result in summary.results:
                            timeline_events.append({
                                "phase": "evaluation",
                                "event_type": "single_eval",
                                "description": f"Evaluated {doc_id[:20]}... with {eval_result.model}",
                                "model": eval_result.model,
                                "timestamp": eval_result.started_at.isoformat() if hasattr(eval_result, 'started_at') and eval_result.started_at else None,
                                "completed_at": eval_result.completed_at.isoformat() if hasattr(eval_result, 'completed_at') and eval_result.completed_at else None,
                                "duration_seconds": eval_result.duration_seconds if hasattr(eval_result, 'duration_seconds') else None,
                                "success": True,
                                "details": {
                                    "doc_id": doc_id,
                                    "trial": eval_result.trial,
                                    "average_score": eval_result.average_score,
                                },
                            })
                
                # Add detailed pairwise events
                if result.pairwise_results and result.pairwise_results.results:
                    for pw_result in result.pairwise_results.results:
                        timeline_events.append({
                            "phase": "pairwise",
                            "event_type": "pairwise_eval",
                            "description": f"Compared {pw_result.doc_id_1[:15]}... vs {pw_result.doc_id_2[:15]}...",
                            "model": pw_result.model,
                            "timestamp": pw_result.started_at.isoformat() if hasattr(pw_result, 'started_at') and pw_result.started_at else None,
                            "completed_at": pw_result.completed_at.isoformat() if hasattr(pw_result, 'completed_at') and pw_result.completed_at else None,
                            "duration_seconds": pw_result.duration_seconds if hasattr(pw_result, 'duration_seconds') else None,
                            "success": True,
                            "details": {
                                "doc_id_1": pw_result.doc_id_1,
                                "doc_id_2": pw_result.doc_id_2,
                                "winner": pw_result.winner_doc_id,
                                "trial": pw_result.trial,
                            },
                        })
                
                # Add combination phase events (one for each combined doc)
                if result.combined_docs:
                    for combined_doc in result.combined_docs:
                        timeline_events.append({
                            "phase": "combination",
                            "event_type": "combine",
                            "description": f"Combined documents using {combined_doc.model}",
                            "model": combined_doc.model,
                            "timestamp": combined_doc.started_at.isoformat() if hasattr(combined_doc, 'started_at') and combined_doc.started_at else None,
                            "completed_at": combined_doc.completed_at.isoformat() if hasattr(combined_doc, 'completed_at') and combined_doc.completed_at else None,
                            "duration_seconds": combined_doc.duration_seconds,
                            "success": True,
                            "details": {"combined_doc_id": combined_doc.doc_id},
                        })
                elif result.combined_doc:
                    # Legacy fallback for single combined doc
                    timeline_events.append({
                        "phase": "combination",
                        "event_type": "combine",
                        "description": "Combined documents into final output",
                        "model": result.combined_doc.model,
                        "timestamp": result.combined_doc.started_at.isoformat() if hasattr(result.combined_doc, 'started_at') and result.combined_doc.started_at else None,
                        "completed_at": result.combined_doc.completed_at.isoformat() if hasattr(result.combined_doc, 'completed_at') and result.combined_doc.completed_at else None,
                        "duration_seconds": result.combined_doc.duration_seconds,
                        "success": True,
                        "details": {"combined_doc_id": result.combined_doc.doc_id},
                    })
                
                # Add run completion event
                if result.completed_at:
                    timeline_events.append({
                        "phase": "completion",
                        "event_type": "complete",
                        "description": "Run completed successfully",
                        "model": None,
                        "timestamp": result.completed_at.isoformat() if result.completed_at else None,
                        "duration_seconds": result.duration_seconds,
                        "success": True,
                        "details": None,
                    })
                
                # Log stats before persisting
                logger.info(f"[STATS] Persisting stats to database for run {run_id}: {result.fpf_stats}")
                
                await run_repo.complete(
                    run_id, 
                    results_summary={
                        "winner": result.winner_doc_id,
                        "generated_count": len(result.generated_docs),
                        "eval_count": len(result.single_eval_results or {}),
                        "fpf_stats": result.fpf_stats,
                        # Legacy: first combined doc for backwards compat
                        "combined_doc_id": result.combined_doc.doc_id if result.combined_doc else None,
                        # New: all combined doc IDs
                        "combined_doc_ids": [cd.doc_id for cd in result.combined_docs] if result.combined_docs else [],
                        "post_combine_eval": _serialize_dataclass(result.post_combine_eval_results) if result.post_combine_eval_results else None,
                        "eval_scores": eval_scores,  # Legacy format for backwards compat
                        # New structured format for heatmaps
                        "generated_docs": generated_docs_info,
                        "pre_combine_evals": pre_combine_evals,
                        "post_combine_evals": post_combine_evals,
                        "pairwise": pairwise_data,
                        # ACM1-style detailed format with criteria breakdown
                        "pre_combine_evals_detailed": pre_combine_evals_detailed,
                        "post_combine_evals_detailed": post_combine_evals_detailed,
                        "criteria_list": sorted(list(all_criteria)),
                        "evaluator_list": sorted(list(all_evaluators)),
                        # ACM1-style generation events
                        "generation_events": generation_events,
                        # ACM1-style timeline events for phase visualization
                        "timeline_events": timeline_events,
                    },
                    total_cost_usd=result.total_cost_usd
                )
                logger.info(f"Run {run_id} completed successfully")
            else:
                error_msg = "; ".join(result.errors) if result.errors else "Unknown error"
                await run_repo.fail(run_id, error_message=error_msg)
                logger.error(f"Run {run_id} failed: {error_msg}")
                
    except Exception as e:
        logger.exception(f"Unexpected error executing run {run_id}")
        async with async_session_factory() as session:
            run_repo = RunRepository(session)
            await run_repo.fail(run_id, error_message=str(e))
    finally:
        # Clean up: remove executor from active list
        try:
            popped = _active_executors.pop(run_id, None)
            logger.debug(f"Executor cleanup for run {run_id}; popped={bool(popped)}")
        except Exception:
            logger.exception("Failed to pop active executor")
        # Clean up: remove file handler and flush/close safely
        try:
            file_handler.flush()
        except Exception:
            logger.exception("Failed to flush run file handler")
        try:
            file_handler.close()
        except Exception:
            logger.exception("Failed to close run file handler")
        try:
            root_logger.removeHandler(file_handler)
        except Exception:
            logger.exception("Failed to remove run file handler from root logger")


def _calculate_progress(run) -> RunProgress:
    """Calculate progress for a run.
    
    NOTE: This function requires tasks to be eagerly loaded. Use get_with_tasks()
    or get_all_with_tasks() to fetch runs before calling this.
    """
    # Use getattr with default to avoid lazy loading issues if tasks weren't loaded
    # Check if tasks relationship is loaded to avoid triggering lazy load
    from sqlalchemy.orm import object_session
    from sqlalchemy import inspect
    
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
        # This is a rough estimate if tasks aren't generated yet
        # But for DB model, we might rely on what's in the DB
        # Or just return 0 progress
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


def _to_summary(run) -> RunSummary:
    """Convert DB run to summary response."""
    config = run.config or {}
    return RunSummary(
        id=run.id,
        name=run.title or "Untitled", # DB has title, schema has name
        description=run.description,
        status=run.status,
        generators=[GeneratorType(g) for g in (config.get("generators") or [])],
        document_count=len(config.get("document_ids") or []),
        model_count=len(config.get("models") or []),
        iterations=config.get("iterations", 1),
        progress=_calculate_progress(run),
        total_cost_usd=run.total_cost_usd or 0.0,
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
        tags=config.get("tags") or [],
    )


def _get_fpf_stats_from_summary(run_id: str, results_summary: dict) -> Optional[FpfStats]:
    """Extract FPF stats from results_summary with robust error handling and logging."""
    try:
        stats_data = results_summary.get("fpf_stats")
        if not stats_data:
            logger.debug(f"[STATS] No fpf_stats in results_summary for run {run_id}")
            return None
        
        # Validate it's a dict
        if not isinstance(stats_data, dict):
            logger.warning(f"[STATS] Invalid fpf_stats type for run {run_id}: {type(stats_data)}")
            return None
        
        # Create FpfStats schema object
        fpf_stats = FpfStats(**stats_data)
        logger.debug(f"[STATS] Successfully retrieved fpf_stats for run {run_id}: total={fpf_stats.total_calls} success={fpf_stats.successful_calls}")
        return fpf_stats
        
    except Exception as e:
        logger.error(f"[STATS] Failed to parse fpf_stats for run {run_id}: {e}", exc_info=True)
        return None


def _to_detail(run) -> RunDetail:
    """Convert DB run to detail response."""
    from ..schemas.runs import ModelConfig, GptrSettings, EvaluationSettings, PairwiseSettings, CombineSettings, GeneratedDocInfo, PairwiseResults, PairwiseRanking, DocumentEvalDetail, JudgeEvaluation, CriterionScoreInfo, PairwiseComparison, TimelineEvent, GenerationEvent
    
    config = run.config or {}
    results_summary = run.results_summary or {}
    
    combine_settings = None
    if config.get("config_overrides") and "combine" in config["config_overrides"]:
        combine_settings = CombineSettings(**config["config_overrides"]["combine"])
    
    # Parse generated docs info
    generated_docs = []
    for doc_info in (results_summary.get("generated_docs") or []):
        generated_docs.append(GeneratedDocInfo(**doc_info))
    
    # Parse pairwise results (including comparisons)
    pairwise_results = None
    if results_summary.get("pairwise"):
        pw = results_summary["pairwise"]
        rankings = [PairwiseRanking(**r) for r in (pw.get("rankings") or [])]
        comparisons = [PairwiseComparison(**c) for c in (pw.get("comparisons") or [])]
        pairwise_results = PairwiseResults(
            total_comparisons=pw.get("total_comparisons", 0),
            winner_doc_id=pw.get("winner_doc_id"),
            rankings=rankings,
            comparisons=comparisons,
        )
    
    # Parse post-combine pairwise results (combined doc vs winner)
    post_combine_pairwise = None
    if results_summary.get("post_combine_eval"):
        pce = results_summary["post_combine_eval"]
        # Build rankings from elo_ratings
        pc_rankings = []
        for elo in (pce.get("elo_ratings") or []):
            pc_rankings.append(PairwiseRanking(
                doc_id=elo.get("doc_id", ""),
                wins=elo.get("wins", 0),
                losses=elo.get("losses", 0),
                elo=elo.get("rating", 1000.0),
            ))
        # Build comparisons from results
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
    
    # Parse generation events (ACM1-style)
    generation_events = [
        GenerationEvent(**ge) for ge in (results_summary.get("generation_events") or [])
    ]
    
    # Parse timeline events (ACM1-style)
    timeline_events = [
        TimelineEvent(**te) for te in (results_summary.get("timeline_events") or [])
    ]
    
    # Parse detailed evaluation data (ACM1-style with criteria breakdown)
    pre_combine_evals_detailed = {}
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
    
    post_combine_evals_detailed = {}
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
    
    return RunDetail(
        id=run.id,
        name=run.title or "Untitled",
        description=run.description,
        status=run.status,
        generators=[GeneratorType(g) for g in (config.get("generators") or [])],
        models=[ModelConfig(**m) for m in (config.get("models") or [])],
        document_ids=config.get("document_ids") or [],
        iterations=config.get("iterations", 1),
        log_level=config.get("log_level", "INFO"),  # Include log_level from config
        gptr_settings=GptrSettings(**config.get("gptr_config")) if config.get("gptr_config") else None,
        evaluation=EvaluationSettings(enabled=config.get("evaluation_enabled", False)), # Simplified
        pairwise=PairwiseSettings(enabled=config.get("pairwise_enabled", False)), # Simplified
        combine=combine_settings,
        progress=_calculate_progress(run),
        tasks=[TaskSummary(
            id=t.id,
            name=t.name,
            status=t.status,
            generator=t.generator,
            duration_seconds=t.duration_seconds,
            cost_usd=t.cost_usd,
            error=t.error_message
        ) for t in (run.tasks or [])],
        # Legacy eval_scores format
        eval_scores=results_summary.get("eval_scores") or {},
        winner=results_summary.get("winner"),
        # New structured eval data
        generated_docs=generated_docs,
        pre_combine_evals=results_summary.get("pre_combine_evals") or {},
        post_combine_evals=results_summary.get("post_combine_evals") or {},
        pairwise_results=pairwise_results,
        post_combine_pairwise=post_combine_pairwise,  # Combined doc vs winner pairwise
        combined_doc_id=results_summary.get("combined_doc_id"),
        # ACM1-style detailed eval data with criteria breakdown
        pre_combine_evals_detailed=pre_combine_evals_detailed,
        post_combine_evals_detailed=post_combine_evals_detailed,
        criteria_list=results_summary.get("criteria_list") or [],
        evaluator_list=results_summary.get("evaluator_list") or [],
        # ACM1-style timeline and generation events
        timeline_events=timeline_events,
        generation_events=generation_events,
        total_cost_usd=run.total_cost_usd or 0.0,
        cost_by_model={},  # TODO
        cost_by_document={},  # TODO
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
        total_duration_seconds=None,  # TODO
        tags=config.get("tags") or [],
        fpf_stats=_get_fpf_stats_from_summary(run.id, results_summary),
    )


# ============================================================================
# Endpoints
# ============================================================================

@router.post("", response_model=RunSummary)
async def create_run(
    data: RunCreate,
    db: AsyncSession = Depends(get_db)
) -> RunSummary:
    """
    Create a new run configuration.
    
    The run starts in PENDING status. Call POST /runs/{id}/start to execute.
    If preset_id is provided, the preset's configuration will be loaded.
    """
    from app.infra.db.repositories import PresetRepository
    
    repo = RunRepository(db)
    preset_repo = PresetRepository(db)
    
    # Require a preset_id: runs must be created from an existing preset
    if not data.preset_id:
        raise HTTPException(status_code=400, detail="Runs must be created from an existing preset; provide a valid preset_id")

    preset = await preset_repo.get_by_id(data.preset_id)
    if not preset:
        raise HTTPException(status_code=404, detail=f"Preset {data.preset_id} not found")
    logger.info(f"Loading config from preset: {preset.name} (id={data.preset_id})")
    
    # Use preset values if available, otherwise use request data or defaults
    # Preset has top-level columns: generators, documents, models, fpf_config, gptr_config, etc.
    # But the REAL config is in config_overrides (fpf, gptr, eval, etc.)
    document_ids = data.document_ids or (preset.documents if preset else [])
    generators = (preset.generators if preset and preset.generators else [g.value for g in data.generators])
    
    # Get config_overrides first - this has the real configuration
    # Start from the preset (if any), then let request overrides win
    config_overrides: dict = {}
    if preset and preset.config_overrides:
        config_overrides = dict(preset.config_overrides)
    if getattr(data, "config_overrides", None):
        # Request overrides take precedence over preset
        config_overrides.update(data.config_overrides)
    
    # Get models from config_overrides.fpf or config_overrides.gptr (where they're actually stored)
    models = []
    if preset and config_overrides:
        # Check FPF config for models
        fpf_cfg = config_overrides.get("fpf", {})
        if fpf_cfg.get("enabled") and fpf_cfg.get("selected_models"):
            for model_str in fpf_cfg["selected_models"]:
                parts = model_str.split(":", 1)
                if len(parts) == 2:
                    models.append({"provider": parts[0], "model": parts[1]})
                else:
                    # Handle models without provider prefix (assume openai)
                    models.append({"provider": "openai", "model": model_str})
        # Check GPTR config for models
        gptr_cfg = config_overrides.get("gptr", {})
        if gptr_cfg.get("enabled") and gptr_cfg.get("selected_models"):
            for model_str in gptr_cfg["selected_models"]:
                parts = model_str.split(":", 1)
                if len(parts) == 2:
                    models.append({"provider": parts[0], "model": parts[1]})
                else:
                    models.append({"provider": "openai", "model": model_str})
    if not models:
        models = [m.model_dump() for m in data.models]
    
    # Get settings from config_overrides
    logger.info(f"DEBUG: RunCreate fields: {data.model_dump().keys()}")
    logger.info(f"DEBUG: Has config_overrides? {hasattr(data, 'config_overrides')} | merged keys: {list(config_overrides.keys()) if config_overrides else 'none'}")
    
    general_cfg = {}
    eval_cfg = {}
    pairwise_cfg = {}
    combine_cfg = {}
    fpf_cfg = {}
    gptr_cfg = {}
    concurrency_cfg = {}

    # Safely access config_overrides if it exists
    overrides = config_overrides or {}
    
    if overrides:
        general_cfg = overrides.get("general", {})
        eval_cfg = overrides.get("eval", {})
        pairwise_cfg = overrides.get("pairwise", {})
        combine_cfg = overrides.get("combine", {})
        fpf_cfg = overrides.get("fpf", {})
        gptr_cfg = overrides.get("gptr", {})
        concurrency_cfg = overrides.get("concurrency", {})

    # Construct config dict
    # log_level priority: preset's general_config.log_level > preset.log_level > request override > fallback INFO
    resolved_log_level = general_cfg.get("log_level") or (preset.log_level if preset else None) or data.log_level or "INFO"
    config = {
        "document_ids": document_ids,
        "generators": generators,
        "models": models,
        "iterations": general_cfg.get("iterations") or (preset.iterations if preset else data.iterations),
        "log_level": resolved_log_level,
        "evaluation_enabled": eval_cfg.get("enabled") if eval_cfg.get("enabled") is not None else (preset.evaluation_enabled if preset else data.evaluation.enabled),
        "pairwise_enabled": pairwise_cfg.get("enabled") if pairwise_cfg.get("enabled") is not None else (preset.pairwise_enabled if preset else data.pairwise.enabled),
        "gptr_config": gptr_cfg if gptr_cfg else (data.gptr_settings.model_dump() if data.gptr_settings else None),
        "fpf_config": fpf_cfg if fpf_cfg else (data.fpf_settings.model_dump() if data.fpf_settings else None),
        "tags": data.tags,
        # Content library instruction IDs - check preset's top-level columns first, then config_overrides
        "generation_instructions_id": (preset.generation_instructions_id if preset else None) or overrides.get("generation_instructions_id"),
        "single_eval_instructions_id": (preset.single_eval_instructions_id if preset else None) or overrides.get("single_eval_instructions_id"),
        "pairwise_eval_instructions_id": (preset.pairwise_eval_instructions_id if preset else None) or overrides.get("pairwise_eval_instructions_id"),
        "eval_criteria_id": (preset.eval_criteria_id if preset else None) or overrides.get("eval_criteria_id"),
        "combine_instructions_id": (preset.combine_instructions_id if preset else None) or overrides.get("combine_instructions_id"),
        # Store phase-specific configs with their separate model lists
        "eval_config": eval_cfg,
        "pairwise_config": pairwise_cfg,
        "combine_config": combine_cfg,
        "concurrency_config": concurrency_cfg,
        # Persist full overrides so start_run can still access all phase configs
        "config_overrides": overrides,
    }
    
    # Add/override combine config if present (preserve other overrides)
    if combine_cfg or data.combine:
        existing_overrides = config.get("config_overrides", {}) or {}
        existing_overrides["combine"] = combine_cfg if combine_cfg else data.combine.model_dump()
        config["config_overrides"] = existing_overrides
    
    run = await repo.create(
        title=data.name,
        description=data.description,
        preset_id=data.preset_id,  # Link run to preset
        config=config,
        status=RunStatus.PENDING
    )
    return _to_summary(run)


@router.get("/count")
async def count_runs(
    status: Optional[str] = Query(None, description="Filter by status"),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Return total number of runs (optionally filtered by status)."""
    repo = RunRepository(db)
    total = await repo.count(status=status)
    return {"total": total, "status": status}


@router.get("", response_model=RunList)
async def list_runs(
    status: Optional[str] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
) -> RunList:
    """
    List all runs with pagination.
    """
    repo = RunRepository(db)
    offset = (page - 1) * page_size
    
    # Use get_all_with_tasks to eagerly load tasks and avoid lazy loading errors
    runs = await repo.get_all_with_tasks(limit=page_size, offset=offset, status=status)
    # total = await repo.count() # Need to implement count
    total = 100 # Placeholder
    
    items = [_to_summary(r) for r in runs]
    pages = (total + page_size - 1) // page_size
    
    return RunList(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/{run_id}", response_model=RunDetail)
async def get_run(
    run_id: str,
    db: AsyncSession = Depends(get_db)
) -> RunDetail:
    """
    Get detailed information about a specific run.
    """
    repo = RunRepository(db)
    run = await repo.get_with_tasks(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return _to_detail(run)


@router.delete("/{run_id}")
async def delete_run(
    run_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Delete a run.
    
    Only allowed for runs in PENDING, COMPLETED, FAILED, or CANCELLED status.
    """
    repo = RunRepository(db)
    run = await repo.get_by_id(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    if run.status == RunStatus.RUNNING:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete a running run. Cancel it first."
        )
    
    await repo.delete(run_id)
    return {"status": "deleted", "run_id": run_id}


@router.post("/{run_id}/start")
async def start_run(
    run_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Start executing a run.
    """
    repo = RunRepository(db)
    run = await repo.get_by_id(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    if run.status != RunStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"Can only start PENDING runs, current status: {run.status}"
        )
    # Ensure this run was created from a preset; starting ad-hoc runs is disallowed
    if not run.preset_id:
        raise HTTPException(status_code=400, detail="Cannot start run: run was not created from a preset")

    # Verify the preset still exists
    from app.infra.db.repositories import PresetRepository
    preset_repo = PresetRepository(db)
    preset = await preset_repo.get_by_id(run.preset_id)
    if not preset:
        raise HTTPException(status_code=404, detail=f"Preset {run.preset_id} not found for this run")
    
    # Mark as running
    await repo.start(run_id)
    
    # Build RunConfig from run.config
    run_config = run.config or {}
    
    # Fetch documents from Content Library only (legacy 'documents' table deprecated)
    content_repo = ContentRepository(db)
    document_contents = {}
    doc_ids = run_config.get("document_ids") or []
    
    for doc_id in doc_ids:
        # Only use Content Library (input_document type)
        content = await content_repo.get_by_id(doc_id)
        if content and content.content_type == "input_document":
            logger.info(f"Document found in Content Library: {doc_id} -> {content.name}")
            document_contents[doc_id] = content.body
        else:
            # Document not found in Content Library - skip it
            logger.warning(f"Document {doc_id} not found in Content Library (may be orphaned reference from legacy 'documents' table)")

    # Get phase-specific configs from run_config
    # These contain the separate model lists for each phase
    combine_config = run_config.get("combine_config", {}) or run_config.get("config_overrides", {}).get("combine", {})
    eval_config = run_config.get("eval_config", {}) or run_config.get("config_overrides", {}).get("eval", {})
    pairwise_config = run_config.get("pairwise_config", {}) or run_config.get("config_overrides", {}).get("pairwise", {})
    concurrency_config = run_config.get("concurrency_config", {}) or run_config.get("config_overrides", {}).get("concurrency", {})
    
    # Get FPF instructions - prefer generation_instructions_id from Content Library
    # Fall back to fpf_config.prompt_template if no Content Library item specified
    generation_instructions_id = run_config.get("generation_instructions_id")
    instructions = ""
    if generation_instructions_id:
        content = await content_repo.get_by_id(generation_instructions_id)
        if content:
            instructions = content.body
            logger.info(f"Loaded generation instructions from Content Library: {content.name}")
    
    # Fall back to prompt_template if no Content Library instructions
    if not instructions:
        fpf_config = run_config.get("fpf_config") or run_config.get("config_overrides", {}).get("fpf", {})
        instructions = fpf_config.get("prompt_template", "") if fpf_config else ""
        if instructions:
            logger.info("Using prompt_template from fpf_config as generation instructions")
    
    # Fetch custom instruction content from Content Library if IDs are provided
    single_eval_instructions = None
    pairwise_eval_instructions = None
    eval_criteria = None
    combine_instructions = None
    
    single_eval_id = run_config.get("single_eval_instructions_id")
    if single_eval_id:
        content = await content_repo.get_by_id(single_eval_id)
        if content:
            single_eval_instructions = content.body
            logger.info(f"Loaded single eval instructions from Content Library: {content.name}")
    
    pairwise_eval_id = run_config.get("pairwise_eval_instructions_id")
    if pairwise_eval_id:
        content = await content_repo.get_by_id(pairwise_eval_id)
        if content:
            pairwise_eval_instructions = content.body
            logger.info(f"Loaded pairwise eval instructions from Content Library: {content.name}")
    
    eval_criteria_id = run_config.get("eval_criteria_id")
    if eval_criteria_id:
        content = await content_repo.get_by_id(eval_criteria_id)
        if content:
            eval_criteria = content.body
            logger.info(f"Loaded eval criteria from Content Library: {content.name}")
    
    combine_instructions_id = run_config.get("combine_instructions_id")
    if combine_instructions_id:
        content = await content_repo.get_by_id(combine_instructions_id)
        if content:
            combine_instructions = content.body
            logger.info(f"Loaded combine instructions from Content Library: {content.name}")
    
    executor_config = RunConfig(
        document_ids=list(document_contents.keys()),
        document_contents=document_contents,
        instructions=instructions,
        generators=[AdapterGeneratorType(g) for g in (run_config.get("generators") or ["gptr"])],
        # Format models as "provider:model" strings for proper routing
        models=[f"{m['provider']}:{m['model']}" for m in (run_config.get("models") or [])],
        iterations=run_config.get("iterations", 1),
        enable_single_eval=eval_config.get("enabled", run_config.get("evaluation_enabled", True)),
        enable_pairwise=pairwise_config.get("enabled", run_config.get("pairwise_enabled", False)),
        eval_iterations=eval_config.get("iterations", 1),
        # Get judge models from eval_config.judge_models (already formatted as "provider:model" strings)
        # NO FALLBACK - must be configured in preset's eval_config.judge_models
        eval_judge_models=eval_config.get("judge_models") or [],
        # Per-call eval timeout from GUI eval panel
        eval_timeout=eval_config.get("timeout_seconds", 600),
        # pairwise_top_n is in eval_config, not pairwise_config
        pairwise_top_n=eval_config.get("pairwise_top_n"),
        # Custom evaluation instructions from Content Library
        single_eval_instructions=single_eval_instructions,
        pairwise_eval_instructions=pairwise_eval_instructions,
        eval_criteria=eval_criteria,
        enable_combine=combine_config.get("enabled", False),
        combine_strategy=combine_config.get("strategy", "intelligent_merge"),
        # Get combine models from combine_config.selected_models (already formatted as "provider:model" strings)
        # NO FALLBACK - must be configured in preset's combine_config.selected_models
        combine_models=combine_config.get("selected_models") or [],
        combine_instructions=combine_instructions,
        log_level=run_config.get("log_level", "INFO"),
        # Concurrency settings (from GUI Settings page via concurrency_config)
        # REQUIRED from preset - no fallback defaults
        generation_concurrency=concurrency_config.get("max_concurrent", concurrency_config.get("generation_concurrency")) or 5,
        eval_concurrency=concurrency_config.get("eval_concurrency") or 5,
        request_timeout=concurrency_config.get("request_timeout") or 600,
        max_retries=concurrency_config.get("max_retries") or 3,
        retry_delay=concurrency_config.get("retry_delay") or 2.0,
    )
    
    background_tasks.add_task(execute_run_background, run_id, executor_config)
    
    return {"status": "started", "run_id": run_id}


@router.post("/{run_id}/pause")
async def pause_run(
    run_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Pause a running run.
    """
    repo = RunRepository(db)
    run = await repo.get_by_id(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    if run.status != RunStatus.RUNNING:
        raise HTTPException(
            status_code=400,
            detail=f"Can only pause RUNNING runs, current status: {run.status}"
        )
    
    await repo.update(run_id, status=RunStatus.PAUSED)
    return {"status": "paused", "run_id": run_id}


@router.post("/{run_id}/resume")
async def resume_run(
    run_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Resume a paused run.
    """
    repo = RunRepository(db)
    run = await repo.get_by_id(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    if run.status != RunStatus.PAUSED:
        raise HTTPException(
            status_code=400,
            detail=f"Can only resume PAUSED runs, current status: {run.status}"
        )
    
    await repo.update(run_id, status=RunStatus.RUNNING)
    return {"status": "running", "run_id": run_id}


@router.post("/{run_id}/cancel")
async def cancel_run(
    run_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Cancel a running or paused run.
    
    This will:
    1. Set the _cancelled flag on the executor (if running)
    2. Update the run status in the database
    
    Note: The running task will stop at the next checkpoint
    (between generations/evaluations).
    """
    repo = RunRepository(db)
    run = await repo.get_by_id(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    if run.status not in (RunStatus.RUNNING, RunStatus.PAUSED, RunStatus.PENDING):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel run in status: {run.status}"
        )
    
    # Signal the executor to stop (if it's running)
    executor = _active_executors.get(run_id)
    if executor:
        logger.info(f"Signaling cancellation for run {run_id}")
        executor.cancel()
    else:
        logger.info(f"No active executor found for run {run_id}, just updating status")
    
    await repo.update(run_id, status=RunStatus.CANCELLED, completed_at=datetime.utcnow())
    return {"status": "cancelled", "run_id": run_id}


@router.websocket("/ws/run/{run_id}")
async def websocket_run_updates(websocket: WebSocket, run_id: str):
    """
    WebSocket endpoint for real-time run updates.
    Clients receive the full run state whenever it changes.
    """
    await run_ws_manager.connect(websocket, run_id)
    try:
        # TODO: Fetch initial state from DB
        # For now, just keep connection open
        while True:
            try:
                await websocket.receive_text()
            except WebSocketDisconnect:
                break
            except Exception:
                break

    except WebSocketDisconnect:
        pass
    finally:
        run_ws_manager.disconnect(websocket, run_id)


@router.get("/{run_id}/report")
async def get_run_report(
    run_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Generate and download the HTML report for a run.
    Includes the Evaluation Timeline Chart.
    """
    repo = RunRepository(db)
    run = await repo.get_with_tasks(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    settings = get_settings()
    generator = ReportGenerator(settings.artifacts_dir)
    
    try:
        # Generate report (run is both config and data)
        run_data = _to_detail(run).model_dump()
        report_path = generator.generate_html_report(run, run_data)
        return FileResponse(report_path)
    except Exception as e:
        logger.error(f"Failed to generate report for run {run_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")


@router.get("/{run_id}/logs")
async def get_run_logs(
    run_id: str,
    lines: int = Query(100, ge=1, le=10000, description="Number of lines to return"),
    offset: int = Query(0, ge=0, description="Line offset from start"),
    include_fpf: bool = Query(False, description="Include FPF output log (VERBOSE mode only)"),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Get run logs with pagination.
    
    Returns log lines from the run's log files.
    For VERBOSE mode runs, can also include FPF subprocess output.
    """
    from pathlib import Path
    
    repo = RunRepository(db)
    run = await repo.get_by_id(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    log_dir = Path("logs") / run_id
    
    # Read main run log
    run_log_file = log_dir / "run.log"
    log_lines = []
    total_lines = 0
    
    if run_log_file.exists():
        try:
            all_lines = run_log_file.read_text(encoding="utf-8").splitlines()
            total_lines = len(all_lines)
            log_lines = all_lines[offset:offset + lines]
        except Exception as e:
            logger.warning(f"Failed to read run log: {e}")
    
    # Optionally include FPF output (for VERBOSE mode)
    fpf_lines = []
    fpf_available = False
    
    fpf_log_file = log_dir / "fpf_output.log"
    if fpf_log_file.exists():
        fpf_available = True
        if include_fpf:
            try:
                fpf_content = fpf_log_file.read_text(encoding="utf-8").splitlines()
                # Return last 100 lines of FPF output
                fpf_lines = fpf_content[-100:] if len(fpf_content) > 100 else fpf_content
            except Exception as e:
                logger.warning(f"Failed to read FPF log: {e}")
    
    # Get run config to check log level
    run_config = run.config or {}
    log_level = run_config.get("log_level", "INFO")
    
    return {
        "run_id": run_id,
        "log_level": log_level,
        "total_lines": total_lines,
        "offset": offset,
        "lines": log_lines,
        "fpf_available": fpf_available,
        "fpf_lines": fpf_lines if include_fpf else None,
    }


@router.get("/{run_id}/generated/{doc_id:path}")
async def get_generated_doc_content(
    run_id: str,
    doc_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Get the content of a generated document.
    
    Returns the markdown content of a generated or combined document.
    Documents are stored in logs/{run_id}/generated/{doc_id}.md
    """
    from pathlib import Path
    
    repo = RunRepository(db)
    run = await repo.get_by_id(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    # Sanitize doc_id for filename (same as when saving)
    safe_doc_id = doc_id.replace(':', '_').replace('/', '_').replace('\\', '_')
    file_path = Path("logs") / run_id / "generated" / f"{safe_doc_id}.md"
    
    if not file_path.exists():
        raise HTTPException(
            status_code=404, 
            detail=f"Generated document not found. The run may have been executed before content saving was enabled."
        )
    
    try:
        content = file_path.read_text(encoding="utf-8")
        return {
            "run_id": run_id,
            "doc_id": doc_id,
            "content": content,
            "content_length": len(content),
        }
    except Exception as e:
        logger.error(f"Failed to read generated doc {doc_id} for run {run_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to read document: {str(e)}")
