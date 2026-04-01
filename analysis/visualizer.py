"""
M3Bench 可视化器

生成6个关键图表和HTML报告
"""

import logging
import numpy as np
import matplotlib.pyplot as plt
from typing import Dict, List, Optional
from pathlib import Path

try:
    import seaborn as sns
    HAS_SEABORN = True
except ImportError:
    HAS_SEABORN = False

from .data_structures import AggregatedResults

logger = logging.getLogger(__name__)


class ExperimentVisualizer:
    """实验可视化器"""

    def __init__(self, output_dir: str = "experiment_results/visualizations"):
        """初始化可视化器

        Args:
            output_dir: 输出目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 设置绘图样式（论文级）
        self._setup_style()

    def _setup_style(self):
        """设置论文级绘图样式"""
        plt.rcParams['font.family'] = 'serif'
        plt.rcParams['font.size'] = 10
        plt.rcParams['axes.labelsize'] = 11
        plt.rcParams['axes.titlesize'] = 12
        plt.rcParams['xtick.labelsize'] = 9
        plt.rcParams['ytick.labelsize'] = 9
        plt.rcParams['legend.fontsize'] = 9
        plt.rcParams['figure.dpi'] = 300
        plt.rcParams['savefig.dpi'] = 300
        plt.rcParams['axes.grid'] = False  # 无背景网格
        plt.rcParams['axes.spines.left'] = True
        plt.rcParams['axes.spines.bottom'] = True
        plt.rcParams['axes.spines.right'] = False
        plt.rcParams['axes.spines.top'] = False

        # 设置色盲友好配色
        if HAS_SEABORN:
            sns.set_palette("husl")

    def plot_radar_chart(self, results_by_model: Dict[str, AggregatedResults],
                        output_file: str = "01_radar_chart.png") -> str:
        """绘制雷达图 - 多维度能力对比

        Args:
            results_by_model: 模型名称 -> 聚合结果的字典
            output_file: 输出文件名

        Returns:
            输出文件路径
        """
        logger.info("生成雷达图...")

        dimensions = [
            'score', 'faithfulness', 'robustness', 'consistency',
            'memory_retention', 'cross_image_confusion', 'disambiguation'
        ]

        # 简化维度标签（用于图表）
        labels = ['Overall', 'Faithfulness', 'Robustness', 'Consistency',
                 'Memory', 'Image Confusion', 'Disambiguation']

        # 提取每个模型的平均分
        model_scores = {}
        for model_name, results in results_by_model.items():
            scores = []
            for dim in dimensions:
                score = results.statistics.score_stats[dim].mean
                scores.append(score)
            model_scores[model_name] = scores

        # 设置角度
        angles = np.linspace(0, 2 * np.pi, len(dimensions), endpoint=False).tolist()
        angles += angles[:1]  # 闭合圆形

        # 创建图表
        fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(projection='polar'))

        colors = plt.cm.tab10(np.linspace(0, 1, len(model_scores)))

        for idx, (model_name, scores) in enumerate(model_scores.items()):
            scores_plot = scores + scores[:1]  # 闭合
            ax.plot(angles, scores_plot, 'o-', linewidth=2, label=model_name, color=colors[idx])
            ax.fill(angles, scores_plot, alpha=0.15, color=colors[idx])

        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(labels, size=10)
        ax.set_ylim(0, 1)
        ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
        ax.set_yticklabels(['0.2', '0.4', '0.6', '0.8', '1.0'], size=8)
        ax.grid(True, linestyle='--', alpha=0.3)
        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1), fontsize=10)

        plt.tight_layout()
        output_path = self.output_dir / output_file
        plt.savefig(output_path, bbox_inches='tight', dpi=300)
        plt.close()

        logger.info(f"雷达图已保存: {output_path}")
        return str(output_path)

    def plot_bar_chart(self, results_by_model: Dict[str, AggregatedResults],
                      dimension: str = "score", output_file: str = "02_bar_chart.png") -> str:
        """绘制柱状图 - 各模型平均分对比

        Args:
            results_by_model: 模型名称 -> 聚合结果的字典
            dimension: 评分维度
            output_file: 输出文件名

        Returns:
            输出文件路径
        """
        logger.info(f"生成柱状图 ({dimension})...")

        model_names = list(results_by_model.keys())
        scores = [results_by_model[m].statistics.score_stats[dimension].mean for m in model_names]

        fig, ax = plt.subplots(figsize=(10, 6))

        colors = plt.cm.tab10(np.linspace(0, 1, len(model_names)))
        bars = ax.bar(model_names, scores, color=colors, alpha=0.7, edgecolor='black', linewidth=1.5)

        # 添加数值标签
        for bar, score in zip(bars, scores):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{score:.3f}',
                   ha='center', va='bottom', fontsize=10, fontweight='bold')

        ax.set_ylabel(f'{dimension.capitalize()} Score', fontsize=12)
        ax.set_xlabel('Model', fontsize=12)
        ax.set_ylim(0, 1.0)
        ax.set_yticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
        ax.grid(axis='y', linestyle='--', alpha=0.3)

        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        output_path = self.output_dir / output_file
        plt.savefig(output_path, bbox_inches='tight', dpi=300)
        plt.close()

        logger.info(f"柱状图已保存: {output_path}")
        return str(output_path)

    def plot_turn_progression(self, results_by_model: Dict[str, AggregatedResults],
                            dimension: str = "score", output_file: str = "03_turn_progression.png") -> str:
        """绘制折线图 - 分数随turn衰减/增长

        Args:
            results_by_model: 模型名称 -> 聚合结果的字典
            dimension: 评分维度
            output_file: 输出文件名

        Returns:
            输出文件路径
        """
        logger.info(f"生成折线图 ({dimension})...")

        fig, ax = plt.subplots(figsize=(12, 6))

        colors = plt.cm.tab10(np.linspace(0, 1, len(results_by_model)))
        markers = ['o', 's', '^', 'D', 'v', '<', '>', 'p']

        for idx, (model_name, results) in enumerate(results_by_model.items()):
            lag_data = results.lag_analysis
            turn_ids = sorted(lag_data.turn_stats.keys())
            turn_means = [lag_data.turn_stats[tid]['mean'] for tid in turn_ids]

            ax.plot(turn_ids, turn_means, marker=markers[idx % len(markers)],
                   label=model_name, linewidth=2, markersize=6, color=colors[idx])

        ax.set_xlabel('Turn Number', fontsize=12)
        ax.set_ylabel(f'{dimension.capitalize()} Score', fontsize=12)
        ax.set_ylim(0, 1.0)
        ax.set_yticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
        ax.grid(axis='y', linestyle='--', alpha=0.3)
        ax.legend(fontsize=10, loc='best')

        plt.tight_layout()
        output_path = self.output_dir / output_file
        plt.savefig(output_path, bbox_inches='tight', dpi=300)
        plt.close()

        logger.info(f"折线图已保存: {output_path}")
        return str(output_path)

    def plot_lag_analysis(self, results_by_model: Dict[str, AggregatedResults],
                         output_file: str = "04_lag_analysis.png") -> str:
        """绘制Lag分析图 - 分数随turn变化

        Args:
            results_by_model: 模型名称 -> 聚合结果的字典
            output_file: 输出文件名

        Returns:
            输出文件路径
        """
        logger.info("生成Lag分析图...")

        fig, axes = plt.subplots(1, 2, figsize=(14, 5))

        # 左图：趋势
        colors = plt.cm.tab10(np.linspace(0, 1, len(results_by_model)))
        markers = ['o', 's', '^', 'D']

        for idx, (model_name, results) in enumerate(results_by_model.items()):
            lag_data = results.lag_analysis
            turn_ids = sorted(lag_data.turn_stats.keys())
            turn_means = [lag_data.turn_stats[tid]['mean'] for tid in turn_ids]
            turn_stds = [lag_data.turn_stats[tid]['std'] for tid in turn_ids]

            axes[0].plot(turn_ids, turn_means, marker=markers[idx % len(markers)],
                        label=model_name, linewidth=2, color=colors[idx])
            axes[0].fill_between(turn_ids,
                                np.array(turn_means) - np.array(turn_stds),
                                np.array(turn_means) + np.array(turn_stds),
                                alpha=0.2, color=colors[idx])

        axes[0].set_xlabel('Turn Number', fontsize=11)
        axes[0].set_ylabel('Average Score', fontsize=11)
        axes[0].set_ylim(0, 1.0)
        axes[0].grid(axis='y', linestyle='--', alpha=0.3)
        axes[0].legend(fontsize=9)

        # 右图：趋势统计
        models = list(results_by_model.keys())
        trends = [results_by_model[m].lag_analysis.trend for m in models]
        correlations = [results_by_model[m].lag_analysis.correlation for m in models]

        axes[1].barh(models, correlations, color=colors, alpha=0.7, edgecolor='black')
        axes[1].set_xlabel('Correlation with Turn Number', fontsize=11)
        axes[1].set_xlim(-1, 1)
        axes[1].axvline(x=0, color='black', linestyle='-', linewidth=0.8)
        axes[1].grid(axis='x', linestyle='--', alpha=0.3)

        for i, (model, corr) in enumerate(zip(models, correlations)):
            axes[1].text(corr + 0.05 if corr > 0 else corr - 0.05, i,
                        f'{corr:.3f}', va='center',
                        ha='left' if corr > 0 else 'right', fontsize=9)

        plt.tight_layout()
        output_path = self.output_dir / output_file
        plt.savefig(output_path, bbox_inches='tight', dpi=300)
        plt.close()

        logger.info(f"Lag分析图已保存: {output_path}")
        return str(output_path)

    def plot_error_distribution(self, results_by_model: Dict[str, AggregatedResults],
                               output_file: str = "05_error_distribution.png") -> str:
        """绘制错误分布图

        Args:
            results_by_model: 模型名称 -> 聚合结果的字典
            output_file: 输出文件名

        Returns:
            输出文件路径
        """
        logger.info("生成错误分布图...")

        fig, axes = plt.subplots(1, 3, figsize=(16, 4))

        # 第一个模型用于演示
        model_name = list(results_by_model.keys())[0]
        results = results_by_model[model_name]
        error_dist = results.error_distribution

        # 左图：错误类型分布
        if error_dist.error_types:
            error_types = list(error_dist.error_types.keys())
            error_counts = list(error_dist.error_types.values())
            colors = plt.cm.Reds(np.linspace(0.4, 0.8, len(error_types)))
            axes[0].barh(error_types, error_counts, color=colors, edgecolor='black')
            axes[0].set_xlabel('Count', fontsize=11)
            axes[0].set_title('Error Types', fontsize=12)
            for i, count in enumerate(error_counts):
                axes[0].text(count, i, f'{count}', va='center', fontsize=9)

        # 中图：按阶段分布
        if error_dist.error_by_phase:
            phases = list(error_dist.error_by_phase.keys())
            phase_counts = list(error_dist.error_by_phase.values())
            colors = plt.cm.Blues(np.linspace(0.4, 0.8, len(phases)))
            axes[1].barh(phases, phase_counts, color=colors, edgecolor='black')
            axes[1].set_xlabel('Count', fontsize=11)
            axes[1].set_title('Errors by Phase', fontsize=12)
            for i, count in enumerate(phase_counts):
                axes[1].text(count, i, f'{count}', va='center', fontsize=9)

        # 右图：按动作分布
        if error_dist.error_by_action:
            actions = list(error_dist.error_by_action.keys())[:10]  # 最多显示10个
            action_counts = list(error_dist.error_by_action.values())[:10]
            colors = plt.cm.Greens(np.linspace(0.4, 0.8, len(actions)))
            axes[2].barh(actions, action_counts, color=colors, edgecolor='black')
            axes[2].set_xlabel('Count', fontsize=11)
            axes[2].set_title('Errors by Action', fontsize=12)
            for i, count in enumerate(action_counts):
                axes[2].text(count, i, f'{count}', va='center', fontsize=9)

        plt.tight_layout()
        output_path = self.output_dir / output_file
        plt.savefig(output_path, bbox_inches='tight', dpi=300)
        plt.close()

        logger.info(f"错误分布图已保存: {output_path}")
        return str(output_path)

    def plot_comparison_table(self, results_by_model: Dict[str, AggregatedResults],
                             output_file: str = "06_comparison_table.png") -> str:
        """绘制对比表格

        Args:
            results_by_model: 模型名称 -> 聚合结果的字典
            output_file: 输出文件名

        Returns:
            输出文件路径
        """
        logger.info("生成对比表格...")

        dimensions = [
            'score', 'faithfulness', 'robustness', 'consistency',
            'memory_retention', 'cross_image_confusion', 'disambiguation'
        ]

        model_names = list(results_by_model.keys())
        table_data = []

        for dim in dimensions:
            row = [dim.replace('_', ' ').title()]
            for model_name in model_names:
                results = results_by_model[model_name]
                stats = results.statistics.score_stats[dim]
                row.append(f'{stats.mean:.3f}±{stats.std:.3f}')
            table_data.append(row)

        # 创建表格
        fig, ax = plt.subplots(figsize=(12, 5))
        ax.axis('tight')
        ax.axis('off')

        columns = ['Dimension'] + model_names
        table = ax.table(cellText=table_data, colLabels=columns,
                        cellLoc='center', loc='center',
                        colWidths=[0.2] + [0.2] * len(model_names))

        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1, 2)

        # 设置表头样式
        for i in range(len(columns)):
            table[(0, i)].set_facecolor('#4CAF50')
            table[(0, i)].set_text_props(weight='bold', color='white')

        # 交替行颜色
        for i in range(1, len(table_data) + 1):
            for j in range(len(columns)):
                if i % 2 == 0:
                    table[(i, j)].set_facecolor('#f0f0f0')
                else:
                    table[(i, j)].set_facecolor('#ffffff')

        plt.tight_layout()
        output_path = self.output_dir / output_file
        plt.savefig(output_path, bbox_inches='tight', dpi=300)
        plt.close()

        logger.info(f"对比表格已保存: {output_path}")
        return str(output_path)

    def generate_all_visualizations(self, results_by_model: Dict[str, AggregatedResults],
                                   output_dir: Optional[str] = None) -> Dict[str, str]:
        """生成所有可视化

        Args:
            results_by_model: 模型名称 -> 聚合结果的字典
            output_dir: 输出目录（可选）

        Returns:
            图表名称 -> 文件路径的字典
        """
        if output_dir:
            self.output_dir = Path(output_dir)
            self.output_dir.mkdir(parents=True, exist_ok=True)

        outputs = {
            'radar_chart': self.plot_radar_chart(results_by_model),
            'bar_chart': self.plot_bar_chart(results_by_model),
            'turn_progression': self.plot_turn_progression(results_by_model),
            'lag_analysis': self.plot_lag_analysis(results_by_model),
            'error_distribution': self.plot_error_distribution(results_by_model),
            'comparison_table': self.plot_comparison_table(results_by_model)
        }

        logger.info(f"所有可视化已生成，保存在: {self.output_dir}")
        return outputs


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(__file__).rsplit('/', 1)[0])
    from log_parser import parse_log_directory
    from result_aggregator import ResultAggregator

    logging.basicConfig(level=logging.INFO)

    # 测试
    log_dir = "E:/Code/M3Bench/M3Bench_new/simulator_test_log/batch_run_20260205_104458"
    logs = parse_log_directory(log_dir)

    aggregator = ResultAggregator()
    results = aggregator.aggregate_logs(logs, "GPT-4")

    visualizer = ExperimentVisualizer(output_dir="experiment_results/visualizations")
    outputs = visualizer.generate_all_visualizations(
        {'GPT-4': results},
        output_dir="experiment_results/visualizations"
    )

    print("\n生成的可视化文件:")
    for name, path in outputs.items():
        print(f"  {name}: {path}")
