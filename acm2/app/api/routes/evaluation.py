"""
Evaluation API Routes.

Endpoints for triggering and managing document evaluations.
"""
import logging
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from ...evaluation import (
    DocumentInput,
    EvaluationConfig,
    EvaluationInput,
    EvaluationService,
    SingleDocEvaluator,
    SingleEvalConfig,
    PairwiseEvaluator,
    PairwiseConfig,
)
from app.auth.middleware import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/evaluation", tags=["evaluation"])


# ============================================================================
# Request/Response Schemas
# ============================================================================

class DocumentEvalRequest(BaseModel):
    """Request to evaluate a single document."""
    doc_id: str = Field(..., description="Document identifier")
    content: str = Field(..., description="Document content to evaluate")
    
class BatchEvalRequest(BaseModel):
    """Request to evaluate multiple documents."""
    documents: List[DocumentEvalRequest]
    iterations: int = Field(default=1, ge=1, le=10)
    judge_models: List[str] = Field(default=["gpt-5"])
    run_id: Optional[str] = Field(default=None, description="Optional run ID to associate with")

class SingleEvalRequest(BaseModel):
    """Request for single-doc evaluation only."""
    documents: List[DocumentEvalRequest]
    iterations: int = Field(default=1, ge=1, le=10)
    judge_models: List[str] = Field(default=["gpt-5"])

class PairwiseEvalRequest(BaseModel):
    """Request for pairwise evaluation."""
    documents: List[DocumentEvalRequest]
    iterations: int = Field(default=1, ge=1, le=5)
    judge_models: List[str] = Field(default=["gpt-5"])
    top_n: Optional[int] = Field(default=None, description="Only compare top N by single-eval score")
    single_eval_scores: Optional[dict[str, float]] = Field(
        default=None, 
        description="Pre-computed single-eval scores for top-N filtering"
    )

class CriterionScoreResponse(BaseModel):
    """Score for a single criterion."""
    criterion: str
    score: int
    reason: str

class SingleEvalResponse(BaseModel):
    """Response for single-doc evaluation."""
    doc_id: str
    avg_score: float
    scores: List[CriterionScoreResponse]
    num_evaluations: int

class EloRatingResponse(BaseModel):
    """Elo rating for a document."""
    doc_id: str
    rating: float
    wins: int
    losses: int

class PairwiseEvalResponse(BaseModel):
    """Response for pairwise evaluation."""
    total_comparisons: int
    total_pairs: int
    rankings: List[EloRatingResponse]
    winner_doc_id: Optional[str]

class FullEvalResponse(BaseModel):
    """Response for full evaluation (single + pairwise)."""
    run_id: str
    single_eval: dict[str, SingleEvalResponse]
    pairwise: Optional[PairwiseEvalResponse]
    winner_doc_id: Optional[str]
    duration_seconds: float

class EvalJobStatus(BaseModel):
    """Status of an async evaluation job."""
    job_id: str
    status: str  # pending, running, completed, failed
    progress: float  # 0-100
    result: Optional[FullEvalResponse] = None
    error: Optional[str] = None


# ============================================================================
# In-Memory Job Store (replace with Redis/DB in production)
# ============================================================================

eval_jobs: dict[str, dict] = {}


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/single", response_model=dict[str, SingleEvalResponse])
async def evaluate_single_docs(
    request: SingleEvalRequest,
    user: Dict[str, Any] = Depends(get_current_user),
) -> dict[str, SingleEvalResponse]:
    """
    Run single-document graded evaluation.
    
    Evaluates each document against criteria and returns scores.
    This is typically called immediately after each document is generated.
    """
    config = SingleEvalConfig(
        iterations=request.iterations,
        judge_models=request.judge_models,
    )
    evaluator = SingleDocEvaluator(config, user_id=user["uuid"])
    
    docs = [
        DocumentInput(doc_id=d.doc_id, content=d.content)
        for d in request.documents
    ]
    
    summaries = await evaluator.evaluate_documents(docs)
    
    return {
        doc_id: SingleEvalResponse(
            doc_id=doc_id,
            avg_score=summary.avg_score,
            scores=[
                CriterionScoreResponse(
                    criterion=crit,
                    score=int(score),
                    reason="",  # Aggregated scores don't have reasons
                )
                for crit, score in summary.scores_by_criterion.items()
            ],
            num_evaluations=summary.num_evaluations,
        )
        for doc_id, summary in summaries.items()
    }


@router.post("/pairwise", response_model=PairwiseEvalResponse)
async def evaluate_pairwise(
    request: PairwiseEvalRequest,
    user: Dict[str, Any] = Depends(get_current_user),
) -> PairwiseEvalResponse:
    """
    Run pairwise comparison evaluation.
    
    Compares documents head-to-head and produces Elo rankings.
    This should be called AFTER all single-doc evaluations are complete.
    
    If single_eval_scores is provided, it will be used for top-N filtering.
    """
    config = PairwiseConfig(
        iterations=request.iterations,
        judge_models=request.judge_models,
        top_n=request.top_n,
    )
    evaluator = PairwiseEvaluator(config, user_id=user["uuid"])
    
    doc_ids = [d.doc_id for d in request.documents]
    contents = {d.doc_id: d.content for d in request.documents}
    
    # Filter to top-N if scores provided
    if request.single_eval_scores and request.top_n:
        doc_ids = evaluator.filter_top_n(
            doc_ids,
            request.single_eval_scores,
            request.top_n,
        )
        contents = {d: contents[d] for d in doc_ids}
    
    summary = await evaluator.evaluate_all_pairs(doc_ids, contents)
    
    return PairwiseEvalResponse(
        total_comparisons=summary.total_comparisons,
        total_pairs=summary.total_pairs,
        rankings=[
            EloRatingResponse(
                doc_id=r.doc_id,
                rating=r.rating,
                wins=r.wins,
                losses=r.losses,
            )
            for r in summary.elo_ratings
        ],
        winner_doc_id=summary.winner_doc_id,
    )


