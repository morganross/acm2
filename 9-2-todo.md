# Live Stats Subsystem Todo List (Extracted from Stats 1-8)

## High Priority: Robustness & Persistence
- [ ] **Implement Database Persistence**: Modify `RunExecutor._broadcast_stats` to update `live_stats` in the `runs` table mid-run (every ~5s or on change).
- [ ] **Fix 0-Connection Broadcasts**: Investigate why `RunConnectionManager` reports 0 connections even when UI is open.
- [ ] **Enforce FPF Deadlines**: Fix `file_handler.py` to respect a total execution deadline across retries (don't reset the 600s timer on every retry).
- [ ] **Fix Heartbeat Math**: Correct the `elapsed` time calculation in `RunExecutor` to prevent double-counting or uneven intervals.
- [ ] **Clear Sticky Errors**: Ensure `last_error` in `FpfStatsTracker` is cleared upon a successful call.

## Medium Priority: UI/UX Polish
- [ ] **Fix Duration Display**: Handle `null` end times in the frontend duration formatter (prevent "05:46:09 - —").
- [ ] **Fix Evaluation Counter**: Correctly calculate `total_evaluations` (docs × models × iterations) and pass to frontend.
- [ ] **Stream Individual Scores**: Ensure WebSocket emits events for each individual evaluation completion, not just the whole phase.
- [ ] **Fix CSS Contrast**: Resolve "White on White" text in the Evaluation Timeline details box.
- [ ] **Remove Decimal Seconds**: Round/format all time displays to whole seconds.

## Low Priority: Cleanup
- [ ] **Remove "FPF Output" Tab**: Delete the obsolete tab from the Execute page.
- [ ] **Stabilize Console Scroll**: Fix jumping/jerking in the console log area when new lines are added.
- [ ] **Default Preset Loading**: Ensure the "Build Preset" page loads with the default preset populated.

## Investigation Tasks
- [ ] **Analyze Phase Drift**: Determine why "current_phase" updates lag behind actual task boundaries.
- [ ] **Capture Parsing Failures**: Log and analyze the specific model outputs that fail JSON parsing despite the `--json` flag.
- [ ] **Verify HTTP Layer Retries**: Confirm if `max_retries=3` in `_http_post_json` is interacting poorly with FPF's own retry logic.
