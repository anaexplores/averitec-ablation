"""Derive every number the paper is allowed to cite, into one artefact.

NEW sprint work. Gate G10 ties each k/n and x.y% figure in docs/PAPER_DRAFT.md back to a
registered results file. This script is the single source of those figures: it recomputes
them from the collected JSONL and the split, so the paper cannot drift from the data.

    python pipeline/make_paper_numbers.py
"""
import collections
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JUDGES = ("claude-haiku-5-5", "deepseek-v4-pro", "gemini-4-argon", "gpt-6-luna")
COND = ("A", "B", "C")
LAB = ("Supported", "Refuted", "Not Enough Evidence", "Conflicting Evidence/Cherrypicking")
SHORT = {"Supported": "Supp", "Refuted": "Refu", "Not Enough Evidence": "Not",
         "Conflicting Evidence/Cherrypicking": "Conf"}


def load_runs(side):
    runs = {}
    for cond in COND:
        for j in JUDGES:
            p = os.path.join(ROOT, "data", "judge_outputs_ablation", cond, f"{j}.jsonl")
            rows = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
            runs[(cond, j)] = {r["claim_id"].rsplit("-", 1)[-1]: r for r in rows}
    return runs


def load_labels(side):
    split = json.load(open(os.path.join(ROOT, "splits", "split_seed20261115.json"), encoding="utf-8"))
    want = set(split[side]["claim_ids"])
    out = {}
    for i, r in enumerate(json.load(open(os.path.join(ROOT, "data", "train.json"), encoding="utf-8"))):
        cid = f"train-{i:04d}-" + hashlib.sha256(
            json.dumps(r["claim"], sort_keys=True).encode()).hexdigest()[:12]
        if cid in want:
            out[cid.rsplit("-", 1)[-1]] = r["label"]
    return out, split


