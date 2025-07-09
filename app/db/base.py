from prisma import Prisma
import logging

logger = logging.getLogger(__name__)

# Initialize Prisma client
prisma = Prisma()

async def initialize_database():
    """Initialize database connection"""
    try:
        await prisma.connect()
        logger.info("✓ Database connected successfully")
        # Test basic query
        count = await prisma.translationmemory.count()
        logger.info(f"✓ Found {count} existing TM entries")
    except Exception as e:
        logger.error(f"⚠ Database connection failed: {e}")
        logger.warning("⚠ Running without database - some features will be limited")

async def cleanup_database():
    """Cleanup database"""
    try:
        await prisma.disconnect()
        logger.info("✓ Database disconnected")
    except Exception as e:
        logger.error(f"⚠ Error disconnecting: {e}")
