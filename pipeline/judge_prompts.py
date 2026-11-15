"""Build judge batch prompts for the AVeriTeC retrieval-context ablation (NEW sprint work).

For one (condition, side, batch) it writes a self-contained prompt file that a judge model
(OpenCode subagent session) reads and answers: a JSON array with one verdict object per claim.
The judge never sees labels, article titles or URLs, and cannot know which condition produced
the excerpts (conditions differ only in the excerpt composition).

    python pipeline/judge_prompts.py --side tuning --condition A --batch-size 20 --only 0
    # writes data/judge_prompts/tuning/A/batch00.txt ... and a manifest of claim ids per batch
"""
import argparse
import hashlib
import json
import os
import random
import sys

from windows_bm25 import MARK, bm25_top, windows  # preexisting retrieval code

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERDICTS = ("Supported", "Refuted", "Not Enough Evidence", "Conflicting Evidence/Cherrypicking")

INSTRUCTIONS = """You are verifying {n} claims against fact-checking excerpts.

For EVERY claim independently decide its verdict based ONLY on the excerpts shown with it:
- "Supported": the excerpts establish the claim.
- "Refuted": the excerpts establish the claim is false.
- "Not Enough Evidence": the excerpts do not contain enough information to judge.
- "Conflicting Evidence/Cherrypicking": parts of the excerpts support and parts contradict the claim, or the excerpts give a selective picture.

Rules:
- Treat each claim independently; do not let other claims influence a verdict.
- Every verdict must include a "quote": at most 25 words copied VERBATIM from that claim's excerpts (the passage that decided your verdict). If no passage applies, copy the closest related passage.
- If the excerpts are irrelevant or empty for a claim, answer "Not Enough Evidence" with a quote from the closest excerpt.
- Output EXACTLY one JSON array, no other text. One object per input item, same order, fields:
  {{"item": <item number>, "verdict": "<one of the four labels>", "quote": "<<=25 words verbatim>"}}
"""


def load_rows(side_file):
    rows = json.load(open(side_file, encoding="utf-8"))
    out = []
    for i, r in enumerate(rows):
        cid = f"{os.path.basename(side_file).replace('_side.json', '')}-{i:04d}-" + \
              hashlib.sha256(json.dumps(r["claim"], sort_keys=True).encode()).hexdigest()[:12]
        out.append({"claim_id": cid, "claim": r["claim"], "article": r["fact_checking_article"], "label": r["label"]})
    return out


def build_excerpts(row, condition, foreign_pool, rng):
    key = hashlib.sha1(row["article"].encode("utf-8")).hexdigest()[:16]
    path = os.path.join(ROOT, "fulltext", f"{key}.txt")
    if not os.path.exists(path):
        return None
    text = open(path, encoding="utf-8").read()
    support = bm25_top(row["claim"], windows(text), 5)
    if condition == "A":
        return support
    if condition in ("B", "C"):
        if condition == "C":
            other = rng.choice(foreign_pool)
            while other == key:
                other = rng.choice(foreign_pool)
            text = open(os.path.join(ROOT, "fulltext", f"{other}.txt"), encoding="utf-8").read()
        marker_windows = [w for w in windows(text, 40, 20) if MARK.search(w)]
        caveats = bm25_top(row["claim"], marker_windows, 5) if marker_windows else []
        return support + caveats
    raise ValueError(condition)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--side", choices=("tuning", "test"), required=True)
    ap.add_argument("--condition", choices=("A", "B", "C"), required=True)
    ap.add_argument("--batch-size", type=int, default=20)
    ap.add_argument("--only", type=int, default=-1, help="build just this batch index")
    ap.add_argument("--seed", type=int, default=20261115)
    ap.add_argument("--available-only", action="store_true",
                    help="skip claims whose article has no fetched fulltext (reads data/unavailable_articles.json)")
    args = ap.parse_args(argv)

    rows = load_rows(os.path.join(ROOT, "data", f"{args.side}_side.json"))
    if args.available_only:
        excl = json.load(open(os.path.join(ROOT, "data", "unavailable_articles.json"), encoding="utf-8"))
        excluded_ids = {e["claim_id"] for e in excl["excluded_claims"]}
        rows = [r for r in rows if r["claim_id"] not in excluded_ids]

    foreign_pool = [f[:-4] for f in os.listdir(os.path.join(ROOT, "fulltext")) if f.endswith(".txt")]
    rng = random.Random(args.seed if args.condition == "C" else 0)

    have = []
    for r in rows:
        ex = build_excerpts(r, args.condition, foreign_pool, rng)
        if ex:
            have.append((r, ex))
    missing = len(rows) - len(have)

    batches = [have[i:i + args.batch_size] for i in range(0, len(have), args.batch_size)]
    out_dir = os.path.join(ROOT, "data", "judge_prompts", args.side, args.condition)
    os.makedirs(out_dir, exist_ok=True)
    manifest = []
    for bi, batch in enumerate(batches):
        if args.only >= 0 and bi != args.only:
            continue
        parts = [INSTRUCTIONS.format(n=len(batch))]
        for i, (r, ex) in enumerate(batch, 1):
            numbered = "\n".join(f"  [{j + 1}] {w}" for j, w in enumerate(ex))
            parts.append(f"\n=== ITEM {i} (claim_id {r['claim_id']}) ===\nCLAIM: {r['claim']}\nEXCERPTS:\n{numbered}")
        prompt = "".join(parts)
        path = os.path.join(out_dir, f"batch{bi:02d}.txt")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(prompt)
        manifest.append({"batch": bi, "file": os.path.relpath(path, ROOT).replace("\\", "/"),
                         "claim_ids": [r["claim_id"] for r, _ in batch],
                         "labels_secret": [r["label"] for r, _ in batch],
                         "chars": len(prompt)})
    man_path = os.path.join(out_dir, "batches_manifest.json")
    with open(man_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"side": args.side, "condition": args.condition, "seed": args.seed,
                   "batch_size": args.batch_size, "claims_with_text": len(have),
                   "claims_missing_text": missing, "batches": manifest}, f, indent=1)
    print(f"{args.side}/{args.condition}: {len(have)} claims with excerpts ({missing} missing), "
          f"{len(manifest)} batch file(s) written; labels listed in batches_manifest.json (judge never sees them)")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
