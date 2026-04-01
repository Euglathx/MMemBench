"""
Unit tests for image path resolution in StrategicSimulator

Phase 2 Task 2.1: Image Sending Pipeline Fix
==============================================

This test suite validates the improved image path resolution logic
to prevent the images_sent empty list issue discovered in Phase 1 Task 1.1.
"""

import unittest
import tempfile
import shutil
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from simulator.strategic_simulator import StrategicSimulator, TaskState, PhaseState


class TestImageResolution(unittest.TestCase):
    """Test image path resolution functionality"""

    def setUp(self):
        """Set up test environment with mock directory structure"""
        # Create temporary directory for testing
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = Path.cwd()

        # Change to test directory
        import os
        os.chdir(self.test_dir)

        # Create mock directory structure
        self.setup_mock_directories()

        # Create simulator instance
        self.simulator = StrategicSimulator(verbose=False)

    def tearDown(self):
        """Clean up test environment"""
        import os
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)

    def setup_mock_directories(self):
        """Create mock directory structure similar to actual project"""
        # Create generated_tasks_v2/run_XX/images structure
        run_dirs = ["run_1", "run_10", "run_18"]
        for run_dir in run_dirs:
            images_dir = Path(self.test_dir) / "generated_tasks_v2" / run_dir / "images"
            images_dir.mkdir(parents=True, exist_ok=True)

            # Create mock image files
            for img_name in ["COCO_val2014_000000578292.jpg", "COCO_val2014_000000157269.jpg"]:
                (images_dir / img_name).touch()

        # Create common images directory at project root
        common_images_dir = Path(self.test_dir) / "images"
        common_images_dir.mkdir(exist_ok=True)
        (common_images_dir / "test_image.jpg").touch()

    def test_direct_path_resolution(self):
        """Test Strategy 1: Direct path resolution"""
        # Create a task with direct path
        task = {
            "task_id": "test_direct",
            "task_type": "attribute_comparison",
            "question": "Test question",
            "answer": "Test answer",
            "images": ["images/test_image.jpg"]
        }

        self.simulator.start_task(task)
        images = self.simulator._get_images_for_turn("guidance")

        self.assertEqual(len(images), 1, "Should resolve 1 image")
        self.assertTrue(Path(images[0]).exists(), "Resolved path should exist")

    def test_run_directory_resolution(self):
        """Test Strategy 3: Resolution from generated_tasks_v2/run_XX/images"""
        task = {
            "task_id": "test_run_dir",
            "task_type": "attribute_comparison",
            "question": "Test question",
            "answer": "Test answer",
            "images": [
                "images/COCO_val2014_000000578292.jpg",
                "images/COCO_val2014_000000157269.jpg"
            ]
        }

        self.simulator.start_task(task)
        images = self.simulator._get_images_for_turn("guidance")

        self.assertEqual(len(images), 2, f"Should resolve 2 images, got {len(images)}")
        for img_path in images:
            self.assertTrue(Path(img_path).exists(), f"Image should exist: {img_path}")

    def test_multiple_images_resolution(self):
        """Test resolving multiple images from different sources"""
        task = {
            "task_id": "test_multiple",
            "task_type": "attribute_comparison",
            "question": "Test question",
            "answer": "Test answer",
            "images": [
                "images/COCO_val2014_000000578292.jpg",
                "images/test_image.jpg"
            ]
        }

        self.simulator.start_task(task)
        images = self.simulator._get_images_for_turn("follow_up")

        self.assertEqual(len(images), 2, "Should resolve 2 images from different sources")

    def test_nonexistent_image_handling(self):
        """Test handling of non-existent images"""
        task = {
            "task_id": "test_nonexistent",
            "task_type": "attribute_comparison",
            "question": "Test question",
            "answer": "Test answer",
            "images": [
                "images/COCO_val2014_000000578292.jpg",
                "images/NONEXISTENT_FILE.jpg"
            ]
        }

        self.simulator.start_task(task)

        # Should not raise error in non-verbose mode
        images = self.simulator._get_images_for_turn("guidance")

        # Should resolve only the existing image
        self.assertEqual(len(images), 1, "Should resolve only existing images")

    def test_empty_images_list(self):
        """Test handling of empty images list"""
        task = {
            "task_id": "test_empty",
            "task_type": "attribute_comparison",
            "question": "Test question",
            "answer": "Test answer",
            "images": []
        }

        self.simulator.start_task(task)
        images = self.simulator._get_images_for_turn("guidance")

        self.assertEqual(len(images), 0, "Should return empty list for tasks with no images")

    def test_all_images_fail_verbose_mode(self):
        """Test that verbose mode raises error when all images fail to resolve"""
        # Re-create simulator with verbose=True
        simulator_verbose = StrategicSimulator(verbose=True)

        task = {
            "task_id": "test_all_fail",
            "task_type": "attribute_comparison",
            "question": "Test question",
            "answer": "Test answer",
            "images": [
                "images/NONEXISTENT1.jpg",
                "images/NONEXISTENT2.jpg"
            ]
        }

        simulator_verbose.start_task(task)

        # Should raise RuntimeError in verbose mode when all images fail
        with self.assertRaises(RuntimeError) as context:
            simulator_verbose._get_images_for_turn("guidance")

        self.assertIn("CRITICAL", str(context.exception))
        self.assertIn("Failed to resolve ANY images", str(context.exception))

    def test_resolve_single_image_path_strategies(self):
        """Test individual resolution strategies"""
        # Create simulator with task state
        task = {
            "task_id": "test_strategies",
            "task_type": "attribute_comparison",
            "question": "Test",
            "answer": "Test",
            "images": ["images/COCO_val2014_000000578292.jpg"]
        }
        self.simulator.start_task(task)

        # Test resolution
        resolved = self.simulator._resolve_single_image_path(
            "images/COCO_val2014_000000578292.jpg",
            img_idx=0
        )

        self.assertIsNotNone(resolved, "Should resolve the image path")
        self.assertTrue(Path(resolved).exists(), "Resolved path should exist")

    def test_newest_run_directory_priority(self):
        """Test that newer run directories are checked first"""
        # Create a newer run directory with a unique image
        newest_run = Path(self.test_dir) / "generated_tasks_v2" / "run_99"
        newest_images = newest_run / "images"
        newest_images.mkdir(parents=True)

        unique_image = "UNIQUE_IMAGE_999.jpg"
        (newest_images / unique_image).touch()

        # Also create the same image in an older run directory
        older_run = Path(self.test_dir) / "generated_tasks_v2" / "run_1" / "images"
        (older_run / unique_image).touch()

        task = {
            "task_id": "test_priority",
            "task_type": "attribute_comparison",
            "question": "Test",
            "answer": "Test",
            "images": [f"images/{unique_image}"]
        }

        self.simulator.start_task(task)
        images = self.simulator._get_images_for_turn("guidance")

        self.assertEqual(len(images), 1)
        # Should resolve from the newer directory (run_99)
        self.assertIn("run_99", images[0], f"Should use newest run directory, got: {images[0]}")

    def test_image_filename_only_resolution(self):
        """Test Strategy 4b: Resolution using only filename in common directories"""
        # Create a file with nested path structure
        nested_path = "some/nested/path/test_nested.jpg"
        task = {
            "task_id": "test_filename",
            "task_type": "attribute_comparison",
            "question": "Test",
            "answer": "Test",
            "images": [nested_path]
        }

        # Create the file in common images directory with just the filename
        common_dir = Path(self.test_dir) / "images"
        (common_dir / "test_nested.jpg").touch()

        self.simulator.start_task(task)
        images = self.simulator._get_images_for_turn("guidance")

        self.assertEqual(len(images), 1, "Should resolve using filename only")
        self.assertTrue("test_nested.jpg" in images[0])


