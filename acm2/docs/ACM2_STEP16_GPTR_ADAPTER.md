# ACM 2.0 Step 16: GPT-Researcher Adapter

> **Platform:** Windows, Linux, macOS. Python + SQLite. No Docker.

---

## 1. Overview

The GPT-Researcher Adapter integrates the open-source `gpt-researcher` library into ACM 2.0, enabling automated research report generation with full cost tracking and rate limiting.

**Why needed:**
- GPT-Researcher performs multi-step web research autonomously
- Each research run makes dozens of LLM calls (planning, scraping, summarizing, writing)
- Without ACM 2.0 integration, costs are invisible and unbounded
- ACM 2.0 wraps GPT-R to track every token, enforce budgets, and log results

**What the adapter does:**
1. Accepts research queries via ACM 2.0 API/CLI
2. Configures and launches GPT-Researcher with user options
3. Captures streaming progress, final report, sources, and images
4. Extracts token costs from GPT-R's internal tracking
5. Stores results in ACM 2.0 database for history and analytics
6. Enforces rate limits and budget caps before/during execution

**Scope:** This adapter handles the standard `GPTResearcher` class. Multi-agent LangGraph orchestration (chief editor, researcher, writer, etc.) is out of scope for v1.

---

## 2. GPT-Researcher Background

GPT-Researcher is an autonomous research agent that performs web research and generates reports.

**Installation:**
```bash
pip install gpt-researcher
```

**Required Environment Variables:**
```bash
OPENAI_API_KEY=sk-...          # Or other LLM provider
TAVILY_API_KEY=tvly-...        # Default web retriever
```

**Core API:**
```python
from gpt_researcher import GPTResearcher

researcher = GPTResearcher(
    query="What are the latest AI developments?",
    report_type="research_report",  # or detailed_report, deep, etc.
    report_source="web",            # or local, hybrid
    tone="Objective",
)
await researcher.conduct_research()
report = await researcher.write_report()
```

**Report Types:**
| Type | Description | Time | Cost |
|------|-------------|------|------|
| `research_report` | Standard research, ~2000 words | ~3 min | ~$0.10 |
| `detailed_report` | Extended report, ~5000 words | ~5 min | ~$0.20 |
| `deep` | Recursive exploration with breadth/depth | ~5 min | ~$0.40 |
| `resource_report` | Bibliography of sources | ~2 min | ~$0.05 |
| `outline_report` | Structured outline only | ~1 min | ~$0.03 |
| `custom_report` | User-defined prompt/format | varies | varies |
| `subtopic_report` | Report on specific subtopic | ~2 min | ~$0.08 |

**Report Sources:**
- `web` - Internet search via retriever (default)
- `local` - Local documents only (DOC_PATH)
- `hybrid` - Web + local documents
- `static` - Restrict to specific URLs (source_urls)
- `langchain_documents` - Pre-loaded LangChain docs
- `langchain_vectorstore` - Vector store retrieval

**Tones:** Objective, Formal, Analytical, Persuasive, Informative, Explanatory, Descriptive, Critical, Comparative, Speculative, Reflective, Narrative, Humorous, Optimistic, Pessimistic, Sarcastic, Inspirational

**LLM Configuration:**
- `FAST_LLM` - Quick tasks (default: gpt-4o-mini)
- `SMART_LLM` - Complex reasoning (default: gpt-4.1)
- `STRATEGIC_LLM` - Planning/orchestration (default: o4-mini)

**Retrievers:** tavily (default), bing, google, duckduckgo, serper, googleSerp, searx, arxiv, semantic_scholar, pubmed, custom

**Key Getters:**
```python
researcher.get_costs()              # Total USD spent
researcher.get_source_urls()        # List of source URLs
researcher.get_research_sources()   # Full source objects
researcher.get_research_images()    # Image URLs found
researcher.get_research_context()   # Aggregated context
```

---

## 3. Adapter Interface

The GPT-R adapter follows the same pattern as the FPF adapter (Step 9): a Python class that wraps the external tool and returns a standardized result.

```python
# acm2/adapters/gptr_adapter.py

from abc import ABC, abstractmethod
from typing import Optional, List
from acm2.schemas.gptr import GptrConfig, GptrRunResult

class GptrAdapterBase(ABC):
    """Abstract base class for GPT-Researcher adapters."""
    
    @abstractmethod
    async def run_research(
        self,
        query: str,
        config: GptrConfig,
        progress_callback: Optional[callable] = None,
    ) -> GptrRunResult:
        """
        Execute a GPT-Researcher run.
        
        Args:
            query: The research question/topic
            config: GptrConfig with report_type, source, tone, etc.
            progress_callback: Optional async callback for streaming updates
            
        Returns:
            GptrRunResult with report, sources, costs, etc.
        """
        pass
    
    @abstractmethod
    async def cancel(self) -> None:
        """Cancel an in-progress research run."""
        pass


class GptrAdapter(GptrAdapterBase):
    """Concrete GPT-Researcher adapter implementation."""
    
    def __init__(self, acm2_config: dict):
        """
        Args:
            acm2_config: ACM 2.0 config with env vars, budget limits, etc.
        """
        self.acm2_config = acm2_config
        self._researcher = None
        self._cancelled = False
    
    async def run_research(
        self,
        query: str,
        config: GptrConfig,
        progress_callback: Optional[callable] = None,
    ) -> GptrRunResult:
        from gpt_researcher import GPTResearcher
        import time
        
        start_time = time.time()
        self._cancelled = False
        
        # Build GPTResearcher with config
        self._researcher = GPTResearcher(
            query=query,
            report_type=config.report_type,
            report_source=config.report_source,
            tone=config.tone,
            source_urls=config.source_urls,
            documents=config.documents,
        )
        
        # Conduct research (with optional progress streaming)
        await self._researcher.conduct_research()
        
        if self._cancelled:
            raise RuntimeError("Research cancelled")
        
        # Generate report
        report = await self._researcher.write_report()
        
        # Extract results
        return GptrRunResult(
            report_content=report,
            report_type=config.report_type,
            sources=self._researcher.get_research_sources(),
            source_urls=self._researcher.get_source_urls(),
            images=self._researcher.get_research_images(),
            costs=self._researcher.get_costs(),
            duration_seconds=time.time() - start_time,
            metadata={
                "query": query,
                "tone": config.tone,
                "report_source": config.report_source,
            }
        )
    
    async def cancel(self) -> None:
        self._cancelled = True
        # GPT-R doesn't have native cancel, but we can flag it
```

**Integration Point:** The adapter is instantiated by ACM 2.0's runner module, which enforces rate limits before calling `run_research()` and logs results after completion.

---

## 4. GptrRunResult Schema

The result schema captures everything returned by a GPT-Researcher run.

```python
# acm2/schemas/gptr.py

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class GptrSource(BaseModel):
    """A single source from GPT-Researcher."""
    url: str
    title: Optional[str] = None
    snippet: Optional[str] = None  # Content excerpt
    raw_content: Optional[str] = None  # Full scraped content (if available)


class GptrRunResult(BaseModel):
    """Result of a GPT-Researcher run."""
    
    # Core output
    report_content: str = Field(..., description="The generated report in Markdown")
    report_type: str = Field(..., description="research_report, detailed_report, deep, etc.")
    
    # Sources
    sources: List[GptrSource] = Field(default_factory=list, description="Structured source objects")
    source_urls: List[str] = Field(default_factory=list, description="Flat list of source URLs")
    
    # Media
    images: List[str] = Field(default_factory=list, description="Image URLs found during research")
    
    # Cost tracking
    costs: float = Field(0.0, description="Total USD cost from GPT-R's get_costs()")
    token_count: Optional[int] = Field(None, description="Total tokens if available")
    
    # Timing
    duration_seconds: float = Field(..., description="Wall-clock time for research")
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional info")
    
    # Status
    success: bool = True
    error_message: Optional[str] = None


class GptrRunResultDB(GptrRunResult):
    """Extended schema for database storage."""
    id: int
    acm2_run_id: int  # FK to acm2_runs table
    query: str
    created_at: datetime
```

**Usage:**
```python
result = await adapter.run_research(query, config)
print(f"Report: {len(result.report_content)} chars")
print(f"Sources: {len(result.sources)}")
print(f"Cost: ${result.costs:.4f}")
print(f"Time: {result.duration_seconds:.1f}s")
```

---

## 5. Configuration Options

The `GptrConfig` schema defines all options for a GPT-Researcher run.

```python
# acm2/schemas/gptr.py

from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Optional


class ReportType(str, Enum):
    RESEARCH_REPORT = "research_report"
    DETAILED_REPORT = "detailed_report"
    DEEP = "deep"
    RESOURCE_REPORT = "resource_report"
    OUTLINE_REPORT = "outline_report"
    CUSTOM_REPORT = "custom_report"
    SUBTOPIC_REPORT = "subtopic_report"


class ReportSource(str, Enum):
    WEB = "web"
    LOCAL = "local"
    HYBRID = "hybrid"
    STATIC = "static"
    LANGCHAIN_DOCUMENTS = "langchain_documents"
    LANGCHAIN_VECTORSTORE = "langchain_vectorstore"


class Tone(str, Enum):
    OBJECTIVE = "Objective"
    FORMAL = "Formal"
    ANALYTICAL = "Analytical"
    PERSUASIVE = "Persuasive"
    INFORMATIVE = "Informative"
    EXPLANATORY = "Explanatory"
    DESCRIPTIVE = "Descriptive"
    CRITICAL = "Critical"
    COMPARATIVE = "Comparative"
    SPECULATIVE = "Speculative"
    REFLECTIVE = "Reflective"
    NARRATIVE = "Narrative"
    HUMOROUS = "Humorous"
    OPTIMISTIC = "Optimistic"
    PESSIMISTIC = "Pessimistic"


class Retriever(str, Enum):
    TAVILY = "tavily"
    BING = "bing"
    GOOGLE = "google"
    DUCKDUCKGO = "duckduckgo"
    SERPER = "serper"
    SEARX = "searx"
    ARXIV = "arxiv"
    SEMANTIC_SCHOLAR = "semantic_scholar"
    PUBMED = "pubmed"


class GptrConfig(BaseModel):
    """Configuration for a GPT-Researcher run."""
    
    # Core options
    report_type: ReportType = Field(ReportType.RESEARCH_REPORT, description="Type of report")
    report_source: ReportSource = Field(ReportSource.WEB, description="Where to get info")
    tone: Tone = Field(Tone.OBJECTIVE, description="Writing tone")
    
    # Source restrictions
    source_urls: Optional[List[str]] = Field(None, description="Restrict to these URLs (static mode)")
    doc_path: Optional[str] = Field(None, description="Path to local documents")
    documents: Optional[List[str]] = Field(None, description="Pre-loaded document contents")
    
    # Report parameters
    max_subtopics: int = Field(3, description="Max subtopics for detailed reports")
    total_words: int = Field(1000, description="Target word count")
    
    # Retriever
    retriever: Retriever = Field(Retriever.TAVILY, description="Search provider")
    
    # LLM overrides (use env var defaults if None)
    fast_llm: Optional[str] = Field(None, description="Override FAST_LLM")
    smart_llm: Optional[str] = Field(None, description="Override SMART_LLM")
    strategic_llm: Optional[str] = Field(None, description="Override STRATEGIC_LLM")
    
    # Deep research options
    deep_research_breadth: int = Field(4, description="Topics per level")
    deep_research_depth: int = Field(2, description="Recursion depth")
    deep_research_concurrency: int = Field(4, description="Parallel research tasks")
    
    # Custom prompt (for custom_report type)
    custom_prompt: Optional[str] = Field(None, description="Custom report prompt")
    
    # ACM 2.0 integration
    budget_limit: Optional[float] = Field(None, description="Max USD to spend")
    timeout_seconds: Optional[int] = Field(None, description="Max execution time")
```

**Example Configs:**

```python
# Quick web research
config = GptrConfig(
    report_type=ReportType.RESEARCH_REPORT,
    tone=Tone.OBJECTIVE,
)

# Deep research with budget cap
config = GptrConfig(
    report_type=ReportType.DEEP,
    deep_research_breadth=3,
    deep_research_depth=2,
    budget_limit=0.50,
)

# Local document research
config = GptrConfig(
    report_type=ReportType.RESEARCH_REPORT,
    report_source=ReportSource.LOCAL,
    doc_path="/path/to/docs",
)

# Restricted to specific URLs
config = GptrConfig(
    report_type=ReportType.RESEARCH_REPORT,
    report_source=ReportSource.STATIC,
    source_urls=["https://example.com/article1", "https://example.com/article2"],
)
```

---

## 6. Environment Variables

GPT-Researcher reads configuration from environment variables. ACM 2.0 passes these through when invoking the adapter.

