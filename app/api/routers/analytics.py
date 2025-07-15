# app/api/routers/analytics.py

from fastapi import APIRouter, HTTPException, Query
import logging
from datetime import datetime, timedelta
import statistics
import difflib
from collections import defaultdict
from typing import Optional, List, Dict, Any
from collections import Counter

from app.db.base import prisma
from app.schemas.quality import QualityRating
from prisma.enums import AnnotationCategory, AnnotationSeverity, QualityLabel, MTModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analytics", tags=["Quality Assessment", "Analytics"])

# Global variable and setter for health_service
health_service = None
def set_health_service(service):
    global health_service
    health_service = service

# Helper functions
def calculate_correlation(x_vals, y_vals):
    if len(x_vals) < 2 or len(y_vals) < 2:
        return 0.0
    
    mean_x = statistics.mean(x_vals)
    mean_y = statistics.mean(y_vals)
    
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(x_vals, y_vals))
    sum_sq_x = sum((x - mean_x) ** 2 for x in x_vals)
    sum_sq_y = sum((y - mean_y) ** 2 for y in y_vals)
    
    denominator = (sum_sq_x * sum_sq_y) ** 0.5
    return numerator / denominator if denominator != 0 else 0.0

def get_engine_type_from_model(model_name: str) -> str:
    """Map model name (which is a string representation of MTModel enum) to engine type."""
    engine_mapping = {
        MTModel.MARIAN_MT_EN_FR.value: "opus_fast",
        MTModel.MARIAN_MT_FR_EN.value: "opus_fast",
        MTModel.MARIAN_MT_EN_JP.value: "opus_fast",
        MTModel.ELAN_MT_JP_EN.value: "elan_specialist",
        MTModel.T5_BASE.value: "t5_versatile",
        MTModel.NLLB_200.value: "nllb_multilingual",
        MTModel.PIVOT_JP_EN_FR.value: "pivot_elan_helsinki",
        "OPUS_JA_EN": "opus_fast",
        "T5_MULTILINGUAL": "t5_versatile",
    }
    return engine_mapping.get(model_name, "unknown")

def calculate_edit_distance(original: str, edited: str) -> float:
    """Calculate normalized edit distance between two strings"""
    return 1 - difflib.SequenceMatcher(None, original, edited).ratio()

def calculate_improvement_score(original: str, edited: str, source: str) -> float:
    """Calculate improvement score based on various metrics"""
    original_words = set(original.lower().split())
    edited_words = set(edited.lower().split())
    source_words = set(source.lower().split())
    
    original_overlap = len(original_words & source_words) / len(source_words) if source_words else 0
    edited_overlap = len(edited_words & source_words) / len(source_words) if source_words else 0
    
    return max(0, edited_overlap - original_overlap)

def classify_edit_type(edit_distance: float, text_length: int) -> str:
    """Classify edit type based on distance and text length"""
    if text_length == 0: # Avoid division by zero
        return "minor" # Or "no_change" or similar, depending on desired categorization for empty text
    
    normalized_edit_distance = edit_distance 
    
    if normalized_edit_distance < 0.1:
        return "minor"
    elif normalized_edit_distance < 0.3:
        return "moderate"
    else:
        return "major"

def calculate_translator_summary(comparisons: list) -> list:
    """Calculate summary statistics for translators"""
    if not comparisons:
        return []  
    
    language_pairs_summary = {}
    for comp in comparisons:
        pair = comp["languagePair"]
        translator_id_key = f"Translator-{pair}" 
        
        if translator_id_key not in language_pairs_summary:
            language_pairs_summary[translator_id_key] = {
                "translatorId": translator_id_key,
                "totalEdits": 0,
                "improvementScores": [],
                "editDistances": [],
                "languagePairs": set(), 
                "editTypes": {"minor": 0, "moderate": 0, "major": 0}
            }
        
        language_pairs_summary[translator_id_key]["totalEdits"] += 1
        language_pairs_summary[translator_id_key]["improvementScores"].append(comp["improvementScore"])
        language_pairs_summary[translator_id_key]["editDistances"].append(comp["editDistance"])
        language_pairs_summary[translator_id_key]["editTypes"][comp["editType"]] += 1
        language_pairs_summary[translator_id_key]["languagePairs"].add(pair)
    
    summary = []
    for translator_data in language_pairs_summary.values():
        avg_improvement = sum(translator_data["improvementScores"]) / len(translator_data["improvementScores"]) if translator_data["improvementScores"] else 0
        avg_edit = sum(translator_data["editDistances"]) / len(translator_data["editDistances"]) if translator_data["editDistances"] else 0

        summary.append({
            "translatorId": translator_data["translatorId"],
            "totalEdits": translator_data["totalEdits"],
            "avgImprovementScore": avg_improvement,
            "avgEditDistance": avg_edit,
            "languagePairs": list(translator_data["languagePairs"]), # Convert set to list for JSON serialization
            "editTypes": translator_data["editTypes"]
        })
    
    return summary

