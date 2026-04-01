"""
模拟多模型测试数据生成器

由于没有真实的API，这个脚本生成模拟的测试日志来演示完整的分析流程
"""

import json
import random
import numpy as np
from pathlib import Path
from datetime import datetime


def generate_mock_turn_data(turn_num, phase, difficulty, model_bias=0.0):
    """生成模拟的turn数据

    Args:
        turn_num: 轮次号
        phase: 阶段名称
        difficulty: 难度
        model_bias: 模型偏差（-0.2到0.2，影响所有评分）
    """
    # 基础分数随难度下降
    base_score = max(0.1, 0.9 - difficulty * 0.1 - turn_num * 0.02)

    # 添加模型偏差和随机噪声
    score = np.clip(base_score + model_bias + np.random.normal(0, 0.1), 0, 1)

    # 其他维度分数
    scores = {
        'score': float(score),
        'faithfulness_score': float(np.clip(score + np.random.normal(0.05, 0.1), 0, 1)),
        'robustness_score': float(np.clip(score + np.random.normal(0.1, 0.08), 0, 1)),
        'consistency_score': float(np.clip(score + np.random.normal(0, 0.15), 0, 1)),
        'memory_retention_score': float(np.clip(score - turn_num * 0.03 + np.random.normal(0, 0.1), 0, 1)),
        'cross_image_confusion_score': float(np.clip(0.95 + np.random.normal(0, 0.05), 0, 1)),
        'disambiguation_score': float(np.clip(0.92 + np.random.normal(0, 0.05), 0, 1)),
        'level_passed': bool(score > 0.5),
        'reasoning': f"Score: {score:.3f}"
    }

    return {
        'turn': turn_num,
        'phase': phase,
        'difficulty': difficulty,
        'action': random.choice(['guidance', 'follow_up', 'fine_grained', 'memory_test']),
        'message': f"Turn {turn_num} message",
        'response': f"Turn {turn_num} response",
        'evaluation': scores,
        'images_sent': []
    }


def generate_mock_log(task_id, task_type, dataset, num_turns=25, model_bias=0.0):
    """生成模拟的完整日志"""
    phases = ['entity_grounding', 'chain_navigation', 'chain_verification',
              'noise_during_reasoning', 'final_answer']

    events = []

    # Task start event
    events.append({
        'event': 'task_start',
        'timestamp': datetime.now().isoformat(),
        'data': {
            'task_id': task_id,
            'task_type': task_type,
            'question': f"Mock question for {task_id}",
            'expected_answer': f"Mock answer",
            'images': [f"image_{task_id}.jpg"]
        }
    })

    # Turn events
    for turn_num in range(1, num_turns + 1):
        phase = phases[min(turn_num // 5, len(phases) - 1)]
        difficulty = min(1 + turn_num // 8, 3)

        events.append({
            'event': 'turn',
            'timestamp': datetime.now().isoformat(),
            'data': generate_mock_turn_data(turn_num, phase, difficulty, model_bias)
        })

        # 每5轮添加一个filler turn
        if turn_num % 5 == 0:
            events.append({
                'event': 'filler_turn',
                'timestamp': datetime.now().isoformat(),
                'data': {
                    'filler_index': turn_num // 5,
                    'user_message': f"Filler {turn_num}",
                    'model_response': "Response",
                    'topic': 'extended_question',
                    'response_length': random.randint(100, 500)
                }
            })

    return events


def generate_model_logs(model_name, model_bias, output_dir, num_tasks=25):
    """为单个模型生成多个日志文件"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    task_types = ['attribute_bridge_reasoning', 'attribute_comparison',
                  'visual_noise_filtering', 'relation_comparison']
    datasets = ['mscoco', 'vcr']

    for i in range(num_tasks):
        task_type = task_types[i % len(task_types)]
        dataset = datasets[i % len(datasets)]
        task_id = f"{task_type[:3]}_{dataset}_{i}"

        log_file = output_path / f"run_log_{task_id}.json"

        # 生成25-35轮的对话
        num_turns = random.randint(25, 35)
        events = generate_mock_log(task_id, task_type, dataset, num_turns, model_bias)

        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(events, f, indent=2, ensure_ascii=False)

    print(f"✓ 为 {model_name} 生成了 {num_tasks} 个日志文件")
    return output_path


def main():
    """生成所有模型的模拟数据"""
    print("="*80)
    print("生成模拟测试数据")
    print("="*80 + "\n")

    # 模型配置：名称 -> (偏差, 任务数)
    # 偏差: 正值表示更好的性能，负值表示更差
    models = {
        'gpt-5': (0.15, 25),              # 最好的模型
        'gemini-2.5-pro': (0.08, 25),     # 第二好
        'gemini-2.5-flash': (-0.05, 25),  # 中等
        'kimi-k2.5': (-0.12, 25)          # 较差
    }

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    results = {}
    for model_name, (bias, num_tasks) in models.items():
        print(f"\n生成 {model_name} 的测试数据 (偏差={bias:+.2f})...")
        output_dir = f"simulator_test_log/mock_{model_name}_{timestamp}"
        path = generate_model_logs(model_name, bias, output_dir, num_tasks)
        results[model_name] = str(path)

    print("\n" + "="*80)
    print("所有模拟数据已生成!")
    print("="*80 + "\n")

    print("生成的日志位置:")
    for model_name, path in results.items():
        print(f"  {model_name}: {path}")

    print("\n下一步:")
    print("  运行分析脚本:")
    for model_name, path in results.items():
        print(f'    python run_analysis.py --log-dir "{path}" --model-name "{model_name}"')

    return results


if __name__ == "__main__":
    results = main()
