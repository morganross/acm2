# Implementation Plan: Per-Document Pipeline + Results UI

## Problem Statement

### Current Behavior (Wrong)
All input documents are pooled together:
- Generation creates variations from ALL input docs
- ONE pairwise tournament compares everything
- ONE global winner emerges
- ONE combined output

### Correct Behavior
Each input document is an independent pipeline:
- Each doc generates its own variations
- Each doc's variations compete only against each other
- Each doc produces its own winner
- Each doc produces its own combined output

### Execution Model
Pipelined concurrency with shared API slots:
```
Doc 1: [Gen][Gen][Gen][Gen][Eval][Eval][Pairwise][Combine] → Output 1
Doc 2:           [Gen][Gen][Gen][Gen][Eval][Eval][Pairwise][Combine] → Output 2
Doc 3:                     [Gen][Gen][Gen][Gen][Eval][Eval][Pairwise][Combine] → Output 3
```
- Phases are serial within a document
- API calls are concurrent across documents (shared semaphore)
- No cross-contamination between document results

---

## Phase 1: Data Model Changes

### 1.1 Update `RunResult` dataclass (run_executor.py)

**Current:**
```python
winner_doc_id: Optional[str]
combined_docs: List[GeneratedDocument]
single_eval_results: Optional[Dict[str, SingleEvalSummary]]
pairwise_results: Optional[PairwiseSummary]
```

**New:**
```python
class RunPhase(str, Enum):
    """Add new status for partial success."""
    PENDING = "pending"
    GENERATING = "generating"
    SINGLE_EVAL = "single_eval"
    PAIRWISE_EVAL = "pairwise_eval"
    COMBINING = "combining"
    POST_COMBINE_EVAL = "post_combine_eval"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"  # NEW: Some docs failed
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class SourceDocResult:
    source_doc_id: str
    source_doc_name: str
    generated_docs: List[GeneratedDocument]
    single_eval_results: Dict[str, SingleEvalSummary]
    pairwise_results: Optional[PairwiseSummary]
    winner_doc_id: Optional[str]
    combined_doc: Optional[GeneratedDocument]
    post_combine_eval: Optional[PairwiseSummary]
    timeline_events: List[dict]
    errors: List[str]
    status: RunPhase  # Per-document status

@dataclass
class RunResult:
    run_id: str
    status: RunPhase  # Overall run status
    source_doc_results: Dict[str, SourceDocResult]  # keyed by source_doc_id
    total_cost_usd: float
    duration_seconds: float
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    errors: List[str]  # Run-level errors
    fpf_stats: Optional[Dict[str, Any]]
```

### 1.2 Update database schema for results storage

- Modify `results_summary` JSON column structure to store per-document results
- Structure: `{ "source_documents": { "doc-001": {...}, "doc-002": {...} }, "totals": {...} }`
- Add migration script if needed for existing runs

---

## Phase 2: Executor Refactor

### 2.1 New orchestration model in `execute()` method

```python
async def execute(self, run_id: str, config: RunConfig) -> RunResult:
    # Create result container
    result = RunResult(run_id=run_id, source_doc_results={}, ...)
    
    # Create pipeline for each source document
    pipelines = []
    for doc_id in config.document_ids:
        pipeline = SourceDocPipeline(
            source_doc_id=doc_id,
            content=config.document_contents[doc_id],
            config=config,
            shared_semaphore=self._api_semaphore,
            stats_tracker=self._fpf_stats,
        )
        pipelines.append(pipeline)
    
    # Run all pipelines concurrently
    # They share the semaphore, so API calls are rate-limited globally
    pipeline_results = await asyncio.gather(
        *[p.run() for p in pipelines],
        return_exceptions=True
    )
    
    # Collect results
    for doc_id, pipe_result in zip(config.document_ids, pipeline_results):
        if isinstance(pipe_result, Exception):
            result.source_doc_results[doc_id] = SourceDocResult(
                source_doc_id=doc_id,
                status=RunPhase.FAILED,
                errors=[str(pipe_result)],
                ...
            )
        else:
            result.source_doc_results[doc_id] = pipe_result
    
    return result
```

### 2.2 Create `SourceDocPipeline` class (new)

