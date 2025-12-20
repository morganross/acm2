from typing import Optional, Dict, Any
import httpx
from pathlib import Path

from app.api.schemas.runs import RunCreate, RunList, RunDetail, RunSummary
from app.api.schemas.presets import PresetList

class ApiClient:
    """Minimal synchronous API client for ACM2 CLI."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._http = httpx.Client(base_url=self.base_url, timeout=30.0)

    def list_runs(self, status: Optional[str] = None) -> RunList:
        params = {"status": status} if status else None
        resp = self._http.get("/runs", params=params)
        resp.raise_for_status()
        return RunList.model_validate(resp.json())

    def get_run(self, run_id: str) -> RunDetail:
        resp = self._http.get(f"/runs/{run_id}")
        resp.raise_for_status()
        return RunDetail.model_validate(resp.json())

    def create_run(self, payload: RunCreate) -> RunSummary:
        resp = self._http.post("/runs", json=payload.model_dump())
        resp.raise_for_status()
        return RunSummary.model_validate(resp.json())

    def delete_run(self, run_id: str) -> None:
        resp = self._http.delete(f"/runs/{run_id}")
        resp.raise_for_status()

    def start_run(self, run_id: str) -> Dict[str, Any]:
        resp = self._http.post(f"/runs/{run_id}/start")
        resp.raise_for_status()
        return resp.json()

    def pause_run(self, run_id: str) -> Dict[str, Any]:
        resp = self._http.post(f"/runs/{run_id}/pause")
        resp.raise_for_status()
        return resp.json()

    def resume_run(self, run_id: str) -> Dict[str, Any]:
        resp = self._http.post(f"/runs/{run_id}/resume")
        resp.raise_for_status()
        return resp.json()

    def cancel_run(self, run_id: str) -> Dict[str, Any]:
        resp = self._http.post(f"/runs/{run_id}/cancel")
        resp.raise_for_status()
        return resp.json()

    def list_presets(self) -> PresetList:
        resp = self._http.get("/presets")
        resp.raise_for_status()
        return PresetList.model_validate(resp.json())

    def execute_preset(self, preset_id: str) -> Dict[str, Any]:
        resp = self._http.post(f"/presets/{preset_id}/execute")
        resp.raise_for_status()
        return resp.json()

    def download_report(self, run_id: str, output_path: Path) -> None:
        """Download the HTML report for a run."""
        resp = self._http.get(f"/runs/{run_id}/report")
        resp.raise_for_status()
        
        with open(output_path, "wb") as f:
            f.write(resp.content)
