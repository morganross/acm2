"""
Presets API Routes.

Endpoints for managing saved preset configurations.
"""
import logging
from datetime import datetime
from typing import Optional
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.session import get_db, async_session_factory
from app.infra.db.repositories import PresetRepository, RunRepository, DocumentRepository
from app.infra.db.models.run import RunStatus
from app.services.run_executor import get_executor, RunConfig
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
    
    try:
        executor = get_executor()
        result = await executor.execute(run_id, config)
        
        # Update run in DB
        async with async_session_factory() as session:
            run_repo = RunRepository(session)
            
            if result.status.value == "completed":
                await run_repo.complete(
                    run_id, 
                    results_summary={
                        "winner": result.winner_doc_id,
                        "generated_count": len(result.generated_docs),
                        "eval_count": len(result.single_eval_results or {}),
                        "combined_doc_id": result.combined_doc.doc_id if result.combined_doc else None,
                        "post_combine_eval": asdict(result.post_combine_eval_results) if result.post_combine_eval_results else None,
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
        # Clean up: remove file handler and flush
        file_handler.flush()
        file_handler.close()
        root_logger.removeHandler(file_handler)


def _get_runs_safely(preset):
    """Safely get runs if loaded, else return empty list."""
    try:
        ins = inspect(preset)
        if ins and 'runs' in ins.unloaded:
            return []
        return preset.runs or []
    except Exception:
        return []

def _derive_iterations(preset) -> int:
    """Derive iterations from config_overrides.general or fall back to 1."""
    try:
        general_cfg = (preset.config_overrides or {}).get("general") or {}
        return general_cfg.get("iterations") or 1
    except Exception:
        return 1


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
    
    # Extract values for DB columns (use new config if available, fall back to legacy)
    iterations = data.general_config.iterations if data.general_config else (data.iterations or 1)
    evaluation_enabled = data.eval_config.enabled if data.eval_config else (data.evaluation.enabled if data.evaluation else True)
    pairwise_enabled = data.pairwise_config.enabled if data.pairwise_config else (data.pairwise.enabled if data.pairwise else False)
    
    # Extract log_level from general_config or top-level field
    log_level = data.log_level or (data.general_config.log_level if data.general_config and hasattr(data.general_config, 'log_level') else "INFO")
    
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
        update_data["iterations"] = data.general_config.iterations
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
    
    if data.iterations is not None and "iterations" not in update_data:
        update_data["iterations"] = data.iterations
    
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
    document_contents = {}
    
    # preset.documents is a list of paths or IDs? 
    # Based on PresetCreate schema, it's List[str].
    # Let's assume they are paths for now, as per ACM 1.0 legacy, 
    # but ideally they should be IDs.
    # If they are paths, we need to find the document by path.
    
    for doc_ref in (preset.documents or []):
        # Try to find by ID first (if it's a UUID)
        doc = await doc_repo.get_by_id(doc_ref)
        if not doc:
            # Try by path
            doc = await doc_repo.get_by_path(doc_ref)
            
        if doc and doc.content:
            document_contents[doc.id] = doc.content
        elif doc:
            # If content is missing in DB, maybe read from file?
            # For now, we'll use a placeholder if content is missing
            document_contents[doc.id] = f"Content for {doc.name}"
            logger.warning(f"Document content missing for {doc.name} ({doc.id})")
        else:
            logger.warning(f"Document reference not found: {doc_ref}")

    # Build execution config
    combine_config = preset.config_overrides.get("combine", {}) if preset.config_overrides else {}
    
    # Get FPF instructions from preset's fpf_config
    fpf_config = preset.fpf_config or {}
    instructions = fpf_config.get("prompt_template", "") if isinstance(fpf_config, dict) else ""
    
    config = RunConfig(
        document_ids=list(document_contents.keys()),
        document_contents=document_contents,
        instructions=instructions,
        generators=[AdapterGeneratorType(g) for g in (preset.generators or [])],
        models=[m["model"] for m in (preset.models or [])],
        iterations=preset.iterations,
        enable_single_eval=preset.evaluation_enabled,
        enable_pairwise=preset.pairwise_enabled,
        # Map other settings...
        eval_iterations=1, # Default
        eval_judge_models=[preset.config_overrides.get("evaluation", {}).get("eval_model")] if preset.config_overrides and preset.config_overrides.get("evaluation", {}).get("eval_model") else [],
        pairwise_top_n=None,
        enable_combine=combine_config.get("enabled", False),
        combine_strategy=combine_config.get("strategy", ""),
        combine_models=[combine_config.get("model", "")] if combine_config.get("enabled", False) else [],
        log_level=getattr(preset, 'log_level', 'INFO') or 'INFO',
    )
    
    # Launch background task
    background_tasks.add_task(execute_run_background, run.id, config)
    
    return {
        "status": "started",
        "run_id": run.id,
        "preset_id": preset_id,
        "preset_name": preset.name,
    }
