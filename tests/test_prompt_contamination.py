import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import draft_chapter
import gen_revision

ROOT = Path(__file__).resolve().parents[1]

PRIOR_PROJECT_SENTINELS = [
    r"PRIOR_PROJECT_PROTAGONIST",
    r"PRIOR_PROJECT_CITY",
    r"PRIOR_PROJECT_FACTION",
    r"PRIOR_PROJECT_TITLE",
    r"PRIOR_PROJECT_MAGIC_RULE",
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


class PromptContaminationTests(unittest.TestCase):
    def test_runtime_prompt_files_do_not_hardcode_prior_project_sentinels(self):
        offenders = []
        for rel in PROMPT_FILES:
            text = (ROOT / rel).read_text(encoding="utf-8")
            for pattern in PRIOR_PROJECT_SENTINELS:
                if re.search(pattern, text):
                    offenders.append(f"{rel}: {pattern}")

        self.assertEqual(offenders, [])

    def test_draft_chapter_prompt_uses_current_seed_and_outline_not_prior_project(self):
        prompts = []

        def fake_call_writer(prompt, max_tokens=16000):
            prompts.append(prompt)
            return "# Chapter One\n\nAri watched the river break against the locked bridge."

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "chapters").mkdir()
            (root / "seed.txt").write_text("TITLE: River Ledger\n", encoding="utf-8")
            (root / "voice.md").write_text("precise, intimate, human-scale", encoding="utf-8")
            (root / "world.md").write_text("The city is divided by a winter river.", encoding="utf-8")
            (root / "characters.md").write_text("Ari Vale is the focal investigator.", encoding="utf-8")
            (root / "canon.md").write_text("- The north bridge is locked.\n", encoding="utf-8")
            (root / "book_profile.md").write_text(
                "# Book Prompt Profile: River Ledger\n"
                "Use only the current foundation. Do not invent nicknames.\n",
                encoding="utf-8",
            )
            (root / "outline.md").write_text(
                "# OUTLINE.MD: River Ledger\n\n"
                "### Ch 1: The Locked Bridge\n"
                "- **POV / focal consciousness:** Ari, because they stand between grief and public interpretation.\n"
                "- **Beats:**\n  - Ari stands in the archive hall.\n"
                "### Ch 2: Next\n",
                encoding="utf-8",
            )

            with patch.object(draft_chapter, "BASE_DIR", root), \
                 patch.object(draft_chapter, "CHAPTERS_DIR", root / "chapters"), \
                 patch.object(draft_chapter, "call_writer", side_effect=fake_call_writer), \
                 patch("sys.argv", ["draft_chapter.py", "1"]):
                draft_chapter.main()

        prompt = prompts[0]
        self.assertIn("River Ledger", prompt)
        self.assertIn("Ari", prompt)
        for pattern in PRIOR_PROJECT_SENTINELS:
            self.assertIsNone(re.search(pattern, prompt), f"prompt leaked {pattern}")

    def test_drafting_requires_generated_book_profile(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "chapters").mkdir()
            (root / "seed.txt").write_text("TITLE: River Ledger\n", encoding="utf-8")
            (root / "voice.md").write_text("voice", encoding="utf-8")
            (root / "world.md").write_text("world", encoding="utf-8")
            (root / "characters.md").write_text("Ari", encoding="utf-8")
            (root / "canon.md").write_text("canon", encoding="utf-8")
            (root / "outline.md").write_text("### Ch 1: Opening\n- **POV:** Ari\n", encoding="utf-8")

            with patch.object(draft_chapter, "BASE_DIR", root), \
                 patch.object(draft_chapter, "CHAPTERS_DIR", root / "chapters"), \
                 patch("sys.argv", ["draft_chapter.py", "1"]), \
                 self.assertRaises(FileNotFoundError):
                draft_chapter.main()

    def test_revision_prompt_uses_current_seed_and_profile_not_prior_project(self):
        prompts = []

        def fake_call_writer(prompt, max_tokens=16000):
            prompts.append(prompt)
            return "# Revised\n"

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            chapters = root / "chapters"
            chapters.mkdir()
            (root / "seed.txt").write_text("TITLE: River Ledger\n", encoding="utf-8")
            (root / "voice.md").write_text("voice", encoding="utf-8")
            (root / "characters.md").write_text("Ari Vale", encoding="utf-8")
            (root / "world.md").write_text("The city waits for the winter hearing.", encoding="utf-8")
            (root / "book_profile.md").write_text(
                "# Book Prompt Profile: River Ledger\nStay with Ari and the archive.\n",
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
        self.assertIn("River Ledger", prompt)
        self.assertIn("Book Prompt Profile", prompt)
        for pattern in PRIOR_PROJECT_SENTINELS:
            self.assertIsNone(re.search(pattern, prompt), f"prompt leaked {pattern}")


if __name__ == "__main__":
    unittest.main()
