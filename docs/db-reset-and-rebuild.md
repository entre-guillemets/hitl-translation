# Database Reset and Baseline Rebuild

This document describes when and how to reset the database and rebuild a clean,
reproducible evaluation baseline. It is intended for use after significant changes
to the pipeline, metric stack, language support, or model configuration.

---

## When a Reset Is Warranted

A reset is appropriate when accumulated test data is no longer a valid basis for
research conclusions. Specific triggers include:

- Eval metric libraries updated (sacrebleu, unbabel-comet, comet-kiwi) — scores
  computed under different versions are not directly comparable
- Language codes changed or normalized (e.g., JA/JP inconsistency)
- Pipeline state machine redefined — old jobs may be stuck in states that no longer
  exist or lack fields required by newer stages
- Models added, removed, or renamed — engine name changes break leaderboard continuity
- Translation routing bugs fixed — any data generated during a broken routing period
  (e.g., Gemini not firing) is structurally incomplete
- Six months or more of ad hoc development testing mixed with genuine evaluation runs

The goal of the reset is to produce a clean baseline where every number is traceable
to a known model version, metric library version, and dataset version.

---

## Step 1 — Before the Reset: Preserve Valuable Data

Not all existing data is worthless. Human post-edits with annotation notes represent
genuine annotation effort and should be exported before the wipe.

Run the following to dump any translations where a human post-edit and annotation
notes both exist:

```bash
psql $DATABASE_URL -c "\COPY (
  SELECT
    tr.id AS request_id,
    tr.\"sourceLanguage\",
    ts.\"targetLanguage\",
    ts.\"sourceText\",
    ts.\"translatedText\",
    ts.\"postEditedText\",
    ts.\"engineName\",
    ts.\"annotationCategory\",
    ts.\"annotationNotes\",
    ts.\"createdAt\"
  FROM \"TranslationString\" ts
  JOIN \"TranslationRequest\" tr ON ts.\"translationRequestId\" = tr.id
  WHERE ts.\"postEditedText\" IS NOT NULL
    AND ts.\"annotationNotes\" IS NOT NULL
  ORDER BY ts.\"createdAt\"
) TO 'exports/human_annotations_pre_reset.csv' CSV HEADER;"
```

Also export glossary entries and TM entries — these are resources, not test data,
and should survive the reset:

```bash
psql $DATABASE_URL -c "\COPY \"GlossaryEntry\" TO 'exports/glossary_pre_reset.csv' CSV HEADER;"
psql $DATABASE_URL -c "\COPY \"TranslationMemory\" TO 'exports/tm_pre_reset.csv' CSV HEADER;"
```

Create the exports directory first: `mkdir -p exports`

---

## Step 2 — Pin Metric Library Versions

Before wiping, record the exact versions of all metric libraries currently installed.
Every score in the new baseline must be computed with these versions — future
comparisons are only valid if versions match.

```bash
pip show sacrebleu unbabel-comet comet transformers torch | \
  grep -E "^(Name|Version):" > docs/metric-versions.txt
```

Add `docs/metric-versions.txt` to version control. If you upgrade any of these
libraries in the future, treat it as a breaking change requiring a new baseline run.

---

## Step 3 — Run the Reset

```bash
# Wipe all data, keep schema
python -m prisma migrate reset --force

# Regenerate the Prisma client after reset
python -m prisma generate
```

`migrate reset --force` drops all data and re-applies migrations from scratch.
The schema (enums, indexes, relations) is preserved. The `--force` flag skips
the interactive confirmation prompt.

Verify the database is empty:

```bash
psql $DATABASE_URL -c "SELECT COUNT(*) FROM \"TranslationRequest\";"
# Expected: 0
```

---

## Step 4 — Rebuild the Baseline

Run benchmark evaluations in this order. The order matters: EN-FR establishes a
clean high-resource baseline (most reliable metrics), JA/JP pairs test the CJK
pipeline, SW pairs test the low-resource pipeline including LLM judge.

### 4a. Restart the backend

The model services cache on startup. After a reset, restart to ensure no stale
state from the old data:

