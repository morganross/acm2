"""
Run lifecycle execution control.

Endpoints for starting, pausing, resuming, and cancelling runs.
"""
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.session import get_db, async_session_factory
from app.infra.db.repositories import RunRepository, ContentRepository
from app.services.run_executor import RunConfig, RunExecutor
from app.adapters.base import GeneratorType as AdapterGeneratorType
from app.utils.logging_utils import get_run_logger
from app.evaluation.models import SingleEvalResult

from ...schemas.runs import RunStatus
from ...websockets import run_ws_manager
from .helpers import serialize_dataclass

logger = logging.getLogger(__name__)
router = APIRouter()

# Track active executors for cancellation support
_active_executors: Dict[str, RunExecutor] = {}


async def execute_run_background(run_id: str, config: RunConfig):
    """
    Background task to execute a run and update DB.
    """
    # Set up file logging for this run
    log_dir = Path("logs") / run_id
    run_log_file = log_dir / "run.log"
    
    # Create private run logger using the preset-provided log level only
    if not hasattr(config, "log_level") or config.log_level is None:
        raise ValueError("log_level missing from run config; must be set by preset")
    log_level = config.log_level
    run_logger = get_run_logger(run_id, run_log_file, log_level)
    
    run_logger.info(f"Starting background execution for run {run_id} with level {log_level}")
    
    try:
        # Create a fresh executor instance for this run
        executor = RunExecutor(ws_manager=run_ws_manager, run_logger=run_logger)
        prev_executor = _active_executors.get(run_id)
        _active_executors[run_id] = executor
        logger.debug(f"Registered executor for run {run_id}; previous_executor_exists={bool(prev_executor)}")
        
        # Set up incremental DB save callback for evaluations
        # Shared state for accumulating results (protected by lock)
        db_lock = asyncio.Lock()
        pre_combine_evals_detailed_incremental = {}
        generated_docs_incremental = []  # Track generated docs for incremental save
        # Track evaluator and criterion sets so the UI can render per-judge, per-criterion badges while the run is live
        all_evaluators_incremental: set[str] = set()
        all_criteria_incremental: set[str] = set()
        eval_count = 0
        gen_count = 0
        
        async def on_gen_complete(doc_id: str, model: str, generator: str, source_doc_id: str, iteration: int):
            """Callback fired after each document generation - writes generated_docs to DB immediately."""
            nonlocal gen_count
            
            logger.info(f"[on_gen_complete] CALLED: doc_id={doc_id}, model={model}, generator={generator}")
            
            async with db_lock:
                gen_count += 1
                
                # Build the doc info
                doc_info = {
                    "id": doc_id,
                    "model": model,
                    "source_doc_id": source_doc_id,
                    "generator": generator,
                    "iteration": iteration,
                }
                generated_docs_incremental.append(doc_info)
                logger.info(f"[on_gen_complete] generated_docs_incremental now has {len(generated_docs_incremental)} items")
                
                # Write to DB using append method (safe against race conditions)
                async with async_session_factory() as session:
                    repo = RunRepository(session)
                    result = await repo.append_generated_doc(run_id, doc_info)
                    if result:
                        logger.info(f"[on_gen_complete] Appended to DB: generated_docs count now {len(result.results_summary.get('generated_docs', []))}")
                    else:
                        logger.warning(f"[on_gen_complete] Run {run_id} not found in DB!")
                
                logger.info(f"[DB] Saved gen #{gen_count}: {doc_id} | {model}")
        
        async def on_eval_complete(doc_id: str, judge_model: str, trial: int, result: SingleEvalResult):
            """Callback fired after each individual judge evaluation - writes to DB immediately."""
            nonlocal eval_count
            
            async with db_lock:
                eval_count += 1
                
                # Initialize doc entry if needed
                if doc_id not in pre_combine_evals_detailed_incremental:
                    pre_combine_evals_detailed_incremental[doc_id] = {
                        "evaluations": [],
                        "overall_average": 0.0,
                    }
                
                # Add this evaluation
                eval_entry = {
                    "judge_model": result.model,
                    "trial": trial,
                    "scores": [{"criterion": s.criterion, "score": s.score, "reason": s.reason} for s in result.scores],
                    "average_score": result.average_score,
                }
                pre_combine_evals_detailed_incremental[doc_id]["evaluations"].append(eval_entry)
                # Track evaluators and criteria for incremental UI rendering
                all_evaluators_incremental.add(result.model)
                for s in result.scores:
                    all_criteria_incremental.add(s.criterion)
                
                # Recalculate overall average for this doc
                all_avgs = [e["average_score"] for e in pre_combine_evals_detailed_incremental[doc_id]["evaluations"]]
                pre_combine_evals_detailed_incremental[doc_id]["overall_average"] = sum(all_avgs) / len(all_avgs) if all_avgs else 0.0
                
                # Build pre_combine_evals (criterion -> score mapping)
                pre_combine_evals = {}
                for d_id, details in pre_combine_evals_detailed_incremental.items():
                    criterion_scores = {}
                    for ev in details["evaluations"]:
                        for sc in ev["scores"]:
                            crit = sc["criterion"]
                            if crit not in criterion_scores:
                                criterion_scores[crit] = []
                            criterion_scores[crit].append(sc["score"])
                    pre_combine_evals[d_id] = {c: sum(s)/len(s) for c, s in criterion_scores.items()}
                
                # Write to DB
                async with async_session_factory() as session:
                    repo = RunRepository(session)
                    run_fresh = await repo.get_by_id(run_id)
                    if run_fresh:
                        results_summary_updated = dict(run_fresh.results_summary or {})
                        results_summary_updated["pre_combine_evals"] = pre_combine_evals
                        results_summary_updated["pre_combine_evals_detailed"] = pre_combine_evals_detailed_incremental
                        # Persist evaluator/criteria lists incrementally so the frontend can render per-judge, per-criterion badges before completion
                        results_summary_updated["evaluator_list"] = sorted(list(all_evaluators_incremental))
                        results_summary_updated["criteria_list"] = sorted(list(all_criteria_incremental))
                        await repo.update(run_id, results_summary=results_summary_updated)
                
                logger.info(f"[DB] Saved eval #{eval_count}: {doc_id} | {judge_model} trial={trial} avg={result.average_score:.2f}")
        
        # Attach callbacks to config
        config.on_gen_complete = on_gen_complete
        config.on_eval_complete = on_eval_complete
        
        result = await executor.execute(run_id, config)
        
        # Update run in DB
        async with async_session_factory() as session:
            run_repo = RunRepository(session)
            
            if result.status.value == "completed":
                # Build generated docs list for frontend display
                generated_docs_info = []
                generation_events = []
                
                for gen_doc in result.generated_docs:
                    generated_docs_info.append({
                        "id": gen_doc.doc_id,
                        "model": gen_doc.model,
                        "source_doc_id": gen_doc.source_doc_id,
                        "generator": gen_doc.generator.value if hasattr(gen_doc.generator, 'value') else str(gen_doc.generator),
                        "iteration": gen_doc.iteration,
                    })
                    
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
                
                # Add combined docs to generated_docs_info
                for combined_doc in (result.combined_docs or []):
                    generated_docs_info.append({
                        "id": combined_doc.doc_id,
                        "model": combined_doc.model,
                        "source_doc_id": combined_doc.source_doc_id,
                        "generator": "combine",
                        "iteration": 1,
                    })
                
                # Build pre-combine evaluation scores
                pre_combine_evals = {}
                pre_combine_evals_detailed = {}
                all_criteria = set()
                all_evaluators = set()
                
                if result.single_eval_results:
                    for gen_doc_id, summary in result.single_eval_results.items():
                        combined_doc_ids = [d.doc_id for d in (result.combined_docs or [])]
                        if gen_doc_id in combined_doc_ids:
                            continue
                        
                        evaluations = []
                        judge_scores = {}
                        for eval_result in summary.results:
                            judge_model = eval_result.model
                            all_evaluators.add(judge_model)
                            
                            if judge_model not in judge_scores:
                                judge_scores[judge_model] = []
                            judge_scores[judge_model].append(eval_result.average_score)
                            
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
                        
                        pre_combine_evals_detailed[gen_doc_id] = {
                            "evaluations": evaluations,
                            "overall_average": summary.avg_score,
                        }
                        
                        pre_combine_evals[gen_doc_id] = {
                            judge: sum(scores) / len(scores)
                            for judge, scores in judge_scores.items()
                        }
                
                # Build post-combine evaluation scores
                post_combine_evals = {}
                post_combine_evals_detailed = {}
                if result.combined_docs and result.single_eval_results:
                    for combined_doc in result.combined_docs:
                        combined_id = combined_doc.doc_id
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
                
                # Build pairwise results
                pairwise_data = None
                comparisons = []
                if result.pairwise_results:
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
                        "comparisons": comparisons,
                    }
                
                # Legacy eval_scores format
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
                
                # Build timeline events
                timeline_events = []
                
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
                
                for gen_event in generation_events:
                    timeline_events.append({
                        "phase": "generation",
                        "event_type": "generation",
                        "description": f"Generated doc using {gen_event['generator']}",
                        "model": gen_event.get("model"),
                        "timestamp": gen_event.get("started_at"),
                        "completed_at": gen_event.get("completed_at"),
                        "duration_seconds": gen_event.get("duration_seconds"),
                        "success": gen_event.get("status") == "completed",
                        "details": {"doc_id": gen_event.get("doc_id")},
                    })
                
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
                
                logger.info(f"[STATS] Persisting stats to database for run {run_id}: {result.fpf_stats}")
                
                await run_repo.complete(
                    run_id, 
                    results_summary={
                        "winner": result.winner_doc_id,
                        "generated_count": len(result.generated_docs),
                        "eval_count": len(result.single_eval_results or {}),
                        "fpf_stats": result.fpf_stats,
                        "combined_doc_id": result.combined_docs[0].doc_id if result.combined_docs else None,
                        "combined_doc_ids": [cd.doc_id for cd in result.combined_docs] if result.combined_docs else [],
                        "post_combine_eval": serialize_dataclass(result.post_combine_eval_results) if result.post_combine_eval_results else None,
                        "eval_scores": eval_scores,
                        "generated_docs": generated_docs_info,
                        "pre_combine_evals": pre_combine_evals,
                        "post_combine_evals": post_combine_evals,
                        "pairwise": pairwise_data,
                        "pre_combine_evals_detailed": pre_combine_evals_detailed,
                        "post_combine_evals_detailed": post_combine_evals_detailed,
                        "criteria_list": sorted(list(all_criteria)),
                        "evaluator_list": sorted(list(all_evaluators)),
                        "generation_events": generation_events,
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
        try:
            popped = _active_executors.pop(run_id, None)
            logger.debug(f"Executor cleanup for run {run_id}; popped={bool(popped)}")
        except Exception:
            logger.exception("Failed to pop active executor")
        if run_logger:
            for handler in run_logger.handlers:
                try:
                    handler.flush()
                    handler.close()
                except Exception:
                    logger.exception("Failed to close run logger handler")


@router.post("/runs/{run_id}/start")
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
    
    if not run.preset_id:
        raise HTTPException(status_code=400, detail="Cannot start run: run was not created from a preset")

    from app.infra.db.repositories import PresetRepository
    preset_repo = PresetRepository(db)
    preset = await preset_repo.get_by_id(run.preset_id)
    if not preset:
        raise HTTPException(status_code=404, detail=f"Preset {run.preset_id} not found for this run")
    
    # NOTE: repo.start(run_id) is called AFTER all validation succeeds (before background task)
    
    run_config = run.config or {}
    
    # Fetch documents from Content Library
    content_repo = ContentRepository(db)
    document_contents = {}
    doc_ids = run_config.get("document_ids") or []
    
    for doc_id in doc_ids:
        content = await content_repo.get_by_id(doc_id)
        if content and content.content_type == "input_document":
            logger.info(f"Document found in Content Library: {doc_id} -> {content.name}")
            document_contents[doc_id] = content.body
        else:
            logger.warning(f"Document {doc_id} not found in Content Library")

    # Get phase-specific configs
    combine_config = run_config.get("combine_config", {}) or run_config.get("config_overrides", {}).get("combine", {})
    eval_config = run_config.get("eval_config", {}) or run_config.get("config_overrides", {}).get("eval", {})
    pairwise_config = run_config.get("pairwise_config", {}) or run_config.get("config_overrides", {}).get("pairwise", {})
    concurrency_config = run_config.get("concurrency_config", {}) or run_config.get("config_overrides", {}).get("concurrency", {})
    fpf_config = run_config.get("fpf_config", {}) or run_config.get("config_overrides", {}).get("fpf", {})
    gptr_config = run_config.get("gptr_config", {}) or run_config.get("config_overrides", {}).get("gptr", {})
    dr_config = run_config.get("dr_config", {}) or run_config.get("config_overrides", {}).get("dr", {})
    
    # Get generation instructions - NO FALLBACKS
    generation_instructions_id = run_config.get("generation_instructions_id")
    if not generation_instructions_id:
        raise ValueError("No generation_instructions_id in run_config - you MUST set this in the GUI")
    content = await content_repo.get_by_id(generation_instructions_id)
    if not content or not content.body:
        raise ValueError(f"Generation instructions content not found or empty (id={generation_instructions_id})")
    instructions = content.body
    logger.info(f"Loaded generation instructions from Content Library: {content.name}")
    
    # Fetch custom instruction content
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
    
    # ALL VALUES MUST COME FROM DB - NO FALLBACKS
    generators = run_config.get("generators")
    if not generators:
        raise ValueError("generators must be set in preset")
    models = run_config.get("models") or []
    iterations = run_config.get("iterations")
    if iterations is None:
        raise ValueError("iterations must be set in preset")
    eval_enabled = eval_config.get("enabled")
    if eval_enabled is None:
        eval_enabled = run_config.get("evaluation_enabled")
    if eval_enabled is None:
        raise ValueError("evaluation_enabled must be set in preset")
    pairwise_enabled = pairwise_config.get("enabled")
    if pairwise_enabled is None:
        pairwise_enabled = run_config.get("pairwise_enabled")
    if pairwise_enabled is None:
        raise ValueError("pairwise_enabled must be set in preset")
    eval_iterations = eval_config.get("iterations")
    if eval_iterations is None:
        raise ValueError("eval_iterations must be set in preset")
    judge_models = eval_config.get("judge_models")
    if eval_enabled and not judge_models:
        raise ValueError("eval_config.judge_models must be set in preset when evaluation is enabled")
    eval_timeout = eval_config.get("timeout_seconds")
    if eval_timeout is None:
        raise ValueError("eval_config.timeout_seconds must be set in preset")
    combine_enabled = combine_config.get("enabled")
    if combine_enabled is None:
        raise ValueError("combine_config.enabled must be set in preset")
    combine_strategy = combine_config.get("strategy")
    if combine_enabled and not combine_strategy:
        raise ValueError("combine_config.strategy must be set when combine is enabled")
    combine_models_list = combine_config.get("selected_models")
    if combine_enabled and not combine_models_list:
        raise ValueError("combine_config.selected_models must be set when combine is enabled")
    combine_max_tokens = combine_config.get("max_tokens")
    if combine_enabled and combine_max_tokens is None:
        raise ValueError("combine_config.max_tokens must be set when combine is enabled")
    log_level = run_config.get("log_level")
    if not log_level:
        raise ValueError("log_level must be set in preset")
    # Read concurrency settings from preset's direct database columns (set by GUI)
    gen_concurrency = preset.generation_concurrency
    if gen_concurrency is None:
        raise ValueError("preset.generation_concurrency must be set in preset")
    eval_concurrency_val = preset.eval_concurrency
    if eval_concurrency_val is None:
        raise ValueError("preset.eval_concurrency must be set in preset")
    request_timeout = preset.request_timeout
    if request_timeout is None:
        raise ValueError("preset.request_timeout must be set in preset")
    
    # Read FPF retry settings from preset's direct database columns (set by GUI)
    fpf_max_retries = preset.fpf_max_retries
    if fpf_max_retries is None:
        raise ValueError("preset.fpf_max_retries must be set in preset")
    fpf_retry_delay = preset.fpf_retry_delay
    if fpf_retry_delay is None:
        raise ValueError("preset.fpf_retry_delay must be set in preset")
    
    def extract_model_keys(selected_models_list):
        """Convert selected_models list to model key strings."""
        if not selected_models_list:
            return None
        keys = []
        for entry in selected_models_list:
            if isinstance(entry, dict):
                p = entry.get("provider")
                m = entry.get("model")
                if p and m:
                    keys.append(f"{p}:{m}")
            elif isinstance(entry, str):
                keys.append(entry)
        return keys if keys else None
    
    fpf_model_keys = extract_model_keys(fpf_config.get("selected_models"))
    gptr_model_keys = extract_model_keys(gptr_config.get("selected_models"))
    dr_model_keys = extract_model_keys(dr_config.get("selected_models"))

    enabled_generators = set(generators)
    if "fpf" in enabled_generators and not fpf_model_keys:
        raise ValueError("FPF enabled but no FPF selected_models set in preset")
    if "gptr" in enabled_generators and not gptr_model_keys:
        raise ValueError("GPTR enabled but no GPTR selected_models set in preset")
    if "dr" in enabled_generators and not dr_model_keys:
        raise ValueError("DR enabled but no DR selected_models set in preset")
    
    logger.info(f"Per-generator models - FPF: {len(fpf_model_keys or [])} models, GPTR: {len(gptr_model_keys or [])} models, DR: {len(dr_model_keys or [])} models")

    # Model settings keyed by model key (provider:model)
    # When same model is used by multiple generators, FPF settings take priority (since FPF uses max_tokens)
    model_settings: dict[str, dict] = {}
    model_names: list[str] = []

    def add_models_for_generator(model_keys: Optional[list[str]], generator_config: dict, label: str, require_max_tokens: bool = True):
        if not model_keys:
            return
        temperature = generator_config.get("temperature")
        max_tokens = generator_config.get("max_tokens")
        if temperature is None:
            raise ValueError(f"{label} enabled but temperature is missing in preset")
        # Only FPF requires max_tokens; GPTR/DR use their own token limit configs
        if require_max_tokens and max_tokens is None:
            raise ValueError(f"{label} enabled but max_tokens is missing in preset")
        
        # For GPTR/DR, use a fallback max_tokens value (won't actually be used, they use their own limits)
        effective_max_tokens = max_tokens if max_tokens is not None else 8192
        
        for key in model_keys:
            parts = key.split(":", 1)
            if len(parts) != 2 or not parts[0] or not parts[1]:
                raise ValueError(f"Model key {key} is invalid; expected provider:model")
            provider, base_model = parts
            settings = {
                "provider": provider,
                "model": base_model,
                "temperature": temperature,
                "max_tokens": effective_max_tokens,
            }
            # If model already exists (from another generator), only override if this is FPF (FPF needs accurate max_tokens)
            if key in model_settings:
                if require_max_tokens:  # This is FPF - its settings take priority
                    model_settings[key] = settings
                # else: keep existing settings (from FPF if already set)
            else:
                model_settings[key] = settings
            model_names.append(key)

    # Process FPF first so its max_tokens values take priority
    add_models_for_generator(fpf_model_keys, fpf_config, "FPF", require_max_tokens=True)
    add_models_for_generator(gptr_model_keys, gptr_config, "GPTR", require_max_tokens=False)  # GPTR uses its own token limits
    add_models_for_generator(dr_model_keys, dr_config, "DR", require_max_tokens=False)  # DR uses its own token limits

    model_names = sorted(set(model_names))
    if not model_names:
        raise ValueError("No models configured for enabled generators in preset")

    if models:
        model_keys_from_models = set()
        for model_entry in models:
            provider = model_entry.get("provider")
            base_model = model_entry.get("model")
            if provider and base_model:
                model_keys_from_models.add(f"{provider}:{base_model}")
            else:
                raise ValueError(f"Model entry missing provider/model: {model_entry}")
        extra_models = model_keys_from_models - set(model_names)
        if extra_models:
            raise ValueError(f"Global models not bound to generators: {sorted(extra_models)}")

    logger.info(f"Built model_settings for {len(model_settings)} unique models")

    eval_temperature = eval_config.get("temperature")
    eval_max_tokens = eval_config.get("max_tokens")
    # Read eval_retries from preset's direct database column (set by GUI)
    eval_retries = preset.eval_retries
    if eval_retries is None:
        raise ValueError("preset.eval_retries must be set in preset")
    if eval_temperature is None:
        raise ValueError("eval_config.temperature must be set in preset")
    if eval_max_tokens is None:
        raise ValueError("eval_config.max_tokens must be set in preset")
    eval_strict_json = eval_config.get("strict_json")
    if eval_strict_json is None:
        raise ValueError("eval_config.strict_json must be set in preset")

    executor_config = RunConfig(
        document_ids=list(document_contents.keys()),
        document_contents=document_contents,
        instructions=instructions,
        generators=[AdapterGeneratorType(g) for g in generators],
        models=model_names,
        model_settings=model_settings,
        fpf_models=fpf_model_keys,
        gptr_models=gptr_model_keys,
        dr_models=dr_model_keys,
        iterations=iterations,
        enable_single_eval=eval_enabled,
        enable_pairwise=pairwise_enabled,
        eval_iterations=eval_iterations,
        eval_judge_models=judge_models,
        eval_retries=eval_retries,
        eval_temperature=eval_temperature,
        eval_max_tokens=eval_max_tokens,
        eval_strict_json=eval_strict_json,
        eval_timeout=eval_timeout,
        pairwise_top_n=eval_config.get("pairwise_top_n"),
        single_eval_instructions=single_eval_instructions,
        pairwise_eval_instructions=pairwise_eval_instructions,
        eval_criteria=eval_criteria,
        enable_combine=combine_enabled,
        combine_strategy=combine_strategy,
        combine_models=combine_models_list,
        combine_instructions=combine_instructions,
        combine_max_tokens=combine_max_tokens,
        post_combine_top_n=run_config.get("post_combine_top_n"),
        expose_criteria_to_generators=run_config.get("expose_criteria_to_generators", False),
        log_level=log_level,
        fpf_log_output="file",
        fpf_log_file_path=str(Path("logs") / run_id / "fpf_output.log"),
        generation_concurrency=gen_concurrency,
        eval_concurrency=eval_concurrency_val,
        request_timeout=request_timeout,
        fpf_max_retries=fpf_max_retries,
        fpf_retry_delay=fpf_retry_delay,
    )
    
    # Set status to RUNNING only after all validation succeeds
    await repo.start(run_id)
    
    background_tasks.add_task(execute_run_background, run_id, executor_config)
    
    return {"status": "started", "run_id": run_id}


@router.post("/runs/{run_id}/pause")
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


@router.post("/runs/{run_id}/resume")
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


@router.post("/runs/{run_id}/cancel")
async def cancel_run(
    run_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Cancel a running or paused run.
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
    
    executor = _active_executors.get(run_id)
    if executor:
        logger.info(f"Signaling cancellation for run {run_id}")
        executor.cancel()
    else:
        logger.info(f"No active executor found for run {run_id}, just updating status")
    
    await repo.update(run_id, status=RunStatus.CANCELLED, completed_at=datetime.utcnow())
    return {"status": "cancelled", "run_id": run_id}