### Required

| Variable | Description | Example |
|----------|-------------|----------|
| `OPENAI_API_KEY` | OpenAI API key (or other LLM provider) | `sk-...` |
| `TAVILY_API_KEY` | Tavily API key for web search | `tvly-...` |

### Optional LLM Configuration

| Variable | Description | Default |
|----------|-------------|----------|
| `FAST_LLM` | Model for quick tasks | `openai:gpt-4o-mini` |
| `SMART_LLM` | Model for complex reasoning | `openai:gpt-4.1` |
| `STRATEGIC_LLM` | Model for planning | `openai:o4-mini` |
| `EMBEDDING_MODEL` | Embedding model | `openai:text-embedding-3-small` |
| `TEMPERATURE` | LLM temperature | `0.4` |

### Optional Retriever/Scraper

| Variable | Description | Default |
|----------|-------------|----------|
| `RETRIEVER` | Search provider | `tavily` |
| `SCRAPER` | Web scraper | `bs` (BeautifulSoup) |
| `BING_API_KEY` | For Bing retriever | |
| `GOOGLE_API_KEY` | For Google retriever | |
| `SERPER_API_KEY` | For Serper retriever | |
| `FIRECRAWL_API_KEY` | For Firecrawl scraper | |

### Optional Deep Research

| Variable | Description | Default |
|----------|-------------|----------|
| `DEEP_RESEARCH_BREADTH` | Topics per level | `4` |
| `DEEP_RESEARCH_DEPTH` | Recursion depth | `2` |
| `DEEP_RESEARCH_CONCURRENCY` | Parallel tasks | `4` |

### Optional Local Research

| Variable | Description | Default |
|----------|-------------|----------|
| `DOC_PATH` | Path to local documents | `./my-docs` |
| `LANGCHAIN_API_KEY` | For LangChain integration | |

### ACM 2.0 Environment Handling

ACM 2.0 manages GPT-R environment variables in three ways:

**1. Pass-through from system environment:**
```python
# ACM 2.0 inherits OPENAI_API_KEY from system
import os
os.environ["OPENAI_API_KEY"]  # Already set by user
```

**2. Override via ACM 2.0 config:**
```yaml
# acm2_config.yaml
gptr:
  fast_llm: "openai:gpt-4o-mini"
  smart_llm: "openai:gpt-4o"
  retriever: "tavily"
```

**3. Per-run override via GptrConfig:**
```python
config = GptrConfig(
    fast_llm="anthropic:claude-3-haiku",
    smart_llm="anthropic:claude-3-sonnet",
)
```

**Priority:** Per-run config > ACM 2.0 config > System environment

---

## 7. Execution Modes

The adapter supports all GPT-Researcher execution modes.

### 7.1 Standard Research (`research_report`)

Default mode. Searches web, aggregates sources, generates ~2000 word report.

```python
config = GptrConfig(report_type=ReportType.RESEARCH_REPORT)
result = await adapter.run_research("Latest developments in quantum computing", config)
# ~3 min, ~$0.10
```

### 7.2 Detailed Research (`detailed_report`)

Extended report with subtopics. Generates ~5000 words with table of contents.

```python
config = GptrConfig(
    report_type=ReportType.DETAILED_REPORT,
    max_subtopics=5,
    total_words=5000,
)
result = await adapter.run_research("Comprehensive guide to machine learning", config)
# ~5 min, ~$0.20
```

### 7.3 Deep Research (`deep`)

Recursive exploration. Generates sub-queries, researches each, synthesizes findings.

```python
config = GptrConfig(
    report_type=ReportType.DEEP,
    deep_research_breadth=4,  # 4 topics per level
    deep_research_depth=2,    # 2 levels deep
    deep_research_concurrency=4,
)
result = await adapter.run_research("Future of renewable energy", config)
# ~5 min, ~$0.40 with o3-mini
```

**Deep Research Flow:**
1. Generate initial breadth queries from main topic
2. Research each query in parallel
3. For each result, generate deeper queries
4. Recurse until depth reached
5. Synthesize all findings into final report

### 7.4 Local Document Research (`report_source=local`)

Research only from local documents. No web search.

```python
config = GptrConfig(
    report_type=ReportType.RESEARCH_REPORT,
    report_source=ReportSource.LOCAL,
    doc_path="/path/to/documents",
)
result = await adapter.run_research("Summarize company policies", config)
```

**Supported formats:** PDF, DOCX, TXT, MD, JSON, CSV

### 7.5 Hybrid Research (`report_source=hybrid`)

Combines web search with local documents.

```python
config = GptrConfig(
    report_type=ReportType.RESEARCH_REPORT,
    report_source=ReportSource.HYBRID,
    doc_path="/path/to/internal-docs",
)
result = await adapter.run_research("Compare our product to competitors", config)
```

### 7.6 Static/Restricted Sources (`source_urls`)

Research only from specified URLs. No general web search.

```python
config = GptrConfig(
    report_type=ReportType.RESEARCH_REPORT,
    report_source=ReportSource.STATIC,
    source_urls=[
        "https://arxiv.org/abs/2301.12345",
        "https://example.com/whitepaper.pdf",
    ],
)
result = await adapter.run_research("Analyze these papers", config)
```

### Execution Mode Summary

| Mode | Source | Time | Cost | Use Case |
|------|--------|------|------|----------|
| `research_report` | Web | ~3 min | ~$0.10 | General research |
| `detailed_report` | Web | ~5 min | ~$0.20 | In-depth reports |
| `deep` | Web | ~5 min | ~$0.40 | Exploratory research |
| `local` | Documents | ~2 min | ~$0.05 | Internal docs |
| `hybrid` | Web + Docs | ~4 min | ~$0.15 | Competitive analysis |
| `static` | Specific URLs | ~2 min | ~$0.05 | Focused analysis |

---

## 8. Async Execution Pattern

GPT-Researcher is fully async. The ACM 2.0 adapter integrates with this pattern.

### Basic Async Flow

```python
# GPT-Researcher native API
from gpt_researcher import GPTResearcher

researcher = GPTResearcher(
    query="What is climate change?",
    report_type="research_report",
)
await researcher.conduct_research()  # Searches, scrapes, aggregates
report = await researcher.write_report()  # Generates final report
```

### ACM 2.0 Adapter Wrapping

```python
# acm2/adapters/gptr_adapter.py

import asyncio
from datetime import datetime

class GptrAdapter:
    async def run_research(
        self,
        query: str,
        config: GptrConfig,
        progress_callback: Optional[callable] = None,
    ) -> GptrRunResult:
        from gpt_researcher import GPTResearcher
        
        started_at = datetime.utcnow()
        
        # Build researcher with config
        researcher = GPTResearcher(
            query=query,
            report_type=config.report_type.value,
            report_source=config.report_source.value,
            tone=config.tone.value,
            source_urls=config.source_urls,
        )
        
        # Conduct research (long-running)
        await researcher.conduct_research()
        
        # Write report
        report = await researcher.write_report()
        
        # Extract all results
        return GptrRunResult(
            report_content=report,
            report_type=config.report_type.value,
            sources=self._extract_sources(researcher.get_research_sources()),
            source_urls=researcher.get_source_urls(),
            images=researcher.get_research_images(),
            costs=researcher.get_costs(),
            duration_seconds=(datetime.utcnow() - started_at).total_seconds(),
            started_at=started_at,
            completed_at=datetime.utcnow(),
            metadata={"query": query},
        )
    
    def _extract_sources(self, raw_sources: list) -> List[GptrSource]:
        """Convert GPT-R source dicts to GptrSource objects."""
        return [
            GptrSource(
                url=s.get("url", ""),
                title=s.get("title"),
                snippet=s.get("content", "")[:500],
                raw_content=s.get("content"),
            )
            for s in raw_sources
        ]
```

### Running from Sync Context

For API endpoints or CLI that aren't async:

```python
import asyncio

def run_research_sync(query: str, config: GptrConfig) -> GptrRunResult:
    adapter = GptrAdapter(acm2_config)
    return asyncio.run(adapter.run_research(query, config))
```

### Timeout Handling

```python
async def run_research_with_timeout(
    self,
    query: str,
    config: GptrConfig,
) -> GptrRunResult:
    timeout = config.timeout_seconds or 600  # Default 10 min
    
    try:
        result = await asyncio.wait_for(
            self.run_research(query, config),
            timeout=timeout,
        )
        return result
    except asyncio.TimeoutError:
        return GptrRunResult(
            report_content="",
            report_type=config.report_type.value,
            success=False,
            error_message=f"Research timed out after {timeout}s",
            duration_seconds=timeout,
        )
```

### Concurrent Runs

ACM 2.0 can run multiple GPT-R queries in parallel:

```python
async def run_batch(queries: List[str], config: GptrConfig) -> List[GptrRunResult]:
    adapter = GptrAdapter(acm2_config)
    tasks = [adapter.run_research(q, config) for q in queries]
    return await asyncio.gather(*tasks, return_exceptions=True)
```

**Note:** Be mindful of API rate limits when running concurrent research.

---

## 9. Progress and Streaming

GPT-Researcher supports real-time progress updates. ACM 2.0 captures these for UI feedback.

### Deep Research Progress Callback

Deep research provides granular progress:

```python
from gpt_researcher import GPTResearcher

async def on_progress(progress: dict):
    """Callback for deep research progress updates."""
    print(f"Depth: {progress['current_depth']}/{progress['total_depth']}")
    print(f"Breadth: {progress['current_breadth']}/{progress['total_breadth']}")
    print(f"Query: {progress['current_query']}")
    print(f"Completed: {progress['completed_queries']}/{progress['total_queries']}")

researcher = GPTResearcher(
    query="Future of AI",
    report_type="deep",
)
await researcher.conduct_research(on_progress=on_progress)
```

**Progress dict fields:**
| Field | Type | Description |
|-------|------|-------------|
| `current_depth` | int | Current recursion level |
| `total_depth` | int | Max recursion depth |
| `current_breadth` | int | Current topic index at this level |
| `total_breadth` | int | Total topics at this level |
| `current_query` | str | Query being researched now |
| `completed_queries` | int | Queries finished |
| `total_queries` | int | Total queries planned |

### WebSocket Streaming

GPT-Researcher can stream to WebSocket for real-time UI:

```python
import json
from fastapi import WebSocket

async def research_websocket(websocket: WebSocket, query: str):
    await websocket.accept()
    
    async def stream_output(data: dict):
        await websocket.send_json(data)
    
    researcher = GPTResearcher(
        query=query,
        report_type="research_report",
        websocket=websocket,  # Native websocket support
    )
    
    await researcher.conduct_research()
    report = await researcher.write_report()
    
    await websocket.send_json({"type": "complete", "report": report})
    await websocket.close()
```

### ACM 2.0 Progress Schema

ACM 2.0 normalizes progress for its own streaming:

```python
# acm2/schemas/gptr.py

class GptrProgress(BaseModel):
    """Progress update from GPT-Researcher."""
    run_id: str
    status: str  # "researching", "writing", "complete", "error"
    
    # Overall progress
    percent_complete: float  # 0.0 to 1.0
    elapsed_seconds: float
    
    # Deep research specific
    current_depth: Optional[int] = None
    total_depth: Optional[int] = None
    current_query: Optional[str] = None
    completed_queries: Optional[int] = None
    total_queries: Optional[int] = None
    
    # Interim data
    sources_found: int = 0
    current_cost: float = 0.0
    
    # Message for UI
    message: str = ""
```

### ACM 2.0 Adapter with Progress

```python
class GptrAdapter:
    async def run_research(
        self,
        query: str,
        config: GptrConfig,
        progress_callback: Optional[callable] = None,
    ) -> GptrRunResult:
        
        start_time = time.time()
        
        async def internal_progress(gptr_progress: dict):
            """Convert GPT-R progress to ACM 2.0 format."""
            if progress_callback:
                acm_progress = GptrProgress(
                    run_id=self.run_id,
                    status="researching",
                    percent_complete=self._calc_percent(gptr_progress),
                    elapsed_seconds=time.time() - start_time,
                    current_depth=gptr_progress.get("current_depth"),
                    total_depth=gptr_progress.get("total_depth"),
                    current_query=gptr_progress.get("current_query"),
                    completed_queries=gptr_progress.get("completed_queries"),
                    total_queries=gptr_progress.get("total_queries"),
                    message=f"Researching: {gptr_progress.get('current_query', '')}",
                )
                await progress_callback(acm_progress)
        
        researcher = GPTResearcher(
            query=query,
            report_type=config.report_type.value,
        )
        
        # Pass progress callback for deep research
        if config.report_type == ReportType.DEEP:
            await researcher.conduct_research(on_progress=internal_progress)
        else:
            await researcher.conduct_research()
        
        # Notify writing phase
        if progress_callback:
            await progress_callback(GptrProgress(
                run_id=self.run_id,
                status="writing",
                percent_complete=0.9,
                elapsed_seconds=time.time() - start_time,
                message="Generating report...",
            ))
        
        report = await researcher.write_report()
        
        return GptrRunResult(...)
    
    def _calc_percent(self, progress: dict) -> float:
        """Calculate overall percent from GPT-R progress."""
        total = progress.get("total_queries", 1)
        completed = progress.get("completed_queries", 0)
        return min(0.9, completed / total)  # Cap at 90%, reserve 10% for writing
```

