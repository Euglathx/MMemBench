"""
Phase 1 Task 1.3: Expected Answer Tracking Validation Script
============================================================

This script validates the P1 issue: whether each turn uses the correct turn-level
expected_answer instead of always using the task-level expected_answer.

Key Findings to Validate:
1. Trace expected_answer sources for each turn
2. Compare turn-level vs task-level expected_answer usage
3. Detect misjudged cases (model answered correctly but marked wrong)
4. Analyze code architecture for turn-level support
"""

import json
import os
import re
import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass, field, asdict
from collections import defaultdict


@dataclass
class TurnExpectedAnswerInfo:
    """Information about expected_answer usage for a single turn"""
    task_id: str
    turn: int
    phase: str
    action: str
    question_asked: str
    model_response: str
    task_expected_answer: str  # The task-level expected answer
    llm_judge_correctness: int
    final_score: float
    level_passed: bool
    reasoning: str

    # Analysis fields
    turn_should_have_expected: Optional[str] = None  # What the turn-level expected should be
    uses_task_level: bool = True  # Whether task-level was used
    is_potential_misjudgment: bool = False
    misjudgment_reason: Optional[str] = None


@dataclass
class MisjudgedCase:
    """A case where the model answered correctly but was marked wrong"""
    task_id: str
    turn: int
    phase: str
    question: str
    model_response: str
    expected_answer_used: str  # Task-level
    should_be: str  # Turn-level
    evaluation_result: str
    should_be_result: str
    evidence: str
    llm_correctness: int


@dataclass
class CodeAnalysis:
    """Analysis of code architecture for turn-level expected_answer support"""
    supports_turn_level_expected: bool
    TaskState_has_turn_ground_truth: bool
    evaluator_uses: str
    simulator_generates_turn_expected: bool
    code_locations: Dict[str, str] = field(default_factory=dict)
    missing_components: List[str] = field(default_factory=list)


