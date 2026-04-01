"""
Experiment: LLM Judge Weight vs Turn Count Analysis
=====================================================

This script runs experiments to analyze the effect of:
1. LLM Judge Weight (0.4, 0.6, 0.8, 1.0) - balance between hard rules and LLM evaluation
2. Turn Count (10, 20, 30, 40, 50) - conversation length

Metrics tracked:
1. Overall Score (综合分数): Weighted combination of all dimensions
2. Robustness Score (鲁棒性): Resistance to misleading information
3. Consistency Score (一致性): Consistency across turns
4. Memory Retention (记忆保持): Retention of key facts
5. Faithfulness (忠实度): Sticking to visual evidence

Output:
- Experiment results JSON
- Multiple plots saved to experiment_images/
"""

import sys
import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field
import random

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Import required modules
try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    import numpy as np
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    print("Warning: matplotlib not available, plots will not be generated")

from src.simulator import (
    StrategicSimulator,
    StatefulStrategicSimulator,
    Evaluator,
    StateAwareEvaluator,
    EvaluationMode,
    LLMClient,
    ContextPadder
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ExperimentConfig:
    """Configuration for experiment run"""
    llm_judge_weights: List[float] = field(default_factory=lambda: [0.4, 0.6, 0.8, 1.0])
    turn_counts: List[int] = field(default_factory=lambda: [10, 20, 30, 40, 50])
    num_tasks_per_config: int = 3  # Number of tasks to run per configuration
    output_dir: str = "experiment_images"
    verbose: bool = True
    enable_stateful_runtime: bool = False
    require_state_schema: bool = False


@dataclass
class TaskResult:
    """Result from a single task run"""
    task_id: str
    llm_judge_weight: float
    max_turns: int
    actual_turns: int
    overall_score: float
    robustness_score: float
    consistency_score: float
    memory_retention: float
    faithfulness_score: float
    final_difficulty: int
    phases_completed: List[str]
    consistency_check_passed: bool
    state_eval_valid: bool = True
    state_eval_invalid_reason: Optional[str] = None


class ExperimentRunner:
    """Run experiments with different configurations"""

    def __init__(self, config: ExperimentConfig):
        self.config = config
        self.results: List[TaskResult] = []
        output_dir = Path(config.output_dir)
        self.output_dir = output_dir if output_dir.is_absolute() else project_root / output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Sample tasks for experiments
        self.tasks = self._load_sample_tasks()

    def _load_sample_tasks(self) -> List[Dict[str, Any]]:
        """Load sample tasks for experiments"""
        # Try to load from existing task files
        task_files = [
            "generated_tasks_unified/vnf_mscoco.jsonl",
            "generated_tasks_v2/run_12/ac_mscoco.jsonl"
        ]

        tasks = []
        for tf in task_files:
            tf_path = project_root / tf
            if tf_path.exists():
                with open(tf_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            try:
                                task = json.loads(line)
                                tasks.append(task)
                                if len(tasks) >= 10:  # Load up to 10 tasks
                                    break
                            except json.JSONDecodeError:
                                continue
                if tasks:
                    logger.info(f"Loaded {len(tasks)} tasks from {tf}")
                    break

        if not tasks:
            # Create synthetic tasks for testing
            logger.warning("No task files found, creating synthetic tasks")
            tasks = self._create_synthetic_tasks()

        return tasks

    def _create_synthetic_tasks(self) -> List[Dict[str, Any]]:
        """Create synthetic tasks for testing when real data unavailable"""
        return [
            {
                "task_id": f"synthetic_{i}",
                "task_type": "attribute_comparison",
                "question": f"Which image has more objects? (Test task {i})",
                "answer": f"Image 1 has more objects",
                "images": []  # No actual images for synthetic tasks
            }
            for i in range(5)
        ]

    def run_single_experiment(
        self,
        task: Dict[str, Any],
        llm_judge_weight: float,
        max_turns: int
    ) -> Optional[TaskResult]:
        """Run a single experiment with given configuration"""
        try:
            if self.config.enable_stateful_runtime or self.config.require_state_schema:
                schema_data = task.get("state_schema")
                if schema_data is None:
                    invalid_reason = "missing_state_schema"
                    if self.config.require_state_schema:
                        logger.warning(f"Skipping {task['task_id']}: {invalid_reason}")
                        return TaskResult(
                            task_id=task["task_id"],
                            llm_judge_weight=llm_judge_weight,
                            max_turns=max_turns,
                            actual_turns=0,
                            overall_score=0.0,
                            robustness_score=0.0,
                            consistency_score=0.0,
                            memory_retention=0.0,
                            faithfulness_score=0.0,
                            final_difficulty=1,
                            phases_completed=[],
                            consistency_check_passed=False,
                            state_eval_valid=False,
                            state_eval_invalid_reason=invalid_reason,
                        )

            # Create LLM client
            llm_client = LLMClient()

            # Create evaluator with specific weight
            evaluator = (
                StateAwareEvaluator(
                    mode=EvaluationMode.STRESS_TEST,
                    use_llm_judge=True,
                    llm_judge_weight=llm_judge_weight
                )
                if self.config.enable_stateful_runtime or self.config.require_state_schema
                else Evaluator(
                    mode=EvaluationMode.STRESS_TEST,
                    use_llm_judge=True,
                    llm_judge_weight=llm_judge_weight
                )
            )

            simulator_cls = (
                StatefulStrategicSimulator
                if self.config.enable_stateful_runtime or self.config.require_state_schema
                else StrategicSimulator
            )

            # Create simulator with specific turn count
            simulator = simulator_cls(
                llm_client=llm_client,
                evaluator=evaluator,
                max_turns_per_task=max_turns,
                min_turns_per_task=max(5, max_turns // 2),  # At least half of max
                enable_consistency_check=True,
                enable_filler_injection=True,
                filler_interval=5,
                verbose=self.config.verbose
            )

            # Run task
            logger.info(f"Running task {task['task_id']} with weight={llm_judge_weight}, max_turns={max_turns}")
            report = simulator.run_task(task)

            # Extract results
            aggregate = report.get("scores", {}).get("aggregate", {})
            consistency = report.get("scores", {}).get("consistency_check", {})

            state_report = report.get("state_report") if isinstance(report, dict) else None
            state_invalid_reason = None
            if self.config.enable_stateful_runtime or self.config.require_state_schema:
                evaluator_state = (state_report or {}).get("evaluator_state", {})
                tracking_log = (state_report or {}).get("tracking_log", [])
                init_log = tracking_log[0] if tracking_log else {}
                if not state_report:
                    state_invalid_reason = "missing_state_report"
                elif evaluator_state.get("status") == "no_schema_registered":
                    state_invalid_reason = "no_schema_registered"
                elif not init_log.get("has_state_schema", False):
                    state_invalid_reason = "has_state_schema_false"
                elif init_log.get("n_tracked_variables", 0) <= 0:
                    state_invalid_reason = "zero_tracked_variables"

            result = TaskResult(
                task_id=task["task_id"],
                llm_judge_weight=llm_judge_weight,
                max_turns=max_turns,
                actual_turns=report.get("execution", {}).get("total_turns", 0),
                overall_score=aggregate.get("overall", 0.0),
                robustness_score=aggregate.get("robustness", 0.0),
                consistency_score=aggregate.get("consistency", 0.0),
                memory_retention=aggregate.get("memory_retention", 0.0),
                faithfulness_score=aggregate.get("faithfulness", 0.0),
                final_difficulty=report.get("execution", {}).get("final_difficulty", 1),
                phases_completed=report.get("execution", {}).get("phases_completed", []),
                consistency_check_passed=consistency.get("passed", False),
                state_eval_valid=state_invalid_reason is None,
                state_eval_invalid_reason=state_invalid_reason,
            )

            return result

        except Exception as e:
            logger.error(f"Experiment failed: {e}")
            import traceback
            traceback.print_exc()
            return None

    def run_all_experiments(self):
        """Run all experiment configurations"""
        total_configs = len(self.config.llm_judge_weights) * len(self.config.turn_counts)
        config_idx = 0

        for llm_weight in self.config.llm_judge_weights:
            for max_turns in self.config.turn_counts:
                config_idx += 1
                logger.info(f"\n{'='*60}")
                logger.info(f"Config {config_idx}/{total_configs}: weight={llm_weight}, turns={max_turns}")
                logger.info(f"{'='*60}")

                # Run multiple tasks per configuration
                for task_idx in range(min(self.config.num_tasks_per_config, len(self.tasks))):
                    task = self.tasks[task_idx]
                    result = self.run_single_experiment(task, llm_weight, max_turns)

                    if result:
                        self.results.append(result)
                        logger.info(f"  Task {task_idx+1}: score={result.overall_score:.3f}, "
                                  f"turns={result.actual_turns}/{max_turns}")

                    # Small delay between tasks
                    time.sleep(1)

        logger.info(f"\nCompleted {len(self.results)} experiment runs")

    def aggregate_results(self) -> Dict[str, Any]:
        """Aggregate results by configuration"""
        aggregated = {}

        for result in self.results:
            key = (result.llm_judge_weight, result.max_turns)
            if key not in aggregated:
                aggregated[key] = {
                    "overall_scores": [],
                    "robustness_scores": [],
                    "consistency_scores": [],
                    "memory_retention_scores": [],
                    "faithfulness_scores": [],
                    "actual_turns": [],
                    "difficulties": [],
                    "consistency_check_passed": []
                }

            aggregated[key]["overall_scores"].append(result.overall_score)
            aggregated[key]["robustness_scores"].append(result.robustness_score)
            aggregated[key]["consistency_scores"].append(result.consistency_score)
            aggregated[key]["memory_retention_scores"].append(result.memory_retention)
            aggregated[key]["faithfulness_scores"].append(result.faithfulness_score)
            aggregated[key]["actual_turns"].append(result.actual_turns)
            aggregated[key]["difficulties"].append(result.final_difficulty)
            aggregated[key]["consistency_check_passed"].append(result.consistency_check_passed)

        # Calculate means
        summary = {}
        for key, values in aggregated.items():
            weight, turns = key
            n = len(values["overall_scores"])
            summary[f"w{weight}_t{turns}"] = {
                "llm_judge_weight": weight,
                "max_turns": turns,
                "n_runs": n,
                "overall_score_mean": sum(values["overall_scores"]) / n if n > 0 else 0,
                "robustness_score_mean": sum(values["robustness_scores"]) / n if n > 0 else 0,
                "consistency_score_mean": sum(values["consistency_scores"]) / n if n > 0 else 0,
                "memory_retention_mean": sum(values["memory_retention_scores"]) / n if n > 0 else 0,
                "faithfulness_mean": sum(values["faithfulness_scores"]) / n if n > 0 else 0,
                "actual_turns_mean": sum(values["actual_turns"]) / n if n > 0 else 0,
                "difficulty_mean": sum(values["difficulties"]) / n if n > 0 else 0,
                "consistency_check_rate": sum(values["consistency_check_passed"]) / n if n > 0 else 0
            }

        return summary

    def plot_results(self, summary: Dict[str, Any]):
        """Generate plots from results"""
        if not HAS_MATPLOTLIB:
            logger.warning("matplotlib not available, skipping plots")
            return

        # Prepare data for plotting
        weights = sorted(set(s["llm_judge_weight"] for s in summary.values()))
        turns = sorted(set(s["max_turns"] for s in summary.values()))

        # Create figure with multiple subplots
        metrics = [
            ("overall_score_mean", "Overall Score", "Higher is better"),
            ("robustness_score_mean", "Robustness Score", "Resistance to misleading"),
            ("consistency_score_mean", "Consistency Score", "Consistency across turns"),
            ("memory_retention_mean", "Memory Retention", "Retention of key facts"),
            ("faithfulness_mean", "Faithfulness Score", "Sticking to visual evidence")
        ]

        for metric_key, metric_name, metric_desc in metrics:
            self._plot_single_metric(summary, weights, turns, metric_key, metric_name, metric_desc)

        # Plot actual turns achieved
        self._plot_actual_turns(summary, weights, turns)

        logger.info(f"Plots saved to {self.output_dir}")

    def _plot_single_metric(
        self,
        summary: Dict[str, Any],
        weights: List[float],
        turns: List[int],
        metric_key: str,
        metric_name: str,
        metric_desc: str
    ):
        """Plot a single metric"""
        fig, ax = plt.subplots(figsize=(10, 6))

        colors = plt.cm.viridis(np.linspace(0, 1, len(weights)))

        for i, weight in enumerate(weights):
            x_vals = []
            y_vals = []

            for turn in turns:
                key = f"w{weight}_t{turn}"
                if key in summary:
                    x_vals.append(turn)
                    y_vals.append(summary[key].get(metric_key, 0))

            if x_vals and y_vals:
                ax.plot(x_vals, y_vals, 'o-', color=colors[i],
                       label=f'LLM Judge Weight = {weight}', linewidth=2, markersize=8)

        ax.set_xlabel('Maximum Turn Count', fontsize=12)
        ax.set_ylabel(metric_name, fontsize=12)
        ax.set_title(f'{metric_name} vs Turn Count\n({metric_desc})', fontsize=14)
        ax.legend(loc='best')
        ax.grid(True, alpha=0.3)
        ax.set_xticks(turns)

        plt.tight_layout()
        output_file = self.output_dir / f'{metric_key}.png'
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        plt.close()

        logger.info(f"Saved {output_file}")

    def _plot_actual_turns(
        self,
        summary: Dict[str, Any],
        weights: List[float],
        turns: List[int]
    ):
        """Plot actual turns achieved vs configured max turns"""
        fig, ax = plt.subplots(figsize=(10, 6))

        colors = plt.cm.viridis(np.linspace(0, 1, len(weights)))

        for i, weight in enumerate(weights):
            x_vals = []
            y_vals = []

            for turn in turns:
                key = f"w{weight}_t{turn}"
                if key in summary:
                    x_vals.append(turn)
                    y_vals.append(summary[key].get("actual_turns_mean", 0))

            if x_vals and y_vals:
                ax.plot(x_vals, y_vals, 'o-', color=colors[i],
                       label=f'LLM Judge Weight = {weight}', linewidth=2, markersize=8)

        # Add diagonal reference line (ideal: actual = max)
        ax.plot(turns, turns, 'k--', alpha=0.5, label='Ideal (Actual = Max)')

        ax.set_xlabel('Maximum Turn Count', fontsize=12)
        ax.set_ylabel('Actual Turns Achieved', fontsize=12)
        ax.set_title('Actual Turns vs Maximum Turns\n(Measuring conversation completion)', fontsize=14)
        ax.legend(loc='best')
        ax.grid(True, alpha=0.3)
        ax.set_xticks(turns)

        plt.tight_layout()
        output_file = self.output_dir / 'actual_turns.png'
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        plt.close()

        logger.info(f"Saved {output_file}")

    def save_results(self, summary: Dict[str, Any]):
        """Save experiment results to JSON"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save raw results
        raw_results_file = self.output_dir / f"experiment_raw_{timestamp}.json"
        with open(raw_results_file, 'w', encoding='utf-8') as f:
            raw_data = [
                {
                    "task_id": r.task_id,
                    "llm_judge_weight": r.llm_judge_weight,
                    "max_turns": r.max_turns,
                    "actual_turns": r.actual_turns,
                    "overall_score": r.overall_score,
                    "robustness_score": r.robustness_score,
                    "consistency_score": r.consistency_score,
                    "memory_retention": r.memory_retention,
                    "faithfulness_score": r.faithfulness_score,
                    "final_difficulty": r.final_difficulty,
                    "phases_completed": r.phases_completed,
                    "consistency_check_passed": r.consistency_check_passed,
                    "state_eval_valid": r.state_eval_valid,
                    "state_eval_invalid_reason": r.state_eval_invalid_reason,
                }
                for r in self.results
            ]
            json.dump(raw_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved raw results to {raw_results_file}")

        # Save summary
        summary_file = self.output_dir / f"experiment_summary_{timestamp}.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved summary to {summary_file}")

    def run(self):
        """Run complete experiment pipeline"""
        logger.info("Starting experiment pipeline...")
        logger.info(f"Config: weights={self.config.llm_judge_weights}, turns={self.config.turn_counts}")
        logger.info(f"Tasks: {len(self.tasks)}, runs per config: {self.config.num_tasks_per_config}")

        # Run experiments
        self.run_all_experiments()

        if not self.results:
            logger.error("No results collected!")
            return

        # Aggregate and analyze
        summary = self.aggregate_results()

        # Generate plots
        self.plot_results(summary)

        # Save results
        self.save_results(summary)

        logger.info("\nExperiment complete!")
        logger.info(f"Results saved to: {self.output_dir}")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Run LLM Judge Weight vs Turn Count experiments")
    parser.add_argument("--weights", nargs="+", type=float, default=[0.4, 0.6, 0.8, 1.0],
                       help="LLM judge weights to test")
    parser.add_argument("--turns", nargs="+", type=int, default=[10, 20, 30, 40, 50],
                       help="Turn counts to test")
    parser.add_argument("--tasks-per-config", type=int, default=2,
                       help="Number of tasks per configuration")
    parser.add_argument("--output-dir", type=str, default="experiment_images",
                       help="Output directory for results")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--enable-stateful-runtime", action="store_true",
                       help="Use state-aware runtime for experiments")
    parser.add_argument("--require-state-schema", action="store_true",
                       help="Require valid state_schema for formal experiment tasks")

    args = parser.parse_args()

    config = ExperimentConfig(
        llm_judge_weights=args.weights,
        turn_counts=args.turns,
        num_tasks_per_config=args.tasks_per_config,
        output_dir=args.output_dir,
        verbose=args.verbose,
        enable_stateful_runtime=args.enable_stateful_runtime or args.require_state_schema,
        require_state_schema=args.require_state_schema,
    )

    runner = ExperimentRunner(config)
    runner.run()


if __name__ == "__main__":
    main()
