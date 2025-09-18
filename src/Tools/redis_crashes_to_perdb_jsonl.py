#!/usr/bin/env python3
"""Convert Redis crash seed commands into per-target RDB JSONL files.

For each target b_db we create one JSONL file containing one record per Redis command line.
Schema per line:
  {"index": <int>, "a_db": "redis", "b_db": <b_db>, "molt": <oracle>, "sql": <command+';'>}

Non-command / commentary lines are skipped via a simple whitelist heuristic.

Usage:
  python -m src.Tools.redis_crashes_to_perdb_jsonl \
      --crashes-dir Input/redis/crashes \
      --out-dir Input/redis_crashes_jsonl \
      --oracle-map norec:norec,tlp:tlp \
      --targets mysql,postgres,sqlite,clickhouse,duckdb,mariadb,tidb,monetdb

Currently oracle-map may be a single value (e.g., --oracle norec) applied to all; more
fine-grained per-db mapping can be added if required.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, List

DEFAULT_TARGETS = [
    "mysql",
    "postgres",
    "sqlite",
    "clickhouse",
    "duckdb",
    "mariadb",
    "tidb",
    "monetdb",
]

# Basic Redis command prefix whitelist (lowercase). Extend as needed.
REDIS_PREFIXES = {
    "set","get","del","exists","incr","decr","decrby","incrby","incrbyfloat",
    "zadd","zrange","zrevrange","zcard","zrank","zrevrank","zincrby","zrem","zinterstore","zunionstore","zrandmember","zmpop",
    "sadd","srem","smembers","srandmember","sunion","sunionstore","sdiff","sdiffstore","sinter","sinterstore",
    "lpush","rpush","lpop","rpop","lrange","llen","lset","lindex","linsert",
    "hset","hget","hgetall","hexists","hincrby","hdel","hlen",
    "bitop","bitpos","setbit","getbit","pfadd","pfcount",
    "sort","save","bgsave","flushall","flushdb","expire","pexpire","ttl","pttl"
}


def iter_crash_files(crashes_dir: Path) -> Iterable[Path]:
    for p in sorted(crashes_dir.iterdir()):
        if p.is_file():
            yield p


def is_command_line(line: str) -> bool:
    if not line or line.startswith("#"):
        return False
    first = line.split()[0].lower()
    return first in REDIS_PREFIXES


def extract_commands(path: Path) -> List[str]:
    out: List[str] = []
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = raw.strip()
        if not s:
            continue
        if not is_command_line(s):
            continue
        # normalize internal spaces
        s = " ".join(s.split())
        if not s.endswith(";"):
            s += ";"
        out.append(s)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Redis crashes -> per-target JSONL")
    ap.add_argument("--crashes-dir", default="Input/redis/crashes")
    ap.add_argument("--out-dir", default="Input/redis_crashes_jsonl")
    ap.add_argument("--targets", default=",".join(DEFAULT_TARGETS), help="Comma-separated b_db targets")
    ap.add_argument("--oracle", default="norec", help="Oracle (molt) to assign")
    ap.add_argument("--start-index", type=int, default=0, help="Starting index value")
    args = ap.parse_args()

    crashes_dir = Path(args.crashes_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    targets = [t for t in args.targets.split(",") if t]

    # Prepare writers per target
    writers = {}
    for t in targets:
        fp = out_dir / f"redis_crashes_{t}.jsonl"
        writers[t] = fp.open("w", encoding="utf-8")

    idx = args.start_index
    file_count = 0
    total_cmds = 0
    for f in iter_crash_files(crashes_dir):
        cmds = extract_commands(f)
        if not cmds:
            continue
        file_count += 1
        for cmd in cmds:
            for t in targets:
                rec = {
                    "index": idx,
                    "a_db": "redis",
                    "b_db": t,
                    "molt": args.oracle,
                    "sql": cmd,
                }
                writers[t].write(json.dumps(rec, ensure_ascii=False) + "\n")
            idx += 1
            total_cmds += 1

    for w in writers.values():
        w.close()

    print(f"Processed files with commands: {file_count}")
    print(f"Total command lines output: {total_cmds}")
    for t in targets:
        fp = out_dir / f"redis_crashes_{t}.jsonl"
        print(f"  {t}: {fp}")

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
