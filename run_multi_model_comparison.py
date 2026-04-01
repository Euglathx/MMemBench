"""
多模型对比可视化脚本

读取多个模型的聚合结果，生成对比图表
"""

import sys
import json
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from analysis import ExperimentVisualizer
from analysis.data_structures import AggregatedResults

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_aggregated_results(results_files):
    """加载多个模型的聚合结果

    Args:
        results_files: {model_name: json_file_path} 字典

    Returns:
        {model_name: AggregatedResults} 字典
    """
    results = {}

    for model_name, json_path in results_files.items():
        logger.info(f"加载 {model_name} 的结果: {json_path}")

        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 转换为AggregatedResults对象（简化版）
        # 注意：这里使用已保存的JSON数据，直接作为dict传递给visualizer
        results[model_name] = data

    return results


def dict_to_aggregated_results(data_dict):
    """将字典转换为AggregatedResults对象（简化版）"""
    from analysis.data_structures import (
        StatisticsRecord, ScoreStats, ScoresAnalysis,
        LagAnalysis, ErrorDistribution, TaskAnalysis
    )

    # 转换score_stats
    score_stats = {}
    for dim, stats in data_dict['statistics']['score_stats'].items():
        score_stats[dim] = ScoreStats(**stats)

    statistics = StatisticsRecord(
        total_tasks=data_dict['statistics']['total_tasks'],
        total_turns=data_dict['statistics']['total_turns'],
        total_filler_turns=data_dict['statistics']['total_filler_turns'],
        avg_turns_per_task=data_dict['statistics']['avg_turns_per_task'],
        avg_filler_turns_per_task=data_dict['statistics']['avg_filler_turns_per_task'],
        score_stats=score_stats,
        phase_distribution=data_dict['statistics']['phase_distribution'],
        action_distribution=data_dict['statistics']['action_distribution'],
        difficulty_progression=data_dict['statistics']['difficulty_progression']
    )

    scores = ScoresAnalysis(**data_dict['scores'])
    lag_analysis = LagAnalysis(**data_dict['lag_analysis'])
    error_distribution = ErrorDistribution(**data_dict['error_distribution'])
    task_details = [TaskAnalysis(**t) for t in data_dict['task_details']]

    return AggregatedResults(
        metadata=data_dict['metadata'],
        statistics=statistics,
        scores=scores,
        lag_analysis=lag_analysis,
        error_distribution=error_distribution,
        task_details=task_details
    )


def main():
    logger.info("="*80)
    logger.info("多模型对比可视化")
    logger.info("="*80 + "\n")

    # 定义模型结果文件路径
    # 运行所有模型的分析后更新这些路径
    models_to_analyze = [
        ('gpt-5', 'simulator_test_log/mock_gpt-5_20260205_171357'),
        ('gemini-2.5-pro', 'simulator_test_log/mock_gemini-2.5-pro_20260205_171357'),
        ('gemini-2.5-flash', 'simulator_test_log/mock_gemini-2.5-flash_20260205_171357'),
        ('kimi-k2.5', 'simulator_test_log/mock_kimi-k2.5_20260205_171357')
    ]

    # 先为每个模型运行分析（如果还没运行）
    logger.info("步骤1: 为每个模型运行分析...")

    from run_analysis import main as run_analysis
    import argparse

    results_by_model = {}

    for model_name, log_dir in models_to_analyze:
        output_dir = f"experiment_results/models/{model_name}"
        logger.info(f"\n分析 {model_name}...")

        # 模拟命令行参数
        sys.argv = [
            'run_analysis.py',
            '--log-dir', log_dir,
            '--model-name', model_name,
            '--output-dir', output_dir
        ]

        try:
            run_analysis()

            # 加载结果
            result_file = Path(output_dir) / 'aggregated_results.json'
            if result_file.exists():
                with open(result_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                results_by_model[model_name] = dict_to_aggregated_results(data)
                logger.info(f"✓ {model_name} 分析完成")
            else:
                logger.warning(f"✗ {model_name} 结果文件不存在")
        except Exception as e:
            logger.error(f"✗ {model_name} 分析失败: {e}")

    if not results_by_model:
        logger.error("没有成功加载任何模型结果！")
        return 1

    # 步骤2: 生成对比可视化
    logger.info("\n步骤2: 生成对比可视化...")
    output_dir = "experiment_results/multi_model_comparison"
    visualizer = ExperimentVisualizer(output_dir=output_dir)

    outputs = visualizer.generate_all_visualizations(
        results_by_model,
        output_dir=output_dir
    )

    logger.info("\n" + "="*80)
    logger.info("多模型对比可视化完成!")
    logger.info("="*80 + "\n")

    logger.info("生成的对比图表:")
    for name, path in outputs.items():
        logger.info(f"  {name}: {path}")

    logger.info(f"\n所有图表已保存到: {output_dir}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
