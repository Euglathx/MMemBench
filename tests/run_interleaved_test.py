"""
Quick test: InterleavedBatchSimulator with run_76 data
======================================================

Loads 3 tasks (1 VNF + 1 RC + 1 AC) from run_76, runs them through
the new InterleavedBatchSimulator in round-robin mode.

Usage:
    python tests/run_interleaved_test.py
    python tests/run_interleaved_test.py --strategy interleaved
    python tests/run_interleaved_test.py --serial   # fallback to original BatchTaskSimulator behavior
"""

import sys
import json
import argparse
import logging
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.simulator import (
    LLMClient,
    BatchConfig,
)
from src.simulator.interleaved_batch import InterleavedBatchSimulator
from src.simulator.state_aware_evaluator import StateAwareEvaluator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

RUN_DIR = PROJECT_ROOT / "generated_tasks_v2" / "run_76"


def load_one_task(jsonl_path: Path) -> dict:
    """Load the first task from a JSONL file."""
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                return json.loads(line)
    raise ValueError(f"Empty file: {jsonl_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", default="round_robin",
                        choices=["round_robin", "interleaved"])
    parser.add_argument("--serial", action="store_true",
                        help="Use serial mode (original BatchTaskSimulator)")
    parser.add_argument("--max-turns", type=int, default=30,
                        help="Max turns per session (default: 30)")
    parser.add_argument("--min-turns-per-task", type=int, default=5)
    parser.add_argument("--max-turns-per-task", type=int, default=10)
    parser.add_argument("--verbose", "-v", action="store_true", default=True)
    parser.add_argument("--model", type=str, default=None,
                        help="Target model override")
    parser.add_argument("--core-model", type=str, default=None,
                        help="Core model override")
    args = parser.parse_args()

    tasks_dir = RUN_DIR / "tasks"

    # Pick 1 task from each of 3 different types
    task_files = [
        tasks_dir / "visual_noise_filtering_mscoco14.jsonl",
        tasks_dir / "relation_comparison_mscoco14.jsonl",
        tasks_dir / "attribute_comparison_mscoco14.jsonl",
    ]

    tasks = []
    for tf in task_files:
        if tf.exists():
            task = load_one_task(tf)
            tasks.append(task)
            logger.info(f"Loaded: {task['task_id']} ({task['task_type']})")
        else:
            logger.warning(f"File not found: {tf}")

    if not tasks:
        logger.error("No tasks loaded!")
        return 1

    print(f"\n{'='*60}")
    print(f"Interleaved Batch Test")
    print(f"  Tasks: {len(tasks)}")
    print(f"  Strategy: {'serial' if args.serial else args.strategy}")
    print(f"  Max turns: {args.max_turns}")
    print(f"{'='*60}\n")

    # --- Build components ---
    llm_kwargs = {}
    if args.model:
        llm_kwargs["target_model"] = args.model
    if args.core_model:
        llm_kwargs["core_model"] = args.core_model

    llm_client = LLMClient(**llm_kwargs)
    evaluator = StateAwareEvaluator()

    config = BatchConfig(
        max_turns_per_session=args.max_turns,
        min_turns_per_task=args.min_turns_per_task,
        max_turns_per_task=args.max_turns_per_task,
        transition_style="natural",
        enable_cross_task_memory_test=False,
    )

    sim = InterleavedBatchSimulator(
        llm_client=llm_client,
        evaluator=evaluator,
        config=config,
        verbose=args.verbose,
        interleave_mode=not args.serial,
        interleave_strategy=args.strategy,
    )

    # --- Run ---
    result = sim.run_batch(tasks)

    # --- Save results ---
    output_dir = PROJECT_ROOT / "interleaved_test_results"
    output_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"result_{ts}.json"

    result_dict = result.to_dict()
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result_dict, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n{'='*60}")
    print(f"Results saved to: {output_file}")
    print(f"  Tasks completed: {result.tasks_completed}/{result.tasks_attempted}")
    print(f"  Total turns: {result.total_turns}")
    if result.aggregate_scores:
        print(f"  Aggregate scores: {result.aggregate_scores}")
    print(f"{'='*60}")

    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
