import asyncio
import json
from app.infra.db.session import async_session_factory
from app.infra.db.repositories import RunRepository

async def main():
    run_id = "220ddff1-aea8-4596-9c18-54ddb44493a5"
    async with async_session_factory() as session:
        repo = RunRepository(session)
        run = await repo.get_with_tasks(run_id)
        if run:
            print(f"Run ID: {run.id}")
            print(f"Tasks count: {len(run.tasks)}")
            print("Results Summary keys:", run.results_summary.keys() if run.results_summary else "None")
            if run.results_summary:
                print(json.dumps(run.results_summary, indent=2))
        else:
            print("Run not found")

if __name__ == "__main__":
    asyncio.run(main())
