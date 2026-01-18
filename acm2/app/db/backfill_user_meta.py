"""
Backfill per-user seed status for existing users.

- If user_meta is missing and per-user DB has data, mark seed_status=ready.
- If per-user DB is empty, run initialize_user to seed.
"""
import asyncio
import logging
import uuid
from typing import Optional

from sqlalchemy import select, func

from app.db.master import get_master_db
from app.db.seed_user import initialize_user
from app.infra.db.session import get_user_session_by_id
from app.infra.db.models.user_meta import UserMeta
from app.infra.db.models.preset import Preset
from app.infra.db.models.run import Run
from app.config import get_settings

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    import datetime
    return datetime.datetime.utcnow().isoformat()


async def _ensure_user_meta(user_id: int) -> str:
    settings = get_settings()
    if not settings.seed_version:
        raise ValueError("seed_version must be set")

    async with get_user_session_by_id(user_id) as session:
        result = await session.execute(
            select(UserMeta).where(UserMeta.user_id == user_id)
        )
        meta = result.scalar_one_or_none()
        if meta and meta.seed_status == "ready":
            return "ready"

        preset_count = await session.scalar(select(func.count()).select_from(Preset))
        run_count = await session.scalar(select(func.count()).select_from(Run))

        if preset_count and run_count:
            if not meta:
                meta = UserMeta(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    seed_status="ready",
                    seed_version=settings.seed_version,
                    seeded_at=None,
                )
                session.add(meta)
            else:
                meta.seed_status = "ready"
                meta.seed_version = settings.seed_version
            return "ready"

    await initialize_user(user_id)
    return "seeded"


async def main(user_id: Optional[int] = None) -> None:
    logging.basicConfig(level=logging.INFO)

    master_db = await get_master_db()
    try:
        users = await master_db.list_users()

        if user_id is not None:
            users = [u for u in users if u["id"] == user_id]

        if not users:
            logger.info("No users to process")
            return

        for user in users:
            uid = user["id"]
            try:
                status = await _ensure_user_meta(uid)
                logger.info(f"User {uid}: {status} ({_now_iso()})")
            except Exception as e:
                logger.error(f"User {uid}: failed ({e})")
    finally:
        await master_db.close()


if __name__ == "__main__":
    import sys

    arg = int(sys.argv[1]) if len(sys.argv) > 1 else None
    asyncio.run(main(arg))
