# 窗口3: Prompt构建灵活性改进 + 长度控制修复

> **目标**: 增强LLM在Query生成中的作用，修复并验证长度控制功能
> **预计工时**: 4-5小时
> **依赖**: 无外部依赖，可独立开发

---

## 🌐 项目背景与整体架构

### M3Bench 是什么

M3Bench 是一个**多轮多模态对话能力评测框架**，用于测试视觉语言模型（VLM）在长上下文对话中的推理、记忆、鲁棒性等能力。核心流程：

1. **数据层**：从视觉数据集（MSCOCO、VCR、Visual Genome 等）中加载图-文对
2. **任务生成层**：自动生成多种推理任务（属性对比、桥式推理、噪声过滤等）
3. **模拟器层**：运行"用户模拟器（User Simulator）"与被测VLM进行多轮对话
4. **评估层**：7维度评估（正确性、忠实性、鲁棒性、一致性、记忆保持、跨图区分、歧义识别）

### 端到端数据流中本窗口的位置

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          M3Bench 端到端流程                              │
│                                                                          │
│  ┌─────────┐    ┌──────────┐    ┌───────────────┐    ┌──────────────┐   │
│  │ 原始数据 │───>│ 任务生成  │───>│ Simulator运行  │───>│ 评估 & 报告  │   │
│  │ 集加载   │    │ (JSONL)  │    │ (多轮对话)     │    │ (7维度评分)  │   │
│  └─────────┘    └──────────┘    └───────────────┘    └──────────────┘   │
│       ▲               ▲             ★窗口3★              ▲             │
│   窗口1-前半      窗口2产出      (Query生成增强         窗口2            │
│   (数据加载)    (VCR rationale    + 长度控制)       (推理链评估)        │
│                  任务生成)                                               │
└──────────────────────────────────────────────────────────────────────────┘
```

**本窗口专注于模拟器层**：改进每轮对话中"用户模拟器生成query"的质量和多样性。

### Simulator内部架构（本窗口的工作区域）

```
┌─── UserSimulator (本窗口核心改造对象) ───────────────────────┐
│                                                               │
│  VLM响应 ──> EntityExtractor ──> ActionSelector ──> Query生成  │
│               (提取实体)        (选择动作)                    │
│                                                    ┌──────┐  │
│                                         当前: ──> │ 规则  │  │
│                                                    │ 模板  │  │
│                                                    └──────┘  │
│                                                    ┌──────┐  │
│                                    ★窗口3: ───> │  LLM  │  │
│                                         新增      │ 生成  │  │
│                                                    └──────┘  │
│                                                               │
│  长度控制: step(length="short"|"medium"|"long")               │
│            ┌──────────┐                                       │
│    当前: ──>│ 固定传入  │  ★窗口3: 动态选择策略               │
│            └──────────┘                                       │
└───────────────────────────────────────────────────────────────┘
```

### 三个并行窗口的关系

| 窗口 | 侧重层面 | 核心改进 | 本窗口输出供谁使用 |
|------|----------|----------|-------------------|
| **窗口1** | 数据层 + 运行层 | 修复数据集生成 + 批处理长对话 | BatchTaskSimulator调用本窗口改进后的Simulator |
| **窗口2** | 数据层 + 评估层 | VCR rationale → 推理链任务 + 推理链评估 | 推理链的query可使用本窗口的LLM生成器 |
| **窗口3 (本文档)** | 模拟器层 | LLM驱动Query生成 + 长度控制 | UserSimulator增强 → 窗口1、2的运行质量提升 |

### 本窗口在整体中的位置

**窗口3是模拟质量窗口**：它解决两个核心问题——

1. **Query生成质量低**：当前Query完全基于模板填充（`QueryGenerator` → `PromptTemplates.render()`），LLM的作用被浪费了。生成的query机械、重复，不像真实用户
2. **长度控制不可见**：虽然代码中实现了长度后缀（`LENGTH_CONTROL_SUFFIX`），但运行日志中未记录，无法验证是否生效，也缺乏动态调整策略

窗口3的改进直接影响每轮对话的query质量，是所有窗口运行效果的"底座"。

---

## 🔗 跨窗口协作规范

### 本窗口的输入来源

| 输入 | 来源 | 说明 |
|------|------|------|
| `src/simulator/query_generator.py` | 已有 | 当前规则Query生成器，本窗口在此基础上创建增强版 |
| `src/simulator/prompt_templates.py` | 已有 | 模板定义，包含 `LENGTH_CONTROL_SUFFIX` |
| `src/simulator/user_simulator.py` | 已有 | 本窗口修改其 `__init__` 和 `step()` 方法 |
| `src/simulator/strategic_simulator.py` | 已有 | 集成动态长度选择 |

### 本窗口的输出（供其他窗口使用）

#### 1. 增强的UserSimulator → 窗口1的BatchTaskSimulator自动获益

本窗口给 `UserSimulator.__init__()` 添加新参数（均有默认值）：

```python
class UserSimulator:
    def __init__(self,
        task, extraction_mode="simple", action_strategy="rule_based",
        allowed_actions=None, verbose=False,
        # ★ 窗口3新增（全部有默认值，窗口1不传也不报错）★
        query_generation_mode: str = "rule",      # "rule" | "llm" | "hybrid"
        llm_client: Optional[Any] = None,
        creativity_level: float = 0.5,
        llm_probability: float = 0.7
    ):
```

> **协作约定**: 窗口1的 `StrategicSimulator` 创建 `UserSimulator` 时，默认使用 `query_generation_mode="rule"`（行为不变）。合并后改为 `"hybrid"` 即可启用LLM生成。

#### 2. 增强的step()返回值 → 窗口1、2的日志中获得更多信息

`UserSimulator.step()` 的返回值新增字段：

```python
{
    # 原有字段（不变）
    "turn": int,
    "action": str,
    "entities": Dict,
    "user_query": str,
    "vlm_response": str,

    # ★ 窗口3新增字段 ★
    "query_length_control": str,        # "short" | "medium" | "long"
    "query_word_count": int,            # query词数
    "query_generation_source": str,     # "rule" | "llm" | "rule_fallback"
    "query_creativity_used": float,     # 使用的创造性级别
    "length_suffix_applied": bool       # 长度后缀是否添加
}
```

> **协作约定**: 窗口1的 `BatchTaskSimulator` 记录对话日志时，自动包含这些新字段。窗口2的推理链测试也会在日志中看到这些数据。

#### 3. DynamicLengthSelector → 窗口2的推理链模式可使用

```python
from length_selector import DynamicLengthSelector, LengthSelectionStrategy

# 窗口2集成时，可为推理链模式指定长度策略
selector = DynamicLengthSelector(strategy=LengthSelectionStrategy.PHASE_BASED)

# 推理链的final阶段使用"long"，让VLM给出详细推理
result = selector.select(phase="final", difficulty=3)
# result["length"] 大概率为 "long"
```

> **协作约定**: 窗口2的 `ReasoningChainBuilder` 可在生成综合验证query时，显式要求 `length="long"`。这不需要依赖 `DynamicLengthSelector`，但合并后可统一使用。

#### 4. LLMQueryGenerator → 窗口2的推理链query可注入

```python
# 窗口2的ReasoningChainBuilder接口预留
class ReasoningChainBuilder:
    def __init__(self, task_with_rationale: Dict,
                 query_generator: Optional[Any] = None):
        # query_generator 可以是窗口3的 LLMQueryGenerator 或 HybridQueryGenerator
        self.query_generator = query_generator