async def get_human_preferences_data(date_filter, lang_filter):
    """Get human preference data"""
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        all_prefs = await prisma.enginepreference.find_many(where={**date_filter, **lang_filter}) 
        
        engine_stats = {}
        for pref in all_prefs:
            key = f"{pref.selectedEngine}_{pref.sourceLanguage}_{pref.targetLanguage}_{pref.preferenceReason or 'unknown'}"
            if key not in engine_stats:
                engine_stats[key] = {
                    "engine": pref.selectedEngine,
                    "sourceLanguage": pref.sourceLanguage,
                    "targetLanguage": pref.targetLanguage,
                    "preferenceReason": pref.preferenceReason or "unknown",
                    "count": 0,
                    "ratings": [],
                    "satisfactions": []
                }
            
            engine_stats[key]["count"] += 1
            if pref.rating is not None:
                engine_stats[key]["ratings"].append(pref.rating)
            if pref.overallSatisfaction is not None:
                engine_stats[key]["satisfactions"].append(pref.overallSatisfaction)
        
        engine_preferences = []
        for stats in engine_stats.values():
            avg_rating = sum(stats["ratings"]) / len(stats["ratings"]) if stats["ratings"] else 0
            avg_satisfaction = sum(stats["satisfactions"]) / len(stats["satisfactions"]) if stats["satisfactions"] else 0
            
            engine_preferences.append({
                "engine": stats["engine"],
                "selectionCount": stats["count"],
                "avgRating": avg_rating,
                "languagePair": f"{stats['sourceLanguage']}-{stats['targetLanguage']}",
                "preferenceReason": stats["preferenceReason"],
                "overallSatisfaction": avg_satisfaction
            })
        
        all_strings = await prisma.translationstring.find_many(
            where={**date_filter, **lang_filter, "reviewerExpertise": {"not": None}}
        )
        
        reviewer_stats = {}
        for string in all_strings:
            key = f"{string.reviewerExpertise}_{string.approvalType or 'unknown'}"
            if key not in reviewer_stats:
                reviewer_stats[key] = {
                    "reviewerExpertise": string.reviewerExpertise,
                    "approvalType": string.approvalType or "unknown",
                    "times": [],
                    "cognitive_loads": [],
                    "count": 0
                }
            
            reviewer_stats[key]["count"] += 1
            if string.timeToReview is not None:
                reviewer_stats[key]["times"].append(string.timeToReview)
            if string.cognitiveLoad is not None:
                reviewer_stats[key]["cognitive_loads"].append(string.cognitiveLoad)
        
        reviewer_behavior = []
        for stats in reviewer_stats.values():
            avg_time = sum(stats["times"]) / len(stats["times"]) if stats["times"] else 0
            avg_cognitive = sum(stats["cognitive_loads"]) / len(stats["cognitive_loads"]) if stats["cognitive_loads"] else 0
            
            reviewer_behavior.append({
                "reviewerExpertise": stats["reviewerExpertise"],
                "avgTimeToReview": avg_time,
                "avgCognitiveLoad": avg_cognitive,
                "approvalType": stats["approvalType"],
                "count": stats["count"]
            })
        
        reason_stats = {}
        for pref in all_prefs:
            if pref.preferenceReason:
                reason = pref.preferenceReason
                if reason not in reason_stats:
                    reason_stats[reason] = {"count": 0, "satisfactions": []}
                reason_stats[reason]["count"] += 1
                if pref.overallSatisfaction is not None:
                    reason_stats[reason]["satisfactions"].append(pref.overallSatisfaction)
        
        preference_reasons = []
        for reason, data in reason_stats.items():
            avg_satisfaction = sum(data["satisfactions"]) / len(data["satisfactions"]) if data["satisfactions"] else 0
            preference_reasons.append({
                "reason": reason,
                "count": data["count"],
                "avgSatisfaction": avg_satisfaction
            })
        
        return {
            "enginePreferences": engine_preferences,
            "reviewerBehavior": reviewer_behavior,
            "preferenceReasons": preference_reasons
        }
        
    except Exception as e:
        logger.error(f"Error fetching human preferences data: {e}")
        return {"enginePreferences": [], "reviewerBehavior": [], "preferenceReasons": []}

async def get_annotations_data(date_filter, lang_filter):
    """Get annotation data"""
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        all_annotations = await prisma.annotation.find_many(
            where={**date_filter},
            include={
                "translationString": {
                    "include": {
                        "translationRequest": True,
                        "modelOutputs": True
                    }
                }
            }
        )
        
        # Further filter by language pair if specified, manually
        if lang_filter and "targetLanguage" in lang_filter:
            target_lang_filter = lang_filter["targetLanguage"]["contains"].lower()
            all_annotations = [
                ann for ann in all_annotations
                if ann.translationString and ann.translationString.targetLanguage.lower() == target_lang_filter
            ]

        logger.info(f"Found {len(all_annotations)} annotations for dashboard")
        
        error_stats = {}
        severity_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
        
        for annotation in all_annotations:
            # Safely get category and severity values (from Enum or string)
            annotation_category_value = annotation.category.value if hasattr(annotation.category, 'value') else str(annotation.category)
            annotation_severity_value = annotation.severity.value if hasattr(annotation.severity, 'value') else str(annotation.severity)

            if annotation_severity_value in severity_counts:
                severity_counts[annotation_severity_value] += 1
            
            model_name = "unknown"
            if annotation.translationString and annotation.translationString.translationRequest:
                if annotation.translationString.translationRequest.mtModel:
                    # Safely get model name from enum or string
                    model_name = annotation.translationString.translationRequest.mtModel.value if hasattr(annotation.translationString.translationRequest.mtModel, 'value') else str(annotation.translationString.translationRequest.mtModel)
            
            if annotation.translationString and annotation.translationString.modelOutputs:
                if len(annotation.translationString.modelOutputs) > 0:
                    model_name = annotation.translationString.modelOutputs[0].modelName
            
            error_type = getattr(annotation, 'errorType', None) or 'general'
            key = f"{model_name}_{annotation_category_value}_{error_type}_{annotation_severity_value}"
            
            if key not in error_stats:
                error_stats[key] = {
                    "model": model_name,
                    "category": annotation_category_value,
                    "errorType": error_type,
                    "severity": annotation_severity_value,
                    "count": 0
                }
            error_stats[key]["count"] += 1
        
        logger.info(f"Severity counts: {severity_counts}")
        logger.info(f"Error stats keys: {len(error_stats)}")
        
        severity_weights = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
        error_heatmap = []
        for stats in error_stats.values():
            pain_index = stats["count"] * severity_weights.get(stats["severity"], 1)
            error_heatmap.append({
                **stats,
                "painIndex": pain_index
            })
        
        severity_breakdown = []
        for severity, count in severity_counts.items():
            if count > 0:
                severity_breakdown.append({
                    "severity": severity,
                    "count": count,
                    "model": "all" 
                })
        
        # Prepare data for stacked bar chart by errorType and model
        stacked_pain_data = defaultdict(lambda: defaultdict(int))
        for item in error_heatmap:
            stacked_pain_data[item['model']][item['errorType']] += item['painIndex']

        formatted_stacked_pain_data = []
        for model, error_types_data in stacked_pain_data.items():
            entry = {"model": model}
            entry.update(error_types_data)
            formatted_stacked_pain_data.append(entry)

        logger.info(f"Returning {len(severity_breakdown)} severity items and {len(error_heatmap)} heatmap items")
        
        return {
            "errorHeatmap": error_heatmap,
            "severityBreakdown": severity_breakdown,
            "spanAnalysis": [], 
            "stackedPainIndexByErrorType": formatted_stacked_pain_data 
        }
        
    except Exception as e:
        logger.error(f"Error in get_annotations_data: {e}")
        import traceback
        traceback.print_exc()
        return {"errorHeatmap": [], "severityBreakdown": [], "spanAnalysis": [], "stackedPainIndexByErrorType": []}