### UI Integration

The Web GUI (Step 11) displays progress in real-time:

```javascript
// Frontend WebSocket handler
ws.onmessage = (event) => {
    const progress = JSON.parse(event.data);
    updateProgressBar(progress.percent_complete * 100);
    updateStatusMessage(progress.message);
    if (progress.current_query) {
        addToActivityLog(`Researching: ${progress.current_query}`);
    }
};
```

---

## 10. Error Handling

The adapter handles errors gracefully and returns structured error information.

### Error Types

```python
# acm2/adapters/gptr_errors.py

from enum import Enum

class GptrErrorType(str, Enum):
    API_KEY_MISSING = "api_key_missing"
    API_KEY_INVALID = "api_key_invalid"
    RATE_LIMITED = "rate_limited"
    NETWORK_ERROR = "network_error"
    SCRAPE_FAILED = "scrape_failed"
    TIMEOUT = "timeout"
    BUDGET_EXCEEDED = "budget_exceeded"
    PARTIAL_FAILURE = "partial_failure"
    UNKNOWN = "unknown"


class GptrError(Exception):
    """GPT-Researcher error with structured info."""
    def __init__(
        self,
        error_type: GptrErrorType,
        message: str,
        partial_result: Optional[GptrRunResult] = None,
    ):
        self.error_type = error_type
        self.message = message
        self.partial_result = partial_result
        super().__init__(message)
```

### API Key Validation

```python
def _validate_env_vars(self) -> None:
    """Check required environment variables before research."""
    import os
    
    if not os.environ.get("OPENAI_API_KEY"):
        raise GptrError(
            GptrErrorType.API_KEY_MISSING,
            "OPENAI_API_KEY environment variable not set"
        )
    
    if not os.environ.get("TAVILY_API_KEY"):
        raise GptrError(
            GptrErrorType.API_KEY_MISSING,
            "TAVILY_API_KEY environment variable not set"
        )
```

### Rate Limit Handling

```python
import openai
import httpx

async def run_research(self, query: str, config: GptrConfig) -> GptrRunResult:
    try:
        self._validate_env_vars()
        result = await self._execute_research(query, config)
        return result
        
    except openai.RateLimitError as e:
        raise GptrError(
            GptrErrorType.RATE_LIMITED,
            f"OpenAI rate limit: {e}. Retry after cooldown."
        )
    
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            raise GptrError(
                GptrErrorType.RATE_LIMITED,
                f"Tavily rate limit: {e}"
            )
        raise GptrError(
            GptrErrorType.NETWORK_ERROR,
            f"HTTP error: {e}"
        )
    
    except httpx.RequestError as e:
        raise GptrError(
            GptrErrorType.NETWORK_ERROR,
            f"Network error during research: {e}"
        )
```

### Timeout Handling

```python
import asyncio

async def run_research_safe(self, query: str, config: GptrConfig) -> GptrRunResult:
    timeout = config.timeout_seconds or 600
    
    try:
        return await asyncio.wait_for(
            self.run_research(query, config),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        raise GptrError(
            GptrErrorType.TIMEOUT,
            f"Research timed out after {timeout} seconds"
        )
```

### Budget Enforcement

```python
async def run_research(self, query: str, config: GptrConfig) -> GptrRunResult:
    # Pre-check budget
    if config.budget_limit:
        estimated_cost = self._estimate_cost(config)
        if estimated_cost > config.budget_limit:
            raise GptrError(
                GptrErrorType.BUDGET_EXCEEDED,
                f"Estimated cost ${estimated_cost:.2f} exceeds budget ${config.budget_limit:.2f}"
            )
    
    # ... run research ...
    
    # Post-check actual cost
    actual_cost = researcher.get_costs()
    if config.budget_limit and actual_cost > config.budget_limit:
        # Return result but flag the overage
        result.metadata["budget_exceeded"] = True
        result.metadata["budget_overage"] = actual_cost - config.budget_limit
    
    return result
```

### Partial Results (Deep Research)

Deep research may partially fail if some sub-queries error:

```python
async def _handle_deep_research(self, query: str, config: GptrConfig) -> GptrRunResult:
    """Deep research with partial failure handling."""
    
    failed_queries = []
    
    async def on_progress(progress: dict):
        if progress.get("error"):
            failed_queries.append({
                "query": progress.get("current_query"),
                "error": progress.get("error"),
            })
    
    researcher = GPTResearcher(query=query, report_type="deep")
    await researcher.conduct_research(on_progress=on_progress)
    report = await researcher.write_report()
    
    result = GptrRunResult(
        report_content=report,
        # ... other fields ...
    )
    
    if failed_queries:
        result.success = True  # Still succeeded overall
        result.metadata["partial_failures"] = failed_queries
        result.metadata["failed_query_count"] = len(failed_queries)
    
    return result
```

### Error Response Schema

```python
class GptrErrorResponse(BaseModel):
    """Structured error response for API."""
    success: bool = False
    error_type: GptrErrorType
    error_message: str
    partial_result: Optional[GptrRunResult] = None
    retry_after_seconds: Optional[int] = None  # For rate limits
```

### Retry Strategy

ACM 2.0 can retry transient failures:

```python
import asyncio
from typing import List

RETRYABLE_ERRORS = [
    GptrErrorType.RATE_LIMITED,
    GptrErrorType.NETWORK_ERROR,
]

async def run_research_with_retry(
    self,
    query: str,
    config: GptrConfig,
    max_retries: int = 3,
    backoff_seconds: List[int] = [5, 15, 60],
) -> GptrRunResult:
    
    last_error = None
    
    for attempt in range(max_retries + 1):
        try:
            return await self.run_research(query, config)
        except GptrError as e:
            last_error = e
            if e.error_type not in RETRYABLE_ERRORS:
                raise  # Non-retryable, fail immediately
            
            if attempt < max_retries:
                wait = backoff_seconds[min(attempt, len(backoff_seconds) - 1)]
                await asyncio.sleep(wait)
    
    raise last_error
```

---

## 11. Cost Tracking

GPT-Researcher tracks token costs internally. ACM 2.0 extracts and stores these for analytics.

### GPT-R Cost API

```python
# Get total cost after research
researcher = GPTResearcher(query="...")
await researcher.conduct_research()
await researcher.write_report()

total_cost = researcher.get_costs()  # Returns float in USD
print(f"Total cost: ${total_cost:.4f}")
```

```python
# Add external costs (e.g., retriever API costs)
researcher.add_costs(0.05)  # Add $0.05 for Tavily usage
```

### Cost Breakdown by Phase

GPT-R costs come from multiple phases:

| Phase | LLM Used | Typical Cost |
|-------|----------|-------------|
| Planning | FAST_LLM | ~$0.01 |
| Search query generation | FAST_LLM | ~$0.01 |
| Content summarization | FAST_LLM | ~$0.02 |
| Report writing | SMART_LLM | ~$0.05 |
| Deep research (per level) | STRATEGIC_LLM | ~$0.10 |

**Note:** Retriever costs (Tavily, Bing, etc.) are external and not tracked by GPT-R's `get_costs()`.

### ACM 2.0 Cost Extraction

```python
# acm2/adapters/gptr_adapter.py

class GptrAdapter:
    async def run_research(self, query: str, config: GptrConfig) -> GptrRunResult:
        researcher = GPTResearcher(query=query, report_type=config.report_type.value)
        
        await researcher.conduct_research()
        report = await researcher.write_report()
        
        # Extract costs
        llm_cost = researcher.get_costs()
        
        # Estimate retriever cost (not tracked by GPT-R)
        retriever_cost = self._estimate_retriever_cost(config, researcher)
        
        return GptrRunResult(
            report_content=report,
            costs=llm_cost,
            metadata={
                "llm_cost": llm_cost,
                "retriever_cost": retriever_cost,
                "total_estimated_cost": llm_cost + retriever_cost,
            },
        )
    
    def _estimate_retriever_cost(self, config: GptrConfig, researcher) -> float:
        """Estimate retriever API cost (not tracked by GPT-R)."""
        source_count = len(researcher.get_source_urls())
        
        # Tavily: ~$0.001 per search
        if config.retriever == Retriever.TAVILY:
            return source_count * 0.001
        
        # Bing: ~$0.003 per search
        if config.retriever == Retriever.BING:
            return source_count * 0.003
        
        return 0.0  # Free retrievers (duckduckgo, arxiv)
```

### Cost Storage in ACM 2.0

Costs are stored at multiple levels:

```python
# Per-artifact cost (gptr_artifacts table)
class GptrArtifact(BaseModel):
    id: int
    run_id: int
    document_id: int
    query: str
    report_content: str
    llm_cost: float
    retriever_cost: float
    total_cost: float

# Per-run aggregate (runs table)
class Run(BaseModel):
    id: int
    generator: str  # "gptr"
    total_llm_cost: float
    total_retriever_cost: float
    total_cost: float
    artifact_count: int
```

### Cost Aggregation Queries

```sql
-- Total cost for a run
SELECT SUM(total_cost) as run_total
FROM gptr_artifacts
WHERE run_id = ?;

-- Cost by report type
SELECT 
    json_extract(metadata, '$.report_type') as report_type,
    COUNT(*) as count,
    AVG(total_cost) as avg_cost,
    SUM(total_cost) as total_cost
FROM gptr_artifacts
GROUP BY report_type;

-- Cost trend over time
SELECT 
    DATE(created_at) as date,
    SUM(total_cost) as daily_cost
FROM gptr_artifacts
GROUP BY DATE(created_at)
ORDER BY date;
```

### Budget Alerts

ACM 2.0 can alert when costs exceed thresholds:

```python
# acm2/services/cost_monitor.py

class CostMonitor:
    def __init__(self, config: dict):
        self.daily_budget = config.get("daily_budget", 10.0)
        self.per_run_budget = config.get("per_run_budget", 1.0)
    
    async def check_budget(self, run_id: int) -> None:
        """Check if run is within budget."""
        run_cost = await self._get_run_cost(run_id)
        
        if run_cost > self.per_run_budget:
            raise GptrError(
                GptrErrorType.BUDGET_EXCEEDED,
                f"Run cost ${run_cost:.2f} exceeds budget ${self.per_run_budget:.2f}"
            )
    
    async def check_daily_budget(self) -> float:
        """Check remaining daily budget."""
        today_cost = await self._get_daily_cost()
        remaining = self.daily_budget - today_cost
        return max(0, remaining)
```

### Cost Estimation

Estimate cost before running:

```python
def estimate_cost(config: GptrConfig, query_count: int = 1) -> dict:
    """Estimate cost for a GPT-R run."""
    
    base_costs = {
        ReportType.RESEARCH_REPORT: 0.10,
        ReportType.DETAILED_REPORT: 0.20,
        ReportType.DEEP: 0.40,
        ReportType.RESOURCE_REPORT: 0.05,
        ReportType.OUTLINE_REPORT: 0.03,
    }
    
    per_query = base_costs.get(config.report_type, 0.10)
    total = per_query * query_count
    
    # Deep research multiplier
    if config.report_type == ReportType.DEEP:
        depth_mult = config.deep_research_depth or 2
        breadth_mult = config.deep_research_breadth or 4
        total *= (depth_mult * breadth_mult) / 8  # Normalize to default
    
    return {
        "estimated_llm_cost": total,
        "estimated_retriever_cost": query_count * 0.01,
        "estimated_total": total + (query_count * 0.01),
    }
```

---

## 12. Source and Citation Extraction

GPT-Researcher provides rich source information. ACM 2.0 extracts and stores this for evaluation and reporting.

### GPT-R Source API

```python
researcher = GPTResearcher(query="...")
await researcher.conduct_research()

# Simple URL list
urls = researcher.get_source_urls()
# ['https://example.com/article1', 'https://example.com/article2', ...]

# Full source objects
sources = researcher.get_research_sources()
# [
#   {'url': '...', 'title': '...', 'content': '...', 'images': [...]},
#   ...
# ]

# Aggregated context (all retrieved content)
context = researcher.get_research_context()
# "Content from source 1...\n\nContent from source 2..."
```

### Source Schema

