# 新旧架构对比

## 架构对比图

### 旧架构 (test_user_simulator.py 原版)
```
┌─────────────────────────────────────┐
│      SimpleUserSimulator            │
│                                     │
│  ┌──────────────────────────────┐  │
│  │  select_action()             │  │
│  │    (耦合在一起)              │  │
│  └──────────────────────────────┘  │
│             ↓                       │
│  ┌──────────────────────────────┐  │
│  │  generate_query()            │  │
│  │    ├─ if follow_up:          │  │
│  │    │   └─ extract_entities() │  │  ← 重复提取
│  │    ├─ elif guidance:         │  │
│  │    │   └─ extract_entities() │  │  ← 重复提取
│  │    └─ elif update:           │  │
│  │        └─ extract_entities() │  │  ← 重复提取
│  └──────────────────────────────┘  │
└─────────────────────────────────────┘
```

### 新架构 (重构后)
```
┌─────────────────────────────────────────────────────────────┐
│                     UserSimulator                            │
│  (主控制器，只负责协调)                                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐    ┌──────────────┐    ┌─────────────────┐
│ Entity        │    │  Action      │    │  Query          │
│ Extractor     │───▶│  Selector    │───▶│  Generator      │
│ 提取一次       │    │ 使用entities  │    │ 使用entities    │
│ 多处复用       │    │ 选择动作      │    │ 填充模板        │
└───────────────┘    └──────────────┘    └─────────────────┘
```

## 代码对比

### 场景：需要优化entity提取

#### 旧架构 - 需要改8个地方
```python
class SimpleUserSimulator:
    def generate_query(self, action_type, vlm_response, task, length='medium'):
        # 每个动作都要提取entity
        entities = self._extract_entities(vlm_response)  # 改这里 ①

        if action_type == 'follow_up':
            entity = entities[0] if entities else "这个"
            ...
        elif action_type == 'guidance':
            entities = self._extract_entities(vlm_response)  # 改这里 ②
            ...
        elif action_type == 'negation':
            entities = self._extract_entities(vlm_response)  # 改这里 ③
            ...
        # ... 还有5个地方需要改

    def _extract_entities(self, text):  # 改这里 ⑨
        # 简单正则
        chinese_entities = re.findall(r'(人|伞|...)', text)
        return entities if entities else ["物体"]
```

**问题**:
- ❌ 需要修改多处
- ❌ 容易遗漏
- ❌ 测试困难
- ❌ 风险高

#### 新架构 - 只改1个文件
```python
# entity_extractor.py - 只改这一个文件！
class EntityExtractor:
    def _extract_simple(self, text, context):
        # 旧实现: 简单正则
        # entities = ...

        # 新实现: 使用NER
        import spacy
        nlp = spacy.load("en_core_web_sm")
        doc = nlp(text)
        entities = {
            "objects": [ent.text for ent in doc.ents if ent.label_ == "OBJECT"],
            ...
        }
        return entities
```

**优势**:
- ✅ 只改一个文件
- ✅ 不影响其他模块
- ✅ 易于测试
- ✅ 风险低

---

## 功能对比

| 功能 | 旧架构 | 新架构 |
|-----|-------|-------|
| **Entity提取** | 散落在各个动作中 | 统一在EntityExtractor |
| **提取模式** | 只有简单正则 | 支持 simple/ner/llm 三种 |
| **动作选择** | 硬编码在select_action | 独立的ActionSelector模块 |
| **选择策略** | 只有基于轮次的规则 | 支持 rule_based/random/weighted |
| **Query生成** | 与entity提取耦合 | 独立的QueryGenerator模块 |
| **模板管理** | 硬编码字典 | 使用PromptTemplates |
| **可配置性** | 有限 | 高度可配置 |
| **可测试性** | 困难 | 每个模块可独立测试 |
| **可扩展性** | 困难 | 容易扩展 |

---

## 使用对比

### 旧架构
```python
simulator = SimpleUserSimulator(allowed_actions=['follow_up', 'guidance'])

# 只能在初始化时配置
# 无法动态调整
# 无法获取统计信息
```

### 新架构
```python
simulator = UserSimulator(
    task=task,
    extraction_mode="simple",      # 可配置
    action_strategy="rule_based",  # 可配置
    allowed_actions=None            # 可配置
)

# 动态配置
simulator.set_extraction_mode("ner")
simulator.set_action_strategy("weighted")
simulator.set_allowed_actions(["follow_up", "guidance"])
simulator.set_action_weight("follow_up", 0.5)

# 获取统计
action_dist = simulator.get_action_distribution()
entity_coverage = simulator.get_entity_coverage()
```

---

## 实验灵活性对比

### 旧架构：修改提取策略

