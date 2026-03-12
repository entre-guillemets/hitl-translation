-- Fix mtModel column default to use MT5_BASE (added in previous migration).
-- This is a separate migration because PostgreSQL requires new enum values to be
-- committed before they can be referenced (e.g. as column defaults) in the same transaction.
ALTER TABLE "translation_requests" ALTER COLUMN "mtModel" SET DEFAULT 'MT5_BASE';

-- Performance indexes added to frequently queried columns
CREATE INDEX IF NOT EXISTS "translation_requests_sourceLanguage_idx" ON "translation_requests"("sourceLanguage");
CREATE INDEX IF NOT EXISTS "translation_requests_createdAt_idx" ON "translation_requests"("createdAt");
CREATE INDEX IF NOT EXISTS "translation_strings_targetLanguage_idx" ON "translation_strings"("targetLanguage");
CREATE INDEX IF NOT EXISTS "translation_strings_translationRequestId_idx" ON "translation_strings"("translationRequestId");
CREATE INDEX IF NOT EXISTS "translation_strings_createdAt_idx" ON "translation_strings"("createdAt");
CREATE INDEX IF NOT EXISTS "annotations_translationStringId_idx" ON "annotations"("translationStringId");