async def get_multi_engine_data(date_filter, lang_filter):
    """Get multi-engine and pivot translation data"""
    try:
        if not prisma.is_connected():
            await prisma.connect()

        all_engine_preferences = await prisma.enginepreference.find_many(
            where={**date_filter, **lang_filter}
        )
        
        selection_trends_dict = {}
        for pref in all_engine_preferences:
            selection_method = pref.selectionMethod or "unknown"
            model_combination = pref.modelCombination or "single"
            key = (selection_method, model_combination) # Use a tuple as key for grouping
            
            if key not in selection_trends_dict:
                selection_trends_dict[key] = {
                    "selectionMethod": selection_method,
                    "modelCombination": model_combination,
                    "count": 0
                }
            selection_trends_dict[key]["count"] += 1

        selection_trends = []
        for (selection_method, model_combination), data in selection_trends_dict.items():
            
            selection_trends.append({
                "date": datetime.now().strftime("%Y-%m-%d"), 
                "selectionMethod": data["selectionMethod"],
                "count": data["count"],
                "modelCombination": data["modelCombination"]
            })
        
        # Pivot quality analysis
        pivot_strings = await prisma.translationstring.find_many(
            where={
                **date_filter,
                **lang_filter,
                "translationType": "PIVOT",
                "intermediateTranslation": {"not": None}
            },
            include={"qualityMetrics": True}
        )
        
        pivot_quality = []
        for string in pivot_strings:
            if string.qualityMetrics:
                for metric in string.qualityMetrics:
                    if metric.metricXScore is not None:
                        pivot_quality.append({
                            "modelCombination": string.selectedModelCombination or "unknown",
                            "directQuality": 0, # Placeholder, needs actual direct quality
                            "pivotQuality": metric.metricXScore,
                            "intermediateQuality": 0 # Placeholder, needs actual intermediate quality
                        })
        
        # Inter-rater agreement (simplified) 
        all_annotations_for_inter_rater = await prisma.annotation.find_many(
            where={**date_filter, "reviewer": {"not": None}}
        )
        
        inter_rater_dict = {}
        for annotation in all_annotations_for_inter_rater:
            reviewer = annotation.reviewer
            if reviewer not in inter_rater_dict:
                inter_rater_dict[reviewer] = {"count": 0}
            inter_rater_dict[reviewer]["count"] += 1
        
        inter_rater = []
        for reviewer, data in inter_rater_dict.items():
            inter_rater.append({
                "annotatorPair": f"{reviewer}-system",
                "agreement": 0.8, # Placeholder
                "category": "overall"
            })
        
        return {
            "selectionTrends": selection_trends,
            "pivotQuality": pivot_quality,
            "interRaterAgreement": inter_rater
        }
    except Exception as e:
        logger.error(f"Error fetching multi-engine data: {e}")
        return {"selectionTrends": [], "pivotQuality": [], "interRaterAgreement": []}

async def get_quality_scores_data(date_filter, lang_filter):
    """Get quality scores data with actual correlations"""
    try:
        if not prisma.is_connected():
            await prisma.connect()

        quality_metrics = await prisma.qualitymetrics.find_many(
            where={
                **date_filter,
                **lang_filter,
                "hasReference": True, # Filter for post-edited data
                "bleuScore": {"not": None},
                "cometScore": {"not": None},
                "terScore": {"not": None}
                # "metricXScore": {"not": None} # Exclude MetricX from direct correlation as per request
            }
        )

        if not quality_metrics:
            return {
                "evaluationModes": [],
                "correlationMatrix": [],
                "scoreDistribution": []
            }

        bleu_scores = [m.bleuScore for m in quality_metrics if m.bleuScore is not None]
        comet_scores = [m.cometScore for m in quality_metrics if m.cometScore is not None]
        ter_scores = [m.terScore for m in quality_metrics if m.terScore is not None]
        # metricx_scores = [m.metricXScore for m in quality_metrics if m.metricXScore is not None] # Exclude MetricX

        correlations = []
        
        # Metric pairs for correlation matrix (excluding MetricX as per request)
        metric_pairs = [
            ("BLEU", "COMET", bleu_scores, comet_scores),
            ("BLEU", "TER", bleu_scores, ter_scores),
            ("COMET", "TER", comet_scores, ter_scores),
            # ("BLEU", "MetricX", bleu_scores, metricx_scores), # Exclude
            # ("COMET", "MetricX", comet_scores, metricx_scores), # Exclude
            # ("TER", "MetricX", ter_scores, metricx_scores) # Exclude
        ]

        for metric1, metric2, scores1, scores2 in metric_pairs:
            # Ensure enough data for correlation calculation (at least 2 data points)
            # and that there are actual scores to compute
            if scores1 and scores2 and len(scores1) > 1 and len(scores2) > 1:
                correlation = calculate_correlation(scores1, scores2)
                correlations.append({
                    "metric1": metric1,
                    "metric2": metric2,
                    "correlation": correlation,
                    "pValue": 0.05 # Placeholder p-value, actual p-value calculation is more complex
                })
            else:
                logger.warning(f"Insufficient data for correlation between {metric1} and {metric2}. Scores1: {len(scores1)}, Scores2: {len(scores2)}")


        # For scoreDistribution, keep the existing metrics (BLEU, COMET, TER)
        # Assuming score ranges are fixed or can be dynamically calculated if needed
        score_distribution = []
        if bleu_scores:
            score_distribution.append({"metric": "BLEU", "scores": bleu_scores, "scoreRange": "0-100"})
        if comet_scores:
            score_distribution.append({"metric": "COMET", "scores": comet_scores, "scoreRange": "0-1"})
        if ter_scores:
            score_distribution.append({"metric": "TER", "scores": ter_scores, "scoreRange": "0-100"})


        # Evaluation modes can be simplified as per quality_scores_data function
        # Reference-based evaluation modes often imply human-edited references
        evaluation_modes = [
            {"mode": "Reference-based", "count": len(bleu_scores), "avgScore": statistics.mean(bleu_scores) if bleu_scores else 0, "confidence": 0.95},
            # Removed MetricX related entry from here as well, since it's reference-free
            # If you have other reference-free metrics, they can be added here
        ]


        return {
            "evaluationModes": evaluation_modes,
            "correlationMatrix": correlations,
            "scoreDistribution": score_distribution
        }

    except Exception as e:
        logger.error(f"Error in get_quality_scores_data: {e}")
        import traceback
        traceback.print_exc()
        return {
            "evaluationModes": [],
            "correlationMatrix": [],
            "scoreDistribution": []
        }

