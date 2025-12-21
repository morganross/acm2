import asyncio
import logging
import sys
from app.infra.db.session import async_session_factory
from app.infra.db.repositories import DocumentRepository

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    doc_id = "ba289490-4678-4337-85b4-66187c93e8b2"
    async with async_session_factory() as session:
        repo = DocumentRepository(session)
        doc = await repo.get_by_id(doc_id)
        if doc:
            logger.info(f"Content: {doc.content}")
        else:
            logger.error("Doc not found")

if __name__ == "__main__":
    import os
    sys.path.append(os.getcwd())
    asyncio.run(main())
