-- DropForeignKey
ALTER TABLE "quality_metrics" DROP CONSTRAINT "quality_metrics_translationRequestId_fkey";

-- DropForeignKey
ALTER TABLE "quality_metrics" DROP CONSTRAINT "quality_metrics_translationStringId_fkey";

-- AddForeignKey
ALTER TABLE "quality_metrics" ADD CONSTRAINT "quality_metrics_translationRequestId_fkey" FOREIGN KEY ("translationRequestId") REFERENCES "translation_requests"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "quality_metrics" ADD CONSTRAINT "quality_metrics_translationStringId_fkey" FOREIGN KEY ("translationStringId") REFERENCES "translation_strings"("id") ON DELETE SET NULL ON UPDATE CASCADE;
