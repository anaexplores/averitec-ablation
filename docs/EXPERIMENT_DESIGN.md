# Experiment design: retrieval-context ablation on AVeriTeC

NEW sprint work (Apart Research, AI x Epistemics sprint, 13-15 Nov 2026).
Author: Ana (GitHub `anaexploves`), solo.

This document states the design as it was actually run, including the isolation
boundaries between sessions and the points where a machine gate enforces the design
instead of relying on discipline. Gate definitions live in [GATES.md](GATES.md); the
machine-readable declarations the gates read live in `data/run_registry.json`.

---

## 1. Question

An LLM fact-check judge is usually shown retrieved windows from a fact-checking article
and asked for a verdict. Systems like `lost-caveats` (preexisting) additionally retrieve
"caveat windows": short passages carrying limiting markers (however, but, partially,
misleading) that qualify the verdict.

Does the composition of the retrieved context change the verdict?

Three conditions, differing **only** in which windows accompany the claim:

| Condition | Windows shown | Purpose |
|---|---|---|
| A | top-5 BM25 support windows, 120 words | baseline, support evidence only |
| B | A + 5 marker caveat windows, 40 words, **same article** | the `lost-caveats` behaviour |
| C | A + 5 caveat windows from a **random other article** | control: same window count and marker density, relevance broken |

C is the informative control. If B beats A, C tells us whether the gain comes from the
caveats being *relevant* or merely from adding hedging language to the context.

## 2. Data

- Source: AVeriTeC (Schlichtkrull et al.), official repository, CC BY-NC 4.0.
  Provenance and file hashes: `data/MANIFEST.json`.
- Labels are the official AVeriTeC labels. No self-labelling anywhere in this project.
- Split: `splits/split_seed20261115.json`, grouped by `fact_checking_article`,
  stratified by label, fixed seed 20261115, tuning 100 / test 200, no shared articles.
- Exclusions declared **before any judge run**: `data/unavailable_articles.json`.
  On the test side, 4 claims whose article is a JS-rendered misbar.com Wayback capture
  with no static text. Effective test n = **196** (9 batches of 20 + 1 batch of 16).
- Official AVeriTeC test labels are not public, so the "test side" is drawn from the
  official train split. The naming is ours; the labels are AVeriTeC's.

## 3. Judge panel

One model per family, all inside the OpenCode Go pool (amendment 2, recorded before any
test-side run):

| Judge id | Model | Family |
|---|---|---|
| claude-haiku-5-5 | `opencode-go/claude-haiku-5-5` | Anthropic |
| gemini-4-argon | `opencode-go/gemini-4-argon` | Google |
| gpt-6-luna | `opencode-go/gpt-6-luna` | OpenAI |
| deepseek-v4-pro | `opencode-go/deepseek-v4-pro` | DeepSeek |

Verdicts are never pooled across judges. Each judge is analysed separately.

## 4. Isolation architecture

Four kinds of actor, with non-overlapping read/write rights. The point is that no actor
that produces a verdict can see a label, and no actor that can see a label produces a
verdict.

```
                      data/train.json  (official labels)
                             |
                             v
     splits/split_seed20261115.json     data/unavailable_articles.json
                             |                       |
                             v                       v
            pipeline/judge_prompts.py  (writes, before any run)
                             |
        +--------------------+--------------------+
        v                                         v
  batchNN.txt  (judge-visible)         batches_manifest.json  (NOT judge-visible,
  claim text + excerpts only           holds claim_ids + labels_secret)
        |
        v
  JUDGE SESSION  (one fresh subagent session per cell)
  reads : exactly one batchNN.txt of exactly one condition
  writes: exactly one <judge>_batchNN.json in that condition's output dir
  model : declared explicitly in the call
  cannot see: labels, the manifest, other conditions, other judges' outputs
        |
        v
  pipeline/collect_outputs.py  -> data/judge_outputs_ablation/<cond>/<judge>.jsonl
        |
        v
  pipeline/score_ablation.py   (the only place labels and verdicts meet)
        |
        v
  results_score_test_*.txt     -> read by pipeline/gates.py and by the paper
```

### Session rules (judge cells)

1. **One cell, one fresh session.** A cell is (judge, condition, batch). 120 cells on the
   test side. No session is reused for a second cell, so no cell can inherit context from
   another condition or another judge.
