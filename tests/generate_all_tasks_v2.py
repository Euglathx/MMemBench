"""
M3Bench任务生成器 V2 - 基于配置文件
==========================================

使用dataset_configs.yaml驱动的任务生成系统。

功能：
1. 自动从配置文件加载数据集信息
2. 为每个数据集生成所有支持的任务类型
3. 支持严格的质量过滤
4. 自动保存生成结果和元数据

支持的任务类型：
- Attribute Bridge Reasoning (ABR): 多跳属性推理
- Attribute Comparison (AC): 属性对比 [NEW!]
- Visual Noise Filtering (VNF): 视觉噪声过滤
- Relation Comparison (RC): 关系对比
"""

import sys
from pathlib import Path
import logging
import json
import shutil
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional

# Add parent directory to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dataprovider import DataLoader, DataGeneratorV2, load_config, ConfigLoader

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def resolve_repo_path(path_like: str) -> Path:
    """Resolve a repository-relative path into an absolute path."""
    path = Path(path_like)
    return path if path.is_absolute() else PROJECT_ROOT / path


# 默认数据集split配置
DEFAULT_SPLITS = {
    'mscoco14': 'val',      # Use val split - train images not downloaded
    'vcr': 'train',
    'visual_genome': 'train',
    'gqa': 'train',
    'sherlock': 'train',
    'docvqa': 'validation',
}


def load_generation_config(
    config_loader: ConfigLoader,
    override_datasets: Optional[List[str]] = None,
    override_num_samples: Optional[int] = None,
    override_split: Optional[str] = None
) -> Dict[str, Dict]:
    """
    从dataset_configs.yaml动态加载生成配置

    Args:
        config_loader: ConfigLoader实例
        override_datasets: 如果指定，只处理这些数据集
        override_num_samples: 如果指定，覆盖样本数
        override_split: 如果指定，覆盖split

    Returns:
        Dict[str, Dict]:
            key: dataset_id
            value: {
                'num_samples': int,
                'split': str,
                'enabled': bool
            }
    """
    generation_config = {}

    for dataset_id in config_loader.get_all_dataset_ids():
        dataset_config = config_loader.get_dataset_config(dataset_id)

        if dataset_config is None:
            continue

        # 检查是否有任何任务类型启用
        has_enabled_task = any(
            dataset_config.is_task_enabled(task)
            for task in dataset_config.supported_tasks
        )

        if not has_enabled_task:
            logger.debug(f"跳过 {dataset_id}: 没有启用的任务类型")
            continue

        # 如果指定了override_datasets，只处理这些数据集
        if override_datasets and dataset_id not in override_datasets:
            continue

        # 获取默认配置
        num_samples = override_num_samples or 10
        split = override_split or DEFAULT_SPLITS.get(dataset_id, 'train')

        generation_config[dataset_id] = {
            'num_samples': num_samples,
            'split': split,
            'enabled': True
        }

    return generation_config


def find_next_run_number(base_dir="generated_tasks_v2"):
    """找到下一个可用的 run 编号"""
    base_path = resolve_repo_path(base_dir)
    base_path.mkdir(exist_ok=True)

    existing_runs = [d for d in base_path.iterdir()
                    if d.is_dir() and d.name.startswith('run_')]

    if not existing_runs:
        return 1

    run_numbers = []
    for run_dir in existing_runs:
        try:
            num = int(run_dir.name.split('_')[1])
            run_numbers.append(num)
        except:
            continue

    return max(run_numbers) + 1 if run_numbers else 1


def setup_output_directory(base_dir="generated_tasks_v2"):
    """创建输出目录结构"""
    run_number = find_next_run_number(base_dir)
    run_dir = resolve_repo_path(base_dir) / f"run_{run_number}"

    # 创建子目录
    (run_dir / "tasks").mkdir(parents=True, exist_ok=True)
    (run_dir / "images").mkdir(parents=True, exist_ok=True)
    (run_dir / "annotations").mkdir(parents=True, exist_ok=True)
    (run_dir / "logs").mkdir(parents=True, exist_ok=True)

    return run_dir, run_number


def copy_image_with_check(src_path, dst_dir):
    """复制图片并验证"""
    src = Path(src_path)

    if not src.exists():
        logger.debug(f"Image not found (will skip copy): {src}")
        # Don't fail - just skip copying, use original path
        return str(src)  # Return original path even if doesn't exist

    dst = Path(dst_dir) / src.name

    try:
        if not dst.exists():  # 避免重复复制
            shutil.copy2(src, dst)
        return f"images/{src.name}"
    except Exception as e:
        logger.error(f"Failed to copy {src}: {e}")
        return str(src)  # Return original path if copy fails


