# MT Evals — CLAUDE.md
> This file gives Claude Code full context about the MT Evals project architecture,
> conventions, and development patterns. Read this before making any changes.

---

## Project Overview

**MT Evals** is a full-stack, AI-enabled machine translation quality assurance platform.
It is not a demo — it is a working research tool used for genuine multilingual evaluation
across English, Japanese, and French, with planned support for low-resource languages.

The platform implements a professional-grade localization workflow:
multimodal source ingestion → pre-translation review → quality estimation →
human post-editing with annotations → automated QA metrics → insights dashboards.

The primary author is a trilingual (EN/JA/FR) TPM with deep MT evaluation expertise.
Design decisions are intentional and research-informed. When in doubt, ask before
changing evaluation logic, metric selection, or pipeline sequencing.

---

## Tech Stack

### Backend
- **Runtime**: Python 3.10+
- **Framework**: FastAPI + Uvicorn
- **ORM**: Prisma (Python client)
- **Database**: PostgreSQL
- **ML / Metrics**: PyTorch, HuggingFace Transformers, Unbabel-COMET, Sacrebleu
- **QE**: COMETKiwi (`Unbabel/wmt22-cometkiwi-da`) — reference-free quality estimation
- **OCR**: Tesseract (multi-language), Manga OCR (Japanese-specialized)
- **Audio**: OpenAI Whisper (timestamped transcription)
- **PDF**: PDFplumber
- **Language Detection**: langdetect + custom Japanese character detection

### Frontend
- **Framework**: Next.js + React + TypeScript
- **Styling**: Tailwind CSS + Shadcn/UI
- **Charts**: Recharts
- **Theme**: Dark mode by default (toggle available)

### Models (loaded from local `/models` directory)
| Key | Model | Direction |
|-----|-------|-----------|
| HELSINKI_EN_JP | Helsinki-NLP/opus-mt-en-jap | EN→JA |
| OPUS_JA_EN | Helsinki-NLP/opus-mt-ja-en | JA→EN |
| ELAN_JA_EN | Mitsua/elan-mt-bt-ja-en | JA→EN |
| HELSINKI_EN_FR | Helsinki-NLP/opus-mt-en-fr | EN→FR |
| HELSINKI_FR_EN | Helsinki-NLP/opus-mt-fr-en | FR→EN |
| OPUS_TC_BIG_EN_FR | Helsinki-NLP/opus-mt-tc-big-en-fr | EN→FR (large) |
| T5_BASE | google-t5/t5-base | multilingual |
| NLLB_200 | facebook/nllb-200-distilled-600M | 200 languages |
| GEMINI | Google Gemini API (`gemini-3.1-flash-lite-preview` for SW pairs) | transcreation |

COMET, COMETKiwi, Manga OCR, and Whisper are managed via HuggingFace cache.

---

## Pipeline Architecture (8 Stages)

Every feature must map to one of these stages. New features should be placed in the
correct stage — do not add translation logic to the dashboard layer, or metric
calculation logic to the ingestion layer.