2. **The model is named explicitly in every call.** A default model is a silent panel
   change.
3. **The session reads one file and writes one file.** The prompt tells it the input path
   and the output path and nothing else about the experiment.
4. **Retries start a new session.** A retried cell never continues a conversation that
   already saw the batch. (gemini B/batch07 needed three attempts after
   "Corrupted thought signature" errors; each attempt was a fresh session.)
5. **Fallbacks are deviations, not substitutions.** If the declared model cannot produce a
   cell, the fallback is recorded in `data/run_registry.json` with the reason, the model
   actually used, and the sensitivity analysis it requires. One cell in this run:
   deepseek A/batch00, after three provider content-filter blocks.
6. **Verified after the run.** `pipeline/backfill_ledger_sessions.py` matched all 120
   cells to unique succeeded sessions in the OpenCode session store (125 sessions in
   total; the 5 extras are the registered blocked attempts and retries). Identifiers are
   recorded in the ledger with `attestation: opencode-session-store`, and the single
   orchestrator session that spawned every judge session issued no verdicts itself.

### Blind mechanics

- The judge prompt contains the claim text, the excerpts and the output schema. Nothing else.
- Gold labels exist in two places only: the source dataset and `labels_secret` inside
  `batches_manifest.json`. Judge sessions never read the manifest.
- G2 recomputes all 588 secret labels from the source dataset and fails if any differs, so
  the labels used for scoring cannot be quietly edited after the run.
- Scoring is the single place where labels and verdicts are joined.

## 5. Statistics (declared in writing before any scoring began)

- Primary metric: exact-match accuracy of the 4-way verdict against the AVeriTeC label,
  per (judge, condition), with 95% Wilson intervals.
- Paired test: exact McNemar on correct/incorrect pairs.
- Declared family: {A vs B, B vs C} mandatory, {A vs C} optional. Holm correction inside
  the family. The optional comparison was declared in the same written plan, before
  wave C ran and before any scoring began, and is reported, not selected after
  seeing the data.
- Per-label breakdown reported separately, never pooled across judges.
- Minimum detectable effect: exact McNemar on n=196 paired claims needs at least 7 net
  discordant pairs to survive Holm across the two mandatory comparisons, about
  **3.6 percentage points**. Smaller true effects would not be detected here.
- For every deviation cell, comparisons involving it are reported twice: with the cell
  (labelled as mixed-model) and without it. If the two disagree, the excluded-cell result
  is primary.

## 6. Where the gates run

| Moment | Gates | Blocks |
|---|---|---|
| after prompt generation, before any judge session | G2 G3 G4 G8 | launching judges on a leaked or drifting prompt |
| after each wave of judge cells | G6 G11 G12 | scoring corrupted, misplaced or contaminated outputs |
| after collection | G7 | statistics on rows that do not match the source arrays |
| after scoring | G1 G5 G9 G13 | reporting numbers the protocol does not allow |
| before submission | G10 | a paper containing a number that is in no results file |

`python pipeline/gates.py` runs all of them and exits non-zero on any FAIL.
`python pipeline/gates.py --selftest` proves each gate turns red on its own violation.

## 7. What this design does not control

Stated plainly, because the gates cannot enforce these:

- **The labels are derivable from the text.** AVeriTeC labels come from the fact-check
  article, and the windows come from the same article. The task is therefore closer to
  "recover the verdict the fact-checker stated" than to independent fact-checking. This
  is a property of the benchmark, and it caps what any context manipulation can change.
- **Batching.** 20 claims share one session. They are independent fact-checks and the
  prompt says to judge each one on its own excerpts, but intra-session anchoring is not
  measured. A one-claim-per-session arm would settle it and was not run.
- **Window parameters.** 5 x 120 words for support, 5 x 40 words for caveats, top-k BM25.
  One setting, not a sweep. A weaker or stronger manipulation could behave differently.
- **Condition D (caveat windows only)** was declared optional and not run.
- **No confidence measure.** Only the categorical verdict is collected, which is the least
  sensitive instrument available. A small shift in hesitation would not show up.
- **Single split, single seed.** Grouped and stratified, drawn once, but n=196 claims.
