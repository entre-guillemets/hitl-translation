-- CreateEnum
CREATE TYPE "RequestType" AS ENUM ('SINGLE_ENGINE', 'MULTI_ENGINE', 'WMT_BENCHMARK', 'PIVOT_TRANSLATION');

-- CreateEnum
CREATE TYPE "SourceLanguage" AS ENUM ('EN', 'JP', 'FR');

-- CreateEnum
CREATE TYPE "MTModel" AS ENUM ('MARIAN_MT_EN_FR', 'MARIAN_MT_FR_EN', 'MARIAN_MT_EN_JP', 'ELAN_MT_JP_EN', 'T5_MULTILINGUAL', 'CUSTOM_MODEL', 'MULTI_ENGINE', 'PIVOT_JP_EN_FR');

-- CreateEnum
CREATE TYPE "RequestStatus" AS ENUM ('PENDING', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED', 'MULTI_ENGINE_REVIEW');

-- CreateEnum
CREATE TYPE "ReferenceType" AS ENUM ('WMT', 'HUMAN_APPROVED', 'PROFESSIONAL', 'AUTO_GENERATED', 'HUMAN_REFERENCE', 'MACHINE_REFERENCE', 'FUZZY_MATCH', 'TRANSLATION_MEMORY');

-- CreateEnum
CREATE TYPE "TranslationType" AS ENUM ('STANDARD', 'PIVOT', 'WMT_BENCHMARK', 'MULTI_ENGINE');

-- CreateEnum
CREATE TYPE "StringStatus" AS ENUM ('DRAFT', 'REVIEWED', 'FINALIZED', 'MULTI_ENGINE_REVIEW', 'APPROVED');

-- CreateEnum
CREATE TYPE "EvaluationMode" AS ENUM ('REFERENCE_BASED', 'REFERENCE_FREE', 'HYBRID');

-- CreateEnum
CREATE TYPE "ModelVariant" AS ENUM ('METRICX_24_HYBRID', 'METRICX_24_XL', 'METRICX_24_XXL', 'METRICX_24_REF', 'METRICX_24_SRC', 'CUSTOM');

-- CreateEnum
CREATE TYPE "QualityLabel" AS ENUM ('EXCELLENT', 'GOOD', 'FAIR', 'POOR', 'ERROR', 'CRITICAL');

-- CreateEnum
CREATE TYPE "AnnotationCategory" AS ENUM ('GRAMMAR', 'WORD_CHOICE', 'CONTEXT', 'FLUENCY', 'TERMINOLOGY', 'STYLE', 'OTHER');

-- CreateEnum
CREATE TYPE "AnnotationSeverity" AS ENUM ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL');

-- CreateEnum
CREATE TYPE "MemoryQuality" AS ENUM ('HIGH', 'MEDIUM', 'LOW');

-- CreateEnum
CREATE TYPE "DoNotTranslateCategory" AS ENUM ('PROPER_NOUN', 'BRAND', 'TECHNICAL', 'ACRONYM', 'OTHER');

-- CreateEnum
CREATE TYPE "OffensiveSeverity" AS ENUM ('LOW', 'MEDIUM', 'HIGH');

-- CreateEnum
CREATE TYPE "OffensiveCategory" AS ENUM ('PROFANITY', 'HATE_SPEECH', 'DISCRIMINATORY', 'INAPPROPRIATE', 'OTHER');

-- CreateEnum
CREATE TYPE "FeedbackType" AS ENUM ('TRANSLATION_EDIT', 'QUALITY_RATING', 'PREFERENCE_COMPARISON', 'ANNOTATION');

-- CreateTable
CREATE TABLE "translation_requests" (
    "id" TEXT NOT NULL,
    "sourceLanguage" "SourceLanguage" NOT NULL,
    "targetLanguages" TEXT[],
    "languagePair" TEXT NOT NULL,
    "wordCount" INTEGER NOT NULL,
    "requestDate" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "requestTime" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "mtModel" "MTModel" NOT NULL DEFAULT 'T5_MULTILINGUAL',
    "modelName" TEXT,
    "fileName" TEXT NOT NULL,
    "status" "RequestStatus" NOT NULL DEFAULT 'PENDING',
    "requestType" "RequestType" NOT NULL DEFAULT 'SINGLE_ENGINE',
    "selectedEngines" TEXT[],
    "totalProcessingTimeMs" INTEGER,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "translation_requests_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "translation_strings" (
    "id" TEXT NOT NULL,
    "sourceText" TEXT NOT NULL,
    "translatedText" TEXT NOT NULL,
    "referenceText" TEXT,
    "referenceType" "ReferenceType",
    "targetLanguage" TEXT NOT NULL,
    "status" "StringStatus" NOT NULL DEFAULT 'DRAFT',
    "isApproved" BOOLEAN NOT NULL DEFAULT false,
    "processingTimeMs" INTEGER,
    "lastModified" TIMESTAMP(3),
    "engineResults" JSONB,
    "selectedEngine" TEXT,
    "enginePreferences" JSONB,
    "fuzzyMatches" JSONB,
    "suggestedTranslation" TEXT,
    "tmMatchPercentage" INTEGER,
    "translationType" "TranslationType" NOT NULL DEFAULT 'STANDARD',
    "intermediateTranslation" TEXT,
    "translationRequestId" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "translation_strings_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "quality_metrics" (
    "id" TEXT NOT NULL,
    "metricXScore" DOUBLE PRECISION,
    "metricXConfidence" DOUBLE PRECISION,
    "metricXMode" "EvaluationMode",
    "metricXVariant" "ModelVariant",
    "bleuScore" DOUBLE PRECISION,
    "cometScore" DOUBLE PRECISION,
    "terScore" DOUBLE PRECISION,
    "qualityLabel" "QualityLabel",
    "hasReference" BOOLEAN NOT NULL DEFAULT false,
    "referenceType" "ReferenceType",
    "calculationEngine" TEXT,
    "translationRequestId" TEXT,
    "translationStringId" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "quality_metrics_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "annotations" (
    "id" TEXT NOT NULL,
    "category" "AnnotationCategory" NOT NULL,
    "severity" "AnnotationSeverity" NOT NULL,
    "comment" TEXT NOT NULL,
    "reviewer" TEXT,
    "textRange" JSONB,
    "isResolved" BOOLEAN NOT NULL DEFAULT false,
    "resolution" TEXT,
    "translationStringId" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "annotations_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "translation_memory" (
    "id" TEXT NOT NULL,
    "sourceText" TEXT NOT NULL,
    "targetText" TEXT NOT NULL,
    "sourceLanguage" TEXT NOT NULL,
    "targetLanguage" TEXT NOT NULL,
    "quality" "MemoryQuality" NOT NULL,
    "domain" TEXT NOT NULL,
    "lastUsed" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "createdFrom" TEXT,
    "originalRequestId" TEXT,
    "approvedBy" TEXT,
    "usageCount" INTEGER NOT NULL DEFAULT 0,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "translation_memory_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "glossary_terms" (
    "id" TEXT NOT NULL,
    "term" TEXT NOT NULL,
    "translation" TEXT NOT NULL,
    "sourceLanguage" TEXT NOT NULL,
    "targetLanguage" TEXT NOT NULL,
    "domain" TEXT NOT NULL,
    "definition" TEXT,
    "notes" TEXT,
    "isActive" BOOLEAN NOT NULL DEFAULT true,
    "usageCount" INTEGER NOT NULL DEFAULT 0,
    "lastUsed" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "glossary_terms_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "do_not_translate_items" (
    "id" TEXT NOT NULL,
    "text" TEXT NOT NULL,
    "category" "DoNotTranslateCategory" NOT NULL,
    "languages" TEXT[],
    "notes" TEXT,
    "alternatives" TEXT,
    "isActive" BOOLEAN NOT NULL DEFAULT true,
    "usageCount" INTEGER NOT NULL DEFAULT 0,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "do_not_translate_items_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "offensive_words" (
    "id" TEXT NOT NULL,
    "word" TEXT NOT NULL,
    "language" TEXT NOT NULL,
    "severity" "OffensiveSeverity" NOT NULL,
    "category" "OffensiveCategory" NOT NULL,
    "alternatives" TEXT[],
    "isActive" BOOLEAN NOT NULL DEFAULT true,
    "detectionCount" INTEGER NOT NULL DEFAULT 0,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "offensive_words_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "engine_preferences" (
    "id" TEXT NOT NULL,
    "selectedEngine" TEXT NOT NULL,
    "rating" INTEGER NOT NULL,
    "comments" TEXT,
    "sourceLanguage" TEXT NOT NULL,
    "targetLanguage" TEXT NOT NULL,
    "textLength" INTEGER NOT NULL,
    "translationStringId" TEXT NOT NULL,
    "requestId" TEXT NOT NULL,
    "allEngineResults" JSONB NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "engine_preferences_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "human_feedback" (
    "id" TEXT NOT NULL,
    "feedbackType" "FeedbackType" NOT NULL,
    "originalTranslation" TEXT,
    "humanEdit" TEXT,
    "revisionInstructions" TEXT,
    "qualityScore" DOUBLE PRECISION,
    "translationA" TEXT,
    "translationB" TEXT,
    "preferred" TEXT,
    "sourceText" TEXT NOT NULL,
    "sourceLanguage" TEXT NOT NULL,
    "targetLanguage" TEXT NOT NULL,
    "translationStringId" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "human_feedback_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "local_models" (
    "id" TEXT NOT NULL,
    "modelName" TEXT NOT NULL,
    "modelType" "MTModel" NOT NULL,
    "sourceLanguage" TEXT NOT NULL,
    "targetLanguage" TEXT NOT NULL,
    "isDownloaded" BOOLEAN NOT NULL DEFAULT false,
    "modelPath" TEXT,
    "modelSize" INTEGER,
    "avgProcessingTime" DOUBLE PRECISION,
    "totalTranslations" INTEGER NOT NULL DEFAULT 0,
    "lastUsed" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "local_models_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "system_config" (
    "id" TEXT NOT NULL,
    "key" TEXT NOT NULL,
    "value" TEXT NOT NULL,
    "description" TEXT,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "system_config_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "quality_metrics_translationRequestId_key" ON "quality_metrics"("translationRequestId");

-- CreateIndex
CREATE INDEX "translation_memory_sourceLanguage_targetLanguage_idx" ON "translation_memory"("sourceLanguage", "targetLanguage");

-- CreateIndex
CREATE INDEX "translation_memory_sourceText_idx" ON "translation_memory"("sourceText");

-- CreateIndex
CREATE INDEX "glossary_terms_term_idx" ON "glossary_terms"("term");

-- CreateIndex
CREATE UNIQUE INDEX "glossary_terms_term_sourceLanguage_targetLanguage_key" ON "glossary_terms"("term", "sourceLanguage", "targetLanguage");

-- CreateIndex
CREATE INDEX "do_not_translate_items_text_idx" ON "do_not_translate_items"("text");

-- CreateIndex
CREATE INDEX "offensive_words_word_idx" ON "offensive_words"("word");

-- CreateIndex
CREATE UNIQUE INDEX "offensive_words_word_language_key" ON "offensive_words"("word", "language");

-- CreateIndex
CREATE INDEX "engine_preferences_selectedEngine_idx" ON "engine_preferences"("selectedEngine");

-- CreateIndex
CREATE INDEX "engine_preferences_sourceLanguage_targetLanguage_idx" ON "engine_preferences"("sourceLanguage", "targetLanguage");

-- CreateIndex
CREATE INDEX "human_feedback_feedbackType_idx" ON "human_feedback"("feedbackType");

-- CreateIndex
CREATE UNIQUE INDEX "local_models_modelName_key" ON "local_models"("modelName");

-- CreateIndex
CREATE UNIQUE INDEX "system_config_key_key" ON "system_config"("key");

-- AddForeignKey
ALTER TABLE "translation_strings" ADD CONSTRAINT "translation_strings_translationRequestId_fkey" FOREIGN KEY ("translationRequestId") REFERENCES "translation_requests"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "quality_metrics" ADD CONSTRAINT "quality_metrics_translationRequestId_fkey" FOREIGN KEY ("translationRequestId") REFERENCES "translation_requests"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "quality_metrics" ADD CONSTRAINT "quality_metrics_translationStringId_fkey" FOREIGN KEY ("translationStringId") REFERENCES "translation_strings"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "annotations" ADD CONSTRAINT "annotations_translationStringId_fkey" FOREIGN KEY ("translationStringId") REFERENCES "translation_strings"("id") ON DELETE CASCADE ON UPDATE CASCADE;
