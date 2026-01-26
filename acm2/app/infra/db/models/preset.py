"""
Preset SQLAlchemy model.

A Preset is a saved configuration for running evaluations.
"""
import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infra.db.base import Base

if TYPE_CHECKING:
    from app.infra.db.models.run import Run
    from app.infra.db.models.content import Content
    from app.infra.db.models.github_connection import GitHubConnection


def generate_id() -> str:
    return str(uuid.uuid4())


class InputSourceType(str, Enum):
    """Where input documents come from."""
    DATABASE = "database"
    GITHUB = "github"


class OutputDestination(str, Enum):
    """Where winning documents are written."""
    NONE = "none"           # Only save to database as OUTPUT_DOCUMENT content
    LIBRARY = "library"     # Save to Content Library only (default)
    GITHUB = "github"       # Also push to GitHub repository


class Preset(Base):
    """
    A saved configuration/preset for running evaluations.
    
    Presets define:
    - Which documents to process
    - Which models to use
    - Which generators (FPF, GPTR) to run
    - How many iterations
    - Whether to run evaluation and pairwise
    """
    
    __tablename__ = "presets"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)  # Multi-tenancy: owner user ID
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(default=None, onupdate=datetime.utcnow)
    
    # Basic info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Configuration (stored as JSON)
    documents: Mapped[list] = mapped_column(JSON, default=list)  # List of document paths/IDs
    models: Mapped[list] = mapped_column(JSON, default=list)     # List of model names
    generators: Mapped[list] = mapped_column(JSON, default=list) # ['fpf', 'gptr']
    
    # Execution settings
    iterations: Mapped[int] = mapped_column(Integer, default=1)  # Number of generation iterations
    evaluation_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    pairwise_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Generator-specific config (stored as JSON)
    gptr_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    fpf_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Logging configuration
    # Options: "ERROR", "WARNING", "INFO", "DEBUG", "VERBOSE"
    # VERBOSE captures FPF output to file for debugging
    log_level: Mapped[str] = mapped_column(String(20), default="INFO")
    
    # =========================================================================
    # Timing & Retry Configuration
    # =========================================================================
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    retry_delay: Mapped[float] = mapped_column(default=2.0)
    request_timeout: Mapped[int] = mapped_column(Integer, default=600)
    eval_timeout: Mapped[int] = mapped_column(Integer, default=600)
    
    # FPF API retry settings (for transient errors like 429, 500s)
    fpf_max_retries: Mapped[int] = mapped_column(Integer, default=3)
    fpf_retry_delay: Mapped[float] = mapped_column(default=1.0)
    
    # Eval parse retry settings (for JSON parse failures, not API errors)
    eval_retries: Mapped[int] = mapped_column(Integer, default=3)
    
    # Concurrency Configuration
    generation_concurrency: Mapped[int] = mapped_column(Integer, default=5)
    eval_concurrency: Mapped[int] = mapped_column(Integer, default=5)
    
    # Iteration Configuration (moved from above, now required)
    # iterations field already exists above - will need to make non-nullable
    eval_iterations: Mapped[int] = mapped_column(Integer, default=1)
    
    # FPF Logging Configuration
    fpf_log_output: Mapped[str] = mapped_column(String(20), default="file")  # 'stream', 'file', 'none'
    fpf_log_file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Post-Combine Configuration
    post_combine_top_n: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Extra settings
    config_overrides: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # =========================================================================
    # NEW: Input Source Configuration
    # =========================================================================
    
    # Where do input documents come from?
    input_source_type: Mapped[str] = mapped_column(
        String(20), default=InputSourceType.DATABASE.value
    )
    
    # For DATABASE inputs: list of Content IDs (content_type=INPUT_DOCUMENT)
    input_content_ids: Mapped[list] = mapped_column(JSON, default=list)
    
    # For GITHUB inputs
    github_connection_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("github_connections.id"), nullable=True
    )
    github_input_paths: Mapped[list] = mapped_column(JSON, default=list)  # ["/inputs/doc1.md", ...]
    github_output_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # "/outputs/"
    
    # =========================================================================
    # Output Configuration
    # =========================================================================
    
    # Where do winning documents get written?
    output_destination: Mapped[str] = mapped_column(
        String(20), default=OutputDestination.LIBRARY.value
    )
    # Filename template for outputs (supports {source_doc_name}, {winner_model}, {timestamp}, {run_id})
    output_filename_template: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, default="{source_doc_name}_{winner_model}_{timestamp}"
    )
    # Commit message for GitHub output
    github_commit_message: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True, default="ACM2: Add winning document"
    )
    
    # =========================================================================
    # NEW: Content References (all stored in DB)
    # =========================================================================
    
    # Generation phase
    generation_instructions_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("contents.id"), nullable=True
    )
    
    # Evaluation phase
    single_eval_instructions_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("contents.id"), nullable=True
    )
    pairwise_eval_instructions_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("contents.id"), nullable=True
    )
    eval_criteria_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("contents.id"), nullable=True
    )
    
    # Combine phase
    combine_instructions_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("contents.id"), nullable=True
    )
    
    # Soft delete
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Relationships
    runs: Mapped[list["Run"]] = relationship("Run", back_populates="preset")
    
    # Content relationships
    github_connection: Mapped[Optional["GitHubConnection"]] = relationship(
        "GitHubConnection", foreign_keys=[github_connection_id]
    )
    generation_instructions: Mapped[Optional["Content"]] = relationship(
        "Content", foreign_keys=[generation_instructions_id]
    )
    single_eval_instructions: Mapped[Optional["Content"]] = relationship(
        "Content", foreign_keys=[single_eval_instructions_id]
    )
    pairwise_eval_instructions: Mapped[Optional["Content"]] = relationship(
        "Content", foreign_keys=[pairwise_eval_instructions_id]
    )
    eval_criteria: Mapped[Optional["Content"]] = relationship(
        "Content", foreign_keys=[eval_criteria_id]
    )
    combine_instructions: Mapped[Optional["Content"]] = relationship(
        "Content", foreign_keys=[combine_instructions_id]
    )
    
    def __repr__(self) -> str:
        return f"<Preset(id={self.id}, name={self.name})>"