@router.post("/full", response_model=FullEvalResponse)
async def evaluate_full(
    request: BatchEvalRequest,
    user: Dict[str, Any] = Depends(get_current_user),
) -> FullEvalResponse:
    """
    Run full evaluation pipeline: single-doc + pairwise.
    
    1. Runs single-doc evaluation on all documents
    2. Uses single-doc scores for top-N filtering
    3. Runs pairwise comparison on filtered set
    4. Returns combined results with final winner
    """
    run_id = request.run_id or str(uuid4())[:8]
    start_time = datetime.utcnow()
    
    config = EvaluationConfig(
        iterations=request.iterations,
        judge_models=request.judge_models,
        enable_single_eval=True,
        enable_pairwise=True,
    )
    service = EvaluationService(config, user_id=user["uuid"])
    
    docs = [
        DocumentInput(doc_id=d.doc_id, content=d.content)
        for d in request.documents
    ]
    
    result = await service.evaluate(EvaluationInput(
        documents=docs,
        run_id=run_id,
    ))
    
    # Convert to response
    single_responses = {}
    if result.single_eval_summaries:
        for doc_id, summary in result.single_eval_summaries.items():
            single_responses[doc_id] = SingleEvalResponse(
                doc_id=doc_id,
                avg_score=summary.avg_score,
                scores=[
                    CriterionScoreResponse(
                        criterion=crit,
                        score=int(score),
                        reason="",
                    )
                    for crit, score in summary.scores_by_criterion.items()
                ],
                num_evaluations=summary.num_evaluations,
            )
    
    pairwise_response = None
    if result.pairwise_summary:
        pairwise_response = PairwiseEvalResponse(
            total_comparisons=result.pairwise_summary.total_comparisons,
            total_pairs=result.pairwise_summary.total_pairs,
            rankings=[
                EloRatingResponse(
                    doc_id=r.doc_id,
                    rating=r.rating,
                    wins=r.wins,
                    losses=r.losses,
                )
                for r in result.pairwise_summary.elo_ratings
            ],
            winner_doc_id=result.pairwise_summary.winner_doc_id,
        )
    
    return FullEvalResponse(
        run_id=run_id,
        single_eval=single_responses,
        pairwise=pairwise_response,
        winner_doc_id=result.winner_doc_id,
        duration_seconds=result.duration_seconds,
    )


@router.post("/full/async")
async def evaluate_full_async(
    request: BatchEvalRequest,
    background_tasks: BackgroundTasks,
    user: Dict[str, Any] = Depends(get_current_user),
) -> dict:
    """
    Start full evaluation pipeline as a background job.
    
    Returns immediately with a job ID. Poll /evaluation/jobs/{job_id} for status.
    """
    job_id = str(uuid4())[:8]
    
    eval_jobs[job_id] = {
        "status": "pending",
        "progress": 0.0,
        "result": None,
        "error": None,
        "created_at": datetime.utcnow(),
    }
    
    async def run_eval():
        try:
            eval_jobs[job_id]["status"] = "running"
            result = await evaluate_full(request)
            eval_jobs[job_id]["status"] = "completed"
            eval_jobs[job_id]["progress"] = 100.0
            eval_jobs[job_id]["result"] = result.model_dump()
        except Exception as e:
            logger.error(f"Eval job {job_id} failed: {e}")
            eval_jobs[job_id]["status"] = "failed"
            eval_jobs[job_id]["error"] = str(e)
    
    background_tasks.add_task(run_eval)
    
    return {"job_id": job_id, "status": "pending"}


@router.get("/jobs/{job_id}", response_model=EvalJobStatus)
async def get_eval_job_status(
    job_id: str,
    user: Dict[str, Any] = Depends(get_current_user),
) -> EvalJobStatus:
    """
    Get status of an async evaluation job.
    """
    job = eval_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return EvalJobStatus(
        job_id=job_id,
        status=job["status"],
        progress=job["progress"],
        result=FullEvalResponse(**job["result"]) if job["result"] else None,
        error=job["error"],
    )


@router.get("/criteria")
async def get_evaluation_criteria(
    user: Dict[str, Any] = Depends(get_current_user),
) -> dict:
    """
    Get evaluation criteria.
    
    Note: Default criteria have been removed. Criteria must be configured
    in the Content Library and referenced via eval_criteria_id in presets.
    This endpoint now returns an empty list to indicate no defaults exist.
    """
    return {
        "criteria": [],
        "message": "No default criteria. Configure criteria in Content Library."
    }
