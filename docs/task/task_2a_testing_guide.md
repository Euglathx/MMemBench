# Task 2A Testing Guide

## 完成的修改

所有4个修改已按照 `task_2a_evaluation_fix.md` 的要求完成:

### ✅ 修改1: 给Judge传图像
**文件**: `src/simulator/evaluator.py`
**位置**: Lines 396-433 (`_call_llm_judge` 方法)

**更改**:
- 添加了 `_encode_image()` 方法用于Base64编码图像
- 修改 `_call_llm_judge()` 接收 `task` 参数
- 构建多模态 `user_content`,包含文本和图像
- 修改 `evaluate_response()` 传递 `task` 参数

**影响**:
- LLM Judge现在可以看到实际图像,能够验证视觉claims
- 非多模态模型的幻觉会被检测出来

---

### ✅ 修改2: 严格的默认分数
**文件**: `src/simulator/evaluator.py`
**位置**: Lines 552-561

**更改**:
```python
# OLD (宽松的默认值)
scores = {
    "correctness": 0.5,
    "faithfulness": 0.8,
    "robustness": 1.0,
    "consistency": 1.0,
    "memory_retention": 1.0,
    "cross_image_confusion": 1.0,
    "disambiguation": 1.0
}

# NEW (严格的默认值)
scores = {
    "correctness": 0.1,           # ↓ 0.5 → 0.1
    "faithfulness": 0.2,          # ↓ 0.8 → 0.2
    "robustness": 0.3,            # ↓ 1.0 → 0.3
    "consistency": 0.3,           # ↓ 1.0 → 0.3
    "memory_retention": 0.3,
    "cross_image_confusion": 0.3, # ↓ 1.0 → 0.3
    "disambiguation": 0.3         # ↓ 1.0 → 0.3
}
```

**影响**:
- 模型必须明确证明能力才能获得高分
- 非多模态模型的默认分数将很低 (<0.3)

---

### ✅ 修改3: 强化Robustness检测
**文件**: `src/simulator/evaluator.py`
**位置**: Lines 620-649

**更改**:
- 添加了 `visual_grounding_phrases` 列表检测
- 要求同时满足:
  1. 抵抗误导信息 (`resisted`)
  2. 提供视觉grounding证据 (`has_visual_grounding`)
- 评分逻辑:
  - 两者都满足: `1.0`
  - 仅抵抗但无视觉证据: `0.6` (部分分数)
  - 接受误导: `0.1`
  - 其他: `0.3`

**影响**:
- 非多模态模型即使"抵抗"误导,但无视觉grounding也只能得0.6
- 真正的多模态模型需要明确提到"in the image", "looking at"等

---

### ✅ 修改4: 更新Judge Prompt
**文件**: `src/simulator/evaluator.py`
**位置**: Lines 116-142

**新增内容**:
```
CRITICAL: You MUST verify all claims against the actual images provided.
- **Correctness**: Check if the response matches what's VISIBLE in the images
- **Faithfulness**: Penalize ANY claim not grounded in the provided images
- **Visual Grounding**: If the model cannot see images but makes specific visual claims, score Faithfulness as 0
- **Non-Multimodal Models**: Models that answer visual questions without access to images should receive very low scores (<3)
```

**影响**:
- LLM Judge会更严格地要求视觉证据
- 非多模态模型会在Correctness和Faithfulness上得到极低分(<3/10)

---

## 测试说明

### 环境准备

确保已安装必要的依赖:
```bash
pip install requests pathlib
```

### 测试步骤

#### 1. 测试非多模态模型 (期望分数 < 0.3)

```bash
# 运行实验 - 使用非多模态模型
python run_experiment.py \
  --model gemini-3-flash-preview-nothinking \
  --num-tasks 5 \
  --output-dir test_output/task_2a_nonmm

# 验证结果
python task/verify_task_2a.py test_output/task_2a_nonmm/run_log_*.json --non-multimodal
```

**期望结果**:
- ✅ Overall Average < 0.3
- ✅ Faithfulness Average < 0.2
- ✅ 大部分评估得分 < 0.3

#### 2. 测试多模态模型 (期望分数 > 0.6)

```bash
# 运行实验 - 使用多模态模型
python run_experiment.py \
  --model gpt-4o \
  --num-tasks 5 \
  --output-dir test_output/task_2a_mm

# 验证结果
python task/verify_task_2a.py test_output/task_2a_mm/run_log_*.json --multimodal
```