```python
class SourceDocPipeline:
    """Executes the full pipeline for a single source document."""
    
    def __init__(
        self,
        source_doc_id: str,
        source_doc_name: str,
        content: str,
        config: RunConfig,
        shared_semaphore: asyncio.Semaphore,
        stats_tracker: FpfStatsTracker,
        logger: logging.Logger,
    ):
        self.source_doc_id = source_doc_id
        self.source_doc_name = source_doc_name
        self.content = content
        self.config = config
        self.semaphore = shared_semaphore
        self.stats = stats_tracker
        self.logger = logger
        
    async def run(self) -> SourceDocResult:
        result = SourceDocResult(
            source_doc_id=self.source_doc_id,
            source_doc_name=self.source_doc_name,
            generated_docs=[],
            single_eval_results={},
            pairwise_results=None,
            winner_doc_id=None,
            combined_doc=None,
            timeline_events=[],
            errors=[],
            status=RunPhase.GENERATING,
        )
        
        try:
            # Phase 1: Generate + Single Eval (streaming)
            await self._run_generation_with_eval(result)
            
            # Phase 2: Pairwise (batch, after all generation)
            if self.config.enable_pairwise and len(result.generated_docs) >= 2:
                result.status = RunPhase.PAIRWISE_EVAL
                await self._run_pairwise(result)
            
            # Phase 3: Combine
            if self.config.enable_combine and result.winner_doc_id:
                result.status = RunPhase.COMBINING
                await self._run_combine(result)
            
            # Phase 4: Post-combine eval
            if self.config.enable_combine and result.combined_doc:
                result.status = RunPhase.POST_COMBINE_EVAL
                await self._run_post_combine_eval(result)
            
            result.status = RunPhase.COMPLETED
            
        except Exception as e:
            result.status = RunPhase.FAILED
            result.errors.append(str(e))
            
        return result
    
    async def _run_generation_with_eval(self, result: SourceDocResult):
        """Generate variations for THIS source doc only."""
        tasks = []
        for generator in self.config.generators:
            models = self.config.get_models_for_generator(generator)
            for model in models:
                for iteration in range(1, self.config.iterations + 1):
                    tasks.append((generator, model, iteration))
        
        async def process_task(task_info):
            generator, model, iteration = task_info
            async with self.semaphore:  # Shared across all pipelines
                gen_result = await self._generate_single(generator, model, iteration)
                if gen_result:
                    result.generated_docs.append(gen_result)
                    # Single eval immediately
                    if self.config.enable_single_eval:
                        eval_result = await self._single_eval(gen_result)
                        result.single_eval_results[gen_result.doc_id] = eval_result
        
        await asyncio.gather(*[process_task(t) for t in tasks])
    
    async def _run_pairwise(self, result: SourceDocResult):
        """Pairwise tournament for THIS source doc's variations only."""
        # Only compare docs generated from this source doc
        docs_to_compare = result.generated_docs
        # Run tournament...
        result.pairwise_results = await self._pairwise_tournament(docs_to_compare)
        result.winner_doc_id = result.pairwise_results.winner_id
    
    async def _run_combine(self, result: SourceDocResult):
        """Combine winner for THIS source doc."""
        winner_doc = next(d for d in result.generated_docs if d.doc_id == result.winner_doc_id)
        result.combined_doc = await self._combine(winner_doc)
```

### 2.3 Update existing methods

- `_run_generation_with_eval()` - Extract core logic, use in SourceDocPipeline
- `_run_pairwise()` - Extract core logic, use in SourceDocPipeline
- `_run_combine()` - Extract core logic, use in SourceDocPipeline
- Keep existing methods as wrappers for backward compatibility during transition

### 2.4 Update timeline events

- Include `source_doc_id` in each event
- Frontend can filter events by source doc

```python
await self._emit_timeline_event(
    run_id=run_id,
    source_doc_id=source_doc_id,  # NEW
    phase="generation",
    event_type="generation",
    ...
)
```

---

## Phase 3: API Response Changes

### 3.1 Update run detail endpoint response

**New response structure:**
```json
{
  "id": "run-123",
  "status": "completed",
  "source_documents": [
    {
      "source_doc_id": "doc-001",
      "source_doc_name": "contract.md",
      "status": "completed",
      "generated_docs": [
        {"doc_id": "doc-001.fpf.1.gpt-4", "content": "...", "model": "gpt-4", ...}
      ],
      "single_eval_results": {
        "doc-001.fpf.1.gpt-4": {"avg_score": 8.5, "results": [...]}
      },
      "pairwise_results": {
        "rankings": [...],
        "winner_id": "doc-001.fpf.1.gpt-4"
      },
      "winner_doc_id": "doc-001.fpf.1.gpt-4",
      "combined_output": {...},
      "timeline_events": [...],
      "errors": []
    },
    {
      "source_doc_id": "doc-002",
      "source_doc_name": "proposal.md",
      ...
    }
  ],
  "total_cost_usd": 1.23,
  "duration_seconds": 45.2,
  "errors": []
}
```