**步骤**:
1. 修改 `_extract_entities()` 方法
2. 测试所有8个动作是否正常
3. 如果出错，需要逐个调试

**耗时**: 2-3小时

### 新架构：修改提取策略

**步骤**:
1. 在 `EntityExtractor` 添加新方法
2. 切换模式: `simulator.set_extraction_mode("ner")`
3. 独立测试EntityExtractor

**耗时**: 30分钟

---

## 渐进优化路径对比

### 旧架构
```
发现entity提取不准
  ↓
改 _extract_entities()
  ↓
测试所有动作 (8个)
  ↓
发现某个动作出错
  ↓
调试 generate_query()
  ↓
又影响了其他动作
  ↓
继续调试...
  ↓
风险高，时间长
```

### 新架构
```
发现entity提取不准
  ↓
只改 EntityExtractor
  ↓
独立测试EntityExtractor
  ↓
通过测试
  ↓
其他模块完全不受影响 ✓
  ↓
风险低，时间短
```

---

## 性能对比

| 指标 | 旧架构 | 新架构 |
|-----|-------|-------|
| **Entity提取次数** | 每个动作1次 (重复) | 每轮1次 (复用) |
| **代码复杂度** | 高 (耦合) | 低 (解耦) |
| **维护成本** | 高 | 低 |
| **扩展成本** | 高 | 低 |
| **测试覆盖** | 困难 | 容易 |

---

## 可扩展性对比

### 添加新的Entity类型

#### 旧架构
```python
# 需要改多个地方
def _extract_entities(self, text):
    chinese_entities = re.findall(r'(人|伞|车)', text)  # 改这里 ①
    # ...
    return entities

def generate_query(self, action_type, ...):
    if action_type == 'follow_up':
        entity = entities[0]  # 可能需要改这里 ②
    elif action_type == 'guidance':
        # 可能需要改这里 ③
    # ...
```

#### 新架构
```python
# 只改一个文件
class EntityExtractor:
    def _init_entity_dict(self):
        self.object_keywords = [..., "新物体"]  # 只改这里！

    def _extract_simple(self, text, context):
        entities["new_type"] = []  # 添加新类型
        # ... 提取逻辑
        return entities
```

---

## 测试对比

### 旧架构 - 难以单元测试
```python
# 很难单独测试entity提取
# 因为它嵌入在generate_query中

def test_extract():
    simulator = SimpleUserSimulator()
    # 必须调用generate_query才能测试提取
    query = simulator.generate_query('follow_up', "图中有人", task)
    # 无法直接验证提取结果
```

### 新架构 - 易于单元测试
```python
# 可以单独测试每个模块

def test_entity_extraction():
    extractor = EntityExtractor()
    entities = extractor.extract("图中有一个人拿着伞")
    assert "人" in entities["objects"]
    assert "伞" in entities["objects"]

def test_action_selection():
    selector = ActionSelector(strategy="rule_based")
    action = selector.select(turn=1, history=[], entities={})
    assert action in ["follow_up", "guidance"]

def test_query_generation():
    generator = QueryGenerator()
    query = generator.generate(
        action_type="follow_up",
        entities={"objects": ["人"]}
    )
    assert "人" in query
```

---

## 实际案例：优化entity提取准确率

### 旧架构流程
1. 修改 `_extract_entities()` - **30分钟**
2. 运行测试发现follow_up动作出错 - **15分钟**
3. 调试follow_up的entity使用 - **30分钟**
4. 修复后发现guidance也出错 - **15分钟**
5. 调试guidance - **30分钟**
6. 发现update动作也受影响 - **15分钟**
7. 继续调试... - **1小时**

**总耗时**: ~3小时
**风险**: 高（牵一发动全身）

### 新架构流程
1. 在EntityExtractor添加新方法 - **30分钟**
2. 单独测试EntityExtractor - **15分钟**
3. 通过测试 - ✓
4. 切换模式运行完整测试 - **10分钟**
5. 完成 - ✓

**总耗时**: ~1小时
**风险**: 低（其他模块不受影响）

---

## 总结

### 旧架构特点
- ✅ 简单直接
- ❌ 耦合度高
- ❌ 难以维护
- ❌ 扩展困难
- ❌ 测试困难

### 新架构特点
- ✅ 模块解耦
- ✅ 易于维护
- ✅ 灵活扩展
- ✅ 独立测试
- ✅ 低风险优化
- ✅ 配置灵活

### 重构投资回报

**成本**:
- 重构时间: ~半天
- 学习成本: 很低（架构清晰）

**收益**:
- 每次修改节省: 1-2小时
- 降低出错风险: 50%+
- 提升可维护性: 显著
- 支持并行开发: 每个模块可独立开发

**建议**: 如果项目还在早期，**强烈推荐立即重构**！