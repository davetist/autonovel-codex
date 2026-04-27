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
            canon.write_text("# Canon\n\n## Existing\n- The river freezes each winter.\n", encoding="utf-8")
            eval_log = base / "ch01.json"
            eval_log.write_text(json.dumps({
                "overall_score": 8.0,
                "new_canon_entries": [
                    "The archive uses a delayed public feed during council segments.",
                    "Liora states that her vow is private and not civic protocol.",
                ],
            }), encoding="utf-8")

            added = append_new_canon_entries_from_eval(base, chapter=1, eval_log=eval_log)

            self.assertEqual(added, 2)
            updated = canon.read_text(encoding="utf-8")
            self.assertIn("## Post-Draft Canon Addendum", updated)
            self.assertIn("### Chapter 1", updated)
            self.assertIn("- The archive uses a delayed public feed during council segments. *(ch01 eval)*", updated)
            self.assertIn("- Liora states that her vow is private and not civic protocol. *(ch01 eval)*", updated)

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
                    "Ren flags a clock offset before the hearing.",
                ],
            }), encoding="utf-8")

            added = append_new_canon_entries_from_eval(base, chapter=2, eval_log=eval_log)

            self.assertEqual(added, 1)
            updated = canon.read_text(encoding="utf-8")
            self.assertEqual(updated.count("orange peel"), 1)
            self.assertIn("- Ren flags a clock offset before the hearing. *(ch02 eval)*", updated)

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
                "new_canon_entries": ["Tamsin labels Ori 'symbolically necessary.'."],
            }), encoding="utf-8")

            append_new_canon_entries_from_eval(base, chapter=4, eval_log=eval_log)

            updated = canon.read_text(encoding="utf-8")
            self.assertIn("- Tamsin labels Ori 'symbolically necessary.' *(ch04 eval)*", updated)
            self.assertNotIn(".'.", updated)


if __name__ == "__main__":
    unittest.main()
