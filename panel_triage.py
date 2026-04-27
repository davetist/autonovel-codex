#!/usr/bin/env python3
"""Rank reader-panel feedback into concrete revision targets."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

QUESTION_WEIGHTS = {
    "missing_scene": 4.0,
    "worst_scene": 3.0,
    "cut_candidate": 3.2,
    "momentum_loss": 2.0,
    "thinnest_character": 1.0,
}
QUESTION_ORDER = {
    "missing_scene": 0,
    "worst_scene": 1,
    "cut_candidate": 2,
    "momentum_loss": 3,
    "thinnest_character": 4,
}
KEY_QUESTIONS = tuple(QUESTION_WEIGHTS)
_CHAPTER_GROUP_RE = re.compile(
    r"\b(?:chapters?|ch\.?)\s+"
    r"((?:\d+\s*(?:[-–]\s*\d+)?)(?:\s*(?:,|,?\s+and)\s*\d+\s*(?:[-–]\s*\d+)?)*)",
    re.I,
)


def _expand_number_group(group: str) -> list[int]:
    numbers: list[int] = []
    parts = re.split(r"\s*(?:,|and)\s*", group)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        range_match = re.fullmatch(r"(\d+)\s*[-–]\s*(\d+)", part)
        if range_match:
            start, end = map(int, range_match.groups())
            if start <= end and end - start <= 50:
                numbers.extend(range(start, end + 1))
            else:
                numbers.extend([start, end])
            continue
        for n in re.findall(r"\d+", part):
            numbers.append(int(n))
    return numbers


def extract_chapter_numbers(text: str) -> list[int]:
    """Extract ordered unique chapter numbers from singular/list/range mentions."""
    seen: set[int] = set()
    chapters: list[int] = []
    for match in _CHAPTER_GROUP_RE.finditer(text or ""):
        for ch in _expand_number_group(match.group(1)):
            if ch not in seen:
                seen.add(ch)
                chapters.append(ch)
    return chapters


def extract_missing_scene_target_chapters(text: str) -> list[int]:
    """Extract the chapter anchor for a missing-scene request.

    Missing-scene comments often mention old setup chapters as rationale and
    then a late placement chapter as the target. Prefer sentences about the
    missing packet/transcript being sent or received; otherwise fall back to the
    first placement sentence, then ordinary chapter extraction.
    """
    text = text or ""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    causal_terms = (
        "transcript", "private packet", "receipt", "receive", "receives",
        "reaches", "sent", "rendering",
    )
    placement_terms = ("late in", "early in", "near the start", "intercut", "between")
    def has_term(sentence: str, term: str) -> bool:
        if " " in term:
            return term in sentence
        return re.search(rf"\b{re.escape(term)}\b", sentence) is not None

    for terms in (causal_terms, placement_terms):
        for sentence in sentences:
            lower = sentence.lower()
            if any(has_term(lower, term) for term in terms):
                chapters = extract_chapter_numbers(sentence)
                if chapters:
                    return [min(chapters)]
    chapters = extract_chapter_numbers(text)
    return [min(chapters)] if chapters else []


def _chapter_issue_seed(chapter: int) -> dict[str, Any]:
    return {
        "chapter": chapter,
        "readers_by_issue": {q: set() for q in KEY_QUESTIONS},
        "snippets_by_issue": {q: [] for q in KEY_QUESTIONS},
    }


def _compact(text: str, limit: int = 420) -> str:
    compact = re.sub(r"\s+", " ", text or "").strip()
    return compact[:limit] + ("..." if len(compact) > limit else "")


def _primary_issue(entry: dict[str, Any]) -> str:
    issue_counts = {
        q: len(readers)
        for q, readers in entry["readers_by_issue"].items()
        if readers
    }
    if not issue_counts:
        return "momentum_loss"
    return max(
        issue_counts,
        key=lambda q: (
            issue_counts[q] * QUESTION_WEIGHTS.get(q, 1.0),
            -QUESTION_ORDER.get(q, 99),
        ),
    )


def _brief_hint(entry: dict[str, Any], issue: str) -> str:
    snippets = entry["snippets_by_issue"].get(issue) or []
    if snippets:
        return snippets[0]
    for values in entry["snippets_by_issue"].values():
        if values:
            return values[0]
    return f"Address {issue.replace('_', ' ')} feedback for Chapter {entry['chapter']}."


def rank_panel_targets(panel: dict[str, Any], limit: int = 5) -> list[dict[str, Any]]:
    """Return ranked revision targets from reader_panel.json data.

    Ranking favors multi-reader agreement, distinct issue types on the same
    chapter, and high-signal issue classes. It uses unique reader sets per
    chapter/issue so repeated chapter mentions in one answer do not inflate a
    target.
    """
    targets: dict[int, dict[str, Any]] = {}

    readers = panel.get("readers", {}) if isinstance(panel, dict) else {}
    for reader_name, answers in readers.items():
        if not isinstance(answers, dict):
            continue
        for question in KEY_QUESTIONS:
            answer = answers.get(question, "")
            if not isinstance(answer, str) or not answer.strip():
                continue
            chapters = (
                extract_missing_scene_target_chapters(answer)
                if question == "missing_scene"
                else extract_chapter_numbers(answer)
            )
            for chapter in chapters:
                entry = targets.setdefault(chapter, _chapter_issue_seed(chapter))
                entry["readers_by_issue"][question].add(str(reader_name))
                snippet = f"[{reader_name}] {_compact(answer)}"
                if snippet not in entry["snippets_by_issue"][question]:
                    entry["snippets_by_issue"][question].append(snippet)

    for disagreement in panel.get("disagreements", []) if isinstance(panel, dict) else []:
        chapter = disagreement.get("chapter")
        question = disagreement.get("question")
        if not isinstance(chapter, int) or question not in KEY_QUESTIONS:
            continue
        entry = targets.setdefault(chapter, _chapter_issue_seed(chapter))
        for reader in disagreement.get("flagged_by", []) or []:
            entry["readers_by_issue"][question].add(str(reader))
        details = disagreement.get("details", {})
        if isinstance(details, dict):
            for reader, detail in details.items():
                if isinstance(detail, str) and detail.strip():
                    snippet = f"[{reader}] {_compact(detail)}"
                    if snippet not in entry["snippets_by_issue"][question]:
                        entry["snippets_by_issue"][question].append(snippet)

    ranked: list[dict[str, Any]] = []
    for chapter, entry in targets.items():
        issue_counts = {
            q: len(readers)
            for q, readers in entry["readers_by_issue"].items()
            if readers
        }
        if not issue_counts:
            continue
        distinct_readers = set().union(*entry["readers_by_issue"].values())
        weighted_issue_score = sum(
            issue_counts[q] * QUESTION_WEIGHTS.get(q, 1.0)
            for q in issue_counts
        )
        issue_diversity_bonus = 0.75 * len(issue_counts)
        multi_reader_bonus = 0.5 * len(distinct_readers)
        score = weighted_issue_score + issue_diversity_bonus + multi_reader_bonus
        primary = _primary_issue(entry)
        ranked.append({
            "chapter": chapter,
            "question": primary,
            "primary_issue": primary,
            "count": len(entry["readers_by_issue"][primary]),
            "flagged_by": sorted(entry["readers_by_issue"][primary]),
            "issue_counts": issue_counts,
            "score": round(score, 3),
            "brief_hint": _brief_hint(entry, primary),
        })

    ranked.sort(
        key=lambda item: (
            -item["score"],
            -item["count"],
            QUESTION_ORDER.get(item["primary_issue"], 99),
            item["chapter"],
        )
    )
    return ranked[:limit]


def load_and_rank(panel_path: Path, limit: int = 5) -> list[dict[str, Any]]:
    if not panel_path.exists():
        return []
    return rank_panel_targets(json.loads(panel_path.read_text(encoding="utf-8")), limit=limit)
