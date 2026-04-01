#!/usr/bin/env python3
"""
Verification Script for Task 1A: Core Model Response Parsing Fix
=================================================================

This script verifies that the parsing fixes for o1-preview and similar models
are working correctly by checking for the absence of parsing errors.

Usage:
    python task/verify_task_1a.py <run_log_file.json>
    python task/verify_task_1a.py test_output/task_1a/run_log_*.json

Success Criteria:
    - "Please continue" count = 0 (in message_to_model field)
    - "Failed to parse" count = 0 (in reasoning field)
    - parse_error flag = False for all core model decisions
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any


class Task1AVerifier:
    """Verifier for Task 1A parsing fixes"""

    def __init__(self):
        self.issues = []
        self.stats = {
            "total_core_decisions": 0,
            "please_continue_count": 0,
            "failed_to_parse_count": 0,
            "parse_error_flag_count": 0,
            "empty_response_count": 0,
        }

    def verify_log_file(self, log_file_path: str) -> bool:
        """
        Verify a single run log file.

        Args:
            log_file_path: Path to the run log JSON file

        Returns:
            True if all checks pass, False otherwise
        """
        print(f"\n{'='*70}")
        print(f"Verifying: {log_file_path}")
        print(f"{'='*70}")

        try:
            with open(log_file_path, 'r', encoding='utf-8') as f:
                log_data = json.load(f)
        except Exception as e:
            print(f"❌ Error reading log file: {e}")
            return False

        # Iterate through all events in the log
        for event in log_data:
            if event.get("event") == "core_model_decision":
                self._check_core_model_event(event)

        # Print statistics
        self._print_stats()

        # Check success criteria
        success = self._check_success_criteria()

        return success

    def _check_core_model_event(self, event: Dict[str, Any]) -> None:
        """Check a single core_model_decision event for parsing issues"""
        self.stats["total_core_decisions"] += 1

        turn = event.get("turn", "?")
        action = event.get("action", "")
        message = event.get("message_to_model", "") or event.get("message", "")
        reasoning = event.get("reasoning", "")
        parse_error = event.get("parse_error", False)

        # Check 1: "Please continue" in message
        if "Please continue" in message or "please continue" in message.lower():
            self.stats["please_continue_count"] += 1
            self.issues.append({
                "turn": turn,
                "type": "please_continue",
                "message": f"Found 'Please continue' in message: {message[:100]}"
            })

        # Check 2: "Failed to parse" in reasoning
        if "Failed to parse" in reasoning or "failed to parse" in reasoning.lower():
            self.stats["failed_to_parse_count"] += 1
            self.issues.append({
                "turn": turn,
                "type": "failed_to_parse",
                "message": f"Found 'Failed to parse' in reasoning: {reasoning[:100]}"
            })

        # Check 3: parse_error flag set to True
        if parse_error:
            self.stats["parse_error_flag_count"] += 1
            error_reason = event.get("error_reason", "unknown")
            self.issues.append({
                "turn": turn,
                "type": "parse_error_flag",
                "message": f"parse_error flag is True (reason: {error_reason})"
            })

        # Check 4: Empty response issues
        if not message or message.strip() == "":
            self.stats["empty_response_count"] += 1
            self.issues.append({
                "turn": turn,
                "type": "empty_message",
                "message": "Message is empty"
            })

    def _print_stats(self) -> None:
        """Print verification statistics"""
        print(f"\n{'Statistics':-^70}")
        print(f"Total core model decisions: {self.stats['total_core_decisions']}")
        print(f"'Please continue' occurrences: {self.stats['please_continue_count']}")
        print(f"'Failed to parse' occurrences: {self.stats['failed_to_parse_count']}")
        print(f"parse_error flag set: {self.stats['parse_error_flag_count']}")
        print(f"Empty messages: {self.stats['empty_response_count']}")

    def _check_success_criteria(self) -> bool:
        """Check if all success criteria are met"""
        print(f"\n{'Success Criteria':-^70}")

        criteria_met = True

        # Criterion 1: No "Please continue"
        if self.stats["please_continue_count"] == 0:
            print("✅ 'Please continue' count = 0")
        else:
            print(f"❌ 'Please continue' count = {self.stats['please_continue_count']} (expected 0)")
            criteria_met = False

        # Criterion 2: No "Failed to parse"
        if self.stats["failed_to_parse_count"] == 0:
            print("✅ 'Failed to parse' count = 0")
        else:
            print(f"❌ 'Failed to parse' count = {self.stats['failed_to_parse_count']} (expected 0)")
            criteria_met = False

        # Criterion 3: No parse_error flags (warning only, not failure)
        if self.stats["parse_error_flag_count"] == 0:
            print("✅ parse_error flags = 0")
        else:
            print(f"⚠️  parse_error flags = {self.stats['parse_error_flag_count']} (investigate if high)")

        # Print issues if any
        if self.issues:
            print(f"\n{'Issues Found':-^70}")
            for idx, issue in enumerate(self.issues, 1):
                print(f"\n{idx}. Turn {issue['turn']} [{issue['type']}]:")
                print(f"   {issue['message']}")

        # Final result
        print(f"\n{'='*70}")
        if criteria_met:
            print("✅ VERIFICATION PASSED - All criteria met!")
        else:
            print("❌ VERIFICATION FAILED - Some criteria not met")
        print(f"{'='*70}\n")

        return criteria_met


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python task/verify_task_1a.py <run_log_file.json>")
        print("Example: python task/verify_task_1a.py test_output/task_1a/run_log_*.json")
        sys.exit(1)

    log_file = sys.argv[1]

    if not Path(log_file).exists():
        print(f"❌ Error: File not found: {log_file}")
        sys.exit(1)

    verifier = Task1AVerifier()
    success = verifier.verify_log_file(log_file)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
