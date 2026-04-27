#!/usr/bin/env python3
"""
One-shot world.md generator for foundation phase.
Reads seed.txt + voice.md + CRAFT.md, calls the writer model, outputs world.md content.
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
            "You are a speculative-fiction worldbuilder and continuity architect. "
            "You adapt to the seed instead of imposing a genre template. Build specific, "
            "interconnected settings where every speculative rule has costs, social effects, "
            "and sensory consequences. Write clean, direct prose and avoid AI slop words."
        ),
        max_tokens=max_tokens,
        temperature=0.7,
        role="writer",
        model=WRITER_MODEL,
        timeout=300,
    )


def voice_identity(text: str) -> str:
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if "Part 2" in line:
            return "\n".join(lines[i:])
    return text


seed = (BASE_DIR / "seed.txt").read_text()
voice = (BASE_DIR / "voice.md").read_text()
craft = (BASE_DIR / "CRAFT.md").read_text()
voice_part2 = voice_identity(voice)

prompt = f"""Build WORLD.MD for this novel from the seed below.

The document is the definitive reference for what exists, what is known, what is uncertain,
and what pressures shape the story. Do not impose a genre template. If the seed is science
fiction, treat the speculative engine as science, technology, culture, institutions, physics,
media, belief, and human cost. Do not invent supernatural systems unless the seed asks for them.

SEED CONCEPT:
{seed}

VOICE IDENTITY:
{voice_part2}

CRAFT REFERENCE:
{craft}

STRUCTURE THE DOCUMENT WITH THESE SECTIONS:

## Core Premise and Ontology
State the central speculative claim, what evidence exists, what remains unproved, and why
uncertainty matters dramatically.

## Timeline and Present-Day Pressure
A timeline of major public and private events. Focus on events that create current tensions,
not decorative backstory.

## Physical / Scientific Rules
List the testable rules, limits, costs, unknowns, failure modes, and contradictions in the
speculative engine. Every rule should create narrative pressure.

## Places and Sensory Signatures
Name and describe the key locations, including ordinary human spaces. Give each place a
specific sensory signature and a role in the plot.

## Institutions, Factions, and Public Response
Map who has power, who wants it, who is harmed, and how governments, markets, media,
religions, families, and fringe groups respond.

## Daily Life Under the Premise
Show how the premise changes work, school, grief, ambition, love, money, ritual, language,
and childhood.

## Technology, Media, and Evidence
Describe the tools, records, data channels, artifacts, and public images the story depends on.
Separate confirmed facts from rumors and propaganda.

## Cultural and Philosophical Fault Lines
Identify the arguments people are having and the embodied costs of those arguments.
Keep the ideas attached to actions, losses, policies, and relationships.

## Internal Consistency Rules
Hard constraints a writer must not violate. Include what cannot happen, what cannot be known,
and what would cheapen the premise.

IMPORTANT:
- Be specific. Use names, dates, procedures, rituals, images, and concrete consequences.
- Facts should interconnect: the speculative engine should shape politics, culture, economy,
  family life, and the protagonist's choices.
- Preserve the seed's uncertainty. Do not solve the metaphysics cleanly.
- Write in clean, direct prose. No filler, no generic uplift, no puzzle-box cleverness.
- Target roughly 3000-4000 dense words.
"""

print("Calling writer model...", file=sys.stderr)
result = call_writer(prompt)
print(result)
