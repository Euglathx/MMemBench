# Round 4 快速启动指南

**请先阅读**: [README.md](./README.md) 了解整体计划

---

## Phase 1 快速启动

### Window 1: 配置审计

**任务**: 检查所有配置，找出 Round 3 修复需要的配置是否正确设置

**执行**:
1. 阅读 [phase1-window1.md](./phase1-window1.md)
2. 工具推荐: Read, Grep, Glob
3. 预计时间: 3 小时

**快速命令**:
```bash
# 读取配置文件
Read config/multimodal.yaml
Read config/attack_evaluation_standard.yaml

# 搜索初始化点
Grep pattern="StrategicSimulator\s*\(" output_mode="content"
Grep pattern="Evaluator\s*\(" output_mode="content"

# 检查代码默认值
Read src/simulator/evaluator.py offset=140 limit=20
```

**输出**:
- docs/task/round4/phase1_config_audit.md
- docs/task/round4/phase1_config_diff.csv

---

### Window 2: 代码逻辑验证

**任务**: 运行测试任务，验证 Round 3 的 6 个修复是否生效

**执行**:
1. 阅读 [phase1-window2.md](./phase1-window2.md)
2. 创建测试脚本
3. 预计时间: 4 小时

**快速命令**:
```bash
# 创建并运行测试脚本
cd /e/Code/M3Bench/M3Bench_new
Write scripts/round4_minimal_test.py
python scripts/round4_minimal_test.py

# 检查生成的 logs
Read docs/task/round4/phase1_test_abr_log.json
Read docs/task/round4/phase1_test_ac_log.json
```

**输出**:
- scripts/round4_minimal_test.py
- docs/task/round4/phase1_test_abr_log.json
- docs/task/round4/phase1_test_ac_log.json
- docs/task/round4/phase1_code_verification_report.md
- docs/task/round4/phase1_failed_checkpoints.csv

---

## Phase 2 快速启动

### Window 1: 评估框架重构 🔴 最关键

**任务**: 重新设计评估框架，从 "expected answer" → "turn purpose"

**执行**:
1. 阅读 [phase2-window1.md](./phase2-window1.md)
2. 实现 TurnEvaluationContext 数据类
3. 重构 LLM Judge prompt
4. 预计时间: 4-6 小时

**关键文件**:
- src/simulator/strategic_simulator.py
- src/simulator/evaluator.py

**核心变化**:
```python
# 新增数据类
@dataclass
class TurnEvaluationContext:
    turn_purpose: str                    # "entity_grounding", "reliability_check", "final_answer"
    is_reliability_check: bool
    task_ground_truth: str               # 重命名自 expected_answer
    evaluation_focus: List[str]

# 新增方法
def _generate_turn_evaluation_context(...)
def _build_llm_judge_prompt_v2(...)
```

**输出**:
- 修改后的 src/simulator/strategic_simulator.py
- 修改后的 src/simulator/evaluator.py
- tests/test_turn_evaluation_context.py
- docs/task/round4/phase2_fix2.0_report.md

---

### Window 2: Prompt 图像数量匹配

**任务**: 修复"发送 3 张图但说 'both images'"

**执行**:
1. 阅读 [phase2-window2.md](./phase2-window2.md)
2. 实现 `get_image_reference_phrase()` 函数
3. 替换所有硬编码的 "both images"
4. 预计时间: 2 小时

**快速搜索**:
```bash
Grep pattern="both images" output_mode="content"
Grep pattern="the image" output_mode="content"
```

**核心函数**:
```python
def get_image_reference_phrase(image_count: int) -> str:
    if image_count == 1:
        return "the image"
    elif image_count == 2:
        return "both images"
    else:
        return f"all {image_count} images"
```

**输出**:
- 修改后的 prompt 生成代码
- tests/test_image_reference_phrase.py
- docs/task/round4/phase2_fix2.1_report.md

---

### Window 3: Evaluator 视觉一致性

**任务**: 修复 Evaluator 对同一对象的判断前后矛盾

**执行**:
1. 阅读 [phase2-window3.md](./phase2-window3.md)
2. 实现视觉事实缓存
3. 检测和解决矛盾
4. 预计时间: 2-3 小时

**关键文件**:
- src/simulator/evaluator.py

**核心方法**:
```python
# 在 Evaluator 中添加
self.visual_fact_cache = {}  # (task_id, object, attribute) -> value

def _cache_visual_fact(self, task_id, obj, attr, value, turn_id):
    # 检测冲突，返回应该使用的值
    ...
```

**输出**:
- 修改后的 src/simulator/evaluator.py
- scripts/round4_test_fix2.2.py
- docs/task/round4/phase2_fix2.2_report.md

---

### Window 4: Consistency Check 图像传递

**任务**: 修复最终 consistency check 没传图的问题

**执行**:
1. 阅读 [phase2-window4.md](./phase2-window4.md)
2. 检查 `run_consistency_check()` 方法
3. 确保图像参数传递
4. 预计时间: 1-2 小时

