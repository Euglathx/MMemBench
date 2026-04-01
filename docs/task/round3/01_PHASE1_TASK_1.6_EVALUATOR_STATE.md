# Phase 1 Task 1.6: 评估器内部状态追踪

## 任务目标

验证评审意见中的**P2级问题**：
1. Evaluator对同一图像的判断是否前后一致（问题4）
2. Faithfulness/Robustness等分数是否像常数（问题1.3）

## 问题描述

### 问题4: 判断不一致
评审意见指出：
- ABR Turn 3评语说"knife在counter右侧、person更右"
- ABR Turn 4又判"knife被person拿着、在cake上方"是对的
- 这两个对knife位置的判断明显冲突

这说明：
- Judge在不同turn的立场漂移
- 或Turn 3用了硬规则，Turn 4顺着模型说法判对

### 问题1.3: 分数像常数
评审意见指出：
- ABR Turn 1: faithfulness=0.68, robustness=0.72, consistency=0.72
- ABR Turn 3（严重错误）: faithfulness=0, robustness=0.72, consistency=0.72
- AC Turn 2（跨图混淆）: memory=0.0, consistency=0.12, disambiguation=0.72

这说明：
- 某些维度分数几乎不随turn变化
- 可能是默认值或字段映射错误

## 验证目标

1. **追踪Evaluator状态**: 记录每个turn的cross_image_mapping, key_facts等
2. **检测判断不一致**: 同一任务内对相��事物的判断是否一致
3. **分析分数分布**: 各维度分数的变化范围和频率
4. **定位默认值问题**: 哪些分数是默认值？何时被更新？

## 验证脚本设计

### 脚本名称
`debug_evaluator_state_tracking.py`

### 验证步骤

#### Step 1: 判断一致性检查
```python
# 对于每个任务:
# 1. 提取所有turn的evaluation reasoning
# 2. 使用NLP提取关于物体位置/属性的判断
#    例如: "knife is on the right", "person is holding knife"
# 3. 对比同一物体在不同turn的判断是否一致
# 4. 标记矛盾cases

# 关键检测:
# - 空间关系矛盾（"A在B左边" vs "A在B右边"）
# - 属性矛盾（"红色" vs "蓝色"）
# - 存在性矛盾（"有X" vs "没有X"）
```

**成功标准**:
- 找出至少5个判断矛盾的cases
- 每个case都有清晰的证据

#### Step 2: 分数分布分析
```python
# 对所有turn:
# 1. 统计每个维度分数的分布:
#    - correctness: [0.1: 30%, 0.3: 20%, 0.66: 25%, 1.0: 25%]
#    - faithfulness: [0.2: 60%, 0.68: 30%, 1.0: 10%]
#    - robustness: [0.72: 80%, 1.0: 20%]  ← 可疑的高集中度
# 2. 计算每个维度的:
#    - 标准差（低标准差 → 像常数）
#    - 唯一值数量
#    - 最常见值的占比

# 警报阈值:
# - 如果某维度有>70%的turns是同一个值 → 可疑
```

**成功标准**:
- 明确每个维度的分数分布特征
- 识别"常数化"的维度

#### Step 3: 默认值追踪
```python
# 追踪hard_rule_evaluation()的默认值:
# scores = {
#     "correctness": 0.1,
#     "faithfulness": 0.2,
#     "robustness": 0.3,
#     "consistency": 0.3,
#     "memory_retention": 0.3,
#     "cross_image_confusion": 0.3,
#     "disambiguation": 0.3
# }

# 对每个turn:
# 1. 检查最终分数是否等于这些默认值
# 2. 如果是，说明该维度未被正确更新
# 3. 统计"未更新率"
```

**成功标准**:
- 量化每个维度的默认值保留率
- 找到未被更新的条件

#### Step 4: 状态快照对比
```python
# 对每个任务，生成每个turn的状态快照:
# {
#   "turn": 1,
#   "cross_image_mapping": {...},
#   "key_facts": {...},
#   "injected_falsehoods": [...],
#   "previous_responses": [...]
# }

# 对比相邻turn:
# - cross_image_mapping是否正确更新？
# - key_facts是否正确累积？
# - 是否有状态丢失或混乱？
```

