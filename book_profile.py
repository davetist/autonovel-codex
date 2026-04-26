"""Book-specific prompt profile helpers.

The pipeline must never keep reusable prompt instructions tied to the first
novel it produced.  Each book gets a generated book_profile.md after the
foundation phase; runtime generators read that profile plus the foundation
files instead of hardcoded story details.
"""
from __future__ import annotations

import re
from pathlib import Path

PROFILE_FILENAME = "book_profile.md"


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def book_title(base_dir: Path) -> str:
    """Return the current book title from seed.txt or outline.md."""
    seed = read_text(base_dir / "seed.txt")
    match = re.search(r"^\s*TITLE\s*:\s*(.+?)\s*$", seed, re.I | re.M)
    if match:
        return match.group(1).strip()

    outline = read_text(base_dir / "outline.md")
    match = re.search(r"^#\s+(?:OUTLINE\.MD\s*:\s*)?(.+?)\s*$", outline, re.I | re.M)
    if match:
        return match.group(1).strip()

    return "Untitled Novel"


def load_book_profile(base_dir: Path, *, required: bool = False) -> str:
    """Return generated book_profile.md, optionally requiring it to exist."""
    profile_path = base_dir / PROFILE_FILENAME
    profile = read_text(profile_path).strip()
    if profile:
        return profile

    if required:
        raise FileNotFoundError(
            f"{PROFILE_FILENAME} is required. Run gen_book_profile.py after the "
            "accepted foundation before drafting, revision, or evaluation."
        )

    return f"""# Book Prompt Profile: {book_title(base_dir)}

No generated book_profile.md exists yet. Use only the current seed.txt,
world.md, characters.md, outline.md, voice.md, canon.md, and adjacent
chapters. Do not import characters, titles, special powers, metaphors,
settings, family structures, disabilities, or recurring scene patterns from
any previous book or example text.
"""


def extract_chapter_focus(chapter_outline: str) -> str:
    """Extract the chapter focal consciousness/POV instruction from outline text."""
    patterns = [
        r"\*\*POV\s*/\s*focal consciousness:\*\*\s*(.+)",
        r"\*\*POV:\*\*\s*(.+)",
        r"POV\s*/\s*focal consciousness:\s*(.+)",
        r"POV:\s*(.+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, chapter_outline, re.I)
        if match:
            return match.group(1).strip()
    return "the focal consciousness specified or implied by this chapter outline"


def source_contamination_warning() -> str:
    return (
        "Use foundation-only specificity. Never import named characters, titles, "
        "settings, magic/sensory systems, illnesses, family structures, recurring "
        "endings, or metaphor wells from a previous/generated example novel."
    )
