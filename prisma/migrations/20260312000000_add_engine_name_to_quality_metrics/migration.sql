-- Add engineName column to quality_metrics so that per-engine metric rows
-- can be distinguished from one another and from aggregated request-level rows.
ALTER TABLE "quality_metrics" ADD COLUMN "engineName" TEXT;

CREATE INDEX IF NOT EXISTS "quality_metrics_engineName_idx" ON "quality_metrics"("engineName");
