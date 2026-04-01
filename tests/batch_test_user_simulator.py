"""
Batch Test User Simulator - Enhanced Version
=============================================

Batch generation of conversations with:
- Command-line argument support
- Progress bar
- Error retry mechanism
- Batch saving
- Statistics reporting
"""

import json
import sys
import argparse
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
import logging

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.simulator.llm_user_simulator import LLMUserSimulator
from src.simulator.llm_client import LLMClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_tasks(tasks_dir: str, task_types: list = None, max_total: int = 100) -> list:
    """
    Load tasks from generated files

    Args:
        tasks_dir: Directory containing task files
        task_types: List of task types to load
        max_total: Maximum total tasks to load

    Returns:
        List of tasks
    """
    tasks_path = Path(tasks_dir)
    all_tasks = []

    if task_types is None:
        task_types = [
            "attribute_comparison",
            "visual_noise_filtering",
            "attribute_bridge_reasoning",
            "relation_comparison"
        ]

    logger.info(f"Loading tasks from {tasks_dir}")
    logger.info(f"Task types: {task_types}")

    for task_type in task_types:
        # Try multiple datasets
        for dataset in ["mscoco14", "vcr", "visual_genome"]:
            task_file = tasks_path / "tasks" / f"{task_type}_{dataset}.jsonl"
            if task_file.exists():
                with open(task_file, "r", encoding="utf-8") as f:
                    count = 0
                    for line in f:
                        if len(all_tasks) >= max_total:
                            break
                        try:
                            task = json.loads(line)
                            all_tasks.append(task)
                            count += 1
                        except json.JSONDecodeError:
                            continue
                    logger.info(f"Loaded {count} tasks from {task_file.name}")

                if len(all_tasks) >= max_total:
                    break

        if len(all_tasks) >= max_total:
            break

    return all_tasks


def save_progress(progress_file: Path, completed_ids: List[str], failed_ids: List[str],
                 total_target: int, start_time: float):
    """Save progress to JSON file"""
    progress_data = {
        "batch_id": f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "started_at": datetime.fromtimestamp(start_time).isoformat(),
        "target_count": total_target,
        "completed_count": len(completed_ids),
        "failed_count": len(failed_ids),
        "completed_task_ids": completed_ids,
        "failed_task_ids": failed_ids,
        "last_updated": datetime.now().isoformat()
    }

    with open(progress_file, 'w', encoding='utf-8') as f:
        json.dump(progress_data, f, indent=2, ensure_ascii=False)


def generate_statistics_report(results: List[Dict], output_dir: Path,
                               start_time: float, end_time: float):
    """Generate comprehensive statistics report"""
    successful = [r for r in results if 'error' not in r]
    failed = [r for r in results if 'error' in r]

    # Task type distribution
    task_type_dist = {}
    for r in successful:
        task_type = r.get('task_type', 'unknown')
        task_type_dist[task_type] = task_type_dist.get(task_type, 0) + 1

    # Average turns
    avg_turns = sum(r.get('turns_executed', 0) for r in successful) / len(successful) if successful else 0

    # Total tokens (if available)
    total_tokens = sum(r.get('total_tokens', 0) for r in successful)

    stats = {
        "batch_id": f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "total_conversations": len(results),
        "successful": len(successful),
        "failed": len(failed),
        "success_rate": len(successful) / len(results) if results else 0,
        "task_type_distribution": task_type_dist,
        "average_turns": round(avg_turns, 2),
        "total_tokens_used": total_tokens,
        "estimated_cost_usd": round(total_tokens * 0.000005, 2),  # Rough estimate
        "duration_seconds": round(end_time - start_time, 2),
        "start_time": datetime.fromtimestamp(start_time).isoformat(),
        "end_time": datetime.fromtimestamp(end_time).isoformat()
    }

    # Save statistics
    stats_file = output_dir / "batch_statistics.json"
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

    logger.info(f"Statistics saved to {stats_file}")
    return stats


def print_progress_bar(current: int, total: int, prefix: str = '', suffix: str = '',
                      length: int = 50, fill: str = '█'):
    """Print a progress bar"""
    percent = f"{100 * (current / float(total)):.1f}"
    filled_length = int(length * current // total)
    bar = fill * filled_length + '-' * (length - filled_length)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end='', flush=True)
    if current == total:
        print()


