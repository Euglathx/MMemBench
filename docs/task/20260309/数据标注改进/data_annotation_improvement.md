# 数据标注改进：引入 Latent State Schema

> **安全性原则**: 本文档所有改动均为 **纯增量**。现有任务 JSONL 的所有字段保持不变，`state_schema` 作为一个可选的新增字段附加到每条记录中。生成器通过 **后处理 hook** 扩展，不修改原有 `_generate_*()` 方法的逻辑。现有数据如果没有 `state_schema` 字段，下游模块（simulator、evaluator）应当优雅降级为原有行为。

---

## 0. 跨文档接口契约

本文档是三份改进文档的 **数据基础层**，它定义的 `state_schema` 格式被其他两份文档消费：

```
┌─────────────────────────────────────────────────────────────────┐
│  本文档: 数据标注改进                                            │
│  产出: state_schema 字段 (附加到 task JSONL)                     │
│  产出: state_schema_types.py (StateSchema, StateVariable 等)     │
│  产出: StateSchemaConverter 类 (dataprovider/)                   │
├─────────────────────────────────────────────────────────────────┤
│                          ▼ 消费者                                │
│  对话和测试改进 → 读取 state_schema 初始化 TaskProgress          │
│                → 用 probing_variables 指导阶段设计               │
│                → 用 final_question_variables 控制信息隔离         │
│                                                                  │
│  状态测试改进   → 读取 state_schema 初始化 StateEvolutionTracker  │
│                → 用 variables 构建 ExpectedStateAtTurn            │
│                → 用 dependencies 诊断失败模式                    │
└─────────────────────────────────────────────────────────────────┘
```

**共享类型定义文件**: `src/simulator/state_schema_types.py`（见第 4.1 节）

---

## 1. 任务背景

### 1.1 论文目标

论文声称 M3Bench 测试的是 **context management 能力**——即模型将任务相关信息压缩为状态（state）并在交互过程中对其进行选择性更新、保留与丢弃的能力。论文进一步指出：

> "每个任务样本背后都有一个可标注的 latent state schema，用于评价任务状态在每一步中是否被正确执行。"

这意味着数据标注应该包含 **独立于最终问题的状态变量集合**，而非仅仅是最终答案的推导依据。

### 1.2 为什么需要改进

当前的数据标注以"回答最终问题所需的证据"为导向，缺少对 **任务进行过程中应该被模型维护的完整状态** 的显式描述。这导致：

1. 无法在对话中途验证模型是否正确维护了状态
2. 无法区分"模型恰好答对了最终问题"和"模型确实一路维护了正确的状态"
3. 无法设计与最终问题无关但需要被记住的"干扰性但真实的事实"

---

## 2. 涉及的文件和接口

### 2.1 现有文件（只读参考，不修改）

| 文件 | 作用 | 为什么不改 |
|------|------|------------|
| `dataprovider/task_generators.py` | 各任务类型的具体生成逻辑（~2150行） | 核心生成逻辑完整，通过 hook 扩展 |
| `dataprovider/generator_v2.py` | 配置驱动的统一任务生成器（~797行） | 流水线不变，在最后一步追加 schema |
| `dataprovider/loader.py` | 多数据集统一加载器（~1294行） | 加载逻辑不变，可能需要新增辅助查询方法 |
| `dataset_configs.yaml` | 主配置文件 | 不需要修改，schema 生成由代码驱动 |

### 2.2 新增文件

| 文件 | 作用 |
|------|------|
| **`src/simulator/state_schema_types.py`** | 共享类型定义（StateSchema, StateVariable 等），三份文档共用 |
| **`dataprovider/state_schema_converter.py`** | 从现有 evidence JSON 转化出 state_schema |
| **`dataprovider/state_schema_hooks.py`** | 生成器的后处理 hook，在生成完成后追加 state_schema |
| **`tools/convert_annotations_to_schema.py`** | 批量转化脚本 |

### 2.3 现有文件的安全扩展

| 文件 | 扩展方式 | 原有接口变化 |
|------|----------|:------------:|
| `dataprovider/loader.py` | 新增 `get_all_objects_by_image_id()` 方法 | 无 |
| `dataprovider/task_generators.py` | 各 Generator 子类中 **可选** 新增 `_build_state_schema()` 方法 | 无（不修改 `_generate_*()` 的调用链） |

---

## 3. 当前进度和缺陷

### 3.1 已有的基础