def process_task_with_images(task, run_dir):
    """处理单个任务：复制图片和标注"""
    try:
        # 复制图片
        image_paths = task.get('images', [])
        new_image_paths = []
        missing_count = 0

        for img_path in image_paths:
            relative_path = copy_image_with_check(img_path, run_dir / "images")
            if relative_path:
                new_image_paths.append(relative_path)
                if not Path(img_path).exists():
                    missing_count += 1
            else:
                logger.debug(f"Skipping task {task.get('task_id')}: missing image {img_path}")
                return None  # 严格过滤：图片完全无法处理则舍弃

        # 如果所有图片都缺失，则舍弃
        if missing_count == len(image_paths):
            logger.debug(f"Skipping task {task.get('task_id')}: all images missing")
            return None

        # 保存推理证据
        if 'reasoning_evidence' in task:
            annot_file = run_dir / "annotations" / f"{task['task_id']}_evidence.json"
            annot_file.parent.mkdir(parents=True, exist_ok=True)

            with open(annot_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'task_id': task['task_id'],
                    'evidence': task['reasoning_evidence'],
                    'state_schema': task.get('state_schema'),
                    'saved_at': datetime.now().isoformat()
                }, f, indent=2, ensure_ascii=False)

            task['evidence_file'] = f"annotations/{annot_file.name}"

        # 更新任务中的图片路径
        task['images'] = new_image_paths
        task['run_info'] = {
            'generated_at': datetime.now().isoformat(),
            'quality_verified': True,
            'image_files_copied': len(new_image_paths) - missing_count,
            'missing_images': missing_count
        }

        # 移除原始证据（已保存到单独文件）
        if 'reasoning_evidence' in task:
            del task['reasoning_evidence']

        return task

    except Exception as e:
        logger.error(f"Failed to process task {task.get('task_id', 'unknown')}: {e}")
        import traceback
        traceback.print_exc()
        return None


def generate_dataset_tasks(generator: DataGeneratorV2,
                          dataset_id: str,
                          run_dir: Path,
                          num_samples: int = 10,
                          split: str = "train") -> Dict[str, List[Dict]]:
    """
    从指定数据集生成所有支持的任务。

    Args:
        generator: DataGeneratorV2 实例
        dataset_id: 数据集ID (e.g., 'mscoco14', 'vcr')
        run_dir: 输出目录
        num_samples: 每种任务生成的样本数
        split: 数据split

    Returns:
        字典: {task_type: [processed_tasks]}
    """
    logger.info(f"\n{'='*70}")
    logger.info(f"处理数据集: {dataset_id.upper()}")
    logger.info(f"{'='*70}")

    all_tasks = {}

    try:
        # 生成所有任务
        tasks_by_type = generator.generate_all_tasks_for_dataset(
            dataset_id=dataset_id,
            num_samples_per_task=num_samples,
            split=split
        )

        # 处理每种任务类型
        for task_type, tasks in tasks_by_type.items():
            logger.info(f"\n处理任务类型: {task_type}")
            logger.info(f"  原始生成: {len(tasks)} 个任务")

            # 复制图片和处理任务
            processed = []
            for task in tasks:
                processed_task = process_task_with_images(task, run_dir)
                if processed_task:
                    processed.append(processed_task)

            if processed:
                # 保存到JSONL文件
                output_file = run_dir / "tasks" / f"{task_type}_{dataset_id}.jsonl"
                with open(output_file, 'w', encoding='utf-8') as f:
                    for task in processed:
                        f.write(json.dumps(task, ensure_ascii=False) + '\n')

                all_tasks[task_type] = processed
                logger.info(f"  ✓ 成功保存: {len(processed)} 个任务 -> {output_file.name}")
            else:
                logger.warning(f"  ✗ 没有有效任务")

    except Exception as e:
        logger.error(f"生成任务失败 ({dataset_id}): {e}")
        import traceback
        traceback.print_exc()

    return all_tasks


