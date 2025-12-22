# Execution Issues Log

## 2025-12-21 — Run 1ef192cb-f774-4d5e-abc7-1f874c9de120
- FPF generation crashed for both openai:gpt-5.1 and google:gemini-3-pro-preview because `grounding_enforcer` cannot be imported when `file_handler.py` runs as a script (relative import fails). No generations succeeded.
- CLI cancel attempt returned 405 Method Not Allowed (run had already completed with errors).

## 2025-12-21 — Run 28f66991-261a-4315-a8b2-db62212ce7ce
- FPF now starts but single-eval repeatedly raises KeyError `task_id` for google:gemini-3-pro-preview output (four retries) so scoring fails ([server.log](acm2/server.log#L200-L224)).
- openai:gpt-5.1 response never finishes/logs beyond the request payload, leaving the run stuck in `running` despite google eval finishing; run.log for this run stays empty after startup and cancel endpoint returns 405 ([acm2/acm2/logs/28f66991-261a-4315-a8b2-db62212ce7ce/run.log](acm2/acm2/logs/28f66991-261a-4315-a8b2-db62212ce7ce/run.log#L1-L35), [acm2/server.log](acm2/server.log#L1-L120)).

## 2025-12-21 — Run 3eebaa17-174b-43e6-9ff4-af8cd97484e7
- google:gemini-3-pro-preview generation completes after ~36s and passes grounding validation; output saved but run stays running because openai calls hang ([FilePromptForge/logs/3eebaa17-174b-43e6-9ff4-af8cd97484e7/fpf_0dd19fd9-45f8-456a-822f-44517469e725.fpf.1.google_gemini-3-pro-preview.log](FilePromptForge/logs/3eebaa17-174b-43e6-9ff4-af8cd97484e7/fpf_0dd19fd9-45f8-456a-822f-44517469e725.fpf.1.google_gemini-3-pro-preview.log#L1-L37), [acm2/acm2/logs/3eebaa17-174b-43e6-9ff4-af8cd97484e7/generated/7469e725.8599.fpf.1.google_gemini-3-pro-preview.md](acm2/acm2/logs/3eebaa17-174b-43e6-9ff4-af8cd97484e7/generated/7469e725.8599.fpf.1.google_gemini-3-pro-preview.md#L1-L80)).
- openai:gpt-5.1 generation never returns; FPF log stops at the outbound request with no response or validation ([FilePromptForge/logs/3eebaa17-174b-43e6-9ff4-af8cd97484e7/fpf_0dd19fd9-45f8-456a-822f-44517469e725.fpf.1.openai_gpt-5.1.log](FilePromptForge/logs/3eebaa17-174b-43e6-9ff4-af8cd97484e7/fpf_0dd19fd9-45f8-456a-822f-44517469e725.fpf.1.openai_gpt-5.1.log#L1-L24)).
- Single-eval with openai:gpt-5-mini starts after google generation but also hangs at the outbound request; no response/validation logs and run status remains `running`; cancel endpoint returns 405 Method Not Allowed ([FilePromptForge/logs/fpf_run_2736.log](FilePromptForge/logs/fpf_run_2736.log#L1-L35), [acm2/server.log](acm2/server.log#L1-L115)).

## 2025-12-21 — Run 83657742-6063-4715-8349-e65561c5e1f8
- google:gemini-3-pro-preview generation succeeds in ~37s and passes grounding/validation; output written ([acm2/acm2/logs/83657742-6063-4715-8349-e65561c5e1f8/run.log](acm2/acm2/logs/83657742-6063-4715-8349-e65561c5e1f8/run.log#L18-L62), [FilePromptForge/logs/83657742-6063-4715-8349-e65561c5e1f8/fpf_0dd19fd9-45f8-456a-822f-44517469e725.fpf.1.google_gemini-3-pro-preview.log](FilePromptForge/logs/83657742-6063-4715-8349-e65561c5e1f8/fpf_0dd19fd9-45f8-456a-822f-44517469e725.fpf.1.google_gemini-3-pro-preview.log#L1-L33), [acm2/acm2/logs/83657742-6063-4715-8349-e65561c5e1f8/generated/7469e725.7420.fpf.1.google_gemini-3-pro-preview.md](acm2/acm2/logs/83657742-6063-4715-8349-e65561c5e1f8/generated/7469e725.7420.fpf.1.google_gemini-3-pro-preview.md#L1-L120)).
- openai:gpt-5.1 generation now completes (186.7s) and passes grounding/validation; output saved, so prior hang is resolved for this model ([FilePromptForge/logs/83657742-6063-4715-8349-e65561c5e1f8/fpf_0dd19fd9-45f8-456a-822f-44517469e725.fpf.1.openai_gpt-5.1.log](FilePromptForge/logs/83657742-6063-4715-8349-e65561c5e1f8/fpf_0dd19fd9-45f8-456a-822f-44517469e725.fpf.1.openai_gpt-5.1.log#L1-L37), [acm2/acm2/logs/83657742-6063-4715-8349-e65561c5e1f8/generated/7469e725.461a.fpf.1.openai_gpt-5.1.md](acm2/acm2/logs/83657742-6063-4715-8349-e65561c5e1f8/generated/7469e725.461a.fpf.1.openai_gpt-5.1.md#L1-L120)).
- Run remains `running` because the first single-eval (openai:gpt-5-mini judging the Google output) logged its start but never produced a response/validation or RUN_COMPLETE; FPF log stops after the outbound request ([FilePromptForge/logs/fpf_run_10856.log](FilePromptForge/logs/fpf_run_10856.log#L1-L24), [acm2/acm2/logs/83657742-6063-4715-8349-e65561c5e1f8/run.log](acm2/acm2/logs/83657742-6063-4715-8349-e65561c5e1f8/run.log#L40-L76)).

## 2025-12-21 — Run 3d2d8315-d694-45a4-823c-82854d2cd61b
- openai:gpt-5.1 generation failed immediately: provider module failed to import due to an IndentationError at the instructions block, exhausting retries and aborting the run ([acm2/acm2/logs/3d2d8315-d694-45a4-823c-82854d2cd61b/run.log](acm2/acm2/logs/3d2d8315-d694-45a4-823c-82854d2cd61b/run.log#L33-L111), [FilePromptForge/providers/openai/fpf_openai_main.py](FilePromptForge/providers/openai/fpf_openai_main.py#L120-L150)).
- google:gemini-3-pro-preview never started because run aborted during OpenAI provider import failure; run remains `running`/stuck.

---

# FIXES APPLIED

## 2025-12-21 — Fix: FPF Adapter file_a/file_b Parameter Ordering

**Problem:** OpenAI generation was taking 17+ minutes and eventually timing out, while Google completed in ~50 seconds. Investigation revealed the FPF prompt was malformed — the prompt contained only instructions with no actual document content.

**Root Cause:** In [app/adapters/fpf/adapter.py](acm2/app/adapters/fpf/adapter.py#L93-L110), the `file_a` and `file_b` parameters were swapped:
- `file_a` was being set to `query` (instructions)
- `file_b` was being set to `document_content`

However, FPF's `compose_input()` function in [FilePromptForge/lib/compose_input.py](FilePromptForge/lib/compose_input.py) concatenates them as: `file_b + "\n\n" + file_a`. This meant the final prompt had document content FIRST, then instructions — but because of the swap, it had instructions followed by an empty string.

**Fix Applied:**
```python
# file_a = document content (appended AFTER file_b in final prompt)
file_a_path = tmp_path / "content.txt"
file_a_content = document_content or ""
file_a_path.write_text(file_a_content, encoding="utf-8")

# file_b = instructions/query (placed FIRST in final prompt)  
file_b_path = tmp_path / "instructions.txt"
file_b_path.write_text(query, encoding="utf-8")
```

**Files Changed:**
- [acm2/app/adapters/fpf/adapter.py](acm2/app/adapters/fpf/adapter.py#L93-L110)

## 2025-12-21 — Fix: Preset Document Reference Mismatch

**Problem:** Even after the file_a/file_b fix, document_content was still empty because the preset referenced a non-existent document ID.

**Root Cause:** The Default Preset's `documents` field contained `["0dd19fd9-45f8-456a-822f-44517469e725"]` but this ID didn't exist in the `documents` table. The only existing document was `ba289490-4678-4337-85b4-66187c93e8b2` (sample_input.txt).

**Fix Applied:** Updated the preset's documents field via SQL:
```sql
UPDATE presets SET documents = '["ba289490-4678-4337-85b4-66187c93e8b2"]' 
WHERE id = '86f721fc-742c-4489-9626-f148cb3d6209'
```

## 2025-12-21 — Fix: Evaluation max_tokens Increased

**Problem:** Evaluation calls may have been truncated due to low max_tokens setting.

**Fix Applied:** Increased `max_tokens` from 4096 to 16384 in:
- [acm2/app/evaluation/judge.py](acm2/app/evaluation/judge.py)
- [acm2/app/evaluation/pairwise.py](acm2/app/evaluation/pairwise.py)
- [acm2/app/evaluation/single_doc.py](acm2/app/evaluation/single_doc.py)

---

# SUCCESSFUL RUN

## 2025-12-21 — Run 1a2167f9-ea04-4b21-86ec-36b9934a9fb4 ✅ COMPLETED

**Status:** `completed`  
**Winner:** `7c93e8b2.b9cd.fpf.1.google_gemini-3-pro-preview`  
**Total Duration:** 1207.6s (20.1 minutes)

### Timeline:
| Phase | Model | Duration | Status |
|-------|-------|----------|--------|
| Generation | google:gemini-3-pro-preview | 53.5s | ✓ |
| Generation | openai:gpt-5.1 | 209.7s (3.5 min) | ✓ |
| Single Eval | 3 judge models | 387.3s | ✓ |
| Single Eval | 3 judge models | 462.4s | ✓ |
| Pairwise | 3 judge models | 527.3s | ✓ |

### Evaluation Scores:
- **Google (gemini-3-pro-preview):** avg=4.28
  - openai:gpt-5-mini: 4.00
  - google:gemini-2.5-flash: 4.83
  - google:gemini-3-pro-preview: 4.00
- **OpenAI (gpt-5.1):** avg=4.50
  - openai:gpt-5-mini: 4.50
  - google:gemini-2.5-flash: 4.17
  - google:gemini-3-pro-preview: 4.83

### Remaining Issues (non-blocking):
1. **Pairwise JSON parsing errors:** gemini-3-pro-preview returned invalid JSON in some pairwise attempts (retried successfully)
2. **Combine phase failed:** "FPF config missing required fields: task_id" — all combine models failed after 3 retries each. The combine adapter needs a `task_id` field that isn't being provided.
