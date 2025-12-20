from datetime import datetime

import pytest

from app.api.routes.runs import (
    RunConnectionManager,
    RunStatus,
    run_store,
    run_ws_manager,
)
from app.services.run_executor import (
    GeneratedDocument,
    RunConfig,
    RunExecutor,
    RunPhase,
    RunResult,
)
from app.adapters.base import GeneratorType


class DummyWebSocket:
    def __init__(self):
        self.accepted = False
        self.messages = []

    async def accept(self):
        self.accepted = True

    async def send_json(self, message):
        self.messages.append(message)


@pytest.fixture(autouse=True)
def reset_run_store():
    run_store.runs.clear()
    run_ws_manager.connections.clear()
    yield
    run_store.runs.clear()
    run_ws_manager.connections.clear()


@pytest.mark.asyncio
async def test_run_connection_manager_serializes_messages():
    manager = RunConnectionManager()
    ws = DummyWebSocket()

    await manager.connect(ws, "run-1")

    await manager.broadcast(
        "run-1",
        {
            "event": "status",
            "status": RunStatus.RUNNING,
            "created_at": datetime(2025, 1, 1, 12, 0, 0),
        },
    )

    assert ws.accepted is True
    assert ws.messages
    payload = ws.messages[0]
    assert payload["status"] == "running"
    assert payload["created_at"] == "2025-01-01T12:00:00"
@pytest.mark.asyncio
async def test_run_executor_progress_updates_run_store_and_ws(monkeypatch):
    executor = RunExecutor()

    class DummyRunStore:
        def __init__(self):
            self.data = {}

        def get(self, run_id):
            return self.data.get(run_id)

        def update(self, run_id, **kwargs):
            self.data.setdefault(run_id, {}).update(kwargs)

    class DummyWsManager:
        def __init__(self):
            self.messages = []

        async def broadcast(self, run_id, message):
            import copy
            self.messages.append((run_id, copy.deepcopy(message)))

    dummy_store = DummyRunStore()
    dummy_store.data["run-exec"] = {
        "tasks": [],
        "document_ids": ["doc-1"],
    }

    executor._run_store = dummy_store
    executor._run_ws_manager = DummyWsManager()

    async def fake_generate_single(doc_id, content, generator, model, iteration, progress_callback=None):
        if progress_callback:
            await progress_callback("halfway", 0.5, "halfway there")
        return GeneratedDocument(
            doc_id=f"{doc_id}.{generator.value}.{iteration}.{model}",
            content="result",
            generator=generator,
            model=model,
            source_doc_id=doc_id,
            iteration=iteration,
            cost_usd=1.23,
            duration_seconds=2.5,
        )

    executor._generate_single = fake_generate_single  # type: ignore

    config = RunConfig(
        document_ids=["doc-1"],
        document_contents={"doc-1": "content"},
        generators=[GeneratorType.GPTR],
        models=["openai:gpt-4o"],
        iterations=1,
        enable_single_eval=False,
        enable_pairwise=False,
    )

    result = RunResult(
        run_id="run-exec",
        status=RunPhase.GENERATING,
        generated_docs=[],
        started_at=datetime.utcnow(),
    )

    await executor._run_generation_with_eval("run-exec", config, result)

    tasks = dummy_store.data["run-exec"]["tasks"]
    assert tasks
    task = tasks[0]
    assert task["progress"] == 1.0
    assert task["status"] == "completed"
    assert task["message"] == "completed"

    # ensure websocket manager saw progress updates
    messages = executor._run_ws_manager.messages
    assert any(m[1]["task"]["progress"] == 0.5 for m in messages if m[1].get("event") == "task_update")
    assert any(m[1]["task"]["progress"] == 1.0 for m in messages if m[1].get("event") == "task_update")
