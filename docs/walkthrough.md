# MT Evals — Visual Walkthrough

A stage-by-stage walkthrough of the platform UI. Screenshots reflect production usage with real EN/JA/FR evaluation data.

---

## Stage 1 — Upload

Accept source files: images, PDFs, audio, plain text. Automatic MIME type detection routes each file to the appropriate processor.

<!-- Screenshot: Upload screen with file type selector and drag-drop zone -->
<!-- docs/screenshots/stage1-upload.png -->

---

## Stage 2 — Parse & Segment

Text is extracted from the source file and split into an ordered segment list. Each segment carries source metadata: bounding box coordinates for images, timestamps for audio.

<!-- Screenshot: Parsed segment list showing position numbers, source text, and pipeline state badges -->
<!-- docs/screenshots/stage2-parsed-segments.png -->

---

## Stage 3 — Pre-Translation Review (String Segmentation Editor)

The most visually distinctive stage. Source image is displayed with colored bounding boxes overlaid on each detected text region. The editable segment list appears alongside the annotated image. Users can edit segment text inline, split or merge segments, and confirm the set before the pipeline proceeds.

Audio sources show a waveform player with timestamp markers aligned to each segment.

Jobs must reach `RECONCILED` status before Stage 4 runs.

<!-- Screenshot: Image source with bounding box overlay (key differentiating screen) -->
<!-- docs/screenshots/stage3-bounding-box-overlay.png -->

<!-- Screenshot (optional): Audio source with waveform player and timestamp segment markers -->
<!-- docs/screenshots/stage3-audio-waveform.png -->

---

## Stage 4 — Quality Estimation

COMETKiwi (`Unbabel/wmt22-cometkiwi-da`) runs reference-free QE on each confirmed segment. Per-segment scores (0–1) are stored and surfaced in the post-editing UI to triage priority segments before any human review time is spent.

<!-- Screenshot: QE scores displayed per segment, with low-confidence segments visually flagged -->
<!-- docs/screenshots/stage4-qe-scores.png -->

---

## Stage 5 — Translation & Post-Editing

Multiple MT engines run in parallel on confirmed segments. The post-editing interface shows side-by-side engine output comparison, inline translation editing, and per-segment signal confidence badges.

**Bulk Review Mode** surfaces all strings with completion tracking, signal confidence badges (`Conf: XX%`), and engine self-scores per segment.

<!-- Screenshot: Post-editing interface with side-by-side engine comparison -->
<!-- docs/screenshots/stage5-post-editing.png -->

<!-- Screenshot: Bulk Review Mode showing confidence badges and completion progress (key screen) -->
<!-- docs/screenshots/stage5-bulk-review-confidence.png -->

<!-- Screenshot: Annotation panel with error category and severity selectors -->
<!-- docs/screenshots/stage5-annotation-panel.png -->

---

## Stage 6 — QA Metrics

Reference-based metrics (BLEU, TER, COMET, ChrF) calculated against post-edited translations. All metrics computed per-segment and aggregated per-job. All statistics (p-values, confidence intervals, correlations) computed via `scipy.stats`.

<!-- Screenshot: QA metrics view showing per-segment and aggregated scores -->
<!-- docs/screenshots/stage6-qa-metrics.png -->

---

## Stage 6.5 — Agentic Analysis Layer

Runs automatically after Stage 6 completes. Checks glossary reuse, DNT compliance, TM leverage, and term consistency across segments. Findings surface in Stage 7 resource views and Stage 8 dashboards.

<!-- Screenshot: Agentic analysis findings panel -->
<!-- docs/screenshots/stage6-5-agentic-analysis.png -->

---

## Stage 7 — Resource Management

Translation Memory, Glossary, and DNT list management. All resources feed back into Stage 4 QE scoring and Stage 5 translation suggestions.

<!-- Screenshot: Glossary management view with term pairs and AI-proposed updates -->
<!-- docs/screenshots/stage7-glossary.png -->

<!-- Screenshot (optional): Translation Memory review queue -->
<!-- docs/screenshots/stage7-tm.png -->

---

## Stage 8 — Insights Dashboards

### Model Performance

Per-language-pair leaderboard comparing MT engine scores across BLEU, TER, COMET, and ChrF.

<!-- Screenshot: Model performance leaderboard with engine rows and language pair filter -->
<!-- docs/screenshots/stage8-model-leaderboard.png -->

### Post-Edit Quality Trends

<!-- Screenshot: Quality trends over time chart -->
<!-- docs/screenshots/stage8-quality-trends.png -->

### Evaluation Quality Tab

Segment Signal Confidence: cross-metric agreement score (`1 − 2σ` over normalized signals). Per-language-pair confidence table with mean/min/max. Lowest-confidence segment triage list for priority human review.

<!-- Screenshot: Eval Quality tab — Segment Signal Confidence card (key methodological screen) -->
<!-- docs/screenshots/stage8-segment-confidence.png -->

<!-- Screenshot: Metric correlation matrix (BLEU/TER/COMET/ChrF) -->
<!-- docs/screenshots/stage8-metric-correlations.png -->

---

## Data Source Transparency

Every dashboard widget displays a data source badge distinguishing live data from sample or fallback data. This is a deliberate design choice — the platform never silently substitutes synthetic values in research outputs.

<!-- Screenshot: Dashboard widget showing live data badge vs. sample data badge -->
<!-- docs/screenshots/data-source-badges.png -->
