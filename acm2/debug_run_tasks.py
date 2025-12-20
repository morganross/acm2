
import asyncio
import sys
import os
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Add the project root to the python path
sys.path.append(r"c:\dev\silky\api_cost_multiplier\acm2")

from app.infra.db.models.run import Run
from app.infra.db.models.task import GenerationTask
from app.config import get_settings

async def check_run_tasks(run_id):
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Get run
        result = await session.execute(select(Run).where(Run.id == run_id))
        run = result.scalar_one_or_none()
        
        if not run:
            print(f"Run {run_id} not found in DB")
            return

        print(f"Run found: {run.id}, Status: {run.status}")

        # Get tasks
        result = await session.execute(select(GenerationTask).where(GenerationTask.run_id == run_id))
        tasks = result.scalars().all()
        
        print(f"Total Tasks found: {len(tasks)}")
        for t in tasks:
            print(f"Task: {t.id} | Doc: {t.document_name} | Status: {t.status} | Phase: {t.phase}")

if __name__ == "__main__":
    run_id = "6c9494cb-77b2-41ec-87c5-0e6aec032494"
    asyncio.run(check_run_tasks(run_id))

