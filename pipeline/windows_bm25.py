"""Windowing and retrieval, ported verbatim from the Lost Caveats v0.1.1 judge inputs.

PREEXISTING CODE (written before the Apart AI x Epistemics Sprint, Nov 13-15 2026), copied from
https://github.com/anaexplores/lost-caveats (pipeline/windows.py, MIT-style repo license) and
reused unchanged except for this header. Any sprint-time changes will be listed below.

Whitespace-split words; 120-word windows (stride 60) for BM25 retrieval; 40-word windows (stride 20)
that contain a limiting marker. BM25 tokens: lower-case [a-z0-9]+ runs, no stemming, no stop words.
For each claim the judge receives:
    support_windows = bm25_top(claim, windows(text), 5)
    caveat_windows  = bm25_top(claim, [w for w in windows(text, 40, 20) if MARK.search(w)], 5)
"""
import math
import re
from collections import Counter

MARK = re.compile(
    r"\b(but not|not (this|that|these|those|yet|all|every|necessarily|always|the same)|only|however|although|though|"
    r"except|excluding|unlike|whereas|earlier|previous(ly)?|prior|preliminary|partial(ly)?|subset|estimated?|"
    r"approximately|roughly|caveat|limitation|limited to|does not|did not|do not|cannot|unverified|not (been )?verified|"
    r"pending|awaiting|at the time|as of|version|v\d|rather than|instead of|in contrast|no longer|still|remain(s|ing)?|"
    r"so far|to date|(19|20)\d\d)\b", re.I)


def windows(text, W=120, S=60):
    w = text.split()
    return [" ".join(w[i:i + W]) for i in range(0, max(1, len(w) - W + S), S)] or [""]


def tok(s):
    return re.findall(r"[a-z0-9]+", s.lower())


def bm25_top(query, docs, k, k1=1.5, b=0.75):
    toks = [tok(d) for d in docs]
    avg = sum(map(len, toks)) / max(1, len(toks))
    df = Counter(t for d in toks for t in set(d))
    n = len(docs)
    q = tok(query)
    scores = []
    for i, d in enumerate(toks):
        tf = Counter(d)
        s = 0.0
        for t in q:
            if t in tf:
                idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                s += idf * tf[t] * (k1 + 1) / (tf[t] + k1 * (1 - b + b * len(d) / avg))
        scores.append((s, i))
    return [docs[i] for _, i in sorted(scores, reverse=True)[:k]]


def judge_windows(claim, text):
    caveat = [w for w in windows(text, 40, 20) if MARK.search(w)]
    return {"support_windows": bm25_top(claim, windows(text), 5),
            "caveat_windows": bm25_top(claim, caveat, 5) if caveat else []}