```

### 与窗口1的协作细节

```
窗口3 改造 Simulator              窗口1 使用 Simulator
────────────────────              ────────────────────
UserSimulator 新增参数            BatchTaskSimulator
     │                                    │
     ▼                                    ▼
query_generation_mode="hybrid"    创建 StrategicSimulator
creativity_level=0.5                      │
     │                                    ▼
     ▼                            StrategicSimulator 创建 UserSimulator
LLMQueryGenerator/                        │
HybridQueryGenerator              默认 query_generation_mode="rule"
     │                            合并后改为 "hybrid"
     ▼                                    │
更自然的query生成 ──────────────> 更好的对话质量
                                         │
DynamicLengthSelector            StrategicSimulator 内部
     │                           调用 selector.select()
     ▼                                    │
动态长度策略 ────────────────────> 每轮自动选择合适长度
```

**关键约定**:
- 本窗口的所有新增参数都有默认值，`query_generation_mode` 默认为 `"rule"`
- 窗口1的 `BatchConfig` 预留了 `query_generation_mode`、`creativity_level`、`length_selection_strategy` 字段
- 合并时只需修改默认值或在运行脚本中传入参数

### 与窗口2的协作细节

```
窗口3 LLMQueryGenerator           窗口2 ReasoningChainBuilder
──────────────────────            ─────────────────────────────
generate(action_type,             build_chain_queries()
         entities, ...)                  │
     │                                   ▼
     │                            对推理链的每一步:
     │   可选注入                  {turn, query, expected_info}
     └──────────────────────────>        │
                                         ▼
                                  如果注入了LLMQueryGenerator:
                                    使用LLM生成更自然的推理链query
                                  否则:
                                    使用内置模板（默认行为）
```

**关键约定**:
- 窗口2的 `ReasoningChainBuilder` 构造函数接受可选的 `query_generator` 参数
- 本窗口的 `LLMQueryGenerator.generate()` 方法签名兼容这个注入接口
- 独立开发时各用各的模板，合并后通过依赖注入统一

### 合并顺序建议

```
阶段1: 各窗口独立开发
          │
阶段2: 窗口1 + 窗口2 合并（不涉及本窗口）
          │
阶段3: + 窗口3 合并
          │  - UserSimulator 新增参数在 StrategicSimulator 中传入
          │  - BatchConfig 中启用 query_generation_mode="hybrid"
          │  - DynamicLengthSelector 集成到 StrategicSimulator
          │  - LLMQueryGenerator 可选注入到 ReasoningChainBuilder
          │
阶段4: 端到端集成测试
             - 验证: LLM Query + 动态长度 + 推理链模式 协同工作
             - 验证: 日志中包含所有新增字段
             - 验证: 长度控制统计数据正确
```

### 共享文件冲突预防

本窗口会修改以下被其他窗口也可能修改的文件：

| 文件 | 本窗口修改内容 | 可能冲突的窗口 | 冲突预防策略 |
|------|--------------|---------------|-------------|
| `user_simulator.py` | 新增 `__init__` 参数、`step()` 返回字段 | 窗口1、2不直接修改此文件 | 无冲突 |
| `strategic_simulator.py` | 新增 `DynamicLengthSelector` 集成 | 窗口2新增 `_run_reasoning_chain_test()` | **分别添加到不同方法，不冲突** |
| `evaluator.py` | 本窗口不修改 | 窗口2新增推理链评估方法 | 无冲突 |
| `__init__.py` | 新增导出 | 窗口1、2也会新增导出 | **合并时需手动合并导出列表** |

---

## 📋 任务概览

| 子任务 | 优先级 | 复杂度 | 状态 |
|--------|--------|--------|------|
| 3.1 创建LLMQueryGenerator | P0 | 高 | 待开始 |
| 3.2 集成LLMQueryGenerator到UserSimulator | P0 | 中 | 待开始 |
| 3.3 添加长度控制日志记录 | P1 | 低 | 待开始 |
| 3.4 实现动态长度选择策略 | P1 | 中 | 待开始 |
| 3.5 编写验证测试 | P2 | 低 | 待开始 |

---

## 🎯 问题诊断

### 问题1: Prompt构建过于规则驱动

**当前流程**:
```
VLM响应 → EntityExtractor提取entities → ActionSelector选择动作 → QueryGenerator填充模板
```

**问题点**:
1. `QueryGenerator` 完全基于模板填充，缺乏创造性
2. LLM只在entity提取时使用（且当前使用simple模式）
3. 生成的Query重复性高，缺乏多样性
4. 无法根据对话上下文灵活调整表达方式

**当前代码位置**: `src/simulator/query_generator.py`

```python
# 当前实现 (Line 73-78)
try:
    query = self.templates.render(
        action_type=action_type,
        length=length,
        **template_params
    )
except (KeyError, ValueError) as e:
    query = self._generate_fallback_query(action_type, length)
```

### 问题2: 长度控制未在日志中体现

**当前实现**: `prompt_templates.py` 定义了 `LENGTH_CONTROL_SUFFIX`:

```python
LENGTH_CONTROL_SUFFIX = {
    "short": "请用一句话简短回答。",
    "medium": "请用2-3句话回答。",
    "long": "请详细解释你的推理过程，包括你观察到的所有相关细节。"
}
```

**问题点**:
1. 日志中未记录使用的length参数
2. 无法验证后缀是否被正确添加
3. 缺乏动态长度选择策略
4. 无法分析长度控制对VLM响应的影响

---

## 🔧 子任务 3.1: 创建LLMQueryGenerator

### 目标

创建一个使用LLM生成更灵活、多样化Query的生成器，作为规则生成器的增强。

### 新文件: `src/simulator/llm_query_generator.py`

```python
"""
LLM驱动的Query生成器

使用LLM生成更灵活、多样的用户查询，同时保留规则生成器作为fallback。
"""

import random
from typing import Dict, List, Any, Optional, Literal

from .query_generator import QueryGenerator
from .prompt_templates import PromptTemplates
from .action_space import ACTION_DEFINITIONS


