from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
import uvicorn
import json

from app.api.schemas.runs import RunCreate, RunList, RunDetail, RunSummary, ModelConfig, GeneratorType
from app.api.schemas.presets import PresetSummary, PresetList
from app.cli.client import ApiClient


app = typer.Typer(help="ACM2 CLI")
run_app = typer.Typer(help="Manage runs")
preset_app = typer.Typer(help="Manage presets")
app.add_typer(run_app, name="runs")
app.add_typer(preset_app, name="presets")


@app.command()
def serve(
	host: str = typer.Option("127.0.0.1", help="Host interface"),
	port: int = typer.Option(8002, help="Port to bind"),
	reload: bool = typer.Option(False, help="Enable autoreload (dev only)"),
):
	"""Start the ACM2 API + SPA server."""

	app_dir = Path(__file__).resolve().parents[1]
	uvicorn.run(
		"app.main:create_app",
		host=host,
		port=port,
		reload=reload,
		factory=True,
		app_dir=str(app_dir),
	)


def _client(base_url: str) -> ApiClient:
	return ApiClient(base_url)


@run_app.command("list")
def runs_list(
	status: Optional[str] = typer.Option(None, help="Filter by status"),
	base_url: str = typer.Option("http://127.0.0.1:8002/api/v1", help="API base URL"),
):
	"""List runs."""
	client = _client(base_url)
	runs = client.list_runs(status=status)
	for r in runs.items:
		typer.echo(f"{r.id}\t{r.status}\t{r.name}")


@run_app.command("get")
def runs_get(
	run_id: str = typer.Argument(..., help="Run ID"),
	base_url: str = typer.Option("http://127.0.0.1:8002/api/v1", help="API base URL"),
):
	"""Get run detail."""
	client = _client(base_url)
	detail: RunDetail = client.get_run(run_id)
	typer.echo(detail.model_dump_json(indent=2))


@run_app.command("create")
def runs_create(
	name: str = typer.Option(..., help="Run name"),
	documents: str = typer.Option(..., help="Comma-separated document IDs"),
	models: str = typer.Option(..., help="Comma-separated model names (e.g. openai:gpt-4o)"),
	iterations: int = typer.Option(1, help="Iterations per model/doc"),
	generators: str = typer.Option("fpf", help="Comma-separated generators (fpf, gptr)"),
	
	# Evaluation options
	single_eval: bool = typer.Option(True, help="Enable single-doc evaluation"),
	pairwise_eval: bool = typer.Option(True, help="Enable pairwise evaluation"),
	eval_iterations: int = typer.Option(1, help="Evaluation iterations"),
	pairwise_top_n: Optional[int] = typer.Option(None, help="Only compare top N docs in pairwise"),
	
	# GPTR options
	gptr_report_type: str = typer.Option("research_report", help="GPTR report type"),
	gptr_tone: Optional[str] = typer.Option(None, help="GPTR tone"),
	gptr_retriever: str = typer.Option("tavily", help="GPTR retriever"),
	
	# Combine options
	combine: bool = typer.Option(False, help="Enable combine phase"),
	combine_model: str = typer.Option("gpt-5", help="Model for combine phase"),
	combine_strategy: str = typer.Option("intelligent_merge", help="Combine strategy"),
	
	base_url: str = typer.Option("http://127.0.0.1:8002/api/v1", help="API base URL"),
):
	"""Create a run with full configuration options."""
	client = _client(base_url)
	
	# Parse models
	model_configs = []
	for m in models.split(','):
		m = m.strip()
		if not m: continue
		if ":" in m:
			provider, model_name = m.split(":", 1)
		else:
			provider, model_name = "openai", m
		model_configs.append(ModelConfig(provider=provider, model=model_name))
		
	# Build payload
	from app.api.schemas.runs import GptrSettings, EvaluationSettings, PairwiseSettings, CombineSettings
	
	payload = RunCreate(
		name=name,
		description=None,
		document_ids=[d.strip() for d in documents.split(',') if d.strip()],
		models=model_configs,
		generators=[GeneratorType(g.strip()) for g in generators.split(',') if g.strip()],
		iterations=iterations,
		
		gptr_settings=GptrSettings(
			report_type=gptr_report_type,
			tone=gptr_tone,
			retriever=gptr_retriever
		),
		
		evaluation=EvaluationSettings(
			enable_single_eval=single_eval,
			enable_pairwise=pairwise_eval,
			iterations=eval_iterations,
			judge_models=[]  # Must be set via preset
		),
		
		pairwise=PairwiseSettings(
			top_n=pairwise_top_n
		),
		
		combine=CombineSettings(
			enabled=combine,
			strategy=combine_strategy,
			model=combine_model
		)
	)
	created: RunSummary = client.create_run(payload)
	typer.echo(created.model_dump_json(indent=2))


