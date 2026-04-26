#!/usr/bin/env python3
"""Autonomous editorial policy for choosing revision scope."""
from __future__ import annotations

from typing import Any

STRONG_NOVEL_SCORE = 9.0
LOW_NOVEL_SCORE = 8.5
MATERIAL_PANEL_SCORE = 8.0
CONCENTRATED_PANEL_SCORE = 20.0
SURGICAL_TARGET_LIMIT = 3
FULL_SCORE_DROP_TOLERANCE = 0.15


def _score(target: dict[str, Any]) -> float:
    try:
        return float(target.get("score", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _chapter(target: dict[str, Any]) -> int | None:
    chapter = target.get("chapter")
    return chapter if isinstance(chapter, int) and chapter > 0 else None


def choose_revision_strategy(
    state: dict[str, Any],
    panel_targets: list[dict[str, Any]],
    *,
    has_reader_panel: bool,
) -> dict[str, Any]:
    """Choose whether to run a broad cycle, surgical fixes, or export.

    The policy encodes the editorial judgment that kept requiring a human:
    high-scoring books with concentrated reader pain get named wounds fixed;
    low-scoring or signal-poor books get a broad revision cycle; clean strong
    books move forward.
    """
    novel_score = float(state.get("novel_score", 0.0) or 0.0)
    revision_cycle = int(state.get("revision_cycle", 0) or 0)
    material_targets = [t for t in panel_targets if _score(t) >= MATERIAL_PANEL_SCORE]
    top_score = _score(material_targets[0]) if material_targets else 0.0
    second_score = _score(material_targets[1]) if len(material_targets) > 1 else 0.0
    top_count = int(material_targets[0].get("count", 0) or 0) if material_targets else 0
    concentrated = bool(
        material_targets
        and (
            top_score >= CONCENTRATED_PANEL_SCORE
            or top_count >= 3
            or (second_score > 0 and top_score >= second_score * 1.5)
        )
    )

    base = {
        "mode": "broad_revision",
        "target_chapters": [],
        "skip_broad_adversarial_pass": False,
        "rerun_reader_panel_after": False,
        "rationale": "",
    }

    if not has_reader_panel:
        return base | {
            "rationale": "No reader panel exists yet; run a broad revision cycle to create fresh editorial signal.",
        }

    if novel_score < LOW_NOVEL_SCORE:
        return base | {
            "rationale": f"Novel score {novel_score:.2f} is below {LOW_NOVEL_SCORE:.2f}; broad revision is safer than local polishing.",
        }

    if material_targets and novel_score >= STRONG_NOVEL_SCORE and concentrated:
        chapters: list[int] = []
        for target in material_targets[:SURGICAL_TARGET_LIMIT]:
            ch = _chapter(target)
            if ch is not None and ch not in chapters:
                chapters.append(ch)
        return base | {
            "mode": "surgical_revision",
            "target_chapters": chapters,
            "skip_broad_adversarial_pass": True,
            "rerun_reader_panel_after": True,
            "rationale": (
                f"Strong novel score {novel_score:.2f} with concentrated reader-panel heat; "
                "fix named wounds instead of rerunning the whole machine."
            ),
        }

    if not material_targets and novel_score >= STRONG_NOVEL_SCORE and revision_cycle >= 1:
        return base | {
            "mode": "export",
            "rationale": f"Strong novel score {novel_score:.2f} and no material panel heat after revision cycle; move to export.",
        }

    return base | {
        "rationale": "Reader-panel signal is diffuse or not yet supported by a strong enough novel score; run broad revision.",
    }


def evaluate_surgical_cycle_outcome(
    *,
    previous_score: float,
    new_score: float,
    tolerance: float = FULL_SCORE_DROP_TOLERANCE,
) -> dict[str, str]:
    """Gate a surgical pass by full-novel score before moving on."""
    if new_score + tolerance >= previous_score:
        return {
            "action": "keep",
            "rationale": f"Full score held within tolerance ({previous_score:.2f} -> {new_score:.2f}).",
        }
    return {
        "action": "review_or_revert",
        "rationale": f"Full score dropped too much ({previous_score:.2f} -> {new_score:.2f}); inspect or revert the surgical pass.",
    }