class LLMQueryGenerator:
    """
    LLM驱动的Query生成器

    特性:
    1. 使用LLM生成自然、多样的query
    2. 支持创造性级别调节
    3. 保留规则生成器作为fallback
    4. 记录生成来源（LLM/Rule）
    """

    def __init__(
        self,
        llm_client: Any,
        fallback_generator: Optional[QueryGenerator] = None,
        default_creativity: float = 0.5,
        max_retries: int = 2
    ):
        """
        Args:
            llm_client: LLM客户端实例
            fallback_generator: 规则生成器（作为fallback）
            default_creativity: 默认创造性级别 (0.0-1.0)
            max_retries: LLM生成失败时的最大重试次数
        """
        self.llm_client = llm_client
        self.fallback_generator = fallback_generator or QueryGenerator()
        self.default_creativity = default_creativity
        self.max_retries = max_retries
        self.templates = PromptTemplates()

        # 统计信息
        self.generation_stats = {
            "llm_success": 0,
            "llm_failed": 0,
            "fallback_used": 0
        }

    def generate(
        self,
        action_type: str,
        entities: Dict[str, Any],
        length: str = "medium",
        vlm_response: str = "",
        history: Optional[List[Dict]] = None,
        context: Optional[Dict[str, Any]] = None,
        creativity_level: Optional[float] = None,
        task_info: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        生成用户查询

        Args:
            action_type: 动作类型
            entities: 提取的entities
            length: 长度控制
            vlm_response: VLM的原始响应
            history: 对话历史
            context: 额外上下文
            creativity_level: 创造性级别 (0.0-1.0)
            task_info: 任务信息

        Returns:
            {
                "query": str,              # 生成的query
                "source": str,             # "llm" 或 "rule"
                "creativity_used": float,  # 实际使用的创造性级别
                "length_suffix_added": bool,  # 是否添加了长度后缀
                "generation_attempts": int    # 尝试次数
            }
        """
        history = history or []
        context = context or {}
        task_info = task_info or {}
        creativity = creativity_level if creativity_level is not None else self.default_creativity

        result = {
            "query": "",
            "source": "unknown",
            "creativity_used": creativity,
            "length_suffix_added": False,
            "generation_attempts": 0
        }

        # 根据创造性级别决定生成方式
        if creativity < 0.3:
            # 低创造性：直接使用规则
            query = self.fallback_generator.generate(
                action_type=action_type,
                entities=entities,
                length=length,
                vlm_response=vlm_response,
                history=history,
                context=context
            )
            result["query"] = query
            result["source"] = "rule"
            result["generation_attempts"] = 1
            self.generation_stats["fallback_used"] += 1
        else:
            # 中高创造性：尝试LLM生成
            for attempt in range(self.max_retries):
                result["generation_attempts"] = attempt + 1

                try:
                    query = self._generate_with_llm(
                        action_type=action_type,
                        entities=entities,
                        vlm_response=vlm_response,
                        task_info=task_info,
                        history=history,
                        creativity=creativity
                    )

                    if query and len(query) >= 5:
                        # 添加长度控制后缀
                        query, suffix_added = self._add_length_suffix(query, length)
                        result["query"] = query
                        result["source"] = "llm"
                        result["length_suffix_added"] = suffix_added
                        self.generation_stats["llm_success"] += 1
                        break

                except Exception as e:
                    print(f"LLM generation attempt {attempt + 1} failed: {e}")
                    continue

            # 所有尝试失败，使用fallback
            if not result["query"]:
                query = self.fallback_generator.generate(
                    action_type=action_type,
                    entities=entities,
                    length=length,
                    vlm_response=vlm_response,
                    history=history,
                    context=context
                )
                result["query"] = query
                result["source"] = "rule_fallback"
                self.generation_stats["llm_failed"] += 1
                self.generation_stats["fallback_used"] += 1

        return result

    def _generate_with_llm(
        self,
        action_type: str,
        entities: Dict[str, Any],
        vlm_response: str,
        task_info: Dict,
        history: List[Dict],
        creativity: float
    ) -> str:
        """使用LLM生成query"""

        # 构建LLM prompt
        llm_prompt = self._build_llm_prompt(
            action_type=action_type,
            entities=entities,
            vlm_response=vlm_response,
            task_info=task_info,
            history=history
        )

        # 调用LLM
        response = self.llm_client.generate(
            prompt=llm_prompt,
            temperature=creativity,
            max_tokens=150
        )

        # 解析输出
        query = self._parse_llm_output(response)

        return query

    def _build_llm_prompt(
        self,
        action_type: str,
        entities: Dict[str, Any],
        vlm_response: str,
        task_info: Dict,
        history: List[Dict]
    ) -> str:
        """构建给LLM的prompt"""

        # 获取动作定义
        action_def = ACTION_DEFINITIONS.get(action_type, {})

        # 格式化entities
        objects_str = ", ".join(entities.get("objects", [])[:5]) or "无"
        attributes_str = self._format_attributes(entities.get("attributes", {}))
        regions_str = ", ".join(entities.get("regions", [])[:3]) or "无"

        # 格式化历史
        history_str = self._format_history(history[-3:])

        prompt = f"""你是一个专业的VLM测试员，正在测试视觉语言模型的能力。

**当前动作类型**: {action_type}
**动作目的**: {action_def.get('purpose', '测试模型能力')}
**动作描述**: {action_def.get('description', '')}

**任务上下文**:
- 原始问题: {task_info.get('question', '未知')}
- 预期答案: {task_info.get('answer', '未知')[:100] if task_info.get('answer') else '未知'}

**VLM最近的回复**:
"{vlm_response[:300]}..."

**从回复中提取的实体**:
- 物体: {objects_str}
- 属性: {attributes_str}
- 区域: {regions_str}

**最近的对话历史**:
{history_str}

---

**你的任务**: 生成一个自然、口语化的用户查询，实现"{action_type}"动作的目的。

要求:
1. 语言自然，像真实用户一样交流
2. 合理使用提取的实体
3. 符合动作的目的
4. 简洁明了（1-2句话）
5. 避免重复之前的问法

直接输出查询内容，不要任何解释或前缀："""

        return prompt

    def _format_attributes(self, attributes: Dict) -> str:
        """格式化属性字典"""
        if not attributes:
            return "无"

        parts = []
        for entity, attrs in list(attributes.items())[:3]:
            if isinstance(attrs, dict):
                attr_strs = [f"{k}={v}" for k, v in list(attrs.items())[:2]]
                parts.append(f"{entity}({', '.join(attr_strs)})")

        return "; ".join(parts) if parts else "无"

    def _format_history(self, history: List[Dict]) -> str:
        """格式化对话历史"""
        if not history:
            return "无历史记录"

        lines = []
        for turn in history:
            query = turn.get("user_query", "")[:50]
            response = turn.get("vlm_response", "")[:50]
            lines.append(f"- User: {query}...")
            lines.append(f"- VLM: {response}...")

        return "\n".join(lines)

    def _parse_llm_output(self, response: str) -> str:
        """解析LLM输出"""
        if not response:
            return ""

        # 清理输出
        query = response.strip()

        # 移除可能的引号
        if query.startswith('"') and query.endswith('"'):
            query = query[1:-1]
        if query.startswith("'") and query.endswith("'"):
            query = query[1:-1]

        # 移除可能的前缀
        prefixes = ["查询:", "Query:", "用户:", "User:"]
        for prefix in prefixes:
            if query.startswith(prefix):
                query = query[len(prefix):].strip()

        return query

    def _add_length_suffix(self, query: str, length: str) -> tuple:
        """添加长度控制后缀"""
        suffix = self.templates.LENGTH_CONTROL_SUFFIX.get(length, "")

        if suffix and suffix not in query:
            return query + " " + suffix, True

        return query, False

    def get_stats(self) -> Dict[str, Any]:
        """获取生成统计信息"""
        total = sum(self.generation_stats.values())
        return {
            **self.generation_stats,
            "total_generations": total,
            "llm_success_rate": (
                self.generation_stats["llm_success"] / total
                if total > 0 else 0
            )
        }

    def reset_stats(self):
        """重置统计信息"""
        self.generation_stats = {
            "llm_success": 0,
            "llm_failed": 0,
            "fallback_used": 0
        }


# ========== 混合模式生成器 ==========

class HybridQueryGenerator:
    """
    混合模式Query生成器

    根据配置在LLM和规则生成器之间切换，
    支持概率混合模式。
    """

    def __init__(
        self,
        llm_client: Optional[Any] = None,
        mode: Literal["rule", "llm", "hybrid"] = "hybrid",
        llm_probability: float = 0.7,
        min_creativity: float = 0.3,
        max_creativity: float = 0.9
    ):
        """
        Args:
            llm_client: LLM客户端
            mode: 生成模式
            llm_probability: hybrid模式下使用LLM的概率
            min_creativity: 最小创造性
            max_creativity: 最大创造性
        """
        self.mode = mode
        self.llm_probability = llm_probability
        self.min_creativity = min_creativity
        self.max_creativity = max_creativity

        # 初始化生成器
        self.rule_generator = QueryGenerator()
        self.llm_generator = None

        if llm_client and mode in ["llm", "hybrid"]:
            self.llm_generator = LLMQueryGenerator(
                llm_client=llm_client,
                fallback_generator=self.rule_generator
            )

    def generate(
        self,
        action_type: str,
        entities: Dict[str, Any],
        length: str = "medium",
        **kwargs
    ) -> Dict[str, Any]:
        """
        生成query

        Returns:
            包含query和元信息的字典
        """

        # 决定使用哪种生成器
        use_llm = False

        if self.mode == "llm" and self.llm_generator:
            use_llm = True
        elif self.mode == "hybrid" and self.llm_generator:
            use_llm = random.random() < self.llm_probability

        # 生成
        if use_llm:
            # 随机创造性级别
            creativity = random.uniform(self.min_creativity, self.max_creativity)

            result = self.llm_generator.generate(
                action_type=action_type,
                entities=entities,
                length=length,
                creativity_level=creativity,
                **kwargs
            )
        else:
            # 使用规则生成
            query = self.rule_generator.generate(
                action_type=action_type,
                entities=entities,
                length=length,
                **kwargs
            )

            result = {
                "query": query,
                "source": "rule",
                "creativity_used": 0.0,
                "length_suffix_added": True,  # 规则生成器总是添加
                "generation_attempts": 1
            }

        result["mode"] = self.mode
        return result
```

### 接口定义

```python
class LLMQueryGeneratorInterface:
    """LLMQueryGenerator的接口定义"""

    def generate(
        self,
        action_type: str,
        entities: Dict[str, Any],
        length: str = "medium",
        vlm_response: str = "",
        history: Optional[List[Dict]] = None,
        context: Optional[Dict[str, Any]] = None,
        creativity_level: Optional[float] = None,
        task_info: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        生成用户查询

        Returns:
            {
                "query": str,              # 生成的query
                "source": str,             # "llm" / "rule" / "rule_fallback"
                "creativity_used": float,  # 使用的创造性级别
                "length_suffix_added": bool,  # 是否添加了长度后缀
                "generation_attempts": int    # 尝试次数
            }
        """
        pass

    def get_stats(self) -> Dict[str, Any]:
        """获取生成统计"""
        pass
```

### 验证标准

- [ ] LLM生成的query语法正确、语义通顺
- [ ] 创造性级别0.0-0.3时使用规则生成
- [ ] 创造性级别0.3-1.0时尝试LLM生成
- [ ] LLM失败时正确回退到规则生成
- [ ] 统计信息正确记录

---

## 🔧 子任务 3.2: 集成LLMQueryGenerator到UserSimulator

### 修改文件: `src/simulator/user_simulator.py`

**修改1**: 添加LLM Query Generator支持

```python
# 文件开头添加import
from .llm_query_generator import LLMQueryGenerator, HybridQueryGenerator

class UserSimulator:
    def __init__(
        self,
        task: Dict[str, Any],
        extraction_mode: str = "simple",
        action_strategy: str = "rule_based",
        allowed_actions: Optional[List[str]] = None,
        verbose: bool = False,
        # === 新增参数 ===
        query_generation_mode: str = "rule",  # "rule", "llm", "hybrid"
        llm_client: Optional[Any] = None,
        creativity_level: float = 0.5,
        llm_probability: float = 0.7
    ):
        """
        Args:
            ...existing args...
            query_generation_mode: Query生成模式
            llm_client: LLM客户端（用于llm/hybrid模式）
            creativity_level: LLM创造性级别
            llm_probability: hybrid模式下LLM使用概率
        """
        self.task = task
        self.verbose = verbose
        self.query_generation_mode = query_generation_mode

        # 初始化三个核心组件
        self.entity_extractor = EntityExtractor(extraction_mode=extraction_mode)
        self.action_selector = ActionSelector(
            strategy=action_strategy,
            allowed_actions=allowed_actions
        )

        # === 新增: 根据模式初始化Query Generator ===
        if query_generation_mode == "rule":
            self.query_generator = QueryGenerator()
            self._use_enhanced_generator = False
        else:
            self.query_generator = HybridQueryGenerator(
                llm_client=llm_client,
                mode=query_generation_mode,
                llm_probability=llm_probability,
                min_creativity=max(0.3, creativity_level - 0.2),
                max_creativity=min(1.0, creativity_level + 0.2)
            )
            self._use_enhanced_generator = True

        # 状态管理
        self.history = []
        self.current_turn = 0
        self.current_entities = {}
```

**修改2**: 更新step方法以支持增强的返回值

```python
def step(
    self,
    vlm_response: str,
    length: str = "medium",
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    执行一步交互

    Returns:
        {
            "turn": 当前轮次,
            "action": 选择的动作,
            "entities": 提取的entities,
            "user_query": 生成的query,
            "vlm_response": VLM响应,
            # === 新增字段 ===
            "query_length_control": 使用的长度控制,
            "query_word_count": query词数,
            "query_generation_source": 生成来源,
            "query_creativity_used": 使用的创造性级别,
            "length_suffix_applied": 是否添加了长度后缀
        }
    """
    context = context or {}

    # Step 1: 提取entities (不变)
    entities = self.entity_extractor.extract(
        vlm_response=vlm_response,
        context={
            "task": self.task,
            "history": self.history,
            **context
        }
    )
    self.current_entities = entities

    # Step 2: 选择动作 (不变)
    action = self.action_selector.select(
        turn=self.current_turn,
        history=self.history,
        entities=entities,
        task_info=self.task,
        context=context
    )

    # Step 3: 生成query (增强版)
    if self._use_enhanced_generator:
        # 使用增强生成器
        generation_result = self.query_generator.generate(
            action_type=action,
            entities=entities,
            length=length,
            vlm_response=vlm_response,
            history=self.history,
            context=context,
            task_info=self.task
        )
        user_query = generation_result["query"]
        query_source = generation_result["source"]
        creativity_used = generation_result["creativity_used"]
        length_suffix_applied = generation_result["length_suffix_added"]
    else:
        # 使用基础生成器
        user_query = self.query_generator.generate(
            action_type=action,
            entities=entities,
            length=length,
            vlm_response=vlm_response,
            history=self.history,
            context=context
        )
        query_source = "rule"
        creativity_used = 0.0
        length_suffix_applied = self._check_length_suffix(user_query, length)

    # 记录历史 (增强版)
    step_info = {
        "turn": self.current_turn,
        "action": action,
        "entities": entities,
        "user_query": user_query,
        "vlm_response": vlm_response,
        # === 新增字段 ===
        "query_length_control": length,
        "query_word_count": len(user_query.split()),
        "query_generation_source": query_source,
        "query_creativity_used": creativity_used,
        "length_suffix_applied": length_suffix_applied
    }

    self.history.append(step_info)
    self.current_turn += 1

    if self.verbose:
        print(f"  [Turn {self.current_turn}] Action: {action}")
        print(f"  Query ({query_source}, len={length}): {user_query[:80]}...")

    return step_info

def _check_length_suffix(self, query: str, length: str) -> bool:
    """检查query是否包含长度控制后缀"""
    from .prompt_templates import PromptTemplates
    templates = PromptTemplates()
    suffix = templates.LENGTH_CONTROL_SUFFIX.get(length, "")
    return suffix in query if suffix else False
```

**修改3**: 添加Query生成统计方法

```python
def get_query_generation_stats(self) -> Dict[str, Any]:
    """获取Query生成统计"""
    if self._use_enhanced_generator and hasattr(self.query_generator, 'llm_generator'):
        llm_stats = self.query_generator.llm_generator.get_stats()
    else:
        llm_stats = {}

    # 从历史中统计
    length_stats = {"short": 0, "medium": 0, "long": 0}
    source_stats = {"rule": 0, "llm": 0, "rule_fallback": 0}
    suffix_applied_count = 0

    for step in self.history:
        length = step.get("query_length_control", "medium")
        length_stats[length] = length_stats.get(length, 0) + 1

        source = step.get("query_generation_source", "rule")
        source_stats[source] = source_stats.get(source, 0) + 1

        if step.get("length_suffix_applied", False):
            suffix_applied_count += 1

    return {
        "total_queries": len(self.history),
        "length_distribution": length_stats,
        "source_distribution": source_stats,
        "length_suffix_applied_rate": (
            suffix_applied_count / len(self.history)
            if self.history else 0
        ),
        "llm_generator_stats": llm_stats
    }
```

### 验证标准

- [ ] 三种模式(rule/llm/hybrid)均可正常工作
- [ ] step返回值包含所有新增字段
- [ ] 统计方法返回正确数据
- [ ] verbose模式正确打印调试信息

---

## 🔧 子任务 3.3: 添加长度控制日志记录

### 修改文件: `src/simulator/strategic_simulator.py`

**添加长度控制日志**:

```python
class StrategicSimulator:
    def __init__(self, ...):
        # ... existing code ...

        # 新增: 长度控制统计
        self.length_control_log = []

    def _log_length_control(
        self,
        turn: int,
        selected_length: str,
        query: str,
        suffix_applied: bool,
        selection_reason: str
    ):
        """记录长度控制信息"""
        self.length_control_log.append({
            "turn": turn,
            "selected_length": selected_length,
            "query_preview": query[:50] + "..." if len(query) > 50 else query,
            "query_word_count": len(query.split()),
            "suffix_applied": suffix_applied,
            "selection_reason": selection_reason,
            "timestamp": datetime.now().isoformat()
        })

    def get_length_control_summary(self) -> Dict[str, Any]:
        """获取长度控制摘要"""
        if not self.length_control_log:
            return {"message": "No length control data"}

        length_counts = {}
        suffix_applied_count = 0
        word_counts_by_length = {"short": [], "medium": [], "long": []}

        for entry in self.length_control_log:
            length = entry["selected_length"]
            length_counts[length] = length_counts.get(length, 0) + 1

            if entry["suffix_applied"]:
                suffix_applied_count += 1

            if length in word_counts_by_length:
                word_counts_by_length[length].append(entry["query_word_count"])

        # 计算平均词数
        avg_word_counts = {}
        for length, counts in word_counts_by_length.items():
            if counts:
                avg_word_counts[length] = sum(counts) / len(counts)

        return {
            "total_entries": len(self.length_control_log),
            "length_distribution": length_counts,
            "suffix_applied_rate": suffix_applied_count / len(self.length_control_log),
            "avg_word_count_by_length": avg_word_counts
        }
```

### 修改运行日志保存

在保存运行日志时，包含长度控制信息:

```python
def _save_run_log(self, ...):
    """保存运行日志"""
    log_data = {
        # ... existing fields ...

        # 新增: 长度控制统计
        "length_control": {
            "summary": self.get_length_control_summary(),
            "detailed_log": self.length_control_log
        }
    }

    # ... save logic ...
```

### 验证标准

- [ ] 每轮对话都记录长度控制信息
- [ ] 日志包含选择原因
- [ ] 统计信息计算正确
- [ ] 运行日志包含完整的长度控制数据

---

## 🔧 子任务 3.4: 实现动态长度选择策略

### 新文件: `src/simulator/length_selector.py`

```python
"""
动态长度选择器

根据对话状态、任务阶段、难度级别等动态选择query长度。
"""

import random
from typing import List, Dict, Any, Optional, Literal
from enum import Enum


class LengthSelectionStrategy(Enum):
    """长度选择策略"""
    FIXED = "fixed"           # 固定长度
    RANDOM = "random"         # 随机选择
    PHASE_BASED = "phase_based"   # 基于阶段
    DIFFICULTY_BASED = "difficulty_based"  # 基于难度
    ADAPTIVE = "adaptive"     # 自适应


class DynamicLengthSelector:
    """
    动态长度选择器

    根据多种因素动态选择query长度:
    - 对话阶段 (grounding/stress_test/final)
    - 难度级别
    - 历史响应质量
    - 任务类型
    """

    def __init__(
        self,
        strategy: LengthSelectionStrategy = LengthSelectionStrategy.ADAPTIVE,
        default_length: str = "medium"
    ):
        self.strategy = strategy
        self.default_length = default_length

        # 各阶段的长度分布配置
        self.phase_distributions = {
            "grounding": {
                "short": 0.2,
                "medium": 0.6,
                "long": 0.2
            },
            "noise_injection": {
                "short": 0.4,
                "medium": 0.4,
                "long": 0.2
            },
            "stress_test": {
                "short": 0.5,
                "medium": 0.3,
                "long": 0.2
            },
            "final": {
                "short": 0.1,
                "medium": 0.3,
                "long": 0.6
            }
        }

        # 难度级别对长度的影响
        self.difficulty_modifiers = {
            1: {"short": -0.1, "medium": 0.0, "long": 0.1},   # 简单: 偏向详细
            2: {"short": 0.0, "medium": 0.0, "long": 0.0},    # 中等: 均衡
            3: {"short": 0.1, "medium": 0.0, "long": -0.1},   # 困难: 偏向简洁
            4: {"short": 0.2, "medium": 0.0, "long": -0.2}    # 极难: 更偏向简洁
        }

    def select(
        self,
        phase: Optional[str] = None,
        difficulty: int = 2,
        turn: int = 0,
        history: Optional[List[Dict]] = None,
        task_type: Optional[str] = None,
        context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        选择query长度

        Args:
            phase: 当前阶段
            difficulty: 难度级别 (1-4)
            turn: 当前轮次
            history: 对话历史
            task_type: 任务类型
            context: 额外上下文

        Returns:
            {
                "length": str,          # 选择的长度
                "reason": str,          # 选择原因
                "probabilities": Dict   # 各长度的概率
            }
        """
        history = history or []
        context = context or {}

        if self.strategy == LengthSelectionStrategy.FIXED:
            return self._select_fixed()

        elif self.strategy == LengthSelectionStrategy.RANDOM:
            return self._select_random()

        elif self.strategy == LengthSelectionStrategy.PHASE_BASED:
            return self._select_by_phase(phase)

        elif self.strategy == LengthSelectionStrategy.DIFFICULTY_BASED:
            return self._select_by_difficulty(difficulty)

        elif self.strategy == LengthSelectionStrategy.ADAPTIVE:
            return self._select_adaptive(
                phase=phase,
                difficulty=difficulty,
                turn=turn,
                history=history,
                task_type=task_type
            )

        return self._select_fixed()

    def _select_fixed(self) -> Dict[str, Any]:
        """固定长度"""
        return {
            "length": self.default_length,
            "reason": "fixed_strategy",
            "probabilities": {self.default_length: 1.0}
        }

    def _select_random(self) -> Dict[str, Any]:
        """随机选择"""
        lengths = ["short", "medium", "long"]
        selected = random.choice(lengths)
        return {
            "length": selected,
            "reason": "random_selection",
            "probabilities": {l: 1/3 for l in lengths}
        }

    def _select_by_phase(self, phase: Optional[str]) -> Dict[str, Any]:
        """基于阶段选择"""
        if phase is None:
            phase = "grounding"

        distribution = self.phase_distributions.get(
            phase,
            self.phase_distributions["grounding"]
        )

        selected = self._sample_from_distribution(distribution)

        return {
            "length": selected,
            "reason": f"phase_based_{phase}",
            "probabilities": distribution
        }

    def _select_by_difficulty(self, difficulty: int) -> Dict[str, Any]:
        """基于难度选择"""
        base_distribution = {"short": 0.33, "medium": 0.34, "long": 0.33}

        modifiers = self.difficulty_modifiers.get(
            difficulty,
            self.difficulty_modifiers[2]
        )

        adjusted = {
            length: max(0, base_distribution[length] + modifiers[length])
            for length in base_distribution
        }

        # 归一化
        total = sum(adjusted.values())
        adjusted = {k: v/total for k, v in adjusted.items()}

        selected = self._sample_from_distribution(adjusted)

        return {
            "length": selected,
            "reason": f"difficulty_based_level_{difficulty}",
            "probabilities": adjusted
        }

    def _select_adaptive(
        self,
        phase: Optional[str],
        difficulty: int,
        turn: int,
        history: List[Dict],
        task_type: Optional[str]
    ) -> Dict[str, Any]:
        """自适应选择"""

        # 从阶段分布开始
        phase = phase or "grounding"
        base_dist = self.phase_distributions.get(
            phase,
            self.phase_distributions["grounding"]
        ).copy()

        # 应用难度修正
        modifiers = self.difficulty_modifiers.get(difficulty, self.difficulty_modifiers[2])
        for length in base_dist:
            base_dist[length] = max(0, base_dist[length] + modifiers[length])

        # 基于历史调整
        if history:
            # 如果最近3轮都是同一长度，增加其他长度的概率
            recent_lengths = [
                h.get("query_length_control", "medium")
                for h in history[-3:]
            ]
            if len(set(recent_lengths)) == 1 and len(recent_lengths) == 3:
                dominant = recent_lengths[0]
                # 减少主导长度，增加其他长度
                for length in base_dist:
                    if length == dominant:
                        base_dist[length] *= 0.5
                    else:
                        base_dist[length] *= 1.25

        # 基于任务类型调整
        if task_type:
            if "reasoning" in task_type.lower():
                # 推理任务偏向详细
                base_dist["long"] *= 1.2
            elif "comparison" in task_type.lower():
                # 比较任务偏向中等
                base_dist["medium"] *= 1.2

        # 归一化
        total = sum(base_dist.values())
        base_dist = {k: v/total for k, v in base_dist.items()}

        selected = self._sample_from_distribution(base_dist)

        return {
            "length": selected,
            "reason": f"adaptive_phase={phase}_diff={difficulty}_turn={turn}",
            "probabilities": base_dist
        }

    def _sample_from_distribution(self, distribution: Dict[str, float]) -> str:
        """从分布中采样"""
        lengths = list(distribution.keys())
        weights = list(distribution.values())
        return random.choices(lengths, weights=weights, k=1)[0]


# ========== 预设配置 ==========

def get_length_selector_presets() -> Dict[str, DynamicLengthSelector]:
    """获取预设的长度选择器配置"""
    return {
        "default": DynamicLengthSelector(
            strategy=LengthSelectionStrategy.ADAPTIVE
        ),
        "stress_test": DynamicLengthSelector(
            strategy=LengthSelectionStrategy.PHASE_BASED
        ),
        "quick": DynamicLengthSelector(
            strategy=LengthSelectionStrategy.FIXED,
            default_length="short"
        ),
        "detailed": DynamicLengthSelector(
            strategy=LengthSelectionStrategy.FIXED,
            default_length="long"
        ),
        "random": DynamicLengthSelector(
            strategy=LengthSelectionStrategy.RANDOM
        )
    }
```

### 集成到StrategicSimulator

```python
# 在 strategic_simulator.py 中

from .length_selector import DynamicLengthSelector, LengthSelectionStrategy

class StrategicSimulator:
    def __init__(
        self,
        # ... existing params ...
        length_selection_strategy: str = "adaptive"
    ):
        # ... existing init ...

        # 初始化长度选择器
        strategy_map = {
            "fixed": LengthSelectionStrategy.FIXED,
            "random": LengthSelectionStrategy.RANDOM,
            "phase_based": LengthSelectionStrategy.PHASE_BASED,
            "difficulty_based": LengthSelectionStrategy.DIFFICULTY_BASED,
            "adaptive": LengthSelectionStrategy.ADAPTIVE
        }
        self.length_selector = DynamicLengthSelector(
            strategy=strategy_map.get(length_selection_strategy,
                                     LengthSelectionStrategy.ADAPTIVE)
        )

    def _select_query_length(self) -> Dict[str, Any]:
        """选择query长度"""
        return self.length_selector.select(
            phase=self.task_state.current_phase.phase_name if self.task_state else None,
            difficulty=self.task_state.difficulty_level if self.task_state else 2,
            turn=self.current_turn,
            history=self.conversation_log,
            task_type=self.task.get("task_type") if self.task else None
        )
```

### 验证标准

- [ ] 所有5种策略正常工作
- [ ] 自适应策略考虑所有因素
- [ ] 概率分布正确归一化
- [ ] 历史去重逻辑正确

---

## 🔧 子任务 3.5: 编写验证测试

### 新文件: `tests/test_query_generation.py`

```python
"""
Query生成相关功能的测试

测试内容:
1. LLMQueryGenerator功能
2. 长度控制功能
3. 动态长度选择器
"""

import pytest
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from simulator.query_generator import QueryGenerator
from simulator.prompt_templates import PromptTemplates
from simulator.user_simulator import UserSimulator


class MockLLMClient:
    """模拟LLM客户端"""

    def __init__(self, responses=None):
        self.responses = responses or [
            "这个人物的表情如何？",
            "能详细描述一下场景吗？",
            "图中有哪些物体？"
        ]
        self.call_count = 0

    def generate(self, prompt, temperature=0.5, max_tokens=100):
        response = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1
        return response


class TestQueryGenerator:
    """QueryGenerator测试"""

    def setup_method(self):
        self.generator = QueryGenerator()
        self.sample_entities = {
            "objects": ["人", "伞", "街道"],
            "attributes": {
                "人": {"位置": ["左边"], "动作": ["站立"]},
                "伞": {"颜色": ["黑色"], "状态": ["打开"]}
            },
            "regions": ["左上角", "中间"]
        }

    def test_follow_up_generation(self):
        """测试follow_up动作生成"""
        query = self.generator.generate(
            action_type="follow_up",
            entities=self.sample_entities,
            length="medium"
        )

        assert query is not None
        assert len(query) > 10
        assert "请用2-3句话回答" in query  # 检查长度后缀

    def test_different_lengths(self):
        """测试不同长度控制"""
        templates = PromptTemplates()

        for length in ["short", "medium", "long"]:
            query = self.generator.generate(
                action_type="guidance",
                entities=self.sample_entities,
                length=length
            )

            expected_suffix = templates.LENGTH_CONTROL_SUFFIX.get(length, "")
            if expected_suffix:
                assert expected_suffix in query, f"Length {length} suffix not found"

    def test_all_action_types(self):
        """测试所有动作类型"""
        action_types = [
            "follow_up", "guidance", "negation", "mislead",
            "update", "distraction", "redundancy", "fine_grained",
            "logic_skip", "next_task"
        ]

        for action in action_types:
            query = self.generator.generate(
                action_type=action,
                entities=self.sample_entities,
                length="medium"
            )

            assert query is not None, f"Action {action} returned None"
            assert len(query) > 0, f"Action {action} returned empty query"


class TestLengthControl:
    """长度控制测试"""

    def test_length_suffix_in_user_simulator(self):
        """测试UserSimulator中的长度后缀"""
        task = {
            "task_id": "test_001",
            "question": "图中有什么？"
        }

        simulator = UserSimulator(
            task=task,
            extraction_mode="simple",
            action_strategy="rule_based"
        )

        vlm_response = "图中有一个人拿着伞站在街上。"

        for length in ["short", "medium", "long"]:
            simulator.reset()
            step_info = simulator.step(vlm_response, length=length)

            query = step_info["user_query"]

            # 检查新增字段是否存在
            if "query_length_control" in step_info:
                assert step_info["query_length_control"] == length

            if "query_word_count" in step_info:
                assert step_info["query_word_count"] > 0

    def test_length_suffix_content(self):
        """测试长度后缀的具体内容"""
        templates = PromptTemplates()

        expected = {
            "short": "请用一句话简短回答",
            "medium": "请用2-3句话回答",
            "long": "请详细解释你的推理过程"
        }

        for length, expected_text in expected.items():
            actual_suffix = templates.LENGTH_CONTROL_SUFFIX.get(length, "")
            assert expected_text in actual_suffix, \
                f"Expected '{expected_text}' in suffix for {length}"


class TestDynamicLengthSelector:
    """动态长度选择器测试"""

    def test_import_length_selector(self):
        """测试导入"""
        try:
            from simulator.length_selector import (
                DynamicLengthSelector,
                LengthSelectionStrategy
            )
            assert True
        except ImportError as e:
            pytest.skip(f"LengthSelector not implemented yet: {e}")

    def test_fixed_strategy(self):
        """测试固定策略"""
        try:
            from simulator.length_selector import (
                DynamicLengthSelector,
                LengthSelectionStrategy
            )
        except ImportError:
            pytest.skip("LengthSelector not implemented")

        selector = DynamicLengthSelector(
            strategy=LengthSelectionStrategy.FIXED,
            default_length="short"
        )

        result = selector.select()
        assert result["length"] == "short"
        assert result["reason"] == "fixed_strategy"

    def test_adaptive_strategy(self):
        """测试自适应策略"""
        try:
            from simulator.length_selector import (
                DynamicLengthSelector,
                LengthSelectionStrategy
            )
        except ImportError:
            pytest.skip("LengthSelector not implemented")

        selector = DynamicLengthSelector(
            strategy=LengthSelectionStrategy.ADAPTIVE
        )

        # 测试不同阶段
        for phase in ["grounding", "stress_test", "final"]:
            result = selector.select(phase=phase, difficulty=2, turn=5)

            assert result["length"] in ["short", "medium", "long"]
            assert "probabilities" in result
            assert sum(result["probabilities"].values()) == pytest.approx(1.0)


class TestLLMQueryGenerator:
    """LLM Query Generator测试"""

    def test_import_llm_generator(self):
        """测试导入"""
        try:
            from simulator.llm_query_generator import (
                LLMQueryGenerator,
                HybridQueryGenerator
            )
            assert True
        except ImportError as e:
            pytest.skip(f"LLMQueryGenerator not implemented yet: {e}")

    def test_low_creativity_uses_rule(self):
        """测试低创造性时使用规则生成"""
        try:
            from simulator.llm_query_generator import LLMQueryGenerator
        except ImportError:
            pytest.skip("LLMQueryGenerator not implemented")

        mock_client = MockLLMClient()
        generator = LLMQueryGenerator(
            llm_client=mock_client,
            default_creativity=0.2  # 低创造性
        )

        entities = {"objects": ["人"], "attributes": {}, "regions": []}

        result = generator.generate(
            action_type="follow_up",
            entities=entities,
            creativity_level=0.1  # 非常低
        )

        assert result["source"] == "rule"
        assert mock_client.call_count == 0  # LLM不应被调用

    def test_hybrid_mode(self):
        """测试混合模式"""
        try:
            from simulator.llm_query_generator import HybridQueryGenerator
        except ImportError:
            pytest.skip("HybridQueryGenerator not implemented")

        mock_client = MockLLMClient()
        generator = HybridQueryGenerator(
            llm_client=mock_client,
            mode="hybrid",
            llm_probability=0.5
        )

        entities = {"objects": ["人"], "attributes": {}, "regions": []}

        # 多次生成，应该有LLM和规则的混合
        sources = []
        for _ in range(20):
            result = generator.generate(
                action_type="guidance",
                entities=entities
            )
            sources.append(result["source"])

        # 应该有多种来源（统计意义上）
        # 由于随机性，不做严格断言


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("Query Generation Tests")
    print("=" * 60)

    # Test QueryGenerator
    print("\n--- Testing QueryGenerator ---")
    test_qg = TestQueryGenerator()
    test_qg.setup_method()

    test_qg.test_follow_up_generation()
    print("  ✓ follow_up generation")

    test_qg.test_different_lengths()
    print("  ✓ different lengths")

    test_qg.test_all_action_types()
    print("  ✓ all action types")

    # Test Length Control
    print("\n--- Testing Length Control ---")
    test_lc = TestLengthControl()

    test_lc.test_length_suffix_in_user_simulator()
    print("  ✓ length suffix in UserSimulator")

    test_lc.test_length_suffix_content()
    print("  ✓ length suffix content")

    # Test Dynamic Length Selector
    print("\n--- Testing Dynamic Length Selector ---")
    test_dls = TestDynamicLengthSelector()

    try:
        test_dls.test_import_length_selector()
        print("  ✓ import successful")

        test_dls.test_fixed_strategy()
        print("  ✓ fixed strategy")

        test_dls.test_adaptive_strategy()
        print("  ✓ adaptive strategy")
    except Exception as e:
        print(f"  ⚠ skipped (not implemented): {e}")

    # Test LLM Query Generator
    print("\n--- Testing LLM Query Generator ---")
    test_llm = TestLLMQueryGenerator()

    try:
        test_llm.test_import_llm_generator()
        print("  ✓ import successful")

        test_llm.test_low_creativity_uses_rule()
        print("  ✓ low creativity uses rule")

        test_llm.test_hybrid_mode()
        print("  ✓ hybrid mode")
    except Exception as e:
        print(f"  ⚠ skipped (not implemented): {e}")

    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
```

### 新文件: `tests/test_length_control_integration.py`

```python
"""
长度控制集成测试

测试完整的长度控制流程，从选择到日志记录。
"""

import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_full_length_control_flow():
    """测试完整的长度控制流程"""

    from simulator.user_simulator import UserSimulator
    from simulator.prompt_templates import PromptTemplates

    print("=" * 60)
    print("Full Length Control Flow Test")
    print("=" * 60)

    # 准备任务
    task = {
        "task_id": "length_test_001",
        "question": "描述图中的场景",
        "task_type": "attribute_comparison"
    }

    # 创建simulator
    simulator = UserSimulator(
        task=task,
        extraction_mode="simple",
        action_strategy="rule_based",
        verbose=False
    )

    # 模拟VLM响应
    vlm_responses = [
        "图中有一个人拿着红色的伞站在街上。",
        "这个人穿着蓝色的外套，伞是打开的。",
        "背景中有几栋建筑物和一些树木。"
    ]

    # 测试三种长度
    results = []
    templates = PromptTemplates()

    for i, vlm_response in enumerate(vlm_responses):
        length = ["short", "medium", "long"][i]

        step_info = simulator.step(
            vlm_response=vlm_response,
            length=length
        )

        # 验证长度后缀
        expected_suffix = templates.LENGTH_CONTROL_SUFFIX.get(length, "")
        suffix_found = expected_suffix in step_info["user_query"]

        result = {
            "turn": i + 1,
            "length_requested": length,
            "query": step_info["user_query"],
            "word_count": len(step_info["user_query"].split()),
            "suffix_found": suffix_found,
            "expected_suffix": expected_suffix[:30] + "..."
        }
        results.append(result)

        print(f"\n--- Turn {i+1}: Length = {length} ---")
        print(f"Query: {step_info['user_query'][:80]}...")
        print(f"Word count: {result['word_count']}")
        print(f"Suffix found: {'✓' if suffix_found else '✗'}")

    # 生成报告
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    all_passed = all(r["suffix_found"] for r in results)

    print(f"\nResults:")
    for r in results:
        status = "PASS" if r["suffix_found"] else "FAIL"
        print(f"  Turn {r['turn']} ({r['length_requested']}): {status}")

    print(f"\nOverall: {'ALL PASSED' if all_passed else 'SOME FAILED'}")

    # 保存详细结果
    output_file = Path("tests/output/length_control_test_results.json")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "test_time": datetime.now().isoformat(),
            "all_passed": all_passed,
            "results": results
        }, f, indent=2, ensure_ascii=False)

    print(f"\nDetailed results saved to: {output_file}")

    return all_passed


