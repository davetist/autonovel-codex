import unittest

import editorial_policy


class EditorialPolicyTests(unittest.TestCase):
    def test_strong_novel_with_concentrated_panel_heat_chooses_surgical_revision(self):
        targets = [
            {"chapter": 23, "score": 39.4, "primary_issue": "missing_scene", "question": "missing_scene"},
            {"chapter": 16, "score": 18.95, "primary_issue": "worst_scene", "question": "worst_scene"},
            {"chapter": 13, "score": 16.65, "primary_issue": "cut_candidate", "question": "cut_candidate"},
        ]
        state = {"phase": "revision", "novel_score": 9.3, "revision_cycle": 1}

        decision = editorial_policy.choose_revision_strategy(state, targets, has_reader_panel=True)

        self.assertEqual(decision["mode"], "surgical_revision")
        self.assertEqual(decision["target_chapters"], [23, 16, 13])
        self.assertTrue(decision["skip_broad_adversarial_pass"])
        self.assertTrue(decision["rerun_reader_panel_after"])
        self.assertIn("concentrated", decision["rationale"])

    def test_low_scoring_novel_uses_broad_revision_even_with_panel_targets(self):
        targets = [{"chapter": 23, "score": 39.4, "primary_issue": "missing_scene"}]
        state = {"phase": "revision", "novel_score": 7.8, "revision_cycle": 0}

        decision = editorial_policy.choose_revision_strategy(state, targets, has_reader_panel=True)

        self.assertEqual(decision["mode"], "broad_revision")
        self.assertFalse(decision["skip_broad_adversarial_pass"])
        self.assertEqual(decision["target_chapters"], [])

    def test_strong_novel_without_panel_heat_moves_to_export_after_revision_cycle(self):
        state = {"phase": "revision", "novel_score": 9.25, "revision_cycle": 1}

        decision = editorial_policy.choose_revision_strategy(state, [], has_reader_panel=True)

        self.assertEqual(decision["mode"], "export")
        self.assertEqual(decision["target_chapters"], [])
        self.assertIn("no material panel heat", decision["rationale"])

    def test_missing_reader_panel_runs_broad_revision_to_create_fresh_signal(self):
        state = {"phase": "revision", "novel_score": 9.25, "revision_cycle": 1}

        decision = editorial_policy.choose_revision_strategy(state, [], has_reader_panel=False)

        self.assertEqual(decision["mode"], "broad_revision")
        self.assertIn("reader panel", decision["rationale"])

    def test_accepts_surgical_pass_only_when_full_score_holds(self):
        keep = editorial_policy.evaluate_surgical_cycle_outcome(previous_score=9.3, new_score=9.25)
        discard = editorial_policy.evaluate_surgical_cycle_outcome(previous_score=9.3, new_score=9.0)

        self.assertEqual(keep["action"], "keep")
        self.assertEqual(discard["action"], "review_or_revert")
        self.assertIn("dropped", discard["rationale"])


if __name__ == "__main__":
    unittest.main()