async def get_operational_data(date_filter, lang_filter):
    """Get operational data including processing times, system health, and model utilization."""
    try:
        if not prisma.is_connected():
            await prisma.connect()

        # 1. Processing Times Data
        all_outputs = await prisma.modeloutput.find_many(
            where={**date_filter},
            include={
                "translationString": {
                    "include": {
                        "translationRequest": True
                    }
                }
            }
        )
        
        processing_stats = {}
        for output in all_outputs:
            # Apply language filter to translation strings related to model output if present
            if lang_filter and "targetLanguage" in lang_filter:
                t_string = output.translationString
                if not t_string or not t_string.translationRequest:
                    continue
                if t_string.targetLanguage.lower() != lang_filter["targetLanguage"]["contains"].lower():
                    continue

            key = f"{output.modelName or 'unknown_model'}_{output.engineName or 'unknown_engine'}"
            if key not in processing_stats:
                processing_stats[key] = {
                    "model": output.modelName or "unknown_model",
                    "engineType": output.engineName or "unknown_engine",
                    "times": [],
                    "count": 0
                }
            
            processing_stats[key]["count"] += 1
            if output.processingTimeMs is not None:
                processing_stats[key]["times"].append(output.processingTimeMs)
        
        processing_times = []
        for stats in processing_stats.values():
            avg_time = sum(stats["times"]) / len(stats["times"]) if stats["times"] else 0
            processing_times.append({
                "model": stats["model"],
                "engineType": stats["engineType"],
                "wordCountBucket": "medium", # Placeholder, ideally derived from text length
                "avgProcessingTime": avg_time,
                "count": stats["count"]
            })

        # 2. System Health Data (Leveraging HealthService)
        system_health_data = []
        if health_service: # Check if the health_service is set/available
            detailed_status = await health_service.get_detailed_status()
            
            # Overall Backend Status
            system_health_data.append({
                "model": "Overall Backend Status",
                "isActive": detailed_status.get("status") == "healthy",
                "lastUsed": datetime.now().isoformat(), # Can be enhanced by tracking server startup or last API call
                "totalTranslations": sum(p['count'] for p in processing_times), # Sum all processed translations
                "avgProcessingTime": sum(p['avgProcessingTime'] * p['count'] for p in processing_times) / sum(p['count'] for p in processing_times) if sum(p['count'] for p in processing_times) > 0 else 0
            })

            # Database Connection Status
            system_health_data.append({
                "model": "Database Connection",
                "isActive": detailed_status.get("database") == "connected",
                "lastUsed": datetime.now().isoformat(),
                "totalTranslations": 0, 
                "avgProcessingTime": 0 
            })

            # MetricX Service Status
            if detailed_status.get("metricx_available") is not None:
                system_health_data.append({
                    "model": "MetricX Service",
                    "isActive": detailed_status["metricx_available"],
                    "lastUsed": datetime.now().isoformat(), # Placeholder
                    "totalTranslations": 0, # Not easily available from health service
                    "avgProcessingTime": 0 # Not easily available from health service
                })
            
            # Translation Core Service Status
            if detailed_status.get("translation_service_available") is not None:
                system_health_data.append({
                    "model": "Translation Core Service",
                    "isActive": detailed_status["translation_service_available"],
                    "lastUsed": datetime.now().isoformat(), # Placeholder
                    "totalTranslations": 0, # Not easily available from health service
                    "avgProcessingTime": 0 # Not easily available from health service
                })

            # Multi-Engine Service and specific engines
            if detailed_status.get("local_engines_available") is not None:
                system_health_data.append({
                    "model": "Multi-Engine Orchestrator",
                    "isActive": detailed_status["local_engines_available"],
                    "lastUsed": datetime.now().isoformat(), # Placeholder
                    "totalTranslations": 0, # Not easily available from health service
                    "avgProcessingTime": 0 # Not easily available from health service
                })

            if detailed_status.get("available_engines"):
                for engine_name in detailed_status["available_engines"]:
                    # Try to find actual usage stats for each specific engine
                    total_t = 0
                    avg_p_time = 0
                    last_used_time = datetime.now().isoformat() # Default

                    for key, stats in processing_stats.items():
                        if stats["model"] == engine_name: # Assuming engine_name from health matches modelName in ModelOutput
                            total_t = stats["count"]
                            avg_p_time = stats["avgProcessingTime"]

                            latest_output_for_model = await prisma.modeloutput.find_first(
                                where={"modelName": engine_name},
                                order={"createdAt": "desc"}
                            )
                            if latest_output_for_model and latest_output_for_model.createdAt:
                                last_used_time = latest_output_for_model.createdAt.isoformat()
                            break
                    
                    system_health_data.append({
                        "model": engine_name,
                        "isActive": True, 
                        "lastUsed": last_used_time,
                        "totalTranslations": total_t,
                        "avgProcessingTime": avg_p_time
                    })
        else:
            logger.warning("HealthService not injected into analytics router. System Health data will be incomplete.")

        # 3. Model Utilization Data (Placeholder for now)        
        model_utilization_data = []
        for stats in processing_stats.values():
            utilization_rate = (stats["count"] / max(1, sum(p['count'] for p in processing_times))) * 100 # Simple ratio
            model_utilization_data.append({
                "model": stats["model"],
                "utilizationRate": utilization_rate,
                "idleDays": 0, # Placeholder
                "needsUpdate": False # Placeholder
            })
            
        return {
            "processingTimes": processing_times,
            "systemHealth": system_health_data,
            "modelUtilization": model_utilization_data
        }
        
    except Exception as e:
        logger.error(f"Error fetching operational data: {e}")
        import traceback
        traceback.print_exc()
        return {"processingTimes": [], "systemHealth": [], "modelUtilization": []}

async def get_tm_glossary_data(date_filter, lang_filter):
    """Get translation memory and glossary data"""
    try:
        if not prisma.is_connected():
            await prisma.connect()

        tm_strings = await prisma.translationstring.find_many(
            where={
                **date_filter,
                **lang_filter,
                "tmMatchPercentage": {"not": None}
            },
            include={"qualityMetrics": True}
        )
        
        tm_impact = {}
        for string in tm_strings:
            match_bucket = (
                "high" if string.tmMatchPercentage >= 90
                else "medium" if string.tmMatchPercentage >= 70
                else "low"
            )
            if match_bucket not in tm_impact:
                tm_impact[match_bucket] = {
                    "matchPercentage": match_bucket,
                    "avgQualityScore": 0,
                    "timeSaved": 0,
                    "approvalRate": 0,
                    "count": 0,
                    "approved": 0
                }

            tm_impact[match_bucket]["count"] += 1
            if string.isApproved:
                tm_impact[match_bucket]["approved"] += 1

            if string.qualityMetrics:
                for metric in string.qualityMetrics:
                    quality_score = (
                        metric.metricXScore if metric.metricXScore is not None
                        else metric.cometScore
                    )
                    if quality_score is not None:
                        tm_impact[match_bucket]["avgQualityScore"] += quality_score

        for bucket in tm_impact.values():
            if bucket["count"] > 0:
                bucket["avgQualityScore"] /= bucket["count"]
                bucket["approvalRate"] = bucket["approved"] / bucket["count"]
                if bucket["matchPercentage"] == "high":
                    bucket["timeSaved"] = bucket["count"] * 5
                elif bucket["matchPercentage"] == "medium":
                    bucket["timeSaved"] = bucket["count"] * 2
                else:
                    bucket["timeSaved"] = bucket["count"] * 0.5

        glossary_terms = await prisma.glossaryterm.find_many(
            where={**lang_filter, "isActive": True, "usageCount": {"gt": 0}}
        )

        term_counts = Counter(term.term for term in glossary_terms)
        top_terms = term_counts.most_common(20)

        glossary_usage = []
        for term, count in top_terms:
            glossary_usage.append({
                "term": term,
                "usageCount": count,
                "overrideRate": 0.1,  # Placeholder
                "qualityImpact": 0.05  # Placeholder
            })

        term_overrides = []  # Placeholder

        return {
            "tmImpact": list(tm_impact.values()),
            "glossaryUsage": glossary_usage,
            "termOverrides": term_overrides
        }
    except Exception as e:
        logger.error(f"Error fetching TM/glossary data: {e}")
        import traceback
        traceback.print_exc()
        return {"tmImpact": [], "glossaryUsage": [], "termOverrides": []}

