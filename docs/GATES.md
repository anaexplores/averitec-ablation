# GATES — what is enforced by machine in this experiment

> Added 2026-11-15, after the test-side run was complete and before the report was written.
> Mechanics adapted from `tech/funnel-v2` (`docs/GATES.md`), retargeted: those gates guard a
> product (money, access, personal data, publishing), these guard the cleanliness of an
> experiment (blindness, identical treatment, declared statistics, traceable numbers).

**Prose is a reminder, a gate is enforcement.** A gate counts as existing only if it has
been proven by injecting a violation into the very thing it guards. `--selftest` does that
for all 13 gates on a synthetic world; a gate that stays green on its own violation is
reported as BLIND and does not count.

**Fail closed.** A missing artefact is a FAIL, not a skip. A gate that crashes is a FAIL.

Runner:

```
python pipeline/gates.py                  # audit the run, exit 1 on any FAIL
python pipeline/gates.py --selftest       # prove every gate turns red
python pipeline/gates.py --only G6 G12    # subset
python pipeline/gates.py --check-links    # G10 also resolves every URL in the draft
python pipeline/gates.py --json r.json --out r.txt
```

Declarations the gates read: `data/run_registry.json` (panel, conditions, batching,
protocol events, exclusions, statistics plan, results artefacts, thresholds).
Report: `results_gates_audit.txt` / `.json`.

---

## 1. The register

| Gate | Risk it guards | What it checks | Proven red by |
|---|---|---|---|
| **G1** protocol freeze | protocol edited after seeing test data | every `amendment` pre-dates `first_test_run_utc`; every `deviation` carries a marker that is actually present in each protocol file it names | an amendment recorded after the first test-side run |
| **G2** label blindness | a judge sees the answer | no leak pattern (`LABEL:`, `GOLD`, `labels_secret`, …) and no manifest reference in any prompt; all 588 `labels_secret` entries recomputed from the source dataset and identical | one secret label in a manifest changed |
| **G3** batch identity | conditions differ in more than the manipulated variable | the same claim_ids in the same order in every condition; batch sizes as declared; total = effective n; `claims_with_text` consistent | condition C drops one claim |
| **G4** prompt template identity | instructions drift between conditions | all instruction headers identical across conditions and batches after masking the claim count (the last batch legitimately holds 16); header hash recorded | one condition's header edited |
| **G5** model identity | a silent model swap changes the panel | every cell's ledger model is in the declared panel, or is a registered deviation whose model matches the register exactly | a cell attributed to an undeclared model |
| **G6** output schema | corrupted or off-vocabulary verdicts enter the statistics | each of the 120 files parses (markdown fences stripped), length matches the manifest batch, items numbered 1..N in order, fields exactly `item`/`verdict`/`quote`, verdict inside the 4-label vocabulary, quote a non-empty string | a verdict of "Mostly True" |
| **G7** collection integrity | the collector rewrites the data | per (judge, condition): row count, uniqueness, claim_id set equal to the manifest, `side`/`condition`/`judge` fields correct, provenance marks present, and every verdict re-derived from the source array | one collected verdict changed |
| **G8** exclusion ledger | post-hoc sample cherry-picking | in **every** condition, split minus batched equals exactly the declared exclusions; effective n as declared; dropped claims' labels reported | one extra claim dropped in condition B |
| **G9** statistics conformance | undeclared tests, or a deviation without its sensitivity run | the scoring script really implements Wilson, exact McNemar and Holm; every declared comparison × every judge appears in the results file; Holm-adjusted p present; each deviation that requires a sensitivity run has a labelled sensitivity file | a declared comparison removed from the results file |
| **G10** report traceability | a number in the paper that no run produced | abstract exists and is 150-250 words; mandatory `Limitations and Dual-Use` appendix present; `preexisting` and `new sprint work` both marked; every `k/n` and `x.y%` figure in the draft found in a results file; links listed (resolved with `--check-links`) | a fabricated `199/196` inserted into the draft |
| **G11** cell isolation | cells overwrite each other, or labels sit where judges write | exactly one file per cell, named `<judge>_batchNN.json`, in the right condition directory; no unexpected artefacts; nothing named `*manifest*` or `*label*` beside the outputs; no missing cell | a stray `labels_manifest.json` dropped into an output dir |
| **G12** quote provenance | hallucinated quotes, or a session that saw another condition | every quote normalised (NFKD, quotes/dashes unified, casefolded, spaces collapsed) and searched in that item's own excerpts; a quote absent from its own condition but present in another condition's text for the same claim is **contamination and fails at any count**; global verbatim rate must clear the declared threshold; a judge below the per-judge threshold is a WARN that must be disclosed | a condition-A quote replaced with text that exists only in condition B |
| **G13** session ledger | one session reused across cells, or an unattributable cell | one ledger row per cell with judge/condition/batch/model/output/isolation/attestation; `isolation` must be `fresh-session-single-batch`; no session_id used for two cells; for cells recorded after `required_from_utc` a missing session_id is a hard FAIL | one session_id copied onto a second cell |

