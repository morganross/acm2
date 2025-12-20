import asyncio
import sys
import os

# Add the current directory to sys.path so we can import app modules
sys.path.append(os.getcwd())

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.infra.db.models.preset import Preset
from app.config import get_settings

async def test_query():
    settings = get_settings()
    print(f"DB URL: {settings.database_url}")
    
    # Force the default URL logic if needed (mimicking main.py fix)
    if settings.database_url == "sqlite+aiosqlite:///./acm2.db":
         settings.database_url = settings.default_database_url
         print(f"Corrected DB URL: {settings.database_url}")

    engine = create_async_engine(settings.database_url)
    async with AsyncSession(engine) as session:
        stmt = (
            select(Preset)
            .options(selectinload(Preset.runs)) # Comment out to isolate relationship issues
            .where(Preset.is_deleted == False)
            .offset(0)
            .limit(100)
            .order_by(Preset.created_at.desc())
        )
        try:
            result = await session.execute(stmt)
            presets = result.scalars().all()
            print(f"Found {len(presets)} presets via SQLAlchemy")
            for p in presets:
                print(f" - {p.name} ({p.id})")
        except Exception as e:
            print(f"Query failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_query())
