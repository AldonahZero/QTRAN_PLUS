"""
Merge command card drafts and parsed examples into a unified Redis knowledge base JSON.
Inputs:
- NoSQLFeatureKnowledgeBase/Redis/command_cards_draft.json
- NoSQLFeatureKnowledgeBase/Redis/parsed_examples/*.json
Output:
- NoSQLFeatureKnowledgeBase/Redis/redis_commands_knowledge.json
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[3]
REDIS_DIR = ROOT / "NoSQLFeatureKnowledgeBase" / "Redis"
CARDS = REDIS_DIR / "command_cards_draft.json"
EX_DIR = REDIS_DIR / "parsed_examples"
EX_DIR_EN = REDIS_DIR / "parsed_examples_enriched"
OUT = REDIS_DIR / "redis_commands_knowledge.json"


def load_cards() -> Dict[str, Dict]:
    if not CARDS.exists():
        return {}
    data = json.loads(CARDS.read_text(encoding="utf-8"))
    cards = {}
    for c in data.get("cards", []):
        command = (c.get("command") or "UNKNOWN").upper()
        cards.setdefault(command, {"cards": []})
        cards[command]["cards"].append(c)
    return cards


def load_examples() -> Dict[str, List[Dict]]:
    out: Dict[str, List[Dict]] = {}
    src_dir = EX_DIR_EN if EX_DIR_EN.exists() else EX_DIR
    if not src_dir.exists():
        return out
    for p in src_dir.glob("*.json"):
        obj = json.loads(p.read_text(encoding="utf-8"))
        cmd = (obj.get("command") or p.stem).upper()
        out[cmd] = obj.get("examples", [])
    return out


def main():
    cards = load_cards()
    examples = load_examples()

    merged: Dict[str, Dict] = {}
    all_cmds = set(cards.keys()) | set(examples.keys())
    for cmd in sorted(all_cmds):
        merged[cmd] = {
            "command": cmd,
            "cards": cards.get(cmd, {}).get("cards", []),
            "examples": examples.get(cmd, []),
        }

    OUT.write_text(json.dumps({"commands": merged}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Unified knowledge written to {OUT}")


if __name__ == "__main__":
    main()
