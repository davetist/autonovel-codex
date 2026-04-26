import json
import tempfile
import unittest
from pathlib import Path

import run_pipeline
import gen_brief

import panel_triage


SAMPLE_PANEL = {
    "readers": {
        "editor": {
            "momentum_loss": "The novel circles itself in chapters 20, 22, and 23. Chapter 23 repeats classification debates.",
            "cut_candidate": "Cut or radically compress chapter 20 first, then use the saved space to tighten chapter 23.",
            "worst_scene": "The weakest scene is chapter 20.",
            "missing_scene": "The novel needs one direct Ruth scene after the private Elias-associated transcript is sent. It should go late in chapter 24. Chapter 23 says Ruth receives the private packet.",
        },
        "genre_reader": {
            "momentum_loss": "The book loses momentum in Chapters 14, 16, 20, and 23. Chapter 13 also slows the central line.",
            "cut_candidate": "I would first compress Chapter 13 and parts of Chapters 16 and 23.",
            "worst_scene": "The weakest scene is Chapter 16, the hearing.",
            "missing_scene": "The novel needs one direct Ruth scene after the private Elias transcript rendering is sent in Chapter 23, either near the start of Chapter 24 or as a short intercut.",
        },
        "writer": {
            "momentum_loss": "The only real sag is in the middle braid, especially Chapters 13-14.",
            "cut_candidate": "I would cut or heavily compress Chapter 13 first.",
            "worst_scene": "Chapter 13 is the weakest scene.",
            "missing_scene": "The novel needs one actual Ruth scene after the private Elias transcript rendering is sent in Chapter 23.",
        },
        "first_reader": {
            "momentum_loss": "The story loses some momentum in Chapters 16 and 23.",
            "cut_candidate": "I would cut or heavily compress Chapter 8 first.",
            "worst_scene": "The weakest scene is Chapter 16, the hearing.",
            "missing_scene": "The novel needs one private Ruth scene after the transcript reaches her, probably late in Chapter 23 or early in Chapter 24.",
        },
    },
    "disagreements": [
        {"chapter": 23, "question": "momentum_loss", "flagged_by": ["editor", "genre_reader", "first_reader"]},
        {"chapter": 13, "question": "momentum_loss", "flagged_by": ["genre_reader", "writer"]},
        {"chapter": 13, "question": "cut_candidate", "flagged_by": ["genre_reader", "writer"]},
        {"chapter": 13, "question": "worst_scene", "flagged_by": ["writer"]},
        {"chapter": 16, "question": "worst_scene", "flagged_by": ["genre_reader", "first_reader"]},
        {"chapter": 20, "question": "worst_scene", "flagged_by": ["editor"]},
    ],
}


class PanelTriageTests(unittest.TestCase):
    def test_extracts_chapter_lists_with_commas_and_and(self):
        text = "The drag appears in chapters 20, 22, and 23, then Chapter 13 returns later."
        self.assertEqual(panel_triage.extract_chapter_numbers(text), [20, 22, 23, 13])

    def test_missing_scene_anchor_ignores_backstory_chapter_mentions(self):
        text = (
            "The novel needs one direct Ruth scene after the private Elias-associated transcript is sent. "
            "It should go late in chapter 24. Ruth has been morally precise from chapter 5. "
            "Chapter 18 makes Mara's desire dangerous. Chapter 23 says Ruth receives the private packet."
        )
        self.assertEqual(panel_triage.extract_missing_scene_target_chapters(text), [23])

    def test_prioritizes_panel_consensus_over_latest_full_eval_guesswork(self):
        targets = panel_triage.rank_panel_targets(SAMPLE_PANEL, limit=4)
        self.assertEqual([target["chapter"] for target in targets[:4]], [23, 13, 16, 20])
        self.assertEqual(targets[0]["primary_issue"], "missing_scene")
        self.assertIn("Ruth", targets[0]["brief_hint"])
        self.assertIn("momentum_loss", targets[0]["issue_counts"])
        self.assertGreaterEqual(targets[1]["issue_counts"].get("worst_scene", 0), 1)

    def test_run_pipeline_parse_panel_consensus_uses_ranked_targets(self):
        with tempfile.TemporaryDirectory() as td:
            panel_path = Path(td) / "reader_panel.json"
            panel_path.write_text(json.dumps(SAMPLE_PANEL))
            items = run_pipeline.parse_panel_consensus(panel_path)

        self.assertEqual([item["chapter"] for item in items[:4]], [23, 13, 16, 20])
        self.assertEqual(items[0]["question"], "missing_scene")
        self.assertGreaterEqual(items[0]["count"], 4)
    def test_combined_brief_includes_missing_scene_feedback(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            chapters = root / "chapters"
            edit_logs = root / "edit_logs"
            eval_logs = root / "eval_logs"
            chapters.mkdir()
            edit_logs.mkdir()
            eval_logs.mkdir()
            (root / "briefs").mkdir()
            (root / "voice.md").write_text("# Voice\n")
            (chapters / "ch_23.md").write_text("## Chapter 23: What the Data Permits\n\nWords. " * 80)
            (edit_logs / "reader_panel.json").write_text(json.dumps(SAMPLE_PANEL))

            old_paths = (
                gen_brief.BASE_DIR, gen_brief.CHAPTERS_DIR, gen_brief.EDIT_LOGS_DIR,
                gen_brief.EVAL_LOGS_DIR, gen_brief.BRIEFS_DIR, gen_brief.VOICE_PATH,
            )
            try:
                gen_brief.BASE_DIR = root
                gen_brief.CHAPTERS_DIR = chapters
                gen_brief.EDIT_LOGS_DIR = edit_logs
                gen_brief.EVAL_LOGS_DIR = eval_logs
                gen_brief.BRIEFS_DIR = root / "briefs"
                gen_brief.VOICE_PATH = root / "voice.md"
                brief = gen_brief.build_combined_brief(23)
            finally:
                (
                    gen_brief.BASE_DIR, gen_brief.CHAPTERS_DIR, gen_brief.EDIT_LOGS_DIR,
                    gen_brief.EVAL_LOGS_DIR, gen_brief.BRIEFS_DIR, gen_brief.VOICE_PATH,
                ) = old_paths

        self.assertIn("[panel/missing_scene]", brief)
        self.assertIn("Ruth", brief)


if __name__ == "__main__":
    unittest.main()
