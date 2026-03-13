CREATE TABLE "eval_snapshots" (
    "id" TEXT NOT NULL,
    "requestId" TEXT,
    "languagePair" TEXT NOT NULL,
    "engineName" TEXT,
    "runDate" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "avgBleu" DOUBLE PRECISION,
    "avgComet" DOUBLE PRECISION,
    "avgChrf" DOUBLE PRECISION,
    "avgTer" DOUBLE PRECISION,
    "segmentCount" INTEGER NOT NULL,
    "notes" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "eval_snapshots_pkey" PRIMARY KEY ("id")
);

CREATE INDEX "eval_snapshots_languagePair_idx" ON "eval_snapshots"("languagePair");
CREATE INDEX "eval_snapshots_engineName_idx" ON "eval_snapshots"("engineName");
CREATE INDEX "eval_snapshots_runDate_idx" ON "eval_snapshots"("runDate");
