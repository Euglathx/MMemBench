# Task 1C: 修复响应截断问题

## 任务优先级
**P0 - Week 1 Day 1**

## 可以并行
✅ 可以与 Task 1A, 1B 同时进行
✅ 最简单的任务，1-2小时完成

## 任务目标
修复target model响应在800 tokens处被截断的问题，确保模型能完整表达推理过程。

---

## 问题现状

### 实际截断示例
从 `simulator_test_log/run_log_20251231_070855.json` Line 267:

```json
{
  "target_response": "Let me take another careful look to be absolutely sure.\n\nI'm comparing the vertical position of the topmost part of the person (their head/helmet) relative to the top edge of the image frame in both pictures.\n\n1.  **Image 1 (Motorcycle):** Look at the top of the red helmet. There is a significant amount of space (sky and background foliage) between the top of the helmet and the top edge of the picture. The top of the helmet is roughly near the vertical center of the image, maybe just slightly above the middle.\n\n2.  **Image 2 (Elephant):** Look at the top of the person's head. It is positioned very close to the top edge of the picture. There is very little space between"
}
```

**问题**: 句子在"between"后直接截断，没有结尾。

### 根本原因
在 `src/simulator/strategic_simulator.py:669`:
```python
target_response = self.llm_client.call_target_model(
    messages=target_messages,
    images=images_to_send if images_to_send else None,
    max_tokens=800  # ← 这里！太小了
)
```

### 量化指标
- **当前**: max_tokens=800，导致复杂推理被截断
- **目标**: max_tokens=2048，足够完整表达
- **预期成本增加**: ~2.5x tokens，但确保质量

---

## 需要修改的文件

### 唯一文件: `src/simulator/strategic_simulator.py`

需要修改所有 `call_target_model()` 调用处的 `max_tokens` 参数。

#### 位置1: Line 669 (主要的step调用)
```python
# BEFORE
target_response = self.llm_client.call_target_model(
    messages=target_messages,
    images=images_to_send if images_to_send else None,
    max_tokens=800
)

# AFTER
target_response = self.llm_client.call_target_model(
    messages=target_messages,
    images=images_to_send if images_to_send else None,
    max_tokens=2048  # Increased to allow complete reasoning
)
```

#### 位置2: Line 806 (consistency check)
```python
# 查找类似的调用
response = self.llm_client.call_target_model(
    messages=[...],
    max_tokens=???  # 检查这里
)
```

#### 位置3: Line 1144 (如果存在)
#### 位置4: Line 1227 (如果存在)
#### 位置5: Line 1296 (如果存在)

**统一修改策略**:
```python
# 所有target model调用都用2048
max_tokens=2048
```

---

## 完整修改清单

使用grep查找所有需要修改的位置:
```bash
cd src/simulator
grep -n "call_target_model" strategic_simulator.py
```

预期输出:
```
666:        target_response = self.llm_client.call_target_model(
806:        response = self.llm_client.call_target_model(
1144:        response = self.llm_client.call_target_model(
1227:        response = self.llm_client.call_target_model(
1296:        response = self.llm_client.call_target_model(
```

对每一处:
1. 定位到该行
2. 检查是否有 `max_tokens` 参数
3. 如果有且 <2048，改为2048
4. 如果没有，添加 `max_tokens=2048`

---

## 接口定义

### 无接口变更
这是纯参数调整，不改变任何函数签名或返回值。

### 配置文件支持（可选，建议添加）
```python
# src/simulator/strategic_simulator.py

class StrategicSimulator:
    def __init__(
        self,
        # ... existing params ...
        target_max_tokens: int = 2048,  # NEW: configurable
    ):
        """
        Args:
            target_max_tokens: Max tokens for target model responses.
                Default 2048. Increase for complex reasoning tasks.
        """
        self.target_max_tokens = target_max_tokens
        # ...

    def step(self):
        # ...
        target_response = self.llm_client.call_target_model(
            messages=target_messages,
            images=images_to_send if images_to_send else None,
            max_tokens=self.target_max_tokens  # Use configured value
        )
```

这样可以在运行时调整:
```bash
python run_experiment.py --target-max-tokens 4096  # 对于特别复杂的任务
```

---

## 测试验证

### 验证脚本
```python
# tools/check_truncation.py
import json
import re
from pathlib import Path

def is_truncated(text: str) -> bool:
    """Check if text appears to be truncated."""
    # Ends without proper punctuation
    if not text.strip():
        return False

    last_char = text.strip()[-1]
    if last_char not in '.!?。！？':
        # Check if it's a complete thought
        # Truncated often ends mid-word or mid-sentence
        if re.search(r'\w$', text):  # Ends with letter/number
            return True
    return False

def check_log(log_path: Path):
    with open(log_path) as f:
        events = json.load(f)

    truncated_count = 0
    total_responses = 0

    for event in events:
        if event.get('event') == 'target_model_response':
            total_responses += 1
            response = event.get('target_response', '')

            if is_truncated(response):
                truncated_count += 1
                print(f"  Turn {event.get('turn')}: TRUNCATED")
                print(f"    Last 100 chars: ...{response[-100:]}")
                print()

    print(f"File: {log_path.name}")
    print(f"  Total responses: {total_responses}")
    print(f"  Truncated: {truncated_count}")
    print(f"  Rate: {truncated_count/total_responses*100:.1f}%")
    print(f"  Target: 0%")
    print(f"  Status: {'✓ PASS' if truncated_count == 0 else '✗ FAIL'}")

if __name__ == "__main__":
    import sys
    check_log(Path(sys.argv[1]))
```

