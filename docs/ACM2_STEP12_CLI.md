# ACM 2.0 – Step 12: CLI

**Status:** Draft  
**Author:** Development Team  
**Last Updated:** 2025-12-04

> **Platform:** Windows, Linux, macOS. Python + SQLite. No Docker.
> **Dependency:** This step requires Steps 7 (Run/Doc API) and the FastAPI backend to be running.  
> **Document Type:** Implementation specification for the code writer. Code samples are illustrative, not copy-paste ready.

---

## Table of Contents

1. [Purpose](#1-purpose)
2. [Scope](#2-scope)
3. [Prerequisites](#3-prerequisites)
4. [CLI Framework Selection](#4-cli-framework-selection)
5. [Command Structure](#5-command-structure)
6. [Server Commands](#6-server-commands)
7. [Run Commands](#7-run-commands)
8. [Document Commands](#8-document-commands)
9. [Evaluation Commands](#9-evaluation-commands)
10. [Report Commands](#10-report-commands)
11. [Config Commands](#11-config-commands)
12. [API Client Integration](#12-api-client-integration)
13. [Output Formatting](#13-output-formatting)
14. [Interactive Mode](#14-interactive-mode)
15. [Error Handling](#15-error-handling)
16. [Configuration File](#16-configuration-file)
17. [Shell Completion](#17-shell-completion)
18. [Tests](#18-tests)
19. [Success Criteria](#19-success-criteria)
20. [File Structure](#20-file-structure)
21. [Next Steps](#21-next-steps)

---

## 1. Purpose

Step 12 implements the **command-line interface (CLI)** for ACM 2.0, providing full access to all system functionality from the terminal.

### Why a CLI?

| Use Case | Benefit |
|----------|---------|
| **Power users** | Faster than GUI for experienced users |
| **Scripting** | Automate runs, evaluations, reports |
| **CI/CD** | Integrate ACM into build pipelines |
| **Headless servers** | Run without display (remote Windows Server) |
| **Quick operations** | Check status, list runs without opening browser |

### Core Principle: API-First

The CLI is a **thin wrapper** around the HTTP API:

```
┌─────────────────────────────────────────────────────────┐
│                      User Interfaces                     │
├─────────────────┬─────────────────┬─────────────────────┤
│    Web GUI      │      CLI        │   Scripts/Tools     │
│   (browser)     │   (terminal)    │    (automation)     │
└────────┬────────┴────────┬────────┴──────────┬──────────┘
         │                 │                   │
         ▼                 ▼                   ▼
┌─────────────────────────────────────────────────────────┐
│                   HTTP/JSON API                          │
│              (FastAPI Backend - Step 7)                  │
└─────────────────────────────────────────────────────────┘
```

The CLI never accesses the database or files directly. All operations go through the API.

### Primary Commands

| Command | Purpose |
|---------|---------|
| `acm2 serve` | Start the web server |
| `acm2 runs` | Manage runs (create, list, start, stop) |
| `acm2 docs` | Manage documents |
| `acm2 eval` | Trigger and query evaluations |
| `acm2 reports` | Access reports |
| `acm2 config` | Manage configuration |

---

## 2. Scope

### 2.1 In Scope

| Item | Description |
|------|-------------|
| Server management | Start/stop FastAPI server |
| Run lifecycle | Create, list, start, stop, delete runs |
| Document management | Add, remove, list documents |
| Evaluation control | Start eval, check status, view results |
| Report access | List reports, open in browser, export |
| Configuration | Set/get config values, show config file |
| Output formats | Table (human), JSON (machine), plain (piping) |
| Shell completion | PowerShell tab completion |

### 2.2 Out of Scope

| Item | Rationale |
|------|-----------|
| Direct database access | API-first architecture |
| Direct file manipulation | Goes through StorageProvider API |
| GUI elements in terminal | Use Web GUI for visual interfaces |

---

## 3. Prerequisites

### 3.1 Required Steps

| Step | Provides |
|------|----------|
| **Step 6** | FastAPI backend project structure |
| **Step 7** | Run/Document API endpoints |
| **Step 9** | FPF adapter (for `acm2 runs start`) |
| **Step 10** | Evaluation API (for `acm2 eval`) |

### 3.2 Technical Requirements

| Requirement | Version |
|-------------|---------|
| Python | 3.11+ |
| Windows | 10/11 or Server 2019+ |
| PowerShell | 5.1+ (for completion) |

### 3.3 Dependencies

```toml
# pyproject.toml
[project]
dependencies = [
    "typer[all]>=0.9.0",     # CLI framework with rich support
    "rich>=13.0.0",           # Pretty terminal output
    "httpx>=0.25.0",          # Async HTTP client
    "pydantic>=2.0.0",        # Config validation
    "pyyaml>=6.0",            # Config file parsing
]
```

---

## 4. CLI Framework Selection

### 4.1 Typer (Recommended)

**Typer** is the recommended CLI framework for ACM 2.0.

| Feature | Benefit |
|---------|---------|
| Type hints | Commands defined with Python type annotations |
| Auto-generated help | `--help` generated from docstrings and types |
| Rich integration | Beautiful output, progress bars, tables |
| Click-compatible | Built on Click, can use Click plugins |
| Shell completion | Built-in completion for PowerShell, bash, zsh |

### 4.2 Basic Typer Application

```python
# acm2/cli/main.py

import typer
from rich.console import Console

app = typer.Typer(
    name="acm2",
    help="ACM 2.0 - Document Generation and Evaluation System",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

console = Console()

# Import and register command groups
from acm2.cli.commands import serve, runs, docs, eval, reports, config

app.add_typer(serve.app, name="serve", help="Start the ACM 2.0 server")
app.add_typer(runs.app, name="runs", help="Manage runs")
app.add_typer(docs.app, name="docs", help="Manage documents")
app.add_typer(eval.app, name="eval", help="Evaluation commands")
app.add_typer(reports.app, name="reports", help="Report commands")
app.add_typer(config.app, name="config", help="Configuration commands")


@app.callback()
def main(
    ctx: typer.Context,
    api_url: str = typer.Option(
        None,
        "--api-url",
        envvar="ACM2_API_URL",
        help="API server URL (default: http://localhost:8000)"
    ),
    format: str = typer.Option(
        "table",
        "--format", "-f",
        help="Output format: table, json, plain"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Show verbose output"
    ),
):
    """ACM 2.0 Command Line Interface."""
    # Store global options in context for subcommands
    ctx.ensure_object(dict)
    ctx.obj["api_url"] = api_url or "http://localhost:8000"
    ctx.obj["format"] = format
    ctx.obj["verbose"] = verbose


def cli():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    cli()
```

### 4.3 Entry Point Configuration

```toml
# pyproject.toml
[project.scripts]
acm2 = "acm2.cli.main:cli"
```

After installation, `acm2` command is available system-wide.

---

## 5. Command Structure

### 5.1 Command Hierarchy

```
acm2
├── serve                    # Start server (special: no subcommands)
├── runs
│   ├── list                 # List all runs
│   ├── create               # Create new run
│   ├── get <run_id>         # Get run details
│   ├── start <run_id>       # Start generation
│   ├── stop <run_id>        # Stop running run
│   ├── delete <run_id>      # Delete run
│   └── watch <run_id>       # Watch run progress (live)
├── docs
│   ├── list [run_id]        # List documents
│   ├── add <run_id> <path>  # Add document to run
│   ├── remove <run_id> <doc_id>  # Remove document
│   └── status <run_id>      # Per-document status
├── eval
│   ├── start <run_id>       # Start evaluation
│   ├── status <run_id>      # Check eval progress
│   ├── results <run_id>     # Show scores/rankings
│   └── cancel <run_id>      # Cancel evaluation
├── reports
│   ├── list <run_id>        # List reports
│   ├── open <report_id>     # Open in browser
│   └── export <run_id>      # Export to file
└── config
    ├── show                 # Show all config
    ├── get <key>            # Get config value
    ├── set <key> <value>    # Set config value
    └── path                 # Show config file path
```

### 5.2 Global Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--api-url` | | API server URL | `http://localhost:8000` |
| `--format` | `-f` | Output format | `table` |
| `--verbose` | `-v` | Verbose output | `false` |
| `--help` | `-h` | Show help | |
| `--version` | | Show version | |

### 5.3 Output Formats

| Format | Use Case | Example |
|--------|----------|---------|
| `table` | Human reading in terminal | Rich formatted tables |
| `json` | Scripting, piping to `jq` | Raw JSON output |
| `plain` | Simple scripts, grep | Tab-separated values |

```powershell
# Examples
acm2 runs list                      # Pretty table
acm2 runs list --format json        # JSON for scripts
acm2 runs list -f json | jq '.runs[0].run_id'  # Pipe to jq
```

---

## 6. Server Commands

### 6.1 Command: `acm2 serve`

The `serve` command starts the FastAPI server. This is a **direct command**, not a subcommand group.

```python
# acm2/cli/commands/serve.py

import typer
from typing import Optional

app = typer.Typer()


@app.callback(invoke_without_command=True)
def serve(
    ctx: typer.Context,
    host: str = typer.Option(
        "127.0.0.1",
        "--host", "-h",
        help="Host to bind to"
    ),
    port: int = typer.Option(
        8000,
        "--port", "-p",
        help="Port to bind to"
    ),
    reload: bool = typer.Option(
        False,
        "--reload", "-r",
        help="Enable auto-reload (development mode)"
    ),
    open_browser: bool = typer.Option(
        False,
        "--open", "-o",
        help="Open browser after starting"
    ),
    workers: int = typer.Option(
        1,
        "--workers", "-w",
        help="Number of worker processes"
    ),
):
    """
    Start the ACM 2.0 server.
    
    Examples:
        acm2 serve                    # Start on localhost:8000
        acm2 serve --port 9000        # Custom port
        acm2 serve --reload           # Dev mode with auto-reload
        acm2 serve --open             # Start and open browser
    """
    import uvicorn
    import webbrowser
    from rich.console import Console
    
    console = Console()
    
    url = f"http://{host}:{port}"
    
    console.print(f"[bold green]Starting ACM 2.0 server...[/bold green]")
    console.print(f"  URL: [link={url}]{url}[/link]")
    console.print(f"  API: [link={url}/api/v1]{url}/api/v1[/link]")
    console.print(f"  Docs: [link={url}/docs]{url}/docs[/link]")
    console.print()
    
    if open_browser:
        # Delay browser open until server is ready
        import threading
        import time
        
        def open_after_delay():
            time.sleep(1.5)  # Wait for server to start
            webbrowser.open(url)
        
        threading.Thread(target=open_after_delay, daemon=True).start()
    
    # Start uvicorn
    uvicorn.run(
        "acm2.app.main:create_app",
        factory=True,
        host=host,
        port=port,
        reload=reload,
        workers=workers if not reload else 1,  # Reload requires 1 worker
        log_level="info",
    )
```

### 6.2 Usage Examples

```powershell
# Basic usage
acm2 serve

# Development mode with auto-reload
acm2 serve --reload

# Custom host/port (allow external access)
acm2 serve --host 0.0.0.0 --port 9000

# Start and open browser
acm2 serve --open

# Production with multiple workers
acm2 serve --workers 4
```

### 6.3 Output Example

```
Starting ACM 2.0 server...
  URL: http://127.0.0.1:8000
  API: http://127.0.0.1:8000/api/v1
  Docs: http://127.0.0.1:8000/docs

INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

---

## 7. Run Commands

### 7.1 Command Group: `acm2 runs`

```python
# acm2/cli/commands/runs.py

import typer
from typing import Optional, List
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from acm2.cli.client import ApiClient
from acm2.cli.output import format_output, format_timestamp

app = typer.Typer(help="Manage runs")
console = Console()


@app.command("list")
def list_runs(
    ctx: typer.Context,
    status: Optional[str] = typer.Option(
        None, "--status", "-s",
        help="Filter by status: pending, running, completed, failed"
    ),
    project: Optional[str] = typer.Option(
        None, "--project", "-p",
        help="Filter by project ID"
    ),
    limit: int = typer.Option(
        20, "--limit", "-n",
        help="Maximum number of runs to show"
    ),
    since: Optional[str] = typer.Option(
        None, "--since",
        help="Show runs since date (YYYY-MM-DD)"
    ),
):
    """
    List all runs.
    
    Examples:
        acm2 runs list
        acm2 runs list --status running
        acm2 runs list --project my-project --limit 50
    """
    client = ApiClient(ctx.obj["api_url"])
    
    params = {"limit": limit}
    if status:
        params["status"] = status
    if project:
        params["project_id"] = project
    if since:
        params["since"] = since
    
    response = client.get("/api/v1/runs", params=params)
    runs = response.json()["runs"]
    
    if ctx.obj["format"] == "json":
        console.print_json(data=runs)
        return
    
    if not runs:
        console.print("[dim]No runs found.[/dim]")
        return
    
    table = Table(title="Runs")
    table.add_column("Run ID", style="cyan", no_wrap=True)
    table.add_column("Title", style="white")
    table.add_column("Status", style="bold")
    table.add_column("Docs", justify="right")
    table.add_column("Created", style="dim")
    
    for run in runs:
        status_style = {
            "pending": "yellow",
            "running": "blue",
            "completed": "green",
            "failed": "red",
        }.get(run["status"], "white")
        
        table.add_row(
            run["run_id"][:8],
            run.get("title", "-"),
            f"[{status_style}]{run['status']}[/{status_style}]",
            str(run.get("document_count", "?")),
            format_timestamp(run["created_at"]),
        )
    
    console.print(table)


@app.command("create")
def create_run(
    ctx: typer.Context,
    title: str = typer.Option(
        ..., "--title", "-t",
        help="Run title"
    ),
    project: str = typer.Option(
        ..., "--project", "-p",
        help="Project ID"
    ),
    generators: List[str] = typer.Option(
        ["fpf"], "--generator", "-g",
        help="Generators to use (fpf, gptr)"
    ),
    iterations: int = typer.Option(
        1, "--iterations", "-i",
        help="Number of iterations per generator"
    ),
    tags: Optional[List[str]] = typer.Option(
        None, "--tag",
        help="Tags for the run"
    ),
):
    """
    Create a new run.
    
    Examples:
        acm2 runs create --title "My Run" --project my-project
        acm2 runs create -t "Test" -p proj -g fpf -g gptr -i 3
    """
    client = ApiClient(ctx.obj["api_url"])
    
    payload = {
        "title": title,
        "project_id": project,
        "config": {
            "generators": generators,
            "iterations": iterations,
        },
        "tags": tags or [],
    }
    
    response = client.post("/api/v1/runs", json=payload)
    run = response.json()
    
    if ctx.obj["format"] == "json":
        console.print_json(data=run)
        return
    
    console.print(f"[green]✓[/green] Created run: [cyan]{run['run_id']}[/cyan]")
    console.print(f"  Title: {run['title']}")
    console.print(f"  Project: {run['project_id']}")
    console.print(f"\nNext: Add documents with [bold]acm2 docs add {run['run_id']} <path>[/bold]")


@app.command("get")
def get_run(
    ctx: typer.Context,
    run_id: str = typer.Argument(..., help="Run ID"),
):
    """
    Get details of a specific run.
    
    Examples:
        acm2 runs get abc123
    """
    client = ApiClient(ctx.obj["api_url"])
    response = client.get(f"/api/v1/runs/{run_id}")
    run = response.json()
    
    if ctx.obj["format"] == "json":
        console.print_json(data=run)
        return
    
    console.print(f"[bold]Run: {run['run_id']}[/bold]")
    console.print(f"  Title: {run.get('title', '-')}")
    console.print(f"  Project: {run['project_id']}")
    console.print(f"  Status: {run['status']}")
    console.print(f"  Documents: {run.get('document_count', '?')}")
    console.print(f"  Created: {format_timestamp(run['created_at'])}")
    
    if run.get("config"):
        console.print(f"\n[bold]Config:[/bold]")
        console.print(f"  Generators: {', '.join(run['config'].get('generators', []))}")
        console.print(f"  Iterations: {run['config'].get('iterations', 1)}")


@app.command("start")
def start_run(
    ctx: typer.Context,
    run_id: str = typer.Argument(..., help="Run ID"),
    wait: bool = typer.Option(
        False, "--wait", "-w",
        help="Wait for completion"
    ),
):
    """
    Start generation for a run.
    
    Examples:
        acm2 runs start abc123
        acm2 runs start abc123 --wait
    """
    client = ApiClient(ctx.obj["api_url"])
    response = client.post(f"/api/v1/runs/{run_id}/start")
    
    console.print(f"[green]✓[/green] Started run: [cyan]{run_id}[/cyan]")
    
    if wait:
        _watch_run(client, run_id)


@app.command("stop")
def stop_run(
    ctx: typer.Context,
    run_id: str = typer.Argument(..., help="Run ID"),
):
    """Stop a running run."""
    client = ApiClient(ctx.obj["api_url"])
    response = client.post(f"/api/v1/runs/{run_id}/stop")
    console.print(f"[yellow]⏹[/yellow] Stopped run: [cyan]{run_id}[/cyan]")


@app.command("delete")
def delete_run(
    ctx: typer.Context,
    run_id: str = typer.Argument(..., help="Run ID"),
    force: bool = typer.Option(
        False, "--force", "-f",
        help="Skip confirmation"
    ),
):
    """Delete a run and all its artifacts."""
    if not force:
        confirm = typer.confirm(f"Delete run {run_id}?")
        if not confirm:
            raise typer.Abort()
    
    client = ApiClient(ctx.obj["api_url"])
    client.delete(f"/api/v1/runs/{run_id}")
    console.print(f"[red]✗[/red] Deleted run: [cyan]{run_id}[/cyan]")


@app.command("watch")
def watch_run(
    ctx: typer.Context,
    run_id: str = typer.Argument(..., help="Run ID"),
):
    """Watch run progress in real-time."""
    client = ApiClient(ctx.obj["api_url"])
    _watch_run(client, run_id)


def _watch_run(client: ApiClient, run_id: str):
    """Internal: Poll and display run progress."""
    import time
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Running...", total=None)
        
        while True:
            response = client.get(f"/api/v1/runs/{run_id}")
            run = response.json()
            
            status = run["status"]
            progress.update(task, description=f"Status: {status}")
            
            if status in ("completed", "failed"):
                break
            
            time.sleep(2)
    
    if status == "completed":
        console.print(f"\n[green]✓[/green] Run completed!")
    else:
        console.print(f"\n[red]✗[/red] Run failed")
```

### 7.2 Usage Examples

```powershell
# List runs
acm2 runs list
acm2 runs list --status running
acm2 runs list --project my-project --limit 10

# Create run
acm2 runs create --title "Policy Docs" --project firstpub -g fpf -i 3

# Get run details
acm2 runs get abc123

# Start and watch
acm2 runs start abc123 --wait

# Delete
acm2 runs delete abc123 --force
```

---

## 8. Document Commands

### 8.1 Command Group: `acm2 docs`

```python
# acm2/cli/commands/docs.py

import typer
from typing import Optional
from pathlib import Path
from rich.console import Console
from rich.table import Table

from acm2.cli.client import ApiClient
from acm2.cli.output import format_timestamp, status_icon

app = typer.Typer(help="Manage documents")
console = Console()


@app.command("list")
def list_docs(
    ctx: typer.Context,
    run_id: Optional[str] = typer.Argument(
        None,
        help="Run ID (optional, lists all docs if omitted)"
    ),
):
    """
    List documents, optionally filtered by run.
    
    Examples:
        acm2 docs list              # All documents
        acm2 docs list abc123       # Documents in run abc123
    """
    client = ApiClient(ctx.obj["api_url"])
    
    if run_id:
        response = client.get(f"/api/v1/runs/{run_id}/documents")
    else:
        response = client.get("/api/v1/documents")
    
    docs = response.json()["documents"]
    
    if ctx.obj["format"] == "json":
        console.print_json(data=docs)
        return
    
    if not docs:
        console.print("[dim]No documents found.[/dim]")
        return
    
    table = Table(title=f"Documents{f' in Run {run_id[:8]}' if run_id else ''}")
    table.add_column("Doc ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="white")
    table.add_column("Path", style="dim")
    table.add_column("Status", style="bold")
    
    for doc in docs:
        status = doc.get("status", "pending")
        table.add_row(
            doc["document_id"][:8],
            doc["name"],
            doc.get("path", "-")[:40],
            f"{status_icon(status)} {status}",
        )
    
    console.print(table)


@app.command("add")
def add_doc(
    ctx: typer.Context,
    run_id: str = typer.Argument(..., help="Run ID"),
    path: str = typer.Argument(..., help="Document path (local or GitHub)"),
    name: Optional[str] = typer.Option(
        None, "--name", "-n",
        help="Document name (defaults to filename)"
    ),
):
    """
    Add a document to a run.
    
    Examples:
        acm2 docs add abc123 ./docs/policy.md
        acm2 docs add abc123 github://owner/repo/docs/policy.md
        acm2 docs add abc123 ./docs/policy.md --name "Policy Doc"
    """
    client = ApiClient(ctx.obj["api_url"])
    
    # Determine document name
    doc_name = name or Path(path).stem
    
    payload = {
        "path": path,
        "name": doc_name,
    }
    
    response = client.post(f"/api/v1/runs/{run_id}/documents", json=payload)
    doc = response.json()
    
    if ctx.obj["format"] == "json":
        console.print_json(data=doc)
        return
    
    console.print(f"[green]✓[/green] Added document: [cyan]{doc['document_id']}[/cyan]")
    console.print(f"  Name: {doc['name']}")
    console.print(f"  Path: {doc['path']}")


@app.command("remove")
def remove_doc(
    ctx: typer.Context,
    run_id: str = typer.Argument(..., help="Run ID"),
    doc_id: str = typer.Argument(..., help="Document ID"),
):
    """Remove a document from a run."""
    client = ApiClient(ctx.obj["api_url"])
    client.delete(f"/api/v1/runs/{run_id}/documents/{doc_id}")
    console.print(f"[red]✗[/red] Removed document: [cyan]{doc_id}[/cyan]")


@app.command("status")
def doc_status(
    ctx: typer.Context,
    run_id: str = typer.Argument(..., help="Run ID"),
):
    """
    Show per-document generation status.
    
    Examples:
        acm2 docs status abc123
    """
    client = ApiClient(ctx.obj["api_url"])
    response = client.get(f"/api/v1/runs/{run_id}/documents/status")
    docs = response.json()["documents"]
    
    if ctx.obj["format"] == "json":
        console.print_json(data=docs)
        return
    
    table = Table(title=f"Document Status - Run {run_id[:8]}")
    table.add_column("Document", style="white")
    table.add_column("FPF", justify="center")
    table.add_column("GPT-R", justify="center")
    table.add_column("Artifacts", justify="right")
    
    for doc in docs:
        fpf_status = doc.get("fpf_status", "-")
        gptr_status = doc.get("gptr_status", "-")
        
        table.add_row(
            doc["name"],
            f"{status_icon(fpf_status)} {fpf_status}",
            f"{status_icon(gptr_status)} {gptr_status}",
            str(doc.get("artifact_count", 0)),
        )
    
    console.print(table)
```

### 8.2 Usage Examples

```powershell
# List all docs in a run
acm2 docs list abc123

# Add documents
acm2 docs add abc123 ./docs/policy.md
acm2 docs add abc123 ./docs/*.md  # Shell glob expansion

# Check per-document status
acm2 docs status abc123

# Remove a document
acm2 docs remove abc123 def456
```

---

## 9. Evaluation Commands

### 9.1 Command Group: `acm2 eval`

```python
# acm2/cli/commands/eval.py

import typer
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from acm2.cli.client import ApiClient
from acm2.cli.output import format_score

app = typer.Typer(help="Evaluation commands")
console = Console()


@app.command("start")
def start_eval(
    ctx: typer.Context,
    run_id: str = typer.Argument(..., help="Run ID"),
    wait: bool = typer.Option(
        False, "--wait", "-w",
        help="Wait for completion"
    ),
    skip_single: bool = typer.Option(
        False, "--skip-single",
        help="Skip single-doc evaluation"
    ),
    skip_pairwise: bool = typer.Option(
        False, "--skip-pairwise",
        help="Skip pairwise evaluation"
    ),
):
    """
    Start evaluation for a run.
    
    Examples:
        acm2 eval start abc123
        acm2 eval start abc123 --wait
        acm2 eval start abc123 --skip-pairwise
    """
    client = ApiClient(ctx.obj["api_url"])
    
    payload = {
        "skip_single_doc": skip_single,
        "skip_pairwise": skip_pairwise,
    }
    
    response = client.post(f"/api/v1/runs/{run_id}/evaluate", json=payload)
    
    console.print(f"[green]✓[/green] Started evaluation for run: [cyan]{run_id}[/cyan]")
    
    if wait:
        _watch_eval(client, run_id)


@app.command("status")
def eval_status(
    ctx: typer.Context,
    run_id: str = typer.Argument(..., help="Run ID"),
):
    """Check evaluation progress."""
    client = ApiClient(ctx.obj["api_url"])
    response = client.get(f"/api/v1/runs/{run_id}/evaluate/status")
    status = response.json()
    
    if ctx.obj["format"] == "json":
        console.print_json(data=status)
        return
    
    console.print(f"[bold]Evaluation Status - Run {run_id[:8]}[/bold]")
    console.print(f"  Phase: {status['phase']}")
    console.print(f"  Progress: {status['progress']}%")
    console.print(f"  Single-doc: {status.get('single_doc_status', '-')}")
    console.print(f"  Pairwise: {status.get('pairwise_status', '-')}")


@app.command("results")
def eval_results(
    ctx: typer.Context,
    run_id: str = typer.Argument(..., help="Run ID"),
    top: int = typer.Option(
        10, "--top", "-n",
        help="Show top N results"
    ),
    sort_by: str = typer.Option(
        "elo", "--sort", "-s",
        help="Sort by: elo, score, name"
    ),
):
    """
    Show evaluation scores and rankings.
    
    Examples:
        acm2 eval results abc123
        acm2 eval results abc123 --top 5
        acm2 eval results abc123 --sort score
    """
    client = ApiClient(ctx.obj["api_url"])
    response = client.get(
        f"/api/v1/runs/{run_id}/evaluate/results",
        params={"limit": top, "sort_by": sort_by}
    )
    results = response.json()
    
    if ctx.obj["format"] == "json":
        console.print_json(data=results)
        return
    
    # Rankings table
    console.print(f"\n[bold]Rankings - Run {run_id[:8]}[/bold]")
    
    table = Table()
    table.add_column("Rank", style="bold", justify="right")
    table.add_column("Artifact", style="cyan")
    table.add_column("Generator", style="dim")
    table.add_column("Elo", justify="right")
    table.add_column("Avg Score", justify="right")
    table.add_column("W-L", justify="center")
    
    for i, result in enumerate(results["rankings"], 1):
        elo = result.get("elo_rating", 1500)
        score = result.get("average_score", 0)
        wins = result.get("wins", 0)
        losses = result.get("losses", 0)
        
        # Color coding for top 3
        rank_style = {1: "gold1", 2: "silver", 3: "orange3"}.get(i, "white")
        
        table.add_row(
            f"[{rank_style}]{i}[/{rank_style}]",
            result["artifact_id"][:12],
            result["generator"],
            format_score(elo, base=1500),
            format_score(score, base=5),
            f"{wins}-{losses}",
        )
    
    console.print(table)
    
    # Summary
    console.print(f"\n[dim]Showing top {len(results['rankings'])} of {results['total']} artifacts[/dim]")


@app.command("cancel")
def cancel_eval(
    ctx: typer.Context,
    run_id: str = typer.Argument(..., help="Run ID"),
):
    """Cancel a running evaluation."""
    client = ApiClient(ctx.obj["api_url"])
    client.post(f"/api/v1/runs/{run_id}/evaluate/cancel")
    console.print(f"[yellow]⏹[/yellow] Cancelled evaluation for run: [cyan]{run_id}[/cyan]")


def _watch_eval(client: ApiClient, run_id: str):
    """Internal: Poll and display eval progress."""
    import time
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Evaluating...", total=None)
        
        while True:
            response = client.get(f"/api/v1/runs/{run_id}/evaluate/status")
            status = response.json()
            
            phase = status.get("phase", "unknown")
            pct = status.get("progress", 0)
            progress.update(task, description=f"{phase}: {pct}%")
            
            if phase in ("completed", "failed"):
                break
            
            time.sleep(2)
    
    if phase == "completed":
        console.print(f"\n[green]✓[/green] Evaluation completed!")
        # Show quick summary
        eval_results(typer.Context({}), run_id, top=5, sort_by="elo")
    else:
        console.print(f"\n[red]✗[/red] Evaluation failed")
```

### 9.2 Usage Examples

```powershell
# Start evaluation
acm2 eval start abc123
acm2 eval start abc123 --wait

# Check status
acm2 eval status abc123

# View results
acm2 eval results abc123
acm2 eval results abc123 --top 5 --sort score

# Cancel
acm2 eval cancel abc123
```

### 9.3 Results Output Example

```
Rankings - Run abc123

  Rank  Artifact       Generator  Elo     Avg Score  W-L
  1     art_a1b2c3...  fpf        1623    8.2        5-1
  2     art_d4e5f6...  gptr       1589    7.9        4-2
  3     art_g7h8i9...  fpf        1534    7.5        3-3
  4     art_j0k1l2...  gptr       1478    7.1        2-4
  5     art_m3n4o5...  fpf        1421    6.8        1-5

Showing top 5 of 12 artifacts
```

---

## 10. Report Commands

### 10.1 Command Group: `acm2 reports`

```python
# acm2/cli/commands/reports.py

import typer
from typing import Optional
from pathlib import Path
from rich.console import Console
from rich.table import Table

from acm2.cli.client import ApiClient
from acm2.cli.output import format_timestamp, format_file_size

app = typer.Typer(help="Report commands")
console = Console()


@app.command("list")
def list_reports(
    ctx: typer.Context,
    run_id: str = typer.Argument(..., help="Run ID"),
):
    """
    List reports for a run.
    
    Examples:
        acm2 reports list abc123
    """
    client = ApiClient(ctx.obj["api_url"])
    response = client.get(f"/api/v1/runs/{run_id}/reports")
    reports = response.json()["reports"]
    
    if ctx.obj["format"] == "json":
        console.print_json(data=reports)
        return
    
    if not reports:
        console.print("[dim]No reports found.[/dim]")
        return
    
    table = Table(title=f"Reports - Run {run_id[:8]}")
    table.add_column("Report ID", style="cyan", no_wrap=True)
    table.add_column("Type", style="white")
    table.add_column("Format", style="dim")
    table.add_column("Size", justify="right")
    table.add_column("Created", style="dim")
    
    for report in reports:
        table.add_row(
            report["report_id"][:12],
            report["report_type"],
            report["format"],
            format_file_size(report.get("size_bytes", 0)),
            format_timestamp(report["created_at"]),
        )
    
    console.print(table)


@app.command("open")
def open_report(
    ctx: typer.Context,
    report_id: str = typer.Argument(..., help="Report ID"),
):
    """
    Open a report in the default browser.
    
    Examples:
        acm2 reports open rpt_abc123
    """
    import webbrowser
    
    api_url = ctx.obj["api_url"]
    report_url = f"{api_url}/api/v1/reports/{report_id}/view"
    
    console.print(f"Opening report in browser: [link={report_url}]{report_url}[/link]")
    webbrowser.open(report_url)


@app.command("download")
def download_report(
    ctx: typer.Context,
    report_id: str = typer.Argument(..., help="Report ID"),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o",
        help="Output file path (defaults to report filename)"
    ),
):
    """
    Download a report to a local file.
    
    Examples:
        acm2 reports download rpt_abc123
        acm2 reports download rpt_abc123 -o ./my_report.html
    """
    client = ApiClient(ctx.obj["api_url"])
    
    # Get report metadata first
    meta_response = client.get(f"/api/v1/reports/{report_id}")
    meta = meta_response.json()
    
    # Determine output path
    if output is None:
        output = Path(meta.get("filename", f"{report_id}.html"))
    
    # Download content
    content_response = client.get(f"/api/v1/reports/{report_id}/download")
    
    output.write_bytes(content_response.content)
    console.print(f"[green]✓[/green] Downloaded: [cyan]{output}[/cyan]")
    console.print(f"  Size: {format_file_size(len(content_response.content))}")


@app.command("export")
def export_results(
    ctx: typer.Context,
    run_id: str = typer.Argument(..., help="Run ID"),
    format: str = typer.Option(
        "csv", "--format", "-f",
        help="Export format: csv, json, xlsx"
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o",
        help="Output file path"
    ),
):
    """
    Export evaluation results to a file.
    
    Examples:
        acm2 reports export abc123 --format csv
        acm2 reports export abc123 -f json -o results.json
    """
    client = ApiClient(ctx.obj["api_url"])
    
    # Determine output path
    if output is None:
        output = Path(f"run_{run_id[:8]}_results.{format}")
    
    response = client.get(
        f"/api/v1/runs/{run_id}/evaluate/results/export",
        params={"format": format}
    )
    
    output.write_bytes(response.content)
    console.print(f"[green]✓[/green] Exported: [cyan]{output}[/cyan]")
    console.print(f"  Format: {format.upper()}")
    console.print(f"  Size: {format_file_size(len(response.content))}")
```

### 10.2 Usage Examples

```powershell
# List reports
acm2 reports list abc123

# Open in browser
acm2 reports open rpt_xyz789

# Download
acm2 reports download rpt_xyz789
acm2 reports download rpt_xyz789 -o ./my_report.html

# Export results
acm2 reports export abc123 --format csv
acm2 reports export abc123 -f json -o ./results.json
```

---

## 11. Config Commands

### 11.1 Command Group: `acm2 config`

```python
# acm2/cli/commands/config.py

import typer
from typing import Optional
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.syntax import Syntax
import yaml

from acm2.cli.config import ConfigManager, get_config_path

app = typer.Typer(help="Configuration commands")
console = Console()


@app.command("show")
def show_config(
    ctx: typer.Context,
):
    """
    Show current configuration.
    
    Examples:
        acm2 config show
    """
    config_manager = ConfigManager()
    config = config_manager.load()
    
    if ctx.obj["format"] == "json":
        console.print_json(data=config)
        return
    
    console.print(f"[bold]Configuration[/bold]")
    console.print(f"  File: {get_config_path()}")
    console.print()
    
    # Display as YAML for readability
    yaml_str = yaml.dump(config, default_flow_style=False, sort_keys=False)
    syntax = Syntax(yaml_str, "yaml", theme="monokai", line_numbers=False)
    console.print(syntax)


@app.command("get")
def get_config(
    ctx: typer.Context,
    key: str = typer.Argument(..., help="Configuration key (dot notation)"),
):
    """
    Get a configuration value.
    
    Examples:
        acm2 config get api_url
        acm2 config get defaults.project
        acm2 config get generators.fpf.model
    """
    config_manager = ConfigManager()
    value = config_manager.get(key)
    
    if value is None:
        console.print(f"[yellow]Key not found:[/yellow] {key}")
        raise typer.Exit(1)
    
    if ctx.obj["format"] == "json":
        console.print_json(data={"key": key, "value": value})
    else:
        console.print(f"{key} = {value}")


@app.command("set")
def set_config(
    ctx: typer.Context,
    key: str = typer.Argument(..., help="Configuration key (dot notation)"),
    value: str = typer.Argument(..., help="Value to set"),
):
    """
    Set a configuration value.
    
    Examples:
        acm2 config set api_url http://localhost:9000
        acm2 config set defaults.project my-project
        acm2 config set generators.fpf.iterations 3
    """
    config_manager = ConfigManager()
    
    # Try to parse value as JSON for complex types
    import json
    try:
        parsed_value = json.loads(value)
    except json.JSONDecodeError:
        parsed_value = value
    
    config_manager.set(key, parsed_value)
    config_manager.save()
    
    console.print(f"[green]✓[/green] Set {key} = {parsed_value}")


@app.command("unset")
def unset_config(
    ctx: typer.Context,
    key: str = typer.Argument(..., help="Configuration key to remove"),
):
    """Remove a configuration value."""
    config_manager = ConfigManager()
    config_manager.unset(key)
    config_manager.save()
    
    console.print(f"[green]✓[/green] Removed: {key}")


@app.command("path")
def config_path(
    ctx: typer.Context,
):
    """Show configuration file path."""
    path = get_config_path()
    console.print(f"{path}")


@app.command("init")
def init_config(
    ctx: typer.Context,
    force: bool = typer.Option(
        False, "--force", "-f",
        help="Overwrite existing config"
    ),
):
    """
    Create default configuration file.
    
    Examples:
        acm2 config init
        acm2 config init --force
    """
    config_path = get_config_path()
    
    if config_path.exists() and not force:
        console.print(f"[yellow]Config already exists:[/yellow] {config_path}")
        console.print("Use --force to overwrite")
        raise typer.Exit(1)
    
    config_manager = ConfigManager()
    config_manager.create_default()
    
    console.print(f"[green]✓[/green] Created config: {config_path}")
```

### 11.2 Configuration File Structure

```yaml
# %APPDATA%\acm2\config.yaml

# API server settings
api_url: http://localhost:8000

# Output preferences
output:
  format: table        # table, json, plain
  colors: true
  pager: false

# Default values for new runs
defaults:
  project: null
  generators:
    - fpf
  iterations: 1
  
# Generator-specific settings
generators:
  fpf:
    model: gpt-4o
    temperature: 0.7
  gptr:
    model: gpt-4o
    mode: standard     # standard, deep

# Evaluation settings
evaluation:
  judges:
    - gpt-4o
  iterations: 3
  skip_pairwise: false
```

### 11.3 ConfigManager Implementation

```python
# acm2/cli/config.py

from pathlib import Path
from typing import Any, Optional
import yaml
import os


def get_config_path() -> Path:
    """Get the configuration file path."""
    # Windows: %APPDATA%\acm2\config.yaml
    appdata = os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")
    return Path(appdata) / "acm2" / "config.yaml"


DEFAULT_CONFIG = {
    "api_url": "http://localhost:8000",
    "output": {
        "format": "table",
        "colors": True,
        "pager": False,
    },
    "defaults": {
        "project": None,
        "generators": ["fpf"],
        "iterations": 1,
    },
    "generators": {
        "fpf": {"model": "gpt-4o", "temperature": 0.7},
        "gptr": {"model": "gpt-4o", "mode": "standard"},
    },
    "evaluation": {
        "judges": ["gpt-4o"],
        "iterations": 3,
        "skip_pairwise": False,
    },
}


class ConfigManager:
    """Manages CLI configuration."""
    
    def __init__(self, path: Optional[Path] = None):
        self._path = path or get_config_path()
        self._config: dict = {}
    
    def load(self) -> dict:
        """Load configuration from file."""
        if self._path.exists():
            with open(self._path) as f:
                self._config = yaml.safe_load(f) or {}
        else:
            self._config = DEFAULT_CONFIG.copy()
        return self._config
    
    def save(self) -> None:
        """Save configuration to file."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w") as f:
            yaml.dump(self._config, f, default_flow_style=False, sort_keys=False)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a value using dot notation (e.g., 'defaults.project')."""
        self.load()
        parts = key.split(".")
        value = self._config
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return default
        return value
    
    def set(self, key: str, value: Any) -> None:
        """Set a value using dot notation."""
        self.load()
        parts = key.split(".")
        config = self._config
        for part in parts[:-1]:
            if part not in config:
                config[part] = {}
            config = config[part]
        config[parts[-1]] = value
    
    def unset(self, key: str) -> None:
        """Remove a value using dot notation."""
        self.load()
        parts = key.split(".")
        config = self._config
        for part in parts[:-1]:
            if part not in config:
                return
            config = config[part]
        config.pop(parts[-1], None)
    
    def create_default(self) -> None:
        """Create default configuration file."""
        self._config = DEFAULT_CONFIG.copy()
        self.save()
```

### 11.4 Usage Examples

```powershell
# Show all config
acm2 config show

# Get specific values
acm2 config get api_url
acm2 config get defaults.project
acm2 config get generators.fpf.model

# Set values
acm2 config set api_url http://localhost:9000
acm2 config set defaults.project my-project
acm2 config set evaluation.iterations 5

# Initialize config
acm2 config init
acm2 config init --force

# Show config file path
acm2 config path
```

---

## 12. API Client Integration

### 12.1 API Client Class

```python
# acm2/cli/client.py

import httpx
from typing import Optional, Any
from rich.console import Console

console = Console()


class ApiError(Exception):
    """API error with status code and message."""
    
    def __init__(self, status_code: int, message: str, details: Optional[dict] = None):
        self.status_code = status_code
        self.message = message
        self.details = details or {}
        super().__init__(f"API Error {status_code}: {message}")


class ApiClient:
    """HTTP client for ACM 2.0 API."""
    
    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._client = httpx.Client(timeout=timeout)
    
    def _headers(self) -> dict:
        """Build request headers."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers
    
    def _handle_response(self, response: httpx.Response) -> httpx.Response:
        """Handle response, raising ApiError for non-2xx status."""
        if response.is_success:
            return response
        
        # Try to parse error details
        try:
            error_data = response.json()
            message = error_data.get("detail", response.reason_phrase)
            details = error_data
        except Exception:
            message = response.reason_phrase
            details = {}
        
        raise ApiError(response.status_code, message, details)
    
    def get(self, path: str, params: Optional[dict] = None) -> httpx.Response:
        """Make GET request."""
        url = f"{self._base_url}{path}"
        response = self._client.get(url, headers=self._headers(), params=params)
        return self._handle_response(response)
    
    def post(self, path: str, json: Optional[dict] = None) -> httpx.Response:
        """Make POST request."""
        url = f"{self._base_url}{path}"
        response = self._client.post(url, headers=self._headers(), json=json)
        return self._handle_response(response)
    
    def put(self, path: str, json: Optional[dict] = None) -> httpx.Response:
        """Make PUT request."""
        url = f"{self._base_url}{path}"
        response = self._client.put(url, headers=self._headers(), json=json)
        return self._handle_response(response)
    
    def delete(self, path: str) -> httpx.Response:
        """Make DELETE request."""
        url = f"{self._base_url}{path}"
        response = self._client.delete(url, headers=self._headers())
        return self._handle_response(response)
    
    def health_check(self) -> bool:
        """Check if API server is reachable."""
        try:
            response = self.get("/api/v1/health")
            return response.json().get("status") == "ok"
        except Exception:
            return False


class AsyncApiClient:
    """Async HTTP client for ACM 2.0 API."""
    
    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
    
    async def __aenter__(self):
        self._client = httpx.AsyncClient(timeout=self._timeout)
        return self
    
    async def __aexit__(self, *args):
        await self._client.aclose()
    
    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers
    
    async def get(self, path: str, params: Optional[dict] = None) -> httpx.Response:
        url = f"{self._base_url}{path}"
        response = await self._client.get(url, headers=self._headers(), params=params)
        return self._handle_response(response)
    
    async def post(self, path: str, json: Optional[dict] = None) -> httpx.Response:
        url = f"{self._base_url}{path}"
        response = await self._client.post(url, headers=self._headers(), json=json)
        return self._handle_response(response)
    
    def _handle_response(self, response: httpx.Response) -> httpx.Response:
        if response.is_success:
            return response
        try:
            error_data = response.json()
            message = error_data.get("detail", response.reason_phrase)
        except Exception:
            message = response.reason_phrase
        raise ApiError(response.status_code, message)
```

### 12.2 Connection Verification

```python
# In CLI commands, verify connection before operations

def ensure_server_running(client: ApiClient) -> None:
    """Verify server is running, exit with helpful message if not."""
    if not client.health_check():
        console.print("[red]Error:[/red] Cannot connect to ACM 2.0 server")
        console.print(f"  URL: {client._base_url}")
        console.print()
        console.print("Start the server with: [bold]acm2 serve[/bold]")
        raise typer.Exit(1)
```

### 12.3 Environment Variable Support

```python
# API URL and key from environment

import os

def get_api_url() -> str:
    """Get API URL from env or default."""
    return os.environ.get("ACM2_API_URL", "http://localhost:8000")

def get_api_key() -> Optional[str]:
    """Get API key from env."""
    return os.environ.get("ACM2_API_KEY")
```

### 12.4 Usage in Commands

```python
@app.command("list")
def list_runs(ctx: typer.Context):
    # Create client from context options
    client = ApiClient(
        base_url=ctx.obj["api_url"],
        api_key=ctx.obj.get("api_key"),
    )
    
    # Optional: verify server is running
    ensure_server_running(client)
    
    # Make API call
    response = client.get("/api/v1/runs")
    runs = response.json()["runs"]
    # ... display results
```

---

## 13. Output Formatting

### 13.1 Output Module

```python
# acm2/cli/output.py

from typing import Any, Optional
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
import json

console = Console()


def format_output(data: Any, format: str, title: Optional[str] = None) -> None:
    """Format and print data based on output format setting."""
    if format == "json":
        console.print_json(data=data)
    elif format == "plain":
        print_plain(data)
    else:  # table (default)
        print_table(data, title)


def print_plain(data: Any) -> None:
    """Print data as plain text (tab-separated for lists)."""
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                print("\t".join(str(v) for v in item.values()))
            else:
                print(item)
    elif isinstance(data, dict):
        for key, value in data.items():
            print(f"{key}\t{value}")
    else:
        print(data)


def print_table(data: Any, title: Optional[str] = None) -> None:
    """Print data as a Rich table."""
    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
        table = Table(title=title)
        
        # Add columns from first item's keys
        for key in data[0].keys():
            table.add_column(key.replace("_", " ").title())
        
        # Add rows
        for item in data:
            table.add_row(*[str(v) for v in item.values()])
        
        console.print(table)
    elif isinstance(data, dict):
        for key, value in data.items():
            console.print(f"[bold]{key}:[/bold] {value}")
    else:
        console.print(data)


def format_timestamp(timestamp: str) -> str:
    """Format ISO timestamp to human-readable string."""
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        now = datetime.now(dt.tzinfo)
        delta = now - dt
        
        if delta.days == 0:
            if delta.seconds < 60:
                return "just now"
            elif delta.seconds < 3600:
                return f"{delta.seconds // 60}m ago"
            else:
                return f"{delta.seconds // 3600}h ago"
        elif delta.days == 1:
            return "yesterday"
        elif delta.days < 7:
            return f"{delta.days}d ago"
        else:
            return dt.strftime("%Y-%m-%d")
    except Exception:
        return timestamp[:10] if len(timestamp) > 10 else timestamp


def format_file_size(bytes: int) -> str:
    """Format file size to human-readable string."""
    if bytes < 1024:
        return f"{bytes} B"
    elif bytes < 1024 * 1024:
        return f"{bytes / 1024:.1f} KB"
    elif bytes < 1024 * 1024 * 1024:
        return f"{bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{bytes / (1024 * 1024 * 1024):.1f} GB"


def format_score(score: float, base: float = 5.0) -> str:
    """Format score with color coding."""
    if score >= base * 1.2:
        return f"[green]{score:.1f}[/green]"
    elif score >= base:
        return f"[yellow]{score:.1f}[/yellow]"
    else:
        return f"[red]{score:.1f}[/red]"


def status_icon(status: str) -> str:
    """Return icon for status."""
    icons = {
        "pending": "⏳",
        "running": "🔄",
        "completed": "✅",
        "failed": "❌",
        "skipped": "⏭️",
        "cancelled": "🛑",
    }
    return icons.get(status, "•")


def print_error(message: str, details: Optional[str] = None) -> None:
    """Print error message."""
    console.print(f"[red]Error:[/red] {message}")
    if details:
        console.print(f"[dim]{details}[/dim]")


def print_success(message: str) -> None:
    """Print success message."""
    console.print(f"[green]✓[/green] {message}")


def print_warning(message: str) -> None:
    """Print warning message."""
    console.print(f"[yellow]⚠[/yellow] {message}")
```

### 13.2 Progress Display

```python
# acm2/cli/progress.py

from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeRemainingColumn,
)
from rich.console import Console

console = Console()


def create_spinner(description: str = "Working...") -> Progress:
    """Create a spinner for indeterminate progress."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    )


def create_progress_bar(description: str = "Progress") -> Progress:
    """Create a progress bar for determinate progress."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
    )


# Usage example:
# with create_progress_bar() as progress:
#     task = progress.add_task("Processing...", total=100)
#     for i in range(100):
#         progress.update(task, advance=1)
```

### 13.3 JSON Output Mode

When `--format json` is used, output is pure JSON for scripting:

```powershell
# Get run IDs for scripting
$runs = acm2 runs list --format json | ConvertFrom-Json
$runs.runs | ForEach-Object { $_.run_id }

# Pipe to jq (if installed)
acm2 runs get abc123 --format json | jq '.status'

# Use in PowerShell scripts
$run = acm2 runs create -t "Test" -p proj --format json | ConvertFrom-Json
acm2 runs start $run.run_id
```

---

## 14. Interactive Mode

### 14.1 REPL Interface (Optional Enhancement)

```python
# acm2/cli/interactive.py

import typer
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from rich.console import Console
from pathlib import Path

console = Console()

COMMANDS = [
    "runs list", "runs create", "runs get", "runs start", "runs stop", "runs delete",
    "docs list", "docs add", "docs remove", "docs status",
    "eval start", "eval status", "eval results", "eval cancel",
    "reports list", "reports open", "reports export",
    "config show", "config get", "config set",
    "help", "exit", "quit",
]


def interactive_mode(api_url: str):
    """
    Start interactive REPL mode.
    
    Usage:
        acm2 interactive
    """
    console.print("[bold]ACM 2.0 Interactive Mode[/bold]")
    console.print("Type 'help' for commands, 'exit' to quit")
    console.print()
    
    # Setup prompt with history and completion
    history_path = Path.home() / ".acm2_history"
    session = PromptSession(
        history=FileHistory(str(history_path)),
        completer=WordCompleter(COMMANDS, ignore_case=True),
    )
    
    while True:
        try:
            # Get input
            text = session.prompt("acm2> ").strip()
            
            if not text:
                continue
            
            if text in ("exit", "quit"):
                console.print("Goodbye!")
                break
            
            if text == "help":
                print_help()
                continue
            
            # Parse and execute command
            execute_command(text, api_url)
            
        except KeyboardInterrupt:
            console.print("\nUse 'exit' to quit")
        except EOFError:
            break


def execute_command(text: str, api_url: str):
    """Parse and execute a command string."""
    import shlex
    import sys
    from acm2.cli.main import app
    
    # Parse command
    args = shlex.split(text)
    
    # Add global options
    args = ["--api-url", api_url] + args
    
    try:
        # Invoke Typer app
        app(args, standalone_mode=False)
    except SystemExit:
        pass  # Typer exits after command
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")


def print_help():
    """Print help for interactive mode."""
    console.print("[bold]Available Commands:[/bold]")
    console.print()
    console.print("  [cyan]runs[/cyan]     - Manage runs (list, create, get, start, stop, delete)")
    console.print("  [cyan]docs[/cyan]     - Manage documents (list, add, remove, status)")
    console.print("  [cyan]eval[/cyan]     - Evaluation (start, status, results, cancel)")
    console.print("  [cyan]reports[/cyan]  - Reports (list, open, export)")
    console.print("  [cyan]config[/cyan]   - Configuration (show, get, set)")
    console.print()
    console.print("  [dim]help[/dim]     - Show this help")
    console.print("  [dim]exit[/dim]     - Exit interactive mode")
```

### 14.2 Interactive Command Registration

```python
# In acm2/cli/main.py

@app.command("interactive")
def interactive(
    ctx: typer.Context,
):
    """
    Start interactive REPL mode.
    
    Provides a shell with command history and tab completion.
    
    Examples:
        acm2 interactive
    """
    from acm2.cli.interactive import interactive_mode
    interactive_mode(ctx.obj["api_url"])
```

### 14.3 Usage

```powershell
PS> acm2 interactive
ACM 2.0 Interactive Mode
Type 'help' for commands, 'exit' to quit

acm2> runs list
  Run ID    Title         Status     Docs  Created
  abc123    Policy Docs   completed  5     2h ago
  def456    New Run       running    3     10m ago

acm2> runs get abc123
Run: abc123
  Title: Policy Docs
  Status: completed
  ...

acm2> exit
Goodbye!
```

---

## 15. Error Handling

### 15.1 Exit Codes

| Code | Meaning | Example |
|------|---------|---------|
| 0 | Success | Command completed successfully |
| 1 | General error | API error, validation error |
| 2 | Usage error | Invalid arguments, missing required options |
| 3 | Connection error | Cannot connect to server |
| 130 | Interrupted | User pressed Ctrl+C |

### 15.2 Error Handler

```python
# acm2/cli/errors.py

import typer
from rich.console import Console
from rich.panel import Panel
from acm2.cli.client import ApiError

console = Console()


def handle_error(func):
    """Decorator to handle errors in CLI commands."""
    import functools
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ApiError as e:
            handle_api_error(e)
        except ConnectionError as e:
            handle_connection_error(e)
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted[/yellow]")
            raise typer.Exit(130)
        except Exception as e:
            handle_unexpected_error(e, kwargs.get("verbose", False))
    
    return wrapper


def handle_api_error(error: ApiError) -> None:
    """Handle API errors with user-friendly messages."""
    messages = {
        400: "Invalid request",
        401: "Authentication required",
        403: "Permission denied",
        404: "Not found",
        409: "Conflict",
        422: "Validation error",
        429: "Rate limited - please wait",
        500: "Server error",
        503: "Service unavailable",
    }
    
    message = messages.get(error.status_code, error.message)
    
    console.print(f"[red]Error {error.status_code}:[/red] {message}")
    
    # Show details for validation errors
    if error.status_code == 422 and error.details:
        if "detail" in error.details:
            for err in error.details["detail"]:
                loc = " -> ".join(str(x) for x in err.get("loc", []))
                console.print(f"  [dim]{loc}:[/dim] {err.get('msg', '')}")
    
    # Suggest fixes for common errors
    if error.status_code == 404:
        console.print("\n[dim]Tip: Use 'acm2 runs list' to see available runs[/dim]")
    elif error.status_code == 401:
        console.print("\n[dim]Tip: Set API key with 'acm2 config set api_key <key>'[/dim]")
    
    raise typer.Exit(1)


def handle_connection_error(error: Exception) -> None:
    """Handle connection errors."""
    console.print("[red]Connection Error:[/red] Cannot connect to ACM 2.0 server")
    console.print()
    console.print("Possible causes:")
    console.print("  • Server is not running")
    console.print("  • Wrong API URL")
    console.print("  • Firewall blocking connection")
    console.print()
    console.print("Solutions:")
    console.print("  1. Start server: [bold]acm2 serve[/bold]")
    console.print("  2. Check URL: [bold]acm2 config get api_url[/bold]")
    
    raise typer.Exit(3)


def handle_unexpected_error(error: Exception, verbose: bool = False) -> None:
    """Handle unexpected errors."""
    console.print(f"[red]Unexpected Error:[/red] {error}")
    
    if verbose:
        console.print()
        console.print_exception()
    else:
        console.print("[dim]Use --verbose for full traceback[/dim]")
    
    raise typer.Exit(1)
```

### 15.3 Applying Error Handler

```python
# In command modules

from acm2.cli.errors import handle_error

@app.command("list")
@handle_error
def list_runs(ctx: typer.Context, ...):
    """List all runs."""
    # Command implementation
    # Errors are caught and handled by decorator
```

### 15.4 User-Friendly Error Examples

```powershell
# Connection error
PS> acm2 runs list
Connection Error: Cannot connect to ACM 2.0 server

Possible causes:
  • Server is not running
  • Wrong API URL
  • Firewall blocking connection

Solutions:
  1. Start server: acm2 serve
  2. Check URL: acm2 config get api_url

# Not found error
PS> acm2 runs get invalid_id
Error 404: Not found

Tip: Use 'acm2 runs list' to see available runs

# Validation error
PS> acm2 runs create
Error 422: Validation error
  body -> title: Field required
  body -> project: Field required
```

---

## 16. Configuration File

### 16.1 Configuration File Location

```python
# Windows: %APPDATA%\acm2\config.yaml
# Example: C:\Users\Morgan\AppData\Roaming\acm2\config.yaml
```

### 16.2 Full Configuration Schema

```yaml
# %APPDATA%\acm2\config.yaml
# ACM 2.0 CLI Configuration

# =============================================================================
# Server Connection
# =============================================================================
api_url: http://localhost:8000
api_key: null  # Optional API key for authentication

# =============================================================================
# Output Preferences
# =============================================================================
output:
  format: table          # table, json, plain
  colors: true           # Enable color output
  pager: false           # Use pager for long output
  timestamps: relative   # relative, absolute, iso

# =============================================================================
# Default Values for New Runs
# =============================================================================
defaults:
  project: null          # Default project ID
  title_prefix: ""       # Prefix for auto-generated titles
  generators:
    - fpf                # Default generators (fpf, gptr)
  iterations: 1          # Default iteration count
  tags: []               # Default tags for new runs

# =============================================================================
# Generator Settings
# =============================================================================
generators:
  fpf:
    model: gpt-4o
    temperature: 0.7
    max_tokens: 4096
  gptr:
    model: gpt-4o
    mode: standard       # standard, deep
    max_iterations: 5

# =============================================================================
# Evaluation Settings
# =============================================================================
evaluation:
  judges:
    - gpt-4o             # Models to use as judges
  iterations: 3          # Eval iterations per artifact
  criteria:
    - accuracy
    - completeness
    - clarity
    - relevance
    - formatting
  pairwise:
    enabled: true
    strategy: round_robin  # round_robin, swiss, top_k
    top_k: 5

# =============================================================================
# Reporting
# =============================================================================
reports:
  auto_open: false       # Open reports in browser automatically
  export_format: html    # Default export format (html, csv, json)
  output_dir: null       # Default output directory (null = current dir)

# =============================================================================
# Advanced
# =============================================================================
advanced:
  timeout: 30            # API request timeout (seconds)
  retries: 3             # Number of retries for failed requests
  verbose: false         # Enable verbose logging
```

### 16.3 Environment Variable Overrides

Environment variables take precedence over config file:

| Variable | Config Key | Description |
|----------|------------|-------------|
| `ACM2_API_URL` | `api_url` | API server URL |
| `ACM2_API_KEY` | `api_key` | API authentication key |
| `ACM2_FORMAT` | `output.format` | Output format |
| `ACM2_VERBOSE` | `advanced.verbose` | Verbose mode |
| `ACM2_CONFIG` | - | Config file path override |

### 16.4 Configuration Precedence

```
1. Command-line options (highest priority)
   ↓
2. Environment variables
   ↓
3. Config file (%APPDATA%\acm2\config.yaml)
   ↓
4. Built-in defaults (lowest priority)
```

### 16.5 Config Validation

```python
# acm2/cli/config.py

from pydantic import BaseModel, Field
from typing import Optional, List


class OutputConfig(BaseModel):
    format: str = "table"
    colors: bool = True
    pager: bool = False
    timestamps: str = "relative"


class GeneratorConfig(BaseModel):
    model: str = "gpt-4o"
    temperature: float = 0.7
    max_tokens: int = 4096


class EvaluationConfig(BaseModel):
    judges: List[str] = ["gpt-4o"]
    iterations: int = 3
    criteria: List[str] = ["accuracy", "completeness", "clarity", "relevance", "formatting"]


class Config(BaseModel):
    """Full CLI configuration schema with validation."""
    api_url: str = "http://localhost:8000"
    api_key: Optional[str] = None
    output: OutputConfig = Field(default_factory=OutputConfig)
    defaults: dict = Field(default_factory=dict)
    generators: dict = Field(default_factory=dict)
    evaluation: EvaluationConfig = Field(default_factory=EvaluationConfig)
    reports: dict = Field(default_factory=dict)
    advanced: dict = Field(default_factory=dict)
```

---

## 17. Shell Completion

### 17.1 Shell Completion

Typer provides built-in completion for PowerShell, bash, zsh, and fish.

```python
# Typer provides built-in completion support

@app.command("--install-completion")
def install_completion():
    """Install shell completion for PowerShell."""
    # Typer handles this automatically
    pass
```

### 17.2 Installing Completion

```powershell
# Install PowerShell completion
acm2 --install-completion powershell

# This adds to your PowerShell profile:
# Register-ArgumentCompleter -Native -CommandName acm2 -ScriptBlock {
#     param($wordToComplete, $commandAst, $cursorPosition)
#     ...
# }
```

### 17.3 Manual Completion Setup

```powershell
# Add to $PROFILE (e.g., ~\Documents\PowerShell\Microsoft.PowerShell_profile.ps1)

Register-ArgumentCompleter -Native -CommandName acm2 -ScriptBlock {
    param($wordToComplete, $commandAst, $cursorPosition)
    
    $env:_ACM2_COMPLETE = "powershell_complete"
    $env:_ACM2_COMPLETE_WORD = $wordToComplete
    $env:_ACM2_COMPLETE_POSITION = $cursorPosition
    
    acm2 | ForEach-Object {
        [System.Management.Automation.CompletionResult]::new(
            $_,
            $_,
            'ParameterValue',
            $_
        )
    }
    
    Remove-Item Env:_ACM2_COMPLETE
    Remove-Item Env:_ACM2_COMPLETE_WORD
    Remove-Item Env:_ACM2_COMPLETE_POSITION
}
```

### 17.4 Completion Features

| Feature | Support |
|---------|---------|
| Command completion | `acm2 ru<TAB>` → `acm2 runs` |
| Subcommand completion | `acm2 runs li<TAB>` → `acm2 runs list` |
| Option completion | `acm2 runs list --st<TAB>` → `--status` |
| Run ID completion | `acm2 runs get <TAB>` → Lists recent run IDs |
| File path completion | `acm2 docs add abc123 ./do<TAB>` → File paths |

### 17.5 Dynamic Completion for Run IDs

```python
# acm2/cli/completion.py

import typer
from typing import List


def complete_run_id(incomplete: str) -> List[str]:
    """Complete run IDs from API."""
    try:
        from acm2.cli.client import ApiClient
        from acm2.cli.config import ConfigManager
        
        config = ConfigManager().load()
        client = ApiClient(config.get("api_url", "http://localhost:8000"))
        
        response = client.get("/api/v1/runs", params={"limit": 20})
        runs = response.json().get("runs", [])
        
        # Filter by incomplete prefix
        return [
            r["run_id"] for r in runs 
            if r["run_id"].startswith(incomplete)
        ]
    except Exception:
        return []


# Usage in commands:
@app.command("get")
def get_run(
    run_id: str = typer.Argument(
        ...,
        help="Run ID",
        autocompletion=complete_run_id,
    ),
):
    ...
```

---

## 18. Tests

### 18.1 Test Structure

```
acm2/
└── tests/
    └── cli/
        ├── __init__.py
        ├── conftest.py           # Fixtures
        ├── test_main.py          # Entry point tests
        ├── test_runs.py          # Run command tests
        ├── test_docs.py          # Document command tests
        ├── test_eval.py          # Evaluation command tests
        ├── test_reports.py       # Report command tests
        ├── test_config.py        # Config command tests
        ├── test_client.py        # API client tests
        ├── test_output.py        # Output formatting tests
        └── test_errors.py        # Error handling tests
```

### 18.2 Test Fixtures

```python
# tests/cli/conftest.py

import pytest
from typer.testing import CliRunner
from unittest.mock import MagicMock, patch
from acm2.cli.main import app


@pytest.fixture
def cli_runner():
    """Typer CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_api_client():
    """Mock API client for testing without server."""
    with patch("acm2.cli.client.ApiClient") as mock:
        client = MagicMock()
        mock.return_value = client
        yield client


@pytest.fixture
def sample_runs():
    """Sample run data for testing."""
    return {
        "runs": [
            {
                "run_id": "run_abc123",
                "title": "Test Run 1",
                "project_id": "test-project",
                "status": "completed",
                "document_count": 5,
                "created_at": "2025-12-04T10:00:00Z",
                "tags": ["test"],
            },
            {
                "run_id": "run_def456",
                "title": "Test Run 2",
                "project_id": "test-project",
                "status": "running",
                "document_count": 3,
                "created_at": "2025-12-04T12:00:00Z",
                "tags": [],
            },
        ]
    }
```

### 18.3 Command Tests

```python
# tests/cli/test_runs.py

import pytest
from typer.testing import CliRunner
from unittest.mock import MagicMock
from acm2.cli.main import app


class TestRunsCommands:
    """Tests for runs commands."""
    
    def test_runs_list(self, cli_runner, mock_api_client, sample_runs):
        """Test 'acm2 runs list' command."""
        # Setup mock
        mock_response = MagicMock()
        mock_response.json.return_value = sample_runs
        mock_api_client.get.return_value = mock_response
        
        # Run command
        result = cli_runner.invoke(app, ["runs", "list"])
        
        # Verify
        assert result.exit_code == 0
        assert "run_abc123" in result.output or "abc123" in result.output
        mock_api_client.get.assert_called_with("/api/v1/runs", params={"limit": 20})
    
    def test_runs_list_with_status_filter(self, cli_runner, mock_api_client, sample_runs):
        """Test 'acm2 runs list --status running'."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"runs": [sample_runs["runs"][1]]}
        mock_api_client.get.return_value = mock_response
        
        result = cli_runner.invoke(app, ["runs", "list", "--status", "running"])
        
        assert result.exit_code == 0
        mock_api_client.get.assert_called_with(
            "/api/v1/runs",
            params={"limit": 20, "status": "running"}
        )
    
    def test_runs_list_json_format(self, cli_runner, mock_api_client, sample_runs):
        """Test 'acm2 runs list --format json'."""
        mock_response = MagicMock()
        mock_response.json.return_value = sample_runs
        mock_api_client.get.return_value = mock_response
        
        result = cli_runner.invoke(app, ["runs", "list", "--format", "json"])
        
        assert result.exit_code == 0
        # Output should be valid JSON
        import json
        output_data = json.loads(result.output)
        assert "runs" in output_data or isinstance(output_data, list)
    
    def test_runs_create(self, cli_runner, mock_api_client):
        """Test 'acm2 runs create'."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "run_id": "run_new123",
            "title": "New Run",
            "project_id": "my-project",
        }
        mock_api_client.post.return_value = mock_response
        
        result = cli_runner.invoke(app, [
            "runs", "create",
            "--title", "New Run",
            "--project", "my-project",
        ])
        
        assert result.exit_code == 0
        assert "run_new123" in result.output or "Created" in result.output
    
    def test_runs_get(self, cli_runner, mock_api_client, sample_runs):
        """Test 'acm2 runs get <run_id>'."""
        mock_response = MagicMock()
        mock_response.json.return_value = sample_runs["runs"][0]
        mock_api_client.get.return_value = mock_response
        
        result = cli_runner.invoke(app, ["runs", "get", "run_abc123"])
        
        assert result.exit_code == 0
        assert "Test Run 1" in result.output or "completed" in result.output
    
    def test_runs_delete_requires_confirmation(self, cli_runner, mock_api_client):
        """Test 'acm2 runs delete' asks for confirmation."""
        result = cli_runner.invoke(app, ["runs", "delete", "run_abc123"], input="n\n")
        
        assert result.exit_code == 1  # Aborted
        mock_api_client.delete.assert_not_called()
    
    def test_runs_delete_force(self, cli_runner, mock_api_client):
        """Test 'acm2 runs delete --force' skips confirmation."""
        mock_api_client.delete.return_value = MagicMock()
        
        result = cli_runner.invoke(app, ["runs", "delete", "run_abc123", "--force"])
        
        assert result.exit_code == 0
        mock_api_client.delete.assert_called_once()
```

### 18.4 Error Handling Tests

```python
# tests/cli/test_errors.py

import pytest
from typer.testing import CliRunner
from unittest.mock import MagicMock, patch
from acm2.cli.main import app
from acm2.cli.client import ApiError


class TestErrorHandling:
    """Tests for CLI error handling."""
    
    def test_api_404_error(self, cli_runner, mock_api_client):
        """Test handling of 404 errors."""
        mock_api_client.get.side_effect = ApiError(404, "Not found")
        
        result = cli_runner.invoke(app, ["runs", "get", "invalid_id"])
        
        assert result.exit_code == 1
        assert "404" in result.output or "Not found" in result.output
    
    def test_connection_error(self, cli_runner, mock_api_client):
        """Test handling of connection errors."""
        mock_api_client.get.side_effect = ConnectionError("Connection refused")
        
        result = cli_runner.invoke(app, ["runs", "list"])
        
        assert result.exit_code == 3
        assert "Connection" in result.output or "connect" in result.output.lower()
    
    def test_validation_error_422(self, cli_runner, mock_api_client):
        """Test handling of validation errors."""
        mock_api_client.post.side_effect = ApiError(
            422,
            "Validation error",
            {"detail": [{"loc": ["body", "title"], "msg": "Field required"}]}
        )
        
        result = cli_runner.invoke(app, ["runs", "create", "--project", "test"])
        
        assert result.exit_code == 1
        assert "422" in result.output or "Validation" in result.output
```

### 18.5 Output Format Tests

```python
# tests/cli/test_output.py

import pytest
from acm2.cli.output import (
    format_timestamp,
    format_file_size,
    format_score,
    status_icon,
)


class TestOutputFormatting:
    """Tests for output formatting utilities."""
    
    def test_format_file_size_bytes(self):
        assert format_file_size(500) == "500 B"
    
    def test_format_file_size_kb(self):
        assert format_file_size(1536) == "1.5 KB"
    
    def test_format_file_size_mb(self):
        assert format_file_size(1048576) == "1.0 MB"
    
    def test_status_icon_completed(self):
        assert status_icon("completed") == "✅"
    
    def test_status_icon_failed(self):
        assert status_icon("failed") == "❌"
    
    def test_status_icon_unknown(self):
        assert status_icon("unknown") == "•"
```

### 18.6 Running Tests

```powershell
# Run all CLI tests
pytest tests/cli/ -v

# Run with coverage
pytest tests/cli/ --cov=acm2.cli --cov-report=html

# Run specific test file
pytest tests/cli/test_runs.py -v

# Run specific test
pytest tests/cli/test_runs.py::TestRunsCommands::test_runs_list -v
```

---

## 19. Success Criteria

### 19.1 Functional Requirements

| ID | Requirement | Verification |
|----|-------------|--------------|
| F-12.1 | `acm2 serve` starts FastAPI server | Manual test |
| F-12.2 | `acm2 runs list` shows all runs | Unit test |
| F-12.3 | `acm2 runs create` creates new run | Unit test |
| F-12.4 | `acm2 runs start` triggers generation | Integration test |
| F-12.5 | `acm2 runs stop` stops running run | Integration test |
| F-12.6 | `acm2 docs add` attaches document to run | Unit test |
| F-12.7 | `acm2 eval start` triggers evaluation | Integration test |
| F-12.8 | `acm2 eval results` shows rankings | Unit test |
| F-12.9 | `acm2 reports open` opens browser | Manual test |
| F-12.10 | `acm2 config set/get` manages config | Unit test |
| F-12.11 | All commands support `--format json` | Unit test |
| F-12.12 | All commands support `--help` | Unit test |

### 19.2 Quality Requirements

| ID | Requirement | Verification |
|----|-------------|--------------|
| Q-12.1 | All commands have docstrings | Code review |
| Q-12.2 | All commands have `--help` with examples | Manual test |
| Q-12.3 | Error messages include suggestions | Unit test |
| Q-12.4 | Exit codes follow convention (0, 1, 2, 3) | Unit test |
| Q-12.5 | Type hints on all functions | mypy check |
| Q-12.6 | Unit test coverage ≥ 80% | pytest-cov |

### 19.3 Usability Requirements

| ID | Requirement | Verification |
|----|-------------|--------------|
| U-12.1 | Tab completion works in PowerShell | Manual test |
| U-12.2 | Progress indicators for long operations | Manual test |
| U-12.3 | Colors disabled when not in TTY | Unit test |
| U-12.4 | Config file created on first use | Manual test |
| U-12.5 | Connection errors suggest `acm2 serve` | Unit test |

### 19.4 Acceptance Checklist

- [ ] `acm2 serve` starts server and optionally opens browser
- [ ] `acm2 runs list` displays formatted table
- [ ] `acm2 runs create` creates run and shows next steps
- [ ] `acm2 runs start --wait` shows progress until completion
- [ ] `acm2 eval results` shows rankings with Elo scores
- [ ] `acm2 --format json` outputs valid JSON for all commands
- [ ] `acm2 config show` displays configuration
- [ ] Shell completion works for commands and run IDs
- [ ] Error messages are clear with suggested fixes
- [ ] All unit tests pass
- [ ] Documentation examples work as shown

---

## 20. File Structure

```
acm2/
├── cli/
│   ├── __init__.py              # Package exports
│   ├── main.py                  # Entry point, Typer app, global options
│   ├── commands/
│   │   ├── __init__.py
│   │   ├── serve.py             # acm2 serve command
│   │   ├── runs.py              # acm2 runs subcommands
│   │   ├── docs.py              # acm2 docs subcommands
│   │   ├── eval.py              # acm2 eval subcommands
│   │   ├── reports.py           # acm2 reports subcommands
│   │   └── config.py            # acm2 config subcommands
│   ├── client.py                # ApiClient, AsyncApiClient
│   ├── config.py                # ConfigManager, get_config_path
│   ├── output.py                # Formatting utilities
│   ├── progress.py              # Progress bars and spinners
│   ├── errors.py                # Error handling, exit codes
│   ├── completion.py            # Dynamic completion helpers
│   └── interactive.py           # Interactive REPL mode (optional)
├── tests/
│   └── cli/
│       ├── __init__.py
│       ├── conftest.py          # Test fixtures
│       ├── test_main.py
│       ├── test_runs.py
│       ├── test_docs.py
│       ├── test_eval.py
│       ├── test_reports.py
│       ├── test_config.py
│       ├── test_client.py
│       ├── test_output.py
│       └── test_errors.py
└── pyproject.toml               # Entry point: acm2 = "acm2.cli.main:cli"
```

### Module Dependencies

```
main.py
├── commands/serve.py
├── commands/runs.py
│   ├── client.py
│   ├── output.py
│   └── errors.py
├── commands/docs.py
│   ├── client.py
│   └── output.py
├── commands/eval.py
│   ├── client.py
│   ├── output.py
│   └── progress.py
├── commands/reports.py
│   └── client.py
├── commands/config.py
│   └── config.py
└── interactive.py (optional)
    └── main.py (recursive for command execution)
```

---

## 21. Next Steps

After Step 12 (CLI) is complete:

### Immediate Dependencies

| Step | Name | Dependency on Step 12 |
|------|------|----------------------|
| **Step 13** | Windows Deployment | Packages CLI as `acm2.exe` |
| **Step 14** | API Key Management | CLI commands for key management |
| **Step 15** | Rate Limiting | CLI shows rate limit status |

### Recommended Order

1. **Step 13 (Windows Deployment)** — Package CLI + server as standalone executable. Users can run `acm2.exe serve` without Python installed.

2. **Step 14 (API Key Management)** — Add `acm2 keys create`, `acm2 keys list`, `acm2 keys revoke` commands.

3. **Step 16 (GPT-R Adapter)** — CLI already supports `-g gptr` flag, just needs backend implementation.

### Integration Points

| From Step 12 | Used By | Purpose |
|--------------|---------|---------|
| `acm2 serve` | Step 13 | Entry point for packaged executable |
| `acm2 runs` | Step 11 (Web GUI) | Same API, different interface |
| `acm2 eval` | Step 10 | CLI trigger for evaluation |
| Config system | All steps | Shared configuration |
| API client | Step 14 | Key management commands |

### Future Enhancements (Post-MVP)

| Enhancement | Description |
|-------------|-------------|
| `acm2 watch` | Real-time dashboard in terminal |
| `acm2 diff` | Compare artifacts side-by-side |
| `acm2 benchmark` | Run performance benchmarks |
| Plugin system | Custom commands via plugins |
| SSH remote | Connect to remote ACM server |

---

**End of Step 12: CLI**
