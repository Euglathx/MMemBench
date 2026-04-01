"""
分析最新的真实测试日志
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from analysis.log_parser import LogParser
from analysis.result_aggregator import ResultAggregator
from analysis.visualizer import ExperimentVisualizer


def analyze_latest_logs():
    """分析最新生成的日志"""

    # 最新日志目录
    log_dir = Path("simulator_test_log/batch_run_20260205_185654")

    if not log_dir.exists():
        print(f"❌ 日志目录不存在: {log_dir}")
        return

    log_files = sorted(log_dir.glob("*.json"))

    if not log_files:
        print(f"❌ 没有日志文件")
        return

    print(f"✓ 找到 {len(log_files)} 个日志文件\n")

    # 解析日志
    parsed_logs = []
    for log_file in log_files:
        try:
            parser = LogParser()
            parsed_log = parser.parse_log_file(log_file)
            parsed_logs.append(parsed_log)
            print(f"✓ {log_file.name} ({len(parsed_log.turns)} 轮)")
        except Exception as e:
            print(f"⚠ 跳过 {log_file.name}: {e}")

    if not parsed_logs:
        print("\n❌ 没有成功解析任何日志")
        return

    print(f"\n✓ 成功解析 {len(parsed_logs)} 个日志\n")

    # 聚合数据
    model_name = "gpt-5_realtest"
    aggregator = ResultAggregator()
    aggregated = aggregator.aggregate_logs(parsed_logs, model_name)

    # 显示统计
    print("="*80)
    print("真实测试数据统计")
    print("="*80)
    print(f"任务总数: {aggregated.statistics.total_tasks}")
    print(f"总轮数: {aggregated.statistics.total_turns}")
    print(f"平均轮数/任务: {aggregated.statistics.avg_turns_per_task:.1f}")

    if 'score' in aggregated.statistics.score_stats:
        score_stat = aggregated.statistics.score_stats['score']
        print(f"\n整体得分:")
        print(f"  平均值: {score_stat.mean:.3f}")
        print(f"  中位数: {score_stat.median:.3f}")
        print(f"  标准差: {score_stat.std:.3f}")
        print(f"  范围: [{score_stat.min:.3f}, {score_stat.max:.3f}]")

    print(f"\n各维度平均分:")
    for dim, stat in aggregated.statistics.score_stats.items():
        if dim != 'score':
            print(f"  {dim}: {stat.mean:.3f}")

    # 生成图表
    print("\n" + "="*80)
    print("生成图表")
    print("="*80)

    output_dir = "experiment_results/latest_real_test"
    visualizer = ExperimentVisualizer(output_dir)

    results_by_model = {model_name: aggregated}

    try:
        visualizer.plot_radar_chart(results_by_model, output_file="01_radar_chart.png")
        print("✓ 01_radar_chart.png")

        visualizer.plot_bar_chart(results_by_model, dimension="score", output_file="02_bar_chart.png")
        print("✓ 02_bar_chart.png")

        visualizer.plot_turn_progression(results_by_model, output_file="03_turn_progression.png")
        print("✓ 03_turn_progression.png")

        visualizer.plot_lag_analysis(results_by_model, output_file="04_lag_analysis.png")
        print("✓ 04_lag_analysis.png")

        visualizer.plot_error_distribution(results_by_model, output_file="05_error_distribution.png")
        print("✓ 05_error_distribution.png")

        visualizer.plot_comparison_table(results_by_model, output_file="06_comparison_table.png")
        print("✓ 06_comparison_table.png")

        print(f"\n✓ 所有图表已生成到: {output_dir}")

    except Exception as e:
        print(f"\n❌ 生成图表失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    analyze_latest_logs()