async def get_model_performance_data(date_filter, lang_filter, group_by="model"):
    """Get model performance data with flexible grouping and filtering"""
    try:
        if not prisma.is_connected():
            await prisma.connect()

        quality_metrics = await prisma.qualitymetrics.find_many(
            where={
                **date_filter,
                "cometScore": {"not": None},
                "hasReference": True # Only include metrics with human post-edits
            },
            include={
                "translationRequest": {
                    "include": {
                        "translationStrings": True
                    }
                },
                "translationString": {
                    "include": {
                        "translationRequest": True,
                        "modelOutputs": True # Include modelOutputs for source of truth on model
                    }
                }
            }
        )

        if group_by == "model":
            grouped_data = group_by_model(quality_metrics, lang_filter)
        elif group_by == "language_pair":
            grouped_data = group_by_language_pair(quality_metrics, lang_filter)
        else:
            grouped_data = group_by_model(quality_metrics, lang_filter)

        return {
            "leaderboard": grouped_data,
            "performanceOverTime": [], # Keeping this empty as it's not explicitly requested to be filled now
            "modelComparison": [] # Keeping this empty as it's not explicitly requested to be filled now
        }

    except Exception as e:
        logger.error(f"Error fetching model performance data: {e}")
        import traceback
        traceback.print_exc()
        return {"leaderboard": [], "performanceOverTime": [], "modelComparison": []}

def calculate_average(scores: list) -> float:
    """Helper to calculate average, handling empty list"""
    return sum(scores) / len(scores) if scores else 0.0

def extract_model_and_language_info(metric):
    """
    Extracts model name and language pair from a quality metric entry.
    Prioritizes specific model names, then falls back to translation request model,
    then to calculation engine types, and finally to 'Untraceable/Other'.
    """
    model_name_extracted = None
    language_pair = "unknown-unknown"

    # 1. Try to get model from direct ModelOutput (most specific)
    if metric.translationString and metric.translationString.modelOutputs:
        if len(metric.translationString.modelOutputs) > 0 and metric.translationString.modelOutputs[0].modelName:
            model_name_extracted = metric.translationString.modelOutputs[0].modelName
            logger.debug(f"Extracted model from ModelOutput: {model_name_extracted}")

    # 2. Fallback to MTModel from TranslationRequest (if no specific ModelOutput or modelName is None)
    if model_name_extracted is None and metric.translationString and metric.translationString.translationRequest:
        if metric.translationString.translationRequest.mtModel:
            mt_model = metric.translationString.translationRequest.mtModel
            model_name_extracted = mt_model.value if hasattr(mt_model, 'value') else str(mt_model)
            logger.debug(f"Extracted model from TranslationRequest.mtModel: {model_name_extracted}")

    # 3. Fallback to calculationEngine for broad categories if still no specific model
    #    Exclude 'MetricX-Evaluation' as it's not a source MT model.
    if model_name_extracted is None and metric.calculationEngine:
        if "comet-prediction" in metric.calculationEngine.lower():
            model_name_extracted = "COMET-Prediction"
            logger.debug(f"Extracted model from calculationEngine (COMET): {model_name_extracted}")
        elif "post-editing-metrics" in metric.calculationEngine.lower():
            model_name_extracted = "Human-Post-Edit"
            logger.debug(f"Extracted model from calculationEngine (Post-Edit): {model_name_extracted}")
        # Removed MetricX-Evaluation from here as it's not an MT model
        # elif "metricx-evaluation" in metric.calculationEngine.lower():
        #     model_name_extracted = "MetricX-Evaluation"
        #     logger.debug(f"Extracted model from calculationEngine (MetricX): {model_name_extracted}")

    # 4. Final fallback for truly untraceable models
    if model_name_extracted is None:
        model_name_extracted = "Untraceable/Other"
        logger.warning(f"Could not trace model for metric {metric.id}, assigned '{model_name_extracted}'. Calculation Engine: {metric.calculationEngine}, Translation String ID: {metric.translationStringId}")


    # Extract language pair
    if metric.translationString and metric.translationString.translationRequest:
        source_lang = metric.translationString.translationRequest.sourceLanguage
        target_lang = metric.translationString.targetLanguage
        language_pair = f"{source_lang}-{target_lang}"
    elif metric.translationRequestId:       
        pass

    return model_name_extracted, language_pair

def matches_language_filter(language_pair: str, lang_filter: dict) -> bool:
    """Checks if a language pair matches the filter.
    lang_filter expects {'targetLanguage': {'contains': 'EN'}}
    """
    if not lang_filter or "targetLanguage" not in lang_filter:
        return True
    
    filter_target_lang = lang_filter["targetLanguage"]["contains"].lower()
    
    parts = language_pair.split('-')
    if len(parts) == 2:
        return parts[1].lower() == filter_target_lang
    return False

def group_by_model(quality_metrics, lang_filter):
    """Group metrics by model and calculate averages"""
    model_stats = {}
    
    for metric in quality_metrics:
        model_name, language_pair = extract_model_and_language_info(metric)
        
        # Filter out non-MT models or untraceable entries for the leaderboard
        if model_name in ["Untraceable/Other", "Human-Post-Edit", "COMET-Prediction", "MetricX-Evaluation"]:
            continue 

        if lang_filter and not matches_language_filter(language_pair, lang_filter):
            continue
        
        # Determine engineType based on model_name using the helper
        engine_type = get_engine_type_from_model(model_name)

        if model_name not in model_stats:
            model_stats[model_name] = {
                "bleu_scores": [],
                "comet_scores": [],
                "ter_scores": [],
                "metricx_scores": [], # Include if needed, but not used in final display as per request
                "total_translations": 0,
                "language_pairs": set(),
                "engineType": engine_type # Add engineType here
            }

        if metric.bleuScore is not None: model_stats[model_name]["bleu_scores"].append(metric.bleuScore)
        if metric.cometScore is not None: model_stats[model_name]["comet_scores"].append(metric.cometScore)
        if metric.terScore is not None: model_stats[model_name]["ter_scores"].append(metric.terScore)
        if metric.metricXScore is not None: model_stats[model_name]["metricx_scores"].append(metric.metricXScore)
        
        model_stats[model_name]["total_translations"] += 1
        model_stats[model_name]["language_pairs"].add(language_pair)

    leaderboard = []
    for model, stats in model_stats.items():
        if stats["total_translations"] > 0:
            leaderboard.append({
                "name": model,
                "type": "model",
                "model": model, # Ensure 'model' field is present for consistency with frontend interface
                "engineType": stats["engineType"], # Ensure engineType is passed
                "avgBleu": calculate_average(stats["bleu_scores"]) * 100, # Convert to percentage
                "avgComet": calculate_average(stats["comet_scores"]) * 100, # Convert to percentage
                "avgTer": calculate_average(stats["ter_scores"]) * 100, # Convert to percentage
                "avgMetricX": calculate_average(stats["metricx_scores"]), # Keep as is, if not used in chart it's fine
                "totalTranslations": stats["total_translations"],
                "languagePairs": list(stats["language_pairs"]),
                "confidenceInterval": { # Placeholder for confidence interval
                    "bleuLow": 0, "bleuHigh": 100,
                    "cometLow": 0, "cometHigh": 100
                }
            })
    
    return sorted(leaderboard, key=lambda x: x["avgComet"], reverse=True)