```
Stage 1 — UPLOAD
  Accept source files: images, PDFs, audio, plain text
  Detect MIME type and route to appropriate processor

Stage 2 — PARSE & SEGMENT
  Extract text strings, preserving layout context
  Images: Manga OCR (JA) or Tesseract, with bounding box detection
  Audio: Whisper transcription with segment-level timestamps
  PDFs: direct text extraction with OCR fallback for scanned pages
  Output: ordered list of segments with source metadata

Stage 3 — PRE-TRANSLATION REVIEW (String Segmentation Editor)
  Show parsed segments alongside source media
  Images: bounding box overlay on source image
  Audio: waveform player with segment timestamp markers
  User can: edit segment text inline, split segments, merge segments
  User confirms segments before pipeline proceeds
  Status: RECONCILED required before Stage 4 runs

Stage 4 — QUALITY ESTIMATION (QE)
  Run COMETKiwi on each confirmed segment (reference-free)
  Output: per-segment QE score (0–1)
  High-confidence segments flagged as likely acceptable
  Low-confidence segments flagged for priority human review
  QE scores stored in DB and surfaced in post-editing UI

Stage 5 — TRANSLATION + POST-EDITING
  Run selected MT models on confirmed segments
  Present translations to user in post-editing interface
  User can: edit translations inline, add annotations, tag error types
  Annotation categories: mistranslation, fluency, terminology, omission, other
  Compare QE score (pre) vs. actual post-edit effort (post)
  Gemini available for transcreation tasks (performs well vs. fine-tuned models)

Stage 6 — QA METRICS (reference-based, requires post-edited reference)
  BLEU: n-gram precision, benchmarking across models over time
  TER: edit distance, measures actual post-editing effort
  COMET: semantic similarity via multilingual embeddings (highest signal)
  ChrF: character-level F-score, reliable for JA/FR morphology
  All metrics calculated per-segment and aggregated per-job
  NO hardcoded placeholder values — all statistics must be computed

Stage 6.5 — AGENTIC ANALYSIS LAYER (in development)
  Runs automatically after Stage 6 completes
  Glossary reuse reporter: checks if MT used correct target terms
  DNT compliance checker: verifies protected strings were preserved
  TM leverage calculator: fuzzy match % against existing TM
  Glossary consistency auditor: LLM-based scan for term inconsistencies
  Findings surface in Stage 7 UI and Stage 8 dashboards

Stage 7 — RESOURCE MANAGEMENT
  TM (Translation Memory): review, approve, edit past translations
  Glossary: add/edit/delete term pairs, review AI-proposed updates
  DNT list: manage protected strings per language pair
  All resources feed back into Stage 4 QE and Stage 5 translation

Stage 8 — INSIGHTS DASHBOARDS
  Model performance leaderboards (per language pair)
  Post-edit quality trends over time
  QE score vs. actual effort correlation
  Glossary reuse rates and DNT compliance rates
  Metric correlation matrices (BLEU/TER/COMET/ChrF)
  Data source badges: clearly distinguish real data from sample/fallback data
```

### Job State Machine
Every translation job tracks segment-level state. Do not skip states.

```
UPLOADED → PARSED → RECONCILED → QE_COMPLETE →
TRANSLATED → POST_EDITED → QA_COMPLETE → ARCHIVED
```

---

## Evaluation Metric Philosophy

This is a research tool. Metric selection is intentional — understand why before changing.

**Why this combination:**
- BLEU + TER = fast, interpretable, industry-standard benchmarks. TER directly measures
  post-editing effort, which is meaningful in a HITL workflow.
- ChrF = character-level metric that handles Japanese and French morphology better than
  BLEU. Correlates well with human judgment for non-Latin scripts.
- COMET = current gold standard for learned evaluation. Uses multilingual embeddings.
  Subsumes most of what BLEURT would add — do not add BLEURT.
- COMETKiwi = reference-free QE. Completely different category from the above.
  Enables pre-review triage (Stage 4) without needing a human reference.

**What we explicitly decided NOT to add:**
- MetricX: JAX/Apple Silicon incompatibility. Run via Colab if needed, document separately.
- BLEURT: redundant given ChrF + COMET for our EN/JA/FR language set.

**Metric calculation rules:**
- All statistics (p-values, confidence intervals, correlations) must be computed via
  scipy.stats. No hardcoded values anywhere in the codebase.
- Per-segment scores must be stored in DB, not just aggregated totals.
- Always display sample size (n) alongside any statistical output.

---

## Language Coverage

### Current (production)
- English (native speaker annotation)
- Japanese (native speaker annotation — Manga OCR specialized support)
- French (near-native annotation)

Language selection rationale: author can serve as qualified human annotator for all
three, enabling genuine HITL evaluation rather than synthetic ground truth.
This is a methodological choice, not a limitation. Document it as such.

### Planned
- One low-resource language via NLLB-200 (target: Swahili or Bengali)
- LLM-as-judge evaluation for low-resource pairs (Claude primary judge)
- Inter-judge consistency testing across Claude/GPT-4/Gemini as validity proxy
- Explicit documentation of where automated evaluation degrades for low-resource pairs

---

## API Conventions

**Base URL**: `http://localhost:8001`
**Docs**: `http://localhost:8001/docs` (Swagger UI)

### Routing rules (enforce consistency — this was a known issue)
- All endpoints use `/api/` prefix
- Translation endpoints: `/api/translate`, `/api/translation-requests`
- Multimodal endpoints: `/api/extract-text`, `/api/detect-language`, `/api/translate-file`
- Analytics endpoints: `/api/analytics/` (not `/api/translation-requests` for analytics)
- QE endpoints: `/api/quality-estimation`
- Agentic analysis: `/api/analysis/glossary-reuse`, `/api/analysis/dnt-compliance`

### Response conventions
- Always include `data_source` field: `"real"` | `"sample"` | `"fallback"`
- Always include `n` (sample size) in any aggregated statistical response
- Segment responses always include `job_id`, `segment_id`, `pipeline_state`

