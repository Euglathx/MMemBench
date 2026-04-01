# Phase 1 Window 1: 配置审计

**任务编号**: ROUND4-P1-W1
**预计时间**: 3 小时
**可并行**: 与 Window 2 完全并行
**优先级**: HIGH - 必须完成才能进入 Phase 2

---

## 任务目标

全面审计当前系统配置，找出 Round 3 修复所需的配置是否被正确设置。

**核心问题**: Round 3 的代码修复已完成，但评审报告显示问题仍然存在。可能是配置未启用或被覆盖。

---

## 背景信息

### Round 3 完成的修复

| 修复 ID | 修复内容 | 需要的配置 |
|---------|---------|-----------|
| Task 2.1 | 图像路径解析 | `verbose=True`（调试模式） |
| Task 2.2 | Turn-level ground truth | 代码中自动生成，无需配置 |
| Task 2.3 | 评分公式调整 | `llm_judge_weight=0.8`, hard_scores defaults=0.5 |
| Task 2.4 | 真值验证 | `filter_incorrect_turns=True`, `error_filter_threshold=0.5` |
| Task 2.5 | 图像注入策略 | `image_injection_policy=SEND_ALL_EVERY_TURN` |
| Task 2.6 | 动态评分 | `enable_snapshots=True`（调试模式） |

### 用户反馈
- 图像传输已部分生效（Task 2.1）
- 配置方式：配置文件 + 硬编码混合

---

## 任务详细要求

### 1. 检查配置文件

**位置**:
- `config/multimodal.yaml`
- `config/attack_evaluation_standard.yaml`

**检查清单**:
```yaml
# 期望的配置项
StrategicSimulator:
  filter_incorrect_turns: true           # Task 2.4
  error_filter_threshold: 0.5            # Task 2.4
  image_injection_policy: "SEND_ALL_EVERY_TURN"  # Task 2.5
  verbose: true                          # Task 2.1 调试

Evaluator:
  llm_judge_weight: 0.8                  # Task 2.3 (从 0.6 改为 0.8)
  enable_snapshots: true                 # Task 2.6 调试
```

**操作**:
1. 读取上述配置文件
2. 查找每个配置项
3. 记录实际值 vs 期望值

### 2. 检查主运行脚本

**文件**: `generate_all_tasks_v2.py`

**操作**:
1. 查找所有 `StrategicSimulator(` 初始化
2. 查找所有 `Evaluator(` 初始化
3. 查找所有 `LLMUserSimulator(` 初始化
4. 记录传入的参数

**示例检查**:
```python
# 期望看到
simulator = StrategicSimulator(
    filter_incorrect_turns=True,        # ✓
    error_filter_threshold=0.5,         # ✓
    image_injection_policy=ImageInjectionPolicy.SEND_ALL_EVERY_TURN,  # ✓
    verbose=True                        # ✓
)

evaluator = Evaluator(
    llm_judge_weight=0.8,               # ✓
    enable_snapshots=True               # ✓
)
```

### 3. 检查代码中的硬编码默认值

**文件**:
- `src/simulator/strategic_simulator.py` - StrategicSimulator.__init__()
- `src/simulator/evaluator.py` - Evaluator.__init__(), _hard_rule_evaluation()

**关键检查点**:

#### 3.1 Evaluator 默认权重
```python
# 在 Evaluator.__init__() 中
# 期望: llm_judge_weight 默认值 = 0.8
def __init__(self, ..., llm_judge_weight: float = 0.8, ...):  # ✓ 期望是 0.8
```

#### 3.2 Hard Scores 默认值
```python
# 在 Evaluator._hard_rule_evaluation() 中
# 期望: 所有维度默认值 = 0.5（中性）
scores = {
    "correctness": 0.5,      # ✓ 期望是 0.5，不是 0.1
    "faithfulness": 0.5,     # ✓ 期望是 0.5，不是 0.2
    "robustness": 0.5,       # ✓ 期望是 0.5，不是 0.3
    "consistency": 0.5,
    "memory_retention": 0.5,
    "cross_image_confusion": 0.5,
    "disambiguation": 0.5
}
```

### 4. 搜索所有初始化点

使用 Grep 工具搜索:
```bash
# 搜索所有 StrategicSimulator 初始化
pattern: "StrategicSimulator\s*\("
```

```bash
# 搜索所有 Evaluator 初始化
pattern: "Evaluator\s*\("
```

---

## 接口定义

### 输入
无特殊输入，直接读取代码库

### 输出