```bash
npm run dev:full
```

### 4b. Run FLORES-200 / WMT benchmarks for all pairs

Use the benchmark endpoint for each language pair. The `sample_size` parameter
controls how many sentences to translate; the full devtest set is recommended.

```bash
# High-resource pairs first
curl -X POST "http://localhost:8001/api/benchmarks/create?language_pair=en-fr&sample_size=100"
curl -X POST "http://localhost:8001/api/benchmarks/create?language_pair=fr-en&sample_size=100"

# CJK pairs
curl -X POST "http://localhost:8001/api/benchmarks/create?language_pair=en-jp&sample_size=100"
curl -X POST "http://localhost:8001/api/benchmarks/create?language_pair=jp-en&sample_size=100"

# Low-resource pairs (FLORES-200 source)
curl -X POST "http://localhost:8001/api/benchmarks/create?language_pair=en-sw&sample_size=10"
curl -X POST "http://localhost:8001/api/benchmarks/create?language_pair=sw-en&sample_size=10"
```

Wait for each request to complete before starting the next pair. The benchmark
endpoint is synchronous for the translation step and will return when done.

### 4c. Run QE (COMETKiwi) on all new segments

```bash
curl -X POST "http://localhost:8001/api/quality-estimation/process-all-pending"
```

This scores all new segments with COMETKiwi before any human review. These
pre-review QE scores are the Stage 4 signal and must exist before post-editing.

### 4d. Run QA metrics (BLEU, TER, COMET, ChrF)

After QE, compute reference-based metrics against the FLORES-200 / WMT references:

```bash
curl -X POST "http://localhost:8001/api/quality-assessment/process-all-pending"
```

### 4e. Run LLM judge on SW segments

For Swahili, the LLM judge is the primary quality signal. Run it immediately after
QA metrics so disagreement scores exist from the start:

```bash
curl -X POST "http://localhost:8001/api/llm-judge/run-all-approved"
```

Note: the LLM judge requires segments to be in an approved/post-edited state.
If running benchmarks without human post-edits, you may need to set segments to
an approved status first, or use the judge's direct evaluation endpoint.

### 4f. Reimport preserved resources

If glossary entries and TM entries were exported in Step 1, reimport them:

```bash
curl -X POST "http://localhost:8001/api/resources/import-glossary" \
  -F "file=@exports/glossary_pre_reset.csv"

curl -X POST "http://localhost:8001/api/resources/import-tm" \
  -F "file=@exports/tm_pre_reset.csv"
```

---

## Step 5 — Verify the Baseline

After the rebuild, confirm the following before treating any results as valid:

```
[ ] Dashboard leaderboard shows all expected models for each pair
[ ] COMET scores are in plausible range: high-resource pairs > 0.7, SW pairs variable
[ ] No COMET scores below -0.5 (negative COMET is a sign of metric computation error)
[ ] Metric Reliability Notes table shows EN-JA/EN-JP as a single deduplicated row
[ ] SW pairs show "LLM judge" as Primary Signal in the reliability table
[ ] Sample size n is identical for all models on the same language pair
    (if models have different n, some translations didn't complete)
[ ] docs/metric-versions.txt is committed alongside the baseline run date
```

Record the baseline run date in `docs/metric-versions.txt`:

```
Baseline established: YYYY-MM-DD
Pairs: en-fr, fr-en, en-jp, jp-en, en-sw, sw-en
Sentence counts: 100 (EN/FR/JP), 10 (SW) per direction
```

---

## Notes for Future Resets

- Any upgrade to sacrebleu, unbabel-comet, or comet-kiwi constitutes a breaking
  change. Treat it the same as a reset: pin new versions, rerun baseline, document
  the change date.
- Expanding FLORES-200 sample size for SW (currently 10 sentences — the full devtest
  has 1,012) should be done as a deliberate baseline extension, not an ad hoc run.
- If adding a new language pair after a baseline is established, run benchmarks for
  that pair in isolation and document it as an addendum to the baseline, not a
  replacement.
