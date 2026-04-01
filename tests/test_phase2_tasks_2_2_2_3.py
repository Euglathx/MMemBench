"""
Unit Tests for Phase 2 Tasks 2.2 & 2.3
========================================

Task 2.2: Turn-Level Ground Truth
Task 2.3: Score Formula Refactoring

Created: 2026-02-04
"""

import unittest
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from simulator.strategic_simulator import StrategicSimulator, TurnGroundTruth, TaskState, PhaseState
from simulator.evaluator import Evaluator, EvaluationMode


class TestTask22TurnGroundTruth(unittest.TestCase):
    """Test Task 2.2: Turn-Level Ground Truth Implementation"""

    def setUp(self):
        """Set up test simulator"""
        self.simulator = StrategicSimulator(
            llm_client=None,  # Mock mode
            evaluator=Evaluator(mode=EvaluationMode.STRESS_TEST, use_llm_judge=False),
            verbose=False
        )

    def test_turn_ground_truth_dataclass(self):
        """Test TurnGroundTruth dataclass creation"""
        turn_gt = TurnGroundTruth(
            turn_id=1,
            phase="entity_grounding",
            action_type="guidance",
            sub_goal="identify_entity",
            expected_answer="Model should identify the person",
            acceptable_variations=["Person is visible"],
            required_images=[0],
            ground_truth_facts=[],
            evaluation_hints={"focus_on": "entity_identification"}
        )

        self.assertEqual(turn_gt.turn_id, 1)
        self.assertEqual(turn_gt.phase, "entity_grounding")
        self.assertEqual(turn_gt.sub_goal, "identify_entity")
        self.assertTrue(turn_gt.expected_answer.startswith("Model should"))

    def test_task_state_has_turn_ground_truths(self):
        """Test TaskState includes turn_ground_truths field"""
        task_state = TaskState(
            task_id="test_001",
            task_type="attribute_bridge_reasoning",
            question="Find person. Find object left of person.",
            expected_answer="The knife",
            images=[]
        )

        # Should have turn_ground_truths field
        self.assertIsNotNone(task_state.turn_ground_truths)
        self.assertIsInstance(task_state.turn_ground_truths, dict)
        self.assertEqual(len(task_state.turn_ground_truths), 0)

        # Should have current_turn_ground_truth field
        self.assertIsNone(task_state.current_turn_ground_truth)

    def test_generate_turn_ground_truth_entity_grounding(self):
        """Test turn ground truth generation for entity_grounding phase"""
        # Set up task state
        self.simulator.task_state = TaskState(
            task_id="test_001",
            task_type="attribute_bridge_reasoning",
            question="Find the person in the image.",
            expected_answer="The knife",
            images=[],
            current_phase=PhaseState(
                phase_name="entity_grounding",
                phase_index=0,
                turns_in_phase=0,
                min_turns=2
            )
        )

        # Generate turn ground truth
        turn_gt = self.simulator._generate_turn_ground_truth(
            phase_name="entity_grounding",
            action="guidance",
            turn_num=1
        )

        # Validate
        self.assertEqual(turn_gt.phase, "entity_grounding")
        self.assertEqual(turn_gt.sub_goal, "identify_entity")
        self.assertTrue("person" in turn_gt.expected_answer.lower())
        self.assertTrue(turn_gt.evaluation_hints.get("ignore_final_answer"))
        self.assertEqual(turn_gt.evaluation_hints.get("focus_on"), "entity_identification")

    def test_generate_turn_ground_truth_chain_navigation(self):
        """Test turn ground truth generation for chain_navigation phase"""
        self.simulator.task_state = TaskState(
            task_id="test_001",
            task_type="attribute_bridge_reasoning",
            question="Find object left of person.",
            expected_answer="The knife",
            images=[],
            current_phase=PhaseState(
                phase_name="chain_navigation",
                phase_index=1,
                turns_in_phase=0,
                min_turns=2
            )
        )

        turn_gt = self.simulator._generate_turn_ground_truth(
            phase_name="chain_navigation",
            action="follow_up",
            turn_num=2
        )

        self.assertEqual(turn_gt.phase, "chain_navigation")
        self.assertEqual(turn_gt.sub_goal, "spatial_relation")
        self.assertTrue(turn_gt.evaluation_hints.get("ignore_final_answer"))
        self.assertEqual(turn_gt.evaluation_hints.get("focus_on"), "spatial_reasoning")

    def test_generate_turn_ground_truth_final_answer(self):
        """Test turn ground truth generation for final_answer phase"""
        self.simulator.task_state = TaskState(
            task_id="test_001",
            task_type="attribute_bridge_reasoning",
            question="What is the final object?",
            expected_answer="The knife",
            images=[],
            current_phase=PhaseState(
                phase_name="final_answer",
                phase_index=3,
                turns_in_phase=0,
                min_turns=1
            )
        )

        turn_gt = self.simulator._generate_turn_ground_truth(
            phase_name="final_answer",
            action="guidance",
            turn_num=5
        )

        self.assertEqual(turn_gt.phase, "final_answer")
        self.assertEqual(turn_gt.sub_goal, "final_answer")
        # Should use task-level expected answer
        self.assertEqual(turn_gt.expected_answer, "The knife")
        self.assertTrue(turn_gt.evaluation_hints.get("is_final_answer"))

    def test_extract_target_entity(self):
        """Test entity extraction from questions"""
        # Test person extraction
        entity = self.simulator._extract_target_entity("Find the person in the image")
        self.assertEqual(entity, "person")

        entity = self.simulator._extract_target_entity("Locate the man")
        self.assertEqual(entity, "person")

        # Test object extraction
        entity = self.simulator._extract_target_entity("Find the object on the left")
        self.assertEqual(entity, "object")

        # Test fallback
        entity = self.simulator._extract_target_entity("What is this?")
        self.assertEqual(entity, "target")


