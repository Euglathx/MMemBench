"""
端到端测试 - 测试完整流程：DataProvider + UserSimulator + VLM

用法:
    python tests/test_end_to_end.py --config configs/test_config.yaml
"""

import json
import yaml
import argparse
import requests
from pathlib import Path
from typing import Dict, List


class VLMClient:
    """
    VLM客户端，支持各种API

    支持的API格式:
    1. OpenAI兼容 (GPT-4V, Qwen-VL等)
    2. 自定义HTTP接口
    """

    def __init__(self, config: Dict):
        self.api_type = config.get('api_type', 'openai')
        self.api_url = config.get('api_url')
        self.api_key = config.get('api_key')
        self.model = config.get('model', 'gpt-4-vision-preview')
        self.max_tokens = config.get('max_tokens', 500)
        self.temperature = config.get('temperature', 0.7)

    def generate(self, messages: List[Dict], image_path: str = None) -> str:
        """
        生成回复

        Args:
            messages: 对话历史，格式: [{"role": "user", "content": "..."}]
            image_path: 图片路径（如果需要）

        Returns:
            VLM的回复文本
        """
        if self.api_type == 'openai':
            return self._call_openai_api(messages, image_path)
        elif self.api_type == 'custom':
            return self._call_custom_api(messages, image_path)
        else:
            raise ValueError(f"Unknown api_type: {self.api_type}")

    def _call_openai_api(self, messages: List[Dict], image_path: str = None) -> str:
        """调用OpenAI兼容的API"""
        import base64

        # 如果有图片，添加到第一条消息
        if image_path and Path(image_path).exists():
            with open(image_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')

            # 修改第一条消息，添加图片
            if messages and messages[0]['role'] == 'user':
                messages[0]['content'] = [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_data}"
                        }
                    },
                    {
                        "type": "text",
                        "text": messages[0]['content']
                    }
                ]

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature
        }

        try:
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            return result['choices'][0]['message']['content']
        except Exception as e:
            print(f"   ✗ API调用失败: {e}")
            return f"[API Error: {e}]"

    def _call_custom_api(self, messages: List[Dict], image_path: str = None) -> str:
        """调用自定义HTTP接口"""
        # 可以根据你的具体API格式修改
        payload = {
            "messages": messages,
            "image_path": image_path,
            "model": self.model,
            "max_tokens": self.max_tokens
        }

        try:
            response = requests.post(self.api_url, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            return result.get('response', result.get('text', '[No response]'))
        except Exception as e:
            print(f"   ✗ API调用失败: {e}")
            return f"[API Error: {e}]"


def run_episode(task, vlm_client, user_simulator, max_turns, verbose=True):
    """
    运行一个完整的episode

    Args:
        task: 任务信息
        vlm_client: VLM客户端
        user_simulator: 用户模拟器
        max_turns: 最大轮次
        verbose: 是否打印详细信息

    Returns:
        episode_log: 完整的对话日志
    """
    episode_log = {
        "task": task,
        "turns": []
    }

    messages = []

    # 初始query
    initial_query = user_simulator.generate_initial_query(task)

    if verbose:
        print(f"\n   {'='*50}")
        print(f"   任务: {task['task_id']}")
        print(f"   {'='*50}")
        print(f"   [Turn 0] User: {initial_query}")

    messages.append({"role": "user", "content": initial_query})

    # 调用VLM
    vlm_response = vlm_client.generate(messages, image_path=task.get('image_path'))

    if verbose:
        print(f"   [Turn 0] VLM: {vlm_response[:200]}...")

    messages.append({"role": "assistant", "content": vlm_response})

    episode_log['turns'].append({
        "turn": 0,
        "action": "initial",
        "user_query": initial_query,
        "vlm_response": vlm_response
    })

    # 后续轮次
    for turn in range(1, max_turns + 1):
        # 选择动作
        action = user_simulator.select_action(
            turn=turn,
            vlm_response=vlm_response,
            task=task,
            history=episode_log['turns']
        )

        # 生成query
        user_query = user_simulator.generate_query(
            action_type=action,
            vlm_response=vlm_response,
            task=task,
            length='medium'
        )

        if verbose:
            print(f"   [Turn {turn}] Action: {action}")
            print(f"   [Turn {turn}] User: {user_query}")

        messages.append({"role": "user", "content": user_query})

        # 调用VLM
        vlm_response = vlm_client.generate(messages, image_path=None)  # 后续轮次不需要重复发图片

        if verbose:
            print(f"   [Turn {turn}] VLM: {vlm_response[:200]}...")

        messages.append({"role": "assistant", "content": vlm_response})

        episode_log['turns'].append({
            "turn": turn,
            "action": action,
            "user_query": user_query,
            "vlm_response": vlm_response
        })

    return episode_log


def main():
    parser = argparse.ArgumentParser(description='端到端测试')
    parser.add_argument('--config', type=str, required=True,
                       help='配置文件路径 (YAML格式)')
    parser.add_argument('--verbose', action='store_true',
                       help='打印详细信息')

    args = parser.parse_args()

    print("="*60)
    print("端到端测试")
    print("="*60)

    # 1. 加载配置
    print(f"\n1. 加载配置 from {args.config}...")
    with open(args.config, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    print(f"   ✓ 配置加载完成")
    print(f"   - 数据集: {config.get('data_dir', 'N/A')}")
    print(f"   - VLM模型: {config['vlm']['model']}")
    print(f"   - 最大轮次: {config.get('max_turns', 5)}")
    print(f"   - 允许的动作: {config.get('allowed_actions', 'all')}")

    # 2. 初始化DataProvider
    print(f"\n2. 初始化DataProvider...")
    from tests.test_data_provider import SimpleDataProvider

    if 'tasks_json' in config:
        # 直接加载已有的JSON
        with open(config['tasks_json'], 'r', encoding='utf-8') as f:
            data = json.load(f)
        tasks = data['tasks']
        print(f"   ✓ 从JSON加载了 {len(tasks)} 个任务")
    else:
        # 从数据目录加载
        provider = SimpleDataProvider(config['data_dir'])
        tasks = provider.load_tasks(max_tasks=config.get('max_tasks'))
        print(f"   ✓ 从数据目录加载了 {len(tasks)} 个任务")

    # 3. 初始化UserSimulator
    print(f"\n3. 初始化UserSimulator...")
    from tests.test_user_simulator import SimpleUserSimulator

    allowed_actions = config.get('allowed_actions')
    user_simulator = SimpleUserSimulator(allowed_actions=allowed_actions)
    print(f"   ✓ UserSimulator初始化完成")

    # 4. 初始化VLM Client
    print(f"\n4. 初始化VLM Client...")
    vlm_client = VLMClient(config['vlm'])
    print(f"   ✓ VLM Client初始化完成")

    # 5. 运行测试
    print(f"\n5. 运行测试...")
    max_turns = config.get('max_turns', 5)
    num_episodes = min(len(tasks), config.get('num_episodes', 1))

    all_logs = []

    for i in range(num_episodes):
        task = tasks[i]
        print(f"\n   Episode {i+1}/{num_episodes}")

        episode_log = run_episode(
            task=task,
            vlm_client=vlm_client,
            user_simulator=user_simulator,
            max_turns=max_turns,
            verbose=args.verbose or (i == 0)  # 至少打印第一个episode
        )

        all_logs.append(episode_log)

    # 6. 保存结果
    output_path = config.get('output', 'output/end_to_end_test.json')
    print(f"\n6. 保存结果到 {output_path}...")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    output_data = {
        "config": config,
        "episodes": all_logs
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"   ✓ 结果已保存")

    # 7. 简单统计
    print(f"\n7. 统计信息:")
    print(f"   - 总Episodes: {len(all_logs)}")
    print(f"   - 平均轮次: {sum(len(log['turns']) for log in all_logs) / len(all_logs):.1f}")

    # 动作分布
    action_counts = {}
    for log in all_logs:
        for turn in log['turns']:
            action = turn['action']
            action_counts[action] = action_counts.get(action, 0) + 1

    print(f"   - 动作分布:")
    for action, count in sorted(action_counts.items(), key=lambda x: -x[1]):
        print(f"      {action}: {count}")

    print(f"\n✓ 测试完成!")


if __name__ == "__main__":
    main()
