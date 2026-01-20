"""
Seed a new user's data with a preset from the shared database.

This script copies a single preset and its associated contents to a new user.
"""
import asyncio
import uuid
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import get_settings
from app.infra.db.session import async_session_factory, engine, _get_or_create_user_engine
from app.infra.db.models import Base
from app.infra.db.models.preset import Preset
from app.infra.db.models.content import Content
from app.infra.db.models.user_meta import UserMeta
from app.infra.db.models.run import Run, RunStatus

logger = logging.getLogger(__name__)
_seed_locks: Dict[int, asyncio.Lock] = {}


async def seed_user_data(user_id: int, source_session: AsyncSession, target_session: AsyncSession) -> Dict[str, str]:
    """
    Seed a new user's database with a preset and associated contents.
    
    Reads from source_session (shared DB) and writes to 
    target_session (per-user DB).
    
    Args:
        user_id: The user's ID from the master database
        source_session: SQLAlchemy session connected to shared DB (for reading defaults)
        target_session: SQLAlchemy session connected to per-user DB (for writing)
        
    Returns:
        Dict mapping original IDs to new IDs for the user
    """
    id_mapping = {}
    
    try:
        settings = get_settings()
        if not settings.seed_preset_id:
            raise ValueError("seed_preset_id must be set")
        if not settings.seed_version:
            raise ValueError("seed_version must be set")

        # 1. Load preset from the source database
        preset_result = await source_session.execute(
            select(Preset)
            .where(Preset.id == settings.seed_preset_id, Preset.is_deleted == False)
        )
        original_preset = preset_result.scalar_one_or_none()
        
        if not original_preset:
            logger.error("No preset found in source DB for seeding")
            return id_mapping

        # Create or update user_meta to mark seed in progress
        seed_version = settings.seed_version
        meta_result = await target_session.execute(
            select(UserMeta).where(UserMeta.user_id == user_id)
        )
        meta = meta_result.scalar_one_or_none()
        if not meta:
            meta = UserMeta(
                id=str(uuid.uuid4()),
                user_id=user_id,
                seed_status="in_progress",
                seed_version=seed_version,
                seeded_at=None,
            )
            target_session.add(meta)
        else:
            meta.seed_status = "in_progress"
            meta.seed_version = seed_version
            meta.seeded_at = None

        # 2. Copy content items referenced by the preset
        # NOTE: preset.documents contains Content IDs (content_type=input_document), 
        # NOT entries from the legacy 'documents' table
        content_ids = set()
        # Add input documents from preset.documents field
        content_ids.update(original_preset.documents or [])
        # Add input content IDs 
        content_ids.update(original_preset.input_content_ids or [])
        for content_id in [
            original_preset.generation_instructions_id,
            original_preset.single_eval_instructions_id,
            original_preset.pairwise_eval_instructions_id,
            original_preset.eval_criteria_id,
            original_preset.combine_instructions_id,
        ]:
            if content_id:
                content_ids.add(content_id)

        if content_ids:
            result = await source_session.execute(
                select(Content).where(Content.id.in_(content_ids), Content.is_deleted == False)
            )
            originals = {content.id: content for content in result.scalars().all()}
            missing = set(content_ids) - set(originals.keys())
            if missing:
                raise ValueError(f"Content not found in source DB: {sorted(missing)}")

            new_contents = []
            for content_id, original in originals.items():
                new_id = str(uuid.uuid4())
                new_contents.append(
                    Content(
                        id=new_id,
                        user_id=user_id,
                        name=original.name,
                        content_type=original.content_type,
                        body=original.body,
                        variables=dict(original.variables) if original.variables else {},
                        description=original.description,
                        tags=list(original.tags) if original.tags else [],
                        is_deleted=False,
                    )
                )
                id_mapping[content_id] = new_id
                logger.info(f"Created content '{original.name}' for user {user_id}: {new_id}")

            target_session.add_all(new_contents)

        await target_session.flush()
        
        new_preset_id = str(uuid.uuid4())
        
        # Update config_overrides to reference new content IDs
        config_overrides = dict(original_preset.config_overrides) if original_preset.config_overrides else {}
        config_overrides = _deep_replace_ids(config_overrides, id_mapping)
        
        # Create new preset for user in target DB
        # Remap document IDs to the newly created copies
        new_document_ids = [id_mapping.get(doc_id, doc_id) for doc_id in (original_preset.documents or [])]
        new_preset = Preset(
            id=new_preset_id,
            user_id=user_id,
            name=original_preset.name,
            description=original_preset.description,
            documents=new_document_ids,
            models=list(original_preset.models) if original_preset.models else [],
            generators=list(original_preset.generators) if original_preset.generators else [],
            iterations=original_preset.iterations,
            evaluation_enabled=original_preset.evaluation_enabled,
            pairwise_enabled=original_preset.pairwise_enabled,
            gptr_config=dict(original_preset.gptr_config) if original_preset.gptr_config else None,
            fpf_config=dict(original_preset.fpf_config) if original_preset.fpf_config else None,
            log_level=original_preset.log_level,
            max_retries=original_preset.max_retries,
            retry_delay=original_preset.retry_delay,
            request_timeout=original_preset.request_timeout,
            eval_timeout=original_preset.eval_timeout,
            fpf_max_retries=original_preset.fpf_max_retries,
            fpf_retry_delay=original_preset.fpf_retry_delay,
            eval_retries=original_preset.eval_retries,
            generation_concurrency=original_preset.generation_concurrency,
            eval_concurrency=original_preset.eval_concurrency,
            eval_iterations=original_preset.eval_iterations,
            fpf_log_output=original_preset.fpf_log_output,
            fpf_log_file_path=original_preset.fpf_log_file_path,
            post_combine_top_n=original_preset.post_combine_top_n,
            config_overrides=config_overrides,
            input_source_type=original_preset.input_source_type,
            input_content_ids=[id_mapping.get(cid) for cid in (original_preset.input_content_ids or [])],
            github_input_paths=list(original_preset.github_input_paths) if original_preset.github_input_paths else [],
            github_output_path=original_preset.github_output_path,
            # Update content references to new IDs
            generation_instructions_id=id_mapping.get(original_preset.generation_instructions_id),
            single_eval_instructions_id=id_mapping.get(original_preset.single_eval_instructions_id),
            pairwise_eval_instructions_id=id_mapping.get(original_preset.pairwise_eval_instructions_id),
            eval_criteria_id=id_mapping.get(original_preset.eval_criteria_id),
            combine_instructions_id=id_mapping.get(original_preset.combine_instructions_id),
            is_deleted=False,
        )
        target_session.add(new_preset)
        id_mapping[original_preset.id] = new_preset_id
        logger.info(f"Created preset '{original_preset.name}' for user {user_id}: {new_preset_id}")
        
        # NOTE: Sample run copying removed - source DB has incompatible schema (no user_id column)
        # Seed a historical run so evaluation tabs render immediately
        
        meta.seed_status = "ready"
        meta.seeded_at = datetime.utcnow()

        # Commit DB after content and preset seeding
        await target_session.commit()
        logger.info(f"Successfully seeded data for user {user_id}")
        
    except Exception as e:
        logger.error(f"Error seeding user {user_id}: {e}")
        await target_session.rollback()
        raise
    
    return id_mapping


