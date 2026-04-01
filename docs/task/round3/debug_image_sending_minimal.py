"""
Minimal reproduction case for image sending issue
"""

import sys
from pathlib import Path

def test_image_path_resolution():
    """测试图像路径解析"""
    # 获取项目根目录
    script_dir = Path(__file__).parent  # round3目录
    project_root = script_dir.parent.parent.parent  # M3Bench_new目录

    # 切换到项目根目录以测试相对路径
    import os
    os.chdir(project_root)

    # 模拟task_state的images字段
    test_images = [
        "images/COCO_val2014_000000578292.jpg",
        "images/COCO_val2014_000000157269.jpg",
        "images/COCO_val2014_000000322864.jpg"
    ]

    print("Testing image path resolution...")
    print(f"Project root: {project_root}")
    print(f"Current working directory: {Path.cwd()}")
    print(f"Task images: {test_images}")
    print()

    # 测试不同的路径解析方法
    valid_images = []
    for img_rel_path in test_images:
        print(f"Testing: {img_rel_path}")

        # Method 1: Direct path
        img_path = Path(img_rel_path)
        exists_1 = img_path.exists()
        print(f"  Direct path exists: {exists_1}")
        if exists_1:
            print(f"  -> {img_path.absolute()}")
            valid_images.append(str(img_path))

        # Method 2: Try different run_XX directories
        found = False
        if not exists_1:
            generated_tasks_dir = Path("generated_tasks_v2")
            if generated_tasks_dir.exists():
                for run_dir in generated_tasks_dir.glob("run_*"):
                    potential_path = run_dir / img_rel_path
                    if potential_path.exists():
                        print(f"  ✓ Found in: {potential_path}")
                        valid_images.append(str(potential_path))
                        found = True
                        break
            else:
                print(f"  ✗ generated_tasks_v2 directory not found")

        if not found and not exists_1:
            print(f"  ❌ NOT FOUND - This would cause empty images_sent")

        print()

    print("="*60)
    print(f"Summary: {len(valid_images)}/{len(test_images)} images found")
    print(f"Valid images: {valid_images}")
    print()

    if len(valid_images) == 0:
        print("❌ ROOT CAUSE CONFIRMED: No images can be resolved")
        print("   This explains why images_sent is empty!")
    elif len(valid_images) < len(test_images):
        print("⚠️  PARTIAL FAILURE: Some images cannot be resolved")
    else:
        print("✓ All images resolved successfully")

    return valid_images

if __name__ == "__main__":
    test_image_path_resolution()
