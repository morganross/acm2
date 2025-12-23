"""Debug script to check config building for a preset."""
import asyncio
import sys
sys.path.insert(0, '.')

from app.infra.db.session import async_session_factory
from app.infra.db.repositories.preset import PresetRepository
from app.infra.db.repositories.content import ContentRepository

async def main():
    async with async_session_factory() as session:
        preset_repo = PresetRepository(session)
        preset = await preset_repo.get_by_id('86f721fc-742c-4489-9626-f148cb3d6209')
        
        if not preset:
            print("Preset not found!")
            return
        
        print("=== PRESET BASIC INFO ===")
        print(f"Name: {preset.name}")
        print(f"ID: {preset.id}")
        
        print("\n=== CONFIG OVERRIDES ===")
        overrides = preset.config_overrides or {}
        combine_config = overrides.get("combine", {})
        
        print(f"combine_config: {combine_config}")
        print(f"combine_config.get('enabled'): {combine_config.get('enabled')}")
        print(f"type: {type(combine_config.get('enabled'))}")
        
        # Simulate what the code does
        combine_enabled = combine_config.get("enabled")
        print(f"\ncombine_enabled = {combine_enabled} (truthy: {bool(combine_enabled)})")
        
        combine_strategy = combine_config.get("strategy")
        print(f"combine_strategy = {combine_strategy}")
        
        combine_models_list = combine_config.get("selected_models")
        print(f"combine_models_list = {combine_models_list}")
        
        # Check combine_instructions_id
        print(f"\ncombine_instructions_id: {preset.combine_instructions_id}")
        
        if preset.combine_instructions_id:
            content_repo = ContentRepository(session)
            content = await content_repo.get_by_id(preset.combine_instructions_id)
            if content:
                print(f"Combine instructions loaded: {content.name} ({len(content.body or '')} chars)")
            else:
                print("WARNING: Combine instructions NOT FOUND")
        else:
            print("WARNING: No combine_instructions_id set!")

if __name__ == "__main__":
    asyncio.run(main())
