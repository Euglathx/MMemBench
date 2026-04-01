"""
快速分析现有日志并生成图表
"""

import sys
import json
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent))

from analysis.log_parser import LogParser
from analysis.result_aggregator import ResultAggregator
from analysis.visualizer import ExperimentVisualizer


def quick_analyze():
    """快速分析已有日志并生成图表"""

    log_dir = Path("simulator_test_log/batch_run_20260205_104458")

    if not log_dir.exists():
        print(f"❌ 日志目录不存在: {log_dir}")
        return

    # 查找所有日志文件
    log_files = sorted(list(log_dir.glob("*.jsonl")) + list(log_dir.glob("*.json")))

    if not log_files:
        print(f"❌ 没有日志文件: {log_dir}")
        return

    print(f"✓ 找到 {len(log_files)} 个日志文件\n")

    # 解析所有日志
    parsed_logs = []
    for log_file in log_files:
        try:
            parser = LogParser()
            parsed_log = parser.parse_log_file(log_file)
            parsed_logs.append(parsed_log)
            print(f"✓ 解析: {log_file.name} ({len(parsed_log.turns)} 轮)")
        except Exception as e:
            print(f"⚠ 跳过: {log_file.name} - {e}")

    if not parsed_logs:
        print("\n❌ 没有成功解析任何日志")
        return

    print(f"\n✓ 成功解析 {len(parsed_logs)} 个日志\n")

    # 聚合数据（使用默认模型名称）
    model_name = "tested_model"
    aggregator = ResultAggregator()
    aggregated = aggregator.aggregate_logs(parsed_logs, model_name)

    # 显示统计
    print("="*80)
    print("数据统计")
    print("="*80)
    print(f"任务总数: {aggregated.statistics.total_tasks}")
    print(f"总轮数: {aggregated.statistics.total_turns}")
    print(f"平均轮数/任务: {aggregated.statistics.avg_turns_per_task:.1f}")

    if 'score' in aggregated.statistics.score_stats:
        score_stat = aggregated.statistics.score_stats['score']
        print(f"\n得分统计:")
        print(f"  平均值: {score_stat.mean:.3f}")
        print(f"  中位数: {score_stat.median:.3f}")
        print(f"  标准差: {score_stat.std:.3f}")
        print(f"  最小值: {score_stat.min:.3f}")
        print(f"  最大值: {score_stat.max:.3f}")

    # 生成图表
    print("\n" + "="*80)
    print("生成图表")
    print("="*80)

    output_dir = "experiment_results/single_model_test"
    visualizer = ExperimentVisualizer(output_dir)

    # 准备数据（作为单模型"对比"）
    results_by_model = {model_name: aggregated}

    try:
        print("\n1. 雷达图...")
        visualizer.plot_radar_chart(results_by_model, output_file="01_radar_chart.png")
        print("   ✓ 已生成: 01_radar_chart.png")

        print("\n2. 柱状图...")
        visualizer.plot_bar_chart(results_by_model, dimension="score", output_file="02_bar_chart.png")
        print("   ✓ 已生成: 02_bar_chart.png")

        print("\n3. 轮次进度图...")
        visualizer.plot_turn_progression(results_by_model, output_file="03_turn_progression.png")
        print("   ✓ 已生成: 03_turn_progression.png")

        print("\n4. Lag分析图...")
        visualizer.plot_lag_analysis(results_by_model, output_file="04_lag_analysis.png")
        print("   ✓ 已生成: 04_lag_analysis.png")

        print("\n5. 错误分布图...")
        visualizer.plot_error_distribution(results_by_model, output_file="05_error_distribution.png")
        print("   ✓ 已生成: 05_error_distribution.png")

        print("\n6. 对比表格...")
        visualizer.plot_comparison_table(results_by_model, output_file="06_comparison_table.png")
        print("   ✓ 已生成: 06_comparison_table.png")

        print("\n" + "="*80)
        print(f"✓ 所有图表已生成到: {output_dir}")
        print("="*80)

        # 保存聚合数据供后续使用
        data_file = Path(output_dir) / "aggregated_data.json"
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump({
                model_name: {
                    'metadata': aggregated.metadata,
                    'statistics': {
                        'total_tasks': aggregated.statistics.total_tasks,
                        'total_turns': aggregated.statistics.total_turns,
                        'avg_turns_per_task': aggregated.statistics.avg_turns_per_task,
                        'score_stats': {k: v.to_dict() for k, v in aggregated.statistics.score_stats.items()}
                    }
                }
            }, f, indent=2, ensure_ascii=False)

        print(f"\n✓ 聚合数据已保存: {data_file}")

    except Exception as e:
        print(f"\n❌ 生成图表失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    quick_analyze()
