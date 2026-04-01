"""
Test User Simulator with Generated Tasks
=========================================

Runs the LLM-driven user simulator on generated tasks and saves logs.
"""

import json
import sys
from pathlib import Path
from datetime import datetime
import logging

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from src.simulator.llm_user_simulator import LLMUserSimulator
from src.simulator.llm_client import LLMClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_tasks(tasks_dir: str, task_types: list = None, max_per_type: int = 1) -> list:
    """Load tasks from generated files"""
    tasks_path = Path(tasks_dir)
    all_tasks = []

    if task_types is None:
        task_types = ["attribute_comparison", "visual_noise_filtering"]

    for task_type in task_types:
        # Try both MSCOCO and VCR
        for dataset in ["mscoco14", "vcr"]:
            task_file = tasks_path / "tasks" / f"{task_type}_{dataset}.jsonl"
            if task_file.exists():
                with open(task_file, "r", encoding="utf-8") as f:
                    count = 0
                    for line in f:
                        if count >= max_per_type:
                            break
                        task = json.loads(line)
                        all_tasks.append(task)
                        count += 1
                logger.info(f"Loaded {count} tasks from {task_file.name}")

    return all_tasks


def main():
    print("="*70)
    print("M3Bench User Simulator Test")
    print("="*70)

    # Configuration
    tasks_dir = "generated_tasks_v2/run_12"
    output_dir = "simulator_test_log"
    max_tasks = 2  # Limit for testing
    max_turns = 15  # Limit turns per task

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Load tasks
    print("\n[1] Loading tasks...")
    tasks = load_tasks(
        tasks_dir,
        task_types=["attribute_comparison", "visual_noise_filtering"],
        max_per_type=1
    )

    if not tasks:
        print("No tasks found!")
        return

    print(f"Loaded {len(tasks)} tasks")
    for task in tasks[:5]:
        print(f"  - {task['task_id']}: {task['task_type']}")

    # Limit tasks for testing
    tasks = tasks[:max_tasks]

    # Initialize simulator
    print("\n[2] Initializing simulator...")
    client = LLMClient()

    # Test connection first
    conn_test = client.test_connection()
    print(f"  Core model: {'OK' if conn_test['core_model'] else 'FAILED'}")
    print(f"  Target model: {'OK' if conn_test['target_model'] else 'FAILED'}")

    if not all(conn_test.values()):
        print("API connection failed!")
        return

    simulator = LLMUserSimulator(
        llm_client=client,
        max_turns_per_task=max_turns,
        verbose=True
    )

    # Run tasks
    print("\n[3] Running tasks...")
    results = []

    for i, task in enumerate(tasks):
        print(f"\n{'='*60}")
        print(f"Task {i+1}/{len(tasks)}: {task['task_id']}")
        print(f"{'='*60}")

        try:
            result = simulator.run_task(task)
            results.append(result)
        except Exception as e:
            import traceback
            logger.error(f"Task failed: {e}")
            traceback.print_exc()
            results.append({
                "task_id": task["task_id"],
                "error": str(e)
            })

    # Export logs
    print("\n[4] Exporting logs...")
    log_path = simulator.export_log(output_dir)

    # Create readable summary
    summary_file = output_path / "readable_summary.txt"
    with open(summary_file, "w", encoding="utf-8") as f:
        f.write("M3Bench User Simulator Test Summary\n")
        f.write("="*50 + "\n\n")
        f.write(f"Run Time: {datetime.now().isoformat()}\n")
        f.write(f"Tasks Run: {len(results)}\n")
        f.write(f"Max Turns per Task: {max_turns}\n\n")

        f.write("Results:\n")
        f.write("-"*50 + "\n")
        for result in results:
            f.write(f"\nTask: {result.get('task_id', 'unknown')}\n")
            f.write(f"  Type: {result.get('task_type', 'unknown')}\n")
            f.write(f"  Turns: {result.get('turns_executed', 0)}\n")
            f.write(f"  Status: {result.get('final_status', 'unknown')}\n")
            if 'error' in result:
                f.write(f"  Error: {result['error']}\n")

        f.write("\n" + "="*50 + "\n")
        f.write("See JSON files for detailed logs.\n")

    print(f"\n[5] Complete!")
    print(f"Logs saved to: {output_path}")
    print(f"  - readable_summary.txt")
    print(f"  - run_log_*.json")
    print(f"  - memory_state_*.json")
    print(f"  - summary_*.json")

    # Print final statistics
    print("\n" + "="*50)
    print("Statistics:")
    stats = simulator.memory.get_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()