### 3.2 Update repository save/load

- `run_repo.complete()` stores new structure in `results_summary`
- `run_repo.get_by_id()` returns new structure

### 3.3 Update artifacts endpoint

- Support fetching by source_doc_id
- `GET /runs/{id}/artifacts?source_doc_id=doc-001`
- `GET /runs/{id}/artifacts/{doc_id}` still works for specific generated doc

---

## Phase 4: Frontend - Results Page Refactor

### 4.1 Update type definitions (ui/src/types/run.ts)

```typescript
interface SourceDocResult {
  source_doc_id: string;
  source_doc_name: string;
  status: string;
  generated_docs: GeneratedDoc[];
  single_eval_results: Record<string, SingleEvalSummary>;
  pairwise_results: PairwiseSummary | null;
  winner_doc_id: string | null;
  combined_output: GeneratedDoc | null;
  timeline_events: TimelineEvent[];
  errors: string[];
}

interface RunDetail {
  id: string;
  status: string;
  source_documents: SourceDocResult[];
  total_cost_usd: number;
  duration_seconds: number;
  errors: string[];
}
```

### 4.2 Update RunDetail page structure

**Current:**
```
RunDetail
├── Tabs (Timeline | Single Eval | Pairwise)
└── Tab content
```

**New:**
```
RunDetail
├── Run Summary (status, cost, duration, errors)
├── Source Document Sections (map over source_documents)
│   └── SourceDocSection (collapsible)
│       ├── Header: "📄 contract.md" [status badge] [expand/collapse]
│       └── Content (when expanded):
│           ├── Tabs (Timeline | Single Eval | Pairwise | Output)
│           └── Tab content for this source doc
```

### 4.3 Create `SourceDocSection` component (new file)

```tsx
// ui/src/components/runs/SourceDocSection.tsx

interface SourceDocSectionProps {
  sourceDoc: SourceDocResult;
  runId: string;
  defaultExpanded?: boolean;
}

export function SourceDocSection({ 
  sourceDoc, 
  runId,
  defaultExpanded = false 
}: SourceDocSectionProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [activeTab, setActiveTab] = useState('timeline');
  
  return (
    <div className="border rounded-lg mb-4 overflow-hidden">
      {/* Header - always visible */}
      <button 
        onClick={() => setExpanded(!expanded)}
        className="w-full p-4 flex items-center justify-between bg-gray-50 hover:bg-gray-100"
      >
        <div className="flex items-center gap-2">
          <span>{expanded ? '▼' : '►'}</span>
          <span className="font-medium">📄 {sourceDoc.source_doc_name}</span>
          <StatusBadge status={sourceDoc.status} />
        </div>
        <div className="text-sm text-gray-500">
          {sourceDoc.generated_docs.length} variations
        </div>
      </button>
      
      {/* Content - only when expanded */}
      {expanded && (
        <div className="p-4">
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList>
              <TabsTrigger value="timeline">Timeline</TabsTrigger>
              <TabsTrigger value="single">Single Eval</TabsTrigger>
              <TabsTrigger value="pairwise">Pairwise</TabsTrigger>
              <TabsTrigger value="output">Output</TabsTrigger>
            </TabsList>
            
            <TabsContent value="timeline">
              <Timeline events={sourceDoc.timeline_events} />
            </TabsContent>
            
            <TabsContent value="single">
              <SingleEvalHeatmap 
                results={sourceDoc.single_eval_results}
                generatedDocs={sourceDoc.generated_docs}
              />
            </TabsContent>
            
            <TabsContent value="pairwise">
              {sourceDoc.pairwise_results ? (
                <PairwiseHeatmap results={sourceDoc.pairwise_results} />
              ) : (
                <p>Pairwise evaluation not run</p>
              )}
            </TabsContent>
            
            <TabsContent value="output">
              <OutputViewer 
                winner={sourceDoc.winner_doc_id}
                combined={sourceDoc.combined_output}
                generatedDocs={sourceDoc.generated_docs}
              />
            </TabsContent>
          </Tabs>
        </div>
      )}
    </div>
  );
}
```

### 4.4 Update RunDetail page

