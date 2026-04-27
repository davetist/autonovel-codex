#!/usr/bin/env python3
"""
Generate canon.md by extracting all hard facts from seed.txt + world.md + characters.md.
"""
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
            "You are a continuity editor extracting hard facts from novel planning documents. "
            "You are precise, exhaustive, and never invent facts that are not in the source "
            "material. Every entry must be traceable to a specific statement in the sources."
        ),
        max_tokens=max_tokens,
        temperature=0.2,
        role="writer",
        model=WRITER_MODEL,
        timeout=300,
    )


world = (BASE_DIR / "world.md").read_text()
characters = (BASE_DIR / "characters.md").read_text()
seed = (BASE_DIR / "seed.txt").read_text()

prompt = f"""Extract EVERY hard fact from these planning documents into CANON.MD.
A hard fact is anything a writer must not contradict: names, ages, dates, locations, physical
rules, technical limits, social facts, relationships, established events, records, public claims,
unknowns, and explicit uncertainties.

SOURCE DOCUMENTS:

=== SEED.TXT ===
{seed}

=== WORLD.MD ===
{world}

=== CHARACTERS.MD ===
{characters}

FORMAT THE OUTPUT AS CANON.MD with these categories:

## Locations and Physical Facts
- Specific facts about places, distances, objects, artifacts, vehicles, environments, and sensory details

## Timeline
- Dated events, ages, durations, mission phases, historical periods, and sequence constraints

## Speculative Rules and Unknowns
- Confirmed rules, observed anomalies, costs, limits, contradictions, and things the story must not prove too cleanly

## Character Facts
- Ages or life stages, physical descriptions, habits, occupations, training, relationships, wounds, wants, secrets
- One entry per fact, not paragraphs

## Institutions, Factions, and Public Response
- Who controls what, who opposes whom, incentives, policies, markets, movements, beliefs, media narratives

## Cultural / Social Details
- Customs, rituals, taboos, slang, public images, economic changes, school or family effects, ordinary life

## Established Backstory
- Events that happened before chapter one and must remain consistent

## Open Questions to Preserve
- Ambiguities explicitly required by the seed or planning documents

RULES:
- One fact per bullet point. Short. Specific. Checkable.
- Include the source (seed.txt, world.md, or characters.md) in parentheses after each fact.
- Aim for 80-120 entries minimum. Be exhaustive.
- If two documents give slightly different details, note the discrepancy.
- Do not invent facts. Only record what is explicitly stated or directly entailed.
"""

print("Calling writer model...", file=sys.stderr)
result = call_writer(prompt)
print(result)
