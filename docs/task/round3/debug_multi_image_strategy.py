#!/usr/bin/env python3
"""
Phase 1 Task 1.5: Multi-Image Strategy Validation
=================================================

验证评审意见中的P1级问题：多图任务的图像注入策略是否一致和正确

检查以下问题:
1. 图像发送统计: 每个turn发送了多少张图？
2. 策略一致性: StrategicSimulator vs LLMUserSimulator策略是否相同？
3. 任务定义验证: question/expected_answer/images是否对齐？
4. Evaluator图像感知: Evaluator知道实际发送了哪些图像吗？
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

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MultiImageStrategyValidator:
    """验证多图任务的图像策略"""

    def __init__(self, log_dir: str, simulator_path: str, task_dir: str):
        """
        初始化验证器

        Args:
            log_dir: Run logs目录路径
            simulator_path: simulator代码路径
            task_dir: 任务定义目录
        """
        self.log_dir = Path(log_dir)
        self.simulator_path = Path(simulator_path)
        self.task_dir = Path(task_dir)

        self.image_stats = {
            "total_ac_turns": 0,
            "all_images_sent": 0,
            "some_images_sent": 0,
            "no_images_sent": 0,
            "distribution": defaultdict(int),
            "by_task": defaultdict(lambda: {"turns": 0, "image_counts": []})
        }

        self.misaligned_tasks = []
        self.evaluator_inconsistencies = []

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

    def analyze_image_sending_stats(self) -> Dict:
        """统计图像发送情况"""
        logger.info("Analyzing image sending statistics...")

        log_files = self.find_log_files()
        logger.info(f"Found {len(log_files)} log files")

        for log_file in log_files:
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    events = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to read {log_file}: {e}")
                continue

            task_id = None
            task_type = None
            task_images = []

            for event in events:
                # 提取task信息
                if event.get("event") == "task_start":
                    data = event.get("data", event)
                    task_id = data.get("task_id")
                    task_type = data.get("task_type")
                    task_images = data.get("images", [])

                # 分析turn事件
                if event.get("event") == "turn":
                    data = event.get("data", event)

                    # 只统计AC任务（多图任务）
                    if task_type != "attribute_comparison":
                        continue

                    self.image_stats["total_ac_turns"] += 1

                    # 获取images_sent字段
                    images_sent = data.get("images_sent", [])
                    num_images = len(images_sent) if images_sent else 0

                    # 统计分布
                    self.image_stats["distribution"][num_images] += 1

                    # 分类统计
                    if num_images == 0:
                        self.image_stats["no_images_sent"] += 1
                    elif num_images == len(task_images):
                        self.image_stats["all_images_sent"] += 1
                    else:
                        self.image_stats["some_images_sent"] += 1

                    # 按任务统计
                    if task_id:
                        self.image_stats["by_task"][task_id]["turns"] += 1
                        self.image_stats["by_task"][task_id]["image_counts"].append(num_images)

        return self.image_stats

    def compare_simulator_strategies(self) -> Dict:
        """对比不同simulator的策略"""
        logger.info("Comparing simulator strategies...")

        strategy_comparison = {
            "StrategicSimulator": {
                "policy": "unknown",
                "implementation": "",
                "code_location": ""
            },
            "LLMUserSimulator": {
                "policy": "unknown",
                "implementation": "",
                "code_location": ""
            },
            "used_in_batch_run": "unknown",
            "consistency": "UNKNOWN"
        }

        # 分析StrategicSimulator
        strategic_path = self.simulator_path / "strategic_simulator.py"
        if strategic_path.exists():
            with open(strategic_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 查找_get_images_for_turn方法
            match = re.search(
                r'def _get_images_for_turn\(self.*?\n(.*?)(?=\n    def |\nclass |\Z)',
                content,
                re.DOTALL
            )
            if match:
                method_body = match.group(1)

                # 检查注释和实现
                if "send ALL images on EVERY turn" in method_body:
                    strategy_comparison["StrategicSimulator"]["policy"] = "send_all_every_turn"
                    strategy_comparison["StrategicSimulator"]["implementation"] = \
                        "_get_images_for_turn() returns all valid images"

                # 提取关键代码行
                lines = [l.strip() for l in method_body.split('\n') if l.strip() and not l.strip().startswith('#')]
                strategy_comparison["StrategicSimulator"]["code_location"] = "strategic_simulator.py:890-919"

        # 分析LLMUserSimulator
        llm_path = self.simulator_path / "llm_user_simulator.py"
        if llm_path.exists():
            with open(llm_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 查找_get_images_to_send方法
            match = re.search(
                r'def _get_images_to_send\(self.*?\n(.*?)(?=\n    def |\nclass |\Z)',
                content,
                re.DOTALL
            )
            if match:
                method_body = match.group(1)

                # 检查实现
                if "guidance" in method_body and "images_shown" in method_body:
                    strategy_comparison["LLMUserSimulator"]["policy"] = "progressive"
                    strategy_comparison["LLMUserSimulator"]["implementation"] = \
                        "_get_images_to_send() sends one at a time on guidance"

                strategy_comparison["LLMUserSimulator"]["code_location"] = "llm_user_simulator.py:517-537"

        # 确定实际使用的simulator
        # 通过检查log文件中的特征来判断
        log_files = self.find_log_files()
        if log_files:
            try:
                with open(log_files[0], 'r', encoding='utf-8') as f:
                    events = json.load(f)

                # StrategicSimulator的特征：有phase字段
                for event in events:
                    if event.get("event") == "turn":
                        data = event.get("data", event)
                        if "phase" in data:
                            strategy_comparison["used_in_batch_run"] = "StrategicSimulator"
                            break
            except:
                pass

        # 判断一致性
        if (strategy_comparison["StrategicSimulator"]["policy"] == "send_all_every_turn" and
            strategy_comparison["LLMUserSimulator"]["policy"] == "progressive"):
            strategy_comparison["consistency"] = "INCONSISTENT"
        else:
            strategy_comparison["consistency"] = "UNKNOWN"

        return strategy_comparison

    def check_task_definition_alignment(self) -> List[Dict]:
        """检查任务定义对齐"""
        logger.info("Checking task definition alignment...")

        misaligned_tasks = []

        # 查找所有任务定义文件
        task_files = []
        for pattern in ["*.json", "*.jsonl"]:
            task_files.extend(self.task_dir.glob(f"**/{pattern}"))

        for task_file in task_files:
            try:
                with open(task_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()

                # 处理JSONL格式
                if task_file.suffix == '.jsonl':
                    tasks = [json.loads(line) for line in content.split('\n') if line.strip()]
                else:
                    # 尝试作为JSON数组或单个对象
                    try:
                        data = json.loads(content)
                        tasks = data if isinstance(data, list) else [data]
                    except:
                        continue

                for task in tasks:
                    # 只检查AC任务
                    if task.get("task_type") != "attribute_comparison":
                        continue

                    task_id = task.get("task_id", "unknown")
                    question = task.get("question", "")
                    images = task.get("images", [])
                    expected_answer = task.get("expected_answer") or task.get("answer", "")

                    # 检查对齐问题
                    issues = []

                    # 问题1: question问比较，但expected只给单图信息
                    comparison_keywords = ["which", "more", "less", "most", "least", "compare"]
                    if any(kw in question.lower() for kw in comparison_keywords):
                        # expected应该包含比较结论
                        if len(images) > 1:
                            # 检查expected是否只提到一个图
                            image_mentions = len(re.findall(r'[Ii]mage \d+', expected_answer))
                            if image_mentions == 1:
                                issues.append(
                                    f"Question asks comparison but expected mentions only 1 image"
                                )

                    # 问题2: 多图任务但expected不完整
                    if len(images) > 1:
                        # expected应该包含所有图的信息或比较结论
                        if "has more" not in expected_answer.lower() and \
                           "has less" not in expected_answer.lower() and \
                           "bottommost" not in expected_answer.lower() and \
                           "topmost" not in expected_answer.lower():
                            # 检查是否只是单纯的计数
                            if re.match(r'^Image \d+ has \d+', expected_answer):
                                issues.append(
                                    f"Multi-image task but expected is single image count"
                                )

                    if issues:
                        misaligned_tasks.append({
                            "task_id": task_id,
                            "question": question,
                            "images_count": len(images),
                            "expected_answer": expected_answer,
                            "issues": issues
                        })

            except Exception as e:
                logger.warning(f"Failed to process {task_file}: {e}")
                continue

        return misaligned_tasks

    def verify_evaluator_awareness(self) -> Dict:
        """验证evaluator的图像感知"""
        logger.info("Verifying evaluator image awareness...")

        awareness_report = {
            "receives_images_sent": False,
            "cross_image_mapping_aligned": None,
            "llm_judge_prompt_accurate": None,
            "inconsistent_cases": []
        }

        # 检查evaluator代码
        evaluator_path = self.simulator_path / "evaluator.py"
        if evaluator_path.exists():
            with open(evaluator_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 查找evaluate_response方法签名
            if "def evaluate_response" in content:
                # 检查是否接收images参数
                match = re.search(
                    r'def evaluate_response\((.*?)\):',
                    content
                )
                if match:
                    params = match.group(1)
                    awareness_report["receives_images_sent"] = "images" in params

        # 从日志中查找不一致案例
        log_files = self.find_log_files()

        for log_file in log_files[:20]:  # 只检查前20个
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    events = json.load(f)
            except:
                continue

            task_id = None

            for event in events:
                if event.get("event") == "task_start":
                    data = event.get("data", event)
                    task_id = data.get("task_id")

                if event.get("event") == "turn":
                    data = event.get("data", event)

                    images_sent = data.get("images_sent", [])
                    evaluation = data.get("evaluation", {})
                    reasoning = evaluation.get("reasoning", "")

                    # 检查reasoning中对图像数量的描述是否正确
                    if images_sent and reasoning:
                        actual_count = len(images_sent)

                        # 查找reasoning中提到的图像数量
                        patterns = [
                            r'only (\w+) image',
                            r'(\w+) image(?:s)?',
                            r'single image',
                            r'one image'
                        ]

                        for pattern in patterns:
                            matches = re.findall(pattern, reasoning.lower())
                            if matches:
                                for match in matches:
                                    if match == 'one' or match == 'single':
                                        claimed_count = 1
                                    elif match == 'two':
                                        claimed_count = 2
                                    elif match == 'three':
                                        claimed_count = 3
                                    else:
                                        continue

                                    if claimed_count != actual_count:
                                        awareness_report["inconsistent_cases"].append({
                                            "task_id": task_id,
                                            "turn": data.get("turn"),
                                            "images_sent": actual_count,
                                            "evaluator_reasoning_says": f"mentions {claimed_count} image(s)",
                                            "inconsistency": f"Evaluator thinks {claimed_count} image(s), actually {actual_count} sent"
                                        })
                                        break

        # 基于发现设置状态
        awareness_report["llm_judge_prompt_accurate"] = len(awareness_report["inconsistent_cases"]) == 0

        return awareness_report

    def generate_report(self) -> Tuple[Dict, str]:
        """生成完整报告"""
        logger.info("Generating comprehensive report...")

        # 执行所有分析
        image_stats = self.analyze_image_sending_stats()
        strategy_comparison = self.compare_simulator_strategies()
        misaligned_tasks = self.check_task_definition_alignment()
        evaluator_awareness = self.verify_evaluator_awareness()

        # 确定状态
        status = "PASS"
        root_causes = []
        recommended_fixes = []

        # 检查问题
        if image_stats["all_images_sent"] > 0 and image_stats["no_images_sent"] > 0:
            status = "FAIL"
            root_causes.append("Inconsistent image sending: some turns send all, some send none")

        if strategy_comparison["consistency"] == "INCONSISTENT":
            status = "FAIL"
            root_causes.append("Two simulators have different image sending strategies")
            recommended_fixes.append("Unify image sending strategy across simulators")

        if len(misaligned_tasks) > 0:
            status = "FAIL"
            root_causes.append(f"Task definition misaligned: {len(misaligned_tasks)} tasks have question/answer mismatch")
            recommended_fixes.append("Fix task definitions: expected_answer should match question type")

        if not evaluator_awareness["llm_judge_prompt_accurate"]:
            status = "FAIL"
            root_causes.append("Evaluator not informed of actually sent images")
            recommended_fixes.append("Pass images_sent to evaluator for accurate assessment")

        # 构建JSON报告
        report = {
            "validation_id": "1.5_multi_image_strategy",
            "timestamp": datetime.now().isoformat(),
            "status": status,
            "image_sending_statistics": {
                "total_ac_turns": image_stats["total_ac_turns"],
                "all_images_sent": image_stats["all_images_sent"],
                "some_images_sent": image_stats["some_images_sent"],
                "no_images_sent": image_stats["no_images_sent"],
                "distribution": dict(image_stats["distribution"])
            },
            "strategy_comparison": strategy_comparison,
            "task_definition_analysis": {
                "total_ac_tasks": len(set(t["task_id"] for t in misaligned_tasks)) if misaligned_tasks else 0,
                "misaligned_tasks": misaligned_tasks[:10],  # 只保存前10个
                "misaligned_count": len(misaligned_tasks),
                "misaligned_rate": len(misaligned_tasks) / max(1, len(misaligned_tasks)) * 100
            },
            "evaluator_image_awareness": evaluator_awareness,
            "root_causes": root_causes,
            "severity": "P1_HIGH" if status == "FAIL" else "P1_LOW",
            "recommended_fixes": recommended_fixes
        }

        # 构建文本报告
        txt_report = self._format_text_report(report)

        return report, txt_report

    def _format_text_report(self, report: Dict) -> str:
        """格式化文本报告"""
        lines = []
        lines.append("=" * 80)
        lines.append("Phase 1 Task 1.5: Multi-Image Strategy Validation Report")
        lines.append("=" * 80)
        lines.append(f"Timestamp: {report['timestamp']}")
        lines.append(f"Status: {report['status']}")
        lines.append(f"Severity: {report['severity']}")
        lines.append("")

        # Image sending statistics
        lines.append("-" * 80)
        lines.append("1. IMAGE SENDING STATISTICS")
        lines.append("-" * 80)
        stats = report['image_sending_statistics']
        lines.append(f"Total AC turns analyzed: {stats['total_ac_turns']}")
        lines.append(f"  - All images sent: {stats['all_images_sent']} ({stats['all_images_sent']/max(1, stats['total_ac_turns'])*100:.1f}%)")
        lines.append(f"  - Some images sent: {stats['some_images_sent']} ({stats['some_images_sent']/max(1, stats['total_ac_turns'])*100:.1f}%)")
        lines.append(f"  - No images sent: {stats['no_images_sent']} ({stats['no_images_sent']/max(1, stats['total_ac_turns'])*100:.1f}%)")
        lines.append("")
        lines.append("Distribution by image count:")
        for count, freq in sorted(stats['distribution'].items()):
            lines.append(f"  {count} images: {freq} turns")
        lines.append("")

        # Strategy comparison
        lines.append("-" * 80)
        lines.append("2. SIMULATOR STRATEGY COMPARISON")
        lines.append("-" * 80)
        comp = report['strategy_comparison']
        lines.append(f"Consistency: {comp['consistency']}")
        lines.append("")
        lines.append("StrategicSimulator:")
        lines.append(f"  Policy: {comp['StrategicSimulator']['policy']}")
        lines.append(f"  Implementation: {comp['StrategicSimulator']['implementation']}")
        lines.append("")
        lines.append("LLMUserSimulator:")
        lines.append(f"  Policy: {comp['LLMUserSimulator']['policy']}")
        lines.append(f"  Implementation: {comp['LLMUserSimulator']['implementation']}")
        lines.append("")
        lines.append(f"Used in batch run: {comp['used_in_batch_run']}")
        lines.append("")

        # Task definition analysis
        lines.append("-" * 80)
        lines.append("3. TASK DEFINITION ALIGNMENT")
        lines.append("-" * 80)
        task_def = report['task_definition_analysis']
        lines.append(f"Misaligned tasks: {task_def['misaligned_count']}")
        lines.append("")
        if task_def['misaligned_tasks']:
            lines.append("Sample misaligned tasks:")
            for i, task in enumerate(task_def['misaligned_tasks'][:5], 1):
                lines.append(f"\n  Task {i}: {task['task_id']}")
                lines.append(f"    Question: {task['question'][:80]}...")
                lines.append(f"    Images: {task['images_count']}")
                lines.append(f"    Expected: {task['expected_answer'][:80]}...")
                lines.append(f"    Issues: {', '.join(task['issues'])}")
        lines.append("")

        # Evaluator awareness
        lines.append("-" * 80)
        lines.append("4. EVALUATOR IMAGE AWARENESS")
        lines.append("-" * 80)
        awareness = report['evaluator_image_awareness']
        lines.append(f"Receives images_sent: {awareness['receives_images_sent']}")
        lines.append(f"LLM Judge prompt accurate: {awareness['llm_judge_prompt_accurate']}")
        lines.append(f"Inconsistent cases found: {len(awareness['inconsistent_cases'])}")
        if awareness['inconsistent_cases']:
            lines.append("\nSample inconsistencies:")
            for i, case in enumerate(awareness['inconsistent_cases'][:3], 1):
                lines.append(f"\n  Case {i}: {case['task_id']} Turn {case['turn']}")
                lines.append(f"    Images sent: {case['images_sent']}")
                lines.append(f"    Evaluator says: {case['evaluator_reasoning_says']}")
                lines.append(f"    Issue: {case['inconsistency']}")
        lines.append("")

        # Root causes
        lines.append("-" * 80)
        lines.append("ROOT CAUSES")
        lines.append("-" * 80)
        for i, cause in enumerate(report['root_causes'], 1):
            lines.append(f"{i}. {cause}")
        lines.append("")

        # Recommended fixes
        lines.append("-" * 80)
        lines.append("RECOMMENDED FIXES")
        lines.append("-" * 80)
        for i, fix in enumerate(report['recommended_fixes'], 1):
            lines.append(f"{i}. {fix}")
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
        json_file = output_path / "phase1_1.5_multi_image.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved JSON report to {json_file}")

        # 保存文本报告
        txt_file = output_path / "phase1_1.5_validation_report.txt"
        with open(txt_file, 'w', encoding='utf-8') as f:
            f.write(txt_report)
        logger.info(f"Saved text report to {txt_file}")

        # 保存misaligned tasks CSV
        if report['task_definition_analysis']['misaligned_tasks']:
            csv_file = output_path / "phase1_1.5_misaligned_tasks.csv"
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'task_id', 'question', 'images_count', 'expected_answer', 'issues'
                ])
                writer.writeheader()
                for task in report['task_definition_analysis']['misaligned_tasks']:
                    writer.writerow({
                        'task_id': task['task_id'],
                        'question': task['question'],
                        'images_count': task['images_count'],
                        'expected_answer': task['expected_answer'],
                        'issues': '; '.join(task['issues'])
                    })
            logger.info(f"Saved misaligned tasks to {csv_file}")

        # 保存evaluator inconsistencies CSV
        if report['evaluator_image_awareness']['inconsistent_cases']:
            csv_file = output_path / "phase1_1.5_evaluator_inconsistencies.csv"
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'task_id', 'turn', 'images_sent', 'evaluator_reasoning_says', 'inconsistency'
                ])
                writer.writeheader()
                for case in report['evaluator_image_awareness']['inconsistent_cases']:
                    writer.writerow(case)
            logger.info(f"Saved evaluator inconsistencies to {csv_file}")

        return report


def main():
    """主函数"""
    # 设置路径
    log_dir = "simulator_test_log"
    simulator_path = "src/simulator"
    task_dir = "generated_tasks_v2"
    output_dir = "docs/task/round3/results"

    # 创建验证器
    validator = MultiImageStrategyValidator(log_dir, simulator_path, task_dir)

    # 运行验证并保存报告
    report = validator.save_reports(output_dir)

    # 打印摘要
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    print(f"Status: {report['status']}")
    print(f"Severity: {report['severity']}")
    print(f"\nKey Findings:")
    print(f"  - Total AC turns: {report['image_sending_statistics']['total_ac_turns']}")
    print(f"  - All images sent: {report['image_sending_statistics']['all_images_sent']}")
    print(f"  - Misaligned tasks: {report['task_definition_analysis']['misaligned_count']}")
    print(f"  - Evaluator inconsistencies: {len(report['evaluator_image_awareness']['inconsistent_cases'])}")
    print("\nReports saved to:", output_dir)
    print("=" * 80)


if __name__ == "__main__":
    main()