**期望结果**:
- ✅ Overall Average > 0.6
- ✅ Faithfulness Average > 0.6
- ✅ 大部分评估得分 > 0.6

#### 3. 对比测试

运行对比分析:
```bash
# 比较两种模型的评估结果
echo "=== Non-Multimodal Model ==="
python task/verify_task_2a.py test_output/task_2a_nonmm/run_log_*.json --non-multimodal

echo ""
echo "=== Multimodal Model ==="
python task/verify_task_2a.py test_output/task_2a_mm/run_log_*.json --multimodal
```

### 验证脚本说明

`task/verify_task_2a.py` 会检查:

1. **评估数量**: 是否有足够的评估数据
2. **分数分布**:
   - Overall average, min, max
   - Correctness, Faithfulness, Robustness averages
   - 分数 < 0.3 和 > 0.6 的数量
3. **通过条件**:
   - 非多模态: Average < 0.3, Faithfulness < 0.2
   - 多模态: Average > 0.6, Faithfulness > 0.6

### 手动验证

如果需要手动检查日志:

```bash
# 查看日志文件中的评估部分
cat test_output/task_2a_*/run_log_*.json | jq '.[] | select(.event == "target_model_response") | .evaluation'
```

关注以下字段:
- `overall_score`: 总分
- `scores.faithfulness`: 忠实度分数
- `scores.robustness`: 鲁棒性分数
- `llm_judge_output`: LLM Judge的详细评估

---

## 预期性能对比

| 指标 | 非多模态模型 | 多模态模型 |
|------|------------|----------|
| Overall Score | < 0.3 | > 0.6 |
| Correctness | < 0.3 | > 0.6 |
| Faithfulness | < 0.2 | > 0.6 |
| Robustness | 0.3-0.6 | > 0.7 |
| Visual Grounding | ❌ 无 | ✅ 有 |

---

## 故障排除

### 问题1: 非多模态模型分数仍然很高 (> 0.5)

**可能原因**:
- LLM Judge没有正确接收图像
- Hard rules权重过高

**检查**:
1. 确认 `task` 字典包含 `images` 字段
2. 检查图像路径是否正确
3. 查看 `llm_judge_weight` 设置 (应该 >= 0.6)

### 问题2: 多模态模型分数过低 (< 0.4)

**可能原因**:
- 模型回答质量确实不好
- 期望答案与实际不匹配

**检查**:
1. 查看原始模型回答
2. 检查 `expected_answer` 是否合理
3. 确认模型确实使用了视觉grounding phrases

### 问题3: 验证脚本找不到评估数据

**可能原因**:
- 日志文件路径错误
- 日志格式不正确

**解决**:
```bash
# 检查日志文件是否存在
ls -lh test_output/task_2a_*/run_log_*.json

# 检查日志格式
head -50 test_output/task_2a_*/run_log_*.json
```

---

## 代码修改总结

### 新增依赖
```python
import base64
from pathlib import Path
```

### 新增方法
- `_encode_image(image_path: str) -> Optional[str]`

### 修改的方法
- `_call_llm_judge()`: 添加 `task` 参数,支持多模态内容
- `evaluate_response()`: 添加 `task` 参数并传递给Judge
- `_hard_rule_evaluation()`: 降低默认分数,强化robustness检测

### 修改的常量
- `LLM_JUDGE_SYSTEM_PROMPT`: 添加视觉验证要求

---

## 下一步

Task 2A已完成。接下来可以:

1. 运行完整的测试套件验证修改
2. 与Task 2B并行开发
3. 为Task 3准备准确的评估系统

---

## 协作依赖

**依赖于**:
- ✅ Task 1A, 1B: 稳定的对话质量 (已完成)
- ✅ Task 1D (可选): 批量数据测试 (已完成)

**提供给**:
- Task 3: 准确的评估系统用于最终验证

---

## 文件清单

修改的文件:
- ✅ `src/simulator/evaluator.py` (约400行修改)

新增的文件:
- ✅ `task/verify_task_2a.py` (~200行)
- ✅ `task/task_2a_testing_guide.md` (本文档)

---

**任务完成时间**: 已完成
**预计工作量**: ~400 lines代码 + 50 lines验证脚本 ✅
**测试时间**: 需要8小时进行多模态对比测试
