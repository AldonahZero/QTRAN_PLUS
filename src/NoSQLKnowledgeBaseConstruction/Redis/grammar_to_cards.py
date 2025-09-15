"""
Extract a draft command card from Redis g4 grammars into JSON skeletons.
We only detect command rule names and map them to uppercase command tokens if present in the lexer.
The result is a minimal card with placeholders for args/returns/invariants.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[3]
LEX = ROOT / "NoSQLFeatureKnowledgeBase" / "Redis" / "RedisLexer.g4"
PAR = ROOT / "NoSQLFeatureKnowledgeBase" / "Redis" / "RedisParser.g4"
OUT = ROOT / "NoSQLFeatureKnowledgeBase" / "Redis" / "command_cards_draft.json"

# Capture TOKEN: 'TOKEN'
TOKEN_RE = re.compile(r"^\s*([A-Z][A-Z0-9_]*)\s*:\s*'([A-Z0-9]+)'\s*;\s*$")
# Capture rules like: spopCommand : SPOP setKeyName POSITIVE_DECIMAL_LITERAL? ;
RULE_RE = re.compile(r"^\s*([a-z][A-Za-z0-9_]*)\s*:\s*([A-Z0-9_][^;]+);\s*$")


def collect_tokens(text: str) -> Dict[str, str]:
    tokens: Dict[str, str] = {}
    for line in text.splitlines():
        m = TOKEN_RE.match(line)
        if m:
            tokens[m.group(1)] = m.group(2)
    return tokens


def collect_command_rules(text: str) -> Dict[str, str]:
    rules: Dict[str, str] = {}
    for line in text.splitlines():
        m = RULE_RE.match(line)
        if m and m.group(1).endswith("Command"):
            rules[m.group(1)] = m.group(2)
    return rules


def main():
    if not LEX.exists() or not PAR.exists():
        raise SystemExit(f"Missing grammar files at {LEX} or {PAR}")
    lex = LEX.read_text(encoding="utf-8")
    par = PAR.read_text(encoding="utf-8")

    tokens = collect_tokens(lex)
    rules = collect_command_rules(par)

    cards: List[Dict] = []
    for rule_name, rhs in rules.items():
        # find first TOKEN in RHS to map to concrete command keyword
        cmd = None
        for tok in re.findall(r"\b([A-Z][A-Z0-9_]*)\b", rhs):
            if tok in tokens:
                cmd = tokens[tok]
                break
        cards.append({
            "rule": rule_name,
            "command": cmd or "UNKNOWN",
            "syntax": rhs.strip(),
            "group": infer_group(rule_name),
            "args": [],
            "returns": "",
            "pitfalls": [],
            "invariants": []
        })

    OUT.write_text(json.dumps({"cards": cards}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Draft command cards written to {OUT}")


def infer_group(rule_name: str) -> str:
    if rule_name.endswith("setCommand") or rule_name.endswith("sCommand"):
        return "string"
    if rule_name.endswith("listCommand"):
        return "list"
    if rule_name.endswith("sortedSetCommand"):
        return "zset"
    if rule_name.endswith("hashCommand"):
        return "hash"
    if rule_name.endswith("commonCommand"):
        return "common"
    # individual commands
    if rule_name.startswith("s"):
        return "set"
    if rule_name.startswith("z"):
        return "zset"
    if rule_name.startswith("h"):
        return "hash"
    if rule_name.startswith("l") or rule_name.startswith("b"):
        return "list"
    if rule_name.startswith("m"):
        return "string"
    return "unknown"


if __name__ == "__main__":
    main()
