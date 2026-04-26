import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import run_pipeline


class PipelineFeedbackLoopTests(unittest.TestCase):
    def test_foundation_below_repair_band_rerolls_instead_of_repairing(self):
        calls = []
        outputs = {
            "gen_world.py": "# World\nFresh candidate.\n",
            "gen_characters.py": "# Characters\nFresh people.\n",
            "gen_outline.py": "# Outline\n### Ch 1: Start\n",
            "gen_outline_part2.py": "## Foreshadowing\n",
            "gen_canon.py": "# Canon\n- Fresh fact.\n",
            "gen_book_profile.py": "# Book Prompt Profile\nFresh current-book profile.\n",
            "evaluate.py --phase=foundation": "overall_score: 7.2\nlore_score: 7.2\neval_log: eval_logs/run2_foundation.json\n",
        }

        def fake_uv_run(script, timeout=600):
            calls.append(script)
            if script.startswith("repair_foundation.py"):
                raise AssertionError("weak foundations should be rerolled, not repaired")
            return subprocess.CompletedProcess(script, 0, outputs[script], "")

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "chapters").mkdir()
            (root / "edit_logs").mkdir()
            eval_dir = root / "eval_logs"
            eval_dir.mkdir()
            eval_log = eval_dir / "weak_foundation.json"
            eval_log.write_text(json.dumps({"overall_score": 6.9, "lore_score": 6.9}))

            with patch.object(run_pipeline, "BASE_DIR", root), \
                 patch.object(run_pipeline, "STATE_FILE", root / "state.json"), \
                 patch.object(run_pipeline, "RESULTS_FILE", root / "results.tsv"), \
                 patch.object(run_pipeline, "CHAPTERS_DIR", root / "chapters"), \
                 patch.object(run_pipeline, "EDIT_LOGS_DIR", root / "edit_logs"), \
                 patch.object(run_pipeline, "EVAL_LOGS_DIR", eval_dir), \
                 patch.object(run_pipeline, "MAX_FOUNDATION_ITERS", 1), \
                 patch.object(run_pipeline, "FOUNDATION_THRESHOLD", 7.5), \
                 patch.object(run_pipeline, "uv_run", side_effect=fake_uv_run), \
                 patch.object(run_pipeline, "git_add_commit", return_value="fresh1"), \
                 patch.object(run_pipeline, "git_reset_hard"):
                state = run_pipeline.default_state()
                state["foundation_score"] = 6.9
                state["lore_score"] = 6.9
                state["foundation_eval_log"] = str(eval_log)
                state = run_pipeline.run_foundation(state)

        self.assertIn("gen_world.py", calls)
        self.assertFalse(any(c.startswith("repair_foundation.py") for c in calls))
        self.assertEqual(state["foundation_score"], 7.2)

    def test_drafting_repairs_failed_chapter_from_eval_before_redrafting_blind(self):
        calls = []
        eval_scores = iter([5.4, 6.3])

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            chapters = root / "chapters"
            briefs = root / "briefs"
            chapters.mkdir()
            briefs.mkdir()
            (root / "edit_logs").mkdir()
            (root / "eval_logs").mkdir()

            def fake_uv_run(script, timeout=600):
                calls.append(script)
                if script == "draft_chapter.py 1":
                    (chapters / "ch_01.md").write_text("draft " * 80)
                    return subprocess.CompletedProcess(script, 0, "drafted", "")
                if script == "evaluate.py --chapter=1":
                    score = next(eval_scores)
                    return subprocess.CompletedProcess(
                        script, 0,
                        f"overall_score: {score}\neval_log: eval_logs/ch01.json\n",
                        "",
                    )
                if script.startswith("gen_revision.py 1 "):
                    (chapters / "ch_01.md").write_text("revised " * 90)
                    return subprocess.CompletedProcess(script, 0, "revised", "")
                raise AssertionError(f"unexpected uv_run call: {script}")

            def fake_run_tool(command, timeout=600, check=False):
                calls.append(command)
                if command == "uv run python gen_brief.py --eval 1":
                    (briefs / "ch01_eval.md").write_text("# Eval brief\nFix the weak chapter.\n")
                    return subprocess.CompletedProcess(command, 0, "", "")
                return subprocess.CompletedProcess(command, 0, "", "")

            with patch.object(run_pipeline, "BASE_DIR", root), \
                 patch.object(run_pipeline, "STATE_FILE", root / "state.json"), \
                 patch.object(run_pipeline, "RESULTS_FILE", root / "results.tsv"), \
                 patch.object(run_pipeline, "CHAPTERS_DIR", chapters), \
                 patch.object(run_pipeline, "BRIEFS_DIR", briefs), \
                 patch.object(run_pipeline, "EDIT_LOGS_DIR", root / "edit_logs"), \
                 patch.object(run_pipeline, "EVAL_LOGS_DIR", root / "eval_logs"), \
                 patch.object(run_pipeline, "MAX_CHAPTER_ATTEMPTS", 3), \
                 patch.object(run_pipeline, "CHAPTER_THRESHOLD", 6.0), \
                 patch.object(run_pipeline, "uv_run", side_effect=fake_uv_run), \
                 patch.object(run_pipeline, "run_tool", side_effect=fake_run_tool), \
                 patch.object(run_pipeline, "git_add_commit", return_value="ch1"):
                state = run_pipeline.default_state()
                state["chapters_total"] = 1
                state = run_pipeline.run_drafting(state)

        self.assertEqual(calls.count("draft_chapter.py 1"), 1)
        self.assertIn("uv run python gen_brief.py --eval 1", calls)
        self.assertTrue(any(str(c).startswith("gen_revision.py 1 ") for c in calls))
        self.assertEqual(state["chapters_drafted"], 1)

    def test_drafting_appends_eval_canon_entries_for_accepted_chapter(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            chapters = root / "chapters"
            eval_logs = root / "eval_logs"
            chapters.mkdir()
            eval_logs.mkdir()
            (root / "briefs").mkdir()
            (root / "edit_logs").mkdir()
            (root / "canon.md").write_text("# Canon\n\n## Existing\n- Earth exists.\n")
            eval_log = eval_logs / "ch01.json"
            eval_log.write_text(json.dumps({
                "overall_score": 7.4,
                "new_canon_entries": [
                    "Witness uses a delayed public feed during crew-health segments.",
                ],
            }))

            def fake_uv_run(script, timeout=600):
                if script == "draft_chapter.py 1":
                    (chapters / "ch_01.md").write_text("draft " * 80)
                    return subprocess.CompletedProcess(script, 0, "drafted", "")
                if script == "evaluate.py --chapter=1":
                    return subprocess.CompletedProcess(
                        script, 0,
                        "overall_score: 7.4\neval_log: eval_logs/ch01.json\n",
                        "",
                    )
                raise AssertionError(f"unexpected uv_run call: {script}")

            with patch.object(run_pipeline, "BASE_DIR", root), \
                 patch.object(run_pipeline, "STATE_FILE", root / "state.json"), \
                 patch.object(run_pipeline, "RESULTS_FILE", root / "results.tsv"), \
                 patch.object(run_pipeline, "CHAPTERS_DIR", chapters), \
                 patch.object(run_pipeline, "BRIEFS_DIR", root / "briefs"), \
                 patch.object(run_pipeline, "EDIT_LOGS_DIR", root / "edit_logs"), \
                 patch.object(run_pipeline, "EVAL_LOGS_DIR", eval_logs), \
                 patch.object(run_pipeline, "CHAPTER_THRESHOLD", 6.0), \
                 patch.object(run_pipeline, "uv_run", side_effect=fake_uv_run), \
                 patch.object(run_pipeline, "git_add_commit", return_value="ch1"):
                state = run_pipeline.default_state()
                state["chapters_total"] = 1
                run_pipeline.run_drafting(state)

            canon_text = (root / "canon.md").read_text()
            self.assertIn("## Post-Draft Canon Addendum", canon_text)
            self.assertIn("- Witness uses a delayed public feed during crew-health segments. *(ch01 eval)*", canon_text)

    def test_revision_generates_combined_briefs_not_panel_only_briefs(self):
        calls = []
        eval_scores = iter([5.8, 6.4])

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            chapters = root / "chapters"
            briefs = root / "briefs"
            edit_logs = root / "edit_logs"
            chapters.mkdir()
            briefs.mkdir()
            edit_logs.mkdir()
            (root / "eval_logs").mkdir()
            (chapters / "ch_01.md").write_text("chapter " * 100)
            (root / "gen_brief.py").write_text("# test stub\n")
            (edit_logs / "reader_panel.json").write_text(json.dumps({
                "disagreements": [{"chapter": 1, "question": "worst_scene", "flagged_by": ["r1", "r2"]}],
                "readers": {},
            }))

            def fake_uv_run(script, timeout=600):
                calls.append(script)
                if script in {"adversarial_edit.py all", "reader_panel.py"}:
                    return subprocess.CompletedProcess(script, 0, "", "")
                if script == "evaluate.py --chapter=1":
                    score = next(eval_scores)
                    return subprocess.CompletedProcess(script, 0, f"overall_score: {score}\n", "")
                if script.startswith("gen_revision.py 1 "):
                    (chapters / "ch_01.md").write_text("revised chapter " * 100)
                    return subprocess.CompletedProcess(script, 0, "", "")
                if script == "evaluate.py --full":
                    return subprocess.CompletedProcess(script, 0, "novel_score: 6.2\n", "")
                raise AssertionError(f"unexpected uv_run call: {script}")

            def fake_run_tool(command, timeout=600, check=False):
                calls.append(command)
                if command == "uv run python gen_brief.py --combined 1":
                    (briefs / "ch01_combined.md").write_text("# Combined brief\nUse panel, eval, and cuts.\n")
                    return subprocess.CompletedProcess(command, 0, "", "")
                if "gen_brief.py --panel" in command:
                    raise AssertionError("revision should not use panel-only briefs")
                return subprocess.CompletedProcess(command, 0, "", "")

            with patch.object(run_pipeline, "BASE_DIR", root), \
                 patch.object(run_pipeline, "STATE_FILE", root / "state.json"), \
                 patch.object(run_pipeline, "RESULTS_FILE", root / "results.tsv"), \
                 patch.object(run_pipeline, "CHAPTERS_DIR", chapters), \
                 patch.object(run_pipeline, "BRIEFS_DIR", briefs), \
                 patch.object(run_pipeline, "EDIT_LOGS_DIR", edit_logs), \
                 patch.object(run_pipeline, "EVAL_LOGS_DIR", root / "eval_logs"), \
                 patch.object(run_pipeline, "MIN_REVISION_CYCLES", 1), \
                 patch.object(run_pipeline, "MAX_REVISION_CYCLES", 1), \
                 patch.object(run_pipeline, "uv_run", side_effect=fake_uv_run), \
                 patch.object(run_pipeline, "run_tool", side_effect=fake_run_tool), \
                 patch.object(run_pipeline, "git_add_commit", return_value="rev1"), \
                 patch.object(run_pipeline, "git_reset_hard"):
                state = run_pipeline.default_state()
                state["phase"] = "revision"
                run_pipeline.run_revision(state, max_cycles=1)

        self.assertIn("uv run python gen_brief.py --combined 1", calls)
        self.assertFalse(any("gen_brief.py --panel" in str(c) for c in calls))


if __name__ == "__main__":
    unittest.main()
