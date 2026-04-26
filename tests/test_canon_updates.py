import json
import tempfile
import unittest
from pathlib import Path

from canon_update import append_new_canon_entries_from_eval


class CanonUpdateTests(unittest.TestCase):
    def test_appends_new_canon_entries_from_accepted_chapter_eval(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            canon = base / "canon.md"
            canon.write_text("# Canon\n\n## Existing\n- Earth exists.\n", encoding="utf-8")
            eval_log = base / "ch01.json"
            eval_log.write_text(json.dumps({
                "overall_score": 8.0,
                "new_canon_entries": [
                    "Witness uses a delayed public feed during crew-health segments.",
                    "Leila states that her prayer is private and not mission protocol.",
                ],
            }), encoding="utf-8")

            added = append_new_canon_entries_from_eval(base, chapter=1, eval_log=eval_log)

            self.assertEqual(added, 2)
            updated = canon.read_text(encoding="utf-8")
            self.assertIn("## Post-Draft Canon Addendum", updated)
            self.assertIn("### Chapter 1", updated)
            self.assertIn("- Witness uses a delayed public feed during crew-health segments. *(ch01 eval)*", updated)
            self.assertIn("- Leila states that her prayer is private and not mission protocol. *(ch01 eval)*", updated)

    def test_does_not_duplicate_existing_entries(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            canon = base / "canon.md"
            canon.write_text(
                "# Canon\n\n## Post-Draft Canon Addendum\n\n"
                "### Chapter 2\n"
                "- The archive frame includes an orange peel. *(ch02 eval)*\n",
                encoding="utf-8",
            )
            eval_log = base / "ch02.json"
            eval_log.write_text(json.dumps({
                "overall_score": 7.0,
                "new_canon_entries": [
                    "The archive frame includes an orange peel.",
                    "Jun flags a star tracker offset before signal loss.",
                ],
            }), encoding="utf-8")

            added = append_new_canon_entries_from_eval(base, chapter=2, eval_log=eval_log)

            self.assertEqual(added, 1)
            updated = canon.read_text(encoding="utf-8")
            self.assertEqual(updated.count("orange peel"), 1)
            self.assertIn("- Jun flags a star tracker offset before signal loss. *(ch02 eval)*", updated)

    def test_ignores_empty_or_missing_new_canon_entries(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            canon = base / "canon.md"
            canon.write_text("# Canon\n", encoding="utf-8")
            eval_log = base / "ch03.json"
            eval_log.write_text(json.dumps({"overall_score": 8.0, "new_canon_entries": []}), encoding="utf-8")

            added = append_new_canon_entries_from_eval(base, chapter=3, eval_log=eval_log)

            self.assertEqual(added, 0)
            self.assertEqual(canon.read_text(encoding="utf-8"), "# Canon\n")
    def test_preserves_punctuation_inside_closing_quotes(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            canon = base / "canon.md"
            canon.write_text("# Canon\n", encoding="utf-8")
            eval_log = base / "ch04.json"
            eval_log.write_text(json.dumps({
                "new_canon_entries": ["Mara labels Mateo 'symbolically mission-critical.'."],
            }), encoding="utf-8")

            append_new_canon_entries_from_eval(base, chapter=4, eval_log=eval_log)

            updated = canon.read_text(encoding="utf-8")
            self.assertIn("- Mara labels Mateo 'symbolically mission-critical.' *(ch04 eval)*", updated)
            self.assertNotIn(".'.", updated)


if __name__ == "__main__":
    unittest.main()
