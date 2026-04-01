"""
Phase 1 Task 1.1: Image Sending Validation
验证评审意见中的P0级问题：图像是否正确发送给VLM模型
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from collections import defaultdict


class ImageSendingValidator:
    """验证图像发送问题"""

    def __init__(self, log_dir: str, task_dir: Optional[str] = None):
        """
        Args:
            log_dir: Run logs目录
            task_dir: 任务数据目录（包含images/）
        """
        self.log_dir = Path(log_dir)
        self.task_dir = Path(task_dir) if task_dir else None
        self.statistics = {
            "total_turns": 0,
            "empty_images_sent": 0,
            "empty_percentage": 0.0,
            "by_task_type": defaultdict(lambda: {"total": 0, "empty": 0}),
            "by_run_log": {},
            "sample_failures": []
        }
        self.run_logs = []

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

    def analyze_single_log(self, log_file: Path) -> Dict:
        """分析单个run log文件"""
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                events = json.load(f)
        except Exception as e:
            return {
                "file": str(log_file),
                "error": str(e),
                "total_turns": 0,
                "empty_turns": 0
            }

        task_id = None
        task_type = None
        task_images = []
        total_turns = 0
        empty_turns = 0
        sample_failure = None

        for event in events:
            # 提取task信息
            if event.get("event") == "task_start":
                task_id = event.get("task_id") or event.get("data", {}).get("task_id")
                task_type = event.get("task_type") or event.get("data", {}).get("task_type")
                task_images = event.get("images") or event.get("data", {}).get("images", [])

            # 分析turn事件
            if event.get("event") == "turn" or event.get("event") == "target_model_response":
                total_turns += 1

                # 获取images_sent字段
                images_sent = event.get("images_sent")
                if images_sent is None and "data" in event:
                    images_sent = event["data"].get("images_sent")

                # 检查是否为空
                if not images_sent or len(images_sent) == 0:
                    empty_turns += 1

                    # 记录第一个失败案例作为样本
                    if sample_failure is None and total_turns <= 3:
                        response = event.get("response") or event.get("data", {}).get("response", "")
                        sample_failure = {
                            "turn": event.get("turn") or event.get("data", {}).get("turn"),
                            "action": event.get("action") or event.get("data", {}).get("action"),
                            "message": event.get("message") or event.get("data", {}).get("message", ""),
                            "response": response[:200] if response else "",
                            "images_sent": images_sent,
                            "task_images": task_images
                        }

        return {
            "file": str(log_file),
            "task_id": task_id,
            "task_type": task_type,
            "total_turns": total_turns,
            "empty_turns": empty_turns,
            "empty_percentage": (empty_turns / total_turns * 100) if total_turns > 0 else 0,
            "sample_failure": sample_failure
        }

    def analyze_logs(self) -> Dict:
        """分析run logs，统计images_sent为空的情况"""
        log_files = self.find_log_files()

        print(f"Found {len(log_files)} log files")
        print("Analyzing logs...")

        for i, log_file in enumerate(log_files):
            if (i + 1) % 10 == 0:
                print(f"  Processed {i + 1}/{len(log_files)} files...")

            result = self.analyze_single_log(log_file)
            self.run_logs.append(result)

            # 累计统计
            self.statistics["total_turns"] += result["total_turns"]
            self.statistics["empty_images_sent"] += result["empty_turns"]

            # 按task_type分组
            task_type = result.get("task_type", "unknown")
            self.statistics["by_task_type"][task_type]["total"] += result["total_turns"]
            self.statistics["by_task_type"][task_type]["empty"] += result["empty_turns"]

            # 记录每个文件的结果
            self.statistics["by_run_log"][result["file"]] = {
                "total": result["total_turns"],
                "empty": result["empty_turns"],
                "percentage": result["empty_percentage"]
            }

            # 收集样本失败案例
            if result.get("sample_failure") and len(self.statistics["sample_failures"]) < 10:
                self.statistics["sample_failures"].append({
                    "file": result["file"],
                    "task_id": result.get("task_id"),
                    **result["sample_failure"]
                })

        # 计算总体百分比
        if self.statistics["total_turns"] > 0:
            self.statistics["empty_percentage"] = (
                self.statistics["empty_images_sent"] / self.statistics["total_turns"] * 100
            )

        return self.statistics

    def trace_code_path(self) -> Dict:
        """追踪代码调用路径，定位问题"""
        # 查找关键代码文件
        script_dir = Path(__file__).parent  # round3目录
        project_root = script_dir.parent.parent.parent  # M3Bench_new目录
        src_dir = project_root / "src"
        simulator_file = src_dir / "simulator" / "strategic_simulator.py"
        llm_client_file = src_dir / "simulator" / "llm_client.py"

        trace_info = {
            "simulator_file": str(simulator_file),
            "llm_client_file": str(llm_client_file),
            "key_functions": {}
        }

        # 读取_get_images_for_turn函数
        if simulator_file.exists():
            with open(simulator_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # 查找_get_images_for_turn函数
            for i, line in enumerate(lines, 1):
                if "def _get_images_for_turn" in line:
                    trace_info["key_functions"]["_get_images_for_turn"] = {
                        "location": f"{simulator_file}:{i}",
                        "code_snippet": "".join(lines[i-1:min(i+29, len(lines))])
                    }
                    break

        # 读取call_target_model函数
        if llm_client_file.exists():
            with open(llm_client_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            for i, line in enumerate(lines, 1):
                if "def call_target_model" in line:
                    trace_info["key_functions"]["call_target_model"] = {
                        "location": f"{llm_client_file}:{i}",
                        "code_snippet": "".join(lines[i-1:min(i+19, len(lines))])
                    }
                    break

        return trace_info

    def identify_root_cause(self) -> Dict:
        """识别根本原因"""
        root_cause = {
            "status": "UNKNOWN",
            "location": None,
            "issue": None,
            "evidence": []
        }

        # 分析统计数据
        empty_pct = self.statistics["empty_percentage"]

        # 检查样本失败案例
        sample_failures = self.statistics.get("sample_failures", [])

        if empty_pct > 80:
            root_cause["status"] = "P0_CRITICAL"
            root_cause["issue"] = "Systematic image sending failure - >80% of turns have empty images_sent"

            # 从样本中查找证据
            if sample_failures:
                # 检查是否都回复"无法查看图像"
                cannot_view_count = sum(
                    1 for s in sample_failures
                    if "unable to view" in s.get("response", "").lower()
                    or "can't view" in s.get("response", "").lower()
                    or "cannot view" in s.get("response", "").lower()
                )

                if cannot_view_count > len(sample_failures) * 0.8:
                    root_cause["evidence"].append(
                        f"{cannot_view_count}/{len(sample_failures)} samples show 'cannot view images' response"
                    )

                # 检查task_images是否存在
                has_task_images = sum(
                    1 for s in sample_failures
                    if s.get("task_images") and len(s.get("task_images", [])) > 0
                )

                root_cause["evidence"].append(
                    f"{has_task_images}/{len(sample_failures)} tasks have images defined in task_start"
                )

            # 可能的原因定位
            root_cause["location"] = "strategic_simulator.py:_get_images_for_turn() or llm_client.py:call_target_model()"

        elif empty_pct > 20:
            root_cause["status"] = "PARTIAL_FAILURE"
            root_cause["issue"] = f"Partial image sending failure - {empty_pct:.1f}% of turns affected"
            root_cause["location"] = "Conditional failure - may depend on task type or configuration"

        else:
            root_cause["status"] = "MINOR_ISSUE"
            root_cause["issue"] = f"Low failure rate - {empty_pct:.1f}% of turns affected"

        return root_cause

    def create_minimal_reproduction(self) -> str:
        """创建最小复现脚本"""
        minimal_script = '''"""
