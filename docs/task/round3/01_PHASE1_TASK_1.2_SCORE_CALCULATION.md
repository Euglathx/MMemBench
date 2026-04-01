# Phase 1 Task 1.2: 评分公式验证

## 任务目标

验证评审意见中的**P0级问题**：评分公式是否正确使用了LLM Judge输出。

## 问题描述（来自评审意见1.1）

在某些turn中：
- **LLM Judge给出的所有维度都是10分（满分）**
- **但最终 `score < 0.7`，导致 `level_passed = false`**
- 例如：ABR Turn 1，correctness=10, faithfulness=10, robustness=10, 但 score=0.663999

这说明：
1. 最终score的计算没有真正使用llm_judge_output
2. 或者hard_score的权重过大
3. 或者缩放/权重计算有bug

## 验证目标

1. **追踪评分计算流程**: 从llm_judge_output → final score的完整链路
2. **验证权重配置**: llm_judge_weight和各维度权重是否合理
3. **检测异常case**: LLM Judge满分但final score低的情况
4. **量化影响**: 有多少turn受此问题影响

## 验证脚本设计

### 脚本名称
`debug_score_calculation.py`

### 验证步骤

#### Step 1: Run Log中的异常Case统计
```python
# 扫描所有run logs，找到:
# 1. llm_judge_output不为null的turn
# 2. llm_judge所有维度 >= 8/10
# 3. 但 final score < 0.7
# 统计这类case的数量和占比
```

**成功标准**:
- 如果 >10% 的turn出现此异常 → P0问题确认
- 列出至少5个具体case供人工检查

#### Step 2: 评分公式逆向工程
```python
# 读取evaluator.py的evaluate_response()函数
# 重现评分计算逻辑:
# 1. hard_rule_evaluation() 的输出
# 2. llm_judge 的输出（如果有）
# 3. 权重组合逻辑
# 4. overall_score 的计算

# 对于每个异常case:
# - 重新计算expected score
# - 对比actual score
# - 找出差异原因
```

**成功标准**:
- 能够精确复现evaluator.py的评分逻辑
- 找到actual vs expected的差异原因

#### Step 3: 权重配置审查
```python
# 检查evaluator.py中的权重配置:
# - llm_judge_weight (默认应该是多少?)
# - STRESS_TEST vs LENIENT模式的权重
# - 各维度的权重 (correctness, faithfulness, etc.)

# 模拟不同权重下的评分结果
# 验证是否合理
```

**成功标准**:
- 明确当前权重配置
- 指出不合理的权重

#### Step 4: Hard Score默认值检查
```python
# 检查hard_rule_evaluation()中的默认分数:
# scores = {
#     "correctness": 0.1,
#     "faithfulness": 0.2,
#     ...
# }

# 这些默认值在什么情况下会被使用?
# 如果llm_judge_output存在，这些默认值是否会被覆盖?
```

**成功标准**:
- 明确hard score的默认值和覆盖逻辑
- 找到是否存在"默认值未被覆盖"的bug

### 输出格式

```json
{
  "validation_id": "1.2_score_calculation",
  "timestamp": "2026-02-03T...",
  "status": "FAIL" | "PASS",
  "anomaly_cases": [
    {
      "task_id": "abr_example_001",
      "turn": 1,
      "llm_judge": {
        "correctness": 10,
        "faithfulness": 10,
        "robustness": 10,
        "consistency": 10,
        "memory_retention": 10
      },
      "hard_scores": {
        "correctness": 0.1,
        "faithfulness": 0.2,
        "robustness": 0.3,
        "consistency": 0.3,
        "memory_retention": 0.3
      },
      "llm_judge_weight": 0.7,
      "expected_score": 0.91,
      "actual_score": 0.664,
      "discrepancy": 0.246,
      "root_cause": "hard_scores not overridden by llm_judge"
    }
  ],
  "statistics": {
    "total_turns_with_llm_judge": 500,
    "anomaly_count": 120,
    "anomaly_percentage": 24.0
  },
  "weight_config": {
    "llm_judge_weight": 0.7,
    "score_mode": "STRESS_TEST",
    "dimension_weights": {
      "correctness": 0.30,
      "faithfulness": 0.20,
      "robustness": 0.25,
      "consistency": 0.15,
      "memory_retention": 0.10
    }
  },
  "root_cause_analysis": {
    "primary_issue": "llm_judge scores are normalized (0-10 → 0-1) but hard_scores are not properly overridden",
    "code_location": "evaluator.py:evaluate_response(), line 908-914",
    "evidence": "When llm_judge exists, final_scores should use llm_scores, but hard_scores defaults are leaking through"
  },
  "severity": "P0_CRITICAL",
  "recommended_fix": "Ensure llm_scores fully override hard_scores when llm_judge_output exists"
}
```

### 诊断输出