def group_by_language_pair(quality_metrics, lang_filter):
    """Group metrics by language pair and calculate averages"""
    pair_stats = {}
    
    for metric in quality_metrics:
        model_name, language_pair = extract_model_and_language_info(metric)
        
        # Filter out non-MT models or untraceable entries
        if model_name in ["Untraceable/Other", "Human-Post-Edit", "COMET-Prediction", "MetricX-Evaluation"]:
            continue 

        if lang_filter and not matches_language_filter(language_pair, lang_filter):
            continue
        
        if language_pair not in pair_stats:
            pair_stats[language_pair] = {
                "bleu_scores": [],
                "comet_scores": [],
                "ter_scores": [],
                "metricx_scores": [],
                "total_translations": 0,
                "models": set() # Use a set to store unique model names for this language pair
            }

        if metric.bleuScore is not None: pair_stats[language_pair]["bleu_scores"].append(metric.bleuScore)
        if metric.cometScore is not None: pair_stats[language_pair]["comet_scores"].append(metric.cometScore)
        if metric.terScore is not None: pair_stats[language_pair]["ter_scores"].append(metric.terScore)
        if metric.metricXScore is not None: pair_stats[language_pair]["metricx_scores"].append(metric.metricXScore)
        
        pair_stats[language_pair]["total_translations"] += 1
        pair_stats[language_pair]["models"].add(model_name) 

    leaderboard = []
    for pair, stats in pair_stats.items():
        if stats["total_translations"] > 0:
            leaderboard.append({
                "name": pair,
                "type": "language_pair",
                "model": "N/A", # Placeholder to satisfy frontend interface if 'model' is always expected
                "engineType": "N/A", # Placeholder to satisfy frontend interface if 'engineType' is always expected
                "avgBleu": calculate_average(stats["bleu_scores"]) * 100,
                "avgComet": calculate_average(stats["comet_scores"]) * 100,
                "avgTer": calculate_average(stats["ter_scores"]) * 100,
                "avgMetricX": calculate_average(stats["metricx_scores"]),
                "totalTranslations": stats["total_translations"],
                "languagePairs": [pair], # This group is by language pair, so it's just this one
                "models": list(stats["models"]), # Include models for this language pair
                "confidenceInterval": { # Placeholder for confidence interval
                    "bleuLow": 0, "bleuHigh": 100,
                    "cometLow": 0, "cometHigh": 100
                }
            })
    
    return sorted(leaderboard, key=lambda x: x["avgComet"], reverse=True)

@router.get("/engine-preferences")
async def get_engine_preference_analytics():
    """Get analytics on engine preferences over time"""
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        all_preferences = await prisma.enginepreference.find_many(where={})

        preferences_grouped = {}
        for pref in all_preferences:
            key = (pref.selectedEngine, pref.sourceLanguage, pref.targetLanguage, pref.preferenceReason)
            if key not in preferences_grouped:
                preferences_grouped[key] = {
                    "selectedEngine": pref.selectedEngine,
                    "sourceLanguage": pref.sourceLanguage,
                    "targetLanguage": pref.targetLanguage,
                    "preferenceReason": pref.preferenceReason,
                    "count": 0,
                    "ratings": [],
                    "overallSatisfactions": []
                }
            preferences_grouped[key]["count"] += 1
            if pref.rating is not None:
                preferences_grouped[key]["ratings"].append(pref.rating)
            if pref.overallSatisfaction is not None:
                preferences_grouped[key]["overallSatisfactions"].append(pref.overallSatisfaction)
        
        engine_preferences = []
        for key, data in preferences_grouped.items():
            avg_rating = sum(data["ratings"]) / len(data["ratings"]) if data["ratings"] else 0
            avg_satisfaction = sum(data["overallSatisfactions"]) / len(data["overallSatisfactions"]) if data["overallSatisfactions"] else 0
            
            engine_preferences.append({
                "engine": data["selectedEngine"],
                "selectionCount": data["count"],
                "avgRating": avg_rating,
                "languagePair": f"{data['sourceLanguage']}-{data['targetLanguage']}",
                "preferenceReason": data["preferenceReason"] or "unknown",
                "overallSatisfaction": avg_satisfaction
            })
        
        total_preferences = len(all_preferences) 
        
        engine_counts = {}
        engine_ratings = {}
        for pref in all_preferences: 
            engine = pref.selectedEngine
            engine_counts[engine] = engine_counts.get(engine, 0) + 1
            if pref.rating is not None:
                engine_ratings.setdefault(engine, []).append(pref.rating)
        avg_ratings = {engine: sum(ratings) / len(ratings) for engine, ratings in engine_ratings.items() if ratings}


        return {
            "totalPreferences": total_preferences,
            "engineCounts": engine_counts,
            "averageRatings": avg_ratings,
            "preferences": engine_preferences[:50]
        }
        
    except Exception as e:
        logger.error(f"Database error: {e}")
        return {
            "totalPreferences": 0,
            "engineCounts": {},
            "averageRatings": {},
            "preferences": []
        }