Minimal reproduction case for image sending issue
"""

import sys
from pathlib import Path

def test_image_path_resolution():
    """测试图像路径解析"""
    # 获取项目根目录
    script_dir = Path(__file__).parent  # round3目录
    project_root = script_dir.parent.parent.parent  # M3Bench_new目录

    # 切换到项目根目录以测试相对路径
    import os
    os.chdir(project_root)

    # 模拟task_state的images字段
    test_images = [
        "images/COCO_val2014_000000578292.jpg",
        "images/COCO_val2014_000000157269.jpg",
        "images/COCO_val2014_000000322864.jpg"
    ]

    print("Testing image path resolution...")
    print(f"Project root: {project_root}")
    print(f"Current working directory: {Path.cwd()}")
    print(f"Task images: {test_images}")
    print()

    # 测试不同的路径解析方法
    valid_images = []
    for img_rel_path in test_images:
        print(f"Testing: {img_rel_path}")

        # Method 1: Direct path
        img_path = Path(img_rel_path)
        exists_1 = img_path.exists()
        print(f"  Direct path exists: {exists_1}")
        if exists_1:
            print(f"  -> {img_path.absolute()}")
            valid_images.append(str(img_path))

        # Method 2: Try different run_XX directories
        found = False
        if not exists_1:
            generated_tasks_dir = Path("generated_tasks_v2")
            if generated_tasks_dir.exists():
                for run_dir in generated_tasks_dir.glob("run_*"):
                    potential_path = run_dir / img_rel_path
                    if potential_path.exists():
                        print(f"  ✓ Found in: {potential_path}")
                        valid_images.append(str(potential_path))
                        found = True
                        break
            else:
                print(f"  ✗ generated_tasks_v2 directory not found")

        if not found and not exists_1:
            print(f"  ❌ NOT FOUND - This would cause empty images_sent")

        print()

    print("="*60)
    print(f"Summary: {len(valid_images)}/{len(test_images)} images found")
    print(f"Valid images: {valid_images}")
    print()

    if len(valid_images) == 0:
        print("❌ ROOT CAUSE CONFIRMED: No images can be resolved")
        print("   This explains why images_sent is empty!")
    elif len(valid_images) < len(test_images):
        print("⚠️  PARTIAL FAILURE: Some images cannot be resolved")
    else:
        print("✓ All images resolved successfully")

    return valid_images

if __name__ == "__main__":
    test_image_path_resolution()
'''

        output_file = Path(__file__).parent / "debug_image_sending_minimal.py"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(minimal_script)

        return str(output_file)

    def generate_report(self) -> Tuple[Dict, str]:
        """生成验证报告"""
        timestamp = datetime.now().isoformat()

        # 分析日志
        print("\n=== Analyzing Run Logs ===")
        self.analyze_logs()

        # 追踪代码路径
        print("\n=== Tracing Code Path ===")
        code_trace = self.trace_code_path()

        # 识别根本原因
        print("\n=== Identifying Root Cause ===")
        root_cause = self.identify_root_cause()

        # 创建最小复现
        print("\n=== Creating Minimal Reproduction ===")
        minimal_script = self.create_minimal_reproduction()

        # 判断总体状态
        empty_pct = self.statistics["empty_percentage"]
        status = "FAIL" if empty_pct > 20 else "PASS"

        # 构建JSON报告
        json_report = {
            "validation_id": "1.1_image_sending",
            "timestamp": timestamp,
            "status": status,
            "statistics": {
                "total_turns": self.statistics["total_turns"],
                "empty_images_sent": self.statistics["empty_images_sent"],
                "empty_percentage": round(self.statistics["empty_percentage"], 2),
                "by_task_type": {
                    k: {"total": v["total"], "empty": v["empty"], "percentage": round(v["empty"]/v["total"]*100, 2) if v["total"] > 0 else 0}
                    for k, v in self.statistics["by_task_type"].items()
                },
                "total_log_files": len(self.run_logs),
                "sample_failures": self.statistics.get("sample_failures", [])[:5]  # 只保留前5个样本
            },
            "root_cause": root_cause,
            "code_trace": {
                "simulator_file": code_trace.get("simulator_file"),
                "llm_client_file": code_trace.get("llm_client_file"),
                "key_functions": list(code_trace.get("key_functions", {}).keys())
            },
            "reproduction": {
                "minimal_case": minimal_script,
                "can_reproduce": True
            },
            "severity": root_cause["status"],
            "recommended_fix": self._generate_recommendations(root_cause)
        }

        # 构建文本报告
        text_report = self._generate_text_report(json_report)

        return json_report, text_report

    def _generate_recommendations(self, root_cause: Dict) -> List[str]:
        """生成修复建议"""
        recommendations = []

        if root_cause["status"] == "P0_CRITICAL":
            recommendations.extend([
                "IMMEDIATE: Fix image path resolution in _get_images_for_turn()",
                "Add path existence validation before API call",
                "Add detailed logging for image loading failures",
                "Verify images are correctly encoded before sending to API",
                "Re-run all experiments after fix to ensure validity"
            ])
        elif root_cause["status"] == "PARTIAL_FAILURE":
            recommendations.extend([
                "Investigate why some tasks succeed and others fail",
                "Check if failure correlates with task_type or timestamp",
                "Add validation to ensure consistent behavior",
                "Consider adding retry logic for failed image loads"
            ])
        else:
            recommendations.extend([
                "Monitor image sending in future runs",
                "Add automated tests to catch regressions"
            ])

        return recommendations

    def _generate_text_report(self, json_report: Dict) -> str:
        """生成人类可读的文本报告"""
        stats = json_report["statistics"]
        root_cause = json_report["root_cause"]

        status_emoji = "✅" if json_report["status"] == "PASS" else "❌"

        report = f"""
