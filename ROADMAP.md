# Evaluation Infrastructure for Multilingual MT Quality
## Project Roadmap

### What This Project Is

This system is **evaluation infrastructure** for measuring and understanding machine translation quality across languages — including languages where standard automatic metrics are unreliable. It uses human post-editing as a first-class signal: post-editors don't just fix translations, they generate ground-truth quality data that the system then analyzes, aggregates, and surfaces across engines, language pairs, and time.

The HITL workflow is the data collection layer. The real artifact is what you can measure from it.

---

### Current Foundation

These components are **implemented and operational**:

**Multi-engine MT orchestration**
- Parallel translation across OPUS-MT, NLLB-200, ELAN, and optional LLM engines (including Claude transcreation)
- Raw outputs from each engine stored as structured JSON per segment — enabling per-engine metric comparison, not just aggregate scores
- Fuzzy matching against translation memory before routing to MT

**Reference-based metric pipeline**
- BLEU, TER, ChrF, and COMET-DA scores calculated per engine per segment against the human post-edit as gold reference
- One `QualityMetrics` row per engine per segment (not per request) — enabling engine-level granularity
- Batch recalculation endpoint (`POST /calculate-all-approved`) that pulls COMET model from app state, scores all reviewed/approved segments, overwrites stale rows

**Reference-free quality estimation**
- COMETKiwi (`wmt20-comet-qe-da`) loaded at startup, available for pre-edit quality prediction before human reference exists
- `/cometkiwi/evaluate` and `/predict-quality` endpoints operational
- DA z-score → quality label mapping calibrated for the wmt20-comet-qe-da output range (~-2 to +2)

**Quality dashboard**
- Model leaderboard by average COMET, BLEU, TER, ChrF across all approved segments
- Post-edit quality metrics broken down by language pair
- Metric correlation matrix (BLEU/COMET/TER/ChrF) computed from real data
- COMET trend analysis by language pair, model, or date

**WMT benchmark integration**
- `wmt_benchmarks` router exists for running standard benchmark evaluation sets

**Human feedback and annotation**
- MQM-style error span annotation (fluency, adequacy, terminology, style, register)
- Preference comparison between engine outputs
- RLHF data collection for downstream use

---

### Sprint 1 — Evaluation Methodology (Current)

**Goal:** Make the project demonstrate what evaluation infrastructure for multilingual AI *actually looks like* — not just metric dashboards, but methodology, reliability, and signal quality.

#### 1. LLM-as-Judge Evaluation Layer

The core argument for this role is that benchmark scores alone are insufficient signals, especially for low-resource languages. LLM-as-judge is the practical answer.

Implementation:
- New service: `app/services/llm_judge_service.py`
- For each post-edited segment, call Claude API with a structured evaluation prompt requesting:
  - Adequacy score (0–4): does the MT convey the full meaning of the source?
  - Fluency score (0–4): is the output natural in the target language?
  - Confidence score (0–1): how certain is the judge given available context?
  - Brief rationale (1–2 sentences)
- Store results in a new `LLMJudgment` table alongside `QualityMetrics`
- New analytics endpoint: `GET /api/analytics/judge-vs-metrics` — surfaces segments where LLM judgment and automatic metrics disagree (high BLEU + low adequacy, etc.)

**Why this matters:** Disagreement between the LLM judge and surface metrics is itself a research finding. It identifies where BLEU/TER are giving false confidence — which is exactly the kind of signal a research TPM would track and escalate to pre-training teams.

#### 2. Metric Reliability Analysis by Language

The project currently scores all language pairs with the same metric suite. This is technically wrong — BLEU's n-gram assumption breaks on agglutinative languages; TER's word-level edit distance is meaningless for scripts without whitespace-delimited tokens.

Implementation:
- New endpoint: `GET /api/analytics/metric-reliability/{language_pair}`
- Returns per-language metadata: script type, tokenization strategy used, known reliability concerns for each metric, sample size, and a `reliability_warning` flag when n < 30 or when BLEU variance across segments is unusually high
- Add `metricReliabilityWarning` field to leaderboard and language-pair analytics responses
- Surface warnings as tooltip annotations in the Quality Dashboard

This doesn't require new data — it annotates existing data with methodological context. The output is a table like:

| Language Pair | BLEU reliability | COMET reliability | ChrF reliability | Notes |
|---|---|---|---|---|
| JP-EN | ⚠️ Low (tokenization) | ✓ | ✓ | MeCab tokenizer used; BLEU sensitive to tokenizer choice |
| EN-JA | ⚠️ Low | ✓ | ✓ | CJK script; BLEU n<30 in this dataset |
| FR-EN | ✓ | ✓ | ✓ | Well-resourced pair, all metrics reliable |

#### 3. Regression Test Harness

The `wmt_benchmarks` router already exists. This sprint closes the loop: a fixed evaluation set per language pair that can be re-run against any model or configuration to detect regressions.

Implementation:
- New table: `EvalSnapshot` (eval_set_id, model_name, model_version, run_date, avg_bleu, avg_comet, avg_chrf, avg_ter, segment_count)
- Endpoint: `POST /api/benchmarks/snapshot` — runs the fixed eval set against the current model configuration and saves a snapshot
- Endpoint: `GET /api/benchmarks/regression-report` — diffs the two most recent snapshots per language pair, flags any metric that degraded more than a configurable threshold (default: 2 BLEU points, 0.02 COMET)
- Dashboard widget: regression timeline per language pair with threshold bands

**Why this matters:** "Regression testing across model updates" is verbatim from the JD. This is the operationalization of it.

---

### Sprint 2 — Low-Resource Language Experiment

