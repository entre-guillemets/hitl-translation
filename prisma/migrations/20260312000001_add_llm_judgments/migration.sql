CREATE TABLE "llm_judgments" (
    "id" TEXT NOT NULL,
    "translationStringId" TEXT NOT NULL,
    "engineName" TEXT,
    "judgeModel" TEXT NOT NULL,
    "adequacyScore" DOUBLE PRECISION NOT NULL,
    "fluencyScore" DOUBLE PRECISION NOT NULL,
    "confidenceScore" DOUBLE PRECISION NOT NULL,
    "rationale" TEXT,
    "cometDisagreement" DOUBLE PRECISION,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "llm_judgments_pkey" PRIMARY KEY ("id")
);

CREATE INDEX "llm_judgments_translationStringId_idx" ON "llm_judgments"("translationStringId");
CREATE INDEX "llm_judgments_engineName_idx" ON "llm_judgments"("engineName");

ALTER TABLE "llm_judgments" ADD CONSTRAINT "llm_judgments_translationStringId_fkey"
    FOREIGN KEY ("translationStringId") REFERENCES "translation_strings"("id")
    ON DELETE CASCADE ON UPDATE CASCADE;
