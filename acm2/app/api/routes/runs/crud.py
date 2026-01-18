"""
CRUD operations for runs.

Endpoints for creating, listing, getting, and deleting runs.
"""
import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any, Optional, Dict

from app.infra.db.session import get_user_db
from app.infra.db.repositories import RunRepository
from app.auth.middleware import get_current_user

from ...schemas.runs import (
    RunCreate,
    RunDetail,
    RunList,
    RunSummary,
    RunStatus,
    GeneratorType,
)
from .helpers import to_summary, to_detail

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/runs", response_model=RunSummary)
async def create_run(
    data: RunCreate,
    user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_user_db)
) -> RunSummary:
    """
    Create a new run configuration.
    
    The run starts in PENDING status. Call POST /runs/{id}/start to execute.
    If preset_id is provided, the preset's configuration will be loaded.
    """
    from app.infra.db.repositories import PresetRepository
    
    repo = RunRepository(db, user_id=user['id'])
    preset_repo = PresetRepository(db, user_id=user['id'])
    
    # Require a preset_id: runs must be created from an existing preset
    if not data.preset_id:
        raise HTTPException(status_code=400, detail="Runs must be created from an existing preset; provide a valid preset_id")

    preset = await preset_repo.get_by_id(data.preset_id)
    if not preset:
        raise HTTPException(status_code=404, detail=f"Preset {data.preset_id} not found")
    logger.info(f"Loading config from preset: {preset.name} (id={data.preset_id})")
    
    # Use preset values if available, otherwise use request data or defaults
    document_ids = data.document_ids or (preset.documents if preset else [])
    generators = (preset.generators if preset and preset.generators else [g.value for g in data.generators])
    
    # Get config_overrides first - this has the real configuration
    config_overrides: dict = {}
    if preset and preset.config_overrides:
        config_overrides = dict(preset.config_overrides)
    if getattr(data, "config_overrides", None):
        config_overrides.update(data.config_overrides)
    
    # Get models from config_overrides.fpf or config_overrides.gptr
    models = []
    if preset and config_overrides:
        fpf_cfg = config_overrides.get("fpf", {})
        if fpf_cfg.get("enabled") and fpf_cfg.get("selected_models"):
            for model_str in fpf_cfg["selected_models"]:
                parts = model_str.split(":", 1)
                if len(parts) == 2:
                    models.append({"provider": parts[0], "model": parts[1]})
                else:
                    raise HTTPException(status_code=400, detail="Model entries must include provider prefix (provider:model)")
        gptr_cfg = config_overrides.get("gptr", {})
        if gptr_cfg.get("enabled") and gptr_cfg.get("selected_models"):
            for model_str in gptr_cfg["selected_models"]:
                parts = model_str.split(":", 1)
                if len(parts) == 2:
                    models.append({"provider": parts[0], "model": parts[1]})
                else:
                    raise HTTPException(status_code=400, detail="Model entries must include provider prefix (provider:model)")
    if not models:
        models = [m.model_dump() for m in data.models]
    
    # Get settings from config_overrides
    logger.info(f"DEBUG: RunCreate fields: {data.model_dump().keys()}")
    logger.info(f"DEBUG: Has config_overrides? {hasattr(data, 'config_overrides')} | merged keys: {list(config_overrides.keys()) if config_overrides else 'none'}")
    
    overrides = config_overrides or {}
    general_cfg = overrides.get("general", {})
    eval_cfg = overrides.get("eval", {})
    pairwise_cfg = overrides.get("pairwise", {})
    combine_cfg = overrides.get("combine", {})
    fpf_cfg = overrides.get("fpf", {})
    gptr_cfg = overrides.get("gptr", {})
    concurrency_cfg = overrides.get("concurrency", {})

    if preset:
        logger.info(f"DEBUG: Preset post_combine_top_n: {preset.post_combine_top_n}")
    
    # log_level priority: preset's general_config.log_level > preset.log_level > request override
    resolved_log_level = general_cfg.get("log_level") or (preset.log_level if preset else None) or data.log_level
    if not resolved_log_level:
        raise HTTPException(status_code=400, detail="log_level must be set in preset or request; defaults are disallowed")
    
    config = {
        "document_ids": document_ids,
        "generators": generators,
        "models": models,
        "iterations": general_cfg.get("iterations") or data.iterations,
        "log_level": resolved_log_level,
        "post_combine_top_n": general_cfg.get("post_combine_top_n") or (preset.post_combine_top_n if preset else None),
        "expose_criteria_to_generators": general_cfg.get("expose_criteria_to_generators", False),
        "evaluation_enabled": eval_cfg.get("enabled") if eval_cfg.get("enabled") is not None else (preset.evaluation_enabled if preset else data.evaluation.enabled),
        "pairwise_enabled": pairwise_cfg.get("enabled") if pairwise_cfg.get("enabled") is not None else (preset.pairwise_enabled if preset else data.pairwise.enabled),
        "gptr_config": gptr_cfg if gptr_cfg else (data.gptr_settings.model_dump() if data.gptr_settings else None),
        "fpf_config": fpf_cfg if fpf_cfg else (data.fpf_settings.model_dump() if data.fpf_settings else None),
        "tags": data.tags,
        "generation_instructions_id": (preset.generation_instructions_id if preset else None) or overrides.get("generation_instructions_id"),
        "single_eval_instructions_id": (preset.single_eval_instructions_id if preset else None) or overrides.get("single_eval_instructions_id"),
        "pairwise_eval_instructions_id": (preset.pairwise_eval_instructions_id if preset else None) or overrides.get("pairwise_eval_instructions_id"),
        "eval_criteria_id": (preset.eval_criteria_id if preset else None) or overrides.get("eval_criteria_id"),
        "combine_instructions_id": (preset.combine_instructions_id if preset else None) or overrides.get("combine_instructions_id"),
        "eval_config": eval_cfg,
        "pairwise_config": pairwise_cfg,
        "combine_config": combine_cfg,
        "concurrency_config": concurrency_cfg,
        "config_overrides": overrides,
    }
    
    if combine_cfg or data.combine:
        existing_overrides = config.get("config_overrides", {}) or {}
        existing_overrides["combine"] = combine_cfg if combine_cfg else data.combine.model_dump()
        config["config_overrides"] = existing_overrides
    
    run = await repo.create(
        title=data.name,
        description=data.description,
        preset_id=data.preset_id,
        config=config,
        status=RunStatus.PENDING
    )
    return to_summary(run)


