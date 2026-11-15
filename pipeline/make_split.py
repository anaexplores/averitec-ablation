"""Draw the AVeriTeC tuning and test splits according to the sprint methods protocol.

Protocol rules implemented (research/apart-epistemics-2026-11/methods_db.json):
  * split by GROUPS, not rows: all claims sharing one fact_checking_article stay on one side
    (a roundup article can carry up to 90 claims);
  * stratify on the label within each side, proportions matching the source pool;
  * one fixed seed, recorded in the output; the split is drawn once and never edited;
  * tuning pool comes from the official dev.json (its intended purpose), test side from the
    official train.json (whose official test counterpart is not public).

Output: splits/split_seed<SEED>.json with the seed, UTC date, the claim ids of each side,
per-side label counts and the group accounting (which articles were taken whole).

    python pipeline/make_split.py --seed 20261115 --tuning-claims 100 --test-claims 200
"""
import argparse
import hashlib
import json
import os
import random
import sys
from collections import Counter
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LABELS = ("Refuted", "Supported", "Not Enough Evidence", "Conflicting Evidence/Cherrypicking")


def claim_id(row, split_name, idx):
    digest = hashlib.sha256(json.dumps(row["claim"], sort_keys=True).encode("utf-8")).hexdigest()[:12]
    return f"{split_name}-{idx:04d}-{digest}"


def group_by_article(rows, split_name):
    """Attach ids first, then group rows by fact_checking_article, preserving ids."""
    for i, r in enumerate(rows):
        r["_id"] = claim_id(r, split_name, i)
    groups = {}
    for r in rows:
        groups.setdefault(r["fact_checking_article"], []).append(r)
    return [groups[a] for a in sorted(groups)]


def draw_side(rows, targets, rng, exclude_articles=frozenset()):
    """Greedy whole-group selection hitting per-label targets.

    Singleton articles are preferred (cleanest); multi-claim groups are added whole when
    singleton mass is insufficient. Stops as soon as every label target is reached.
    Articles in `exclude_articles` are skipped entirely (e.g. articles that also appear
    in the OTHER official AVeriTeC file would leak between tuning and test sides).
    """
    singletons = [g for g in rows if len(g) == 1 and g[0]["fact_checking_article"] not in exclude_articles]
    multis = [g for g in rows if len(g) > 1 and g[0]["fact_checking_article"] not in exclude_articles]
    rng.shuffle(singletons)
    rng.shuffle(multis)
    counts = Counter()
    chosen = []
    taken_ids = set()

    def try_add(group):
        for r in group:
            if counts[r["label"]] >= targets[r["label"]]:
                pass  # whole-group rule: group added if it does not overshoot badly

    # Phase 1: singletons per label, exact fill.
    for label in LABELS:
        need = targets[label]
        have = counts[label]
        if have >= need:
            continue
        pool = [g for g in singletons if g[0]["label"] == label and id(g) not in taken_ids]
        for g in pool:
            if counts[label] >= need:
                break
            taken_ids.add(id(g))
            chosen.append(g)
            counts[g[0]["label"]] += 1

    # Phase 2: multi-claim groups whole, until every target is met.
    for g in multis:
        if all(counts[l] >= targets[l] for l in LABELS):
            break
        overshoot = max((counts[r["label"]] + 1 - targets[r["label"]] for r in g), default=0)
        # allow a group if it overshoots any class by at most half a target class size
        max_overshoot_allowed = max(1, min(targets.values()) // 2)
        if overshoot <= max_overshoot_allowed:
            taken_ids.add(id(g))
            chosen.append(g)
            for r in g:
                counts[r["label"]] += 1

    claims = [r for g in chosen for r in g]
    return claims, counts


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--train", default=os.path.join(ROOT, "data", "train.json"))
    ap.add_argument("--dev", default=os.path.join(ROOT, "data", "dev.json"))
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--tuning-claims", type=int, default=100)
    ap.add_argument("--test-claims", type=int, default=200)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    with open(args.dev, encoding="utf-8") as f:
        dev = json.load(f)
    with open(args.train, encoding="utf-8") as f:
        train = json.load(f)
    rng = random.Random(args.seed)

    # Articles present in BOTH official files (dev.json and train.json) would leak from the
    # tuning side into the test side; they are excluded from tuning and logged.
    train_articles = {r["fact_checking_article"] for r in train}
    dev_articles = {r["fact_checking_article"] for r in dev}
    both_files = sorted(dev_articles & train_articles)

    # Tuning side: official dev.json, proportions matching dev's own label distribution.
    dev_counts = Counter(r["label"] for r in dev)
    tuning_targets = {l: round(args.tuning_claims * dev_counts[l] / len(dev)) for l in LABELS}
    tuning, tuning_counts = draw_side(group_by_article(dev, "dev"), tuning_targets, rng, exclude_articles=train_articles)

    # Test side: official train.json, proportions matching train's label distribution.
    train_counts = Counter(r["label"] for r in train)
    test_targets = {l: round(args.test_claims * train_counts[l] / len(train)) for l in LABELS}
    test, test_counts = draw_side(group_by_article(train, "train"), test_targets, rng)

    out = {
        "seed": args.seed,
        "drawn_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "protocol": "grouped by fact_checking_article; stratified by label; fixed seed; test side drawn once",
        "leakage_guard": {
            "rule": "articles present in BOTH official dev.json and train.json are excluded from the tuning side",
            "excluded_articles": both_files,
        },
        "tuning": {
            "source": "data/dev.json (official AVeriTeC dev)",
            "n_claims": len(tuning),
            "n_articles": len({r["fact_checking_article"] for r in tuning}),
            "labels": dict(sorted(tuning_counts.items())),
            "claim_ids": sorted(r["_id"] for r in tuning),
        },
        "test": {
            "source": "data/train.json (official AVeriTeC train; official test labels not public)",
            "n_claims": len(test),
            "n_articles": len({r["fact_checking_article"] for r in test}),
            "labels": dict(sorted(test_counts.items())),
            "claim_ids": sorted(r["_id"] for r in test),
        },
    }
    out_path = args.out or os.path.join(ROOT, "splits", f"split_seed{args.seed}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print(f"tuning: {out['tuning']['n_claims']} claims from {out['tuning']['n_articles']} articles {out['tuning']['labels']}")
    print(f"test:   {out['test']['n_claims']} claims from {out['test']['n_articles']} articles {out['test']['labels']}")
    print(f"written: {out_path}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
