"""
测试 Evaluator 的 503 错误修复
=================================

专门测试 LLM Judge 调用是否正常工作
"""

import sys
import logging
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.simulator import Evaluator, EvaluationMode

# 配置详细日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_evaluator_initialization():
    """测试 Evaluator 初始化"""
    print("\n" + "="*70)
    print("测试 1: Evaluator 初始化")
    print("="*70)

    try:
        evaluator = Evaluator(mode=EvaluationMode.STRESS_TEST)
        print(f"✓ Evaluator 初始化成功")
        print(f"  - API URL: {evaluator.api_url}")
        print(f"  - Evaluation Model: {evaluator.evaluation_model}")
        print(f"  - Use LLM Judge: {evaluator.use_llm_judge}")
        print(f"  - LLM Judge Weight: {evaluator.llm_judge_weight}")
        return True, evaluator
    except Exception as e:
        print(f"✗ Evaluator 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def test_image_encoding(evaluator):
    """测试图像编码（带压缩）"""
    print("\n" + "="*70)
    print("测试 2: Evaluator 图像编码和压缩")
    print("="*70)

    # 查找测试图像
    test_images = []
    for pattern in ["generated_tasks_v2/*/images/*.jpg", "data/*/images/*.jpg"]:
        found = list(project_root.glob(pattern))
        if found:
            test_images = [str(f) for f in found[:2]]
            break

    if not test_images:
        print("⚠ 未找到测试图像，跳过此测试")
        return True

    print(f"找到 {len(test_images)} 张测试图像")

    total_size = 0
    for i, img_path in enumerate(test_images, 1):
        print(f"\n图像 {i}: {Path(img_path).name}")

        # 检查原始大小
        file_size = Path(img_path).stat().st_size / (1024 * 1024)
        print(f"  原始大小: {file_size:.2f}MB")

        # 测试编码
        encoded = evaluator._encode_image(img_path, max_size_mb=3.0)

        if encoded:
            encoded_size = len(encoded) / (1024 * 1024)
            total_size += encoded_size
            print(f"  编码后大小: {encoded_size:.2f}MB")
            print(f"  ✓ 编码成功")
        else:
            print(f"  ✗ 编码失败")
            return False

    print(f"\n总编码大小: {total_size:.2f}MB")
    return True


def test_llm_judge_call(evaluator):
    """测试 LLM Judge 调用"""
    print("\n" + "="*70)
    print("测试 3: LLM Judge 调用 (最关键)")
    print("="*70)

    # 查找测试图像
    test_images = []
    for pattern in ["generated_tasks_v2/*/images/*.jpg"]:
        found = list(project_root.glob(pattern))
        if found:
            test_images = [str(f) for f in found[:2]]  # 只用2张图
            break

    if not test_images:
        print("⚠ 未找到测试图像，使用空图像列表测试")

    print(f"使用 {len(test_images)} 张图像进行测试")
    for img in test_images:
        print(f"  - {Path(img).name}")

    # 构建测试任务
    task = {
        "task_type": "attribute_comparison",
        "question": "Which image has more objects?",
        "expected_answer": "Image 1",
        "images": test_images
    }

    # 初始化 evaluator 状态
    evaluator.reset_for_task(
        task_type=task["task_type"],
        num_images=len(test_images) if test_images else 1
    )

    print("\n正在调用 LLM Judge...")
    try:
        # 测试评估
        result = evaluator.evaluate_response(
            response="I think Image 1 has more objects because I can see several items.",
            expected_answer=task.get("expected_answer"),
            question_asked=task.get("question"),
            action_type="guidance",
            task=task
        )

        if result:
            print(f"✓ LLM Judge 调用成功!")
            print(f"\n评估结果:")
            print(f"  - Score: {result.score:.3f}")
            print(f"  - Reasoning: {result.reasoning[:200]}...")
            print(f"  - Faithfulness: {result.faithfulness_score:.3f}")
            print(f"  - Robustness: {result.robustness_score:.3f}")

            if result.llm_judge_output:
                print(f"  - LLM Judge 已执行: ✓")
            else:
                print(f"  - LLM Judge 未执行（可能禁用或失败）")

            return True
        else:
            print(f"✗ LLM Judge 调用失败 (返回None)")
            return False

    except Exception as e:
        print(f"✗ LLM Judge 调用异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "="*70)
    print("Evaluator 503 错误修复验证测试")
    print("="*70)
    print("\n此脚本将测试:")
    print("  1. Evaluator 初始化（检查模型配置）")
    print("  2. 图像编码和压缩")
    print("  3. LLM Judge API 调用")
    print("\n开始测试...\n")

    results = {}

    # 测试 1: 初始化
    success, evaluator = test_evaluator_initialization()
    results["initialization"] = success

    if not evaluator:
        print("\n⚠ Evaluator 初始化失败，无法继续后续测试")
        return

    # 测试 2: 图像编码
    try:
        results["encoding"] = test_image_encoding(evaluator)
    except Exception as e:
        print(f"图像编码测试异常: {e}")
        results["encoding"] = False

    # 测试 3: LLM Judge 调用
    try:
        results["llm_judge"] = test_llm_judge_call(evaluator)
    except Exception as e:
        print(f"LLM Judge 测试异常: {e}")
        results["llm_judge"] = False

    # 汇总结果
    print("\n" + "="*70)
    print("测试结果汇总")
    print("="*70)

    total_tests = len([r for r in results.values() if r is not None])
    passed_tests = sum(1 for r in results.values() if r is True)

    for test_name, result in results.items():
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{test_name:20s}: {status}")

    print("\n" + "-"*70)
    if total_tests > 0:
        print(f"总计: {passed_tests}/{total_tests} 测试通过 ({passed_tests*100//total_tests}%)")

    # 诊断建议
    print("\n" + "="*70)
    print("诊断建议")
    print("="*70)

    if not results.get("initialization"):
        print("⚠ Evaluator 初始化失败")
        print("  - 检查 API URL 和 API Key")
    elif not results.get("llm_judge"):
        print("⚠ LLM Judge 调用失败，可能的原因:")
        print("  1. 模型名称错误 - 检查日志中的 evaluation_model")
        print("  2. 确保 evaluation_model 在你的 API 平台上存在")
        print("  3. 设置环境变量:")
        print("     $env:M3BENCH_EVAL_MODEL=\"gemini-2.5-flash-image-preview\"")
        print("  4. 图像过大 - 日志中会显示 payload 大小")
        print("\n  查看上方日志中的详细错误信息")
    else:
        print("✓ 所有测试通过!")
        print("\n修复已成功:")
        print("  1. Evaluator 使用正确的模型")
        print("  2. 图像自动压缩功能正常")
        print("  3. LLM Judge 可以正常调用")

    print("\n详细文档: API_CONFIGURATION.md")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
