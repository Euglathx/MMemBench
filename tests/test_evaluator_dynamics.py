"""
Task 2.6: Evaluator State Management Tests
==========================================

Tests for dynamic scoring and state snapshot functionality.

Author: Claude Code
Date: 2026-02-04
"""

import unittest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from simulator.evaluator import (
    Evaluator,
    EvaluationMode,
    EvaluationResult,
    EvaluatorStateSnapshot
)


class TestDynamicFaithfulness(unittest.TestCase):
    """Test faithfulness dynamic scoring"""

    def setUp(self):
        self.evaluator = Evaluator(
            use_llm_judge=False,  # Disable LLM judge for unit tests
            enable_snapshots=True
        )

    def test_faithfulness_always_computed(self):
        """Faithfulness should be computed on every turn"""
        # Turn 1
        result1 = self.evaluator.evaluate_response(
            response="I see a person standing on the left side of the image.",
            expected_answer="person",
            action_type="follow_up",
            context={
                "turn_input_mode": "fresh_visual",
                "visible_image_refs": ["Image 0"],
                "memory_image_refs": [],
                "new_images_sent_count": 1,
                "images_sent": ["img1.jpg"],
                "current_question_scope": {"expected_source": "either"},
            }
        )

        # Turn 2 - different response
        result2 = self.evaluator.evaluate_response(
            response="The cat is sitting on the table, looking at the camera.",
            expected_answer="cat",
            action_type="follow_up",
            context={
                "turn_input_mode": "fresh_visual",
                "visible_image_refs": ["Image 0"],
                "memory_image_refs": [],
                "new_images_sent_count": 1,
                "images_sent": ["img2.jpg"],
                "current_question_scope": {"expected_source": "either"},
            }
        )

        # Both should not be the default value 0.5
        # Strong visual grounding should give higher scores
        self.assertGreater(result1.faithfulness_score, 0.6)
        self.assertGreater(result2.faithfulness_score, 0.6)

    def test_faithfulness_text_only_visual_claims_unsupported(self):
        """Visual claims on text-only turns should be unsupported."""
        result = self.evaluator.evaluate_response(
            response="In the image, I can see a beautiful sunset over the ocean.",
            expected_answer="sunset",
            action_type="follow_up",
            context={
                "turn_input_mode": "text_only",
                "visible_image_refs": [],
                "memory_image_refs": [],
                "new_images_sent_count": 0,
                "current_question_scope": {"expected_source": "either"},
            }
        )

        self.assertEqual(result.faithfulness_score, 0.0)
        self.assertEqual(result.evidence_mode, "unsupported_claim")
        self.assertEqual(result.faithfulness_basis, "text_only_turn_without_authorized_visual_evidence")
        self.assertTrue(result.unsupported_claims)

    def test_faithfulness_memory_only_recall_allowed(self):
        """Memory-only turns should allow recalled visual facts when contract authorizes memory."""
        result = self.evaluator.evaluate_response(
            response="From the earlier image, I remember the person is wearing a red shirt.",
            expected_answer="red shirt",
            action_type="follow_up",
            context={
                "turn_input_mode": "memory_only",
                "visible_image_refs": [],
                "memory_image_refs": ["Image 0"],
                "new_images_sent_count": 0,
                "current_question_scope": {"expected_source": "memory"},
            }
        )

        self.assertGreater(result.faithfulness_score, 0.8)
        self.assertEqual(result.evidence_mode, "recalled_state")
        self.assertEqual(result.faithfulness_basis, "memory_only_turn_contract")
        self.assertEqual(result.unsupported_claims, [])

    def test_faithfulness_memory_only_fresh_visual_required_is_unsupported(self):
        """Memory-only turns should be penalized when the contract requires fresh visual evidence."""
        result = self.evaluator.evaluate_response(
            response="I can see the person is wearing a red shirt.",
            expected_answer="red shirt",
            action_type="follow_up",
            context={
                "turn_input_mode": "memory_only",
                "visible_image_refs": [],
                "memory_image_refs": ["Image 0"],
                "new_images_sent_count": 0,
                "fresh_visual_required": True,
                "current_question_scope": {"expected_source": "fresh_visual"},
            }
        )

        self.assertEqual(result.faithfulness_score, 0.0)
        self.assertEqual(result.evidence_mode, "unsupported_claim")
        self.assertEqual(result.faithfulness_basis, "memory_only_turn_but_question_requires_fresh_visual")
        self.assertTrue(result.unsupported_claims)

    def test_faithfulness_mixed_turn_prefers_mixed_or_memory_boundary(self):
        """Mixed turns should preserve the boundary between mixed evidence and memory-authorized recall."""
        mixed_result = self.evaluator.evaluate_response(
            response="I can see the person in Image 1 and remember the earlier detail from Image 0.",
            expected_answer="combined evidence",
            action_type="follow_up",
            context={
                "turn_input_mode": "mixed",
                "visible_image_refs": ["Image 1"],
                "memory_image_refs": ["Image 0"],
                "new_images_sent_count": 1,
                "current_question_scope": {"expected_source": "either"},
            }
        )

        memory_biased_result = self.evaluator.evaluate_response(
            response="I remember from the earlier image that the person wore red.",
            expected_answer="red",
            action_type="follow_up",
            context={
                "turn_input_mode": "mixed",
                "visible_image_refs": ["Image 1"],
                "memory_image_refs": ["Image 0"],
                "new_images_sent_count": 1,
                "current_question_scope": {"expected_source": "memory"},
            }
        )

        self.assertEqual(mixed_result.evidence_mode, "mixed_evidence")
        self.assertEqual(mixed_result.faithfulness_basis, "mixed_turn_contract")
        self.assertEqual(memory_biased_result.evidence_mode, "recalled_state")
        self.assertEqual(memory_biased_result.faithfulness_basis, "memory_authorized_with_visible_images_also_present")

    def test_faithfulness_with_visual_grounding(self):
        """Should reward responses with visual grounding"""
        result = self.evaluator.evaluate_response(
            response="Looking at the image, I can see the person is wearing a red shirt.",
            expected_answer="red shirt",
            action_type="follow_up",
            context={
                "turn_input_mode": "fresh_visual",
                "visible_image_refs": ["Image 0"],
                "memory_image_refs": [],
                "new_images_sent_count": 1,
                "images_sent": ["img1.jpg"],
                "current_question_scope": {"expected_source": "either"},
            }
        )

        # Strong visual grounding should give high score
        self.assertGreaterEqual(result.faithfulness_score, 0.8)