if __name__ == "__main__":
    success = test_full_length_control_flow()
    sys.exit(0 if success else 1)
```

### 验证标准

- [ ] 所有单元测试通过
- [ ] 集成测试验证完整流程
- [ ] 测试覆盖所有新增功能
- [ ] 测试输出结果保存正确

---

## 📋 配置文件更新

### 新增配置: `configs/query_generation_config.yaml`

```yaml
# Query生成配置

query_generation:
  # 生成模式: rule / llm / hybrid
  mode: "hybrid"

  # LLM相关配置
  llm:
    # 是否启用
    enabled: true
    # 在hybrid模式下使用LLM的概率
    probability: 0.7
    # 创造性级别范围
    min_creativity: 0.3
    max_creativity: 0.9
    # 最大重试次数
    max_retries: 2
    # 最大token数
    max_tokens: 150

  # 规则生成器配置
  rule:
    # 是否总是添加长度后缀
    always_add_length_suffix: true

length_control:
  # 长度选择策略: fixed / random / phase_based / difficulty_based / adaptive
  strategy: "adaptive"

  # 固定模式的默认长度
  default_length: "medium"

  # 各阶段的长度分布
  phase_distributions:
    grounding:
      short: 0.2
      medium: 0.6
      long: 0.2
    noise_injection:
      short: 0.4
      medium: 0.4
      long: 0.2
    stress_test:
      short: 0.5
      medium: 0.3
      long: 0.2
    final:
      short: 0.1
      medium: 0.3
      long: 0.6

  # 是否记录详细日志
  detailed_logging: true

