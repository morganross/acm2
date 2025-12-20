# ACM 2.0 Step 17: Combine Integration

> **Platform:** Windows, Linux, macOS. Python + SQLite. No Docker.

---

## 1. Overview

The Combine phase is the final stage of the ACM 2.0 pipeline, responsible for merging multiple artifacts into a single cohesive output.

**Purpose:**
- Merge multiple generated artifacts into a final document
- Select best artifacts based on evaluation scores
- Deduplicate overlapping content from multiple sources
- Create a polished deliverable from multi-document runs

**When Combine Runs:**
```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Generate   │ →  │  Evaluate   │ →  │   Combine   │ →  │   Output    │
│  (FPF/GPTR) │    │  (Score)    │    │  (Merge)    │    │  (Final)    │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
      ↓                  ↓                  ↓                  ↓
   Artifacts         Scores           Combined Doc       Saved/Exported
```

**Key Features:**
1. Multiple combination strategies (concatenate, select best, merge)
2. Score-based artifact selection
3. Source/citation aggregation for GPT-R outputs
4. Table of contents generation
5. LLM-assisted intelligent merging (optional)

**Scope:** This step covers combining artifacts within a single run. Cross-run comparison is out of scope.

---

## 2. Use Cases

### 2.1 Multi-Section Document Generation

Generate different sections with FPF, combine into final document:

```python
# Run with multiple documents (sections)
run = await acm2.create_run(name="Technical Report", generator="fpf")
await acm2.add_document(run.id, content="intro_template.md", section="introduction")
await acm2.add_document(run.id, content="methods_template.md", section="methods")
await acm2.add_document(run.id, content="results_template.md", section="results")
await acm2.add_document(run.id, content="conclusion_template.md", section="conclusion")

# Generate all sections
await acm2.run_generation(run.id)

# Combine into final report
result = await acm2.combine(run.id, strategy="section_assembly")
```

### 2.2 Best-of-N Selection

Generate multiple variants, select the best one:

```python
# Generate 3 variants of the same content
for i in range(3):
    await acm2.add_document(run.id, content="blog_post_template.md", variant=i)

await acm2.run_generation(run.id)
await acm2.run_evaluation(run.id)

# Select best variant based on coherence score
result = await acm2.combine(run.id, strategy="best_of_n", metric="coherence")
```

### 2.3 Research + Generation Hybrid

Use GPT-R for research, then FPF for final formatting:

```python
# Phase 1: Research with GPT-R
research_run = await acm2.create_run(name="Market Research", generator="gptr")
await acm2.add_document(research_run.id, content="Cloud computing market trends")
await acm2.add_document(research_run.id, content="Top cloud providers comparison")
await acm2.run_generation(research_run.id)

# Phase 2: Combine research into context for FPF
research_combined = await acm2.combine(research_run.id, strategy="concatenate")

# Phase 3: Use research as FPF context
report_run = await acm2.create_run(name="Market Report", generator="fpf")
await acm2.add_document(report_run.id, 
    template="executive_report.md",
    context={"research": research_combined.combined_content}
)
```

### 2.4 Multi-Topic Research Consolidation

Research multiple topics, create unified report:

```python
# Research multiple related topics
run = await acm2.create_run(name="AI Overview", generator="gptr")
await acm2.add_document(run.id, content="Machine learning fundamentals")
await acm2.add_document(run.id, content="Deep learning applications")
await acm2.add_document(run.id, content="AI ethics and governance")

await acm2.run_generation(run.id)

# Intelligent merge to create cohesive report
result = await acm2.combine(run.id, 
    strategy="intelligent_merge",
    merge_prompt="Create a comprehensive AI overview report from these research sections."
)
```

### 2.5 Document Assembly from Components

Assemble document from reusable components:

```python
# Standard components
components = [
    ("header", "company_header.md"),
    ("disclaimer", "legal_disclaimer.md"),
    ("body", "main_content.md"),
    ("footer", "standard_footer.md"),
]

for section, template in components:
    await acm2.add_document(run.id, content=template, section=section)

# Assemble in order
result = await acm2.combine(run.id, 
    strategy="section_assembly",
    section_order=["header", "body", "disclaimer", "footer"]
)
```

---

## 3. Combine Strategies

ACM 2.0 supports five combination strategies.

### Strategy Overview

| Strategy | Description | Use When | Cost |
|----------|-------------|----------|------|
| `concatenate` | Append artifacts in order | Simple assembly | Free |
| `best_of_n` | Select highest-scored artifact | Quality selection | Free |
| `section_assembly` | Combine by document structure | Structured docs | Free |
| `intelligent_merge` | LLM-assisted deduplication | Overlapping content | LLM cost |
| `weighted_blend` | Score-weighted combination | Partial selection | Free |

### 3.1 Concatenation

Simplest strategy - append artifacts sequentially.

```
Artifact 1: "# Introduction\n\nThis is the intro..."
Artifact 2: "# Methods\n\nOur approach..."
Artifact 3: "# Results\n\nWe found..."
                    ↓
Combined:   "# Introduction\n\nThis is the intro...\n\n---\n\n# Methods\n\nOur approach...\n\n---\n\n# Results\n\nWe found..."
```

**Options:**
- `separator`: String between artifacts (default: `\n\n---\n\n`)
- `include_toc`: Generate table of contents (default: false)
- `artifact_order`: Custom ordering (default: document order)

### 3.2 Best-of-N Selection

Select single best artifact based on evaluation scores.

```
Artifact 1: score = 0.72
Artifact 2: score = 0.89  ← Selected
Artifact 3: score = 0.65
                    ↓
Combined:   Artifact 2 content (unchanged)
```

**Options:**
- `metric`: Which evaluation metric to use (default: aggregate)
- `tie_breaker`: How to handle ties (first, random, shortest, longest)
- `minimum_score`: Reject if best is below threshold

### 3.3 Section Assembly

Combine artifacts by named sections with defined structure.

```
Document Structure:
├── introduction (doc_id: 1)
├── background (doc_id: 2)
├── analysis (doc_id: 3)
└── conclusion (doc_id: 4)
                    ↓
Combined:   Ordered by structure, with headers
```

**Options:**
- `section_order`: List of section names in order
- `section_headers`: Custom header format per section
- `missing_section_behavior`: error, skip, or placeholder

### 3.4 Intelligent Merge

LLM-assisted combination for overlapping or redundant content.

```
Artifact 1: "AI is transforming healthcare. Machine learning enables..."
Artifact 2: "Machine learning in healthcare is revolutionary. AI systems..."
                    ↓ (LLM merge)
Combined:   "AI and machine learning are transforming healthcare. These technologies enable..."
```

**Options:**
- `merge_prompt`: Custom prompt for LLM
- `model`: LLM to use for merging
- `deduplicate`: Remove redundant content (default: true)
- `preserve_citations`: Keep source references intact

**Cost:** Incurs LLM token costs for merge operation.

### 3.5 Weighted Blend

Select portions of artifacts based on evaluation scores.

```
Artifact 1 (intro): score = 0.9  → Use intro from Artifact 1
Artifact 2 (intro): score = 0.7  → Skip
Artifact 1 (body):  score = 0.6  → Skip
Artifact 2 (body):  score = 0.85 → Use body from Artifact 2
                    ↓
Combined:   Best intro + Best body
```

**Options:**
- `blend_level`: paragraph, section, or document
- `minimum_score`: Threshold for inclusion
- `fallback`: What to do if no section meets threshold

### Strategy Selection Guide

```
Need simple assembly?           → concatenate
Need single best output?        → best_of_n
Have structured document?       → section_assembly
Have overlapping content?       → intelligent_merge
Want best parts from each?      → weighted_blend
```

---

## 4. CombineConfig Schema

Configuration options for the combine phase.

```python
# acm2/schemas/combine.py

from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class CombineStrategy(str, Enum):
    CONCATENATE = "concatenate"
    BEST_OF_N = "best_of_n"
    SECTION_ASSEMBLY = "section_assembly"
    INTELLIGENT_MERGE = "intelligent_merge"
    WEIGHTED_BLEND = "weighted_blend"


class TieBreaker(str, Enum):
    FIRST = "first"      # First in order
    RANDOM = "random"    # Random selection
    SHORTEST = "shortest"  # Shortest content
    LONGEST = "longest"   # Longest content


class BlendLevel(str, Enum):
    DOCUMENT = "document"    # Whole artifact
    SECTION = "section"      # By markdown sections
    PARAGRAPH = "paragraph"  # By paragraph


class MissingSectionBehavior(str, Enum):
    ERROR = "error"          # Fail if section missing
    SKIP = "skip"            # Silently skip
    PLACEHOLDER = "placeholder"  # Insert placeholder text


class CombineConfig(BaseModel):
    """Configuration for combine phase."""
    
    # Strategy selection
    strategy: CombineStrategy = Field(
        CombineStrategy.CONCATENATE,
        description="Combination strategy to use"
    )
    
    # --- Concatenation options ---
    separator: str = Field(
        "\n\n---\n\n",
        description="String to insert between artifacts"
    )
    include_toc: bool = Field(
        False,
        description="Generate table of contents"
    )
    artifact_order: Optional[List[int]] = Field(
        None,
        description="Custom artifact ID ordering (default: document order)"
    )
    
    # --- Best-of-N options ---
    selection_metric: str = Field(
        "aggregate",
        description="Evaluation metric for selection (aggregate, coherence, etc.)"
    )
    tie_breaker: TieBreaker = Field(
        TieBreaker.FIRST,
        description="How to handle tied scores"
    )
    minimum_score: Optional[float] = Field(
        None,
        description="Reject if best score below threshold"
    )
    
    # --- Section Assembly options ---
    section_order: Optional[List[str]] = Field(
        None,
        description="Ordered list of section names"
    )
    section_headers: Optional[Dict[str, str]] = Field(
        None,
        description="Custom header format per section"
    )
    missing_section_behavior: MissingSectionBehavior = Field(
        MissingSectionBehavior.ERROR,
        description="What to do if section is missing"
    )
    
    # --- Intelligent Merge options ---
    merge_prompt: Optional[str] = Field(
        None,
        description="Custom LLM prompt for intelligent merge"
    )
    merge_model: Optional[str] = Field(
        None,
        description="LLM model for merging (default: use config default)"
    )
    deduplicate: bool = Field(
        True,
        description="Remove redundant content"
    )
    preserve_citations: bool = Field(
        True,
        description="Keep source references intact"
    )
    
    # --- Weighted Blend options ---
    blend_level: BlendLevel = Field(
        BlendLevel.SECTION,
        description="Granularity of blending"
    )
    blend_minimum_score: float = Field(
        0.5,
        description="Minimum score for inclusion in blend"
    )
    
    # --- Common options ---
    include_sources: bool = Field(
        True,
        description="Include aggregated sources (for GPT-R artifacts)"
    )
    include_images: bool = Field(
        False,
        description="Include image references"
    )
    output_format: str = Field(
        "markdown",
        description="Output format (markdown, html, plain)"
    )
```

