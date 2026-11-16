"""Backfill session_id in data/session_ledger.jsonl from the OpenCode session store.

NEW sprint work (2026-11-15). The completed run's ledger rows were written with
session_id=null / attestation="not-retained" because the orchestrator log was not
kept as an artefact. The session store itself was retained, so the identifiers can
be recovered rather than invented. Read-only towards the store; rewrites only the
session_id and attestation fields of existing ledger rows.

A ledger row is matched to exactly one session when:
  * the session title is '<cond> batch<NN> <short-judge>', optionally with a
    suffix (registered retries use ' retry'/' retry2', the deviation cell uses
    ' fallback'), and
  * the session ended successfully, and
  * the row's recorded_utc (the output file's mtime) falls inside the session's
    [time_created, time_updated] window widened by 60 s on both sides (clock
    tolerance; the fallback cell's output was written shortly after its
    session closed), and
  * the session's model matches the row's model_used.

Any cell without exactly one such session is reported and left untouched.

    python pipeline/backfill_ledger_sessions.py            # rewrite the ledger
    python pipeline/backfill_ledger_sessions.py --dry-run  # print the plan
"""
import argparse
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_FILE = os.path.expanduser("~/.local/share/opencode/opencode.db").replace("\\", "/")
DB = f"file:{DB_FILE}?mode=ro"
TOLERANCE_MS = 60000
TITLE_RE = re.compile(r"^([ABC]) batch(\d{2}) ([a-z]+)(?: .*)?$")


def parse_utc(s):
    return datetime.fromisoformat(s).timestamp() * 1000


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    reg = json.load(open(os.path.join(ROOT, "data", "run_registry.json"), encoding="utf-8"))
    ledger_path = os.path.join(ROOT, reg["ledger"]["file"])
    rows = [json.loads(l) for l in open(ledger_path, encoding="utf-8") if l.strip()]

    db = sqlite3.connect(DB, uri=True)
    db.row_factory = sqlite3.Row
    sessions = []
    for r in db.execute("select id,title,model,time_created,time_updated,idle_outcome "
                        "from session_v2 order by time_created"):
        m = TITLE_RE.match(r["title"] or "")
        if not m:
            continue
        sessions.append({
            "id": r["id"], "title": r["title"],
            "cond": m.group(1), "batch": int(m.group(2)),
            "judge": m.group(3),
            "model": json.loads(r["model"])["id"],
            "provider": json.loads(r["model"]).get("providerID"),
            "created": r["time_created"], "updated": r["time_updated"],
            "outcome": r["idle_outcome"],
        })

    assigned, unmatched, model_mismatch = {}, [], []
    used = {}
    for row in rows:
        short = row["judge"].split("-")[0]
        mt = parse_utc(row["recorded_utc"])
        cands = [s for s in sessions
                 if s["cond"] == row["condition"] and s["batch"] == row["batch"]
                 and s["judge"] == short and s["outcome"] == "succeeded"
                 and s["created"] - TOLERANCE_MS <= mt <= s["updated"] + TOLERANCE_MS]
        if len(cands) != 1:
            unmatched.append((row["judge"], row["condition"], row["batch"], len(cands)))
            continue
        s = cands[0]
        if s["model"] not in row["model_used"]:
            model_mismatch.append((row["judge"], row["condition"], row["batch"],
                                   s["model"], row["model_used"]))
            continue
        if s["id"] in used:
            raise SystemExit(f"FATAL: session {s['id']} matched twice "
                             f"({used[s['id']]} and {row['judge']}/{row['condition']}/{row['batch']})")
        used[s["id"]] = (row["judge"], row["condition"], row["batch"])
        assigned[(row["judge"], row["condition"], row["batch"])] = s

    extras = [s for s in sessions if s["id"] not in used]

    print(f"ledger rows: {len(rows)}; store candidate sessions: {len(sessions)}")
    print(f"matched: {len(assigned)}; unmatched cells: {len(unmatched)}; "
          f"model mismatches: {len(model_mismatch)}")
    print(f"store sessions not bound to a cell (retries/blocked attempts): {len(extras)}")
    for s in extras:
        print(f"  unbound: {s['title']} [{s['model']}] outcome={s['outcome']}")
    for u in unmatched:
        print(f"  UNMATCHED CELL: {u}")
    for mm in model_mismatch:
        print(f"  MODEL MISMATCH: {mm}")
    if unmatched or model_mismatch:
        print("ledger left unchanged")
        return 1

    for row in rows:
        s = assigned.get((row["judge"], row["condition"], row["batch"]))
        if not s:
            continue
        row["session_id"] = s["id"]
        row["attestation"] = ("opencode-session-store;deviation-registered" if row["deviation_id"]
                              else "opencode-session-store")
    text = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    if args.dry_run:
        sys.stdout.write(text)
    else:
        with open(ledger_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print(f"ledger rewritten: {ledger_path}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
