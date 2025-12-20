# LIVE STATS POSTMORTEM (FUCKING-LIVE-STATS-7)

Date: December 20, 2025
Run IDs: ACM run 066d07f9-96e5-4f2f-996d-78b66c493072; FPF run 5536f75b
Logs reviewed: acm2/logs/066d07f9-96e5-4f2f-996d-78b66c493072/run.log; FilePromptForge/logs/20251220T000411-5536f75b.json

## Problems Observed
- WebSocket broadcasts reported **0 connected clients** for all stats updates, so no live observer ever received fpf_stats_update despite frequent broadcasts (see run.log). Live stats were effectively dropped.
- Stats tracker left **stale error text** even after successful calls: last_error stayed set to the JSON parse failure (“Retry 2: Found JSON-like content but failed to parse…”) while successful_calls was 7 and failed_calls was 0. The error is not cleared on recovery, so the UI will show an error even though the run succeeded.
- At least one generation/eval attempt **failed JSON parsing** despite the `--json` flag; retries were triggered, inflating retries count to 2. We need to capture the offending output and fix parsing/validation.
- The FPF consolidation log recorded **parsed_json_found=False** and only markdown output paths; structured JSON was never extracted. That means downstream consumers relying on parsed JSON (scores/metadata) will not have data.
- Run executor logged **heartbeats with very large elapsed values (800–1170s) and uneven intervals**, suggesting the timeout/heartbeat math is wrong or duplicated, and making it hard to tell real wall-clock progress.
- Because no clients were connected and we still do not persist live stats to the DB, **refreshing the UI would still show “No stats”** during the run; observability is fragile.
- Broadcast loop kept emitting while connections were zero; we do not short-circuit or buffer, wasting cycles and masking the lack of subscribers.
- The run consumed a long OpenAI call (214s) before returning, yet stats continued to broadcast “current_phase=generation” long after; phase transitions are delayed and not synchronized to the actual task boundaries.

## Evidence Pointers
- ACM run log: acm2/logs/066d07f9-96e5-4f2f-996d-78b66c493072/run.log (WebSocket 0-connections, retries=2, stale last_error, long heartbeat spans, phase drift).
- FPF run log: FilePromptForge/logs/20251220T000411-5536f75b.json (parsed_json_found=False, long 214s OpenAI call, web_search tool used, validation passes but no structured output).
