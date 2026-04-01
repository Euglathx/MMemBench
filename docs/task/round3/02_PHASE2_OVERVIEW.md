# Phase 2: 架构修复方案概述

## 目标

根据Phase 1的验证结果，设计并实现系统性修复方案。

## 任务列表

| ID | 任务名称 | 依赖Phase1 | 预估时间 | 并行组 |
|----|---------|-----------|---------|--------|
| 2.1 | 图像发送管道修复 | 1.1 | 2-3h | D |
| 2.2 | Turn-level Ground Truth设计与实现 | 1.3 | 3-4h | E |
| 2.3 | 评分公式重构 | 1.2 | 2-3h | E |
| 2.4 | Simulator真值校验机制 | 1.4 | 3h | F |
| 2.5 | 多图策略统一 | 1.5 | 2-3h | F |
| 2.6 | Evaluator状态管理重构 | 1.6 | 3-4h | G |

## 修复原则

1. **最小侵入性**: 尽量不改变现有接口
2. **向后兼容**: 修复后应能处理旧的run logs
3. **可配置性**: 修复应该是可选配置，不是硬编码
4. **可测试性**: 每个修复都要有单元测试

## 关键修复点

### 2.1 图像发送管道修复

**问题**: images_sent为空，模型收不到图像

**修复方向**:
- 修复_get_images_for_turn()中的路径解析
- 确保Path.exists()检查正确的目录
- 添加图像加载失败的日志和错误处理
- 验证API payload中的image_url格式

**输出**: 修复后的strategic_simulator.py，确保images_sent正确

### 2.2 Turn-level Ground Truth设计与实现

**问题**: 所有turn使用task-level expected_answer

**修复方向**:
- 设计TurnGroundTruth数据结构
- 在TaskState中添加turn_ground_truths字段
- 修改_generate_question()生成turn-specific expected_answer
- 修改evaluator接收turn-level expected_answer

**输出**: 新的数据结构和修改后的simulator/evaluator

### 2.3 评分公式重构

**问题**: LLM Judge满分但final score低

**修复方向**:
- 调整hard_score默认值（0.1-0.3 → 0.5中性值）
- 或修改权重组合逻辑（llm_judge_weight=1.0当available时）
- 或只在llm_judge为null时使用hard_scores
- 添加score calculation的详细日志

**输出**: 修改后的evaluator.py的evaluate_response()

### 2.4 Simulator真值校验机制

**问题**: Simulator将模型错误输出当成事实

**修复方向**:
- 添加_validate_model_claims()方法
- 在生成下一轮问题前，校验上一轮的claims
- 维护validated_claims vs unvalidated_claims
- 修改prompt生成逻辑，只引用validated claims

**输出**: 修改后的strategic_simulator.py

### 2.5 多图策略统一

**问题**: 图像注入策略不一致，任务定义不对齐

**修复方向**:
- 统一StrategicSimulator和LLMUserSimulator的策略
- 实现ImageInjectionPolicy配置
- 修复AC任务的expected_answer定义
- 传递images_sent给evaluator

**输出**: 修改后的simulators和task_generators

### 2.6 Evaluator状态管理重构

**问题**: 判断不一致，分数像常数

**修复方向**:
- 标准化LLM Judge的evidence提供方式
- 确保所有维度分数都动态更新
- 实现EvaluatorStateSnapshot用于调试
- 添加判断一致性检查

**输出**: 修改后的evaluator.py

## 并行执行策略

- **组D（独立）**: Task 2.1（图像修复最紧急）
- **组E（可并行）**: Task 2.2 + 2.3（逻辑相关但可以并行设计接口）
- **组F（可并行）**: Task 2.4 + 2.5（simulator相关）
- **组G（独立）**: Task 2.6（evaluator独立模块）

**推荐顺序**:
1. 先完成2.1（阻塞性最高）
2. 并行2.2+2.3+2.4+2.5
3. 最后2.6

## 详细文档

每个任务都有详细的设计文档（待创建）:
- `02_PHASE2_TASK_2.X_<NAME>.md`

包含：
- 修复设计
- 接口定义
- 实现步骤
- 单元测试
- 集成要求

---

**Phase 2预计时间**: 15-20小时（串行）或8-10小时（并行）