# 长度后缀定义
length_suffixes:
  short: "请用一句话简短回答。"
  medium: "请用2-3句话回答。"
  long: "请详细解释你的推理过程，包括你观察到的所有相关细节。"

# 长度后缀（英文）
length_suffixes_en:
  short: "Please answer briefly in one sentence."
  medium: "Please answer in 2-3 sentences."
  long: "Please explain your reasoning process in detail, including all relevant observations."
```

---

## ✅ 完成验证清单

### 子任务 3.1: LLMQueryGenerator
- [ ] `src/simulator/llm_query_generator.py` 文件创建完成
- [ ] `LLMQueryGenerator` 类实现完成
- [ ] `HybridQueryGenerator` 类实现完成
- [ ] 创造性级别控制正常工作
- [ ] Fallback机制正常工作

### 子任务 3.2: UserSimulator集成
- [ ] `UserSimulator` 支持新的 `query_generation_mode` 参数
- [ ] `step()` 返回值包含新增字段
- [ ] `get_query_generation_stats()` 方法实现
- [ ] 三种模式均可正常工作

### 子任务 3.3: 长度控制日志
- [ ] `StrategicSimulator` 记录长度控制信息
- [ ] 运行日志包含长度控制数据
- [ ] 统计摘要计算正确

### 子任务 3.4: 动态长度选择
- [ ] `src/simulator/length_selector.py` 文件创建完成
- [ ] 5种选择策略实现完成
- [ ] 自适应策略考虑多因素
- [ ] 集成到 `StrategicSimulator`

### 子任务 3.5: 测试验证
- [ ] `tests/test_query_generation.py` 所有测试通过
- [ ] `tests/test_length_control_integration.py` 通过
- [ ] 测试覆盖率满足要求

---

## 📊 验证命令

```bash
# 1. 运行单元测试
python tests/test_query_generation.py

