"""
示例：如何使用Mantis-Instruct数据集
展示如何加载和使用已验证完整的数据集
"""

from pathlib import Path
import zipfile
import json

def load_mantis_dataset(dataset_root, dataset_name, split='train'):
    """
    加载Mantis-Instruct数据集

    Args:
        dataset_root: 数据集根目录 (F:/datasets/TIGER-Lab_Mantis-Instruct)
        dataset_name: 数据集名称 (如 'birds-to-words', 'chartqa', 'star')
        split: 'train' 或 'val'

    Returns:
        parquet_path: parquet文件路径
        zip_path: zip文件路径
    """
    dataset_path = Path(dataset_root) / dataset_name

    # 查找parquet文件
    parquet_files = list(dataset_path.glob(f'{split}-*.parquet'))
    if not parquet_files:
        raise FileNotFoundError(f"未找到 {split} 的parquet文件")

    # 查找zip文件
    zip_path = dataset_path / f'{split}_images.zip'
    if not zip_path.exists():
        raise FileNotFoundError(f"未找到 {split}_images.zip")

    return parquet_files[0], zip_path


def read_parquet_metadata(parquet_file):
    """
    读取parquet文件的元数据
    需要安装: pip install pyarrow pandas
    """
    try:
        import pandas as pd
        df = pd.read_parquet(parquet_file)
        return df
    except ImportError:
        print("需要安装 pandas 和 pyarrow: pip install pandas pyarrow")
        return None


def extract_image_from_zip(zip_path, image_name, output_dir=None):
    """
    从zip文件中提取单个图片

    Args:
        zip_path: zip文件路径
        image_name: 图片文件名
        output_dir: 输出目录（可选，如果不指定则返回字节数据）

    Returns:
        如果指定output_dir，返回保存的文件路径；否则返回图片字节数据
    """
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        if output_dir:
            output_path = Path(output_dir) / image_name
            zip_ref.extract(image_name, output_dir)
            return output_path
        else:
            return zip_ref.read(image_name)


def list_available_datasets(dataset_root):
    """列出所有可用的数据集"""
    root = Path(dataset_root)

    # 已验证完整的数据集
    verified_complete = ['birds-to-words', 'chartqa', 'star']

    print("=" * 80)
    print("✅ 已验证完整的数据集（推荐使用）:")
    print("=" * 80)

    for dataset in verified_complete:
        dataset_path = root / dataset
        if dataset_path.exists():
            parquet_files = list(dataset_path.glob('*.parquet'))
            zip_files = list(dataset_path.glob('*.zip'))

            print(f"\n📁 {dataset}/")
            print(f"   Parquet文件: {len(parquet_files)}")
            print(f"   Zip文件: {len(zip_files)}")

            for pf in parquet_files:
                size_mb = pf.stat().st_size / (1024 * 1024)
                print(f"   - {pf.name}: {size_mb:.2f} MB")

            for zf in zip_files:
                size_mb = zf.stat().st_size / (1024 * 1024)
                print(f"   - {zf.name}: {size_mb:.2f} MB")


def usage_example():
    """使用示例"""
    print("\n" + "=" * 80)
    print("📖 使用示例")
    print("=" * 80)

    print("""
# 1. 列出可用数据集
from mantis_dataset_loader import list_available_datasets
list_available_datasets('F:/datasets/TIGER-Lab_Mantis-Instruct')

# 2. 加载数据集
from mantis_dataset_loader import load_mantis_dataset, read_parquet_metadata

parquet_path, zip_path = load_mantis_dataset(
    'F:/datasets/TIGER-Lab_Mantis-Instruct',
    'birds-to-words',
    split='train'
)

# 3. 读取元数据
df = read_parquet_metadata(parquet_path)
print(f"数据集大小: {len(df)} 条")
print(f"列名: {df.columns.tolist()}")

# 4. 访问单条数据
sample = df.iloc[0]
print(sample)

# 5. 从zip中提取图片
from mantis_dataset_loader import extract_image_from_zip

# 假设parquet中有图片文件名字段
image_name = sample['image']  # 根据实际字段名调整
image_bytes = extract_image_from_zip(zip_path, image_name)

# 或者保存到文件
output_path = extract_image_from_zip(zip_path, image_name, output_dir='./images')

# 6. 使用PIL加载图片
from PIL import Image
import io
img = Image.open(io.BytesIO(image_bytes))
img.show()
""")


if __name__ == "__main__":
    dataset_root = r"F:\datasets\TIGER-Lab_Mantis-Instruct"

    print("🔍 Mantis-Instruct 数据集加载器")

    # 列出可用数据集
    list_available_datasets(dataset_root)

    # 显示使用示例
    usage_example()

    print("\n" + "=" * 80)
    print("💡 提示:")
    print("=" * 80)
    print("1. 推荐使用已验证完整的数据集: birds-to-words, chartqa, star")
    print("2. 这些数据集的zip文件已通过完整性测试")
    print("3. 可以直接用于训练和测试")
    print("4. 如需使用其他数据集，请先重新下载损坏的zip文件")
