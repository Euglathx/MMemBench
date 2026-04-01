# Round 3: 评审问题根本性修复计划

## 紧急声明

这份评审意见揭示的问题**极其严重**，触及了M3Bench评估系统的核心可信度。这不是简单的bug修复，而是需要对评估架构进行系统性重构。

## 评审意见核心问题总结

### 🚨 P0级别问题（立即致命）

1. **图像完全未发送** (新发现，比评审意见更严重)
   - 所有run log显示 `images_sent: []`
   - 模型一直回答"I cannot view images"
   - 整个视觉评测完全失效

2. **评估器"接错了信号"** (评审意见问题1)
   - LLM Judge给10分，最终score却<0.7导致fail
   - 说明final score计算没有正确使用llm_judge_output
   - 或hard_score权重过大且使用了错误的ground truth

3. **Turn级别的expected_answer错位** (评审意见问题1.2)
   - 每个turn的评估仍在用task-level expected_answer
   - 导致中间步骤天然偏低
   - 鼓励模型泄露最终答案（违背Information Decoupling设计目标）

### 🔴 P1级别问题（系统性缺陷）

4. **Simulator将模型输出当成事实** (评审意见问题2)
   - 下一轮提问把模型错误输出写成"You correctly noted..."
   - 造成错误自我强化
   - 污染"回马枪验证"机制

5. **多图任务的图像注入策略混乱** (评审意见问题3)
   - 每轮都发送所有图像，但问题只针对单图
   - cross-image归因混乱
   - StrategicSimulator vs LLMUserSimulator策略不一致

6. **任务定义不一致** (评审意见问题5)
   - AC任务：question要求比较，expected_answer只标注单图
   - images有3张，但answer_image_idx只指向一张
   - Evaluator不知道当前turn实际发送了哪些图像

### 🟡 P2级别问题（可信度风险）

7. **Evaluator对同一图像的判断前后矛盾** (评审意见问题4)
   - 同一张图中knife位置的判断在不同turn自相矛盾
   - Judge prompt或证据约束存在漂移

8. **Faithfulness/Robustness等分数像常数** (评审意见问题1.3)
   - 某些维度分数几乎不随turn变化
   - 可能是默认值或字段映射错误

9. **Phase名称与架构文档不一致** (评审意见问题5)
   - 文档宣称Phase 1~4，实际日志phase名称不同
   - 可能只是命名，但需要确认实现是否偏差

## 三阶段修复策略

### Phase 1: 验证与诊断（Debug Scripts）

**目标**: 用debug脚本验证每个评审问题，量化其严重程度，定位根因

| 任务ID | 任务名称 | 并行组 |
|--------|---------|--------|
| 1.1 | 图像发送验证 | A |
| 1.2 | 评分公式验证 | A |
| 1.3 | Expected Answer追踪 | B |
| 1.4 | Simulator提示词检查 | B |
| 1.5 | 多图策略一致性检查 | C |
| 1.6 | 评估器内部状态追踪 | C |

**并行策略**:
- 组A: 最紧急的两个问题，可以并行验证
- 组B: 涉及turn-level逻辑，可以并行
- 组C: 涉及多图和跨turn状态，可以并行

### Phase 2: 架构修复（Fix Design）

**目标**: 设计修复方案，确保Information Decoupling和评估独立性

| 任务ID | 任务名称 | 依赖 | 并行组 |
|--------|---------|------|--------|
| 2.1 | 图像发送管道修复 | 1.1 | D |
| 2.2 | Turn-level Ground Truth设计 | 1.3 | E |
| 2.3 | 评分公式重构 | 1.2 | E |
| 2.4 | Simulator真值校验机制 | 1.4 | F |
| 2.5 | 多图策略统一 | 1.5 | F |
| 2.6 | Evaluator状态管理重构 | 1.6 | G |

**并行策略**:
- 组D: 最紧急，独立修复
- 组E: 涉及ground truth和评分，逻辑相关但可以并行设计接口
- 组F: 涉及simulator行为，可以并行设计
- 组G: 涉及evaluator状态，独立模块

### Phase 3: 严格验证（Validation Scripts）

**目标**: 可量化验证，确保问题不再出现

| 任务ID | 任务名称 | 依赖 | 并行组 |
|--------|---------|------|--------|
| 3.1 | 图像发送完整性测试 | 2.1 | H |
| 3.2 | 评分公式正确性测试 | 2.3 | H |
| 3.3 | Turn-level Ground Truth覆盖测试 | 2.2 | I |
| 3.4 | Simulator真值一致性测试 | 2.4 | I |
| 3.5 | 多图任务端到端测试 | 2.5 | J |
| 3.6 | 评估器状态一致性测试 | 2.6 | J |
| 3.7 | 回归测试套件 | all | K |

**并行策略**:
- 组H: 最基础的测试，可以并行
- 组I: 涉及turn-level逻辑，可以并行
- 组J: 涉及复杂任务，可以并行
- 组K: 回归测试，需要等所有修复完成

## 严厉的验证原则

### 验证脚本必须满足：

1. **零容忍原则**:
   - 任何维度的验证失败都必须FAIL整个测试
   - 不接受"部分通过"或"基本正确"

2. **可量化反馈**:
   - 每个问题必须有明确的数值指标
   - 例如: "图像发送率: 0/100轮" → FAIL
   - 例如: "Score公式误差: >10%" → FAIL

3. **边界case覆盖**:
   - 必须测试极端情况
   - 例如: 单图任务、3图任务、10图任务
   - 例如: turn 1、turn 20、turn 50

