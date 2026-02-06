"""
Artifact endpoints for runs.

Endpoints for reports, logs, and generated documents.
"""
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any

from app.infra.db.session import get_user_db
from app.infra.db.repositories import RunRepository
from app.auth.middleware import get_current_user
from ....config import get_settings
from ....evaluation.reports.generator import ReportGenerator
from .helpers import to_detail

logger = logging.getLogger(__name__)
router = APIRouter()


def get_run_root(user_uuid: str, run_id: str) -> Path:
    settings = get_settings()
    return settings.data_dir / f"user_{user_uuid}" / "runs" / run_id


@router.get("/runs/{run_id}/report")
async def get_run_report(
    run_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_user_db)
):
    """
    Generate and download the HTML report for a run.
    Includes the Evaluation Timeline Chart.
    """
    repo = RunRepository(db, user_uuid=user['uuid'])
    run = await repo.get_with_tasks(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    run_root = get_run_root(user['uuid'], run_id)
    reports_dir = run_root / "reports"
    generator = ReportGenerator(reports_dir)
    
    try:
        run_data = to_detail(run).model_dump()
        report_path = generator.generate_html_report(run, run_data)
        return FileResponse(report_path)
    except Exception as e:
        logger.error(f"Failed to generate report for run {run_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")


@router.get("/runs/{run_id}/logs")
async def get_run_logs(
    run_id: str,
    lines: int = Query(100, ge=1, le=10000, description="Number of lines to return"),
    offset: int = Query(0, ge=0, description="Line offset from start"),
    include_fpf: bool = Query(False, description="Include FPF output log (VERBOSE mode only)"),
    user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_user_db)
) -> dict:
    """
    Get run logs with pagination.
    
    Returns log lines from the run's log files.
    For VERBOSE mode runs, can also include FPF subprocess output.
    """
    repo = RunRepository(db, user_uuid=user['uuid'])
    run = await repo.get_by_id(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    log_dir = get_run_root(user['uuid'], run_id) / "logs"
    
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
                fpf_lines = fpf_content[-100:] if len(fpf_content) > 100 else fpf_content
            except Exception as e:
                logger.warning(f"Failed to read FPF log: {e}")
    
    run_config = run.config or {}
    if "log_level" not in run_config:
        raise ValueError("run.config must contain 'log_level' - no fallback defaults allowed")
    log_level = run_config["log_level"]
    
    return {
        "run_id": run_id,
        "log_level": log_level,
        "total_lines": total_lines,
        "offset": offset,
        "lines": log_lines,
        "fpf_available": fpf_available,
        "fpf_lines": fpf_lines if include_fpf else None,
    }


@router.get("/runs/{run_id}/generated/{doc_id:path}")
async def get_generated_doc_content(
    run_id: str,
    doc_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_user_db)
) -> dict:
    """
    Get the content of a generated document.
    
    Returns the markdown content of a generated or combined document.
    Documents are stored in data/user_{user_uuid}/runs/{run_id}/generated/{doc_id}.md
    """
    repo = RunRepository(db, user_uuid=user['uuid'])
    run = await repo.get_by_id(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    # Sanitize doc_id for filename
    safe_doc_id = doc_id.replace(':', '_').replace('/', '_').replace('\\', '_')
    file_path = get_run_root(user['uuid'], run_id) / "generated" / f"{safe_doc_id}.md"
    
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