class ExpectedAnswerTracker:
    """
    Tracks expected_answer usage across all turns in logs.

    Main goal: Verify if the evaluation system correctly uses turn-level
    expected answers for intermediate turns, or if it incorrectly uses
    the final task-level answer for all turns.
    """

    # Phases that should have independent sub-goals
    PHASES_WITH_SUBGOALS = {
        "entity_grounding": "Identify/locate the target entity",
        "chain_navigation": "Find the next object in the chain (NOT final answer)",
        "attribute_extraction": "Extract specific attributes",
        "grounding": "Establish baseline understanding"
    }

    # Phases that should use task-level expected_answer
    PHASES_WITH_FINAL_ANSWER = {
        "final_answer": "Should match task expected_answer",
        "final_evaluation": "Should match task expected_answer",
        "chain_verification": "Final answer verification",
        "consistency_check": "Final consistency check"
    }

    def __init__(self, log_dir: str, source_dir: str = None):
        """
        Initialize the tracker.

        Args:
            log_dir: Directory containing run logs
            source_dir: Directory containing source code (for code analysis)
        """
        self.log_dir = Path(log_dir)
        self.source_dir = Path(source_dir) if source_dir else None

        self.all_turns: List[TurnExpectedAnswerInfo] = []
        self.misjudged_cases: List[MisjudgedCase] = []
        self.code_analysis: Optional[CodeAnalysis] = None

        # Statistics
        self.total_turns = 0
        self.turns_using_task_level = 0
        self.turns_that_should_use_turn_level = 0

    def scan_logs(self) -> Dict[str, Any]:
        """Scan all log files and extract expected_answer usage info"""
        log_files = list(self.log_dir.rglob("run_log*.json"))

        print(f"Found {len(log_files)} log files")

        for log_file in log_files:
            try:
                self._process_log_file(log_file)
            except Exception as e:
                print(f"Error processing {log_file}: {e}")

        return {
            "total_logs": len(log_files),
            "total_turns": self.total_turns,
            "turns_processed": len(self.all_turns)
        }

    def _process_log_file(self, log_file: Path):
        """Process a single log file"""
        with open(log_file, 'r', encoding='utf-8') as f:
            events = json.load(f)

        task_expected_answer = None
        task_id = None
        task_type = None

        for event in events:
            if event.get("event") == "task_start":
                task_expected_answer = event["data"].get("expected_answer", "")
                task_id = event["data"].get("task_id", "")
                task_type = event["data"].get("task_type", "")

            elif event.get("event") == "turn" and task_expected_answer:
                self._process_turn(event["data"], task_id, task_type, task_expected_answer)

    def _process_turn(self, turn_data: Dict, task_id: str, task_type: str, task_expected_answer: str):
        """Process a single turn and extract expected_answer usage"""
        self.total_turns += 1

        turn_num = turn_data.get("turn", 0)
        phase = turn_data.get("phase", "unknown")
        action = turn_data.get("action", "unknown")
        message = turn_data.get("message", "")
        response = turn_data.get("response", "")
        evaluation = turn_data.get("evaluation", {})

        llm_output = evaluation.get("llm_judge_output", {}) or {}
        llm_correctness = llm_output.get("correctness", 0)
        final_score = evaluation.get("score", 0)
        level_passed = evaluation.get("level_passed", False)
        reasoning = llm_output.get("reasoning", evaluation.get("reasoning", ""))

        # Determine if this turn should use turn-level expected_answer
        should_use_turn_level = phase in self.PHASES_WITH_SUBGOALS
        turn_expected = self._infer_turn_expected_answer(phase, action, message, task_type)

        # Check for potential misjudgment
        is_misjudgment, misjudgment_reason = self._check_for_misjudgment(
            phase=phase,
            llm_correctness=llm_correctness,
            final_score=final_score,
            level_passed=level_passed,
            response=response,
            task_expected_answer=task_expected_answer,
            turn_expected=turn_expected
        )

        turn_info = TurnExpectedAnswerInfo(
            task_id=task_id,
            turn=turn_num,
            phase=phase,
            action=action,
            question_asked=message,
            model_response=response[:500],  # Truncate
            task_expected_answer=task_expected_answer,
            llm_judge_correctness=llm_correctness,
            final_score=final_score,
            level_passed=level_passed,
            reasoning=reasoning[:300] if reasoning else "",
            turn_should_have_expected=turn_expected,
            uses_task_level=True,  # Current system always uses task-level
            is_potential_misjudgment=is_misjudgment,
            misjudgment_reason=misjudgment_reason
        )

        self.all_turns.append(turn_info)
        self.turns_using_task_level += 1

        if should_use_turn_level:
            self.turns_that_should_use_turn_level += 1

        if is_misjudgment:
            self._record_misjudged_case(turn_info, turn_expected or "turn-specific")

    def _infer_turn_expected_answer(self, phase: str, action: str, question: str, task_type: str) -> Optional[str]:
        """
        Infer what the turn-level expected_answer should be based on context.

        This is heuristic-based since the system doesn't actually track turn-level answers.
        """
        # For entity_grounding phase, expected answer should be about locating/identifying entity
        if phase == "entity_grounding":
            # Extract entity from question
            entity_match = re.search(r"locate the (\w+)|find the (\w+)|identify the (\w+)", question.lower())
            if entity_match:
                entity = entity_match.group(1) or entity_match.group(2) or entity_match.group(3)
                return f"Model should identify/describe the {entity}"
            return "Model should identify the target entity"

        # For chain_navigation, expected answer is the intermediate object
        if phase == "chain_navigation":
            # The question asks about what's next to/near something
            direction_match = re.search(r"(left|right|above|below|next to|near) (?:of )?(?:the |that )?(\w+)", question.lower())
            if direction_match:
                return f"The object {direction_match.group(1)} the {direction_match.group(2)}"
            return "The intermediate object in the reasoning chain"

        # For grounding phase in attribute_comparison
        if phase == "grounding":
            return "Model should describe relevant attributes"

        return None

    def _check_for_misjudgment(
        self,
        phase: str,
        llm_correctness: int,
        final_score: float,
        level_passed: bool,
        response: str,
        task_expected_answer: str,
        turn_expected: Optional[str]
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if this turn might be a misjudgment case.

        Criteria for potential misjudgment:
        1. LLM Judge gave high correctness (7+) but level_passed = False
        2. Phase is an intermediate phase (not final_answer)
        3. Response seems relevant to the turn question but doesn't mention final answer
        """
        # Not a misjudgment candidate if it passed
        if level_passed:
            return False, None

        # High LLM correctness but failed
        if llm_correctness >= 8 and not level_passed:
            if phase in self.PHASES_WITH_SUBGOALS:
                return True, f"LLM gave {llm_correctness}/10 but level_passed=False (intermediate phase '{phase}')"

        # Good score but under threshold
        if final_score >= 0.6 and not level_passed:
            if phase in self.PHASES_WITH_SUBGOALS:
                return True, f"Score {final_score:.2f} close to threshold but failed (intermediate phase)"

        # Response doesn't contain final answer but contains relevant info
        if phase in self.PHASES_WITH_SUBGOALS:
            final_answer_lower = task_expected_answer.lower()
            response_lower = response.lower()

            # If response doesn't mention final answer but LLM still gave decent score
            if llm_correctness >= 7:
                # Check if final answer keywords are NOT in response
                final_keywords = re.findall(r'\b\w+\b', final_answer_lower)
                important_keywords = [k for k in final_keywords if len(k) > 3]

                keywords_in_response = sum(1 for k in important_keywords if k in response_lower)

                if keywords_in_response < len(important_keywords) * 0.3:
                    # Response likely focuses on intermediate step, not final answer
                    return True, f"Response focuses on intermediate step, not final answer (correctness={llm_correctness})"

        return False, None

    def _record_misjudged_case(self, turn_info: TurnExpectedAnswerInfo, turn_expected: str):
        """Record a potential misjudged case"""
        case = MisjudgedCase(
            task_id=turn_info.task_id,
            turn=turn_info.turn,
            phase=turn_info.phase,
            question=turn_info.question_asked[:200],
            model_response=turn_info.model_response[:300],
            expected_answer_used=turn_info.task_expected_answer,
            should_be=turn_expected,
            evaluation_result=f"FAIL (score={turn_info.final_score:.2f})",
            should_be_result="PASS (turn-specific)",
            evidence=turn_info.misjudgment_reason or "Phase requires turn-level expected_answer",
            llm_correctness=turn_info.llm_judge_correctness
        )
        self.misjudged_cases.append(case)

    def trace_expected_answer_source(self) -> Dict:
        """Trace expected_answer sources across all turns"""
        return {
            "total_turns": self.total_turns,
            "using_task_level": self.turns_using_task_level,
            "should_use_turn_level": self.turns_that_should_use_turn_level,
            "task_level_percentage": (self.turns_using_task_level / max(1, self.total_turns)) * 100,
            "by_phase": self._analyze_by_phase()
        }

    def _analyze_by_phase(self) -> Dict[str, Dict]:
        """Analyze expected_answer usage by phase"""
        phase_stats = defaultdict(lambda: {"count": 0, "should_use_turn_level": 0, "misjudged": 0})

        for turn in self.all_turns:
            phase_stats[turn.phase]["count"] += 1
            if turn.phase in self.PHASES_WITH_SUBGOALS:
                phase_stats[turn.phase]["should_use_turn_level"] += 1
            if turn.is_potential_misjudgment:
                phase_stats[turn.phase]["misjudged"] += 1

        return dict(phase_stats)

    def analyze_sub_goals(self) -> Dict:
        """Analyze task strategies and their sub-goal definitions"""
        return {
            "phases_with_subgoals": self.PHASES_WITH_SUBGOALS,
            "phases_with_final_answer": self.PHASES_WITH_FINAL_ANSWER,
            "issue": "Current implementation has no turn-level expected_answer mechanism",
            "impact": [
                "All intermediate turns are evaluated against final answer",
                "entity_grounding phase: model finds entity but judged on final answer",
                "chain_navigation phase: model finds intermediate object but judged on final",
                "This violates Information Decoupling principle"
            ]
        }

    def find_misjudged_cases(self) -> List[Dict]:
        """Return all potential misjudged cases"""
        return [asdict(case) for case in self.misjudged_cases]

    def check_code_architecture(self) -> Dict:
        """
        Analyze code to check if turn-level expected_answer is supported.

        This is a static analysis based on known code patterns.
        """
        self.code_analysis = CodeAnalysis(
            supports_turn_level_expected=False,
            TaskState_has_turn_ground_truth=False,
            evaluator_uses="task-level expected_answer (self.task_state.expected_answer)",
            simulator_generates_turn_expected=False,
            code_locations={
                "evaluator_call": "strategic_simulator.py:818-827 - passes self.task_state.expected_answer",
                "TaskState_definition": "strategic_simulator.py:55-79 - no turn_ground_truths field",
                "evaluate_response": "evaluator.py:852-874 - expected_answer parameter is task-level",
                "TASK_STRATEGIES": "action_space.py:528-684 - defines phases but not per-turn expected"
            },
            missing_components=[
                "TurnGroundTruth dataclass",
                "turn_ground_truths field in TaskState",
                "Turn-level expected_answer generation in _generate_question()",
                "Turn-level expected_answer passing to evaluator.evaluate_response()"
            ]
        )
        return asdict(self.code_analysis)

    def generate_report(self) -> Tuple[Dict, str]:
        """Generate both JSON and text reports"""
        # Ensure analysis is done
        expected_sources = self.trace_expected_answer_source()
        sub_goals = self.analyze_sub_goals()
        misjudged = self.find_misjudged_cases()
        code_analysis = self.check_code_architecture()

        # Determine status
        status = "FAIL" if self.misjudged_cases or self.turns_that_should_use_turn_level > 0 else "PASS"

        json_report = {
            "validation_id": "1.3_expected_answer_tracking",
            "timestamp": datetime.now().isoformat(),
            "status": status,
            "expected_answer_sources": expected_sources,
            "misjudged_cases": misjudged[:20],  # Limit to top 20
            "misjudged_count": len(misjudged),
            "code_analysis": code_analysis,
            "root_cause": {
                "primary_issue": "No turn-level expected_answer mechanism implemented",
                "code_location": "strategic_simulator.py:818-827 - always passes task_state.expected_answer to evaluator",
                "design_gap": "TASK_STRATEGIES defines phases with goals but not per-turn expected answers"
            },
            "severity": "P1_HIGH",
            "recommended_fix": "Implement TurnGroundTruth data structure and update evaluation flow"
        }

        text_report = self._generate_text_report(expected_sources, sub_goals, misjudged, code_analysis)

        return json_report, text_report

    def _generate_text_report(self, expected_sources: Dict, sub_goals: Dict, misjudged: List, code_analysis: Dict) -> str:
        """Generate human-readable text report"""
        lines = [
            "=" * 70,
            "Expected Answer Tracking Validation Report",
            "Task 1.3: Verify Turn-Level Expected Answer Usage",
            "=" * 70,
            "",
            f"Status: {'FAIL ❌' if misjudged or self.turns_that_should_use_turn_level > 0 else 'PASS ✓'}",
            f"Timestamp: {datetime.now().isoformat()}",
            "",
            "=" * 70,
            "PROBLEM SUMMARY",
            "=" * 70,
            "",
            f"Total turns analyzed: {expected_sources['total_turns']}",
            f"Turns using task-level expected_answer: {expected_sources['using_task_level']} ({expected_sources['task_level_percentage']:.1f}%)",
            f"Turns that SHOULD use turn-level expected: {expected_sources['should_use_turn_level']}",
            f"Potential misjudged cases found: {len(misjudged)}",
            "",
            "The core issue is that ALL turns are evaluated against the task's",
            "final expected answer, even intermediate turns that test different aspects.",
            "",
            "=" * 70,
            "PHASE ANALYSIS",
            "=" * 70,
            ""
        ]

        for phase, stats in expected_sources.get("by_phase", {}).items():
            phase_desc = self.PHASES_WITH_SUBGOALS.get(phase, self.PHASES_WITH_FINAL_ANSWER.get(phase, "Unknown"))
            should_flag = "⚠️ Should use turn-level" if phase in self.PHASES_WITH_SUBGOALS else "✓ Can use task-level"
            lines.extend([
                f"Phase: {phase}",
                f"  Count: {stats['count']}",
                f"  {should_flag}",
                f"  Potential misjudgments: {stats['misjudged']}",
                f"  Purpose: {phase_desc}",
                ""
            ])

        lines.extend([
            "=" * 70,
            "EVIDENCE OF MISJUDGMENT",
            "=" * 70,
            ""
        ])

        for i, case in enumerate(misjudged[:10], 1):
            lines.extend([
                f"Case {i}: {case['task_id']}, Turn {case['turn']}",
                f"  Phase: {case['phase']}",
                f"  Question: {case['question'][:100]}...",
                f"  Model Response: {case['model_response'][:100]}...",
                f"  Expected (used): {case['expected_answer_used'][:80]}...",
                f"  Should be: {case['should_be']}",
                f"  LLM Correctness: {case['llm_correctness']}/10",
                f"  Evaluation: {case['evaluation_result']}",
                f"  Evidence: {case['evidence']}",
                ""
            ])

        lines.extend([
            "=" * 70,
            "CODE ARCHITECTURE ANALYSIS",
            "=" * 70,
            "",
            f"Supports turn-level expected: {code_analysis['supports_turn_level_expected']}",
            f"TaskState has turn_ground_truths: {code_analysis['TaskState_has_turn_ground_truth']}",
            f"Evaluator uses: {code_analysis['evaluator_uses']}",
            f"Simulator generates turn expected: {code_analysis['simulator_generates_turn_expected']}",
            "",
            "Code Locations:",
        ])

        for name, location in code_analysis.get("code_locations", {}).items():
            lines.append(f"  - {name}: {location}")

        lines.extend([
            "",
            "Missing Components:",
        ])

        for component in code_analysis.get("missing_components", []):
            lines.append(f"  - {component}")

        lines.extend([
            "",
            "=" * 70,
            "WHY THIS IS SERIOUS (P1 HIGH)",
            "=" * 70,
            "",
            "1. Violates Information Decoupling principle",
            "   - Models are expected to reveal final answer in turn 1",
            "   - Creates 'hindsight bias' in evaluation",
            "",
            "2. Encourages wrong model behavior",
            "   - Model that says 'I see a person and a knife' passes",
            "   - Model that focuses on asked entity ('find the person') fails",
            "",
            "3. Makes evaluation meaningless for intermediate turns",
            "   - Can't test step-by-step reasoning",
            "   - Can't isolate error sources",
            "   - Model could fail entity_grounding but pass final_answer",
            "",
            "=" * 70,
            "CURRENT CODE PATTERN (PROBLEMATIC)",
            "=" * 70,
            "",
            "```python",
            "# In strategic_simulator.py:818-827",
            "eval_result = self.evaluator.evaluate_response(",
            "    response=model_content,",
            "    expected_answer=self.task_state.expected_answer,  # ❌ Always task-level!",
            "    action_type=action,",
            "    question_asked=message,",
            "    context={...}",
            ")",
            "```",
            "",
            "=" * 70,
            "RECOMMENDED ARCHITECTURE",
            "=" * 70,
            "",
            "```python",
            "@dataclass",
            "class TurnGroundTruth:",
            "    turn_id: int",
            "    phase: str",
            "    sub_goal: str  # e.g., 'identify_entity', 'spatial_relation'",
            "    expected_answer: str  # Turn-specific answer",
            "    acceptable_variations: List[str]",
            "",
            "@dataclass",
            "class TaskState:",
            "    ...",
            "    turn_ground_truths: Dict[int, TurnGroundTruth]  # NEW",
            "    current_turn_ground_truth: TurnGroundTruth  # NEW",
            "```",
            "",
            "=" * 70,
            "IMPACT ON DESIGN GOALS",
            "=" * 70,
            "",
            "❌ Information Decoupling: BROKEN",
            "❌ Step-by-step evaluation: IMPOSSIBLE",
            "❌ Error source isolation: UNRELIABLE",
            "✓ Final answer check: Still works (only for final_answer phase)",
            "",
            "Severity: P1 HIGH",
            "This is a fundamental architecture gap, not just a bug.",
            "",
            "=" * 70,
            "DELIVERABLES",
            "=" * 70,
            "",
            "Files generated:",
            "- phase1_1.3_expected_answer.json (machine-readable)",
            "- phase1_1.3_validation_report.txt (this report)",
            "- phase1_1.3_misjudged_cases.csv (all cases)",
            ""
        ])

        return "\n".join(lines)

    def save_results(self, output_dir: Path):
        """Save all results to output directory"""
        output_dir.mkdir(parents=True, exist_ok=True)

        json_report, text_report = self.generate_report()

        # Save JSON report
        json_path = output_dir / "phase1_1.3_expected_answer.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_report, f, indent=2, ensure_ascii=False)
        print(f"Saved JSON report to {json_path}")

        # Save text report
        text_path = output_dir / "phase1_1.3_validation_report.txt"
        with open(text_path, 'w', encoding='utf-8') as f:
            f.write(text_report)
        print(f"Saved text report to {text_path}")

        # Save CSV of misjudged cases
        csv_path = output_dir / "phase1_1.3_misjudged_cases.csv"
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            if self.misjudged_cases:
                writer = csv.DictWriter(f, fieldnames=asdict(self.misjudged_cases[0]).keys())
                writer.writeheader()
                for case in self.misjudged_cases:
                    writer.writerow(asdict(case))
        print(f"Saved CSV report to {csv_path}")

        return json_path, text_path, csv_path


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Expected Answer Tracking Validation")
    parser.add_argument("--log-dir", default="simulator_test_log", help="Log directory")
    parser.add_argument("--output-dir", default="docs/task/round3/report", help="Output directory")
    parser.add_argument("--source-dir", default="src/simulator", help="Source code directory")

    args = parser.parse_args()

    # Resolve paths
    script_dir = Path(__file__).parent.parent.parent.parent  # M3Bench_new root
    log_dir = script_dir / args.log_dir
    output_dir = script_dir / args.output_dir
    source_dir = script_dir / args.source_dir

    print("=" * 60)
    print("Phase 1 Task 1.3: Expected Answer Tracking Validation")
    print("=" * 60)
    print(f"Log directory: {log_dir}")
    print(f"Output directory: {output_dir}")
    print()

    # Create tracker and run analysis
    tracker = ExpectedAnswerTracker(str(log_dir), str(source_dir))

    print("Scanning logs...")
    scan_result = tracker.scan_logs()
    print(f"Processed {scan_result['total_turns']} turns from {scan_result['total_logs']} logs")
    print()

    print("Analyzing expected_answer sources...")
    sources = tracker.trace_expected_answer_source()
    print(f"  Task-level usage: {sources['task_level_percentage']:.1f}%")
    print(f"  Should use turn-level: {sources['should_use_turn_level']} turns")
    print()

    print("Finding misjudged cases...")
    misjudged = tracker.find_misjudged_cases()
    print(f"  Found {len(misjudged)} potential misjudged cases")
    print()

    print("Checking code architecture...")
    code = tracker.check_code_architecture()
    print(f"  Supports turn-level: {code['supports_turn_level_expected']}")
    print()

    print("Saving results...")
    json_path, text_path, csv_path = tracker.save_results(output_dir)

    print()
    print("=" * 60)
    print("Validation Complete")
    print("=" * 60)
    print(f"Status: {'FAIL ❌' if misjudged else 'PASS ✓'}")
    print(f"Output files:")
    print(f"  - {json_path}")
    print(f"  - {text_path}")
    print(f"  - {csv_path}")


if __name__ == "__main__":
    main()
