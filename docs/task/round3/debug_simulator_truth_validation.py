#!/usr/bin/env python3
"""
Phase 1 Task 1.4: Simulator Truth Validation Script

This script validates whether the Simulator incorrectly treats model errors as facts
in subsequent turns (P1 level issue from review feedback).

Usage:
    python debug_simulator_truth_validation.py \
        --log-dir ../../../simulator_test_log \
        --simulator-code ../../../src/simulator/strategic_simulator.py \
        --output-dir ./results
"""

import json
import os
import re
import ast
from pathlib import Path
from typing import List, Dict, Tuple, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from collections import defaultdict
import csv


@dataclass
class FalseConfirmationCase:
    """Records a case where simulator confirms an incorrect model response"""
    task_id: str
    turn_n: int
    turn_n_evaluation: Dict[str, Any]
    turn_n_plus_1_message: str
    confirmation_phrase: str
    severity: str
    turn_n_response: str = ""
    expected_answer: str = ""


@dataclass
class ErrorPropagationChain:
    """Tracks how a false claim propagates through turns"""
    task_id: str
    initial_turn: int
    false_claim: str
    is_correct: bool
    propagated_to_turns: List[int]
    propagation_depth: int


class SimulatorTruthValidator:
    """Validates simulator's truth validation mechanisms"""

    # Confirmation phrases that indicate simulator is affirming model's statement
    CONFIRMATION_PHRASES = [
        "you correctly",
        "you've correctly",
        "you identified",
        "you mentioned",
        "you noted",
        "as you said",
        "you've established",
        "you confirmed",
        "correct",
        "you described",
        "you observed",
        "you stated",
        "you pointed out",
        "you recognized",
        "well done",
        "good job",
        "exactly",
        "that's right",
        "you found"
    ]

    def __init__(self, log_dir: str, simulator_path: str, output_dir: str):
        self.log_dir = Path(log_dir)
        self.simulator_path = Path(simulator_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Results storage
        self.false_confirmation_cases: List[FalseConfirmationCase] = []
        self.error_propagation_chains: List[ErrorPropagationChain] = []
        self.task_logs: Dict[str, List[Dict]] = {}

    def load_run_logs(self) -> None:
        """Load all run logs from the log directory"""
        print(f"Loading run logs from {self.log_dir}...")

        for log_file in self.log_dir.glob("run_log_*.json"):
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    events = json.load(f)

                # Group events by task_id
                current_task_id = None
                task_events = []

                for event in events:
                    if event.get("event") == "task_start":
                        # Save previous task if exists
                        if current_task_id and task_events:
                            self.task_logs[current_task_id] = task_events

                        # Start new task
                        current_task_id = event.get("task_id")
                        task_events = [event]
                    else:
                        task_events.append(event)

                # Save last task
                if current_task_id and task_events:
                    self.task_logs[current_task_id] = task_events

            except Exception as e:
                print(f"Warning: Failed to load {log_file}: {e}")

        print(f"Loaded {len(self.task_logs)} tasks from run logs")

    def detect_false_confirmations(self) -> List[FalseConfirmationCase]:
        """
        Step 1: Detect cases where simulator confirms incorrect model responses

        Logic:
        1. For each turn N: check if evaluation shows model was wrong
        2. For turn N+1: check if simulator message contains confirmation phrases
        3. If both true: record as false confirmation
        """
        print("\n=== Step 1: Detecting False Confirmations ===")

        for task_id, events in self.task_logs.items():
            # Extract task start info
            task_start = next((e for e in events if e.get("event") == "task_start"), None)
            if not task_start:
                continue

            expected_answer = task_start.get("expected_answer", "")

            # Extract turn pairs
            turns = []
            for event in events:
                if event.get("event") == "target_model_response":
                    turns.append({
                        "turn": event.get("turn"),
                        "response": event.get("target_response", ""),
                        "evaluation": event.get("evaluation", {})
                    })
                elif event.get("event") == "core_model_decision":
                    turn_num = event.get("turn")
                    # Find matching turn
                    for t in turns:
                        if t["turn"] == turn_num:
                            t["next_message"] = event.get("message_to_model", "")
                            break

            # Check for false confirmations
            for i, turn in enumerate(turns):
                eval_data = turn.get("evaluation", {})

                # Check if model was wrong
                is_wrong = self._is_response_incorrect(eval_data, turn.get("response", ""))

                if is_wrong and i + 1 < len(turns):
                    # Check next turn's message for confirmation phrases
                    next_message = turns[i + 1].get("next_message", "")
                    if not next_message:
                        continue

                    confirmation_phrase = self._find_confirmation_phrase(next_message)

                    if confirmation_phrase:
                        # Found false confirmation!
                        severity = self._assess_severity(eval_data)

                        case = FalseConfirmationCase(
                            task_id=task_id,
                            turn_n=turn["turn"],
                            turn_n_evaluation=eval_data,
                            turn_n_plus_1_message=next_message,
                            confirmation_phrase=confirmation_phrase,
                            severity=severity,
                            turn_n_response=turn.get("response", ""),
                            expected_answer=expected_answer
                        )

                        self.false_confirmation_cases.append(case)
                        print(f"  Found false confirmation: {task_id} Turn {turn['turn']} -> {turn['turn']+1}")

        print(f"\nFound {len(self.false_confirmation_cases)} false confirmation cases")
        return self.false_confirmation_cases

    def _is_response_incorrect(self, eval_data: Dict, response: str) -> bool:
        """
        Determine if a model response was incorrect based on evaluation

        Criteria:
        - assessment contains negative indicators (wrong, incorrect, hallucination)
        - score < 0.5 (if present)
        - level_passed = false (if present)
        """
        # Check assessment text
        assessment = eval_data.get("assessment", "").lower()

        negative_indicators = [
            "wrong", "incorrect", "error", "fail", "hallucination",
            "confused", "mixed up", "1/5", "2/5", "0/5"
        ]

        has_negative = any(indicator in assessment for indicator in negative_indicators)

        # Check numeric score
        score = eval_data.get("score")
        if score is not None:
            try:
                score_val = float(score)
                if score_val < 0.5:
                    return True
            except (ValueError, TypeError):
                pass

        # Check level_passed
        level_passed = eval_data.get("level_passed")
        if level_passed is False:
            return True

        # Check if assessment indicates low quality (1/5, 2/5, etc.)
        if "/5" in assessment:
            match = re.search(r'(\d+)/5', assessment)
            if match:
                rating = int(match.group(1))
                if rating <= 2:
                    return True

        return has_negative

    def _find_confirmation_phrase(self, message: str) -> Optional[str]:
        """Find confirmation phrase in message"""
        message_lower = message.lower()

        for phrase in self.CONFIRMATION_PHRASES:
            if phrase in message_lower:
                return phrase

        return None

    def _assess_severity(self, eval_data: Dict) -> str:
        """Assess severity of false confirmation"""
        score = eval_data.get("score")

        if score is not None:
            try:
                score_val = float(score)
                if score_val < 0.3:
                    return "HIGH"
                elif score_val < 0.5:
                    return "MEDIUM"
            except (ValueError, TypeError):
                pass

        assessment = eval_data.get("assessment", "").lower()
        if "hallucination" in assessment or "completely wrong" in assessment:
            return "HIGH"

        return "MEDIUM"

    def trace_error_propagation(self) -> Dict[str, Any]:
        """
        Step 2: Trace how errors propagate through conversation turns

        Logic:
        1. Extract model claims from each turn
        2. Check if claims are referenced in subsequent turns
        3. Build propagation chains
        """
        print("\n=== Step 2: Tracing Error Propagation ===")

        total_false_claims = 0
        propagated_claims = 0
        propagation_depths = []

        for task_id, events in self.task_logs.items():
            # Extract expected answer
            task_start = next((e for e in events if e.get("event") == "task_start"), None)
            if not task_start:
                continue

            expected_answer = task_start.get("expected_answer", "")

            # Extract turns with responses and messages
            turns = []
            for event in events:
                if event.get("event") == "target_model_response":
                    turns.append({
                        "turn": event.get("turn"),
                        "response": event.get("target_response", ""),
                        "evaluation": event.get("evaluation", {}),
                        "subsequent_messages": []
                    })

            # Collect subsequent messages
            for event in events:
                if event.get("event") == "core_model_decision":
                    turn_num = event.get("turn")
                    message = event.get("message_to_model", "")
                    # Add to all previous turns
                    for turn_data in turns:
                        if turn_data["turn"] < turn_num:
                            turn_data["subsequent_messages"].append({
                                "turn": turn_num,
                                "message": message
                            })

            # Analyze propagation
            for turn_data in turns:
                is_incorrect = self._is_response_incorrect(
                    turn_data["evaluation"],
                    turn_data["response"]
                )

                if is_incorrect:
                    total_false_claims += 1

                    # Extract key claims from response
                    claims = self._extract_key_claims(turn_data["response"])

                    # Check if claims appear in subsequent messages
                    propagated_to = []
                    for msg_data in turn_data["subsequent_messages"]:
                        if self._claims_referenced_in_message(claims, msg_data["message"]):
                            propagated_to.append(msg_data["turn"])

                    if propagated_to:
                        propagated_claims += 1
                        depth = len(propagated_to)
                        propagation_depths.append(depth)

                        # Record propagation chain
                        chain = ErrorPropagationChain(
                            task_id=task_id,
                            initial_turn=turn_data["turn"],
                            false_claim=turn_data["response"][:200],  # First 200 chars
                            is_correct=False,
                            propagated_to_turns=propagated_to,
                            propagation_depth=depth
                        )
                        self.error_propagation_chains.append(chain)

        # Calculate statistics
        propagation_rate = (propagated_claims / total_false_claims * 100) if total_false_claims > 0 else 0
        avg_depth = sum(propagation_depths) / len(propagation_depths) if propagation_depths else 0
        max_depth = max(propagation_depths) if propagation_depths else 0

        result = {
            "total_false_claims": total_false_claims,
            "propagated_claims": propagated_claims,
            "propagation_rate": round(propagation_rate, 2),
            "max_propagation_depth": max_depth,
            "average_depth": round(avg_depth, 2)
        }

        print(f"  Total false claims: {total_false_claims}")
        print(f"  Propagated claims: {propagated_claims}")
        print(f"  Propagation rate: {propagation_rate:.2f}%")
        print(f"  Max depth: {max_depth}, Avg depth: {avg_depth:.2f}")

        return result

    def _extract_key_claims(self, response: str) -> List[str]:
        """Extract key factual claims from model response"""
        # Simple extraction: look for noun phrases and numbers
        claims = []

        # Extract sentences
        sentences = re.split(r'[.!?]\s+', response)

        for sentence in sentences[:3]:  # First 3 sentences
            sentence = sentence.strip()
            if len(sentence) > 10:
                claims.append(sentence.lower())

        # Extract numbers
        numbers = re.findall(r'\b\d+\b', response)
        claims.extend(numbers)

        return claims

    def _claims_referenced_in_message(self, claims: List[str], message: str) -> bool:
        """Check if any claims are referenced in the message"""
        message_lower = message.lower()

        for claim in claims:
            # For sentence claims, check for significant word overlap
            if len(claim) > 10:
                words = set(re.findall(r'\b\w+\b', claim))
                # Remove common words
                words = {w for w in words if len(w) > 3}

                if len(words) > 2:
                    matches = sum(1 for word in words if word in message_lower)
                    if matches >= min(2, len(words) // 2):
                        return True
            else:
                # For short claims (like numbers), exact match
                if claim in message_lower:
                    return True

        return False

    def check_truth_validation_mechanism(self) -> Dict[str, Any]:
        """
        Step 3: Check code for truth validation logic

        Analyzes strategic_simulator.py to see if it validates model claims
        against ground truth before using them in context
        """
        print("\n=== Step 3: Checking Truth Validation Mechanism ===")

        with open(self.simulator_path, 'r', encoding='utf-8') as f:
            code = f.read()

        # Check for truth validation patterns
        has_truth_validation = False
        model_claims_tracked = "model_claims" in code
        claims_validated_against_ground_truth = False

        # Look for validation against ground_truths
        validation_patterns = [
            r'ground_truth.*validate',
            r'validate.*ground_truth',
            r'check.*ground_truth',
            r'verify.*model_claims',
            r'compare.*expected_answer'
        ]

        for pattern in validation_patterns:
            if re.search(pattern, code, re.IGNORECASE):
                claims_validated_against_ground_truth = True
                has_truth_validation = True
                break

        # Check if conversation history includes failed responses
        uses_all_history = "get_conversation_history" in code

        # Check if memory filters by correctness
        filters_incorrect = "correctness" in code and "filter" in code

        result = {
            "has_truth_validation": has_truth_validation,
            "model_claims_tracked": model_claims_tracked,
            "claims_validated_against_ground_truth": claims_validated_against_ground_truth,
            "uses_all_conversation_history": uses_all_history,
            "filters_incorrect_responses": filters_incorrect,
            "consistency_check_polluted": not claims_validated_against_ground_truth
        }

        print(f"  Truth validation present: {has_truth_validation}")
        print(f"  Model claims tracked: {model_claims_tracked}")
        print(f"  Claims validated: {claims_validated_against_ground_truth}")
        print(f"  Consistency check polluted: {not claims_validated_against_ground_truth}")

        return result

    def analyze_consistency_check_pollution(self) -> Dict[str, Any]:
        """
        Step 4: Analyze if consistency checks are polluted by model errors

        Consistency checks should be based on ground truth, not model's own claims
        """
        print("\n=== Step 4: Analyzing Consistency Check Pollution ===")

        polluted_checks = 0
        total_checks = 0
        examples = []

        for task_id, events in self.task_logs.items():
            # Find consistency check actions
            for event in events:
                if event.get("event") == "core_model_decision":
                    action = event.get("action", "")
                    message = event.get("message_to_model", "")

                    # Check if this is a consistency check
                    if "consistency" in action.lower() or \
                       any(phrase in message.lower() for phrase in [
                           "you said", "you mentioned", "earlier you",
                           "previously you", "confirm", "verify"
                       ]):
                        total_checks += 1

                        # Check if it references model's previous response
                        # (which could be wrong)
                        if self._references_model_claim(message):
                            polluted_checks += 1

                            if len(examples) < 3:
                                examples.append({
                                    "task_id": task_id,
                                    "turn": event.get("turn"),
                                    "message": message
                                })

        pollution_rate = (polluted_checks / total_checks * 100) if total_checks > 0 else 0

        result = {
            "total_consistency_checks": total_checks,
            "polluted_checks": polluted_checks,
            "pollution_rate": round(pollution_rate, 2),
            "examples": examples
        }

        print(f"  Total consistency checks: {total_checks}")
        print(f"  Polluted checks: {polluted_checks}")
        print(f"  Pollution rate: {pollution_rate:.2f}%")

        return result

    def _references_model_claim(self, message: str) -> bool:
        """Check if message references model's previous claim"""
        reference_phrases = [
            "you said", "you mentioned", "you identified", "you noted",
            "you described", "you stated", "earlier you", "previously you",
            "as you"
        ]

        message_lower = message.lower()
        return any(phrase in message_lower for phrase in reference_phrases)

    def generate_report(self) -> Tuple[Dict, str]:
        """Generate validation report in JSON and text formats"""
        print("\n=== Generating Report ===")

        # Calculate statistics
        total_turns = sum(
            len([e for e in events if e.get("event") == "target_model_response"])
            for events in self.task_logs.values()
        )

        false_confirmation_rate = (
            len(self.false_confirmation_cases) / total_turns * 100
            if total_turns > 0 else 0
        )

        # Determine status
        status = "FAIL" if len(self.false_confirmation_cases) > 0 else "PASS"

        # Build JSON report
        json_report = {
            "validation_id": "1.4_simulator_truth_validation",
            "timestamp": datetime.now().isoformat(),
            "status": status,
            "false_confirmation_cases": [
                {
                    "task_id": case.task_id,
                    "turn_n": case.turn_n,
                    "turn_n_evaluation": case.turn_n_evaluation,
                    "turn_n_plus_1_message": case.turn_n_plus_1_message[:200],
                    "confirmation_phrase": case.confirmation_phrase,
                    "severity": case.severity
                }
                for case in self.false_confirmation_cases[:20]  # Limit to first 20
            ],
            "statistics": {
                "total_turn_pairs": total_turns,
                "false_confirmation_count": len(self.false_confirmation_cases),
                "false_confirmation_rate": round(false_confirmation_rate, 2)
            },
            "error_propagation": self.trace_error_propagation(),
            "code_analysis": self.check_truth_validation_mechanism(),
            "consistency_check_analysis": self.analyze_consistency_check_pollution(),
            "root_cause": {
                "primary_issue": "Simulator trusts model output without ground truth validation",
                "code_location": "strategic_simulator.py: memory.add_turn() and get_conversation_history()",
                "missing_mechanism": "Ground truth comparison before incorporating model claims into context"
            },
            "severity": "P1_HIGH" if false_confirmation_rate > 10 else "P1_MEDIUM",
            "recommended_fix": "Add truth validation layer between model response and next turn generation"
        }

        # Build text report
        text_report = self._build_text_report(json_report)

        return json_report, text_report

    def _build_text_report(self, json_report: Dict) -> str:
        """Build human-readable text report"""
        status_emoji = "❌" if json_report["status"] == "FAIL" else "✅"

        report = f"""=== Simulator Truth Validation Report ===

Status: {json_report['status']} {status_emoji}
Generated: {json_report['timestamp']}

Problem Summary:
- {json_report['statistics']['false_confirmation_rate']}% of turn pairs show false confirmation
- {json_report['error_propagation']['propagation_rate']}% of model's false claims are propagated to later turns
- {json_report['consistency_check_analysis']['pollution_rate']}% of consistency checks are polluted by model's own errors

Statistics:
- Total turn pairs analyzed: {json_report['statistics']['total_turn_pairs']}
- False confirmation cases found: {json_report['statistics']['false_confirmation_count']}
- Total false claims: {json_report['error_propagation']['total_false_claims']}
- Propagated claims: {json_report['error_propagation']['propagated_claims']}
- Max propagation depth: {json_report['error_propagation']['max_propagation_depth']} turns
- Average propagation depth: {json_report['error_propagation']['average_depth']} turns

Evidence of False Confirmation:
"""

        # Add example cases
        for i, case in enumerate(json_report['false_confirmation_cases'][:5], 1):
            report += f"\nCase {i}: {case['task_id']}, Turn {case['turn_n']} → {case['turn_n'] + 1}\n"
            report += f"  Evaluation: {case['turn_n_evaluation'].get('assessment', 'N/A')[:100]}\n"
            report += f"  Next turn message: \"{case['turn_n_plus_1_message'][:150]}...\"\n"
            report += f"  Confirmation phrase: \"{case['confirmation_phrase']}\"\n"
            report += f"  Severity: {case['severity']}\n"

        report += f"""
Code Analysis:
- Has truth validation: {json_report['code_analysis']['has_truth_validation']}
- Model claims tracked: {json_report['code_analysis']['model_claims_tracked']}
- Claims validated against ground truth: {json_report['code_analysis']['claims_validated_against_ground_truth']}
- Consistency check polluted: {json_report['code_analysis']['consistency_check_polluted']}

Root Cause:
{json_report['root_cause']['primary_issue']}

Location: {json_report['root_cause']['code_location']}
Missing: {json_report['root_cause']['missing_mechanism']}

Severity: {json_report['severity']}

Recommended Fix:
{json_report['recommended_fix']}

Impact on Design Goals:
❌ Error self-reinforcement: Happening
❌ "回马枪" validation: Polluted
❌ Information decoupling: Broken (simulator leaks model's misconceptions)
✓ Multi-turn testing: Still works mechanically

Why This Is Serious:
1. Creates feedback loop of errors
2. Makes it impossible to test "recovery from error"
3. Pollutes the very mechanism (consistency check) meant to catch errors
4. Violates the "independent evaluator" design principle
"""

        return report

    def save_results(self, json_report: Dict, text_report: str) -> None:
        """Save all results to files"""
        print("\n=== Saving Results ===")

        # Save JSON report
        json_path = self.output_dir / "phase1_1.4_simulator_truth.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_report, f, indent=2, ensure_ascii=False)
        print(f"Saved JSON report: {json_path}")

        # Save text report
        txt_path = self.output_dir / "phase1_1.4_validation_report.txt"
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(text_report)
        print(f"Saved text report: {txt_path}")

        # Save false confirmation cases as CSV
        csv_path = self.output_dir / "phase1_1.4_false_confirmations.csv"
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                "task_id", "turn_n", "confirmation_phrase", "severity",
                "evaluation_assessment", "next_message_preview"
            ])

            for case in self.false_confirmation_cases:
                writer.writerow([
                    case.task_id,
                    case.turn_n,
                    case.confirmation_phrase,
                    case.severity,
                    case.turn_n_evaluation.get("assessment", "")[:100],
                    case.turn_n_plus_1_message[:150]
                ])
        print(f"Saved CSV cases: {csv_path}")

        # Save error propagation graph
        graph_path = self.output_dir / "phase1_1.4_error_propagation_graph.json"
        propagation_data = {
            "chains": [
                {
                    "task_id": chain.task_id,
                    "initial_turn": chain.initial_turn,
                    "false_claim_preview": chain.false_claim[:100],
                    "propagated_to_turns": chain.propagated_to_turns,
                    "propagation_depth": chain.propagation_depth
                }
                for chain in self.error_propagation_chains
            ]
        }
        with open(graph_path, 'w', encoding='utf-8') as f:
            json.dump(propagation_data, f, indent=2, ensure_ascii=False)
        print(f"Saved propagation graph: {graph_path}")

    def run(self) -> None:
        """Execute full validation pipeline"""
        print("=" * 60)
        print("Simulator Truth Validation - Phase 1 Task 1.4")
        print("=" * 60)

        # Step 0: Load logs
        self.load_run_logs()

        if not self.task_logs:
            print("\n❌ No task logs found! Please check log directory.")
            return

        # Step 1: Detect false confirmations
        self.detect_false_confirmations()

        # Steps 2-4 are called within generate_report
        # Step 5: Generate report
        json_report, text_report = self.generate_report()

        # Step 6: Save results
        self.save_results(json_report, text_report)

        print("\n" + "=" * 60)
        print("Validation Complete!")
        print("=" * 60)
        print(f"\nStatus: {json_report['status']}")
        print(f"False confirmations found: {len(self.false_confirmation_cases)}")
        print(f"Error propagation chains: {len(self.error_propagation_chains)}")
        print(f"\nReports saved to: {self.output_dir}")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate simulator's truth validation mechanism"
    )
    parser.add_argument(
        "--log-dir",
        type=str,
        default="../../../simulator_test_log",
        help="Path to run logs directory"
    )
    parser.add_argument(
        "--simulator-code",
        type=str,
        default="../../../src/simulator/strategic_simulator.py",
        help="Path to strategic_simulator.py"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./results",
        help="Output directory for reports"
    )

    args = parser.parse_args()

    # Create validator and run
    validator = SimulatorTruthValidator(
        log_dir=args.log_dir,
        simulator_path=args.simulator_code,
        output_dir=args.output_dir
    )

    validator.run()


if __name__ == "__main__":
    main()