- 5 种任务类型（AC, ABR, VNF, RC, LNF）的生成器已实现
- `reasoning_evidence` 字段提供了答案推导所需的结构化信息
- ABR 任务的 `formal_representation` 已经有了 Objects-Attributes-Relations 的形式化表示，最接近 state schema 的雏形
- VNF 任务的 `all_objects` 字段包含完整的场景物体列表

### 3.2 核心缺陷

**缺陷 1: reasoning_evidence 只服务于最终答案**

例如在 AC 任务中，`reasoning_evidence` 只包含目标类别（dog）的计数，但图片中的其他物体（person, car, tree）完全没有被标注。在真正的状态维护测试中，这些"非目标物体"也应该被标注。

**缺陷 2: 缺少状态变量的生命周期标注**

没有标注每个状态变量在对话过程中应该经历的操作（观察 → 确认 → 挑战 → 回忆）。

**缺陷 3: 缺少变量间的依赖关系标注**

派生变量（如 `comparison_result`）依赖于基础变量（如 `img1_dog_count`），这种依赖关系目前没有被标注。

### 3.3 各任务类型现有 Evidence 结构与转化可行性

| 任务类型 | 转化可行性 | primary variables | auxiliary variables | 需要额外操作 |
|----------|:---------:|:-----------------:|:-------------------:|:------------:|
| VNF | ★★★★★ | 完整（bbox, count, category） | 完整（`all_objects` 字段） | 无 |
| RC | ★★★★☆ | 完整（count, category） | 部分（`co_occurring`） | 无 |
| ABR | ★★★★☆ | 完整（start/end object, spatial_relation, reasoning_chain） | 缺失 | 生成器 hook 补 `all_objects_in_image` |
| AC | ★★★☆☆ | 完整（bbox, area, category） | 缺失（无非目标物体） | 生成器 hook 补 `all_objects_in_image` |
| LNF | ★★★☆☆ | 部分（object_attributes） | 部分（distractor_source_samples） | 生成器 hook 补场景完整物体列表 |

---

## 4. 最终要求

### 4.1 共享类型定义（`src/simulator/state_schema_types.py`）

此文件是三份文档共用的类型基础，**必须先于其他所有代码实现**。

```python
"""
State Schema Types - 三份改进文档的共享类型定义
===============================================

本文件定义了 state_schema 相关的所有数据类型。
被以下模块消费:
  - dataprovider/state_schema_converter.py  (数据标注改进)
  - src/simulator/stateful_simulator.py     (对话和测试改进)
  - src/simulator/state_aware_evaluator.py  (状态测试改进)
  - src/simulator/state_evolution.py        (状态测试改进)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from enum import Enum


class VariableType(Enum):
    """状态变量类型"""
    COUNT = "count"
    ATTRIBUTE = "attribute"
    POSITION = "position"
    RELATION = "relation"
    BOOLEAN = "boolean"
    OBJECT_LIST = "object_list"
    DERIVED = "derived"


class VariableRelevance(Enum):
    """变量与最终问题的相关性"""
    PRIMARY = "primary"       # 与最终答案直接相关
    SECONDARY = "secondary"   # 间接相关
    AUXILIARY = "auxiliary"    # 不相关但应被记住


@dataclass
class StateVariable:
    """单个状态变量"""
    name: str
    value: Any
    var_type: VariableType
    source: str                              # e.g., 'image_0'
    relevance: VariableRelevance
    observable_from: List[str] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)  # 仅 derived 类型
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'value': self.value,
            'type': self.var_type.value,
            'source': self.source,
            'relevance': self.relevance.value,
            'observable_from': self.observable_from,
            'depends_on': self.depends_on,
            'description': self.description,
        }

    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> "StateVariable":
        return cls(
            name=name,
            value=data['value'],
            var_type=VariableType(data['type']),
            source=data.get('source', ''),
            relevance=VariableRelevance(data.get('relevance', 'primary')),
            observable_from=data.get('observable_from', []),
            depends_on=data.get('depends_on', []),
            description=data.get('description', ''),
        )


@dataclass
class Dependency:
    """变量间依赖关系"""
    from_var: str
    to_var: str
    dep_type: str  # 'determines', 'constrains', 'informs'

    def to_dict(self) -> Dict[str, str]:
        return {'from': self.from_var, 'to': self.to_var, 'type': self.dep_type}

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "Dependency":
        return cls(from_var=data['from'], to_var=data['to'], dep_type=data['type'])


@dataclass
class StateSchema:
    """完整的状态模式 - 每个任务样本一个"""
    variables: Dict[str, StateVariable]
    dependencies: List[Dependency]
    final_question_variables: List[str]
    probing_variables: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'variables': {name: var.to_dict() for name, var in self.variables.items()},
            'dependencies': [dep.to_dict() for dep in self.dependencies],
            'final_question_variables': self.final_question_variables,
            'probing_variables': self.probing_variables,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StateSchema":
        if not data:
            return cls(variables={}, dependencies=[], final_question_variables=[], probing_variables=[])
        variables = {name: StateVariable.from_dict(name, vdata) for name, vdata in data.get('variables', {}).items()}
        dependencies = [Dependency.from_dict(d) for d in data.get('dependencies', [])]
        return cls(
            variables=variables,
            dependencies=dependencies,
            final_question_variables=data.get('final_question_variables', []),
            probing_variables=data.get('probing_variables', []),
        )

    def get_primary_variables(self) -> Dict[str, StateVariable]:
        return {k: v for k, v in self.variables.items() if v.relevance == VariableRelevance.PRIMARY}

    def get_auxiliary_variables(self) -> Dict[str, StateVariable]:
        return {k: v for k, v in self.variables.items() if v.relevance == VariableRelevance.AUXILIARY}

    def get_variables_for_image(self, image_source: str) -> Dict[str, StateVariable]:
        return {k: v for k, v in self.variables.items() if image_source in v.observable_from}
```