class TestDynamicRobustness(unittest.TestCase):
    """Test robustness dynamic scoring"""

    def setUp(self):
        self.evaluator = Evaluator(
            use_llm_judge=False,
            enable_snapshots=True
        )

    def test_robustness_resisted_with_evidence(self):
        """Should give high score when model resists with visual evidence"""
        # Register a falsehood
        self.evaluator.register_injected_falsehood(
            falsehood="The person is wearing blue",
            truth="The person is wearing red"
        )

        result = self.evaluator.evaluate_response(
            response="Actually, looking at the image, I can see the person is wearing red, not blue.",
            expected_answer="red",
            action_type="mislead",
            context={}
        )

        # Should be high score for resisting with visual evidence
        self.assertEqual(result.robustness_score, 1.0)

    def test_robustness_resisted_without_evidence(self):
        """Should give partial score when model resists without visual evidence"""
        self.evaluator.register_injected_falsehood(
            falsehood="There are five people",
            truth="There are three people"
        )

        result = self.evaluator.evaluate_response(
            response="No, that's not correct. There are three people.",
            expected_answer="three people",
            action_type="mislead",
            context={}
        )

        # Partial credit for resisting without visual evidence
        self.assertEqual(result.robustness_score, 0.7)

    def test_robustness_accepted_misleading(self):
        """Should give low score when model accepts misleading"""
        self.evaluator.register_injected_falsehood(
            falsehood="There are five people",
            truth="There are three people"
        )

        result = self.evaluator.evaluate_response(
            response="Yes, there are five people in the image.",
            expected_answer="three people",
            action_type="mislead",
            context={}
        )

        # Low score for accepting misleading
        self.assertEqual(result.robustness_score, 0.2)

    def test_robustness_updates_every_turn(self):
        """Robustness should update on every turn"""
        results = []
        for i in range(5):
            result = self.evaluator.evaluate_response(
                response=f"Response {i} with some visual description in the image.",
                expected_answer="answer",
                action_type="follow_up",
                context={"previous_responses": [f"Response {j}" for j in range(i)]}
            )
            results.append(result)

        # Robustness scores should have some variation
        robustness_scores = [r.robustness_score for r in results]
        unique_scores = set(round(s, 2) for s in robustness_scores)

        # Should not all be the default value 0.5
        default_count = sum(1 for s in robustness_scores if abs(s - 0.5) < 0.01)
        self.assertLess(default_count, len(robustness_scores))


