#!/usr/bin/env python3
"""Eval-guided foundation repair.

Reads the current best foundation docs plus a foundation eval JSON, then asks the
writer model to make targeted repairs instead of rerolling the foundation from
scratch. The model returns marked full-file sections; only allowed planning files
are written.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

from llm_client import call_llm

BASE_DIR = Path(__file__).parent
ALLOWED_FILES = {"world.md", "characters.md", "outline.md", "canon.md", "voice.md"}


def parse_file_sections(text: str) -> dict[str, str]:
    """Extract <<<FILE: name>>> ... <<<END FILE>>> sections from model output."""
    pattern = re.compile(
        r"<<<FILE:\s*([^>\n]+?)\s*>>>\s*\n(.*?)\n\s*<<<END FILE>>>",
        re.DOTALL,
    )
    sections: dict[str, str] = {}
    for raw_name, content in pattern.findall(text):
        name = raw_name.strip()
        if name not in ALLOWED_FILES:
            continue
        sections[name] = content.strip() + "\n"
    return sections


def dimension_summary(eval_data: dict) -> str:
    """Condense eval JSON into actionable repair instructions."""
    lines: list[str] = []
    lines.append(f"overall_score: {eval_data.get('overall_score')}")
    lines.append(f"lore_score: {eval_data.get('lore_score')}")
    weakest = eval_data.get("weakest_dimension")
    if weakest:
        lines.append(f"weakest_dimension: {weakest}")

    improvements = eval_data.get("top_3_improvements") or eval_data.get("top_3_revisions") or []
    if improvements:
        lines.append("\nTOP IMPROVEMENTS:")
        for idx, item in enumerate(improvements, 1):
            lines.append(f"{idx}. {item}")

    contradictions = eval_data.get("contradictions_found") or []
    if contradictions:
        lines.append("\nCONTRADICTIONS TO FIX:")
        for idx, item in enumerate(contradictions, 1):
            lines.append(f"{idx}. {item}")

    lines.append("\nDIMENSION GAPS AND FIXES:")
    for key, value in eval_data.items():
        if not isinstance(value, dict):
            continue
        gap = value.get("gap")
        fix = value.get("fix")
        score = value.get("score")
        if gap or fix:
            lines.append(f"\n[{key}] score={score}")
            if gap:
                lines.append(f"gap: {gap}")
            if fix:
                lines.append(f"fix: {fix}")
    return "\n".join(lines)


def read_doc(name: str) -> str:
    path = BASE_DIR / name
    return path.read_text() if path.exists() else ""


def build_prompt(eval_data: dict, eval_path: Path) -> str:
    docs = {name: read_doc(name) for name in sorted(ALLOWED_FILES)}
    repair_brief = dimension_summary(eval_data)
    return f"""Repair the current foundation docs for this novel using the eval feedback.

This is NOT a fresh generation pass. Preserve the existing best run's core creative choices,
proper nouns, dates, mission architecture, tone, premise, and strong material. Make surgical
improvements that address the eval gaps without introducing alternate canon.

Eval source: {eval_path}

REPAIR BRIEF:
{repair_brief}

CURRENT DOCS:

<<<CURRENT: world.md>>>
{docs['world.md']}
<<<END CURRENT>>>

<<<CURRENT: characters.md>>>
{docs['characters.md']}
<<<END CURRENT>>>

<<<CURRENT: outline.md>>>
{docs['outline.md']}
<<<END CURRENT>>>

<<<CURRENT: canon.md>>>
{docs['canon.md']}
<<<END CURRENT>>>

<<<CURRENT: voice.md>>>
{docs['voice.md']}
<<<END CURRENT>>>

REPAIR RULES:
- Do not reroll the premise, cast, timeline, institutions, or craft names.
- Do not replace strong foundation material with a shorter generic summary.
- Fix the exact weaknesses in the eval brief.
- Highest priority for this run: write a real voice profile in voice.md, add operational Boundary/Candle rules, add an anomaly/evidence matrix, and standardize continuity risks.
- If creating operations/anomaly material, place it inside world.md and canon.md so evaluate.py can see it.
- Output only files that need changes.
- For every changed file, output the complete new file, not a diff.
- Use this exact wrapper format and no markdown code fences:

<<<FILE: voice.md>>>
...complete file...
<<<END FILE>>>

<<<FILE: world.md>>>
...complete file...
<<<END FILE>>>
"""


def apply_sections(sections: dict[str, str]) -> list[str]:
    written: list[str] = []
    for name, content in sections.items():
        if name not in ALLOWED_FILES:
            continue
        path = BASE_DIR / name
        path.write_text(content)
        written.append(name)
    return written


def repair(eval_log: Path) -> list[str]:
    load_dotenv(BASE_DIR / ".env")
    eval_data = json.loads(eval_log.read_text())
    prompt = build_prompt(eval_data, eval_log)
    model = os.environ.get("AUTONOVEL_WRITER_MODEL", "claude-sonnet-4-6")
    result = call_llm(
        prompt,
        system=(
            "You are a rigorous developmental editor and continuity architect. "
            "You improve an existing novel foundation by following eval notes exactly. "
            "You preserve strong existing choices and avoid random rewrites."
        ),
        max_tokens=24000,
        temperature=0.25,
        role="writer",
        model=model,
        timeout=int(os.environ.get("AUTONOVEL_CODEX_TIMEOUT", "1800")),
    )
    sections = parse_file_sections(result)
    if not sections:
        raise SystemExit("No repair file sections found in model output")
    return apply_sections(sections)


def main() -> None:
    parser = argparse.ArgumentParser(description="Repair foundation docs using a foundation eval log")
    parser.add_argument("--eval-log", required=True, help="Path to *_foundation.json eval log")
    args = parser.parse_args()

    eval_log = Path(args.eval_log)
    if not eval_log.is_absolute():
        eval_log = BASE_DIR / eval_log
    if not eval_log.exists():
        print(f"ERROR: eval log not found: {eval_log}", file=sys.stderr)
        raise SystemExit(2)

    written = repair(eval_log)
    print("Repaired foundation files:")
    for name in written:
        print(f"- {name}")


if __name__ == "__main__":
    main()
