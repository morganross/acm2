from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

class GptrConfig(BaseModel):
    """Configuration specific to GPT-Researcher adapter."""
    report_type: str = Field("research_report", description="Type of report to generate (research_report, deep, etc.)")
    tone: Optional[str] = Field(None, description="Tone of the report (Objective, etc.)")
    retriever: Optional[str] = Field(None, description="Retriever to use (tavily, duckduckgo, etc.)")
    source_urls: Optional[list[str]] = Field(None, description="List of source URLs to restrict research to")
    
    # Environment variable overrides for this specific run
    env_overrides: Dict[str, str] = Field(default_factory=dict, description="Environment variables to override for the subprocess")

    class Config:
        extra = "ignore"
