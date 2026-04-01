#!/usr/bin/env python
"""
Phase 3 Group J Runner
======================

Runs Task 3.5 (Multi-Image E2E) and Task 3.6 (Evaluator State Consistency)
as part of Phase 3 validation.

These tasks can be run in parallel with Group H and Group I.

Usage:
    python run_phase3_group_J.py [--log-dir LOG_DIR] [--output-dir OUTPUT_DIR]

Author: Claude Code
Date: 2026-02-04
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

# Add project root to path - go up from docs/task/round3 to project root
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent.parent.parent  # docs/task/round3 -> docs/task -> docs -> project_root
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "tests" / "phase3"))


def run_task_3_5(log_dir: str, output_dir: str) -> Dict[str, Any]:
    """Run Task 3.5: Multi-Image E2E Test"""
    print("\n" + "=" * 60)
    print("Running Task 3.5: Multi-Image Task End-to-End Test")
    print("=" * 60 + "\n")

    try:
        from test_3_5_multi_image_e2e import run_comprehensive_test, save_results

        result = run_comprehensive_test(log_dir)
        save_results(result, output_dir)

        return {
            "task_id": "3.5",
            "task_name": "Multi-Image E2E Test",
            "status": result.status,
            "overall_pass": result.overall_pass,
            "metrics": result.metrics,
            "failure_reasons": result.failure_reasons
        }
    except Exception as e:
        import traceback
        return {
            "task_id": "3.5",
            "task_name": "Multi-Image E2E Test",
            "status": "ERROR",
            "overall_pass": False,
            "metrics": {},
            "failure_reasons": [f"Exception: {str(e)}\n{traceback.format_exc()}"]
        }


def run_task_3_6(log_dir: str, output_dir: str) -> Dict[str, Any]:
    """Run Task 3.6: Evaluator State Consistency Test"""
    print("\n" + "=" * 60)
    print("Running Task 3.6: Evaluator State Consistency Test")
    print("=" * 60 + "\n")

    try:
        from test_3_6_evaluator_state_consistency import run_comprehensive_test, save_results

        result = run_comprehensive_test(log_dir)
        save_results(result, output_dir)

        return {
            "task_id": "3.6",
            "task_name": "Evaluator State Consistency Test",
            "status": result.status,
            "overall_pass": result.overall_pass,
            "metrics": result.metrics,
            "failure_reasons": result.failure_reasons
        }
    except Exception as e:
        import traceback
        return {
            "task_id": "3.6",
            "task_name": "Evaluator State Consistency Test",
            "status": "ERROR",
            "overall_pass": False,
            "metrics": {},
            "failure_reasons": [f"Exception: {str(e)}\n{traceback.format_exc()}"]
        }


def generate_group_report(results: List[Dict[str, Any]], output_dir: str):
    """Generate a combined report for Group J"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Calculate overall group status
    all_passed = all(r["overall_pass"] for r in results)
    group_status = "PASS" if all_passed else "FAIL"

    report = {
        "group": "J",
        "group_name": "Multi-Image Strategy & Evaluator State",
        "timestamp": datetime.now().isoformat(),
        "overall_status": group_status,
        "tasks": results,
        "summary": {
            "total_tasks": len(results),
            "passed": sum(1 for r in results if r["overall_pass"]),
            "failed": sum(1 for r in results if not r["overall_pass"])
        }
    }

    # Save JSON report
    json_path = output_path / "phase3_group_J_report.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # Generate text report
    txt_path = output_path / "phase3_group_J_summary.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("Phase 3 Group J: Multi-Image Strategy & Evaluator State Validation\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"Timestamp: {report['timestamp']}\n")
        f.write(f"Overall Status: {group_status}\n")
        f.write(f"Tasks Passed: {report['summary']['passed']}/{report['summary']['total_tasks']}\n\n")

        f.write("-" * 50 + "\n")
        f.write("TASK RESULTS\n")
        f.write("-" * 50 + "\n\n")

        for task in results:
            status_icon = "✓" if task["overall_pass"] else "✗"
            f.write(f"[{status_icon}] Task {task['task_id']}: {task['task_name']}\n")
            f.write(f"    Status: {task['status']}\n")

            if task["metrics"]:
                f.write("    Metrics:\n")
                for metric_name, metric_data in task["metrics"].items():
                    metric_status = "PASS" if metric_data.get("pass", False) else "FAIL"
                    if isinstance(metric_data.get("value"), dict):
                        f.write(f"      - {metric_name}: [{metric_status}]\n")
                    else:
                        value = metric_data.get("value", "N/A")
                        if isinstance(value, float):
                            f.write(f"      - {metric_name}: {value:.2f} [{metric_status}]\n")
                        else:
                            f.write(f"      - {metric_name}: {value} [{metric_status}]\n")

            if task["failure_reasons"]:
                f.write("    Failures:\n")
                for reason in task["failure_reasons"][:3]:  # Limit to first 3
                    f.write(f"      - {reason[:100]}...\n")

            f.write("\n")

        f.write("-" * 50 + "\n")
        f.write("NEXT STEPS\n")
        f.write("-" * 50 + "\n\n")

        if all_passed:
            f.write("All Group J tasks PASSED. ✓\n\n")
            f.write("Phase 2 fixes for Task 2.5 and Task 2.6 are validated.\n")
            f.write("You can proceed with:\n")
            f.write("- Merging Phase 2 changes to main branch\n")
            f.write("- Running full benchmark evaluation\n")
        else:
            f.write("Some Group J tasks FAILED. ✗\n\n")
            f.write("Please review the failure reasons above and:\n")
            f.write("1. Check if Phase 2 fixes were properly applied\n")
            f.write("2. Review the specific test failures\n")
            f.write("3. Return to Phase 2 to fix any remaining issues\n")
            f.write("4. Re-run Group J tests after fixes\n")

        f.write("\n" + "=" * 70 + "\n")

    print(f"\nGroup J report saved to {output_path}")
    return report