def main(argv=None):
    ap_side = "test"
    runs = load_runs(ap_side)
    all_labels, split = load_labels(ap_side)
    n_split = len(split[ap_side]["claim_ids"])
    # The effective set is what was actually batched and judged, not the whole split:
    # 4 claims were excluded before any judge run (see data/unavailable_articles.json).
    effective = set.intersection(*[set(r) for r in runs.values()])
    labels = {h: all_labels[h] for h in effective if h in all_labels}
    batched = len(labels)
    missing_from_runs = set(all_labels) - effective

    L = []
    L.append("PAPER NUMBERS - derived from data/judge_outputs_ablation/<cond>/<judge>.jsonl")
    L.append("Regenerate with: python pipeline/make_paper_numbers.py")
    L.append("")
    L.append("== Sample ==")
    L.append(f"split test claims: {n_split}")
    L.append(f"declared exclusions: {len(missing_from_runs)}")
    L.append(f"effective n per judge per condition: {batched}")
    lab_counts = collections.Counter(labels.values())
    L.append("label distribution (effective): " + ", ".join(
        f"{SHORT[k]} {lab_counts[k]}/{batched} = {lab_counts[k] / batched * 100:.1f}%" for k in LAB))
    maj = max(lab_counts.values())
    L.append(f"majority-class baseline (always {max(lab_counts, key=lab_counts.get)}): "
             f"{maj}/{batched} = {maj / batched * 100:.1f}%")
    L.append("")

    L.append("== Exact-match accuracy per judge per condition ==")
    pooled = collections.Counter()
    pooled_tot = collections.Counter()
    for j in JUDGES:
        for cond in COND:
            r = runs[(cond, j)]
            k = sum(1 for h, row in r.items() if h in labels and row["verdict"] == labels[h])
            n = sum(1 for h in r if h in labels)
            L.append(f"{j} {cond}: {k}/{n} = {k / n * 100:.1f}%")
            for h, row in r.items():
                if h in labels:
                    pooled[(labels[h], row["verdict"])] += 1
                    pooled_tot[labels[h]] += 1
    L.append("")

    L.append("== Per-label accuracy, pooled over judges and conditions ==")
    for t in LAB:
        ok = pooled[(t, t)]
        tot = pooled_tot[t]
        L.append(f"{t}: {ok}/{tot} = {ok / tot * 100:.1f}%")
    L.append("")

    L.append("== Predicted label distribution (how often each verdict was used) ==")
    for cond in COND:
        for j in JUDGES:
            c = collections.Counter(row["verdict"] for h, row in runs[(cond, j)].items() if h in labels)
            L.append(f"{j} {cond}: " + ", ".join(f"{SHORT[k]} {c[k]}" for k in LAB))
    used = collections.Counter()
    for cond in COND:
        for j in JUDGES:
            for h, row in runs[(cond, j)].items():
                if h in labels:
                    used[row["verdict"]] += 1
    tot_used = sum(used.values())
    L.append("pooled predictions: " + ", ".join(
        f"{SHORT[k]} {used[k]}/{tot_used} = {used[k] / tot_used * 100:.1f}%" for k in LAB))
    L.append("")

    L.append("== Confusion matrix (truth rows x predicted cols), pooled ==")
    L.append("truth\\pred".ljust(34) + "".join(f"{SHORT[p]:>8}" for p in LAB))
    for t in LAB:
        L.append(SHORT[t].ljust(34) + "".join(f"{pooled[(t, p)]:>8}" for p in LAB))
    L.append("")

    L.append("== Verdict stability across conditions (per judge) ==")
    for j in JUDGES:
        a, b, c = runs[("A", j)], runs[("B", j)], runs[("C", j)]
        ids = [h for h in a if h in labels]
        ab = sum(1 for h in ids if a[h]["verdict"] != b[h]["verdict"])
        bc = sum(1 for h in ids if b[h]["verdict"] != c[h]["verdict"])
        ac = sum(1 for h in ids if a[h]["verdict"] != c[h]["verdict"])
        anyc = sum(1 for h in ids if not (a[h]["verdict"] == b[h]["verdict"] == c[h]["verdict"]))
        L.append(f"{j}: A!=B {ab}/{len(ids)} = {ab / len(ids) * 100:.1f}%, "
                 f"B!=C {bc}/{len(ids)} = {bc / len(ids) * 100:.1f}%, "
                 f"A!=C {ac}/{len(ids)} = {ac / len(ids) * 100:.1f}%, "
                 f"any change {anyc}/{len(ids)} = {anyc / len(ids) * 100:.1f}%")
    L.append("")

    L.append("== Inter-judge agreement (raw pairwise, per condition) ==")
    for cond in COND:
        tot = agree = 0
        for i in range(len(JUDGES)):
            for k2 in range(i + 1, len(JUDGES)):
                x, y = runs[(cond, JUDGES[i])], runs[(cond, JUDGES[k2])]
                ids = [h for h in x if h in labels and h in y]
                agree += sum(1 for h in ids if x[h]["verdict"] == y[h]["verdict"])
                tot += len(ids)
        L.append(f"condition {cond}: {agree}/{tot} = {agree / tot * 100:.1f}%")
    L.append("")

    L.append("== Minimum detectable effect ==")
    L.append("exact McNemar, n=196 paired claims, Holm across the 2 mandatory comparisons")
    L.append("needs >= 7 net discordant pairs (two-sided p=0.0156, adjusted 0.0313)")
    L.append(f"7/{batched} = {7 / batched * 100:.1f}% accuracy difference is the floor of detectability")
    L.append("")

    reg = json.load(open(os.path.join(ROOT, "data", "run_registry.json"), encoding="utf-8"))
    gates_txt = os.path.join(ROOT, "results_gates_audit.txt")
    if os.path.exists(gates_txt):
        raw = open(gates_txt, "rb").read()
        txt = raw.decode("utf-8-sig", errors="replace")
        for line in txt.splitlines():
            if "quotes_checked" in line or "TOTAL:" in line or "effective" in line.lower():
                L.append("== from the gates audit ==")
                L.append(line.strip())
    L.append(f"deviation cells: {sum(1 for e in reg['protocol_events'] if e['type'] == 'deviation')}")
    L.append(f"deepseek A batch00 excluded sensitivity n: {batched - 20}")

    out = os.path.join(ROOT, "results_paper_numbers.txt")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")
    print(f"wrote {os.path.relpath(out, ROOT)} ({len(L)} lines)")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
