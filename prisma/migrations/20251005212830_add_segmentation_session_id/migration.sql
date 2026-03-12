/*
  Warnings:

  - You are about to drop the column `enginePreferences` on the `translation_strings` table. All the data in the column will be lost.

*/
-- CreateEnum
CREATE TYPE "MediaType" AS ENUM ('IMAGE', 'AUDIO', 'PDF', 'TEXT');

-- CreateEnum
CREATE TYPE "SegmentationStatus" AS ENUM ('PROCESSING', 'READY_FOR_EDIT', 'USER_EDITING', 'COMPLETED', 'EXPIRED');

-- AlterEnum
-- This migration adds more than one value to an enum.
-- With PostgreSQL versions 11 and earlier, this is not possible
-- in a single migration. This can be worked around by creating
-- multiple migrations, each migration adding only one value to
-- the enum.


ALTER TYPE "AnnotationCategory" ADD VALUE 'ACCURACY';
ALTER TYPE "AnnotationCategory" ADD VALUE 'LOCALE_CONVENTION';

-- AlterEnum
-- This migration adds more than one value to an enum.
-- With PostgreSQL versions 11 and earlier, this is not possible
-- in a single migration. This can be worked around by creating
-- multiple migrations, each migration adding only one value to
-- the enum.


ALTER TYPE "ErrorType" ADD VALUE 'PUNCTUATION';
ALTER TYPE "ErrorType" ADD VALUE 'SPELLING';

-- AlterEnum
-- This migration adds more than one value to an enum.
-- With PostgreSQL versions 11 and earlier, this is not possible
-- in a single migration. This can be worked around by creating
-- multiple migrations, each migration adding only one value to
-- the enum.

ALTER TYPE "MTModel" ADD VALUE 'MT5_BASE';
ALTER TYPE "MTModel" ADD VALUE 'PLAMO_2_TRANSLATE';
ALTER TYPE "MTModel" ADD VALUE 'OPUS_MT_JA_EN';
ALTER TYPE "MTModel" ADD VALUE 'OPUS_MT_EN_JAP';
ALTER TYPE "MTModel" ADD VALUE 'OPUS_MT_TC_BIG_EN_FR';
ALTER TYPE "MTModel" ADD VALUE 'NLLB_MULTILINGUAL';
ALTER TYPE "MTModel" ADD VALUE 'PIVOT_ELAN_HELSINKI';
ALTER TYPE "MTModel" ADD VALUE 'MT5_MULTILINGUAL';

-- AlterEnum
-- This migration adds more than one value to an enum.
-- With PostgreSQL versions 11 and earlier, this is not possible
-- in a single migration. This can be worked around by creating
-- multiple migrations, each migration adding only one value to
-- the enum.


ALTER TYPE "ReferenceType" ADD VALUE 'POST_EDITED';
ALTER TYPE "ReferenceType" ADD VALUE 'BACK_TRANSLATION';
ALTER TYPE "ReferenceType" ADD VALUE 'SYNTHETIC';

-- DropIndex
DROP INDEX "quality_metrics_translationRequestId_key";

-- AlterTable
ALTER TABLE "engine_preferences" ADD COLUMN     "generationParams" JSONB,
ADD COLUMN     "modelCombination" TEXT,
ADD COLUMN     "outputVariant" TEXT,
ADD COLUMN     "selectionMethod" TEXT,
ALTER COLUMN "rating" DROP NOT NULL,
ALTER COLUMN "textLength" DROP NOT NULL,
ALTER COLUMN "requestId" DROP NOT NULL,
ALTER COLUMN "allEngineResults" DROP NOT NULL;

-- AlterTable
ALTER TABLE "local_models" ADD COLUMN     "engineType" TEXT;

-- AlterTable
ALTER TABLE "quality_metrics" ADD COLUMN     "chrfScore" DOUBLE PRECISION;

-- AlterTable
ALTER TABLE "translation_requests" ADD COLUMN     "originalSegments" JSONB,
ADD COLUMN     "segmentationSessionId" TEXT,
ALTER COLUMN "mtModel" SET DEFAULT 'T5_MULTILINGUAL';

-- AlterTable
ALTER TABLE "translation_strings" DROP COLUMN "enginePreferences",
ADD COLUMN     "hasReference" BOOLEAN DEFAULT false,
ADD COLUMN     "originalTranslation" TEXT,
ADD COLUMN     "selectedAt" TIMESTAMP(3),
ADD COLUMN     "selectedModelCombination" TEXT,
ADD COLUMN     "selectionMethod" TEXT;

-- CreateTable
CREATE TABLE "segmentation_sessions" (
    "id" TEXT NOT NULL,
    "segmentationId" TEXT NOT NULL,
    "originalFileName" TEXT NOT NULL,
    "mediaType" "MediaType" NOT NULL,
    "segments" JSONB NOT NULL,
    "mediaData" TEXT,
    "detectedLanguage" TEXT NOT NULL,
    "wordCount" INTEGER NOT NULL,
    "sourceLanguage" TEXT,
    "targetLanguages" TEXT[],
    "useMultiEngine" BOOLEAN NOT NULL DEFAULT false,
    "selectedEngines" TEXT[],
    "status" "SegmentationStatus" NOT NULL DEFAULT 'PROCESSING',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "expiresAt" TIMESTAMP(3) NOT NULL,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "segmentation_sessions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "model_outputs" (
    "id" TEXT NOT NULL,
    "translationStringId" TEXT NOT NULL,
    "modelName" TEXT NOT NULL,
    "engineName" TEXT NOT NULL,
    "outputText" TEXT NOT NULL,
    "confidence" DOUBLE PRECISION,
    "processingTimeMs" INTEGER,
    "generationParams" JSONB,
    "isPivot" BOOLEAN NOT NULL DEFAULT false,
    "pivotIntermediate" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "model_outputs_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "segmentation_sessions_segmentationId_key" ON "segmentation_sessions"("segmentationId");

-- AddForeignKey
ALTER TABLE "engine_preferences" ADD CONSTRAINT "engine_preferences_translationStringId_fkey" FOREIGN KEY ("translationStringId") REFERENCES "translation_strings"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "model_outputs" ADD CONSTRAINT "model_outputs_translationStringId_fkey" FOREIGN KEY ("translationStringId") REFERENCES "translation_strings"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
