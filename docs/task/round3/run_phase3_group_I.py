#!/usr/bin/env python3
"""
Phase 3 Group I Runner: Tasks 3.3 & 3.4
========================================

Runs validation tests for:
- Task 3.3: Turn-Level Ground Truth Coverage Test
- Task 3.4: Simulator Truth Validation Test

These tasks can be run in parallel with Groups H and J.

Usage:
    python docs/task/round3/run_phase3_group_I.py [options]

Options:
    --log-dir       Log directory (default: simulator_test_log)
    --output-dir    Output directory (default: docs/task/round3/report/stage3)
    --verbose       Enable verbose output
    --parallel      Run tests in parallel (default: sequential)

Created: 2026-02-04
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
from dataclasses import dataclass, field, asdict
import concurrent.futures
import traceback

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "tests"))

# Import test modules
from tests.phase3.test_3_3_turn_level_ground_truth import (
    run_comprehensive_test as run_test_3_3,
    TurnLevelGTResult
)
from tests.phase3.test_3_4_simulator_truth_validation import (
    run_comprehensive_test as run_test_3_4,
    SimulatorTruthResult
)


@dataclass
class GroupIResult:
    """Combined result for Group I tests"""
    group_id: str = "I"
    group_name: str = "Turn-Level & Truth Validation Tests"
    status: str = "PENDING"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    task_3_3: Dict[str, Any] = field(default_factory=dict)
    task_3_4: Dict[str, Any] = field(default_factory=dict)
    overall_pass: bool = False
    execution_time_seconds: float = 0.0
    failure_summary: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def run_task_3_3(log_dir: str, output_dir: str, verbose: bool = False) -> TurnLevelGTResult:
    """Run Task 3.3: Turn-Level Ground Truth Coverage Test"""
    if verbose:
        print("\n" + "=" * 60)
        print("Running Task 3.3: Turn-Level Ground Truth Coverage Test")
        print("=" * 60)

    try:
        result = run_test_3_3(log_dir, output_dir)
        if verbose:
            print(f"Task 3.3 Status: {result.status}")
            for name, metric in result.metrics.items():
                print(f"  - {name}: {metric['value']:.2%} ({'PASS' if metric['pass'] else 'FAIL'})")
        return result
    except Exception as e:
        if verbose:
            print(f"Task 3.3 Error: {e}")
            traceback.print_exc()
        result = TurnLevelGTResult()
        result.status = "ERROR"
        result.failure_reasons = [str(e)]
        return result


def run_task_3_4(log_dir: str, output_dir: str, verbose: bool = False) -> SimulatorTruthResult:
    """Run Task 3.4: Simulator Truth Validation Test"""
    if verbose:
        print("\n" + "=" * 60)
        print("Running Task 3.4: Simulator Truth Validation Test")
        print("=" * 60)

    try:
        result = run_test_3_4(log_dir, output_dir)
        if verbose:
            print(f"Task 3.4 Status: {result.status}")
            for name, metric in result.metrics.items():
                print(f"  - {name}: {metric['value']:.2%} ({'PASS' if metric['pass'] else 'FAIL'})")
        return result
    except Exception as e:
        if verbose:
            print(f"Task 3.4 Error: {e}")
            traceback.print_exc()
        result = SimulatorTruthResult()
        result.status = "ERROR"
        result.failure_reasons = [str(e)]
        return result


def run_group_i_sequential(log_dir: str, output_dir: str, verbose: bool = False) -> GroupIResult:
    """Run Group I tests sequentially"""
    start_time = datetime.now()
    group_result = GroupIResult()

    # Run Task 3.3
    result_3_3 = run_task_3_3(log_dir, output_dir, verbose)
    group_result.task_3_3 = result_3_3.to_dict()

    # Run Task 3.4
    result_3_4 = run_task_3_4(log_dir, output_dir, verbose)
    group_result.task_3_4 = result_3_4.to_dict()

    # Calculate overall status
    group_result.overall_pass = (
        result_3_3.status == "PASS" and
        result_3_4.status == "PASS"
    )
    group_result.status = "PASS" if group_result.overall_pass else "FAIL"

    # Collect failure summaries
    if result_3_3.status != "PASS":
        group_result.failure_summary.append(f"Task 3.3: {result_3_3.failure_reasons}")
    if result_3_4.status != "PASS":
        group_result.failure_summary.append(f"Task 3.4: {result_3_4.failure_reasons}")

    end_time = datetime.now()
    group_result.execution_time_seconds = (end_time - start_time).total_seconds()

    return group_result


def run_group_i_parallel(log_dir: str, output_dir: str, verbose: bool = False) -> GroupIResult:
    """Run Group I tests in parallel"""
    start_time = datetime.now()
    group_result = GroupIResult()

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_3_3 = executor.submit(run_task_3_3, log_dir, output_dir, verbose)
        future_3_4 = executor.submit(run_task_3_4, log_dir, output_dir, verbose)

        result_3_3 = future_3_3.result()
        result_3_4 = future_3_4.result()

    group_result.task_3_3 = result_3_3.to_dict()
    group_result.task_3_4 = result_3_4.to_dict()

    # Calculate overall status
    group_result.overall_pass = (
        result_3_3.status == "PASS" and
        result_3_4.status == "PASS"
    )
    group_result.status = "PASS" if group_result.overall_pass else "FAIL"

    # Collect failure summaries
    if result_3_3.status != "PASS":
        group_result.failure_summary.append(f"Task 3.3: {result_3_3.failure_reasons}")
    if result_3_4.status != "PASS":
        group_result.failure_summary.append(f"Task 3.4: {result_3_4.failure_reasons}")

    end_time = datetime.now()
    group_result.execution_time_seconds = (end_time - start_time).total_seconds()

    return group_result


def generate_summary_report(result: GroupIResult, output_dir: str):
    """Generate summary report for Group I"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # JSON report
    json_path = output_path / "phase3_group_I_summary.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)

    # Text report
    txt_path = output_path / "phase3_group_I_summary.txt"
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write("=" * 70 + "\n")
        f.write("Phase 3 Group I: Turn-Level & Truth Validation Tests - Summary\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"Overall Status: {result.status}\n")
        f.write(f"Timestamp: {result.timestamp}\n")
        f.write(f"Execution Time: {result.execution_time_seconds:.2f} seconds\n\n")

        f.write("-" * 70 + "\n")
        f.write("Task 3.3: Turn-Level Ground Truth Coverage Test\n")
        f.write("-" * 70 + "\n")
        task_3_3 = result.task_3_3
        f.write(f"Status: {task_3_3.get('status', 'N/A')}\n")
        if task_3_3.get('metrics'):
            f.write("Metrics:\n")
            for name, metric in task_3_3['metrics'].items():
                status = "PASS" if metric.get('pass') else "FAIL"
                f.write(f"  - {name}: {metric.get('value', 0):.2%} ({status})\n")

        f.write("\n" + "-" * 70 + "\n")
        f.write("Task 3.4: Simulator Truth Validation Test\n")
        f.write("-" * 70 + "\n")
        task_3_4 = result.task_3_4
        f.write(f"Status: {task_3_4.get('status', 'N/A')}\n")
        if task_3_4.get('metrics'):
            f.write("Metrics:\n")
            for name, metric in task_3_4['metrics'].items():
                status = "PASS" if metric.get('pass') else "FAIL"
                f.write(f"  - {name}: {metric.get('value', 0):.2%} ({status})\n")

        if result.failure_summary:
            f.write("\n" + "=" * 70 + "\n")
            f.write("Failure Summary\n")
            f.write("=" * 70 + "\n")
            for failure in result.failure_summary:
                f.write(f"  - {failure}\n")

        f.write("\n" + "=" * 70 + "\n")
        f.write(f"Overall Pass: {result.overall_pass}\n")
        f.write("=" * 70 + "\n")

    print(f"\nReports generated:")
    print(f"  - JSON: {json_path}")
    print(f"  - Text: {txt_path}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Run Phase 3 Group I Tests (Tasks 3.3 & 3.4)"
    )
    parser.add_argument(
        "--log-dir",
        default="simulator_test_log",
        help="Log directory (default: simulator_test_log)"
    )
    parser.add_argument(
        "--output-dir",
        default="docs/task/round3/report/stage3",
        help="Output directory (default: docs/task/round3/report/stage3)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Run tests in parallel"
    )

    args = parser.parse_args()

    print("=" * 70)
    print("Phase 3 Group I: Turn-Level & Truth Validation Tests")
    print("=" * 70)
    print(f"Log Directory: {args.log_dir}")
    print(f"Output Directory: {args.output_dir}")
    print(f"Mode: {'Parallel' if args.parallel else 'Sequential'}")
    print("=" * 70)

    # Run tests
    if args.parallel:
        result = run_group_i_parallel(args.log_dir, args.output_dir, args.verbose)
    else:
        result = run_group_i_sequential(args.log_dir, args.output_dir, args.verbose)

    # Generate summary report
    generate_summary_report(result, args.output_dir)

    # Print summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Task 3.3 (Turn-Level GT):     {result.task_3_3.get('status', 'N/A')}")
    print(f"Task 3.4 (Simulator Truth):   {result.task_3_4.get('status', 'N/A')}")
    print(f"Execution Time:               {result.execution_time_seconds:.2f}s")
    print("-" * 70)
    print(f"OVERALL STATUS:               {result.status}")
    print("=" * 70)

    # Exit with appropriate code
    sys.exit(0 if result.overall_pass else 1)


if __name__ == "__main__":
    main()
