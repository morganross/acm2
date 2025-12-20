# ACM2 PRESET SAVE/LOAD BUG REPORT

**Date:** December 13, 2025  
**Severity:** HIGH  
**Component:** Preset Configuration Persistence  
**Status:** Identified, Fix In Progress

---

## EXECUTIVE SUMMARY

### What IS Broken
**The Preset Save/Load system** - When a user configures settings on the Build Preset page and clicks Save, most of the configuration is NOT being saved to the database. When they reload the preset, those settings are lost.

### What is NOT Broken
**The Run Execution System** - The core ACM2 architecture for processing multiple runs simultaneously is INTACT. This bug does not affect:
- ✅ Run creation and queuing
- ✅ Parallel run execution
- ✅ Run status tracking
- ✅ Run history and results
- ✅ The fundamental multi-run architecture

---

## CLARIFICATION: PRESETS vs RUNS

### Presets (BROKEN)
A **Preset** is a saved configuration template. It's like a "recipe" that defines:
- Which documents to process
- Which models to use (FPF, GPTR, Eval, Combine)
- Parameter settings (temperature, token limits, etc.)
- Whether to run evaluation, pairwise, combine phases

Presets are saved once and reused many times. The bug is that the "save recipe" feature doesn't save all ingredients.

### Runs (NOT BROKEN)
A **Run** is an actual execution of that recipe. When you click "Execute", a Run is created with:
- A copy of the preset configuration at that moment
- Its own status (pending, running, completed, failed)
- Its own results and outputs

The Run system works correctly. Multiple runs CAN execute simultaneously. The architecture is sound.

---

## THE ACTUAL BUG

### Problem Statement
The Build Preset page (`/configure`) has a form with ~50+ configurable fields across sections:
- General Settings
- FPF Parameters (18 fields)
- GPTR Parameters (16 fields)  
- Deep Research Parameters (16 fields)
- Multi-Agent Configuration (8 fields)
- Evaluation Configuration (12 fields)
- Combine Configuration (2 fields)

**Only ~10 of these fields are actually being saved to the database.**

### Data Flow Breakdown

```
┌─────────────────────────────────────────────────────────────────────────┐
│ USER INTERFACE (Configure.tsx)                                          │
│                                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │ FPF Panel   │  │ GPTR Panel  │  │ Eval Panel  │  │Combine Panel│   │
│  │ 18 fields   │  │ 16 fields   │  │ 12 fields   │  │ 2 fields    │   │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘   │
│         │                │                │                │          │
│         ▼                ▼                ▼                ▼          │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                    Zustand Config Store                          │  │
│  │  (Holds ALL field values correctly)                              │  │
│  └─────────────────────────────────┬───────────────────────────────┘  │
│                                    │                                   │
│                                    ▼                                   │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │              handleSavePreset() Function                         │  │
│  │                                                                  │  │
│  │  ❌ Only extracts ~10 fields from store                          │  │
│  │  ❌ Hardcodes empty arrays for criteria                          │  │
│  │  ❌ Only saves first model from arrays                           │  │
│  │  ❌ Ignores DR, MA sections entirely                             │  │
│  └─────────────────────────────────┬───────────────────────────────┘  │
└────────────────────────────────────┼───────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ API LAYER (presets.ts → /api/v1/presets)                                │
│                                                                         │
│  PresetCreate {                                                         │
│    name: ✅                     documents: ✅                            │
│    generators: ✅               models: ✅ (FPF only)                    │
│    iterations: ✅                                                        │
│    gptr_settings: ⚠️ (partial)  evaluation: ⚠️ (partial)                │
│    pairwise: ⚠️ (partial)       combine: ❌ (not sent)                   │
│    fpf_settings: ❌ (not sent)  dr_settings: ❌ (not sent)               │
│    ma_settings: ❌ (not sent)   concurrency: ❌ (not sent)               │
│  }                                                                      │
└─────────────────────────────────────┬───────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ DATABASE (preset table)                                                  │
│                                                                         │
│  Columns:                                                               │
│    id, name, description, documents, models, generators, iterations    │
│    evaluation_enabled, pairwise_enabled                                 │
│    gptr_config (JSON), fpf_config (JSON), config_overrides (JSON)      │
│                                                                         │
│  ⚠️ Schema CAN store everything via JSON columns                        │
│  ❌ But frontend doesn't send it, backend doesn't read it back          │
└─────────────────────────────────────────────────────────────────────────┘
```

### What Gets Lost

| Section | Fields in UI | Fields Saved | Fields Lost |
|---------|-------------|--------------|-------------|
| General | 5 | 1 (iterations) | 4 |
| FPF | 18 | 4 (models, temp, maxTokens, enabled) | 14 |
| GPTR | 16 | 4 (reportType, reportSource, fast_llm, smart_llm) | 12 |
| DR | 16 | 0 | 16 |
| MA | 8 | 0 | 8 |
| Eval | 12 | 1 (enabled) | 11 |
| Combine | 2 | 0 | 2 |
| **TOTAL** | **77** | **~10** | **~67 (87% lost)** |