**Goal:** Add a genuinely low-resource language (Swahili, SW) and document evaluation methodology breakdown — not as a feature, but as a research experiment with findings.

#### 1. Swahili Support

- Add `SW` to `SourceLanguage` and `TargetLanguage` enums in Prisma schema
- NLLB-200 already covers Swahili (`ace_Latn` → `swh_Latn`) — route SW pairs through NLLB by default
- Source 50–100 SW↔EN sentence pairs with reference translations (FLORES-200 dataset is public and covers Swahili)
- Ingest as a fixed eval set via the benchmark infrastructure from Sprint 1

#### 2. Document Metric Degradation

Run the full metric suite on SW-EN and EN-SW and write up findings in `docs/low-resource-evaluation.md`:
- BLEU scores will be artifically low due to morphological complexity (Swahili has 8 noun classes, rich verb morphology)
- ChrF will outperform BLEU — character-level overlap is more meaningful than n-gram overlap for agglutinative languages
- COMET-DA may be unreliable if wmt20-comet-da has sparse Swahili training data — document this
- LLM judge (from Sprint 1) becomes the primary signal for SW — document why and what the inter-metric disagreement looks like

**The artifact here is the documentation**, not just the code. A 2-page findings doc that explains why BLEU fails on Swahili and what you used instead is exactly what demonstrates research credibility for this role.

#### 3. Inter-Annotator Agreement

When multiple reviewers post-edit the same source segment (or when annotation data exists for the same segment from different sessions), calculate inter-annotator agreement:
- Cohen's κ on quality labels (EXCELLENT/GOOD/FAIR/POOR/CRITICAL)
- Krippendorff's α on TER scores (continuous)
- Flag segments with κ < 0.4 as "low-confidence evaluation" — these are candidates for adjudication

New endpoint: `GET /api/analytics/annotator-agreement`

This feeds into data quality reporting — a core operational concern for anyone managing multilingual dataset collection at scale.

---

### Sprint 3 — Data Quality Audit and Signal Confidence

**Goal:** Build the "meaningful signal beyond benchmark scores" layer — a view that identifies where the evaluation itself is uncertain and where human review effort should be concentrated.

#### 1. Segment-Level Signal Confidence

For each evaluated segment, compute a `signal_confidence` score based on:
- Do all four automatic metrics agree on quality direction? (high BLEU + high COMET + low TER = coherent signal)
- Does the LLM judge agree with automatic metrics?
- Is this language pair flagged for metric unreliability (from Sprint 1)?
- Was the human post-edit effort low (near-zero TER = minimal change) or high (editor rewrote significantly)?

Segments with low signal confidence should be surfaced for human review, not treated as ground truth.

#### 2. Data Quality Dashboard View

New dashboard tab: **Evaluation Quality**
- Distribution of signal confidence scores across language pairs
- Segments where LLM judge and COMET disagree most (sorted by |comet - llm_adequacy_normalized|)
- Low inter-annotator agreement segments
- Language pairs where metric reliability warnings are active
- Sample size sufficiency indicator per language pair (n < 30 = insufficient for aggregated claims)

#### 3. Metric Correlation by Language

The current correlation matrix is global. This sprint makes it per-language-pair:
- Does COMET correlate with human TER effort on JP-EN? What about SW-EN?
- If COMET and TER decorrelate on a language pair, that's a signal that one of them is unreliable for that pair
- Surface this as a language-pair-specific reliability finding, not just a global matrix

---

### What Was Deprioritized and Why

**Stage 7 Resource Management UI** (TM/Glossary/DNT management interfaces): The backend CRUD is complete. This is a translator tooling feature, not evaluation methodology. It may be revisited if the project narrative shifts toward demonstrating end-to-end workflow ownership, but it doesn't strengthen the eval infrastructure story.

**Agentic analysis layer** (DNT compliance checker, glossary reuse reporter, TM leverage calculator): These are valuable localization QA features but belong to a different product layer. They answer "did the translation follow instructions?" not "is our evaluation methodology sound?" Deprioritized in favor of the research credibility work above.

**METEOR metric**: Marginally better than BLEU for morphological languages but adds limited differentiation given that ChrF already handles character-level overlap. The LLM-as-judge and COMET are higher-signal investments.

**scipy p-values and confidence intervals**: Technically correct work, but not differentiating for the target role. The metric reliability and inter-annotator agreement work (Sprints 1–2) demonstrates statistical methodology more compellingly than adding scipy imports to analytics.py.

**Pipeline state machine** (UPLOADED → RECONCILED → QE_COMPLETE → ...): Defined in CLAUDE.md but not tracked in the DB or service layer. Not needed for the evaluation infrastructure story — the current status-based filtering (REVIEWED/APPROVED) is sufficient.

---

### Interview Narrative

> "I built evaluation infrastructure for multilingual MT quality. The core insight is that the HITL post-editing workflow isn't just a translation tool — it's a data collection mechanism. Every time a human editor changes an MT output, that's a quality signal. The system captures that signal, scores it against multiple automatic metrics, and then — critically — interrogates the reliability of those metrics per language pair.
>
> For well-resourced language pairs like French-English, you can trust BLEU and COMET. For Japanese, you need to be careful about tokenization. For Swahili, BLEU is largely noise — the morphological complexity means n-gram overlap doesn't correspond to translation quality. So we added an LLM-as-judge layer that runs alongside the automatic metrics and flags disagreement. High disagreement between COMET and the LLM judge is itself a research finding — it tells you where your evaluation is uncertain, which is exactly the information a pre-training team needs when they're deciding what data to collect next.
>
> The regression harness closes the loop: for any language pair with a fixed evaluation set, I can re-run the full metric suite against any model configuration and surface degradations before they reach production."
