import asyncio
from app.infra.database import get_db
from app.domain.presets import Preset

async def main():
    async for db in get_db():
        preset = await db.get(Preset, '86f721fc-742c-4489-9626-f148cb3d6209')
        print('instruction_ids:', preset.instruction_ids)
        print('generators:', preset.generators)
        print('models:', preset.models)
        print('fpf_config:', preset.fpf_config)
        break

asyncio.run(main())