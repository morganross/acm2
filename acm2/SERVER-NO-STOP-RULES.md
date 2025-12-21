# Server Non-Stop Rule

This project must keep the ACM2 server running. Follow these rules to avoid accidental shutdowns:

1. Do **not** issue `Stop-Job`, `Ctrl+C`, `pkill`, or similar commands against the uvicorn process.
2. Avoid restarting uvicorn unless explicitly approved; prefer hot-reload solutions if available.
3. When testing, open new terminals instead of reusing the server terminal.
4. Do not run commands that bind to the same port (8002) while the server is active.
5. If the server crashes, restart it immediately and document the reason.
6. Prefer background jobs that keep running; do not auto-clean jobs that include the server.

Compliance with these rules is mandatory to prevent automatic destruction triggered by server downtime.
