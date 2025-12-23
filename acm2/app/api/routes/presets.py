"""
Presets API Routes.

Endpoints for managing saved preset configurations.
"""
import json
import logging
from datetime import datetime
from typing import Optional
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.session import get_db, async_session_factory
from app.infra.db.repositories import PresetRepository, RunRepository, DocumentRepository, ContentRepository
from app.infra.db.models.run import RunStatus
from app.services.run_executor import get_executor, RunConfig, RunExecutor
from app.utils.logging_utils import get_run_logger
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
    
    logger.info(f"Starting background execution for run {run_id}")
    
    executor = get_executor()
    result = await executor.execute(run_id, config)
    
    # Update run in DB
    async with async_session_factory() as session:
        run_repo = RunRepository(session)
        
        if result.status.value == "completed":
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
            logger.info(f"Run {run_id} completed successfully")
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
    """Get iterations from config_overrides.general - NO FALLBACKS."""
    general_cfg = preset.config_overrides["general"]
    iterations = general_cfg["iterations"]
    if iterations is None:
        raise ValueError(f"Preset {preset.name} ({preset.id}) has no iterations configured - set this in the GUI")
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
        # Logging
        log_level=getattr(preset, 'log_level', None) or "INFO",
        # Legacy fields (backward compatibility)
        generators=[GeneratorType(g) for g in (preset.generators or ["gptr"])],
        models=[ModelConfig(**m) for m in (preset.models or [])],
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
    db: AsyncSession = Depends(get_db)
) -> PresetResponse:
    """
    Create a new preset configuration.
    """
    repo = PresetRepository(db)
    
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
    
    # Extract values for DB columns - NO FALLBACKS, values MUST be set
    if data.eval_config:
        evaluation_enabled = data.eval_config.enabled
    elif data.evaluation:
        evaluation_enabled = data.evaluation.enabled
    else:
        raise ValueError("evaluation_enabled must be set in preset")
    
    if data.pairwise_config:
        pairwise_enabled = data.pairwise_config.enabled
    elif data.pairwise:
        pairwise_enabled = data.pairwise.enabled
    else:
        raise ValueError("pairwise_enabled must be set in preset")
    
    # Extract log_level - MUST be set, no fallback
    if data.log_level:
        log_level = data.log_level
    elif data.general_config and hasattr(data.general_config, 'log_level') and data.general_config.log_level:
        log_level = data.general_config.log_level
    else:
        raise ValueError("log_level must be set in preset")
    
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
    )
    
    return _preset_to_response(preset)


@router.get("", response_model=PresetList)
async def list_presets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
) -> PresetList:
    """
    List all presets with pagination.
    """
    repo = PresetRepository(db)
    
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
    db: AsyncSession = Depends(get_db)
) -> PresetResponse:
    """
    Get a specific preset by ID.
    """
    repo = PresetRepository(db)
    preset = await repo.get_by_id(preset_id)
    
    if not preset or preset.is_deleted:
        raise HTTPException(status_code=404, detail="Preset not found")
    
    return _preset_to_response(preset)


