-- CreateEnum
CREATE TYPE "PersonaTranscreationStatus" AS ENUM ('PENDING', 'IN_PROGRESS', 'COMPLETED', 'NEEDS_REVIEW', 'FAILED');

-- CreateEnum
CREATE TYPE "HumanAnnotator" AS ENUM ('REVIEWER_1', 'REVIEWER_2', 'REVIEWER_3');

-- CreateEnum
CREATE TYPE "BrandTone" AS ENUM ('AUTHORITATIVE', 'PLAYFUL', 'LUXURY', 'APPROACHABLE', 'TECHNICAL', 'BOLD');

-- CreateEnum
CREATE TYPE "AdRegister" AS ENUM ('FORMAL', 'INFORMAL', 'NEUTRAL');

-- AlterEnum
ALTER TYPE "AnnotationCategory" ADD VALUE 'BRAND_VOICE_DEVIATION';
ALTER TYPE "AnnotationCategory" ADD VALUE 'CULTURAL_MISSTEP';
ALTER TYPE "AnnotationCategory" ADD VALUE 'POLICY_FLAG';
ALTER TYPE "AnnotationCategory" ADD VALUE 'MISSED_TRANSCREATION';
ALTER TYPE "AnnotationCategory" ADD VALUE 'REGISTER_MISMATCH';

-- AlterEnum
ALTER TYPE "MTModel" ADD VALUE 'GEMINI_TRANSCREATION';

-- AlterEnum
ALTER TYPE "RequestType" ADD VALUE 'PERSONA_TRANSCREATION';

-- AlterEnum
ALTER TYPE "SourceLanguage" ADD VALUE 'SW';

-- AlterTable
ALTER TABLE "annotations" ADD COLUMN     "annotatorId" "HumanAnnotator" NOT NULL DEFAULT 'REVIEWER_1';

-- AlterTable
ALTER TABLE "llm_judgments" ADD COLUMN     "agentIterations" JSONB,
ADD COLUMN     "brandVoiceScore" DOUBLE PRECISION,
ADD COLUMN     "culturalFitnessScore" DOUBLE PRECISION,
ADD COLUMN     "refinementAttempts" INTEGER,
ADD COLUMN     "wasRefined" BOOLEAN NOT NULL DEFAULT false;

-- AlterTable
ALTER TABLE "translation_memory" ADD COLUMN     "personaId" TEXT;

-- AlterTable
ALTER TABLE "translation_requests" ADD COLUMN     "advertiserProfileId" TEXT;

-- AlterTable
ALTER TABLE "translation_strings" ADD COLUMN     "annotatorId" "HumanAnnotator" NOT NULL DEFAULT 'REVIEWER_1';

-- CreateTable
CREATE TABLE "advertiser_profiles" (
    "id" TEXT NOT NULL,
    "brandName" TEXT NOT NULL,
    "brandTone" "BrandTone" NOT NULL,
    "register" "AdRegister" NOT NULL,
    "targetMarkets" TEXT[],
    "keyTerms" TEXT[],
    "tabooTerms" TEXT[],
    "policyNotes" TEXT,
    "isActive" BOOLEAN NOT NULL DEFAULT true,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "advertiser_profiles_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "personas" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "psychographicDescription" TEXT NOT NULL,
    "messagingPriorities" TEXT[],
    "toneOverride" "BrandTone",
    "registerOverride" "AdRegister",
    "advertiserProfileId" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "personas_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "persona_transcreations" (
    "id" TEXT NOT NULL,
    "translationStringId" TEXT NOT NULL,
    "personaId" TEXT NOT NULL,
    "targetLanguage" TEXT NOT NULL,
    "outputText" TEXT,
    "status" "PersonaTranscreationStatus" NOT NULL DEFAULT 'PENDING',
    "brandVoiceScore" DOUBLE PRECISION,
    "culturalFitnessScore" DOUBLE PRECISION,
    "tabooViolation" BOOLEAN,
    "keyTermMissing" BOOLEAN,
    "differentiationScore" DOUBLE PRECISION,
    "refinementAttempts" INTEGER NOT NULL DEFAULT 0,
    "agentIterations" JSONB,
    "rationale" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "persona_transcreations_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "advertiser_profiles_brandName_idx" ON "advertiser_profiles"("brandName");

-- CreateIndex
CREATE INDEX "personas_advertiserProfileId_idx" ON "personas"("advertiserProfileId");

-- CreateIndex
CREATE INDEX "persona_transcreations_translationStringId_idx" ON "persona_transcreations"("translationStringId");

-- CreateIndex
CREATE INDEX "persona_transcreations_personaId_idx" ON "persona_transcreations"("personaId");

-- CreateIndex
CREATE INDEX "quality_metrics_translationRequestId_idx" ON "quality_metrics"("translationRequestId");

-- CreateIndex
CREATE INDEX "quality_metrics_translationStringId_idx" ON "quality_metrics"("translationStringId");

-- CreateIndex
CREATE UNIQUE INDEX "translation_requests_segmentationSessionId_key" ON "translation_requests"("segmentationSessionId");

-- CreateIndex
CREATE INDEX "translation_requests_status_idx" ON "translation_requests"("status");

-- CreateIndex
CREATE INDEX "translation_strings_status_idx" ON "translation_strings"("status");

-- AddForeignKey
ALTER TABLE "translation_requests" ADD CONSTRAINT "translation_requests_segmentationSessionId_fkey" FOREIGN KEY ("segmentationSessionId") REFERENCES "segmentation_sessions"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "translation_requests" ADD CONSTRAINT "translation_requests_advertiserProfileId_fkey" FOREIGN KEY ("advertiserProfileId") REFERENCES "advertiser_profiles"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "personas" ADD CONSTRAINT "personas_advertiserProfileId_fkey" FOREIGN KEY ("advertiserProfileId") REFERENCES "advertiser_profiles"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "persona_transcreations" ADD CONSTRAINT "persona_transcreations_translationStringId_fkey" FOREIGN KEY ("translationStringId") REFERENCES "translation_strings"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "persona_transcreations" ADD CONSTRAINT "persona_transcreations_personaId_fkey" FOREIGN KEY ("personaId") REFERENCES "personas"("id") ON DELETE CASCADE ON UPDATE CASCADE;