@router.get("/runs/count")
async def count_runs(
    status: Optional[str] = Query(None, description="Filter by status"),
    user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_user_db)
) -> dict:
    """Return total number of runs (optionally filtered by status)."""
    repo = RunRepository(db, user_id=user['id'])
    total = await repo.count(status=status)
    return {"total": total, "status": status}


@router.get("/runs", response_model=RunList)
async def list_runs(
    status: Optional[str] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_user_db)
) -> RunList:
    """
    List all runs with pagination.
    """
    repo = RunRepository(db, user_id=user['id'])
    offset = (page - 1) * page_size
    
    runs = await repo.get_all_with_tasks(limit=page_size, offset=offset, status=status)
    total = 100  # Placeholder
    
    items = [to_summary(r) for r in runs]
    pages = (total + page_size - 1) // page_size
    
    return RunList(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/runs/{run_id}", response_model=RunDetail)
async def get_run(
    run_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_user_db)
) -> Any:
    """
    Get detailed information about a specific run.
    """
    logger.debug(f"Getting run {run_id}")
    repo = RunRepository(db, user_id=user['id'])
    run = await repo.get_with_tasks(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    try:
        return to_detail(run)
    except Exception as e:
        logger.exception(f"Error serializing run {run_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving run: {str(e)}")


@router.delete("/runs/bulk")
async def bulk_delete_runs(
    target: str = Query(..., regex="^(failed|completed_failed)$", description="failed or completed_failed"),
    user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_user_db)
) -> dict:
    """Bulk delete runs by status groups."""
    repo = RunRepository(db, user_id=user['id'])
    if target == "failed":
        statuses = [RunStatus.FAILED.value, RunStatus.CANCELLED.value]
    else:
        statuses = [RunStatus.FAILED.value, RunStatus.COMPLETED.value, RunStatus.CANCELLED.value]
    deleted = await repo.bulk_delete_by_status(statuses)
    return {"status": "ok", "deleted": deleted, "target": target}


@router.delete("/runs/{run_id}")
async def delete_run(
    run_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_user_db)
) -> dict:
    """
    Delete a run.
    
    Only allowed for runs in PENDING, COMPLETED, FAILED, or CANCELLED status.
    """
    repo = RunRepository(db, user_id=user['id'])
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
