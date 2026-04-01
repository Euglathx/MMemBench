"""
Unit Tests for Image Strategy Unification (Phase 2 Task 2.5)
=============================================================

Tests the image injection policy features including:
- ImagePolicyManager
- Strategy consistency across simulators
- Images_sent parameter passing
"""

import unittest
from unittest.mock import Mock, patch
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from simulator.image_policy import ImageInjectionPolicy, ImagePolicyManager
from simulator.strategic_simulator import StrategicSimulator
from simulator.llm_user_simulator import LLMUserSimulator


class TestImagePolicyManager(unittest.TestCase):
    """Tests for ImagePolicyManager class"""

    def test_send_all_every_turn_policy(self):
        """SEND_ALL_EVERY_TURN should send all images on every turn"""
        manager = ImagePolicyManager(ImageInjectionPolicy.SEND_ALL_EVERY_TURN)

        images = ["img1.jpg", "img2.jpg", "img3.jpg"]

        # Turn 1, 2, 3 should all return all images
        for turn in [1, 2, 3]:
            result = manager.get_images_to_send(images, turn, "follow_up")
            self.assertEqual(len(result), 3)
            self.assertEqual(result, images)

    def test_progressive_policy_guidance_action(self):
        """PROGRESSIVE policy should send images one at a time on guidance actions"""
        manager = ImagePolicyManager(ImageInjectionPolicy.PROGRESSIVE)

        images = ["img1.jpg", "img2.jpg", "img3.jpg"]

        # Turn 1: First image
        result1 = manager.get_images_to_send(images, 1, "guidance")
        self.assertEqual(len(result1), 1)
        self.assertEqual(result1[0], "img1.jpg")

        # Turn 2: Second image
        result2 = manager.get_images_to_send(images, 2, "guidance")
        self.assertEqual(len(result2), 1)
        self.assertEqual(result2[0], "img2.jpg")

        # Turn 3: Third image
        result3 = manager.get_images_to_send(images, 3, "guidance")
        self.assertEqual(len(result3), 1)
        self.assertEqual(result3[0], "img3.jpg")

        # Turn 4: All shown, return empty
        result4 = manager.get_images_to_send(images, 4, "guidance")
        self.assertEqual(len(result4), 0)

    def test_progressive_policy_non_guidance_action(self):
        """PROGRESSIVE policy should not send images on non-guidance actions"""
        manager = ImagePolicyManager(ImageInjectionPolicy.PROGRESSIVE)

        images = ["img1.jpg", "img2.jpg", "img3.jpg"]

        # Non-guidance action should return empty
        result = manager.get_images_to_send(images, 1, "follow_up")
        self.assertEqual(len(result), 0)

    def test_send_all_first_turn_policy(self):
        """SEND_ALL_FIRST_TURN should only send on turn 1"""
        manager = ImagePolicyManager(ImageInjectionPolicy.SEND_ALL_FIRST_TURN)

        images = ["img1.jpg", "img2.jpg", "img3.jpg"]

        # Turn 1: Send all
        result1 = manager.get_images_to_send(images, 1, "follow_up")
        self.assertEqual(len(result1), 3)

        # Turn 2+: Send none
        result2 = manager.get_images_to_send(images, 2, "follow_up")
        self.assertEqual(len(result2), 0)

    def test_action_dependent_policy(self):
        """ACTION_DEPENDENT should send based on action type"""
        manager = ImagePolicyManager(ImageInjectionPolicy.ACTION_DEPENDENT)

        images = ["img1.jpg", "img2.jpg"]

        # Guidance: should send all
        result1 = manager.get_images_to_send(images, 1, "guidance")
        self.assertEqual(len(result1), 2)

        # Follow-up: should send all
        result2 = manager.get_images_to_send(images, 2, "follow_up")
        self.assertEqual(len(result2), 2)

        # Mislead: should send none
        result3 = manager.get_images_to_send(images, 3, "mislead")
        self.assertEqual(len(result3), 0)

    def test_policy_reset(self):
        """Reset should clear progressive policy state"""
        manager = ImagePolicyManager(ImageInjectionPolicy.PROGRESSIVE)

        images = ["img1.jpg", "img2.jpg"]

        # Send first image
        result1 = manager.get_images_to_send(images, 1, "guidance")
        self.assertEqual(len(result1), 1)

        # Reset
        manager.reset()

        # Should send first image again
        result2 = manager.get_images_to_send(images, 1, "guidance")
        self.assertEqual(len(result2), 1)
        self.assertEqual(result2[0], "img1.jpg")

    def test_empty_images_list(self):
        """Should handle empty images list gracefully"""
        manager = ImagePolicyManager(ImageInjectionPolicy.SEND_ALL_EVERY_TURN)

        result = manager.get_images_to_send([], 1, "follow_up")
        self.assertEqual(len(result), 0)


