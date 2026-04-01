"""
多模型批处理测试脚本

按照用户要求，为4个模型分别运行测试：
- gpt-5
- gemini-2.5-pro
- gemini-2.5-flash
- kimi-k2.5
"""

import sys
import json
import argparse
import glob
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.simulator import (
    BatchTaskSimulator,
    BatchConfig,
    LLMClient,
    Evaluator,
    EvaluationMode
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_tasks_from_files(task_files: List[str], max_tasks: int = None) -> List[Dict]:
    """从JSONL文件加载任务"""
    all_tasks = []

    for file_pattern in task_files:
        pattern_path = Path(file_pattern)
        if any(ch in file_pattern for ch in "*?[]"):
            pattern = str(pattern_path if pattern_path.is_absolute() else PROJECT_ROOT / pattern_path)
            matching_files = [Path(p) for p in glob.glob(pattern, recursive=True)]
        else:
            resolved_path = pattern_path if pattern_path.is_absolute() else PROJECT_ROOT / pattern_path
            matching_files = [resolved_path]

        for file_path in matching_files:
            if not file_path.exists():
                logger.warning(f"文件不存在: {file_path}")
                continue

            logger.info(f"加载任务: {file_path}")

            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    if line.strip():
                        try:
                            task = json.loads(line)
                            all_tasks.append(task)
                        except json.JSONDecodeError as e:
                            logger.warning(f"跳过无效JSON ({file_path}:{line_num}): {e}")

    if max_tasks and len(all_tasks) > max_tasks:
        all_tasks = all_tasks[:max_tasks]

    logger.info(f"共加载 {len(all_tasks)} 个任务")
    return all_tasks


def split_into_batches(tasks: List[Dict], batch_size: int) -> List[List[Dict]]:
    """将任务分成批次"""
    batches = []
    for i in range(0, len(tasks), batch_size):
        batches.append(tasks[i:i + batch_size])
    return batches


def run_model_tests(model_name: str, model_api_name: str = None,
                   tasks_per_batch: int = 4, num_batches: int = 8,
                   max_turns_per_session: int = 30, min_turns_per_task: int = 15,
                   max_turns_per_task: int = 30):
    """为单个模型运行测试

    Args:
        model_name: 模型名称（用于日志文件和输出）
        model_api_name: 模型API名称（可选，如果不同于model_name）
        tasks_per_batch: 每批任务数
        num_batches: 批次数
        max_turns_per_session: session最大轮数
        min_turns_per_task: 任务最小轮数
        max_turns_per_task: 任务最大轮数
    """
    logger.info("="*80)
    logger.info(f"为模型 {model_name} 运行测试")
    logger.info("="*80)

    # 加载任务
    task_files = list((PROJECT_ROOT / 'generated_tasks_v2' / 'run_18' / 'tasks').glob('*.jsonl'))
    all_tasks = load_tasks_from_files([str(f) for f in task_files], max_tasks=None)

    if not all_tasks:
        logger.error("没有加载到任何任务!")
        return False

    # 分批
    batches = split_into_batches(all_tasks, tasks_per_batch)
    batches = batches[:num_batches]

    logger.info(f"总任务: {len(all_tasks)}")
    logger.info(f"批次数: {len(batches)}")
    logger.info(f"每批任务数: {tasks_per_batch}")
    logger.info(f"Max turns/session: {max_turns_per_session}")
    logger.info(f"Min/Max turns/task: {min_turns_per_task}/{max_turns_per_task}")
    logger.info("")

    # 创建输出目录
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = PROJECT_ROOT / 'simulator_test_log' / f'batch_run_{model_name}_{timestamp}'
    output_dir.mkdir(parents=True, exist_ok=True)

    # 初始化组件
    api_name = model_api_name or model_name
    try:
        llm_client = LLMClient(target_model=api_name)
    except Exception as e:
        logger.error(f"无法初始化LLM客户端: {e}")
        logger.info(f"使用 {api_name} 初始化失败，但继续执行...")
        # 继续执行，模拟器会使用默认模型
        llm_client = LLMClient()

    evaluator = Evaluator(mode=EvaluationMode.STRESS_TEST)

    # 配置批处理
    config = BatchConfig(
        max_turns_per_session=max_turns_per_session,
        min_turns_per_task=min_turns_per_task,
        max_turns_per_task=max_turns_per_task,
        transition_style='natural',
        enable_cross_task_memory_test=True,
        cross_task_memory_interval=3
    )

    batch_simulator = BatchTaskSimulator(
        llm_client=llm_client,
        evaluator=evaluator,
        config=config,
        verbose=True
    )

    # 运行批处理
    all_results = []

    for batch_idx, batch in enumerate(batches):
        logger.info(f"\n{'='*60}")
        logger.info(f"运行批次 {batch_idx + 1}/{len(batches)}")
        logger.info(f"任务: {[t.get('task_id', 'unknown') for t in batch]}")
        logger.info(f"{'='*60}")

        try:
            result = batch_simulator.run_batch(batch)
            all_results.append(result.to_dict())

            logger.info(f"批次 {batch_idx + 1} 完成:")
            logger.info(f"  总轮数: {result.total_turns}")
            logger.info(f"  完成任务: {result.tasks_completed}/{result.tasks_attempted}")

        except Exception as e:
            logger.error(f"批次 {batch_idx + 1} 失败: {e}")
            import traceback
            traceback.print_exc()

    # 保存结果
    summary = {
        'model_name': model_name,
        'total_batches': len(all_results),
        'total_turns': sum(r.get('total_turns', 0) for r in all_results),
        'total_tasks_completed': sum(r.get('tasks_completed', 0) for r in all_results),
        'total_tasks_attempted': sum(r.get('tasks_attempted', 0) for r in all_results),
    }

    output_file = output_dir / f"summary_{model_name}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'run_time': timestamp,
            'model': model_name,
            'config': {
                'tasks_per_batch': tasks_per_batch,
                'num_batches': len(batches),
                'max_turns_per_session': max_turns_per_session,
                'min_turns_per_task': min_turns_per_task,
                'max_turns_per_task': max_turns_per_task,
            },
            'summary': summary,
            'results': all_results
        }, f, indent=2, ensure_ascii=False)

    logger.info(f"\n结果已保存: {output_file}")
    logger.info("\n" + "="*80)
    logger.info(f"模型 {model_name} 测试完成!")
    logger.info("="*80)
    logger.info(f"总批次: {summary['total_batches']}")
    logger.info(f"总轮数: {summary['total_turns']}")
    logger.info(f"完成任务: {summary['total_tasks_completed']}/{summary['total_tasks_attempted']}")

    return output_dir