```tsx
// ui/src/pages/RunDetail.tsx

export function RunDetail() {
  const { runId } = useParams();
  const { data: run, isLoading } = useRun(runId);
  
  if (isLoading) return <Loading />;
  if (!run) return <NotFound />;
  
  // For single-doc runs (backward compat), expand by default
  const defaultExpanded = run.source_documents.length === 1;
  
  return (
    <div className="container mx-auto p-6">
      {/* Run Summary */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Run {run.id.slice(0, 8)}</h1>
        <div className="flex gap-4 mt-2">
          <StatusBadge status={run.status} />
          <span>Cost: ${run.total_cost_usd.toFixed(4)}</span>
          <span>Duration: {run.duration_seconds.toFixed(1)}s</span>
        </div>
        {run.errors.length > 0 && (
          <div className="mt-2 text-red-500">
            {run.errors.map((e, i) => <p key={i}>{e}</p>)}
          </div>
        )}
      </div>
      
      {/* Source Document Sections */}
      <div className="space-y-4">
        {run.source_documents.map((sourceDoc, index) => (
          <SourceDocSection
            key={sourceDoc.source_doc_id}
            sourceDoc={sourceDoc}
            runId={run.id}
            defaultExpanded={defaultExpanded || index === 0}
          />
        ))}
      </div>
    </div>
  );
}
```

### 4.5 Update data fetching

- Update `useRun()` hook to handle new response structure
- Add backward compatibility for old runs

---

## Phase 5: Backward Compatibility & Migration

### 5.1 Existing runs

Old runs stored with flat structure need to be displayed correctly:

```typescript
// In data fetching layer
function normalizeRunData(raw: any): RunDetail {
  // If old format (no source_documents), convert
  if (!raw.source_documents && raw.generated_docs) {
    return {
      ...raw,
      source_documents: [{
        source_doc_id: 'legacy',
        source_doc_name: 'Document',
        generated_docs: raw.generated_docs,
        single_eval_results: raw.single_eval_results || {},
        pairwise_results: raw.pairwise_results,
        winner_doc_id: raw.winner_doc_id,
        combined_output: raw.combined_docs?.[0] || null,
        timeline_events: raw.timeline_events || [],
        errors: [],
        status: raw.status,
      }]
    };
  }
  return raw;
}
```

### 5.2 Database migration

- No schema change needed (results_summary is JSON)
- Old runs continue to work via normalization layer

---

## Phase 6: Testing

### 6.1 Unit tests

- `SourceDocPipeline` class
- Result aggregation logic
- Backward compatibility normalization

### 6.2 Integration tests

- Single document run (regression)
- Multiple document run (new)
- Mixed success/failure (some docs fail)
- Cancellation mid-run

### 6.3 UI tests

- Collapse/expand behavior
- Tab state per section
- Correct data isolation
- Backward compat with old runs

---

## File Changes Summary

| File | Change Type | Complexity |
|------|-------------|------------|
| `app/services/run_executor.py` | Major refactor | High |
| `app/services/source_doc_pipeline.py` | New file | High |
| `app/models/run.py` or `app/schemas/` | Add types | Low |
| `app/api/routes/runs/crud.py` | Update response | Medium |
| `app/api/routes/presets.py` | Update result handling | Medium |
| `app/infra/db/repositories/run.py` | Update storage | Medium |
| `ui/src/types/run.ts` | Add types | Low |
| `ui/src/pages/RunDetail.tsx` | Major refactor | Medium |
| `ui/src/components/runs/SourceDocSection.tsx` | New file | Medium |
| `ui/src/hooks/useRun.ts` | Add normalization | Low |

---

## Estimated Effort

| Phase | Complexity | Estimate |
|-------|------------|----------|
| Phase 1: Data Models | Medium | 2-3 hours |
| Phase 2: Executor Refactor | High | 8-10 hours |
| Phase 3: API Changes | Medium | 2-3 hours |
| Phase 4: Frontend | Medium-High | 5-7 hours |
| Phase 5: Backward Compat | Low | 1-2 hours |
| Phase 6: Testing | Medium | 4-5 hours |
| **Total** | | **22-30 hours** |

---

## Implementation Order

