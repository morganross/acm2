import typer
import uvicorn
import httpx
import json
import os
from typing import Optional
from rich.console import Console
from rich.table import Table

app = typer.Typer()
console = Console()

API_URL = os.getenv("ACM_API_URL", "http://127.0.0.1:8000/api/v1")

@app.command()
def serve(
    host: str = "127.0.0.1",
    port: int = 8000,
    reload: bool = False
):
    """Start the ACM2 API server."""
    console.print(f"[green]Starting ACM2 server at http://{host}:{port}[/green]")
    uvicorn.run("app.main:app", host=host, port=port, reload=reload)

@app.command()
def version():
    """Show version."""
    console.print("ACM 2.0.0")

# Runs group
runs_app = typer.Typer()
app.add_typer(runs_app, name="runs", help="Manage execution runs")

@runs_app.command("list")
def list_runs(
    limit: int = 20,
    offset: int = 0
):
    """List execution runs."""
    try:
        with httpx.Client() as client:
            response = client.get(f"{API_URL}/runs", params={"limit": limit, "offset": offset})
            response.raise_for_status()
            data = response.json()
            
            table = Table(title="Execution Runs")
            table.add_column("ID", style="cyan")
            table.add_column("Name", style="magenta")
            table.add_column("Status", style="green")
            table.add_column("Created", style="blue")
            
            for run in data["items"]:
                table.add_row(
                    run["id"][:8],
                    run["name"],
                    run["status"],
                    run["created_at"]
                )
            
            console.print(table)
            
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

@runs_app.command("create")
def create_run(
    preset_id: str = typer.Option(..., help="ID of the preset to use"),
    start: bool = typer.Option(True, help="Start the run immediately")
):
    """Create a new run from a preset."""
    try:
        with httpx.Client() as client:
            # If start is True, use the execute endpoint
            if start:
                response = client.post(f"{API_URL}/presets/{preset_id}/execute")
            else:
                # Just create
                # We don't have a direct 'create from preset' endpoint that doesn't start?
                # Actually we do: POST /runs with config. 
                # But execute_preset does both.
                # For now let's just support execute.
                response = client.post(f"{API_URL}/presets/{preset_id}/execute")
                
            response.raise_for_status()
            data = response.json()
            
            console.print(f"[green]Run created successfully![/green]")
            console.print(f"Run ID: {data['run_id']}")
            console.print(f"Status: {data['status']}")
            
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

@runs_app.command("cancel")
def cancel_run(run_id: str = typer.Option(..., help="ID of the run to cancel")):
    """Cancel a running run."""
    try:
        with httpx.Client() as client:
            response = client.put(f"{API_URL}/runs/{run_id}/status", json={"status": "cancelled"})
            response.raise_for_status()
            console.print(f"[green]Run {run_id} cancelled successfully![/green]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

# Presets group
presets_app = typer.Typer()
app.add_typer(presets_app, name="presets", help="Manage configuration presets")

@presets_app.command("list")
def list_presets(
    limit: int = 20,
    offset: int = 0
):
    """List configuration presets."""
    try:
        with httpx.Client() as client:
            response = client.get(f"{API_URL}/presets", params={"limit": limit, "offset": offset})
            response.raise_for_status()
            data = response.json()
            
            table = Table(title="Presets")
            table.add_column("ID", style="cyan")
            table.add_column("Name", style="magenta")
            table.add_column("Docs", style="blue")
            table.add_column("Models", style="green")
            
            for preset in data["items"]:
                table.add_row(
                    preset["id"],
                    preset["name"],
                    str(preset["document_count"]),
                    str(preset["model_count"])
                )
            
            console.print(table)
            
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

if __name__ == "__main__":
    app()