def main():
    parser = argparse.ArgumentParser(
        description='M3Bench 多模型批处理测试',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 为所有4个模型运行测试
  python tests/run_batch_test_multi_model.py

  # 只测试特定模型
  python tests/run_batch_test_multi_model.py --models gpt-5 gemini-2.5-pro

  # 自定义参数
  python tests/run_batch_test_multi_model.py --tasks-per-batch 3 --num-batches 10 --max-turns 40
        """
    )

    parser.add_argument(
        '--models',
        nargs='+',
        default=['gpt-5', 'gemini-2.5-pro', 'gemini-2.5-flash', 'kimi-k2.5'],
        help='要测试的模型名称'
    )
    parser.add_argument(
        '--tasks-per-batch',
        type=int,
        default=4,
        help='每批任务数'
    )
    parser.add_argument(
        '--num-batches',
        type=int,
        default=8,
        help='批次数'
    )
    parser.add_argument(
        '--max-turns',
        type=int,
        default=30,
        help='每个session最大轮数'
    )
    parser.add_argument(
        '--min-turns',
        type=int,
        default=15,
        help='每个任务最小轮数'
    )
    parser.add_argument(
        '--max-task-turns',
        type=int,
        default=30,
        help='每个任务最大轮数'
    )

    args = parser.parse_args()

    print("\n" + "="*80)
    print("M3Bench 多模型批处理测试")
    print("="*80 + "\n")

    models = args.models
    print(f"将为以下模型运行测试:")
    for i, model in enumerate(models, 1):
        print(f"  {i}. {model}")
    print()

    results = {}

    for model_name in models:
        try:
            output_dir = run_model_tests(
                model_name=model_name,
                tasks_per_batch=args.tasks_per_batch,
                num_batches=args.num_batches,
                max_turns_per_session=args.max_turns,
                min_turns_per_task=args.min_turns,
                max_turns_per_task=args.max_task_turns
            )
            results[model_name] = str(output_dir)
        except Exception as e:
            logger.error(f"模型 {model_name} 测试失败: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "="*80)
    print("所有模型测试完成!")
    print("="*80)
    print("\n测试结果位置:")
    for model_name, output_dir in results.items():
        print(f"  {model_name}: {output_dir}")


if __name__ == "__main__":
    main()