## 2. Audit result on the completed run (2026-11-15)

`results_gates_audit.txt`: **13 gates, 0 FAIL, 2 WARN, 11 PASS.**

Numbers the gates established rather than assumed:

- 588 secret labels recomputed from `data/train.json`, zero mismatches (G2).
- 3 conditions, one identical batch composition, 196 claims each (G3).
- 30 instruction headers, zero drift, sha256 `f948718f22f07be4` (G4).
- 120 cells, one file each, no stray artefacts (G11), all schema-conformant (G6).
- 200 split claims − 4 declared exclusions = 196, identical in all three conditions; the
  dropped claims were 3 Supported and 1 Refuted (G8). Worth stating in the paper: the
  exclusions were not label-neutral.
- 2352 quotes checked, 2297 verbatim in their own condition, **0 cross-condition
  contamination**, global rate 0.9766 (G12).
- 12 declared comparisons present, Holm applied, sensitivity run present for the one
  deviation (G9).

The two WARNs are honest gaps, not passes:

- **G13**: the 120 cells of the completed run pre-date ledger enforcement. The orchestrator
  log was not retained as a machine artefact, so `session_id` is `null` and
  `attestation: not-retained` rather than an invented identifier. Those cells are still
  audited structurally (G11) and by quote provenance (G12), which is the check that would
  actually catch a session seeing another condition's text. From
  `ledger.required_from_utc` onward a missing session_id is a FAIL.
- **G10**: the report draft does not exist yet. The gate re-runs when it does.

One judge-level caveat surfaced by G12 and carried into the paper: per-judge verbatim
quote rates are claude 0.995, gemini 0.998, gpt 0.992, **deepseek 0.922**. DeepSeek
paraphrases or truncates the deciding passage more often than the others. It is above the
0.90 disclosure threshold, so it is a WARN-level caveat, but it means DeepSeek's `quote`
field is the least reliable of the four and should not be used for quote-level analysis
without manual checking.

## 3. What the gates do NOT catch (honest list)

- **Whether the question is worth asking.** G2-G13 verify treatment and bookkeeping. No
  gate can tell you that the manipulation was too weak to matter, which is what the result
  suggests.
- **Construct validity.** G2 proves the judge never saw the gold label. It cannot prove the
  judge did not infer it from the article's own wording, which in AVeriTeC is often the
  verdict sentence itself.
- **Truthfulness of a quote that does match.** G12 proves the quote appears in the excerpts
  shown. It does not prove the passage actually decides the verdict, and it does not check
  the excerpt against the original article.
- **Intra-batch influence.** 20 claims share one session. G13 proves sessions are not
  reused across cells; it cannot detect anchoring between claims inside one batch.
- **Model identity is attested, not observed.** G5 checks the ledger against the declared
  panel. The ledger records what the orchestrator passed in the call. If a provider silently
  served something else behind one model id, no gate here would see it.
- **Timestamps.** G1 compares recorded ISO strings. A back-dated registry entry would pass.
  The git history is the only external check on ordering.
- **The statistics being the right statistics.** G9 verifies the declared tests are the ones
  implemented and reported. Whether exact McNemar with Holm is the best choice for this
  design is a judgement, not a gate.
- **Selection of what to report.** G10 ties every number in the draft to a results file. It
  cannot detect a true number omitted because it was inconvenient.
