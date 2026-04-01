"""
测试DataProvider - 独立测试数据加载和Scene Graph构建

用法:
    python tests/test_data_provider.py --data_dir data/sample --output output/data_provider_test.json
"""

import os
import json
import argparse
from pathlib import Path


class SimpleDataProvider:
    """
    简化的DataProvider，用于测试

    输入格式: 一个文件夹，包含
    - images/ (图片文件)
    - queries.json (问题列表)
    - scene_graphs.json (可选，如果没有则不使用scene graph)
    """

    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.images_dir = self.data_dir / "images"
        self.queries_file = self.data_dir / "queries.json"
        self.scene_graphs_file = self.data_dir / "scene_graphs.json"

        # 加载queries
        if not self.queries_file.exists():
            raise FileNotFoundError(f"queries.json not found in {data_dir}")

        with open(self.queries_file, 'r', encoding='utf-8') as f:
            self.queries = json.load(f)

        # 加载scene graphs (可选)
        self.scene_graphs = None
        if self.scene_graphs_file.exists():
            with open(self.scene_graphs_file, 'r', encoding='utf-8') as f:
                self.scene_graphs = json.load(f)
            print(f"✓ Loaded {len(self.scene_graphs)} scene graphs")
        else:
            print("⚠ No scene_graphs.json found, will skip scene graph features")

    def load_tasks(self, split="all", max_tasks=None):
        """
        加载任务列表

        Args:
            split: "all", "train", "test" (如果queries.json中有split字段)
            max_tasks: 最多加载多少个任务

        Returns:
            List of tasks, 每个task格式:
            {
                "task_id": str,
                "image_path": str,
                "question": str,
                "scene_graph": dict (可选),
                "ground_truth": dict (可选)
            }
        """
        tasks = []

        for i, query_item in enumerate(self.queries):
            # 检查split
            if split != "all":
                if "split" in query_item and query_item["split"] != split:
                    continue

            task_id = query_item.get("id", f"task_{i}")
            image_file = query_item.get("image", f"{task_id}.jpg")
            image_path = str(self.images_dir / image_file)

            # 检查图片是否存在
            if not Path(image_path).exists():
                print(f"⚠ Warning: Image not found: {image_path}")

            task = {
                "task_id": task_id,
                "image_path": image_path,
                "question": query_item["question"],
            }

            # 添加ground truth (如果有)
            if "answer" in query_item:
                task["ground_truth"] = {
                    "answer": query_item["answer"]
                }

            # 添加scene graph (如果有)
            if self.scene_graphs and task_id in self.scene_graphs:
                task["scene_graph"] = self.scene_graphs[task_id]

            # 添加任务类型 (如果有)
            if "task_type" in query_item:
                task["task_type"] = query_item["task_type"]

            tasks.append(task)

            # 限制数量
            if max_tasks and len(tasks) >= max_tasks:
                break

        return tasks

    def export_to_json(self, output_path: str, split="all", max_tasks=None):
        """导出为JSON文件，供其他测试使用"""
        tasks = self.load_tasks(split=split, max_tasks=max_tasks)

        output = {
            "metadata": {
                "data_dir": str(self.data_dir),
                "split": split,
                "total_tasks": len(tasks),
                "has_scene_graphs": self.scene_graphs is not None
            },
            "tasks": tasks
        }

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        print(f"\n✓ Exported {len(tasks)} tasks to {output_path}")
        return output


def main():
    parser = argparse.ArgumentParser(description='测试DataProvider')
    parser.add_argument('--data_dir', type=str, required=True,
                       help='数据目录路径')
    parser.add_argument('--output', type=str, default='output/data_provider_test.json',
                       help='输出JSON文件路径')
    parser.add_argument('--split', type=str, default='all',
                       choices=['all', 'train', 'test'],
                       help='数据集划分')
    parser.add_argument('--max_tasks', type=int, default=None,
                       help='最多加载多少个任务')

    args = parser.parse_args()

    print("="*60)
    print("测试DataProvider")
    print("="*60)

    # 初始化DataProvider
    print(f"\n1. 加载数据 from {args.data_dir}...")
    provider = SimpleDataProvider(args.data_dir)

    # 加载任务
    print(f"\n2. 解析任务 (split={args.split}, max_tasks={args.max_tasks})...")
    tasks = provider.load_tasks(split=args.split, max_tasks=args.max_tasks)

    # 打印统计
    print(f"\n3. 任务统计:")
    print(f"   - 总任务数: {len(tasks)}")

    task_types = {}
    has_scene_graph = 0
    has_ground_truth = 0

    for task in tasks:
        # 统计任务类型
        task_type = task.get("task_type", "unknown")
        task_types[task_type] = task_types.get(task_type, 0) + 1

        if "scene_graph" in task:
            has_scene_graph += 1
        if "ground_truth" in task:
            has_ground_truth += 1

    print(f"   - 任务类型分布: {task_types}")
    print(f"   - 包含Scene Graph: {has_scene_graph}/{len(tasks)}")
    print(f"   - 包含Ground Truth: {has_ground_truth}/{len(tasks)}")

    # 打印示例
    if tasks:
        print(f"\n4. 示例任务:")
        example = tasks[0]
        print(f"   Task ID: {example['task_id']}")
        print(f"   Image: {example['image_path']}")
        print(f"   Question: {example['question']}")
        if "scene_graph" in example:
            sg = example["scene_graph"]
            print(f"   Scene Graph: {len(sg.get('objects', []))} objects, {len(sg.get('relations', []))} relations")
        if "ground_truth" in example:
            print(f"   Ground Truth: {example['ground_truth']['answer'][:100]}...")

    # 导出
    print(f"\n5. 导出JSON...")
    provider.export_to_json(args.output, split=args.split, max_tasks=args.max_tasks)

    print(f"\n✓ 测试完成!")
    print(f"  JSON文件已保存到: {args.output}")
    print(f"  可以使用该文件进行UserSimulator测试")


if __name__ == "__main__":
    main()
