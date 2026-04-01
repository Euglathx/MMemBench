"""
Task 2B Verification Script: Action Diversity
==============================================

Verifies that the action space expansion is working correctly:
- At least 8 unique actions used
- No single action exceeds 40% of total
- High-level actions (memory_injection, cross_image_confusion, consistency_check) are being used

Usage:
    python task/verify_task_2b.py <log_file>

Example:
    python task/verify_task_2b.py test_output/task_2b/run_log_20250201.json
"""

import json
import sys
from collections import Counter
from pathlib import Path


def verify_action_diversity(log_file: str) -> bool:
    """
    Verify that action diversity goals are met.

    Criteria:
    - At least 8 unique actions
    - No single action > 40% of total
    - At least 1 occurrence of high-level actions
    """
    log_path = Path(log_file)

    if not log_path.exists():
        print(f"Error: Log file not found: {log_file}")
        return False

    with open(log_path, encoding='utf-8') as f:
        events = json.load(f)

    # Extract actions from core_model_decision events
    actions = [
        e.get('action')
        for e in events
        if e.get('event') == 'core_model_decision' and e.get('action')
    ]

    if not actions:
        print("No actions found in log file")
        print("Looking for actions in other event types...")

        # Try to find actions in other event types
        for e in events:
            if 'action' in e:
                actions.append(e.get('action'))

    if not actions:
        print("ERROR: No actions found in the log file")
        return False

    action_counts = Counter(actions)
    unique_count = len(action_counts)
    total_count = len(actions)

    print("=" * 50)
    print("=== Task 2B: Action Diversity Verification ===")
    print("=" * 50)
    print(f"\nTotal actions: {total_count}")
    print(f"Unique actions: {unique_count}")
    print(f"Target: >= 8 unique actions")

    print("\n--- Action Distribution ---")
    for action, count in action_counts.most_common():
        pct = count / total_count * 100
        bar = "█" * int(pct / 2)
        print(f"  {action:25s}: {count:3d} ({pct:5.1f}%) {bar}")

    # Check high-level actions
    high_level_actions = ['memory_injection', 'cross_image_confusion', 'consistency_check']
    used_high_level = [a for a in high_level_actions if a in action_counts]

    print(f"\n--- High-Level Actions ---")
    print(f"Target: At least 1 of {high_level_actions}")
    print(f"Found: {used_high_level if used_high_level else 'None'}")

    # Verification criteria
    passed = True
    print("\n--- Verification Results ---")

    # Criterion 1: At least 8 unique actions
    if unique_count >= 8:
        print(f"✅ PASS: {unique_count} unique actions (>= 8)")
    else:
        print(f"❌ FAIL: Only {unique_count} unique actions (need >= 8)")
        passed = False

    # Criterion 2: No single action > 40%
    max_action_pct = max(c / total_count for c in action_counts.values()) * 100
    max_action_name = action_counts.most_common(1)[0][0]
    if max_action_pct <= 40:
        print(f"✅ PASS: Max action '{max_action_name}' at {max_action_pct:.1f}% (<= 40%)")
    else:
        print(f"❌ FAIL: Action '{max_action_name}' at {max_action_pct:.1f}% (> 40%)")
        passed = False

    # Criterion 3: At least 1 high-level action used
    if len(used_high_level) >= 1:
        print(f"✅ PASS: {len(used_high_level)} high-level action(s) used")
    else:
        print(f"⚠️ WARN: No high-level actions used (optional but recommended)")

    print("\n" + "=" * 50)
    if passed:
        print("✅ OVERALL: Action diversity verification PASSED")
    else:
        print("❌ OVERALL: Action diversity verification FAILED")
    print("=" * 50)

    return passed


def analyze_action_patterns(log_file: str):
    """Additional analysis of action usage patterns"""
    log_path = Path(log_file)

    if not log_path.exists():
        return

    with open(log_path, encoding='utf-8') as f:
        events = json.load(f)

    # Find actions by turn
    turn_actions = []
    for e in events:
        if e.get('event') == 'core_model_decision' and e.get('action'):
            turn = e.get('turn', len(turn_actions))
            turn_actions.append((turn, e.get('action')))

    if not turn_actions:
        return

    print("\n--- Action Pattern Analysis ---")

    # Check for consecutive repeats
    consecutive_repeats = 0
    for i in range(1, len(turn_actions)):
        if turn_actions[i][1] == turn_actions[i-1][1]:
            consecutive_repeats += 1

    print(f"Consecutive repeats: {consecutive_repeats}")

    # Check early turn diversity (first 5 turns)
    early_actions = [a for t, a in turn_actions if t < 5]
    if early_actions:
        early_unique = len(set(early_actions))
        print(f"Early turn (0-4) diversity: {early_unique} unique actions from {len(early_actions)} turns")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python verify_task_2b.py <log_file>")
        print("Example: python verify_task_2b.py test_output/task_2b/run_log_*.json")
        sys.exit(1)

    log_file = sys.argv[1]

    # Handle glob pattern
    if '*' in log_file:
        from glob import glob
        matches = glob(log_file)
        if matches:
            log_file = matches[0]
            print(f"Using: {log_file}")
        else:
            print(f"No files matching pattern: {log_file}")
            sys.exit(1)

    success = verify_action_diversity(log_file)
    analyze_action_patterns(log_file)

    sys.exit(0 if success else 1)