1. **Phase 1** - Data models first (foundation)
2. **Phase 2** - Executor refactor (core logic)
3. **Phase 3** - API changes (connect backend to frontend)
4. **Phase 4** - Frontend (user-visible changes)
5. **Phase 5** - Backward compat (polish)
6. **Phase 6** - Testing (throughout, but formalize at end)

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Breaking existing runs | Normalization layer for old data |
| Performance with many docs | Shared semaphore already limits concurrency |
| Complex state management | Each pipeline is isolated, reduces coupling |
| WebSocket updates | Include source_doc_id in events for filtering |
---

## Additional Design Considerations

### A. Semaphore Scope: ALL API Calls

The shared semaphore must wrap ALL LLM API calls, not just generation:

```python
# Generation
async with self.semaphore:
    gen_result = await self._generate_single(...)

# Single eval
async with self.semaphore:
    eval_result = await self._single_eval(...)

# Pairwise comparisons
async with self.semaphore:
    comparison = await self._pairwise_compare(...)

# Combine
async with self.semaphore:
    combined = await self._combine(...)
```

This ensures global rate limiting across all phases and all pipelines.

---

### B. Per-Document Progress & WebSocket Updates

Each pipeline emits progress events with `source_doc_id`:

```python
await self._emit_progress_event(
    run_id=run_id,
    source_doc_id=self.source_doc_id,  # Include source context
    phase="generation",
    progress=0.5,
    message="Generated 4/8 variations",
)
```

**Frontend handling:**
- Subscribe to run-level WebSocket
- Filter events by `source_doc_id` for per-section updates
- Show individual progress bars per collapsible section

**WebSocket payload:**
```json
{
  "event": "progress",
  "source_doc_id": "doc-001",
  "phase": "generation",
  "progress": 0.5,
  "message": "Generated 4/8 variations"
}
```

---

### C. Error Isolation Between Documents

Each pipeline is isolated. One doc failing doesn't stop others:

```python
pipeline_results = await asyncio.gather(
    *[p.run() for p in pipelines],
    return_exceptions=True  # Critical: don't fail-fast
)
```

**Run status logic:**
```python
def determine_run_status(results: List[SourceDocResult]) -> RunPhase:
    statuses = [r.status for r in results]
    
    if all(s == RunPhase.COMPLETED for s in statuses):
        return RunPhase.COMPLETED
    elif all(s == RunPhase.FAILED for s in statuses):
        return RunPhase.FAILED
    elif all(s == RunPhase.CANCELLED for s in statuses):
        return RunPhase.CANCELLED
    elif any(s == RunPhase.FAILED for s in statuses):
        return RunPhase.COMPLETED_WITH_ERRORS  # New status
    else:
        return RunPhase.COMPLETED
```

**UI display:**
- Run-level shows overall status
- Each section shows its own status badge
- Failed sections show error details, successful sections show results

---

### D. Document Name Resolution

Capture human-readable names when loading documents:

```python
# In execute_preset or config building
for doc_ref in preset.documents:
    doc = await doc_repo.get_by_id(doc_ref)
    if doc:
        source_doc_name = doc.name or doc.filename or doc_ref
    else:
        content_item = await content_repo.get_by_id(doc_ref)
        source_doc_name = content_item.name if content_item else doc_ref
    
    document_names[doc_ref] = source_doc_name
```

Pass `document_names` dict to config, use in pipeline initialization.

---

### E. Cancel Handling Per Pipeline

Each pipeline checks for cancellation:

```python
class SourceDocPipeline:
    def __init__(self, ..., cancel_event: asyncio.Event):
        self.cancel_event = cancel_event
    
    async def _run_generation_with_eval(self, result):
        for task_info in tasks:
            if self.cancel_event.is_set():
                result.status = RunPhase.CANCELLED
                return
            
            async with self.semaphore:
                if self.cancel_event.is_set():
                    result.status = RunPhase.CANCELLED
                    return
                # ... do work
```

**Shared cancel event:**
```python
# In RunExecutor.execute()
self._cancel_event = asyncio.Event()

# Each pipeline gets reference
for doc_id in config.document_ids:
    pipeline = SourceDocPipeline(..., cancel_event=self._cancel_event)
```

Already-completed pipelines keep their results. In-progress pipelines stop gracefully.

---

### F. Run-Level Overview Section

Add a "Run Overview" above per-doc sections:

