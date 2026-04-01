"""
Prompt Router — Modular Prompt Assembly
=======================================

Replaces the monolithic _build_core_system_prompt() /
_build_core_user_prompt() with a composable prompt assembly pipeline:

  system = SYSTEM_BASE + TASK_PROMPTS[task_type] + PHASE_PROMPTS[phase]
  user   = compressed_history + vlm_response_summary + status_block

Used by StatefulStrategicSimulator (composed, not inherited).
Does NOT modify StrategicSimulator — the original prompt methods remain
intact and are used as fallback when state_schema is absent.

Safety:
  - Independent new file — no existing code modified
  - All template format keys use safe_format() to avoid KeyError
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from .action_space import TASK_STRATEGIES


# ============================================================
# Fixed system base (shared across all task types)
# ============================================================

SYSTEM_BASE = """你是一个VLM能力测试的考官。你的任务是通过策略性的多轮对话来测试目标模型的能力极限。

## 输出格式
请以JSON格式输出:
```json
{{
    "action": "动作名称",
    "message": "发送给目标模型的自然语言消息",
    "reasoning": "选择此动作的原因",
    "expected_response": "预期模型会如何回应",
    "difficulty_assessment": "当前对模型难度的评估"
}}
```

## 策略指南
1. **任务导向**: 所有动作都是为了测试模型完成任务的能力
2. **渐进压力**: 先建立基础，再逐步增加压力
3. **自适应**: 模型表现好就加难度，表现差就调整策略
4. **隐蔽性**: mislead和memory_injection要自然，不要太明显
5. **最终验证**: 在结束前必须做consistency_check
6. **证据驱动**: 在 grounding/observation 阶段，必须要求模型提供具体的视觉证据（如物体位置、颜色、数量、空间关系），而不是只给结论。后续阶段的挑战应针对这些具体 claim 进行。
7. **避免不可观测指标**: 不要要求模型给出精确的关系数量、bbox坐标等人类也无法直接从图片中数出的数值。聚焦于可视觉验证的属性（颜色、相对大小、位置关系、物体类别等）。
"""

# ============================================================
# Per-task-type prompt fragments
# ============================================================

TASK_PROMPTS: Dict[str, str] = {
    "attribute_comparison": """## 当前任务: 属性比较 (Attribute Comparison)
目标: 比较多张图片中目标物体的属性差异（数量、大小、颜色等）
评测重点: 跨图观察准确性、属性提取精度、比较推理能力
""",

    "visual_noise_filtering": """## 当前任务: 视觉噪声过滤 (Visual Noise Filtering)
目标: 在干扰信息中识别目标图片中的关键信息
评测重点: 注意力维持、噪声抗性、视觉记忆稳定性
""",

    "attribute_bridge_reasoning": """## 当前任务: 属性桥接推理 (Attribute Bridge Reasoning)
目标: 通过多跳推理链追踪物体间的空间/属性关系
评测重点: 推理链完整性、每步推理正确性、干扰下的推理稳定性
""",

    "relation_comparison": """## 当前任务: 关系比较 (Relation Comparison)
目标: 比较多张图片中物体间关系的差异
评测重点: 关系识别准确性、跨图关系比较、共现物体追踪
""",

    "logical_noise_filtering": """## 当前任务: 逻辑噪声过滤 (Logical Noise Filtering)
目标: 从多个描述中识别正确描述图片的选项，过滤逻辑干扰项
评测重点: 视觉证据核实、逻辑干扰抗性、选项评估准确性
""",
}

# ============================================================
# Per-phase prompt fragments (with safe format placeholders)
# ============================================================

PHASE_PROMPTS: Dict[str, str] = {
    # --- Common phases ---
    "grounding": """## 当前阶段: 基础建立 (Grounding)
引导模型观察图片，建立对图片内容的基础理解。
**关键**: 必须要求模型提供具体的视觉证据（物体位置、颜色、数量、空间关系），不要接受模糊的描述。后续阶段将针对这些具体 claim 进行挑战。
可用动作: {allowed_actions}
""",

    "entity_grounding": """## 当前阶段: 实体定位 (Entity Grounding)
