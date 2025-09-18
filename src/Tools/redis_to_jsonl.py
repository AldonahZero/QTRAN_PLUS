#!/usr/bin/env python3
"""Bundle Redis crash/hang command sequences into QTRAN JSONL input format.

Each output JSON object matches the existing demo1.jsonl schema:
  {
    "index": <int>,
    "a_db": "redis",
    "b_db": "mysql",              # or any target RDB
    "molt": "norec",              # placeholder oracle type
    "sqls": ["SET k 1;", "GET k;"]
  }

Design notes:
  * We treat each Redis file (a crash or hang seed) as one logical "bug" item.
  * Redis commands are not SQL; we keep them as separate pseudo statements terminated with ';'
    so that downstream components expecting semicolons can tokenize uniformly.
  * The first element of sqls is a comment giving the original relative path for traceability.
  * User can specify multiple target b_dbs; we duplicate the record per target (optional).
  * For very large corpora you can cap with --max-files and/or shuffle.

CLI example:
  python -m src.Tools.redis_to_jsonl \
      --crashes-dir Input/redis/crashes \
      --hangs-dir Input/redis/hangs \
      --include-hangs \
      --b-dbs mysql,postgres,sqlite \
      --max-files 50 \
      --output Input/redis_demo.jsonl

"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Iterable, List


DEFAULT_B_DBS = [
    "mysql",
    "postgres",
    "sqlite",
    "clickhouse",
    "duckdb",
    "mariadb",
    "tidb",
    "monetdb",
]


def iter_seed_files(crashes_dir: Path, hangs_dir: Path | None, include_hangs: bool) -> Iterable[Path]:
    if crashes_dir.is_dir():
        for p in sorted(crashes_dir.iterdir()):
            if p.is_file():
                yield p
    if include_hangs and hangs_dir and hangs_dir.is_dir():
        for p in sorted(hangs_dir.iterdir()):
            if p.is_file():
                yield p


def load_commands(path: Path) -> List[str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines: List[str] = []
    for raw in text.splitlines():
        s = raw.strip()
        if not s:
            continue
        # Normalize internal whitespace a bit (avoid huge gaps)
        s = " ".join(s.split())
        # Append semicolon if not already ending with ; to emulate SQL statement boundary.
        if not s.endswith(";"):
            s = s + ";"
        lines.append(s)
    return lines


def build_records(files: List[Path], b_dbs: List[str], molt: str, shuffle: bool) -> List[dict]:
    if shuffle:
        random.shuffle(files)
    out: List[dict] = []
    idx = 0
    for f in files:
        cmds = load_commands(f)
        if not cmds:
            continue
        rel = f.as_posix()
        for b in b_dbs:
            record = {
                "index": idx,
                "a_db": "redis",
                "b_db": b,
                "molt": molt,
                "sqls": [f"-- source: {rel}"] + cmds,
            }
            out.append(record)
            idx += 1
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Convert Redis crash/hang seeds into QTRAN JSONL input format")
    ap.add_argument("--crashes-dir", default="Input/redis/crashes", help="Directory containing crash seeds")
    ap.add_argument("--hangs-dir", default="Input/redis/hangs", help="Directory containing hang seeds")
    ap.add_argument("--include-hangs", action="store_true", help="Include hang seeds as well as crashes")
    ap.add_argument("--b-dbs", default="mysql", help="Comma-separated target b_db list (default: mysql)")
    ap.add_argument("--molt", default="norec", help="Oracle strategy tag to populate in records")
    ap.add_argument("--max-files", type=int, default=None, help="Cap number of source files (after merge)")
    ap.add_argument("--shuffle", action="store_true", help="Shuffle file order before truncation")
    ap.add_argument("--output", required=True, help="Output JSONL path")
    ap.add_argument("--all-b-dbs", action="store_true", help="Use the full built-in 8 RDB list")

    args = ap.parse_args()

    crashes_dir = Path(args.crashes_dir)
    hangs_dir = Path(args.hangs_dir)

    if args.all_b_dbs:
        b_dbs = DEFAULT_B_DBS
    else:
        b_dbs = [s for s in (args.b_dbs.split(",") if args.b_dbs else ["mysql"]) if s]

    files = list(iter_seed_files(crashes_dir, hangs_dir, args.include_hangs))
    if args.shuffle:
        random.shuffle(files)
    if args.max_files is not None:
        files = files[: args.max_files]

    records = build_records(files, b_dbs=b_dbs, molt=args.molt, shuffle=False)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as w:
        for r in records:
            w.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"Wrote {len(records)} records to {out_path}")
    print(f"  source files used: {len(files)} (crashes: {crashes_dir.exists()}, hangs included: {args.include_hangs})")
    print(f"  target b_dbs: {','.join(b_dbs)}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