class TestImageResolutionIntegration(unittest.TestCase):
    """Integration tests using actual project structure"""

    def setUp(self):
        """Set up using actual project structure"""
        # Find project root (where generated_tasks_v2 exists)
        current = Path(__file__).parent
        while current.parent != current:
            if (current / "generated_tasks_v2").exists():
                self.project_root = current
                break
            current = current.parent
        else:
            self.skipTest("Cannot find project root with generated_tasks_v2")

        self.original_cwd = Path.cwd()
        import os
        os.chdir(self.project_root)

        self.simulator = StrategicSimulator(verbose=False)

    def tearDown(self):
        """Restore working directory"""
        import os
        os.chdir(self.original_cwd)

    def test_actual_coco_images(self):
        """Test resolution of actual COCO images from run logs"""
        # Find an actual run directory with images
        run_dirs = list((self.project_root / "generated_tasks_v2").glob("run_*"))
        if not run_dirs:
            self.skipTest("No run directories found")

        # Find first run directory with images
        for run_dir in run_dirs:
            images_dir = run_dir / "images"
            if images_dir.exists():
                image_files = list(images_dir.glob("*.jpg"))
                if image_files:
                    # Use first few images
                    test_images = [f"images/{img.name}" for img in image_files[:3]]

                    task = {
                        "task_id": "integration_test",
                        "task_type": "attribute_comparison",
                        "question": "Test with real images",
                        "answer": "Test",
                        "images": test_images
                    }

                    self.simulator.start_task(task)
                    resolved = self.simulator._get_images_for_turn("guidance")

                    self.assertEqual(
                        len(resolved),
                        len(test_images),
                        f"Should resolve all {len(test_images)} actual images"
                    )

                    for img_path in resolved:
                        self.assertTrue(
                            Path(img_path).exists(),
                            f"Resolved image should exist: {img_path}"
                        )

                    # Test passed, exit
                    return

        self.skipTest("No run directories with images found")


if __name__ == "__main__":
    unittest.main()