@router.get("/dashboard/post-edit-metrics")
async def get_post_edit_metrics(
    language_pair: Optional[str] = Query("all"),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None)
):
    """Get post-editing metrics for dashboard"""
    try:
        if not prisma.is_connected():
            await prisma.connect()

        _date_from = datetime.fromisoformat(date_from) if date_from else None
        _date_to = datetime.fromisoformat(date_to) if date_to else None

        date_filter_obj = {}
        if _date_from:
            date_filter_obj["createdAt"] = {"gte": _date_from}
        if _date_to:
            date_filter_obj.setdefault("createdAt", {})["lte"] = _date_to


        metrics = await prisma.qualitymetrics.find_many(
            where={
                **date_filter_obj,
                "hasReference": True,
                "bleuScore": {"not": None},
                "cometScore": {"not": None},
                "terScore": {"not": None}
            },
            include={
                "translationRequest": {
                    "include": {
                        "translationStrings": {
                            "where": {
                                "hasReference": True # Ensure only strings with reference are included
                            }
                        }
                    }
                }
            }
        )

        language_pair_metrics = {}
        correlation_data_raw = [] 
        
        for metric in metrics:
            if metric.translationRequest and metric.translationRequest.translationStrings:
                source_lang = metric.translationRequest.sourceLanguage
                target_lang = "unknown"
                if metric.translationString and metric.translationString.targetLanguage:
                    target_lang = metric.translationString.targetLanguage
                elif metric.translationRequest and metric.translationRequest.targetLanguages:
                    # Fallback if quality metric isn't directly linked to a specific translation string's language
                    target_lang = metric.translationRequest.targetLanguages[0] if metric.translationRequest.targetLanguages else "unknown"


                pair = f"{source_lang}-{target_lang}"
                
                if language_pair != "all" and pair.lower() != language_pair.lower():
                    continue
                
                if pair not in language_pair_metrics:
                    language_pair_metrics[pair] = {
                        "languagePair": pair,
                        "bleuScores": [],
                        "cometScores": [],
                        "terScores": [],
                        "count": 0
                    }
                
                if metric.bleuScore is not None: language_pair_metrics[pair]["bleuScores"].append(metric.bleuScore)
                if metric.cometScore is not None: language_pair_metrics[pair]["cometScores"].append(metric.cometScore)
                if metric.terScore is not None: language_pair_metrics[pair]["terScores"].append(metric.terScore)
                language_pair_metrics[pair]["count"] += 1
                
                # Collect data for correlation calculation
                if metric.bleuScore is not None and metric.cometScore is not None and metric.terScore is not None:
                     correlation_data_raw.append({
                        "bleu": metric.bleuScore,
                        "comet": metric.cometScore,
                        "ter": metric.terScore
                    })

        bar_chart_data = []
        for pair, data in language_pair_metrics.items():
            if data["count"] > 0:
                bar_chart_data.append({
                    "languagePair": pair,
                    "avgBleu": sum(data["bleuScores"]) / len(data["bleuScores"]) * 100 if data["bleuScores"] else 0,
                    "avgComet": sum(data["cometScores"]) / len(data["cometScores"]) * 100 if data["cometScores"] else 0,
                    "avgTer": sum(data["terScores"]) / len(data["terScores"]) if data["terScores"] else 0, # TER is usually interpreted as lower is better, often not percentage
                    "count": data["count"]
                })

        # Calculate actual correlations for the matrix, excluding MetricX
        bleu_vals = [d["bleu"] for d in correlation_data_raw]
        comet_vals = [d["comet"] for d in correlation_data_raw]
        ter_vals = [d["ter"] for d in correlation_data_raw]

        calculated_correlation_matrix = []
        
        # BLEU-COMET
        if len(bleu_vals) > 1 and len(comet_vals) > 1:
            calculated_correlation_matrix.append({
                "metric1": "BLEU", "metric2": "COMET", 
                "correlation": calculate_correlation(bleu_vals, comet_vals), 
                "pValue": 0.05 # Placeholder
            })
        
        # BLEU-TER
        if len(bleu_vals) > 1 and len(ter_vals) > 1:
            calculated_correlation_matrix.append({
                "metric1": "BLEU", "metric2": "TER", 
                "correlation": calculate_correlation(bleu_vals, ter_vals), 
                "pValue": 0.05 # Placeholder
            })

        # COMET-TER
        if len(comet_vals) > 1 and len(ter_vals) > 1:
            calculated_correlation_matrix.append({
                "metric1": "COMET", "metric2": "TER", 
                "correlation": calculate_correlation(comet_vals, ter_vals), 
                "pValue": 0.05 # Placeholder
            })

        logger.info(f"Returning {len(bar_chart_data)} language pairs for dashboard")

        return {
            "languagePairMetrics": bar_chart_data,
            "correlationMatrix": calculated_correlation_matrix,
            "totalPostEdits": len(correlation_data_raw) # Sum of all individual string metrics
        }

    except Exception as e:
        logger.error(f"Error getting post-edit metrics: {e}")
        import traceback
        traceback.print_exc()
        return {
            "languagePairMetrics": [],
            "correlationMatrix": [],
            "totalPostEdits": 0
        }

@router.get("/dashboard/analytics")
async def get_dashboard_analytics(
    language_pair: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    group_by: Optional[str] = Query("model", description="Group by: model or language_pair"),
    engine_filter: Optional[str] = Query(None), # New filter for preferences
):
    """Get comprehensive analytics data for the dashboard"""
    try:
        if not prisma.is_connected():
            await prisma.connect()

        lang_filter_obj = {}
        if language_pair and language_pair.lower() != "all":
            # Assuming language_pair comes as 'EN-FR' and we only need target for filtering
            parts = language_pair.upper().split('-')
            if len(parts) == 2:
                lang_filter_obj["targetLanguage"] = {"contains": parts[1]}

        # Prepare date filter object
        _date_from = datetime.fromisoformat(date_from) if date_from else None
        _date_to = datetime.fromisoformat(date_to) if date_to else None

        date_filter_obj = {}
        if _date_from:
            date_filter_obj["createdAt"] = {"gte": _date_from}
        if _date_to:
            date_filter_obj.setdefault("createdAt", {})["lte"] = _date_to
            
        # Prepare engine filter for human preferences
        engine_pref_filter_obj = {**date_filter_obj}
        if language_pair and language_pair.lower() != "all":
             parts = language_pair.upper().split('-')
             if len(parts) == 2:
                engine_pref_filter_obj["sourceLanguage"] = {"contains": parts[0]}
                engine_pref_filter_obj["targetLanguage"] = {"contains": parts[1]}
        if engine_filter and engine_filter.lower() != "all":
            engine_pref_filter_obj["selectedEngine"] = {"contains": engine_filter}

        model_performance = await get_model_performance_data(
                    date_filter_obj, 
                    lang_filter_obj, 
                    group_by=group_by
                )        
        quality_scores = await get_quality_scores_data(date_filter_obj, lang_filter_obj)
        human_preferences = await get_human_preferences_data(engine_pref_filter_obj, lang_filter_obj) # Use engine_pref_filter_obj
        annotations_data = await get_annotations_data(date_filter_obj, lang_filter_obj)
        operational_data = await get_operational_data(date_filter_obj, lang_filter_obj)
        tm_glossary_data = await get_tm_glossary_data(date_filter_obj, lang_filter_obj)
        multi_engine_data = await get_multi_engine_data(date_filter_obj, lang_filter_obj)

        return {
            "modelPerformance": model_performance,
            "humanPreferences": human_preferences,
            "annotations": annotations_data,
            "multiEngine": multi_engine_data,
            "qualityScores": quality_scores,
            "operational": operational_data,
            "tmGlossary": tm_glossary_data
        }

    except Exception as e:
        logger.error(f"Dashboard analytics error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "modelPerformance": {"leaderboard": [], "performanceOverTime": [], "modelComparison": []},
            "humanPreferences": {"enginePreferences": [], "reviewerBehavior": [], "preferenceReasons": []},
            "annotations": {"errorHeatmap": [], "severityBreakdown": [], "spanAnalysis": [], "stackedPainIndexByErrorType": []}, # Added new field
            "multiEngine": {"selectionTrends": [], "pivotQuality": [], "interRaterAgreement": []},
            "qualityScores": {"evaluationModes": [], "correlationMatrix": [], "scoreDistribution": []},
            "operational": {"processingTimes": [], "systemHealth": [], "modelUtilization": []},
            "tmGlossary": {"tmImpact": [], "glossaryUsage": [], "termOverrides": []}
        }


