import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import repair_foundation
import run_pipeline


class FoundationPhaseTests(unittest.TestCase):
    def test_run_foundation_writes_generator_stdout_to_layer_files_and_skips_voice_fingerprint(self):
        outputs = {
            "gen_world.py": "# Generated World\nMars is visible and unreachable.\n",
            "gen_characters.py": "# Generated Characters\nDr. Mara Venn wants the last truth.\n",
            "gen_outline.py": "# Generated Outline\n### Ch 1: The Paused Frame\n",
            "gen_outline_part2.py": "## Foreshadowing Ledger\n| Thread | Planted (Ch) | Payoff (Ch) |\n",
            "gen_canon.py": "# Generated Canon\n- Mars is unreachable. (world.md)\n",
            "evaluate.py --phase=foundation": "overall_score: 8.2\nlore_score: 8.0\n",
        }
        calls = []

        def fake_uv_run(script, timeout=600):
            calls.append(script)
            return subprocess.CompletedProcess(
                args=script,
                returncode=0,
                stdout=outputs[script],
                stderr="",
            )

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for name in ("world.md", "characters.md", "outline.md", "canon.md"):
                (root / name).write_text(f"PLACEHOLDER {name}\n")
            (root / "chapters").mkdir()
            (root / "edit_logs").mkdir()
            (root / "eval_logs").mkdir()

            with patch.object(run_pipeline, "BASE_DIR", root), \
                 patch.object(run_pipeline, "STATE_FILE", root / "state.json"), \
                 patch.object(run_pipeline, "RESULTS_FILE", root / "results.tsv"), \
                 patch.object(run_pipeline, "CHAPTERS_DIR", root / "chapters"), \
                 patch.object(run_pipeline, "EDIT_LOGS_DIR", root / "edit_logs"), \
                 patch.object(run_pipeline, "EVAL_LOGS_DIR", root / "eval_logs"), \
                 patch.object(run_pipeline, "MAX_FOUNDATION_ITERS", 1), \
                 patch.object(run_pipeline, "uv_run", side_effect=fake_uv_run), \
                 patch.object(run_pipeline, "git_add_commit", return_value="abc123"), \
                 patch.object(run_pipeline, "git_reset_hard") as reset_hard:
                state = run_pipeline.default_state()
                state = run_pipeline.run_foundation(state)

            self.assertEqual((root / "world.md").read_text(), outputs["gen_world.py"])
            self.assertEqual((root / "characters.md").read_text(), outputs["gen_characters.py"])
            self.assertEqual(
                (root / "outline.md").read_text(),
                outputs["gen_outline.py"].rstrip() + "\n\n" + outputs["gen_outline_part2.py"].lstrip(),
            )
            self.assertEqual((root / "canon.md").read_text(), outputs["gen_canon.py"])
            self.assertNotIn("voice_fingerprint.py", calls)
            reset_hard.assert_not_called()
            self.assertEqual(state["phase"], "drafting")

    def test_outline_part2_uses_project_outline_file_not_tmp_placeholder(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "gen_outline_part2.py").read_text()

        self.assertNotIn("/tmp/outline_output.md", text)
        self.assertIn("outline.md", text)

    def test_foundation_generators_do_not_pin_previous_fantasy_book(self):
        root = Path(__file__).resolve().parents[1]
        forbidden = [
            "Cass",
            "Bellwright",
            "Corda",
            "Cantamura",
            "Tonal Law",
            "The Second Son",
            "House of Bells",
            "fantasy novel",
            "Magic System",
            "Bell Tower",
        ]
        offenders = []
        for name in ("gen_world.py", "gen_characters.py", "gen_outline.py", "gen_outline_part2.py"):
            text = (root / name).read_text()
            for token in forbidden:
                if token in text:
                    offenders.append(f"{name}: {token}")

        self.assertEqual(offenders, [])

    def test_repair_output_parser_extracts_marked_file_sections(self):
        text = """
        preamble ignored
        <<<FILE: voice.md>>>
        # Voice\nSpare, clinical, wounded.\n
        <<<END FILE>>>
        <<<FILE: canon.md>>>
        # Canon\n- Asterion vanished.\n
        <<<END FILE>>>
        """

        sections = repair_foundation.parse_file_sections(text)

        self.assertEqual(set(sections), {"voice.md", "canon.md"})
        self.assertIn("Spare, clinical", sections["voice.md"])
        self.assertIn("Asterion vanished", sections["canon.md"])

    def test_foundation_after_best_score_uses_eval_guided_repair_not_random_regeneration(self):
        calls = []

        def fake_uv_run(script, timeout=600):
            calls.append(script)
            if script.startswith("repair_foundation.py --eval-log"):
                return subprocess.CompletedProcess(args=script, returncode=0, stdout="repaired\n", stderr="")
            if script == "evaluate.py --phase=foundation":
                return subprocess.CompletedProcess(
                    args=script,
                    returncode=0,
                    stdout="overall_score: 7.8\nlore_score: 7.9\neval_log: eval_logs/run2_foundation.json\n",
                    stderr="",
                )
            raise AssertionError(f"unexpected call: {script}")

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "chapters").mkdir()
            (root / "edit_logs").mkdir()
            eval_dir = root / "eval_logs"
            eval_dir.mkdir()
            eval_log = eval_dir / "run1_foundation.json"
            eval_log.write_text(json.dumps({"overall_score": 7.4, "lore_score": 7.6}))

            with patch.object(run_pipeline, "BASE_DIR", root), \
                 patch.object(run_pipeline, "STATE_FILE", root / "state.json"), \
                 patch.object(run_pipeline, "RESULTS_FILE", root / "results.tsv"), \
                 patch.object(run_pipeline, "CHAPTERS_DIR", root / "chapters"), \
                 patch.object(run_pipeline, "EDIT_LOGS_DIR", root / "edit_logs"), \
                 patch.object(run_pipeline, "EVAL_LOGS_DIR", eval_dir), \
                 patch.object(run_pipeline, "MAX_FOUNDATION_ITERS", 2), \
                 patch.object(run_pipeline, "FOUNDATION_THRESHOLD", 7.5), \
                 patch.object(run_pipeline, "uv_run", side_effect=fake_uv_run), \
                 patch.object(run_pipeline, "git_add_commit", return_value="def456"), \
                 patch.object(run_pipeline, "git_reset_hard") as reset_hard:
                state = run_pipeline.default_state()
                state["foundation_score"] = 7.4
                state["lore_score"] = 7.6
                state["foundation_eval_log"] = str(eval_log)
                state = run_pipeline.run_foundation(state)

        self.assertTrue(any(c.startswith("repair_foundation.py --eval-log") for c in calls))
        self.assertNotIn("gen_world.py", calls)
        reset_hard.assert_not_called()
        self.assertEqual(state["foundation_score"], 7.8)

    def test_foundation_recovers_best_eval_log_when_state_score_was_reset(self):
        calls = []

        def fake_uv_run(script, timeout=600):
            calls.append(script)
            if script.startswith("repair_foundation.py --eval-log"):
                return subprocess.CompletedProcess(args=script, returncode=0, stdout="repaired\n", stderr="")
            if script == "evaluate.py --phase=foundation":
                return subprocess.CompletedProcess(
                    args=script,
                    returncode=0,
                    stdout="overall_score: 7.7\nlore_score: 7.8\neval_log: eval_logs/repaired_foundation.json\n",
                    stderr="",
                )
            raise AssertionError(f"unexpected call: {script}")

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "chapters").mkdir()
            (root / "edit_logs").mkdir()
            eval_dir = root / "eval_logs"
            eval_dir.mkdir()
            eval_log = eval_dir / "run1_foundation.json"
            eval_log.write_text(json.dumps({"overall_score": 7.4, "lore_score": 7.6}))

            with patch.object(run_pipeline, "BASE_DIR", root), \
                 patch.object(run_pipeline, "STATE_FILE", root / "state.json"), \
                 patch.object(run_pipeline, "RESULTS_FILE", root / "results.tsv"), \
                 patch.object(run_pipeline, "CHAPTERS_DIR", root / "chapters"), \
                 patch.object(run_pipeline, "EDIT_LOGS_DIR", root / "edit_logs"), \
                 patch.object(run_pipeline, "EVAL_LOGS_DIR", eval_dir), \
                 patch.object(run_pipeline, "MAX_FOUNDATION_ITERS", 1), \
                 patch.object(run_pipeline, "FOUNDATION_THRESHOLD", 7.5), \
                 patch.object(run_pipeline, "uv_run", side_effect=fake_uv_run), \
                 patch.object(run_pipeline, "git_add_commit", return_value="ghi789"), \
                 patch.object(run_pipeline, "git_reset_hard"):
                state = run_pipeline.default_state()
                state = run_pipeline.run_foundation(state)

        self.assertTrue(any(c.startswith("repair_foundation.py --eval-log") for c in calls))
        self.assertNotIn("gen_world.py", calls)
        self.assertEqual(state["foundation_score"], 7.7)


if __name__ == "__main__":
    unittest.main()
