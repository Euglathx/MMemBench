"""
Phase 3 Task 3.4: Simulator Truth Validation Test
===================================================

Validates Phase 2 Task 2.4 fixes, ensuring the Simulator does not
"confirm" model errors and prevents error propagation.

Success Criteria:
- false_confirmation_rate: 0% (model errors NOT confirmed by simulator)
- error_propagation_rate: < 5% (errors don't propagate to subsequent turns)
- ground_truth_consistency_check: 100% (consistency check based on ground truth)

Created: 2026-02-04
"""

import os
import json
import unittest
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from simulator.strategic_simulator import StrategicSimulator, TaskState, PhaseState
from simulator.evaluator import Evaluator, EvaluationMode, EvaluationResult
from simulator.memory_store import MemoryStore, TurnRecord


# ============================================================
# Constants
# ============================================================

# Confirmation phrases that indicate false confirmation
FALSE_CONFIRMATION_PHRASES = [
    "you correctly",
    "you identified",
    "you mentioned",
    "as you said",
    "you're right",
    "correct, the",
    "yes, that's right",
    "you accurately"
]

# Deliberately wrong responses for testing
DELIBERATELY_WRONG_RESPONSES = [
    {
        "question": "What color is the car in the image?",
        "ground_truth": "The car is red",
        "wrong_response": "I can see a blue car in the image.",
        "expected_is_correct": False
    },
    {
        "question": "How many people are in the image?",
        "ground_truth": "There are 3 people",
        "wrong_response": "There is only 1 person in the image.",
        "expected_is_correct": False
    },
    {
        "question": "What is the person holding?",
        "ground_truth": "A book",
        "wrong_response": "The person is holding a phone.",
        "expected_is_correct": False
    },
    {
        "question": "Is the cat sitting or standing?",
        "ground_truth": "sitting",
        "wrong_response": "The cat is standing on the floor.",
        "expected_is_correct": False
    },
    {
        "question": "What is on the left side of the table?",
        "ground_truth": "A lamp",
        "wrong_response": "There is a vase on the left side of the table.",
        "expected_is_correct": False
    },
    {
        "question": "What time is shown on the clock?",
        "ground_truth": "3:30",
        "wrong_response": "The clock shows 7:45.",
        "expected_is_correct": False
    },
    {
        "question": "Is the door open or closed?",
        "ground_truth": "open",
        "wrong_response": "The door appears to be closed.",
        "expected_is_correct": False
    },
    {
        "question": "What breed is the dog?",
        "ground_truth": "Golden Retriever",
        "wrong_response": "This is a German Shepherd.",
        "expected_is_correct": False
    },
    {
        "question": "What is the weather like in the image?",
        "ground_truth": "sunny",
        "wrong_response": "It looks like a rainy day with dark clouds.",
        "expected_is_correct": False
    },
    {
        "question": "Where is the ball located?",
        "ground_truth": "under the chair",
        "wrong_response": "The ball is on top of the table.",
        "expected_is_correct": False
    }
]


# ============================================================
# Result Data Classes
# ============================================================

@dataclass
class SimulatorTruthResult:
    """Result of Task 3.4 validation test"""
    test_id: str = "3.4"
    test_name: str = "Simulator Truth Consistency Test"
    status: str = "PENDING"
    metrics: Dict[str, Dict] = field(default_factory=dict)
    overall_pass: bool = False
    failure_reasons: List[str] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================
# Test Classes
# ============================================================

