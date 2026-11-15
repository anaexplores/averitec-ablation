"""Retrieval-context ablation runner for AVeriTeC (conditions A/B/C, NEW sprint work).

The ONLY thing that varies across conditions is the composition of the retrieved context;
the claim, judge, prompt template, sampling parameters and scoring are identical.

Conditions (pre-declared in the sprint methods protocol, methods_db.json -> experiment_execution_rules):
  A  support-only          : the 5 top BM25 120-word windows for the claim
  B  support + caveat      : A plus the 5 top limiting-marker 40-word windows from the SAME article
  C  support + foreign     : A plus the 5 top limiting-marker windows from a DIFFERENT random
                             article (BM25-selected against the same claim; preserves window count
                             and marker density, breaks document relevance)

Judge input: the claim and the excerpt list. The judge must return JSON:
  {"verdict": "Supported" | "Refuted" | "Not Enough Evidence" | "Conflicting Evidence/Cherrypicking",
   "quote": "<=25 words verbatim from the excerpts"}
The judge never sees the label, the article title/URL, or which condition produced the excerpts.

Usage:
    python pipeline/ablation_runner.py --split splits/split_seed20261115.json --side test
        --conditions A B --judges openai/gpt-5.6-sol google/gemini-3.1-pro-preview
Requires OPENROUTER_API_KEY in the environment.
"""
import argparse
import hashlib
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

from windows_bm25 import MARK, bm25_top, judge_windows, windows  # preexisting retrieval code

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERDICTS = ("Supported", "Refuted", "Not Enough Evidence", "Conflicting Evidence/Cherrypicking")
PROMPT_TEMPLATE = """You are verifying a claim against fact-checking excerpts.

CLAIM: {claim}

EXCERPTS:
{excerpts}

Decide the verdict for the claim based ONLY on the excerpts above:
- "Supported": the excerpts establish the claim.
- "Refuted": the excerpts establish the claim is false.
- "Not Enough Evidence": the excerpts do not contain enough information to judge.
- "Conflicting Evidence/Cherrypicking": parts of the excerpts support and parts contradict the claim, or the excerpts give a selective picture.

Answer with JSON only, no other text:
{{"verdict": "<one of the four labels above>", "quote": "<at most 25 words copied verbatim from the excerpts that decided your verdict>"}}"""


def load_jsonl(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def append_jsonl(path, row):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_split_rows(split_path, side):
    """Map claim_ids of the requested side back to their AVeriTeC rows."""
    with open(split_path, encoding="utf-8") as f:
        split = json.load(f)
    want = set(split[side]["claim_ids"])
    source_file = os.path.join(ROOT, split[side]["source"])
    with open(source_file, encoding="utf-8") as f:
        rows = json.load(f)
    name = "dev" if "dev.json" in split[side]["source"] else "train"
    out = {}
    for i, r in enumerate(rows):
        cid = f"{name}-{i:04d}-" + hashlib.sha256(json.dumps(r["claim"], sort_keys=True).encode()).hexdigest()[:12]
        if cid in want:
            r["_id"] = cid
            out[cid] = r
    missing = want - set(out)
    if missing:
        raise SystemExit(f"{len(missing)} split ids not found in {split[side]['source']}, e.g. {sorted(missing)[:3]}")
    return split, out


def build_contexts(rows, condition, foreign_pool, rng):
    """Return {claim_id: excerpt_list} for one condition."""
    contexts = {}
    for cid, r in rows.items():
        key = hashlib.sha1(r["fact_checking_article"].encode("utf-8")).hexdigest()[:16]
        path = os.path.join(ROOT, "fulltext", f"{key}.txt")
        if not os.path.exists(path):
            contexts[cid] = None  # article not fetched yet; logged, not silently dropped
            continue
        with open(path, encoding="utf-8") as f:
            text = f.read()
        support = bm25_top(r["claim"], windows(text), 5)
        if condition == "A":
            excerpts = list(support)
        elif condition in ("B", "C"):
            if condition == "C":
                other_key = rng.choice(foreign_pool)
                while other_key == key:
                    other_key = rng.choice(foreign_pool)
                with open(os.path.join(ROOT, "fulltext", f"{other_key}.txt"), encoding="utf-8") as f:
                    text = f.read()
            marker_windows = [w for w in windows(text, 40, 20) if MARK.search(w)]
            caveats = bm25_top(r["claim"], marker_windows, 5) if marker_windows else []
            excerpts = support + caveats
        else:
            raise ValueError(f"unknown condition {condition}")
        contexts[cid] = excerpts
    return contexts


def call_openrouter(model, claim, excerpts, temperature=0.0, max_retries=4):
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise SystemExit("OPENROUTER_API_KEY is not set in the environment")
    numbered = "\n\n".join(f"[{i + 1}] {w}" for i, w in enumerate(excerpts))
    prompt = PROMPT_TEMPLATE.format(claim=claim, excerpts=numbered)
    body = {
        "model": model,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 300,
    }
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"]
            return content, resp.status
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt < max_retries - 1:
                time.sleep(2 ** attempt * 5)
                continue
            return json.dumps({"error": f"HTTP {e.code}"}), e.code
        except Exception as e:  # noqa: BLE001
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt * 5)
                continue
            return json.dumps({"error": str(e)[:200]}), None


def parse_verdict(content):
    m = re.search(r"\{.*\}", content, re.S)
    if not m:
        return {"verdict": None, "quote": None, "raw": content}
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return {"verdict": None, "quote": None, "raw": content}
    v = obj.get("verdict")
    return {"verdict": v if v in VERDICTS else None, "quote": obj.get("quote"), "raw": content}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--split", required=True)
    ap.add_argument("--side", choices=("tuning", "test"), required=True)
    ap.add_argument("--conditions", nargs="+", choices=("A", "B", "C"), default=["A", "B"])
    ap.add_argument("--judges", nargs="+", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--seed", type=int, default=0, help="seed for condition-C foreign article choice")
    args = ap.parse_args(argv)

    split, rows = load_split_rows(args.split, args.side)
    ids = sorted(rows)
    if args.limit:
        ids = ids[: args.limit]
    foreign_pool = [f for f in os.listdir(os.path.join(ROOT, "fulltext")) if f.endswith(".txt")]

    for judge in args.judges:
        for condition in args.conditions:
            rng = random.Random(args.seed if condition == "C" else 0)
            out_path = os.path.join(ROOT, "data", "judge_outputs_ablation", condition, f"{judge.replace('/', '__')}.jsonl")
            done = {r["claim_id"] for r in load_jsonl(out_path)}
            contexts = build_contexts(rows, condition, foreign_pool, rng)
            todo = [cid for cid in ids if cid not in done]
            no_text = [cid for cid in todo if contexts[cid] is None]
            print(f"judge {judge} condition {condition}: {len(todo)} to run, {len(no_text)} without fetched fulltext")
            for n, cid in enumerate(todo, 1):
                excerpts = contexts[cid]
                if excerpts is None:
                    continue
                content, status = call_openrouter(judge, rows[cid]["claim"], excerpts)
                parsed = parse_verdict(content)
                append_jsonl(out_path, {
                    "claim_id": cid,
                    "condition": condition,
                    "judge": judge,
                    "verdict": parsed["verdict"],
                    "quote": parsed["quote"],
                    "raw": parsed.get("raw"),
                    "http_status": status,
                    "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "ai_generated": True,
                    "label_hidden": True,
                })
                if n % 20 == 0 or n == len(todo):
                    print(f"  {n}/{len(todo)}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
