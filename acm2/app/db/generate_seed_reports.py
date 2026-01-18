"""
Generate reports for the configured seed run in the shared DB.
"""
import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.infra.db.session import async_session_factory
from app.infra.db.models.run import Run
from app.evaluation.reports.generator import ReportGenerator
from app.api.routes.runs.helpers import to_detail

logger = logging.getLogger(__name__)


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()

    raise ValueError("Seed report generation is disabled because historical run seeding is removed")


if __name__ == "__main__":
    asyncio.run(main())