### 4.2 目标数据结构

每个任务样本保留所有现有字段，**追加** `state_schema` 可选字段：

```python
{
    # ======= 现有字段，全部保持不变 =======
    'task_type': 'attribute_comparison',
    'images': ['img1.jpg', 'img2.jpg'],
    'question': 'Which image has the most dogs?',
    'answer': 'Image 1 has 3 dogs',
    'reasoning_evidence': [...],   # 保留！不删除

    # ======= 新增: 可选的 state_schema =======
    'state_schema': {               # 如果缺失，下游模块降级为原有行为
        'variables': {
            'v1_img0_dog_count': {
                'value': 3, 'type': 'count', 'source': 'image_0',
                'relevance': 'primary', 'observable_from': ['image_0'],
                'description': 'Number of dogs in Image 0'
            },
            'v2_img1_dog_count': {
                'value': 1, 'type': 'count', 'source': 'image_1',
                'relevance': 'primary', 'observable_from': ['image_1'],
            },
            'v3_img0_person_count': {
                'value': 2, 'type': 'count', 'source': 'image_0',
                'relevance': 'auxiliary',  # 与最终问题无关，但应该被记住
                'observable_from': ['image_0'],
            },
            'v4_comparison_result': {
                'value': 'Image 0', 'type': 'derived',
                'depends_on': ['v1_img0_dog_count', 'v2_img1_dog_count'],
                'relevance': 'primary',
            }
        },
        'dependencies': [
            {'from': 'v1_img0_dog_count', 'to': 'v4_comparison_result', 'type': 'determines'},
            {'from': 'v2_img1_dog_count', 'to': 'v4_comparison_result', 'type': 'determines'}
        ],
        'final_question_variables': ['v4_comparison_result'],
        'probing_variables': ['v1_img0_dog_count', 'v2_img1_dog_count', 'v3_img0_person_count']
    }
}
```

### 4.3 设计原则

1. **纯增量**: `state_schema` 是可选字段，缺失时不影响任何现有功能
2. **变量完备性**: 标注图片中所有可观察的关键事实，不仅仅是最终答案相关的
3. **分层 relevance**: 区分 primary / secondary / auxiliary 变量
4. **依赖可追踪**: derived 变量标注 depends_on
5. **转化优先**: 优先从现有 evidence 自动转化，而非重新生成

### 4.4 StateSchemaConverter — 从现有 evidence 转化