```python
# acm2/schemas/gptr.py

class GptrSource(BaseModel):
    """A source from GPT-Researcher."""
    
    # Core fields
    url: str
    title: Optional[str] = None
    
    # Content
    snippet: Optional[str] = None  # First ~500 chars
    raw_content: Optional[str] = None  # Full scraped content
    word_count: Optional[int] = None
    
    # Metadata
    domain: Optional[str] = None  # Extracted from URL
    scraped_at: Optional[datetime] = None
    scrape_method: Optional[str] = None  # bs, browser, firecrawl
    
    # Media
    images: List[str] = Field(default_factory=list)
    
    # Quality indicators
    relevance_score: Optional[float] = None  # 0-1 if available


class GptrSourceList(BaseModel):
    """Collection of sources with metadata."""
    sources: List[GptrSource]
    total_count: int
    unique_domains: int
    total_content_length: int
```

### Source Extraction in Adapter

```python
# acm2/adapters/gptr_adapter.py

from urllib.parse import urlparse

class GptrAdapter:
    def _extract_sources(self, raw_sources: list) -> List[GptrSource]:
        """Convert GPT-R source dicts to structured objects."""
        sources = []
        
        for s in raw_sources:
            url = s.get("url", "")
            content = s.get("content", "")
            
            source = GptrSource(
                url=url,
                title=s.get("title"),
                snippet=content[:500] if content else None,
                raw_content=content,
                word_count=len(content.split()) if content else 0,
                domain=urlparse(url).netloc if url else None,
                images=s.get("images", []),
            )
            sources.append(source)
        
        return sources
    
    def _create_source_list(self, sources: List[GptrSource]) -> GptrSourceList:
        """Create source list with aggregate metadata."""
        domains = set(s.domain for s in sources if s.domain)
        total_length = sum(len(s.raw_content or "") for s in sources)
        
        return GptrSourceList(
            sources=sources,
            total_count=len(sources),
            unique_domains=len(domains),
            total_content_length=total_length,
        )
```

### Citation Format

ACM 2.0 can generate formatted citations:

```python
# acm2/utils/citations.py

def format_citation_markdown(source: GptrSource, index: int) -> str:
    """Format source as markdown citation."""
    title = source.title or source.domain or "Source"
    return f"[{index}] [{title}]({source.url})"


def format_citation_list(sources: List[GptrSource]) -> str:
    """Generate markdown reference list."""
    lines = ["## References\n"]
    for i, source in enumerate(sources, 1):
        lines.append(format_citation_markdown(source, i))
    return "\n".join(lines)


def format_citation_bibtex(source: GptrSource, key: str) -> str:
    """Format source as BibTeX entry."""
    return f"""@online{{{key},
  title = {{{source.title or "Untitled"}}},
  url = {{{source.url}}},
  urldate = {{{source.scraped_at.strftime("%Y-%m-%d") if source.scraped_at else ""}}}
}}"""
```

### Source Storage

```sql
-- gptr_sources table
CREATE TABLE gptr_sources (
    id INTEGER PRIMARY KEY,
    artifact_id INTEGER NOT NULL,
    url TEXT NOT NULL,
    title TEXT,
    domain TEXT,
    snippet TEXT,
    raw_content TEXT,
    word_count INTEGER,
    images TEXT,  -- JSON array
    scraped_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (artifact_id) REFERENCES gptr_artifacts(id)
);

-- Index for domain analysis
CREATE INDEX idx_sources_domain ON gptr_sources(domain);
```

### Source Analytics

```sql
-- Most cited domains
SELECT domain, COUNT(*) as citation_count
FROM gptr_sources
GROUP BY domain
ORDER BY citation_count DESC
LIMIT 20;

-- Sources per report
SELECT 
    a.id as artifact_id,
    COUNT(s.id) as source_count,
    COUNT(DISTINCT s.domain) as unique_domains
FROM gptr_artifacts a
JOIN gptr_sources s ON s.artifact_id = a.id
GROUP BY a.id;

-- Average content length by domain
SELECT 
    domain,
    AVG(word_count) as avg_words,
    COUNT(*) as times_cited
FROM gptr_sources
WHERE domain IS NOT NULL
GROUP BY domain
HAVING times_cited > 5;
```

### Source Quality Evaluation

ACM 2.0 can evaluate source quality for reports:

```python
# acm2/evaluation/source_quality.py

class SourceQualityEvaluator:
    # Known high-quality domains
    TRUSTED_DOMAINS = {
        "arxiv.org", "nature.com", "science.org",
        "ieee.org", "acm.org", "nih.gov", "gov",
    }
    
    def score_source(self, source: GptrSource) -> float:
        """Score source quality 0-1."""
        score = 0.5  # Base score
        
        # Boost for trusted domains
        if any(d in (source.domain or "") for d in self.TRUSTED_DOMAINS):
            score += 0.3
        
        # Boost for substantial content
        if (source.word_count or 0) > 500:
            score += 0.1
        
        # Boost for having title
        if source.title:
            score += 0.1
        
        return min(1.0, score)
    
    def score_source_list(self, sources: List[GptrSource]) -> dict:
        """Score overall source quality."""
        if not sources:
            return {"average_score": 0, "trusted_count": 0}
        
        scores = [self.score_source(s) for s in sources]
        trusted = sum(1 for s in sources if self._is_trusted(s))
        
        return {
            "average_score": sum(scores) / len(scores),
            "trusted_count": trusted,
            "trusted_percent": trusted / len(sources) * 100,
            "unique_domains": len(set(s.domain for s in sources if s.domain)),
        }
```

---

## 13. Image Handling

GPT-Researcher scrapes and filters relevant images during research. ACM 2.0 captures and stores these.

### GPT-R Image API

```python
researcher = GPTResearcher(query="Solar panel technology")
await researcher.conduct_research()

# Get image URLs found during research
images = researcher.get_research_images()
# [
#   'https://example.com/solar-diagram.png',
#   'https://example.com/efficiency-chart.jpg',
#   ...
# ]
```

**Image Filtering:** GPT-R automatically filters images by:
- Minimum size (avoids icons/buttons)
- Relevance to query
- Valid image formats (PNG, JPG, GIF, WebP)

### Image Schema

```python
# acm2/schemas/gptr.py

class GptrImage(BaseModel):
    """An image from GPT-Researcher."""
    url: str
    source_url: Optional[str] = None  # Page where image was found
    alt_text: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    format: Optional[str] = None  # png, jpg, etc.
    
    # ACM 2.0 storage
    local_path: Optional[str] = None  # If downloaded locally
    cached: bool = False
```

### Image Extraction in Adapter

```python
# acm2/adapters/gptr_adapter.py

class GptrAdapter:
    def _extract_images(self, image_urls: List[str]) -> List[GptrImage]:
        """Convert GPT-R image URLs to structured objects."""
        images = []
        
        for url in image_urls:
            # Extract format from URL
            format = None
            for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp"]:
                if ext in url.lower():
                    format = ext.replace(".", "")
                    break
            
            images.append(GptrImage(
                url=url,
                format=format,
            ))
        
        return images
```

### Image Storage Options

**Option 1: Store URLs only (default)**

```python
# Store image URLs in artifact metadata
result = GptrRunResult(
    images=[img.url for img in images],
    metadata={"image_count": len(images)},
)
```

**Option 2: Download and cache locally**

```python
# acm2/services/image_cache.py

import httpx
import hashlib
from pathlib import Path

class ImageCache:
    def __init__(self, cache_dir: str = "./image_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
    
    async def cache_image(self, url: str) -> Optional[str]:
        """Download and cache image, return local path."""
        try:
            # Create filename from URL hash
            url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
            ext = self._get_extension(url)
            filename = f"{url_hash}{ext}"
            local_path = self.cache_dir / filename
            
            if local_path.exists():
                return str(local_path)
            
            # Download image
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=30)
                response.raise_for_status()
                
                local_path.write_bytes(response.content)
                return str(local_path)
        
        except Exception as e:
            print(f"Failed to cache image {url}: {e}")
            return None
    
    async def cache_all(self, urls: List[str]) -> List[GptrImage]:
        """Cache all images, return updated objects."""
        images = []
        for url in urls:
            local_path = await self.cache_image(url)
            images.append(GptrImage(
                url=url,
                local_path=local_path,
                cached=local_path is not None,
            ))
        return images
    
    def _get_extension(self, url: str) -> str:
        for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp"]:
            if ext in url.lower():
                return ext
        return ".jpg"  # Default
```

### Image Database Storage

```sql
-- gptr_images table
CREATE TABLE gptr_images (
    id INTEGER PRIMARY KEY,
    artifact_id INTEGER NOT NULL,
    url TEXT NOT NULL,
    source_url TEXT,
    local_path TEXT,
    format TEXT,
    width INTEGER,
    height INTEGER,
    cached BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (artifact_id) REFERENCES gptr_artifacts(id)
);
```

### Image in Report Output

Include images in final reports:

```python
def embed_images_in_report(report: str, images: List[GptrImage]) -> str:
    """Append image references to report."""
    if not images:
        return report
    
    image_section = "\n\n## Images\n\n"
    for i, img in enumerate(images, 1):
        image_section += f"![Image {i}]({img.url})\n\n"
    
    return report + image_section
```

### Configuration

```yaml
# acm2_config.yaml
gptr:
  images:
    enabled: true
    cache_locally: false  # Set true to download
    cache_dir: "./image_cache"
    max_images_per_report: 10
    allowed_formats: ["png", "jpg", "gif", "webp"]
```

---

## 14. Custom Prompts

GPT-Researcher supports custom prompts for report generation. ACM 2.0 leverages this for flexible output formats.

### GPT-R Custom Prompt API

```python
researcher = GPTResearcher(query="Climate change impacts")
await researcher.conduct_research()

# Default report
report = await researcher.write_report()

# Custom format report
custom_report = await researcher.write_report(
    custom_prompt="Write a brief executive summary with 5 bullet points."
)
```

### Prompt Templates

ACM 2.0 provides built-in prompt templates:

```python
# acm2/prompts/gptr_templates.py

GPTR_PROMPT_TEMPLATES = {
    "executive_summary": """
        Write a concise executive summary (300-500 words) covering:
        - Key findings
        - Main conclusions
        - Recommended actions
    """,
    
    "bullet_points": """
        Summarize the research as a bulleted list:
        - Use 10-15 key points
        - Each point should be 1-2 sentences
        - Organize by theme or importance
    """,
    
    "faq": """
        Format the research as a FAQ document:
        - Generate 8-12 relevant questions
        - Provide concise answers (2-3 sentences each)
        - Include citations where appropriate
    """,
    
    "technical_report": """
        Write a technical report with:
        - Abstract
        - Methodology section
        - Detailed findings
        - Technical specifications where relevant
        - References section
    """,
    
    "blog_post": """
        Write an engaging blog post:
        - Catchy introduction
        - Conversational tone
        - Use subheadings for readability
        - Include a conclusion with call-to-action
    """,
    
    "comparison": """
        Create a comparison analysis:
        - Identify 3-5 key aspects to compare
        - Use a structured format (tables if helpful)
        - Provide pros/cons for each option
        - Conclude with recommendations
    """,
    
    "academic": """
        Write in academic style:
        - Formal language
        - Cite sources inline
        - Include literature review
        - Methodology discussion
        - Limitations and future work
    """,
}
```

### Using Templates in Adapter

```python
# acm2/adapters/gptr_adapter.py

class GptrAdapter:
    async def run_research(
        self,
        query: str,
        config: GptrConfig,
    ) -> GptrRunResult:
        researcher = GPTResearcher(
            query=query,
            report_type=config.report_type.value,
        )
        
        await researcher.conduct_research()
        
        # Determine prompt
        custom_prompt = None
        if config.custom_prompt:
            # User-provided prompt
            custom_prompt = config.custom_prompt
        elif config.output_format:
            # Template-based prompt
            custom_prompt = GPTR_PROMPT_TEMPLATES.get(config.output_format)
        
        # Generate report
        if custom_prompt:
            report = await researcher.write_report(custom_prompt=custom_prompt)
        else:
            report = await researcher.write_report()
        
        return GptrRunResult(
            report_content=report,
            metadata={
                "output_format": config.output_format,
                "custom_prompt_used": custom_prompt is not None,
            },
        )
```

### Config Schema Update

```python
# acm2/schemas/gptr.py

class OutputFormat(str, Enum):
    DEFAULT = "default"
    EXECUTIVE_SUMMARY = "executive_summary"
    BULLET_POINTS = "bullet_points"
    FAQ = "faq"
    TECHNICAL_REPORT = "technical_report"
    BLOG_POST = "blog_post"
    COMPARISON = "comparison"
    ACADEMIC = "academic"


class GptrConfig(BaseModel):
    # ... existing fields ...
    
    # Output format
    output_format: Optional[OutputFormat] = Field(
        None, description="Predefined output format template"
    )
    custom_prompt: Optional[str] = Field(
        None, description="Custom prompt (overrides output_format)"
    )
```