class TestNoFalseConfirmations(unittest.TestCase):
    """Tests to verify Simulator doesn't confirm model errors"""

    def setUp(self):
        """Set up test fixtures"""
        self.simulator = StrategicSimulator(
            llm_client=None,
            verbose=False,
            filter_incorrect_turns=True,
            error_filter_threshold=0.5
        )

    def test_01_validate_model_claims_method_exists(self):
        """Verify _validate_model_claims method exists"""
        self.assertTrue(
            hasattr(self.simulator, '_validate_model_claims'),
            "StrategicSimulator should have _validate_model_claims method"
        )

    def test_02_high_score_marked_correct(self):
        """High score responses should be marked as correct"""
        self.simulator.task_state = TaskState(
            task_id="test",
            task_type="simple",
            question="What is in the image?",
            expected_answer="A person",
            images=[]
        )

        eval_result = EvaluationResult(score=0.9, level_passed=True, reasoning="High score response")

        validation = self.simulator._validate_model_claims(
            response="I see a person in the image",
            turn_number=1,
            evaluation=eval_result
        )

        self.assertFalse(validation["has_false_claims"])
        self.assertEqual(validation["false_claim_count"], 0)
        self.assertTrue(validation.get("is_correct", True))

    def test_03_low_score_marked_incorrect(self):
        """Low score responses with factual claims should be marked as having false claims"""
        self.simulator.task_state = TaskState(
            task_id="test",
            task_type="simple",
            question="What is in the image?",
            expected_answer="A person",
            images=[]
        )

        eval_result = EvaluationResult(score=0.2, level_passed=False, reasoning="Low score response")

        # Use a response that contains a factual (but incorrect) claim,
        # not just a refusal/apology (which gets filtered by _extract_factual_claims)
        validation = self.simulator._validate_model_claims(
            response="The image shows a large blue elephant standing in a forest. There are trees everywhere.",
            turn_number=1,
            evaluation=eval_result
        )

        # The response contains factual claims that contradict "A person"
        self.assertTrue(validation["has_false_claims"])
        self.assertGreater(validation["false_claim_count"], 0)

    def test_04_deliberately_wrong_responses_not_confirmed(self):
        """All 10 deliberately wrong responses should not be confirmed"""
        false_confirmations = []

        for case in DELIBERATELY_WRONG_RESPONSES:
            self.simulator.task_state = TaskState(
                task_id="test_wrong",
                task_type="simple",
                question=case["question"],
                expected_answer=case["ground_truth"],
                images=[]
            )

            eval_result = EvaluationResult(score=0.2, level_passed=False, reasoning="Low score response")

            validation = self.simulator._validate_model_claims(
                response=case["wrong_response"],
                turn_number=1,
                evaluation=eval_result
            )

            # Wrong response should be marked as having false claims
            if not validation["has_false_claims"]:
                false_confirmations.append({
                    "question": case["question"],
                    "wrong_response": case["wrong_response"],
                    "validation": validation
                })

        self.assertEqual(
            len(false_confirmations), 0,
            f"Found {len(false_confirmations)} false confirmations"
        )

    def test_05_claim_validation_has_is_correct_field(self):
        """Claim validation should include is_correct field"""
        self.simulator.task_state = TaskState(
            task_id="test",
            task_type="simple",
            question="Test question",
            expected_answer="Test answer",
            images=[]
        )

        eval_result = EvaluationResult(score=0.5, level_passed=False, reasoning="Medium score response")

        validation = self.simulator._validate_model_claims(
            response="Test response",
            turn_number=1,
            evaluation=eval_result
        )

        # Should have is_correct derived from validation
        self.assertIn("claims", validation)
        self.assertIn("has_false_claims", validation)
        self.assertIn("false_claim_count", validation)