---

## Database Schema (key models)

```
Job
  id, created_at, source_language, target_languages[], pipeline_state
  source_file_type (image|audio|pdf|text), source_file_path

Segment
  id, job_id, position, source_text, pipeline_state
  ocr_bounding_box (JSON, images only)
  audio_timestamp_start, audio_timestamp_end (audio only)
  qe_score (COMETKiwi, nullable until Stage 4)

Translation
  id, segment_id, model_name, raw_output
  post_edited_text (nullable until Stage 5)
  annotation_category, annotation_notes
  bleu, ter, comet, chrf (nullable until Stage 6)

GlossaryEntry
  id, source_term, target_term, language_pair
  domain, notes, created_at, last_used_at

DNTEntry
  id, term, language_pair, context_notes

TranslationMemory
  id, source_text, target_text, language_pair
  job_id, quality_score, times_reused
```

---

## Frontend Conventions

- Dark theme is default. Components must look correct in dark mode first.
- Use Shadcn/UI components before writing custom components.
- Recharts for all data visualization — do not introduce new charting libraries.
- Segment editors always show: segment number, source text, edit button, status badge.
- Pipeline state badges use consistent colors:
  - UPLOADED: gray
  - RECONCILED: blue
  - QE_COMPLETE: purple
  - POST_EDITED: orange
  - QA_COMPLETE: green
  - ARCHIVED: muted

**Data source transparency (critical):**
Every dashboard widget that could show sample/fallback data must display a badge:
- 🟢 Live data
- 🟡 Sample data
- 🔴 Insufficient data (show minimum n required)

---

## Development Workflow

### Running the project
```bash
npm run dev:full          # starts both frontend and backend
```

Backend: `http://localhost:8001`
Frontend: `http://localhost:5173`

### Environment variables (.env)
```
DATABASE_URL="postgresql://user:password@localhost:5432/mydb"
REACT_APP_API_URL="http://localhost:8001"
FUZZY_MATCH_THRESHOLD=0.6
AUTO_TM_CREATION=true
TRANSFORMERS_CACHE=./models
HF_HOME=./models
PYTORCH_TRANSFORMERS_CACHE=./models
LOG_LEVEL=INFO
TRANSFORMERS_TRUST_REMOTE_CODE=1
```

### Database
```bash
python -m prisma db push      # apply schema changes
python -m prisma generate     # regenerate client after schema edits
```

### Model management
```bash
python app/services/model_manager.py --status        # check loaded models
python app/services/model_manager.py --download-all  # download all models
```

---

## Testing Approach

### What's fully tested
- BLEU/TER/COMET/ChrF calculation accuracy
- Database CRUD operations
- Multi-engine orchestration
- Image OCR (Tesseract + Manga OCR)
- PDF extraction with OCR fallback
- Whisper transcription + timestamp segmentation
- Language detection across modalities

### What needs testing (priority order)
1. COMETKiwi QE score calculation and storage
2. Placeholder → real statistical calculations (scipy.stats)
3. Agentic analysis layer (glossary reuse, DNT compliance)
4. Confidence interval calculations across data distributions
5. Concurrent load performance
6. Low-resource language evaluation pipeline

### Screenshot testing
When implementing UI features, take a screenshot of the result and verify:
- Correct pipeline state badge is shown
- Data source badge is present on dashboard widgets
- Segment editor shows source media alongside segments
- Dark mode renders correctly

---

## Known Issues (do not reintroduce)

1. **Placeholder statistics**: p-values, confidence intervals, and correlation
   coefficients in analytics were previously hardcoded. All must use scipy.stats.
2. **Mixed routing**: analytics previously used inconsistent API paths. All analytics
   go through `/api/analytics/`.
3. **Data source ambiguity**: dashboard previously didn't distinguish real vs. sample
   data. All widgets must show data source badge.

---

## What This Project Is Designed to Demonstrate

For anyone reading this in a hiring or evaluation context:

This platform implements the same evaluation patterns used in professional MT research:
- Multi-metric evaluation with complementary signal (not redundant metrics)
- Reference-free QE for pre-review triage vs. reference-based metrics for post-edit QA
- HITL annotation with error typology, not just accept/reject
- Segment-level state tracking through a defined pipeline
- Multimodal source handling with layout-aware segmentation
- Methodological documentation of why each design decision was made

The author serves as the human annotator for EN/JA/FR — a deliberate choice that
enables genuine human-in-the-loop evaluation rather than synthetic ground truth.