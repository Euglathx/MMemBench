# Phase 1 Window 2: 代码逻辑验证

**任务编号**: ROUND4-P1-W2
**预计时间**: 4 小时
**可并行**: 与 Window 1 完全并行
**优先级**: HIGH - 必须完成才能进入 Phase 2

---

## 任务目标

运行**最小复现测试**，验证 Round 3 的代码在正确配置下是否能正常工作。

**核心问题**: 代码已修复，但需要验证：
1. 代码逻辑本身是否正确
2. 哪些修复生效了，哪些没生效

---

## 背景信息

### Round 3 修复列表

| 修复 ID | 修复内容 | 验证重点 |
|---------|---------|---------|
| Task 2.1 | 图像路径解析 | `images_sent` 非空 |
| Task 2.2 | Turn-level ground truth | Turn 1 的 expected_answer 是 turn-level |
| Task 2.3 | 评分公式 | LLM Judge 10/10 → final score >= 0.8 |
| Task 2.4 | 真值验证 | Simulator 提示词不错误确认模型输出 |
| Task 2.5 | 图像注入策略 | 图像数量一致 + prompt 用词匹配 |
| Task 2.6 | 动态评分 | 各维度分数动态变化 |

### 用户反馈重点

**反馈 1**: 图像传输已改善（Task 2.1 部分生效）

**反馈 2**: Turn-level 评估的本质问题
> "对于很多 turn 来说不一定有 expected answer。很多动作（turn）只是为了增加可靠性。"

**含义**: Task 2.2 的概念框架可能错了
- 中间 turn 不应该有 "expected answer" 来判断对错
- 应该有 "purpose" 来判断是否完成了该 turn 的功能

**反馈 3**: Simulator "确认错误"可能是 ground truth 问题
- 可能是 ground truth 错了，模型对了，但被判错

---

## 任务详细要求

### 1. 创建测试脚本

**文件**: `scripts/round4_minimal_test.py`

**目的**: 运行 1-2 个任务，手动设置正确配置，检查 run logs

**脚本框架**:
```python
"""
Round 4 Phase 1 最小复现测试
目的：验证 Round 3 修复在正确配置下是否工作
"""

from src.simulator.strategic_simulator import StrategicSimulator
from src.simulator.evaluator import Evaluator
from src.simulator.image_policy import ImageInjectionPolicy

# 手动设置正确配置（绕过配置文件）
def create_simulator_with_correct_config():
    evaluator = Evaluator(
        llm_judge_weight=0.8,        # Task 2.3: 从 0.6 改为 0.8
        enable_snapshots=True         # Task 2.6: 启用快照
    )

    simulator = StrategicSimulator(
        evaluator=evaluator,
        filter_incorrect_turns=True,  # Task 2.4
        error_filter_threshold=0.5,   # Task 2.4
        image_injection_policy=ImageInjectionPolicy.SEND_ALL_EVERY_TURN,  # Task 2.5
        verbose=True                  # Task 2.1: 调试模式
    )

    return simulator

# 运行测试
def run_test_task(simulator, task_data):
    """运行单个任务并返回 run log"""
    simulator.start_task(task_data)

    # 运行到完成
    while not simulator.is_task_complete():
        simulator.step()

    # 返回完整日志
    return simulator.get_run_log()

# 主函数
def main():
    print("="*80)
    print("Round 4 Phase 1 - 最小复现测试")
    print("="*80)

    simulator = create_simulator_with_correct_config()

    # 测试任务 1: ABR 任务
    abr_task = {
        "task_id": "round4_test_abr_1",
        "task_type": "adversarial_bit_recovery",
        # ... 任务数据
    }

    print("\n[1/2] 运行 ABR 测试任务...")
    abr_log = run_test_task(simulator, abr_task)

    # 测试任务 2: AC 任务（多图）
    ac_task = {
        "task_id": "round4_test_ac_1",
        "task_type": "attribute_comparison",
        "images": [
            "images/COCO_val2014_000000001.jpg",
            "images/COCO_val2014_000000002.jpg",
            "images/COCO_val2014_000000003.jpg"
        ],
        # ... 任务数据
    }

    print("\n[2/2] 运行 AC 测试任务（3张图）...")
    ac_log = run_test_task(simulator, ac_task)

    # 保存日志
    import json
    with open("docs/task/round4/phase1_test_abr_log.json", "w") as f:
        json.dump(abr_log, f, indent=2)

    with open("docs/task/round4/phase1_test_ac_log.json", "w") as f:
        json.dump(ac_log, f, indent=2)

    print("\n✓ 测试完成！日志已保存到 docs/task/round4/")
    print("  - phase1_test_abr_log.json")
    print("  - phase1_test_ac_log.json")

if __name__ == "__main__":
    main()
```

### 2. 运行测试并生成 run logs

**操作**:
1. 创建测试脚本
2. 准备 2 个测试任务数据（1 个 ABR + 1 个 AC）
3. 运行脚本
4. 检查生成的 run logs

### 3. 验证检查点

根据评审报告和用户反馈，检查以下内容：

#### 检查点 1: Task 2.1 - 图像发送（优先级：低）
**预期**: 用户确认已改善

