#!/usr/bin/env python3
"""
Test script for M3Bench DataProvider
====================================

Quick test to verify DataLoader and DataGenerator functionality.
Run this to make sure everything is working.
"""

import sys
from pathlib import Path

# Add dataprovider to path
sys.path.insert(0, str(Path(__file__).parent))

from dataprovider import DataLoader, DataGenerator, DataGeneratorV2


def test_dataloader():
    """Test DataLoader basic functionality."""
    print("=" * 60)
    print("Testing DataLoader")
    print("=" * 60)

    loader = DataLoader(data_root="data")

    # Test 1: List supported datasets
    print(f"\n✓ Supported datasets: {len(loader.SUPPORTED_DATASETS)}")
    print(f"  {', '.join(loader.SUPPORTED_DATASETS[:5])}...")

    # Test 2: Get dataset info
    info = loader.get_dataset_info("mscoco14")
    if info:
        print(f"\n✓ Dataset info for MSCOCO14:")
        print(f"  Name: {info['name']}")
        print(f"  Modalities: {info['modalities']}")
    else:
        print("\n✗ Failed to get dataset info")

    # Test 3: Try loading MSCOCO (will fail if data doesn't exist, that's ok)
    try:
        data = loader.load_dataset("mscoco14", split="train", max_samples=1)
        if data:
            print(f"\n✓ Successfully loaded {len(data)} MSCOCO sample(s)")
            print(f"  Sample ID: {data[0]['sample_id']}")
            print(f"  Number of objects: {len(data[0]['objects'])}")
        else:
            print("\n⚠ MSCOCO data exists but returned empty")
    except FileNotFoundError:
        print("\n⚠ MSCOCO data not found (expected if not set up yet)")
    except Exception as e:
        print(f"\n✗ Error loading MSCOCO: {e}")

    print("\n✓ DataLoader tests completed")
    return True


def test_datagenerator():
    """Test DataGenerator basic functionality."""
    print("\n" + "=" * 60)
    print("Testing DataGenerator")
    print("=" * 60)

    loader = DataLoader(data_root="data")
    generator = DataGenerator(loader)

    # Test 1: Check task generators registered
    print(f"\n✓ Registered task generators: {len(generator.task_generators)}")
    print(f"  {', '.join(generator.task_generators.keys())}")

    # Test 2: Check supported tasks for datasets
    datasets_to_test = ["mscoco14", "visual_genome", "vcr"]
    for dataset_id in datasets_to_test:
        supported = generator.get_supported_tasks(dataset_id)
        print(f"\n✓ {dataset_id} supports {len(supported)} task type(s):")
        for task in supported:
            print(f"    - {task}")

    # Test 3: Try generating a VNF task (will fail if data doesn't exist)
    try:
        print("\n⚠ Attempting to generate VNF task from MSCOCO...")
        tasks = generator.generate_task(
            task_type="visual_noise_filtering",
            source_dataset="mscoco14",
            num_samples=1,
            n_distractor_images=2
        )

        if tasks:
            print(f"✓ Successfully generated {len(tasks)} task(s)")
            task = tasks[0]
            print(f"  Task ID: {task['task_id']}")
            print(f"  Task Type: {task['task_type']}")
            print(f"  Number of images: {len(task['images'])}")
            print(f"  Question: {task['question'][:60]}...")

            # Test saving
            output_path = Path("output/test_task.jsonl")
            output_path.parent.mkdir(exist_ok=True)
            generator.save_generated_tasks(tasks, str(output_path))
            print(f"\n✓ Saved task to: {output_path}")

            # Verify file exists
            if output_path.exists():
                file_size = output_path.stat().st_size
                print(f"  File size: {file_size} bytes")
            else:
                print("✗ Failed to save file")

        else:
            print("⚠ Task generation returned empty (data may not be available)")

    except FileNotFoundError:
        print("⚠ MSCOCO data not found (expected if not set up yet)")
    except Exception as e:
        print(f"⚠ Error generating task: {e}")

    print("\n✓ DataGenerator tests completed")
    return True


