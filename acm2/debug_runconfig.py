"""Debug script to trace the actual execute flow and check config."""
import asyncio
import sys
sys.path.insert(0, '.')

from app.infra.db.session import async_session_factory
from app.infra.db.repositories.preset import PresetRepository
from app.infra.db.repositories.content import ContentRepository
from app.infra.db.repositories.document import DocumentRepository
from app.infra.db.repositories.run import RunRepository
from app.services.run_executor import RunConfig
from app.adapters.base import GeneratorType as AdapterGeneratorType

# Debug script uses a fixed test user ID
DEBUG_USER_ID = 1

async def main():
    async with async_session_factory() as session:
        preset_repo = PresetRepository(session, user_id=DEBUG_USER_ID)
        content_repo = ContentRepository(session, user_id=DEBUG_USER_ID)
        doc_repo = DocumentRepository(session, user_id=DEBUG_USER_ID)
        
        preset = await preset_repo.get_by_id('86f721fc-742c-4489-9626-f148cb3d6209')
        
        if not preset:
            print("Preset not found!")
            return
        
        # Simulate what execute_preset does
        overrides = preset.config_overrides or {}
        combine_config = overrides.get("combine", {})
        eval_cfg = overrides.get("eval", {})
        concurrency_cfg = overrides.get("concurrency", {})
        fpf_cfg = overrides.get("fpf", {})
        
        # Build combine values
        combine_enabled = combine_config.get("enabled")
        combine_strategy = combine_config.get("strategy")
        combine_models_list = combine_config.get("selected_models")
        
        print("=== COMBINE CONFIG ===")
        print(f"combine_enabled: {combine_enabled} (type: {type(combine_enabled)})")
        print(f"combine_strategy: {combine_strategy}")
        print(f"combine_models_list: {combine_models_list}")
        
        # Load combine instructions
        combine_instructions = ""
        if preset.combine_instructions_id:
            content = await content_repo.get_by_id(preset.combine_instructions_id)
            if content and content.body:
                combine_instructions = content.body
                print(f"combine_instructions: loaded ({len(combine_instructions)} chars)")
        
        # Now build the RunConfig like presets.py does
        print("\n=== BUILDING RunConfig ===")
        
        # Minimal config for testing
        try:
            config = RunConfig(
                user_id=DEBUG_USER_ID,
                document_ids=["test"],
                document_contents={"test": "test content"},
                instructions="test",
                generators=[AdapterGeneratorType.FPF],
                models=["openai:gpt-5.1"],
                model_settings={"openai:gpt-5.1": {"provider": "openai", "model": "gpt-5.1", "temperature": 0.7, "max_tokens": 1000}},
                iterations=1,
                eval_iterations=1,
                generation_concurrency=1,
                eval_concurrency=1,
                request_timeout=60,
                eval_timeout=60,
                max_retries=1,
                retry_delay=1.0,
                log_level="INFO",
                enable_single_eval=True,
                enable_pairwise=True,
                eval_judge_models=["openai:gpt-5-mini"],
                eval_retries=1,
                eval_temperature=0.0,
                eval_max_tokens=1000,
                enable_combine=combine_enabled,  # <-- THIS IS THE KEY
                combine_strategy=combine_strategy or "",
                combine_models=combine_models_list if combine_enabled else [],
                single_eval_instructions="test",
                pairwise_eval_instructions="test",
                eval_criteria="test",
                combine_instructions=combine_instructions,
            )
            print(f"RunConfig created successfully!")
            print(f"  config.enable_combine = {config.enable_combine}")
            print(f"  config.combine_strategy = {config.combine_strategy}")
            print(f"  config.combine_models = {config.combine_models}")
            print(f"  config.combine_instructions = {len(config.combine_instructions or '')} chars")
        except Exception as e:
            print(f"ERROR creating RunConfig: {e}")

if __name__ == "__main__":
    asyncio.run(main())