```tsx
// In RunDetail page
<div className="mb-6 p-4 bg-gray-50 rounded-lg">
  <h2 className="font-semibold mb-2">Run Overview</h2>
  <div className="grid grid-cols-4 gap-4 text-sm">
    <div>
      <span className="text-gray-500">Status:</span>
      <StatusBadge status={run.status} />
    </div>
    <div>
      <span className="text-gray-500">Documents:</span>
      {run.source_documents.filter(d => d.status === 'completed').length} / {run.source_documents.length} completed
    </div>
    <div>
      <span className="text-gray-500">Total Cost:</span>
      ${run.total_cost_usd.toFixed(4)}
    </div>
    <div>
      <span className="text-gray-500">Duration:</span>
      {run.duration_seconds.toFixed(1)}s
    </div>
  </div>
  {run.errors.length > 0 && (
    <div className="mt-2 text-red-500 text-sm">
      <strong>Run-level errors:</strong>
      {run.errors.map((e, i) => <p key={i}>{e}</p>)}
    </div>
  )}
</div>
```

---

### G. Expand/Collapse State Persistence

Use localStorage to remember which sections are expanded:

```tsx
function SourceDocSection({ sourceDoc, runId, defaultExpanded }) {
  const storageKey = `run-${runId}-${sourceDoc.source_doc_id}-expanded`;
  
  const [expanded, setExpanded] = useState(() => {
    const stored = localStorage.getItem(storageKey);
    return stored !== null ? stored === 'true' : defaultExpanded;
  });
  
  useEffect(() => {
    localStorage.setItem(storageKey, String(expanded));
  }, [expanded, storageKey]);
  
  // ... rest of component
}
```

---

### H. Batch Pipeline Concurrency Limit

Prevent memory issues with many input documents:

```python
# In RunConfig
max_concurrent_pipelines: int = 5  # Don't run more than 5 pipelines at once

# In execute()
pipeline_semaphore = asyncio.Semaphore(config.max_concurrent_pipelines)

async def run_pipeline_with_limit(pipeline):
    async with pipeline_semaphore:
        return await pipeline.run()

pipeline_results = await asyncio.gather(
    *[run_pipeline_with_limit(p) for p in pipelines],
    return_exceptions=True
)
```

This is separate from the API call semaphore. It limits how many document pipelines are active simultaneously, while the API semaphore limits actual LLM calls.

---

## Extended Testing Checklist

### Concurrency Edge Cases
- [ ] All docs finish at same time
- [ ] All docs finish at different times (staggered)
- [ ] First doc fails immediately, others succeed
- [ ] Last doc fails after others complete
- [ ] Middle doc fails, first and last succeed
- [ ] All docs fail
- [ ] Cancel during generation phase
- [ ] Cancel during pairwise phase
- [ ] Cancel when some docs are done, some in-progress

### UI Edge Cases
- [ ] Single document run (backward compat)
- [ ] Two document run
- [ ] Ten+ document run (scroll, performance)
- [ ] Mix of completed/failed/cancelled sections
- [ ] Expand/collapse persistence across page reload
- [ ] Tab state per section (independent)
- [ ] WebSocket updates update correct section only

### Data Edge Cases
- [ ] Old run data (pre-multi-doc) displays correctly
- [ ] Run with no documents (should fail validation)
- [ ] Run with empty document content (should fail validation)
- [ ] Very long document names (UI truncation)

---

## Implementation Progress Log

### Phase 1: Data Model Changes ✅ COMPLETED

**Date:** Completed  
**Files Modified:** `app/services/run_executor.py`

**Changes Made:**

1. **RunPhase Enum Update** (~line 51)
   - Added `COMPLETED_WITH_ERRORS = "completed_with_errors"` for partial success scenarios

2. **SourceDocResult Dataclass** (lines ~333-370)
   - Created new dataclass with all required fields:
     - `source_doc_id: str`
     - `source_doc_name: str`
     - `status: RunPhase`
     - `generated_docs: List[GeneratedDocument]`
     - `single_eval_results: Dict[str, SingleEvalSummary]`
     - `pairwise_results: Optional[PairwiseSummary]`
     - `winner_doc_id: Optional[str]`
     - `combined_doc: Optional[GeneratedDocument]`
     - `timeline_events: List[dict]`
     - `errors: List[str]`
     - `cost_usd: float`
     - `duration_seconds: float`

3. **RunResult Dataclass Update** (lines ~374-420)
   - Added `source_doc_results: Dict[str, SourceDocResult]` field
   - Kept legacy flat fields for backward compatibility during transition

4. **RunConfig Dataclass Update** (lines ~143-155)
   - Added `document_names: Dict[str, str]` - maps doc_id to display name
   - Added `max_concurrent_pipelines: int = 5` - limits simultaneous pipeline execution