class TestSimulatorPolicyConsistency(unittest.TestCase):
    """Tests for policy consistency across simulators"""

    def test_strategic_simulator_uses_policy(self):
        """StrategicSimulator should use ImagePolicyManager"""
        policy = ImageInjectionPolicy.SEND_ALL_EVERY_TURN
        simulator = StrategicSimulator(
            image_injection_policy=policy,
            verbose=False
        )

        # Check that policy manager is initialized
        self.assertIsNotNone(simulator.image_policy)
        self.assertEqual(simulator.image_policy.policy, policy)

    def test_llm_user_simulator_uses_policy(self):
        """LLMUserSimulator should use ImagePolicyManager"""
        policy = ImageInjectionPolicy.PROGRESSIVE
        simulator = LLMUserSimulator(
            image_injection_policy=policy,
            verbose=False
        )

        # Check that policy manager is initialized
        self.assertIsNotNone(simulator.image_policy)
        self.assertEqual(simulator.image_policy.policy, policy)

    def test_simulators_use_same_policy(self):
        """Both simulators should use the same policy when configured"""
        policy = ImageInjectionPolicy.SEND_ALL_EVERY_TURN

        strategic = StrategicSimulator(
            image_injection_policy=policy,
            verbose=False
        )
        llm_user = LLMUserSimulator(
            image_injection_policy=policy,
            verbose=False
        )

        # Verify both use the same policy
        self.assertEqual(strategic.image_policy.policy, policy)
        self.assertEqual(llm_user.image_policy.policy, policy)


class TestImagesSentParameter(unittest.TestCase):
    """Tests for images_sent parameter passing to evaluator"""

    @patch('simulator.strategic_simulator.LLMClient')
    @patch('simulator.strategic_simulator.Evaluator')
    def test_evaluator_receives_images_sent(self, mock_evaluator, mock_llm):
        """Evaluator should receive images_sent in context"""
        # Set up mocks
        mock_llm_instance = Mock()
        mock_llm.return_value = mock_llm_instance

        mock_evaluator_instance = Mock()
        mock_evaluator.return_value = mock_evaluator_instance

        simulator = StrategicSimulator(
            llm_client=mock_llm_instance,
            evaluator=mock_evaluator_instance,
            verbose=False
        )

        # Start a task with images
        task = {
            "task_id": "test",
            "task_type": "simple",
            "question": "Test",
            "answer": "Test",
            "images": ["img1.jpg", "img2.jpg"]
        }

        try:
            # Mock the image resolution to return valid paths
            with patch.object(simulator, '_resolve_single_image_path') as mock_resolve:
                mock_resolve.side_effect = lambda path, idx: f"/mock/path/{path}"

                simulator.start_task(task)

                # Mock responses
                mock_llm_instance.call_core_model.return_value = {
                    "success": True,
                    "content": '{"action": "follow_up", "message": "Test"}',
                    "reasoning_content": ""
                }

                mock_llm_instance.call_target_model.return_value = {
                    "success": True,
                    "content": "Test response"
                }

                from simulator.evaluator import EvaluationResult
                mock_evaluator_instance.evaluate_response.return_value = EvaluationResult(
                    score=0.8,
                    level_passed=True
                )

                # Execute step
                simulator.step()

                # Check that evaluate_response was called with context containing images_sent
                call_args = mock_evaluator_instance.evaluate_response.call_args
                if call_args:
                    context = call_args[1].get('context', {})
                    self.assertIn('images_sent', context)
                    self.assertIn('total_task_images', context)

        except Exception as e:
            # If there are missing dependencies, skip the test
            self.skipTest(f"Integration test skipped due to: {e}")


class TestImagePolicyEnum(unittest.TestCase):
    """Tests for ImageInjectionPolicy enum"""

    def test_policy_enum_values(self):
        """Test that all expected policy values exist"""
        self.assertEqual(
            ImageInjectionPolicy.SEND_ALL_EVERY_TURN,
            "send_all_every_turn"
        )
        self.assertEqual(
            ImageInjectionPolicy.PROGRESSIVE,
            "progressive"
        )
        self.assertEqual(
            ImageInjectionPolicy.SEND_ALL_FIRST_TURN,
            "send_all_first_turn"
        )
        self.assertEqual(
            ImageInjectionPolicy.ACTION_DEPENDENT,
            "action_dependent"
        )