### 运行测试
```bash
# Run experiment with fix
python run_experiment.py \
  --model gpt-4o \
  --task-file generated_tasks_v2/run_18/tasks/attribute_comparison_mscoco14.jsonl \
  --num-tasks 5 \
  --output-dir test_output/task_1c

# Check for truncation
python tools/check_truncation.py test_output/task_1c/run_log_*.json

# Should show: Truncated: 0, Rate: 0%
```

### 对比测试
```bash
# Before fix (800 tokens) - using old code
git stash  # Save current changes
python run_experiment.py ... --output-dir test_output/before_fix
git stash pop

# After fix (2048 tokens)
python run_experiment.py ... --output-dir test_output/after_fix

# Compare
python tools/check_truncation.py test_output/before_fix/run_log_*.json
python tools/check_truncation.py test_output/after_fix/run_log_*.json
```

### 成功标准
- [ ] 截断率 = 0%
- [ ] 所有响应以正确标点结尾
- [ ] 平均响应长度增加（说明模型能完整表达）
- [ ] Token使用量增加但仍在预算内

---

## 协作要求

### 对其他任务的影响
**所有任务**:
✅ 完整的响应有助于所有后续分析
✅ 特别是Task 2（评估系统）能更准确评分

### 需要其他任务提供
❌ 无依赖，可立即开始

### 提供给其他任务
✅ 完整、未截断的模型响应
✅ 更准确的评估数据

---

## 实现建议

### 快速实现方案（推荐）
如果只是简单修复，直接改5处调用即可：

```bash
# 1. 查找所有位置
grep -n "max_tokens=" src/simulator/strategic_simulator.py | grep call_target_model

# 2. 批量替换
sed -i 's/max_tokens=800/max_tokens=2048/g' src/simulator/strategic_simulator.py
sed -i 's/max_tokens=1000/max_tokens=2048/g' src/simulator/strategic_simulator.py

# 3. 验证
grep -n "max_tokens=" src/simulator/strategic_simulator.py | grep call_target_model
# 应该都显示2048
```

### 完整实现方案（建议）
添加配置支持，便于后续调整：

**Step 1**: 修改 `__init__`
```python
def __init__(self, ..., target_max_tokens: int = 2048):
    self.target_max_tokens = target_max_tokens
```

**Step 2**: 替换所有硬编码的800/1000
```python
# 查找replace:
max_tokens=800  →  max_tokens=self.target_max_tokens
max_tokens=1000 →  max_tokens=self.target_max_tokens
```

**Step 3**: 添加CLI参数（如果修改 `run_experiment.py`）
```python
parser.add_argument(
    '--target-max-tokens',
    type=int,
    default=2048,
    help='Max tokens for target model responses'
)

simulator = StrategicSimulator(
    ...,
    target_max_tokens=args.target_max_tokens
)
```

---

## 成本影响分析

### Token使用预估
假设:
- 当前: 平均每响应 ~600 tokens（因800截断）
- 修复后: 平均每响应 ~1200 tokens（完整表达）

**成本影响**:
- GPT-4o: ~$0.015/1k tokens → 每响应增加 $0.009
- 10任务 × 平均8轮 = 80响应 → 增加 ~$0.72
- 可接受范围内

### 优化建议
如果成本是问题，可以差异化设置：

```python
# 简单任务用较小值
simple_task_tokens = 1024

# 复杂推理用大值
complex_task_tokens = 2048

# 根据任务类型动态选择
if task_type in ["attribute_comparison", "visual_noise_filtering"]:
    max_tokens = simple_task_tokens
else:  # reasoning tasks
    max_tokens = complex_task_tokens
```

---

## 预期工作量
- **代码修改**: 5-10 lines（如果只改参数）
- **代码修改**: ~50 lines（如果添加配置支持）
- **验证脚本**: ~40 lines
- **测试时间**: 1 hour
- **总时间**: 2-4 hours
- **可并行**: 100%（与所有其他Task独立）

---

## 快速检查清单

修改前检查:
- [ ] 备份当前代码: `git stash` 或 `cp strategic_simulator.py strategic_simulator.py.bak`
- [ ] 确认所有 `call_target_model()` 位置

修改后检查:
- [ ] 所有位置都已更新为2048
- [ ] 代码能正常运行（无语法错误）
- [ ] 运行一次测试，检查响应是否完整

提交前检查:
- [ ] 运行truncation检查脚本
- [ ] 确认0%截断率
- [ ] 检查token使用量在预算内
