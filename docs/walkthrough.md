# MT Evals — Visual Walkthrough

A stage-by-stage walkthrough of the platform UI. Screenshots reflect production usage with real EN/JA/FR evaluation data.

---

## Stage 1 — Upload

Accept source files: images, PDFs, audio, plain text. Automatic MIME type detection routes each file to the appropriate processor.

<img width="1500" height="806" alt="request-translation" src="https://github.com/user-attachments/assets/b2808a64-20e4-4184-ae75-e08b57c07854" />

<!-- Screenshot: Upload screen with file type selector and drag-drop zone -->
<!-- docs/screenshots/stage1-upload.png -->

---

## Stage 2 — Parse & Segment

Text is extracted from the source file and split into an ordered segment list. Each segment carries source metadata: bounding box coordinates for images, timestamps for audio.

<img width="1493" height="815" alt="string-merge" src="https://github.com/user-attachments/assets/cb182866-4c2e-4e02-b015-5cc6588aafb1" />

<!-- Screenshot: Parsed segment list showing position numbers, source text, and pipeline state badges -->
<!-- docs/screenshots/stage2-parsed-segments.png -->

---

## Stage 3 — Pre-Translation Review (String Segmentation Editor)

The most visually distinctive stage. Source image is displayed with colored bounding boxes overlaid on each detected text region. The editable segment list appears alongside the annotated image. Users can edit segment text inline, split or merge segments, and confirm the set before the pipeline proceeds.

Audio sources show a waveform player with timestamp markers aligned to each segment.

Jobs must reach `RECONCILED` status before Stage 4 runs.

<img width="1510" height="811" alt="Screenshot 2026-03-16 at 22 09 18" src="https://github.com/user-attachments/assets/b44d2f31-1526-4c02-9b1f-9b0077f2cd80" />


<!-- Screenshot: Image source with bounding box overlay (key differentiating screen) -->
<!-- docs/screenshots/stage3-bounding-box-overlay.png -->

<!-- Screenshot (optional): Audio source with waveform player and timestamp segment markers -->
<!-- docs/screenshots/stage3-audio-waveform.png -->

---

## Stage 4 — Quality Estimation

COMETKiwi (`Unbabel/wmt22-cometkiwi-da`) runs reference-free QE on each confirmed segment. Per-segment scores (0–1) are stored and surfaced in the post-editing UI to triage priority segments before any human review time is spent.

<img width="1504" height="810" alt="Screenshot 2026-03-16 at 22 10 12" src="https://github.com/user-attachments/assets/a8f29940-d738-442e-acab-c7fd87dc4f82" />

<!-- Screenshot: QE scores displayed per segment, with low-confidence segments visually flagged -->
<!-- docs/screenshots/stage4-qe-scores.png -->

---

## Stage 5 — Translation & Post-Editing

Multiple MT engines run in parallel on confirmed segments. The post-editing interface shows side-by-side engine output comparison, inline translation editing, and per-segment signal confidence badges.

**Bulk Review Mode** surfaces all strings with completion tracking, signal confidence badges (`Conf: XX%`), and engine self-scores per segment.

<img width="1491" height="812" alt="Screenshot 2026-03-16 at 22 10 57" src="https://github.com/user-attachments/assets/ea3806ea-6042-44c8-ba98-a9e474072d8d" />


<!-- Screenshot: Post-editing interface with side-by-side engine comparison -->
<!-- docs/screenshots/stage5-post-editing.png -->

<!-- Screenshot: Bulk Review Mode showing confidence badges and completion progress (key screen) -->
<!-- docs/screenshots/stage5-bulk-review-confidence.png -->

<!-- Screenshot: Annotation panel with error category and severity selectors -->
<!-- docs/screenshots/stage5-annotation-panel.png -->

---

## Stage 6 — QA Metrics

Reference-based metrics (BLEU, TER, COMET, ChrF) calculated against post-edited translations. All metrics computed per-segment and aggregated per-job. All statistics (p-values, confidence intervals, correlations) computed via `scipy.stats`.


<img width="1499" height="802" alt="Screenshot 2026-03-16 at 22 11 50" src="https://github.com/user-attachments/assets/d9936708-faa1-44f6-8c3a-41c936ecfd1f" />

<!-- Screenshot: QA metrics view showing per-segment and aggregated scores -->
<!-- docs/screenshots/stage6-qa-metrics.png -->

---

## Stage 6.5 — Agentic Analysis Layer (WORK IN PROGRESS)

Runs automatically after Stage 6 completes. Checks glossary reuse, DNT compliance, TM leverage, and term consistency across segments. Findings surface in Stage 7 resource views and Stage 8 dashboards.

<!-- Screenshot: Agentic analysis findings panel -->
<!-- docs/screenshots/stage6-5-agentic-analysis.png -->

---

## Stage 7 — Resource Management

Translation Memory, Glossary, and DNT list management. All resources feed back into Stage 4 QE scoring and Stage 5 translation suggestions.

<img width="1505" height="806" alt="Screenshot 2026-03-16 at 22 12 33" src="https://github.com/user-attachments/assets/0c25fb71-be3a-4b4c-baaa-bb4c4e2effe6" />


<!-- Screenshot: Glossary management view with term pairs and AI-proposed updates -->
<!-- docs/screenshots/stage7-glossary.png -->

<!-- Screenshot (optional): Translation Memory review queue -->
<!-- docs/screenshots/stage7-tm.png -->

---

## Stage 8 — Insights Dashboards

### Model Performance

Per-language-pair leaderboard comparing MT engine scores across BLEU, TER, COMET, and ChrF.

<img width="1496" height="797" alt="Screenshot 2026-03-16 at 22 13 16" src="https://github.com/user-attachments/assets/089e5d49-c29b-4852-b171-d267b3087f6d" />

<!-- Screenshot: Model performance leaderboard with engine rows and language pair filter -->
<!-- docs/screenshots/stage8-model-leaderboard.png -->

### Post-Edit Quality Trends

<img width="1501" height="807" alt="Screenshot 2026-03-16 at 22 13 51" src="https://github.com/user-attachments/assets/31216728-5f0f-4d3c-8201-d18475057b35" />


<!-- Screenshot: Quality trends over time chart -->
<!-- docs/screenshots/stage8-quality-trends.png -->

### Evaluation Quality Tab (WORK IN PROGRESS)

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
