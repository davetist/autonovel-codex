#!/usr/bin/env python3
"""
One-shot characters.md generator for foundation phase.
Reads seed.txt + voice.md + world.md + CRAFT.md, calls writer model, outputs characters.md content.
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
            "You are a character designer for literary speculative fiction. You build people "
            "with wounds, wants, needs, contradictions, secrets, pressures, and distinct speech. "
            "Infer the required cast from the seed and planning documents instead of reusing a "
            "template. Write clean, direct prose and avoid AI slop words."
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
world = (BASE_DIR / "world.md").read_text()
voice = (BASE_DIR / "voice.md").read_text()
craft = (BASE_DIR / "CRAFT.md").read_text()
voice_part2 = voice_identity(voice)

prompt = f"""Build CHARACTERS.MD for this novel.

This is the definitive reference for who exists in the story, what drives them, how they speak,
what they hide, and how their choices collide. Use the seed's named people and roles exactly.
Infer any additional cast the story needs from the world bible and structural promise.

SEED CONCEPT:
{seed}

WORLD BIBLE:
{world}

VOICE IDENTITY:
{voice_part2}

CRAFT REFERENCE:
{craft}

CHARACTER CRAFT REQUIREMENTS:

## Core Cast
Include the protagonist, the people named in the seed, key mission or institutional figures,
public-facing antagonistic forces, intimate relationships, and 3-5 additional characters who
make the premise social rather than abstract.

## For Each Major Character
- Name, age or life stage, role, occupation, and social position
- Ghost / wound / want / need / lie chain
- Proactivity, likability, and competence sliders with justification
- Arc type and arc trajectory
- External goal and private fear
- Relationship web: who they need, resent, protect, use, or misunderstand
- Secrets, withheld knowledge, and what would change if revealed
- Speech pattern across vocabulary, sentence length, formality, evasions, metaphor domain,
  directness, interruptions, and sample lines
- Physical presence, habits, tells, and stress behaviors
- Thematic function: what question this person forces the book to answer

## For Secondary and Collective Characters
Include shorter entries for voices that represent institutions, movements, families, publics,
media, markets, belief systems, and ordinary people affected by the premise.

IMPORTANT:
- Character conflicts must grow from competing needs, not cartoon villainy.
- The protagonist's lie should be challenged by multiple people in different ways.
- Give every major person a reason to believe they are doing something necessary.
- Tie speech, habit, and worldview to job, grief, class, training, and pressure.
- Do not solve the premise through a single mouthpiece. Keep uncertainty alive.
- Target roughly 3000-4000 dense words.
"""

print("Calling writer model...", file=sys.stderr)
result = call_writer(prompt)
print(result)
