"""Build data/session_ledger.jsonl for the cells that exist on disk.

NEW sprint work. One row per (judge, condition, batch) cell. The ledger is what gates
G5 (model identity) and G13 (session isolation) read.

Honesty rules:
  * recorded_utc is the output file's modification time, not a reconstructed guess;
  * model_used is the declared panel model, except for cells listed as a deviation in
    data/run_registry.json, which carry the fallback model that actually produced them;
  * session_id is null for the completed run: the orchestrator log was not retained as a
    machine artefact, so the rows are marked attestation="not-retained" instead of
    inventing identifiers. From ledger.required_from_utc onward a missing session_id is a
    hard FAIL in G13.

    python pipeline/make_ledger.py            # write the ledger
    python pipeline/make_ledger.py --dry-run  # print it, write nothing
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def mtime_utc(path):
    return datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc).isoformat(timespec="seconds")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    reg = json.load(open(os.path.join(ROOT, "data", "run_registry.json"), encoding="utf-8"))
    side = reg["side"]
    dev = {(e["cell"]["judge"], e["cell"]["condition"], e["cell"]["batch"]): e
           for e in reg["protocol_events"] if e["type"] == "deviation" and "cell" in e}

    rows = []
    for cond in reg["conditions"]:
        man = json.load(open(os.path.join(ROOT, "data", "judge_prompts", side, cond,
                                          "batches_manifest.json"), encoding="utf-8"))
        for b in man["batches"]:
            for judge in reg["panel"]:
                rel = os.path.join("data", "judge_outputs_ablation", side, cond,
                                   f"{judge}_batch{b['batch']:02d}.json")
                path = os.path.join(ROOT, rel)
                if not os.path.exists(path):
                    continue
                d = dev.get((judge, cond, b["batch"]))
                rows.append({
                    "judge": judge,
                    "condition": cond,
                    "batch": b["batch"],
                    "n_claims": len(b["claim_ids"]),
                    "model_declared": reg["panel"][judge],
                    "model_used": d["model_used"] if d else reg["panel"][judge],
                    "deviation_id": d["id"] if d else None,
                    "output_file": rel.replace(os.sep, "/"),
                    "session_id": None,
                    "isolation": "fresh-session-single-batch",
                    "attestation": "not-retained" if d is None else "not-retained;deviation-registered",
                    "recorded_utc": mtime_utc(path),
                    "side": side,
                    "ai_generated": True,
                    "label_hidden": True,
                })

    rows.sort(key=lambda r: (r["condition"], r["judge"], r["batch"]))
    out = os.path.join(ROOT, reg["ledger"]["file"])
    text = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    if args.dry_run:
        sys.stdout.write(text)
    else:
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    devs = sum(1 for r in rows if r["deviation_id"])
    print(f"{len(rows)} ledger rows ({devs} registered deviation cell(s)) -> {os.path.relpath(out, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
