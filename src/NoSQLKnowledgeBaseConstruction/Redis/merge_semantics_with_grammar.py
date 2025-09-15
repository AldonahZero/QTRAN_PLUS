#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Merge Redis grammar tag-to-command/arg mapping into redis_semantic_kb.json.
- Parse by_tag keys like "AppendRule1->elem" to infer command name (append) and arg label (elem)
- Aggregate actions (DefineSymbol/UseSymbol/InvalidateSymbol/AlterOrder) per command and per arg label
- Write merged view into outputs/redis_semantic_kb.json under key `by_command` and `tag_to_command`

Assumptions:
- Tag keys may be comma-separated; handle each tag separately
- Rule name pattern: ^([A-Za-z]+)Rule (prefix is the command base)
- Command name = lowercased prefix (e.g., ZUnionStore -> zunionstore)
- Arg label is substring after '->', if missing, use 'arg'
- Some tags may concatenate labels (e.g., elemmember); keep raw label

Idempotent: Safe to run multiple times; it regenerates by_command each run.
"""

import json
import os
import re
from collections import defaultdict
from typing import Dict, List, Any, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
FEATURE_ROOT = os.path.join(
    ROOT, "NoSQLFeatureKnowledgeBase", "Redis"
)
OUTPUTS = os.path.join(FEATURE_ROOT, "outputs")
SEM_FILE = os.path.join(OUTPUTS, "redis_semantic_kb.json")
GRAMMAR_FILE = os.path.join(FEATURE_ROOT, "inputs", "grammars", "Redis.g4")

RULE_PREFIX_RE = re.compile(r"^([A-Za-z]+)Rule")


def normalize_command(base: str) -> str:
    """Convert mixed-case base to redis command name (lowercase, no separators).
    ZUnionStore -> zunionstore; Append -> append; XReadGroup -> xreadgroup
    """
    return base.lower()


def parse_tag(tag: str) -> Tuple[str, str]:
    """Split 'AppendRule1->elem' into ('AppendRule1', 'elem'). If no '->', label='arg'."""
    if "->" in tag:
        left, right = tag.split("->", 1)
        return left.strip(), right.strip()
    return tag.strip(), "arg"


def rule_to_command(rule_name: str) -> str:
    m = RULE_PREFIX_RE.match(rule_name)
    if not m:
        # Fallback: sometimes rule is just 'AppendRule' or other forms
        # Use non-greedy up to 'Rule'
        idx = rule_name.find("Rule")
        if idx > 0:
            return normalize_command(rule_name[:idx])
        return normalize_command(rule_name)
    return normalize_command(m.group(1))


def merge_by_command(by_tag: Dict[str, List[Dict[str, Any]]]) -> Tuple[Dict[str, Any], Dict[str, str]]:
    by_command: Dict[str, Any] = {}
    tag_to_command: Dict[str, str] = {}

    # Structure: by_command[cmd] = { "actions": {DefineSymbol:[types], UseSymbol:[types], ...},
    #                                "args": { label: {action: [types or entries]} },
    #                                "tags": [ ... ] }
    for tag_key, entries in by_tag.items():
        # tag_key may include multiple tags separated by commas
        for raw_tag in [t.strip() for t in tag_key.split(",") if t.strip()]:
            rule_name, label = parse_tag(raw_tag)
            cmd = rule_to_command(rule_name)
            tag_to_command[raw_tag] = cmd
            bucket = by_command.setdefault(cmd, {"actions": defaultdict(set), "args": defaultdict(lambda: defaultdict(set)), "tags": set()})
            bucket["tags"].add(raw_tag)

            for entry in entries:
                action = entry.get("action")
                args = entry.get("args", {})
                if not action:
                    continue
                # Collect high-level action types
                if action in ("DefineSymbol", "UseSymbol", "InvalidateSymbol"):
                    sym_type = args.get("type")
                    type_block = args.get("type_block")
                    custom_types = args.get("custom_types")
                    # Normalize into iterable
                    types: List[str] = []
                    if isinstance(sym_type, list):
                        types.extend(sym_type)
                    elif isinstance(sym_type, str):
                        types.append(sym_type)
                    if isinstance(type_block, list):
                        types.extend(type_block)
                    elif isinstance(type_block, str):
                        types.append(type_block)
                    if isinstance(custom_types, list):
                        types.extend(custom_types)
                    elif isinstance(custom_types, str):
                        types.append(custom_types)
                    # Dedup & add
                    for t in types:
                        bucket["actions"][action].add(t)
                        bucket["args"][label][action].add(t)
                else:
                    # Other actions like AlterOrder
                    bucket["actions"][action].add(json.dumps(args, sort_keys=True))
                    bucket["args"][label][action].add(json.dumps(args, sort_keys=True))

    # Convert sets to sorted lists for JSON serializable stable output
    def to_sorted(obj):
        if isinstance(obj, dict):
            return {k: to_sorted(v) for k, v in sorted(obj.items())}
        if isinstance(obj, set):
            return sorted(obj)
        return obj

    for cmd, data in by_command.items():
        data["actions"] = to_sorted(data["actions"])  # type: ignore
        # args labels
        data["args"] = {lbl: to_sorted(acts) for lbl, acts in sorted(data["args"].items())}  # type: ignore
        data["tags"] = sorted(data["tags"])  # type: ignore

    return by_command, tag_to_command


def main():
    if not os.path.exists(SEM_FILE):
        raise SystemExit(f"semantic KB not found: {SEM_FILE}")
    with open(SEM_FILE, "r", encoding="utf-8") as f:
        sem = json.load(f)

    by_tag = sem.get("by_tag") or {}
    if not by_tag:
        raise SystemExit("by_tag is empty in semantic KB; cannot merge")

    by_command, tag_to_command = merge_by_command(by_tag)

    sem["by_command"] = by_command
    sem["tag_to_command"] = tag_to_command

    # Optional: embed grammar source info for traceability
    if os.path.exists(GRAMMAR_FILE):
        try:
            # lightweight checksum: file size and mtime
            st = os.stat(GRAMMAR_FILE)
            sem.setdefault("sources", {})["Redis.g4"] = {
                "path": os.path.relpath(GRAMMAR_FILE, ROOT),
                "size": st.st_size,
                "mtime": int(st.st_mtime),
            }
        except Exception:
            pass

    with open(SEM_FILE, "w", encoding="utf-8") as f:
        json.dump(sem, f, ensure_ascii=False, indent=2, sort_keys=True)

    print(f"Merged by_command for {len(by_command)} commands. Updated: {SEM_FILE}")


if __name__ == "__main__":
    main()
