# M3Bench 集成测试完成状态与后续任务规划

**日期**: 2026-01-26
**版本**: v0.7.0
**状态**: ✅ 所有任务已完成

---

## 一、当前完成状态总结

### ✅ 已完成的工作

#### 1. 任务ID全局唯一性修复
- **问题**: 之前不同run中的任务ID存在重复（如 `ac_mscoco_0`, `ac_mscoco_1`）
- **解决方案**: 创建了全局唯一ID生成器
  - 新ID格式: `{type}_{dataset}_{timestamp}_{random}_{seq}`
  - 示例: `ac_mscoco_1769393592_ysty_001`
- **修改的文件**:
  - `dataprovider/task_id_generator.py` (新增)
  - `dataprovider/task_generators.py` (修改)
  - `dataprovider/rationale_based_generator.py` (修改)
  - `dataprovider/mantis_loader.py` (修改)
  - `dataprovider/__init__.py` (更新导出)

#### 2. 集成测试
- **测试文件**: `tests/test_integration.py`
- **测试覆盖**: 8项核心功能，全部通过
  - Task ID唯一性 ✅
  - DataProvider导入 ✅
  - Simulator导入 ✅
  - Length Selector (窗口3) ✅
  - UserSimulator ✅
  - BatchTaskSimulator ✅
  - QueryGenerator ✅
  - 端到端流程 ✅

#### 3. 批量数据生成
- **输出目录**: `generated_tasks_v2/run_18/`
- **数据量**: 138个任务
  - MSCOCO14: 70个 (35 AC + 35 VNF)
  - VCR: 68个 (33 Rationale-based ABR + 35 AC)
- **任务ID**: 全部唯一，已验证

#### 4. Simulator批处理日志
- **输出文件**: `batch_test_results/batch_results_20260126_102200.json`
- **测试规模**:
  - 10批次，每批5个任务
  - 总计50个任务，372轮对话
  - 包含自然过渡和跨任务记忆测试

---

## 二、待解决的问题

### ✅ 问题1: 缺少实际VLM对话日志 (已解决)

**问题描述**:
`batch_test_results/batch_results_20260126_102200.json` 中只包含模拟的打分数据，没有真实的VLM对话内容（query和response）。

**原因分析**:
`BatchTaskSimulator` 使用的是mock LLM client，不会真正调用VLM，只生成随机分数。

**定位**:
- 文件: `src/simulator/batch_task_simulator.py`
- 行数: 334-399 (方法 `_run_single_task_in_batch`)
- 问题代码:
```python
# 模拟分数，没有真实对话
'scores': {
    'correctness': random.uniform(0.7, 1.0),
    ...
}
```

**需要**:
- 真正调用 `StrategicSimulator` 执行完整对话流程
- 保存每轮的 user_query 和 vlm_response
- 生成标准的 `run_log_*.json` 格式日志

**相关文件**:
- `src/simulator/strategic_simulator.py` - 实际执行对话的模拟器
- `simulator_test_log/run_log_*.json` - 正确格式的日志示例

---

### ✅ 问题2: 数据集支持范围受限 (已解决)

**问题描述**:
虽然 `dataset_configs.yaml` 中配置了多个数据集，但实际只生成了 MSCOCO14 和 VCR 的数据。

**配置文件位置**: `dataset_configs.yaml`

**已配置但未生成的数据集**:
- Visual Genome (已配置，路径有效)
- Sherlock
- DocVQA
- GQA (路径无效)
- MM-NIAH (路径无效)
- MMMU (路径无效)

**问题定位**:

1. **缺少 generator.py 模块**:
   - ABR 和 RC 任务生成依赖 `dataprovider/generator.py`
   - 该文件不存在，导致报错:
   ```python
   ModuleNotFoundError: No module named 'dataprovider.generator'
   ```
   - 影响文件: `dataprovider/generator_v2.py` 行218, 245

2. **Visual Genome AC 未实现**:
   - `task_generators.py` 中 `AttributeComparisonGenerator.generate_from_vcr()` 存在
   - 但没有 `generate_from_visual_genome()` 方法