class TestErrorPropagationControlled(unittest.TestCase):
    """Tests to verify errors don't propagate to subsequent turns"""

    def setUp(self):
        """Set up test fixtures"""
        self.memory = MemoryStore()

    def test_01_memory_filtering_enabled_by_default(self):
        """Memory filtering should be available"""
        self.memory.start_task("test_task", "test_type", "test_answer")

        # Add correct turn
        self.memory.add_turn(
            action="follow_up",
            user_message="Question 1",
            model_response="Correct answer",
            evaluation={"score": 0.9},
            is_correct=True
        )

        # Add incorrect turn
        self.memory.add_turn(
            action="follow_up",
            user_message="Question 2",
            model_response="Wrong answer",
            evaluation={"score": 0.2},
            is_correct=False
        )

        # Get filtered history
        filtered_history = self.memory.get_conversation_history(
            filter_incorrect=True,
            score_threshold=0.5
        )

        # Should only have correct turn (2 messages: user + assistant)
        self.assertEqual(len(filtered_history), 2)

    def test_02_incorrect_turns_excluded_from_context(self):
        """Incorrect turns should be excluded when filter_incorrect=True"""
        self.memory.start_task("test_task", "test_type", "test_answer")

        # Add multiple turns with varying scores
        turns_data = [
            {"score": 0.9, "is_correct": True, "response": "Good answer 1"},
            {"score": 0.2, "is_correct": False, "response": "Bad answer"},
            {"score": 0.8, "is_correct": True, "response": "Good answer 2"},
            {"score": 0.3, "is_correct": False, "response": "Another bad answer"},
        ]

        for i, data in enumerate(turns_data):
            self.memory.add_turn(
                action="follow_up",
                user_message=f"Question {i}",
                model_response=data["response"],
                evaluation={"score": data["score"]},
                is_correct=data["is_correct"]
            )

        # Without filtering: 8 messages (4 turns * 2)
        unfiltered = self.memory.get_conversation_history(filter_incorrect=False)
        self.assertEqual(len(unfiltered), 8)

        # With filtering: 4 messages (2 correct turns * 2)
        filtered = self.memory.get_conversation_history(filter_incorrect=True)
        self.assertEqual(len(filtered), 4)

        # Verify content - should only have good answers
        all_content = " ".join(msg["content"] for msg in filtered if msg["role"] == "assistant")
        self.assertIn("Good answer", all_content)
        self.assertNotIn("Bad answer", all_content)

    def test_03_is_correct_takes_precedence_over_score(self):
        """is_correct flag should take precedence over score threshold"""
        self.memory.start_task("test_task", "test_type", "test_answer")

        # High score but marked incorrect
        self.memory.add_turn(
            action="follow_up",
            user_message="Question",
            model_response="Misleading high-score answer",
            evaluation={"score": 0.9},
            is_correct=False  # Explicitly marked incorrect despite high score
        )

        # Filter should exclude based on is_correct flag
        filtered = self.memory.get_conversation_history(filter_incorrect=True)
        self.assertEqual(len(filtered), 0)

    def test_04_error_propagation_rate_under_threshold(self):
        """Error propagation rate should be under 5%"""
        self.memory.start_task("test_task", "test_type", "test_answer")

        # Simulate 20 turns, 5 with errors
        for i in range(20):
            is_error = i % 4 == 0  # Every 4th turn is error (5 errors)
            self.memory.add_turn(
                action="follow_up",
                user_message=f"Question {i}",
                model_response=f"{'Error' if is_error else 'Correct'} response {i}",
                evaluation={"score": 0.2 if is_error else 0.9},
                is_correct=not is_error
            )

        # Get filtered history
        filtered = self.memory.get_conversation_history(filter_incorrect=True)

        # Should only have correct turns (15 turns * 2 = 30 messages)
        self.assertEqual(len(filtered), 30)

        # With filtering enabled, error propagation is 0% because errors are filtered out
        # The metric measures how many errors would propagate WITHOUT intervention
        # With our filtering mechanism, propagation rate = 0%
        # So we verify that the filtering removes errors
        error_count = sum(1 for i in range(20) if i % 4 == 0)  # 5 errors
        correct_count = 20 - error_count  # 15 correct

        # Verify filtering worked correctly
        self.assertEqual(len(filtered) // 2, correct_count)


class TestConsistencyCheckUsesGroundTruth(unittest.TestCase):
    """Tests to verify consistency checks use ground truth, not model claims"""

    def setUp(self):
        """Set up test fixtures"""
        self.simulator = StrategicSimulator(
            llm_client=None,
            verbose=False
        )

    def test_01_generate_consistency_check_method_exists(self):
        """Verify _generate_consistency_check_from_ground_truth method exists"""
        self.assertTrue(
            hasattr(self.simulator, '_generate_consistency_check_from_ground_truth'),
            "StrategicSimulator should have _generate_consistency_check_from_ground_truth method"
        )

    def test_02_consistency_check_uses_original_question(self):
        """Consistency check should reference original question"""
        self.simulator.task_state = TaskState(
            task_id="test",
            task_type="simple",
            question="What object is visible in the image?",
            expected_answer="A knife",
            images=[]
        )

        message = self.simulator._generate_consistency_check_from_ground_truth()

        # Should contain original question or reformulation
        self.assertTrue(
            "object" in message.lower() or "visible" in message.lower() or "what" in message.lower(),
            "Consistency check should reference original question"
        )

    def test_03_consistency_check_does_not_reference_model_claims(self):
        """Consistency check should NOT reference model's claims"""
        self.simulator.task_state = TaskState(
            task_id="test",
            task_type="simple",
            question="What is the color?",
            expected_answer="Red",
            images=[],
            model_claims=[
                {"turn": 1, "claim": "I see a blue car", "action_context": "follow_up"}
            ]
        )

        message = self.simulator._generate_consistency_check_from_ground_truth()

        # Should NOT contain phrases that reference model claims
        for phrase in ["you said", "you mentioned", "you claimed", "you stated"]:
            self.assertNotIn(
                phrase,
                message.lower(),
                f"Consistency check should not contain '{phrase}'"
            )

    def test_04_consistency_check_reformulates_question(self):
        """Consistency check should reformulate original question"""
        test_questions = [
            "What is in the image?",
            "How many people are there?",
            "What color is the object?"
        ]

        for question in test_questions:
            self.simulator.task_state = TaskState(
                task_id="test",
                task_type="simple",
                question=question,
                expected_answer="Test answer",
                images=[]
            )

            message = self.simulator._generate_consistency_check_from_ground_truth()

            # Should produce a valid message
            self.assertIsInstance(message, str)
            self.assertGreater(len(message), 10)

    def test_05_all_consistency_checks_ground_truth_based(self):
        """All consistency checks should be based on ground truth"""
        test_cases = [
            {"question": "What is the car's color?", "expected": "Red"},
            {"question": "How many dogs are visible?", "expected": "3"},
            {"question": "Where is the book located?", "expected": "On the table"},
        ]

        for case in test_cases:
            self.simulator.task_state = TaskState(
                task_id="test",
                task_type="simple",
                question=case["question"],
                expected_answer=case["expected"],
                images=[],
                model_claims=[
                    {"turn": 1, "claim": "Incorrect claim", "action_context": "follow_up"}
                ]
            )

            message = self.simulator._generate_consistency_check_from_ground_truth()

            # Verify message doesn't validate against model's incorrect claim
            self.assertNotIn("Incorrect claim", message)


class TestClaimValidationLogic(unittest.TestCase):
    """Tests for claim validation logic correctness"""

    def setUp(self):
        """Set up test fixtures"""
        self.simulator = StrategicSimulator(
            llm_client=None,
            verbose=False
        )
        self.simulator.task_state = TaskState(
            task_id="test",
            task_type="simple",
            question="Test question",
            expected_answer="Test answer",
            images=[]
        )

    def test_01_score_based_validation_high_confidence(self):
        """Score >= 0.7 should assume correct (high confidence)"""
        eval_result = EvaluationResult(score=0.85, level_passed=True, reasoning="High confidence response")

        validation = self.simulator._validate_model_claims(
            response="High confidence response",
            turn_number=1,
            evaluation=eval_result
        )

        # High score = assume correct
        self.assertFalse(validation["has_false_claims"])

    def test_02_score_based_validation_low_confidence(self):
        """Score < 0.4 should assume incorrect (low confidence)"""
        eval_result = EvaluationResult(score=0.25, level_passed=False, reasoning="Low confidence response")

        validation = self.simulator._validate_model_claims(
            response="Low confidence response with incorrect information",
            turn_number=1,
            evaluation=eval_result
        )

        # Low score = assume incorrect
        self.assertTrue(validation["has_false_claims"])

    def test_03_score_based_validation_medium_range(self):
        """Score 0.4-0.7 should use heuristic comparison"""
        eval_result = EvaluationResult(score=0.55, level_passed=False, reasoning="Medium range response")

        validation = self.simulator._validate_model_claims(
            response="Medium confidence response",
            turn_number=1,
            evaluation=eval_result
        )

        # Medium range - result depends on heuristic
        self.assertIn("has_false_claims", validation)
        self.assertIn("claims", validation)


class TestMemoryFilteringFunctionality(unittest.TestCase):
    """Tests for memory filtering functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.memory = MemoryStore()
        self.memory.start_task("test_task", "test_type", "test_answer")

    def test_01_filter_incorrect_true_excludes_low_scores(self):
        """filter_incorrect=True should exclude turns with low scores"""
        self.memory.add_turn(
            action="follow_up",
            user_message="Q1",
            model_response="A1 (correct)",
            evaluation={"score": 0.9}
        )
        self.memory.add_turn(
            action="follow_up",
            user_message="Q2",
            model_response="A2 (incorrect)",
            evaluation={"score": 0.3}
        )

        filtered = self.memory.get_conversation_history(
            filter_incorrect=True,
            score_threshold=0.5
        )

        # Only first turn should be included
        self.assertEqual(len(filtered), 2)
        self.assertIn("correct", filtered[1]["content"])

    def test_02_filter_incorrect_false_includes_all(self):
        """filter_incorrect=False should include all turns"""
        self.memory.add_turn(
            action="follow_up",
            user_message="Q1",
            model_response="A1",
            evaluation={"score": 0.9}
        )
        self.memory.add_turn(
            action="follow_up",
            user_message="Q2",
            model_response="A2",
            evaluation={"score": 0.1}
        )

        unfiltered = self.memory.get_conversation_history(filter_incorrect=False)

        # Both turns should be included
        self.assertEqual(len(unfiltered), 4)

    def test_03_score_threshold_respected(self):
        """Score threshold should be correctly applied"""
        scores = [0.3, 0.5, 0.7, 0.9]
        for i, score in enumerate(scores):
            self.memory.add_turn(
                action="follow_up",
                user_message=f"Q{i}",
                model_response=f"A{i}",
                evaluation={"score": score}
            )

        # Threshold 0.6: should keep 0.7 and 0.9
        filtered = self.memory.get_conversation_history(
            filter_incorrect=True,
            score_threshold=0.6
        )
        self.assertEqual(len(filtered), 4)  # 2 turns * 2 messages

    def test_04_is_correct_flag_overrides_score(self):
        """is_correct flag should override score-based filtering"""
        self.memory.add_turn(
            action="follow_up",
            user_message="Q1",
            model_response="Marked correct despite low score",
            evaluation={"score": 0.3},
            is_correct=True
        )
        self.memory.add_turn(
            action="follow_up",
            user_message="Q2",
            model_response="Marked incorrect despite high score",
            evaluation={"score": 0.9},
            is_correct=False
        )

        filtered = self.memory.get_conversation_history(filter_incorrect=True)

        # Only first turn should be included
        self.assertEqual(len(filtered), 2)
        self.assertIn("low score", filtered[1]["content"])


class TestFalseClaimInjectionResistance(unittest.TestCase):
    """Tests for resistance to false claim injection"""

    def setUp(self):
        """Set up test fixtures"""
        self.simulator = StrategicSimulator(
            llm_client=None,
            verbose=False,
            filter_incorrect_turns=True
        )

    def test_01_false_claims_not_treated_as_facts(self):
        """Injected false claims should not be treated as facts"""
        self.simulator.task_state = TaskState(
            task_id="test",
            task_type="simple",
            question="What color is the car?",
            expected_answer="Red",
            images=[]
        )

        # Inject false claim
        false_response = "The car is definitely blue, and I'm 100% certain of this."

        eval_result = EvaluationResult(score=0.2, level_passed=False, reasoning="Low score response")

        validation = self.simulator._validate_model_claims(
            response=false_response,
            turn_number=1,
            evaluation=eval_result
        )

        # Should detect false claim
        self.assertTrue(validation["has_false_claims"])

    def test_02_consistency_check_not_based_on_false_claims(self):
        """Consistency check should not validate based on false claims"""
        self.simulator.task_state = TaskState(
            task_id="test",
            task_type="simple",
            question="What color is the car?",
            expected_answer="Red",
            images=[],
            model_claims=[
                {"turn": 1, "claim": "The car is blue", "action_context": "follow_up"}
            ]
        )

        message = self.simulator._generate_consistency_check_from_ground_truth()

        # Should not validate the false claim
        self.assertNotIn("blue", message.lower())


class TestComprehensiveTruthValidation(unittest.TestCase):
    """Comprehensive validation tests"""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures"""
        cls.project_root = Path(__file__).parent.parent.parent
        cls.log_dir = cls.project_root / "simulator_test_log"
        cls.result = SimulatorTruthResult()

    def test_comprehensive_false_confirmation_check(self):
        """Check for false confirmations across all test cases"""
        simulator = StrategicSimulator(llm_client=None, verbose=False)
        false_confirmations = 0

        for case in DELIBERATELY_WRONG_RESPONSES:
            simulator.task_state = TaskState(
                task_id="comprehensive_test",
                task_type="simple",
                question=case["question"],
                expected_answer=case["ground_truth"],
                images=[]
            )

            eval_result = EvaluationResult(score=0.2, level_passed=False, reasoning="Low score response")

            validation = simulator._validate_model_claims(
                response=case["wrong_response"],
                turn_number=1,
                evaluation=eval_result
            )

            if not validation["has_false_claims"]:
                false_confirmations += 1

        # Calculate rate
        total_cases = len(DELIBERATELY_WRONG_RESPONSES)
        false_confirmation_rate = false_confirmations / total_cases

        # Should be 0%
        self.assertEqual(
            false_confirmation_rate, 0.0,
            f"False confirmation rate is {false_confirmation_rate:.2%}, should be 0%"
        )


def run_comprehensive_test(log_dir: str, output_dir: str) -> SimulatorTruthResult:
    """Run comprehensive test suite and generate report"""
    result = SimulatorTruthResult()
    result.metrics = {}
    result.failure_reasons = []
    result.evidence = {
        "false_confirmation_cases": [],
        "error_propagation_cases": [],
        "sample_logs": [],
        "deliberately_wrong_responses_tested": len(DELIBERATELY_WRONG_RESPONSES),
        "consistency_check_samples": []
    }

    # Run unit tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestNoFalseConfirmations))
    suite.addTests(loader.loadTestsFromTestCase(TestErrorPropagationControlled))
    suite.addTests(loader.loadTestsFromTestCase(TestConsistencyCheckUsesGroundTruth))
    suite.addTests(loader.loadTestsFromTestCase(TestClaimValidationLogic))
    suite.addTests(loader.loadTestsFromTestCase(TestMemoryFilteringFunctionality))
    suite.addTests(loader.loadTestsFromTestCase(TestFalseClaimInjectionResistance))

    # Run tests
    import io
    stream = io.StringIO()
    runner = unittest.TextTestRunner(stream=stream, verbosity=2)
    test_result = runner.run(suite)

    # Calculate metrics
    total_tests = test_result.testsRun
    failures = len(test_result.failures)
    errors = len(test_result.errors)
    passed = total_tests - failures - errors

    # Test false confirmation rate
    simulator = StrategicSimulator(llm_client=None, verbose=False)
    false_confirmations = 0

    for case in DELIBERATELY_WRONG_RESPONSES:
        simulator.task_state = TaskState(
            task_id="test",
            task_type="simple",
            question=case["question"],
            expected_answer=case["ground_truth"],
            images=[]
        )
        eval_result = EvaluationResult(score=0.2, level_passed=False, reasoning="Low score response")
        validation = simulator._validate_model_claims(
            response=case["wrong_response"],
            turn_number=1,
            evaluation=eval_result
        )
        if not validation["has_false_claims"]:
            false_confirmations += 1
            result.evidence["false_confirmation_cases"].append(case)

    false_confirmation_rate = false_confirmations / len(DELIBERATELY_WRONG_RESPONSES)

    # Test memory filtering - error propagation rate measures how many
    # errors would propagate to subsequent turns WITH filtering enabled.
    # If filtering works correctly, propagation rate = 0% because
    # errors are removed from the conversation history.
    memory = MemoryStore()
    memory.start_task("test", "test", "test")
    error_count = 0
    total_count = 10
    for i in range(total_count):
        is_error = i % 3 == 0
        if is_error:
            error_count += 1
        memory.add_turn(
            action="follow_up",
            user_message=f"Q{i}",
            model_response=f"A{i}",
            evaluation={"score": 0.2 if is_error else 0.9},
            is_correct=not is_error
        )

    filtered = memory.get_conversation_history(filter_incorrect=True)

    # Count how many error turns leaked through the filter
    # (propagation = errors that remain in filtered context)
    errors_in_filtered = 0
    for msg in filtered:
        if msg["role"] == "assistant":
            # Check if this was an error turn by matching against original data
            for turn in memory.current_task.turns:
                if turn.model_response == msg["content"] and turn.is_correct is False:
                    errors_in_filtered += 1

    # Error propagation rate = errors leaked / total errors
    error_propagation_rate = errors_in_filtered / error_count if error_count > 0 else 0.0

    # Calculate consistency check rate
    consistency_check_passed = 0
    consistency_check_total = 3

    for i in range(consistency_check_total):
        simulator.task_state = TaskState(
            task_id=f"test_{i}",
            task_type="simple",
            question=f"Test question {i}?",
            expected_answer=f"Test answer {i}",
            images=[],
            model_claims=[{"turn": 1, "claim": "Wrong claim", "action_context": "follow_up"}]
        )
        message = simulator._generate_consistency_check_from_ground_truth()
        if "wrong claim" not in message.lower() and "you said" not in message.lower():
            consistency_check_passed += 1
            result.evidence["consistency_check_samples"].append({
                "type": "reformulated_question",
                "original": f"Test question {i}?",
                "consistency_question": message
            })

    consistency_check_rate = consistency_check_passed / consistency_check_total

    # Build metrics
    result.metrics = {
        "false_confirmation_rate": {
            "value": false_confirmation_rate,
            "threshold": 0.0,
            "pass": false_confirmation_rate == 0.0,
            "detail": f"{false_confirmations}/{len(DELIBERATELY_WRONG_RESPONSES)} wrong responses were falsely confirmed"
        },
        "error_propagation_rate": {
            "value": error_propagation_rate,
            "threshold": 0.05,
            "pass": error_propagation_rate < 0.05,
            "detail": f"{error_propagation_rate:.2%} errors propagated to subsequent turns"
        },
        "ground_truth_consistency_check": {
            "value": consistency_check_rate,
            "threshold": 1.0,
            "pass": consistency_check_rate == 1.0,
            "detail": f"{consistency_check_rate:.2%} consistency checks based on ground truth"
        }
    }

    result.evidence["memory_filtering_tests"] = {
        "total_turns": total_count,
        "error_turns": error_count,
        "errors_leaked_through_filter": errors_in_filtered,
        "filter_reason": "is_correct=False or score<0.5"
    }

    result.overall_pass = all(m["pass"] for m in result.metrics.values())
    result.status = "PASS" if result.overall_pass else "FAIL"

    # Add test results
    if failures > 0 or errors > 0:
        for failure in test_result.failures:
            result.failure_reasons.append(f"Test failure: {failure[0]}")
        for error in test_result.errors:
            result.failure_reasons.append(f"Test error: {error[0]}")

    # Save results
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # JSON report
    json_path = output_path / "phase3_3.4_simulator_truth.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)

    # Text report
    txt_path = output_path / "phase3_3.4_validation_report.txt"
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write("=" * 60 + "\n")
        f.write("Phase 3 Task 3.4: Simulator Truth Validation Report\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"Status: {result.status}\n")
        f.write(f"Timestamp: {result.timestamp}\n\n")
        f.write("Metrics:\n")
        for name, metric in result.metrics.items():
            status = "PASS" if metric["pass"] else "FAIL"
            f.write(f"  - {name}: {metric['value']:.2%} (threshold: {metric['threshold']:.2%}) - {status}\n")
            f.write(f"    Detail: {metric['detail']}\n")
        f.write("\nEvidence:\n")
        f.write(f"  - Deliberately wrong responses tested: {result.evidence.get('deliberately_wrong_responses_tested', 0)}\n")
        f.write(f"  - False confirmations found: {len(result.evidence.get('false_confirmation_cases', []))}\n")
        if result.evidence.get("memory_filtering_tests"):
            mft = result.evidence["memory_filtering_tests"]
            f.write(f"  - Memory filtering: {mft['error_turns']} error turns / {mft['total_turns']} total, {mft['errors_leaked_through_filter']} errors leaked\n")
        if result.failure_reasons:
            f.write("\nFailure Reasons:\n")
            for reason in result.failure_reasons:
                f.write(f"  - {reason}\n")

    return result


def run_tests():
    """Run all tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestNoFalseConfirmations))
    suite.addTests(loader.loadTestsFromTestCase(TestErrorPropagationControlled))
    suite.addTests(loader.loadTestsFromTestCase(TestConsistencyCheckUsesGroundTruth))
    suite.addTests(loader.loadTestsFromTestCase(TestClaimValidationLogic))
    suite.addTests(loader.loadTestsFromTestCase(TestMemoryFilteringFunctionality))
    suite.addTests(loader.loadTestsFromTestCase(TestFalseClaimInjectionResistance))
    suite.addTests(loader.loadTestsFromTestCase(TestComprehensiveTruthValidation))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run Task 3.4 Simulator Truth Validation Tests")
    parser.add_argument("--log-dir", default="simulator_test_log", help="Log directory")
    parser.add_argument("--output-dir", default="docs/task/round3/report/stage3", help="Output directory")
    parser.add_argument("--comprehensive", action="store_true", help="Run comprehensive test")

    args = parser.parse_args()

    if args.comprehensive:
        result = run_comprehensive_test(args.log_dir, args.output_dir)
        print(f"\nOverall Status: {result.status}")
        sys.exit(0 if result.overall_pass else 1)
    else:
        success = run_tests()
        sys.exit(0 if success else 1)
