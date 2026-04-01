#!/usr/bin/env python3
"""
Task 1D Verification Script

验证batch测试结果是否包含完整的turn-level对话细节。

用法:
    python task/verify_task_1d.py <batch_result_file>

示例:
    python task/verify_task_1d.py test_output/task_1d/batch_results_20260201_120000.json
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any


def verify_turn_structure(turn: Dict[str, Any], task_id: str, turn_index: int) -> List[str]:
    """
    验证单个turn的结构是否完整

    Args:
        turn: turn数据字典
        task_id: 任务ID
        turn_index: turn索引

    Returns:
        错误消息列表(如果有)
    """
    errors = []
    required_keys = ['turn', 'action', 'query', 'response']
    recommended_keys = ['images_sent', 'evaluation', 'timestamp']

    # 检查必需字段
    missing_required = [k for k in required_keys if k not in turn]
    if missing_required:
        errors.append(
            f"Task {task_id}, Turn {turn_index}: Missing required keys {missing_required}"
        )

    # 检查推荐字段
    missing_recommended = [k for k in recommended_keys if k not in turn]
    if missing_recommended:
        errors.append(
            f"Task {task_id}, Turn {turn_index}: Missing recommended keys {missing_recommended}"
        )

    # 检查字段内容是否为空
    if 'query' in turn and not turn['query']:
        errors.append(f"Task {task_id}, Turn {turn_index}: 'query' is empty")

    if 'response' in turn and not turn['response']:
        errors.append(f"Task {task_id}, Turn {turn_index}: 'response' is empty")

    return errors


def verify_batch_integration(batch_result_file: Path) -> bool:
    """
    验证batch结果文件的turn-level集成

    Args:
        batch_result_file: batch结果文件路径

    Returns:
        是否通过验证
    """
    if not batch_result_file.exists():
        print(f"❌ ERROR: File not found: {batch_result_file}")
        return False

    print("=== Task 1D Verification ===")
    print(f"File: {batch_result_file.name}\n")

    try:
        with open(batch_result_file, encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ ERROR: Invalid JSON - {e}")
        return False

    total_tasks = 0
    tasks_with_turns = 0
    total_turns_captured = 0
    all_errors = []

    # 处理results列表(每个batch是一个元素)
    results = data.get('results', [])
    if not results:
        print("❌ FAIL: No 'results' field in batch file")
        return False

    for batch_idx, batch in enumerate(results):
        batch_id = batch.get('batch_id', f'batch_{batch_idx}')
        task_results = batch.get('task_results', [])

        for task_result in task_results:
            total_tasks += 1
            task_id = task_result.get('task_id', 'unknown')

            # 检查是否有turns字段
            if 'turns' in task_result:
                turns = task_result['turns']

                if not turns:
                    all_errors.append(f"Task {task_id}: 'turns' field exists but is empty")
                    continue

                tasks_with_turns += 1
                num_turns = len(turns)
                total_turns_captured += num_turns

                # 验证每个turn的结构
                for turn_idx, turn_data in enumerate(turns):
                    turn_errors = verify_turn_structure(turn_data, task_id, turn_idx)
                    all_errors.extend(turn_errors)

                # 如果没有错误,报告成功
                if not any(task_id in err for err in all_errors):
                    print(f"✅ Task {task_id}: {num_turns} turns captured with complete data")
            else:
                all_errors.append(f"Task {task_id}: Missing 'turns' field")

    # 打印统计信息
    print(f"\n{'='*60}")
    print("Summary:")
    print(f"  Total tasks: {total_tasks}")
    print(f"  Tasks with turn details: {tasks_with_turns}")
    print(f"  Total turns captured: {total_turns_captured}")

    if total_tasks > 0:
        coverage = (tasks_with_turns / total_tasks) * 100
        print(f"  Coverage: {coverage:.1f}%")

        if total_turns_captured > 0:
            avg_turns = total_turns_captured / tasks_with_turns if tasks_with_turns > 0 else 0
            print(f"  Average turns per task: {avg_turns:.1f}")

    # 打印错误
    print(f"\n{'='*60}")
    if all_errors:
        print(f"Errors found: {len(all_errors)}")
        for error in all_errors[:10]:  # 只显示前10个错误
            print(f"  - {error}")
        if len(all_errors) > 10:
            print(f"  ... and {len(all_errors) - 10} more errors")
    else:
        print("No errors found!")

    # 判断是否通过
    print(f"\n{'='*60}")
    if tasks_with_turns == total_tasks and total_turns_captured > 0 and not all_errors:
        print("✅ PASS: All tasks have complete turn-level details")
        return True
    else:
        print(f"❌ FAIL:")
        if tasks_with_turns < total_tasks:
            print(f"  - {total_tasks - tasks_with_turns} tasks missing turn details")
        if total_turns_captured == 0:
            print(f"  - No turns captured at all")
        if all_errors:
            print(f"  - {len(all_errors)} structural errors found")
        return False


def verify_no_placeholders(runlog_file: Path) -> bool:
    """
    验证转换后的runlog中没有placeholder事件

    Args:
        runlog_file: runlog文件路径

    Returns:
        是否没有placeholder
    """
    if not runlog_file.exists():
        print(f"⚠️ WARNING: Runlog file not found: {runlog_file}")
        return True  # 不影响主验证

    print(f"\n{'='*60}")
    print("Checking for placeholders in converted runlog...")

    try:
        with open(runlog_file, encoding='utf-8') as f:
            events = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ ERROR: Invalid JSON in runlog - {e}")
        return False

    placeholder_count = 0
    placeholder_pattern = "detailed log not available"

    for event in events:
        if event.get('event') == 'core_model_decision':
            msg = event.get('message_to_model', '')
            if placeholder_pattern in msg:
                placeholder_count += 1

        if event.get('event') == 'target_model_response':
            response = event.get('target_response', '')
            if placeholder_pattern in response:
                placeholder_count += 1

    print(f"Placeholder events found: {placeholder_count}")

    if placeholder_count == 0:
        print("✅ PASS: No placeholders in runlog")
        return True
    else:
        print(f"❌ FAIL: {placeholder_count} placeholder events found")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python task/verify_task_1d.py <batch_result_file> [runlog_file]")
        print("\nExample:")
        print("  python task/verify_task_1d.py test_output/task_1d/batch_results_*.json")
        print("  python task/verify_task_1d.py batch_results.json converted_runlog.json")
        sys.exit(1)

    result_file = Path(sys.argv[1])
    passed = verify_batch_integration(result_file)

    # 如果提供了runlog文件,也检查它
    if len(sys.argv) >= 3:
        runlog_file = Path(sys.argv[2])
        passed_runlog = verify_no_placeholders(runlog_file)
        passed = passed and passed_runlog

    sys.exit(0 if passed else 1)
