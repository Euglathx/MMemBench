"""
检查实验状态的脚本
"""

import json
from pathlib import Path
from datetime import datetime

def check_logs():
    """检查最新的日志目录"""
    log_base = Path("simulator_test_log")

    if not log_base.exists():
        print("❌ 日志目录不存在")
        return

    # 查找所有batch_run目录（排除mock）
    dirs = sorted(
        [d for d in log_base.glob("batch_run_*") if d.is_dir() and "mock" not in d.name],
        key=lambda x: x.stat().st_mtime,
        reverse=True
    )

    if not dirs:
        print("❌ 没有找到任何测试日志")
        return

    print("="*80)
    print("最近的测试运行:")
    print("="*80 + "\n")

    for i, log_dir in enumerate(dirs[:5], 1):  # 只显示最近5个
        print(f"{i}. {log_dir.name}")

        # 统计日志文件
        log_files = list(log_dir.glob("*.jsonl"))
        print(f"   日志文件数: {len(log_files)}")

        if log_files:
            # 分析第一个日志文件
            first_log = log_files[0]
            try:
                with open(first_log, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

                events = [json.loads(line) for line in lines if line.strip()]

                # 提取信息
                task_start = None
                turns = []
                for event in events:
                    if event.get('event') == 'task_start':
                        task_start = event.get('data', {})
                    elif event.get('event') == 'turn':
                        turns.append(event)

                if task_start:
                    print(f"   任务类型: {task_start.get('task_type', 'N/A')}")
                    print(f"   数据集: {task_start.get('dataset', 'N/A')}")
                    print(f"   模型: {task_start.get('model_name', 'N/A')}")

                print(f"   对话轮数: {len(turns)}")

            except Exception as e:
                print(f"   ⚠ 无法解析日志: {e}")

        # 获取创建时间
        timestamp = datetime.fromtimestamp(log_dir.stat().st_mtime)
        print(f"   创建时间: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print()


def check_experiment_results():
    """检查已生成的实验结果"""
    results_base = Path("experiment_results")

    if not results_base.exists():
        print("❌ 实验结果目录不存在")
        return

    print("="*80)
    print("已生成的实验结果:")
    print("="*80 + "\n")

    # 单模型结果
    models_dir = results_base / "models"
    if models_dir.exists():
        model_dirs = sorted(models_dir.glob("*"))
        if model_dirs:
            print("单模型分析:")
            for model_dir in model_dirs:
                if model_dir.is_dir():
                    charts = list(model_dir.glob("*.png"))
                    print(f"  ✓ {model_dir.name}: {len(charts)} 张图表")
        else:
            print("  ❌ 还没有单模型分析结果")

    print()

    # 多模型对比
    comparison_dir = results_base / "multi_model_comparison"
    if comparison_dir.exists():
        charts = list(comparison_dir.glob("*.png"))
        if charts:
            print("多模型对比:")
            print(f"  ✓ 已生成 {len(charts)} 张对比图表")
            for chart in sorted(charts):
                print(f"    - {chart.name}")
        else:
            print("  ❌ 还没有多模型对比结果")
    else:
        print("  ❌ 还没有多模型对比结果")


if __name__ == "__main__":
    check_logs()
    print("\n")
    check_experiment_results()
