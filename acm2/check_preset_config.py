import asyncio
import json
from app.infra.db.session import async_session_factory
from app.infra.db.repositories import PresetRepository

async def main():
    preset_id = "83589d0e-c37e-4b19-a829-d46fdafa0e09"
    async with async_session_factory() as session:
        repo = PresetRepository(session)
        preset = await repo.get_by_id(preset_id)
        if preset:
            print(json.dumps(preset.config_overrides, indent=2))
        else:
            print("Preset not found")

if __name__ == "__main__":
    asyncio.run(main())
