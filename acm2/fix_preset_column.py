import asyncio
import sys
import os

# Add current directory to path so imports work
sys.path.append(os.getcwd())

from app.infra.db.session import async_session_factory
from app.infra.db.repositories import PresetRepository

async def main():
    preset_id = "86f721fc-742c-4489-9626-f148cb3d6209"
    async with async_session_factory() as session:
        repo = PresetRepository(session)
        preset = await repo.get_by_id(preset_id)
        if not preset:
            print(f"Preset {preset_id} not found")
            return

        print(f"Current column request_timeout: {preset.request_timeout}")
        
        # Update the column
        await repo.update(preset_id, request_timeout=1800, eval_timeout=1800)
        print(f"Updated column request_timeout to 1800")
        
        # Verify
        updated = await repo.get_by_id(preset_id)
        print(f"New column request_timeout: {updated.request_timeout}")

if __name__ == "__main__":
    asyncio.run(main())
