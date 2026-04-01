"""
M3Bench 实验分析主入口脚本

用法:
    python run_analysis.py --log-dir simulator_test_log/batch_run_20260205_104458 --model-name "Test Model"
"""

import argparse
import logging
import json
from pathlib import Path
from datetime import datetime

from analysis import (
    parse_log_directory,
    ResultAggregator,
    ExperimentVisualizer
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description='M3Bench 实验分析工具',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--log-dir',
        type=str,
        required=True,
        help='日志目录路径'
    )
    parser.add_argument(
        '--model-name',
        type=str,
        default='Unknown Model',
        help='模型名称'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default=None,
        help='输出目录（默认: experiment_results/{timestamp}）'
    )
    parser.add_argument(
        '--dimension',
        type=str,
        default='score',
        choices=['score', 'faithfulness', 'robustness', 'consistency',
                'memory_retention', 'cross_image_confusion', 'disambiguation'],
        help='主要评分维度'
    )

    args = parser.parse_args()

    # 设置输出目录
    if args.output_dir is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_dir = Path(f'experiment_results/{timestamp}')
    else:
        output_dir = Path(args.output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("="*80)
    logger.info("M3Bench 实验分析工具")
    logger.info("="*80)
    logger.info(f"日志目录: {args.log_dir}")
    logger.info(f"模型名称: {args.model_name}")
    logger.info(f"输出目录: {output_dir}")
    logger.info("")

    # Step 1: 解析日志
    logger.info("Step 1: 解析日志文件...")
    parsed_logs = parse_log_directory(args.log_dir)
    if not parsed_logs:
        logger.error("没有成功解析任何日志文件！")
        return 1

    logger.info(f"成功解析 {len(parsed_logs)} 个日志文件")

    # Step 2: 聚合结果
    logger.info("\nStep 2: 聚合结果...")
    aggregator = ResultAggregator()
    results = aggregator.aggregate_logs(parsed_logs, args.model_name)

    # 保存聚合结果
    results_path = output_dir / 'aggregated_results.json'
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump(results.to_dict(), f, indent=2, ensure_ascii=False)
    logger.info(f"聚合结果已保存: {results_path}")

    # 打印统计摘要
    stats = results.statistics
    logger.info("\n统计摘要:")
    logger.info(f"  总任务数: {stats.total_tasks}")
    logger.info(f"  总Turn数: {stats.total_turns}")
    logger.info(f"  平均Turn/任务: {stats.avg_turns_per_task:.1f}")
    logger.info(f"  总体评分: {stats.score_stats['score'].mean:.3f} ± {stats.score_stats['score'].std:.3f}")
    logger.info(f"  Lag趋势: {results.lag_analysis.trend}")
    logger.info(f"  低分Turn数: {len(results.error_distribution.low_score_turns)}")

    # Step 3: 生成可视化
    logger.info("\nStep 3: 生成可视化...")
    visualizer = ExperimentVisualizer(output_dir=str(output_dir / 'visualizations'))

    outputs = visualizer.generate_all_visualizations(
        {args.model_name: results},
        output_dir=str(output_dir / 'visualizations')
    )

    logger.info("\n生成的可视化文件:")
    for name, path in outputs.items():
        logger.info(f"  {name}: {path}")

    # 生成文本报告
    report_path = output_dir / 'analysis_report.txt'
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("="*80 + "\n")
        f.write(f"M3Bench 实验分析报告\n")
        f.write("="*80 + "\n\n")
        f.write(f"模型名称: {args.model_name}\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        f.write("统计摘要\n")
        f.write("-"*40 + "\n")
        f.write(f"总任务数: {stats.total_tasks}\n")
        f.write(f"总Turn数: {stats.total_turns}\n")
        f.write(f"总Filler Turn数: {stats.total_filler_turns}\n")
        f.write(f"平均Turn/任务: {stats.avg_turns_per_task:.1f}\n")
        f.write(f"平均Filler Turn/任务: {stats.avg_filler_turns_per_task:.1f}\n\n")

        f.write("各维度评分\n")
        f.write("-"*40 + "\n")
        for dim in ['score', 'faithfulness', 'robustness', 'consistency',
                   'memory_retention', 'cross_image_confusion', 'disambiguation']:
            dim_stats = stats.score_stats[dim]
            f.write(f"{dim.ljust(25)}: {dim_stats.mean:.3f} ± {dim_stats.std:.3f}\n")

        f.write("\n阶段分布\n")
        f.write("-"*40 + "\n")
        for phase, count in sorted(stats.phase_distribution.items(), key=lambda x: -x[1]):
            f.write(f"{phase.ljust(25)}: {count}\n")

        f.write("\nLag分析\n")
        f.write("-"*40 + "\n")
        f.write(f"趋势: {results.lag_analysis.trend}\n")
        f.write(f"相关系数: {results.lag_analysis.correlation:.3f}\n")

    logger.info(f"\n文本报告已保存: {report_path}")

    logger.info("\n" + "="*80)
    logger.info("分析完成！")
    logger.info("="*80)

    return 0


if __name__ == "__main__":
    exit(main())
