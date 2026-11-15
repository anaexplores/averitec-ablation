"""Score the retrieval-context ablation runs (conditions x judges) on AVeriTeC.

NEW sprint work. Statistics follow the pre-declared plan (sprint methods protocol):
  * primary metric: exact-match accuracy of the 4-way verdict against the AVeriTeC label,
    per (judge, condition), with 95% Wilson intervals (Brown/Cai/DasGupta: not Wald);
  * paired test: exact McNemar on correct/incorrect pairs for the comparison family
    {A vs B, B vs C} (+ optional A vs C, A vs D), Holm-corrected within the family;
  * per-label breakdown (Supported / Refuted / Not Enough Evidence / Conflicting Evidence
    /Cherrypicking) reported separately, never pooled across judges.

    python pipeline/score_ablation.py --split splits/split_seed20261115.json --side test
    python pipeline/score_ablation.py ... --family A_vs_B B_vs_C A_vs_C
"""
import argparse
import glob
import json
import math
import os
import sys
from collections import Counter
from itertools import combinations

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LABELS = ("Supported", "Refuted", "Not Enough Evidence", "Conflicting Evidence/Cherrypicking")


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def mcnemar_exact(b, c):
    """Exact two-sided McNemar p-value for discordant counts b, c."""
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(0, min(b, c) + 1)) * (0.5 ** n)
    return min(1.0, 2 * tail)


def holm(pvals):
    """Holm-Bonferroni adjusted p-values, order preserved."""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    adjusted = [None] * m
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvals[i]))
        adjusted[i] = running
    return adjusted


def score_file(path, side):
    rows = load_jsonl(path)
    verdict = {r["claim_id"].rsplit("-", 1)[-1]: r.get("verdict")
               for r in rows if r.get("side") == side and r.get("verdict")}
    batch = {r["claim_id"].rsplit("-", 1)[-1]: r.get("batch")
             for r in rows if r.get("side") == side}
    cond = rows[0]["condition"] if rows else "?"
    judge = rows[0]["judge"] if rows else "?"
    return cond, judge, verdict, batch


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--outputs", default=os.path.join(ROOT, "data", "judge_outputs_ablation"))
    ap.add_argument("--split", required=True)
    ap.add_argument("--side", choices=("tuning", "test"), required=True)
    ap.add_argument("--family", nargs="+", required=True,
                    help="comparison family, e.g. A_vs_B B_vs_C (Holm applied within this list)")
    ap.add_argument("--exclude", nargs="*", default=[],
                    help="sensitivity analysis: exclude a judge batch cell, e.g. "
                         "deepseek-v4-pro,A,0 (repeatable entries); a note is printed")
    args = ap.parse_args(argv)

    with open(args.split, encoding="utf-8") as f:
        split = json.load(f)
    want = set(split[args.side]["claim_ids"])
    label_of = {}
    id_of = {}
    name = "dev" if "dev.json" in split[args.side]["source"] else "train"
    src = split[args.side]["source"].split(" (")[0]
    with open(os.path.join(ROOT, src), encoding="utf-8") as f:
        for i, r in enumerate(json.load(f)):
            cid = f"{name}-{i:04d}-" + __import__("hashlib").sha256(
                json.dumps(r["claim"], sort_keys=True).encode()).hexdigest()[:12]
            if cid in want:
                # Claim ids differ between the split (train-/dev- prefixed) and the
                # batch manifests (test-/tuning- prefixed) but share the same 12-char
                # hash suffix; match on the hash so the sides stay linkable.
                label_of[cid.rsplit("-", 1)[-1]] = r["label"]
                id_of[cid.rsplit("-", 1)[-1]] = cid

    # Load one file per (condition, judge).
    runs = {}
    for path in sorted(glob.glob(os.path.join(args.outputs, "*", "*.jsonl"))):
        cond, judge, verdict, batch = score_file(path, args.side)
        for ex in args.exclude:
            ej, ec, eb = ex.rsplit(",", 2)[0], ex.rsplit(",", 2)[1], int(ex.rsplit(",", 2)[2])
            if judge == ej and cond == ec:
                verdict = {c: v for c, v in verdict.items() if batch.get(c) != eb}
        runs[(cond, judge)] = verdict

    conditions = sorted({c for c, _ in runs})
    judges = sorted({j for _, j in runs})

    print(f"side {args.side}, {len(label_of)} claims with labels")
    if args.exclude:
        print(f"SENSITIVITY RUN: excluded cells {args.exclude} (deviation protocol)")
    print()
    print(f"{'judge':38} {'cond':5} {'exact-match acc':26} per-label correct/total")
    for judge in judges:
        for cond in conditions:
            verdict = runs.get((cond, judge))
            if verdict is None:
                continue
            scored = {cid: (v == label_of[cid]) for cid, v in verdict.items() if cid in label_of and v}
            k, n = sum(scored.values()), len(scored)
            lo, hi = wilson(k, n)
            per = {}
            for lb in LABELS:
                ids = [c for c in scored if label_of[c] == lb]
                per[lb] = f"{sum(scored[c] for c in ids)}/{len(ids)}"
            print(f"{judge:38} {cond:5} {f'{k}/{n} [{lo:.2f},{hi:.2f}]':26} "
                  + " ".join(f"{lb.split(' ')[0][:4]}:{per[lb]}" for lb in LABELS))
        verdictless = [id_of[c] for c in label_of
                       if not any(c in runs.get((cd, judge), {}) for cd in conditions)]
        if verdictless:
            print(f"{judge:38} -- missing verdicts for {len(verdictless)} claims (e.g. {verdictless[:3]})")

    # Paired comparisons: exact McNemar on correct/incorrect, Holm within --family.
    print("\nPaired McNemar (correct vs incorrect), Holm-corrected within the declared family")
    fam_p, fam_desc = [], []
    for comp in args.family:
        try:
            ca, cb = comp.split("_vs_")
        except ValueError:
            raise SystemExit(f"family entry must look like A_vs_B, got {comp}")
        pvals, desc = [], []
        for judge in judges:
            va, vb = runs.get((ca, judge)), runs.get((cb, judge))
            if not va or not vb:
                continue
            common = [c for c in label_of if va.get(c) and vb.get(c)]
            b = sum(1 for c in common if (va[c] == label_of[c]) and (vb[c] != label_of[c]))
            c_ = sum(1 for c in common if (va[c] != label_of[c]) and (vb[c] == label_of[c]))
            p = mcnemar_exact(b, c_)
            pvals.append(p)
            desc.append(f"{judge} {ca} vs {cb}: b={b} c={c_} (n discordant={b + c_}, paired n={len(common)}) p={p:.4f}")
        adj = holm(pvals)
        for d, a in zip(desc, adj):
            print(f"  {d}  -> Holm adj p={a:.4f}")
        fam_p.append(adj)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