**成功标准**:
- 生成完整的状态演化图
- 识别状态管理bug

### 输出格式

```json
{
  "validation_id": "1.6_evaluator_state_tracking",
  "timestamp": "2026-02-03T...",
  "status": "FAIL" | "PASS",
  "judgment_inconsistencies": [
    {
      "task_id": "abr_example_001",
      "object": "knife",
      "turn_3_judgment": "knife is on counter right side, person is more right",
      "turn_4_judgment": "knife is held by person, above cake",
      "contradiction": "Cannot be both 'on counter' and 'held by person'",
      "severity": "HIGH"
    }
  ],
  "score_distribution_analysis": {
    "robustness": {
      "unique_values": 3,
      "most_common": 0.72,
      "most_common_rate": 0.82,
      "std_dev": 0.15,
      "status": "SUSPICIOUS (low diversity)"
    },
    "disambiguation": {
      "unique_values": 2,
      "most_common": 0.3,
      "most_common_rate": 0.90,
      "std_dev": 0.08,
      "status": "CONSTANT (90% same value)"
    },
    "correctness": {
      "unique_values": 15,
      "most_common": 0.1,
      "most_common_rate": 0.35,
      "std_dev": 0.32,
      "status": "NORMAL"
    }
  },
  "default_value_retention": {
    "robustness": {
      "default": 0.3,
      "retained_rate": 0.65,
      "issue": "Updated only when action_type in ['mislead', 'memory_injection']"
    },
    "disambiguation": {
      "default": 0.3,
      "retained_rate": 0.90,
      "issue": "Rarely updated, only for specific action_types"
    }
  },
  "state_evolution_issues": [
    "cross_image_mapping not aligned with images_sent",
    "key_facts not consistently updated",
    "previous_responses truncated after 3 turns"
  ],
  "root_causes": [
    "LLM Judge立场漂移: prompt or evidence changes between turns",
    "Hard score defaults not updated for most action_types",
    "cross_image_confusion/disambiguation only evaluated for specific actions"
  ],
  "severity": "P2_MEDIUM",
  "recommended_fixes": [
    "Standardize LLM Judge evidence across turns",
    "Update all dimension scores dynamically, not just defaults",
    "Evaluate all dimensions for all action types"
  ]
}
```

## 变量和接口定义

### 输入
- `log_dir`: Run logs目录
- `evaluator_code_path`: evaluator.py路径

### 输出
- `validation_report.json`
- `validation_report.txt`
- `judgment_inconsistencies.csv`
- `score_distributions.png` (可视化)

### 接口

```python
class EvaluatorStateTracker:
    """追踪evaluator的内部状态和一致性"""

    def __init__(self, log_dir: str, evaluator_path: str):
        pass

    def check_judgment_consistency(self) -> List[Dict]:
        """检查判断一致性"""
        pass

    def analyze_score_distributions(self) -> Dict:
        """分析分数分布"""
        pass

    def trace_default_value_retention(self) -> Dict:
        """追踪默认值保留情况"""
        pass

    def snapshot_state_evolution(self, task_logs: List) -> List[Dict]:
        """生成状态快照序列"""
        pass

    def generate_report(self) -> Tuple[Dict, str]:
        pass
```

## 协作要求

### 依赖
- **可并行**: 与Task 1.5并行（组C）
- **被依赖**: Task 2.6（Evaluator状态管理重构）需要这个

### 数据共享
- 报告: `round3/results/phase1_1.6_evaluator_state.json`

## 成功标准

- [ ] 找到至少3个判断不一致的cases
- [ ] 明确识别"常数化"的维度
- [ ] 量化默认值保留率
- [ ] 生成状态演化图
- [ ] 提供修复建议

## 时间估算
- 约4-5小时

---

**并行组**: C (与Task 1.5并行)
**优先级**: P2
**预估难度**: Medium-Hard
