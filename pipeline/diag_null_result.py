"""Ad-hoc diagnostics for the ablation results (not part of the pre-declared stats plan).

NEW sprint work, written after the runs to interpret the null result honestly.
"""
import collections
import hashlib
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JUDGES = ("claude-haiku-5-5", "deepseek-v4-pro", "gemini-4-argon", "gpt-6-luna")
COND = ("A", "B", "C")
LAB = ("Supported", "Refuted", "Not Enough Evidence", "Conflicting Evidence/Cherrypicking")

runs = {}
for cond in COND:
    for j in JUDGES:
        p = os.path.join(ROOT, "data", "judge_outputs_ablation", cond, f"{j}.jsonl")
        rows = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
        runs[(cond, j)] = {r["claim_id"].rsplit("-", 1)[-1]: r["verdict"] for r in rows}

split = json.load(open(os.path.join(ROOT, "splits", "split_seed20261115.json"), encoding="utf-8"))
want = set(split["test"]["claim_ids"])
labels = {}
train = json.load(open(os.path.join(ROOT, "data", "train.json"), encoding="utf-8"))
for i, r in enumerate(train):
    cid = f"train-{i:04d}-" + hashlib.sha256(
        json.dumps(r["claim"], sort_keys=True).encode()).hexdigest()[:12]
    if cid in want:
        labels[cid.rsplit("-", 1)[-1]] = r["label"]

print("=== 1. How often the verdict changes between conditions (per judge) ===")
for j in JUDGES:
    a, b, c = runs[("A", j)], runs[("B", j)], runs[("C", j)]
    ids = sorted(a)
    ch_ab = sum(1 for i in ids if a[i] != b[i])
    ch_bc = sum(1 for i in ids if b[i] != c[i])
    ch_ac = sum(1 for i in ids if a[i] != c[i])
    ch_any = sum(1 for i in ids if not (a[i] == b[i] == c[i]))
    print(f"{j:22} A!=B:{ch_ab:3}  B!=C:{ch_bc:3}  A!=C:{ch_ac:3}  any-change:{ch_any:3} of {len(ids)}")

print("\n=== 2. Inter-judge agreement per condition (raw pairwise %) ===")
for cond in COND:
    tot = agree = 0
    for i in range(len(JUDGES)):
        for k in range(i + 1, len(JUDGES)):
            x, y = runs[(cond, JUDGES[i])], runs[(cond, JUDGES[k])]
            ids = sorted(x)
            agree += sum(1 for q in ids if x[q] == y[q])
            tot += len(ids)
    print(f"cond {cond}: {agree / tot:.3f}")

print("\n=== 3. Pooled confusion matrix (truth rows x predicted cols) ===")
cm = collections.Counter()
for cond in COND:
    for j in JUDGES:
        for h, v in runs[(cond, j)].items():
            if h in labels:
                cm[(labels[h], v)] += 1
hdr = "truth\\pred".ljust(38) + "".join(f"{l[:10]:>12}" for l in LAB)
print(hdr)
for t in LAB:
    print(t.ljust(38) + "".join(f"{cm[(t, p)]:>12}" for p in LAB))

print("\n=== 4. Accuracy per label, pooled over judges and conditions ===")
for t in LAB:
    tot = sum(cm[(t, p)] for p in LAB)
    ok = cm[(t, t)]
    print(f"{t:38} {ok}/{tot} = {ok / tot:.3f}")

print("\n=== 5. Power: what effect size could we have seen? ===")
# exact McNemar two-sided; Holm across 2 mandatory comparisons -> need p<=0.025
print("min net discordant pairs for two-sided p<0.05 (all flips one way):")
for n in range(3, 12):
    p = 2 * 0.5 ** n
    print(f"  n={n:2}  p={p:.4f}{'  <-- significant' if p < 0.05 else ''}")
print("Holm across {A vs B, B vs C}: smallest p must be <=0.025, i.e. n>=7 net discordant")
print(f"On n=196 paired claims, 7 net flips = {7 / 196 * 100:.1f} percentage points")