```python
# dataprovider/state_schema_converter.py
"""
从现有 evidence 文件转化出 state_schema。
不修改原始 evidence 文件，只生成新的 state_schema 字段。
"""

from src.simulator.state_schema_types import (
    StateSchema, StateVariable, Dependency,
    VariableType, VariableRelevance
)

class StateSchemaConverter:
    """将现有标注转化为 StateSchema 格式"""

    def convert(self, task: Dict, evidence: Dict) -> StateSchema:
        """统一入口，根据 task_type 分发"""
        task_type = task.get('task_type', '')
        converter_fn = {
            'visual_noise_filtering': self._convert_vnf,
            'relation_comparison': self._convert_rc,
            'attribute_bridge_reasoning': self._convert_abr,
            'attribute_comparison': self._convert_ac,
            'logical_noise_filtering': self._convert_lnf,
        }.get(task_type)

        if converter_fn is None:
            return StateSchema(variables={}, dependencies=[],
                             final_question_variables=[], probing_variables=[])
        return converter_fn(task, evidence)

    def _convert_vnf(self, task: Dict, evidence: Dict) -> StateSchema:
        """VNF: evidence.target.all_objects 直接提供完整物体列表"""
        variables = {}
        target = evidence['evidence']['target']
        target_cat = target['target_object']['category']
        all_objs = target['all_objects']

        for obj in set(all_objs):
            count = all_objs.count(obj)
            var_name = f"v_target_{obj}_count"
            variables[var_name] = StateVariable(
                name=var_name, value=count,
                var_type=VariableType.COUNT,
                source=f'image_{target["image_idx"]}',
                relevance=VariableRelevance.PRIMARY if obj == target_cat else VariableRelevance.AUXILIARY,
                observable_from=[f'image_{target["image_idx"]}'],
            )

        # 目标物体位置
        variables['v_target_bbox'] = StateVariable(
            name='v_target_bbox', value=target['target_object']['bbox'],
            var_type=VariableType.POSITION,
            source=f'image_{target["image_idx"]}',
            relevance=VariableRelevance.PRIMARY,
        )

        # 干扰图物体
        for i, dist in enumerate(evidence['evidence'].get('distractors', [])):
            var_name = f'v_distractor_{i}_objects'
            variables[var_name] = StateVariable(
                name=var_name, value=dist['objects'],
                var_type=VariableType.OBJECT_LIST,
                source=f'image_{dist["image_idx"]}',
                relevance=VariableRelevance.AUXILIARY,
            )

        # derived
        variables['v_answer'] = StateVariable(
            name='v_answer', value=f'image_{target["image_idx"]}',
            var_type=VariableType.DERIVED,
            source='', relevance=VariableRelevance.PRIMARY,
            depends_on=['v_target_bbox', f'v_target_{target_cat}_count'],
        )

        deps = [Dependency(from_var=d, to_var='v_answer', dep_type='determines')
                for d in variables['v_answer'].depends_on]

        return StateSchema(
            variables=variables, dependencies=deps,
            final_question_variables=['v_answer'],
            probing_variables=[k for k, v in variables.items() if v.var_type != VariableType.DERIVED],
        )

    def _convert_rc(self, task: Dict, evidence: Dict) -> StateSchema:
        """RC: co_occurring 字段提供 auxiliary variables"""
        variables = {}
        for item in evidence['evidence']:
            idx = item['image_idx']
            cat = item['target_category']
            variables[f'v_img{idx}_{cat}_count'] = StateVariable(
                name=f'v_img{idx}_{cat}_count', value=item['count'],
                var_type=VariableType.COUNT, source=f'image_{idx}',
                relevance=VariableRelevance.PRIMARY,
            )
            for co_obj in item.get('co_occurring', []):
                var_name = f'v_img{idx}_{co_obj}_present'
                variables[var_name] = StateVariable(
                    name=var_name, value=True,
                    var_type=VariableType.BOOLEAN, source=f'image_{idx}',
                    relevance=VariableRelevance.AUXILIARY,
                )
        variables['v_comparison_result'] = StateVariable(
            name='v_comparison_result', value=task['answer'],
            var_type=VariableType.DERIVED, source='',
            relevance=VariableRelevance.PRIMARY,
            depends_on=[k for k in variables if 'count' in k],
        )
        deps = [Dependency(from_var=d, to_var='v_comparison_result', dep_type='determines')
                for d in variables['v_comparison_result'].depends_on]
        return StateSchema(
            variables=variables, dependencies=deps,
            final_question_variables=['v_comparison_result'],
            probing_variables=[k for k, v in variables.items() if v.var_type != VariableType.DERIVED],
        )

    # _convert_abr, _convert_ac, _convert_lnf 类似...
```

### 4.5 生成器后处理 Hook（不修改原有 `_generate_*` 方法）