def main():
    parser = argparse.ArgumentParser(
        description='Batch generate conversations using LLM User Simulator'
    )
    parser.add_argument('--num-tasks', type=int, default=100,
                       help='Number of tasks to run (default: 100)')
    parser.add_argument('--max-turns', type=int, default=30,
                       help='Maximum turns per task (default: 30)')
    parser.add_argument('--min-turns', type=int, default=20,
                       help='Minimum turns per task (default: 20)')
    parser.add_argument('--task-dir', type=str, default='generated_tasks_v2/run_12',
                       help='Directory containing task files')
    parser.add_argument('--output-dir', type=str, default='simulator_test_log',
                       help='Output directory for logs')
    parser.add_argument('--batch-size', type=int, default=10,
                       help='Save progress every N tasks (default: 10)')
    parser.add_argument('--task-types', nargs='+', default=None,
                       help='Task types to include (default: all)')
    parser.add_argument('--max-retries', type=int, default=3,
                       help='Maximum retries per task (default: 3)')
    parser.add_argument('--verbose', action='store_true',
                       help='Print detailed logs')

    args = parser.parse_args()

    print("="*70)
    print("M3Bench Batch Conversation Generator")
    print("="*70)
    print(f"\nConfiguration:")
    print(f"  Target conversations: {args.num_tasks}")
    print(f"  Turns per conversation: {args.min_turns}-{args.max_turns}")
    print(f"  Task directory: {args.task_dir}")
    print(f"  Output directory: {args.output_dir}")
    print(f"  Batch size: {args.batch_size}")
    print(f"  Max retries: {args.max_retries}")

    # Create output directory
    output_path = Path(args.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Load tasks
    print(f"\n[1] Loading tasks...")
    start_time = time.time()

    tasks = load_tasks(
        args.task_dir,
        task_types=args.task_types,
        max_total=args.num_tasks
    )

    if not tasks:
        print("❌ No tasks found!")
        return

    print(f"✓ Loaded {len(tasks)} tasks")
    if len(tasks) < args.num_tasks:
        print(f"⚠️  Warning: Only {len(tasks)} tasks available (requested {args.num_tasks})")

    # Show task distribution
    task_type_counts = {}
    for task in tasks:
        task_type = task.get('task_type', 'unknown')
        task_type_counts[task_type] = task_type_counts.get(task_type, 0) + 1

    print(f"\nTask distribution:")
    for task_type, count in task_type_counts.items():
        print(f"  - {task_type}: {count}")

    # Initialize simulator
    print(f"\n[2] Initializing simulator...")
    client = LLMClient()

    # Test connection
    conn_test = client.test_connection()
    print(f"  Core model: {'✓ OK' if conn_test['core_model'] else '❌ FAILED'}")
    print(f"  Target model: {'✓ OK' if conn_test['target_model'] else '❌ FAILED'}")

    if not all(conn_test.values()):
        print("\n❌ API connection failed! Please check your API configuration.")
        return

    simulator = LLMUserSimulator(
        llm_client=client,
        max_turns_per_task=args.max_turns,
        verbose=args.verbose
    )

    # Run tasks
    print(f"\n[3] Running {len(tasks)} tasks...")
    print(f"{'='*70}\n")

    results = []
    completed_ids = []
    failed_ids = []
    progress_file = output_path / "batch_progress.json"

    for i, task in enumerate(tasks):
        task_id = task.get('task_id', f'task_{i}')

        # Progress bar
        print_progress_bar(
            i, len(tasks),
            prefix=f'Progress',
            suffix=f'({i}/{len(tasks)}) Current: {task_id[:30]}...'
        )

        # Try with retries
        success = False
        last_error = None

        for attempt in range(args.max_retries):
            try:
                result = simulator.run_task(task)
                results.append(result)
                completed_ids.append(task_id)
                success = True
                break
            except Exception as e:
                last_error = str(e)
                if attempt < args.max_retries - 1:
                    logger.warning(f"Task {task_id} failed (attempt {attempt+1}/{args.max_retries}): {e}")
                    time.sleep(2)  # Wait before retry
                else:
                    logger.error(f"Task {task_id} failed after {args.max_retries} attempts: {e}")

        if not success:
            results.append({
                "task_id": task_id,
                "task_type": task.get('task_type', 'unknown'),
                "error": last_error
            })
            failed_ids.append(task_id)

        # Save progress periodically
        if (i + 1) % args.batch_size == 0:
            save_progress(progress_file, completed_ids, failed_ids, len(tasks), start_time)
            logger.info(f"Progress saved: {len(completed_ids)} completed, {len(failed_ids)} failed")

    # Final progress bar
    print_progress_bar(len(tasks), len(tasks), prefix='Progress', suffix='Complete!')

    end_time = time.time()

    # Export logs
    print(f"\n[4] Exporting logs...")
    log_path = simulator.export_log(args.output_dir)
    print(f"✓ Logs exported to {log_path}")

    # Save final progress
    save_progress(progress_file, completed_ids, failed_ids, len(tasks), start_time)

    # Generate statistics
    print(f"\n[5] Generating statistics...")
    stats = generate_statistics_report(results, output_path, start_time, end_time)

    # Print summary
    print(f"\n{'='*70}")
    print("BATCH GENERATION COMPLETE")
    print(f"{'='*70}")
    print(f"\n📊 Summary:")
    print(f"  Total conversations: {stats['total_conversations']}")
    print(f"  Successful: {stats['successful']} ({stats['success_rate']*100:.1f}%)")
    print(f"  Failed: {stats['failed']}")
    print(f"  Average turns: {stats['average_turns']}")
    print(f"  Total tokens: {stats['total_tokens_used']:,}")
    print(f"  Estimated cost: ${stats['estimated_cost_usd']:.2f}")
    print(f"  Duration: {stats['duration_seconds']:.1f}s ({stats['duration_seconds']/60:.1f} min)")

    print(f"\n📁 Output files:")
    print(f"  - {output_path}/run_log_*.json")
    print(f"  - {output_path}/memory_state_*.json")
    print(f"  - {output_path}/summary_*.json")
    print(f"  - {output_path}/batch_statistics.json")
    print(f"  - {output_path}/batch_progress.json")

    if stats['failed'] > 0:
        print(f"\n⚠️  {stats['failed']} tasks failed. Check logs for details.")
        print(f"Failed task IDs: {failed_ids[:5]}{'...' if len(failed_ids) > 5 else ''}")

    print(f"\n✅ Batch generation complete!")


if __name__ == "__main__":
    main()