=== Image Sending Validation Report ===

Status: {json_report['status']} {status_emoji}
Timestamp: {json_report['timestamp']}

Problem Summary:
- {stats['empty_percentage']:.1f}% of turns have empty images_sent
- Total turns analyzed: {stats['total_turns']}
- Turns with empty images: {stats['empty_images_sent']}
- Log files analyzed: {stats['total_log_files']}

Breakdown by Task Type:
"""

        for task_type, data in stats['by_task_type'].items():
            report += f"  - {task_type}: {data['empty']}/{data['total']} empty ({data['percentage']:.1f}%)\n"

        report += f"""
Root Cause Analysis:
Status: {root_cause['status']}
Issue: {root_cause['issue']}
Location: {root_cause.get('location', 'Unknown')}

Evidence:
"""
        for evidence in root_cause.get('evidence', []):
            report += f"  - {evidence}\n"

        if stats.get('sample_failures'):
            report += f"""
Sample Failures (showing {len(stats['sample_failures'])} examples):
"""
            for i, sample in enumerate(stats['sample_failures'], 1):
                report += f"""
  Example {i}:
    File: {sample.get('file', 'Unknown')}
    Task ID: {sample.get('task_id', 'Unknown')}
    Turn: {sample.get('turn', 'Unknown')}
    Action: {sample.get('action', 'Unknown')}
    Task Images: {sample.get('task_images', [])}
    Images Sent: {sample.get('images_sent', [])}
    Model Response: "{sample.get('response', '')[:150]}..."