**Verified:** No linting/compile errors

---

### Phase 2: Executor Refactor ✅ COMPLETED

**Date:** Completed  
**Files Created:** `app/services/source_doc_pipeline.py`  
**Files Modified:** `app/services/run_executor.py`

**Changes Made:**

1. **Created SourceDocPipeline Class** (`source_doc_pipeline.py`, ~700 lines)
   - Encapsulates complete pipeline for a single source document
   - Phases are serial within document: Generation → Single Eval → Pairwise → Combine → Post-Combine Eval
   - Shares API semaphore with other pipelines for rate limiting
   - Key methods:
     - `run()` - Main entry point, returns `SourceDocResult`
     - `_run_generation_with_eval()` - Generate + streaming single eval
     - `_run_pairwise()` - Pairwise evaluation for this doc's variations only
     - `_run_combine()` - Combine top docs
     - `_run_post_combine_eval()` - Post-combine pairwise evaluation
     - `_generate_single()` - Generate one document variation
     - `_emit_timeline_event()` - Per-document timeline events
   - Supports cancellation via `cancel()` method

2. **Refactored RunExecutor.execute()** (run_executor.py)
   - Added decision point: multi-doc vs single-doc execution
   - Multi-doc (>1 document): Uses new `_execute_multi_doc()` method
   - Single-doc (1 document): Uses legacy `_execute_single_doc_legacy()` method for backward compatibility

3. **New _execute_multi_doc() Method** (run_executor.py)
   - Creates a `SourceDocPipeline` for each source document
   - Runs all pipelines concurrently with `asyncio.gather()`
   - Uses two semaphores:
     - `api_semaphore` - Limits concurrent API calls (shared across all pipelines)
     - `pipeline_semaphore` - Limits how many pipelines are active (max_concurrent_pipelines)
   - Aggregates results from all pipelines into `RunResult.source_doc_results`
   - Determines overall run status:
     - `COMPLETED` - All pipelines succeeded
     - `COMPLETED_WITH_ERRORS` - Some succeeded, some failed
     - `FAILED` - All pipelines failed
     - `CANCELLED` - Run was cancelled
   - Maintains backward compatibility by populating legacy `generated_docs` list

4. **New _on_pipeline_timeline_event() Method** (run_executor.py)
   - Callback passed to SourceDocPipeline instances
   - Forwards timeline events to the main timeline system
   - Includes source_doc_id in all events for filtering

5. **Legacy Path Preserved** (run_executor.py)
   - `_execute_single_doc_legacy()` contains the original execution logic
   - Used for single-document runs to avoid breaking existing behavior
   - Will be deprecated once multi-doc path is fully tested

**Verified:** No linting/compile errors

---

### Phase 3: API Layer Updates ✅ COMPLETED

**Date:** Completed  
**Files Modified:**
- `app/api/schemas/runs.py`
- `app/api/routes/runs/helpers.py`
- `app/api/routes/runs/execution.py`

**Changes Made:**

1. **New API Schema Models** (runs.py)
   - Added `SourceDocStatus` enum with all pipeline states
   - Added `SourceDocResultResponse` model with fields:
     - `source_doc_id`, `source_doc_name`, `status`
     - `generated_docs: list[GeneratedDocInfo]`
     - `single_eval_scores: dict[str, float]`
     - `single_eval_detailed: dict[str, DocumentEvalDetail]`
     - `pairwise_results: Optional[PairwiseResults]`
     - `winner_doc_id`, `combined_doc`
     - `post_combine_eval_scores`, `post_combine_pairwise`
     - `timeline_events: list[TimelineEvent]`
     - `errors`, `cost_usd`, `duration_seconds`

2. **Updated RunDetail Model** (runs.py)
   - Added `source_doc_results: dict[str, SourceDocResultResponse]`
   - Documented as "Results organized by source document ID"

3. **Updated to_detail() Helper** (helpers.py)
   - Added import for `SourceDocResultResponse` and `SourceDocStatus`
   - Added parsing logic for `source_doc_results` from `results_summary`
   - Handles nested structures: generated_docs, pairwise, combined_doc, timeline
   - Graceful fallback on parse errors with logging

4. **Updated Results Persistence** (execution.py)
   - Added serialization of `source_doc_results` using `serialize_dataclass()`
   - Saves per-document results to database in `results_summary.source_doc_results`

**Verified:** No linting/compile errors
---

### Phase 4: Frontend Updates  COMPLETED

