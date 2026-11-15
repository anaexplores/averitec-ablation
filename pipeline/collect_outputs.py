"""Collect judge batch outputs into the JSONL layout score_ablation.py expects.

NEW sprint work. Judge sessions write one JSON array per (side, condition, judge, batch):
    data/judge_outputs_ablation/test/A/<judge>_batchNN.json
The manifest data/judge_prompts/<side>/<condition>/batches_manifest.json maps each batch
file to its claim_ids in order. This script cross-checks every array against the manifest
(item count, item numbering) and writes:
    data/judge_outputs_ablation/<condition>/<judge>.jsonl
one row per claim: {claim_id, condition, judge, verdict, quote, batch, ai_generated: true}.

    python pipeline/collect_outputs.py --side test
"""
import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_ROOT = os.path.join(ROOT, "data", "judge_outputs_ablation")


def collect_side_condition(side, condition, judge_dirs):
    man_path = os.path.join(ROOT, "data", "judge_prompts", side, condition, "batches_manifest.json")
    with open(man_path, encoding="utf-8") as f:
        man = json.load(f)
    for batch in man["batches"]:
        batch_idx = batch["batch"]
        for judge_dir, judges in judge_dirs.items():
            for fname in judges:
                m = re.match(rf"(.+)_batch{batch_idx:02d}\.json$", fname)
                if not m:
                    continue
                judge = m.group(1)
                with open(os.path.join(judge_dir, fname), encoding="utf-8") as f:
                    arr = json.load(f)
                ids = batch["claim_ids"]
                if len(arr) != len(ids):
                    print(f"  WARN {side}/{condition} {judge} batch{batch_idx:02d}: {len(arr)} verdicts for {len(ids)} claims")
                    continue
                out_dir = os.path.join(OUT_ROOT, condition)
                os.makedirs(out_dir, exist_ok=True)
                out_path = os.path.join(out_dir, f"{judge}.jsonl")
                rows = [json.loads(l) for l in open(out_path, encoding="utf-8").read().splitlines() if l.strip()] \
                    if os.path.exists(out_path) else []
                have = {r["claim_id"] for r in rows}
                for verdict_obj, cid in zip(arr, ids):
                    if cid in have:
                        continue
                    rows.append({
                        "claim_id": cid,
                        "condition": condition,
                        "judge": judge,
                        "verdict": verdict_obj.get("verdict"),
                        "quote": verdict_obj.get("quote"),
                        "batch": batch_idx,
                        "side": side,
                        "ai_generated": True,
                        "label_hidden": True,
                    })
                with open(out_path, "w", encoding="utf-8", newline="\n") as f:
                    for r in rows:
                        f.write(json.dumps(r, ensure_ascii=False) + "\n")
                print(f"  {side}/{condition} {judge} batch{batch_idx:02d}: +{len(arr)} rows -> {len(rows)} total")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--side", choices=("tuning", "test"), required=True)
    args = ap.parse_args(argv)
    for condition in ("A", "B", "C"):
        cond_dir = os.path.join(OUT_ROOT, args.side, condition)
        if not os.path.isdir(cond_dir):
            continue
        judge_dirs = {cond_dir: os.listdir(cond_dir)}
        collect_side_condition(args.side, condition, judge_dirs)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
