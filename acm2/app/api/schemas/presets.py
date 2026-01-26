"""
API Schemas for Presets.

Presets are saved configurations for runs that can be reused.
"""
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field

from .runs import (
    GeneratorType, ModelConfig, GptrSettings, FpfSettings, 
    EvaluationSettings, PairwiseSettings, CombineSettings,
    # Complete config types for preset persistence
    FpfConfigComplete, GptrConfigComplete, DrConfigComplete, MaConfigComplete,
    EvalConfigComplete, PairwiseConfigComplete, CombineConfigComplete,
    GeneralConfigComplete, ConcurrencyConfigComplete,
)


class OutputDestination(str, Enum):
    """Where winning documents are written."""
    NONE = "none"           # Don't save outputs
    LIBRARY = "library"     # Save to Content Library as OUTPUT_DOCUMENT (default)
    GITHUB = "github"       # Also push to GitHub repository


# ============================================================================
# Request Models
# ============================================================================

class PresetCreate(BaseModel):
    """Request to create a new preset."""
    name: str = Field(..., min_length=1, max_length=200, description="Preset name")
    description: Optional[str] = Field(None, max_length=2000)
    
    # Default documents to include
    documents: list[str] = Field(
        default_factory=list,
        description="Default document IDs for this preset"
    )
    
    # Content Library instruction IDs
    single_eval_instructions_id: Optional[str] = Field(None, description="Content ID for single eval instructions")
    pairwise_eval_instructions_id: Optional[str] = Field(None, description="Content ID for pairwise eval instructions")
    eval_criteria_id: Optional[str] = Field(None, description="Content ID for evaluation criteria")
    combine_instructions_id: Optional[str] = Field(None, description="Content ID for combine instructions")
    generation_instructions_id: Optional[str] = Field(None, description="Content ID for FPF generation instructions")
    
    # Complete configuration objects (NEW - for full preset persistence)
    general_config: Optional[GeneralConfigComplete] = None
    fpf_config: Optional[FpfConfigComplete] = None
    gptr_config: Optional[GptrConfigComplete] = None
    dr_config: Optional[DrConfigComplete] = None
    ma_config: Optional[MaConfigComplete] = None
    eval_config: Optional[EvalConfigComplete] = None
    pairwise_config: Optional[PairwiseConfigComplete] = None
    combine_config: Optional[CombineConfigComplete] = None
    concurrency_config: Optional[ConcurrencyConfigComplete] = None
    
    # Logging configuration
    # Options: "ERROR", "WARNING", "INFO", "DEBUG", "VERBOSE"
    # VERBOSE captures FPF output to file for debugging
    log_level: str = Field(default="INFO", description="Log level for run execution")
    
    # GitHub input source configuration
    input_source_type: Optional[str] = Field(None, description="Input source: 'database' or 'github'")
    github_connection_id: Optional[str] = Field(None, description="GitHub connection ID for input")
    github_input_paths: Optional[list[str]] = Field(default=None, description="Paths in GitHub repo to use as input")
    github_output_path: Optional[str] = Field(None, description="Path in GitHub repo for output")
    
    # Output configuration
    output_destination: Optional[OutputDestination] = Field(
        default=OutputDestination.LIBRARY, 
        description="Where to save winning documents: 'none', 'library', or 'github'"
    )
    output_filename_template: Optional[str] = Field(
        default="{source_doc_name}_{winner_model}_{timestamp}",
        description="Template for output filenames"
    )
    github_commit_message: Optional[str] = Field(
        default="ACM2: Add winning document",
        description="Commit message when pushing to GitHub"
    )
    
    # Legacy fields (backward compatibility)
    generators: Optional[list[GeneratorType]] = Field(
        default=None,
        description="Which generators to run (legacy)"
    )
    models: Optional[list[ModelConfig]] = Field(
        default=None,
        description="Models to use (legacy)"
    )
    iterations: Optional[int] = Field(None, ge=1, le=10, description="Number of iterations (legacy)")
    gptr_settings: Optional[GptrSettings] = None
    fpf_settings: Optional[FpfSettings] = None
    evaluation: Optional[EvaluationSettings] = None
    pairwise: Optional[PairwiseSettings] = None
    combine: Optional[CombineSettings] = None