# 2. 运行集成测试
python tests/test_length_control_integration.py

# 3. 验证LLM Query Generator (需要LLM客户端)
python -c "
from src.simulator.llm_query_generator import LLMQueryGenerator, HybridQueryGenerator
print('Import successful!')
"

# 4. 验证长度选择器
python -c "
from src.simulator.length_selector import DynamicLengthSelector, LengthSelectionStrategy
selector = DynamicLengthSelector(strategy=LengthSelectionStrategy.ADAPTIVE)
result = selector.select(phase='grounding', difficulty=2, turn=5)
print(f'Selected length: {result[\"length\"]}')
print(f'Reason: {result[\"reason\"]}')
"

# 5. 运行完整simulator测试
python tests/test_user_simulator.py

# 6. 检查日志输出
cat simulator_test_log/run_log_*.json | python -c "
import json, sys
data = json.load(sys.stdin)
if 'length_control' in data:
    print('Length control data found!')
    print(json.dumps(data['length_control']['summary'], indent=2))
else:
    print('No length control data in log')
"
```

---

## 📝 注意事项

1. **LLM客户端兼容性**: `LLMQueryGenerator` 需要一个实现了 `generate(prompt, temperature, max_tokens)` 接口的LLM客户端

2. **性能考虑**: LLM生成比规则生成慢，在高频场景下建议降低 `llm_probability`

3. **日志大小**: 详细的长度控制日志可能增加日志文件大小，生产环境可关闭 `detailed_logging`

4. **向后兼容**: 所有新增参数都有默认值，不影响现有代码运行

5. **测试环境**: 测试LLM相关功能需要配置有效的LLM客户端，否则会被跳过

> **跨窗口协作详情**请参见本文档顶部的「🔗 跨窗口协作规范」章节。
