# CRITICAL REFACTOR: Tabs INSIDE Per-Input-File Sections

## THE REQUIREMENT

```
Execute Page:
│
├── Header (preset, start button, stats)
│
├── 📁 INPUT FILE 1 (COLLAPSIBLE)
│   ├── [Single Eval | Pairwise | Timeline]  ← TABS HERE
│   └── Content for file 1 only
│
├── 📁 INPUT FILE 2 (COLLAPSIBLE)
│   ├── [Single Eval | Pairwise | Timeline]  ← TABS HERE
│   └── Content for file 2 only
│
└── Log Viewer
```

**TABS MUST BE INSIDE EACH SECTION. NEVER AT PAGE LEVEL.**

---

## ACTUAL EXECUTION FLOW (CORRECTED)

**The frontend does NOT use `/presets/{id}/execute`!**

Actual flow:
1. `POST /api/v1/runs` → `crud.py:create_run()` → Creates run, returns `RunSummary`
2. `POST /api/v1/runs/{id}/start` → `execution.py:start_run()` → Returns `{"status": "started"}`
3. `execute_run_background()` in `execution.py` → Runs pipeline, saves results

**Problem:** `source_doc_results` is only saved at the END of execution (line ~457 in execution.py).
The frontend never sees it until the run completes!

---

## PHASE 1: DIAGNOSE (Find the Break Point)

### Step 1.1: Check API Response
```
1. Open browser to http://127.0.0.1:8002/execute
2. Open DevTools → Network tab
3. Click "Start Execution"
4. Find POST /api/v1/runs (creates run)
5. Find POST /api/v1/runs/{id}/start (starts run)
6. Neither returns source_doc_results!
```

### Step 1.2: The Actual Problem
```
- crud.py creates run → no source_doc_results
- execution.py starts run → no source_doc_results  
- execute_run_background saves source_doc_results → but that's AFTER response is sent
- Frontend never gets source_doc_results until run completes
```

---

## PHASE 2: FIX BACKEND

### File: `app/api/routes/runs/execution.py`

**Fix: Initialize source_doc_results in start_run() BEFORE background task**

After line ~792 (`await repo.start(run_id)`), before `background_tasks.add_task()`:

```python
# Initialize source_doc_results for immediate frontend display
source_doc_results_init = {}
for doc_id in document_contents.keys():
    source_doc_results_init[doc_id] = {
        "source_doc_id": doc_id,
        "source_doc_name": doc_id,
        "status": "pending",
        "generated_docs": [],
        "single_eval_results": {},
        "pairwise_results": None,
        "winner_doc_id": None,
        "combined_doc": None,
        "cost_usd": 0.0,
        "errors": [],
    }

# Save to DB before returning
await repo.update(run_id, results_summary={"source_doc_results": source_doc_results_init})
logger.info(f"[INIT] Pre-initialized source_doc_results with {len(document_contents)} input documents")
```

**Also:** The response from `start_run()` should return the updated run data OR the frontend should re-fetch the run after starting.

---

## PHASE 2: FIX BACKEND

### Only File: `app/api/routes/presets.py`

The execution flow is:
1. POST `/presets/{id}/execute` creates run
2. Background task runs pipeline
3. WebSocket broadcasts updates

**Fix A: Initialize source_doc_results BEFORE returning response**

The current code initializes in `execute_run_background()` but that's AFTER the HTTP response is sent. Move initialization to BEFORE `BackgroundTasks.add_task()`:

```python
# In execute_preset endpoint, BEFORE background task starts:

# Pre-initialize source_doc_results
source_doc_results = {}
for doc_id in document_contents.keys():
    source_doc_results[doc_id] = {
        "source_doc_id": doc_id,
        "source_doc_name": doc_id,
        "status": "pending",
        "generated_docs": [],
        "single_eval_results": {},
        "pairwise_results": None,
        "winner_doc_id": None,
        "combined_doc": None,
        "cost_usd": 0.0,
        "errors": [],
    }

# Save to DB before returning
await repo.update(run.id, results_summary={"source_doc_results": source_doc_results})

# NOW start background task
background_tasks.add_task(execute_run_background, run.id, config)

# Return run WITH source_doc_results already populated
```

**Fix B: Ensure response includes source_doc_results**

Check that the returned Run object includes the updated `results_summary` after the save.

---

## PHASE 3: FIX FRONTEND

### File 1: `Execute.tsx`

**DELETE these things:**
1. The `type TabType = 'evaluation' | 'pairwise' | 'timeline'` definition
2. The `const [activeTab, setActiveTab] = useState<TabType>('evaluation')` state
3. The entire tab bar div (the one with "Single Evaluation", "Pairwise Comparison", "Timeline & Details" buttons)
4. All `activeTab === 'xxx'` conditional checks

**KEEP:**
- The SourceDocSection rendering loop
- The error display when source_doc_results is missing
- The "no run started" placeholder

### File 2: `SourceDocSection.tsx`

**ADD Timeline tab:**

1. Update TabType:
```tsx
type TabType = 'evaluation' | 'pairwise' | 'timeline'
```

2. Add Timeline button to existing tab bar:
```tsx
<button onClick={() => setActiveTab('timeline')} ...>
  <Clock size={14} />
  Timeline
</button>
```

3. Add Timeline content:
```tsx
{activeTab === 'timeline' && (
  <div style={{ color: '#9ca3af', padding: '20px', textAlign: 'center' }}>
    <Clock size={24} style={{ marginBottom: '8px' }} />
    <div>Timeline for {sourceDocResult.source_doc_name}</div>
    <div style={{ fontSize: '12px', marginTop: '8px' }}>
      Status: {sourceDocResult.status}
    </div>
    {sourceDocResult.duration_seconds && (
      <div style={{ fontSize: '12px' }}>
        Duration: {sourceDocResult.duration_seconds}s
      </div>
    )}
  </div>
)}
```

---

## PHASE 4: BUILD & TEST

```powershell
# 1. Rebuild UI
cd c:\dev\godzilla\acm2\acm2\ui
npm run build

# 2. Restart server
python c:\dev\godzilla\acm2\acm2\cli.py serve

# 3. Test in browser
# - Go to http://127.0.0.1:8002/execute
# - Select preset with 2 documents
# - Click Start Execution
# - VERIFY: Collapsible sections appear immediately
# - VERIFY: Tabs are INSIDE each section
# - VERIFY: NO tabs at page level
```

---

## VERIFICATION CHECKLIST

- [ ] No `activeTab` state in Execute.tsx
- [ ] No tab bar rendered in Execute.tsx
- [ ] SourceDocSection has 3 tabs: Eval, Pairwise, Timeline
- [ ] Each section's tabs are independent
- [ ] source_doc_results appears in API response immediately
- [ ] Collapsible sections show before first generation completes

---

## FILES TO MODIFY (ONLY 3)

| File | Action |
|------|--------|
| `presets.py` | Initialize source_doc_results before returning response |
| `Execute.tsx` | DELETE page-level tabs and activeTab state |
| `SourceDocSection.tsx` | ADD Timeline tab |

---

## SUCCESS = 

1. Page loads → No tabs visible at page level
2. Start run → Collapsible sections appear with tabs INSIDE
3. Click tab in Section 1 → Section 2 unaffected
