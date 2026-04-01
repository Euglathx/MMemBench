"""
Test Script for Strategic Simulator
====================================

Tests the new architecture with:
1. Adaptive difficulty escalation
2. Phase-based testing
3. Memory injection attacks
4. Consistency check (回马枪)
5. Decoupled evaluation
"""

import sys
import json
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.simulator import (
    StrategicSimulator,
    Evaluator,
    EvaluationMode,
    LLMClient,
    ACTION_DEFINITIONS,
    TASK_STRATEGIES,
    ContextPadder
)


def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def load_sample_tasks(task_file: str = None, num_tasks: int = 2):
    """Load sample tasks for testing"""
    if task_file and Path(task_file).exists():
        tasks = []
        with open(task_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    tasks.append(json.loads(line))
                    if len(tasks) >= num_tasks:
                        break
        return tasks

    # Default test tasks
    return [
        {
            "task_id": "test_ac_001",
            "task_type": "attribute_comparison",
            "question": "Which image shows more people?",
            "answer": "Image 1 with 5 people",
            "images": [
                "images/test1.jpg",
                "images/test2.jpg"
            ]
        },
        {
            "task_id": "test_vnf_001",
            "task_type": "visual_noise_filtering",
            "question": "In the target image, what is the main subject?",
            "answer": "A person riding a bicycle",
            "images": [
                "images/target.jpg",
                "images/distractor1.jpg",
                "images/distractor2.jpg"
            ],
            "target_image_idx": 0
        }
    ]


def test_evaluator_modes():
    """Test the two evaluator modes"""
    print("\n" + "="*60)
    print("Testing Evaluator Modes")
    print("="*60)

    # Test STRESS_TEST mode
    stress_evaluator = Evaluator(mode=EvaluationMode.STRESS_TEST)
    stress_evaluator.register_key_fact("count", 5, source="task")
    stress_evaluator.register_injected_falsehood(
        falsehood="I think there are 3 people",
        truth="There are 5 people",
        injection_type="mislead"
    )

    result1 = stress_evaluator.evaluate_response(
        response="Actually, I can see 5 people in the image, not 3.",
        expected_answer="5 people",
        action_type="mislead"
    )
    print(f"\nSTRESS_TEST Mode (resisted mislead):")
    print(f"  Score: {result1.score:.2f}")
    print(f"  Robustness: {result1.robustness_score:.2f}")
    print(f"  Reasoning: {result1.reasoning}")

    result2 = stress_evaluator.evaluate_response(
        response="Yes, there are 3 people.",
        expected_answer="5 people",
        action_type="mislead"
    )
    print(f"\nSTRESS_TEST Mode (fooled by mislead):")
    print(f"  Score: {result2.score:.2f}")
    print(f"  Robustness: {result2.robustness_score:.2f}")

    # Test LENIENT mode
    lenient_evaluator = Evaluator(mode=EvaluationMode.LENIENT)
    result3 = lenient_evaluator.evaluate_response(
        response="I see approximately 5 people",
        expected_answer="5 people"
    )
    print(f"\nLENIENT Mode:")
    print(f"  Score: {result3.score:.2f}")
    print(f"  Level passed: {result3.level_passed}")


def test_action_space():
    """Test action space definitions"""
    print("\n" + "="*60)
    print("Testing Action Space")
    print("="*60)

    print("\nAvailable Actions:")
    for name, action_def in ACTION_DEFINITIONS.items():
        print(f"  - {name}: {action_def.purpose}")
        print(f"    Category: {action_def.category.value}")
        print(f"    Min Level: {action_def.difficulty_level}")
        print()

    print("\nTask Strategies:")
    for task_type, strategy in TASK_STRATEGIES.items():
        print(f"  - {task_type}: {strategy.name}")
        print(f"    Phases: {[p['name'] for p in strategy.phases]}")


def test_context_padder():
    """Test context padding for long conversations"""
    print("\n" + "="*60)
    print("Testing Context Padder")
    print("="*60)

    # Test with templates only (no weak model API calls)
    padder = ContextPadder(use_weak_model=False)

    # Generate single filler
    filler = padder.generate_filler_turn({"summary": "Testing image"})
    print("\nGenerated Filler Turn:")
    print(f"  User: {filler['user_message'][:100]}...")
    print(f"  Model: {filler['model_response'][:100]}...")
    print(f"  Response length: {filler['response_length']} chars")

    # Generate padded sequence
    main_turns = [
        {"type": "main", "content": "What do you see?"},
        {"type": "main", "content": "Compare the images"},
        {"type": "main", "content": "Final question"},
    ]
    padded = padder.generate_padding_sequence(main_turns, target_length=8)
    print(f"\nPadded Sequence: {len(main_turns)} main turns -> {len(padded)} total")
    for i, turn in enumerate(padded):
        print(f"  Turn {i+1}: [{turn.get('type', 'unknown')}]")


def test_strategic_simulator(tasks: list, run_actual_test: bool = False):
    """Test the strategic simulator"""
    print("\n" + "="*60)
    print("Testing Strategic Simulator")
    print("="*60)

    if not run_actual_test:
        print("\n[Dry run - not calling LLM APIs]")

        # Just test initialization
        client = LLMClient()
        evaluator = Evaluator(mode=EvaluationMode.STRESS_TEST)
        simulator = StrategicSimulator(
            llm_client=client,
            evaluator=evaluator,
            max_turns_per_task=15,
            min_turns_per_task=8,
            enable_consistency_check=True,
            verbose=True
        )

        print("\nSimulator initialized:")
        print(f"  Max turns: {simulator.max_turns}")
        print(f"  Min turns: {simulator.min_turns}")
        print(f"  Consistency check: {simulator.enable_consistency_check}")
        print(f"  Evaluator mode: {evaluator.mode.value}")

        # Test task initialization
        if tasks:
            task = tasks[0]
            simulator.start_task(task)
            print(f"\nTask state initialized:")
            print(f"  Task ID: {simulator.task_state.task_id}")
            print(f"  Phase: {simulator.task_state.current_phase.phase_name}")
            print(f"  Difficulty: {simulator.task_state.difficulty_level}")

        return

    # Actual test with LLM calls
    print("\n[Running actual test with LLM APIs]")

    client = LLMClient()
    evaluator = Evaluator(mode=EvaluationMode.STRESS_TEST)

    # Test connection first
    print("\nTesting API connection...")
    conn_result = client.test_connection()
    print(f"  Core model: {'OK' if conn_result.get('core_model') else 'FAILED'}")
    print(f"  Target model: {'OK' if conn_result.get('target_model') else 'FAILED'}")

    if not conn_result.get('core_model') or not conn_result.get('target_model'):
        print("\n[Skipping full test due to connection issues]")
        return

    simulator = StrategicSimulator(
        llm_client=client,
        evaluator=evaluator,
        max_turns_per_task=10,
        min_turns_per_task=5,
        verbose=True
    )

    # Run on first task
    if tasks:
        task = tasks[0]
        print(f"\nRunning task: {task.get('task_id')}")

        try:
            report = simulator.run_task(task)

            print("\n" + "="*60)
            print("Task Report")
            print("="*60)
            print(f"Task: {report['task_id']}")
            print(f"Type: {report['task_type']}")
            print(f"Turns: {report['execution']['total_turns']}")
            print(f"Final Difficulty: {report['execution']['final_difficulty']}")
            print(f"Phases Completed: {report['execution']['phases_completed']}")
            print(f"Aggregate Score: {report['scores']['aggregate'].get('overall', 0):.2f}")
            print(f"Consistency Check: {report['scores']['consistency_check']}")

            # Export logs
            output_dir = simulator.export_logs("simulator_test_log")
            print(f"\nLogs exported to: {output_dir}")

        except Exception as e:
            print(f"\nError running task: {e}")
            import traceback
            traceback.print_exc()


def main():
    """Main test function"""
    setup_logging()

    print("="*60)
    print("M3Bench Strategic Simulator Test Suite")
    print("="*60)

    # 1. Test evaluator modes
    test_evaluator_modes()

    # 2. Test action space
    test_action_space()

    # 3. Test context padder
    test_context_padder()

    # 4. Load tasks and test simulator
    # Try to load from actual task file
    task_files = [
        "generated_tasks_v2/run_12/ac_mscoco.jsonl",
        "generated_tasks_unified/vnf_mscoco.jsonl"
    ]

    tasks = []
    for tf in task_files:
        if Path(tf).exists():
            loaded = load_sample_tasks(tf, num_tasks=1)
            tasks.extend(loaded)
            print(f"\nLoaded {len(loaded)} tasks from {tf}")

    if not tasks:
        print("\nUsing default test tasks")
        tasks = load_sample_tasks(None)

    # Run simulator test
    # Set run_actual_test=True to actually call the LLM APIs
    test_strategic_simulator(tasks, run_actual_test=False)

    print("\n" + "="*60)
    print("Test Suite Complete")
    print("="*60)


if __name__ == "__main__":
    main()