**Date:** Completed  
**Files Created:**
- `ui/src/pages/execute/SourceDocSection.tsx`
- `ui/src/pages/execute/SourceDocEvaluationContent.tsx`
- `ui/src/pages/execute/SourceDocPairwiseContent.tsx`

**Files Modified:**
- `ui/src/api/runs.ts`
- `ui/src/pages/Execute.tsx`

**Changes Made:**

1. **New TypeScript Types** (runs.ts)
   - Added `SourceDocStatus` type with all pipeline states
   - Added `SourceDocResult` interface with fields:
     - `source_doc_id`, `source_doc_name`, `status`
     - `generated_docs: GeneratedDocInfo[]`
     - `single_eval_scores: Record<string, number>`
     - `single_eval_detailed?: Record<string, DocumentEvalDetail>`
     - `pairwise_results?: PairwiseResults`
     - `winner_doc_id?`, `combined_doc?`
     - `post_combine_eval_scores?`, `post_combine_pairwise?`
     - `timeline_events?: TimelineEvent[]`
     - `errors: string[]`, `cost_usd`, `duration_seconds`
   - Updated `Run` interface with `source_doc_results?: Record<string, SourceDocResult>`
   - Updated `mapRun()` to include `source_doc_results`

2. **New SourceDocSection Component** (SourceDocSection.tsx)
   - Collapsible section per source document
   - Header shows: document name, status badge, winner info, duration, cost
   - Contains inner tabs for "Single Evaluation" and "Pairwise"
   - Status badges with colors for all SourceDocStatus values
   - Green dot indicators for tabs with data
   - Error display section when errors exist

3. **New SourceDocEvaluationContent Component** (SourceDocEvaluationContent.tsx)
   - Displays generated docs table with scores
   - Shows average score with color-coded badges
   - Document viewer modal for viewing generated content
   - Post-combine evaluation section
   - Winner highlighting

4. **New SourceDocPairwiseContent Component** (SourceDocPairwiseContent.tsx)
   - ELO rankings table with medals ()
   - Win/loss/win-rate statistics
   - Post-combine vs winner comparison section
   - Winner highlighting throughout

5. **Updated Execute.tsx**
   - Added import for `SourceDocSection`
   - Added conditional rendering logic:
     - If `source_doc_results` exists and has entries  Show multi-doc view
     - Otherwise  Fall back to legacy single-doc view
   - Multi-doc view shows:
     - Info banner explaining multi-doc mode
     - Count of source documents
     - SourceDocSection for each source document
   - Auto-collapses sections when > 3 documents
   - Timeline tab still uses global TimelineTab component

**Verified:** No linting/compile errors

---

### Phase 5: Backward Compatibility & Unified Execution  COMPLETED

**Date:** Completed
**Files Modified:**
- `app/services/run_executor.py`
- `ui/src/pages/Execute.tsx`
- `ui/src/pages/execute/SourceDocSection.tsx`

**Changes Made:**

1. **Unified Execution Path** (run_executor.py)
   - ALL runs now use the per-source-document pipeline architecture
   - Single-document runs are a special case with one pipeline
   - Removed the conditional routing (`if len(document_ids) > 1`)
   - Legacy `_execute_single_doc_legacy()` method is preserved but no longer called
   - Can be removed after testing confirms stability

2. **Adaptive UI for Single-Doc Runs** (Execute.tsx)
   - Multi-doc info banner only shows when 2+ documents
   - Single-doc runs display cleanly without extra chrome
   - Passes `hideHeader={true}` to SourceDocSection for single-doc

3. **SourceDocSection Header Toggle** (SourceDocSection.tsx)
   - Added `hideHeader` prop (default: false)
   - When `hideHeader=true`:
     - No collapsible header shown
     - Transparent background (blends with parent)
     - No border/margin
     - Content always expanded
   - Single-doc runs look like the old UI, multi-doc shows collapsible sections

4. **Legacy Run Compatibility**
   - Old runs without `source_doc_results` still use legacy EvaluationTab/PairwiseTab
   - Frontend checks `source_doc_results` existence before rendering new UI
   - Graceful fallback for database runs from before this change

**Testing Checklist:**
- [x] Single-doc run uses SourceDocPipeline (verified by routing change)
- [x] Multi-doc run shows collapsible sections (verified by component logic)
- [x] Old runs without source_doc_results fall back to legacy view (preserved)
- [x] No TypeScript/linting errors

**Verified:** No linting/compile errors