def print_final_summary(report: Dict[str, Any]):
    """Print final summary to console"""
    print("\n")
    print("=" * 70)
    print("PHASE 3 GROUP J FINAL SUMMARY")
    print("=" * 70)
    print(f"\nOverall Status: {report['overall_status']}")
    print(f"Tasks Passed: {report['summary']['passed']}/{report['summary']['total_tasks']}")
    print("\nTask Results:")

    for task in report["tasks"]:
        status_icon = "✓" if task["overall_pass"] else "✗"
        print(f"  [{status_icon}] Task {task['task_id']}: {task['status']}")

    if report["overall_status"] == "PASS":
        print("\n" + "-" * 50)
        print("SUCCESS: All Group J validation tasks passed!")
        print("Phase 2 Task 2.5 and Task 2.6 fixes are validated.")
        print("-" * 50)
    else:
        print("\n" + "-" * 50)
        print("ATTENTION: Some validation tasks failed.")
        print("Please review the detailed reports in the output directory.")
        print("-" * 50)


def main():
    parser = argparse.ArgumentParser(
        description="Run Phase 3 Group J validation tasks"
    )
    parser.add_argument(
        "--log-dir",
        default="generated_tasks_v2",
        help="Directory containing run logs"
    )
    parser.add_argument(
        "--output-dir",
        default="docs/task/round3/report/stage3",
        help="Directory for output reports"
    )
    parser.add_argument(
        "--task",
        choices=["3.5", "3.6", "all"],
        default="all",
        help="Which task to run (default: all)"
    )

    args = parser.parse_args()

    # Resolve paths
    log_dir = str(project_root / args.log_dir)
    output_dir = str(project_root / args.output_dir)

    # Ensure output directory exists
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("Phase 3 Group J: Multi-Image Strategy & Evaluator State Validation")
    print("=" * 70)
    print(f"\nLog Directory: {log_dir}")
    print(f"Output Directory: {output_dir}")
    print(f"Tasks to run: {args.task}")

    results = []

    # Run selected tasks
    if args.task in ["3.5", "all"]:
        result_3_5 = run_task_3_5(log_dir, output_dir)
        results.append(result_3_5)

    if args.task in ["3.6", "all"]:
        result_3_6 = run_task_3_6(log_dir, output_dir)
        results.append(result_3_6)

    # Generate combined report
    if results:
        report = generate_group_report(results, output_dir)
        print_final_summary(report)

        # Return exit code based on status
        return 0 if report["overall_status"] == "PASS" else 1

    return 0


if __name__ == "__main__":
    exit(main())
