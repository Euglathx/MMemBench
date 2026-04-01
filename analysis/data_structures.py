"""
M3Bench 分析模块数据结构定义

包含日志解析、结果聚合、可视化所需的数据类型
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime


@dataclass
class ScoreRecord:
    """单轮评分记录"""
    score: Optional[float]
    faithfulness: Optional[float]
    robustness: Optional[float]
    consistency: Optional[float]
    memory_retention: Optional[float]
    cross_image_confusion: Optional[float]
    disambiguation: Optional[float]
    level_passed: bool
    reasoning: str = ""
    dimension_reports: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    official_overall_score: Optional[float] = None
    evaluation_validity: str = "valid"
    image_delivery_status: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'score': self.score,
            'faithfulness': self.faithfulness,
            'robustness': self.robustness,
            'consistency': self.consistency,
            'memory_retention': self.memory_retention,
            'cross_image_confusion': self.cross_image_confusion,
            'disambiguation': self.disambiguation,
            'level_passed': self.level_passed,
            'reasoning': self.reasoning,
            'dimension_reports': self.dimension_reports,
            'official_overall_score': self.official_overall_score,
            'evaluation_validity': self.evaluation_validity,
            'image_delivery_status': self.image_delivery_status,
        }

    def get_all_scores(self) -> Dict[str, Optional[float]]:
        """获取所有评分维度"""
        return {
            'score': self.score,
            'faithfulness': self.faithfulness,
            'robustness': self.robustness,
            'consistency': self.consistency,
            'memory_retention': self.memory_retention,
            'cross_image_confusion': self.cross_image_confusion,
            'disambiguation': self.disambiguation
        }


@dataclass
class TurnRecord:
    """单个turn的完整记录"""
    turn_id: int
    phase: str
    difficulty: int
    action: str
    message: str
    response: str
    images_sent: List[str]
    scores: ScoreRecord
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'turn_id': self.turn_id,
            'phase': self.phase,
            'difficulty': self.difficulty,
            'action': self.action,
            'message': self.message,
            'response': self.response,
            'images_sent': self.images_sent,
            'scores': self.scores.to_dict(),
            'timestamp': self.timestamp
        }


@dataclass
class FillerTurnRecord:
    """干扰turn的记录"""
    filler_index: int
    user_message: str
    model_response: str
    topic: str
    response_length: int
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'filler_index': self.filler_index,
            'user_message': self.user_message,
            'model_response': self.model_response,
            'topic': self.topic,
            'response_length': self.response_length,
            'timestamp': self.timestamp
        }


@dataclass
class TaskMetadata:
    """任务元数据"""
    task_id: str
    task_type: str
    question: str
    expected_answer: str
    images: List[str]
    dataset: str
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'task_id': self.task_id,
            'task_type': self.task_type,
            'question': self.question,
            'expected_answer': self.expected_answer,
            'images': self.images,
            'dataset': self.dataset,
            'timestamp': self.timestamp
        }


@dataclass
class ConsistencyCheckRecord:
    """一致性检查记录"""
    question: str
    response: str
    score: float
    expected: str
    grounded_in_truth: bool
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'question': self.question,
            'response': self.response,
            'score': self.score,
            'expected': self.expected,
            'grounded_in_truth': self.grounded_in_truth,
            'timestamp': self.timestamp
        }


@dataclass
class ParsedLog:
    """解析后的完整日志"""
    task_metadata: TaskMetadata
    turns: List[TurnRecord]
    filler_turns: List[FillerTurnRecord]
    consistency_check: Optional[ConsistencyCheckRecord]
    total_turns: int
    total_filler_turns: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            'task_metadata': self.task_metadata.to_dict(),
            'turns': [t.to_dict() for t in self.turns],
            'filler_turns': [f.to_dict() for f in self.filler_turns],
            'consistency_check': self.consistency_check.to_dict() if self.consistency_check else None,
            'total_turns': self.total_turns,
            'total_filler_turns': self.total_filler_turns
        }


@dataclass
class ScoreStats:
    """单个维度的统计"""
    mean: float
    median: float
    std: float
    min: float
    max: float
    q25: float
    q75: float
    count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            'mean': self.mean,
            'median': self.median,
            'std': self.std,
            'min': self.min,
            'max': self.max,
            'q25': self.q25,
            'q75': self.q75,
            'count': self.count
        }


@dataclass
class StatisticsRecord:
    """统计数据"""
    total_tasks: int
    total_turns: int
    total_filler_turns: int
    avg_turns_per_task: float
    avg_filler_turns_per_task: float
    score_stats: Dict[str, ScoreStats]
    phase_distribution: Dict[str, int]
    action_distribution: Dict[str, int]
    difficulty_progression: List[float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_tasks': self.total_tasks,
            'total_turns': self.total_turns,
            'total_filler_turns': self.total_filler_turns,
            'avg_turns_per_task': self.avg_turns_per_task,
            'avg_filler_turns_per_task': self.avg_filler_turns_per_task,
            'score_stats': {k: v.to_dict() for k, v in self.score_stats.items()},
            'phase_distribution': self.phase_distribution,
            'action_distribution': self.action_distribution,
            'difficulty_progression': self.difficulty_progression
        }


@dataclass
class LagAnalysis:
    """Lag分析结果"""
    turn_scores: Dict[int, List[float]]
    turn_stats: Dict[int, Dict[str, float]]
    trend: str
    correlation: float
    trend_line: Optional[Dict[str, float]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'turn_scores': {str(k): v for k, v in self.turn_scores.items()},
            'turn_stats': {str(k): v for k, v in self.turn_stats.items()},
            'trend': self.trend,
            'correlation': self.correlation,
            'trend_line': self.trend_line
        }


@dataclass
class ErrorDistribution:
    """错误分布分析"""
    low_score_turns: List[Dict[str, Any]]
    error_types: Dict[str, int]
    error_by_phase: Dict[str, int]
    error_by_action: Dict[str, int]
    error_by_difficulty: Dict[int, int]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'low_score_turns': self.low_score_turns,
            'error_types': self.error_types,
            'error_by_phase': self.error_by_phase,
            'error_by_action': self.error_by_action,
            'error_by_difficulty': {str(k): v for k, v in self.error_by_difficulty.items()}
        }


@dataclass
class TaskAnalysis:
    """单个任务的分析结果"""
    task_id: str
    task_type: str
    dataset: str
    question: str
    expected_answer: str
    total_turns: int
    total_filler_turns: int
    final_score: float
    score_progression: List[float]
    phase_scores: Dict[str, float]
    action_scores: Dict[str, float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'task_id': self.task_id,
            'task_type': self.task_type,
            'dataset': self.dataset,
            'question': self.question,
            'expected_answer': self.expected_answer,
            'total_turns': self.total_turns,
            'total_filler_turns': self.total_filler_turns,
            'final_score': self.final_score,
            'score_progression': self.score_progression,
            'phase_scores': self.phase_scores,
            'action_scores': self.action_scores
        }


@dataclass
class ScoresAnalysis:
    """分数分析"""
    by_dimension: Dict[str, Dict[str, Any]]
    by_task_type: Dict[str, Dict[str, Any]]
    by_dataset: Dict[str, Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'by_dimension': self.by_dimension,
            'by_task_type': self.by_task_type,
            'by_dataset': self.by_dataset
        }


@dataclass
class AggregatedResults:
    """完整的聚合结果"""
    metadata: Dict[str, Any]
    statistics: StatisticsRecord
    scores: ScoresAnalysis
    lag_analysis: LagAnalysis
    error_distribution: ErrorDistribution
    task_details: List[TaskAnalysis]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'metadata': self.metadata,
            'statistics': self.statistics.to_dict(),
            'scores': self.scores.to_dict(),
            'lag_analysis': self.lag_analysis.to_dict(),
            'error_distribution': self.error_distribution.to_dict(),
            'task_details': [t.to_dict() for t in self.task_details]
        }


@dataclass
class ModelResults:
    """单个模型的所有结果"""
    model_name: str
    aggregated_results: AggregatedResults
    log_count: int
    processing_time: float
    errors: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
