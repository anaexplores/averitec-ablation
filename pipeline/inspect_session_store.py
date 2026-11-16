"""Inspect the OpenCode session store for hard evidence about the judge runs.

Read-only. Answers: how many sessions ran, which model each used, when, and which files
each session touched. This is the primary evidence behind the isolation claim; the repo
ledger is derived from it rather than from memory.
"""
import os
import sqlite3
import sys

DB_FILE = os.path.expanduser("~/.local/share/opencode/opencode.db").replace("\\", "/")
DB = f"file:{DB_FILE}?mode=ro"


def main():
    db = sqlite3.connect(DB, uri=True)
    db.row_factory = sqlite3.Row
    tables = [r[0] for r in db.execute("select name from sqlite_master where type='table' order by name")]
    print("tables:", tables)
    for t in tables:
        n = db.execute(f'select count(*) from "{t}"').fetchone()[0]
        cols = [c[1] for c in db.execute(f'pragma table_info("{t}")')]
        print(f"  {t:26} rows={n:<9} cols={cols}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
