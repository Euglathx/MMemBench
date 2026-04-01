# Phase 1 Task 1.5: 多图策略一致性检查

## 任务目标

验证评审意见中的**P1级问题**：多图任务的图像注入策略是否一致和正确。

## 问题描述（来自评审意见3）

评审意见指出三个子问题：

### 3.1 每轮都发送所有图像
- AC每轮的`images_sent`都包含三张图
- 但问题只针对其中一张
- 导致cross-image归因混乱

### 3.2 任务定义不一致
- AC任务: question问"which has more?"
- images有3张
- expected_answer只写了"Image 0 has 3 person(s)"
- 不匹配：应该输出比较结论或所有图的计数

### 3.3 图像编号混用
- Evaluator指责模型"把image label搞混"
- 但reasoning说"model only had one image 'Image 0'"
- 实际上`images_sent`有三张图
- Evaluator对"可见图像列表"的描述与实际不一致

## 验证目标

1. **统计图像发送策略**: 每个turn发送了多少张图？是否一致？
2. **检查策略一致性**: StrategicSimulator vs LLMUserSimulator策略是否相同？
3. **验证任务定义**: question/expected_answer/images是否对齐？
4. **检查Evaluator的图像感知**: Evaluator知道实际发送了哪些图像吗？

## 验证脚本设计

### 脚本名称
`debug_multi_image_strategy.py`

### 验证步骤

#### Step 1: 图像发送统计
```python
# 对于每个AC任务的每个turn:
# 1. 读取task_start的images列表（应该是3张）
# 2. 读取turn的images_sent
# 3. 统计:
#    - images_sent == all task images? → 全量发送
#    - images_sent == 1 image? → 单图发送
#    - images_sent == []? → 未发送

# 关注:
# - 不同phase的图像发送是否不同
# - 是否有"渐进式"发送（先发1张，再发第2张）
```

**成功标准**:
- 明确每个turn的图像发送数量
- 统计不同模式的占比

#### Step 2: 代码策略对比
```python
# 对比两个simulator的图像策略:

# StrategicSimulator._get_images_for_turn():
#   - 注释说"send ALL images on EVERY turn"
#   - 返回所有valid_images

# LLMUserSimulator._get_images_to_send():
#   - 对guidance action，发送下一张未展示的图
#   - 维护images_shown列表

# 检查:
# - 两种策略的设计意图
# - 实际使用哪个simulator
# - 是否有配置可以切换策略
```

**成功标准**:
- 明确两种策略的差异
- 指出应该使用哪种策略

#### Step 3: 任务定义验证
```python
# 对于每个AC任务:
# 1. 读取question
# 2. 读取images列表（数量）
# 3. 读取expected_answer
# 4. 检查对齐:
#    - question问"which has more" → expected应该是比较结论
#    - images有3张 → expected应该包含所有3张的信息或比较

# 统计:
# - 定义一致的任务数
# - 定义不一致的任务数（详细列出）
```

**成功标准**:
- 找出所有定义不一致的任务
- 明确不一致的类型

#### Step 4: Evaluator图像感知检查
```python
# 检查Evaluator是否知道当前turn发送了哪些图像:
# 1. evaluate_response()的参数中有images信息吗？
# 2. cross_image_object_mapping是否与images_sent对齐？
# 3. LLM Judge prompt中描述的可见图像与实际是否一致？

# 重点检查:
# - Evaluator的reasoning中对图像数量的描述
# - 是否出现"model only had one image"但实际发了3张的情况
```

**成功标准**:
- 明确Evaluator的图像感知是否正确
- 找出不一致的cases

### 输出格式

```json
{
  "validation_id": "1.5_multi_image_strategy",
  "timestamp": "2026-02-03T...",
  "status": "FAIL" | "PASS",
  "image_sending_statistics": {
    "total_ac_turns": 500,
    "all_images_sent": 0,
    "some_images_sent": 0,
    "no_images_sent": 500,
    "distribution": {
      "0_images": 500,
      "1_image": 0,
      "2_images": 0,
      "3_images": 0
    }
  },
  "strategy_comparison": {
    "StrategicSimulator": {
      "policy": "send_all_every_turn",
      "implementation": "_get_images_for_turn() returns all valid images"
    },
    "LLMUserSimulator": {
      "policy": "progressive",
      "implementation": "_get_images_to_send() sends one at a time on guidance"
    },
    "used_in_batch_run": "StrategicSimulator",
    "consistency": "INCONSISTENT"
  },
  "task_definition_analysis": {
    "total_ac_tasks": 100,
    "misaligned_tasks": [
      {
        "task_id": "ac_mscoco_001",
        "question": "Which image has more cars?",
        "images_count": 3,
        "expected_answer": "Image 0 has 3 car(s)",
        "issue": "Expected should be comparison result, not single image count"
      }
    ],
    "misaligned_count": 80,
    "misaligned_rate": 80.0
  },
  "evaluator_image_awareness": {
    "receives_images_sent": false,
    "cross_image_mapping_aligned": false,
    "llm_judge_prompt_accurate": false,
    "inconsistent_cases": [
      {
        "task_id": "ac_mscoco_001",
        "turn": 6,
        "images_sent": 3,
        "evaluator_reasoning_says": "model only had one image",
        "inconsistency": "Evaluator thinks 1 image, actually 3 sent"
      }
    ]
  },
  "root_causes": [
    "StrategicSimulator sends all images but question targets single image",
    "Task definition misaligned: question asks comparison, expected is single count",
    "Evaluator not informed of actually sent images"
  ],
  "severity": "P1_HIGH",
  "recommended_fixes": [
    "Implement selective image sending based on question target",
    "Fix task definition: expected_answer should match question",
    "Pass images_sent to evaluator for accurate assessment"
  ]
}
```

## 变量和接口定义

### 输入
- `log_dir`: Run logs目录
- `simulator_code_path`: strategic_simulator.py路径
- `task_dir`: 任务定义目录

### 输出
- `validation_report.json`
- `validation_report.txt`
- `misaligned_tasks.csv`
- `evaluator_inconsistencies.csv`

### 接口

```python
class MultiImageStrategyValidator:
    """验证多图任务的图像策略"""

    def __init__(self, log_dir: str, simulator_path: str, task_dir: str):
        pass

    def analyze_image_sending_stats(self) -> Dict:
        """统计图像发送情况"""
        pass

    def compare_simulator_strategies(self) -> Dict:
        """对比不同simulator的策略"""
        pass

    def check_task_definition_alignment(self) -> List[Dict]:
        """检查任务定义对齐"""
        pass

    def verify_evaluator_awareness(self) -> Dict:
        """验证evaluator的图像感知"""
        pass

    def generate_report(self) -> Tuple[Dict, str]:
        pass
```

## 协作要求

### 依赖
- **可并行**: 与Task 1.6并行（组C）
- **被依赖**: Task 2.5（多图策略统一）需要这个

### 数据共享
- 报告: `round3/results/phase1_1.5_multi_image.json`

## 成功标准

- [ ] 统计至少100个AC任务的turns
- [ ] 明确两种simulator策略的差异
- [ ] 找出所有任务定义不一致的cases
- [ ] 验证evaluator的图像感知问题
- [ ] 提供修复建议

## 时间估算
- 约4小时

---

**并行组**: C (与Task 1.6并行)
**优先级**: P1
**预估难度**: Medium