### Prompt Variables

Support dynamic prompt variables:

```python
def render_prompt(template: str, variables: dict) -> str:
    """Render prompt template with variables."""
    result = template
    for key, value in variables.items():
        result = result.replace(f"{{{key}}}", str(value))
    return result

# Example usage
template = """
Write a report for {audience} about {topic}.
Target length: {word_count} words.
Focus on: {focus_areas}
"""

prompt = render_prompt(template, {
    "audience": "technical managers",
    "topic": "AI adoption strategies",
    "word_count": 1500,
    "focus_areas": "ROI, implementation challenges, success metrics",
})
```

### Document-Specific Prompts

ACM 2.0 can store per-document prompts:

```sql
-- documents table extension
ALTER TABLE documents ADD COLUMN gptr_custom_prompt TEXT;
ALTER TABLE documents ADD COLUMN gptr_output_format TEXT;
```

```python
# When generating for a document
doc = await db.get_document(doc_id)
config = GptrConfig(
    report_type=ReportType.RESEARCH_REPORT,
    custom_prompt=doc.gptr_custom_prompt,
    output_format=doc.gptr_output_format,
)
result = await adapter.run_research(doc.content, config)
```

### Prompt Library Management

```python
# acm2/services/prompt_library.py

class PromptLibrary:
    """Manage custom prompt templates."""
    
    def __init__(self, db):
        self.db = db
    
    async def save_prompt(self, name: str, template: str, description: str = "") -> int:
        """Save a custom prompt template."""
        return await self.db.execute(
            "INSERT INTO gptr_prompts (name, template, description) VALUES (?, ?, ?)",
            (name, template, description)
        )
    
    async def get_prompt(self, name: str) -> Optional[str]:
        """Get prompt template by name."""
        row = await self.db.fetchone(
            "SELECT template FROM gptr_prompts WHERE name = ?",
            (name,)
        )
        return row["template"] if row else None
    
    async def list_prompts(self) -> List[dict]:
        """List all available prompts."""
        return await self.db.fetchall(
            "SELECT name, description FROM gptr_prompts ORDER BY name"
        )
```

---

## 15. Integration with ACM 2.0 Pipeline

GPT-Researcher integrates with the standard ACM 2.0 pipeline as an alternative generator.

### Pipeline Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        ACM 2.0 Pipeline                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. CREATE RUN                                                  │
│     └── Select generator: "fpf" or "gptr"                      │
│                                                                 │
│  2. ADD DOCUMENTS                                               │
│     └── FPF: file paths, prompts                                │
│     └── GPT-R: queries, topics                                  │
│                                                                 │
│  3. GENERATION PHASE                                            │
│     └── For each document:                                      │
│         └── FPF: render prompt → call LLM → save artifact       │
│         └── GPT-R: research query → write report → save artifact│
│                                                                 │
│  4. EVALUATION PHASE (optional)                                 │
│     └── Score artifacts with configured evaluators              │
│     └── Same evaluators work for FPF and GPT-R output           │
│                                                                 │
│  5. COMBINE PHASE (optional)                                    │
│     └── Merge winning artifacts                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Generator Selection

```python
# acm2/schemas/run.py

class Generator(str, Enum):
    FPF = "fpf"        # FilePromptForge
    GPTR = "gptr"      # GPT-Researcher


class RunConfig(BaseModel):
    generator: Generator = Generator.FPF
    
    # FPF-specific config
    fpf_config: Optional[FpfConfig] = None
    
    # GPT-R-specific config
    gptr_config: Optional[GptrConfig] = None
```

### Run Creation with GPT-R

```python
# API usage
run = await acm2.create_run(
    name="AI Research Project",
    generator="gptr",
    gptr_config=GptrConfig(
        report_type=ReportType.RESEARCH_REPORT,
        tone=Tone.OBJECTIVE,
    ),
)

# Add queries as "documents"
await acm2.add_document(run.id, content="Latest developments in quantum computing")
await acm2.add_document(run.id, content="Comparison of cloud AI platforms")
await acm2.add_document(run.id, content="Best practices for ML model deployment")
```

### Generation Phase

```python
# acm2/services/generator.py

class GeneratorService:
    def __init__(self):
        self.fpf_adapter = FpfAdapter()
        self.gptr_adapter = GptrAdapter()
    
    async def generate_for_document(
        self,
        run: Run,
        document: Document,
    ) -> Artifact:
        """Generate artifact for a document using run's generator."""
        
        if run.generator == Generator.FPF:
            result = await self.fpf_adapter.generate(
                document=document,
                config=run.fpf_config,
            )
            return self._fpf_result_to_artifact(result, run, document)
        
        elif run.generator == Generator.GPTR:
            result = await self.gptr_adapter.run_research(
                query=document.content,  # Document content is the query
                config=run.gptr_config,
            )
            return self._gptr_result_to_artifact(result, run, document)
    
    def _gptr_result_to_artifact(self, result: GptrRunResult, run: Run, doc: Document) -> Artifact:
        """Convert GPT-R result to ACM 2.0 artifact."""
        return Artifact(
            run_id=run.id,
            document_id=doc.id,
            generator="gptr",
            content=result.report_content,
            cost_usd=result.costs,
            duration_seconds=result.duration_seconds,
            metadata={
                "report_type": result.report_type,
                "source_count": len(result.sources),
                "image_count": len(result.images),
                "query": doc.content,
            },
        )
```

### Batch Generation

```python
# acm2/services/runner.py

class RunnerService:
    async def run_generation_phase(
        self,
        run_id: int,
        progress_callback: Optional[callable] = None,
    ) -> List[Artifact]:
        """Run generation for all documents in a run."""
        
        run = await self.db.get_run(run_id)
        documents = await self.db.get_documents(run_id)
        artifacts = []
        
        for i, doc in enumerate(documents):
            if progress_callback:
                await progress_callback({
                    "phase": "generation",
                    "current": i + 1,
                    "total": len(documents),
                    "document_id": doc.id,
                })
            
            try:
                artifact = await self.generator.generate_for_document(run, doc)
                await self.db.save_artifact(artifact)
                artifacts.append(artifact)
            except GptrError as e:
                # Log error but continue with other documents
                await self.db.save_error(run_id, doc.id, str(e))
        
        return artifacts
```

### Evaluation Phase

The same evaluators work for both FPF and GPT-R artifacts:

```python
# acm2/services/evaluator.py

class EvaluatorService:
    async def evaluate_artifact(self, artifact: Artifact) -> EvaluationResult:
        """Evaluate artifact content regardless of generator."""
        
        # All evaluators work on artifact.content (markdown string)
        scores = {}
        
        for evaluator in self.evaluators:
            score = await evaluator.score(artifact.content)
            scores[evaluator.name] = score
        
        return EvaluationResult(
            artifact_id=artifact.id,
            scores=scores,
            aggregate_score=sum(scores.values()) / len(scores),
        )
```

### GPT-R-Specific Evaluators

Add evaluators that leverage GPT-R metadata:

```python
# acm2/evaluation/gptr_evaluators.py

class SourceCountEvaluator:
    """Score based on number of sources."""
    name = "source_count"
    
    def score(self, artifact: Artifact) -> float:
        source_count = artifact.metadata.get("source_count", 0)
        # More sources = better (up to a point)
        return min(1.0, source_count / 10)


class SourceDiversityEvaluator:
    """Score based on diversity of source domains."""
    name = "source_diversity"
    
    async def score(self, artifact: Artifact) -> float:
        sources = await self.db.get_sources_for_artifact(artifact.id)
        domains = set(s.domain for s in sources if s.domain)
        # More unique domains = better
        return min(1.0, len(domains) / 5)
```

### Pipeline Configuration

```yaml
# acm2_config.yaml

pipeline:
  # Generator settings
  generators:
    fpf:
      enabled: true
    gptr:
      enabled: true
      default_report_type: research_report
      default_tone: Objective
  
  # Evaluation settings
  evaluation:
    enabled: true
    evaluators:
      - name: coherence
        weight: 1.0
      - name: source_count
        weight: 0.5
        generator: gptr  # Only for GPT-R artifacts
      - name: source_diversity
        weight: 0.5
        generator: gptr
  
  # Combine settings
  combine:
    enabled: false  # Usually not needed for research
```

### Mixed Generator Runs

Future enhancement: Allow mixing generators in a single run:

```python
# Future: per-document generator override
await acm2.add_document(
    run_id,
    content="Introduction",
    generator="fpf",  # Use FPF for this doc
)
await acm2.add_document(
    run_id,
    content="Market analysis of cloud providers",
    generator="gptr",  # Use GPT-R for research
)
```

---

## 16. Database Schema Updates

GPT-Researcher results require additional database tables beyond the core ACM 2.0 schema.

### GPT-R Artifacts Table

Extends the base artifacts with GPT-R specific fields:

```sql
-- gptr_artifacts table
CREATE TABLE gptr_artifacts (
    id INTEGER PRIMARY KEY,
    artifact_id INTEGER NOT NULL UNIQUE,  -- FK to artifacts table
    
    -- Query and config
    query TEXT NOT NULL,
    report_type TEXT NOT NULL,  -- research_report, detailed_report, deep, etc.
    report_source TEXT NOT NULL,  -- web, local, hybrid, static
    tone TEXT,
    
    -- Results
    report_content TEXT NOT NULL,
    source_count INTEGER DEFAULT 0,
    image_count INTEGER DEFAULT 0,
    
    -- Costs and timing
    llm_cost REAL DEFAULT 0.0,
    retriever_cost REAL DEFAULT 0.0,
    total_cost REAL DEFAULT 0.0,
    duration_seconds REAL,
    
    -- Config used
    config_json TEXT,  -- Full GptrConfig as JSON
    
    -- Timestamps
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (artifact_id) REFERENCES artifacts(id) ON DELETE CASCADE
);

CREATE INDEX idx_gptr_artifacts_report_type ON gptr_artifacts(report_type);
CREATE INDEX idx_gptr_artifacts_created ON gptr_artifacts(created_at);
```

### GPT-R Sources Table

Stores sources referenced in reports:

```sql
-- gptr_sources table
CREATE TABLE gptr_sources (
    id INTEGER PRIMARY KEY,
    gptr_artifact_id INTEGER NOT NULL,
    
    -- Source info
    url TEXT NOT NULL,
    title TEXT,
    domain TEXT,
    
    -- Content
    snippet TEXT,  -- First ~500 chars
    raw_content TEXT,  -- Full content if stored
    word_count INTEGER,
    
    -- Metadata
    scraped_at TIMESTAMP,
    scrape_method TEXT,  -- bs, browser, firecrawl
    relevance_score REAL,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (gptr_artifact_id) REFERENCES gptr_artifacts(id) ON DELETE CASCADE
);

CREATE INDEX idx_gptr_sources_domain ON gptr_sources(domain);
CREATE INDEX idx_gptr_sources_artifact ON gptr_sources(gptr_artifact_id);
```

### GPT-R Images Table

Stores images found during research:

```sql
-- gptr_images table
CREATE TABLE gptr_images (
    id INTEGER PRIMARY KEY,
    gptr_artifact_id INTEGER NOT NULL,
    
    -- Image info
    url TEXT NOT NULL,
    source_page_url TEXT,
    alt_text TEXT,
    
    -- Dimensions
    width INTEGER,
    height INTEGER,
    format TEXT,  -- png, jpg, gif, webp
    
    -- Local cache
    local_path TEXT,
    cached BOOLEAN DEFAULT FALSE,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (gptr_artifact_id) REFERENCES gptr_artifacts(id) ON DELETE CASCADE
);

CREATE INDEX idx_gptr_images_artifact ON gptr_images(gptr_artifact_id);
```

### GPT-R Prompts Table

Stores custom prompt templates:

```sql
-- gptr_prompts table
CREATE TABLE gptr_prompts (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    template TEXT NOT NULL,
    description TEXT,
    
    -- Metadata
    is_builtin BOOLEAN DEFAULT FALSE,
    usage_count INTEGER DEFAULT 0,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_gptr_prompts_name ON gptr_prompts(name);
```

### GPT-R Progress Table

Tracks progress for long-running research (optional):

```sql
-- gptr_progress table (for deep research tracking)
CREATE TABLE gptr_progress (
    id INTEGER PRIMARY KEY,
    gptr_artifact_id INTEGER NOT NULL,
    
    -- Progress data
    status TEXT NOT NULL,  -- researching, writing, complete, error
    percent_complete REAL DEFAULT 0.0,
    
    -- Deep research progress
    current_depth INTEGER,
    total_depth INTEGER,
    current_query TEXT,
    completed_queries INTEGER,
    total_queries INTEGER,
    
    -- Costs so far
    current_cost REAL DEFAULT 0.0,
    sources_found INTEGER DEFAULT 0,
    
    -- Message
    message TEXT,
    
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (gptr_artifact_id) REFERENCES gptr_artifacts(id) ON DELETE CASCADE
);
```