**Example Configs:**

```python
# Simple concatenation
config = CombineConfig(
    strategy=CombineStrategy.CONCATENATE,
    include_toc=True,
)

# Best-of-N by coherence score
config = CombineConfig(
    strategy=CombineStrategy.BEST_OF_N,
    selection_metric="coherence",
    minimum_score=0.7,
)

# Section assembly with custom order
config = CombineConfig(
    strategy=CombineStrategy.SECTION_ASSEMBLY,
    section_order=["executive_summary", "introduction", "analysis", "conclusion"],
    missing_section_behavior=MissingSectionBehavior.PLACEHOLDER,
)

# Intelligent merge with custom prompt
config = CombineConfig(
    strategy=CombineStrategy.INTELLIGENT_MERGE,
    merge_prompt="Combine these research sections into a coherent report. Remove duplicate information and ensure smooth transitions.",
    deduplicate=True,
)
```

---

## 5. CombineResult Schema

Output from the combine phase.

```python
# acm2/schemas/combine.py

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class SourceReference(BaseModel):
    """Aggregated source from GPT-R artifacts."""
    url: str
    title: Optional[str] = None
    domain: Optional[str] = None
    from_artifact_id: int


class ArtifactContribution(BaseModel):
    """How an artifact contributed to the combined output."""
    artifact_id: int
    document_id: int
    included: bool
    reason: str  # "selected_best", "concatenated", "merged", "excluded_low_score"
    score: Optional[float] = None
    content_length: int
    sections_used: Optional[List[str]] = None  # For weighted_blend


class CombineResult(BaseModel):
    """Result of the combine phase."""
    
    # Core output
    combined_content: str = Field(..., description="Final merged document")
    
    # Strategy info
    strategy_used: CombineStrategy
    config_used: CombineConfig
    
    # Source tracking
    source_artifacts: List[int] = Field(
        default_factory=list,
        description="Artifact IDs that contributed to output"
    )
    artifact_contributions: List[ArtifactContribution] = Field(
        default_factory=list,
        description="How each artifact contributed"
    )
    
    # Aggregated sources (from GPT-R)
    sources: List[SourceReference] = Field(
        default_factory=list,
        description="Deduplicated sources from all artifacts"
    )
    source_count: int = 0
    unique_domains: int = 0
    
    # Images (if included)
    images: List[str] = Field(default_factory=list)
    
    # Metrics
    total_input_length: int = Field(0, description="Combined length of input artifacts")
    output_length: int = Field(0, description="Length of final output")
    compression_ratio: float = Field(1.0, description="Output/Input length ratio")
    
    # Cost tracking (for intelligent_merge)
    merge_cost: float = Field(0.0, description="LLM cost for merge operation")
    
    # Timing
    duration_seconds: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Status
    success: bool = True
    warnings: List[str] = Field(default_factory=list)
    error_message: Optional[str] = None


class CombineResultDB(CombineResult):
    """Extended schema for database storage."""
    id: str  # ULID
    run_id: str  # ULID
```

**Example Result:**

```python
result = CombineResult(
    combined_content="# Research Report\n\n## Introduction\n\n...",
    strategy_used=CombineStrategy.SECTION_ASSEMBLY,
    config_used=config,
    source_artifacts=[1, 2, 3],
    artifact_contributions=[
        ArtifactContribution(
            artifact_id=1, document_id=1, included=True,
            reason="concatenated", score=0.85, content_length=1500
        ),
        ArtifactContribution(
            artifact_id=2, document_id=2, included=True,
            reason="concatenated", score=0.78, content_length=2200
        ),
        ArtifactContribution(
            artifact_id=3, document_id=3, included=True,
            reason="concatenated", score=0.82, content_length=1800
        ),
    ],
    sources=[
        SourceReference(url="https://example.com/1", title="Source 1", from_artifact_id=1),
        SourceReference(url="https://example.com/2", title="Source 2", from_artifact_id=2),
    ],
    source_count=2,
    unique_domains=1,
    total_input_length=5500,
    output_length=5800,  # Slightly longer due to separators/TOC
    compression_ratio=1.05,
    duration_seconds=0.25,
)
```

---

## 6. Combiner Interface

Abstract interface and concrete implementations for each strategy.

```python
# acm2/combiners/base.py

from abc import ABC, abstractmethod
from typing import List, Optional
from acm2.schemas.combine import CombineConfig, CombineResult
from acm2.schemas.artifact import Artifact


class CombinerBase(ABC):
    """Abstract base class for combiners."""
    
    @abstractmethod
    async def combine(
        self,
        artifacts: List[Artifact],
        config: CombineConfig,
    ) -> CombineResult:
        """
        Combine multiple artifacts into a single output.
        
        Args:
            artifacts: List of artifacts to combine
            config: Combination configuration
            
        Returns:
            CombineResult with merged content and metadata
        """
        pass
    
    def _aggregate_sources(self, artifacts: List[Artifact]) -> List[SourceReference]:
        """Collect and deduplicate sources from artifacts."""
        seen_urls = set()
        sources = []
        
        for artifact in artifacts:
            artifact_sources = artifact.metadata.get("sources", [])
            for s in artifact_sources:
                url = s.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    sources.append(SourceReference(
                        url=url,
                        title=s.get("title"),
                        domain=s.get("domain"),
                        from_artifact_id=artifact.id,
                    ))
        
        return sources
    
    def _generate_toc(self, content: str) -> str:
        """Generate table of contents from markdown headers."""
        import re
        
        toc_lines = ["## Table of Contents\n"]
        headers = re.findall(r'^(#{1,3})\s+(.+)$', content, re.MULTILINE)
        
        for hashes, title in headers:
            level = len(hashes) - 1
            indent = "  " * level
            anchor = title.lower().replace(" ", "-").replace(".", "")
            toc_lines.append(f"{indent}- [{title}](#{anchor})")
        
        return "\n".join(toc_lines) + "\n\n"


class CombinerFactory:
    """Factory for creating combiners based on strategy."""
    
    _combiners = {}
    
    @classmethod
    def register(cls, strategy: CombineStrategy, combiner_class: type):
        """Register a combiner class for a strategy."""
        cls._combiners[strategy] = combiner_class
    
    @classmethod
    def create(cls, strategy: CombineStrategy, **kwargs) -> CombinerBase:
        """Create a combiner for the given strategy."""
        if strategy not in cls._combiners:
            raise ValueError(f"Unknown strategy: {strategy}")
        
        return cls._combiners[strategy](**kwargs)
    
    @classmethod
    def get_combiner(cls, config: CombineConfig, **kwargs) -> CombinerBase:
        """Create combiner from config."""
        return cls.create(config.strategy, **kwargs)
```

### Combiner Implementations

```python
# acm2/combiners/__init__.py

from acm2.combiners.base import CombinerBase, CombinerFactory
from acm2.combiners.concatenate import ConcatenateCombiner
from acm2.combiners.best_of_n import BestOfNCombiner
from acm2.combiners.section_assembly import SectionAssemblyCombiner
from acm2.combiners.intelligent_merge import IntelligentMergeCombiner
from acm2.combiners.weighted_blend import WeightedBlendCombiner

# Register all combiners
CombinerFactory.register(CombineStrategy.CONCATENATE, ConcatenateCombiner)
CombinerFactory.register(CombineStrategy.BEST_OF_N, BestOfNCombiner)
CombinerFactory.register(CombineStrategy.SECTION_ASSEMBLY, SectionAssemblyCombiner)
CombinerFactory.register(CombineStrategy.INTELLIGENT_MERGE, IntelligentMergeCombiner)
CombinerFactory.register(CombineStrategy.WEIGHTED_BLEND, WeightedBlendCombiner)
```

### Usage

```python
# Get combiner for config
config = CombineConfig(strategy=CombineStrategy.CONCATENATE)
combiner = CombinerFactory.get_combiner(config)

# Combine artifacts
artifacts = await db.get_artifacts(run_id)
result = await combiner.combine(artifacts, config)

print(f"Combined {len(result.source_artifacts)} artifacts")
print(f"Output length: {result.output_length}")
print(f"Sources: {result.source_count}")
```

### Service Layer

```python
# acm2/services/combiner_service.py

class CombinerService:
    """High-level service for combine operations."""
    
    def __init__(self, db, llm_client=None):
        self.db = db
        self.llm_client = llm_client  # For intelligent_merge
    
    async def combine_run(
        self,
        run_id: int,
        config: CombineConfig,
    ) -> CombineResult:
        """Combine all artifacts in a run."""
        
        # Get artifacts
        artifacts = await self.db.get_artifacts(run_id)
        if not artifacts:
            raise ValueError(f"No artifacts found for run {run_id}")
        
        # Get evaluations if needed for scoring
        if config.strategy in [CombineStrategy.BEST_OF_N, CombineStrategy.WEIGHTED_BLEND]:
            for artifact in artifacts:
                artifact.evaluation = await self.db.get_evaluation(artifact.id)
        
        # Create combiner
        combiner = CombinerFactory.get_combiner(
            config,
            llm_client=self.llm_client,
        )
        
        # Combine
        result = await combiner.combine(artifacts, config)
        
        # Save result
        await self.db.save_combined_output(run_id, result)
        
        return result
```

---

## 7. Concatenation Strategy

Simplest strategy - append artifacts sequentially with optional enhancements.

```python
# acm2/combiners/concatenate.py

from typing import List
from acm2.combiners.base import CombinerBase
from acm2.schemas.combine import CombineConfig, CombineResult, ArtifactContribution
from acm2.schemas.artifact import Artifact
import time


class ConcatenateCombiner(CombinerBase):
    """Concatenate artifacts in sequence."""
    
    async def combine(
        self,
        artifacts: List[Artifact],
        config: CombineConfig,
    ) -> CombineResult:
        start_time = time.time()
        
        # Determine order
        if config.artifact_order:
            # Custom order by artifact ID
            id_to_artifact = {a.id: a for a in artifacts}
            ordered = [id_to_artifact[aid] for aid in config.artifact_order if aid in id_to_artifact]
        else:
            # Default: order by document order
            ordered = sorted(artifacts, key=lambda a: a.document_id)
        
        # Build combined content
        parts = []
        contributions = []
        total_input_length = 0
        
        for artifact in ordered:
            parts.append(artifact.content)
            total_input_length += len(artifact.content)
            
            contributions.append(ArtifactContribution(
                artifact_id=artifact.id,
                document_id=artifact.document_id,
                included=True,
                reason="concatenated",
                score=getattr(artifact, 'evaluation', {}).get('aggregate'),
                content_length=len(artifact.content),
            ))
        
        # Join with separator
        combined_content = config.separator.join(parts)
        
        # Add table of contents if requested
        if config.include_toc:
            toc = self._generate_toc(combined_content)
            combined_content = toc + combined_content
        
        # Aggregate sources
        sources = self._aggregate_sources(ordered) if config.include_sources else []
        
        return CombineResult(
            combined_content=combined_content,
            strategy_used=CombineStrategy.CONCATENATE,
            config_used=config,
            source_artifacts=[a.id for a in ordered],
            artifact_contributions=contributions,
            sources=sources,
            source_count=len(sources),
            unique_domains=len(set(s.domain for s in sources if s.domain)),
            total_input_length=total_input_length,
            output_length=len(combined_content),
            compression_ratio=len(combined_content) / total_input_length if total_input_length else 1.0,
            duration_seconds=time.time() - start_time,
        )
```