@router.put("/{preset_id}", response_model=PresetResponse)
async def update_preset(
    preset_id: str,
    data: PresetUpdate,
    db: AsyncSession = Depends(get_db)
) -> PresetResponse:
    """
    Update a preset.
    """
    repo = PresetRepository(db)
    preset = await repo.get_by_id(preset_id)
    
    if not preset or preset.is_deleted:
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
    
    if data.pairwise_config is not None:
        overrides["pairwise"] = data.pairwise_config.model_dump()
        update_data["pairwise_enabled"] = data.pairwise_config.enabled
    
    if data.combine_config is not None:
        overrides["combine"] = data.combine_config.model_dump()
    
    if data.concurrency_config is not None:
        overrides["concurrency"] = data.concurrency_config.model_dump()
    
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
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Delete a preset.
    
    By default performs a soft delete. Use permanent=true for hard delete.
    """
    repo = PresetRepository(db)
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
    db: AsyncSession = Depends(get_db)
) -> PresetResponse:
    """
    Create a copy of an existing preset with a new name.
    """
    repo = PresetRepository(db)
    
    # Check original exists
    original = await repo.get_by_id(preset_id)
    if not original or original.is_deleted:
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
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Execute a preset by creating and starting a new run.
    
    This is a convenience endpoint that:
    1. Creates a new run from the preset configuration
    2. Immediately starts the run
    
    Returns the created run ID.
    """
    repo = PresetRepository(db)
    preset = await repo.get_by_id(preset_id)
    
    if not preset or preset.is_deleted:
        raise HTTPException(status_code=404, detail="Preset not found")
    
    # Create a new run from the preset
    run_repo = RunRepository(db)
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
    doc_repo = DocumentRepository(db)
    content_repo = ContentRepository(db)
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
    
    # Get eval config - REQUIRED
    eval_cfg = preset.config_overrides.get("eval", {}) if preset.config_overrides else {}
    eval_iterations = eval_cfg.get("iterations")
    if eval_iterations is None:
        raise ValueError(f"Preset {preset.name} has no eval_config.iterations - set this in the GUI")
    judge_models = eval_cfg.get("judge_models")
    if not judge_models:
        raise ValueError(f"Preset {preset.name} has no eval_config.judge_models - set this in the GUI")
    
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
    
    # Get log_level - REQUIRED
    if not preset.log_level:
        raise ValueError(f"Preset {preset.name} has no log_level - set this in the GUI")
    
    fpf_cfg = preset.config_overrides.get("fpf", {}) if preset.config_overrides else {}
    gptr_cfg = preset.config_overrides.get("gptr", {}) if preset.config_overrides else {}
    concurrency_cfg = preset.config_overrides.get("concurrency", {}) if preset.config_overrides else {}

    model_settings = {}
    model_names: list[str] = []
    for model_entry in (preset.models or []):
        if not isinstance(model_entry, dict):
            raise ValueError(f"Preset {preset.name} has invalid model entry: {model_entry}")
        provider = model_entry.get("provider")
        base_model = model_entry.get("model")
        temperature = model_entry.get("temperature")
        max_tokens = model_entry.get("max_tokens")

        if temperature is None:
            temperature = fpf_cfg.get("temperature") or gptr_cfg.get("temperature")
        if max_tokens is None:
            max_tokens = fpf_cfg.get("max_tokens") or gptr_cfg.get("max_tokens")
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

    eval_temperature = eval_cfg.get("temperature") or fpf_cfg.get("temperature")
    eval_max_tokens = eval_cfg.get("max_tokens") or fpf_cfg.get("max_tokens")
    eval_retries = eval_cfg.get("retries")
    if eval_retries is None:
        raise ValueError(f"Preset {preset.name} has no eval_config.retries - set this in the GUI")
    if eval_temperature is None:
        raise ValueError(f"Preset {preset.name} has no eval temperature configured")
    if eval_max_tokens is None:
        raise ValueError(f"Preset {preset.name} has no eval max_tokens configured")
    eval_strict_json = eval_cfg.get("strict_json", True)
    eval_enable_grounding = eval_cfg.get("enable_grounding", True)

    gen_concurrency = concurrency_cfg.get("generation_concurrency") if concurrency_cfg else None
    eval_concurrency_val = concurrency_cfg.get("eval_concurrency") if concurrency_cfg else None
    request_timeout_val = concurrency_cfg.get("request_timeout") if concurrency_cfg else None
    eval_timeout_val = eval_cfg.get("timeout_seconds")
    if eval_timeout_val is None and concurrency_cfg:
        eval_timeout_val = concurrency_cfg.get("eval_timeout")
    if eval_timeout_val is None:
        raise ValueError(f"Preset {preset.name} has no eval timeout configured")

    config = RunConfig(
        document_ids=list(document_contents.keys()),
        document_contents=document_contents,
        instructions=instructions,
        generators=[AdapterGeneratorType(g) for g in preset.generators],
        models=model_names,
        model_settings=model_settings,
        iterations=_derive_iterations(preset),
        enable_single_eval=preset.evaluation_enabled,
        enable_pairwise=preset.pairwise_enabled,
        eval_iterations=eval_iterations,
        eval_judge_models=judge_models,
        eval_retries=eval_retries,
        eval_temperature=eval_temperature,
        eval_max_tokens=eval_max_tokens,
        eval_strict_json=eval_strict_json,
        eval_enable_grounding=eval_enable_grounding,
        pairwise_top_n=eval_cfg.get("pairwise_top_n"),
        enable_combine=combine_enabled,
        combine_strategy=combine_strategy or "",
        combine_models=combine_models_list if combine_enabled else [],
        log_level=preset.log_level,
        max_retries=concurrency_cfg.get("max_retries") if concurrency_cfg else preset.max_retries,
        retry_delay=concurrency_cfg.get("retry_delay") if concurrency_cfg else preset.retry_delay,
        request_timeout=request_timeout_val or preset.request_timeout,
        eval_timeout=eval_timeout_val or preset.eval_timeout,
        generation_concurrency=gen_concurrency or preset.generation_concurrency,
        eval_concurrency=eval_concurrency_val or preset.eval_concurrency,
        fpf_log_output=preset.fpf_log_output or "file",
        fpf_log_file_path=preset.fpf_log_file_path or f"logs/{run.id}/fpf_output.log",
        post_combine_top_n=preset.post_combine_top_n,
        single_eval_instructions=single_eval_instructions,
        pairwise_eval_instructions=pairwise_eval_instructions,
        eval_criteria=eval_criteria,
        combine_instructions=combine_instructions,
    )
    
    # Launch background task
    background_tasks.add_task(execute_run_background, run.id, config)
    
    return {
        "status": "started",
        "run_id": run.id,
        "preset_id": preset_id,
        "preset_name": preset.name,
    }