### Migration Script

```python
# acm2/migrations/003_gptr_tables.py

def upgrade(db):
    """Create GPT-R tables."""
    
    db.execute('''
        CREATE TABLE IF NOT EXISTS gptr_artifacts (
            id INTEGER PRIMARY KEY,
            artifact_id INTEGER NOT NULL UNIQUE,
            query TEXT NOT NULL,
            report_type TEXT NOT NULL,
            report_source TEXT NOT NULL,
            tone TEXT,
            report_content TEXT NOT NULL,
            source_count INTEGER DEFAULT 0,
            image_count INTEGER DEFAULT 0,
            llm_cost REAL DEFAULT 0.0,
            retriever_cost REAL DEFAULT 0.0,
            total_cost REAL DEFAULT 0.0,
            duration_seconds REAL,
            config_json TEXT,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (artifact_id) REFERENCES artifacts(id) ON DELETE CASCADE
        )
    ''')
    
    db.execute('''
        CREATE TABLE IF NOT EXISTS gptr_sources (
            id INTEGER PRIMARY KEY,
            gptr_artifact_id INTEGER NOT NULL,
            url TEXT NOT NULL,
            title TEXT,
            domain TEXT,
            snippet TEXT,
            raw_content TEXT,
            word_count INTEGER,
            scraped_at TIMESTAMP,
            scrape_method TEXT,
            relevance_score REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (gptr_artifact_id) REFERENCES gptr_artifacts(id) ON DELETE CASCADE
        )
    ''')
    
    db.execute('''
        CREATE TABLE IF NOT EXISTS gptr_images (
            id INTEGER PRIMARY KEY,
            gptr_artifact_id INTEGER NOT NULL,
            url TEXT NOT NULL,
            source_page_url TEXT,
            alt_text TEXT,
            width INTEGER,
            height INTEGER,
            format TEXT,
            local_path TEXT,
            cached BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (gptr_artifact_id) REFERENCES gptr_artifacts(id) ON DELETE CASCADE
        )
    ''')
    
    db.execute('''
        CREATE TABLE IF NOT EXISTS gptr_prompts (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            template TEXT NOT NULL,
            description TEXT,
            is_builtin BOOLEAN DEFAULT FALSE,
            usage_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create indexes
    db.execute('CREATE INDEX IF NOT EXISTS idx_gptr_artifacts_report_type ON gptr_artifacts(report_type)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_gptr_sources_domain ON gptr_sources(domain)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_gptr_sources_artifact ON gptr_sources(gptr_artifact_id)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_gptr_images_artifact ON gptr_images(gptr_artifact_id)')
    
    # Seed builtin prompts
    from acm2.prompts.gptr_templates import GPTR_PROMPT_TEMPLATES
    for name, template in GPTR_PROMPT_TEMPLATES.items():
        db.execute(
            'INSERT OR IGNORE INTO gptr_prompts (name, template, is_builtin) VALUES (?, ?, TRUE)',
            (name, template)
        )


def downgrade(db):
    """Drop GPT-R tables."""
    db.execute('DROP TABLE IF EXISTS gptr_progress')
    db.execute('DROP TABLE IF EXISTS gptr_images')
    db.execute('DROP TABLE IF EXISTS gptr_sources')
    db.execute('DROP TABLE IF EXISTS gptr_prompts')
    db.execute('DROP TABLE IF EXISTS gptr_artifacts')
```

### Repository Methods

```python
# acm2/db/gptr_repository.py

class GptrRepository:
    def __init__(self, db):
        self.db = db
    
    async def save_gptr_artifact(self, artifact_id: int, result: GptrRunResult, config: GptrConfig) -> int:
        """Save GPT-R result to database."""
        gptr_id = await self.db.execute(
            '''INSERT INTO gptr_artifacts 
               (artifact_id, query, report_type, report_source, tone, report_content,
                source_count, image_count, llm_cost, retriever_cost, total_cost,
                duration_seconds, config_json, started_at, completed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (artifact_id, result.metadata.get("query"), result.report_type,
             config.report_source.value, config.tone.value, result.report_content,
             len(result.sources), len(result.images), result.costs,
             result.metadata.get("retriever_cost", 0), result.costs,
             result.duration_seconds, config.json(), result.started_at, result.completed_at)
        )
        
        # Save sources
        for source in result.sources:
            await self.db.execute(
                '''INSERT INTO gptr_sources 
                   (gptr_artifact_id, url, title, domain, snippet, word_count)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (gptr_id, source.url, source.title, source.domain, source.snippet, source.word_count)
            )
        
        # Save images
        for img_url in result.images:
            await self.db.execute(
                'INSERT INTO gptr_images (gptr_artifact_id, url) VALUES (?, ?)',
                (gptr_id, img_url)
            )
        
        return gptr_id
    
    async def get_gptr_artifact(self, artifact_id: int) -> Optional[dict]:
        """Get GPT-R artifact by artifact ID."""
        return await self.db.fetchone(
            'SELECT * FROM gptr_artifacts WHERE artifact_id = ?',
            (artifact_id,)
        )
    
    async def get_sources(self, gptr_artifact_id: int) -> List[dict]:
        """Get sources for a GPT-R artifact."""
        return await self.db.fetchall(
            'SELECT * FROM gptr_sources WHERE gptr_artifact_id = ? ORDER BY id',
            (gptr_artifact_id,)
        )
    
    async def get_images(self, gptr_artifact_id: int) -> List[dict]:
        """Get images for a GPT-R artifact."""
        return await self.db.fetchall(
            'SELECT * FROM gptr_images WHERE gptr_artifact_id = ? ORDER BY id',
            (gptr_artifact_id,)
        )
```

---

## 17. API Endpoints

REST and WebSocket endpoints for GPT-Researcher operations.

### Generate Research Report

```
POST /api/v1/runs/{run_id}/documents/{doc_id}/generate/gptr
```

Trigger GPT-R generation for a specific document.

**Request:**
```json
{
  "report_type": "research_report",
  "report_source": "web",
  "tone": "Objective",
  "source_urls": null,
  "output_format": "executive_summary",
  "budget_limit": 0.50,
  "timeout_seconds": 600
}
```

**Response:**
```json
{
  "artifact_id": 123,
  "status": "completed",
  "report_content": "# Research Report\n\n...",
  "report_type": "research_report",
  "source_count": 12,
  "image_count": 3,
  "costs": 0.12,
  "duration_seconds": 185.4,
  "sources": [
    {"url": "https://...", "title": "...", "domain": "example.com"}
  ]
}
```

**Error Response:**
```json
{
  "success": false,
  "error_type": "rate_limited",
  "error_message": "OpenAI rate limit exceeded",
  "retry_after_seconds": 60
}
```

### Get GPT-R Result

```
GET /api/v1/runs/{run_id}/documents/{doc_id}/gptr-result
```

Retrieve stored GPT-R result for a document.

**Response:**
```json
{
  "artifact_id": 123,
  "query": "Latest developments in quantum computing",
  "report_type": "research_report",
  "report_content": "# Research Report\n\n...",
  "sources": [...],
  "images": [...],
  "costs": 0.12,
  "duration_seconds": 185.4,
  "created_at": "2024-01-15T10:30:00Z"
}
```

### Get Sources

```
GET /api/v1/artifacts/{artifact_id}/gptr-sources
```

Get all sources for a GPT-R artifact.

**Response:**
```json
{
  "sources": [
    {
      "id": 1,
      "url": "https://example.com/article",
      "title": "Article Title",
      "domain": "example.com",
      "snippet": "First 500 characters...",
      "word_count": 1250
    }
  ],
  "total_count": 12,
  "unique_domains": 8
}
```

### Get Images

```
GET /api/v1/artifacts/{artifact_id}/gptr-images
```

Get all images for a GPT-R artifact.

**Response:**
```json
{
  "images": [
    {
      "id": 1,
      "url": "https://example.com/image.png",
      "format": "png",
      "cached": false,
      "local_path": null
    }
  ],
  "total_count": 3
}
```

### Standalone Research (No Run)

```
POST /api/v1/gptr/research
```

Run research without creating a run (quick one-off queries).

**Request:**
```json
{
  "query": "Best practices for Kubernetes security",
  "report_type": "research_report",
  "tone": "Objective"
}
```

**Response:** Same as generate endpoint.

### Estimate Cost

```
POST /api/v1/gptr/estimate
```

Estimate cost before running research.

**Request:**
```json
{
  "report_type": "deep",
  "deep_research_breadth": 4,
  "deep_research_depth": 2,
  "query_count": 3
}
```

**Response:**
```json
{
  "estimated_llm_cost": 1.20,
  "estimated_retriever_cost": 0.03,
  "estimated_total": 1.23,
  "estimated_duration_minutes": 15
}
```

### List Prompt Templates

```
GET /api/v1/gptr/prompts
```

List available prompt templates.

**Response:**
```json
{
  "prompts": [
    {"name": "executive_summary", "description": "Concise executive summary", "is_builtin": true},
    {"name": "faq", "description": "FAQ format", "is_builtin": true},
    {"name": "my_custom", "description": "My custom format", "is_builtin": false}
  ]
}
```

### Create Custom Prompt

```
POST /api/v1/gptr/prompts
```

**Request:**
```json
{
  "name": "my_custom_format",
  "template": "Write a report focusing on {{focus_area}}...",
  "description": "Custom format for specific use case"
}
```

### WebSocket Progress Streaming

```
WebSocket /ws/gptr/progress/{run_id}
```

Stream real-time progress for GPT-R research.

**Connection:**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/gptr/progress/123');

ws.onmessage = (event) => {
  const progress = JSON.parse(event.data);
  console.log(progress);
};
```

**Progress Messages:**
```json
{"type": "started", "document_id": 1, "query": "..."}
```
```json
{
  "type": "progress",
  "document_id": 1,
  "status": "researching",
  "percent_complete": 0.45,
  "current_depth": 1,
  "total_depth": 2,
  "current_query": "Sub-topic being researched",
  "completed_queries": 3,
  "total_queries": 8,
  "sources_found": 15,
  "current_cost": 0.08
}
```
```json
{"type": "writing", "document_id": 1, "percent_complete": 0.9}
```
```json
{"type": "completed", "document_id": 1, "artifact_id": 123, "costs": 0.12}
```
```json
{"type": "error", "document_id": 1, "error_type": "timeout", "message": "..."}
```

### FastAPI Implementation

```python
# acm2/api/gptr_routes.py

from fastapi import APIRouter, WebSocket, HTTPException
from acm2.adapters.gptr_adapter import GptrAdapter
from acm2.schemas.gptr import GptrConfig, GptrRunResult

router = APIRouter(prefix="/api/v1", tags=["gptr"])


