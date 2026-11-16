"""Figure 1 for the paper: how often each verdict is true vs how often judges use it.

NEW sprint work. Reads the same collected JSONL as the statistics, so the figure cannot
disagree with the tables.

    python pipeline/make_figure.py
"""
import collections
import hashlib
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JUDGES = ("claude-haiku-5-5", "deepseek-v4-pro", "gemini-4-argon", "gpt-6-luna")
COND = ("A", "B", "C")
LAB = ("Supported", "Refuted", "Not Enough\nEvidence", "Conflicting/\nCherrypicking")
KEYS = ("Supported", "Refuted", "Not Enough Evidence", "Conflicting Evidence/Cherrypicking")


def labels_map():
    split = json.load(open(os.path.join(ROOT, "splits", "split_seed20261115.json"), encoding="utf-8"))
    want = set(split["test"]["claim_ids"])
    out = {}
    for i, r in enumerate(json.load(open(os.path.join(ROOT, "data", "train.json"), encoding="utf-8"))):
        cid = f"train-{i:04d}-" + hashlib.sha256(
            json.dumps(r["claim"], sort_keys=True).encode()).hexdigest()[:12]
        if cid in want:
            out[cid.rsplit("-", 1)[-1]] = r["label"]
    return out


def main():
    labels = labels_map()
    truth = collections.Counter()
    pred = collections.Counter()
    for cond in COND:
        for j in JUDGES:
            p = os.path.join(ROOT, "data", "judge_outputs_ablation", cond, f"{j}.jsonl")
            for line in open(p, encoding="utf-8"):
                if not line.strip():
                    continue
                r = json.loads(line)
                h = r["claim_id"].rsplit("-", 1)[-1]
                if h not in labels:
                    continue
                truth[labels[h]] += 1
                pred[r["verdict"]] += 1
    t_tot, p_tot = sum(truth.values()), sum(pred.values())

    x = range(len(LAB))
    w = 0.38
    tvals = [truth[k] / t_tot * 100 for k in KEYS]
    pvals = [pred[k] / p_tot * 100 for k in KEYS]

    fig, ax = plt.subplots(figsize=(7.0, 3.4), dpi=200)
    b1 = ax.bar([i - w / 2 for i in x], tvals, w, label="AVeriTeC gold label", color="#3b6ea5")
    b2 = ax.bar([i + w / 2 for i in x], pvals, w, label="judge verdict (pooled, 4 judges x 3 conditions)",
                color="#d98c3f")
    for bars in (b1, b2):
        for b in bars:
            ax.annotate(f"{b.get_height():.1f}%", (b.get_x() + b.get_width() / 2, b.get_height()),
                        ha="center", va="bottom", fontsize=7.5)
    ax.set_xticks(list(x))
    ax.set_xticklabels(LAB, fontsize=8.5)
    ax.set_ylabel("share (%)", fontsize=9)
    ax.set_title("Judges almost never abstain: gold labels vs verdicts actually issued",
                 fontsize=10.5)
    ax.tick_params(axis="y", labelsize=8)
    ax.legend(fontsize=8, frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()

    out_dir = os.path.join(ROOT, "docs", "figures")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "fig1_label_use.png")
    fig.savefig(out)
    print("wrote", os.path.relpath(out, ROOT))
    for k, kk in zip(LAB, KEYS):
        print(f"  {kk:36} gold {truth[kk]:5} ({truth[kk]/t_tot*100:5.1f}%)   "
              f"predicted {pred[kk]:5} ({pred[kk]/p_tot*100:5.1f}%)")


if __name__ == "__main__":
    main()
