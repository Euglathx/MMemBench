"""
M3Bench Analysis Module
"""

from .log_parser import LogParser, parse_log_directory
from .result_aggregator import ResultAggregator
try:
    from .visualizer import ExperimentVisualizer
    VISUALIZER_IMPORT_ERROR = None
except Exception as exc:
    ExperimentVisualizer = None
    VISUALIZER_IMPORT_ERROR = exc
from .data_structures import (
    ParsedLog,
    TaskMetadata,
    TurnRecord,
    ScoreRecord,
    FillerTurnRecord,
    ConsistencyCheckRecord,
    AggregatedResults,
    StatisticsRecord,
    ScoreStats,
    ScoresAnalysis,
    LagAnalysis,
    ErrorDistribution,
    TaskAnalysis,
    ModelResults
)

__all__ = [
    'LogParser',
    'parse_log_directory',
    'ResultAggregator',
    'ExperimentVisualizer',
    'ParsedLog',
    'TaskMetadata',
    'TurnRecord',
    'ScoreRecord',
    'FillerTurnRecord',
    'ConsistencyCheckRecord',
    'AggregatedResults',
    'StatisticsRecord',
    'ScoreStats',
    'ScoresAnalysis',
    'LagAnalysis',
    'ErrorDistribution',
    'TaskAnalysis',
    'ModelResults',
    'VISUALIZER_IMPORT_ERROR',
]
