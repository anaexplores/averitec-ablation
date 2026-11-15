"""Cleanliness gates for the AVeriTeC retrieval-context ablation.

NEW sprint work. Mechanics adapted from tech/funnel-v2 (docs/GATES.md):
  * prose is a reminder, a gate is enforcement;
  * a gate counts as existing only if it has been proven by injecting a violation
    into the very thing it guards (`--selftest`);
  * gates fail closed: a missing artefact is a FAIL, not a skip;
  * there is an honest list of what the gates do NOT catch (docs/GATES.md section 5).

Unlike funnel-v2 these gates protect the cleanliness of an experiment, not a product:
label blindness, identical batching, model identity, schema integrity, declared
exclusions, declared statistics, quote provenance, session isolation.

    python pipeline/gates.py                 # audit the real run
    python pipeline/gates.py --selftest      # prove every gate turns red
    python pipeline/gates.py --json out.json # machine-readable report
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import unicodedata
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LABELS = ("Supported", "Refuted", "Not Enough Evidence", "Conflicting Evidence/Cherrypicking")
PASS, FAIL, WARN = "PASS", "FAIL", "WARN"


# --------------------------------------------------------------------------- helpers

class Gate:
    def __init__(self, name: str, title: str):
        self.name = name
        self.title = title
        self.status = PASS
        self.details: list[str] = []
        self.metrics: dict = {}

    def fail(self, msg: str):
        self.status = FAIL
        self.details.append(f"FAIL: {msg}")

    def warn(self, msg: str):
        if self.status != FAIL:
            self.status = WARN
        self.details.append(f"WARN: {msg}")

    def note(self, msg: str):
        self.details.append(msg)

    def as_dict(self):
        return {"gate": self.name, "title": self.title, "status": self.status,
                "metrics": self.metrics, "details": self.details}


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def read_text(path: str) -> str:
    """Read a text artefact written either by Python (UTF-8) or by PowerShell Tee-Object (UTF-16 LE BOM)."""
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "utf-16", "cp1251"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def norm(s: str) -> str:
    """Normalise for verbatim-quote matching: NFKD, unify quotes/dashes, casefold, collapse spaces."""
    s = unicodedata.normalize("NFKD", s)
    for a, b in (("\u2018", "'"), ("\u2019", "'"), ("\u201c", '"'), ("\u201d", '"'),
                 ("\u2013", "-"), ("\u2014", "-"), ("\u00a0", " ")):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip().casefold()


def strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        t = t.rsplit("```", 1)[0]
    return t.strip()


def read_output_array(path):
    return json.loads(strip_fences(open(path, encoding="utf-8-sig").read()))


ITEM_RE = re.compile(r"=== ITEM (\d+) \(claim_id ([^)]+)\) ===")


def parse_prompt(path: str) -> dict:
    """Split a batch prompt into its header and per-item blocks."""
    text = open(path, encoding="utf-8").read()
    marks = [(m.start(), int(m.group(1)), m.group(2)) for m in ITEM_RE.finditer(text)]
    if not marks:
        return {"header": text, "items": {}}
    header = text[: marks[0][0]]
    items = {}
    for i, (start, no, cid) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        items[no] = {"claim_id": cid, "block": text[start:end]}
    return {"header": header, "items": items}


def side_source_name(reg, split, side):
    src = split[side]["source"]
    return ("dev" if "dev.json" in src else "train"), src.split(" (")[0]


def official_labels(root, reg, split, side):
    """Recompute {hash_suffix: label} straight from the source dataset."""
    name, rel = side_source_name(reg, split, side)
    want = set(split[side]["claim_ids"])
    out = {}
    for i, r in enumerate(load_json(os.path.join(root, rel))):
        cid = f"{name}-{i:04d}-" + hashlib.sha256(
            json.dumps(r["claim"], sort_keys=True).encode()).hexdigest()[:12]
        if cid in want:
            out[cid.rsplit("-", 1)[-1]] = r["label"]
    return out


def manifests(root, reg, side):
    return {c: load_json(os.path.join(root, "data", "judge_prompts", side, c, "batches_manifest.json"))
            for c in reg["conditions"]}


def cells(root, reg, side):
    """Yield (judge, condition, batch_idx, manifest_batch, output_path)."""
    for cond in reg["conditions"]:
        man = load_json(os.path.join(root, "data", "judge_prompts", side, cond, "batches_manifest.json"))
        d = os.path.join(root, "data", "judge_outputs_ablation", side, cond)
        for b in man["batches"]:
            for judge in reg["panel"]:
                yield judge, cond, b["batch"], b, os.path.join(d, f"{judge}_batch{b['batch']:02d}.json")


# --------------------------------------------------------------------------- gates

def g1_protocol_freeze(root, reg, side):
    g = Gate("G1", "Protocol freeze: amendments only before the first test-side run; deviations recorded in the protocol")
    first = reg.get("first_test_run_utc")
    if not first:
        g.fail("registry has no first_test_run_utc")
        return g
    amend_after = [e for e in reg["protocol_events"]
                   if e["type"] == "amendment" and e["recorded_utc"] > first]
    for e in amend_after:
        g.fail(f"amendment '{e['id']}' recorded {e['recorded_utc']} AFTER first test run {first}")
    devs = [e for e in reg["protocol_events"] if e["type"] == "deviation"]
    g.metrics = {"amendments": sum(1 for e in reg["protocol_events"] if e["type"] == "amendment"),
                 "deviations": len(devs), "first_test_run_utc": first}
    for e in devs:
        markers = e.get("protocol_markers") or {}
        if not markers:
            single = e.get("protocol_marker")
            markers = {pf: single for pf in reg["protocol_files"]} if single else {}
        if not markers:
            g.fail(f"deviation '{e['id']}' has no protocol_markers to verify")
            continue
        for pf, marker in markers.items():
            if not os.path.exists(pf):
                g.fail(f"protocol file missing: {pf}")
                continue
            if marker not in read_text(pf):
                g.fail(f"deviation '{e['id']}' marker '{marker}' not found in {pf}")
        for pf in reg["protocol_files"]:
            if pf not in markers:
                g.warn(f"deviation '{e['id']}' has no marker declared for {pf}")
    if g.status == PASS:
        g.note(f"{g.metrics['amendments']} amendment(s) all pre-date the first test run; "
               f"{len(devs)} deviation(s) carry a marker present in every protocol file they declare")
    return g


def g2_label_blind(root, reg, side):
    g = Gate("G2", "Label blindness: judges never see gold labels; secret labels match the source dataset")
    split = load_json(os.path.join(root, "splits", reg["split_file"]))
    official = official_labels(root, reg, split, side)
    leak_pat = re.compile(r"\b(LABEL|GOLD|CORRECT ANSWER|GROUND TRUTH|labels_secret)\s*[:=]", re.I)
    checked = mismatched = leaked = 0
    for cond in reg["conditions"]:
        man = load_json(os.path.join(root, "data", "judge_prompts", side, cond, "batches_manifest.json"))
        for b in man["batches"]:
            prompt_path = os.path.join(root, "data", "judge_prompts", side, cond, f"batch{b['batch']:02d}.txt")
            p = parse_prompt(prompt_path)
            raw = open(prompt_path, encoding="utf-8").read()
            if leak_pat.search(raw):
                g.fail(f"{cond}/batch{b['batch']:02d}: prompt contains a label-leak pattern")
                leaked += 1
            if "batches_manifest" in raw:
                g.fail(f"{cond}/batch{b['batch']:02d}: prompt references the manifest (labels live there)")
                leaked += 1
            secret = b.get("labels_secret") or []
            if len(secret) != len(b["claim_ids"]):
                g.fail(f"{cond}/batch{b['batch']:02d}: labels_secret length {len(secret)} != {len(b['claim_ids'])}")
            for cid, lab in zip(b["claim_ids"], secret):
                h = cid.rsplit("-", 1)[-1]
                checked += 1
                if h in official and official[h] != lab:
                    g.fail(f"{cond}/batch{b['batch']:02d} {cid}: secret label '{lab}' != official '{official[h]}'")
                    mismatched += 1
    g.metrics = {"labels_checked": checked, "label_mismatches": mismatched, "leak_hits": leaked}
    if g.status == PASS:
        g.note(f"{checked} secret labels recomputed from the source dataset, all identical; no leak pattern in any prompt")
    return g


def g3_batch_identity(root, reg, side):
    g = Gate("G3", "Batch identity: the same claims in the same order in every condition")
    mans = manifests(root, reg, side)
    ref = None
    total = None
    for cond, man in mans.items():
        ids = [tuple(b["claim_ids"]) for b in man["batches"]]
        sizes = [len(b["claim_ids"]) for b in man["batches"]]
        n = sum(sizes)
        if total is None:
            total = n
        if n != reg["batching"]["effective_n"]:
            g.fail(f"{cond}: {n} claims in batches, registry declares {reg['batching']['effective_n']}")
        if man.get("claims_with_text") != n:
            g.fail(f"{cond}: manifest claims_with_text={man.get('claims_with_text')} != {n} batched")
        bs = reg["batching"]["batch_size"]
        for i, s in enumerate(sizes[:-1]):
            if s != bs:
                g.fail(f"{cond}/batch{i:02d}: size {s} != declared {bs}")
        if sizes and sizes[-1] != reg["batching"]["last_batch_size"]:
            g.fail(f"{cond}/batch{len(sizes)-1:02d}: last size {sizes[-1]} != declared {reg['batching']['last_batch_size']}")
        if ref is None:
            ref = (cond, ids)
        elif ids != ref[1]:
            g.fail(f"{cond}: batch composition differs from {ref[0]} (conditions must differ ONLY in context)")
    g.metrics = {"conditions": len(mans), "claims_per_condition": total}
    if g.status == PASS:
        g.note(f"{len(mans)} conditions share one identical batch composition of {total} claims")
    return g


def _canon_header(h: str) -> str:
    """Mask the claim count: the last batch legitimately holds fewer claims, and that
    number appears in the instruction line. Everything else must be byte-identical."""
    h = re.sub(r"verifying\s+\d+\s+claims", "verifying N claims", h)
    return re.sub(r"\b\d+\s+claims\b", "N claims", h)


def g4_prompt_template_identity(root, reg, side):
    g = Gate("G4", "Prompt template identity: instructions identical across conditions and batches (claim count masked)")
    headers = {}
    for cond in reg["conditions"]:
        man = load_json(os.path.join(root, "data", "judge_prompts", side, cond, "batches_manifest.json"))
        for b in man["batches"]:
            path = os.path.join(root, "data", "judge_prompts", side, cond, f"batch{b['batch']:02d}.txt")
            headers[(cond, b["batch"])] = _canon_header(parse_prompt(path)["header"])
    ref_key = min(headers)
    ref = headers[ref_key]
    drift = [k for k, v in headers.items() if v != ref]
    for k in drift:
        g.fail(f"{k[0]}/batch{k[1]:02d} instruction header differs from {ref_key[0]}/batch{ref_key[1]:02d}")
    g.metrics = {"headers_compared": len(headers), "drifted": len(drift),
                 "header_sha256": hashlib.sha256(ref.encode()).hexdigest()[:16]}
    if g.status == PASS:
        g.note(f"{len(headers)} instruction headers compared, all identical after masking the claim count "
               f"(sha256 {g.metrics['header_sha256']})")
    return g


def g5_model_identity(root, reg, side):
    g = Gate("G5", "Model identity: every cell produced by a declared panel model, or by a registered deviation")
    ledger_path = os.path.join(root, reg["ledger"]["file"])
    declared = set(reg["panel"].values())
    dev_cells = {(e["cell"]["judge"], e["cell"]["condition"], e["cell"]["batch"]): e
                 for e in reg["protocol_events"] if e["type"] == "deviation" and "cell" in e}
    if not os.path.exists(ledger_path):
        g.fail(f"session ledger missing: {ledger_path}")
        return g
    rows = load_jsonl(ledger_path)
    by_cell = {(r["judge"], r["condition"], r["batch"]): r for r in rows}
    n_dev = n_undeclared = 0
    for judge, cond, bi, _b, _p in cells(root, reg, side):
        r = by_cell.get((judge, cond, bi))
        if r is None:
            g.fail(f"no ledger entry for cell {judge}/{cond}/batch{bi:02d}")
            continue
        used = r.get("model_used")
        if (judge, cond, bi) in dev_cells:
            n_dev += 1
            expect = dev_cells[(judge, cond, bi)]["model_used"]
            if used != expect:
                g.fail(f"cell {judge}/{cond}/batch{bi:02d}: ledger model '{used}' != registered deviation model '{expect}'")
            continue
        if used not in declared:
            g.fail(f"cell {judge}/{cond}/batch{bi:02d}: model '{used}' is not in the declared panel and has no deviation entry")
            n_undeclared += 1
    g.metrics = {"cells": sum(1 for _ in cells(root, reg, side)), "deviation_cells": n_dev,
                 "undeclared_models": n_undeclared}
    if g.status == PASS:
        g.note(f"{g.metrics['cells']} cells checked; {n_dev} registered deviation cell(s); no undeclared model")
    return g


def g6_output_schema(root, reg, side):
    g = Gate("G6", "Output schema: every judge file is a well-formed array in the declared label vocabulary")
    bad_files = 0
    n_files = 0
    for judge, cond, bi, b, path in cells(root, reg, side):
        n_files += 1
        if not os.path.exists(path):
            g.fail(f"missing output file {os.path.relpath(path, root)}")
            bad_files += 1
            continue
        try:
            arr = read_output_array(path)
        except Exception as e:
            g.fail(f"{judge}/{cond}/batch{bi:02d}: unparsable JSON ({e})")
            bad_files += 1
            continue
        if not isinstance(arr, list):
            g.fail(f"{judge}/{cond}/batch{bi:02d}: not a JSON array")
            bad_files += 1
            continue
        if len(arr) != len(b["claim_ids"]):
            g.fail(f"{judge}/{cond}/batch{bi:02d}: {len(arr)} verdicts for {len(b['claim_ids'])} claims")
            bad_files += 1
        if [o.get("item") for o in arr] != list(range(1, len(arr) + 1)):
            g.fail(f"{judge}/{cond}/batch{bi:02d}: item numbering is not 1..{len(arr)} in order")
            bad_files += 1
        for o in arr:
            if not isinstance(o, dict) or not {"item", "verdict", "quote"} <= set(o):
                g.fail(f"{judge}/{cond}/batch{bi:02d} item {o.get('item')}: missing required field")
                bad_files += 1
                break
            if o.get("verdict") not in LABELS:
                g.fail(f"{judge}/{cond}/batch{bi:02d} item {o.get('item')}: verdict '{o.get('verdict')}' outside vocabulary")
                bad_files += 1
                break
            q = o.get("quote")
            if not isinstance(q, str) or not q.strip():
                g.fail(f"{judge}/{cond}/batch{bi:02d} item {o.get('item')}: empty or non-string quote")
                bad_files += 1
                break
    g.metrics = {"files_checked": n_files, "files_with_problems": bad_files}
    if g.status == PASS:
        g.note(f"{n_files} output files parsed; item numbering, field set and label vocabulary all conform")
    return g


def g7_collection_integrity(root, reg, side):
    g = Gate("G7", "Collection integrity: JSONL rows are exactly the manifest claims, verdicts unchanged")
    for cond in reg["conditions"]:
        man = load_json(os.path.join(root, "data", "judge_prompts", side, cond, "batches_manifest.json"))
        want = [cid for b in man["batches"] for cid in b["claim_ids"]]
        for judge in reg["panel"]:
            p = os.path.join(root, "data", "judge_outputs_ablation", cond, f"{judge}.jsonl")
            if not os.path.exists(p):
                g.fail(f"missing collected file data/judge_outputs_ablation/{cond}/{judge}.jsonl")
                continue
            rows = load_jsonl(p)
            got = [r["claim_id"] for r in rows]
            if len(got) != len(want):
                g.fail(f"{cond}/{judge}: {len(got)} rows, expected {len(want)}")
            if len(set(got)) != len(got):
                g.fail(f"{cond}/{judge}: duplicate claim_ids in JSONL")
            if set(got) != set(want):
                g.fail(f"{cond}/{judge}: claim_id set differs from the manifest")
            for r in rows:
                if r.get("side") != side or r.get("condition") != cond or r.get("judge") != judge:
                    g.fail(f"{cond}/{judge}: row {r.get('claim_id')} has wrong side/condition/judge fields")
                    break
                if r.get("label_hidden") is not True or r.get("ai_generated") is not True:
                    g.fail(f"{cond}/{judge}: row {r.get('claim_id')} lacks the provenance marks")
                    break
            # verdicts must equal the source arrays
            src = {}
            for b in man["batches"]:
                fp = os.path.join(root, "data", "judge_outputs_ablation", side, cond,
                                  f"{judge}_batch{b['batch']:02d}.json")
                if not os.path.exists(fp):
                    continue
                for o, cid in zip(read_output_array(fp), b["claim_ids"]):
                    src[cid] = o.get("verdict")
            diff = [r["claim_id"] for r in rows if src.get(r["claim_id"]) and r["verdict"] != src[r["claim_id"]]]
            if diff:
                g.fail(f"{cond}/{judge}: {len(diff)} verdict(s) differ from the source files (e.g. {diff[:3]})")
    g.metrics = {"pairs_checked": len(reg["conditions"]) * len(reg["panel"])}
    if g.status == PASS:
        g.note(f"{g.metrics['pairs_checked']} (judge, condition) files re-derived from the source arrays, all identical")
    return g


def g8_exclusion_ledger(root, reg, side):
    g = Gate("G8", "Exclusion ledger: in EVERY condition the dropped claims are exactly the pre-declared ones")
    exc = load_json(os.path.join(root, reg["exclusions"]["file"]))
    split = load_json(os.path.join(root, "splits", reg["split_file"]))
    official = official_labels(root, reg, split, side)
    official_ids = set(split[side]["claim_ids"])
    official_h = {i.rsplit("-", 1)[-1] for i in official_ids}
    exc_hashes = {e["claim_id"].rsplit("-", 1)[-1] for e in exc["excluded_claims"]
                  if e["claim_id"].rsplit("-", 1)[-1] in official_h}
    if len(exc_hashes) != reg["exclusions"]["expected_excluded"]:
        g.fail(f"registry declares {reg['exclusions']['expected_excluded']} exclusions, "
               f"{len(exc_hashes)} of them are on this side")
    per_cond = {}
    for cond in reg["conditions"]:
        man = load_json(os.path.join(root, "data", "judge_prompts", side, cond, "batches_manifest.json"))
        batched = {cid for b in man["batches"] for cid in b["claim_ids"]}
        batched_h = {c.rsplit("-", 1)[-1] for c in batched}
        per_cond[cond] = len(batched_h)
        dropped_h = official_h - batched_h
        if dropped_h != exc_hashes:
            g.fail(f"{cond}: dropped {sorted(dropped_h)} != declared exclusions {sorted(exc_hashes)}")
        if len(batched_h) != reg["exclusions"]["effective_n_after"]:
            g.fail(f"{cond}: effective n={len(batched_h)}, registry declares {reg['exclusions']['effective_n_after']}")
        if batched - official_ids and not {b.rsplit('-', 1)[-1] for b in batched} <= official_h:
            g.fail(f"{cond}: batched claims outside the split")
    g.metrics = {"split_n": len(official_h), "declared_exclusions": len(exc_hashes),
                 "effective_n_per_condition": per_cond,
                 "labels_of_dropped": sorted(official[h] for h in (official_h - exc_hashes ^ official_h)
                                             if h in official)}
    g.metrics["labels_of_dropped"] = sorted(official[h] for h in exc_hashes if h in official)
    if g.status == PASS:
        g.note(f"{len(official_h)} split claims - {len(exc_hashes)} declared exclusions = "
               f"{reg['exclusions']['effective_n_after']} effective, identical in every condition; "
               f"labels of the dropped claims: {g.metrics['labels_of_dropped']}")
    return g


def g9_stats_conformance(root, reg, side):
    g = Gate("G9", "Statistics conformance: only the declared family, declared tests, declared sensitivity runs")
    script = os.path.join(root, "pipeline", "score_ablation.py")
    if not os.path.exists(script):
        g.fail("pipeline/score_ablation.py missing")
        return g
    src = read_text(script)
    for fn, why in (("def wilson", "Wilson interval"), ("def mcnemar_exact", "exact McNemar"),
                    ("def holm", "Holm correction")):
        if fn not in src:
            g.fail(f"scoring script has no {why} ({fn})")
    plan = reg["statistics_plan"]
    main_path = os.path.join(root, reg["results_files"]["main"])
    if not os.path.exists(main_path):
        g.fail(f"main results file missing: {main_path}")
        return g
    main = read_text(main_path)
    for comp in plan["family"]:
        a, b = comp.split("_vs_")
        for judge in reg["panel"]:
            if f"{judge} {a} vs {b}:" not in main:
                g.fail(f"main results missing declared comparison {judge} {a} vs {b}")
    if "Holm adj p" not in main:
        g.fail("main results show no Holm-adjusted p-values")
    for e in reg["protocol_events"]:
        if e["type"] == "deviation" and e.get("requires_sensitivity_run"):
            key = reg["results_files"].get("deepseek_excluded")
            if not key:
                g.fail(f"deviation '{e['id']}' requires a sensitivity run but the registry names no results file")
                continue
            p = os.path.join(root, key)
            if not os.path.exists(p):
                g.fail(f"sensitivity results file missing for '{e['id']}': {p}")
                continue
            txt = read_text(p)
            if "SENSITIVITY RUN" not in txt:
                g.fail(f"{key} is not labelled as a sensitivity run")
            c = e["cell"]
            if f"{c['judge']} {c['condition']} vs" not in txt and f"{c['judge']}" not in txt:
                g.fail(f"sensitivity file does not cover judge {c['judge']}")
    g.metrics = {"family": plan["family"], "comparisons_required": len(plan["family"]) * len(reg["panel"])}
    if g.status == PASS:
        g.note(f"all {g.metrics['comparisons_required']} declared comparisons present, Holm applied, "
               f"sensitivity run present for every deviation that requires one")
    return g


def g10_report_traceability(root, reg, side, check_links=False):
    g = Gate("G10", "Report traceability: every number in the draft comes from a results file; required parts present")
    rep = reg["report"]
    draft = os.path.join(root, rep["draft"])
    if not os.path.exists(draft):
        g.warn(f"report draft not written yet ({rep['draft']}); gate re-runs once it exists")
        return g
    text = read_text(draft)
    m = re.search(r"(?ims)^#+\s*abstract\s*$(.*?)(?=^#+\s|\Z)", text)
    if not m:
        g.fail("no Abstract section found")
    else:
        words = len(re.findall(r"\S+", re.sub(r"[*_`#>]", " ", m.group(1))))
        g.metrics["abstract_words"] = words
        if not (rep["abstract_words_min"] <= words <= rep["abstract_words_max"]):
            g.fail(f"abstract is {words} words, allowed {rep['abstract_words_min']}-{rep['abstract_words_max']}")
    if rep["required_appendix_heading"].lower() not in text.lower():
        g.fail(f"mandatory appendix heading '{rep['required_appendix_heading']}' not found")
    for k in ("preexisting", "new sprint work"):
        if k.lower() not in text.lower():
            g.fail(f"report does not mark '{k}' (sprint rule: undisclosed prior work = disqualification)")
    known = ""
    for key, rel in reg["results_files"].items():
        p = os.path.join(root, rel)
        if os.path.exists(p):
            known += read_text(p)
    nums = set(re.findall(r"\b\d{1,3}/\d{2,4}\b|\b\d{1,3}\.\d%\b", text))
    unknown = sorted(n for n in nums if n not in known)
    g.metrics["numbers_in_draft"] = len(nums)
    if unknown:
        g.fail(f"{len(unknown)} number(s) in the draft are not in any results file: {unknown[:8]}")
    links = sorted(set(re.findall(r"https?://[^\s)>\]\"']+", text)))
    g.metrics["links"] = len(links)
    if check_links:
        import urllib.request
        for u in links:
            try:
                req = urllib.request.Request(u, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
                urllib.request.urlopen(req, timeout=15).read(0)
            except Exception as e:
                g.fail(f"link does not resolve: {u} ({e})")
    else:
        g.warn(f"{len(links)} link(s) not checked (pass --check-links); submission checklist requires working links")
    if g.status == PASS:
        g.note("abstract length, mandatory appendix, preexisting/new marking and every numeric claim verified against results files")
    return g


def g11_cell_isolation(root, reg, side):
    g = Gate("G11", "Cell isolation: exactly one output file per cell, correctly named, no label artefacts beside outputs")
    expected = {}
    for judge, cond, bi, _b, path in cells(root, reg, side):
        expected.setdefault((cond, os.path.basename(path)), 0)
        expected[(cond, os.path.basename(path))] += 1
    for cond in reg["conditions"]:
        d = os.path.join(root, "data", "judge_outputs_ablation", side, cond)
        if not os.path.isdir(d):
            g.fail(f"output directory missing for condition {cond}")
            continue
        names = sorted(os.listdir(d))
        for n in names:
            if not n.endswith(".json"):
                g.fail(f"{cond}: unexpected non-JSON artefact beside judge outputs: {n}")
                continue
            if "manifest" in n.lower() or "label" in n.lower():
                g.fail(f"{cond}: label-bearing artefact '{n}' sits where judge sessions write")
            m = re.match(r"(.+)_batch(\d{2})\.json$", n)
            if not m:
                g.fail(f"{cond}: file '{n}' does not match <judge>_batchNN.json")
                continue
            judge, bi = m.group(1), int(m.group(2))
            if judge not in reg["panel"]:
                g.fail(f"{cond}: '{n}' is not from a declared panel judge")
            if expected.get((cond, n), 0) != 1:
                g.fail(f"{cond}: cell {judge}/batch{bi:02d} expected once, found {expected.get((cond, n), 0)}")
        want = {f"{j}_batch{b:02d}.json" for j in reg["panel"] for b in range(len(
            load_json(os.path.join(root, 'data', 'judge_prompts', side, cond, 'batches_manifest.json'))['batches']))}
        missing = sorted(want - set(names))
        if missing:
            g.fail(f"{cond}: {len(missing)} cell file(s) missing (e.g. {missing[:3]})")
    g.metrics = {"expected_cells": len(expected)}
    if g.status == PASS:
        g.note(f"{len(expected)} cells, one file each, naming and placement conform, no label artefacts in output dirs")
    return g


def g12_quote_provenance(root, reg, side):
    g = Gate("G12", "Quote provenance: quotes verbatim from that condition's own excerpts; zero tolerance for cross-condition bleed")
    cfg = reg["quote_provenance"]
    prompts = {}
    for cond in reg["conditions"]:
        man = load_json(os.path.join(root, "data", "judge_prompts", side, cond, "batches_manifest.json"))
        for b in man["batches"]:
            p = parse_prompt(os.path.join(root, "data", "judge_prompts", side, cond, f"batch{b['batch']:02d}.txt"))
            for no, it in p["items"].items():
                prompts[(cond, b["batch"], no)] = norm(it["block"])
    total = matched = unmatched = contaminated = 0
    per_judge = {j: [0, 0] for j in reg["panel"]}  # judge -> [matched, total]
    worst = []
    for judge, cond, bi, b, path in cells(root, reg, side):
        if not os.path.exists(path):
            continue
        for o in read_output_array(path):
            no = o.get("item")
            q = norm(str(o.get("quote", "")))
            if not q:
                continue
            total += 1
            per_judge[judge][1] += 1
            if q in prompts.get((cond, bi, no), ""):
                matched += 1
                per_judge[judge][0] += 1
                continue
            others = [c for c in reg["conditions"] if c != cond and q in prompts.get((c, bi, no), "")]
            if others and cfg.get("contamination_zero_tolerance"):
                contaminated += 1
                g.fail(f"{judge}/{cond}/batch{bi:02d} item {no}: quote absent from {cond} but present in "
                       f"{others} - that session saw another condition's context")
            else:
                unmatched += 1
                if len(worst) < 8:
                    worst.append(f"{judge}/{cond}/batch{bi:02d} item {no}")
    rate = matched / total if total else 0.0
    g.metrics = {"quotes_checked": total, "verbatim_in_own_condition": matched,
                 "unmatched_anywhere": unmatched, "cross_condition_contamination": contaminated,
                 "global_match_rate": round(rate, 4),
                 "per_judge_match_rate": {j: round(v[0] / v[1], 4) for j, v in per_judge.items() if v[1]}}
    if contaminated:
        g.metrics["verdict"] = "CONTAMINATION"
    elif rate < cfg["min_global_match_rate"]:
        g.fail(f"global verbatim match rate {rate:.4f} < {cfg['min_global_match_rate']}")
    for j, v in per_judge.items():
        if not v[1]:
            continue
        jr = v[0] / v[1]
        if jr < cfg["min_judge_match_rate"]:
            g.warn(f"{j}: verbatim match rate {jr:.3f} < {cfg['min_judge_match_rate']} "
                   f"({v[1] - v[0]} paraphrased quotes) - disclose in the paper as a data-quality caveat")
    if g.status == PASS:
        g.note(f"{matched}/{total} quotes verbatim in their own condition's excerpts, "
               f"cross-condition contamination {contaminated}")
    elif unmatched and contaminated == 0:
        g.note(f"unmatched (paraphrased, not contaminated) examples: {worst}")
    return g


def g13_session_ledger(root, reg, side):
    g = Gate("G13", "Session ledger: one fresh isolated session per cell, recorded; enforced for cells after required_from")
    p = os.path.join(root, reg["ledger"]["file"])
    if not os.path.exists(p):
        g.fail(f"ledger missing: {p}")
        return g
    rows = load_jsonl(p)
    by_cell = {(r["judge"], r["condition"], r["batch"]): r for r in rows}
    req_from = reg["ledger"]["required_from_utc"]
    n_cells = not_retained = missing = enforced_fail = 0
    sids = {}
    for judge, cond, bi, _b, _path in cells(root, reg, side):
        n_cells += 1
        r = by_cell.get((judge, cond, bi))
        if r is None:
            g.fail(f"no ledger entry for {judge}/{cond}/batch{bi:02d}")
            missing += 1
            continue
        sid = r.get("session_id")
        if sid:
            sids.setdefault(sid, []).append((judge, cond, bi))
        rec = r.get("recorded_utc", "")
        if rec >= req_from and not sid:
            g.fail(f"{judge}/{cond}/batch{bi:02d}: recorded after {req_from} but has no session_id")
            enforced_fail += 1
        elif not sid:
            not_retained += 1
        for f in ("judge", "condition", "batch", "model_used", "output_file", "isolation", "attestation"):
            if f not in r:
                g.fail(f"{judge}/{cond}/batch{bi:02d}: ledger entry lacks field '{f}'")
                break
        if r.get("isolation") != "fresh-session-single-batch":
            g.fail(f"{judge}/{cond}/batch{bi:02d}: isolation='{r.get('isolation')}' is not the declared fresh-session-single-batch")
    reused = {k: v for k, v in sids.items() if len(v) > 1}
    if reused:
        for sid, cs in list(reused.items())[:5]:
            g.fail(f"session {sid} was reused for {len(cs)} cells ({cs[:3]}) - sessions must not be shared between cells")
    g.metrics = {"cells": n_cells, "ledger_rows": len(rows), "unique_sessions": len(sids),
                 "reused_sessions": len(reused), "session_id_not_retained": not_retained,
                 "missing_entries": missing}
    if not_retained and g.status != FAIL:
        g.warn(f"{not_retained} cell(s) pre-date ledger enforcement ({req_from}); their session ids are marked "
               f"not-retained rather than invented. Structural isolation (G11) and quote provenance (G12) still audit them.")
    if g.status == PASS:
        g.note(f"{len(sids)} unique sessions for {n_cells} cells, no session reused across cells")
    return g


ALL_GATES = [g1_protocol_freeze, g2_label_blind, g3_batch_identity, g4_prompt_template_identity,
             g5_model_identity, g6_output_schema, g7_collection_integrity, g8_exclusion_ledger,
             g9_stats_conformance, g11_cell_isolation, g12_quote_provenance, g13_session_ledger]


def run_all(root, side=None, check_links=False, only=None):
    reg = load_json(os.path.join(root, "data", "run_registry.json"))
    side = side or reg["side"]
    reg.setdefault("split_file", os.path.basename(
        next(f for f in os.listdir(os.path.join(root, "splits")) if f.endswith(".json"))))
    out = []
    for fn in ALL_GATES:
        try:
            g = fn(root, reg, side, check_links) if fn is g10_report_traceability else fn(root, reg, side)
        except Exception as e:
            g = Gate(fn.__name__, "gate crashed")
            g.fail(f"gate raised {type(e).__name__}: {e}")
        out.append(g)
    try:
        out.append(g10_report_traceability(root, reg, side, check_links))
    except Exception as e:
        g = Gate("G10", "gate crashed")
        g.fail(f"gate raised {type(e).__name__}: {e}")
        out.append(g)
    if only:
        out = [g for g in out if g.name in only]
    return reg, side, out


def render(reg, side, gates):
    lines = [f"CLEANLINESS GATES - side '{side}', run registry data/run_registry.json",
             f"generated {datetime.now(timezone.utc).isoformat(timespec='seconds')}", ""]
    for g in gates:
        lines.append(f"[{g.status:4}] {g.name} {g.title}")
        for d in g.details:
            lines.append(f"        {d}")
        if g.metrics:
            lines.append(f"        metrics: {json.dumps(g.metrics, ensure_ascii=False)}")
    n_fail = sum(1 for g in gates if g.status == FAIL)
    n_warn = sum(1 for g in gates if g.status == WARN)
    lines += ["", f"TOTAL: {len(gates)} gates, {n_fail} FAIL, {n_warn} WARN, "
                  f"{len(gates) - n_fail - n_warn} PASS",
              "A FAIL blocks the claim that the run is clean: fix the artefact or record a deviation in the registry."]
    return "\n".join(lines)


# --------------------------------------------------------------------------- selftest

def _build_world(tmp):
    """A minimal synthetic repo that passes every gate; used to prove each gate turns red."""
    os.makedirs(os.path.join(tmp, "splits"), exist_ok=True)
    for c in ("A", "B", "C"):
        os.makedirs(os.path.join(tmp, "data", "judge_prompts", "test", c), exist_ok=True)
        os.makedirs(os.path.join(tmp, "data", "judge_outputs_ablation", "test", c), exist_ok=True)
        os.makedirs(os.path.join(tmp, "data", "judge_outputs_ablation", c), exist_ok=True)
    os.makedirs(os.path.join(tmp, "pipeline"), exist_ok=True)
    os.makedirs(os.path.join(tmp, "docs"), exist_ok=True)

    judges = ["judge-x", "judge-y"]
    claims = [{"claim": {"text": "the sky is blue"}, "label": "Supported"},
              {"claim": {"text": "water is dry"}, "label": "Refuted"}]
    with open(os.path.join(tmp, "data", "train.json"), "w", encoding="utf-8") as f:
        json.dump(claims, f)
    hashes = [hashlib.sha256(json.dumps(c["claim"], sort_keys=True).encode()).hexdigest()[:12] for c in claims]
    split_ids = [f"train-{i:04d}-{h}" for i, h in enumerate(hashes)]
    man_ids = [f"test-{i:04d}-{h}" for i, h in enumerate(hashes)]
    with open(os.path.join(tmp, "splits", "split_seed1.json"), "w", encoding="utf-8") as f:
        json.dump({"seed": 1, "test": {"source": "data/train.json (official AVeriTeC train)",
                                       "claim_ids": split_ids, "n_claims": 2}}, f)
    with open(os.path.join(tmp, "data", "unavailable_articles.json"), "w", encoding="utf-8") as f:
        json.dump({"created": "2026-11-15", "excluded_claims": []}, f)

    header = ("You are verifying 2 claims against fact-checking excerpts.\n\n"
              "Rules:\n- Treat each claim independently.\n- Output EXACTLY one JSON array.\n\n")
    caveat = {"A": "", "B": "CAVEAT WINDOW from the same article. ", "C": "CAVEAT WINDOW from another article. "}
    for c in ("A", "B", "C"):
        body = ""
        for i, (cid, cl) in enumerate(zip(man_ids, claims), start=1):
            body += (f"=== ITEM {i} (claim_id {cid}) ===\n"
                     f"CLAIM: {cl['claim']['text']}\n"
                     f"EXCERPTS:\n"
                     f"  [1] excerpt one for {cid} says the ruling is {cl['label']} by the fact-checker. {caveat[c]}\n"
                     f"  [2] excerpt two for {cid} adds context.\n")
        with open(os.path.join(tmp, "data", "judge_prompts", "test", c, "batch00.txt"), "w", encoding="utf-8") as f:
            f.write(header + body)
        with open(os.path.join(tmp, "data", "judge_prompts", "test", c, "batches_manifest.json"), "w", encoding="utf-8") as f:
            json.dump({"side": "test", "condition": c, "seed": 1, "batch_size": 2,
                       "claims_with_text": 2, "claims_missing_text": 0,
                       "batches": [{"batch": 0, "file": f"data/judge_prompts/test/{c}/batch00.txt",
                                    "claim_ids": man_ids, "labels_secret": [cl["label"] for cl in claims],
                                    "chars": 100}]}, f)

    ledger = []
    for c in ("A", "B", "C"):
        for j in judges:
            arr = [{"item": i + 1, "verdict": cl["label"],
                    "quote": f"excerpt one for {cid} says the ruling is {cl['label']}"}
                   for i, (cid, cl) in enumerate(zip(man_ids, claims))]
            with open(os.path.join(tmp, "data", "judge_outputs_ablation", "test", c, f"{j}_batch00.json"),
                      "w", encoding="utf-8") as f:
                json.dump(arr, f)
            with open(os.path.join(tmp, "data", "judge_outputs_ablation", c, f"{j}.jsonl"), "w",
                      encoding="utf-8", newline="\n") as f:
                for cid, o in zip(man_ids, arr):
                    f.write(json.dumps({"claim_id": cid, "condition": c, "judge": j, "verdict": o["verdict"],
                                        "quote": o["quote"], "batch": 0, "side": "test",
                                        "ai_generated": True, "label_hidden": True}) + "\n")
            for i in range(len(judges)):
                pass
    for c in ("A", "B", "C"):
        for j in judges:
            ledger.append({"judge": j, "condition": c, "batch": 0,
                           "model_used": f"opencode-go/{j}", "model_declared": f"opencode-go/{j}",
                           "output_file": f"data/judge_outputs_ablation/test/{c}/{j}_batch00.json",
                           "session_id": f"ses_{j}_{c}_00", "isolation": "fresh-session-single-batch",
                           "attestation": "synthetic-selftest", "recorded_utc": "2026-11-15T10:00:00+00:00"})
    with open(os.path.join(tmp, "data", "session_ledger.jsonl"), "w", encoding="utf-8", newline="\n") as f:
        for r in ledger:
            f.write(json.dumps(r) + "\n")

    with open(os.path.join(tmp, "pipeline", "score_ablation.py"), "w", encoding="utf-8") as f:
        f.write("def wilson(k, n): pass\ndef mcnemar_exact(b, c): pass\ndef holm(p): pass\n")

    fam = ["A_vs_B", "B_vs_C", "A_vs_C"]
    main = "side test, 2 claims with labels\n"
    for j in judges:
        for c in ("A", "B", "C"):
            main += f"{j:20} {c:5} 2/2 [0.34,1.00]\n"
    main += "\nPaired McNemar\n"
    for comp in fam:
        a, b = comp.split("_vs_")
        for j in judges:
            main += f"  {j} {a} vs {b}: b=0 c=0 p=1.0000  -> Holm adj p=1.0000\n"
    with open(os.path.join(tmp, "results_score_test_main.txt"), "w", encoding="utf-8") as f:
        f.write(main)

    reg = {
        "side": "test", "conditions": ["A", "B", "C"],
        "panel": {j: f"opencode-go/{j}" for j in judges},
        "label_vocabulary": list(LABELS),
        "batching": {"batch_size": 2, "n_batches": 1, "last_batch_size": 2, "effective_n": 2},
        "exclusions": {"file": "data/unavailable_articles.json", "expected_excluded": 0,
                       "effective_n_after": 2},
        "split_file": "split_seed1.json",
        "first_test_run_utc": "2026-11-15T12:00:00+00:00",
        "protocol_events": [{"type": "amendment", "id": "a1", "recorded_utc": "2026-11-15T10:00:00+00:00",
                             "summary": "x"}],
        "protocol_files": [os.path.join(tmp, "docs", "protocol.md")],
        "statistics_plan": {"family": fam, "mandatory": ["A_vs_B", "B_vs_C"]},
        "results_files": {"main": "results_score_test_main.txt"},
        "quote_provenance": {"min_global_match_rate": 0.95, "min_judge_match_rate": 0.9,
                             "contamination_zero_tolerance": True},
        "ledger": {"file": "data/session_ledger.jsonl", "required_from_utc": "2026-11-20T00:00:00+00:00"},
        "report": {"draft": "docs/PAPER_DRAFT.md", "abstract_words_min": 3, "abstract_words_max": 500,
                   "required_appendix_heading": "Limitations and Dual-Use", "max_pages_before_refs": 8},
    }
    with open(os.path.join(tmp, "data", "run_registry.json"), "w", encoding="utf-8") as f:
        json.dump(reg, f)
    with open(os.path.join(tmp, "docs", "protocol.md"), "w", encoding="utf-8") as f:
        f.write("# protocol\nno deviations.\n")
    with open(os.path.join(tmp, "docs", "PAPER_DRAFT.md"), "w", encoding="utf-8") as f:
        f.write("# Title\n\n## Abstract\nWe report a null result. Preexisting code is marked. "
                "New sprint work is marked.\n\n## Limitations and Dual-Use / Ethical Considerations\nx\n")
    return reg


def _run_gate(tmp, gate_fn):
    reg, side, gates = run_all(tmp, "test")
    return next(g for g in gates if g.name == gate_fn.name.split("_", 1)[0].upper()
                or g.name == getattr(gate_fn, "gate_name", None)) if False else None


def _status_of(tmp, name):
    _reg, _side, gates = run_all(tmp, "test")
    return next((g.status for g in gates if g.name == name), "ABSENT")


SELFTEST_CASES = [
    ("G1", "amendment recorded after the first test-side run",
     lambda t: _patch_registry(t, lambda r: r["protocol_events"].append(
         {"type": "amendment", "id": "late", "recorded_utc": "2026-11-16T00:00:00+00:00", "summary": "x"}))),
    ("G2", "a secret label in the manifest differs from the source dataset",
     lambda t: _patch_manifest(t, "A", lambda m: m["batches"][0]["labels_secret"].__setitem__(0, "Not Enough Evidence"))),
    ("G3", "condition C drops a claim, so batching is no longer identical",
     lambda t: _patch_manifest(t, "C", lambda m: m["batches"][0]["claim_ids"].pop())),
    ("G4", "instruction header edited in one condition only",
     lambda t: _patch_prompt(t, "B", lambda s: s.replace("Treat each claim independently.",
                                                         "Treat each claim independently and prefer Refuted."))),
    ("G5", "a cell is attributed to a model outside the declared panel",
     lambda t: _patch_ledger(t, lambda r: r.__setitem__(2, dict(r[2], model_used="opencode-go/some-other-model")))),
    ("G6", "a verdict outside the label vocabulary",
     lambda t: _patch_output(t, "A", "judge-x", lambda a: a[0].__setitem__("verdict", "Mostly True"))),
    ("G7", "a collected verdict differs from its source file",
     lambda t: _patch_jsonl(t, "A", "judge-x", lambda r: r.__setitem__(0, dict(r[0], verdict="Not Enough Evidence")))),
    ("G8", "an extra claim is dropped without a declared exclusion",
     lambda t: _patch_manifest(t, "B", lambda m: m["batches"][0]["claim_ids"].pop())),
    ("G9", "a declared comparison is missing from the results file",
     lambda t: _patch_text(t, "results_score_test_main.txt",
                           lambda s: s.replace("judge-y A vs B:", "judge-y A vs Z:"))),
    ("G10", "a number in the draft appears in no results file",
     lambda t: _patch_text(t, "docs/PAPER_DRAFT.md", lambda s: s.replace("null result.", "null result, 199/196 correct."))),
    ("G11", "a stray label-bearing artefact beside the judge outputs",
     lambda t: _write(t, os.path.join("data", "judge_outputs_ablation", "test", "A", "labels_manifest.json"), "{}")),
    ("G12", "a quote lifted from another condition's excerpts",
     lambda t: _patch_output(t, "A", "judge-x", lambda a: a[0].__setitem__(
         "quote", "CAVEAT WINDOW from the same article."))),
    ("G13", "one session reused for two cells",
     lambda t: _patch_ledger(t, lambda r: r.__setitem__(1, dict(r[1], session_id=r[0]["session_id"])))),
]


def _patch_registry(tmp, fn):
    p = os.path.join(tmp, "data", "run_registry.json")
    r = load_json(p)
    fn(r)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(r, f)


def _patch_manifest(tmp, cond, fn):
    p = os.path.join(tmp, "data", "judge_prompts", "test", cond, "batches_manifest.json")
    m = load_json(p)
    fn(m)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(m, f)


def _patch_prompt(tmp, cond, fn):
    p = os.path.join(tmp, "data", "judge_prompts", "test", cond, "batch00.txt")
    s = open(p, encoding="utf-8").read()
    open(p, "w", encoding="utf-8").write(fn(s))


def _patch_output(tmp, cond, judge, fn):
    p = os.path.join(tmp, "data", "judge_outputs_ablation", "test", cond, f"{judge}_batch00.json")
    a = load_json(p)
    fn(a)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(a, f)


def _patch_jsonl(tmp, cond, judge, fn):
    p = os.path.join(tmp, "data", "judge_outputs_ablation", cond, f"{judge}.jsonl")
    rows = load_jsonl(p)
    fn(rows)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def _patch_ledger(tmp, fn):
    p = os.path.join(tmp, "data", "session_ledger.jsonl")
    rows = load_jsonl(p)
    fn(rows)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def _patch_text(tmp, rel, fn):
    p = os.path.join(tmp, rel)
    open(p, "w", encoding="utf-8").write(fn(open(p, encoding="utf-8").read()))


def _write(tmp, rel, text):
    p = os.path.join(tmp, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8").write(text)


def selftest():
    base = tempfile.mkdtemp(prefix="gates-world-")
    try:
        _build_world(base)
        clean = _status_of_all(base)
        print("synthetic world, expected PASS (WARN allowed where a gate needs an explicit flag):")
        bad = [k for k, v in clean.items() if v == FAIL]
        for k, v in sorted(clean.items()):
            print(f"  {k:4} {v}")
        if bad:
            print(f"SELFTEST BROKEN: the clean world already fails {bad}")
            return 1
        print("\ninjected violations, each gate must turn red:")
        failed = []
        for name, what, inject in SELFTEST_CASES:
            tmp = tempfile.mkdtemp(prefix="gates-case-")
            shutil.copytree(base, tmp, dirs_exist_ok=True)
            inject(tmp)
            st = _status_of(tmp, name)
            ok = st == FAIL
            print(f"  {name:4} {'RED  ' if ok else 'BLIND'} {what} -> {st}")
            if not ok:
                failed.append((name, what, st))
            shutil.rmtree(tmp, ignore_errors=True)
        print()
        if failed:
            print(f"BLIND GATES: {len(failed)} - a gate that does not turn red on its own violation does not exist")
            for f in failed:
                print(f"  {f[0]}: {f[1]} (got {f[2]})")
            return 1
        print(f"all {len(SELFTEST_CASES)} gates proven red on their own violation")
        return 0
    finally:
        shutil.rmtree(base, ignore_errors=True)


def _status_of_all(tmp):
    _reg, _side, gates = run_all(tmp, "test")
    return {g.name: g.status for g in gates}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=ROOT)
    ap.add_argument("--side")
    ap.add_argument("--json", help="write the machine-readable report here")
    ap.add_argument("--out", help="write the human-readable report here")
    ap.add_argument("--check-links", action="store_true")
    ap.add_argument("--only", nargs="*", help="run only these gates, e.g. G6 G12")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    reg, side, gates = run_all(args.root, args.side, args.check_links, args.only)
    text = render(reg, side, gates)
    print(text)
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(text + "\n")
    if args.json:
        with open(args.json, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"side": side, "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                       "gates": [g.as_dict() for g in gates]}, f, ensure_ascii=False, indent=1)
    return 1 if any(g.status == FAIL for g in gates) else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