### Features

**Ordering Options:**
```python
# Default: by document order
config = CombineConfig(strategy=CombineStrategy.CONCATENATE)

# Custom order
config = CombineConfig(
    strategy=CombineStrategy.CONCATENATE,
    artifact_order=[3, 1, 2],  # Specific sequence
)
```

**Separators:**
```python
# Markdown horizontal rule (default)
config = CombineConfig(separator="\n\n---\n\n")

# Page break
config = CombineConfig(separator="\n\n<div style='page-break-after: always;'></div>\n\n")

# Simple newlines
config = CombineConfig(separator="\n\n")

# Custom section marker
config = CombineConfig(separator="\n\n## ---\n\n")
```

**Table of Contents:**
```python
config = CombineConfig(
    strategy=CombineStrategy.CONCATENATE,
    include_toc=True,
)

# Output:
# ## Table of Contents
# - [Introduction](#introduction)
# - [Methods](#methods)
#   - [Data Collection](#data-collection)
# - [Results](#results)
# 
# ---
# 
# # Introduction
# ...
```

---

## 8. Best-of-N Selection Strategy

Select the single best artifact based on evaluation scores.

```python
# acm2/combiners/best_of_n.py

from typing import List, Optional
import random
import time
from acm2.combiners.base import CombinerBase
from acm2.schemas.combine import (
    CombineConfig, CombineResult, CombineStrategy,
    ArtifactContribution, TieBreaker
)
from acm2.schemas.artifact import Artifact


class BestOfNCombiner(CombinerBase):
    """Select best artifact by evaluation score."""
    
    async def combine(
        self,
        artifacts: List[Artifact],
        config: CombineConfig,
    ) -> CombineResult:
        start_time = time.time()
        
        if not artifacts:
            return CombineResult(
                combined_content="",
                strategy_used=CombineStrategy.BEST_OF_N,
                config_used=config,
                success=False,
                error_message="No artifacts to select from",
            )
        
        # Get scores for each artifact
        scored_artifacts = []
        for artifact in artifacts:
            score = self._get_score(artifact, config.selection_metric)
            scored_artifacts.append((artifact, score))
        
        # Sort by score descending
        scored_artifacts.sort(key=lambda x: x[1] if x[1] is not None else -1, reverse=True)
        
        # Check minimum score threshold
        best_artifact, best_score = scored_artifacts[0]
        if config.minimum_score and (best_score is None or best_score < config.minimum_score):
            return CombineResult(
                combined_content="",
                strategy_used=CombineStrategy.BEST_OF_N,
                config_used=config,
                success=False,
                error_message=f"Best score {best_score} below minimum {config.minimum_score}",
                warnings=[f"Best artifact scored {best_score}, below threshold {config.minimum_score}"],
            )
        
        # Handle ties
        tied = [a for a, s in scored_artifacts if s == best_score]
        if len(tied) > 1:
            best_artifact = self._break_tie(tied, config.tie_breaker)
        
        # Build contributions list
        contributions = []
        for artifact, score in scored_artifacts:
            is_selected = artifact.id == best_artifact.id
            contributions.append(ArtifactContribution(
                artifact_id=artifact.id,
                document_id=artifact.document_id,
                included=is_selected,
                reason="selected_best" if is_selected else "not_selected",
                score=score,
                content_length=len(artifact.content),
            ))
        
        # Aggregate sources from selected artifact only
        sources = self._aggregate_sources([best_artifact]) if config.include_sources else []
        
        return CombineResult(
            combined_content=best_artifact.content,
            strategy_used=CombineStrategy.BEST_OF_N,
            config_used=config,
            source_artifacts=[best_artifact.id],
            artifact_contributions=contributions,
            sources=sources,
            source_count=len(sources),
            unique_domains=len(set(s.domain for s in sources if s.domain)),
            total_input_length=sum(len(a.content) for a in artifacts),
            output_length=len(best_artifact.content),
            compression_ratio=len(best_artifact.content) / sum(len(a.content) for a in artifacts),
            duration_seconds=time.time() - start_time,
            metadata={
                "selected_artifact_id": best_artifact.id,
                "selected_score": best_score,
                "selection_metric": config.selection_metric,
                "candidates_count": len(artifacts),
                "tied_count": len(tied),
            }
        )
    
    def _get_score(self, artifact: Artifact, metric: str) -> Optional[float]:
        """Get score for artifact by metric."""
        evaluation = getattr(artifact, 'evaluation', None)
        if not evaluation:
            return None
        
        if metric == "aggregate":
            return evaluation.get('aggregate_score')
        
        scores = evaluation.get('scores', {})
        return scores.get(metric)
    
    def _break_tie(self, tied: List[Artifact], method: TieBreaker) -> Artifact:
        """Break tie between equally-scored artifacts."""
        if method == TieBreaker.FIRST:
            return tied[0]
        elif method == TieBreaker.RANDOM:
            return random.choice(tied)
        elif method == TieBreaker.SHORTEST:
            return min(tied, key=lambda a: len(a.content))
        elif method == TieBreaker.LONGEST:
            return max(tied, key=lambda a: len(a.content))
        else:
            return tied[0]
```

### Features

**Selection by Different Metrics:**
```python
# By aggregate score (default)
config = CombineConfig(
    strategy=CombineStrategy.BEST_OF_N,
    selection_metric="aggregate",
)

# By specific metric
config = CombineConfig(
    strategy=CombineStrategy.BEST_OF_N,
    selection_metric="coherence",
)

# By source quality (for GPT-R)
config = CombineConfig(
    strategy=CombineStrategy.BEST_OF_N,
    selection_metric="source_quality",
)
```

**Tie Breaking:**
```python
# First in order (default)
config = CombineConfig(
    strategy=CombineStrategy.BEST_OF_N,
    tie_breaker=TieBreaker.FIRST,
)

# Random selection
config = CombineConfig(
    strategy=CombineStrategy.BEST_OF_N,
    tie_breaker=TieBreaker.RANDOM,
)

# Prefer shorter content
config = CombineConfig(
    strategy=CombineStrategy.BEST_OF_N,
    tie_breaker=TieBreaker.SHORTEST,
)
```

**Minimum Score Threshold:**
```python
config = CombineConfig(
    strategy=CombineStrategy.BEST_OF_N,
    selection_metric="coherence",
    minimum_score=0.7,  # Reject if best < 0.7
)
```

---

## 9. Section Assembly Strategy

Structure-aware combination that assembles artifacts by named sections.

```python
# acm2/combiners/section_assembly.py

from typing import List, Dict, Optional
import time
from acm2.combiners.base import CombinerBase
from acm2.schemas.combine import (
    CombineConfig, CombineResult, CombineStrategy,
    ArtifactContribution, MissingSectionBehavior
)
from acm2.schemas.artifact import Artifact


class SectionAssemblyCombiner(CombinerBase):
    """Assemble artifacts by section structure."""
    
    async def combine(
        self,
        artifacts: List[Artifact],
        config: CombineConfig,
    ) -> CombineResult:
        start_time = time.time()
        warnings = []
        
        # Build section -> artifact mapping
        section_map: Dict[str, Artifact] = {}
        for artifact in artifacts:
            section = artifact.metadata.get('section') or artifact.document.metadata.get('section')
            if section:
                section_map[section] = artifact
        
        # Determine section order
        if config.section_order:
            ordered_sections = config.section_order
        else:
            # Default: order by document order
            ordered_sections = list(section_map.keys())
        
        # Assemble sections
        parts = []
        contributions = []
        used_artifacts = []
        total_input_length = 0
        
        for section_name in ordered_sections:
            artifact = section_map.get(section_name)
            
            if artifact:
                # Get section content with optional custom header
                content = self._format_section(artifact, section_name, config)
                parts.append(content)
                used_artifacts.append(artifact)
                total_input_length += len(artifact.content)
                
                contributions.append(ArtifactContribution(
                    artifact_id=artifact.id,
                    document_id=artifact.document_id,
                    included=True,
                    reason="assembled",
                    content_length=len(artifact.content),
                    sections_used=[section_name],
                ))
            else:
                # Handle missing section
                if config.missing_section_behavior == MissingSectionBehavior.ERROR:
                    return CombineResult(
                        combined_content="",
                        strategy_used=CombineStrategy.SECTION_ASSEMBLY,
                        config_used=config,
                        success=False,
                        error_message=f"Missing required section: {section_name}",
                    )
                elif config.missing_section_behavior == MissingSectionBehavior.PLACEHOLDER:
                    placeholder = f"## {section_name}\n\n*[Section content not available]*\n"
                    parts.append(placeholder)
                    warnings.append(f"Missing section '{section_name}' replaced with placeholder")
                elif config.missing_section_behavior == MissingSectionBehavior.SKIP:
                    warnings.append(f"Skipped missing section: {section_name}")
        
        # Mark unused artifacts
        for artifact in artifacts:
            if artifact not in used_artifacts:
                contributions.append(ArtifactContribution(
                    artifact_id=artifact.id,
                    document_id=artifact.document_id,
                    included=False,
                    reason="no_matching_section",
                    content_length=len(artifact.content),
                ))
        
        # Join sections
        combined_content = "\n\n".join(parts)
        
        # Add TOC if requested
        if config.include_toc:
            toc = self._generate_toc(combined_content)
            combined_content = toc + combined_content
        
        # Aggregate sources
        sources = self._aggregate_sources(used_artifacts) if config.include_sources else []
        
        return CombineResult(
            combined_content=combined_content,
            strategy_used=CombineStrategy.SECTION_ASSEMBLY,
            config_used=config,
            source_artifacts=[a.id for a in used_artifacts],
            artifact_contributions=contributions,
            sources=sources,
            source_count=len(sources),
            unique_domains=len(set(s.domain for s in sources if s.domain)),
            total_input_length=total_input_length,
            output_length=len(combined_content),
            compression_ratio=len(combined_content) / total_input_length if total_input_length else 1.0,
            duration_seconds=time.time() - start_time,
            warnings=warnings,
            metadata={
                "sections_assembled": [s for s in ordered_sections if s in section_map],
                "sections_missing": [s for s in ordered_sections if s not in section_map],
            }
        )
    
    def _format_section(
        self,
        artifact: Artifact,
        section_name: str,
        config: CombineConfig,
    ) -> str:
        """Format section with optional custom header."""
        content = artifact.content
        
        # Apply custom header if specified
        if config.section_headers and section_name in config.section_headers:
            header_format = config.section_headers[section_name]
            # Remove existing header if content starts with one
            lines = content.split('\n')
            if lines and lines[0].startswith('#'):
                content = '\n'.join(lines[1:]).lstrip()
            content = f"{header_format}\n\n{content}"
        
        return content
```

