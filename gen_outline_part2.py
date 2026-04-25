#!/usr/bin/env python3
"""Generate an appendable outline continuation, repair pass, and foreshadowing ledger."""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from llm_client import call_llm

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

WRITER_MODEL = os.environ.get("AUTONOVEL_WRITER_MODEL", "claude-sonnet-4-6")


def call_writer(prompt, max_tokens=16000):
    return call_llm(
        prompt,
        system=(
            "You are a novel architect doing a second pass on an existing outline. Produce "
            "markdown that can be appended to outline.md: continue only if the outline is cut "
            "off, then add repair notes, continuity constraints, and a foreshadowing ledger. "
            "Adapt to the seed and never reuse another book's plot."
        ),
        max_tokens=max_tokens,
        temperature=0.5,
        role="writer",
        model=WRITER_MODEL,
        timeout=600,
    )


outline_path = BASE_DIR / "outline.md"
part1 = outline_path.read_text() if outline_path.exists() else ""
seed = (BASE_DIR / "seed.txt").read_text()
mystery = (BASE_DIR / "MYSTERY.md").read_text()
world = (BASE_DIR / "world.md").read_text()
characters = (BASE_DIR / "characters.md").read_text()

prompt = f"""Review the existing OUTLINE.MD for this novel and produce a second-pass appendix.
Your output will be appended to outline.md by the pipeline.

If the existing outline is visibly cut off, start by continuing from the last complete chapter
until the planned ending is complete. If it is already complete, do NOT rewrite every chapter;
instead add a compact repair pass that strengthens continuity, plant/payoff logic, and the final
movement.

SEED CONCEPT:
{seed}

EXISTING OUTLINE.MD:
{part1}

WORLD BIBLE EXCERPT:
{world[:12000]}

CHARACTER REGISTRY EXCERPT:
{characters[:12000]}

CENTRAL MYSTERY / AUTHOR NOTES:
{mystery}

OUTPUT FORMAT:

## Outline Second Pass
State whether the existing outline appears complete or cut off. If cut off, continue with the
missing chapters in the same chapter format. If complete, list the highest-priority structural
repairs instead of duplicating chapters.

## Continuity and Causality Repairs
- Identify any weak or missing causal links.
- Identify any places where public-scale events need private-scale consequences.
- Identify any places where the protagonist's interior turn needs a sharper external cost.
- Identify any places where the speculative uncertainty is over-explained or under-supported.

## Foreshadowing Ledger
| # | Thread | Planted (Ch) | Reinforced (Ch) | Payoff (Ch) | Type |
|---|--------|--------------|-----------------|-------------|------|

Include at least 15 threads. Plant-to-payoff distance should usually span at least 3 chapters.
Use threads that fit this seed: recurring images, records, anomalies, public rituals, private
habits, lines of dialogue, institutional actions, relationship beats, and structural echoes.

## Drafting Constraints
List the hard constraints a chapter drafter must honor so the outline does not drift.
"""

print("Calling writer model...", file=sys.stderr)
result = call_writer(prompt)
print(result)
