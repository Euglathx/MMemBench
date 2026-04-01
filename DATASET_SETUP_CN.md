# M3Bench 数据集配置指南

## 目录
- [快速开始](#快速开始)
- [数据集准备](#数据集准备)
- [配置步骤](#配置步骤)
- [运行示例](#运行示例)
- [常见问题](#常见问题)

## 快速开始

### 1. 安装依赖
```bash
pip install jsonlines
```

### 2. 准备数据集
将你的 VCR 和 MSCOCO 数据集按照下面的文件结构组织

### 3. 修改配置
编辑 `generate_tasks_example.py` 中的 `DATA_ROOT` 变量

### 4. 运行生成脚本
```bash
python generate_tasks_example.py
```

## 数据集准备

### MSCOCO 2014 数据集

**下载地址**: http://cocodataset.org/

**需要的文件**:
- `instances_train2014.json` - 目标检测标注
- `captions_train2014.json` - 图像描述标注
- `instances_val2014.json` - 验证集标注
- `captions_val2014.json` - 验证集描述
- 图片文件 (train2014/*.jpg, val2014/*.jpg)

**文件结构**:
```
{DATA_ROOT}/
└── MSCOCO14/
    ├── example/
    │   ├── instances_train2014.json
    │   ├── captions_train2014.json
    │   ├── instances_val2014.json
    │   └── captions_val2014.json
    └── train2014/  # 或者直接把图片放在 MSCOCO14/ 下
        ├── COCO_train2014_000000000001.jpg
        ├── COCO_train2014_000000000002.jpg
        └── ...
```

**标注文件格式**:
- `instances_*.json`: COCO 格式的目标检测标注，包含 `images`, `annotations`, `categories` 字段
- `captions_*.json`: COCO 格式的描述标注，包含 `images`, `annotations` 字段

### VCR (Visual Commonsense Reasoning) 数据集

**下载地址**: https://visualcommonsense.com/

**需要的文件**:
- `train.jsonl` - 训练集标注
- `val.jsonl` - 验证集标注
- `test.jsonl` - 测试集标注 (可选)
- `vcr1images/` - 图片目录
- `vcr1annots/` - 元数据目录

**文件结构**:
```
{DATA_ROOT}/
└── VisualCommenReasoning/  # 注意：目录名是 "VisualCommenReasoning"
    ├── train.jsonl
    ├── val.jsonl
    ├── test.jsonl
    ├── vcr1images/
    │   ├── movieclips_*/
    │   │   └── *.jpg
    │   └── lsmdc_*/
    │       └── *.jpg
    └── vcr1annots/
        └── *.json
```

**JSONL 格式说明**:
每一行是一个 JSON 对象，包含以下字段：
```json
{
  "annot_id": "train-0",
  "img_fn": "vcr1images/movieclips_XXX/XXX.jpg",
  "metadata_fn": "vcr1annots/XXX.json",
  "objects": ["person", "car", ...],
  "question": ["What", "is", [0], "doing", "?"],
  "answer_choices": [[...], [...], [...], [...]],
  "answer_label": 2,
  "rationale_choices": [[...], [...], [...], [...]],
  "rationale_label": 1
}
```

### Visual Genome (可选)

**下载地址**: https://visualgenome.org/

**需要的文件**:
- `scene_graphs_train.json` - 训练集场景图
- `scene_graphs_val.json` - 验证集场景图
- 图片文件

**文件结构**:
```
{DATA_ROOT}/
└── visual_genome/
    ├── scene_graphs_train.json
    ├── scene_graphs_val.json
    └── images/
        ├── 1.jpg
        ├── 2.jpg
        └── ...
```

## 配置步骤

### 步骤 1: 确定数据集根目录

假设你的数据集都存放在 `E:/Datasets/`，那么你应该有以下目录：
```
E:/Datasets/
├── MSCOCO14/
└── VisualCommenReasoning/
```

### 步骤 2: 修改配置文件

编辑 `generate_tasks_example.py`，修改第 30 行左右的 `DATA_ROOT` 变量：

```python
# 绝对路径方式
DATA_ROOT = "E:/Datasets"

# 或者相对路径方式（相对于脚本所在目录）
# DATA_ROOT = "./data"
# DATA_ROOT = "../datasets"
```

### 步骤 3: 验证配置

运行测试脚本验证数据集是否可以正常加载：

```bash
python test_dataprovider.py
```

如果看到类似以下输出，说明配置正确：
```
✓ Successfully loaded 1 MSCOCO sample(s)
✓ DataLoader tests completed
```

## 运行示例

### 基本用法

```bash
# 运行完整的任务生成流程
python generate_tasks_example.py
```

生成的任务将保存在 `generated_tasks/` 目录下：
- `vnf_mscoco.jsonl` - MSCOCO 视觉噪声过滤任务
- `vnf_vcr.jsonl` - VCR 视觉噪声过滤任务
- `abr_mscoco.jsonl` - MSCOCO 属性桥接推理任务
- `abr_vcr.jsonl` - VCR 属性桥接推理任务
- `rc_mscoco.jsonl` - MSCOCO 关系比较任务
- `sm_mscoco.jsonl` - MSCOCO 符号记忆任务

### 自定义生成

你也可以在 Python 中直接使用 API：

```python
from dataprovider import DataLoader, DataGenerator

# 初始化
loader = DataLoader(data_root="E:/Datasets")
generator = DataGenerator(loader)

# 生成特定类型的任务
tasks = generator.generate_task(
    task_type='visual_noise_filtering',
    source_dataset='mscoco14',
    num_samples=100,              # 生成 100 个样本
    n_distractor_images=5         # 每个任务 5 张干扰图片
)

# 保存结果
generator.save_generated_tasks(
    tasks,
    output_path="my_tasks.jsonl",
    format="jsonl"
)
```

### 可用的任务类型

| 任务类型 | 描述 | 支持的数据集 |
|---------|------|-------------|
| `visual_noise_filtering` | 视觉噪声过滤：从N张图片中找到包含答案的图片 | MSCOCO, VCR, Sherlock |
| `attribute_bridge_reasoning` | 属性桥接推理：通过对象属性和关系链进行多跳推理 | MSCOCO, VCR, Visual Genome |
| `relation_comparison` | 关系比较：比较多张图片中对象的关系或属性 | MSCOCO, Visual Genome |
| `symbol_memory` | 符号记忆：将图标/符号与意图关联 | MSCOCO |

### 任务参数说明

#### Visual Noise Filtering
```python
generator.generate_task(
    task_type='visual_noise_filtering',
    source_dataset='mscoco14',
    num_samples=100,                    # 生成的任务数量
    n_distractor_images=3               # 干扰图片数量 (默认: 3)
)
```

#### Attribute-Bridge Reasoning
```python
generator.generate_task(
    task_type='attribute_bridge_reasoning',
    source_dataset='mscoco14',
    num_samples=100,
    min_hops=2,                         # 最少推理跳数 (默认: 2)
    max_hops=4                          # 最多推理跳数 (默认: 4)
)
```

#### Relation Comparison
```python
generator.generate_task(
    task_type='relation_comparison',
    source_dataset='mscoco14',
    num_samples=100,
    n_images=3                          # 比较的图片数量 (默认: 3)
)
```

#### Symbol Memory
```python
generator.generate_task(
    task_type='symbol_memory',
    source_dataset='mscoco14',
    num_samples=100,
    n_symbols=5                         # 符号数量 (默认: 5)
)
```

## 常见问题

### Q1: 运行时提示 "No module named 'jsonlines'"

**解决方法**:
```bash
pip install jsonlines
```

### Q2: 提示文件不存在或数据集无法加载

**可能原因**:
1. `DATA_ROOT` 路径配置不正确
2. 数据集目录名称不匹配
3. 标注文件路径不正确

**检查步骤**:
1. 确认 `DATA_ROOT` 变量指向正确的目录
2. 确认数据集目录名为 `MSCOCO14` 和 `VisualCommenReasoning`（注意大小写）
3. 确认标注文件在 `example/` 子目录下（MSCOCO）
4. 确认 `.jsonl` 文件直接在数据集根目录下（VCR）

### Q3: 生成的任务数量少于预期

**原因**: 数据集中符合条件的样本不足

**解决方法**:
1. 减少 `num_samples` 参数
2. 降低任务难度参数（如 `n_distractor_images`, `max_hops` 等）
3. 使用完整的数据集而不是 example 子集

### Q4: 图片路径在生成的任务中不正确

**原因**:
- `image_path` 字段是根据数据集标注文件中的 `file_name` 构建的
- 需要确保标注文件中的路径与实际文件结构匹配

**示例**:
如果标注文件中 `file_name` 是 `"train2014/COCO_train2014_000000000001.jpg"`，
那么完整路径会是 `{DATA_ROOT}/MSCOCO14/train2014/COCO_train2014_000000000001.jpg`

### Q5: VCR 数据集的元数据文件找不到

**说明**:
VCR 数据集的每个样本都有一个对应的元数据文件，路径在 `.jsonl` 中的 `metadata_fn` 字段指定。

**检查**:
1. 确认 `vcr1annots/` 目录存在
2. 确认元数据 JSON 文件存在
3. 如果元数据文件不完整，代码会继续运行，只是 metadata 字段为空

### Q6: 内存不足

**原因**: 一次性加载大量数据到内存

**解决方法**:
1. 使用 `max_samples` 参数限制加载的样本数量：
```python
loader.load_dataset('mscoco14', split='train', max_samples=1000)
```

2. 分批生成任务：
```python
# 分批生成
for batch in range(10):
    tasks = generator.generate_task(
        task_type='visual_noise_filtering',
        source_dataset='mscoco14',
        num_samples=100
    )
    generator.save_generated_tasks(
        tasks,
        f"output/batch_{batch}.jsonl"
    )
```

### Q7: 如何验证生成的任务是否正确？

可以读取生成的 JSONL 文件查看：

```python
import jsonlines

with jsonlines.open('generated_tasks/vnf_mscoco.jsonl') as reader:
    for task in reader:
        print(f"Task ID: {task['task_id']}")
        print(f"Question: {task['question']}")
        print(f"Images: {task['images']}")
        print(f"Answer: {task['answer']}")
        print("-" * 50)
```

## 高级用法

### 使用过滤器

```python
# 加载数据集
data = loader.load_dataset('mscoco14', split='train')

# 过滤：只要包含 2-5 个对象的样本
filtered_data = loader.filter_by_attributes(
    data,
    filters={
        'num_objects': (2, 5)  # 范围过滤
    }
)
```

### 查询数据集信息

```python
# 获取数据集元信息
info = loader.get_dataset_info('mscoco14')
print(f"Name: {info['name']}")
print(f"Splits: {info['splits']}")
print(f"Modalities: {info['modalities']}")

# 查看支持的任务类型
tasks = generator.get_supported_tasks('mscoco14')
print(f"Supported tasks: {tasks}")
```

### 自定义输出格式

```python
# 保存为 JSON（带缩进）
generator.save_generated_tasks(
    tasks,
    output_path="output.json",
    format="json"
)

# 保存为 JSONL（每行一个 JSON）
generator.save_generated_tasks(
    tasks,
    output_path="output.jsonl",
    format="jsonl"
)
```

## 技术支持

如有问题，请查看：
1. `test_dataprovider.py` - 测试脚本示例
2. `dataprovider/loader.py` - 数据加载器源码
3. `dataprovider/generator.py` - 任务生成器源码

---

最后更新: 2025-12-25