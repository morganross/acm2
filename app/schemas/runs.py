from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class GeneratorType(str, Enum):
    FPF = "fpf"
    GPTR = "gptr"

class ModelConfig(BaseModel):
    provider: str
    model: str

class GptrSettings(BaseModel):
    report_type: str = "research_report"
    tone: Optional[str] = None
    retriever: str = "tavily"

class EvaluationSettings(BaseModel):
    enable_single_eval: bool = True
    enable_pairwise: bool = True
    iterations: int = 1
    judge_models: List[str] = []  # REQUIRED - must be set by preset

class PairwiseSettings(BaseModel):
    top_n: Optional[int] = None

class RunCreate(BaseModel):
    name: str
    description: Optional[str] = None
    preset_id: Optional[str] = None
    generators: List[GeneratorType] = []
    models: List[ModelConfig] = []
    document_ids: List[str] = []
    iterations: int = 1
    gptr_settings: Optional[GptrSettings] = None
    fpf_settings: Optional[Dict[str, Any]] = None
    evaluation: EvaluationSettings = EvaluationSettings()
    pairwise: PairwiseSettings = PairwiseSettings()
    tags: List[str] = []
    combine: Optional[Dict[str, Any]] = None
    log_level: Optional[str] = None
    config_overrides: Optional[Dict[str, Any]] = None

class TaskSummary(BaseModel):
    task_id: str
    status: TaskStatus
    progress: float
    message: Optional[str] = None

class RunProgress(BaseModel):
    total_tasks: int
    completed_tasks: int
    running_tasks: int
    failed_tasks: int
    pending_tasks: int
    percent: float

class RunSummary(BaseModel):
    id: str
    name: str
    status: RunStatus
    created_at: datetime
    completed_at: Optional[datetime] = None
    total_cost_usd: float

class RunList(BaseModel):
    runs: List[RunSummary]

class RunDetail(RunSummary):
    description: Optional[str] = None
    generators: List[GeneratorType]
    models: List[Dict[str, Any]]
    document_ids: List[str]
    iterations: int
    tasks: List[TaskSummary]
    evaluation: Dict[str, Any]
    pairwise: Dict[str, Any]