---

## SPECIFIC FAILURES

### 1. Eval Judge Models Not Saved
```typescript
// CURRENT (broken):
evaluation: {
  enabled: config.eval.enabled,
  criteria: [],  // ❌ HARDCODED EMPTY
  eval_model: config.eval.judgeModels[0]  // ❌ ONLY FIRST MODEL
}

// SHOULD BE:
evaluation: {
  enabled: config.eval.enabled,
  criteria: buildCriteriaArray(),  // From checkboxes
  eval_models: config.eval.judgeModels,  // ALL models
  iterations: config.eval.iterations,
  pairwise_top_n: config.eval.pairwiseTopN,
}
```

### 2. Eval Judge Models Not Loaded
```typescript
// CURRENT (broken):
config.updateEval({
  enabled: preset.evaluation?.enabled ?? true,
  // ❌ judgeModels NOT SET
  // ❌ iterations NOT SET
  // ❌ pairwiseTopN NOT SET
  // ❌ criteria NOT SET
})

// SHOULD BE:
config.updateEval({
  enabled: preset.evaluation?.enabled ?? true,
  judgeModels: preset.evaluation?.eval_models?.map(m => `openai:${m}`) ?? [],
  iterations: preset.evaluation?.iterations ?? 3,
  pairwiseTopN: preset.evaluation?.pairwise_top_n ?? 5,
  // ... restore all criteria checkboxes
})
```

### 3. GPTR Models Not Saved/Loaded
The UI has a `gptr.selectedModels` array but only `fast_llm` and `smart_llm` (single strings) are saved.

### 4. Combine Settings Not Saved/Loaded
The `combine.enabled` and `combine.selectedModels` are never sent to the API.

### 5. FPF Parameters Not Saved/Loaded
All the sliders (grounding, topP, topK, frequency penalty, etc.) are ignored.

---

## ROOT CAUSE ANALYSIS

### Why This Happened
1. **Incremental Development** - The UI was built with full config store, but save/load was implemented minimally
2. **No Round-Trip Testing** - Nobody tested: configure → save → close → reopen → verify all fields match
3. **Schema Mismatch** - Backend schemas use single `eval_model` but UI needs `eval_models[]`
4. **Copy-Paste Bugs** - Some code was copied without adapting to full requirements

### Technical Debt
The `handleSavePreset` and `handlePresetChange` functions in `Configure.tsx` were written to handle a subset of fields and never expanded.

---

## IMPACT ASSESSMENT

### User Experience Impact
- **HIGH** - Users configure presets, save them, but settings are lost
- Users must re-configure every time they load a preset
- This defeats the entire purpose of having presets

### System Functionality Impact
- **MEDIUM** - Runs still execute, but with incomplete/wrong configuration
- Default values are used instead of user's intended settings

### Multi-Run Architecture Impact
- **NONE** - The run execution system is unaffected
- Multiple runs can still execute in parallel
- Run tracking and status management work correctly

---

## FIX PLAN

### Phase 1: Frontend Save (Configure.tsx handleSavePreset)
Expand to capture ALL config store fields:
- All FPF params
- All GPTR params  
- All Eval params (including judgeModels array)
- All Combine params
- DR and MA if enabled

### Phase 2: Backend Schema (if needed)
Check if schemas need expansion for arrays:
- `EvaluationSettings.eval_models: list[str]` instead of single string
- Additional fields for all params

### Phase 3: Frontend Load (Configure.tsx handlePresetChange)
Expand to restore ALL fields from preset response to config store.

### Phase 4: Testing
Create automated test that:
1. Sets every single field to a non-default value
2. Saves preset
3. Resets to defaults
4. Loads preset
5. Verifies every field matches

---

## CONCLUSION

This is a **Preset Persistence Bug**, not a fundamental architecture problem. The core ACM2 value proposition - managing multiple simultaneous runs - is intact and working.

The fix requires:
1. ~100 lines of code changes in `Configure.tsx`
2. Possible minor schema additions
3. Rebuild and deploy

Estimated fix time: 1-2 hours.

---

## APPENDIX: Files Involved

| File | Role | Needs Changes |
|------|------|---------------|
| `ui/src/pages/Configure.tsx` | Save/load logic | YES - Major |
| `ui/src/stores/config.ts` | State management | NO - Works correctly |
| `ui/src/api/presets.ts` | API types | YES - Add fields |
| `app/api/schemas/runs.py` | Backend schemas | MAYBE - Add array support |
| `app/api/schemas/presets.py` | Preset schemas | NO - Uses runs schemas |
| `app/api/routes/presets.py` | API endpoints | MAYBE - Handle new fields |
| `app/infra/db/models/preset.py` | DB model | NO - JSON columns can store anything |