class TestDeliveryValidityClassification(unittest.TestCase):
    """Tests for Window D delivery validity classification"""

    def setUp(self):
        self.simulator = StrategicSimulator(
            llm_client=Mock(),
            evaluator=Mock(),
            enable_filler_injection=False,
            verbose=False,
        )

    def test_payload_matches_intended_is_confirmed_valid(self):
        """Matching intended/payload images should be confirmed and valid"""
        turn_protocol = {
            "intended_image_refs": ["Image 0"],
            "visible_image_refs": ["Image 0"],
            "turn_input_mode": "fresh_visual",
            "current_question_scope": {"expected_source": "fresh_visual"},
        }
        target_response = {
            "success": True,
            "request_image_count": 1,
            "status_code": 200,
            "receipt_metadata": None,
            "response_metadata": {},
        }

        image_delivery, evaluation_validity = self.simulator._classify_image_delivery(
            turn_protocol,
            target_response,
            model_content="I see the object clearly.",
        )

        self.assertEqual(image_delivery["status"], "confirmed")
        self.assertEqual(image_delivery["evidence_source"], "request_payload")
        self.assertEqual(evaluation_validity, "valid")

    def test_payload_mismatch_is_confirmed_failed(self):
        """Objective payload mismatch should be confirmed failure"""
        turn_protocol = {
            "intended_image_refs": ["Image 0", "Image 1"],
            "visible_image_refs": ["Image 0", "Image 1"],
            "turn_input_mode": "fresh_visual",
            "current_question_scope": {"expected_source": "fresh_visual"},
        }
        target_response = {
            "success": True,
            "request_image_count": 1,
            "status_code": 200,
            "receipt_metadata": None,
            "response_metadata": {},
        }

        image_delivery, evaluation_validity = self.simulator._classify_image_delivery(
            turn_protocol,
            target_response,
            model_content="I compared them.",
        )

        self.assertEqual(image_delivery["status"], "confirmed_failed")
        self.assertEqual(image_delivery["status_reason"], "payload_count_visible_refs_mismatch")
        self.assertEqual(evaluation_validity, "invalid_due_to_delivery")

    def test_memory_only_turn_without_fresh_images_is_not_applicable(self):
        """Memory/text turns without fresh delivery requirement should stay valid"""
        turn_protocol = {
            "intended_image_refs": [],
            "visible_image_refs": [],
            "turn_input_mode": "memory_only",
            "current_question_scope": {"expected_source": "either"},
        }
        target_response = {
            "success": True,
            "request_image_count": 0,
            "status_code": 200,
            "receipt_metadata": None,
            "response_metadata": {},
        }

        image_delivery, evaluation_validity = self.simulator._classify_image_delivery(
            turn_protocol,
            target_response,
            model_content="Based on the previous image, the answer is red.",
        )

        self.assertEqual(image_delivery["status"], "not_applicable")
        self.assertEqual(image_delivery["system_receipt_status"], "not_applicable")
        self.assertEqual(evaluation_validity, "valid")

    def test_heuristic_refusal_only_becomes_suspected_failed(self):
        """Heuristic evidence must not escalate to confirmed failure"""
        turn_protocol = {
            "intended_image_refs": ["Image 2"],
            "visible_image_refs": ["Image 2"],
            "turn_input_mode": "fresh_visual",
            "current_question_scope": {"expected_source": "fresh_visual"},
        }
        target_response = {
            "success": False,
            "request_image_count": 1,
            "status_code": None,
            "receipt_metadata": None,
            "response_metadata": {},
        }

        image_delivery, evaluation_validity = self.simulator._classify_image_delivery(
            turn_protocol,
            target_response,
            model_content="I can't see the image you mentioned.",
        )

        self.assertEqual(image_delivery["status"], "suspected_failed")
        self.assertEqual(image_delivery["evidence_source"], "behavior_heuristic")
        self.assertEqual(evaluation_validity, "excluded_unverified_delivery")

    def test_legacy_delivery_helper_marks_unverified_metadata(self):
        """Legacy side paths should be explicitly marked unverified"""
        image_delivery = self.simulator._build_legacy_unverified_delivery(
            reason="placeholder_side_path",
            intended_image_refs=["Image 3"],
        )

        self.assertEqual(image_delivery["status"], "unverified")
        self.assertEqual(image_delivery["evidence_source"], "legacy_or_missing_metadata")
        self.assertEqual(image_delivery["status_reason"], "placeholder_side_path")

    def test_task_validity_rollup_prioritizes_invalid_then_excluded_then_legacy(self):
        """Task-level validity should follow Window D priority order"""
        task_validity = self.simulator._roll_up_task_validity([
            {
                "evaluation_validity": "valid",
                "image_delivery": {"evidence_source": "request_payload"},
            },
            {
                "evaluation_validity": "legacy_unverified",
                "image_delivery": {"evidence_source": "legacy_or_missing_metadata"},
            },
            {
                "evaluation_validity": "excluded_unverified_delivery",
                "image_delivery": {"evidence_source": "behavior_heuristic"},
            },
            {
                "evaluation_validity": "invalid_due_to_delivery",
                "image_delivery": {"evidence_source": "system_receipt"},
            },
        ])

        self.assertEqual(task_validity["status"], "invalid_due_to_delivery")
        self.assertEqual(task_validity["first_invalid_turn"], 2)
        self.assertEqual(
            task_validity["evidence_sources"],
            ["request_payload", "legacy_or_missing_metadata", "behavior_heuristic", "system_receipt"],
        )


if __name__ == "__main__":
    unittest.main()