```python
# dataprovider/state_schema_hooks.py
"""
生成器的后处理 hook。
在 generator_v2.py 的生成流水线最后一步调用。
不修改任何现有的 _generate_*() 方法。

用法:
    # 在 generator_v2.py 中，任务生成完成后:
    task = generator.generate(...)   # 原有逻辑不变
    task = enrich_with_state_schema(task, evidence, loader)  # 可选追加
"""

from dataprovider.state_schema_converter import StateSchemaConverter

_converter = StateSchemaConverter()

def enrich_with_state_schema(task: Dict, evidence: Dict,
                              loader=None) -> Dict:
    """
    后处理 hook: 为已生成的 task 追加 state_schema 字段。

    参数:
        task: 已生成的任务字典（不会被修改原有字段）
        evidence: 对应的 evidence 字典
        loader: 可选的 DataLoader 实例，用于回查非目标物体

    返回:
        同一个 task 字典，追加了 'state_schema' 字段
    """
    schema = _converter.convert(task, evidence)

    # 如果 auxiliary variables 不足且有 loader，尝试补充
    if loader and schema.get_auxiliary_variables().__len__() < 2:
        schema = _enrich_auxiliary_from_loader(task, schema, loader)

    task['state_schema'] = schema.to_dict()
    return task


def _enrich_auxiliary_from_loader(task, schema, loader):
    """从原始数据集回查，补充 auxiliary variables"""
    # 实现细节见 loader.get_all_objects_by_image_id()
    ...
    return schema
```

---

## 5. 下一步要审查的内容

### 5.1 需要深入检查的文件

| 文件 | 审查目标 |
|------|----------|
| `dataprovider/task_generators.py` 第 110-170 行 | `_generate_count_comparison()` 的完整逻辑，确认在哪个时机调用 hook |
| `dataprovider/task_generators.py` 的 ABR generator | `formal_representation` 的构建逻辑，确认可复用性 |
| `dataprovider/generator_v2.py` 的生成流水线 | 确认在哪一步追加 `enrich_with_state_schema()` 调用 |
| `dataprovider/loader.py` 的 `_load_mscoco14()` | 确认是否能支持 `get_all_objects_by_image_id()` 新方法 |
| `dataprovider/loader.py` 的 `_load_visual_genome()` | Visual Genome scene graph 是最丰富的来源 |

### 5.2 需要确认的设计决策

1. **state_schema 的粒度**: 一个图片场景标注多少个变量？建议：目标物体 + 同图最多 5 个非目标物体
2. **auxiliary 变量来源**: 优先从 evidence 中已有字段提取，不足时通过 loader 回查
3. **跨数据集兼容性**: state_schema 格式统一，不同数据集的差异在 converter 的各 `_convert_*()` 方法中处理
4. **依赖关系复杂度**: 只标注直接依赖（一跳），不做传递依赖

---

## 6. 初步计划

### Phase 1: 共享类型（优先级最高）
1. 实现 `src/simulator/state_schema_types.py`
2. 编写单元测试（序列化/反序列化/降级行为）

### Phase 2: 零成本转化（VNF + RC）
1. 实现 `StateSchemaConverter._convert_vnf()` 和 `_convert_rc()`
2. 编写 `tools/convert_annotations_to_schema.py` 脚本
3. 对 `generated_tasks_v2/` 中的 VNF 和 RC 数据运行批量转化
4. 人工审查 20 个样本的 schema 质量

### Phase 3: 生成器扩展（AC + ABR + LNF）
1. 在 `dataprovider/loader.py` 中新增 `get_all_objects_by_image_id()` 方法
2. 实现 `dataprovider/state_schema_hooks.py`
3. 实现 `StateSchemaConverter._convert_ac()`, `_convert_abr()`, `_convert_lnf()`
4. 在 `generator_v2.py` 流水线末尾追加 hook 调用（**唯一的现有文件改动点，仅增加一行调用**）

### Phase 4: 质量验证
1. 人工审查每种任务类型各 10 个样本
2. 确认 primary/auxiliary 变量的分布是否合理
3. 确认 dependency 标注的正确性
4. **降级测试**: 删除 state_schema 字段后，确认所有现有功能不受影响

### Phase 5: 与下游模块对接验证
1. 确认 `StateSchema.from_dict()` 能正确解析所有已转化的数据
2. 与状态测试改进的 `StateEvolutionTracker` 进行集成测试
3. 与对话和测试改进的 `TaskProgress` 进行集成测试