### Features

**Section Ordering:**
```python
# Define document structure
config = CombineConfig(
    strategy=CombineStrategy.SECTION_ASSEMBLY,
    section_order=[
        "executive_summary",
        "introduction",
        "methodology",
        "findings",
        "recommendations",
        "conclusion",
        "appendix",
    ],
)
```

**Custom Section Headers:**
```python
config = CombineConfig(
    strategy=CombineStrategy.SECTION_ASSEMBLY,
    section_order=["intro", "body", "conclusion"],
    section_headers={
        "intro": "# 1. Introduction",
        "body": "# 2. Main Content",
        "conclusion": "# 3. Conclusion",
    },
)
```

**Missing Section Handling:**
```python
# Fail if any section missing (default for strict assembly)
config = CombineConfig(
    strategy=CombineStrategy.SECTION_ASSEMBLY,
    missing_section_behavior=MissingSectionBehavior.ERROR,
)

# Insert placeholder text
config = CombineConfig(
    strategy=CombineStrategy.SECTION_ASSEMBLY,
    missing_section_behavior=MissingSectionBehavior.PLACEHOLDER,
)

# Silently skip missing sections
config = CombineConfig(
    strategy=CombineStrategy.SECTION_ASSEMBLY,
    missing_section_behavior=MissingSectionBehavior.SKIP,
)
```

**Document Setup:**
```python
# When adding documents, specify section
await acm2.add_document(run.id, content="intro.md", metadata={"section": "introduction"})
await acm2.add_document(run.id, content="methods.md", metadata={"section": "methodology"})
await acm2.add_document(run.id, content="results.md", metadata={"section": "findings"})
```

---

## 10. Intelligent Merge Strategy

LLM-assisted combination that synthesizes a coherent narrative from multiple artifacts.

```python
# acm2/combiners/intelligent_merge.py

from typing import List, Optional
import time
from acm2.combiners.base import CombinerBase
from acm2.schemas.combine import (
    CombineConfig, CombineResult, CombineStrategy,
    ArtifactContribution
)
from acm2.schemas.artifact import Artifact
from acm2.generators.llm import LLMClient


DEFAULT_MERGE_PROMPT = """You are tasked with merging multiple documents into a single coherent output.

Guidelines:
- Remove duplicate information, keeping the best version
- Maintain logical flow between sections
- Preserve all unique insights and data
- Resolve any contradictions by preferring higher-quality sources
- Maintain consistent tone and formatting

Documents to merge:
{documents}

Produce a single, well-organized document that combines all the above."""


class IntelligentMergeCombiner(CombinerBase):
    """LLM-assisted artifact merging."""
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or LLMClient()
    
    async def combine(
        self,
        artifacts: List[Artifact],
        config: CombineConfig,
    ) -> CombineResult:
        start_time = time.time()
        
        if not artifacts:
            return CombineResult(
                combined_content="",
                strategy_used=CombineStrategy.INTELLIGENT_MERGE,
                config_used=config,
                success=False,
                error_message="No artifacts to merge",
            )
        
        # Prepare documents for prompt
        documents_text = self._format_documents_for_prompt(artifacts)
        
        # Get merge prompt
        merge_prompt = config.merge_prompt or DEFAULT_MERGE_PROMPT
        prompt = merge_prompt.format(documents=documents_text)
        
        # Add instructions for structure if specified
        if config.target_structure:
            prompt += f"\n\nTarget structure:\n{config.target_structure}"
        
        # Call LLM
        llm_response = await self.llm.generate(
            prompt=prompt,
            model=config.merge_model or "gpt-4o-mini",
            max_tokens=config.merge_max_tokens or 8000,
            temperature=0.3,  # Lower temp for consistency
        )
        
        combined_content = llm_response.content
        
        # Track contribution (all artifacts contributed)
        contributions = [
            ArtifactContribution(
                artifact_id=a.id,
                document_id=a.document_id,
                included=True,
                reason="merged",
                content_length=len(a.content),
            )
            for a in artifacts
        ]
        
        # Aggregate sources
        sources = self._aggregate_sources(artifacts) if config.include_sources else []
        
        total_input_length = sum(len(a.content) for a in artifacts)
        
        return CombineResult(
            combined_content=combined_content,
            strategy_used=CombineStrategy.INTELLIGENT_MERGE,
            config_used=config,
            source_artifacts=[a.id for a in artifacts],
            artifact_contributions=contributions,
            sources=sources,
            source_count=len(sources),
            unique_domains=len(set(s.domain for s in sources if s.domain)),
            total_input_length=total_input_length,
            output_length=len(combined_content),
            compression_ratio=len(combined_content) / total_input_length if total_input_length else 1.0,
            duration_seconds=time.time() - start_time,
            cost=llm_response.cost,
            metadata={
                "merge_model": config.merge_model or "gpt-4o-mini",
                "prompt_tokens": llm_response.prompt_tokens,
                "completion_tokens": llm_response.completion_tokens,
            }
        )
    
    def _format_documents_for_prompt(self, artifacts: List[Artifact]) -> str:
        """Format artifacts for inclusion in merge prompt."""
        parts = []
        for i, artifact in enumerate(artifacts, 1):
            doc_label = artifact.document.filename if artifact.document else f"Document {i}"
            parts.append(f"--- {doc_label} ---\n{artifact.content}")
        return "\n\n".join(parts)
```

### Features

**Custom Merge Prompt:**
```python
config = CombineConfig(
    strategy=CombineStrategy.INTELLIGENT_MERGE,
    merge_prompt="""Synthesize these research documents into a comprehensive report.
    Focus on:
    - Key findings from each source
    - Areas of agreement and disagreement
    - Gaps in the research
    
    Documents:
    {documents}
    """,
)
```

**Model Selection:**
```python
# Use GPT-4 for complex merges
config = CombineConfig(
    strategy=CombineStrategy.INTELLIGENT_MERGE,
    merge_model="gpt-4o",
    merge_max_tokens=16000,
)

# Use cheaper model for simple merges
config = CombineConfig(
    strategy=CombineStrategy.INTELLIGENT_MERGE,
    merge_model="gpt-4o-mini",
    merge_max_tokens=4000,
)
```

**Target Structure:**
```python
config = CombineConfig(
    strategy=CombineStrategy.INTELLIGENT_MERGE,
    target_structure="""1. Executive Summary
    2. Background
    3. Key Findings
    4. Analysis
    5. Recommendations
    6. Appendices""",
)
```

**Cost Tracking:**
```python
result = await combiner.combine(artifacts, config)

print(f"Merge cost: ${result.cost:.4f}")
print(f"Tokens used: {result.metadata['prompt_tokens']} + {result.metadata['completion_tokens']}")
```

---

## 11. Source and Citation Handling

Aggregating and deduplicating sources from multiple artifacts, especially GPT-R outputs.

```python
# acm2/combiners/source_handler.py

from typing import List, Dict, Set, Optional
from urllib.parse import urlparse
from dataclasses import dataclass
from acm2.schemas.artifact import Artifact
from acm2.schemas.combine import SourceReference


@dataclass
class AggregatedSource:
    """Source aggregated from multiple artifacts."""
    url: str
    title: Optional[str]
    domain: str
    from_artifacts: List[int]  # Artifact IDs that used this source
    citation_count: int        # How many artifacts cited this
    

class SourceHandler:
    """Handle source aggregation and citation generation."""
    
    def aggregate_sources(
        self,
        artifacts: List[Artifact],
        deduplicate: bool = True,
    ) -> List[AggregatedSource]:
        """
        Aggregate sources from multiple artifacts.
        
        Args:
            artifacts: Artifacts to extract sources from
            deduplicate: Whether to merge duplicate URLs
            
        Returns:
            List of aggregated sources with citation counts
        """
        url_map: Dict[str, AggregatedSource] = {}
        
        for artifact in artifacts:
            sources = self._extract_sources(artifact)
            
            for source in sources:
                url = self._normalize_url(source.url) if deduplicate else source.url
                
                if url in url_map:
                    # Update existing
                    url_map[url].from_artifacts.append(artifact.id)
                    url_map[url].citation_count += 1
                else:
                    # Add new
                    url_map[url] = AggregatedSource(
                        url=source.url,  # Keep original URL
                        title=source.title,
                        domain=urlparse(source.url).netloc,
                        from_artifacts=[artifact.id],
                        citation_count=1,
                    )
        
        return list(url_map.values())
    
    def _extract_sources(self, artifact: Artifact) -> List[SourceReference]:
        """Extract sources from artifact metadata."""
        sources = []
        
        # From metadata.sources (GPT-R format)
        raw_sources = artifact.metadata.get("sources", [])
        for s in raw_sources:
            if isinstance(s, dict):
                sources.append(SourceReference(
                    url=s.get("url", ""),
                    title=s.get("title"),
                    domain=s.get("domain"),
                ))
        
        return sources
    
    def _normalize_url(self, url: str) -> str:
        """Normalize URL for deduplication."""
        # Remove trailing slashes, normalize case
        parsed = urlparse(url.lower())
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"
        return normalized
    
    def generate_reference_list(
        self,
        sources: List[AggregatedSource],
        format: str = "markdown",
        sort_by: str = "citation_count",
    ) -> str:
        """
        Generate formatted reference list.
        
        Args:
            sources: Aggregated sources
            format: Output format (markdown, html, plain)
            sort_by: Sort order (citation_count, domain, title)
            
        Returns:
            Formatted reference list
        """
        # Sort sources
        if sort_by == "citation_count":
            sorted_sources = sorted(sources, key=lambda s: s.citation_count, reverse=True)
        elif sort_by == "domain":
            sorted_sources = sorted(sources, key=lambda s: s.domain)
        elif sort_by == "title":
            sorted_sources = sorted(sources, key=lambda s: s.title or "")
        else:
            sorted_sources = sources
        
        if format == "markdown":
            return self._format_markdown(sorted_sources)
        elif format == "html":
            return self._format_html(sorted_sources)
        else:
            return self._format_plain(sorted_sources)
    
    def _format_markdown(self, sources: List[AggregatedSource]) -> str:
        """Format as markdown reference list."""
        lines = ["## References\n"]
        for i, s in enumerate(sources, 1):
            title = s.title or s.url
            lines.append(f"{i}. [{title}]({s.url}) - *{s.domain}*")
        return "\n".join(lines)
    
    def _format_html(self, sources: List[AggregatedSource]) -> str:
        """Format as HTML reference list."""
        lines = ["<h2>References</h2>\n<ol>"]
        for s in sources:
            title = s.title or s.url
            lines.append(f'  <li><a href="{s.url}">{title}</a> - <em>{s.domain}</em></li>')
        lines.append("</ol>")
        return "\n".join(lines)
    
    def _format_plain(self, sources: List[AggregatedSource]) -> str:
        """Format as plain text."""
        lines = ["References:\n"]
        for i, s in enumerate(sources, 1):
            title = s.title or "Untitled"
            lines.append(f"{i}. {title}")
            lines.append(f"   URL: {s.url}")
            lines.append(f"   Domain: {s.domain}")
            lines.append("")
        return "\n".join(lines)
```

