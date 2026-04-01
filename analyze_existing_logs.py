"""
使用现有日志进行实验分析
不需要等待API完成，直接用已有的日志数据
"""

import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent))

from analysis.log_parser import LogParser
from analysis.result_aggregator import ResultAggregator
from analysis.visualizer import ExperimentVisualizer


def analyze_existing_logs():
    """分析已有的日志文件"""
    log_base = Path("simulator_test_log")

    # 找到 batch_run_20260205_104458 目录
    target_dir = log_base / "batch_run_20260205_104458"

    if not target_dir.exists():
        print(f"❌ 日志目录不存在: {target_dir}")
        return

    # 支持 .jsonl 和 .json 两种格式
    log_files = sorted(list(target_dir.glob("*.jsonl")) + list(target_dir.glob("*.json")))

    if not log_files:
        print(f"❌ 目录中没有日志文件: {target_dir}")
        return

    print(f"✓ 找到 {len(log_files)} 个日志文件\n")

    # 按模型分组（这些日志没有model_name字段，使用默认名称）
    model_name = "unknown_model"  # 默认模型名称
    model_logs = {model_name: []}

    for log_file in log_files:
        try:
            parser = LogParser()
            parsed_log = parser.parse_log_file(log_file)

            model_logs[model_name].append(parsed_log)

            print(f"✓ 解析: {log_file.name}")
            print(f"  任务类型: {parsed_log.task_metadata.task_type}")
            print(f"  数据集: {parsed_log.task_metadata.dataset}")
            print(f"  轮数: {len(parsed_log.turns)}")
            print()

        except Exception as e:
            print(f"⚠ 解析失败 {log_file.name}: {e}\n")
            import traceback
            traceback.print_exc()
            continue

    if not model_logs:
        print("❌ 没有成功解析任何日志文件")
        return

    # 为每个模型生成图表
    print("\n" + "="*80)
    print("生成单模型分析图表")
    print("="*80 + "\n")

    for model_name, parsed_logs in model_logs.items():
        print(f"分析模型: {model_name}")
        print(f"日志数量: {len(parsed_logs)}")

        # 聚合数据
        aggregator = ResultAggregator()
        aggregated = aggregator.aggregate_logs(parsed_logs, model_name)

        avg_score = aggregated.statistics.score_stats.get('score').mean if 'score' in aggregated.statistics.score_stats else 0.0
        print(f"  平均得分: {avg_score:.3f}")
        print(f"  平均轮数: {aggregated.statistics.avg_turns_per_task:.1f}")
        print(f"  任务总数: {aggregated.statistics.total_tasks}")
        print(f"  总轮数: {aggregated.statistics.total_turns}")
        print()

        # 生成可视化
        output_dir = Path(f"experiment_results/models/{model_name}")
        output_dir.mkdir(parents=True, exist_ok=True)

        visualizer = ExperimentVisualizer(aggregated, output_dir)

        try:
            visualizer.plot_radar_chart()
            print(f"  ✓ 雷达图")

            visualizer.plot_bar_chart()
            print(f"  ✓ 柱状图")

            visualizer.plot_turn_progression()
            print(f"  ✓ 折线图")

            visualizer.plot_lag_analysis()
            print(f"  ✓ Lag分析图")

            visualizer.plot_error_distribution()
            print(f"  ✓ 错误分布图")

            visualizer.plot_comparison_table()
            print(f"  ✓ 对比表格")

            print(f"\n✓ {model_name} 的所有图表已生成到: {output_dir}\n")

        except Exception as e:
            print(f"❌ 生成图表失败: {e}\n")
            import traceback
            traceback.print_exc()

    # 生成多模型对比
    print("\n" + "="*80)
    print("生成多模型对比")
    print("="*80 + "\n")

    all_aggregated = {}
    for model_name, parsed_logs in model_logs.items():
        aggregator = ResultAggregator()
        all_aggregated[model_name] = aggregator.aggregate_logs(parsed_logs, model_name)

    if len(all_aggregated) > 1:
        # 使用multi_model_comparison脚本
        print("✓ 多个模型数据已收集")
        print("模型列表:", list(all_aggregated.keys()))
        print("\n运行: python run_multi_model_comparison.py")
    else:
        print(f"⚠ 只有 {len(all_aggregated)} 个模型，无法生成多模型对比")
        print("需要至少2个模型的数据")


if __name__ == "__main__":
    analyze_existing_logs()
