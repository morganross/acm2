import asyncio
import logging
import sys
from app.infra.db.session import async_session_factory
from app.infra.db.repositories import ContentRepository

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    content_id = "4203a57f-df74-4a41-8b50-f4672672e0d1"
    
    async with async_session_factory() as session:
        repo = ContentRepository(session)
        content = await repo.get_by_id(content_id)
        if not content:
            logger.error(f"Content {content_id} not found")
            return
        
        logger.info(f"Content found: {content.name}")
        logger.info(f"Body length: {len(content.body)}")
        logger.info(f"Body: {content.body}")

if __name__ == "__main__":
    import os
    sys.path.append(os.getcwd())
    asyncio.run(main())