**关键检查**:
```python
def run_consistency_check(self):
    # 检查：是否调用了 _get_images_for_turn()?
    images_to_send = self._get_images_for_turn("consistency_check")  # ✓

    # 检查：是否传递给模型?
    response = self.target_model.generate(
        messages=[...],
        images=images_to_send  # ✓ 应该传递
    )
```

**输出**:
- 修改后的 src/simulator/strategic_simulator.py
- scripts/round4_test_fix2.3.py
- docs/task/round4/phase2_fix2.3_report.md

---

## 并行执行建议

### 如果有 2 个 windows:

**Window A**:
1. Phase 1 Window 1 (3h)
2. Phase 2 Window 1 (4-6h) ← 最关键

**Window B**:
1. Phase 1 Window 2 (4h)
2. Phase 2 Window 2 (2h)
3. Phase 2 Window 4 (1-2h)

**时间**: 约 10-13 小时

---

### 如果有 3 个 windows:

**Window A**:
1. Phase 1 Window 1 (3h)
2. Phase 2 Window 1 (4-6h) ← 最关键

**Window B**:
1. Phase 1 Window 2 (4h)
2. Phase 2 Window 2 (2h)

**Window C**:
1. 等待 Phase 1 完成
2. Phase 2 Window 3 (2-3h)
3. Phase 2 Window 4 (1-2h)

**时间**: 约 9-12 小时

---

### 如果有 4 个 windows:

**Phase 1** (并行):
- Window A: Phase 1 Window 1 (3h)
- Window B: Phase 1 Window 2 (4h)

**Phase 2** (并行):
- Window A: Phase 2 Window 1 (4-6h) ← 最关键
- Window B: Phase 2 Window 2 (2h)
- Window C: Phase 2 Window 3 (2-3h)
- Window D: Phase 2 Window 4 (1-2h)

**时间**: 约 7-10 小时

---

## 工作流程

```
开始 → 选择 Phase & Window → 阅读任务文件 → 执行任务 → 生成输出 → 完成

每个 Window:
1. 阅读任务文件（XXX-windowY.md）
2. 理解背景和要求
3. 执行任务（使用推荐工具）
4. 生成输出文件
5. 填写"任务开始/完成时间"和"执行人"
6. 标记为完成 ✓
```

---

## 检查清单

### Phase 1 完成检查
- [ ] Window 1: phase1_config_audit.md 已生成
- [ ] Window 1: phase1_config_diff.csv 已生成
- [ ] Window 2: scripts/round4_minimal_test.py 已创建并运行
- [ ] Window 2: phase1_test_abr_log.json 已生成
- [ ] Window 2: phase1_test_ac_log.json 已生成
- [ ] Window 2: phase1_code_verification_report.md 已生成
- [ ] Window 2: phase1_failed_checkpoints.csv 已生成

### Phase 2 完成检查
- [ ] Window 1: TurnEvaluationContext 已实现
- [ ] Window 1: LLM Judge prompt 已重构
- [ ] Window 1: phase2_fix2.0_report.md 已生成
- [ ] Window 2: get_image_reference_phrase() 已实现
- [ ] Window 2: 所有 "both images" 已替换
- [ ] Window 2: phase2_fix2.1_report.md 已生成
- [ ] Window 3: visual_fact_cache 已实现
- [ ] Window 3: phase2_fix2.2_report.md 已生成
- [ ] Window 4: consistency_check 图像传递已修复
- [ ] Window 4: phase2_fix2.3_report.md 已生成

---

## 常见问题

**Q: 我应该从哪个 window 开始？**
A: 如果单人执行，按顺序：Phase 1 Window 1 → Phase 1 Window 2 → Phase 2 Window 1（最关键）。如果多人，Phase 1 的两个 windows 可以完全并行。

**Q: Phase 2 Window 1 为什么最关键？**
A: 这是用户反馈的核心问题，涉及评估框架的概念重构，不是简单的 bug 修复。

**Q: 如果时间不够怎么办？**
A: 优先完成 Phase 1 全部 + Phase 2 Window 1。其他 Phase 2 任务可以降级。

**Q: 多个 windows 修改同一个文件会冲突吗？**
A: Window 1 和 Window 3 都可能修改 `evaluator.py`。建议 Window 3 等待 Window 1 完成，或提前沟通。

**Q: 我需要运行 Round 3 的单元测试吗？**
A: 不需要。Phase 1 的测试是集成测试（运行完整任务），Phase 2 每个修复有自己的测试。

---

## 支持资源

- **总览**: [README.md](./README.md)
- **原始计划**: `C:\Users\16979\.claude\plans\warm-beaming-hopper.md`
- **评审报告**: `C:\Users\16979\Downloads\MMemBench_log_review_report.md`
- **Round 3 报告**: `docs/task/round3/report/`

---

**祝执行顺利！如有问题，查看具体任务文件的"注意事项"章节。**