"""

        report += f"""
Impact:
"""
        if root_cause['status'] == "P0_CRITICAL":
            report += f"""  - {stats['empty_percentage']:.1f}% of visual evaluations are invalid
  - All run logs with this issue are unreliable
  - Need to re-run all experiments after fix
"""
        elif root_cause['status'] == "PARTIAL_FAILURE":
            report += f"""  - {stats['empty_percentage']:.1f}% of evaluations may be unreliable
  - Need to investigate conditional failure pattern
"""
        else:
            report += "  - Low impact, but monitoring recommended\n"

        report += """
Recommended Actions:
"""
        for i, rec in enumerate(json_report['recommended_fix'], 1):
            report += f"  {i}. {rec}\n"

        report += f"""
Minimal Reproduction:
Run: python {json_report['reproduction']['minimal_case']}
Expected: Image paths should resolve correctly
Actual: Will show which paths exist and which don't

Code Trace:
- Simulator: {json_report['code_trace']['simulator_file']}
- LLM Client: {json_report['code_trace']['llm_client_file']}
- Key functions: {', '.join(json_report['code_trace']['key_functions'])}

---
Report generated by ImageSendingValidator
"""

        return report


def main():
    """主函数"""
    # 配置路径 - 从round3目录往上找到项目根目录
    script_dir = Path(__file__).parent  # round3目录
    project_root = script_dir.parent.parent.parent  # M3Bench_new目录
    log_dir = project_root / "simulator_test_log"

    if not log_dir.exists():
        print(f"Error: Log directory not found: {log_dir}")
        print(f"Script location: {Path(__file__)}")
        print(f"Project root: {project_root}")
        sys.exit(1)

    # 创建验证器
    validator = ImageSendingValidator(str(log_dir))

    # 生成报告
    json_report, text_report = validator.generate_report()

    # 保存报告
    output_dir = Path(__file__).parent / "results"
    output_dir.mkdir(exist_ok=True)

    json_file = output_dir / "phase1_1.1_image_sending.json"
    text_file = output_dir / "phase1_1.1_image_sending.txt"

    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(json_report, f, indent=2, ensure_ascii=False)

    with open(text_file, 'w', encoding='utf-8') as f:
        f.write(text_report)

    # 输出到控制台
    print("\n" + text_report)
    print(f"\nReports saved to:")
    print(f"  JSON: {json_file}")
    print(f"  Text: {text_file}")

    # 创建日志
    log_dir_output = Path(__file__).parent / "logs"
    log_dir_output.mkdir(exist_ok=True)

    log_file = log_dir_output / "phase1_1.1_debug.log"
    with open(log_file, 'w', encoding='utf-8') as f:
        f.write(f"=== Debug Log for Phase 1 Task 1.1 ===\n")
        f.write(f"Timestamp: {datetime.now().isoformat()}\n")
        f.write(f"Log files analyzed: {len(validator.run_logs)}\n\n")

        f.write("Detailed results per log file:\n")
        for result in validator.run_logs[:20]:  # 只记录前20个
            f.write(f"\nFile: {result['file']}\n")
            f.write(f"  Task ID: {result.get('task_id', 'N/A')}\n")
            f.write(f"  Task Type: {result.get('task_type', 'N/A')}\n")
            f.write(f"  Total turns: {result['total_turns']}\n")
            f.write(f"  Empty turns: {result['empty_turns']}\n")
            f.write(f"  Empty %: {result['empty_percentage']:.1f}%\n")

        if len(validator.run_logs) > 20:
            f.write(f"\n... and {len(validator.run_logs) - 20} more files\n")

    print(f"  Log: {log_file}")

    # 返回状态码
    return 0 if json_report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
