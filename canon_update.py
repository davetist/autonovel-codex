#!/usr/bin/env python3
"""Append accepted chapter eval canon entries into canon.md."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

ADDENDUM_HEADING = "## Post-Draft Canon Addendum"


def _clean_entry(entry: object) -> str | None:
    if not isinstance(entry, str):
        return None
    text = " ".join(entry.strip().split())
    if not text:
        return None
    text = re.sub(r"([.!?])([\"'’”])\.$", r"\1\2", text)
    if text.endswith((".", "!", "?", ".'", ".\"", ".’", ".”", "!'", "!\"", "?’", "?”")):
        return text
    return text + "."


def _canonical_key(line: str) -> str:
    text = line.strip()
    if text.startswith("-"):
        text = text[1:].strip()
    if "*(" in text:
        text = text.split("*(", 1)[0].strip()
    return text.rstrip(" .").casefold()


def _existing_fact_keys(canon_text: str) -> set[str]:
    keys: set[str] = set()
    for line in canon_text.splitlines():
        if line.lstrip().startswith("-"):
            keys.add(_canonical_key(line))
    return keys


def _format_entries(chapter: int, entries: Iterable[str]) -> str:
    lines = [f"### Chapter {chapter}", ""]
    for entry in entries:
        lines.append(f"- {entry} *(ch{chapter:02d} eval)*")
    return "\n".join(lines).rstrip() + "\n"


def append_new_canon_entries_from_eval(
    base_dir: str | Path,
    *,
    chapter: int,
    eval_log: str | Path | None,
) -> int:
    """Append unique new_canon_entries from an accepted chapter eval to canon.md.

    Returns the number of new facts appended. Missing eval logs, missing canon.md,
    malformed JSON, or empty new_canon_entries are treated as no-op so drafting
    can continue after a successful chapter evaluation.
    """
    if eval_log is None:
        return 0

    base = Path(base_dir)
    canon_path = base / "canon.md"
    eval_path = Path(eval_log)
    if not eval_path.is_absolute():
        eval_path = base / eval_path

    if not canon_path.exists() or not eval_path.exists():
        return 0

    try:
        data = json.loads(eval_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0

    raw_entries = data.get("new_canon_entries", [])
    if not isinstance(raw_entries, list):
        return 0

    canon_text = canon_path.read_text(encoding="utf-8")
    existing = _existing_fact_keys(canon_text)
    new_entries: list[str] = []
    for raw in raw_entries:
        entry = _clean_entry(raw)
        if entry is None:
            continue
        key = _canonical_key(entry)
        if key in existing:
            continue
        existing.add(key)
        new_entries.append(entry)

    if not new_entries:
        return 0

    addition = _format_entries(chapter, new_entries)
    text = canon_text.rstrip()
    if ADDENDUM_HEADING not in text:
        text = f"{text}\n\n{ADDENDUM_HEADING}\n\n{addition}" if text else f"{ADDENDUM_HEADING}\n\n{addition}"
    else:
        text = f"{text}\n\n{addition}"
    canon_path.write_text(text.rstrip() + "\n", encoding="utf-8")
    return len(new_entries)
