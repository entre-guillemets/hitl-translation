import logging
from typing import Dict, List, Optional
from datetime import datetime
from app.db.base import prisma

logger = logging.getLogger(__name__)

class HumanFeedbackService:
    def __init__(self):
        self.feedback_types = {
            'QUALITY_RATING': 'Quality Rating (1-5)',
            'PREFERENCE': 'Translation Preference',
            'ANNOTATION': 'Error Annotation',
            'CORRECTION': 'Manual Correction',
            'ENGINE_SELECTION': 'Engine Selection'
        }

    async def record_quality_rating(self, translation_string_id: str, rating: float, 
                                   reviewer: str = None, comments: str = None) -> Dict:
        """Record quality rating for a translation"""
        try:
            if not prisma.is_connected():
                await prisma.connect()
            
            # Create quality rating record
            quality_rating = await prisma.qualityrating.create(
                data={
                    "translationStringId": translation_string_id,
                    "qualityScore": rating,
                    "reviewer": reviewer,
                    "comments": comments,
                    "ratingType": "HUMAN_EVALUATION"
                }
            )
            
            # Update translation string with human feedback
            await prisma.translationstring.update(
                where={"id": translation_string_id},
                data={
                    "humanRating": rating,
                    "hasHumanFeedback": True,
                    "lastReviewed": datetime.now()
                }
            )
            
            logger.info(f"✓ Quality rating recorded: {rating}/5 for string {translation_string_id}")
            return {"success": True, "rating_id": quality_rating.id}
            
        except Exception as e:
            logger.error(f"Failed to record quality rating: {e}")
            return {"success": False, "error": str(e)}

    async def record_preference_comparison(self, source_text: str, translation_a: str, 
                                         translation_b: str, preferred: str, 
                                         language_pair: str, reviewer: str = None) -> Dict:
        """Record preference between two translations"""
        try:
            if not prisma.is_connected():
                await prisma.connect()
            
            preference = await prisma.preferencecomparison.create(
                data={
                    "sourceText": source_text,
                    "translationA": translation_a,
                    "translationB": translation_b,
                    "preferred": preferred,
                    "languagePair": language_pair,
                    "reviewer": reviewer
                }
            )
            
            logger.info(f"✓ Preference recorded: {preferred} for {language_pair}")
            return {"success": True, "preference_id": preference.id}
            
        except Exception as e:
            logger.error(f"Failed to record preference: {e}")
            return {"success": False, "error": str(e)}

    async def add_error_annotation(self, translation_string_id: str, category: str, 
                                  severity: str, comment: str, reviewer: str = None) -> Dict:
        """Add error annotation to a translation"""
        try:
            if not prisma.is_connected():
                await prisma.connect()
            
            from prisma.enums import AnnotationCategory, AnnotationSeverity
            
            # Map string values to enums
            category_map = {
                'accuracy': AnnotationCategory.ACCURACY,
                'fluency': AnnotationCategory.FLUENCY,
                'terminology': AnnotationCategory.TERMINOLOGY,
                'style': AnnotationCategory.STYLE,
                'grammar': AnnotationCategory.GRAMMAR
            }
            
            severity_map = {
                'minor': AnnotationSeverity.MINOR,
                'major': AnnotationSeverity.MAJOR,
                'critical': AnnotationSeverity.CRITICAL
            }
            
            annotation = await prisma.annotation.create(
                data={
                    "translationStringId": translation_string_id,
                    "category": category_map.get(category.lower(), AnnotationCategory.ACCURACY),
                    "severity": severity_map.get(severity.lower(), AnnotationSeverity.MINOR),
                    "comment": comment,
                    "reviewer": reviewer
                }
            )
            
            # Update translation string to mark as having annotations
            await prisma.translationstring.update(
                where={"id": translation_string_id},
                data={
                    "hasAnnotations": True,
                    "lastReviewed": datetime.now()
                }
            )
            
            logger.info(f"✓ Error annotation added: {category}/{severity}")
            return {"success": True, "annotation_id": annotation.id}
            
        except Exception as e:
            logger.error(f"Failed to add annotation: {e}")
            return {"success": False, "error": str(e)}

    async def record_manual_correction(self, translation_string_id: str, 
                                     corrected_text: str, reviewer: str = None) -> Dict:
        """Record manual correction of a translation"""
        try:
            if not prisma.is_connected():
                await prisma.connect()
            
            # Get original translation
            original = await prisma.translationstring.find_unique(
                where={"id": translation_string_id}
            )
            
            if not original:
                return {"success": False, "error": "Translation string not found"}
            
            # Update with correction
            updated = await prisma.translationstring.update(
                where={"id": translation_string_id},
                data={
                    "translatedText": corrected_text,
                    "originalTranslation": original.translatedText,
                    "hasReference": True,
                    "status": "CORRECTED",
                    "lastModified": datetime.now(),
                    "correctedBy": reviewer
                }
            )
            
            # Create correction record
            correction = await prisma.manualcorrection.create(
                data={
                    "translationStringId": translation_string_id,
                    "originalText": original.translatedText,
                    "correctedText": corrected_text,
                    "reviewer": reviewer,
                    "correctionReason": "MANUAL_IMPROVEMENT"
                }
            )
            
            logger.info(f"✓ Manual correction recorded for string {translation_string_id}")
            return {"success": True, "correction_id": correction.id}
            
        except Exception as e:
            logger.error(f"Failed to record correction: {e}")
            return {"success": False, "error": str(e)}

    async def get_feedback_summary(self, translation_request_id: str) -> Dict:
        """Get summary of human feedback for a translation request"""
        try:
            if not prisma.is_connected():
                await prisma.connect()
            
            # Get all translation strings for this request
            strings = await prisma.translationstring.find_many(
                where={"translationRequestId": translation_request_id},
                include={
                    "annotations": True,
                    "qualityRatings": True
                }
            )
            
            summary = {
                "total_strings": len(strings),
                "with_human_feedback": sum(1 for s in strings if s.hasHumanFeedback),
                "with_annotations": sum(1 for s in strings if s.hasAnnotations),
                "average_rating": 0,
                "annotation_breakdown": {},
                "correction_count": sum(1 for s in strings if s.hasReference)
            }
            
            # Calculate average rating
            ratings = [s.humanRating for s in strings if s.humanRating is not None]
            if ratings:
                summary["average_rating"] = sum(ratings) / len(ratings)
            
            # Annotation breakdown
            all_annotations = []
            for string in strings:
                all_annotations.extend(string.annotations)
            
            for annotation in all_annotations:
                category = annotation.category
                if category not in summary["annotation_breakdown"]:
                    summary["annotation_breakdown"][category] = 0
                summary["annotation_breakdown"][category] += 1
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to get feedback summary: {e}")
            return {"error": str(e)}

# Global human feedback service instance
human_feedback_service = HumanFeedbackService()
