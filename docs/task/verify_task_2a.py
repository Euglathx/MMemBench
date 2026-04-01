"""
Verification Script for Task 2A: Evaluation System Fix

This script verifies that:
1. Non-multimodal models receive scores < 0.3
2. Multimodal models receive scores > 0.6
3. Faithfulness scores properly reflect visual grounding
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any


def load_log_file(log_file: str) -> List[Dict[str, Any]]:
    """Load events from log file"""
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            events = json.load(f)
        return events if isinstance(events, list) else []
    except Exception as e:
        print(f"Error loading log file: {e}")
        return []


def extract_evaluations(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract evaluation data from events"""
    evaluations = []

    for event in events:
        if event.get('event') == 'target_model_response':
            eval_data = event.get('evaluation', {})
            if eval_data:
                evaluations.append(eval_data)

    return evaluations


def analyze_scores(evaluations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze evaluation scores"""
    if not evaluations:
        return {
            "error": "No evaluations found",
            "count": 0
        }

    # Extract overall scores (support both 'score' and 'overall_score')
    overall_scores = [
        eval.get('score', eval.get('overall_score', 0))
        for eval in evaluations
        if 'score' in eval or 'overall_score' in eval
    ]

    # Extract dimension scores
    correctness_scores = []
    faithfulness_scores = []
    robustness_scores = []

    for eval in evaluations:
        # Support both nested 'scores' dict and flat '*_score' fields
        scores = eval.get('scores', {})
        if scores:
            correctness_scores.append(scores.get('correctness', 0))
            faithfulness_scores.append(scores.get('faithfulness', 0))
            robustness_scores.append(scores.get('robustness', 0))
        else:
            # Use flat structure
            if 'faithfulness_score' in eval:
                faithfulness_scores.append(eval.get('faithfulness_score', 0))
            if 'robustness_score' in eval:
                robustness_scores.append(eval.get('robustness_score', 0))
            # Correctness is not in flat structure, use overall score
            if 'score' in eval:
                correctness_scores.append(eval.get('score', 0))

    def safe_avg(lst):
        return sum(lst) / len(lst) if lst else 0

    return {
        "count": len(evaluations),
        "overall_avg": safe_avg(overall_scores),
        "overall_min": min(overall_scores) if overall_scores else 0,
        "overall_max": max(overall_scores) if overall_scores else 0,
        "correctness_avg": safe_avg(correctness_scores),
        "faithfulness_avg": safe_avg(faithfulness_scores),
        "robustness_avg": safe_avg(robustness_scores),
        "scores_below_03": sum(1 for s in overall_scores if s < 0.3),
        "scores_above_06": sum(1 for s in overall_scores if s > 0.6)
    }


def verify_evaluation_fix(log_file: str, is_multimodal: bool = True):
    """
    Verify the evaluation system fix

    Args:
        log_file: Path to the log file
        is_multimodal: Whether the tested model is multimodal
    """
    print(f"\n{'='*60}")
    print(f"Verifying Task 2A: Evaluation System Fix")
    print(f"{'='*60}")
    print(f"Log file: {log_file}")
    print(f"Model type: {'Multimodal' if is_multimodal else 'Non-Multimodal'}")
    print(f"{'='*60}\n")

    # Load and analyze
    events = load_log_file(log_file)
    if not events:
        print("❌ Failed to load events from log file")
        return False

    evaluations = extract_evaluations(events)
    if not evaluations:
        print("❌ No evaluations found in log file")
        return False

    analysis = analyze_scores(evaluations)
    if "error" in analysis:
        print(f"❌ {analysis['error']}")
        return False

    # Print results
    print(f"Total evaluations: {analysis['count']}")
    print(f"\n📊 Score Analysis:")
    print(f"  Overall Average:     {analysis['overall_avg']:.3f}")
    print(f"  Overall Min:         {analysis['overall_min']:.3f}")
    print(f"  Overall Max:         {analysis['overall_max']:.3f}")
    print(f"\n📈 Dimension Averages:")
    print(f"  Correctness:         {analysis['correctness_avg']:.3f}")
    print(f"  Faithfulness:        {analysis['faithfulness_avg']:.3f}")
    print(f"  Robustness:          {analysis['robustness_avg']:.3f}")
    print(f"\n📉 Score Distribution:")
    print(f"  Scores < 0.3:        {analysis['scores_below_03']} ({analysis['scores_below_03']/analysis['count']*100:.1f}%)")
    print(f"  Scores > 0.6:        {analysis['scores_above_06']} ({analysis['scores_above_06']/analysis['count']*100:.1f}%)")

    # Verify expectations
    print(f"\n✓ Verification:")

    if is_multimodal:
        print(f"  Expected: Average score > 0.6 for multimodal model")
        if analysis['overall_avg'] > 0.6:
            print(f"  ✅ PASS: Average score {analysis['overall_avg']:.3f} > 0.6")
            passed = True
        else:
            print(f"  ❌ FAIL: Average score {analysis['overall_avg']:.3f} ≤ 0.6")
            passed = False

        # Check faithfulness
        print(f"  Expected: Faithfulness > 0.6 for multimodal model")
        if analysis['faithfulness_avg'] > 0.6:
            print(f"  ✅ PASS: Faithfulness {analysis['faithfulness_avg']:.3f} > 0.6")
        else:
            print(f"  ⚠️  WARNING: Faithfulness {analysis['faithfulness_avg']:.3f} ≤ 0.6")
            passed = False
    else:
        print(f"  Expected: Average score < 0.3 for non-multimodal model")
        if analysis['overall_avg'] < 0.3:
            print(f"  ✅ PASS: Average score {analysis['overall_avg']:.3f} < 0.3")
            passed = True
        else:
            print(f"  ❌ FAIL: Average score {analysis['overall_avg']:.3f} ≥ 0.3")
            passed = False

        # Check faithfulness
        print(f"  Expected: Faithfulness < 0.2 for non-multimodal model")
        if analysis['faithfulness_avg'] < 0.2:
            print(f"  ✅ PASS: Faithfulness {analysis['faithfulness_avg']:.3f} < 0.2")
        else:
            print(f"  ⚠️  WARNING: Faithfulness {analysis['faithfulness_avg']:.3f} ≥ 0.2")

    print(f"\n{'='*60}")
    print(f"Overall Result: {'✅ PASS' if passed else '❌ FAIL'}")
    print(f"{'='*60}\n")

    return passed


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python verify_task_2a.py <log_file> [--multimodal|--non-multimodal]")
        print("")
        print("Examples:")
        print("  python verify_task_2a.py test_output/task_2a_mm/run_log_*.json --multimodal")
        print("  python verify_task_2a.py test_output/task_2a_nonmm/run_log_*.json --non-multimodal")
        sys.exit(1)

    log_file = sys.argv[1]

    # Determine if multimodal based on flag or file path
    is_multimodal = True
    if len(sys.argv) > 2:
        if sys.argv[2] == "--non-multimodal":
            is_multimodal = False
        elif sys.argv[2] == "--multimodal":
            is_multimodal = True
    else:
        # Infer from path
        if "nonmm" in log_file.lower() or "non-mm" in log_file.lower():
            is_multimodal = False

    # Verify
    success = verify_evaluation_fix(log_file, is_multimodal)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
