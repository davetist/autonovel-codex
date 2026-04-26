#!/usr/bin/env python3
"""Normalize chapter headings without rewriting chapter prose.

This is an export-hygiene pass. It rewrites only the chapter heading line
and the blank-line boundary immediately after it. If a chapter starts straight
with body prose, it prepends a safe ``## Chapter N`` heading and preserves the
original first line as body.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CHAPTERS_DIR = BASE_DIR / "chapters"


@dataclass
class ChapterTitleResult:
    path: Path
    chapter_number: int
    original_heading: str
    normalized_heading: str
    changed: bool
    inserted_heading: bool = False
    reason: str = ""


@dataclass
class ChapterTitleReport:
    results: list[ChapterTitleResult]
    write: bool = False
    check: bool = False

    @property
    def changed_count(self) -> int:
        return sum(1 for result in self.results if result.changed)

    @property
    def inserted_count(self) -> int:
        return sum(1 for result in self.results if result.inserted_heading)

    @property
    def exit_code(self) -> int:
        return 1 if self.check and self.changed_count else 0


_HEADING_PATTERNS = [
    # ## Chapter 12: Some Title / CHAPTER 12: SOME TITLE / ### Chapter 12
    re.compile(r"^(?:#{1,6}\s*)?chapter\s+(?P<num>\d+)\s*(?::|[-–—])?\s*(?P<title>.*)$", re.I),
    # 12. Some Title / ## 12. Some Title
    re.compile(r"^(?:#{1,6}\s*)?(?P<num>\d+)\.\s*(?P<title>.+)$"),
]

_MD_TITLE_WITHOUT_NUMBER = re.compile(r"^#{1,6}\s+(?P<title>.+)$")

_SMALL_WORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "but",
    "by",
    "for",
    "from",
    "in",
    "nor",
    "of",
    "on",
    "or",
    "per",
    "the",
    "to",
    "vs",
    "via",
    "with",
    "yet",
}


def chapter_number_from_path(path: Path) -> int:
    match = re.search(r"ch_(\d+)", path.name, re.I)
    if not match:
        raise ValueError(f"Cannot infer chapter number from {path.name!r}")
    return int(match.group(1))


def title_case(title: str) -> str:
    """Return readable title case while preserving intentional acronyms."""
    title = " ".join(title.strip().split())
    if not title:
        return ""

    parts = re.split(r"(\s+)", title)
    word_indexes = [i for i, part in enumerate(parts) if part.strip()]
    if not word_indexes:
        return title

    first_word = word_indexes[0]
    last_word = word_indexes[-1]

    def convert_token(token: str, *, force: bool) -> str:
        # Keep bracketed/source labels and mixed-case technical tokens alone.
        if token.startswith("[") and token.endswith("]"):
            return token
        if re.search(r"[A-Z][a-z].*[A-Z]|[a-z].*[A-Z]", token):
            return token

        leading = re.match(r"^\W*", token).group(0)
        trailing = re.search(r"\W*$", token).group(0)
        core = token[len(leading): len(token) - len(trailing) if trailing else len(token)]
        if not core:
            return token

        lower = core.lower()
        if not force and lower in _SMALL_WORDS:
            converted = lower
        elif core.isupper() and len(core) <= 4 and lower not in _SMALL_WORDS:
            converted = core
        elif "-" in core:
            converted = "-".join(
                part[:1].upper() + part[1:].lower() if part else part
                for part in core.split("-")
            )
        else:
            converted = lower[:1].upper() + lower[1:]
        return f"{leading}{converted}{trailing}"

    converted_parts = []
    for index, part in enumerate(parts):
        if not part.strip():
            converted_parts.append(part)
            continue
        converted_parts.append(convert_token(part, force=index in {first_word, last_word}))
    return "".join(converted_parts)


def first_nonempty_line(lines: list[str]) -> tuple[int | None, str]:
    for index, line in enumerate(lines):
        if line.strip():
            return index, line.strip()
    return None, ""


def parse_existing_heading(line: str, expected_chapter: int) -> tuple[str | None, str]:
    stripped = line.strip()
    for pattern in _HEADING_PATTERNS:
        match = pattern.match(stripped)
        if not match:
            continue
        parsed_number = int(match.group("num"))
        title = title_case(match.group("title") or "")
        if parsed_number != expected_chapter:
            # Keep the file's chapter number as the source of truth and flag it
            # by normalizing to the filename. The report still shows original.
            parsed_number = expected_chapter
        heading = f"## Chapter {parsed_number}"
        if title:
            heading += f": {title}"
        return heading, "normalized existing chapter heading"

    md_match = _MD_TITLE_WITHOUT_NUMBER.match(stripped)
    if md_match:
        title = title_case(md_match.group("title"))
        return f"## Chapter {expected_chapter}: {title}", "added chapter number to markdown heading"

    return None, "inserted missing chapter heading"


def rebuild_chapter_text(
    lines: list[str],
    first_index: int | None,
    normalized_heading: str,
    *,
    inserted_heading: bool,
) -> str:
    if first_index is None:
        return normalized_heading + "\n"

    if inserted_heading:
        body_lines = lines[first_index:]
    else:
        body_start = first_index + 1
        while body_start < len(lines) and not lines[body_start].strip():
            body_start += 1
        body_lines = lines[body_start:]

    body = "\n".join(body_lines).strip("\n")
    if body:
        return f"{normalized_heading}\n\n{body}\n"
    return normalized_heading + "\n"


def normalize_chapter_file(path: Path, *, write: bool = False) -> ChapterTitleResult:
    chapter_number = chapter_number_from_path(path)
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    first_index, first_line = first_nonempty_line(lines)

    if first_index is None:
        normalized_heading = f"## Chapter {chapter_number}"
        new_text = normalized_heading + "\n"
        result = ChapterTitleResult(
            path=path,
            chapter_number=chapter_number,
            original_heading="",
            normalized_heading=normalized_heading,
            changed=text != new_text,
            inserted_heading=True,
            reason="inserted missing chapter heading in empty chapter file",
        )
    else:
        parsed_heading, reason = parse_existing_heading(first_line, chapter_number)
        inserted = parsed_heading is None
        normalized_heading = parsed_heading or f"## Chapter {chapter_number}"
        new_text = rebuild_chapter_text(
            lines,
            first_index,
            normalized_heading,
            inserted_heading=inserted,
        )
        result = ChapterTitleResult(
            path=path,
            chapter_number=chapter_number,
            original_heading=first_line,
            normalized_heading=normalized_heading,
            changed=text != new_text,
            inserted_heading=inserted,
            reason=reason,
        )

    if write and result.changed:
        path.write_text(new_text, encoding="utf-8")
    return result


def normalize_chapters(
    chapters_dir: Path = DEFAULT_CHAPTERS_DIR,
    *,
    write: bool = False,
    check: bool = False,
) -> ChapterTitleReport:
    paths = sorted(chapters_dir.glob("ch_*.md"))
    results = [normalize_chapter_file(path, write=write) for path in paths]
    return ChapterTitleReport(results=results, write=write, check=check)


def print_report(report: ChapterTitleReport) -> None:
    mode = "check" if report.check else "write" if report.write else "dry-run"
    print(f"Chapter title normalization ({mode})")
    print(f"Scanned: {len(report.results)} chapter files")
    print(f"Changes needed: {report.changed_count}")
    print(f"Missing headings inserted: {report.inserted_count}")
    print()

    for result in report.results:
        marker = "CHANGE" if result.changed else "ok"
        inserted = " inserted" if result.inserted_heading else ""
        print(
            f"{marker:6} {result.path.name}: "
            f"{result.original_heading or '<empty>'!r} -> "
            f"{result.normalized_heading!r}"
            f" ({result.reason}{inserted})"
        )

    if report.check and report.changed_count:
        print("\nCheck failed: run `uv run python normalize_chapter_titles.py --write` before export.")
    elif not report.write and report.changed_count:
        print("\nDry run only: add `--write` to update headings.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Normalize chapter headings without rewriting body prose.",
    )
    parser.add_argument(
        "--chapters-dir",
        type=Path,
        default=DEFAULT_CHAPTERS_DIR,
        help="Directory containing ch_*.md files (default: ./chapters)",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Rewrite chapter files. Default is dry-run inventory only.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if any chapter heading would change.",
    )
    args = parser.parse_args(argv)

    if args.write and args.check:
        parser.error("--write and --check are mutually exclusive")
    if not args.chapters_dir.exists():
        parser.error(f"chapters directory does not exist: {args.chapters_dir}")

    report = normalize_chapters(args.chapters_dir, write=args.write, check=args.check)
    print_report(report)
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
