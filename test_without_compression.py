"""
测试禁用图像压缩后是否仍然工作正常
=====================================

验证原始图片大小是否会导致503错误
"""

import sys
import logging
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.simulator import LLMClient, Evaluator, EvaluationMode

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_with_large_limit():
    """测试使用较大的大小限制（基本不压缩）"""
    print("\n" + "="*70)
    print("测试: 使用10MB限制（基本不压缩原始图片）")
    print("="*70)

    client = LLMClient()

    # 查找测试图像
    test_images = []
    for pattern in ["generated_tasks_v2/*/images/*.jpg"]:
        found = list(project_root.glob(pattern))
        if found:
            # 找最大的几张图
            found.sort(key=lambda x: x.stat().st_size, reverse=True)
            test_images = [str(f) for f in found[:3]]
            break

    if not test_images:
        print("⚠ 未找到测试图像")
        return False

    print(f"\n使用 {len(test_images)} 张图像:")
    total_original_size = 0
    for img in test_images:
        size_mb = Path(img).stat().st_size / (1024 * 1024)
        total_original_size += size_mb
        print(f"  - {Path(img).name}: {size_mb:.2f}MB")

    print(f"总原始大小: {total_original_size:.2f}MB")

    # 使用10MB的大小限制（基本不会触发压缩）
    print("\n正在编码图像（max_size_mb=10.0）...")
    encoded_images = []
    total_encoded_size = 0

    for img_path in test_images:
        encoded = client._encode_image(img_path, max_size_mb=10.0)
        if encoded:
            encoded_size = len(encoded) / (1024 * 1024)
            total_encoded_size += encoded_size
            encoded_images.append(encoded)
            print(f"  ✓ 编码成功: {encoded_size:.2f}MB")
        else:
            print(f"  ✗ 编码失败")
            return False

    print(f"\n总编码大小: {total_encoded_size:.2f}MB")

    if total_encoded_size > 15:
        print(f"⚠ 警告: Payload 可能过大（{total_encoded_size:.2f}MB > 15MB）")
        print("  这可能会导致503错误")

    # 尝试发送到API
    messages = [{
        "role": "user",
        "content": "Please briefly describe what you see in these images."
    }]

    print("\n正在发送到 API...")
    try:
        response = client.call_target_model(
            messages=messages,
            images=test_images,
            max_tokens=200
        )

        if response.get("success"):
            print(f"✓ API 调用成功（未压缩原图）!")
            print(f"  响应: {response.get('content', '')[:150]}...")
            return True
        else:
            error = response.get("error", "Unknown error")
            print(f"✗ API 调用失败")
            print(f"  错误: {error}")

            if "503" in error:
                print("\n  → 确认: 原始大小图片会导致503错误")
                print("  → 图像压缩是必需的")
            return False

    except Exception as e:
        print(f"✗ API 调用异常: {e}")
        return False


def test_evaluator_with_large_images():
    """测试 Evaluator 在大图像下是否正常工作"""
    print("\n" + "="*70)
    print("测试: Evaluator LLM Judge 与大图像")
    print("="*70)

    evaluator = Evaluator(mode=EvaluationMode.STRESS_TEST)

    # 查找测试图像
    test_images = []
    for pattern in ["generated_tasks_v2/*/images/*.jpg"]:
        found = list(project_root.glob(pattern))
        if found:
            found.sort(key=lambda x: x.stat().st_size, reverse=True)
            test_images = [str(f) for f in found[:2]]
            break

    if not test_images:
        print("⚠ 未找到测试图像")
        return True

    print(f"\n使用 {len(test_images)} 张图像:")
    for img in test_images:
        size_mb = Path(img).stat().st_size / (1024 * 1024)
        print(f"  - {Path(img).name}: {size_mb:.2f}MB")

    # 构建任务
    task = {
        "task_type": "attribute_comparison",
        "question": "Which image has more objects?",
        "expected_answer": "Image 1",
        "images": test_images
    }

    evaluator.reset_for_task(
        task_type=task["task_type"],
        num_images=len(test_images)
    )

    print("\n正在调用 LLM Judge...")
    try:
        result = evaluator.evaluate_response(
            response="Image 1 has more objects.",
            expected_answer=task.get("expected_answer"),
            question_asked=task.get("question"),
            action_type="guidance",
            task=task
        )

        if result and result.llm_judge_output:
            print(f"✓ LLM Judge 成功（图像大小无压缩限制）")
            print(f"  Score: {result.score:.3f}")
            return True
        elif result:
            print(f"⚠ 评估完成但未使用 LLM Judge")
            print(f"  可能因为图像过大导致LLM Judge失败")
            return False
        else:
            print(f"✗ 评估失败")
            return False

    except Exception as e:
        print(f"✗ 评估异常: {e}")
        return False


def main():
    """主测试"""
    print("\n" + "="*70)
    print("图像压缩必要性测试")
    print("="*70)
    print("\n此测试验证:")
    print("  1. 原始大小图片是否会导致503错误")
    print("  2. 图像压缩是否必需")
    print("\n开始测试...\n")

    # 测试1: 大限制（基本不压缩）
    test1_result = test_with_large_limit()

    # 测试2: Evaluator
    test2_result = test_evaluator_with_large_images()

    # 总结
    print("\n" + "="*70)
    print("测试结果总结")
    print("="*70)

    print(f"大图像API调用: {'✓ 成功' if test1_result else '✗ 失败'}")
    print(f"LLM Judge调用: {'✓ 成功' if test2_result else '✗ 失败'}")

    print("\n" + "-"*70)
    print("结论:")
    print("-"*70)

    if test1_result and test2_result:
        print("✓ 当前图片大小可以直接使用，不需要压缩")
        print("\n说明:")
        print("  - 你的测试图片都比较小")
        print("  - 但仍建议保留压缩功能作为保护措施")
        print("  - 当遇到大图片时会自动处理")
    elif not test1_result:
        print("✗ 图像压缩是必需的")
        print("\n原因:")
        print("  - 原始大小图片导致 API 返回503错误")
        print("  - 请求体超过 API 限制")
        print("\n解决方案:")
        print("  - 保持当前的图像压缩功能（max_size_mb=5.0 for LLMClient, 3.0 for Evaluator）")
        print("  - 或者预处理图像，将所有图像调整到合适大小")
    elif not test2_result:
        print("⚠ LLM Judge 需要图像压缩")
        print("\n原因:")
        print("  - LLM Judge 发送的payload包含更多上下文信息")
        print("  - 图像 + 长文本提示 = 更大的请求体")
        print("\n当前设置:")
        print("  - Evaluator 使用 max_size_mb=3.0 (更严格)")

    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    main()
