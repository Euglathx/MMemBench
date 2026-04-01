"""
真实API实验 - 4个模型完整测试
改进版：更好的进度追踪和错误处理
"""

import sys
import subprocess
import logging
import time
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


def modify_llm_client_model(model_name):
    """修改llm_client.py中的目标模型"""
    llm_client_path = Path("src/simulator/llm_client.py")

    logger.info(f"修改目标模型为: {model_name}")

    with open(llm_client_path, 'r', encoding='utf-8') as f:
        content = f.read()

    import re
    pattern = r'DEFAULT_TARGET_MODEL\s*=\s*["\']([^"\']+)["\']'

    if re.search(pattern, content):
        new_content = re.sub(
            pattern,
            f'DEFAULT_TARGET_MODEL = "{model_name}"',
            content
        )

        with open(llm_client_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        logger.info(f"✓ 已修改 DEFAULT_TARGET_MODEL = \"{model_name}\"")
        return True
    else:
        logger.error("✗ 未找到DEFAULT_TARGET_MODEL定义")
        return False


def run_single_batch_test(model_name, batch_size=2, num_batches=3, max_turns=35):
    """为单个模型运行一个小规模测试

    Args:
        model_name: 模型名称
        batch_size: 每批任务数（减少到2）
        num_batches: 批次数（减少到3）
        max_turns: 最大轮数
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"开始测试模型: {model_name}")
    logger.info(f"配置: {num_batches} batches × {batch_size} tasks = {num_batches * batch_size} tasks")
    logger.info(f"{'='*80}\n")

    # 构建命令 - 使用更少的任务进行测试
    cmd = [
        sys.executable,
        "run_batch_test.py",
        "--task-files", "generated_tasks_v2/run_18/tasks/*.jsonl",
        "--tasks-per-batch", str(batch_size),
        "--num-batches", str(num_batches),
        "--max-turns-per-session", "50",
        "--min-turns-per-task", "25",
        "--max-turns-per-task", str(max_turns),
        "--model", model_name,
        "--verbose"  # 启用详细输出
    ]

    logger.info(f"执行命令: {' '.join(cmd)}\n")

    # 实时输出
    try:
        process = subprocess.Popen(
            cmd,
            cwd=Path(__file__).parent,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )

        # 实时打印输出
        output_lines = []
        for line in process.stdout:
            print(line, end='')
            output_lines.append(line)

            # 检测关键进度信息
            if "批次" in line or "完成" in line or "ERROR" in line or "失败" in line:
                logger.info(f">>> {line.strip()}")

        process.wait()

        if process.returncode == 0:
            logger.info(f"\n✓ {model_name} 测试完成！")
            return True
        else:
            logger.error(f"\n✗ {model_name} 测试失败 (返回码: {process.returncode})")
            return False

    except subprocess.TimeoutExpired:
        logger.error(f"\n✗ {model_name} 测试超时")
        return False
    except Exception as e:
        logger.error(f"\n✗ {model_name} 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def find_latest_log_dir():
    """查找最新的日志目录"""
    log_base = Path("simulator_test_log")

    # 查找所有非mock的batch_run目录
    dirs = sorted(
        [d for d in log_base.glob("batch_run_*") if d.is_dir() and "mock" not in d.name],
        key=lambda x: x.stat().st_mtime,
        reverse=True
    )

    if dirs:
        return dirs[0]
    return None


def main():
    """主流程"""
    logger.info("="*80)
    logger.info("M3Bench 真实API完整实验")
    logger.info("="*80 + "\n")

    # 4个模型
    models = [
        "gpt-5",
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "kimi-k2.5"
    ]

    # 测试参数（减小规模以加快测试）
    batch_size = 2      # 每批2个任务
    num_batches = 3     # 3个批次
    max_turns = 35      # 最多35轮

    total_tasks_per_model = batch_size * num_batches

    logger.info(f"实验配置:")
    logger.info(f"  模型数量: {len(models)}")
    logger.info(f"  每个模型: {num_batches} batches × {batch_size} tasks = {total_tasks_per_model} tasks")
    logger.info(f"  最大轮数: {max_turns}")
    logger.info(f"  预计总任务数: {len(models) * total_tasks_per_model}\n")

    successful_models = []
    model_log_dirs = {}

    start_time = time.time()

    # 测试每个模型
    for i, model_name in enumerate(models, 1):
        model_start_time = time.time()

        logger.info(f"\n{'#'*80}")
        logger.info(f"进度: [{i}/{len(models)}] 测试模型: {model_name}")
        logger.info(f"{'#'*80}\n")

        # 修改模型配置
        if not modify_llm_client_model(model_name):
            logger.error(f"跳过 {model_name} - 无法修改配置")
            continue

        # 运行测试
        success = run_single_batch_test(
            model_name,
            batch_size=batch_size,
            num_batches=num_batches,
            max_turns=max_turns
        )

        model_elapsed = time.time() - model_start_time

        if success:
            successful_models.append(model_name)

            # 查找生成的日志目录
            log_dir = find_latest_log_dir()
            if log_dir:
                model_log_dirs[model_name] = log_dir
                logger.info(f"✓ 日志目录: {log_dir}")

            logger.info(f"✓ {model_name} 完成! 用时: {model_elapsed:.1f}秒")
        else:
            logger.warning(f"⚠ {model_name} 测试失败，用时: {model_elapsed:.1f}秒")

        logger.info(f"\n当前进度: 已完成 {i}/{len(models)} 个模型")
        logger.info(f"成功: {len(successful_models)} | 失败: {i - len(successful_models)}")

        # 短暂休息
        if i < len(models):
            logger.info("\n等待3秒后继续下一个模型...\n")
            time.sleep(3)

    total_elapsed = time.time() - start_time

    # 最终总结
    logger.info("\n" + "="*80)
    logger.info("实验完成!")
    logger.info("="*80 + "\n")

    logger.info(f"总用时: {total_elapsed:.1f}秒 ({total_elapsed/60:.1f}分钟)")
    logger.info(f"成功测试的模型 ({len(successful_models)}/{len(models)}):")

    if successful_models:
        for model_name in successful_models:
            log_dir = model_log_dirs.get(model_name, "未知")
            logger.info(f"  ✓ {model_name}: {log_dir}")
    else:
        logger.error("  ❌ 没有成功测试任何模型")
        return 1

    # 下一步提示
    logger.info(f"\n下一步:")
    logger.info(f"1. 分析结果: python run_analysis.py --log-dir <日志目录> --model-name <模型名>")
    logger.info(f"2. 多模型对比: python run_multi_model_comparison.py")

    return 0 if len(successful_models) == len(models) else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logger.info("\n\n用户中断实验")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n未预期的错误: {e}", exc_info=True)
        sys.exit(1)