async def initialize_user(user_id: int) -> Dict[str, str]:
    """
    Full initialization for a new user:
    1. Create per-user SQLite database schema using SQLAlchemy
    2. Seed per-user database with copies of a preset + contents from shared DB
    
    Args:
        user_id: The user's ID from the master database
        
    Returns:
        Dict mapping original IDs to new user-specific IDs
    """
    lock = _seed_locks.setdefault(user_id, asyncio.Lock())
    async with lock:
        # 1. Get or create per-user SQLAlchemy engine (creates SQLite file and schema)
        _, target_session_factory = await _get_or_create_user_engine(user_id)
        logger.info(f"Initialized per-user SQLAlchemy database for user {user_id}")

        # 2. Use TWO sessions: source (shared DB) and target (per-user DB)

        async with async_session_factory() as source_session:
            async with target_session_factory() as target_session:
                try:
                    existing_meta = await target_session.execute(
                        select(UserMeta).where(UserMeta.user_id == user_id)
                    )
                    meta = existing_meta.scalar_one_or_none()
                    if meta and meta.seed_status == "ready":
                        logger.info(f"User {user_id} already seeded (version={meta.seed_version})")
                        return {}
                    id_mapping = await seed_user_data(user_id, source_session, target_session)
                    # Commit is handled in seed_user_data
                except Exception:
                    await target_session.rollback()
                    raise

        return id_mapping


async def main():
    """Test seeding for a sample user."""
    import sys

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("Usage: python -m app.db.seed_user <user_id>")
        sys.exit(1)

    user_id = int(sys.argv[1])

    # Ensure tables exist with new columns
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    id_mapping = await initialize_user(user_id)

    print(f"\nSeeded data for user {user_id}:")
    for original_id, new_id in id_mapping.items():
        print(f"  {original_id} -> {new_id}")


def _deep_replace_ids(value: object, id_map: Dict[str, str]) -> object:
    if isinstance(value, dict):
        return {k: _deep_replace_ids(v, id_map) for k, v in value.items()}
    if isinstance(value, list):
        return [_deep_replace_ids(v, id_map) for v in value]
    if isinstance(value, str) and value in id_map:
        return id_map[value]
    return value


if __name__ == "__main__":
    asyncio.run(main())