### Usage Examples

**Basic Source Aggregation:**
```python
handler = SourceHandler()
sources = handler.aggregate_sources(artifacts)

print(f"Total unique sources: {len(sources)}")
for s in sources:
    print(f"  - {s.domain}: cited {s.citation_count} times")
```

**Generate Reference List:**
```python
handler = SourceHandler()
sources = handler.aggregate_sources(artifacts)

# Markdown format sorted by citations
references = handler.generate_reference_list(
    sources,
    format="markdown",
    sort_by="citation_count",
)

# Append to combined content
combined_content += f"\n\n---\n\n{references}"
```

**Integration with Combiner:**
```python
class ConcatenateCombiner(CombinerBase):
    def __init__(self):
        self.source_handler = SourceHandler()
    
    async def combine(self, artifacts, config):
        # ... combine content ...
        
        if config.include_sources:
            sources = self.source_handler.aggregate_sources(artifacts)
            ref_list = self.source_handler.generate_reference_list(sources)
            combined_content += f"\n\n{ref_list}"
        
        # ...
```

**Source Statistics:**
```python
sources = handler.aggregate_sources(artifacts)

stats = {
    "total_sources": len(sources),
    "unique_domains": len(set(s.domain for s in sources)),
    "most_cited": max(sources, key=lambda s: s.citation_count) if sources else None,
    "domain_breakdown": {},
}

for s in sources:
    stats["domain_breakdown"][s.domain] = stats["domain_breakdown"].get(s.domain, 0) + 1
```

---

## 12. Integration with Pipeline

Combine as the final phase in the artifact generation pipeline.

### Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         ACM2 PIPELINE                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐            │
│  │  GENERATION  │────▶│  EVALUATION  │────▶│   COMBINE    │            │
│  │    Phase     │     │    Phase     │     │    Phase     │            │
│  └──────────────┘     └──────────────┘     └──────────────┘            │
│         │                    │                    │                    │
│         ▼                    ▼                    ▼                    │
│   Raw Artifacts        Scored Artifacts    Combined Output             │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Pipeline Service Integration

```python
# acm2/pipeline/orchestrator.py

from typing import Optional
from acm2.generators import GeneratorService
from acm2.evaluators import EvaluatorService
from acm2.combiners import CombinerService
from acm2.schemas.run import Run, RunPhase
from acm2.schemas.combine import CombineConfig, CombineResult
from acm2.database import Database


class PipelineOrchestrator:
    """Orchestrate the full artifact pipeline."""
    
    def __init__(self, db: Database):
        self.db = db
        self.generator = GeneratorService(db)
        self.evaluator = EvaluatorService(db)
        self.combiner = CombinerService(db)
    
    async def run_full_pipeline(
        self,
        run_id: int,
        combine_config: Optional[CombineConfig] = None,
        auto_combine: bool = True,
    ) -> CombineResult:
        """
        Execute full pipeline: generate -> evaluate -> combine.
        
        Args:
            run_id: Run to process
            combine_config: Optional combine configuration
            auto_combine: Whether to auto-trigger combine after evaluation
            
        Returns:
            Final combined result
        """
        run = await self.db.get_run(run_id)
        
        # Phase 1: Generation
        if run.phase == RunPhase.PENDING:
            await self._update_phase(run, RunPhase.GENERATING)
            artifacts = await self.generator.generate_all(run_id)
            await self._update_phase(run, RunPhase.GENERATED)
        else:
            artifacts = await self.db.get_artifacts(run_id)
        
        # Phase 2: Evaluation
        if run.phase in [RunPhase.GENERATED, RunPhase.PENDING_EVALUATION]:
            await self._update_phase(run, RunPhase.EVALUATING)
            evaluated = await self.evaluator.evaluate_all(run_id)
            await self._update_phase(run, RunPhase.EVALUATED)
        else:
            evaluated = artifacts
        
        # Phase 3: Combine
        if auto_combine and run.phase == RunPhase.EVALUATED:
            await self._update_phase(run, RunPhase.COMBINING)
            config = combine_config or self._get_default_config(run)
            result = await self.combiner.combine(run_id, config)
            await self._update_phase(run, RunPhase.COMPLETED)
            return result
        
        return None
    
    async def _update_phase(self, run: Run, phase: RunPhase):
        """Update run phase in database."""
        run.phase = phase
        await self.db.update_run(run)
    
    def _get_default_config(self, run: Run) -> CombineConfig:
        """Get default combine config based on run settings."""
        if run.config.combine:
            return run.config.combine
        
        # Default to concatenate for multiple docs, best_of_n for single
        doc_count = len(run.documents)
        if doc_count == 1:
            return CombineConfig(strategy=CombineStrategy.BEST_OF_N)
        else:
            return CombineConfig(strategy=CombineStrategy.CONCATENATE)
```

### Phase Transitions

```python
class RunPhase(str, Enum):
    PENDING = "pending"                    # Initial state
    GENERATING = "generating"              # Generation in progress
    GENERATED = "generated"                # Generation complete
    PENDING_EVALUATION = "pending_evaluation"  # Awaiting eval
    EVALUATING = "evaluating"              # Evaluation in progress
    EVALUATED = "evaluated"                # Evaluation complete
    COMBINING = "combining"                # Combine in progress
    COMPLETED = "completed"                # All phases complete
    FAILED = "failed"                      # Pipeline failed
```

### Manual vs Automatic Combine

**Automatic (Default):**
```python
# Combine triggers automatically after evaluation
result = await pipeline.run_full_pipeline(
    run_id=123,
    auto_combine=True,
)
```

**Manual:**
```python
# Run generation and evaluation only
await pipeline.run_full_pipeline(
    run_id=123,
    auto_combine=False,
)

# Later, trigger combine manually
result = await pipeline.combiner.combine(
    run_id=123,
    config=CombineConfig(
        strategy=CombineStrategy.BEST_OF_N,
        selection_metric="coherence",
    ),
)
```

### Event Hooks

```python
class PipelineOrchestrator:
    def __init__(self, db: Database):
        # ...
        self.on_phase_change = []  # Callbacks for phase changes
        self.on_combine_complete = []  # Callbacks for combine completion
    
    async def _update_phase(self, run: Run, phase: RunPhase):
        old_phase = run.phase
        run.phase = phase
        await self.db.update_run(run)
        
        # Notify listeners
        for callback in self.on_phase_change:
            await callback(run.id, old_phase, phase)
    
    async def run_full_pipeline(self, run_id, ...):
        # ... pipeline logic ...
        
        if result:
            for callback in self.on_combine_complete:
                await callback(run_id, result)
        
        return result

# Usage
pipeline = PipelineOrchestrator(db)

async def log_phase_change(run_id, old_phase, new_phase):
    print(f"Run {run_id}: {old_phase} -> {new_phase}")

pipeline.on_phase_change.append(log_phase_change)
```

---

## 13. Database Schema

SQLite schema for storing combined outputs.

### combined_outputs Table

```sql
CREATE TABLE combined_outputs (
    id TEXT PRIMARY KEY,  -- ULID
    run_id TEXT NOT NULL,
    
    -- Strategy used
    strategy TEXT NOT NULL,  -- 'concatenate', 'best_of_n', 'section_assembly', etc.
    
    -- Combined content
    combined_content TEXT NOT NULL,
    content_length INTEGER NOT NULL,
    
    -- Source tracking
    source_artifact_ids TEXT NOT NULL,  -- JSON array: [1, 2, 3]
    artifact_contributions TEXT,         -- JSON array of contribution details
    
    -- Sources (for GPT-R)
    sources TEXT,            -- JSON array of source references
    source_count INTEGER DEFAULT 0,
    unique_domains INTEGER DEFAULT 0,
    
    -- Metrics
    total_input_length INTEGER,
    compression_ratio REAL,
    duration_seconds REAL,
    cost REAL,               -- For intelligent_merge LLM cost
    
    -- Configuration
    config_used TEXT,        -- JSON: full CombineConfig
    
    -- Status
    success INTEGER DEFAULT 1,
    error_message TEXT,
    warnings TEXT,           -- JSON array
    
    -- Metadata
    metadata TEXT,           -- JSON: strategy-specific metadata
    
    -- Timestamps
    created_at TEXT DEFAULT (datetime('now')),
    
    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
);

-- Index for run lookups
CREATE INDEX idx_combined_outputs_run_id ON combined_outputs(run_id);

-- Index for strategy filtering
CREATE INDEX idx_combined_outputs_strategy ON combined_outputs(strategy);
```

### Repository Methods

```python
# acm2/database/repositories/combined_output_repository.py

from typing import List, Optional
import json
from acm2.database.base import BaseRepository
from acm2.schemas.combine import CombineResult, CombineStrategy


class CombinedOutputRepository(BaseRepository):
    """Repository for combined_outputs table."""
    
    async def save(self, run_id: int, result: CombineResult) -> int:
        """Save combined output to database."""
        query = """
            INSERT INTO combined_outputs (
                run_id, strategy, combined_content, content_length,
                source_artifact_ids, artifact_contributions,
                sources, source_count, unique_domains,
                total_input_length, compression_ratio, duration_seconds, cost,
                config_used, success, error_message, warnings, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        cursor = await self.db.execute(query, (
            run_id,
            result.strategy_used.value,
            result.combined_content,
            result.output_length,
            json.dumps(result.source_artifacts),
            json.dumps([c.dict() for c in result.artifact_contributions]),
            json.dumps([s.dict() for s in result.sources]),
            result.source_count,
            result.unique_domains,
            result.total_input_length,
            result.compression_ratio,
            result.duration_seconds,
            result.cost,
            json.dumps(result.config_used.dict()),
            1 if result.success else 0,
            result.error_message,
            json.dumps(result.warnings),
            json.dumps(result.metadata),
        ))
        
        await self.db.commit()
        return cursor.lastrowid
    
    async def get_by_run(self, run_id: int) -> Optional[CombineResult]:
        """Get latest combined output for a run."""
        query = """
            SELECT * FROM combined_outputs
            WHERE run_id = ?
            ORDER BY created_at DESC
            LIMIT 1
        """
        
        row = await self.db.fetchone(query, (run_id,))
        if not row:
            return None
        
        return self._row_to_result(row)
    
    async def get_all_by_run(self, run_id: int) -> List[CombineResult]:
        """Get all combined outputs for a run (history)."""
        query = """
            SELECT * FROM combined_outputs
            WHERE run_id = ?
            ORDER BY created_at DESC
        """
        
        rows = await self.db.fetchall(query, (run_id,))
        return [self._row_to_result(row) for row in rows]
    
    async def delete_by_run(self, run_id: int) -> int:
        """Delete all combined outputs for a run."""
        query = "DELETE FROM combined_outputs WHERE run_id = ?"
        cursor = await self.db.execute(query, (run_id,))
        await self.db.commit()
        return cursor.rowcount
    
    def _row_to_result(self, row: dict) -> CombineResult:
        """Convert database row to CombineResult."""
        return CombineResult(
            combined_content=row['combined_content'],
            strategy_used=CombineStrategy(row['strategy']),
            config_used=CombineConfig(**json.loads(row['config_used'])),
            source_artifacts=json.loads(row['source_artifact_ids']),
            artifact_contributions=[
                ArtifactContribution(**c) 
                for c in json.loads(row['artifact_contributions'] or '[]')
            ],
            sources=[
                SourceReference(**s)
                for s in json.loads(row['sources'] or '[]')
            ],
            source_count=row['source_count'],
            unique_domains=row['unique_domains'],
            total_input_length=row['total_input_length'],
            output_length=row['content_length'],
            compression_ratio=row['compression_ratio'],
            duration_seconds=row['duration_seconds'],
            cost=row['cost'],
            success=bool(row['success']),
            error_message=row['error_message'],
            warnings=json.loads(row['warnings'] or '[]'),
            metadata=json.loads(row['metadata'] or '{}'),
        )
```

