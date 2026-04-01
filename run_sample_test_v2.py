"""
样本验证测试脚本
================

从 run_76 和 run_77 的每种任务类型+数据集组合中各取1条任务，
验证所有组合都能正常跑出对话日志。

输出: simulator_test_log/batch_run_{timestamp}/ 目录下的 per-task JSON 日志

用法:
    python run_sample_test_v2.py
    python run_sample_test_v2.py --runs run_76          # 只跑 run_76
    python run_sample_test_v2.py --runs run_76 run_77   # 跑两个 run
    python run_sample_test_v2.py --verbose               # 详细输出
"""

import sys
import json
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

sys.path.insert(0, str(Path(__file__).parent))

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


def load_sample_tasks(run_dirs: List[str], tasks_per_file: int = 1) -> List[Dict]:
    """从每个 JSONL 文件中取 N 条任务，确保覆盖所有任务类型+数据集组合

    Args:
        run_dirs: run 目录名称列表 (如 ["run_76", "run_77"])
        tasks_per_file: 每个文件取几条任务

    Returns:
        采样后的任务列表
    """
    all_tasks = []
    coverage = {}  # 统计覆盖情况

    for run_name in run_dirs:
        tasks_dir = Path("generated_tasks_v2") / run_name / "tasks"
        if not tasks_dir.exists():
            logger.warning(f"目录不存在: {tasks_dir}")
            continue

        jsonl_files = sorted(tasks_dir.glob("*.jsonl"))
        logger.info(f"[{run_name}] 找到 {len(jsonl_files)} 个任务文件")

        for jsonl_file in jsonl_files:
            file_key = f"{run_name}/{jsonl_file.stem}"
            loaded = 0

            with open(jsonl_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if loaded >= tasks_per_file:
                        break
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        task = json.loads(line)
                        # 标记来源 run 目录，方便图片路径解析
                        task['_source_run'] = run_name
                        all_tasks.append(task)
                        loaded += 1

                        task_type = task.get('task_type', 'unknown')
                        dataset = task.get('metadata', {}).get('source_dataset', 'unknown')
                        key = f"{task_type} x {dataset}"
                        if key not in coverage:
                            coverage[key] = []
                        coverage[key].append(run_name)
                    except json.JSONDecodeError as e:
                        logger.warning(f"JSON 解析失败 ({jsonl_file.name}): {e}")

            if loaded > 0:
                logger.info(f"  {jsonl_file.name}: 取了 {loaded} 条")

    # 打印覆盖统计
    print(f"\n{'='*60}")
    print(f"任务覆盖统计")
    print(f"{'='*60}")
    print(f"总任务数: {len(all_tasks)}")
    print(f"\n任务类型 x 数据集 覆盖:")
    for key in sorted(coverage.keys()):
        runs = coverage[key]
        print(f"  {key}: {len(runs)} 条 (来自 {', '.join(sorted(set(runs)))})")
    print(f"{'='*60}\n")

    return all_tasks


def main():
    parser = argparse.ArgumentParser(
        description='M3Bench 样本验证测试 (run_76 & run_77)',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--runs', nargs='+', default=['run_76', 'run_77'],
        help='要测试的 run 目录 (默认: run_76 run_77)'
    )
    parser.add_argument(
        '--tasks-per-file', type=int, default=1,
        help='每个 JSONL 文件取几条任务 (默认: 1)'
    )
    parser.add_argument(
        '--max-turns', type=int, default=15,
        help='每个任务最大轮数 (默认: 15)'
    )
    parser.add_argument(
        '--min-turns', type=int, default=5,
        help='每个任务最小轮数 (默认: 5)'
    )
    parser.add_argument(
        '--core-model', type=str, default='gpt-5.4',
        help='Core model 名称 (默认: gpt-5.4)'
    )
    parser.add_argument(
        '--target-model', type=str, default='gpt-4o',
        help='Target model 名称 (默认: gpt-4o)'
    )
    parser.add_argument(
        '--verbose', '-v', action='store_true',
        help='详细输出'
    )

    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("M3Bench 样本验证测试")
    print(f"测试 run 目录: {', '.join(args.runs)}")
    print("=" * 70 + "\n")

    # 1. 加载采样任务
    tasks = load_sample_tasks(args.runs, tasks_per_file=args.tasks_per_file)

    if not tasks:
        print("没有加载到任何任务!")
        return 1

    # 2. 初始化组件
    print("[1] 初始化 LLM 客户端...")
    print(f"  Core model: {args.core_model}")
    print(f"  Target model: {args.target_model}")
    llm_client = LLMClient(core_model=args.core_model, target_model=args.target_model)
    conn_test = llm_client.test_connection()
    print(f"  Core model ({llm_client.core_model}): {'OK' if conn_test.get('core_model') else 'FAILED'}")
    print(f"  Target model ({llm_client.target_model}): {'OK' if conn_test.get('target_model') else 'FAILED'}")

    if not all(conn_test.values()):
        print("\nAPI 连接失败! 请检查 API 配置。")
        return 1

    evaluator = Evaluator(mode=EvaluationMode.STRESS_TEST)

    # 3. 配置 - 每个任务独立跑, 1 task per batch
    config = BatchConfig(
        max_turns_per_session=args.max_turns + 5,  # 留一些余量
        min_turns_per_task=args.min_turns,
        max_turns_per_task=args.max_turns,
        transition_style='natural',
        enable_cross_task_memory_test=False,  # 验证时不需要跨任务记忆测试
    )

    batch_simulator = BatchTaskSimulator(
        llm_client=llm_client,
        evaluator=evaluator,
        config=config,
        verbose=args.verbose
    )

    # 4. 逐个任务运行
    print(f"\n[2] 开始运行 {len(tasks)} 个任务...\n")

    success_count = 0
    fail_count = 0
    results_summary = []

    for i, task in enumerate(tasks):
        task_id = task.get('task_id', f'task_{i}')
        task_type = task.get('task_type', 'unknown')
        dataset = task.get('metadata', {}).get('source_dataset', 'unknown')
        source_run = task.get('_source_run', 'unknown')

        print(f"  [{i+1}/{len(tasks)}] {task_id} ({task_type} x {dataset}, {source_run})")

        try:
            # 每个任务独立跑一个 batch（1 task per batch）
            result = batch_simulator.run_batch([task])

            turns = result.total_turns
            completed = result.tasks_completed
            scores = result.aggregate_scores

            status = "OK" if completed > 0 else "INCOMPLETE"
            print(f"         -> {status}: {turns} turns, scores={scores}")

            results_summary.append({
                'task_id': task_id,
                'task_type': task_type,
                'dataset': dataset,
                'source_run': source_run,
                'status': status,
                'turns': turns,
                'scores': scores
            })

            if completed > 0:
                success_count += 1
            else:
                fail_count += 1

        except Exception as e:
            print(f"         -> FAILED: {e}")
            fail_count += 1
            results_summary.append({
                'task_id': task_id,
                'task_type': task_type,
                'dataset': dataset,
                'source_run': source_run,
                'status': 'FAILED',
                'error': str(e)
            })

    # 5. 保存汇总
    log_dir = batch_simulator.get_batch_log_dir()
    if log_dir:
        summary_file = Path(log_dir) / "sample_test_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump({
                'test_time': datetime.now().isoformat(),
                'runs_tested': args.runs,
                'total_tasks': len(tasks),
                'success': success_count,
                'failed': fail_count,
                'results': results_summary
            }, f, indent=2, ensure_ascii=False)

    # 6. 打印最终统计
    print(f"\n{'='*70}")
    print("样本验证测试完成")
    print(f"{'='*70}")
    print(f"  总任务数: {len(tasks)}")
    print(f"  成功: {success_count}")
    print(f"  失败: {fail_count}")
    if log_dir:
        print(f"\n  日志目录: {log_dir}")
    print(f"{'='*70}\n")

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())