@router.post("/runs/{run_id}/documents/{doc_id}/generate/gptr")
async def generate_gptr(
    run_id: int,
    doc_id: int,
    config: GptrConfig,
) -> GptrRunResult:
    """Generate GPT-R report for a document."""
    adapter = GptrAdapter()
    
    # Get document query
    doc = await db.get_document(doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    
    # Run research
    try:
        result = await adapter.run_research(doc.content, config)
        
        # Save to database
        artifact_id = await db.save_artifact(run_id, doc_id, result)
        await gptr_repo.save_gptr_artifact(artifact_id, result, config)
        
        return result
    except GptrError as e:
        raise HTTPException(400, detail={
            "error_type": e.error_type.value,
            "error_message": e.message,
        })


@router.get("/runs/{run_id}/documents/{doc_id}/gptr-result")
async def get_gptr_result(run_id: int, doc_id: int):
    """Get stored GPT-R result."""
    artifact = await db.get_artifact(run_id, doc_id, generator="gptr")
    if not artifact:
        raise HTTPException(404, "GPT-R result not found")
    
    gptr_data = await gptr_repo.get_gptr_artifact(artifact.id)
    sources = await gptr_repo.get_sources(gptr_data["id"])
    images = await gptr_repo.get_images(gptr_data["id"])
    
    return {
        **gptr_data,
        "sources": sources,
        "images": images,
    }


@router.post("/gptr/research")
async def standalone_research(query: str, config: GptrConfig) -> GptrRunResult:
    """Run standalone research without a run."""
    adapter = GptrAdapter()
    return await adapter.run_research(query, config)


@router.websocket("/ws/gptr/progress/{run_id}")
async def gptr_progress_websocket(websocket: WebSocket, run_id: int):
    """WebSocket for streaming GPT-R progress."""
    await websocket.accept()
    
    async def send_progress(progress):
        await websocket.send_json(progress.dict())
    
    # Subscribe to progress updates for this run
    await progress_manager.subscribe(run_id, send_progress)
    
    try:
        while True:
            # Keep connection alive, handle client messages
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except Exception:
        pass
    finally:
        await progress_manager.unsubscribe(run_id, send_progress)
```

---

## 18. CLI Commands

CLI commands for GPT-Researcher operations.

### Quick Research

Run a quick research query:

```bash
# Basic research
acm2 gptr research "Latest developments in quantum computing"

# With options
acm2 gptr research "AI in healthcare" \
  --report-type detailed_report \
  --tone Formal \
  --output report.md

# Deep research
acm2 gptr research "Future of renewable energy" \
  --report-type deep \
  --depth 2 \
  --breadth 4

# Local document research
acm2 gptr research "Summarize our Q4 reports" \
  --source local \
  --doc-path ./quarterly_reports/

# Restricted to specific URLs
acm2 gptr research "Compare these products" \
  --source static \
  --urls "https://example.com/product1,https://example.com/product2"
```

### Generate for Run/Document

Generate GPT-R report for an existing document in a run:

```bash
# Generate for specific document
acm2 gptr generate --run-id 5 --doc-id 12

# With config overrides
acm2 gptr generate --run-id 5 --doc-id 12 \
  --report-type detailed_report \
  --tone Analytical

# Generate for all documents in a run
acm2 gptr generate --run-id 5 --all
```

### Output Formats

```bash
# Output to file
acm2 gptr research "Topic" --output report.md

# Output to stdout (default)
acm2 gptr research "Topic"

# JSON output (includes metadata, sources, costs)
acm2 gptr research "Topic" --format json

# Include sources in output
acm2 gptr research "Topic" --include-sources

# Custom prompt template
acm2 gptr research "Topic" --template executive_summary
acm2 gptr research "Topic" --custom-prompt "Write a 500-word blog post..."
```

### Cost and Progress

```bash
# Estimate cost before running
acm2 gptr estimate "Topic" --report-type deep --depth 3

# Show progress during research
acm2 gptr research "Topic" --progress

# Set budget limit
acm2 gptr research "Topic" --budget 0.50

# Set timeout
acm2 gptr research "Topic" --timeout 300
```

### Prompt Management

```bash
# List available prompts
acm2 gptr prompts list

# Show prompt template
acm2 gptr prompts show executive_summary

# Create custom prompt
acm2 gptr prompts create my_format --template "Write a report focusing on..."

# Delete custom prompt
acm2 gptr prompts delete my_format
```

### View Results

```bash
# View stored result
acm2 gptr result --artifact-id 123

# View sources for a result
acm2 gptr sources --artifact-id 123

# View images for a result
acm2 gptr images --artifact-id 123

# Export result with all data
acm2 gptr export --artifact-id 123 --output result.json
```

### CLI Implementation

```python
# acm2/cli/gptr_commands.py

import click
import asyncio
from acm2.adapters.gptr_adapter import GptrAdapter
from acm2.schemas.gptr import GptrConfig, ReportType, ReportSource, Tone


@click.group()
def gptr():
    """GPT-Researcher commands."""
    pass


@gptr.command()
@click.argument("query")
@click.option("--report-type", "-t", default="research_report",
              type=click.Choice(["research_report", "detailed_report", "deep", 
                                "resource_report", "outline_report"]))
@click.option("--tone", default="Objective",
              type=click.Choice(["Objective", "Formal", "Analytical", "Informative"]))
@click.option("--source", default="web",
              type=click.Choice(["web", "local", "hybrid", "static"]))
@click.option("--doc-path", help="Path to local documents")
@click.option("--urls", help="Comma-separated URLs for static source")
@click.option("--depth", default=2, help="Deep research depth")
@click.option("--breadth", default=4, help="Deep research breadth")
@click.option("--output", "-o", help="Output file path")
@click.option("--format", "output_format", default="markdown",
              type=click.Choice(["markdown", "json"]))
@click.option("--template", help="Prompt template name")
@click.option("--custom-prompt", help="Custom prompt text")
@click.option("--budget", type=float, help="Budget limit in USD")
@click.option("--timeout", type=int, default=600, help="Timeout in seconds")
@click.option("--progress", is_flag=True, help="Show progress")
@click.option("--include-sources", is_flag=True, help="Include sources in output")
def research(query, report_type, tone, source, doc_path, urls, depth, breadth,
             output, output_format, template, custom_prompt, budget, timeout,
             progress, include_sources):
    """Run GPT-Researcher on a query."""
    
    # Build config
    config = GptrConfig(
        report_type=ReportType(report_type),
        report_source=ReportSource(source),
        tone=Tone(tone),
        doc_path=doc_path,
        source_urls=urls.split(",") if urls else None,
        deep_research_depth=depth,
        deep_research_breadth=breadth,
        budget_limit=budget,
        timeout_seconds=timeout,
        output_format=template,
        custom_prompt=custom_prompt,
    )
    
    # Progress callback
    def show_progress(p):
        if progress:
            click.echo(f"\r{p.status}: {p.percent_complete*100:.0f}% - {p.message}", nl=False)
    
    # Run research
    adapter = GptrAdapter({})
    result = asyncio.run(adapter.run_research(
        query, config,
        progress_callback=show_progress if progress else None
    ))
    
    if progress:
        click.echo()  # New line after progress
    
    # Format output
    if output_format == "json":
        import json
        content = json.dumps(result.dict(), indent=2, default=str)
    else:
        content = result.report_content
        if include_sources:
            content += "\n\n## Sources\n\n"
            for i, s in enumerate(result.sources, 1):
                content += f"{i}. [{s.title or s.domain}]({s.url})\n"
    
    # Output
    if output:
        with open(output, "w", encoding="utf-8") as f:
            f.write(content)
        click.echo(f"Report saved to {output}")
        click.echo(f"Cost: ${result.costs:.4f} | Duration: {result.duration_seconds:.1f}s")
    else:
        click.echo(content)


@gptr.command()
@click.option("--run-id", required=True, type=int)
@click.option("--doc-id", type=int, help="Specific document ID")
@click.option("--all", "all_docs", is_flag=True, help="Generate for all documents")
@click.option("--report-type", "-t", default=None)
@click.option("--tone", default=None)
def generate(run_id, doc_id, all_docs, report_type, tone):
    """Generate GPT-R report for run documents."""
    
    async def _generate():
        from acm2.services.runner import RunnerService
        runner = RunnerService()
        
        if all_docs:
            results = await runner.run_gptr_generation(run_id)
            click.echo(f"Generated {len(results)} reports")
        elif doc_id:
            result = await runner.run_gptr_for_document(run_id, doc_id)
            click.echo(f"Generated report: {len(result.report_content)} chars")
            click.echo(f"Cost: ${result.costs:.4f}")
        else:
            click.echo("Specify --doc-id or --all")
    
    asyncio.run(_generate())


@gptr.command()
@click.argument("query")
@click.option("--report-type", "-t", default="research_report")
@click.option("--depth", default=2)
@click.option("--breadth", default=4)
def estimate(query, report_type, depth, breadth):
    """Estimate cost for a research query."""
    from acm2.adapters.gptr_adapter import estimate_cost
    
    config = GptrConfig(
        report_type=ReportType(report_type),
        deep_research_depth=depth,
        deep_research_breadth=breadth,
    )
    
    est = estimate_cost(config, query_count=1)
    
    click.echo(f"Estimated LLM cost:       ${est['estimated_llm_cost']:.2f}")
    click.echo(f"Estimated retriever cost: ${est['estimated_retriever_cost']:.2f}")
    click.echo(f"Estimated total:          ${est['estimated_total']:.2f}")


@gptr.group()
def prompts():
    """Manage prompt templates."""
    pass


@prompts.command("list")
def list_prompts():
    """List available prompt templates."""
    from acm2.prompts.gptr_templates import GPTR_PROMPT_TEMPLATES
    
    click.echo("Built-in templates:")
    for name in GPTR_PROMPT_TEMPLATES:
        click.echo(f"  - {name}")


@prompts.command("show")
@click.argument("name")
def show_prompt(name):
    """Show a prompt template."""
    from acm2.prompts.gptr_templates import GPTR_PROMPT_TEMPLATES
    
    if name in GPTR_PROMPT_TEMPLATES:
        click.echo(GPTR_PROMPT_TEMPLATES[name])
    else:
        click.echo(f"Template '{name}' not found")


# Register with main CLI
def register(cli):
    cli.add_command(gptr)
```

### Example Usage Session

```bash
# Quick research with output
$ acm2 gptr research "Best practices for API security" --output api_security.md
Report saved to api_security.md
Cost: $0.1234 | Duration: 145.2s

# Deep research with progress
$ acm2 gptr research "Future of AI" --report-type deep --progress
researching: 25% - Researching: AI in healthcare
researching: 50% - Researching: AI in transportation
researching: 75% - Researching: AI ethics concerns
writing: 90% - Generating report...

# Future of AI
...

# Estimate before expensive deep research
$ acm2 gptr estimate "Complex topic" --report-type deep --depth 3 --breadth 5
Estimated LLM cost:       $0.80
Estimated retriever cost: $0.05
Estimated total:          $0.85
```

---

## 19. Comparison with FPF Adapter

GPT-Researcher and FilePromptForge serve different purposes in ACM 2.0.

### Feature Comparison

| Aspect | FPF Adapter | GPT-R Adapter |
|--------|-------------|---------------|
| **Input** | File paths, prompt templates | Research queries, topics |
| **Output** | Generated documents | Research reports |
| **Sources** | User-provided context files | Web search, local docs |
| **Cost** | LLM tokens only | LLM + search API |
| **Speed** | Fast (~10-30s) | Slower (~2-5 min) |
| **Determinism** | More reproducible | Variable (web changes) |
| **Offline** | Yes (with local LLM) | Partial (local mode only) |
| **Use Case** | Document generation | Research, fact-finding |

### When to Use FPF

- **Template-based generation**: Creating documents from templates with variable substitution
- **Controlled output**: When you need consistent, reproducible results
- **Fast turnaround**: Quick generation from known context
- **Batch processing**: High-volume document creation
- **Offline scenarios**: Air-gapped environments

**Examples:**
- Generate API documentation from code comments
- Create reports from structured data
- Produce marketing copy from product specs
- Batch generate email templates

### When to Use GPT-R

- **Research tasks**: Finding current information on topics
- **Fact-finding**: Gathering data from multiple sources
- **Competitive analysis**: Researching market/competitors
- **Literature review**: Summarizing multiple sources
- **Unknown domains**: Topics where you lack source material

**Examples:**
- Research latest AI developments
- Analyze competitor offerings
- Summarize academic papers on a topic
- Create market research reports

### Cost Comparison

| Report Type | FPF Cost | GPT-R Cost | Notes |
|-------------|----------|------------|-------|
| Short doc (~500 words) | ~$0.01 | ~$0.10 | GPT-R includes search |
| Medium doc (~2000 words) | ~$0.03 | ~$0.15 | FPF 5x cheaper |
| Long doc (~5000 words) | ~$0.08 | ~$0.25 | GPT-R detailed_report |
| Deep research | N/A | ~$0.40 | GPT-R exclusive |

### Hybrid Approach

Combine both adapters for comprehensive workflows:

```python
# Example: Research + Generate

# 1. Use GPT-R for research
gptr_result = await gptr_adapter.run_research(
    "Current trends in cloud computing",
    GptrConfig(report_type=ReportType.RESEARCH_REPORT)
)

# 2. Use research as context for FPF generation
fpf_result = await fpf_adapter.generate(
    template="executive_brief.md",
    context={
        "research_summary": gptr_result.report_content,
        "sources": gptr_result.source_urls,
        "company_context": company_data,
    }
)
```

### Pipeline Integration

```yaml
# Example: Mixed pipeline config
pipeline:
  stages:
    - name: research
      generator: gptr
      config:
        report_type: research_report
    
    - name: generate
      generator: fpf
      config:
        template: report_template.md
        context_from: research  # Use previous stage output
```

---

## 20. Testing Strategy

Comprehensive testing approach for the GPT-R adapter.

### Unit Tests (Mocked)

Test adapter logic without API calls:

```python
# tests/test_gptr_adapter.py

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from acm2.adapters.gptr_adapter import GptrAdapter
from acm2.schemas.gptr import GptrConfig, ReportType


@pytest.fixture
def mock_researcher():
    """Mock GPTResearcher class."""
    with patch('acm2.adapters.gptr_adapter.GPTResearcher') as mock:
        instance = MagicMock()
        instance.conduct_research = AsyncMock()
        instance.write_report = AsyncMock(return_value="# Test Report\n\nContent here.")
        instance.get_costs.return_value = 0.15
        instance.get_source_urls.return_value = ["https://example.com/1", "https://example.com/2"]
        instance.get_research_sources.return_value = [
            {"url": "https://example.com/1", "title": "Source 1", "content": "Content 1"},
            {"url": "https://example.com/2", "title": "Source 2", "content": "Content 2"},
        ]
        instance.get_research_images.return_value = ["https://example.com/img.png"]
        mock.return_value = instance
        yield mock


@pytest.mark.asyncio
async def test_run_research_basic(mock_researcher):
    """Test basic research execution."""
    adapter = GptrAdapter({})
    config = GptrConfig(report_type=ReportType.RESEARCH_REPORT)
    
    result = await adapter.run_research("Test query", config)
    
    assert result.report_content == "# Test Report\n\nContent here."
    assert result.costs == 0.15
    assert len(result.sources) == 2
    assert len(result.images) == 1
    mock_researcher.assert_called_once()


@pytest.mark.asyncio
async def test_run_research_deep(mock_researcher):
    """Test deep research with breadth/depth."""
    adapter = GptrAdapter({})
    config = GptrConfig(
        report_type=ReportType.DEEP,
        deep_research_breadth=3,
        deep_research_depth=2,
    )
    
    result = await adapter.run_research("Deep query", config)
    
    assert result.report_type == "deep"


@pytest.mark.asyncio
async def test_source_extraction():
    """Test source extraction from raw GPT-R data."""
    adapter = GptrAdapter({})
    raw_sources = [
        {"url": "https://example.com/article", "title": "Test", "content": "A" * 1000},
    ]
    
    sources = adapter._extract_sources(raw_sources)
    
    assert len(sources) == 1
    assert sources[0].url == "https://example.com/article"
    assert sources[0].domain == "example.com"
    assert len(sources[0].snippet) == 500  # Truncated


@pytest.mark.asyncio
async def test_error_handling_missing_api_key(mock_researcher):
    """Test error when API key missing."""
    adapter = GptrAdapter({})
    config = GptrConfig()
    
    with patch.dict('os.environ', {}, clear=True):
        with pytest.raises(GptrError) as exc:
            await adapter.run_research("Query", config)
        
        assert exc.value.error_type == GptrErrorType.API_KEY_MISSING


@pytest.mark.asyncio
async def test_timeout_handling(mock_researcher):
    """Test timeout error handling."""
    adapter = GptrAdapter({})
    config = GptrConfig(timeout_seconds=1)
    
    # Make research take too long
    async def slow_research():
        import asyncio
        await asyncio.sleep(10)
    
    mock_researcher.return_value.conduct_research = slow_research
    
    with pytest.raises(GptrError) as exc:
        await adapter.run_research_with_timeout("Query", config)
    
    assert exc.value.error_type == GptrErrorType.TIMEOUT
```

### Integration Tests (Real API)

Test with actual GPT-Researcher (requires API keys):

```python
# tests/integration/test_gptr_integration.py

import pytest
import os

# Skip if no API keys
pytestmark = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY") or not os.environ.get("TAVILY_API_KEY"),
    reason="API keys not set"
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_research_report():
    """Test real research_report generation."""
    adapter = GptrAdapter({})
    config = GptrConfig(
        report_type=ReportType.RESEARCH_REPORT,
        tone=Tone.OBJECTIVE,
    )
    
    result = await adapter.run_research(
        "What is Python programming language?",
        config
    )
    
    assert result.success
    assert len(result.report_content) > 500
    assert result.costs > 0
    assert len(result.sources) > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_local_research():
    """Test local document research."""
    adapter = GptrAdapter({})
    config = GptrConfig(
        report_type=ReportType.RESEARCH_REPORT,
        report_source=ReportSource.LOCAL,
        doc_path="./test_docs/",
    )
    
    result = await adapter.run_research(
        "Summarize the documents",
        config
    )
    
    assert result.success


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_real_deep_research():
    """Test deep research (slow, expensive)."""
    adapter = GptrAdapter({})
    config = GptrConfig(
        report_type=ReportType.DEEP,
        deep_research_breadth=2,
        deep_research_depth=1,
        budget_limit=0.50,
    )
    
    result = await adapter.run_research(
        "Explain machine learning basics",
        config
    )
    
    assert result.success
    assert result.costs <= 0.50
```

### Schema Tests

```python
# tests/test_gptr_schemas.py

from acm2.schemas.gptr import GptrConfig, GptrRunResult, ReportType, Tone


def test_config_defaults():
    """Test GptrConfig default values."""
    config = GptrConfig()
    
    assert config.report_type == ReportType.RESEARCH_REPORT
    assert config.tone == Tone.OBJECTIVE
    assert config.deep_research_breadth == 4
    assert config.deep_research_depth == 2


def test_config_serialization():
    """Test config JSON serialization."""
    config = GptrConfig(
        report_type=ReportType.DEEP,
        source_urls=["https://example.com"],
    )
    
    json_str = config.json()
    restored = GptrConfig.parse_raw(json_str)
    
    assert restored.report_type == ReportType.DEEP
    assert restored.source_urls == ["https://example.com"]


def test_result_with_partial_data():
    """Test GptrRunResult with partial data."""
    result = GptrRunResult(
        report_content="Test",
        report_type="research_report",
        duration_seconds=10.5,
    )
    
    assert result.sources == []
    assert result.costs == 0.0
    assert result.success == True
```

### Database Tests

```python
# tests/test_gptr_repository.py

import pytest
from acm2.db.gptr_repository import GptrRepository


@pytest.fixture
async def db():
    """Create test database."""
    from acm2.db import create_test_db
    return await create_test_db()


@pytest.mark.asyncio
async def test_save_and_retrieve_gptr_artifact(db):
    """Test saving and retrieving GPT-R artifacts."""
    repo = GptrRepository(db)
    
    result = GptrRunResult(
        report_content="# Test Report",
        report_type="research_report",
        sources=[GptrSource(url="https://example.com", title="Test")],
        costs=0.15,
        duration_seconds=120.5,
    )
    config = GptrConfig(report_type=ReportType.RESEARCH_REPORT)
    
    gptr_id = await repo.save_gptr_artifact(artifact_id=1, result=result, config=config)
    
    retrieved = await repo.get_gptr_artifact(artifact_id=1)
    assert retrieved["report_content"] == "# Test Report"
    assert retrieved["total_cost"] == 0.15
    
    sources = await repo.get_sources(gptr_id)
    assert len(sources) == 1
    assert sources[0]["url"] == "https://example.com"
```

### API Tests

```python
# tests/test_gptr_api.py

import pytest
from fastapi.testclient import TestClient
from acm2.api import app

client = TestClient(app)


def test_estimate_endpoint():
    """Test cost estimation endpoint."""
    response = client.post("/api/v1/gptr/estimate", json={
        "report_type": "deep",
        "deep_research_breadth": 4,
        "deep_research_depth": 2,
        "query_count": 1
    })
    
    assert response.status_code == 200
    data = response.json()
    assert "estimated_total" in data
    assert data["estimated_total"] > 0


def test_prompts_list_endpoint():
    """Test prompts listing endpoint."""
    response = client.get("/api/v1/gptr/prompts")
    
    assert response.status_code == 200
    data = response.json()
    assert "prompts" in data
    assert len(data["prompts"]) > 0
```

### Test Coverage Goals

| Component | Target Coverage |
|-----------|----------------|
| GptrAdapter | 90% |
| GptrConfig/Schemas | 95% |
| GptrRepository | 85% |
| API Endpoints | 80% |
| CLI Commands | 70% |
| Error Handling | 90% |

### CI/CD Integration

```yaml
# .github/workflows/test.yml

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Run unit tests
        run: pytest tests/ -m "not integration" --cov=acm2
      
      - name: Run integration tests (if keys available)
        if: env.OPENAI_API_KEY != ''
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          TAVILY_API_KEY: ${{ secrets.TAVILY_API_KEY }}
        run: pytest tests/ -m integration --timeout=300
```

---

## 21. Out of Scope

The following features are explicitly excluded from this adapter specification.

### Multi-Agent Orchestration (LangGraph)

GPT-Researcher includes a multi-agent system with LangGraph:
- Chief Editor, Researcher, Editor, Reviewer, Revisor, Writer, Publisher agents
- Complex orchestration via `task.json` configuration
- Parallel agent execution

**Why out of scope:**
- Significantly more complex than single-researcher pattern
- Different cost profile and timing characteristics
- Requires separate testing and monitoring infrastructure
- Can be added as separate adapter (Step 17+ potentially)

**Future consideration:** `acm2/adapters/gptr_multiagent_adapter.py`

### MCP Server Integration

GPT-Researcher supports Model Context Protocol (MCP) servers:
- Custom tool servers for specialized research
- External data source integration
- Real-time data feeds

**Why out of scope:**
- Requires additional infrastructure setup
- Security considerations for external servers
- Not needed for core research functionality

### Custom Retrievers

Beyond the built-in retrievers (tavily, bing, google, duckduckgo, etc.):
- Custom search engine integrations
- Enterprise search connectors (Elasticsearch, Solr)
- Proprietary database connections

**Why out of scope:**
- Built-in retrievers cover most use cases
- Custom retrievers require per-deployment configuration
- Can be contributed as extensions

### Self-Hosted Search Engines

- SearXNG self-hosted instances
- Local Elasticsearch clusters
- On-premise search infrastructure

**Why out of scope:**
- Requires infrastructure setup outside ACM 2.0
- Configuration varies per deployment
- Can use existing retriever options with custom endpoints

### PDF/DOCX Export

Direct export to PDF or Word formats:
- Native PDF generation
- DOCX formatting
- Print-ready layouts

**Why out of scope:**
- GPT-R CLI supports this natively
- ACM 2.0 outputs Markdown (universal format)
- External tools (Pandoc, WeasyPrint) can convert

### Real-Time Research Updates

- Automatic re-research on schedule
- Research result refresh/update
- Change tracking between research runs

**Why out of scope:**
- Complex scheduling infrastructure needed
- Storage requirements for historical data
- Can be built on top of existing adapter

### Citation Style Formatting

Formal citation styles:
- APA, MLA, Chicago, IEEE formatting
- Bibliography generation
- Citation management integration

**Why out of scope:**
- Specialized academic requirement
- Many external tools exist (Zotero, Mendeley)
- Basic citation list is included in sources

### Research Quality Scoring

Automatic quality assessment of research:
- Source credibility scoring
- Fact-checking integration
- Bias detection

**Why out of scope:**
- Requires external fact-checking services
- Subjective quality criteria
- Can be added as custom evaluator

---

## Open Questions

### Resolved

1. **Should GPT-R run in-process or as subprocess for isolation?**
   - **Decision:** In-process. GPT-R is a Python library, subprocess adds complexity without significant benefit. Use async/await for non-blocking execution.

2. **How to handle very long deep research (>10 min)?**
   - **Decision:** Use configurable timeout (default 600s). Progress streaming via WebSocket. User can cancel via API. Store partial results on timeout.

### Open

3. **Should we cache/reuse research context across documents?**
   - **Options:**
     - A) No caching - each query is independent
     - B) Session cache - reuse within a run
     - C) Persistent cache - reuse across runs for similar queries
   - **Consideration:** Caching could reduce costs but may return stale data
   - **Recommendation:** Start with A, add B as optimization later

4. **Rate limiting strategy for GPT-R runs?**
   - **Issue:** GPT-R manages its own API calls and does not natively use our `ACM2_RATE_LIMITING_PLAN.md` logic.
   - **Decision:** For MVP, treat GPT-R as "unmanaged".
     - Set internal concurrency low (1-2) via configuration.
     - Rely on global concurrency limits (e.g., max 2 parallel GPT-R runs) to prevent API flooding.
     - Future: Monkey-patch or configure GPT-R to use a custom HTTP client that respects our rate limiter.

5. **How to handle GPT-R library updates/breaking changes?**
   - **Options:**
     - A) Pin specific version
     - B) Adapter version checking with fallbacks
     - C) Abstract interface with version-specific implementations
   - **Recommendation:** Pin version, document upgrade path

---

## Document Revision History

| Version | Date | Author | Changes |
|---------|------|--------|----------|
| 1.0 | 2024-12-04 | ACM 2.0 Team | Initial specification |

---

## References

- [GPT-Researcher GitHub](https://github.com/assafelovic/gpt-researcher)
- [GPT-Researcher Documentation](https://docs.gptr.dev/)
- [ACM 2.0 Step 9: FPF Adapter](./ACM2_STEP9_FPF_ADAPTER.md)
- [ACM 2.0 Development Steps](./ACM2_DEVELOPMENT_STEPS.md)