3. **VCR VNF 依赖缺失**:
   - `EnhancedVNFGenerator.generate_from_vcr()` 依赖 `generator.py`
   - 行579: `from dataprovider.generator import DataGenerator`

**解决方向**:
- Option A: 移植 `generator.py` 中的方法到 `generator_v2.py`
- Option B: 在 `task_generators.py` 中实现缺失的生成方法
- Option C: 禁用依赖缺失的任务类型

---

### ✅ 问题3: Human Annotation模块适配 (已解决)

**问题描述**:
现有的 annotation 工具期望从 `simulator_test_log/run_log_*.json` 读取数据，但当前的批处理结果格式不同。

**现有文件**:
- `tools/extract_annotation_samples.py` - 从 run_log 抽取样本
- `tools/prepare_annotation.py` - 准备标注环境
- `simulator_test_log/run_log_*.json` - 旧格式日志（存在）

**格式差异**:

**旧格式 (run_log)**: 事件流，包含详细对话
```json
{
  "event": "target_model_response",
  "turn": 5,
  "target_response": "实际VLM回复...",
  "images_sent": [...],
  "evaluation": {...}
}
```

**新格式 (batch_results)**: 聚合结果，只有分数
```json
{
  "task_id": "ac_mscoco_...",
  "turns_used": 8,
  "scores": {
    "correctness": 0.88,
    ...
  }
}
```

**缺失内容**:
- 每轮的 user query
- 每轮的 VLM response
- Action type 信息
- Evaluation details

**适配策略**:
1. 修复问题1后，生成标准的 run_log
2. 或者修改 `extract_annotation_samples.py` 支持新格式
3. 或者创建格式转换脚本

---

## 三、关键文件和接口说明

### 核心模块

#### 1. 数据生成模块
```
dataprovider/
├── generator_v2.py          # 主生成器（配置驱动）
├── task_generators.py       # AC和VNF生成器
├── rationale_based_generator.py  # 窗口2: Rationale-based ABR
├── task_id_generator.py     # 任务ID生成器（新增）
├── loader.py                # 数据集加载器
└── config_loader.py         # 配置文件解析器
```

**关键接口**:
```python
from dataprovider import DataGeneratorV2, TaskIDGenerator

# 生成任务
gen = DataGeneratorV2(data_loader, config_file="dataset_configs.yaml")
tasks = gen.generate_task(
    task_type='attribute_comparison',
    source_dataset='mscoco14',
    num_samples=100
)

# 生成唯一ID
id_gen = TaskIDGenerator(task_type='attribute_comparison', dataset='mscoco14')
task_id = id_gen.next()  # ac_mscoco_1769393592_ysty_001
```

#### 2. 模拟器模块
```
src/simulator/
├── strategic_simulator.py      # 单任务战略模拟器
├── batch_task_simulator.py     # 批处理模拟器
├── user_simulator.py           # 用户行为模拟（窗口3）
├── query_generator.py          # Query生成器
├── length_selector.py          # 长度控制（窗口3）
├── llm_client.py              # LLM客户端接口
└── evaluator.py               # 评估器
```

**关键接口**:
```python
from src.simulator import BatchTaskSimulator, BatchConfig, LLMClient, Evaluator

# 批处理配置
config = BatchConfig(
    max_turns_per_session=50,
    min_turns_per_task=5,
    max_turns_per_task=10,
    transition_style="natural"
)

# 运行批处理
batch_sim = BatchTaskSimulator(llm_client, evaluator, config)
result = batch_sim.run_batch(tasks)
```

#### 3. Human Annotation模块
```
tools/
├── extract_annotation_samples.py  # 抽取标注样本
├── prepare_annotation.py          # 准备标注环境
└── validate_evaluation.py         # 验证标注结果
```

### 配置文件