#### 1. 配置审计报告 (Markdown)

**文件**: `docs/task/round4/phase1_config_audit.md`

**格式**:
```markdown
# Phase 1 配置审计报告

生成时间: 2026-02-05

## 执行摘要

- 配置文件检查: ✓/✗
- 主脚本检查: ✓/✗
- 代码默认值检查: ✓/✗
- 发现的问题数量: X 个

## 详细发现

### 1. 配置文件差异

| 配置项 | 文件位置 | 期望值 | 实际值 | 状态 |
|--------|---------|--------|--------|------|
| filter_incorrect_turns | config/multimodal.yaml | true | false | ❌ 不匹配 |
| llm_judge_weight | config/... | 0.8 | 0.6 | ❌ 不匹配 |
| ... | ... | ... | ... | ... |

### 2. 主脚本参数

**generate_all_tasks_v2.py**:
- 行 X: StrategicSimulator() 初始化
  - filter_incorrect_turns: 未设置（使用默认值）❌
  - image_injection_policy: 未设置（使用默认值）❌

### 3. 代码默认值

**src/simulator/evaluator.py**:
- 行 Y: llm_judge_weight 默认值 = 0.6 ❌（应该是 0.8）
- 行 Z: hard_scores["correctness"] = 0.1 ❌（应该是 0.5）

### 4. 所有初始化点列表

1. generate_all_tasks_v2.py:123 - StrategicSimulator()
2. scripts/test_runner.py:45 - Evaluator()
...

## 优先级修复建议

### Critical (必须修复):
1. [配置项名称] - [原因]
2. ...

### High (强烈建议):
1. ...

### Medium (可选):
1. ...
```

#### 2. 配置差异 CSV

**文件**: `docs/task/round4/phase1_config_diff.csv`

**格式**:
```csv
category,item,location,expected,actual,status,priority
config_file,filter_incorrect_turns,config/multimodal.yaml,true,false,MISMATCH,CRITICAL
code_default,llm_judge_weight,src/simulator/evaluator.py:150,0.8,0.6,MISMATCH,HIGH
...
```

---

## 协作要求

### 与 Window 2 的协调

**独立性**: 完全独立，不需要同步

**共享输出**: Window 2 会使用本任务的审计报告来理解配置问题

### 阻塞关系

**阻塞**: Phase 2 所有任务（需要先知道哪些配置有问题）

**不阻塞**: Window 2 可以同时进行代码验证

---

## 当前进度

- [ ] 创建输出目录
- [ ] 读取 config/multimodal.yaml
- [ ] 读取 config/attack_evaluation_standard.yaml
- [ ] 读取 generate_all_tasks_v2.py
- [ ] 检查 StrategicSimulator 初始化
- [ ] 检查 Evaluator 初始化
- [ ] 检查代码默认值
- [ ] 搜索所有初始化点
- [ ] 生成配置审计报告
- [ ] 生成配置差异 CSV
- [ ] 完成

---

## 验证标准

### Must Have
1. ✅ 审计报告完整，包含所有 Round 3 修复需要的配置
2. ✅ 明确列出每个不匹配的配置项
3. ✅ 给出优先级修复建议
4. ✅ CSV 文件可被程序解析

### Nice to Have
1. 统计配置匹配率（X% 配置正确）
2. 可视化图表
3. 自动化检测脚本

---

## 工具使用建议

### 推荐工具
1. **Read** - 读取配置文件和代码
2. **Grep** - 搜索所有初始化点
3. **Glob** - 查找所有相关文件

### 示例命令

```python
# 读取配置文件
Read("config/multimodal.yaml")

# 搜索初始化
Grep(pattern="StrategicSimulator\s*\(", output_mode="content", context=5)

# 查找所有配置文件
Glob(pattern="config/**/*.yaml")
```

---

## 交付物清单

- [ ] `docs/task/round4/phase1_config_audit.md` - 主审计报告
- [ ] `docs/task/round4/phase1_config_diff.csv` - 配置差异表
- [ ] （可选）`docs/task/round4/phase1_config_summary.txt` - 一句话总结

---

## 注意事项

1. **不要修改任何代码** - 这是只读审计任务
2. **记录完整路径** - 方便后续修复时快速定位
3. **区分"未设置"和"设置错误"** - 两种情况的修复方式不同
4. **检查多个初始化点** - 可能有测试脚本、工具脚本等也在使用

---

**任务开始时间**: _____________
**任务完成时间**: _____________
**执行人**: _____________
