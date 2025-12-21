import asyncio
import json
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

        print(f"Current config_overrides: {json.dumps(preset.config_overrides, indent=2)}")
        
        overrides = preset.config_overrides or {}
        if "concurrency" not in overrides:
            overrides["concurrency"] = {}
        
        current_timeout = overrides["concurrency"].get("request_timeout")
        print(f"Current request_timeout: {current_timeout}")
        
        # Update timeout
        overrides["concurrency"]["request_timeout"] = 1800
        overrides["concurrency"]["eval_timeout"] = 1800
        
        # Update the preset
        await repo.update(preset_id, config_overrides=overrides)
        print(f"Updated request_timeout to 1800")
        
        # Verify
        updated = await repo.get_by_id(preset_id)
        print(f"New request_timeout: {updated.config_overrides['concurrency']['request_timeout']}")

if __name__ == "__main__":
    asyncio.run(main())