#### dataset_configs.yaml
- **位置**: 项目根目录
- **作用**: 定义数据集路径、splits、支持的任务类型等
- **关键配置**:
```yaml
datasets:
  mscoco14:
    path: "E:/Dataset/MSCOCO/MSCOCO14"
    supported_tasks:
      - attribute_comparison
      - visual_noise_filtering
      - attribute_bridge_reasoning
      - relation_comparison
    task_configs:
      attribute_comparison:
        enabled: true
        n_images: 3
```

### 数据输出目录

```
M3Bench_new/
├── generated_tasks_v2/
│   └── run_18/                    # 最新生成的任务
│       ├── tasks/
│       │   ├── attribute_comparison_mscoco14.jsonl  # 35个AC任务
│       │   ├── attribute_comparison_vcr.jsonl       # 35个AC任务
│       │   ├── rationale_based_abr_vcr.jsonl        # 33个ABR任务
│       │   └── visual_noise_filtering_mscoco14.jsonl # 35个VNF任务
│       ├── images/                # 复制的图片文件
│       ├── annotations/           # 证据文件
│       ├── REPORT.json
│       └── README.md
│
├── batch_test_results/
│   └── batch_results_20260126_102200.json  # 批处理结果（无实际对话）
│
├── simulator_test_log/            # 旧格式日志（有实际对话）
│   ├── run_log_20260119_094231.json
│   └── ...
│
└── human_annotations/             # 人类标注输出目录
    ├── annotation_samples.jsonl   # 待标注样本
    ├── annotation_template.xlsx   # Excel标注模板
    └── annotation_results.jsonl   # 标注结果
```

---

## 四、后续任务详细规划

### 任务A: 生成真实VLM对话日志 ✅ **已完成**

**目标**: 让批处理测试生成包含实际对话内容的 run_log 格式日志

**步骤**:

1. **修改 BatchTaskSimulator**
   - 文件: `src/simulator/batch_task_simulator.py`
   - 方法: `_run_single_task_in_batch` (行293-399)

   当前代码:
   ```python
   # 简化处理，返回模拟分数
   task_report = {
       'scores': {
           'correctness': random.uniform(0.7, 1.0),
           ...
       }
   }
   ```

   修改为:
   ```python
   # 实际调用 StrategicSimulator
   simulator = StrategicSimulator(llm_client, evaluator, **kwargs)

   # 注入session上下文
   self._inject_session_context(simulator)

   # 运行任务，获取完整日志
   result = simulator.run_task(
       task=task,
       save_log=True,
       log_dir="batch_simulator_logs"
   )

   # 提取日志事件
   conversation_events = result.get('events', [])
   ```

2. **调整日志保存**
   - 在 `batch_test_results/` 中保存聚合报告（现有格式）
   - 在 `simulator_test_log/batch_run_{timestamp}/` 中保存详细对话日志
   - 每个批次一个子目录，包含该批次所有任务的 run_log

3. **验证输出**
   ```bash
   python run_batch_test.py \
       --task-files "generated_tasks_v2/run_18/tasks/*.jsonl" \
       --tasks-per-batch 5 \
       --num-batches 3 \
       --verbose

   # 检查输出
   ls simulator_test_log/batch_run_*/
   # 应该看到: run_log_task_001.json, run_log_task_002.json, ...
   ```

**预期输出**:
```
simulator_test_log/
└── batch_run_20260126_123456/
    ├── run_log_ac_mscoco_1769393592_ysty_001.json
    ├── run_log_ac_mscoco_1769393592_ysty_002.json
    └── ...
```

**测试脚本**:
```python
# test_batch_with_real_logs.py
import json
from pathlib import Path

log_dir = Path("simulator_test_log/batch_run_20260126_123456")
log_files = list(log_dir.glob("run_log_*.json"))

print(f"Found {len(log_files)} log files")

for log_file in log_files[:3]:
    with open(log_file) as f:
        events = json.load(f)

    # 检查是否有真实对话
    has_response = any(e.get('event') == 'target_model_response' for e in events)
    print(f"{log_file.name}: has_response={has_response}")
```

