/*
  Warnings:

  - Made the column `fuzzyMatches` on table `translation_strings` required. This step will fail if there are existing NULL values in that column.

*/
-- CreateEnum
CREATE TYPE "ApprovalType" AS ENUM ('IMMEDIATE', 'MINOR_EDIT', 'MAJOR_EDIT', 'COMPLETE_REWRITE');

-- CreateEnum
CREATE TYPE "ReviewerExpertise" AS ENUM ('NATIVE', 'PROFESSIONAL', 'BILINGUAL', 'LEARNER');

-- CreateEnum
CREATE TYPE "ErrorType" AS ENUM ('OMISSION', 'ADDITION', 'MISTRANSLATION', 'WORD_ORDER', 'REGISTER', 'AMBIGUITY', 'CULTURAL_CONTEXT');

-- CreateEnum
CREATE TYPE "PreferenceReason" AS ENUM ('ACCURACY', 'FLUENCY', 'STYLE', 'TERMINOLOGY', 'CULTURAL_FIT', 'NATURALNESS');

-- AlterTable
ALTER TABLE "annotations" ADD COLUMN     "confidenceInFix" INTEGER,
ADD COLUMN     "errorType" "ErrorType",
ADD COLUMN     "sourceSpan" JSONB,
ADD COLUMN     "suggestedFix" TEXT,
ADD COLUMN     "targetSpan" JSONB;

-- AlterTable
ALTER TABLE "engine_preferences" ADD COLUMN     "overallSatisfaction" INTEGER,
ADD COLUMN     "preferenceReason" "PreferenceReason",
ADD COLUMN     "preferenceStrength" INTEGER,
ADD COLUMN     "worstModel" TEXT,
ADD COLUMN     "worstModelReason" TEXT;

-- AlterTable
ALTER TABLE "translation_strings" ADD COLUMN     "approvalType" "ApprovalType",
ADD COLUMN     "cognitiveLoad" INTEGER,
ADD COLUMN     "domainFamiliarity" INTEGER,
ADD COLUMN     "editDistance" INTEGER,
ADD COLUMN     "reviewerExpertise" "ReviewerExpertise",
ADD COLUMN     "timeToReview" INTEGER,
ALTER COLUMN "fuzzyMatches" SET NOT NULL,
ALTER COLUMN "fuzzyMatches" SET DEFAULT '[]';