@run_app.command("delete")
def runs_delete(
	run_id: str = typer.Argument(..., help="Run ID"),
	base_url: str = typer.Option("http://127.0.0.1:8002/api/v1", help="API base URL"),
):
	"""Delete a run."""
	client = _client(base_url)
	client.delete_run(run_id)
	typer.echo(f"Deleted {run_id}")


@run_app.command("start")
def runs_start(
	run_id: str = typer.Argument(..., help="Run ID"),
	base_url: str = typer.Option("http://127.0.0.1:8002/api/v1", help="API base URL"),
):
	"""Start a pending run."""
	client = _client(base_url)
	resp = client.start_run(run_id)
	typer.echo(resp)


@run_app.command("pause")
def runs_pause(
	run_id: str = typer.Argument(..., help="Run ID"),
	base_url: str = typer.Option("http://127.0.0.1:8002/api/v1", help="API base URL"),
):
	"""Pause a running run."""
	client = _client(base_url)
	resp = client.pause_run(run_id)
	typer.echo(resp)


@run_app.command("resume")
def runs_resume(
	run_id: str = typer.Argument(..., help="Run ID"),
	base_url: str = typer.Option("http://127.0.0.1:8002/api/v1", help="API base URL"),
):
	"""Resume a paused run."""
	client = _client(base_url)
	resp = client.resume_run(run_id)
	typer.echo(resp)


@run_app.command("cancel")
def runs_cancel(
	run_id: str = typer.Argument(..., help="Run ID"),
	base_url: str = typer.Option("http://127.0.0.1:8002/api/v1", help="API base URL"),
):
	"""Cancel a run (pending/running/paused)."""
	client = _client(base_url)
	resp = client.cancel_run(run_id)
	typer.echo(resp)


@run_app.command("report")
def runs_report(
	run_id: str = typer.Argument(..., help="Run ID"),
	output: Path = typer.Option(..., help="Output path for HTML report"),
	base_url: str = typer.Option("http://127.0.0.1:8002/api/v1", help="API base URL"),
):
	"""Download the HTML report for a run."""
	client = _client(base_url)
	client.download_report(run_id, output)
	typer.echo(f"Report saved to {output}")


@preset_app.command("list")
def presets_list(
	base_url: str = typer.Option("http://127.0.0.1:8002/api/v1", help="API base URL"),
):
	"""List presets."""
	client = _client(base_url)
	presets = client.list_presets()
	for p in presets.items:
		typer.echo(f"{p.id}\t{p.name}\t{p.run_count} runs")


@preset_app.command("execute")
def presets_execute(
	preset_id: str = typer.Argument(..., help="Preset ID"),
	base_url: str = typer.Option("http://127.0.0.1:8002/api/v1", help="API base URL"),
):
	"""Execute a preset and print the new run id."""
	client = _client(base_url)
	resp = client.execute_preset(preset_id)
	typer.echo(json.dumps(resp))


if __name__ == "__main__":
	cli()
