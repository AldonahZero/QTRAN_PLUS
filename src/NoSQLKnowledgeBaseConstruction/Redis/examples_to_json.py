"""
Parse Redis examples/*.txt into structured JSON examples per command.
Each .txt line is treated as a raw CLI example line. We try to extract command name and args.
Output is written to NoSQLFeatureKnowledgeBase/Redis/parsed_examples/<COMMAND>.json
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import List, Dict

ROOT = Path(__file__).resolve().parents[3]
EX_DIR = ROOT / "NoSQLFeatureKnowledgeBase" / "Redis" / "examples"
OUT_DIR = ROOT / "NoSQLFeatureKnowledgeBase" / "Redis" / "parsed_examples"

CMD_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9]*)\b(.*)$")


def parse_line(line: str) -> Dict:
    line = line.strip()
    if not line:
        return {}
    m = CMD_RE.match(line)
    if not m:
        return {"raw": line}
    cmd = m.group(1).upper()
    rest = m.group(2).strip()
    # naive split respecting quotes
    args: List[str] = []
    buf = ""
    in_s = False
    in_d = False
    for ch in rest:
        if ch == "'" and not in_d:
            in_s = not in_s
            buf += ch
        elif ch == '"' and not in_s:
            in_d = not in_d
            buf += ch
        elif ch.isspace() and not in_s and not in_d:
            if buf:
                args.append(buf)
                buf = ""
        else:
            buf += ch
    if buf:
        args.append(buf)
    return {"command": cmd, "args": args, "raw": line}


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for p in EX_DIR.glob("*.txt"):
        name = p.stem.upper()
        items: List[Dict] = []
        for line in p.read_text(encoding="utf-8").splitlines():
            rec = parse_line(line)
            if rec:
                items.append(rec)
        out = OUT_DIR / f"{name}.json"
        out.write_text(json.dumps({"command": name, "examples": items}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Parsed examples written to {OUT_DIR}")


if __name__ == "__main__":
    main()