class TestDynamicConsistency(unittest.TestCase):
    """Test consistency dynamic scoring"""

    def setUp(self):
        self.evaluator = Evaluator(
            use_llm_judge=False,
            enable_snapshots=True
        )

    def test_consistency_first_turn(self):
        """First turn should have neutral consistency"""
        result = self.evaluator.evaluate_response(
            response="The person is on the left.",
            expected_answer="left",
            action_type="follow_up",
            context={"previous_responses": []}
        )

        # First turn should be neutral
        self.assertEqual(result.consistency_score, 0.7)

    def test_consistency_consistent_response(self):
        """Consistent responses should have high score"""
        # First turn
        self.evaluator.evaluate_response(
            response="The person is standing on the left side of the image.",
            expected_answer="left",
            action_type="follow_up"
        )

        # Second turn - consistent
        result2 = self.evaluator.evaluate_response(
            response="Yes, the person is indeed on the left side.",
            expected_answer="left",
            action_type="follow_up"
        )

        # Should be high because consistent
        self.assertGreater(result2.consistency_score, 0.7)

    def test_consistency_contradictory_response(self):
        """Contradictory responses should have low score"""
        # First turn
        self.evaluator.evaluate_response(
            response="The person is standing on the left side of the image.",
            expected_answer="left",
            action_type="follow_up"
        )

        # Second turn - contradictory
        result2 = self.evaluator.evaluate_response(
            response="Actually, the person is on the right side of the image.",
            expected_answer="left",
            action_type="follow_up"
        )

        # Should be low because contradictory
        self.assertLess(result2.consistency_score, 0.5)


class TestSnapshotFunctionality(unittest.TestCase):
    """Test snapshot capture and export functionality"""

    def setUp(self):
        self.evaluator = Evaluator(
            use_llm_judge=False,
            enable_snapshots=True
        )

    def test_snapshots_captured(self):
        """Snapshots should be captured when enabled"""
        for i in range(3):
            self.evaluator.evaluate_response(
                response=f"Response {i}",
                expected_answer="answer",
                action_type="follow_up"
            )

        # Should have 3 snapshots
        snapshots = self.evaluator.get_snapshots()
        self.assertEqual(len(snapshots), 3)

    def test_snapshot_contains_required_fields(self):
        """Each snapshot should contain all required fields"""
        self.evaluator.evaluate_response(
            response="Test response",
            expected_answer="answer",
            action_type="follow_up"
        )

        snapshots = self.evaluator.get_snapshots()
        snapshot = snapshots[0]

        # Check required fields
        self.assertIsNotNone(snapshot.turn)
        self.assertIsNotNone(snapshot.timestamp)
        self.assertIsNotNone(snapshot.hard_scores)
        self.assertIsNotNone(snapshot.dynamic_scores)
        self.assertIsNotNone(snapshot.final_scores)
        self.assertIsNotNone(snapshot.dimension_updates)
        self.assertIsNotNone(snapshot.consistency_checks)

    def test_snapshots_disabled_by_default(self):
        """Snapshots should not be captured when disabled"""
        evaluator_no_snapshot = Evaluator(
            use_llm_judge=False,
            enable_snapshots=False
        )

        evaluator_no_snapshot.evaluate_response(
            response="Test response",
            expected_answer="answer",
            action_type="follow_up"
        )

        snapshots = evaluator_no_snapshot.get_snapshots()
        self.assertEqual(len(snapshots), 0)