**检查**:
```json
// 在 run log 的每个 turn 中
{
  "turn": 1,
  "images_sent": ["E:\\...\\COCO_val2014_000000001.jpg"],  // ✓ 非空
  "images_sent_count": 1  // ✓ >= 1
}
```

**判断**:
- ✅ PASS: images_sent 非空且路径存在
- ❌ FAIL: images_sent 为 [] 或路径不存在
- ⚠️ PARTIAL: 部分 turn 有图像，部分没有

#### 检查点 2: Task 2.2 - Turn-level evaluation（优先级：最高）
**关键**: 检查 LLM Judge prompt，不只是 expected_answer

**检查**:
```json
// Turn 1 (entity_grounding 阶段)
{
  "turn": 1,
  "phase": "entity_grounding",
  "action": "guidance",

  // 1. 检查 expected_answer 是否是 turn-level
  "expected_answer": "Model should identify/describe the person",  // ✓ turn-level
  // 不应该是: "The final object is a knife"  // ❌ task-level

  // 2. 关键：检查 evaluator 的 prompt
  "evaluator_prompt": "...",  // 需要包含"This is a RELIABILITY CHECK turn"

  // 3. 检查 evaluation context
  "evaluation_context": {
    "turn_purpose": "entity_grounding",
    "is_reliability_check": true,  // ✓ 应该是 true
    "evaluation_focus": ["entity_identification"],  // ✓ 不包括 "final_answer_match"
  }
}
```

**判断**:
- ✅ PASS: LLM Judge prompt 明确说"不要按最终答案判断"
- ❌ FAIL: LLM Judge prompt 仍在比较最终答案
- ⚠️ PARTIAL: expected_answer 是 turn-level，但 prompt 不明确

#### 检查点 3: Task 2.3 - 评分公式（优先级：高）
**检查**:
```json
{
  "llm_judge_output": {
    "correctness": 10,  // 满分
    "faithfulness": 10,
    "robustness": 10,
    // ...
  },
  "llm_judge_weight": 0.8,  // ✓ 应该是 0.8，不是 0.6
  "hard_scores": {
    "correctness": 0.5,  // ✓ 应该是 0.5，不是 0.1
    // ...
  },
  "final_scores": {
    "correctness": 0.9,  // ✓ 应该 >= 0.8
  },
  "overall_score": 0.85,  // ✓ 应该 >= 0.8
  "level_passed": true  // ✓ 应该是 true
}
```

**判断**:
- ✅ PASS: LLM Judge 10/10 → final score >= 0.8
- ❌ FAIL: LLM Judge 10/10 但 final score < 0.7

#### 检查点 4: Task 2.4 - Simulator 真值验证（优先级：中，重新定义）
**新重点**: 不检查"错误确认"，检查"当 ground truth 可疑时的行为"

**检查**:
```json
{
  "turn": 2,
  "simulator_prompt": "...",

  // 不应该看到: "You correctly noted that [模型的错误输出]"
  // 应该看到: "You mentioned that [模型输出]. Let's verify..."
}
```

**判断**:
- ✅ PASS: Simulator 不盲目确认模型输出
- ❌ FAIL: Simulator 说 "You correctly noted [错误内容]"
- ⚠️ PARTIAL: 可能是 ground truth 问题，需进一步分析

#### 检查点 5: Task 2.5 - 图像注入策略（优先级：高）
**检查**:
```json
// AC 任务（3张图）
{
  "task_images": ["img1.jpg", "img2.jpg", "img3.jpg"],

  "turn_1": {
    "images_sent": ["img1.jpg", "img2.jpg", "img3.jpg"],  // ✓ 3张
    "question": "Looking at all 3 images, which..."  // ✓ "all 3 images"
    // 不应该是: "Looking at both images"  // ❌ 2 vs 3 不匹配
  },

  "turn_2": {
    "images_sent": ["img1.jpg", "img2.jpg", "img3.jpg"],  // ✓ 仍然是 3张
    "question": "Looking at all 3 images, ..."  // ✓ 一致
  }
}
```

**判断**:
- ✅ PASS: 图像数量一致 + prompt 用词匹配
- ❌ FAIL: 发送 3 张图但说 "both images"
- ⚠️ PARTIAL: 图像数量对，但用词不对

#### 检查点 6: Task 2.6 - 动态评分（优先级：中）
**检查**:
```json
{
  "turn_1": {
    "scores": {
      "faithfulness": 0.7,
      "robustness": 0.6,
      "consistency": 0.8
    }
  },
  "turn_2": {
    "scores": {
      "faithfulness": 0.9,  // ✓ 变化了
      "robustness": 0.8,    // ✓ 变化了
      "consistency": 0.7    // ✓ 变化了
    }
  }
}
```

**判断**:
- ✅ PASS: 各维度分数有变化（标准差 > 0.1）
- ❌ FAIL: 某些维度几乎是常数（标准差 < 0.05）

---

## 接口定义

### 输入
- 2 个测试任务数据（JSON 格式）
- Round 3 修复的代码（当前代码库）

### 输出

#### 1. 测试 run logs (JSON)