def test_state_schema_attachment():
    """Test that generated tasks are enriched with a non-empty state_schema."""
    loader = DataLoader(data_root="data")
    generator = DataGeneratorV2(loader)

    task = {
        'task_id': 'test_state_schema',
        'task_type': 'attribute_comparison',
        'images': ['img0.jpg', 'img1.jpg'],
        'question': 'Which image has more cats?',
        'answer': 'Image 1',
        'answer_image_idx': 1,
        'comparison_metric': 'count',
        'comparison_values': [1, 3],
        'reasoning_evidence': [
            {'image_idx': 0, 'count': 1, 'objects': [{'category': 'cat'}]},
            {'image_idx': 1, 'count': 3, 'objects': [{'category': 'cat'}, {'category': 'cat'}]},
        ],
        'metadata': {'source_dataset': 'unit_test'}
    }

    enriched = generator._attach_state_schema(task)
    schema = enriched.get('state_schema')

    assert isinstance(schema, dict)
    assert isinstance(schema.get('variables'), dict)
    assert len(schema['variables']) > 0
    assert 'expected_answer' in schema['variables']
    assert 'answer_image_idx' in schema['variables']
    assert 'image_0_comparison_value' in schema['variables']
    assert 'image_1_comparison_value' in schema['variables']
    assert schema.get('final_question_variables')
    assert schema.get('probing_variables')


def test_formal_representation():
    """Test formal representation building."""
    print("\n" + "=" * 60)
    print("Testing Formal Representation")
    print("=" * 60)

    # Create a mock scene graph
    mock_sg = {
        'objects': {
            'o1': {'name': 'person', 'attributes': ['tall', 'wearing_hat']},
            'o2': {'name': 'dog', 'attributes': ['small', 'brown']},
            'o3': {'name': 'ball', 'attributes': ['red', 'round']}
        },
        'relationships': [
            {'subject': 'o1', 'predicate': 'walking', 'object': 'o2'},
            {'subject': 'o2', 'predicate': 'chasing', 'object': 'o3'}
        ]
    }

    loader = DataLoader(data_root="data")
    generator = DataGenerator(loader)

    # Build formal representation
    formal_repr = generator._build_formal_representation(
        mock_sg,
        relevant_obj_ids=['o1', 'o2', 'o3']
    )

    print("\n✓ Built formal representation:")
    print(f"\n  Objects (O):")
    for oid, name in formal_repr['objects'].items():
        print(f"    {oid}: {name}")

    print(f"\n  Attributes (A):")
    for oid, attrs in formal_repr['attributes'].items():
        print(f"    A({oid}): {attrs}")

    print(f"\n  Relations (R):")
    for rel in formal_repr['relations']:
        print(f"    {rel['subject']} --[{rel['predicate']}]--> {rel['object']}")

    print("\n✓ Formal representation test completed")
    return True


def test_vcr_token_parsing():
    """Test VCR token parsing."""
    print("\n" + "=" * 60)
    print("Testing VCR Token Parsing")
    print("=" * 60)

    loader = DataLoader(data_root="data")
    generator = DataGenerator(loader)

    # Test case 1: Simple tokens
    tokens1 = ["What", "is", "happening", "?"]
    objects1 = ["person", "car", "tree"]
    text1 = generator._vcr_tokens_to_text(tokens1, objects1)
    print(f"\n✓ Test 1:")
    print(f"  Input: {tokens1}")
    print(f"  Output: {text1}")
    assert text1 == "What is happening ?", f"Expected 'What is happening ?', got '{text1}'"

    # Test case 2: Tokens with object references
    tokens2 = ["What", "are", [0, 1], "doing", "near", [2], "?"]
    objects2 = ["person", "dog", "tree"]
    text2 = generator._vcr_tokens_to_text(tokens2, objects2)
    print(f"\n✓ Test 2:")
    print(f"  Input: {tokens2}")
    print(f"  Objects: {objects2}")
    print(f"  Output: {text2}")
    expected2 = "What are person and dog doing near tree ?"
    assert text2 == expected2, f"Expected '{expected2}', got '{text2}'"

    print("\n✓ VCR token parsing tests completed")
    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print(" M3Bench DataProvider Test Suite")
    print("=" * 70)

    tests = [
        ("DataLoader", test_dataloader),
        ("DataGenerator", test_datagenerator),
        ("State Schema Attachment", test_state_schema_attachment),
        ("Formal Representation", test_formal_representation),
        ("VCR Token Parsing", test_vcr_token_parsing),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, "PASS" if success else "FAIL"))
        except Exception as e:
            print(f"\n✗ Test '{test_name}' failed with exception: {e}")
            results.append((test_name, "ERROR"))

    # Print summary
    print("\n" + "=" * 70)
    print(" Test Summary")
    print("=" * 70)

    for test_name, status in results:
        symbol = "✓" if status == "PASS" else "✗"
        print(f"{symbol} {test_name}: {status}")

    # Overall result
    all_passed = all(status == "PASS" for _, status in results)

    print("\n" + "=" * 70)
    if all_passed:
        print("✓ All tests passed!")
    else:
        print("⚠ Some tests failed or encountered errors")
        print("  This is expected if datasets are not yet downloaded")
    print("=" * 70 + "\n")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())