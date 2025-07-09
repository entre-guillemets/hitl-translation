from app.db.base import prisma
from app.services.fuzzy_matching_service import fuzzy_matcher
from app.services.multi_engine_service import multi_engine_service

async def get_database():
    """Get database connection"""
    if not prisma.is_connected():
        await prisma.connect()
    return prisma

def get_fuzzy_matcher():
    """Get fuzzy matching service"""
    return fuzzy_matcher

def get_multi_engine_service():
    """Get multi-engine service"""
    return multi_engine_service
