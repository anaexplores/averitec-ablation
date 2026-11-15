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
- [x] article fetcher with Wayback-banner cleanup (smoke-tested 20/20)
- [ ] tuning-pool article fetch (dev.json, 371 articles) — running
- [ ] split file (grouped by `fact_checking_article`, stratified by label, fixed seed)
- [ ] ablation runner (conditions A/B/C)
- [ ] judge runs, statistics, report

## Data provenance

- `data/train.json` SHA-256 `AE5EDA7C42DDF1695EF185A7BA1BC716928F5ADF57103E4F78AAE5F9AFE00F9C` (10,184,813 bytes)
- `data/dev.json` SHA-256 `499793726B4A5406780928A3D9DEDC48D6DD53DE778F22437D129CACDB08E300` (1,785,475 bytes)
- Labels: `Supported` 849 / `Refuted` 1742 / `Conflicting Evidence/Cherrypicking` 195 / `Not Enough Evidence` 282 (train)
- Per-article fulltext manifest: `data/fulltext_manifest.json` (URL, status, SHA-256 of extraction, fetch date)

No personal data is involved beyond what AVeriTeC itself publishes (public claims by public
figures and fact-checking articles). No judge sees the label of any claim.
