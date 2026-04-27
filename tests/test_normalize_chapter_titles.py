import tempfile
import unittest
from pathlib import Path

from normalize_chapter_titles import normalize_chapter_file, normalize_chapters


class NormalizeChapterTitlesTests(unittest.TestCase):
    def test_existing_heading_styles_normalize_to_house_style(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "ch_03.md"
            path.write_text("3. RELEASE ENVIRONMENT\n\nBody stays exactly here.\n", encoding="utf-8")

            result = normalize_chapter_file(path, write=True)

            self.assertTrue(result.changed)
            self.assertEqual(result.original_heading, "3. RELEASE ENVIRONMENT")
            self.assertEqual(result.normalized_heading, "## Chapter 3: Release Environment")
            self.assertEqual(
                path.read_text(encoding="utf-8"),
                "## Chapter 3: Release Environment\n\nBody stays exactly here.\n",
            )

    def test_missing_heading_is_prepended_without_eating_body_prose(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "ch_07.md"
            path.write_text(
                "Nadine closed the archive viewer with two fingers.\n\nSecond paragraph.\n",
                encoding="utf-8",
            )

            result = normalize_chapter_file(path, write=True)

            self.assertTrue(result.changed)
            self.assertTrue(result.inserted_heading)
            self.assertEqual(result.normalized_heading, "## Chapter 7")
            self.assertEqual(
                path.read_text(encoding="utf-8"),
                "## Chapter 7\n\nNadine closed the archive viewer with two fingers.\n\nSecond paragraph.\n",
            )

    def test_missing_heading_can_use_outline_title_without_eating_body_prose(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "ch_07.md"
            path.write_text(
                "Nadine closed the archive viewer with two fingers.\n\nSecond paragraph.\n",
                encoding="utf-8",
            )

            result = normalize_chapter_file(
                path,
                write=True,
                outline_titles={7: "Archive Narrowband"},
            )

            self.assertTrue(result.changed)
            self.assertTrue(result.inserted_heading)
            self.assertEqual(result.normalized_heading, "## Chapter 7: Archive Narrowband")
            self.assertEqual(
                path.read_text(encoding="utf-8"),
                "## Chapter 7: Archive Narrowband\n\n"
                "Nadine closed the archive viewer with two fingers.\n\nSecond paragraph.\n",
            )

    def test_outline_title_fills_existing_untitled_chapter_heading(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "ch_16.md"
            path.write_text("### Chapter 16\n\nBody.\n", encoding="utf-8")

            result = normalize_chapter_file(
                path,
                write=True,
                outline_titles={16: "Release Hearing"},
            )

            self.assertTrue(result.changed)
            self.assertEqual(result.normalized_heading, "## Chapter 16: Release Hearing")
            self.assertEqual(
                path.read_text(encoding="utf-8"),
                "## Chapter 16: Release Hearing\n\nBody.\n",
            )

    def test_dry_run_reports_changes_without_writing(self):
        with tempfile.TemporaryDirectory() as td:
            chapters = Path(td)
            (chapters / "ch_01.md").write_text("Chapter 1: First Light\n\nBody.\n", encoding="utf-8")

            report = normalize_chapters(chapters, write=False)

            self.assertEqual(report.changed_count, 1)
            self.assertEqual(
                (chapters / "ch_01.md").read_text(encoding="utf-8"),
                "Chapter 1: First Light\n\nBody.\n",
            )

    def test_check_mode_fails_when_changes_are_needed(self):
        with tempfile.TemporaryDirectory() as td:
            chapters = Path(td)
            (chapters / "ch_24.md").write_text("CHAPTER 24: NEARER STARS\n\nBody.\n", encoding="utf-8")

            report = normalize_chapters(chapters, check=True)

            self.assertEqual(report.exit_code, 1)
            self.assertEqual(report.changed_count, 1)


if __name__ == "__main__":
    unittest.main()