class PresetUpdate(BaseModel):
    """Request to update a preset."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    documents: Optional[list[str]] = None
    
    # Content Library instruction IDs
    single_eval_instructions_id: Optional[str] = None
    pairwise_eval_instructions_id: Optional[str] = None
    eval_criteria_id: Optional[str] = None
    combine_instructions_id: Optional[str] = None
    generation_instructions_id: Optional[str] = None
    
    # Complete configuration objects (NEW)
    general_config: Optional[GeneralConfigComplete] = None
    fpf_config: Optional[FpfConfigComplete] = None
    gptr_config: Optional[GptrConfigComplete] = None
    dr_config: Optional[DrConfigComplete] = None
    ma_config: Optional[MaConfigComplete] = None
    eval_config: Optional[EvalConfigComplete] = None
    pairwise_config: Optional[PairwiseConfigComplete] = None
    combine_config: Optional[CombineConfigComplete] = None
    concurrency_config: Optional[ConcurrencyConfigComplete] = None
    
    # Logging configuration
    log_level: Optional[str] = Field(None, description="Log level for run execution")
    
    # GitHub input source configuration
    input_source_type: Optional[str] = Field(None, description="Input source: 'database' or 'github'")
    github_connection_id: Optional[str] = Field(None, description="GitHub connection ID for input")
    github_input_paths: Optional[list[str]] = Field(default=None, description="Paths in GitHub repo to use as input")
    github_output_path: Optional[str] = Field(None, description="Path in GitHub repo for output")
    
    # Output configuration
    output_destination: Optional[OutputDestination] = Field(
        None, 
        description="Where to save winning documents: 'none', 'library', or 'github'"
    )
    output_filename_template: Optional[str] = Field(
        None,
        description="Template for output filenames"
    )
    github_commit_message: Optional[str] = Field(
        None,
        description="Commit message when pushing to GitHub"
    )
    
    # Legacy fields (backward compatibility)
    generators: Optional[list[GeneratorType]] = None
    models: Optional[list[ModelConfig]] = None
    iterations: Optional[int] = Field(None, ge=1, le=10)
    gptr_settings: Optional[GptrSettings] = None
    fpf_settings: Optional[FpfSettings] = None
    evaluation: Optional[EvaluationSettings] = None
    pairwise: Optional[PairwiseSettings] = None
    combine: Optional[CombineSettings] = None


# ============================================================================
# Response Models
# ============================================================================

class PresetResponse(BaseModel):
    """Full preset response."""
    id: str
    name: str
    description: Optional[str] = None
    
    documents: list[str] = Field(default_factory=list)
    
    # Content Library instruction IDs
    single_eval_instructions_id: Optional[str] = None
    pairwise_eval_instructions_id: Optional[str] = None
    eval_criteria_id: Optional[str] = None
    combine_instructions_id: Optional[str] = None
    generation_instructions_id: Optional[str] = None
    
    # Complete configuration objects (NEW)
    general_config: Optional[GeneralConfigComplete] = None
    fpf_config: Optional[FpfConfigComplete] = None
    gptr_config: Optional[GptrConfigComplete] = None
    dr_config: Optional[DrConfigComplete] = None
    ma_config: Optional[MaConfigComplete] = None
    eval_config: Optional[EvalConfigComplete] = None
    pairwise_config: Optional[PairwiseConfigComplete] = None
    combine_config: Optional[CombineConfigComplete] = None
    concurrency_config: Optional[ConcurrencyConfigComplete] = None
    
    # Logging configuration
    log_level: str = "INFO"
    
    # GitHub input source configuration
    input_source_type: Optional[str] = None
    github_connection_id: Optional[str] = None
    github_input_paths: Optional[list[str]] = None
    github_output_path: Optional[str] = None
    
    # Output configuration
    output_destination: OutputDestination = OutputDestination.LIBRARY
    output_filename_template: Optional[str] = "{source_doc_name}_{winner_model}_{timestamp}"
    github_commit_message: Optional[str] = "ACM2: Add winning document"
    
    # Legacy fields (backward compatibility)
    generators: list[GeneratorType] = Field(default_factory=list)
    models: list[ModelConfig] = Field(default_factory=list)
    iterations: int = 1
    gptr_settings: Optional[GptrSettings] = None
    fpf_settings: Optional[FpfSettings] = None
    evaluation: EvaluationSettings = Field(default_factory=EvaluationSettings)
    pairwise: PairwiseSettings = Field(default_factory=PairwiseSettings)
    combine: CombineSettings = Field(default_factory=CombineSettings)
    
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    # Statistics
    run_count: int = 0
    last_run_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True  # Enable ORM mode


class PresetSummary(BaseModel):
    """Summary preset for list views."""
    id: str
    name: str
    description: Optional[str] = None
    document_count: int = 0
    model_count: int = 0
    iterations: int = 1
    generators: list[GeneratorType] = Field(default_factory=list)
    created_at: datetime
    updated_at: Optional[datetime] = None
    run_count: int = 0
    
    class Config:
        from_attributes = True


class PresetList(BaseModel):
    """Paginated list of presets."""
    items: list[PresetSummary]
    total: int
    page: int
    page_size: int
    pages: int