**参考文件**:
- `src/simulator/strategic_simulator.py` - 已有完整实现
- `simulator_test_log/run_log_20260119_094231.json` - 正确格式示例

---

### 任务B: 扩展数据集支持 ✅ **已完成**

**目标**: 修复数据集生成问题，支持更多数据集

#### B1: 修复依赖缺失（ABR/RC生成器）

**Option 1: 移植方法** (推荐)

1. 检查是否有备份的 `generator.py`
   ```bash
   find . -name "generator.py" -o -name "generator.py.bak"
   ```

2. 如果有，提取需要的方法:
   - `_abr_from_mscoco()`
   - `_abr_from_vcr()`
   - `_abr_from_visual_genome()`
   - `_rc_from_mscoco()`
   - `_rc_from_visual_genome()`
   - `_vcr_tokens_to_text()` (VCR text处理)

3. 将方法移植到 `generator_v2.py`:
   ```python
   # generator_v2.py
   def _generate_attribute_bridge_reasoning(self, ...):
       if source_dataset == "mscoco14":
           return self._abr_from_mscoco(source_data, ...)
       ...

   def _abr_from_mscoco(self, source_data, num_samples, min_hops, max_hops):
       # 移植的代码
       ...
   ```

**Option 2: 简化实现** (快速但功能受限)

在 `task_generators.py` 中添加简化版生成器:
```python
class ABRGenerator:
    @staticmethod
    def generate_from_mscoco_simple(source_data, num_samples, task_config):
        """简化的ABR生成（不依赖旧generator）"""
        # 基于spatial relations的简单实现
        ...
```

#### B2: 实现 Visual Genome 支持

1. 在 `task_generators.py` 添加:
   ```python
   @staticmethod
   def generate_from_visual_genome(source_data, num_samples, task_config, templates):
       """Generate AC from Visual Genome"""
       id_gen = TaskIDGenerator('attribute_comparison', 'visual_genome')

       # Visual Genome有丰富的attributes
       # 可以直接比较object的attribute
       ...
   ```

2. 在 `generator_v2.py` 中启用:
   ```python
   def _generate_attribute_comparison(self, ...):
       ...
       elif source_dataset == "visual_genome":
           return AttributeComparisonGenerator.generate_from_visual_genome(...)
   ```

#### B3: 测试多数据集生成

```bash
# 生成多数据集任务
python generate_all_tasks_v2.py \
    --datasets mscoco14 vcr visual_genome sherlock \
    --num-samples 30 \
    --verbose

# 检查输出
ls generated_tasks_v2/run_*/tasks/
```

**验证清单**:
- [ ] MSCOCO14: AC, VNF, ABR, RC
- [ ] VCR: AC, VNF, Rationale-based ABR
- [ ] Visual Genome: AC, ABR, RC
- [ ] Sherlock: AC, VNF
- [ ] 所有任务ID唯一

---

### 任务C: 适配Human Annotation模块 ✅ **已完成**

**目标**: 让现有的annotation工具能够处理新的批处理日志

#### C1: 创建格式转换脚本