引导模型找到起始实体，并要求描述其具体视觉特征（位置、颜色、大小等）。
可用动作: {allowed_actions}
""",

    "noise_injection": """## 当前阶段: 噪声注入 (Noise Injection)
通过误导信息和干扰测试模型的鲁棒性。针对模型在 grounding 阶段给出的具体视觉 claim 进行挑战。
可用动作: {allowed_actions}
""",

    "stress_test": """## 当前阶段: 压力测试 (Stress Test)
用微妙的误导和记忆注入挑战模型。
可用动作: {allowed_actions}
""",

    "final_evaluation": """## 当前阶段: 最终评估 (Final Evaluation)
提出最终问题，验证模型答案。
可用动作: {allowed_actions}
""",

    # --- VNF-specific ---
    "target_presentation": """## 当前阶段: 目标展示 (Target Presentation)
展示目标图片，引导模型进行初步观察。
**关键**: 要求模型描述具体看到了什么物体、它们的位置和特征，建立可验证的视觉 claim。
可用动作: {allowed_actions}
""",

    "memory_attack": """## 当前阶段: 记忆攻击 (Memory Attack)
尝试覆写模型的视觉记忆。
可用动作: {allowed_actions}
""",

    "final_test": """## 当前阶段: 最终测试 (Final Test)
提出需要过滤噪声才能回答的问题。
可用动作: {allowed_actions}
""",

    # --- ABR-specific ---
    "chain_navigation": """## 当前阶段: 推理链导航 (Chain Navigation)
引导模型逐步完成推理链。
可用动作: {allowed_actions}
""",

    "chain_verification": """## 当前阶段: 推理链验证 (Chain Verification)
验证模型是否正确追踪了推理链。
可用动作: {allowed_actions}
""",

    "noise_during_reasoning": """## 当前阶段: 推理中噪声 (Noise During Reasoning)
在推理过程中注入干扰。
可用动作: {allowed_actions}
""",

    "final_answer": """## 当前阶段: 最终回答 (Final Answer)
获取推理链的最终答案。
可用动作: {allowed_actions}
""",

    # --- RC-specific ---
    "relationship_probing": """## 当前阶段: 关系探测 (Relationship Probing)
探测模型对物体间关系的理解。要求模型基于之前观察到的具体视觉证据回答，而非重新猜测。
可探测的变量: {probing_variables}
可用动作: {allowed_actions}
""",

    # --- LNF-specific ---
    "image_observation": """## 当前阶段: 图片观察 (Image Observation)
引导模型描述图片中的内容。
**关键**: 要求模型列出具体的物体、属性和空间关系，而不是笼统描述。这些具体 claim 将在后续阶段被用来测试记忆和鲁棒性。
可用动作: {allowed_actions}
""",

    "option_presentation": """## 当前阶段: 选项展示 (Option Presentation)
展示描述选项，让模型进行评估。
可用动作: {allowed_actions}
""",

    "distractor_injection": """## 当前阶段: 干扰注入 (Distractor Injection)
注入干扰选项，测试模型的鲁棒性。
可用动作: {allowed_actions}
""",

    "final_selection": """## 当前阶段: 最终选择 (Final Selection)
