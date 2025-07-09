import logging
from typing import Dict, List
from difflib import SequenceMatcher
from prisma import Prisma # Assuming Prisma client is passed or imported

logger = logging.getLogger(__name__)

class FuzzyMatchingService:
    def __init__(self, threshold=0.7, prisma: Prisma = None):
        self.threshold = threshold
        self.prisma = prisma # Dependency injection for Prisma client

    def calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts using SequenceMatcher"""
        return SequenceMatcher(None, text1.lower().strip(), text2.lower().strip()).ratio()

    async def find_fuzzy_matches(self, source_text: str, target_language: str, source_language: str) -> List[Dict]:
        """Find fuzzy matches in translation memory using database"""
        try:
            if self.prisma is None:
                raise ValueError("Prisma client not initialized in FuzzyMatchingService.")
            
            if not self.prisma.is_connected():
                await self.prisma.connect()

            # Get all TM entries for the language pair from database
            tm_entries = await self.prisma.translationmemory.find_many(
                where={
                    "sourceLanguage": source_language,
                    "targetLanguage": target_language
                }
            )

            matches = []
            for tm_entry in tm_entries:
                similarity = self.calculate_similarity(source_text, tm_entry.sourceText)

                if similarity >= self.threshold:
                    match_percentage = int(similarity * 100)
                    matches.append({
                        "tm_id": tm_entry.id,
                        "source_text": tm_entry.sourceText,
                        "target_text": tm_entry.targetText,
                        "similarity": similarity,
                        "match_percentage": match_percentage,
                        "domain": tm_entry.domain,
                        "quality": tm_entry.quality.lower(),
                        "last_used": tm_entry.lastUsed.isoformat() if tm_entry.lastUsed else None
                    })

            matches.sort(key=lambda x: x["similarity"], reverse=True)
            return matches[:5]

        except Exception as e:
            logger.error(f"Error in fuzzy matching: {e}")
            return []