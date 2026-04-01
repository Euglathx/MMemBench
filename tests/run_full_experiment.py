"""
完整实验运行脚本 - 使用真实API

为4个模型运行真实测试，然后生成对比图表
"""

import sys
import subprocess
import logging
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = PROJECT_ROOT / "tests"
ANALYSIS_DIR = PROJECT_ROOT / "analysis"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


def run_model_test(model_name, num_batches=5, tasks_per_batch=4, max_turns=35):
    """为单个模型运行真实API测试"""
    logger.info(f"{'='*80}")
    logger.info(f"开始测试模型: {model_name}")
    logger.info(f"{'='*80}")

    # 构建命令
    cmd = [
        sys.executable,
        str(TESTS_DIR / "run_batch_test.py"),
        "--task-files", "generated_tasks_v2/run_18/tasks/*.jsonl",
        "--tasks-per-batch", str(tasks_per_batch),
        "--num-batches", str(num_batches),
        "--max-turns-per-session", "50",
        "--min-turns-per-task", "25",
        "--max-turns-per-task", str(max_turns),
        "--model", model_name
    ]

    logger.info(f"执行命令: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=1800  # 30分钟超时
        )

        if result.returncode == 0:
            logger.info(f"✓ {model_name} 测试完成")
            logger.info(f"输出:\n{result.stdout[-500:]}")  # 只显示最后500字符
            return True
        else:
            logger.error(f"✗ {model_name} 测试失败")
            logger.error(f"错误:\n{result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        logger.error(f"✗ {model_name} 测试超时")
        return False
    except Exception as e:
        logger.error(f"✗ {model_name} 测试异常: {e}")
        return False


def modify_llm_client_model(model_name):
    """修改llm_client.py中的目标模型"""
    llm_client_path = PROJECT_ROOT / "src" / "simulator" / "llm_client.py"

    logger.info(f"修改目标模型为: {model_name}")

    with open(llm_client_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 查找并替换DEFAULT_TARGET_MODEL
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


def find_latest_log_dir(model_name):
    """查找最新的日志目录"""
    log_base = PROJECT_ROOT / "simulator_test_log"

    # 查找所有非mock的batch_run目录
    pattern = f"batch_run_*"
    dirs = sorted(
        [d for d in log_base.glob(pattern) if d.is_dir() and "mock" not in d.name],
        key=lambda x: x.stat().st_mtime,
        reverse=True
    )

    if dirs:
        latest = dirs[0]
        logger.info(f"找到最新日志目录: {latest}")
        return str(latest)
    else:
        logger.error("未找到日志目录")
        return None


def run_analysis(model_name, log_dir):
    """分析单个模型的结果"""
    logger.info(f"{'='*80}")
    logger.info(f"分析模型: {model_name}")
    logger.info(f"{'='*80}")

    output_dir = PROJECT_ROOT / "experiment_results" / "models" / model_name

    cmd = [
        sys.executable,
        str(ANALYSIS_DIR / "run_analysis.py"),
        "--log-dir", log_dir,
        "--model-name", model_name,
        "--output-dir", str(output_dir)
    ]

    logger.info(f"执行命令: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=300  # 5分钟超时
        )

        if result.returncode == 0:
            logger.info(f"✓ {model_name} 分析完成")
            return output_dir
        else:
            logger.error(f"✗ {model_name} 分析失败")
            logger.error(f"错误:\n{result.stderr}")
            return None

    except Exception as e:
        logger.error(f"✗ {model_name} 分析异常: {e}")
        return None


def generate_comparison():
    """生成多模型对比"""
    logger.info(f"{'='*80}")
    logger.info("生成多模型对比图表")
    logger.info(f"{'='*80}")

    comparison_script = ANALYSIS_DIR / "run_multi_model_comparison.py"
    if not comparison_script.exists():
        logger.warning("未找到 analysis/run_multi_model_comparison.py，跳过多模型对比生成")
        return None

    cmd = [sys.executable, str(comparison_script)]

    try:
        result = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode == 0:
            logger.info("✓ 多模型对比完成")
            logger.info(f"输出:\n{result.stdout}")
            return True
        else:
            logger.error("✗ 多模型对比失败")
            logger.error(f"错误:\n{result.stderr}")
            return False

    except Exception as e:
        logger.error(f"✗ 多模型对比异常: {e}")
        return False


def main():
    """主流程"""
    logger.info("="*80)
    logger.info("M3Bench 完整实验 - 真实API测试")
    logger.info("="*80 + "\n")

    # 4个模型
    models = [
        "gpt-5",
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "kimi-k2.5"
    ]

    # 测试参数
    num_batches = 6  # 6个batch
    tasks_per_batch = 4  # 每batch 4个任务
    max_turns = 35  # 最多35轮

    logger.info(f"测试配置:")
    logger.info(f"  模型数量: {len(models)}")
    logger.info(f"  每个模型: {num_batches} batches × {tasks_per_batch} tasks = {num_batches * tasks_per_batch} tasks")
    logger.info(f"  最大轮数: {max_turns}")
    logger.info(f"  预计总任务数: {len(models) * num_batches * tasks_per_batch}\n")

    model_log_dirs = {}

    # 步骤1: 为每个模型运行测试
    logger.info("阶段 1/3: 运行真实API测试")
    logger.info("-" * 80 + "\n")

    for i, model_name in enumerate(models, 1):
        logger.info(f"\n[{i}/{len(models)}] 测试模型: {model_name}\n")

        # 修改llm_client.py中的目标模型
        if not modify_llm_client_model(model_name):
            logger.error(f"跳过 {model_name}")
            continue

        # 运行测试
        success = run_model_test(
            model_name,
            num_batches=num_batches,
            tasks_per_batch=tasks_per_batch,
            max_turns=max_turns
        )

        if success:
            # 查找生成的日志目录
            log_dir = find_latest_log_dir(model_name)
            if log_dir:
                model_log_dirs[model_name] = log_dir
        else:
            logger.warning(f"⚠ {model_name} 测试失败，将跳过此模型")

        logger.info(f"\n完成 [{i}/{len(models)}] {model_name}\n")

    if not model_log_dirs:
        logger.error("所有模型测试都失败了！")
        return 1

    logger.info(f"\n成功测试的模型: {list(model_log_dirs.keys())}\n")

    # 步骤2: 分析每个模型
    logger.info("\n阶段 2/3: 分析测试结果")
    logger.info("-" * 80 + "\n")

    analysis_results = {}
    for model_name, log_dir in model_log_dirs.items():
        output_dir = run_analysis(model_name, log_dir)
        if output_dir:
            analysis_results[model_name] = output_dir

    if not analysis_results:
        logger.error("所有模型分析都失败了！")
        return 1

    # 步骤3: 生成多模型对比
    logger.info("\n阶段 3/3: 生成多模型对比")
    logger.info("-" * 80 + "\n")

    comparison_success = generate_comparison()

    # 最终总结
    logger.info("\n" + "="*80)
    logger.info("实验完成!")
    logger.info("="*80 + "\n")

    logger.info(f"成功测试的模型 ({len(analysis_results)}/{len(models)}):")
    for model_name, output_dir in analysis_results.items():
        logger.info(f"  ✓ {model_name}: {output_dir}")

    if comparison_success:
        logger.info(f"\n多模型对比图表: experiment_results/multi_model_comparison/")
        logger.info("\n生成的图表:")
        logger.info("  - 01_radar_chart.png          (雷达图)")
        logger.info("  - 02_bar_chart.png            (柱状图)")
        logger.info("  - 03_turn_progression.png     (折线图 - 30+轮)")
        logger.info("  - 04_lag_analysis.png         (Lag分析)")
        logger.info("  - 05_error_distribution.png   (错误分布)")
        logger.info("  - 06_comparison_table.png     (对比表格)")
    elif comparison_success is None:
        logger.info("\n已跳过多模型对比图表生成")

    return 0 if comparison_success is not False else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logger.info("\n用户中断")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n未预期的错误: {e}", exc_info=True)
        sys.exit(1)
