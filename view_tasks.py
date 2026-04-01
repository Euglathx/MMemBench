"""
查看生成的任务内容
"""

import json
import jsonlines
from pathlib import Path

def view_task_file(file_path, max_tasks=3):
    """查看任务文件内容"""
    file_path = Path(file_path)

    if not file_path.exists():
        print(f"文件不存在: {file_path}")
        return

    print("\n" + "="*70)
    print(f"文件: {file_path.name}")
    print("="*70)

    tasks = []
    with jsonlines.open(file_path) as reader:
        for task in reader:
            tasks.append(task)

    print(f"\n总任务数: {len(tasks)}")

    # 显示前几个任务
    for i, task in enumerate(tasks[:max_tasks]):
        print(f"\n{'-'*70}")
        print(f"任务 {i+1}/{len(tasks)}")
        print(f"{'-'*70}")

        print(f"任务ID: {task['task_id']}")
        print(f"任务类型: {task['task_type']}")

        if task['task_type'] == 'visual_noise_filtering':
            print(f"\n问题: {task['question']}")
            print(f"答案: {task['answer']}")
            print(f"正确图片索引: {task['target_image_idx']}")
            print(f"\n图片列表 ({len(task['images'])} 张):")
            for j, img in enumerate(task['images']):
                marker = " ✓" if j == task['target_image_idx'] else ""
                print(f"  [{j}] {Path(img).name}{marker}")

        elif task['task_type'] == 'attribute_bridge_reasoning':
            print(f"\n问题: {task['question']}")
            print(f"答案: {task['answer']}")
            print(f"推理深度: {task['reasoning_depth']}")

            formal = task['formal_representation']
            print(f"\n形式化表示:")
            print(f"  对象: {list(formal['objects'].values())}")
            print(f"  属性数量: {len(formal['attributes'])}")
            print(f"  关系数量: {len(formal['relations'])}")

            if formal['relations']:
                print(f"\n  关系链:")
                for rel in formal['relations']:
                    subj = formal['objects'][rel['subject']]
                    obj = formal['objects'][rel['object']]
                    print(f"    {subj} --[{rel['predicate']}]--> {obj}")

        elif task['task_type'] == 'relation_comparison':
            print(f"\n问题: {task['question']}")
            print(f"答案: {task['answer']}")
            print(f"比较目标: {task['comparison_target']}")
            print(f"\n比较的图片 ({len(task['images'])} 张):")
            for j, img in enumerate(task['images']):
                print(f"  [{j}] {Path(img).name}")

        elif task['task_type'] == 'symbol_memory':
            print(f"\n问题: {task['question']}")
            print(f"答案: {task['answer']}")
            print(f"\n符号映射 ({len(task['symbol_mappings'])} 个):")
            for mapping in task['symbol_mappings']:
                print(f"  • {mapping['symbol_name']}: {mapping['intent']}")
                print(f"    图片: {Path(mapping['symbol_image']).name}")

        # 显示元数据
        if 'metadata' in task:
            print(f"\n元数据:")
            for key, value in task['metadata'].items():
                print(f"  {key}: {value}")

    if len(tasks) > max_tasks:
        print(f"\n... (还有 {len(tasks) - max_tasks} 个任务未显示)")

    print("\n" + "="*70)

def main():
    """主函数"""
    output_dir = Path("generated_tasks")

    if not output_dir.exists():
        print(f"输出目录不存在: {output_dir}")
        return

    # 查找所有生成的任务文件
    task_files = list(output_dir.glob("*.jsonl"))

    if not task_files:
        print(f"没有找到任务文件在: {output_dir}")
        return

    print("\n" + "="*70)
    print("M3Bench 生成任务查看器")
    print("="*70)
    print(f"\n找到 {len(task_files)} 个任务文件:")
    for i, f in enumerate(task_files, 1):
        size = f.stat().st_size
        print(f"  {i}. {f.name} ({size:,} bytes)")

    # 逐个显示文件内容
    for task_file in sorted(task_files):
        view_task_file(task_file, max_tasks=2)

    print("\n提示:")
    print("  - 可以修改 max_tasks 参数来显示更多任务")
    print("  - 任务文件采用 JSONL 格式（每行一个 JSON）")
    print()

if __name__ == "__main__":
    main()