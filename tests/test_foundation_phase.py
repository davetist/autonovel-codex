import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
