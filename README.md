# AVeriTeC retrieval-context ablation (Apart AI x Epistemics Sprint 2026)

Does the verdict of an LLM judge checking a claim depend on WHICH windows a retriever shows it?
We run a retrieval-context ablation on the external AVeriTeC benchmark: identical judge, identical
prompt template, identical claim; only the composition of the retrieved context varies.

**Preexisting vs new work (sprint rule):**

| Component | Status |
|---|---|
| `data/train.json`, `data/dev.json` | external, AVeriTeC (MichSchli/AVeriTeC, CC BY-NC 4.0), downloaded 2026-11-15 |
| BM25 windowing approach (120-word windows stride 60, 40-word marker windows stride 20, tokens `[a-z0-9]+`, k1=1.5, b=0.75) | **preexisting**, reused from `anaexplores/lost-caveats` `pipeline/windows.py` |
| Quote-check levels L0-L3 | **preexisting** pattern from `anaexplores/lost-caveats` `pipeline/quote_check.py` |
| Wilson interval + scoring layout | **preexisting** pattern from `anaexplores/lost-caveats` `pipeline/score_judges.py` |
| HTML extraction (html.parser, drop script/style, html.unescape, CR→LF before hashing) | **preexisting** pattern from `anaexplores/lost-caveats` `fetch_fulltext.py` |
| `pipeline/fetch_articles.py`, ablation runner, split script, statistics, report | **new work done during the sprint** |

## Status

- [x] data download + manifest (data/train.json 3,068 claims, data/dev.json 500 claims)
- [x] article fetcher with Wayback-banner cleanup (throttle-safe: 1 worker, 3 s delay)
- [x] split file (grouped by `fact_checking_article`, stratified by label, seed 20261115;
      cross-file article overlap excluded from tuning, 0 shared articles between sides)
- [x] unavailable-article exclusions pre-declared BEFORE any judge run
      (data/unavailable_articles.json: 6 tuning claims, 100 -> 94, and 4 test claims,
      200 -> 196; misbar.com JS-rendered Wayback captures with no static text,
      excluded from every condition equally)
- [x] ablation runner (conditions A/B/C) + statistics (Wilson, exact McNemar, Holm)
- [x] full judge matrix: 4 judges x 3 conditions x 196 claims, one fresh isolated
      session per (judge, condition, batch), 125 sessions verified in the OpenCode
      session store; all 12 paired comparisons non-significant after Holm
      (minimum detectable effect 3.6 percentage points)
- [x] cleanliness gates: 13 machine-enforced gates + selftest, audit in
      results_gates_audit.txt
- [x] report: docs/PAPER_DRAFT.md and paper_submission.pdf; every number in the
      report regenerates via pipeline/make_paper_numbers.py

## Data provenance

- `data/train.json` SHA-256 `AE5EDA7C42DDF1695EF185A7BA1BC716928F5ADF57103E4F78AAE5F9AFE00F9C` (10,184,813 bytes)
- `data/dev.json` SHA-256 `499793726B4A5406780928A3D9DEDC48D6DD53DE778F22437D129CACDB08E300` (1,785,475 bytes)
- Labels: `Supported` 849 / `Refuted` 1742 / `Conflicting Evidence/Cherrypicking` 195 / `Not Enough Evidence` 282 (train)
- Per-article fulltext manifest: `data/fulltext_manifest.json` (URL, status, SHA-256 of extraction, fetch date)

No personal data is involved beyond what AVeriTeC itself publishes (public claims by public
figures and fact-checking articles). No judge sees the label of any claim.