### Migration

```python
# acm2/database/migrations/004_add_combined_outputs.py

MIGRATION_SQL = """
-- Create combined_outputs table
CREATE TABLE IF NOT EXISTS combined_outputs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    strategy TEXT NOT NULL,
    combined_content TEXT NOT NULL,
    content_length INTEGER NOT NULL,
    source_artifact_ids TEXT NOT NULL,
    artifact_contributions TEXT,
    sources TEXT,
    source_count INTEGER DEFAULT 0,
    unique_domains INTEGER DEFAULT 0,
    total_input_length INTEGER,
    compression_ratio REAL,
    duration_seconds REAL,
    cost REAL,
    config_used TEXT,
    success INTEGER DEFAULT 1,
    error_message TEXT,
    warnings TEXT,
    metadata TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_combined_outputs_run_id ON combined_outputs(run_id);
CREATE INDEX IF NOT EXISTS idx_combined_outputs_strategy ON combined_outputs(strategy);
"""
```

---

## 14. API Endpoints

FastAPI endpoints for combine operations.

```python
# acm2/api/routes/combine.py

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from acm2.schemas.combine import (
    CombineConfig, CombineResult, CombineStrategy,
    CombineRequest, CombineResponse
)
from acm2.combiners import CombinerService
from acm2.database import get_db

router = APIRouter(prefix="/runs/{run_id}", tags=["combine"])


@router.post("/combine", response_model=CombineResponse)
async def combine_artifacts(
    run_id: int,
    request: CombineRequest,
    db = Depends(get_db),
):
    """
    Combine artifacts for a run.
    
    Triggers the combine phase with specified strategy and options.
    Returns the combined output.
    """
    service = CombinerService(db)
    
    # Build config from request
    config = CombineConfig(
        strategy=request.strategy,
        separator=request.separator,
        include_toc=request.include_toc,
        include_sources=request.include_sources,
        artifact_order=request.artifact_order,
        selection_metric=request.selection_metric,
        tie_breaker=request.tie_breaker,
        minimum_score=request.minimum_score,
        section_order=request.section_order,
        merge_prompt=request.merge_prompt,
        merge_model=request.merge_model,
    )
    
    try:
        result = await service.combine(run_id, config)
        
        if not result.success:
            raise HTTPException(
                status_code=400,
                detail=result.error_message or "Combine failed"
            )
        
        return CombineResponse(
            success=True,
            combined_content=result.combined_content,
            strategy=result.strategy_used.value,
            source_artifact_count=len(result.source_artifacts),
            source_count=result.source_count,
            output_length=result.output_length,
            compression_ratio=result.compression_ratio,
            duration_seconds=result.duration_seconds,
            cost=result.cost,
            warnings=result.warnings,
        )
    
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/combined-output", response_model=CombineResponse)
async def get_combined_output(
    run_id: int,
    db = Depends(get_db),
):
    """
    Get the latest combined output for a run.
    
    Returns 404 if no combined output exists.
    """
    service = CombinerService(db)
    result = await service.get_combined(run_id)
    
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"No combined output found for run {run_id}"
        )
    
    return CombineResponse(
        success=result.success,
        combined_content=result.combined_content,
        strategy=result.strategy_used.value,
        source_artifact_count=len(result.source_artifacts),
        source_count=result.source_count,
        output_length=result.output_length,
        compression_ratio=result.compression_ratio,
        duration_seconds=result.duration_seconds,
        cost=result.cost,
        warnings=result.warnings,
    )


@router.get("/combined-output/sources")
async def get_combined_sources(
    run_id: int,
    format: str = "json",
    sort_by: str = "citation_count",
    db = Depends(get_db),
):
    """
    Get aggregated sources from combined output.
    
    Query params:
    - format: json, markdown, html, plain
    - sort_by: citation_count, domain, title
    """
    service = CombinerService(db)
    result = await service.get_combined(run_id)
    
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"No combined output found for run {run_id}"
        )
    
    if format == "json":
        return {
            "sources": [s.dict() for s in result.sources],
            "total": result.source_count,
            "unique_domains": result.unique_domains,
        }
    else:
        # Generate formatted reference list
        handler = SourceHandler()
        formatted = handler.generate_reference_list(
            result.sources,
            format=format,
            sort_by=sort_by,
        )
        return {"formatted": formatted, "format": format}


@router.get("/combined-output/history")
async def get_combine_history(
    run_id: int,
    db = Depends(get_db),
):
    """
    Get all historical combined outputs for a run.
    
    Useful for comparing different combine strategies.
    """
    service = CombinerService(db)
    results = await service.get_all_combined(run_id)
    
    return {
        "run_id": run_id,
        "count": len(results),
        "history": [
            {
                "strategy": r.strategy_used.value,
                "output_length": r.output_length,
                "source_count": r.source_count,
                "created_at": r.created_at,
                "success": r.success,
            }
            for r in results
        ],
    }


@router.delete("/combined-output")
async def delete_combined_output(
    run_id: int,
    db = Depends(get_db),
):
    """
    Delete all combined outputs for a run.
    
    Allows re-running combine with different strategy.
    """
    service = CombinerService(db)
    deleted = await service.delete_combined(run_id)
    
    return {
        "deleted": deleted,
        "message": f"Deleted {deleted} combined output(s) for run {run_id}",
    }
```

### Request/Response Schemas

```python
# acm2/schemas/combine.py (additional schemas)

from pydantic import BaseModel
from typing import Optional, List


class CombineRequest(BaseModel):
    """Request body for POST /combine."""
    
    strategy: CombineStrategy = CombineStrategy.CONCATENATE
    
    # Common options
    include_toc: bool = False
    include_sources: bool = True
    
    # Concatenate options
    separator: Optional[str] = None
    artifact_order: Optional[List[int]] = None
    
    # Best-of-N options
    selection_metric: str = "aggregate"
    tie_breaker: Optional[TieBreaker] = None
    minimum_score: Optional[float] = None
    
    # Section Assembly options
    section_order: Optional[List[str]] = None
    
    # Intelligent Merge options
    merge_prompt: Optional[str] = None
    merge_model: Optional[str] = None


class CombineResponse(BaseModel):
    """Response from combine endpoints."""
    
    success: bool
    combined_content: str
    strategy: str
    source_artifact_count: int
    source_count: int
    output_length: int
    compression_ratio: float
    duration_seconds: float
    cost: Optional[float] = None
    warnings: List[str] = []
```

### Example API Calls

```bash
# Combine with concatenate (default)
curl -X POST "http://localhost:8000/runs/123/combine" \
  -H "Content-Type: application/json" \
  -d '{"strategy": "concatenate", "include_toc": true}'

# Combine with best-of-n
curl -X POST "http://localhost:8000/runs/123/combine" \
  -H "Content-Type: application/json" \
  -d '{"strategy": "best_of_n", "selection_metric": "coherence"}'

# Get combined output
curl "http://localhost:8000/runs/123/combined-output"

# Get sources as markdown
curl "http://localhost:8000/runs/123/combined-output/sources?format=markdown"
```

---

## 15. CLI Commands

CLI commands for combine operations.