@router.get("/rlhf/analytics")
async def get_rlhf_analytics():
    """Get RLHF analytics data"""
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        preferences = await prisma.enginepreference.find_many()
        
        total_feedback = len(preferences)
        preference_pairs = sum(1 for p in preferences if p.rating is not None and p.rating >= 4)
        
        feedback_types = {}
        for pref in preferences:
            engine = pref.selectedEngine
            feedback_types[engine] = feedback_types.get(engine, 0) + 1
        
        avg_quality_scores = {}
        engine_ratings = {}
        for pref in preferences:
            engine = pref.selectedEngine
            if engine not in engine_ratings:
                engine_ratings[engine] = []
            if pref.rating is not None:
                engine_ratings[engine].append(pref.rating)
        
        for engine, ratings in engine_ratings.items():
            avg_quality_scores[engine] = sum(ratings) / len(ratings) if ratings else 0
        
        return {
            "total_feedback_entries": total_feedback,
            "total_preference_pairs": preference_pairs,
            "feedback_types": feedback_types,
            "average_quality_scores": avg_quality_scores,
            "training_data_available": total_feedback > 0
        }
        
    except Exception as e:
        logger.error(f"Error fetching RLHF analytics: {e}")
        return {
            "total_feedback_entries": 0,
            "total_preference_pairs": 0,
            "feedback_types": {},
            "average_quality_scores": {},
            "training_data_available": False
        }

@router.get("/human-feedback/analytics")
async def get_human_feedback_analytics():
    """Get human feedback analytics data"""
    try:
        if not prisma.is_connected():
            await prisma.connect()
        
        annotations = await prisma.annotation.find_many()
        
        total_entries = len(annotations)
        
        feedback_distribution = {}
        for annotation in annotations:
            category = annotation.category.value if hasattr(annotation.category, 'value') else str(annotation.category)
            feedback_distribution[category] = feedback_distribution.get(category, 0) + 1
        
        severity_distribution = {}
        for annotation in annotations:
            severity = annotation.severity.value if hasattr(annotation.severity, 'value') else str(annotation.severity)
            severity_distribution[severity] = severity_distribution.get(severity, 0) + 1
        
        total_requests_count = await prisma.translationrequest.count()
        average_feedback_per_request_val = total_entries / max(1, total_requests_count)

        return {
            "total_entries": total_entries,
            "feedback_distribution": feedback_distribution,
            "quality_metrics": {
                "severity_distribution": severity_distribution,
                "categories_covered": len(feedback_distribution),
                "average_feedback_per_request": average_feedback_per_request_val
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching human feedback analytics: {e}")
        return {
            "total_entries": 0,
            "feedback_distribution": {},
            "quality_metrics": {}
        }

@router.post("/rlhf/quality-rating")
async def submit_quality_rating(rating: QualityRating):
    """Submit quality rating for RLHF"""
    try:
        logger.info(f"Received RLHF quality rating: {rating.dict()}")
        return {"success": True, "message": "Quality rating submitted successfully"}
    except Exception as e:
        logger.error(f"Failed to submit RLHF rating: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to submit rating: {str(e)}")

@router.get("/quality-trends") 
async def get_quality_trends():
    """Get quality trends analytics"""
    try:
        if not prisma.is_connected():
            await prisma.connect()

        recent_requests = await prisma.translationrequest.find_many(
            include={
                "translationStrings": {
                    "include": {"qualityRatings": True}
                }
            },
            order={"createdAt": "desc"},
            take=100
        )

        trends = {
            "total_requests": len(recent_requests),
            "quality_distribution": {},
            "engine_performance": {},
            "language_pair_quality": {}
        }

        all_ratings = []
        for request in recent_requests:
            for string in request.translationStrings:
                if string.humanRating is not None:
                    all_ratings.append(string.humanRating)

        if all_ratings:
            trends["quality_distribution"] = {
                "average": sum(all_ratings) / len(all_ratings),
                "count": len(all_ratings),
                "distribution": {
                    "5_stars": len([r for r in all_ratings if r >= 4.5]),
                    "4_stars": len([r for r in all_ratings if 3.5 <= r < 4.5]),
                    "3_stars": len([r for r in all_ratings if 2.5 <= r < 3.5]),
                    "2_stars": len([r for r in all_ratings if 1.5 <= r < 2.5]),
                    "1_star": len([r for r in all_ratings if r < 1.5])
                }
            }

        return trends

    except Exception as e:
        logger.error(f"Quality trends analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/dashboard/translator-impact")
async def get_translator_impact_data(language_pair: Optional[str] = Query("all")):
    """Get translator impact analysis data"""
    try:
        if not prisma.is_connected():
            await prisma.connect()

        lang_filter_obj = {}
        if language_pair and language_pair.lower() != "all":
            # Assuming language_pair comes as 'EN-FR' and we only need target for filtering
            parts = language_pair.upper().split('-')
            if len(parts) == 2:
                lang_filter_obj["targetLanguage"] = {"contains": parts[1]}


        translations = await prisma.translationstring.find_many(
            where={
                **lang_filter_obj,
                "originalTranslation": {"not": None}, 
                "translatedText": {"not": ""},
                "status": {"in": ["REVIEWED", "APPROVED"]},
            },
            include={
                "translationRequest": True,
                "qualityMetrics": True
            }
        )

        logger.info(f"Found {len(translations)} translation strings for translator impact analysis.")

        if not translations:
            return {"comparisons": [], "summary": []}

        comparisons = []
        for translation in translations:
            if not translation.originalTranslation or not translation.originalTranslation.strip():
                logger.warning(f"Skipping string {translation.id} in translator impact: originalTranslation is empty or null.")
                continue
            if not translation.translatedText or not translation.translatedText.strip():
                logger.warning(f"Skipping string {translation.id} in translator impact: translatedText is empty or null.")
                continue

            if translation.originalTranslation.strip() != translation.translatedText.strip():
                
                edit_distance = calculate_edit_distance(
                    translation.originalTranslation, 
                    translation.translatedText
                )
                
                source_text_for_improvement = translation.sourceText if translation.sourceText else ""

                improvement_score = calculate_improvement_score(
                    translation.originalTranslation,
                    translation.translatedText,
                    source_text_for_improvement
                )
                
                edit_type = classify_edit_type(edit_distance, len(translation.originalTranslation.strip()))
                
                comparisons.append({
                    "id": translation.id,
                    "sourceText": translation.sourceText,
                    "originalMT": translation.originalTranslation,
                    "humanEdited": translation.translatedText,
                    "languagePair": f"{translation.translationRequest.sourceLanguage}-{translation.targetLanguage}",
                    "jobId": translation.translationRequest.id,
                    "jobName": translation.translationRequest.fileName,
                    "editDistance": edit_distance,
                    "improvementScore": improvement_score,
                    "editType": edit_type,
                    "timestamp": translation.updatedAt.isoformat() if translation.updatedAt else None,
                })

        logger.info(f"Created {len(comparisons)} comparisons for translator impact.")

        summary = calculate_translator_summary(comparisons)

        return {
            "comparisons": comparisons,
            "summary": summary
        }

    except Exception as e:
        logger.error(f"Error fetching translator impact data: {e}")
        import traceback
        traceback.print_exc()
        return {"comparisons": [], "summary": []}