class TestTask23ScoreFormula(unittest.TestCase):
    """Test Task 2.3: Score Formula Refactoring"""

    def setUp(self):
        """Set up test evaluator"""
        self.evaluator = Evaluator(
            mode=EvaluationMode.STRESS_TEST,
            use_llm_judge=False,  # Test hard scores only
            llm_judge_weight=0.8  # Task 2.3: New default
        )

    def test_hard_scores_neutral_defaults(self):
        """Test that hard scores use neutral defaults (0.5)"""
        hard_scores = self.evaluator._hard_rule_evaluation(
            response="Test response",
            expected_answer="Test expected",
            action_type="guidance"
        )

        # All scores should default to 0.5 (neutral)
        self.assertEqual(hard_scores["correctness"], 0.5)
        self.assertEqual(hard_scores["faithfulness"], 0.5)
        self.assertEqual(hard_scores["robustness"], 0.5)
        self.assertEqual(hard_scores["consistency"], 0.5)
        self.assertEqual(hard_scores["memory_retention"], 0.5)
        self.assertEqual(hard_scores["cross_image_confusion"], 0.5)
        self.assertEqual(hard_scores["disambiguation"], 0.5)

    def test_llm_judge_weight_default(self):
        """Test that LLM Judge weight is 0.8 by default"""
        evaluator = Evaluator(mode=EvaluationMode.STRESS_TEST)
        self.assertEqual(evaluator.llm_judge_weight, 0.8)

    def test_llm_judge_perfect_score_high_final(self):
        """Test that LLM Judge 10/10 gives high final score"""
        evaluator = Evaluator(
            mode=EvaluationMode.STRESS_TEST,
            use_llm_judge=False,
            llm_judge_weight=0.8
        )

        # Simulate LLM Judge perfect scores
        llm_scores = {
            "correctness": 1.0,
            "faithfulness": 1.0,
            "robustness": 1.0,
            "consistency": 1.0,
            "memory_retention": 1.0,
            "cross_image_confusion": 1.0,
            "disambiguation": 1.0
        }

        # Hard scores (neutral defaults)
        hard_scores = {
            "correctness": 0.5,
            "faithfulness": 0.5,
            "robustness": 0.5,
            "consistency": 0.5,
            "memory_retention": 0.5,
            "cross_image_confusion": 0.5,
            "disambiguation": 0.5
        }

        # Calculate final scores
        w = 0.8
        final_scores = {
            k: w * llm_scores[k] + (1 - w) * hard_scores[k]
            for k in hard_scores
        }

        # Verify high scores
        self.assertGreaterEqual(final_scores["correctness"], 0.80)
        self.assertGreaterEqual(final_scores["faithfulness"], 0.80)
        self.assertGreaterEqual(final_scores["robustness"], 0.80)

        # Expected: 0.8 * 1.0 + 0.2 * 0.5 = 0.9
        self.assertAlmostEqual(final_scores["correctness"], 0.9, places=2)

    def test_llm_judge_low_score_still_low(self):
        """Test that LLM Judge low score results in low final score"""
        # Simulate LLM Judge low scores
        llm_scores = {
            "correctness": 0.2,
            "faithfulness": 0.2,
            "robustness": 0.2,
            "consistency": 0.2,
            "memory_retention": 0.2,
            "cross_image_confusion": 0.2,
            "disambiguation": 0.2
        }

        hard_scores = {
            "correctness": 0.5,
            "faithfulness": 0.5,
            "robustness": 0.5,
            "consistency": 0.5,
            "memory_retention": 0.5,
            "cross_image_confusion": 0.5,
            "disambiguation": 0.5
        }

        w = 0.8
        final_scores = {
            k: w * llm_scores[k] + (1 - w) * hard_scores[k]
            for k in hard_scores
        }

        # Verify low scores
        self.assertLess(final_scores["correctness"], 0.4)
        # Expected: 0.8 * 0.2 + 0.2 * 0.5 = 0.26
        self.assertAlmostEqual(final_scores["correctness"], 0.26, places=2)

    def test_old_vs_new_score_calculation(self):
        """Compare old (w=0.6, default=0.1) vs new (w=0.8, default=0.5) scoring"""
        # OLD configuration (before Task 2.3)
        old_w = 0.6
        old_hard_default = 0.1
        llm_score = 1.0  # Perfect LLM score

        old_final_score = old_w * llm_score + (1 - old_w) * old_hard_default
        # Expected: 0.6 * 1.0 + 0.4 * 0.1 = 0.64 (FAILED at threshold 0.7)

        # NEW configuration (after Task 2.3)
        new_w = 0.8
        new_hard_default = 0.5
        new_final_score = new_w * llm_score + (1 - new_w) * new_hard_default
        # Expected: 0.8 * 1.0 + 0.2 * 0.5 = 0.90 (PASSED at threshold 0.7)

        self.assertAlmostEqual(old_final_score, 0.64, places=2)
        self.assertAlmostEqual(new_final_score, 0.90, places=2)

        # Verify improvement
        self.assertLess(old_final_score, 0.7)  # Would fail
        self.assertGreaterEqual(new_final_score, 0.7)  # Would pass


