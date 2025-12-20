ACM2 → ACM1 Parity Plan (UI + Reports)
======================================

Goals
- Match ACM1 pairwise heatmap math, sizing, and palette.
- Fix single-eval contrast with ACM1 score badges.
- Add generation and evaluation timelines with per-run start/end/duration, costs, and unplanned rows.
- Preserve doc labels (shorten + hyperlinks) and ELO hints where relevant.

Source Reference
- ACM1 generator: `llm-doc-eval/reporting/html_exporter.py` (pairwise matrix, score badges, timelines, cost/unplanned sections, ELO labels).

Data Strategy (start times/durations)
- Canonical: persist per-step start_ts, end_ts, duration_seconds, tokens, cost, status in DB (timeline_events or dedicated table). Logs/JSON only as backup/export artifacts. DB-first keeps reports reproducible.
- API: expose timeline rows (phase, judge/model, target, start/end, duration, tokens, cost, status, source/delta) for reports/UI.

Implementation Steps (ordered)
1) Pairwise heatmap ACM1 style (Execute + HTML report)
   - Use net win delta per cell; tiered colors: green/red ±1/±2/±3, neutral gray; fixed 50x50 squares, thin borders.
   - Vertical column headers with shorten_label + ELO + 🏆 on winner; tooltips keep wins/total.
   - Update palette to match ACM1 matrix CSS.
   ✅ Execute pairwise matrix updated (ui/src/pages/Execute.tsx) — net delta, ACM1 palette, 50px cells, ELO/winner in headers.

2) Single-eval contrast
   - Apply ACM1 score badge classes: score-perfect/great/mid/low colors; ensure dark text where needed.
   - Remove white-on-white in single-eval table/cards.
   ✅ getScoreBadgeStyle updated (ui/src/pages/Execute.tsx) — thresholds mapped to ACM1 score-X tiers, dark text on mid-range colors.

3) Timelines (generation + eval)
   - Backend: store per-step start/end/duration/tokens/cost/status in DB; export timeline JSON from DB (logs optional backup).
   - Frontend report: port ACM1 renderers (grouped headers Expected/Logs/DB/Costs/Status, phase headers, subtotals, grand total, bar visuals, status icons, unplanned actuals table, FPF call table).
   - Execute UI: show start/end/duration columns and status icons; add generation + eval views aligned with ACM1 structure.
   ✅ Backend generation_events now includes started_at/completed_at (app/api/routes/runs.py).
   ✅ Execute timeline tab updated with Start/End/Duration/Visual/Status columns (ui/src/pages/Execute.tsx).
   ✅ GeneratedDocument model now has started_at/completed_at fields (app/services/run_executor.py).
   ✅ _generate_single captures start/end timestamps and includes them in GeneratedDocument.
   ✅ SingleEvalResult and PairwiseResult models now have started_at/completed_at/duration_seconds (app/evaluation/models.py).
   ✅ Judge.evaluate_single and evaluate_pairwise now track and return timing (app/evaluation/judge.py).
   ✅ timeline_events now include detailed per-eval and per-pairwise events with timing (app/api/routes/runs.py).
   ✅ Evaluation Details table added to Execute UI showing eval/pairwise timing (ui/src/pages/Execute.tsx).

4) Cost/unplanned sections
   - Add eval cost summary (FPF logs) with model breakdown.
   - Add unplanned actuals section (show runs not matched to expected).

5) Labels/links
   - Use shorten_label logic; add doc hyperlinks where paths available; include ELO in headers for pairwise.

Testing/Validation
- Compare live Execute pairwise grid against ACM1 heatmap screenshot for size/palette/net math.
- Generate report and verify timelines show per-run start/end/duration, subtotals, grand totals, unplanned, and cost sections.
- Check single-eval scores for contrast on light backgrounds.

Verification Screenshots (saved to acm2/docs/)
- `verify-single-tab.png` — Single eval tab with score badges
- `verify-single-scores.png` — Close-up of score badges with colors
- `verify-pairwise-tab.png` — Pairwise rankings table
- `verify-pairwise-matrix.png` — Head-to-head matrix with 50x50 cells
- `verify-matrix-close.png` — Matrix close-up
- `verify-timeline-tab.png` — Timeline tab header
- `verify-timeline-rows.png` — Timeline rows with duration and visual bars

Verified Features (2024-12-13)
✅ Score badges: 4=green/dark, 3=gold/dark, 2=orange/white, 1=red/white — visible contrast
✅ Pairwise matrix: 50x50 cells, ELO in headers, 🏆 on winner, net delta values
✅ Timeline table: dark header (#343a40), Start/End/Duration/Visual columns, green bar width proportional to duration
✅ Rankings table: 🥇/🥈 emojis, Wins/Losses/WinRate/ELO columns

Notes
- DB-first for timing; logs/JSON as supplementary artifacts.
- Start/End times now populated from run_executor — no log/terminal parsing needed.
- All timing data flows: run_executor → GeneratedDocument/SingleEvalResult/PairwiseResult → API → Frontend.

Updated 2024-12-14:
- Added timing fields to GeneratedDocument, SingleEvalResult, PairwiseResult dataclasses.
- Updated _generate_single, evaluate_single, evaluate_pairwise to capture start/end timestamps.
- API now builds detailed timeline_events with per-generation, per-evaluation, per-pairwise entries.
- Frontend Execute.tsx now shows Evaluation Details table with timing bars.