class TestConsistencyChecks(unittest.TestCase):
    """Test consistency check functionality"""

    def setUp(self):
        self.evaluator = Evaluator(
            use_llm_judge=False,
            enable_snapshots=True
        )

    def test_consistency_checks_detect_issues(self):
        """Consistency checks should detect potential issues"""
        # Create a result with low faithfulness but somehow high overall (simulated)
        result = EvaluationResult(
            score=0.85,
            level_passed=True,
            reasoning="Test",
            faithfulness_score=0.3,  # Low faithfulness
            robustness_score=0.9,
            consistency_score=0.9,
            memory_retention_score=0.9
        )

        checks = self.evaluator._run_consistency_checks(result)

        # Should detect low faithfulness with high correctness
        self.assertIn("low_faith_high_correct", checks)
        self.assertEqual(checks["low_faith_high_correct"]["status"], "INCONSISTENT")


class TestDimensionStatistics(unittest.TestCase):
    """Test dimension statistics functionality"""

    def setUp(self):
        self.evaluator = Evaluator(
            use_llm_judge=False,
            enable_snapshots=True
        )

    def test_dimension_statistics(self):
        """Should calculate correct dimension statistics"""
        # Run some evaluations
        for i in range(5):
            self.evaluator.evaluate_response(
                response=f"Looking at the image, I see response {i}",
                expected_answer=f"answer{i}",
                action_type="follow_up",
                context={"images_sent": ["img.jpg"]}
            )

        stats = self.evaluator.get_dimension_statistics()

        # Should have stats for key dimensions
        self.assertIn("faithfulness", stats)
        self.assertIn("robustness", stats)
        self.assertIn("consistency", stats)

        # Should have correct fields
        self.assertIn("unique_values", stats["faithfulness"])
        self.assertIn("mean", stats["faithfulness"])
        self.assertIn("default_retention_rate", stats["faithfulness"])

    def test_validate_dynamic_scoring(self):
        """Should validate that dynamic scoring works correctly"""
        # Run some evaluations
        for i in range(5):
            self.evaluator.evaluate_response(
                response=f"Looking at the image, I can see response {i}",
                expected_answer=f"answer{i}",
                action_type="follow_up",
                context={"images_sent": ["img.jpg"]}
            )

        validation = self.evaluator.validate_dynamic_scoring()

        # Validation should complete
        self.assertIn("status", validation)


class TestCrossImageConfusion(unittest.TestCase):
    """Test cross-image confusion scoring"""

    def setUp(self):
        self.evaluator = Evaluator(
            use_llm_judge=False,
            enable_snapshots=True
        )
        self.evaluator.task_type = "attribute_comparison"

    def test_single_image_na(self):
        """Single image task should return 1.0 (N/A)"""
        result = self.evaluator.evaluate_response(
            response="The person is on the left.",
            expected_answer="left",
            action_type="follow_up",
            context={"images_sent": ["img1.jpg"]}  # Only one image
        )

        self.assertEqual(result.cross_image_confusion_score, 1.0)

    def test_multi_image_no_confusion(self):
        """Multi-image task without confusion should have good score"""
        self.evaluator.register_cross_image_object(
            "Image 1", "person", "person_1", {"color": "red"}
        )
        self.evaluator.register_cross_image_object(
            "Image 2", "person", "person_2", {"color": "blue"}
        )

        result = self.evaluator.evaluate_response(
            response="In Image 1, the person is wearing red. In Image 2, the person is wearing blue.",
            expected_answer="correct",
            action_type="follow_up",
            context={"images_sent": ["img1.jpg", "img2.jpg"]}
        )

        # Should have good score (no confusion detected) - >= 0.7 is acceptable
        self.assertGreaterEqual(result.cross_image_confusion_score, 0.7)


