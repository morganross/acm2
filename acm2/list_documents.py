import asyncio
import logging
import sys
from app.infra.db.session import async_session_factory
from app.infra.db.repositories import DocumentRepository

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    async with async_session_factory() as session:
        repo = DocumentRepository(session)
        docs = await repo.get_active()
        logger.info(f"Found {len(docs)} documents")
        for doc in docs:
            logger.info(f"ID: {doc.id}, Name: {doc.name}, Path: {doc.path}")

if __name__ == "__main__":
    import os
    sys.path.append(os.getcwd())
    asyncio.run(main())