```python
# tools/convert_batch_results_to_runlog.py
"""
将batch_results格式转换为run_log格式
"""

import json
from pathlib import Path
from datetime import datetime

def convert_batch_result_to_events(batch_result):
    """转换单个batch结果为事件流"""
    events = []

    # 添加batch_start事件
    events.append({
        "event": "batch_start",
        "batch_id": batch_result['batch_id'],
        "timestamp": batch_result['start_time']
    })

    # 处理每个任务
    for task_result in batch_result['task_results']:
        # task_start
        events.append({
            "event": "task_start",
            "task_id": task_result['task_id'],
            "task_type": task_result['task_type'],
            "question": task_result['question'],
            "expected_answer": task_result['expected_answer'],
            "images": task_result['images']
        })

        # 如果有对话日志，添加turn事件
        if 'turns' in task_result:
            for turn in task_result['turns']:
                # user_query
                events.append({
                    "event": "core_model_decision",
                    "turn": turn['turn'],
                    "action": turn['action'],
                    "message_to_model": turn['query']
                })

                # vlm_response
                events.append({
                    "event": "target_model_response",
                    "turn": turn['turn'],
                    "target_response": turn['response'],
                    "images_sent": turn.get('images_sent', []),
                    "evaluation": turn.get('evaluation', {})
                })

        # task_end
        events.append({
            "event": "task_end",
            "task_id": task_result['task_id'],
            "completed": task_result['completed'],
            "scores": task_result['scores']
        })

    return events

def main():
    input_file = Path("batch_test_results/batch_results_20260126_102200.json")
    output_dir = Path("simulator_test_log/converted/")
    output_dir.mkdir(exist_ok=True)

    with open(input_file) as f:
        data = json.load(f)

    for i, batch_result in enumerate(data['results']):
        events = convert_batch_result_to_events(batch_result)

        output_file = output_dir / f"run_log_batch_{i+1}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(events, f, indent=2, ensure_ascii=False)

        print(f"Converted batch {i+1} -> {output_file}")

if __name__ == "__main__":
    main()
```

#### C2: 修改 extract_annotation_samples.py

添加对新格式的支持:
```python
# 在 load_all_logs() 中添加
def load_all_logs(log_dir: str) -> List[Dict]:
    """加载所有日志文件（支持多种格式）"""
    log_path = Path(log_dir)
    all_samples = []

    # 加载标准 run_log
    for log_file in log_path.glob("run_log_*.json"):
        samples = extract_samples_from_log(...)
        all_samples.extend(samples)

    # 加载 batch_results（如果有详细对话）
    batch_dir = Path("batch_test_results")
    if batch_dir.exists():
        for batch_file in batch_dir.glob("batch_results_*.json"):
            samples = extract_samples_from_batch_result(...)
            all_samples.extend(samples)

    return all_samples
```

#### C3: 生成标注文件

```bash
# 1. 先完成任务A，生成真实对话日志

# 2. 抽取标注样本
python tools/extract_annotation_samples.py

# 3. 准备标注环境
python tools/prepare_annotation.py

# 4. 检查输出
ls human_annotations/
# 应该看到:
# - annotation_samples.jsonl
# - annotation_template.xlsx
```

---

## 五、执行建议

### 优先级排序

1. **任务A** (必须先做)
   - 影响任务C
   - 生成真实可用的对话日志
   - 预计时间: 2-3小时

2. **任务B** (可并行)
   - 扩展系统能力
   - 不阻塞其他任务
   - 预计时间: 4-6小时

3. **任务C** (依赖任务A)
   - 完善标注流程
   - 预计时间: 1-2小时

### 调试技巧

#### 快速验证任务ID唯一性
```bash
cd generated_tasks_v2/run_18/tasks
python -c "
import json
ids = []
for f in ['*.jsonl']:
    for line in open(f):
        ids.append(json.loads(line)['task_id'])
print(f'Total: {len(ids)}, Unique: {len(set(ids))}')
"
```

#### 检查日志格式
```bash
# 查看日志结构
python -c "
import json
with open('simulator_test_log/run_log_20260119_094231.json') as f:
    events = json.load(f)
print(f'Events: {len(events)}')
print(f'Event types: {set(e["event"] for e in events)}')
"
```

#### 验证数据集配置
```bash
python -c "
from dataprovider import ConfigLoader
config = ConfigLoader('dataset_configs.yaml')
print('Available datasets:', config.get_all_dataset_ids())
print('Valid paths:', config.validate_dataset_paths())
"
```

---

## 六、关键API参考

### TaskIDGenerator
```python
from dataprovider import TaskIDGenerator, reset_counters

# 单次生成
task_id = generate_task_id('attribute_comparison', 'mscoco14')

# 批量生成
gen = TaskIDGenerator('attribute_comparison', 'mscoco14')
for i in range(100):
    task_id = gen.next()

# 重置计数器（新批次）
reset_counters()
```