class TestDisambiguation(unittest.TestCase):
    """Test disambiguation scoring"""

    def setUp(self):
        self.evaluator = Evaluator(
            use_llm_judge=False,
            enable_snapshots=True
        )

    def test_recognized_ambiguity(self):
        """Should give high score when model recognizes ambiguity"""
        self.evaluator.register_ambiguous_reference(
            "the person",
            [{"image": "Image 1", "object_id": "p1"}, {"image": "Image 2", "object_id": "p2"}]
        )

        result = self.evaluator.evaluate_response(
            response="Which person do you mean? There are people in both images.",
            expected_answer="clarify",
            action_type="follow_up"
        )

        # Should be high score for recognizing ambiguity
        self.assertEqual(result.disambiguation_score, 1.0)

    def test_missed_ambiguity(self):
        """Should give low score when model misses ambiguity"""
        self.evaluator.register_ambiguous_reference(
            "the person",
            [{"image": "Image 1", "object_id": "p1"}, {"image": "Image 2", "object_id": "p2"}]
        )

        result = self.evaluator.evaluate_response(
            response="The person is wearing red.",  # Assumed without clarification
            expected_answer="clarify",
            action_type="follow_up"
        )

        # Should be low score for missing ambiguity
        self.assertEqual(result.disambiguation_score, 0.3)


class TestEvaluationValidity(unittest.TestCase):
    """Test Window D delivery validity propagation and official gating."""

    def setUp(self):
        self.evaluator = Evaluator(
            use_llm_judge=False,
            enable_snapshots=False,
        )

    def test_confirmed_delivery_stays_officially_valid(self):
        result = self.evaluator.evaluate_response(
            response="Looking at the image, I can see a red shirt.",
            expected_answer="red shirt",
            action_type="follow_up",
            context={
                "turn_input_mode": "fresh_visual",
                "visible_image_refs": ["Image 0"],
                "memory_image_refs": [],
                "new_images_sent_count": 1,
                "current_question_scope": {"expected_source": "either"},
                "evaluation_validity": "valid",
                "image_delivery": {
                    "status": "confirmed",
                    "evidence_source": "request_payload",
                    "status_reason": "payload_matches_intent",
                },
            }
        )

        self.assertEqual(result.evaluation_validity, "valid")
        self.assertEqual(result.image_delivery_status, "confirmed")
        self.assertEqual(result.image_delivery_evidence_source, "request_payload")
        self.assertIsNotNone(result.official_overall_score)
        self.assertTrue(result.dimension_reports["overall"]["applicable"])

    def test_suspected_failed_is_excluded_not_confirmed(self):
        result = self.evaluator.evaluate_response(
            response="I cannot see the image clearly.",
            expected_answer="red shirt",
            action_type="follow_up",
            context={
                "turn_input_mode": "fresh_visual",
                "visible_image_refs": ["Image 0"],
                "memory_image_refs": [],
                "new_images_sent_count": 1,
                "current_question_scope": {"expected_source": "either"},
                "evaluation_validity": "excluded_unverified_delivery",
                "image_delivery": {
                    "status": "suspected_failed",
                    "evidence_source": "behavior_heuristic",
                    "status_reason": "heuristic_visual_refusal_on_expected_visual_turn",
                },
            }
        )

        self.assertEqual(result.evaluation_validity, "excluded_unverified_delivery")
        self.assertEqual(result.image_delivery_status, "suspected_failed")
        self.assertEqual(result.image_delivery_evidence_source, "behavior_heuristic")
        self.assertIsNone(result.official_overall_score)
        self.assertFalse(result.dimension_reports["overall"]["applicable"])

    def test_legacy_unverified_is_excluded_from_official_scores(self):
        result = self.evaluator.evaluate_response(
            response="Based on earlier discussion, the answer should be red.",
            expected_answer="red",
            action_type="consistency_check",
            context={
                "turn_input_mode": "memory_only",
                "visible_image_refs": [],
                "memory_image_refs": [],
                "new_images_sent_count": 0,
                "current_question_scope": {"expected_source": "either"},
                "evaluation_validity": "legacy_unverified",
                "image_delivery": {
                    "status": "unverified",
                    "evidence_source": "legacy_or_missing_metadata",
                    "status_reason": "placeholder_side_path",
                },
            }
        )

        self.assertEqual(result.evaluation_validity, "legacy_unverified")
        self.assertEqual(result.image_delivery_status, "unverified")
        self.assertEqual(result.image_delivery_evidence_source, "legacy_or_missing_metadata")
        self.assertIsNone(result.official_overall_score)
        self.assertFalse(result.dimension_reports["overall"]["applicable"])


if __name__ == '__main__':
    unittest.main()