```
=== Score Calculation Validation Report ===

Status: FAIL ❌

Problem Summary:
- 24.0% of turns with LLM Judge show score anomalies
- LLM Judge gives 10/10, but final score is 0.66
- This means ~120 turns are mis-evaluated

Root Cause:
Location: evaluator.py:evaluate_response(), lines 908-914
Issue: LLM scores not properly overriding hard scores

Code Analysis:
```python
# Current (WRONG):
if llm_scores:
    w = self.llm_judge_weight  # w = 0.7
    final_scores = {
        k: w * llm_scores[k] + (1 - w) * hard_scores[k]
        for k in hard_scores
    }

# Problem:
# - llm_scores["correctness"] = 10/10 = 1.0
# - hard_scores["correctness"] = 0.1 (default, never updated!)
# - final_scores["correctness"] = 0.7 * 1.0 + 0.3 * 0.1 = 0.73

# Expected (CORRECT):
# - hard_scores should be updated based on actual evaluation
# - OR hard_scores should be 1.0 by default when llm_judge says 10/10
```

Why hard_scores are wrong:
1. hard_rule_evaluation() sets default scores (0.1, 0.2, 0.3...)
2. These are "penalty defaults" assuming failure
3. They are only updated if specific conditions are met
4. When llm_judge says "correctness=10", hard_score may still be 0.1
5. Weighted average: 0.7*1.0 + 0.3*0.1 = 0.73 (not 1.0!)

Impact:
- Even perfect LLM Judge scores result in 0.70-0.75 final scores
- Level 1 threshold is 0.7, so borderline cases fail incorrectly
- This explains why models "答对也过不了"

Example Anomaly Cases:
1. Task: abr_example_001, Turn 1
   - LLM Judge: All 10/10
   - Final score: 0.664 (FAIL, threshold 0.7)
   - Discrepancy: -0.246 (24.6% lower than expected)

2. Task: ac_mscoco_001, Turn 3
   - LLM Judge: All 10/10
   - Final score: 0.680 (FAIL, threshold 0.7)
   - Discrepancy: -0.220 (22% lower than expected)

Weight Configuration:
- llm_judge_weight: 0.7 (reasonable)
- But hard_scores have too much influence (30%) with wrong defaults

Recommended Fix:
Option 1: Set hard_score defaults to neutral (0.5 instead of 0.1-0.3)
Option 2: Only use hard_scores as fallback when llm_judge is null
Option 3: Use llm_scores exclusively when available (weight=1.0)

Severity: P0 CRITICAL
This directly contradicts the design goal of using LLM-as-Judge.
```

## 变量和接口定义

### 输入
- `log_dir`: Run logs目录
- `code_path`: evaluator.py的路径（用于代码分析）

### 输出
- `validation_report.json`: 机器可读验证结果
- `validation_report.txt`: 人类可读详细报告
- `anomaly_cases.csv`: 所有异常case的列表

### 接口

```python
class ScoreCalculationValidator:
    """验证评分公式问题"""

    def __init__(self, log_dir: str, evaluator_code_path: str):
        pass

    def find_anomaly_cases(self) -> List[Dict]:
        """找出LLM Judge高分但final score低的cases"""
        pass

    def reverse_engineer_scoring(self, case: Dict) -> Dict:
        """逆向工程评分逻辑，复现计算过程"""
        pass

    def analyze_weight_config(self) -> Dict:
        """分析权重配置"""
        pass

    def check_hard_score_defaults(self) -> Dict:
        """检查hard score的默认值逻辑"""
        pass

    def generate_report(self) -> Tuple[Dict, str]:
        """生成验证报告"""
        pass
```

## 协作要求

### 与其他任务的依赖
- **独立任务**: 不依赖其他Phase 1任务
- **可并行**: 可以与Task 1.1并行执行
- **被依赖**: Task 2.3（评分公式重构）需要这个验证结果

### 与Phase 2的接口
- 必须明确当前权重配置和问题
- 必须提供具体的异常cases
- 必须给出推荐的修复方向

### 数据共享
- 验证报告: `round3/results/phase1_1.2_score_calculation.json`
- 异常cases: `round3/results/phase1_1.2_anomaly_cases.csv`
- 详细日志: `round3/logs/phase1_1.2_debug.log`

## 成功标准

- [ ] 找到至少10个异常cases
- [ ] 精确复现evaluator.py的评分逻辑（误差<0.01）
- [ ] 明确指出根因（代码行号）
- [ ] 给出至少2种修复方案
- [ ] 报告清晰、有数据支持

## 时间估算

- 脚本开发: 1.5小时
- 日志分析: 0.5小时
- 代码逆向: 1小时
- 报告撰写: 1小时
- **总计: 约4小时**

## 风险和注意事项

1. **LLM Judge可能为null**: 很多turn没有LLM Judge输出（如Task 1.1发现images_sent为空）
2. **权重配置可能变化**: 不同时间的run logs可能使用不同配置
3. **浮点数精度**: 评分计算涉及浮点运算，需要考虑精度误差

## 验证清单

- [ ] 异常cases统计准确（手动验证10个）
- [ ] 评分公式复现精确（误差<1%）
- [ ] 根因分析有代码证据
- [ ] 修复方案可行且具体
- [ ] 报告包含量化数据

---

**并行组**: A (可以与Task 1.1并行)
**优先级**: P0 (最高优先级)
**预估难度**: Hard (需要深入理解评分逻辑)
