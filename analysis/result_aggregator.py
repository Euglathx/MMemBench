"""
M3Bench 结果聚合器

从ParsedLog对象聚合统计数据
"""

import logging
import numpy as np
from typing import List, Dict, Any, Optional
from collections import defaultdict

from .data_structures import (
    ParsedLog,
    AggregatedResults,
    StatisticsRecord,
    ScoreStats,
    ScoresAnalysis,
    LagAnalysis,
    ErrorDistribution,
    TaskAnalysis
)

logger = logging.getLogger(__name__)


class ResultAggregator:
    """结果聚合器"""

    OFFICIAL_DIMENSIONS = [
        'score',
        'faithfulness',
        'robustness',
        'consistency',
        'memory_retention',
        'cross_image_confusion',
        'disambiguation',
    ]

    def aggregate_logs(self, parsed_logs: List[ParsedLog], model_name: str) -> AggregatedResults:
        """聚合多个日志文件

        Args:
            parsed_logs: ParsedLog对象列表
            model_name: 模型名称

        Returns:
            AggregatedResults对象
        """
        logger.info(f"聚合 {len(parsed_logs)} 个日志 (模型: {model_name})")

        # 计算基础统计
        statistics = self.compute_statistics(parsed_logs)

        # 计算分数分析
        scores = self.compute_scores_analysis(parsed_logs)

        # 计算Lag分析
        lag_analysis = self.compute_lag_analysis(parsed_logs)

        # 计算错误分布
        error_distribution = self.compute_error_distribution(parsed_logs)

        # 计算任务分析
        task_details = self.compute_task_analysis(parsed_logs)

        # 构建元数据
        metadata = {
            'model': model_name,
            'log_count': len(parsed_logs),
            'total_tasks': statistics.total_tasks,
            'total_turns': statistics.total_turns,
            'total_filler_turns': statistics.total_filler_turns
        }

        return AggregatedResults(
            metadata=metadata,
            statistics=statistics,
            scores=scores,
            lag_analysis=lag_analysis,
            error_distribution=error_distribution,
            task_details=task_details
        )

    def compute_statistics(self, parsed_logs: List[ParsedLog]) -> StatisticsRecord:
        """计算统计数据"""
        total_tasks = len(parsed_logs)
        total_turns = sum(log.total_turns for log in parsed_logs)
        total_filler_turns = sum(log.total_filler_turns for log in parsed_logs)

        avg_turns_per_task = total_turns / total_tasks if total_tasks > 0 else 0
        avg_filler_turns_per_task = total_filler_turns / total_tasks if total_tasks > 0 else 0

        # 计算各维度的统计
        score_stats = {}
        dimensions = self.OFFICIAL_DIMENSIONS

        for dim in dimensions:
            scores = self._extract_scores_by_dimension(parsed_logs, dim)
            if scores:
                score_stats[dim] = self._compute_score_stats(scores)

        # 阶段分布
        phase_distribution = defaultdict(int)
        for log in parsed_logs:
            for turn in log.turns:
                phase_distribution[turn.phase] += 1

        # 动作分布
        action_distribution = defaultdict(int)
        for log in parsed_logs:
            for turn in log.turns:
                action_distribution[turn.action] += 1

        # 难度进展
        difficulty_progression = []
        for log in parsed_logs:
            if log.turns:
                avg_difficulty = np.mean([turn.difficulty for turn in log.turns])
                difficulty_progression.append(avg_difficulty)

        return StatisticsRecord(
            total_tasks=total_tasks,
            total_turns=total_turns,
            total_filler_turns=total_filler_turns,
            avg_turns_per_task=avg_turns_per_task,
            avg_filler_turns_per_task=avg_filler_turns_per_task,
            score_stats=score_stats,
            phase_distribution=dict(phase_distribution),
            action_distribution=dict(action_distribution),
            difficulty_progression=difficulty_progression
        )

    def compute_scores_analysis(self, parsed_logs: List[ParsedLog]) -> ScoresAnalysis:
        """计算分数分析"""
        dimensions = self.OFFICIAL_DIMENSIONS

        # 按维度分析
        by_dimension = {}
        for dim in dimensions:
            dim_data = {
                'mean': 0,
                'std': 0,
                'support': 0,
                'by_task_type': {},
                'by_dataset': {}
            }

            # 所有分数
            all_scores = self._extract_scores_by_dimension(parsed_logs, dim)
            dim_data['support'] = len(all_scores)
            if all_scores:
                dim_data['mean'] = float(np.mean(all_scores))
                dim_data['std'] = float(np.std(all_scores))

            # 按任务类型
            for log in parsed_logs:
                task_type = log.task_metadata.task_type
                if task_type not in dim_data['by_task_type']:
                    dim_data['by_task_type'][task_type] = []

                for turn in log.turns:
                    score = self._get_score_by_dimension(turn, dim)
                    if score is not None:
                        dim_data['by_task_type'][task_type].append(score)

            # 计算任务类型平均分
            dim_data['by_task_type'] = {
                k: {
                    'score': float(np.mean(v)) if v else 0,
                    'support': len(v)
                }
                for k, v in dim_data['by_task_type'].items()
            }

            # 按数据集
            for log in parsed_logs:
                dataset = log.task_metadata.dataset
                if dataset not in dim_data['by_dataset']:
                    dim_data['by_dataset'][dataset] = []

                for turn in log.turns:
                    score = self._get_score_by_dimension(turn, dim)
                    if score is not None:
                        dim_data['by_dataset'][dataset].append(score)

            # 计算数据集平均分
            dim_data['by_dataset'] = {
                k: {
                    'score': float(np.mean(v)) if v else 0,
                    'support': len(v)
                }
                for k, v in dim_data['by_dataset'].items()
            }

            by_dimension[dim] = dim_data

        # 按任务类型分析
        by_task_type = defaultdict(dict)
        for log in parsed_logs:
            task_type = log.task_metadata.task_type
            for turn in log.turns:
                for dim in dimensions:
                    if dim not in by_task_type[task_type]:
                        by_task_type[task_type][dim] = []
                    score = self._get_score_by_dimension(turn, dim)
                    if score is not None:
                        by_task_type[task_type][dim].append(score)

        by_task_type = {
            k: {
                dim: {
                    'score': float(np.mean(v)) if v else 0,
                    'support': len(v)
                }
                for dim, v in v_dict.items()
            }
            for k, v_dict in by_task_type.items()
        }

        # 按数据集分析
        by_dataset = defaultdict(dict)
        for log in parsed_logs:
            dataset = log.task_metadata.dataset
            for turn in log.turns:
                for dim in dimensions:
                    if dim not in by_dataset[dataset]:
                        by_dataset[dataset][dim] = []
                    score = self._get_score_by_dimension(turn, dim)
                    if score is not None:
                        by_dataset[dataset][dim].append(score)

        by_dataset = {
            k: {
                dim: {
                    'score': float(np.mean(v)) if v else 0,
                    'support': len(v)
                }
                for dim, v in v_dict.items()
            }
            for k, v_dict in by_dataset.items()
        }

        return ScoresAnalysis(
            by_dimension=by_dimension,
            by_task_type=by_task_type,
            by_dataset=by_dataset
        )

    def compute_lag_analysis(self, parsed_logs: List[ParsedLog]) -> LagAnalysis:
        """计算Lag分析"""
        turn_scores = defaultdict(list)
        all_turns = []
        all_scores = []

        for log in parsed_logs:
            for turn in log.turns:
                turn_scores[turn.turn_id].append(turn.scores.score)
                all_turns.append(turn.turn_id)
                all_scores.append(turn.scores.score)

        # 计算统计
        turn_stats = {}
        for turn_id in sorted(turn_scores.keys()):
            scores = turn_scores[turn_id]
            turn_stats[turn_id] = {
                'mean': float(np.mean(scores)),
                'std': float(np.std(scores)),
                'count': len(scores)
            }

        # 计算趋势
        turn_ids = sorted(turn_scores.keys())
        turn_means = [turn_stats[tid]['mean'] for tid in turn_ids]

        if len(turn_means) > 1:
            # 计算相关系数
            correlation = float(np.corrcoef(turn_ids, turn_means)[0, 1])

            # 计算趋势
            if np.isnan(correlation):
                trend = 'stable'
            elif correlation > 0.05:
                trend = 'improving'
            elif correlation < -0.05:
                trend = 'declining'
            else:
                trend = 'stable'

            # 计算趋势线
            z = np.polyfit(turn_ids, turn_means, 1)
            trend_line = {
                'slope': float(z[0]),
                'intercept': float(z[1]),
                'r_squared': float(np.corrcoef(turn_ids, turn_means)[0, 1] ** 2)
            }
        else:
            correlation = 0.0
            trend = 'stable'
            trend_line = None

        return LagAnalysis(
            turn_scores={int(k): v for k, v in turn_scores.items()},
            turn_stats={int(k): v for k, v in turn_stats.items()},
            trend=trend,
            correlation=correlation,
            trend_line=trend_line
        )

    def compute_error_distribution(self, parsed_logs: List[ParsedLog]) -> ErrorDistribution:
        """计算错误分布"""
        low_score_turns = []
        error_types = defaultdict(int)
        error_by_phase = defaultdict(int)
        error_by_action = defaultdict(int)
        error_by_difficulty = defaultdict(int)

        for log in parsed_logs:
            for turn in log.turns:
                if turn.scores.score is not None and turn.scores.score < 0.3:  # 低分阈值
                    low_score_turns.append({
                        'task_id': log.task_metadata.task_id,
                        'turn': turn.turn_id,
                        'score': turn.scores.score,
                        'phase': turn.phase,
                        'action': turn.action,
                        'difficulty': turn.difficulty
                    })

                    # 分类错误
                    if turn.scores.score < 0.1:
                        error_types['critical_failure'] += 1
                    elif turn.scores.score < 0.3:
                        error_types['significant_error'] += 1

                    error_by_phase[turn.phase] += 1
                    error_by_action[turn.action] += 1
                    error_by_difficulty[turn.difficulty] += 1

        return ErrorDistribution(
            low_score_turns=low_score_turns[:100],  # 最多保存100条
            error_types=dict(error_types),
            error_by_phase=dict(error_by_phase),
            error_by_action=dict(error_by_action),
            error_by_difficulty=dict(error_by_difficulty)
        )

    def compute_task_analysis(self, parsed_logs: List[ParsedLog]) -> List[TaskAnalysis]:
        """计算任务分析"""
        task_analyses = []

        for log in parsed_logs:
            # 分数进展
            score_progression = [turn.scores.score for turn in log.turns if turn.scores.score is not None]

            # 各阶段平均分
            phase_scores = defaultdict(list)
            for turn in log.turns:
                if turn.scores.score is not None:
                    phase_scores[turn.phase].append(turn.scores.score)

            phase_scores = {
                k: float(np.mean(v)) if v else 0
                for k, v in phase_scores.items()
            }

            # 各动作平均分
            action_scores = defaultdict(list)
            for turn in log.turns:
                if turn.scores.score is not None:
                    action_scores[turn.action].append(turn.scores.score)

            action_scores = {
                k: float(np.mean(v)) if v else 0
                for k, v in action_scores.items()
            }

            # 最终分数
            final_score = score_progression[-1] if score_progression else 0.0

            task_analysis = TaskAnalysis(
                task_id=log.task_metadata.task_id,
                task_type=log.task_metadata.task_type,
                dataset=log.task_metadata.dataset,
                question=log.task_metadata.question,
                expected_answer=log.task_metadata.expected_answer,
                total_turns=log.total_turns,
                total_filler_turns=log.total_filler_turns,
                final_score=final_score,
                score_progression=score_progression,
                phase_scores=phase_scores,
                action_scores=action_scores
            )
            task_analyses.append(task_analysis)

        return task_analyses

    def _compute_score_stats(self, scores: List[float]) -> ScoreStats:
        """计算单个维度的统计"""
        scores_array = np.array(scores)
        return ScoreStats(
            mean=float(np.mean(scores_array)),
            median=float(np.median(scores_array)),
            std=float(np.std(scores_array)),
            min=float(np.min(scores_array)),
            max=float(np.max(scores_array)),
            q25=float(np.percentile(scores_array, 25)),
            q75=float(np.percentile(scores_array, 75)),
            count=len(scores)
        )

    def _extract_scores_by_dimension(self, parsed_logs: List[ParsedLog], dimension: str) -> List[float]:
        """提取特定维度的所有正式分数"""
        scores = []
        for log in parsed_logs:
            for turn in log.turns:
                score = self._get_score_by_dimension(turn, dimension)
                if score is not None:
                    scores.append(score)
        return scores

    def _get_score_by_dimension(self, turn, dimension: str) -> Optional[float]:
        """获取turn中特定维度的正式分数"""
        if dimension == 'score':
            return turn.scores.score

        dimension_map = {
            'faithfulness': 'faithfulness',
            'robustness': 'robustness',
            'consistency': 'consistency',
            'memory_retention': 'memory_retention',
            'cross_image_confusion': 'cross_image_disambiguation',
            'disambiguation': 'ambiguity_recognition',
        }

        report_key = dimension_map.get(dimension)
        if report_key:
            report = (turn.scores.dimension_reports or {}).get(report_key, {})
            if isinstance(report, dict):
                return report.get('score')

        if dimension == 'faithfulness':
            return turn.scores.faithfulness
        elif dimension == 'robustness':
            return turn.scores.robustness
        elif dimension == 'consistency':
            return turn.scores.consistency
        elif dimension == 'memory_retention':
            return turn.scores.memory_retention
        elif dimension == 'cross_image_confusion':
            return turn.scores.cross_image_confusion
        elif dimension == 'disambiguation':
            return turn.scores.disambiguation
        return None


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(__file__).rsplit('/', 1)[0])
    from log_parser import parse_log_directory

    logging.basicConfig(level=logging.INFO)

    # 测试
    log_dir = "E:/Code/M3Bench/M3Bench_new/simulator_test_log/batch_run_20260205_104458"
    logs = parse_log_directory(log_dir)

    aggregator = ResultAggregator()
    results = aggregator.aggregate_logs(logs, "test_model")

    print(f"\n聚合结果:")
    print(f"总任务: {results.statistics.total_tasks}")
    print(f"总Turn: {results.statistics.total_turns}")
    print(f"总体分数: {results.statistics.score_stats['score'].mean:.3f} ± {results.statistics.score_stats['score'].std:.3f}")
    print(f"Lag趋势: {results.lag_analysis.trend}")
    print(f"错误Turn数: {len(results.error_distribution.low_score_turns)}")
