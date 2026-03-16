# Low-Resource Language Evaluation: Swahili (SW)

## Why Swahili

Swahili was chosen as the first low-resource experiment for three concrete reasons:

1. **NLLB-200 coverage** — Facebook's `nllb-200-distilled-600M` includes Swahili (`swh_Latn`), making it the only model in the current stack that can translate EN↔SW without a dedicated fine-tuned model.
2. **FLORES-200 benchmark availability** — Meta AI's FLORES-200 dataset provides 1,012 professionally translated sentence pairs for Swahili, enabling reproducible benchmarking. WMT does not have a Swahili shared task.
3. **Methodological clarity** — Swahili's known metric failure modes (agglutinative morphology, 8 noun classes) are well-documented and make it a clean case study for demonstrating where automatic MT evaluation degrades.

This is an explicit methodological choice, not a limitation. The author cannot serve as a qualified human annotator for Swahili the way they can for EN/JA/FR. This affects the evaluation design (see Annotation Approach below).

---

## Benchmark Data

**Source**: FLORES-200 devtest ([Goyal et al., 2022](https://arxiv.org/abs/2207.04672))

| Direction | NLLB tag | Sentences |
|-----------|----------|-----------|
| EN → SW   | `swh_Latn` | 10 (from 1,012 available) |
| SW → EN   | `eng_Latn` | 10 (from 1,012 available) |

The sentences were drawn from the FLORES-200 devtest split, which covers domains including science, news, and general knowledge. All references are native-speaker translations.

**Why not WMT?** WMT shared tasks have covered EN↔DE, EN↔ZH, EN↔JA, EN↔FR among others, but not Swahili. The standard benchmarking resource for low-resource and multilingual models including NLLB-200 is FLORES-200.

---

## Metric Reliability for Swahili

| Metric | Reliability | Reason |
|--------|-------------|--------|
| BLEU   | Low         | Swahili's 8 noun classes and agglutinative verb morphology produce high surface variation for semantically equivalent outputs. A morphologically correct translation of the same meaning may share few n-grams with the reference. Moses 13a tokenizer has no Swahili-specific handling. |
| TER    | Low         | Word-level edit distance is unstable for agglutinative languages where morphological variants are single tokens. A single wrong prefix inflects the whole word, producing high TER from a minor error. |
| ChrF   | Medium      | Character n-grams partially capture morphological similarity. More meaningful than BLEU for Swahili but still noisy — reference scarcity means a single reference may not cover the full space of valid outputs. |
| COMET  | Medium      | The `wmt22-cometkiwi-da` model's Swahili training data is sparse. Embeddings are less reliable than for EN/FR/JA. Treat as indicative, not authoritative. Inter-rater disagreement with LLM judge scores should be expected and documented. |

**Minimum sample recommendation**: n ≥ 30 before drawing aggregate conclusions. At current sample sizes (n < 10), individual segment inspection and LLM judge scores are more meaningful than aggregate statistics.

---

## Evaluation Approach

### Primary signal: LLM-as-judge (Gemini)

Automatic metrics are not reliable primary signals for Swahili. The LLM judge (Gemini) serves as the primary evaluation instrument for this language pair.

The judge prompt includes Swahili-specific guidance:
- Noun class concord checking (agreement between nouns and adjectives/verbs via class prefixes)
- Verb tense and aspect marker evaluation
- Confidence calibration guidance — scores of 0.5–0.7 are appropriate when morphological correctness cannot be verified without native-speaker input

### Annotation approach

The author cannot serve as a qualified human annotator for Swahili. The annotation workflow for SW differs from EN/JA/FR:

| Aspect | EN/JA/FR | SW |
|--------|----------|----|
| Human annotation | Author (native/near-native) | LLM judge primary; human review of flagged segments |
| Ground truth | Author post-edits | FLORES-200 reference only |
| Error typology | Full MQM annotation | Limited to adequacy/fluency; morphological error tagging deferred |
| Metric authority | COMET + ChrF | LLM judge |

This is explicitly documented as a methodological limitation. Results for Swahili should be interpreted with this context.

### Inter-judge consistency (planned)

Once sufficient SW evaluations exist, inter-judge agreement across Claude/GPT-4/Gemini will be tested as a proxy for evaluation validity for this language pair. High disagreement across judges signals that the pair is at the boundary of reliable LLM evaluation.

---

## Known Failure Modes

### What NLLB-200 commonly gets wrong for Swahili

1. **Noun class agreement** — NLLB frequently produces agreement errors. In Swahili, noun prefixes determine the agreement pattern for all modifiers and verbs in the sentence. A single wrong noun class prefix cascades into multiple grammatical errors that metrics may not detect.

   Example pattern: `mtoto mzuri` (good child, cl.1) vs `watoto wazuri` (good children, cl.2). NLLB may produce `watoto mzuri` (mixing classes) — grammatically wrong but hard for BLEU to penalize.

2. **Subject prefix omission** — Swahili verbs carry obligatory subject prefixes (e.g., `a-` for 3rd person singular cl.1). MT models often drop these, producing ungrammatical output.

3. **Tense/aspect markers** — Swahili encodes tense and aspect through infixes within the verb stem. NLLB conflates present and habitual, and frequently confuses the `-me-` (perfect) and `-na-` (present progressive) markers.

4. **Register collapse** — Formal and informal registers are structurally distinct in Swahili. NLLB tends to flatten to a single register regardless of source register.

### Metric failure modes

- BLEU can be near-zero for a correct translation that uses valid morphological variants not present in the single reference
- COMET scores may appear reasonable for fluent but adequacy-poor output (hallucinations in Swahili are hard for the model to detect)
- High TER can result from morphologically correct but inflectionally different outputs

---

## Implementation Notes

### Model configuration
- Engine: `nllb_multilingual` (NLLB-200 distilled 600M)
- NLLB language tag: `swh_Latn` (Swahili, Latin script)
- Source language code in DB: `SW` (added to `SourceLanguage` enum in schema migration)
- No Helsinki model available for SW pairs

### Benchmark data location
Hardcoded FLORES-200 samples in `app/api/routers/wmt_benchmarks.py` under keys `"en-sw"` and `"sw-en"`. To expand to the full 1,012-sentence FLORES-200 devtest, download from the [FLORES-200 repository](https://github.com/facebookresearch/flores) and add to this dict or load from file.

### Metric reliability
Static reliability metadata for Swahili is defined in `app/core/metric_reliability.py` under key `"sw"`. The recommended primary metric is `"LLM judge (auto metrics unreliable)"` and will appear in the Metric Reliability Notes table in the dashboard.

---

## Roadmap

- [ ] Expand FLORES-200 sample from 10 to full 1,012 devtest sentences
- [ ] Run inter-judge consistency test (Claude vs. Gemini vs. GPT-4) on 50 SW segments
- [ ] Document NLLB morphological error rate on noun class concord
- [ ] Evaluate whether COMET scores correlate with LLM judge scores at all for SW (expected: low correlation)
- [ ] Consider adding a second low-resource language (Bengali/BN) as a comparison point — different script (Bengali), similarly sparse COMET training data