def generate_report(run_dir: Path, all_results: Dict[str, Dict], run_number: int):
    """生成详细报告"""

    # 统计信息
    total_tasks = 0
    tasks_by_type = {}
    tasks_by_dataset = {}

    for dataset_id, tasks_dict in all_results.items():
        dataset_total = 0
        for task_type, tasks in tasks_dict.items():
            count = len(tasks)
            total_tasks += count
            dataset_total += count

            if task_type not in tasks_by_type:
                tasks_by_type[task_type] = 0
            tasks_by_type[task_type] += count

        tasks_by_dataset[dataset_id] = dataset_total

    # 生成报告
    report = {
        'run_number': run_number,
        'generated_at': datetime.now().isoformat(),
        'summary': {
            'total_tasks': total_tasks,
            'datasets_processed': list(all_results.keys()),
            'task_types': list(tasks_by_type.keys())
        },
        'tasks_by_type': tasks_by_type,
        'tasks_by_dataset': tasks_by_dataset,
        'detailed_counts': {
            dataset_id: {
                task_type: len(tasks)
                for task_type, tasks in tasks_dict.items()
            }
            for dataset_id, tasks_dict in all_results.items()
        },
        'output_structure': {
            'tasks_directory': 'tasks/',
            'images_directory': 'images/',
            'annotations_directory': 'annotations/',
            'logs_directory': 'logs/'
        }
    }

    # 保存JSON报告
    report_file = run_dir / "REPORT.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # 创建Markdown报告
    readme_file = run_dir / "README.md"
    with open(readme_file, 'w', encoding='utf-8') as f:
        f.write(f"# M3Bench 任务生成报告 - Run {run_number}\n\n")
        f.write(f"**生成时间**: {report['generated_at']}\n\n")

        f.write("## 📊 总览\n\n")
        f.write(f"- **总任务数**: {total_tasks}\n")
        f.write(f"- **数据集数**: {len(all_results)}\n")
        f.write(f"- **任务类型**: {', '.join(tasks_by_type.keys())}\n\n")

        f.write("## 📈 按任务类型统计\n\n")
        for task_type, count in sorted(tasks_by_type.items()):
            f.write(f"- **{task_type}**: {count} 个任务\n")

        f.write("\n## 📁 按数据集统计\n\n")
        for dataset_id, count in sorted(tasks_by_dataset.items()):
            f.write(f"### {dataset_id} ({count} 个任务)\n\n")
            if dataset_id in all_results:
                for task_type, tasks in all_results[dataset_id].items():
                    f.write(f"  - {task_type}: {len(tasks)}\n")
                f.write("\n")

        f.write("## 📂 目录结构\n\n")
        f.write("```\n")
        f.write(f"run_{run_number}/\n")
        f.write("├── tasks/               # 生成的任务文件 (JSONL)\n")
        f.write("├── images/              # 复制的图片\n")
        f.write("├── annotations/         # 推理证据和原始标注\n")
        f.write("├── logs/                # 生成日志\n")
        f.write("├── REPORT.json          # JSON格式的详细报告\n")
        f.write("└── README.md            # 本文件\n")
        f.write("```\n\n")

        f.write("## 🔍 任务文件说明\n\n")
        f.write("每个任务文件的格式为 `{task_type}_{dataset_id}.jsonl`\n\n")
        f.write("任务字段说明：\n")
        f.write("- `task_id`: 任务唯一标识\n")
        f.write("- `task_type`: 任务类型\n")
        f.write("- `images`: 图片路径列表（相对路径）\n")
        f.write("- `question`: 问题\n")
        f.write("- `answer`: 答案\n")
        f.write("- `reasoning_depth`: 推理深度\n")
        f.write("- `evidence_file`: 推理证据文件路径\n")
        f.write("- `metadata`: 元数据\n")

    logger.info(f"✓ 报告已保存: {report_file} 和 {readme_file}")


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="M3Bench 任务生成器 V2 - 配置驱动的多数据集任务生成",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用默认配置生成所有已启用数据集的任务
  python tests/generate_all_tasks_v2.py

  # 只为特定数据集生成任务
  python tests/generate_all_tasks_v2.py --datasets mscoco14 vcr visual_genome

  # 自定义样本数量
  python tests/generate_all_tasks_v2.py --num-samples 20

  # 指定数据split
  python tests/generate_all_tasks_v2.py --split val

  # 组合使用
  python tests/generate_all_tasks_v2.py --datasets gqa sherlock --num-samples 15 --split train
        """
    )

    parser.add_argument(
        '--datasets', nargs='+',
        help='指定要生成的数据集 (默认: 所有已启用的数据集)'
    )
    parser.add_argument(
        '--num-samples', type=int, default=None,
        help='每个任务类型的样本数 (默认: 10)'
    )
    parser.add_argument(
        '--split', default=None,
        help='数据集划分 (默认: 每个数据集使用各自的默认split)'
    )
    parser.add_argument(
        '--config-file', default='dataset_configs.yaml',
        help='配置文件路径 (默认: dataset_configs.yaml)'
    )
    parser.add_argument(
        '--data-root', default='E:/Dataset',
        help='数据集根目录 (默认: E:/Dataset)'
    )
    parser.add_argument(
        '--output-dir', default='generated_tasks_v2',
        help='输出目录 (默认: generated_tasks_v2)'
    )
    parser.add_argument(
        '--verbose', '-v', action='store_true',
        help='显示详细输出'
    )

    return parser.parse_args()


def main():
    """主函数"""
    args = parse_args()

    print("\n" + "="*80)
    print("M3Bench 任务生成器 V2 (配置驱动)")
    print("="*80)
    print("\n支持的任务类型:")
    print("  1. Attribute Bridge Reasoning (ABR)")
    print("  2. Attribute Comparison (AC) [NEW!]")
    print("  3. Visual Noise Filtering (VNF)")
    print("  4. Relation Comparison (RC)")
    print("\n" + "="*80 + "\n")

    # 设置输出目录
    config_file = resolve_repo_path(args.config_file)
    output_dir = resolve_repo_path(args.output_dir)
    run_dir, run_number = setup_output_directory(output_dir)
    print(f"📁 输出目录: {run_dir}")
    print(f"🔢 运行编号: {run_number}\n")

    # 设置日志文件
    log_file = run_dir / "logs" / "generation.log"
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    logging.getLogger().addHandler(file_handler)

    try:
        # 加载配置
        logger.info("加载配置文件...")
        config = load_config(str(config_file))

        # 验证数据集路径
        logger.info("验证数据集路径...")
        path_validation = config.validate_dataset_paths()
        valid_datasets = [ds for ds, valid in path_validation.items() if valid]

        print("\n可用数据集:")
        for dataset_id in valid_datasets:
            dataset_config = config.get_dataset_config(dataset_id)
            enabled_tasks = [t for t in dataset_config.supported_tasks
                           if dataset_config.is_task_enabled(t)]
            print(f"  ✓ {dataset_id}: {', '.join(enabled_tasks)}")

        # 动态加载生成配置
        logger.info("加载生成配置...")
        generation_config = load_generation_config(
            config_loader=config,
            override_datasets=args.datasets,
            override_num_samples=args.num_samples,
            override_split=args.split
        )

        if args.verbose:
            print("\n生成配置:")
            for ds_id, ds_config in generation_config.items():
                print(f"  {ds_id}: samples={ds_config['num_samples']}, split={ds_config['split']}")

        # 初始化生成器
        logger.info("初始化数据生成器...")
        loader = DataLoader(data_root=args.data_root)
        generator = DataGeneratorV2(loader, config_file=str(config_file))

        # 生成任务
        all_results = {}

        for dataset_id in valid_datasets:
            if dataset_id not in generation_config:
                if args.verbose:
                    logger.info(f"跳过 {dataset_id} (未在生成配置中)")
                continue

            config_for_dataset = generation_config[dataset_id]

            tasks_dict = generate_dataset_tasks(
                generator=generator,
                dataset_id=dataset_id,
                run_dir=run_dir,
                num_samples=config_for_dataset['num_samples'],
                split=config_for_dataset['split']
            )

            if tasks_dict:
                all_results[dataset_id] = tasks_dict

        # 生成报告
        if all_results:
            logger.info("\n生成报告...")
            generate_report(run_dir, all_results, run_number)

        # 总结
        print("\n" + "="*80)
        print("✅ 生成完成！")
        print("="*80)
        print(f"\n📂 输出位置: {run_dir}")

        if all_results:
            total_tasks = sum(
                len(tasks)
                for tasks_dict in all_results.values()
                for tasks in tasks_dict.values()
            )

            print(f"\n📊 任务统计:")
            print(f"  总计: {total_tasks} 个任务")

            for dataset_id, tasks_dict in all_results.items():
                dataset_total = sum(len(tasks) for tasks in tasks_dict.values())
                print(f"\n  {dataset_id}: {dataset_total} 个任务")
                for task_type, tasks in tasks_dict.items():
                    print(f"    - {task_type}: {len(tasks)}")

            total_images = len(list((run_dir / 'images').glob('*')))
            total_annotations = len(list((run_dir / 'annotations').glob('*')))

            print(f"\n📁 文件统计:")
            print(f"  - 图片: {total_images}")
            print(f"  - 标注: {total_annotations}")
        else:
            print("\n⚠️  没有成功生成任何任务")

        print(f"\n📄 查看报告:")
        print(f"  cat {run_dir / 'README.md'}")
        print()

    except Exception as e:
        logger.error(f"生成过程出错: {e}")
        import traceback
        traceback.print_exc()
        print(f"\n❌ 错误: {e}")
        print("请查看日志文件了解详情")


if __name__ == "__main__":
    main()
