"""
Presets API Routes.

Endpoints for managing saved preset configurations.
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Optional
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Dict, Any

from app.infra.db.session import get_user_db, get_user_session_by_id
from app.infra.db.repositories import PresetRepository, RunRepository, DocumentRepository, ContentRepository
from app.auth.middleware import get_current_user
from app.infra.db.models.run import RunStatus
from app.services.run_executor import get_executor, RunConfig, RunExecutor
from app.services.output_writer import OutputWriter
from app.utils.logging_utils import get_run_logger
from app.utils.paths import get_log_path
from app.adapters.base import GeneratorType as AdapterGeneratorType
from ..schemas.presets import (
    PresetCreate,
    PresetUpdate,
    PresetResponse,
    PresetSummary,
    PresetList,
)
from ..schemas.runs import (
    GeneratorType, ModelConfig, GptrSettings, FpfSettings, 
    EvaluationSettings, PairwiseSettings, CombineSettings,
    # Complete config types
    FpfConfigComplete, GptrConfigComplete, DrConfigComplete, MaConfigComplete,
    EvalConfigComplete, PairwiseConfigComplete, CombineConfigComplete,
    GeneralConfigComplete, ConcurrencyConfigComplete,
)

from sqlalchemy import inspect

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/presets", tags=["presets"])


async def execute_run_background(run_id: str, config: RunConfig):
    """
    Background task to execute a run and update DB.
    """
    from pathlib import Path
    from app.evaluation.models import SingleEvalResult
    
    # Set up file logging for this run (per-user logs directory)
    run_log_file = get_log_path(config.user_id, run_id, "run.log")
    
    # Ensure the logs directory exists
    run_log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Create a file handler for this run
    file_handler = logging.FileHandler(run_log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    ))
    
    # Add handler to root logger to capture all app logs
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)
    
    logger.info(f"Starting background execution for run {run_id}")
    
    # Set up incremental DB save callbacks (copied from execution.py)
    db_lock = asyncio.Lock()
    pre_combine_evals_detailed_incremental = {}
    generated_docs_incremental = []
    
    # Pre-initialize source_doc_results with entries for each input document
    # so that collapsible sections appear immediately when generation STARTS
    source_doc_results_incremental = {}
    for doc_id in config.document_ids:
        source_doc_results_incremental[doc_id] = {
            "source_doc_id": doc_id,
            "source_doc_name": doc_id,
            "status": "pending",
            "generated_docs": [],
            "single_eval_results": {},
            "pairwise_results": None,
            "winner_doc_id": None,
            "combined_doc": None,
            "cost_usd": 0.0,
            "errors": [],
        }
    
    # Save initial source_doc_results to DB immediately so UI shows collapsible sections
    async with get_user_session_by_id(config.user_id) as session:
        repo = RunRepository(session, user_id=config.user_id)
        run_fresh = await repo.get_by_id(run_id)
        if run_fresh:
            results_summary_updated = dict(run_fresh.results_summary or {})
            results_summary_updated["source_doc_results"] = source_doc_results_incremental
            await repo.update(run_id, results_summary=results_summary_updated)
            logger.info(f"[INIT] Pre-initialized source_doc_results with {len(config.document_ids)} input documents")
    
    all_evaluators_incremental: set[str] = set()
    all_criteria_incremental: set[str] = set()
    eval_count = 0
    gen_count = 0
    
    async def on_gen_complete(doc_id: str, model: str, generator: str, source_doc_id: str, iteration: int):
        """Callback fired after each document generation - writes generated_docs to DB immediately."""
        nonlocal gen_count
        
        logger.info(f"[on_gen_complete] CALLED: doc_id={doc_id}, model={model}, generator={generator}, source_doc_id={source_doc_id}")
        
        async with db_lock:
            gen_count += 1
            
            doc_info = {
                "id": doc_id,
                "model": model,
                "source_doc_id": source_doc_id,
                "generator": generator,
                "iteration": iteration,
            }
            generated_docs_incremental.append(doc_info)
            
            # Update source_doc_results - entry should already exist from pre-initialization
            # If not (edge case), create it
            if source_doc_id not in source_doc_results_incremental:
                source_doc_results_incremental[source_doc_id] = {
                    "source_doc_id": source_doc_id,
                    "source_doc_name": source_doc_id,
                    "status": "running",
                    "generated_docs": [],
                    "single_eval_results": {},
                    "pairwise_results": None,
                    "winner_doc_id": None,
                    "combined_doc": None,
                    "cost_usd": 0.0,
                    "errors": [],
                }
            else:
                # Update status from "pending" to "running" on first generation
                source_doc_results_incremental[source_doc_id]["status"] = "running"
            
            # Add to generated_docs for this source doc
            source_doc_results_incremental[source_doc_id]["generated_docs"].append({
                "doc_id": doc_id,
                "model": model,
                "generator": generator,
                "source_doc_id": source_doc_id,
                "iteration": iteration,
            })
            
            async with get_user_session_by_id(config.user_id) as session:
                repo = RunRepository(session, user_id=config.user_id)
                run_fresh = await repo.get_by_id(run_id)
                if run_fresh:
                    results_summary_updated = dict(run_fresh.results_summary or {})
                    results_summary_updated["generated_docs"] = generated_docs_incremental
                    results_summary_updated["source_doc_results"] = source_doc_results_incremental
                    await repo.update(run_id, results_summary=results_summary_updated)
                    logger.info(f"[on_gen_complete] Saved to DB: generated_docs={len(generated_docs_incremental)}, source_doc_results={list(source_doc_results_incremental.keys())}")
                else:
                    logger.warning(f"[on_gen_complete] Run {run_id} not found in DB!")
            
            logger.info(f"[DB] Saved gen #{gen_count}: {doc_id} | {model}")
    
    async def on_eval_complete(doc_id: str, judge_model: str, trial: int, result: SingleEvalResult):
        """Callback fired after each individual judge evaluation - writes to DB immediately."""
        nonlocal eval_count
        
        async with db_lock:
            eval_count += 1
            
            if doc_id not in pre_combine_evals_detailed_incremental:
                pre_combine_evals_detailed_incremental[doc_id] = {
                    "evaluations": [],
                    "overall_average": 0.0,
                }
            
            eval_entry = {
                "judge_model": result.model,
                "trial": trial,
                "scores": [{"criterion": s.criterion, "score": s.score, "reason": s.reason} for s in result.scores],
                "average_score": result.average_score,
            }
            pre_combine_evals_detailed_incremental[doc_id]["evaluations"].append(eval_entry)
            all_evaluators_incremental.add(result.model)
            for s in result.scores:
                all_criteria_incremental.add(s.criterion)
            
            all_avgs = [e["average_score"] for e in pre_combine_evals_detailed_incremental[doc_id]["evaluations"]]
            pre_combine_evals_detailed_incremental[doc_id]["overall_average"] = sum(all_avgs) / len(all_avgs) if all_avgs else 0.0
            
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
            
            # Find which source_doc this generated doc belongs to and update its single_eval_results
            source_doc_id = None
            for src_id, sdr in source_doc_results_incremental.items():
                for gen_doc in sdr.get("generated_docs", []):
                    if gen_doc.get("doc_id") == doc_id:
                        source_doc_id = src_id
                        break
                if source_doc_id:
                    break
            
            if source_doc_id and source_doc_id in source_doc_results_incremental:
                # Add/update eval result for this doc in source_doc_results
                if doc_id not in source_doc_results_incremental[source_doc_id]["single_eval_results"]:
                    source_doc_results_incremental[source_doc_id]["single_eval_results"][doc_id] = {
                        "avg_score": 0.0,
                        "scores_by_criterion": {},
                        "scores_by_model": {},
                    }
                # Update the average score
                source_doc_results_incremental[source_doc_id]["single_eval_results"][doc_id]["avg_score"] = \
                    pre_combine_evals_detailed_incremental[doc_id]["overall_average"]
            
            async with get_user_session_by_id(config.user_id) as session:
                repo = RunRepository(session, user_id=config.user_id)
                run_fresh = await repo.get_by_id(run_id)
                if run_fresh:
                    results_summary_updated = dict(run_fresh.results_summary or {})
                    results_summary_updated["pre_combine_evals"] = pre_combine_evals
                    results_summary_updated["pre_combine_evals_detailed"] = pre_combine_evals_detailed_incremental
                    results_summary_updated["evaluator_list"] = sorted(list(all_evaluators_incremental))
                    results_summary_updated["criteria_list"] = sorted(list(all_criteria_incremental))
                    results_summary_updated["source_doc_results"] = source_doc_results_incremental
                    await repo.update(run_id, results_summary=results_summary_updated)
            
            logger.info(f"[DB] Saved eval #{eval_count}: {doc_id} | {judge_model} trial={trial} avg={result.average_score:.2f}")
    
    # Attach callbacks to config
    config.on_gen_complete = on_gen_complete
    config.on_eval_complete = on_eval_complete
    
    executor = get_executor()
    result = await executor.execute(run_id, config)
    
    logger.info(f"Executor returned for run {run_id}: status={result.status.value}, docs={len(result.generated_docs)}, errors={result.errors}")
    
    # Update run in DB
    async with get_user_session_by_id(config.user_id) as session:
        run_repo = RunRepository(session, user_id=config.user_id)
        
        if result.status.value == "completed":
            logger.info(f"Run {run_id}: Saving completed results to DB...")
            try:
                # Build pre_combine_evals: { doc_id: { judge_model: avg_score } }
                pre_combine_evals = {}
                pre_combine_evals_detailed = {}
                if result.single_eval_results:
                    for doc_id, summary in result.single_eval_results.items():
                        # Build simple scores by model
                        scores_by_model = {}
                        if hasattr(summary, 'results') and summary.results:
                            model_scores: dict[str, list[float]] = {}
                            for eval_result in summary.results:
                                model = eval_result.model
                                if model not in model_scores:
                                    model_scores[model] = []
                                for score_item in eval_result.scores:
                                    model_scores[model].append(score_item.score)
                            # Average per model
                            for model, scores in model_scores.items():
                                scores_by_model[model] = sum(scores) / len(scores) if scores else 0.0
                        pre_combine_evals[doc_id] = scores_by_model
                        # Detailed info
                        pre_combine_evals_detailed[doc_id] = {
                            "avg_score": summary.avg_score,
                            "scores_by_criterion": summary.scores_by_criterion,
                            "num_evaluations": summary.num_evaluations,
                        }
                
                # Build pairwise_results
                pairwise_data = None
                if result.pairwise_results:
                    pw = result.pairwise_results
                    pairwise_data = {
                        "total_comparisons": pw.total_comparisons,
                        "total_pairs": pw.total_pairs,
                        "winner_doc_id": pw.winner_doc_id,
                        "rankings": [
                            {"doc_id": r.doc_id, "elo": r.rating, "wins": r.wins, "losses": r.losses}
                            for r in pw.elo_ratings
                        ],
                        "comparisons": [
                            {
                                "doc_id_a": r.doc_id_1,
                                "doc_id_b": r.doc_id_2,
                                "winner": r.winner_doc_id,
                                "judge_model": r.model,
                                "trial": r.trial,
                                "reason": r.reason,
                            }
                            for r in pw.results
                        ],
                    }
                
                # Build generated_docs list
                generated_docs_data = []
                for doc in result.generated_docs:
                    generated_docs_data.append({
                        "id": doc.doc_id,
                        "model": doc.model,
                        "generator": doc.generator.value if hasattr(doc.generator, 'value') else str(doc.generator),
                        "source_doc_id": doc.source_doc_id,
                        "iteration": doc.iteration,
                    })
                
                # Add combined docs to generated_docs (UI filters from this list)
                for combined_doc in (result.combined_docs or []):
                    generated_docs_data.append({
                        "id": combined_doc.doc_id,
                        "model": combined_doc.model,
                        "generator": combined_doc.generator.value if hasattr(combined_doc.generator, 'value') else str(combined_doc.generator),
                        "source_doc_id": combined_doc.source_doc_id,
                        "iteration": combined_doc.iteration,
                        "is_combined": True,
                    })
                
                # Serialize source_doc_results for multi-doc pipeline
                source_doc_results_data = {}
                for src_doc_id, sdr in (result.source_doc_results or {}).items():
                    # Serialize generated docs for this source
                    sdr_gen_docs = []
                    for doc in (sdr.generated_docs or []):
                        sdr_gen_docs.append({
                            "doc_id": doc.doc_id,
                            "model": doc.model,
                            "generator": doc.generator.value if hasattr(doc.generator, 'value') else str(doc.generator),
                            "source_doc_id": doc.source_doc_id,
                            "iteration": doc.iteration,
                        })
                    
                    # Serialize single eval scores for this source
                    sdr_single_eval_scores = {}
                    for doc_id, summary in (sdr.single_eval_results or {}).items():
                        scores_by_model = {}
                        if hasattr(summary, 'results') and summary.results:
                            model_scores: dict[str, list[float]] = {}
                            for eval_result in summary.results:
                                model = eval_result.model
                                if model not in model_scores:
                                    model_scores[model] = []
                                for score_item in eval_result.scores:
                                    model_scores[model].append(score_item.score)
                            for model, scores in model_scores.items():
                                scores_by_model[model] = sum(scores) / len(scores) if scores else 0.0
                        sdr_single_eval_scores[doc_id] = {
                            "avg_score": summary.avg_score,
                            "scores_by_criterion": summary.scores_by_criterion,
                            "scores_by_model": scores_by_model,
                        }
                    
                    # Serialize pairwise results for this source
                    sdr_pairwise = None
                    if sdr.pairwise_results:
                        pw = sdr.pairwise_results
                        sdr_pairwise = {
                            "total_comparisons": pw.total_comparisons,
                            "total_pairs": pw.total_pairs,
                            "winner_doc_id": pw.winner_doc_id,
                            "rankings": [
                                {"doc_id": r.doc_id, "elo": r.rating, "wins": r.wins, "losses": r.losses}
                                for r in (pw.elo_ratings or [])
                            ],
                        }
                    
                    # Serialize combined doc for this source
                    sdr_combined = None
                    if sdr.combined_doc:
                        sdr_combined = {
                            "doc_id": sdr.combined_doc.doc_id,
                            "model": sdr.combined_doc.model,
                            "generator": sdr.combined_doc.generator.value if hasattr(sdr.combined_doc.generator, 'value') else str(sdr.combined_doc.generator),
                        }
                    
                    source_doc_results_data[src_doc_id] = {
                        "source_doc_id": sdr.source_doc_id,
                        "source_doc_name": sdr.source_doc_name,
                        "status": sdr.status.value if hasattr(sdr.status, 'value') else str(sdr.status),
                        "generated_docs": sdr_gen_docs,
                        "single_eval_results": sdr_single_eval_scores,  # Match dataclass field name
                        "pairwise_results": sdr_pairwise,
                        "winner_doc_id": sdr.winner_doc_id,
                        "combined_doc": sdr_combined,
                        "cost_usd": sdr.cost_usd,
                        "duration_seconds": sdr.duration_seconds,
                        "errors": sdr.errors,
                    }
                
                results_summary = {
                    "winner": result.winner_doc_id,
                    "generated_count": len(result.generated_docs),
                    "eval_count": len(result.single_eval_results or {}),
                    "combined_doc_id": result.combined_docs[0].doc_id if result.combined_docs else None,
                    "post_combine_eval": asdict(result.post_combine_eval_results) if result.post_combine_eval_results else None,
                    "pre_combine_evals": pre_combine_evals,
                    "pre_combine_evals_detailed": pre_combine_evals_detailed,
                    "pairwise_results": pairwise_data,
                    "generated_docs": generated_docs_data,
                    "source_doc_results": source_doc_results_data,  # NEW: Per-source-document results
                }

                # Convert datetime objects to ISO strings for JSON serialization
                def datetime_serializer(obj):
                    if isinstance(obj, datetime):
                        return obj.isoformat()
                    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
                
                await run_repo.complete(
                    run_id, 
                    results_summary=json.loads(json.dumps(results_summary, default=datetime_serializer)),
                    total_cost_usd=result.total_cost_usd
                )
                logger.info(f"Run {run_id} completed and saved to DB successfully")
                
                # === Output Writer: Save winning document ===
                if result.winner_doc_id and config.output_destination != "none":
                    try:
                        # Find the winner content
                        winner_content = None
                        winner_model = None
                        source_doc_name = "unknown"
                        
                        # Check generated_docs first
                        for doc in result.generated_docs:
                            if doc.doc_id == result.winner_doc_id:
                                winner_content = doc.content
                                winner_model = doc.model
                                source_doc_name = config.document_names.get(doc.source_doc_id, doc.source_doc_id)
                                break
                        
                        # Check combined_docs if not found
                        if not winner_content:
                            for doc in (result.combined_docs or []):
                                if doc.doc_id == result.winner_doc_id:
                                    winner_content = doc.content
                                    winner_model = doc.model
                                    source_doc_name = config.document_names.get(doc.source_doc_id, doc.source_doc_id) if doc.source_doc_id else "combined"
                                    break
                        
                        if winner_content:
                            output_writer = OutputWriter(session, config.user_id)
                            output_result = await output_writer.write_winner(
                                content=winner_content,
                                output_destination=config.output_destination,
                                filename_template=config.output_filename_template,
                                run_id=run_id,
                                winner_doc_id=result.winner_doc_id,
                                source_doc_name=source_doc_name,
                                winner_model=winner_model or "unknown",
                                github_connection_id=None,  # TODO: Add to config
                                github_output_path=None,  # TODO: Add to config
                                github_commit_message=config.github_commit_message,
                            )
                            
                            if output_result.success:
                                logger.info(f"Run {run_id}: Saved winning document - content_id={output_result.content_id}")
                                # Update results_summary with output info
                                results_summary["output"] = output_result.to_dict()
                                await run_repo.update(run_id, results_summary=results_summary)
                            else:
                                logger.warning(f"Run {run_id}: Failed to save winning document - {output_result.error}")
                        else:
                            logger.warning(f"Run {run_id}: Winner doc_id={result.winner_doc_id} not found in generated or combined docs")
                    except Exception as output_err:
                        logger.exception(f"Run {run_id}: Error writing output: {output_err}")
                        # Don't fail the run just because output writing failed
            except Exception as save_err:
                logger.exception(f"Run {run_id}: Failed to save results to DB: {save_err}")
                await run_repo.fail(run_id, error_message=f"Failed to save results: {save_err}")
        else:
            error_msg = "; ".join(result.errors) if result.errors else "Unknown error"
            await run_repo.fail(run_id, error_message=error_msg)
            logger.error(f"Run {run_id} failed: {error_msg}")


def _get_runs_safely(preset):
    """Safely get runs if loaded, else return empty list."""
    ins = inspect(preset)
    if ins and 'runs' in ins.unloaded:
        return []
    return preset.runs or []

def _derive_iterations(preset) -> int:
    """Get iterations from config_overrides.general with fallback."""
    general_cfg = (preset.config_overrides or {}).get("general", {})
    iterations = general_cfg.get("iterations", 1)
    return iterations


def _preset_to_response(preset) -> PresetResponse:
    """Convert DB preset to API response."""
    runs = _get_runs_safely(preset)
    overrides = preset.config_overrides or {}
    
    # Build legacy combine settings
    combine_settings = CombineSettings()
    if "combine" in overrides:
        combine_settings = CombineSettings(**overrides["combine"])
    
    # Build complete config objects from overrides
    general_config = None
    if "general" in overrides:
        general_config = GeneralConfigComplete(**overrides["general"])
    
    fpf_config = None
    if "fpf" in overrides:
        fpf_config = FpfConfigComplete(**overrides["fpf"])
    
    gptr_config = None
    if "gptr" in overrides:
        gptr_config = GptrConfigComplete(**overrides["gptr"])
    
    dr_config = None
    if "dr" in overrides:
        dr_config = DrConfigComplete(**overrides["dr"])
    
    ma_config = None
    if "ma" in overrides:
        ma_config = MaConfigComplete(**overrides["ma"])
    
    eval_config = None
    if "eval" in overrides:
        eval_config = EvalConfigComplete(**overrides["eval"])
    
    pairwise_config = None
    if "pairwise" in overrides:
        pairwise_config = PairwiseConfigComplete(**overrides["pairwise"])
    
    combine_config = None
    if "combine" in overrides:
        combine_config = CombineConfigComplete(**overrides["combine"])
    
    concurrency_config = None
    if "concurrency" in overrides:
        concurrency_config = ConcurrencyConfigComplete(**overrides["concurrency"])
        
    return PresetResponse(
        id=preset.id,
        name=preset.name,
        description=preset.description,
        documents=preset.documents or [],
        # Content Library instruction IDs
        single_eval_instructions_id=preset.single_eval_instructions_id,
        pairwise_eval_instructions_id=preset.pairwise_eval_instructions_id,
        eval_criteria_id=preset.eval_criteria_id,
        combine_instructions_id=preset.combine_instructions_id,
        generation_instructions_id=preset.generation_instructions_id,
        # Complete config objects (NEW)
        general_config=general_config,
        fpf_config=fpf_config,
        gptr_config=gptr_config,
        dr_config=dr_config,
        ma_config=ma_config,
        eval_config=eval_config,
        pairwise_config=pairwise_config,
        combine_config=combine_config,
        concurrency_config=concurrency_config,
        # Logging - REQUIRED
        log_level=preset.log_level,
        # GitHub input source configuration - REQUIRED
        input_source_type=preset.input_source_type,
        github_connection_id=getattr(preset, 'github_connection_id', None),
        github_input_paths=preset.github_input_paths,
        github_output_path=getattr(preset, 'github_output_path', None),
        # Legacy fields - REQUIRED from preset
        generators=[GeneratorType(g) for g in preset.generators],
        models=[ModelConfig(**m) for m in preset.models],
        iterations=_derive_iterations(preset),
        gptr_settings=GptrSettings(**preset.gptr_config) if preset.gptr_config else None,
        fpf_settings=FpfSettings(**preset.fpf_config) if preset.fpf_config else None,
        evaluation=EvaluationSettings(enabled=preset.evaluation_enabled),
        pairwise=PairwiseSettings(enabled=preset.pairwise_enabled),
        combine=combine_settings,
        created_at=preset.created_at,
        updated_at=preset.updated_at,
        run_count=len(runs),
        last_run_at=max((r.created_at for r in runs), default=None) if runs else None,
    )


def _preset_to_summary(preset) -> PresetSummary:
    """Convert DB preset to summary response."""
    runs = _get_runs_safely(preset)
    return PresetSummary(
        id=preset.id,
        name=preset.name,
        description=preset.description,
        document_count=len(preset.documents) if preset.documents else 0,
        model_count=len(preset.models) if preset.models else 0,
        iterations=_derive_iterations(preset),
        generators=[GeneratorType(g) for g in (preset.generators or ["gptr"])],
        created_at=preset.created_at,
        updated_at=preset.updated_at,
        run_count=len(runs),
    )


# ============================================================================
# Endpoints
# ============================================================================

@router.post("", response_model=PresetResponse)
async def create_preset(
    data: PresetCreate,
    user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_user_db)
) -> PresetResponse:
    """
    Create a new preset configuration.
    """
    repo = PresetRepository(db, user_id=user['uuid'])
    
    # Check for duplicate name
    existing = await repo.get_by_name(data.name)
    if existing:
        raise HTTPException(status_code=400, detail=f"Preset with name '{data.name}' already exists")
    
    # Build config_overrides from complete config objects (NEW)
    config_overrides = {}
    
    if data.general_config:
        config_overrides["general"] = data.general_config.model_dump()
    if data.fpf_config:
        config_overrides["fpf"] = data.fpf_config.model_dump()
    if data.gptr_config:
        config_overrides["gptr"] = data.gptr_config.model_dump()
    if data.dr_config:
        config_overrides["dr"] = data.dr_config.model_dump()
    if data.ma_config:
        config_overrides["ma"] = data.ma_config.model_dump()
    if data.eval_config:
        config_overrides["eval"] = data.eval_config.model_dump()
    if data.pairwise_config:
        config_overrides["pairwise"] = data.pairwise_config.model_dump()
    if data.combine_config:
        config_overrides["combine"] = data.combine_config.model_dump()
    if data.concurrency_config:
        config_overrides["concurrency"] = data.concurrency_config.model_dump()
    
    # Legacy combine support
    if data.combine and "combine" not in config_overrides:
        config_overrides["combine"] = data.combine.model_dump()
    
    # Extract values for DB columns with fallback defaults
    if data.eval_config:
        evaluation_enabled = data.eval_config.enabled
    elif data.evaluation:
        evaluation_enabled = data.evaluation.enabled
    else:
        evaluation_enabled = False
    
    if data.pairwise_config:
        pairwise_enabled = data.pairwise_config.enabled
    elif data.pairwise:
        pairwise_enabled = data.pairwise.enabled
    else:
        pairwise_enabled = False
    
    # Extract log_level with fallback to INFO
    if data.log_level:
        log_level = data.log_level
    elif data.general_config and hasattr(data.general_config, 'log_level') and data.general_config.log_level:
        log_level = data.general_config.log_level
    else:
        log_level = "INFO"
    
    # Get generators from fpf/gptr enabled flags or legacy
    generators = []
    if data.fpf_config and data.fpf_config.enabled:
        generators.append("fpf")
    if data.gptr_config and data.gptr_config.enabled:
        generators.append("gptr")
    if data.dr_config and data.dr_config.enabled:
        generators.append("dr")
    if data.ma_config and data.ma_config.enabled:
        generators.append("ma")
    if not generators and data.generators:
        generators = [g.value for g in data.generators]
    if not generators:
        generators = ["gptr"]
    
    # Get models from fpf_config or legacy
    models = []
    if data.fpf_config and data.fpf_config.selected_models:
        for model_str in data.fpf_config.selected_models:
            if ":" in model_str:
                provider, model = model_str.split(":", 1)
                models.append({"provider": provider, "model": model, "temperature": 0.7, "max_tokens": 4000})
            else:
                models.append({"provider": "openai", "model": model_str, "temperature": 0.7, "max_tokens": 4000})
    elif data.models:
        models = [m.model_dump() for m in data.models]
    
    preset = await repo.create(
        name=data.name,
        description=data.description,
        documents=data.documents,
        models=models if models else None,
        generators=generators,
        evaluation_enabled=evaluation_enabled,
        pairwise_enabled=pairwise_enabled,
        gptr_config=data.gptr_settings.model_dump() if data.gptr_settings else None,
        config_overrides=config_overrides if config_overrides else None,
        # Content Library instruction IDs
        single_eval_instructions_id=data.single_eval_instructions_id,
        pairwise_eval_instructions_id=data.pairwise_eval_instructions_id,
        eval_criteria_id=data.eval_criteria_id,
        combine_instructions_id=data.combine_instructions_id,
        generation_instructions_id=data.generation_instructions_id,
        # Logging
        log_level=log_level,
        # GitHub input source configuration
        input_source_type=data.input_source_type or 'database',
        github_connection_id=data.github_connection_id,
        github_input_paths=data.github_input_paths or [],
        github_output_path=data.github_output_path,
    )
    
    return _preset_to_response(preset)


@router.get("", response_model=PresetList)
async def list_presets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_user_db)
) -> PresetList:
    """
    List all presets with pagination.
    """
    repo = PresetRepository(db, user_id=user['uuid'])
    
    # Get active (non-deleted) presets
    offset = (page - 1) * page_size
    presets = await repo.get_active(limit=page_size, offset=offset)
    total = await repo.count()
    pages = (total + page_size - 1) // page_size
    
    return PresetList(
        items=[_preset_to_summary(p) for p in presets],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/{preset_id}", response_model=PresetResponse)
async def get_preset(
    preset_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_user_db)
) -> PresetResponse:
    """
    Get a specific preset by ID.
    """
    repo = PresetRepository(db, user_id=user['uuid'])
    preset = await repo.get_by_id(preset_id)
    
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")
    
    return _preset_to_response(preset)


@router.put("/{preset_id}", response_model=PresetResponse)
async def update_preset(
    preset_id: str,
    data: PresetUpdate,
    user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_user_db)
) -> PresetResponse:
    """
    Update a preset.
    """
    repo = PresetRepository(db, user_id=user['uuid'])
    preset = await repo.get_by_id(preset_id)
    
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")
    
    # Build update dict from non-None values
    update_data = {}
    
    if data.name is not None:
        # Check for duplicate name (exclude current preset)
        existing = await repo.get_by_name(data.name)
        if existing and existing.id != preset_id:
            raise HTTPException(status_code=400, detail=f"Preset with name '{data.name}' already exists")
        update_data["name"] = data.name
    
    if data.description is not None:
        update_data["description"] = data.description
    
    if data.documents is not None:
        update_data["documents"] = data.documents
    
    # Handle complete config objects (NEW)
    overrides = preset.config_overrides.copy() if preset.config_overrides else {}
    
    if data.general_config is not None:
        overrides["general"] = data.general_config.model_dump()
        # Extract log_level from general_config
        if hasattr(data.general_config, 'log_level') and data.general_config.log_level:
            update_data["log_level"] = data.general_config.log_level
    
    # Also check for top-level log_level
    if data.log_level is not None:
        update_data["log_level"] = data.log_level
    
    if data.fpf_config is not None:
        overrides["fpf"] = data.fpf_config.model_dump()
        # Also update models from fpf_config
        models = []
        for model_str in data.fpf_config.selected_models:
            if ":" in model_str:
                provider, model = model_str.split(":", 1)
                models.append({"provider": provider, "model": model, "temperature": 0.7, "max_tokens": 4000})
            else:
                models.append({"provider": "openai", "model": model_str, "temperature": 0.7, "max_tokens": 4000})
        if models:
            update_data["models"] = models
    
    if data.gptr_config is not None:
        overrides["gptr"] = data.gptr_config.model_dump()
    
    if data.dr_config is not None:
        overrides["dr"] = data.dr_config.model_dump()
    
    if data.ma_config is not None:
        overrides["ma"] = data.ma_config.model_dump()
    
    if data.eval_config is not None:
        overrides["eval"] = data.eval_config.model_dump()
        update_data["evaluation_enabled"] = data.eval_config.enabled
        # Extract eval_retries to direct DB column
        if hasattr(data.eval_config, 'retries') and data.eval_config.retries is not None:
            update_data["eval_retries"] = data.eval_config.retries
    
    if data.pairwise_config is not None:
        overrides["pairwise"] = data.pairwise_config.model_dump()
        update_data["pairwise_enabled"] = data.pairwise_config.enabled
    
    if data.combine_config is not None:
        overrides["combine"] = data.combine_config.model_dump()
    
    if data.concurrency_config is not None:
        overrides["concurrency"] = data.concurrency_config.model_dump()
        # Extract concurrency settings to direct DB columns
        cc = data.concurrency_config
        if hasattr(cc, 'generation_concurrency') and cc.generation_concurrency is not None:
            update_data["generation_concurrency"] = cc.generation_concurrency
        if hasattr(cc, 'eval_concurrency') and cc.eval_concurrency is not None:
            update_data["eval_concurrency"] = cc.eval_concurrency
        if hasattr(cc, 'request_timeout') and cc.request_timeout is not None:
            update_data["request_timeout"] = cc.request_timeout
        if hasattr(cc, 'fpf_max_retries') and cc.fpf_max_retries is not None:
            update_data["fpf_max_retries"] = cc.fpf_max_retries
        if hasattr(cc, 'fpf_retry_delay') and cc.fpf_retry_delay is not None:
            update_data["fpf_retry_delay"] = cc.fpf_retry_delay
    
    # Update generators from enabled flags
    generators = []
    if data.fpf_config and data.fpf_config.enabled:
        generators.append("fpf")
    if data.gptr_config and data.gptr_config.enabled:
        generators.append("gptr")
    if data.dr_config and data.dr_config.enabled:
        generators.append("dr")
    if data.ma_config and data.ma_config.enabled:
        generators.append("ma")
    if generators:
        update_data["generators"] = generators
    
    # Legacy field handling
    if data.models is not None:
        update_data["models"] = [m.model_dump() for m in data.models]
    
    if data.generators is not None and "generators" not in update_data:
        update_data["generators"] = [g.value for g in data.generators]
    
    if data.gptr_settings is not None:
        update_data["gptr_config"] = data.gptr_settings.model_dump()
    
    if data.evaluation is not None and data.eval_config is None:
        update_data["evaluation_enabled"] = data.evaluation.enabled
        overrides["evaluation"] = data.evaluation.model_dump()
    
    if data.pairwise is not None and data.pairwise_config is None:
        update_data["pairwise_enabled"] = data.pairwise.enabled
        overrides["pairwise"] = data.pairwise.model_dump()
             
    if data.combine is not None and data.combine_config is None:
        overrides["combine"] = data.combine.model_dump()
    
    # Handle Content Library instruction IDs
    if data.single_eval_instructions_id is not None:
        update_data["single_eval_instructions_id"] = data.single_eval_instructions_id
    if data.pairwise_eval_instructions_id is not None:
        update_data["pairwise_eval_instructions_id"] = data.pairwise_eval_instructions_id
    if data.eval_criteria_id is not None:
        update_data["eval_criteria_id"] = data.eval_criteria_id
    if data.combine_instructions_id is not None:
        update_data["combine_instructions_id"] = data.combine_instructions_id
    if data.generation_instructions_id is not None:
        update_data["generation_instructions_id"] = data.generation_instructions_id
    
    # Handle GitHub input source configuration
    if data.input_source_type is not None:
        update_data["input_source_type"] = data.input_source_type
    if data.github_connection_id is not None:
        update_data["github_connection_id"] = data.github_connection_id
    if data.github_input_paths is not None:
        update_data["github_input_paths"] = data.github_input_paths
    if data.github_output_path is not None:
        update_data["github_output_path"] = data.github_output_path
    
    # Save config_overrides if modified
    if overrides:
        update_data["config_overrides"] = overrides
    
    if update_data:
        preset = await repo.update(preset_id, **update_data)
    
    return _preset_to_response(preset)


@router.delete("/{preset_id}")
async def delete_preset(
    preset_id: str,
    permanent: bool = Query(False, description="Permanently delete instead of soft delete"),
    user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_user_db)
) -> dict:
    """
    Delete a preset.
    
    By default performs a soft delete. Use permanent=true for hard delete.
    """
    repo = PresetRepository(db, user_id=user['uuid'])
    preset = await repo.get_by_id(preset_id)
    
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")
    
    if permanent:
        await repo.delete(preset_id)
        return {"status": "deleted", "preset_id": preset_id, "permanent": True}
    else:
        await repo.soft_delete(preset_id)
        return {"status": "deleted", "preset_id": preset_id, "permanent": False}


@router.post("/{preset_id}/duplicate", response_model=PresetResponse)
async def duplicate_preset(
    preset_id: str,
    new_name: str = Query(..., min_length=1, max_length=200),
    user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_user_db)
) -> PresetResponse:
    """
    Create a copy of an existing preset with a new name.
    """
    repo = PresetRepository(db, user_id=user['uuid'])
    
    # Check original exists
    original = await repo.get_by_id(preset_id)
    if not original:
        raise HTTPException(status_code=404, detail="Preset not found")
    
    # Check new name doesn't exist
    existing = await repo.get_by_name(new_name)
    if existing:
        raise HTTPException(status_code=400, detail=f"Preset with name '{new_name}' already exists")
    
    # Duplicate
    new_preset = await repo.duplicate(preset_id, new_name)
    if not new_preset:
        raise HTTPException(status_code=500, detail="Failed to duplicate preset")
    
    return _preset_to_response(new_preset)


@router.post("/{preset_id}/execute")
async def execute_preset(
    preset_id: str,
    background_tasks: BackgroundTasks,
    user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_user_db)
) -> dict:
    """
    Execute a preset by creating and starting a new run.
    
    This is a convenience endpoint that:
    1. Creates a new run from the preset configuration
    2. Immediately starts the run
    
    Returns the created run ID.
    """
    repo = PresetRepository(db, user_id=user['uuid'])
    preset = await repo.get_by_id(preset_id)
    
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")
    
    # Create a new run from the preset
    run_repo = RunRepository(db, user_id=user['uuid'])
    run = await run_repo.create(
        preset_id=preset_id,
        title=f"Run from {preset.name} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        description=f"Executed from preset: {preset.name}",
        # Run starts with preset's configuration
    )
    
    # Start the run
    started_run = await run_repo.start(run.id)
    
    if not started_run:
        raise HTTPException(status_code=500, detail="Failed to start run")
        
    # Fetch document contents for execution
    doc_repo = DocumentRepository(db, user_id=user['uuid'])
    content_repo = ContentRepository(db, user_id=user['uuid'])
    document_contents = {}
    
    # preset.documents is a list of IDs that can reference either:
    # 1. The 'documents' table (legacy files)
    # 2. The 'contents' table with content_type='input_document'
    
    for doc_ref in (preset.documents or []):
        # Try to find by ID in documents table first
        doc = await doc_repo.get_by_id(doc_ref)
        if not doc:
            # Try by path in documents table
            doc = await doc_repo.get_by_path(doc_ref)
        
        if doc and doc.content:
            document_contents[doc.id] = doc.content
        elif doc and doc.file_path:
            # Read content from file if not in DB
            from pathlib import Path
            file_path = Path(doc.file_path)
            # Try relative to acm2/acm2 directory
            base_paths = [
                Path(__file__).parent.parent.parent.parent / doc.file_path,  # acm2/acm2/data/...
                Path(doc.file_path),  # absolute path
            ]
            content_loaded = False
            for try_path in base_paths:
                if try_path.exists():
                    try:
                        document_contents[doc.id] = try_path.read_text(encoding="utf-8")
                        content_loaded = True
                        logger.info(f"Loaded document content from file: {try_path}")
                        break
                    except Exception as e:
                        logger.error(f"Failed to read document file {try_path}: {e}")
            if not content_loaded:
                raise ValueError(f"Document content missing and file not found for {doc.name} ({doc.id}), file_path={doc.file_path}")
        elif doc:
            raise ValueError(f"Document {doc.name} ({doc.id}) has no content and no file_path - cannot execute")
        else:
            # Not found in documents table - try contents table (input_document type)
            content_item = await content_repo.get_by_id(doc_ref)
            if content_item and content_item.body:
                document_contents[content_item.id] = content_item.body
                logger.info(f"Loaded document from contents table: {content_item.name} ({content_item.id})")
            elif content_item:
                raise ValueError(f"Content item {content_item.name} ({content_item.id}) has no body - cannot execute")
            else:
                raise ValueError(f"Document reference not found in documents or contents table: {doc_ref}")

    # Load instruction contents - NO fallbacks, explicit errors if content missing
    single_eval_instructions = ""
    if preset.single_eval_instructions_id:
        content = await content_repo.get_by_id(preset.single_eval_instructions_id)
        if content and content.body:
            single_eval_instructions = content.body
        elif content:
            raise ValueError(f"Single eval instructions content exists but body is empty (id={preset.single_eval_instructions_id})")
        else:
            raise ValueError(f"Single eval instructions content not found (id={preset.single_eval_instructions_id})")
    pairwise_eval_instructions = ""
    if preset.pairwise_eval_instructions_id:
        content = await content_repo.get_by_id(preset.pairwise_eval_instructions_id)
        if content and content.body:
            pairwise_eval_instructions = content.body
        elif content:
            raise ValueError(f"Pairwise eval instructions content exists but body is empty (id={preset.pairwise_eval_instructions_id})")
        else:
            raise ValueError(f"Pairwise eval instructions content not found (id={preset.pairwise_eval_instructions_id})")
    eval_criteria = ""
    if preset.eval_criteria_id:
        content = await content_repo.get_by_id(preset.eval_criteria_id)
        if content and content.body:
            eval_criteria = content.body
        elif content:
            raise ValueError(f"Eval criteria content exists but body is empty (id={preset.eval_criteria_id})")
        else:
            raise ValueError(f"Eval criteria content not found (id={preset.eval_criteria_id})")
    combine_instructions = ""
    if preset.combine_instructions_id:
        content = await content_repo.get_by_id(preset.combine_instructions_id)
        if content and content.body:
            combine_instructions = content.body
        elif content:
            raise ValueError(f"Combine instructions content exists but body is empty (id={preset.combine_instructions_id})")
        else:
            raise ValueError(f"Combine instructions content not found (id={preset.combine_instructions_id})")

    # Build execution config
    combine_config = preset.config_overrides.get("combine", {}) if preset.config_overrides else {}
    
    # Get generation instructions from Content Library - NO FALLBACKS
    if not preset.generation_instructions_id:
        raise ValueError(f"Preset {preset.name} ({preset.id}) has no generation_instructions_id - you MUST set this in the GUI")
    gen_content = await content_repo.get_by_id(preset.generation_instructions_id)
    if not gen_content or not gen_content.body:
        raise ValueError(f"Generation instructions content not found or empty (id={preset.generation_instructions_id})")
    instructions = gen_content.body
    logger.info(f"Loaded generation instructions from Content Library: {gen_content.name}")
    
    # ALL VALUES MUST COME FROM DB - NO FALLBACKS
    if not preset.generators:
        raise ValueError(f"Preset {preset.name} has no generators - set this in the GUI")
    if not preset.models:
        raise ValueError(f"Preset {preset.name} has no models - set this in the GUI")
    if preset.evaluation_enabled is None:
        raise ValueError(f"Preset {preset.name} has no evaluation_enabled - set this in the GUI")
    if preset.pairwise_enabled is None:
        raise ValueError(f"Preset {preset.name} has no pairwise_enabled - set this in the GUI")
    
    # Get eval config - REQUIRED only when evaluation is enabled
    eval_cfg = preset.config_overrides.get("eval", {}) if preset.config_overrides else {}
    eval_enabled = eval_cfg.get("enabled")
    if eval_enabled is None:
        raise ValueError(f"Preset {preset.name} has no eval.enabled - set this in the GUI")
    eval_iterations = eval_cfg.get("iterations")
    if eval_iterations is None:
        raise ValueError(f"Preset {preset.name} has no eval_config.iterations - set this in the GUI")
    judge_models = eval_cfg.get("judge_models")
    if eval_enabled and not judge_models:
        raise ValueError(f"Preset {preset.name} has eval enabled but no judge_models - set this in the GUI")
    
    # Get combine config - REQUIRED
    combine_enabled = combine_config.get("enabled")
    if combine_enabled is None:
        raise ValueError(f"Preset {preset.name} has no combine_config.enabled - set this in the GUI")
    combine_strategy = combine_config.get("strategy")
    if combine_enabled and not combine_strategy:
        raise ValueError(f"Preset {preset.name} has combine enabled but no strategy - set this in the GUI")
    combine_models_list = combine_config.get("selected_models")
    if not combine_models_list and combine_config.get("model"):
        combine_models_list = [combine_config.get("model")]
    if combine_enabled and not combine_models_list:
        raise ValueError(f"Preset {preset.name} has combine enabled but no models - set this in the GUI")
    combine_max_tokens = combine_config.get("max_tokens")
    if combine_enabled and combine_max_tokens is None:
        # Default for backwards compatibility with old presets
        combine_max_tokens = 64000
        logger.warning(f"Preset {preset.name} has no combine_max_tokens, using default of 64000")
    logger.info(f"DEBUG: combine_enabled={combine_enabled}, combine_max_tokens={combine_max_tokens}")
    
    # Get log_level - REQUIRED
    if not preset.log_level:
        raise ValueError(f"Preset {preset.name} has no log_level - set this in the GUI")
    
    logger.info(f"DEBUG EARLY: preset.config_overrides={preset.config_overrides}")
    general_cfg = preset.config_overrides.get("general", {}) if preset.config_overrides else {}
    fpf_cfg = preset.config_overrides.get("fpf", {}) if preset.config_overrides else {}
    logger.info(f"DEBUG EARLY: fpf_cfg={fpf_cfg}")
    gptr_cfg = preset.config_overrides.get("gptr", {}) if preset.config_overrides else {}
    dr_cfg = preset.config_overrides.get("dr", {}) if preset.config_overrides else {}
    concurrency_cfg = preset.config_overrides.get("concurrency", {}) if preset.config_overrides else {}

    # Extract FPF log settings from general config (where GUI saves them)
    fpf_log_output = general_cfg.get("fpf_log_output")
    fpf_log_file_path = general_cfg.get("fpf_log_file_path")
    
    # Extract per-generator model keys from config_overrides
    fpf_model_keys = fpf_cfg.get("selected_models") if fpf_cfg.get("selected_models") else None
    gptr_model_keys = gptr_cfg.get("selected_models") if gptr_cfg.get("selected_models") else None
    dr_model_keys = dr_cfg.get("selected_models") if dr_cfg.get("selected_models") else None
    
    logger.info(f"DEBUG: preset.config_overrides type={type(preset.config_overrides)}")
    logger.info(f"DEBUG: fpf_cfg={fpf_cfg}")
    logger.info(f"DEBUG: fpf_model_keys={fpf_model_keys}")

    model_settings = {}
    model_names: list[str] = []
    for model_entry in (preset.models or []):
        if not isinstance(model_entry, dict):
            raise ValueError(f"Preset {preset.name} has invalid model entry: {model_entry}")
        provider = model_entry.get("provider")
        base_model = model_entry.get("model")
        temperature = model_entry.get("temperature")
        max_tokens = model_entry.get("max_tokens")

        # No fallbacks - temperature and max_tokens must be set per-model in the GUI
        if not provider or not base_model:
            raise ValueError(f"Model entry missing provider/model in preset {preset.name}: {model_entry}")
        if temperature is None:
            raise ValueError(f"Model {provider}:{base_model} missing temperature in preset {preset.name}")
        if max_tokens is None:
            raise ValueError(f"Model {provider}:{base_model} missing max_tokens in preset {preset.name}")

        key = f"{provider}:{base_model}"
        model_settings[key] = {
            "provider": provider,
            "model": base_model,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        model_names.append(key)

    # MIGRATION: If per-generator model lists are empty but we have legacy models,
    # use the legacy model_names for each enabled generator. This handles presets
    # saved before per-generator model selection was implemented.
    if model_names:
        generators_list = preset.generators or []
        if not fpf_model_keys and "fpf" in generators_list:
            logger.info(f"MIGRATION: Using legacy models for FPF generator: {model_names}")
            fpf_model_keys = model_names
        if not gptr_model_keys and "gptr" in generators_list:
            logger.info(f"MIGRATION: Using legacy models for GPTR generator: {model_names}")
            gptr_model_keys = model_names
        if not dr_model_keys and "dr" in generators_list:
            logger.info(f"MIGRATION: Using legacy models for DR generator: {model_names}")
            dr_model_keys = model_names

    eval_temperature = eval_cfg.get("temperature")
    eval_max_tokens = eval_cfg.get("max_tokens")
    # Read eval_retries from preset's direct database column (set by GUI)
    eval_retries = preset.eval_retries
    if eval_retries is None:
        raise ValueError(f"Preset {preset.name} has no eval_retries - set this in the GUI")
    # Only require eval temperature/max_tokens if eval is enabled
    if eval_enabled:
        if eval_temperature is None:
            raise ValueError(f"Preset {preset.name} has no eval temperature configured")
        if eval_max_tokens is None:
            raise ValueError(f"Preset {preset.name} has no eval max_tokens configured")
    eval_strict_json = eval_cfg.get("strict_json")
    # Only require strict_json if eval is enabled
    if eval_enabled and eval_strict_json is None:
        raise ValueError(f"Preset {preset.name} has no eval strict_json configured - set this in the GUI")
    # NOTE: eval_enable_grounding removed - FPF always uses grounding

    gen_concurrency = concurrency_cfg.get("generation_concurrency") if concurrency_cfg else None
    eval_concurrency_val = concurrency_cfg.get("eval_concurrency") if concurrency_cfg else None
    request_timeout_val = concurrency_cfg.get("request_timeout") if concurrency_cfg else None
    eval_timeout_val = eval_cfg.get("timeout_seconds")
    if eval_timeout_val is None and concurrency_cfg:
        eval_timeout_val = concurrency_cfg.get("eval_timeout")
    # Note: request_timeout, gen_concurrency, eval_concurrency can be None (no timeout/default)
    # eval_timeout is required when eval is enabled
    if eval_enabled and eval_timeout_val is None:
        raise ValueError(f"Preset {preset.name} has no eval timeout configured")

    config = RunConfig(
        user_uuid=user['uuid'],
        document_ids=list(document_contents.keys()),
        document_contents=document_contents,
        instructions=instructions,
        generators=[AdapterGeneratorType(g) for g in preset.generators],
        models=model_names,
        model_settings=model_settings,
        fpf_models=fpf_model_keys,
        gptr_models=gptr_model_keys,
        dr_models=dr_model_keys,
        iterations=_derive_iterations(preset),
        enable_single_eval=eval_enabled,
        enable_pairwise=preset.pairwise_enabled,
        eval_iterations=eval_iterations,
        eval_judge_models=judge_models,
        eval_retries=eval_retries,
        eval_temperature=eval_temperature,
        eval_max_tokens=eval_max_tokens,
        eval_strict_json=eval_strict_json,
        pairwise_top_n=eval_cfg.get("pairwise_top_n"),
        enable_combine=combine_enabled,
        combine_strategy=combine_strategy or "",
        combine_models=combine_models_list if combine_enabled else [],
        combine_max_tokens=combine_max_tokens,
        log_level=preset.log_level,
        request_timeout=request_timeout_val,
        eval_timeout=eval_timeout_val,
        generation_concurrency=gen_concurrency,
        eval_concurrency=eval_concurrency_val,
        fpf_log_output=fpf_log_output,
        fpf_log_file_path=fpf_log_file_path,
        fpf_max_retries=concurrency_cfg.get("fpf_max_retries"),
        fpf_retry_delay=concurrency_cfg.get("fpf_retry_delay"),
        post_combine_top_n=general_cfg.get("post_combine_top_n"),
        single_eval_instructions=single_eval_instructions,
        pairwise_eval_instructions=pairwise_eval_instructions,
        eval_criteria=eval_criteria,
        combine_instructions=combine_instructions,
        # Output settings
        output_destination=preset.output_destination or "library",
        output_filename_template=preset.output_filename_template or "{source_doc_name}_{winner_model}_{timestamp}",
        github_repo_url=preset.github_connection.repo if preset.github_connection else None,
        github_commit_message=preset.github_commit_message or "ACM2: Add winning document",
        preset_id=str(preset.id),
        preset_name=preset.name,
    )
    
    # Launch background task
    background_tasks.add_task(execute_run_background, run.id, config)
    
    return {
        "status": "started",
        "run_id": run.id,
        "preset_id": preset_id,
        "preset_name": preset.name,
    }