要求模型做出最终选择并提供依据。
可用动作: {allowed_actions}
""",
}


def _safe_format(template: str, **kwargs) -> str:
    """
    Format a template string, silently ignoring missing keys.

    Uses defaultdict so unreferenced {placeholders} stay as-is
    rather than raising KeyError.
    """
    mapping = defaultdict(str, **kwargs)
    try:
        return template.format_map(mapping)
    except (KeyError, ValueError):
        # Fallback: return template with what we can fill
        return template


class PromptRouter:
    """
    Modular prompt assembler.

    Composed into StatefulStrategicSimulator — not inherited from anything.
    Does NOT modify the original StrategicSimulator prompt methods.

    Usage::

        router = PromptRouter()
        system, user = router.assemble_prompt(
            task_type="attribute_comparison",
            phase="grounding",
            difficulty=2,
            turn_count=5,
            vlm_response="I see two dogs...",
            history=[...],
        )
    """

    def __init__(self):
        self._task_prompts = TASK_PROMPTS
        self._phase_prompts = PHASE_PROMPTS

    def assemble_prompt(
        self,
        task_type: str,
        phase: str,
        difficulty: int,
        turn_count: int,
        vlm_response: str = "",
        history: Optional[List] = None,
        state_context: Optional[Dict[str, Any]] = None,
        allowed_actions: Optional[List[str]] = None,
    ) -> Tuple[str, str]:
        """
        Build (system_prompt, user_prompt) for the core model.

        Args:
            task_type: Task type key (e.g. 'attribute_comparison')
            phase: Current phase name (e.g. 'grounding')
            difficulty: Difficulty level 1-4
            turn_count: Current turn number
            vlm_response: Target model's latest response (may be empty)
            history: Recent conversation history entries
            state_context: Optional state info (probing_variables, etc.)
            allowed_actions: Explicit action list; if None, inferred from strategy

        Returns:
            (system_prompt, user_prompt) tuple
        """
        history = history or []
        state_context = state_context or {}

        # --- System prompt ---
        system = SYSTEM_BASE
        system += self._task_prompts.get(task_type, "")

        # Resolve allowed actions
        if allowed_actions is None:
            allowed_actions = self._infer_phase_actions(task_type, phase, difficulty)

        actions_str = ", ".join(allowed_actions) if allowed_actions else "follow_up, guidance"
        probing_vars = state_context.get("probing_variables", [])
        probing_str = ", ".join(probing_vars) if probing_vars else "(none)"

        phase_template = self._phase_prompts.get(phase, "")
        if phase_template:
            system += _safe_format(
                phase_template,
                allowed_actions=actions_str,
                probing_variables=probing_str,
            )
        else:
            # Unknown phase — append a generic block
            system += f"\n## 当前阶段: {phase}\n可用动作: {actions_str}\n"

        # --- User prompt ---
        user_parts = []

        if vlm_response:
            compressed = self._compress_response(vlm_response)
            user_parts.append(f"## 待测模型最新回复\n{compressed}")

        if history:
            summary = self._compress_history(history)
            user_parts.append(f"## 对话摘要 (最近{min(3, len(history))}轮)\n{summary}")

        user_parts.append(
            f"## 当前状态\n"
            f"- 轮次: {turn_count}\n"
            f"- 难度: {difficulty}/4\n"
            f"- 阶段: {phase}"
        )

        user = "\n\n".join(user_parts) + "\n\n请选择下一个动作并生成消息。"

        return system, user

    # --- Internal helpers ---

    def _infer_phase_actions(
        self, task_type: str, phase: str, difficulty: int
    ) -> List[str]:
        """Get allowed actions for (task_type, phase, difficulty) from TASK_STRATEGIES."""
        strategy = TASK_STRATEGIES.get(task_type)
        if not strategy:
            return ["guidance", "follow_up", "fine_grained"]

        # Find phase config
        phase_actions = []
        for pc in strategy.phases:
            if pc["name"] == phase:
                phase_actions = list(pc.get("actions", []))
                break

        if not phase_actions:
            phase_actions = ["guidance", "follow_up", "fine_grained"]

        # Optionally intersect with difficulty_progression
        diff_actions = strategy.difficulty_progression.get(difficulty)
        if diff_actions and diff_actions != ["all"]:
            # Keep only actions allowed at this difficulty level
            phase_actions = [a for a in phase_actions if a in diff_actions] or phase_actions

        return phase_actions

    def _compress_response(self, response: str, max_length: int = 300) -> str:
        """Truncate long VLM responses for the core model's context."""
        if len(response) <= max_length:
            return response
        return response[:max_length] + "...(truncated)"

    def _compress_history(self, history: List, max_turns: int = 3) -> str:
        """Compress conversation history to a short summary."""
        recent = history[-max_turns:] if history else []
        lines = []
        for entry in recent:
            if isinstance(entry, dict):
                action = entry.get("action", "?")
                msg = str(entry.get("user_message", entry.get("message", "")))[:80]
                resp = str(entry.get("model_response", entry.get("response", "")))[:80]
                lines.append(f"[{action}] User: {msg}...")
                lines.append(f"         Model: {resp}...")
            else:
                lines.append(str(entry)[:160])
        return "\n".join(lines) if lines else "(no history)"
