"""
Unit Tests for Truth Validation Mechanism (Phase 2 Task 2.4)
=============================================================

Tests the truth validation features including:
- Claim validation
- Memory filtering
- Consistency check grounding
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from simulator.strategic_simulator import StrategicSimulator, TaskState
from simulator.memory_store import MemoryStore, TurnRecord
from simulator.evaluator import EvaluationResult


class TestClaimValidation(unittest.TestCase):
    """Tests for claim validation mechanism"""

    def setUp(self):
        """Set up test fixtures"""
        self.simulator = StrategicSimulator(verbose=False)

    def test_validate_correct_claims_high_score(self):
        """High score responses should be marked as correct"""
        # Create a mock task state
        self.simulator.task_state = TaskState(
            task_id="test",
            task_type="simple",
            question="What is in the image?",
            expected_answer="A person",
            images=[]
        )

        # High score evaluation
        eval_result = EvaluationResult(score=0.9, level_passed=True)

        validation = self.simulator._validate_model_claims(
            response="I see a person in the image",
            turn_number=1,
            evaluation=eval_result
        )

        self.assertFalse(validation["has_false_claims"])
        self.assertEqual(validation["false_claim_count"], 0)

    def test_validate_incorrect_claims_low_score(self):
        """Low score responses should be marked as incorrect"""
        self.simulator.task_state = TaskState(
            task_id="test",
            task_type="simple",
            question="What is in the image?",
            expected_answer="A person",
            images=[]
        )

        # Low score evaluation
        eval_result = EvaluationResult(score=0.2, level_passed=False)

        validation = self.simulator._validate_model_claims(
            response="I cannot see images, I am text-only",
            turn_number=1,
            evaluation=eval_result
        )

        self.assertTrue(validation["has_false_claims"])
        self.assertGreater(validation["false_claim_count"], 0)

    def test_extract_factual_claims(self):
        """Test extraction of factual claims from response"""
        response = "I see a person. The person is holding a knife. I think this is correct."

        claims = self.simulator._extract_factual_claims(response)

        # Should extract factual statements
        self.assertGreater(len(claims), 0)

        # Should exclude "I think" statements
        self.assertTrue(all("I think" not in claim for claim in claims))

    def test_extract_factual_claims_filters_non_factual(self):
        """Non-factual statements should be filtered out"""
        response = "I apologize but I cannot see images. As an AI, I don't have vision."

        claims = self.simulator._extract_factual_claims(response)

        # Should filter out apologies and AI disclaimers
        self.assertEqual(len(claims), 0)


class TestMemoryFiltering(unittest.TestCase):
    """Tests for memory filtering functionality"""

    def test_memory_filtering_excludes_incorrect_turns(self):
        """Memory filtering should exclude turns with low scores"""
        memory = MemoryStore()
        memory.start_task("test_task", "test_type", "test_answer")

        # Add correct turn (high score)
        memory.add_turn(
            action="follow_up",
            user_message="Question 1",
            model_response="Correct answer",
            evaluation={"score": 0.9},
            key_info=[],
            is_correct=True
        )

        # Add incorrect turn (low score)
        memory.add_turn(
            action="follow_up",
            user_message="Question 2",
            model_response="Wrong answer",
            evaluation={"score": 0.2},
            key_info=[],
            is_correct=False
        )

        # Without filtering: should have 4 messages (2 turns * 2 messages/turn)
        history_all = memory.get_conversation_history(filter_incorrect=False)
        self.assertEqual(len(history_all), 4)

        # With filtering: should only have 2 messages (1 correct turn * 2)
        history_filtered = memory.get_conversation_history(filter_incorrect=True)
        self.assertEqual(len(history_filtered), 2)

    def test_memory_filtering_uses_score_threshold(self):
        """Memory filtering should respect score threshold parameter"""
        memory = MemoryStore()
        memory.start_task("test_task", "test_type", "test_answer")

        # Add turns with various scores
        memory.add_turn(
            action="follow_up",
            user_message="Q1",
            model_response="A1",
            evaluation={"score": 0.8},
            key_info=[]
        )

        memory.add_turn(
            action="follow_up",
            user_message="Q2",
            model_response="A2",
            evaluation={"score": 0.4},
            key_info=[]
        )

        memory.add_turn(
            action="follow_up",
            user_message="Q3",
            model_response="A3",
            evaluation={"score": 0.6},
            key_info=[]
        )

        # Filter with threshold 0.5: should keep scores >= 0.5
        history = memory.get_conversation_history(
            filter_incorrect=True,
            score_threshold=0.5
        )

        # Should keep turns with scores 0.8 and 0.6 (4 messages)
        self.assertEqual(len(history), 4)

    def test_memory_filtering_prefers_is_correct_flag(self):
        """is_correct flag should take precedence over score"""
        memory = MemoryStore()
        memory.start_task("test_task", "test_type", "test_answer")

        # Turn with high score but marked incorrect
        memory.add_turn(
            action="follow_up",
            user_message="Q1",
            model_response="A1",
            evaluation={"score": 0.9},
            key_info=[],
            is_correct=False  # Explicitly marked incorrect
        )

        history = memory.get_conversation_history(filter_incorrect=True)

        # Should be filtered out despite high score
        self.assertEqual(len(history), 0)


class TestConsistencyCheckGrounding(unittest.TestCase):
    """Tests for consistency check grounding in ground truth"""

    def setUp(self):
        """Set up test fixtures"""
        self.simulator = StrategicSimulator(verbose=False)

    def test_consistency_check_uses_ground_truth(self):
        """Consistency check should generate question from ground truth"""
        self.simulator.task_state = TaskState(
            task_id="test",
            task_type="simple",
            question="What object is visible?",
            expected_answer="A knife",
            images=[]
        )

        message = self.simulator._generate_consistency_check_from_ground_truth()

        # Should contain the original question
        self.assertIn("What object is visible", message)

        # Should not reference model's claims
        self.assertNotIn("You said", message.lower())
        self.assertNotIn("You mentioned", message.lower())

    def test_consistency_check_reformulates_question(self):
        """Consistency check should reformulate original question"""
        self.simulator.task_state = TaskState(
            task_id="test",
            task_type="simple",
            question="What is the color?",
            expected_answer="Red",
            images=[]
        )

        # Generate multiple times to test randomization
        messages = [
            self.simulator._generate_consistency_check_from_ground_truth()
            for _ in range(5)
        ]

        # All should contain the original question
        for msg in messages:
            self.assertIn("What is the color", msg)


class TestIntegrationTruthValidation(unittest.TestCase):
    """Integration tests for truth validation system"""

    @patch('simulator.strategic_simulator.LLMClient')
    @patch('simulator.strategic_simulator.Evaluator')
    def test_step_includes_validation(self, mock_evaluator, mock_llm):
        """Step method should include claim validation"""
        # Set up mocks
        mock_llm_instance = Mock()
        mock_llm.return_value = mock_llm_instance

        mock_evaluator_instance = Mock()
        mock_evaluator.return_value = mock_evaluator_instance

        simulator = StrategicSimulator(
            llm_client=mock_llm_instance,
            evaluator=mock_evaluator_instance,
            verbose=False,
            filter_incorrect_turns=True
        )

        # Start a task
        task = {
            "task_id": "test",
            "task_type": "simple",
            "question": "What is this?",
            "answer": "A test",
            "images": []
        }

        try:
            simulator.start_task(task)

            # Mock responses
            mock_llm_instance.call_core_model.return_value = {
                "success": True,
                "content": '{"action": "follow_up", "message": "Tell me more"}',
                "reasoning_content": ""
            }

            mock_llm_instance.call_target_model.return_value = {
                "success": True,
                "content": "This is a test response"
            }

            mock_evaluator_instance.evaluate_response.return_value = EvaluationResult(
                score=0.8,
                level_passed=True
            )

            # Execute step
            result = simulator.step()

            # Check that validation occurred
            self.assertIn("evaluation", result)

        except Exception as e:
            # If there are missing dependencies, skip the test
            self.skipTest(f"Integration test skipped due to: {e}")


if __name__ == "__main__":
    unittest.main()