```python
# acm2/cli/commands/combine.py

import click
import asyncio
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from acm2.combiners import CombinerService
from acm2.schemas.combine import CombineConfig, CombineStrategy, TieBreaker
from acm2.database import Database

console = Console()


@click.group()
def combine():
    """Combine artifacts into final output."""
    pass


@combine.command("run")
@click.option("--run-id", "-r", required=True, type=int, help="Run ID to combine")
@click.option(
    "--strategy", "-s",
    type=click.Choice(["concatenate", "best_of_n", "section_assembly", "intelligent_merge"]),
    default="concatenate",
    help="Combination strategy"
)
@click.option("--metric", "-m", default="aggregate", help="Selection metric (for best_of_n)")
@click.option("--min-score", type=float, help="Minimum score threshold (for best_of_n)")
@click.option("--separator", help="Separator between artifacts (for concatenate)")
@click.option("--toc/--no-toc", default=False, help="Include table of contents")
@click.option("--sources/--no-sources", default=True, help="Include source references")
@click.option("--order", help="Artifact order as comma-separated IDs")
@click.option("--section-order", help="Section order as comma-separated names")
@click.option("--merge-model", help="Model for intelligent merge")
@click.option("--output", "-o", type=click.Path(), help="Output file path")
@click.option("--format", "output_format", type=click.Choice(["markdown", "html", "json"]), default="markdown")
def run_combine(
    run_id: int,
    strategy: str,
    metric: str,
    min_score: float,
    separator: str,
    toc: bool,
    sources: bool,
    order: str,
    section_order: str,
    merge_model: str,
    output: str,
    output_format: str,
):
    """
    Combine artifacts for a run.
    
    Examples:
    
        # Simple concatenation
        acm2 combine run --run-id 123 --strategy concatenate
        
        # Best-of-N by coherence score
        acm2 combine run --run-id 123 --strategy best_of_n --metric coherence
        
        # Section assembly with custom order
        acm2 combine run --run-id 123 --strategy section_assembly --section-order "intro,body,conclusion"
        
        # Save to file
        acm2 combine run --run-id 123 -o output.md
    """
    # Build config
    config = CombineConfig(
        strategy=CombineStrategy(strategy),
        selection_metric=metric,
        minimum_score=min_score,
        separator=separator or "\n\n---\n\n",
        include_toc=toc,
        include_sources=sources,
        artifact_order=[int(x) for x in order.split(",")] if order else None,
        section_order=section_order.split(",") if section_order else None,
        merge_model=merge_model,
    )
    
    async def _run():
        db = Database()
        await db.connect()
        service = CombinerService(db)
        
        with console.status(f"[bold blue]Combining artifacts for run {run_id}..."):
            result = await service.combine(run_id, config)
        
        await db.close()
        return result
    
    result = asyncio.run(_run())
    
    if not result.success:
        console.print(f"[red]Combine failed: {result.error_message}[/red]")
        raise click.Abort()
    
    # Display summary
    table = Table(title=f"Combine Results - Run {run_id}")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Strategy", result.strategy_used.value)
    table.add_row("Source Artifacts", str(len(result.source_artifacts)))
    table.add_row("Output Length", f"{result.output_length:,} chars")
    table.add_row("Compression Ratio", f"{result.compression_ratio:.2f}")
    table.add_row("Sources", str(result.source_count))
    table.add_row("Duration", f"{result.duration_seconds:.2f}s")
    if result.cost:
        table.add_row("Cost", f"${result.cost:.4f}")
    
    console.print(table)
    
    if result.warnings:
        for w in result.warnings:
            console.print(f"[yellow]Warning: {w}[/yellow]")
    
    # Output
    if output:
        with open(output, "w", encoding="utf-8") as f:
            f.write(result.combined_content)
        console.print(f"\n[green]Saved to {output}[/green]")
    else:
        # Print preview
        preview = result.combined_content[:500]
        if len(result.combined_content) > 500:
            preview += "\n...\n[truncated]"
        console.print(Panel(preview, title="Output Preview"))


@combine.command("show")
@click.option("--run-id", "-r", required=True, type=int, help="Run ID")
@click.option("--output", "-o", type=click.Path(), help="Output file path")
@click.option("--sources", is_flag=True, help="Show sources only")
def show_combined(run_id: int, output: str, sources: bool):
    """
    Show existing combined output for a run.
    
    Examples:
    
        # View combined output
        acm2 combine show --run-id 123
        
        # Save to file
        acm2 combine show --run-id 123 -o output.md
        
        # Show sources only
        acm2 combine show --run-id 123 --sources
    """
    async def _run():
        db = Database()
        await db.connect()
        service = CombinerService(db)
        result = await service.get_combined(run_id)
        await db.close()
        return result
    
    result = asyncio.run(_run())
    
    if not result:
        console.print(f"[red]No combined output found for run {run_id}[/red]")
        raise click.Abort()
    
    if sources:
        # Show sources
        table = Table(title="Sources")
        table.add_column("#", style="dim")
        table.add_column("Title")
        table.add_column("Domain", style="cyan")
        table.add_column("URL", style="dim")
        
        for i, s in enumerate(result.sources, 1):
            table.add_row(str(i), s.title or "Untitled", s.domain, s.url[:50])
        
        console.print(table)
    elif output:
        with open(output, "w", encoding="utf-8") as f:
            f.write(result.combined_content)
        console.print(f"[green]Saved to {output}[/green]")
    else:
        console.print(result.combined_content)


@combine.command("history")
@click.option("--run-id", "-r", required=True, type=int, help="Run ID")
def show_history(run_id: int):
    """
    Show combine history for a run.
    
    Displays all previous combine operations.
    """
    async def _run():
        db = Database()
        await db.connect()
        service = CombinerService(db)
        results = await service.get_all_combined(run_id)
        await db.close()
        return results
    
    results = asyncio.run(_run())
    
    if not results:
        console.print(f"[yellow]No combine history for run {run_id}[/yellow]")
        return
    
    table = Table(title=f"Combine History - Run {run_id}")
    table.add_column("#", style="dim")
    table.add_column("Strategy")
    table.add_column("Output Length")
    table.add_column("Sources")
    table.add_column("Duration")
    table.add_column("Success")
    
    for i, r in enumerate(results, 1):
        success = "[green]✓[/green]" if r.success else "[red]✗[/red]"
        table.add_row(
            str(i),
            r.strategy_used.value,
            f"{r.output_length:,}",
            str(r.source_count),
            f"{r.duration_seconds:.2f}s",
            success,
        )
    
    console.print(table)


@combine.command("clear")
@click.option("--run-id", "-r", required=True, type=int, help="Run ID")
@click.confirmation_option(prompt="Delete all combined outputs for this run?")
def clear_combined(run_id: int):
    """
    Delete all combined outputs for a run.
    
    Allows re-running combine with different strategy.
    """
    async def _run():
        db = Database()
        await db.connect()
        service = CombinerService(db)
        deleted = await service.delete_combined(run_id)
        await db.close()
        return deleted
    
    deleted = asyncio.run(_run())
    console.print(f"[green]Deleted {deleted} combined output(s)[/green]")
```

### CLI Usage Examples

```bash
# Basic concatenation
acm2 combine run --run-id 123

# Best-of-N with coherence metric
acm2 combine run -r 123 -s best_of_n --metric coherence

# Best-of-N with minimum threshold
acm2 combine run -r 123 -s best_of_n --metric aggregate --min-score 0.7

# Section assembly with order
acm2 combine run -r 123 -s section_assembly --section-order "intro,methods,results,discussion"

# Concatenate with TOC and custom separator
acm2 combine run -r 123 --toc --separator "\n\n## ---\n\n"

# Intelligent merge with GPT-4
acm2 combine run -r 123 -s intelligent_merge --merge-model gpt-4o

# Save output to file
acm2 combine run -r 123 -o report.md

# View existing combined output
acm2 combine show -r 123

# View sources only
acm2 combine show -r 123 --sources

# View combine history
acm2 combine history -r 123

# Clear and re-combine
acm2 combine clear -r 123
acm2 combine run -r 123 -s best_of_n
```

---

## 16. Configuration

Default combine settings and override patterns.

### Global Configuration

```yaml
# acm2_config.yaml

combine:
  # Default strategy when not specified
  default_strategy: concatenate
  
  # Auto-trigger combine after evaluation
  auto_combine: false
  
  # Common defaults
  include_toc: false
  include_sources: true
  
  # Strategy-specific defaults
  concatenate:
    separator: "\n\n---\n\n"
  
  best_of_n:
    selection_metric: aggregate
    tie_breaker: first
    minimum_score: null  # No threshold by default
  
  section_assembly:
    missing_section_behavior: error
  
  intelligent_merge:
    model: gpt-4o-mini
    max_tokens: 8000
    default_prompt: null  # Use built-in prompt
```

### Loading Configuration

```python
# acm2/config/combine_config.py

from typing import Optional
from pydantic import BaseModel
import yaml


class ConcatenateDefaults(BaseModel):
    separator: str = "\n\n---\n\n"


class BestOfNDefaults(BaseModel):
    selection_metric: str = "aggregate"
    tie_breaker: str = "first"
    minimum_score: Optional[float] = None


class SectionAssemblyDefaults(BaseModel):
    missing_section_behavior: str = "error"


class IntelligentMergeDefaults(BaseModel):
    model: str = "gpt-4o-mini"
    max_tokens: int = 8000
    default_prompt: Optional[str] = None


class CombineDefaults(BaseModel):
    default_strategy: str = "concatenate"
    auto_combine: bool = False
    include_toc: bool = False
    include_sources: bool = True
    concatenate: ConcatenateDefaults = ConcatenateDefaults()
    best_of_n: BestOfNDefaults = BestOfNDefaults()
    section_assembly: SectionAssemblyDefaults = SectionAssemblyDefaults()
    intelligent_merge: IntelligentMergeDefaults = IntelligentMergeDefaults()


def load_combine_config(config_path: str = "acm2_config.yaml") -> CombineDefaults:
    """Load combine configuration from YAML file."""
    try:
        with open(config_path, "r") as f:
            data = yaml.safe_load(f)
        combine_data = data.get("combine", {})
        return CombineDefaults(**combine_data)
    except FileNotFoundError:
        return CombineDefaults()
```

### Per-Run Configuration

```python
# Run-level override in run config
run_config = RunConfig(
    # ... other config ...
    combine=CombineConfig(
        strategy=CombineStrategy.BEST_OF_N,
        selection_metric="coherence",
        minimum_score=0.7,
    ),
)

# Create run with combine config
run = await acm2.create_run(
    name="Research Report",
    config=run_config,
)
```

### Configuration Precedence

```
1. Explicit API/CLI parameters (highest priority)
2. Per-run configuration
3. Global config file (acm2_config.yaml)
4. Built-in defaults (lowest priority)
```

```python
# acm2/combiners/service.py

class CombinerService:
    def __init__(self, db: Database, config: CombineDefaults = None):
        self.db = db
        self.defaults = config or load_combine_config()
    
    def _resolve_config(
        self,
        explicit_config: Optional[CombineConfig],
        run: Run,
    ) -> CombineConfig:
        """Resolve final config with precedence."""
        # Start with defaults
        final = CombineConfig(
            strategy=CombineStrategy(self.defaults.default_strategy),
            include_toc=self.defaults.include_toc,
            include_sources=self.defaults.include_sources,
        )
        
        # Apply strategy-specific defaults
        if final.strategy == CombineStrategy.CONCATENATE:
            final.separator = self.defaults.concatenate.separator
        elif final.strategy == CombineStrategy.BEST_OF_N:
            final.selection_metric = self.defaults.best_of_n.selection_metric
            final.tie_breaker = TieBreaker(self.defaults.best_of_n.tie_breaker)
        # ... etc
        
        # Override with run config
        if run.config.combine:
            final = final.copy(update=run.config.combine.dict(exclude_unset=True))
        
        # Override with explicit config
        if explicit_config:
            final = final.copy(update=explicit_config.dict(exclude_unset=True))
        
        return final
```

### Environment Variables

```bash
# Override default strategy
export ACM2_COMBINE_DEFAULT_STRATEGY=best_of_n

# Override intelligent merge model
export ACM2_COMBINE_MERGE_MODEL=gpt-4o

# Enable auto-combine
export ACM2_COMBINE_AUTO=true
```

```python
import os

class CombineDefaults(BaseModel):
    @classmethod
    def from_env(cls) -> "CombineDefaults":
        """Create defaults with environment overrides."""
        defaults = cls()
        
        if strategy := os.getenv("ACM2_COMBINE_DEFAULT_STRATEGY"):
            defaults.default_strategy = strategy
        
        if model := os.getenv("ACM2_COMBINE_MERGE_MODEL"):
            defaults.intelligent_merge.model = model
        
        if auto := os.getenv("ACM2_COMBINE_AUTO"):
            defaults.auto_combine = auto.lower() in ("true", "1", "yes")
        
        return defaults
```

---

## 17. Testing Strategy

Comprehensive testing for combine functionality.

### Unit Tests