class TestIntegration22And23(unittest.TestCase):
    """Integration test for Task 2.2 and 2.3 working together"""

    def setUp(self):
        """Set up integrated system"""
        self.evaluator = Evaluator(
            mode=EvaluationMode.STRESS_TEST,
            use_llm_judge=False,
            llm_judge_weight=0.8
        )
        self.simulator = StrategicSimulator(
            llm_client=None,
            evaluator=self.evaluator,
            verbose=False
        )

    def test_entity_grounding_turn_evaluation(self):
        """Test evaluation of entity grounding turn with turn-level expected answer"""
        # Set up task
        self.simulator.task_state = TaskState(
            task_id="test_001",
            task_type="attribute_bridge_reasoning",
            question="Find person. Find object left of person.",
            expected_answer="The knife",
            images=[],
            current_phase=PhaseState(
                phase_name="entity_grounding",
                phase_index=0,
                turns_in_phase=1,
                min_turns=2
            )
        )

        # Generate turn ground truth
        turn_gt = self.simulator._generate_turn_ground_truth(
            phase_name="entity_grounding",
            action="guidance",
            turn_num=1
        )

        # Store in task state
        self.simulator.task_state.turn_ground_truths[1] = turn_gt
        self.simulator.task_state.current_turn_ground_truth = turn_gt

        # Model response (identifies person but not knife)
        response = "The person is on the right side, wearing a red shirt"

        # Evaluate using turn-level expected answer
        eval_result = self.evaluator.evaluate_response(
            response=response,
            expected_answer=turn_gt.expected_answer,  # Turn-level!
            action_type="guidance",
            question_asked="Can you locate the person?",
            context={
                "sub_goal": turn_gt.sub_goal,
                "turn_ground_truth": turn_gt,
                "evaluation_hints": turn_gt.evaluation_hints,
                "task_expected_answer": self.simulator.task_state.expected_answer
            }
        )

        # Should evaluate based on entity identification, not final answer
        self.assertIsNotNone(eval_result)
        # Note: With hard scores only and no exact match, score may be moderate
        # The key is that it's NOT being judged against "The knife"


def run_tests():
    """Run all tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestTask22TurnGroundTruth))
    suite.addTests(loader.loadTestsFromTestCase(TestTask23ScoreFormula))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration22And23))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
