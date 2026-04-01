#!/usr/bin/env python3
"""
Phase 1 Task 1.6: Evaluator State Tracking
==========================================

验证评审意见中的P2级问题:
1. Evaluator对同一图像的判断是否前后一致（问题4）
2. Faithfulness/Robustness等分数是否像常数（问题1.3）

检查以下问题:
1. 判断一致性: 同一任务内对相同事物的判断是否一致
2. 分数分布: 各维度分数的变化范围和频率
3. 默认值追踪: 哪些分数是默认值？何时被更新？
4. 状态演化: cross_image_mapping, key_facts等状态是否正确管理
"""

import json
import re
import csv
import sys
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime
from collections import defaultdict, Counter
import logging
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EvaluatorStateTracker:
    """追踪evaluator的内部状态和一致性"""

    def __init__(self, log_dir: str, evaluator_path: str):
        """
        初始化追踪器

        Args:
            log_dir: Run logs目录路径
            evaluator_path: evaluator.py的路径
        """
        self.log_dir = Path(log_dir)
        self.evaluator_path = Path(evaluator_path)

        # 默认值（从evaluator.py提取）
        self.hard_score_defaults = {
            "correctness": 0.1,
            "faithfulness": 0.2,
            "robustness": 0.3,
            "consistency": 0.3,
            "memory_retention": 0.3,
            "cross_image_confusion": 0.3,
            "disambiguation": 0.3
        }

        # 数据收集
        self.score_data = defaultdict(list)  # {dimension: [scores]}
        self.judgment_inconsistencies = []
        self.default_retention_stats = defaultdict(lambda: {"total": 0, "retained": 0})
        self.state_snapshots = []

    def find_log_files(self) -> List[Path]:
        """查找所有run log文件"""
        log_files = []

        # 查找单个run logs
        for log_file in self.log_dir.glob("run_log_*.json"):
            if "memory_state" not in log_file.name and "summary" not in log_file.name:
                log_files.append(log_file)

        # 查找batch run logs
        for batch_dir in self.log_dir.glob("batch_run_*"):
            if batch_dir.is_dir():
                for log_file in batch_dir.glob("run_log_*.json"):
                    log_files.append(log_file)

        return sorted(log_files)

    def extract_spatial_relations(self, text: str) -> List[Dict[str, str]]:
        """从文本中提取空间关系判断"""
        relations = []

        # 常见空间关系模式
        patterns = [
            # "X is on/in/at/above/below/left/right Y"
            r'(\w+(?:\s+\w+)?)\s+is\s+(on|in|at|above|below|left|right|near|beside|next to|held by|holding)\s+(\w+(?:\s+\w+)?)',
            # "X on/in/at the Y"
            r'(\w+(?:\s+\w+)?)\s+(on|in|at)\s+the\s+(\w+(?:\s+\w+)?)',
            # Position descriptions
            r'(\w+(?:\s+\w+)?)\s+(?:is|are)\s+(positioned|located)\s+(\w+)',
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, text.lower())
            for match in matches:
                relations.append({
                    "subject": match.group(1),
                    "relation": match.group(2),
                    "object": match.group(3) if len(match.groups()) >= 3 else ""
                })

        return relations

    def check_judgment_consistency(self) -> List[Dict]:
        """检查判断一致性"""
        logger.info("Checking judgment consistency...")

        log_files = self.find_log_files()
        inconsistencies = []

        for log_file in log_files[:50]:  # 检查前50个
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    events = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to read {log_file}: {e}")
                continue

            task_id = None
            turn_judgments = []  # [(turn, relations, reasoning)]

            for event in events:
                if event.get("event") == "task_start":
                    data = event.get("data", event)
                    task_id = data.get("task_id")

                if event.get("event") == "turn":
                    data = event.get("data", event)
                    turn = data.get("turn")
                    evaluation = data.get("evaluation", {})
                    reasoning = evaluation.get("reasoning", "")

                    if reasoning:
                        relations = self.extract_spatial_relations(reasoning)
                        turn_judgments.append((turn, relations, reasoning))

            # 对比不同turn的判断
            if len(turn_judgments) >= 2:
                for i in range(len(turn_judgments) - 1):
                    turn1, rels1, reasoning1 = turn_judgments[i]
                    turn2, rels2, reasoning2 = turn_judgments[i + 1]

                    # 查找相同对象的矛盾判断
                    for rel1 in rels1:
                        for rel2 in rels2:
                            # 同一对象的不同位置判断
                            if rel1["subject"] == rel2["subject"]:
                                # 检查矛盾的空间关系
                                contradictions = self._check_spatial_contradiction(
                                    rel1["relation"], rel2["relation"]
                                )

                                if contradictions:
                                    inconsistencies.append({
                                        "task_id": task_id,
                                        "object": rel1["subject"],
                                        f"turn_{turn1}_judgment": f"{rel1['subject']} {rel1['relation']} {rel1['object']}",
                                        f"turn_{turn2}_judgment": f"{rel2['subject']} {rel2['relation']} {rel2['object']}",
                                        "contradiction": contradictions,
                                        "severity": "HIGH",
                                        f"turn_{turn1}_reasoning": reasoning1[:200],
                                        f"turn_{turn2}_reasoning": reasoning2[:200]
                                    })

        return inconsistencies

    def _check_spatial_contradiction(self, rel1: str, rel2: str) -> Optional[str]:
        """检查两个空间关系是否矛盾"""
        contradictions_map = {
            "left": ["right"],
            "right": ["left"],
            "above": ["below", "on"],
            "below": ["above"],
            "on": ["held by", "holding", "above"],
            "held by": ["on"],
            "holding": ["on"],
            "in": ["on top of"],
        }

        if rel1 in contradictions_map:
            if rel2 in contradictions_map[rel1]:
                return f"Cannot be both '{rel1}' and '{rel2}'"

        return None

    def analyze_score_distributions(self) -> Dict:
        """分析分数分布"""
        logger.info("Analyzing score distributions...")

        log_files = self.find_log_files()

        # 收集所有分数
        score_dimensions = [
            "faithfulness_score", "robustness_score", "consistency_score",
            "memory_retention_score", "cross_image_confusion_score",
            "disambiguation_score", "score"
        ]

        for log_file in log_files:
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    events = json.load(f)
            except:
                continue

            for event in events:
                if event.get("event") == "turn":
                    data = event.get("data", event)
                    evaluation = data.get("evaluation", {})

                    for dim in score_dimensions:
                        if dim in evaluation:
                            score = evaluation[dim]
                            if isinstance(score, (int, float)):
                                self.score_data[dim].append(score)

        # 分析每个维度
        distribution_analysis = {}

        for dim, scores in self.score_data.items():
            if not scores:
                continue

            scores_array = np.array(scores)
            unique_values = np.unique(scores_array)
            value_counts = Counter(scores)
            most_common = value_counts.most_common(1)[0]

            # 计算统计指标
            analysis = {
                "unique_values": len(unique_values),
                "most_common": most_common[0],
                "most_common_rate": most_common[1] / len(scores),
                "std_dev": float(np.std(scores_array)),
                "mean": float(np.mean(scores_array)),
                "median": float(np.median(scores_array)),
                "min": float(np.min(scores_array)),
                "max": float(np.max(scores_array)),
                "value_distribution": dict(value_counts.most_common(10))
            }

            # 判断状态
            if analysis["most_common_rate"] > 0.9:
                analysis["status"] = f"CONSTANT ({analysis['most_common_rate']*100:.0f}% same value)"
            elif analysis["most_common_rate"] > 0.7:
                analysis["status"] = "SUSPICIOUS (low diversity)"
            elif analysis["unique_values"] < 5:
                analysis["status"] = "LOW_DIVERSITY"
            else:
                analysis["status"] = "NORMAL"

            distribution_analysis[dim] = analysis

        return distribution_analysis

    def trace_default_value_retention(self) -> Dict:
        """追踪默认值保留情况"""
        logger.info("Tracing default value retention...")

        log_files = self.find_log_files()

        # 维度映射（从LLM输出到内部字段）
        dimension_mapping = {
            "faithfulness_score": ("faithfulness", 0.2),
            "robustness_score": ("robustness", 0.3),
            "consistency_score": ("consistency", 0.3),
            "memory_retention_score": ("memory_retention", 0.3),
            "cross_image_confusion_score": ("cross_image_confusion", 0.3),
            "disambiguation_score": ("disambiguation", 0.3),
        }

        for log_file in log_files:
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    events = json.load(f)
            except:
                continue

            for event in events:
                if event.get("event") == "turn":
                    data = event.get("data", event)
                    evaluation = data.get("evaluation", {})
                    action = data.get("action", "")

                    for score_field, (dim_name, default_val) in dimension_mapping.items():
                        if score_field in evaluation:
                            score = evaluation[score_field]
                            self.default_retention_stats[dim_name]["total"] += 1

                            # 检查是否等于默认值（允许浮点误差）
                            if abs(score - default_val) < 0.01:
                                self.default_retention_stats[dim_name]["retained"] += 1

        # 计算保留率
        retention_report = {}
        for dim, stats in self.default_retention_stats.items():
            if stats["total"] > 0:
                retention_rate = stats["retained"] / stats["total"]
                retention_report[dim] = {
                    "default": dimension_mapping.get(f"{dim}_score", (dim, 0.3))[1],
                    "retained_rate": retention_rate,
                    "total_samples": stats["total"],
                    "retained_count": stats["retained"],
                    "issue": self._diagnose_retention_issue(dim, retention_rate)
                }

        return retention_report

    def _diagnose_retention_issue(self, dimension: str, retention_rate: float) -> str:
        """诊断默认值保留问题"""
        if retention_rate > 0.8:
            return f"Very high retention ({retention_rate*100:.0f}%) - likely not being updated"
        elif retention_rate > 0.5:
            return f"Moderate retention ({retention_rate*100:.0f}%) - may only update for specific actions"
        elif retention_rate > 0.2:
            return f"Some retention ({retention_rate*100:.0f}%) - partially updated"
        else:
            return f"Low retention ({retention_rate*100:.0f}%) - appears to be updated regularly"

    def snapshot_state_evolution(self, max_tasks: int = 10) -> List[Dict]:
        """生成状态快照序列"""
        logger.info("Snapshotting state evolution...")

        log_files = self.find_log_files()
        snapshots = []

        for log_file in log_files[:max_tasks]:
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    events = json.load(f)
            except:
                continue

            task_id = None
            task_snapshots = []

            for event in events:
                if event.get("event") == "task_start":
                    data = event.get("data", event)
                    task_id = data.get("task_id")

                if event.get("event") == "turn":
                    data = event.get("data", event)
                    turn = data.get("turn")
                    evaluation = data.get("evaluation", {})

                    snapshot = {
                        "task_id": task_id,
                        "turn": turn,
                        "phase": data.get("phase", "unknown"),
                        "action": data.get("action", "unknown"),
                        "evaluation_scores": {
                            "score": evaluation.get("score", 0),
                            "faithfulness": evaluation.get("faithfulness_score", 0),
                            "robustness": evaluation.get("robustness_score", 0),
                            "consistency": evaluation.get("consistency_score", 0),
                        },
                        "llm_judge_scores": evaluation.get("llm_judge_output", {}),
                        "level_passed": evaluation.get("level_passed", False)
                    }

                    task_snapshots.append(snapshot)

            if task_snapshots:
                snapshots.append({
                    "task_id": task_id,
                    "total_turns": len(task_snapshots),
                    "snapshots": task_snapshots,
                    "state_issues": self._detect_state_issues(task_snapshots)
                })

        return snapshots

    def _detect_state_issues(self, snapshots: List[Dict]) -> List[str]:
        """检测状态管理问题"""
        issues = []

        # 检查分数是否异常不变
        if len(snapshots) >= 3:
            robustness_scores = [s["evaluation_scores"]["robustness"] for s in snapshots]
            if len(set(robustness_scores)) == 1:
                issues.append(f"Robustness score constant at {robustness_scores[0]}")

            consistency_scores = [s["evaluation_scores"]["consistency"] for s in snapshots]
            if len(set(consistency_scores)) == 1:
                issues.append(f"Consistency score constant at {consistency_scores[0]}")

        # 检查LLM judge和最终分数的关系
        for snapshot in snapshots:
            llm_judge = snapshot.get("llm_judge_scores", {})
            if llm_judge is None:
                llm_judge = {}
            final_scores = snapshot["evaluation_scores"]

            if llm_judge.get("correctness", 0) >= 8 and final_scores["score"] < 0.5:
                issues.append(f"Turn {snapshot['turn']}: LLM judge high (8+) but final score low ({final_scores['score']:.2f})")

        return issues

    def generate_report(self) -> Tuple[Dict, str]:
        """生成完整报告"""
        logger.info("Generating comprehensive report...")

        # 执行所有分析
        judgment_inconsistencies = self.check_judgment_consistency()
        score_distributions = self.analyze_score_distributions()
        default_retention = self.trace_default_value_retention()
        state_snapshots = self.snapshot_state_evolution()

        # 收集状态演化问题
        state_evolution_issues = []
        for task_snapshot in state_snapshots:
            state_evolution_issues.extend(task_snapshot["state_issues"])

        # 确定状态
        status = "PASS"
        root_causes = []
        recommended_fixes = []

        # 检查问题
        if len(judgment_inconsistencies) > 0:
            status = "FAIL"
            root_causes.append(f"Found {len(judgment_inconsistencies)} judgment inconsistencies")
            recommended_fixes.append("Standardize LLM Judge evidence across turns")

        # 检查分数常数化问题
        constant_dimensions = [
            dim for dim, analysis in score_distributions.items()
            if "CONSTANT" in analysis.get("status", "")
        ]
        if constant_dimensions:
            status = "FAIL"
            root_causes.append(f"Dimensions with constant scores: {', '.join(constant_dimensions)}")
            recommended_fixes.append("Update all dimension scores dynamically, not just defaults")

        # 检查默认值保留问题
        high_retention_dims = [
            dim for dim, stats in default_retention.items()
            if stats["retained_rate"] > 0.7
        ]
        if high_retention_dims:
            status = "FAIL"
            root_causes.append(f"High default retention in: {', '.join(high_retention_dims)}")
            recommended_fixes.append("Evaluate all dimensions for all action types")

        # 构建JSON报告
        report = {
            "validation_id": "1.6_evaluator_state_tracking",
            "timestamp": datetime.now().isoformat(),
            "status": status,
            "judgment_inconsistencies": judgment_inconsistencies[:10],  # 只保存前10个
            "judgment_inconsistency_count": len(judgment_inconsistencies),
            "score_distribution_analysis": score_distributions,
            "default_value_retention": default_retention,
            "state_evolution_issues": list(set(state_evolution_issues)),  # 去重
            "state_snapshots_analyzed": len(state_snapshots),
            "root_causes": root_causes,
            "severity": "P2_MEDIUM" if status == "FAIL" else "P2_LOW",
            "recommended_fixes": recommended_fixes
        }

        # 构建文本报告
        txt_report = self._format_text_report(report)

        return report, txt_report

    def _format_text_report(self, report: Dict) -> str:
        """格式化文本报告"""
        lines = []
        lines.append("=" * 80)
        lines.append("Phase 1 Task 1.6: Evaluator State Tracking Report")
        lines.append("=" * 80)
        lines.append(f"Timestamp: {report['timestamp']}")
        lines.append(f"Status: {report['status']}")
        lines.append(f"Severity: {report['severity']}")
        lines.append("")

        # Judgment inconsistencies
        lines.append("-" * 80)
        lines.append("1. JUDGMENT CONSISTENCY")
        lines.append("-" * 80)
        lines.append(f"Total inconsistencies found: {report['judgment_inconsistency_count']}")
        lines.append("")
        if report['judgment_inconsistencies']:
            lines.append("Sample inconsistencies:")
            for i, inc in enumerate(report['judgment_inconsistencies'][:5], 1):
                lines.append(f"\n  Inconsistency {i}:")
                lines.append(f"    Task: {inc['task_id']}")
                lines.append(f"    Object: {inc['object']}")
                # 动态获取turn信息
                for key, value in inc.items():
                    if key.startswith("turn_") and key.endswith("_judgment"):
                        lines.append(f"    {key}: {value}")
                lines.append(f"    Contradiction: {inc['contradiction']}")
                lines.append(f"    Severity: {inc['severity']}")
        lines.append("")

        # Score distributions
        lines.append("-" * 80)
        lines.append("2. SCORE DISTRIBUTION ANALYSIS")
        lines.append("-" * 80)
        for dim, analysis in sorted(report['score_distribution_analysis'].items()):
            lines.append(f"\n{dim}:")
            lines.append(f"  Status: {analysis['status']}")
            lines.append(f"  Unique values: {analysis['unique_values']}")
            lines.append(f"  Most common: {analysis['most_common']} ({analysis['most_common_rate']*100:.1f}%)")
            lines.append(f"  Std dev: {analysis['std_dev']:.3f}")
            lines.append(f"  Mean: {analysis['mean']:.3f}")
            lines.append(f"  Range: [{analysis['min']:.2f}, {analysis['max']:.2f}]")
        lines.append("")

        # Default value retention
        lines.append("-" * 80)
        lines.append("3. DEFAULT VALUE RETENTION")
        lines.append("-" * 80)
        for dim, stats in sorted(report['default_value_retention'].items()):
            lines.append(f"\n{dim}:")
            lines.append(f"  Default value: {stats['default']}")
            lines.append(f"  Retention rate: {stats['retained_rate']*100:.1f}%")
            lines.append(f"  ({stats['retained_count']}/{stats['total_samples']} samples)")
            lines.append(f"  Issue: {stats['issue']}")
        lines.append("")

        # State evolution issues
        lines.append("-" * 80)
        lines.append("4. STATE EVOLUTION ISSUES")
        lines.append("-" * 80)
        lines.append(f"Tasks analyzed: {report['state_snapshots_analyzed']}")
        if report['state_evolution_issues']:
            lines.append("\nIssues found:")
            for i, issue in enumerate(report['state_evolution_issues'], 1):
                lines.append(f"  {i}. {issue}")
        else:
            lines.append("\nNo state evolution issues detected")
        lines.append("")

        # Root causes
        lines.append("-" * 80)
        lines.append("ROOT CAUSES")
        lines.append("-" * 80)
        if report['root_causes']:
            for i, cause in enumerate(report['root_causes'], 1):
                lines.append(f"{i}. {cause}")
        else:
            lines.append("No major issues found")
        lines.append("")

        # Recommended fixes
        lines.append("-" * 80)
        lines.append("RECOMMENDED FIXES")
        lines.append("-" * 80)
        if report['recommended_fixes']:
            for i, fix in enumerate(report['recommended_fixes'], 1):
                lines.append(f"{i}. {fix}")
        else:
            lines.append("No fixes needed")
        lines.append("")

        lines.append("=" * 80)

        return "\n".join(lines)

    def save_reports(self, output_dir: str):
        """保存报告"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # 生成报告
        report, txt_report = self.generate_report()

        # 保存JSON报告
        json_file = output_path / "phase1_1.6_evaluator_state.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved JSON report to {json_file}")

        # 保存文本报告
        txt_file = output_path / "phase1_1.6_validation_report.txt"
        with open(txt_file, 'w', encoding='utf-8') as f:
            f.write(txt_report)
        logger.info(f"Saved text report to {txt_file}")

        # 保存judgment inconsistencies CSV
        if report['judgment_inconsistencies']:
            csv_file = output_path / "phase1_1.6_judgment_inconsistencies.csv"
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                if report['judgment_inconsistencies']:
                    # 获取所有可能的字段名
                    fieldnames = set()
                    for inc in report['judgment_inconsistencies']:
                        fieldnames.update(inc.keys())
                    fieldnames = sorted(fieldnames)

                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    for inc in report['judgment_inconsistencies']:
                        writer.writerow(inc)
            logger.info(f"Saved judgment inconsistencies to {csv_file}")

        # 保存score distributions可视化数据
        viz_file = output_path / "phase1_1.6_score_distributions.json"
        with open(viz_file, 'w', encoding='utf-8') as f:
            viz_data = {
                "distributions": report['score_distribution_analysis'],
                "raw_scores": {dim: scores[:1000] for dim, scores in self.score_data.items()}  # 限制数量
            }
            json.dump(viz_data, f, indent=2)
        logger.info(f"Saved score distributions data to {viz_file}")

        return report


def main():
    """主函数"""
    # 设置路径
    log_dir = "simulator_test_log"
    evaluator_path = "src/simulator/evaluator.py"
    output_dir = "docs/task/round3/results"

    # 创建追踪器
    tracker = EvaluatorStateTracker(log_dir, evaluator_path)

    # 运行验证并保存报告
    report = tracker.save_reports(output_dir)

    # 打印摘要
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    print(f"Status: {report['status']}")
    print(f"Severity: {report['severity']}")
    print(f"\nKey Findings:")
    print(f"  - Judgment inconsistencies: {report['judgment_inconsistency_count']}")
    print(f"  - Score dimensions analyzed: {len(report['score_distribution_analysis'])}")
    print(f"  - State snapshots: {report['state_snapshots_analyzed']}")

    # 显示常数化的维度
    constant_dims = [
        dim for dim, analysis in report['score_distribution_analysis'].items()
        if "CONSTANT" in analysis.get("status", "")
    ]
    if constant_dims:
        print(f"  - Constant score dimensions: {', '.join(constant_dims)}")

    # 显示高默认值保留的维度
    high_retention = [
        dim for dim, stats in report['default_value_retention'].items()
        if stats['retained_rate'] > 0.7
    ]
    if high_retention:
        print(f"  - High default retention: {', '.join(high_retention)}")

    print("\nReports saved to:", output_dir)
    print("=" * 80)


if __name__ == "__main__":
    main()