```python
# tests/test_combiners/test_concatenate.py

import pytest
from acm2.combiners.concatenate import ConcatenateCombiner
from acm2.schemas.combine import CombineConfig, CombineStrategy
from tests.factories import ArtifactFactory


class TestConcatenateCombiner:
    @pytest.fixture
    def combiner(self):
        return ConcatenateCombiner()
    
    @pytest.fixture
    def sample_artifacts(self):
        return [
            ArtifactFactory.create(content="# Section A\n\nContent A"),
            ArtifactFactory.create(content="# Section B\n\nContent B"),
            ArtifactFactory.create(content="# Section C\n\nContent C"),
        ]
    
    @pytest.mark.asyncio
    async def test_basic_concatenation(self, combiner, sample_artifacts):
        """Test basic artifact concatenation."""
        config = CombineConfig(strategy=CombineStrategy.CONCATENATE)
        
        result = await combiner.combine(sample_artifacts, config)
        
        assert result.success
        assert "Section A" in result.combined_content
        assert "Section B" in result.combined_content
        assert "Section C" in result.combined_content
        assert len(result.source_artifacts) == 3
    
    @pytest.mark.asyncio
    async def test_custom_separator(self, combiner, sample_artifacts):
        """Test custom separator between artifacts."""
        config = CombineConfig(
            strategy=CombineStrategy.CONCATENATE,
            separator="\n\n***\n\n",
        )
        
        result = await combiner.combine(sample_artifacts, config)
        
        assert "***" in result.combined_content
        assert result.combined_content.count("***") == 2  # Between 3 artifacts
    
    @pytest.mark.asyncio
    async def test_custom_order(self, combiner, sample_artifacts):
        """Test custom artifact ordering."""
        config = CombineConfig(
            strategy=CombineStrategy.CONCATENATE,
            artifact_order=[sample_artifacts[2].id, sample_artifacts[0].id],
        )
        
        result = await combiner.combine(sample_artifacts, config)
        
        # Section C should appear before Section A
        assert result.combined_content.index("Section C") < result.combined_content.index("Section A")
    
    @pytest.mark.asyncio
    async def test_toc_generation(self, combiner, sample_artifacts):
        """Test table of contents generation."""
        config = CombineConfig(
            strategy=CombineStrategy.CONCATENATE,
            include_toc=True,
        )
        
        result = await combiner.combine(sample_artifacts, config)
        
        assert "Table of Contents" in result.combined_content
        assert "[Section A]" in result.combined_content
    
    @pytest.mark.asyncio
    async def test_empty_artifacts(self, combiner):
        """Test handling of empty artifact list."""
        config = CombineConfig(strategy=CombineStrategy.CONCATENATE)
        
        result = await combiner.combine([], config)
        
        assert result.combined_content == ""
        assert len(result.source_artifacts) == 0
```

```python
# tests/test_combiners/test_best_of_n.py

import pytest
from acm2.combiners.best_of_n import BestOfNCombiner
from acm2.schemas.combine import CombineConfig, CombineStrategy, TieBreaker
from tests.factories import ArtifactFactory


class TestBestOfNCombiner:
    @pytest.fixture
    def combiner(self):
        return BestOfNCombiner()
    
    @pytest.fixture
    def scored_artifacts(self):
        return [
            ArtifactFactory.create(
                content="Low quality",
                evaluation={"aggregate_score": 0.5, "scores": {"coherence": 0.4}},
            ),
            ArtifactFactory.create(
                content="High quality",
                evaluation={"aggregate_score": 0.9, "scores": {"coherence": 0.95}},
            ),
            ArtifactFactory.create(
                content="Medium quality",
                evaluation={"aggregate_score": 0.7, "scores": {"coherence": 0.6}},
            ),
        ]
    
    @pytest.mark.asyncio
    async def test_selects_highest_aggregate(self, combiner, scored_artifacts):
        """Test selection by highest aggregate score."""
        config = CombineConfig(
            strategy=CombineStrategy.BEST_OF_N,
            selection_metric="aggregate",
        )
        
        result = await combiner.combine(scored_artifacts, config)
        
        assert result.success
        assert "High quality" in result.combined_content
        assert len(result.source_artifacts) == 1
    
    @pytest.mark.asyncio
    async def test_selects_by_specific_metric(self, combiner, scored_artifacts):
        """Test selection by specific metric."""
        config = CombineConfig(
            strategy=CombineStrategy.BEST_OF_N,
            selection_metric="coherence",
        )
        
        result = await combiner.combine(scored_artifacts, config)
        
        assert "High quality" in result.combined_content  # Highest coherence
    
    @pytest.mark.asyncio
    async def test_minimum_score_threshold(self, combiner):
        """Test minimum score rejection."""
        artifacts = [
            ArtifactFactory.create(
                content="Below threshold",
                evaluation={"aggregate_score": 0.3},
            ),
        ]
        
        config = CombineConfig(
            strategy=CombineStrategy.BEST_OF_N,
            minimum_score=0.5,
        )
        
        result = await combiner.combine(artifacts, config)
        
        assert not result.success
        assert "below" in result.error_message.lower()
    
    @pytest.mark.asyncio
    async def test_tie_breaker_shortest(self, combiner):
        """Test tie-breaking with shortest content."""
        artifacts = [
            ArtifactFactory.create(
                content="This is a longer piece of content",
                evaluation={"aggregate_score": 0.8},
            ),
            ArtifactFactory.create(
                content="Short",
                evaluation={"aggregate_score": 0.8},
            ),
        ]
        
        config = CombineConfig(
            strategy=CombineStrategy.BEST_OF_N,
            tie_breaker=TieBreaker.SHORTEST,
        )
        
        result = await combiner.combine(artifacts, config)
        
        assert result.combined_content == "Short"
```

### Integration Tests

```python
# tests/test_combiners/test_integration.py

import pytest
from acm2.combiners import CombinerService
from acm2.database import Database
from acm2.schemas.combine import CombineConfig, CombineStrategy


class TestCombineIntegration:
    @pytest.fixture
    async def db(self):
        db = Database(":memory:")
        await db.connect()
        await db.run_migrations()
        yield db
        await db.close()
    
    @pytest.fixture
    async def run_with_artifacts(self, db):
        """Create a run with evaluated artifacts."""
        # Create run
        run_id = await db.create_run(name="Test Run")
        
        # Add documents
        for i in range(3):
            doc_id = await db.add_document(run_id, f"doc{i}.md", f"Content {i}")
            
            # Create artifact with evaluation
            await db.create_artifact(
                run_id=run_id,
                document_id=doc_id,
                content=f"# Document {i}\n\nGenerated content {i}",
                evaluation={"aggregate_score": 0.7 + i * 0.1},
            )
        
        return run_id
    
    @pytest.mark.asyncio
    async def test_full_combine_flow(self, db, run_with_artifacts):
        """Test complete combine workflow."""
        service = CombinerService(db)
        
        # Run combine
        result = await service.combine(
            run_with_artifacts,
            CombineConfig(strategy=CombineStrategy.CONCATENATE),
        )
        
        assert result.success
        assert "Document 0" in result.combined_content
        assert "Document 1" in result.combined_content
        assert "Document 2" in result.combined_content
        
        # Verify saved to database
        saved = await service.get_combined(run_with_artifacts)
        assert saved is not None
        assert saved.combined_content == result.combined_content
    
    @pytest.mark.asyncio
    async def test_combine_history(self, db, run_with_artifacts):
        """Test multiple combine operations are tracked."""
        service = CombinerService(db)
        
        # Run multiple combines with different strategies
        await service.combine(
            run_with_artifacts,
            CombineConfig(strategy=CombineStrategy.CONCATENATE),
        )
        await service.combine(
            run_with_artifacts,
            CombineConfig(strategy=CombineStrategy.BEST_OF_N),
        )
        
        # Get history
        history = await service.get_all_combined(run_with_artifacts)
        
        assert len(history) == 2
        strategies = [r.strategy_used for r in history]
        assert CombineStrategy.CONCATENATE in strategies
        assert CombineStrategy.BEST_OF_N in strategies
```

### Test Fixtures

```python
# tests/factories.py

from typing import Optional, Dict, Any
from acm2.schemas.artifact import Artifact
from acm2.schemas.document import Document


class ArtifactFactory:
    _id_counter = 0
    
    @classmethod
    def create(
        cls,
        content: str,
        evaluation: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Artifact:
        cls._id_counter += 1
        return Artifact(
            id=cls._id_counter,
            run_id=1,
            document_id=cls._id_counter,
            content=content,
            evaluation=evaluation or {},
            metadata=metadata or {},
            document=Document(
                id=cls._id_counter,
                run_id=1,
                filename=f"doc{cls._id_counter}.md",
            ),
        )
```

### Test Coverage Targets

| Component | Target Coverage |
|-----------|----------------|
| ConcatenateCombiner | 95% |
| BestOfNCombiner | 95% |
| SectionAssemblyCombiner | 90% |
| IntelligentMergeCombiner | 85% |
| SourceHandler | 90% |
| CombinerService | 90% |
| CombinedOutputRepository | 90% |
| API endpoints | 85% |
| CLI commands | 80% |

---

## 18. Out of Scope

Features explicitly not included in this specification.

### Not Included

| Feature | Reason | Alternative |
|---------|--------|-------------|
| **Real-time collaborative editing** | Complexity, requires WebSocket infrastructure | Export and use external tools |
| **Version control/diff tracking** | Complex state management | Use history feature + external git |
| **External document management** | Integration scope too broad | Export to external systems |
| **PDF generation** | Rendering complexity | Use pandoc or similar post-processing |
| **Multi-format output** | Beyond core scope | Post-process markdown output |
| **Weighted blend strategy** | Deferred to future iteration | Use intelligent_merge as alternative |
| **Interactive merge UI** | GUI feature, not core | CLI/API sufficient for v1 |
| **Merge conflict resolution** | Section assembly handles this simply | Use section_assembly or intelligent_merge |
| **Streaming combine output** | Low priority for batch operation | Polling for progress |
| **Combine undo/rollback** | History provides audit trail | Re-run combine with different config |

### Future Considerations

**Potential v2 Features:**
- Weighted blend strategy (combine by paragraph/section weights)
- Interactive section reordering UI
- Combine templates for common document structures
- Source quality weighting in intelligent merge
- Automatic format detection and normalization
- Multi-language content handling

**Integration Points for Future:**
```python
# These hooks exist but are not fully implemented
class CombinerBase:
    # Hook for pre-processing
    async def pre_combine(self, artifacts: List[Artifact]) -> List[Artifact]:
        return artifacts  # Override in subclass
    
    # Hook for post-processing
    async def post_combine(self, result: CombineResult) -> CombineResult:
        return result  # Override in subclass
```

### Deferred Design Decisions

1. **Re-evaluation after combine**: Should combined output be scored?
   - Decision: Not in v1, user can manually trigger evaluation on combined content

2. **Automatic combine trigger**: When should combine auto-run?
   - Decision: Manual trigger by default, optional auto via config

3. **Incompatible format handling**: What if artifacts have different formats?
   - Decision: Assume all markdown for v1, log warnings for others

---

## Open Questions

1. ~~Should combine be automatic after evaluation or manual trigger?~~
   - **Resolved**: Manual by default, `auto_combine: true` in config enables automatic

2. ~~How to handle artifacts with incompatible formats?~~
   - **Resolved**: Assume markdown, log warnings, defer multi-format to v2

3. ~~Should combined output be re-evaluated?~~
   - **Resolved**: Not automatically; user can trigger evaluation on combined content if needed

