#!/usr/bin/env python3
"""Generate book_profile.md once from accepted foundation documents."""
import os
from pathlib import Path
from dotenv import load_dotenv

from book_profile import book_title
from llm_client import call_llm

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")
WRITER_MODEL = os.environ.get("AUTONOVEL_WRITER_MODEL", "claude-sonnet-4-6")


def load_file(name: str) -> str:
    try:
        return (BASE_DIR / name).read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def call_writer(prompt: str, max_tokens: int = 8000) -> str:
    return call_llm(
        prompt,
        system=(
            "You create concise, book-specific prompt profiles for a reusable "
            "novel-generation pipeline. Extract only from the supplied foundation. "
            "Never import examples or details from other books. Output markdown only."
        ),
        max_tokens=max_tokens,
        temperature=0.2,
        role="writer",
        model=WRITER_MODEL,
        timeout=600,
    )


def main() -> None:
    title = book_title(BASE_DIR)
    seed = load_file("seed.txt")
    voice = load_file("voice.md")
    world = load_file("world.md")
    characters = load_file("characters.md")
    outline = load_file("outline.md")
    canon = load_file("canon.md")

    prompt = f"""Generate book_profile.md for the current novel: {title}.

This profile will be injected into every drafting, revision, evaluation, and
summary prompt. It replaces all hardcoded prompt details that belonged to an
earlier book. Be concrete, but derive every concrete item from the foundation
below.

Include these markdown sections:

# Book Prompt Profile: {title}
## Core identity
- Title
- Genre/mode/form
- Narrative tense/person/focalization rules
- What this book is centrally about

## Per-chapter drafting rules
- How to choose the POV/focal consciousness from the outline
- How to handle braided/fragments/records if present
- What the chapter must never invent outside the foundation

## Sensory and metaphor palette
- Concrete sensory wells from voice/world/characters
- Metaphor domains allowed by the book
- Domains to avoid if they are not in the foundation

## Speculative system / world rules
- The rules, costs, uncertainty boundaries, institutions, and taboos a writer must preserve

## Character and dialogue rules
- How character voices should differ
- How to avoid generic protagonist drift or nickname invention

## Evaluation priorities
- What judges should reward or penalize for this specific book

## Anti-contamination rules
- Explicitly say not to import prior-book characters, titles, settings, magic systems,
  disability/sensory gimmicks, family structures, or repeated ending patterns.
- Do not name any prior book or prior-book character. Keep this section general.

FOUNDATION:

SEED:
{seed}

VOICE:
{voice}

WORLD:
{world}

CHARACTERS:
{characters}

OUTLINE:
{outline}

CANON:
{canon}
"""

    result = call_writer(prompt).strip() + "\n"
    (BASE_DIR / "book_profile.md").write_text(result, encoding="utf-8")
    print(result)


if __name__ == "__main__":
    main()