### BatchTaskSimulator
```python
from src.simulator import BatchTaskSimulator, BatchConfig

config = BatchConfig(
    max_turns_per_session=50,
    min_turns_per_task=5,
    max_turns_per_task=10,
    transition_style="natural",  # "natural" | "abrupt" | "contextual"
    enable_cross_task_memory_test=True,
    cross_task_memory_interval=3
)

simulator = BatchTaskSimulator(llm_client, evaluator, config, verbose=True)
result = simulator.run_batch(tasks)

# 访问结果
print(f"Completed: {result.tasks_completed}/{result.tasks_attempted}")
print(f"Total turns: {result.total_turns}")
print(f"Aggregate scores: {result.aggregate_scores}")
```

### DataGeneratorV2
```python
from dataprovider import DataLoader, DataGeneratorV2

loader = DataLoader()
gen = DataGeneratorV2(loader, config_file="dataset_configs.yaml")

# 生成单个任务类型
tasks = gen.generate_task(
    task_type='attribute_comparison',
    source_dataset='mscoco14',
    num_samples=100,
    split='val'
)

# 生成数据集的所有任务
all_tasks = gen.generate_all_tasks_for_dataset(
    dataset_id='mscoco14',
    num_samples_per_task=50,
    split='val'
)
```

---

## 七、联系信息与资源

### 文档
- 窗口1需求: `docs/task/TASK_WINDOW_1_DATA_AND_BATCH.md`
- 窗口2需求: `docs/task/TASK_WINDOW_2_VCR_AND_REASONING.md`
- 窗口3需求: `docs/task/TASK_WINDOW_3_PROMPT_AND_LENGTH.md`

### 测试
- 集成测试: `tests/test_integration.py`
- 运行: `python tests/test_integration.py`

### 数据
- 配置: `dataset_configs.yaml`
- 任务输出: `generated_tasks_v2/run_18/`
- 批处理日志: `batch_test_results/`
- 旧格式日志: `simulator_test_log/`

---

**版本历史**:
- v0.7.0 (2026-01-26): ✅ 所有任务完成
  - 任务A: BatchTaskSimulator现在调用StrategicSimulator生成真实对话日志
  - 任务B: 创建了generator.py模块，修复了依赖缺失，支持Visual Genome
  - 任务C: 创建了格式转换脚本，更新了extract_annotation_samples.py
- v0.6.0 (2026-01-26): 任务ID唯一性修复，集成测试通过
- v0.5.0 (之前): 窗口2功能完成（Rationale-based ABR）

---

## 八、v0.7.0 更新摘要

### 新增文件
1. `dataprovider/generator.py` - 基础数据生成器，包含:
   - `_vcr_tokens_to_text()`: VCR token格式转换
   - `_abr_from_mscoco()`, `_abr_from_vcr()`, `_abr_from_visual_genome()`: ABR任务生成
   - `_rc_from_mscoco()`, `_rc_from_visual_genome()`: RC任务生成
   - `_determine_spatial_relation()`: 空间关系判断

2. `tools/convert_batch_results_to_runlog.py` - 格式转换脚本

3. `test_batch_with_real_logs.py` - 测试脚本

### 修改的文件
1. `src/simulator/batch_task_simulator.py`:
   - `_run_single_task_in_batch()`: 现在调用StrategicSimulator执行真实对话
   - 新增 `_save_task_run_log()`: 保存详细run_log
   - 新增 `_format_run_log()`: 格式化日志为标准格式
   - 新增 `get_batch_log_dir()`: 获取日志目录

2. `dataprovider/task_generators.py`:
   - 新增 `AttributeComparisonGenerator.generate_from_visual_genome()`

3. `dataprovider/generator_v2.py`:
   - 更新 `_generate_attribute_comparison()` 支持 visual_genome

4. `dataprovider/__init__.py`:
   - 导出 `DataGenerator` 和 `vcr_tokens_to_text`

5. `tools/extract_annotation_samples.py`:
   - 更新 `load_all_logs()` 支持多种日志格式
   - 新增 `extract_samples_from_batch_result()` 直接解析batch格式
