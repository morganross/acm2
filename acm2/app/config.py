"""
Application configuration using pydantic-settings.
"""
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # Application
    app_name: str = "ACM2"
    app_version: str = "2.0.0"
    debug: bool = False
    
    # Database
    # Default to a per-user database file in ~/.acm2/acm2.db
    @property
    def default_database_url(self) -> str:
        app_dir = Path.home() / ".acm2"
        app_dir.mkdir(exist_ok=True)
        return f"sqlite+aiosqlite:///{(app_dir / 'acm2.db').as_posix()}"

    database_url: str = "sqlite+aiosqlite:///./acm2.db"
    
    def model_post_init(self, __context):
        if self.database_url == "sqlite+aiosqlite:///./acm2.db":
             self.database_url = self.default_database_url
    
    # API Keys (optional, loaded from env)
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    tavily_api_key: Optional[str] = None
    encryption_key: Optional[str] = None

    # ACM API key + rate limiting
    api_key: Optional[str] = None
    rate_limit_max_requests: int = 120
    rate_limit_window_seconds: int = 60
    
    # Paths
    data_dir: Path = Path("./data")
    documents_dir: Path = Path("./data/documents")
    artifacts_dir: Path = Path("./data/artifacts")
    logs_dir: Path = Path("./logs")

    # Seed package (required for deterministic per-user initialization)
    seed_preset_id: Optional[str] = None
    seed_version: Optional[str] = None
    
    # Execution
    max_concurrent_tasks: int = 3
    # Note: Operational timeouts are controlled by sub-systems (FPF, GPTR, Evaluation)
    # This is only a safety ceiling for catastrophic failures - should never be reached
    safety_ceiling_seconds: int = 86400  # 24 hours
    
    # CORS
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:5174", "http://127.0.0.1:5173", "http://127.0.0.1:5174"]
    
    def ensure_dirs(self) -> None:
        """Create required directories if they don't exist."""
        for dir_path in [self.data_dir, self.documents_dir, self.artifacts_dir, self.logs_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    settings = Settings()
    settings.ensure_dirs()
    return settings
