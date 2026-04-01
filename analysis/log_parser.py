"""
M3Bench 日志解析器

从JSON格式的日志文件中提取结构化数据
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any

from .data_structures import (
    ParsedLog,
    TaskMetadata,
    TurnRecord,
    ScoreRecord,
    FillerTurnRecord,
    ConsistencyCheckRecord
)

logger = logging.getLogger(__name__)


class LogParser:
    """日志解析器"""

    def __init__(self):
        self.errors = []

    def parse_log_file(self, log_path: str) -> Optional[ParsedLog]:
        """解析单个日志文件

        Args:
            log_path: 日志文件路径

        Returns:
            ParsedLog对象，解析失败返回None
        """
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                events = json.load(f)

            if not isinstance(events, list):
                logger.error(f"日志格式错误: {log_path} - 期望数组")
                self.errors.append(f"日志格式错误: {log_path}")
                return None

            # 提取各部分数据
            task_metadata = self.extract_task_metadata(events)
            if not task_metadata:
                logger.error(f"无法提取任务元数据: {log_path}")
                self.errors.append(f"无法提取任务元数据: {log_path}")
                return None

            turns = self.extract_turns(events)
            filler_turns = self.extract_filler_turns(events)
            consistency_check = self.extract_consistency_check(events)

            return ParsedLog(
                task_metadata=task_metadata,
                turns=turns,
                filler_turns=filler_turns,
                consistency_check=consistency_check,
                total_turns=len(turns),
                total_filler_turns=len(filler_turns)
            )

        except Exception as e:
            logger.error(f"解析日志失败 {log_path}: {e}")
            self.errors.append(f"解析日志失败 {log_path}: {str(e)}")
            return None

    def extract_task_metadata(self, events: List[Dict]) -> Optional[TaskMetadata]:
        """提取任务元数据"""
        for event in events:
            if event.get('event') == 'task_start':
                data = event.get('data', {})
                task_id = data.get('task_id', '')

                # 从task_id推断dataset
                dataset = self._infer_dataset(task_id)

                return TaskMetadata(
                    task_id=task_id,
                    task_type=data.get('task_type', ''),
                    question=data.get('question', ''),
                    expected_answer=data.get('expected_answer', ''),
                    images=data.get('images', []),
                    dataset=dataset,
                    timestamp=event.get('timestamp', '')
                )
        return None

    def extract_turns(self, events: List[Dict]) -> List[TurnRecord]:
        """提取所有turn事件"""
        turns = []
        for event in events:
            if event.get('event') == 'turn':
                data = event.get('data', {})

                # 提取评分
                eval_data = data.get('evaluation', {})
                scores = ScoreRecord(
                    score=eval_data.get('official_overall_score', eval_data.get('score')),
                    faithfulness=(eval_data.get('dimension_reports', {}).get('faithfulness', {}) or {}).get('score', eval_data.get('faithfulness_score')),
                    robustness=(eval_data.get('dimension_reports', {}).get('robustness', {}) or {}).get('score', eval_data.get('robustness_score')),
                    consistency=(eval_data.get('dimension_reports', {}).get('consistency', {}) or {}).get('score', eval_data.get('consistency_score')),
                    memory_retention=(eval_data.get('dimension_reports', {}).get('memory_retention', {}) or {}).get('score', eval_data.get('memory_retention_score')),
                    cross_image_confusion=(eval_data.get('dimension_reports', {}).get('cross_image_disambiguation', {}) or {}).get('score', eval_data.get('cross_image_confusion_score')),
                    disambiguation=(eval_data.get('dimension_reports', {}).get('ambiguity_recognition', {}) or {}).get('score', eval_data.get('disambiguation_score')),
                    level_passed=eval_data.get('level_passed', False),
                    reasoning=eval_data.get('reasoning', ''),
                    dimension_reports=eval_data.get('dimension_reports', {}),
                    official_overall_score=eval_data.get('official_overall_score'),
                    evaluation_validity=eval_data.get('evaluation_validity', 'valid'),
                    image_delivery_status=eval_data.get('image_delivery_status', 'unknown')
                )

                turn = TurnRecord(
                    turn_id=data.get('turn', 0),
                    phase=data.get('phase', ''),
                    difficulty=data.get('difficulty', 1),
                    action=data.get('action', ''),
                    message=data.get('message', ''),
                    response=data.get('response', ''),
                    images_sent=data.get('images_sent', []),
                    scores=scores,
                    timestamp=event.get('timestamp', '')
                )
                turns.append(turn)

        return sorted(turns, key=lambda x: x.turn_id)

    def extract_filler_turns(self, events: List[Dict]) -> List[FillerTurnRecord]:
        """提取filler_turn事件"""
        filler_turns = []
        for event in events:
            if event.get('event') == 'filler_turn':
                data = event.get('data', {})
                filler = FillerTurnRecord(
                    filler_index=data.get('filler_index', 0),
                    user_message=data.get('user_message', ''),
                    model_response=data.get('model_response', ''),
                    topic=data.get('topic', ''),
                    response_length=data.get('response_length', 0),
                    timestamp=event.get('timestamp', '')
                )
                filler_turns.append(filler)

        return sorted(filler_turns, key=lambda x: x.filler_index)

    def extract_consistency_check(self, events: List[Dict]) -> Optional[ConsistencyCheckRecord]:
        """提取一致性检查事件"""
        for event in events:
            if event.get('event') == 'consistency_check':
                data = event.get('data', {})
                return ConsistencyCheckRecord(
                    question=data.get('question', ''),
                    response=data.get('response', ''),
                    score=data.get('score', 0.0),
                    expected=data.get('expected', ''),
                    grounded_in_truth=data.get('grounded_in_truth', False),
                    timestamp=event.get('timestamp', '')
                )
        return None

    def _infer_dataset(self, task_id: str) -> str:
        """从task_id推断dataset"""
        # task_id 格式通常为: {task_type}_{dataset}_{suffix}
        # 例如: abr_mscoco_0, ac_mscoco_1
        parts = task_id.split('_')
        if len(parts) >= 2:
            return parts[1]
        return 'unknown'

    def parse_multiple_logs(self, log_paths: List[str]) -> List[ParsedLog]:
        """批量解析多个日志文件

        Args:
            log_paths: 日志文件路径列表

        Returns:
            ParsedLog对象列表（跳过解析失败的文件）
        """
        parsed_logs = []
        for log_path in log_paths:
            logger.info(f"解析日志: {log_path}")
            parsed = self.parse_log_file(log_path)
            if parsed:
                parsed_logs.append(parsed)

        logger.info(f"成功解析 {len(parsed_logs)}/{len(log_paths)} 个日志文件")
        if self.errors:
            logger.warning(f"解析错误: {len(self.errors)} 个")
            for error in self.errors:
                logger.warning(f"  - {error}")

        return parsed_logs

    def get_errors(self) -> List[str]:
        """获取解析错误列表"""
        return self.errors.copy()


def parse_log_directory(log_dir: str, pattern: str = "run_log_*.json") -> List[ParsedLog]:
    """解析目录下的所有日志文件

    Args:
        log_dir: 日志目录路径
        pattern: 文件名匹配模式

    Returns:
        ParsedLog对象列表
    """
    log_dir_path = Path(log_dir)
    if not log_dir_path.exists():
        logger.error(f"日志目录不存在: {log_dir}")
        return []

    log_files = list(log_dir_path.glob(pattern))
    logger.info(f"找到 {len(log_files)} 个日志文件")

    parser = LogParser()
    return parser.parse_multiple_logs([str(f) for f in log_files])


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)

    # 解析现有日志
    log_dir = "E:/Code/M3Bench/M3Bench_new/simulator_test_log/batch_run_20260205_104458"
    logs = parse_log_directory(log_dir)

    print(f"\n解析结果:")
    print(f"总日志数: {len(logs)}")
    if logs:
        print(f"\n第一个日志示例:")
        log = logs[0]
        print(f"  任务ID: {log.task_metadata.task_id}")
        print(f"  任务类型: {log.task_metadata.task_type}")
        print(f"  数据集: {log.task_metadata.dataset}")
        print(f"  Turn数: {log.total_turns}")
        print(f"  Filler Turn数: {log.total_filler_turns}")
        if log.turns:
            print(f"  第一个Turn评分: {log.turns[0].scores.score:.3f}")
