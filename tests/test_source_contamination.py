import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import draft_chapter
import gen_revision

ROOT = Path(__file__).resolve().parents[1]

SOURCE_NOVEL_TOKENS = [
    r"\bCass\b",
    r"Bellwright",
    r"Cantamura",
    r"House of Bells",
    r"House of Corda",
    r"Second Son",
    r"under-note",
    r"quarter-tone",
    r"F-sharp",
    r"Eddan",
    r"Perin",
    r"Lenne",
    r"Torvald",
]

PROMPT_FILES = [
    "book_profile.py",
    "gen_book_profile.py",
    "draft_chapter.py",
    "gen_revision.py",
    "evaluate.py",
    "build_arc_summary.py",
    "reader_panel.py",
    "gen_audiobook_script.py",
    "gen_art_directions.py",
    "gen_cover_composite.py",
    "gen_cover_print.py",
    "typeset/build_tex.py",
]


class SourceNovelContaminationTests(unittest.TestCase):
    def test_runtime_prompt_files_do_not_hardcode_source_novel_tokens(self):
        offenders = []
        for rel in PROMPT_FILES:
            text = (ROOT / rel).read_text(encoding="utf-8")
            for pattern in SOURCE_NOVEL_TOKENS:
                if re.search(pattern, text):
                    offenders.append(f"{rel}: {pattern}")

        self.assertEqual(offenders, [])

    def test_draft_chapter_prompt_uses_current_seed_and_outline_not_source_novel(self):
        prompts = []

        def fake_call_writer(prompt, max_tokens=16000):
            prompts.append(prompt)
            return "# Chapter One\n\nMara watched Mars through the glass."

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "chapters").mkdir()
            (root / "seed.txt").write_text("TITLE: The Boundary Condition\n", encoding="utf-8")
            (root / "voice.md").write_text("clinical, intimate, human-scale", encoding="utf-8")
            (root / "world.md").write_text("Mars is visible but unreachable.", encoding="utf-8")
            (root / "characters.md").write_text("Mara Venn is the focal interpreter.", encoding="utf-8")
            (root / "canon.md").write_text("- Asterion vanished.\n", encoding="utf-8")
            (root / "book_profile.md").write_text(
                "# Book Prompt Profile: The Boundary Condition\n"
                "Use only the current foundation. Do not invent nicknames.\n",
                encoding="utf-8",
            )
            (root / "outline.md").write_text(
                "# OUTLINE.MD: The Boundary Condition\n\n"
                "### Ch 1: The Paused Frame\n"
                "- **POV / focal consciousness:** Mara, because she stands between grief and public interpretation.\n"
                "- **Beats:**\n  - Mara stands in a Glass Room.\n"
                "### Ch 2: Next\n",
                encoding="utf-8",
            )

            with patch.object(draft_chapter, "BASE_DIR", root), \
                 patch.object(draft_chapter, "CHAPTERS_DIR", root / "chapters"), \
                 patch.object(draft_chapter, "call_writer", side_effect=fake_call_writer), \
                 patch("sys.argv", ["draft_chapter.py", "1"]):
                draft_chapter.main()

        prompt = prompts[0]
        self.assertIn("The Boundary Condition", prompt)
        self.assertIn("Mara", prompt)
        for pattern in SOURCE_NOVEL_TOKENS:
            self.assertIsNone(re.search(pattern, prompt), f"prompt leaked {pattern}")

    def test_drafting_requires_generated_book_profile(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "chapters").mkdir()
            (root / "seed.txt").write_text("TITLE: The Boundary Condition\n", encoding="utf-8")
            (root / "voice.md").write_text("voice", encoding="utf-8")
            (root / "world.md").write_text("world", encoding="utf-8")
            (root / "characters.md").write_text("Mara", encoding="utf-8")
            (root / "canon.md").write_text("canon", encoding="utf-8")
            (root / "outline.md").write_text("### Ch 1: Opening\n- **POV:** Mara\n", encoding="utf-8")

            with patch.object(draft_chapter, "BASE_DIR", root), \
                 patch.object(draft_chapter, "CHAPTERS_DIR", root / "chapters"), \
                 patch("sys.argv", ["draft_chapter.py", "1"]), \
                 self.assertRaises(FileNotFoundError):
                draft_chapter.main()

    def test_revision_prompt_uses_current_seed_and_profile_not_source_novel(self):
        prompts = []

        def fake_call_writer(prompt, max_tokens=16000):
            prompts.append(prompt)
            return "# Revised\n"

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            chapters = root / "chapters"
            chapters.mkdir()
            (root / "seed.txt").write_text("TITLE: The Boundary Condition\n", encoding="utf-8")
            (root / "voice.md").write_text("voice", encoding="utf-8")
            (root / "characters.md").write_text("Mara Venn", encoding="utf-8")
            (root / "world.md").write_text("Witness approaches the Boundary.", encoding="utf-8")
            (root / "book_profile.md").write_text(
                "# Book Prompt Profile: The Boundary Condition\nStay with Mara and Witness.\n",
                encoding="utf-8",
            )
            (chapters / "ch_01.md").write_text("old draft", encoding="utf-8")
            brief = root / "brief.md"
            brief.write_text("Tighten ambiguity.", encoding="utf-8")

            with patch.object(gen_revision, "BASE_DIR", root), \
                 patch.object(gen_revision, "call_writer", side_effect=fake_call_writer), \
                 patch("sys.argv", ["gen_revision.py", "1", str(brief)]):
                gen_revision.main()

        prompt = prompts[0]
        self.assertIn("The Boundary Condition", prompt)
        self.assertIn("Book Prompt Profile", prompt)
        for pattern in SOURCE_NOVEL_TOKENS:
            self.assertIsNone(re.search(pattern, prompt), f"prompt leaked {pattern}")


if __name__ == "__main__":
    unittest.main()