4. **回归检测**:
   - 修复一个问题不能引入新问题
   - 必须有完整的before/after对比

5. **人工可审查**:
   - 每个验证失败必须输出详细日志
   - 包括预期值、实际值、差异原因

## 关键接口定义

### 1. Turn-level Ground Truth

```python
@dataclass
class TurnGroundTruth:
    """每个turn的独立ground truth"""
    turn_id: int
    phase: str
    action_type: str

    # 这个turn应该评估什么
    evaluation_target: str  # "entity_identification" | "spatial_relation" | "final_answer"
    expected_answer: str  # 这个turn的expected answer
    evaluation_criteria: Dict[str, Any]  # 这个turn的评分标准

    # 这个turn需要哪些图像
    required_images: List[int]  # 图像索引列表
    image_labels: Dict[int, str]  # {0: "Image 0", 1: "Image 1"}

    # 真值校验信息
    ground_truth_facts: List[Dict[str, Any]]  # 这个turn涉及的真实事实
    acceptable_variations: List[str]  # 可接受的回答变体
```

### 2. Image Injection Protocol

```python
@dataclass
class ImageInjectionPolicy:
    """图像注入策略"""
    policy_type: str  # "all" | "progressive" | "selective" | "target_only"

    # 对于每个action type，应该发送哪些图像
    action_image_mapping: Dict[str, List[int]]

    # 图像标签策略
    label_images: bool  # 是否在message中显式标注"Image 0", "Image 1"
    label_format: str  # "numeric" | "descriptive"
```

### 3. Evaluator State Snapshot

```python
@dataclass
class EvaluatorStateSnapshot:
    """Evaluator在每个turn的状态快照"""
    turn_id: int

    # Ground truth state
    current_ground_truth: TurnGroundTruth
    task_level_ground_truth: Dict[str, Any]

    # Cross-image tracking
    cross_image_mapping: Dict[str, Dict]
    images_actually_sent: List[str]  # 实际发送的图像路径

    # Memory state
    key_facts: Dict[str, Any]
    injected_falsehoods: List[Dict]

    # Previous responses (for consistency check)
    previous_responses: List[str]
```

### 4. Score Calculation Protocol

```python
@dataclass
class ScoreCalculationTrace:
    """评分计算的完整追踪"""
    turn_id: int

    # Input
    llm_judge_output: Optional[Dict]  # LLM Judge的原始输出
    hard_rule_scores: Dict[str, float]  # 硬规则评分

    # Weights
    llm_judge_weight: float
    score_weights: Dict[str, float]  # 每个维度的权重

    # Calculation steps
    weighted_scores: Dict[str, float]  # 加权后的分数
    overall_score: float
    threshold: float
    level_passed: bool

    # Diagnosis
    score_breakdown: str  # 人类可读的评分分解
```

## 接下来的工作流程

1. **阅读各个任务文档**: `01_PHASE1_*.md`, `02_PHASE2_*.md`, `03_PHASE3_*.md`

2. **选择一个窗口开始工作**:
   - 窗口1: Phase 1.1 + 1.2 (最紧急的验证)
   - 窗口2: Phase 1.3 + 1.4 (turn-level逻辑验证)
   - 窗口3: Phase 1.5 + 1.6 (多图和状态验证)

3. **每个窗口完成后**:
   - 运行验证脚本
   - 将结果写入 `round3/results/phase1_*.json`
   - 汇总到 `round3/results/phase1_summary.md`

4. **Phase 1全部完成后**:
   - 召开"Phase 1验证结果评审会"
   - 根据验证结果调整Phase 2的修复优先级
   - 开始Phase 2的并行修复

5. **Phase 2全部完成后**:
   - 运行Phase 3的验证套件
   - 如果任何测试FAIL，回到Phase 2修复
   - 全部PASS后，准备Round 4

## 成功标准

### Phase 1成功标准:
- [ ] 所有6个验证脚本运行无错误
- [ ] 每个评审问题都有量化的严重程度报告
- [ ] 根因定位到具体的代码行和逻辑

### Phase 2成功标准:
- [ ] 所有6个修复设计有完整的接口定义
- [ ] 修复设计通过架构评审（可以是人工或LLM）
- [ ] 修复代码实现并通过单元测试

### Phase 3成功标准:
- [ ] 所有7个验证测试100% PASS
- [ ] 回归测试套件覆盖所有任务类型
- [ ] 生成可量化的改进报告（修复前vs修复后）

## 时间估算（仅供参考，不作承诺）

- Phase 1: 3-4个并行窗口，每个1-2小时
- Phase 2: 4-5个并行窗口，每个2-3小时
- Phase 3: 3-4个并行窗口，每个1-2小时
- 总计: 约15-20小时的实际编码时间（如果高度并行）

## 风险提示

1. **连锁反应风险**: 修复一个问题可能触发其他问题
2. **数据兼容性风险**: 修复后的代码可能与现有run logs不兼容
3. **性能风险**: Turn-level ground truth可能增加计算开销
4. **架构风险**: 可能需要重构核心类的接口

**应对策略**: 每个Phase都有完整的验证和回滚机制

---

**最后的警告**:

这份评审意见不是在挑刺，而是在救命。如果这些问题不解决，M3Bench的论文数据将完全不可信。

请以最严厉的态度对待每一个问题，不要试图"局部修补"或"差不多就行"。

我们需要的是**系统性重构**，而不是打补丁。
