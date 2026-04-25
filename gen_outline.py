#!/usr/bin/env python3
"""Generate outline.md from seed + world + characters + mystery + craft."""
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
            "You are a novel architect for literary speculative fiction. You build outlines "
            "that preserve the seed's promise, braid external plot with interior change, and give "
            "each chapter concrete scenes, decisions, reversals, and consequences. Write clean, "
            "direct prose and avoid AI slop words."
        ),
        max_tokens=max_tokens,
        temperature=0.5,
        role="writer",
        model=WRITER_MODEL,
        timeout=600,
    )


def voice_identity(text: str) -> str:
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if "Part 2" in line:
            return "\n".join(lines[i:])
    return text


seed = (BASE_DIR / "seed.txt").read_text()
world = (BASE_DIR / "world.md").read_text()
characters = (BASE_DIR / "characters.md").read_text()
mystery = (BASE_DIR / "MYSTERY.md").read_text()
craft = (BASE_DIR / "CRAFT.md").read_text()
voice = (BASE_DIR / "voice.md").read_text()
voice_part2 = voice_identity(voice)

prompt = f"""Build OUTLINE.MD for this novel. Target 22-26 chapters and roughly 80,000 words total
unless the seed clearly calls for a different shape.

Use the seed, world, and character documents as authority. Preserve the seed's requested
structure, including any braided narrative, recovered records, public fragments, or shifts in
scale. Do not force a single-POV adventure template if the seed asks for a different form.

SEED CONCEPT:
{seed}

CENTRAL MYSTERY / AUTHOR NOTES:
{mystery}

WORLD BIBLE:
{world}

CHARACTER REGISTRY:
{characters}

VOICE:
{voice_part2}

CRAFT REFERENCE:
{craft}

BUILD THE OUTLINE WITH:

## Structural Overview
Map the acts or movements. State the escalation from inciting event to irreversible commitment,
midpoint revelation, crisis, climax, and aftermath. Explain how the public/external plot and the
protagonist's interior arc pressure each other.

## Narrative Threads
List the major threads: protagonist arc, speculative mystery, institutional or civic fallout,
relationships, recovered records or documents, and thematic argument. For each thread, state
where it opens, turns, and pays off.

## Chapter-by-Chapter Outline
For EACH chapter, provide:
### Ch N: [Title]
- **Primary mode:** present action, recovered record, public fragment, interview, log, etc.
- **POV / focal consciousness:** who carries the scene and why
- **Location:** specific place or document source
- **Structural function:** what this chapter changes in the plot
- **Emotional arc:** starting emotion → ending emotion
- **Conflict / try-fail shape:** yes-but, no-and, no-but, yes-and, or a named alternative
- **Beats:** 3-5 specific scene beats that must happen
- **New information:** what the reader learns and what remains uncertain
- **Plants:** foreshadowing elements planted or reinforced
- **Payoffs:** earlier elements paid off here
- **Character movement:** what changes in belief, relationship, leverage, or obligation
- **Theme pressure:** how the chapter tests the seed's central question
- **Approximate word count target**

## Foreshadowing Ledger
A table tracking every planted thread:
| Thread | Planted (Ch) | Reinforced (Ch) | Payoff (Ch) | Type |

Include at least 15 threads. Types may include object, image, line of dialogue, data anomaly,
public ritual, institutional action, relationship beat, structural echo, or sensory motif.

CONSTRAINTS:
- Keep the central uncertainty alive. Do not over-explain the speculative engine.
- Make the social response feel as important as the technical mystery.
- Every chapter should contain a choice, cost, discovery, reversal, or irreversible pressure.
- Quiet chapters still need tension and consequence.
- The ending should answer the human/thematic question without neatly solving the universe.
"""

print("Calling writer model...", file=sys.stderr)
result = call_writer(prompt)
print(result)
