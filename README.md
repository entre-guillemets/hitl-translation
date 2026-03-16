# MT Evals — Human-in-the-Loop Machine Translation Evaluation Platform

A research-grade, full-stack platform for professional MT quality assurance across English, Japanese, and French. MT Evals implements an 8-stage HITL evaluation pipeline covering multimodal source ingestion, pre-translation review, quality estimation, human post-editing with error annotation, automated QA metrics, and multi-dimensional insights dashboards.

![Quality Dashboard Screenshot](https://github.com/user-attachments/assets/c6b88707-f57e-441f-a6d0-7efdb87c86b4)

This is not a demo or proof-of-concept. The platform is used for genuine multilingual MT evaluation where the author serves as the qualified human annotator for all three production languages — a deliberate methodological choice that enables authentic HITL evaluation rather than synthetic ground truth.

---

## 8-Stage Pipeline

Every feature in the platform maps to one of these stages.

### Stage 1 — Upload
Accept source files: images, PDFs, audio, plain text. Automatic MIME type detection routes each file to the appropriate processor.

### Stage 2 — Parse & Segment
Extract text strings with layout context preserved:
- **Images**: Manga OCR (Japanese-specialized) or Tesseract with bounding box detection
- **Audio**: OpenAI Whisper transcription with segment-level timestamps
- **PDFs**: Direct text extraction with OCR fallback for scanned pages
- **Text**: Direct segmentation

Output is an ordered list of segments with source metadata attached.

### Stage 3 — Pre-Translation Review (String Segmentation Editor)
Interactive editor for reviewing and confirming parsed segments before translation:
- Bounding box overlay on source images
- Waveform player with timestamp markers for audio segments
- Inline segment editing, splitting, and merging
- Jobs must reach `RECONCILED` status before Stage 4 runs

### Stage 4 — Quality Estimation
COMETKiwi (`Unbabel/wmt22-cometkiwi-da`) runs reference-free QE on each confirmed segment. Per-segment QE scores (0–1) are stored in the database and surfaced in the post-editing UI to triage priority review before any human time is spent on translation.

### Stage 5 — Translation & Post-Editing
Multi-engine MT with parallel model outputs and a full post-editing interface:
- Run Helsinki-NLP (OPUS), ELAN, mT5, NLLB-200, or Gemini on confirmed segments
- Side-by-side engine output comparison
- Inline translation editing
- Annotation categories: mistranslation, fluency, terminology, omission, other
- Annotation severity: minor, major, critical
- Engine preference tracking (which engine the reviewer selected and why)
- Translation Memory (TM) fuzzy match suggestions per segment
- Bulk Review Mode with per-string signal confidence badges and completion tracking

### Stage 6 — QA Metrics
Reference-based metrics calculated against post-edited translations:
- **BLEU**: n-gram precision; benchmarking across models over time
- **TER**: Edit distance; directly measures post-editing effort
- **COMET** (`Unbabel/wmt22-comet-da`): Semantic similarity via multilingual embeddings; highest signal
- **ChrF**: Character-level F-score; reliable for Japanese and French morphology

All metrics calculated per-segment and aggregated per-job. All statistics (p-values, confidence intervals, correlations) computed via `scipy.stats` — no hardcoded values.

### Stage 6.5 — Agentic Analysis Layer
Runs automatically after Stage 6 completes:
- **Glossary reuse reporter**: Checks whether MT used correct target terms from the project glossary
- **DNT compliance checker**: Verifies protected strings were preserved in translation
- **TM leverage calculator**: Fuzzy match percentage against existing TM
- **Glossary consistency auditor**: LLM-based scan for term inconsistencies across segments

Findings surface in Stage 7 resource views and Stage 8 dashboards.

### Stage 7 — Resource Management
- **Translation Memory**: Review, approve, and edit past translations
- **Glossary**: Add, edit, delete term pairs; review AI-proposed updates
- **DNT list**: Manage protected strings per language pair

All resources feed back into Stage 4 QE scoring and Stage 5 translation.

### Stage 8 — Insights Dashboards
- Model performance leaderboards per language pair
- Post-edit quality trends over time
- QE score vs. actual post-edit effort correlation
- Glossary reuse rates and DNT compliance rates
- Metric correlation matrices (BLEU/TER/COMET/ChrF)
- **Segment Signal Confidence**: Cross-metric agreement score (`1 − 2σ` over normalized signals) — surfaces low-confidence segments for priority human review
- **Evaluation Quality tab**: Signal coverage per language pair, metric correlations by pair, LLM judge calibration against human effort
- Data source badges on every widget distinguishing live data from sample/fallback data

---

## Methodology

### Metric Selection

This platform uses BLEU + TER + ChrF + COMET + COMETKiwi. The combination is intentional:

| Metric | Category | Rationale |
|--------|----------|-----------|
| BLEU | Reference-based | Fast, interpretable, industry standard for benchmarking over time |
| TER | Reference-based | Directly measures post-editing effort — meaningful in a HITL workflow |
| ChrF | Reference-based | Character-level; handles Japanese and French morphology better than BLEU |
| COMET | Reference-based | Current gold standard for learned MT evaluation; uses multilingual embeddings |
| COMETKiwi | Reference-free QE | Completely different category — enables pre-review triage without a human reference |

**Not included, and why:**
- **MetricX**: JAX/Apple Silicon incompatibility; can be run via Colab if needed
- **BLEURT**: Redundant given ChrF + COMET for this language set

### Language Coverage

| Language | Status | Annotation basis |
|----------|--------|-----------------|
| English | Production | Native speaker |
| Japanese | Production | Native speaker (Manga OCR specialized support) |
| French | Production | Near-native speaker |
| Swahili | In development | LLM-as-judge via Claude; inter-judge consistency testing across Claude/GPT-4/Gemini as validity proxy |

The EN/JA/FR scope is a methodological choice: the author can serve as a qualified human annotator for all three, enabling genuine HITL evaluation. Swahili is the selected low-resource target: NLLB-200 provides translation coverage, and LLM-as-judge evaluation will explicitly document where automated evaluation degrades for low-resource pairs.

### Job State Machine

```
UPLOADED → PARSED → RECONCILED → QE_COMPLETE →
TRANSLATED → POST_EDITED → QA_COMPLETE → ARCHIVED
```

States must not be skipped. The pipeline enforces `RECONCILED` before QE runs and `QA_COMPLETE` before archiving.

---

## Tech Stack

### Backend
- **Runtime**: Python 3.10+
- **Framework**: FastAPI + Uvicorn
- **ORM**: Prisma (Python client)
- **Database**: PostgreSQL
- **ML / Metrics**: PyTorch, HuggingFace Transformers, Unbabel-COMET, Sacrebleu, scipy
- **QE**: COMETKiwi (`Unbabel/wmt22-cometkiwi-da`) — reference-free quality estimation
- **OCR**: Tesseract (multi-language), Manga OCR (Japanese-specialized)
- **Audio**: OpenAI Whisper (timestamped transcription)
- **PDF**: PDFplumber
- **Language Detection**: langdetect + custom Japanese character detection

### Frontend
- **Framework**: React + TypeScript + Vite
- **Styling**: Tailwind CSS + Shadcn/UI
- **Charts**: Recharts
- **Theme**: Dark mode default

### Models

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
| GEMINI | Google Gemini API | transcreation |

COMET, COMETKiwi, Manga OCR, and Whisper are managed via HuggingFace cache.

---

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+ and npm
- Git
- PostgreSQL
- System dependencies:

```bash
# Tesseract OCR (required for image extraction)
brew install tesseract tesseract-lang          # macOS
sudo apt-get install tesseract-ocr tesseract-ocr-eng tesseract-ocr-fra tesseract-ocr-jpn  # Ubuntu

# MeCab (required for Japanese tokenization with sacrebleu)
brew install mecab mecab-ipadic               # macOS
sudo apt-get install mecab libmecab-dev mecab-ipadic-utf8  # Ubuntu

# FFmpeg (required for Whisper audio processing)
brew install ffmpeg                           # macOS
sudo apt-get install ffmpeg                   # Ubuntu
```

### 1. Clone the Repository

```bash
git clone git@github.com:entre-guillemets/hitl-translation.git
cd hitl-translation
```

### 2. Download Models

Models load from a local `models/` directory not tracked in version control. Use the provided script:

```bash
python app/services/model_manager.py --download-all
```

This downloads several gigabytes and may take 20–60 minutes. To check status:

```bash
python app/services/model_manager.py --status
```

To download a single model:

```bash
python app/services/model_manager.py --download mt5_multilingual
```

**Manual placement** — if managing models yourself, place them in `models/` with these folder names:

| Model Key | HuggingFace Repo | Folder Name |
|-----------|-----------------|-------------|
| HELSINKI_EN_JP | Helsinki-NLP/opus-mt-en-jap | `Helsinki-NLP_opus-mt-en-jap` |
| OPUS_JA_EN | Helsinki-NLP/opus-mt-ja-en | `opus-mt-ja-en` |
| ELAN_JA_EN | Mitsua/elan-mt-bt-ja-en | `Mitsua_elan-mt-bt-ja-en` |
| HELSINKI_EN_FR | Helsinki-NLP/opus-mt-en-fr | `Helsinki-NLP_opus-mt-en-fr` |
| HELSINKI_FR_EN | Helsinki-NLP/opus-mt-fr-en | `Helsinki-NLP_opus-mt-fr-en` |
| OPUS_TC_BIG_EN_FR | Helsinki-NLP/opus-mt-tc-big-en-fr | `opus-mt-tc-big-en-fr` |
| T5_BASE | google-t5/t5-base | `google-t5_t5-base` |
| NLLB_200 | facebook/nllb-200-distilled-600M | `nllb-200-distilled-600M` |
| COMET | Unbabel/wmt22-comet-da | *(HuggingFace cache)* |
| COMETKiwi | Unbabel/wmt22-cometkiwi-da | *(HuggingFace cache)* |
| Manga OCR | kha-white/manga-ocr-base | *(HuggingFace cache)* |
| Whisper | openai/whisper | *(Whisper library cache)* |

**Note on COMETKiwi**: `wmt22-cometkiwi-da` is a gated HuggingFace repository — request access at https://huggingface.co/Unbabel/wmt22-cometkiwi-da. The fallback `wmt20-comet-qe-da` is freely available and uses the same `unbabel-comet` library. To upgrade, update the model name in `app/main.py`.

### 3. Backend Setup

```bash
python -m venv venv
source venv/bin/activate

pip install sentencepiece==0.2.0
pip install -r requirements.txt

# Multimodal dependencies
pip install pytesseract opencv-python pillow pdfplumber manga-ocr openai-whisper langdetect
```

Configure environment:

```bash
cp .env.example .env
```

```env
DATABASE_URL="postgresql://user:password@localhost:5432/mydb"
REACT_APP_API_URL="http://localhost:8001"
FUZZY_MATCH_THRESHOLD=0.6
AUTO_TM_CREATION=true
TRANSFORMERS_CACHE=./models
HF_HOME=./models
PYTORCH_TRANSFORMERS_CACHE=./models
LOG_LEVEL=INFO
TRANSFORMERS_TRUST_REMOTE_CODE=1
GEMINI_API_KEY=xxxxxxxx
```

Initialize the database:

```bash
python -m prisma db push
```

### 4. Frontend Setup

```bash
npm install
```

### 5. Run

```bash
npm run dev:full
```

- Backend: `http://localhost:8001`
- Frontend: `http://localhost:5173`
- API docs (Swagger UI): `http://localhost:8001/docs`

---

## API Reference

Full interactive documentation at `http://localhost:8001/docs`.

### Multimodal (Stage 1–2)
- `POST /api/extract-text` — extract text from images, PDFs, audio
- `POST /api/detect-language` — detect language from multimodal content
- `POST /api/translate-file` — upload and translate content from files

### Translation (Stage 5)
- `POST /api/translate` — translate text between supported language pairs
- `GET /api/translation-requests` — retrieve jobs with metrics
- `PUT /api/translation-requests/translation-strings/:id` — post-edit a string
- `POST /api/translation-requests/translation-strings/:id/annotations` — add annotation

### Quality Estimation (Stage 4)
- `POST /api/quality-estimation` — run COMETKiwi QE on segments

### Analytics (Stage 8)
- `GET /api/analytics/model-performance` — leaderboard data
- `GET /api/analytics/post-edit-metrics` — BLEU/TER/COMET/ChrF by language pair
- `GET /api/analytics/segment-confidence` — cross-metric signal confidence scores
- `GET /api/analytics/eval-quality` — coverage, correlations, judge calibration
- `GET /api/analytics/rlhf/quality-rating` — human preference data

### Health
- `GET /api/health/detailed` — database, COMETKiwi, and MT engine status

---

## Troubleshooting

**Tesseract not found:**
```bash
which tesseract
# If missing, install via package manager or set TESSERACT_CMD in .env
```

**Japanese OCR not working:**
```bash
sudo apt-get install tesseract-ocr-jpn   # Ubuntu
brew install tesseract-lang              # macOS
```

**Whisper fails:**
```bash
brew install ffmpeg        # macOS
sudo apt-get install ffmpeg  # Ubuntu
```

**Database connection errors:**
```bash
python -m prisma db push   # re-apply schema
python -m prisma generate  # regenerate client after schema edits
```

---

## Visual Walkthrough

Stage-by-stage screenshots with annotation: [docs/walkthrough.md](docs/walkthrough.md)

---

## License

MIT License — see [LICENSE](LICENSE) for details.