**文件**:
- `docs/task/round4/phase1_test_abr_log.json`
- `docs/task/round4/phase1_test_ac_log.json`

#### 2. 验证报告 (Markdown)

**文件**: `docs/task/round4/phase1_code_verification_report.md`

**格式**:
```markdown
# Phase 1 代码验证报告

生成时间: 2026-02-05

## 执行摘要

- 测试任务数: 2
- 通过的检查点: X / 6
- 失败的检查点: Y / 6
- 部分通过: Z / 6

## 测试配置

手动设置的配置（绕过配置文件）:
- llm_judge_weight: 0.8
- filter_incorrect_turns: true
- image_injection_policy: SEND_ALL_EVERY_TURN
- ...

## 检查点验证结果

### 检查点 1: Task 2.1 - 图像发送
**状态**: ✅ PASS / ❌ FAIL / ⚠️ PARTIAL

**ABR 任务**:
- Turn 1: images_sent count = 1 ✓
- Turn 2: images_sent count = 1 ✓

**AC 任务**:
- Turn 1: images_sent count = 3 ✓
- Turn 2: images_sent count = 3 ✓

**结论**: 图像发送正常

---

### 检查点 2: Task 2.2 - Turn-level evaluation
**状态**: ❌ FAIL

**发现**:
Turn 1 (entity_grounding):
- expected_answer: "The final object is a knife" ❌ （应该是 turn-level）
- evaluator_prompt: 没有"RELIABILITY CHECK"字样 ❌
- evaluation_context: is_reliability_check = false ❌

**结论**: Task 2.2 未生效，或概念框架错误

**建议**: 需要重新设计评估框架（见 Phase 2 修复 2.0）

---

[... 其他检查点 ...]

## 失败检查点汇总

| 检查点 | 状态 | 根本原因 | 优先级 |
|--------|------|---------|--------|
| Task 2.2 | ❌ FAIL | 概念框架错误 | P0 |
| Task 2.5 | ⚠️ PARTIAL | prompt 生成逻辑未更新 | P1 |
| ... | ... | ... | ... |

## 下一步行动

进入 Phase 2，修复以下失败的检查点:
1. [检查点 ID] - [修复任务]
2. ...
```

#### 3. 失败检查点列表 (CSV)

**文件**: `docs/task/round4/phase1_failed_checkpoints.csv`

```csv
checkpoint_id,task_id,status,priority,root_cause,phase2_fix
checkpoint_2,task_2.2,FAIL,P0,Conceptual framework issue,fix_2.0
checkpoint_5,task_2.5,PARTIAL,P1,Prompt generation not updated,fix_2.1
...
```

---

## 协作要求

### 与 Window 1 的协调

**依赖性**: 理论上可以完全并行，但如果 Window 1 发现配置问题，可以先修改配置再运行

**建议**: 先用手动配置运行测试，不要等 Window 1

### 阻塞关系

**阻塞**: Phase 2 的修复任务（需要知道哪些检查点失败了）

---

## 当前进度

- [ ] 创建测试脚本
- [ ] 准备测试任务数据
- [ ] 运行 ABR 测试
- [ ] 运行 AC 测试
- [ ] 检查点 1 验证
- [ ] 检查点 2 验证（关键！）
- [ ] 检查点 3 验证
- [ ] 检查点 4 验证
- [ ] 检查点 5 验证
- [ ] 检查点 6 验证
- [ ] 生成验证报告
- [ ] 生成失败检查点列表
- [ ] 完成

---

## 验证标准

### Must Have
1. ✅ 至少运行 2 个测试任务（1 ABR + 1 AC）
2. ✅ 检查所有 6 个检查点
3. ✅ 明确标记每个检查点的状态（PASS/FAIL/PARTIAL）
4. ✅ 对失败的检查点给出根本原因分析

### Nice to Have
1. 运行更多测试任务
2. 自动化检查脚本
3. 可视化检查结果

---

## 工具使用建议

### 推荐工具
1. **Bash** - 运行 Python 测试脚本
2. **Read** - 读取生成的 run logs
3. **Write** - 生成验证报告

### 示例命令

```bash
# 运行测试脚本
cd /e/Code/M3Bench/M3Bench_new
python scripts/round4_minimal_test.py
```

---

## 交付物清单

- [ ] `scripts/round4_minimal_test.py` - 测试脚本
- [ ] `docs/task/round4/phase1_test_abr_log.json` - ABR 测试日志
- [ ] `docs/task/round4/phase1_test_ac_log.json` - AC 测试日志
- [ ] `docs/task/round4/phase1_code_verification_report.md` - 验证报告
- [ ] `docs/task/round4/phase1_failed_checkpoints.csv` - 失败列表

---

## 注意事项

1. **手动设置配置** - 不要依赖配置文件，直接在代码中设置
2. **重点检查 Task 2.2** - 这是用户反馈的核心问题
3. **记录详细证据** - 每个检查点都要有 run log 截图或摘录
4. **区分"未生效"和"概念错误"** - Task 2.2 可能是概念框架问题

---

**任务开始时间**: _____________
**任务完成时间**: _____________
**执行人**: _____________
