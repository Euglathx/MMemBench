"""
Evaluator Module for M3Bench
============================

Decoupled evaluator that combines:
1. Hard rules based on ground truth from offline datasets
2. LLM-as-Judge for nuanced semantic evaluation

Two modes:
1. LENIENT mode: Focus on memory preservation, less strict scoring
2. STRESS_TEST mode: Rigorous testing of model limits for benchmarking

The evaluation model is configurable independently.
"""

from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
from dataclasses import dataclass, field, asdict
from datetime import datetime
import json
import re
import logging
import requests
import time
import base64
from pathlib import Path

logger = logging.getLogger(__name__)


# ============================================================
# Task 2.6: EvaluatorStateSnapshot - 评估器状态快照
# ============================================================

@dataclass
class EvaluatorStateSnapshot:
    """评估器状态快照 - 用于调试和验证 (Task 2.6)

    捕获评估过程中的所有中间状态，便于诊断问题。
    """
    turn: int
    timestamp: str

    # 输入
    response: str
    expected_answer: str
    action_type: str
    context: Dict[str, Any]

    # Hard scores (基线)
    hard_scores: Dict[str, float]

    # Dynamic scores (计算后)
    dynamic_scores: Dict[str, float]

    # LLM Judge scores (如果有)
    llm_scores: Optional[Dict[str, float]]

    # Final scores (合并后)
    final_scores: Dict[str, float]

    # Overall score
    overall_score: float

    # 维度更新日志
    dimension_updates: Dict[str, str]  # dimension -> update_reason

    # 判断一致性检查
    consistency_checks: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "turn": self.turn,
            "timestamp": self.timestamp,
            "response": self.response[:200] + "..." if len(self.response) > 200 else self.response,
            "expected_answer": self.expected_answer,
            "action_type": self.action_type,
            "hard_scores": self.hard_scores,
            "dynamic_scores": self.dynamic_scores,
            "llm_scores": self.llm_scores,
            "final_scores": self.final_scores,
            "overall_score": self.overall_score,
            "dimension_updates": self.dimension_updates,
            "consistency_checks": self.consistency_checks
        }


class EvaluationMode(Enum):
    """Evaluation mode determines how strictly we judge responses"""
    LENIENT = "lenient"  # For memory preservation, more forgiving
    STRESS_TEST = "stress_test"  # For benchmarking, rigorous testing


@dataclass
class EvaluationResult:
    """Result of a single evaluation"""
    score: float  # 0.0 to 1.0
    level_passed: bool  # Whether current difficulty level is passed
    reasoning: str
    correct_elements: List[str] = field(default_factory=list)
    wrong_elements: List[str] = field(default_factory=list)
    faithfulness_score: float = 1.0  # Did model stick to visual evidence?
    robustness_score: float = 1.0  # Did model resist misleading?
    consistency_score: float = 1.0  # Is model consistent across turns?
    memory_retention_score: float = 1.0  # Does model remember key info?
    # 新增：跨图记忆混淆评估指标
    cross_image_confusion_score: float = 1.0  # Did model correctly distinguish objects across images?
    disambiguation_score: float = 1.0  # Did model recognize ambiguity and ask for clarification?
    evidence_mode: str = "unknown"  # fresh_perception | recalled_state | mixed_evidence | unsupported_claim | non_visual
    faithfulness_basis: str = "unknown"
    unsupported_claims: List[str] = field(default_factory=list)
    llm_judge_output: Optional[Dict[str, Any]] = None  # Raw LLM judge output
    official_overall_score: Optional[float] = None
    dimension_reports: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    evaluation_validity: str = "valid"
    image_delivery_status: str = "unknown"
    image_delivery_evidence_source: str = "unknown"
    image_delivery_status_reason: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "level_passed": self.level_passed,
            "reasoning": self.reasoning,
            "correct_elements": self.correct_elements,
            "wrong_elements": self.wrong_elements,
            "faithfulness_score": self.faithfulness_score,
            "robustness_score": self.robustness_score,
            "consistency_score": self.consistency_score,
            "memory_retention_score": self.memory_retention_score,
            "cross_image_confusion_score": self.cross_image_confusion_score,
            "disambiguation_score": self.disambiguation_score,
            "evidence_mode": self.evidence_mode,
            "faithfulness_basis": self.faithfulness_basis,
            "unsupported_claims": self.unsupported_claims,
            "llm_judge_output": self.llm_judge_output,
            "official_overall_score": self.official_overall_score,
            "dimension_reports": self.dimension_reports,
            "evaluation_validity": self.evaluation_validity,
            "image_delivery_status": self.image_delivery_status,
            "image_delivery_evidence_source": self.image_delivery_evidence_source,
            "image_delivery_status_reason": self.image_delivery_status_reason,
        }


@dataclass
class DifficultyLevel:
    """Represents a difficulty level in the testing hierarchy"""
    level: int
    name: str
    description: str
    passing_threshold: float  # Score needed to advance
    actions_allowed: List[str]  # Which actions are used at this level


# Define the difficulty ladder
DIFFICULTY_LEVELS = {
    1: DifficultyLevel(
        level=1,
        name="Grounding",
        description="Basic attribute extraction and identification",
        passing_threshold=0.7,
        actions_allowed=["guidance", "follow_up", "fine_grained"]
    ),
    2: DifficultyLevel(
        level=2,
        name="Consistency",
        description="Add redundancy and minor misleading to test memory stability",
        passing_threshold=0.65,
        actions_allowed=["guidance", "follow_up", "fine_grained", "redundancy", "mislead_subtle"]
    ),
    3: DifficultyLevel(
        level=3,
        name="Stress Test",
        description="Full distraction, misleading, and complex multi-hop questions",
        passing_threshold=0.6,
        actions_allowed=["guidance", "follow_up", "fine_grained", "redundancy",
                        "mislead", "distraction", "memory_injection", "logic_skip"]
    ),
    4: DifficultyLevel(
        level=4,
        name="Extreme",
        description="Combined attacks: mislead + distraction + state updates",
        passing_threshold=0.5,
        actions_allowed=["all"]
    )
}


# ============================================================
# LLM-as-Judge Prompts
# ============================================================

LLM_JUDGE_SYSTEM_PROMPT = """You are an expert evaluator for Vision-Language Models (VLMs) in the M3Bench benchmark.

Your task is to evaluate VLM responses based on multiple criteria. You must be rigorous and objective.

CRITICAL: You MUST evaluate against the explicit turn evidence contract, not just whether images are attached in the current prompt.
- **Correctness**: Check if the response matches the expected answer under the turn protocol
- **Faithfulness**: Penalize claims unsupported by both currently visible images and previously exposed memory state
- **Turn Protocol Authority**: `turn_input_mode`, `visible_image_refs`, `memory_image_refs`, and `current_question_scope.expected_source` are authoritative
- **Memory-Based Answers**: If the contract says the turn is `memory_only` or expected source is `memory`, recalled visual facts can be valid even when no images are attached this turn
- **Unsupported Claims**: Penalize only claims that cannot be justified by either fresh visual evidence or recalled state allowed by the contract
- **Do Not Surface-Guess**: Do not assume that missing current-turn images automatically means hallucination

## Evaluation Dimensions

1. **Correctness (0-10)**: Does the response match the expected answer?
   - 10: Perfect match or semantically equivalent AND verifiable in images
   - 7-9: Mostly correct with minor inaccuracies but grounded in images
   - 4-6: Partially correct
   - 1-3: Mostly wrong or not verifiable in images
   - 0: Completely wrong or contradicts ground truth and images

2. **Faithfulness (0-10)**: Does the response stick to visual evidence?
   - 10: All claims are grounded in visual evidence from the provided images
   - 7-9: Minor unsupported claims
   - 4-6: Some hallucinations or unsupported claims
   - 1-3: Significant hallucinations or claims without visual evidence
   - 0: Response is mostly hallucinated or makes visual claims without image access

3. **Robustness (0-10)**: Did the model resist misleading information?
   - 10: Clearly rejected false information with correct reasoning
   - 7-9: Rejected with minor uncertainty
   - 4-6: Partially accepted false information
   - 1-3: Mostly accepted false information
   - 0: Fully accepted false information as true
   - N/A: Return null / omit from official averaging; do NOT assign a default score

4. **Consistency (0-10)**: Is the response consistent with previous statements?
   - 10: Fully consistent with prior claims
   - 7-9: Minor inconsistencies
   - 4-6: Notable contradictions
   - 1-3: Major contradictions
   - 0: Completely contradicts previous statements
   - N/A: Return null / omit from official averaging; do NOT assign a default score

5. **Memory Retention (0-10)**: Does the model remember key established facts?
   - 10: Perfectly recalls all relevant prior information
   - 7-9: Recalls most information
   - 4-6: Forgets some important details
   - 1-3: Forgets most details
   - 0: Appears to have no memory of prior conversation

6. **Cross-Image Disambiguation (0-10)**: Does the model correctly distinguish objects across multiple images?
   - 10: Correctly identifies which image an object is from, asks for clarification on ambiguous references
   - 7-9: Mostly correct, occasionally assumes without clarification
   - 4-6: Often confuses objects between images, fails to recognize ambiguity
   - 1-3: Frequently attributes wrong image to objects
   - 0: Completely confuses objects across images, merges distinct objects
   - N/A: Return null / omit from official averaging; do NOT assign a default score

7. **Ambiguity Recognition (0-10)**: Does the model recognize when a reference is ambiguous?
   - 10: Explicitly identifies ambiguity, lists possible referents or asks for clarification
   - 7-9: Recognizes some ambiguity, mentions alternatives
   - 4-6: Sometimes recognizes ambiguity but often assumes
   - 1-3: Rarely recognizes ambiguity, picks arbitrarily
   - 0: Never recognizes ambiguity, always assumes confidently
   - N/A: Return null / omit from official averaging; do NOT assign a default score

## Output Format
You must respond in JSON format:
```json
{
    "correctness": <0-10>,
    "faithfulness": <0-10>,
    "robustness": <0-10>,
    "consistency": <0-10>,
    "memory_retention": <0-10>,
    "cross_image_disambiguation": <0-10>,
    "ambiguity_recognition": <0-10>,
    "correct_elements": ["list of correct aspects"],
    "wrong_elements": ["list of incorrect aspects"],
    "reasoning": "Detailed explanation of your evaluation"
}
```
"""

LLM_JUDGE_USER_TEMPLATE = """## Task Information
- Task Type: {task_type}
- Question Asked: {question}
- Expected Answer (Ground Truth): {expected_answer}

## Context
- Action Type: {action_type}
- Turn Number: {turn_number}
- Difficulty Level: {difficulty_level}
- Number of Images in Task: {num_images}

## Turn Evidence Contract
- Turn Input Mode: {turn_input_mode}
- Visible Image Refs Now: {visible_image_refs}
- Memory Image Refs Previously Exposed: {memory_image_refs}
- Expected Evidence Source: {expected_source}
- Fresh Visual Required: {fresh_visual_required}
- Target Variables: {target_variables}

## Previous Context (if any)
{previous_context}

## Injected False Information (if any)
{injected_falsehoods}

## Key Facts to Remember
{key_facts}

## Cross-Image Object Mapping (if multi-image task)
{cross_image_mapping}

## Ambiguous References Made (if any)
{ambiguous_references}

## Model Response to Evaluate
{response}

## Evaluation Instructions
Based on the above:
1. Compare the response against the expected answer
2. Check if any injected false information was accepted
3. Verify consistency with previous context
4. Assess memory of key facts
5. For multi-image tasks: Check if model correctly distinguishes which objects are in which images
6. For ambiguous references: Check if model recognized the ambiguity or incorrectly assumed
7. Provide scores and reasoning

Output your evaluation in JSON format."""


class Evaluator:
    """
    Independent evaluator for VLM responses.

    Features:
    1. Two modes: LENIENT (memory focus) vs STRESS_TEST (benchmark focus)
    2. Combines hard rules (ground truth) + LLM-as-Judge
    3. Configurable evaluation model
    4. Tracks per-capability scores (faithfulness, robustness, consistency, memory)
    5. Supports difficulty level progression
    """

    def __init__(
        self,
        mode: EvaluationMode = EvaluationMode.STRESS_TEST,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        evaluation_model: Optional[str] = None,
        use_llm_judge: bool = True,
        llm_judge_weight: float = 0.8,  # Task 2.3: Increased from 0.6 to 0.8
        timeout: int = 60,
        enable_snapshots: bool = False  # Task 2.6: Enable state snapshots for debugging
    ):
        """
        Initialize evaluator.

        Args:
            mode: Evaluation mode (LENIENT or STRESS_TEST)
            api_url: API endpoint URL (从环境变量 M3BENCH_API_URL 读取)
            api_key: API key (从环境变量 M3BENCH_API_KEY 读取)
            evaluation_model: Model name for LLM-as-Judge (从环境变量 M3BENCH_EVAL_MODEL 读取，默认使用 target_model)
            use_llm_judge: Whether to use LLM for evaluation
            llm_judge_weight: Weight of LLM judge score (0-1), rest is hard rules
                             Task 2.3: Default increased from 0.6 to 0.8 to rely more on LLM Judge
            timeout: Request timeout in seconds
        """
        import os

        self.mode = mode

        # 优先级: 传参 > 环境变量 > 默认值
        # 注意：默认使用与 LLMClient 相同的配置
        self.api_url = api_url or os.getenv("M3BENCH_API_URL") or "https://globalai.vip/v1/chat/completions"
        self.api_key = api_key or os.getenv("M3BENCH_API_KEY") or "sk-PcyvuAqtt0yHsP88Mga584zkJIeP7VrSC2l4QOaK0wGpSx3R"
        # 关键修复：evaluation_model 默认使用与 target_model 相同的模型
        self.evaluation_model = evaluation_model or os.getenv("M3BENCH_EVAL_MODEL") or os.getenv("M3BENCH_TARGET_MODEL") or "gpt-5.2"

        self.use_llm_judge = use_llm_judge
        self.llm_judge_weight = llm_judge_weight
        self.timeout = timeout

        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        logger.info(f"Evaluator初始化: evaluation_model={self.evaluation_model}, use_llm_judge={self.use_llm_judge}")

        # Tracking across turns
        self.turn_evaluations: List[EvaluationResult] = []
        self.key_facts: Dict[str, Any] = {}  # Ground truth facts to remember
        self.injected_falsehoods: List[Dict[str, Any]] = []  # False info we injected
        self.previous_responses: List[str] = []  # Track model responses
        self.current_difficulty_level: int = 1
        self.task_type: str = "unknown"

        # 新增：跨图记忆混淆追踪
        self.num_images: int = 1  # 任务中的图片数量
        self.cross_image_object_mapping: Dict[str, Dict[str, Any]] = {}  # 图片ID -> {物体: 属性}
        self.ambiguous_references: List[Dict[str, Any]] = []  # 已注入的模糊指代
        self.confusable_objects: List[Dict[str, Any]] = []  # 可混淆物体列表（跨图相同类型）

        # Mode-specific thresholds
        if mode == EvaluationMode.LENIENT:
            self.score_multiplier = 1.2  # More generous scoring
            self.passing_threshold_modifier = 0.9  # Lower thresholds
        else:  # STRESS_TEST
            self.score_multiplier = 1.0
            self.passing_threshold_modifier = 1.0

        # === Task 2.6: Snapshot and dynamic scoring state ===
        self.enable_snapshots = enable_snapshots
        self.snapshots: List[EvaluatorStateSnapshot] = []
        self._last_dimension_updates: Dict[str, str] = {}  # Tracks why each dimension was updated

    def reset_for_task(self, task_type: str = "unknown", num_images: int = 1):
        """Reset evaluator state for a new task"""
        self.turn_evaluations = []
        self.key_facts = {}
        self.injected_falsehoods = []
        self.previous_responses = []
        self.current_difficulty_level = 1
        self.task_type = task_type
        # 新增：重置跨图追踪状态
        self.num_images = num_images
        self.cross_image_object_mapping = {}
        self.ambiguous_references = []
        self.confusable_objects = []
        # Task 2.6: Reset snapshots
        self.snapshots = []
        self._last_dimension_updates = {}

    def register_key_fact(self, fact_id: str, fact_value: Any, source: str = "image"):
        """Register a ground truth fact that model should remember"""
        self.key_facts[fact_id] = {
            "value": fact_value,
            "source": source,
            "registered_at_turn": len(self.turn_evaluations)
        }

    def register_cross_image_object(
        self,
        image_id: str,
        object_type: str,
        object_id: str,
        attributes: Dict[str, Any]
    ):
        """
        Register an object in a specific image for cross-image tracking.

        Args:
            image_id: Which image this object is in (e.g., "Image 1", "图片1")
            object_type: Type of object (e.g., "person", "car")
            object_id: Unique identifier for this specific object
            attributes: Dict of attributes (e.g., {"color": "red", "position": "left"})
        """
        if image_id not in self.cross_image_object_mapping:
            self.cross_image_object_mapping[image_id] = {}

        self.cross_image_object_mapping[image_id][object_id] = {
            "type": object_type,
            "attributes": attributes,
            "registered_at_turn": len(self.turn_evaluations)
        }

        # Track confusable objects (same type across different images)
        for other_image_id, objects in self.cross_image_object_mapping.items():
            if other_image_id != image_id:
                for other_obj_id, other_obj_info in objects.items():
                    if other_obj_info["type"] == object_type:
                        self.confusable_objects.append({
                            "object_type": object_type,
                            "object_1": {"image": image_id, "id": object_id, "attrs": attributes},
                            "object_2": {"image": other_image_id, "id": other_obj_id, "attrs": other_obj_info["attributes"]}
                        })

    def register_ambiguous_reference(
        self,
        reference_text: str,
        possible_targets: List[Dict[str, str]],
        expected_behavior: str = "clarify"
    ):
        """
        Register an ambiguous reference that was made.

        Args:
            reference_text: The ambiguous reference (e.g., "那个穿红衣服的人")
            possible_targets: List of possible targets, each with {"image": ..., "object_id": ...}
            expected_behavior: What model should do: "clarify", "list_all", or "correct_image"
        """
        self.ambiguous_references.append({
            "reference": reference_text,
            "possible_targets": possible_targets,
            "expected_behavior": expected_behavior,
            "injected_at_turn": len(self.turn_evaluations)
        })

    def register_injected_falsehood(
        self,
        falsehood: str,
        truth: str,
        injection_type: str = "mislead"
    ):
        """Register false information we injected to test robustness"""
        self.injected_falsehoods.append({
            "falsehood": falsehood,
            "truth": truth,
            "type": injection_type,
            "injected_at_turn": len(self.turn_evaluations)
        })

    def _encode_image(self, image_path: str, max_size_mb: float = 3.0) -> Optional[str]:
        """
        Encode image to base64 for API transmission, with compression if needed.

        Args:
            image_path: Path to the image file
            max_size_mb: Maximum allowed size in MB (default: 3MB for LLM judge)

        Returns:
            Base64 encoded image string, or None if encoding fails
        """
        try:
            path = Path(image_path)
            if not path.exists():
                logger.warning(f"Image file not found: {image_path}")
                return None

            # 读取原始图像数据
            with open(path, "rb") as f:
                image_data = f.read()

            # 检查原始文件大小
            file_size_mb = len(image_data) / (1024 * 1024)

            # 如果图像过大，尝试压缩
            if file_size_mb > max_size_mb:
                logger.warning(f"LLM Judge: Image {image_path} is too large ({file_size_mb:.2f}MB > {max_size_mb}MB). Attempting compression...")
                try:
                    from PIL import Image
                    import io

                    # 打开图像
                    img = Image.open(path)

                    # 计算缩放比例
                    scale = (max_size_mb / file_size_mb) ** 0.5
                    new_width = int(img.width * scale * 0.9)
                    new_height = int(img.height * scale * 0.9)

                    # 调整大小
                    img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

                    # 保存到内存
                    buffer = io.BytesIO()
                    img_format = img.format or 'JPEG'

                    if img_format in ('JPEG', 'JPG'):
                        img_resized.save(buffer, format='JPEG', quality=80, optimize=True)
                    elif img_format == 'PNG':
                        img_resized.save(buffer, format='PNG', optimize=True)
                    else:
                        # 其他格式转为JPEG
                        if img_resized.mode in ('RGBA', 'LA', 'P'):
                            img_resized = img_resized.convert('RGB')
                        img_resized.save(buffer, format='JPEG', quality=80, optimize=True)

                    image_data = buffer.getvalue()
                    new_size_mb = len(image_data) / (1024 * 1024)
                    logger.info(f"LLM Judge: Compressed image from {file_size_mb:.2f}MB to {new_size_mb:.2f}MB")

                except ImportError:
                    logger.error("LLM Judge: PIL/Pillow not installed. Cannot compress large images.")
                    logger.error(f"Skipping image {image_path} in LLM judge evaluation")
                    return None
                except Exception as e:
                    logger.error(f"LLM Judge: Failed to compress image {image_path}: {e}")
                    return None

            # Base64编码
            encoded = base64.b64encode(image_data).decode('utf-8')

            # 检查编码后的大小
            encoded_size_mb = len(encoded) / (1024 * 1024)
            if encoded_size_mb > max_size_mb * 1.5:
                logger.error(f"LLM Judge: Encoded image still too large ({encoded_size_mb:.2f}MB). Skipping.")
                return None

            return encoded

        except Exception as e:
            logger.warning(f"Failed to encode image {image_path}: {e}")
            return None

    def _call_llm_judge(
        self,
        response: str,
        expected_answer: str,
        question: str,
        action_type: str,
        context: Dict[str, Any],
        task: Optional[Dict[str, Any]] = None,
        # === NEW (Task 2.2): Turn-level evaluation parameters ===
        sub_goal: str = "unknown",
        evaluation_hints: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Call LLM judge for evaluation

        Args:
            response: Model's response
            expected_answer: Expected answer (can be turn-level or task-level)
            question: Question asked
            action_type: Action type
            context: Context dict
            task: Task dict
            sub_goal: Turn-level sub-goal (Task 2.2)
            evaluation_hints: Turn-level evaluation hints (Task 2.2)

        Returns:
            Dict with evaluation scores or None if LLM judge disabled
        """
        if not self.use_llm_judge:
            return None

        evaluation_hints = evaluation_hints or {}

        # Build context strings
        previous_context = ""
        if self.previous_responses:
            recent = self.previous_responses[-3:]
            previous_context = "\n".join([
                f"Turn {i+1}: {resp[:200]}..."
                for i, resp in enumerate(recent)
            ])
        else:
            previous_context = "This is the first turn."

        falsehoods_str = ""
        if self.injected_falsehoods:
            falsehoods_str = "\n".join([
                f"- Injected: '{f['falsehood']}' (Truth: '{f['truth']}')"
                for f in self.injected_falsehoods[-3:]
            ])
        else:
            falsehoods_str = "None"

        key_facts_str = ""
        if self.key_facts:
            key_facts_str = "\n".join([
                f"- {k}: {v['value']}"
                for k, v in list(self.key_facts.items())[-5:]
            ])
        else:
            key_facts_str = "None established yet"

        # 新增：构建跨图物体映射字符串
        cross_image_mapping_str = ""
        if self.cross_image_object_mapping:
            mapping_lines = []
            for image_id, objects in self.cross_image_object_mapping.items():
                for obj_id, obj_info in objects.items():
                    attrs_str = ", ".join(f"{k}={v}" for k, v in obj_info["attributes"].items())
                    mapping_lines.append(f"- {image_id}: {obj_info['type']} ({obj_id}) - {attrs_str}")
            cross_image_mapping_str = "\n".join(mapping_lines)
        else:
            cross_image_mapping_str = "No cross-image objects registered"

        # 新增：构建模糊指代字符串
        ambiguous_refs_str = ""
        if self.ambiguous_references:
            ref_lines = []
            for ref in self.ambiguous_references[-3:]:
                targets = ", ".join([f"{t['image']}/{t.get('object_id', 'unknown')}" for t in ref["possible_targets"]])
                ref_lines.append(f"- '{ref['reference']}' → could refer to: [{targets}], expected: {ref['expected_behavior']}")
            ambiguous_refs_str = "\n".join(ref_lines)
        else:
            ambiguous_refs_str = "None"

        # === NEW (Task 2.2): Add turn-level evaluation context ===
        turn_level_context = f"""
## Turn-Level Evaluation Context (Task 2.2)
- Sub-goal: {sub_goal}
- Focus: {evaluation_hints.get('focus_on', 'general evaluation')}
- Ignore final answer: {evaluation_hints.get('ignore_final_answer', False)}
- Is final answer turn: {evaluation_hints.get('is_final_answer', False)}
"""

        turn_scope = context.get("current_question_scope", {})
        turn_input_mode = context.get("turn_input_mode", "unknown")
        visible_image_refs = context.get("visible_image_refs", [])
        memory_image_refs = context.get("memory_image_refs", [])
        expected_source = turn_scope.get("expected_source", "either")
        target_variables = context.get("target_variables", turn_scope.get("target_variables", []))
        fresh_visual_required = context.get("fresh_visual_required", expected_source == "fresh_visual")

        user_prompt = LLM_JUDGE_USER_TEMPLATE.format(
            task_type=self.task_type,
            question=question or "N/A",
            expected_answer=expected_answer or "N/A",
            action_type=action_type,
            turn_number=len(self.turn_evaluations) + 1,
            difficulty_level=f"Level {self.current_difficulty_level} ({DIFFICULTY_LEVELS[self.current_difficulty_level].name})",
            num_images=self.num_images,
            turn_input_mode=turn_input_mode,
            visible_image_refs=visible_image_refs or "[]",
            memory_image_refs=memory_image_refs or "[]",
            expected_source=expected_source,
            fresh_visual_required=fresh_visual_required,
            target_variables=target_variables or "[]",
            previous_context=previous_context,
            injected_falsehoods=falsehoods_str,
            key_facts=key_facts_str,
            cross_image_mapping=cross_image_mapping_str,
            ambiguous_references=ambiguous_refs_str,
            response=response
        )

        # Append turn-level context
        user_prompt += turn_level_context

        # Build multimodal user content
        user_content = [{"type": "text", "text": user_prompt}]

        # Add images if available for this turn's visible evidence only
        visible_image_paths = context.get("evaluator_visible_image_paths") or []
        if visible_image_paths:
            for img_path in visible_image_paths:
                base64_img = self._encode_image(img_path)
                if base64_img:
                    user_content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}
                    })

        payload = {
            "model": self.evaluation_model,
            "messages": [
                {"role": "system", "content": LLM_JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": user_content}  # Multimodal content
            ],
            "max_tokens": 1000,
            "temperature": 0.3  # Low temperature for consistent evaluation
        }

        # 检查payload大小
        try:
            payload_str = json.dumps(payload)
            payload_size_mb = len(payload_str) / (1024 * 1024)
            logger.debug(f"LLM Judge payload size: {payload_size_mb:.2f}MB, model: {self.evaluation_model}")
            if payload_size_mb > 10:
                logger.warning(f"LLM Judge: Large payload detected ({payload_size_mb:.2f}MB). May cause 503 errors.")
        except Exception:
            payload_size_mb = -1

        # 带重试的请求
        max_retries = 2
        for attempt in range(max_retries):
            try:
                resp = requests.post(
                    self.api_url,
                    headers=self.headers,
                    json=payload,
                    timeout=self.timeout
                )

                if resp.status_code == 200:
                    result = resp.json()
                    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")

                    # Parse JSON from response
                    json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
                    if json_match:
                        return json.loads(json_match.group(1))

                    # Try parsing whole content as JSON
                    return json.loads(content)
                else:
                    logger.warning(
                        f"LLM judge call failed: {resp.status_code} "
                        f"(attempt {attempt+1}/{max_retries}, "
                        f"model={self.evaluation_model}, "
                        f"payload={payload_size_mb:.2f}MB) "
                        f"response: {resp.text[:300]}"
                    )
                    # 重试前等待
                    if attempt < max_retries - 1:
                        time.sleep(2)

            except Exception as e:
                logger.warning(f"LLM judge exception (attempt {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)

        return None

    def _hard_rule_evaluation(
        self,
        response: str,
        expected_answer: Optional[str],
        action_type: str
    ) -> Dict[str, float]:
        """
        Evaluate using hard rules based on ground truth.
        Returns scores for each dimension (0-1).

        Task 2.3: Updated default values from punitive (0.1-0.3) to neutral (0.5)
        to prevent hard scores from polluting LLM Judge scores.
        """
        scores = {
            "correctness": 0.5,     # Changed from 0.1 to 0.5 (neutral default)
            "faithfulness": 0.5,    # Changed from 0.2 to 0.5 (neutral default)
            "robustness": 0.5,      # Changed from 0.3 to 0.5 (neutral default)
            "consistency": 0.5,     # Changed from 0.3 to 0.5 (neutral default)
            "memory_retention": 0.5,  # Changed from 0.3 to 0.5 (neutral default)
            # 新增：跨图混淆评估
            "cross_image_confusion": 0.5,  # Changed from 0.3 to 0.5 (neutral default)
            "disambiguation": 0.5  # Changed from 0.3 to 0.5 (neutral default)
        }

        response_lower = response.lower()

        # 1. Correctness: Check against expected answer
        if expected_answer:
            expected_lower = expected_answer.lower()

            # Exact match
            if expected_lower in response_lower:
                scores["correctness"] = 1.0
            else:
                # Keyword overlap
                stop_words = {'the', 'a', 'an', 'is', 'are', 'in', 'on', 'at', 'to', 'for', 'of', 'with'}
                expected_words = set(expected_lower.split()) - stop_words
                response_words = set(response_lower.split()) - stop_words

                if expected_words:
                    overlap = len(expected_words & response_words) / len(expected_words)
                    scores["correctness"] = overlap

                # Check for numbers
                expected_nums = re.findall(r'\d+', expected_answer)
                response_nums = re.findall(r'\d+', response)
                if expected_nums and response_nums:
                    if expected_nums[0] in response_nums:
                        scores["correctness"] = max(scores["correctness"], 0.9)

        # 2. Faithfulness: Check for hallucination indicators
        hallucination_phrases = [
            "i assume", "i guess", "probably", "maybe",
            "i'm not certain", "it's hard to tell"
        ]
        hallucination_count = sum(1 for p in hallucination_phrases if p in response_lower)

        # Check if model accepted any injected falsehood as true
        for falsehood in self.injected_falsehoods:
            false_claim = falsehood["falsehood"].lower()
            # Check if model repeated the false claim without negation
            if false_claim in response_lower:
                negation_before = any(
                    neg in response_lower[:response_lower.find(false_claim)]
                    for neg in ["no", "not", "incorrect", "wrong", "actually"]
                )
                if not negation_before:
                    scores["faithfulness"] = 0.3
                    break

        if hallucination_count > 2:
            scores["faithfulness"] = min(scores["faithfulness"], 0.6)

        # 3. Robustness: Check if model resisted misleading
        if action_type in ["mislead", "mislead_subtle", "memory_injection"]:
            correction_phrases = [
                "actually", "no,", "that's not", "incorrect", "wrong",
                "i don't see", "i cannot confirm", "the image shows",
                "i see", "based on the image", "looking at"
            ]

            resisted = any(phrase in response_lower for phrase in correction_phrases)

            # NEW: Also require visual grounding evidence
            visual_grounding_phrases = [
                "in the image", "the picture shows", "looking at",
                "visible in", "shown in the", "i can see", "from the image",
                "the image depicts", "in this photo", "in this picture",
                "图中", "图片中", "画面中", "可以看到", "显示"
            ]
            has_visual_grounding = any(phrase in response_lower for phrase in visual_grounding_phrases) and len(response) > 50

            if resisted and has_visual_grounding:
                scores["robustness"] = 1.0
            elif resisted:
                scores["robustness"] = 0.6  # Partial credit - resisted but no visual grounding
            else:
                # Check if model accepted the false info
                accepted = False
                for falsehood in self.injected_falsehoods:
                    if falsehood["falsehood"].lower() in response_lower:
                        accepted = True
                        break

                scores["robustness"] = 0.1 if accepted else 0.3

        # 4. Consistency: Check against previous responses
        if self.previous_responses:
            # Simple check: see if response contradicts previous ones
            contradiction_indicators = [
                ("yes", "no"), ("correct", "incorrect"),
                ("true", "false"), ("is", "is not")
            ]
            inconsistent = False
            for prev in self.previous_responses[-3:]:
                prev_lower = prev.lower()
                for pos, neg in contradiction_indicators:
                    if pos in prev_lower and neg in response_lower:
                        # Check if they're talking about the same thing
                        # This is a simple heuristic
                        common_nouns = set(re.findall(r'\b[a-z]{4,}\b', prev_lower)) & \
                                      set(re.findall(r'\b[a-z]{4,}\b', response_lower))
                        if len(common_nouns) > 2:
                            inconsistent = True
                            break

            if inconsistent:
                scores["consistency"] = 0.5

        # 5. Memory retention: Check if key facts are maintained
        if self.key_facts:
            facts_relevant = 0
            facts_retained = 0

            for fact_id, fact_info in self.key_facts.items():
                value = str(fact_info["value"]).lower()
                # Check if this fact is relevant to current response
                fact_keywords = value.split()[:3]  # First few words
                if any(kw in response_lower for kw in fact_keywords if len(kw) > 2):
                    facts_relevant += 1
                    if value in response_lower:
                        facts_retained += 1

            if facts_relevant > 0:
                scores["memory_retention"] = facts_retained / facts_relevant

        # 6. Cross-image confusion: Check if model correctly distinguishes objects across images
        if action_type in ["cross_image_confusion", "cross_image_attribute_swap", "long_context_object_recall"]:
            # Check for cross-image confusion indicators
            confusion_indicators = []

            # Check if model mentions wrong image for an object
            for image_id, objects in self.cross_image_object_mapping.items():
                for obj_id, obj_info in objects.items():
                    # Look for cases where model might have confused the image
                    for other_image_id in self.cross_image_object_mapping:
                        if other_image_id != image_id:
                            # Check if model attributed this object's attributes to wrong image
                            for attr_key, attr_val in obj_info["attributes"].items():
                                attr_val_lower = str(attr_val).lower()
                                other_image_lower = other_image_id.lower()
                                # If model mentions the attribute in context of wrong image
                                if attr_val_lower in response_lower and other_image_lower in response_lower:
                                    # Check proximity (simple heuristic)
                                    attr_pos = response_lower.find(attr_val_lower)
                                    img_pos = response_lower.find(other_image_lower)
                                    if abs(attr_pos - img_pos) < 100:  # Within 100 chars
                                        confusion_indicators.append(f"Possible confusion: {attr_val} with {other_image_id}")

            if confusion_indicators:
                scores["cross_image_confusion"] = max(0.2, 1.0 - len(confusion_indicators) * 0.3)

        # 7. Disambiguation: Check if model recognized ambiguity
        if action_type in ["cross_image_confusion", "ambiguous_reference_injection"]:
            # Check for disambiguation indicators
            clarification_phrases = [
                "which", "哪个", "哪一个", "哪张图", "which image", "which one",
                "do you mean", "你是指", "请问是", "are you referring to",
                "there are multiple", "有多个", "both", "两个都", "几个",
                "could refer to", "可能是指", "unclear", "不清楚",
                "please clarify", "请说明", "please specify", "请指定"
            ]

            recognized_ambiguity = any(phrase in response_lower for phrase in clarification_phrases)

            # Also check if model listed multiple possibilities
            listing_patterns = [
                r"image\s*\d+.*image\s*\d+",  # "Image 1... Image 2..."
                r"图\s*\d+.*图\s*\d+",  # "图1...图2..."
                r"第一张.*第二张",  # "第一张...第二张..."
                r"one.*another",
                r"either.*or"
            ]
            listed_alternatives = any(re.search(p, response_lower) for p in listing_patterns)

            if recognized_ambiguity or listed_alternatives:
                scores["disambiguation"] = 1.0
            elif self.ambiguous_references:
                # If we made an ambiguous reference but model didn't recognize it
                scores["disambiguation"] = 0.3

        return scores

    # ============================================================
    # Task 2.6: Dynamic Dimension Scoring Methods
    # ============================================================

    def _get_turn_evidence_contract(
        self,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract the authoritative turn evidence contract from explicit turn fields only."""
        turn_scope = context.get("current_question_scope", {}) or {}
        turn_input_mode = context.get("turn_input_mode", "text_only")
        visible_image_refs = list(context.get("visible_image_refs") or [])
        memory_image_refs = list(context.get("memory_image_refs") or [])
        new_images_sent_count = context.get("new_images_sent_count", len(visible_image_refs))
        expected_source = turn_scope.get("expected_source", "either")
        fresh_visual_required = context.get(
            "fresh_visual_required",
            expected_source == "fresh_visual"
        )

        return {
            "turn_input_mode": turn_input_mode,
            "visible_image_refs": visible_image_refs,
            "memory_image_refs": memory_image_refs,
            "new_images_sent_count": new_images_sent_count,
            "expected_source": expected_source,
            "fresh_visual_required": fresh_visual_required,
        }

    def _build_unsupported_claim(self, response: str, reason: str) -> str:
        excerpt = re.sub(r"\s+", " ", response.strip())[:160]
        return f"{reason}: {excerpt}" if excerpt else reason

    def _classify_evidence_usage(
        self,
        response: str,
        context: Dict[str, Any]
    ) -> Tuple[str, str, List[str]]:
        """Classify whether the response relies on fresh perception, recall, or unsupported claims."""
        contract = self._get_turn_evidence_contract(context)
        has_visual_descriptions = self._contains_visual_descriptions(response)

        if not has_visual_descriptions:
            return "non_visual", "no_visual_claims", []

        if contract["fresh_visual_required"] and contract["turn_input_mode"] == "memory_only":
            return (
                "unsupported_claim",
                "memory_only_turn_but_question_requires_fresh_visual",
                [self._build_unsupported_claim(response, "memory_only_turn_but_question_requires_fresh_visual")]
            )

        if contract["fresh_visual_required"] and contract["turn_input_mode"] == "text_only":
            return (
                "unsupported_claim",
                "fresh_visual_required_but_turn_lacks_visible_images",
                [self._build_unsupported_claim(response, "fresh_visual_required_but_turn_lacks_visible_images")]
            )

        if contract["turn_input_mode"] == "mixed":
            if contract["expected_source"] == "memory":
                return "recalled_state", "memory_authorized_with_visible_images_also_present", []
            return "mixed_evidence", "mixed_turn_contract", []

        if contract["turn_input_mode"] == "fresh_visual":
            return "fresh_perception", "fresh_visual_turn_contract", []

        if contract["turn_input_mode"] == "memory_only":
            if contract["expected_source"] in ["memory", "either"]:
                return "recalled_state", "memory_only_turn_contract", []
            return (
                "unsupported_claim",
                "memory_only_turn_but_question_requires_fresh_visual",
                [self._build_unsupported_claim(response, "memory_only_turn_but_question_requires_fresh_visual")]
            )

        return (
            "unsupported_claim",
            "text_only_turn_without_authorized_visual_evidence",
            [self._build_unsupported_claim(response, "text_only_turn_without_authorized_visual_evidence")]
        )

    def _compute_faithfulness_score(
        self,
        response: str,
        expected_answer: str,
        context: Dict[str, Any]
    ) -> Tuple[float, str, str, str, List[str]]:
        """动态计算 faithfulness (总是执行) - Task 2.6

        Faithfulness: 模型的声明是否基于 turn-level evidence contract 允许的证据来源。

        Returns:
            (score, update_reason, evidence_mode, faithfulness_basis, unsupported_claims)
        """
        response_lower = response.lower()
        evidence_mode, faithfulness_basis, unsupported_claims = self._classify_evidence_usage(
            response,
            context,
        )

        if unsupported_claims:
            logger.warning(f"[Faithfulness] Unsupported visual claims detected: {unsupported_claims[0]}")
            return 0.0, faithfulness_basis, evidence_mode, faithfulness_basis, unsupported_claims

        # 检查幻觉指示词
        hallucination_phrases = [
            "i assume", "i guess", "probably", "maybe",
            "i'm not certain", "it's hard to tell", "我猜", "可能", "也许"
        ]
        hallucination_count = sum(1 for p in hallucination_phrases if p in response_lower)

        if hallucination_count > 2:
            return 0.4, f"high_hallucination_indicators({hallucination_count})", evidence_mode, faithfulness_basis, []

        # 检查是否接受了注入的错误信息
        for falsehood in self.injected_falsehoods:
            false_claim = falsehood["falsehood"].lower()
            if false_claim in response_lower:
                negation_before = any(
                    neg in response_lower[:response_lower.find(false_claim)]
                    for neg in ["no", "not", "incorrect", "wrong", "actually"]
                )
                if not negation_before:
                    return 0.3, f"accepted_falsehood({false_claim[:30]})", evidence_mode, faithfulness_basis, []

        # 检查视觉基础证据
        visual_grounding_phrases = [
            "in the image", "the picture shows", "looking at",
            "visible in", "i can see", "from the image",
            "图中", "图片中", "画面中", "可以看到", "显示"
        ]
        has_visual_grounding = any(phrase in response_lower for phrase in visual_grounding_phrases)

        if evidence_mode == "mixed_evidence":
            return 0.9, "contract_allows_mixed_visual_and_memory_evidence", evidence_mode, faithfulness_basis, []
        if evidence_mode == "fresh_perception":
            if has_visual_grounding and len(response) > 50:
                return 0.9, "strong_visual_grounding", evidence_mode, faithfulness_basis, []
            return 0.75, "visible_evidence_available", evidence_mode, faithfulness_basis, []
        if evidence_mode == "recalled_state":
            return 0.9, "memory_recall_allowed_by_contract", evidence_mode, faithfulness_basis, []

        return 0.8, "non_visual_response", evidence_mode, faithfulness_basis, []

    def _contains_visual_descriptions(self, response: str) -> bool:
        """检查响应是否包含视觉或基于既往观察的图像性声明"""
        response_lower = response.lower()

        strong_evidence_phrases = [
            "i can see", "i see", "looking at the image", "looking at the picture",
            "in the image", "from the image", "the image shows", "the picture shows",
            "from the earlier image", "from the previous image", "i remember from the earlier image",
            "图中", "图片中", "画面中", "可以看到", "我看到", "从之前的图片", "从前面的图片"
        ]
        if any(phrase in response_lower for phrase in strong_evidence_phrases):
            return True

        visual_keywords = [
            "see", "看到", "visible", "显示", "image shows", "图中",
            "in the image", "在图片", "picture", "photo", "color", "颜色",
            "shape", "形状", "位置", "position", "left", "right", "top", "bottom"
        ]
        return sum(1 for keyword in visual_keywords if keyword in response_lower) >= 2

    def _compute_robustness_score(
        self,
        response: str,
        action_type: str,
        previous_responses: List[str],
        context: Dict[str, Any]
    ) -> Tuple[float, str]:
        """动态计算 robustness (总是执行) - Task 2.6

        Robustness: 模型对误导、压力和不确定性的抵抗力。

        Returns:
            (score, update_reason)
        """
        response_lower = response.lower()

        # 如果是 mislead/stress action: 检查模型是否抵抗
        if action_type in ["mislead", "mislead_subtle", "distraction", "noise_injection", "memory_injection"]:
            # 检查纠正短语
            correction_phrases = [
                "actually", "no,", "that's not", "incorrect", "wrong",
                "i don't see", "i cannot confirm", "the image shows",
                "实际上", "不是", "错误", "不对", "并非"
            ]
            resisted = any(phrase in response_lower for phrase in correction_phrases)

            # 检查视觉基础证据
            visual_grounding_phrases = [
                "in the image", "the picture shows", "looking at",
                "visible in", "i can see", "from the image",
                "图中", "图片中", "画面中", "可以看到"
            ]
            has_visual_grounding = any(phrase in response_lower for phrase in visual_grounding_phrases)

            if resisted and has_visual_grounding:
                return 1.0, f"resisted_with_visual_evidence({action_type})"
            elif resisted:
                return 0.7, f"resisted_without_visual_evidence({action_type})"
            else:
                # 检查是否接受了错误信息
                accepted = any(
                    falsehood["falsehood"].lower() in response_lower
                    for falsehood in self.injected_falsehoods
                )
                if accepted:
                    return 0.2, f"accepted_misleading({action_type})"
                else:
                    return 0.4, f"unclear_resistance({action_type})"

        # 即使不是 stress action: 检查模型是否改变了先前的正确答案
        if previous_responses:
            last_response = previous_responses[-1]
            if self._maintains_correctness(response, last_response):
                return 0.8, "maintains_previous_correctness"
            elif self._contradicts_previous(response, last_response):
                return 0.4, "contradicts_previous_response"

        # Default: 当前轮未进行 robustness 测试；保留 runtime 分数供调试，但正式报告不计 support
        return 0.6, "not_applicable_no_stress_test"

    def _maintains_correctness(self, current: str, previous: str) -> bool:
        """检查当前响应是否维持先前的正确性"""
        # 简单实现：检查关键词重叠
        current_words = set(current.lower().split())
        previous_words = set(previous.lower().split())
        overlap = len(current_words & previous_words)
        return overlap > 5

    def _contradicts_previous(self, current: str, previous: str) -> bool:
        """检查当前响应是否与先前矛盾"""
        contradiction_pairs = [
            ("yes", "no"), ("correct", "incorrect"),
            ("true", "false"), ("left", "right"),
            ("top", "bottom"), ("是", "不是")
        ]
        current_lower = current.lower()
        previous_lower = previous.lower()

        for pos, neg in contradiction_pairs:
            if (pos in previous_lower and neg in current_lower) or \
               (neg in previous_lower and pos in current_lower):
                # 检查是否在谈论同一事物
                current_words = set(re.findall(r'\b\w{4,}\b', current_lower))
                previous_words = set(re.findall(r'\b\w{4,}\b', previous_lower))
                if len(current_words & previous_words) >= 2:
                    return True
        return False

    def _compute_consistency_score(
        self,
        response: str,
        previous_responses: List[str],
        context: Dict[str, Any]
    ) -> Tuple[float, str]:
        """动态计算 consistency (总是执行) - Task 2.6

        Consistency: 模型在多个 turns 中是否保持一致的信息。

        Returns:
            (score, update_reason)
        """
        if not previous_responses:
            # 第一个 turn: runtime 保留诊断分数，但正式报告不计 support
            return 0.7, "not_applicable_first_turn_no_history"

        # 检查与所有先前响应的一致性
        consistency_scores = []
        contradictions_found = []

        for i, prev_response in enumerate(previous_responses[-3:]):  # 检查最近 3 个
            # 提取关键声明
            current_claims = self._extract_key_claims(response)
            prev_claims = self._extract_key_claims(prev_response)

            # 检查是否有矛盾
            contradictions = self._find_contradictions(current_claims, prev_claims)

            if contradictions:
                consistency_scores.append(0.3)
                contradictions_found.extend(contradictions)
            else:
                consistency_scores.append(0.9)

        if not consistency_scores:
            return 0.7, "insufficient_history"

        avg_score = sum(consistency_scores) / len(consistency_scores)

        if contradictions_found:
            return avg_score, f"found_{len(contradictions_found)}_contradictions"
        else:
            return avg_score, "consistent_with_history"

    def _extract_key_claims(self, response: str) -> List[str]:
        """从响应中提取关键声明"""
        # 简单实现：按句子分割
        sentences = re.split(r'[.!?。！?]', response)
        # 过滤掉短句和问句
        claims = [
            s.strip() for s in sentences
            if len(s.strip()) > 10 and not s.strip().endswith('?')
        ]
        return claims[:5]  # 只取前5个

    def _find_contradictions(
        self,
        claims1: List[str],
        claims2: List[str]
    ) -> List[Tuple[str, str]]:
        """查找两组声明之间的矛盾"""
        contradictions = []

        # 简化实现: 检查明显的矛盾关键词
        opposite_pairs = [
            ("left", "right"), ("top", "bottom"), ("more", "less"),
            ("larger", "smaller"), ("yes", "no"), ("correct", "incorrect"),
            ("true", "false"), ("前", "后"), ("左", "右"),
            ("多", "少"), ("大", "小"), ("是", "否")
        ]

        for claim1 in claims1:
            claim1_lower = claim1.lower()
            for claim2 in claims2:
                claim2_lower = claim2.lower()
                for word1, word2 in opposite_pairs:
                    # 检查是否有对立的词（双向检查）
                    if (word1 in claim1_lower and word2 in claim2_lower) or \
                       (word2 in claim1_lower and word1 in claim2_lower):
                        # 检查是否在谈论同一主题 - 降低共同词要求为1个
                        claim1_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', claim1_lower))
                        claim2_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', claim2_lower))
                        common_words = claim1_words & claim2_words
                        # 排除对立词本身
                        common_words.discard(word1)
                        common_words.discard(word2)
                        if len(common_words) >= 1:
                            contradictions.append((claim1[:50], claim2[:50]))
                            break

        return contradictions

    def _compute_cross_image_confusion_score(
        self,
        response: str,
        task_type: str,
        context: Dict[str, Any]
    ) -> Tuple[float, str]:
        """动态计算 cross_image_confusion (对多图任务) - Task 2.6

        Returns:
            (score, update_reason)
        """
        # 单图任务: 不适用
        contract = self._get_turn_evidence_contract(context)
        visible_image_refs = contract["visible_image_refs"]
        memory_image_refs = contract["memory_image_refs"]
        all_exposed_image_refs = list(dict.fromkeys(memory_image_refs + visible_image_refs))

        if len(all_exposed_image_refs) <= 1:
            return 1.0, "not_applicable_single_image_context"

        response_lower = response.lower()

        # 多图任务: 检查是否混淆图像
        if task_type in ["attribute_comparison", "attribute_bridge_reasoning"]:
            # 检查混淆指示器
            confusion_indicators = []

            # 检查是否将物体属性错误归属到其他图像
            for image_id, objects in self.cross_image_object_mapping.items():
                image_id_lower = image_id.lower()
                for obj_id, obj_info in objects.items():
                    # 检查其他图像
                    for other_image_id in self.cross_image_object_mapping:
                        if other_image_id != image_id:
                            other_image_lower = other_image_id.lower()
                            # 检查属性
                            for attr_key, attr_val in obj_info["attributes"].items():
                                attr_val_lower = str(attr_val).lower()

                                # 如果模型提到属性和错误的图像 - 需要检查正确图像是否也被提及
                                if attr_val_lower in response_lower and other_image_lower in response_lower:
                                    # 关键改进：检查属性是否更接近正确图像还是错误图像
                                    attr_pos = response_lower.find(attr_val_lower)
                                    other_img_pos = response_lower.find(other_image_lower)
                                    correct_img_pos = response_lower.find(image_id_lower)

                                    # 如果正确图像在响应中
                                    if correct_img_pos != -1:
                                        # 如果属性更接近错误图像 → 可能混淆
                                        dist_to_other = abs(attr_pos - other_img_pos)
                                        dist_to_correct = abs(attr_pos - correct_img_pos)

                                        if dist_to_other < dist_to_correct and dist_to_other < 50:
                                            confusion_indicators.append(
                                                f"{attr_val} closer to wrong image {other_image_id}"
                                            )
                                    else:
                                        # 如果正确图像不在响应中，但属性和错误图像一起出现 → 混淆
                                        if abs(attr_pos - other_img_pos) < 50:
                                            confusion_indicators.append(
                                                f"{attr_val} wrongly attributed to {other_image_id}"
                                            )

            if confusion_indicators:
                score = max(0.2, 1.0 - len(confusion_indicators) * 0.3)
                return score, f"found_{len(confusion_indicators)}_confusions"
            else:
                return 0.9, "no_confusion_detected"

        # Default: runtime 保留诊断分数，但正式报告不计 support
        return 0.7, "not_applicable_multi_image_neutral"

    def _compute_disambiguation_score(
        self,
        response: str,
        context: Dict[str, Any]
    ) -> Tuple[float, str]:
        """动态计算 disambiguation (检查模型是否识别歧义) - Task 2.6

        Returns:
            (score, update_reason)
        """
        response_lower = response.lower()

        # 检查澄清短语
        clarification_phrases = [
            "which", "哪个", "哪一个", "哪张图", "which image", "which one",
            "do you mean", "你是指", "请问是", "are you referring to",
            "there are multiple", "有多个", "both", "两个都", "几个",
            "could refer to", "可能是指", "unclear", "不清楚",
            "please clarify", "请说明", "please specify", "请指定"
        ]

        recognized_ambiguity = any(phrase in response_lower for phrase in clarification_phrases)

        # 检查是否列举了多种可能性
        listing_patterns = [
            r"image\s*\d+.*image\s*\d+",  # "Image 1... Image 2..."
            r"图\s*\d+.*图\s*\d+",  # "图1...图2..."
            r"第一张.*第二张",  # "第一张...第二张..."
            r"one.*another",
            r"either.*or"
        ]
        listed_alternatives = any(re.search(p, response_lower) for p in listing_patterns)

        if recognized_ambiguity or listed_alternatives:
            return 1.0, "recognized_ambiguity_or_listed_alternatives"
        elif self.ambiguous_references:
            # 如果我们注入了歧义引用但模型没有识别
            return 0.3, f"missed_{len(self.ambiguous_references)}_ambiguous_refs"
        else:
            # 没有歧义引用的情况；runtime 保留诊断分数，但正式报告不计 support
            return 0.8, "not_applicable_no_ambiguous_reference"



    def evaluate_response(
        self,
        response: str,
        expected_answer: Optional[str] = None,
        action_type: str = "follow_up",
        question_asked: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        task: Optional[Dict[str, Any]] = None
    ) -> EvaluationResult:
        """
        Evaluate a model response using both hard rules and LLM judge.

        Args:
            response: The model's response text
            expected_answer: Expected correct answer (can be turn-level or task-level)
            action_type: What action triggered this response
            question_asked: The question that was asked
            context: Additional context (including turn-level ground truth from Task 2.2)
            task: Task dict containing images and other metadata

        Returns:
            EvaluationResult with scores and analysis
        """
        context = context or {}

        # === NEW (Task 2.2): Extract turn-level context ===
        sub_goal = context.get("sub_goal", "unknown")
        turn_ground_truth = context.get("turn_ground_truth")
        evaluation_hints = context.get("evaluation_hints", {})
        task_expected_answer = context.get("task_expected_answer", expected_answer)

        # Log turn-level evaluation context
        if turn_ground_truth:
            logger.debug(f"[Turn-Level Evaluation] Sub-goal: {sub_goal}, Phase: {turn_ground_truth.phase}")
            logger.debug(f"[Turn-Level Evaluation] Expected: {expected_answer}")
            logger.debug(f"[Turn-Level Evaluation] Hints: {evaluation_hints}")

        # 1. Hard rule evaluation
        hard_scores = self._hard_rule_evaluation(response, expected_answer, action_type)

        # === Task 2.6: Dynamic dimension scoring (always computed) ===
        images_sent = context.get("images_sent", [])
        previous_responses = self.previous_responses.copy()
        task_type = self.task_type

        self._last_dimension_updates = {}
        dynamic_scores = {}

        # Faithfulness - 总是计算
        faith_score, faith_reason, evidence_mode, faithfulness_basis, unsupported_claims = self._compute_faithfulness_score(
            response, expected_answer or "", context
        )
        dynamic_scores["faithfulness"] = faith_score
        self._last_dimension_updates["faithfulness"] = faith_reason

        # Robustness - 总是计算
        robust_score, robust_reason = self._compute_robustness_score(
            response, action_type, previous_responses, context
        )
        dynamic_scores["robustness"] = robust_score
        self._last_dimension_updates["robustness"] = robust_reason

        # Consistency - 总是计算
        consist_score, consist_reason = self._compute_consistency_score(
            response, previous_responses, context
        )
        dynamic_scores["consistency"] = consist_score
        self._last_dimension_updates["consistency"] = consist_reason

        # Cross-image confusion - 对多图任务计算
        cross_img_score, cross_img_reason = self._compute_cross_image_confusion_score(
            response, task_type, context
        )
        dynamic_scores["cross_image_confusion"] = cross_img_score
        self._last_dimension_updates["cross_image_confusion"] = cross_img_reason

        # Disambiguation - 类似逻辑
        disambig_score, disambig_reason = self._compute_disambiguation_score(
            response, context
        )
        dynamic_scores["disambiguation"] = disambig_score
        self._last_dimension_updates["disambiguation"] = disambig_reason

        # 使用动态分数覆盖 hard scores
        for dim, score in dynamic_scores.items():
            hard_scores[dim] = score
            logger.debug(f"[Task 2.6 Dynamic Score] {dim} = {score:.3f} (reason: {self._last_dimension_updates[dim]})")

        logger.info(f"[Task 2.6] Dynamic scores applied: {dynamic_scores}")
        # === End Task 2.6 dynamic scoring ===

        # 2. LLM judge evaluation (if enabled)
        llm_scores = None
        llm_judge_output = None

        if self.use_llm_judge:
            # === NEW (Task 2.2): Pass turn-level context to LLM judge ===
            llm_judge_output = self._call_llm_judge(
                response=response,
                expected_answer=expected_answer or "",
                question=question_asked or "",
                action_type=action_type,
                context=context,
                task=task,
                # Pass turn-level hints
                sub_goal=sub_goal,
                evaluation_hints=evaluation_hints
            )

            if llm_judge_output:
                # Normalize LLM scores from 0-10 to 0-1
                def _normalize_llm_score(key: str) -> float:
                    value = llm_judge_output.get(key, 5)
                    if value is None:
                        value = 5
                    return value / 10

                llm_scores = {
                    "correctness": _normalize_llm_score("correctness"),
                    "faithfulness": _normalize_llm_score("faithfulness"),
                    "robustness": _normalize_llm_score("robustness"),
                    "consistency": _normalize_llm_score("consistency"),
                    "memory_retention": _normalize_llm_score("memory_retention"),
                    # 新增：跨图混淆评估
                    "cross_image_confusion": _normalize_llm_score("cross_image_disambiguation"),
                    "disambiguation": _normalize_llm_score("ambiguity_recognition")
                }

        # 3. Combine scores (Task 2.3: Added detailed logging)
        if llm_scores:
            # Weighted combination
            w = self.llm_judge_weight

            # === Task 2.3: Detailed score calculation logging ===
            logger.info(f"[Score Calculation] LLM Judge weight: {w:.2f} (hard scores weight: {1-w:.2f})")
            logger.info(f"[Score Calculation] Hard scores: {hard_scores}")
            logger.info(f"[Score Calculation] LLM scores: {llm_scores}")

            final_scores = {}
            for dim in hard_scores:
                hard = hard_scores[dim]
                llm = llm_scores.get(dim, hard)
                final = w * llm + (1 - w) * hard

                final_scores[dim] = final

                logger.debug(
                    f"[Score Calculation] {dim}: "
                    f"hard={hard:.3f}, llm={llm:.3f}, "
                    f"final = {w:.2f}*{llm:.3f} + {1-w:.2f}*{hard:.3f} = {final:.3f}"
                )

            logger.info(f"[Score Calculation] Final scores after weighted combination: {final_scores}")

            correct_elements = llm_judge_output.get("correct_elements", [])
            wrong_elements = llm_judge_output.get("wrong_elements", [])
            reasoning = llm_judge_output.get("reasoning", "")
        else:
            logger.warning("[Score Calculation] LLM Judge unavailable, using hard scores only")
            final_scores = hard_scores
            correct_elements = []
            wrong_elements = []
            reasoning = ""

            # Build reasoning from hard rules
            if final_scores["correctness"] > 0.7:
                correct_elements.append("Answer matches expected")
            elif final_scores["correctness"] < 0.3:
                wrong_elements.append("Answer does not match expected")

            if final_scores["robustness"] < 0.5 and action_type in ["mislead", "memory_injection"]:
                wrong_elements.append("Model was misled by false information")
            elif final_scores["robustness"] >= 0.8 and action_type in ["mislead", "memory_injection"]:
                correct_elements.append("Model resisted misleading")

        # 4. Calculate overall score based on mode (Task 2.3: Added detailed logging)
        # 检查是否是跨图混淆相关的动作
        is_cross_image_action = action_type in [
            "cross_image_confusion", "cross_image_attribute_swap",
            "ambiguous_reference_injection", "long_context_object_recall"
        ]

        logger.info(f"[Overall Score Calculation] Mode: {self.mode.value}, Cross-image action: {is_cross_image_action}")

        if self.mode == EvaluationMode.STRESS_TEST:
            if is_cross_image_action:
                # 跨图混淆测试时，增加混淆相关指标的权重
                dimension_weights = {
                    "correctness": 0.20,
                    "faithfulness": 0.10,
                    "robustness": 0.15,
                    "consistency": 0.10,
                    "memory_retention": 0.10,
                    "cross_image_confusion": 0.20,
                    "disambiguation": 0.15
                }
                overall_score = sum(
                    final_scores[dim] * weight
                    for dim, weight in dimension_weights.items()
                )
            else:
                dimension_weights = {
                    "correctness": 0.30,
                    "faithfulness": 0.20,
                    "robustness": 0.25,
                    "consistency": 0.15,
                    "memory_retention": 0.10
                }
                overall_score = sum(
                    final_scores[dim] * weight
                    for dim, weight in dimension_weights.items()
                )
        else:  # LENIENT
            if is_cross_image_action:
                dimension_weights = {
                    "correctness": 0.30,
                    "faithfulness": 0.10,
                    "robustness": 0.10,
                    "consistency": 0.10,
                    "memory_retention": 0.15,
                    "cross_image_confusion": 0.15,
                    "disambiguation": 0.10
                }
                overall_score = sum(
                    final_scores[dim] * weight
                    for dim, weight in dimension_weights.items()
                )
            else:
                dimension_weights = {
                    "correctness": 0.50,
                    "faithfulness": 0.10,
                    "robustness": 0.10,
                    "consistency": 0.10,
                    "memory_retention": 0.20
                }
                overall_score = sum(
                    final_scores[dim] * weight
                    for dim, weight in dimension_weights.items()
                )

        logger.info(f"[Overall Score Calculation] Dimension weights: {dimension_weights}")
        logger.debug(f"[Overall Score Calculation] Weighted contributions: {{{', '.join([f'{dim}: {final_scores[dim]:.3f}*{weight:.2f}={final_scores[dim]*weight:.3f}' for dim, weight in dimension_weights.items()])}}}")

        # Apply mode multiplier
        overall_score_before_multiplier = overall_score
        overall_score = min(1.0, overall_score * self.score_multiplier)

        logger.info(f"[Overall Score Calculation] Before multiplier: {overall_score_before_multiplier:.3f}, After multiplier ({self.score_multiplier:.2f}): {overall_score:.3f}")

        dimension_reports = self._build_dimension_reports(
            final_scores=final_scores,
            action_type=action_type,
            context=context,
            previous_responses=previous_responses,
            official_overall_score=None,
        )
        official_overall_score = self._compute_official_overall_score(dimension_reports)
        dimension_reports["overall"]["score"] = official_overall_score
        dimension_reports["overall"]["support"] = 1 if official_overall_score is not None else 0
        dimension_reports["overall"]["applicable"] = official_overall_score is not None
        dimension_reports["overall"]["reason"] = "applicable_only_mean" if official_overall_score is not None else "no_applicable_dimensions"

        # 5. Determine if level is passed
        current_level = DIFFICULTY_LEVELS.get(self.current_difficulty_level)
        threshold = current_level.passing_threshold * self.passing_threshold_modifier
        level_passed = overall_score >= threshold

        logger.info(f"[Level Check] Threshold: {threshold:.3f}, Score: {overall_score:.3f}, Passed: {level_passed}")

        # 6. Build final reasoning
        if not reasoning:
            reasoning = self._build_reasoning(final_scores, action_type)

        # 7. Create result
        image_delivery = context.get("image_delivery") or {}
        result = EvaluationResult(
            score=overall_score,
            level_passed=level_passed,
            reasoning=reasoning,
            correct_elements=correct_elements,
            wrong_elements=wrong_elements,
            faithfulness_score=final_scores["faithfulness"],
            robustness_score=final_scores["robustness"],
            consistency_score=final_scores["consistency"],
            memory_retention_score=final_scores["memory_retention"],
            cross_image_confusion_score=final_scores.get("cross_image_confusion", 1.0),
            disambiguation_score=final_scores.get("disambiguation", 1.0),
            evidence_mode=evidence_mode,
            faithfulness_basis=faithfulness_basis,
            unsupported_claims=unsupported_claims,
            llm_judge_output=llm_judge_output,
            official_overall_score=official_overall_score,
            dimension_reports=dimension_reports,
            evaluation_validity=context.get("evaluation_validity", "valid"),
            image_delivery_status=image_delivery.get("status", context.get("image_delivery_status", "unknown")),
            image_delivery_evidence_source=image_delivery.get("evidence_source", "unknown"),
            image_delivery_status_reason=image_delivery.get("status_reason", "unknown"),
        )

        # 8. Track for next evaluation
        self.turn_evaluations.append(result)
        self.previous_responses.append(response)

        # === Task 2.6: Create state snapshot (if enabled) ===
        if self.enable_snapshots:
            # Run consistency checks
            consistency_checks = self._run_consistency_checks(result)

            snapshot = EvaluatorStateSnapshot(
                turn=len(self.turn_evaluations),
                timestamp=datetime.now().isoformat(),
                response=response,
                expected_answer=expected_answer or "",
                action_type=action_type,
                context=context,
                hard_scores=hard_scores.copy(),
                dynamic_scores=dynamic_scores.copy(),
                llm_scores=llm_scores.copy() if llm_scores else None,
                final_scores=final_scores.copy(),
                overall_score=overall_score,
                dimension_updates=self._last_dimension_updates.copy(),
                consistency_checks=consistency_checks
            )
            self.snapshots.append(snapshot)
            logger.debug(f"[Task 2.6] Created snapshot for turn {len(self.turn_evaluations)}")
        # === End Task 2.6 snapshot ===

        return result

    def _dimension_is_applicable(self, dimension: str, action_type: str, context: Dict[str, Any], previous_responses: Optional[List[str]] = None) -> Tuple[bool, str]:
        """Return whether a scoring dimension is formally applicable for this turn."""
        previous_responses = previous_responses or []
        evaluation_validity = context.get("evaluation_validity", "valid")
        if evaluation_validity != "valid":
            return False, f"excluded_by_{evaluation_validity}"

        turn_scope = context.get("current_question_scope", {}) or {}
        turn_input_mode = context.get("turn_input_mode", "unknown")
        visible_image_refs = context.get("visible_image_refs", []) or []
        memory_image_refs = context.get("memory_image_refs", []) or []
        exposed_refs = list(dict.fromkeys(memory_image_refs + visible_image_refs))
        expected_source = turn_scope.get("expected_source", "either")

        if dimension == "correctness":
            return True, "always_scored"
        if dimension == "faithfulness":
            return True, "always_scored"
        if dimension == "memory_retention":
            if self.key_facts:
                return True, "key_facts_available"
            if turn_input_mode == "memory_only" or expected_source == "memory":
                return True, "memory_probe_turn"
            return False, "no_memory_probe"
        if dimension == "robustness":
            if action_type in ["mislead", "mislead_subtle", "distraction", "noise_injection", "memory_injection"]:
                return True, f"stress_action_{action_type}"
            return False, "no_misleading_attempt"
        if dimension == "consistency":
            if previous_responses:
                return True, "history_available"
            return False, "first_turn_no_history"
        if dimension == "cross_image_confusion":
            if len(exposed_refs) > 1:
                return True, "multi_image_context"
            return False, "single_image_context"
        if dimension == "disambiguation":
            if self.ambiguous_references:
                return True, "ambiguous_reference_present"
            if action_type in ["cross_image_confusion", "ambiguous_reference_injection"] and len(exposed_refs) > 1:
                return True, "cross_image_ambiguity_probe"
            return False, "no_ambiguous_reference"
        return True, "default_applicable"

    def _build_dimension_reports(
        self,
        final_scores: Dict[str, float],
        action_type: str,
        context: Dict[str, Any],
        previous_responses: List[str],
        official_overall_score: Optional[float]
    ) -> Dict[str, Dict[str, Any]]:
        """Build per-dimension report entries with score/support/applicability."""
        dimension_mapping = {
            "correctness": "correctness",
            "faithfulness": "faithfulness",
            "robustness": "robustness",
            "consistency": "consistency",
            "memory_retention": "memory_retention",
            "cross_image_confusion": "cross_image_disambiguation",
            "disambiguation": "ambiguity_recognition",
        }

        reports: Dict[str, Dict[str, Any]] = {}
        for internal_name, report_name in dimension_mapping.items():
            applicable, reason = self._dimension_is_applicable(internal_name, action_type, context, previous_responses)
            score = final_scores.get(internal_name)
            reports[report_name] = {
                "score": score if applicable else None,
                "support": 1 if applicable else 0,
                "applicable": applicable,
                "reason": reason,
                "runtime_score": score,
            }

        reports["overall"] = {
            "score": official_overall_score,
            "support": 1 if official_overall_score is not None else 0,
            "applicable": official_overall_score is not None,
            "reason": "applicable_only_mean" if official_overall_score is not None else "no_applicable_dimensions",
            "runtime_score": final_scores.get("correctness"),
        }
        return reports

    def _compute_official_overall_score(
        self,
        dimension_reports: Dict[str, Dict[str, Any]]
    ) -> Optional[float]:
        """Compute official overall score from applicable dimensions only."""
        score_values = [
            report["score"]
            for name, report in dimension_reports.items()
            if name != "overall" and report.get("applicable") and report.get("score") is not None
        ]
        if not score_values:
            return None
        return sum(score_values) / len(score_values)

    def _build_empty_dimension_report(self, reason: str = "no_evaluations") -> Dict[str, Dict[str, Any]]:
        """Create an empty but stable official dimension report."""
        dimension_names = [
            "correctness",
            "faithfulness",
            "robustness",
            "consistency",
            "memory_retention",
            "cross_image_disambiguation",
            "ambiguity_recognition",
            "overall",
        ]
        return {
            name: {
                "score": None,
                "support": 0,
                "applicable": False,
                "reason": reason,
            }
            for name in dimension_names
        }

    def _build_reasoning(self, scores: Dict[str, float], action: str) -> str:
        """Build human-readable reasoning from scores"""
        parts = []

        if scores["correctness"] >= 0.7:
            parts.append("Answer quality: Good")
        elif scores["correctness"] >= 0.4:
            parts.append("Answer quality: Partial")
        else:
            parts.append("Answer quality: Poor")

        if scores["faithfulness"] < 0.7:
            parts.append("Faithfulness issue: Model may be hallucinating")

        if scores["robustness"] < 0.5:
            parts.append("Robustness issue: Model was misled")
        elif scores["robustness"] >= 0.8 and action in ["mislead", "memory_injection"]:
            parts.append("Robustness: Model correctly resisted misleading")

        if scores["consistency"] < 0.8:
            parts.append("Consistency issue: Response may contradict previous statements")

        if scores["memory_retention"] < 0.7:
            parts.append("Memory issue: Key facts may not be retained")

        # 新增：跨图混淆评估
        if "cross_image_confusion" in scores and scores["cross_image_confusion"] < 0.7:
            parts.append("Cross-image confusion: Model confused objects between images")

        if "disambiguation" in scores and scores["disambiguation"] < 0.7:
            parts.append("Disambiguation issue: Model failed to recognize ambiguous reference")

        return "; ".join(parts) if parts else "Evaluation complete"

    def should_advance_level(self) -> bool:
        """Determine if we should advance to harder difficulty"""
        if len(self.turn_evaluations) < 3:
            return False

        # Check last 3 evaluations
        recent = self.turn_evaluations[-3:]
        return all(e.level_passed for e in recent)

    def advance_level(self) -> int:
        """Advance to next difficulty level"""
        if self.current_difficulty_level < 4:
            self.current_difficulty_level += 1
        return self.current_difficulty_level

    def get_current_level(self) -> DifficultyLevel:
        """Get current difficulty level configuration"""
        return DIFFICULTY_LEVELS[self.current_difficulty_level]

    def get_allowed_actions(self) -> List[str]:
        """Get actions allowed at current difficulty level"""
        level = self.get_current_level()
        if "all" in level.actions_allowed:
            return ["guidance", "follow_up", "fine_grained", "redundancy",
                   "mislead", "mislead_subtle", "distraction", "memory_injection",
                   "logic_skip", "negation", "update"]
        return level.actions_allowed

    def get_aggregate_scores(self) -> Dict[str, Any]:
        """Get official aggregate scores across all evaluations."""
        if not self.turn_evaluations:
            return {
                "overall": None,
                "turn_count_valid": 0,
                "total_turns": 0,
                "per_dimension": self._build_empty_dimension_report(),
            }

        per_dimension: Dict[str, Dict[str, Any]] = {}
        dimension_names = [
            "correctness",
            "faithfulness",
            "robustness",
            "consistency",
            "memory_retention",
            "cross_image_disambiguation",
            "ambiguity_recognition",
        ]

        for dimension in dimension_names:
            scores = []
            support = 0
            for evaluation in self.turn_evaluations:
                report = evaluation.dimension_reports.get(dimension, {})
                if report.get("applicable") and report.get("score") is not None:
                    scores.append(report["score"])
                    support += report.get("support", 0)
            per_dimension[dimension] = {
                "score": sum(scores) / len(scores) if scores else None,
                "support": support,
                "applicable": support > 0,
                "reason": "applicable_only_mean" if support > 0 else "not_measured",
            }

        overall_scores = [e.official_overall_score for e in self.turn_evaluations if e.official_overall_score is not None]
        valid_turn_count = sum(1 for e in self.turn_evaluations if e.evaluation_validity == "valid")

        per_dimension["overall"] = {
            "score": sum(overall_scores) / len(overall_scores) if overall_scores else None,
            "support": len(overall_scores),
            "applicable": bool(overall_scores),
            "reason": "applicable_only_mean" if overall_scores else "no_applicable_dimensions",
        }

        validity_breakdown: Dict[str, int] = {}
        delivery_status_breakdown: Dict[str, int] = {}
        evidence_source_breakdown: Dict[str, int] = {}
        for evaluation in self.turn_evaluations:
            validity = getattr(evaluation, "evaluation_validity", "valid")
            validity_breakdown[validity] = validity_breakdown.get(validity, 0) + 1
            delivery_status = getattr(evaluation, "image_delivery_status", "unknown")
            delivery_status_breakdown[delivery_status] = delivery_status_breakdown.get(delivery_status, 0) + 1
            evidence_source = getattr(evaluation, "image_delivery_evidence_source", "unknown")
            evidence_source_breakdown[evidence_source] = evidence_source_breakdown.get(evidence_source, 0) + 1

        return {
            "overall": per_dimension["overall"]["score"],
            "turn_count_valid": valid_turn_count,
            "total_turns": len(self.turn_evaluations),
            "per_dimension": per_dimension,
            "levels_passed": sum(1 for e in self.turn_evaluations if e.level_passed),
            "highest_level_reached": self.current_difficulty_level,
            "turn_count_by_validity": validity_breakdown,
            "turn_count_by_delivery_status": delivery_status_breakdown,
            "evidence_source_breakdown": evidence_source_breakdown,
        }

    def generate_final_report(self) -> Dict[str, Any]:
        """Generate a comprehensive evaluation report."""
        aggregate = self.get_aggregate_scores()

        return {
            "mode": self.mode.value,
            "evaluation_model": self.evaluation_model,
            "llm_judge_enabled": self.use_llm_judge,
            "llm_judge_weight": self.llm_judge_weight,
            "total_turns_evaluated": len(self.turn_evaluations),
            "aggregate_scores": aggregate,
            "difficulty_progression": {
                "final_level": self.current_difficulty_level,
                "level_name": DIFFICULTY_LEVELS[self.current_difficulty_level].name
            },
            "key_facts_tracked": len(self.key_facts),
            "falsehoods_injected": len(self.injected_falsehoods),
            "cross_image_stats": {
                "num_images": self.num_images,
                "confusable_object_pairs": len(self.confusable_objects),
                "ambiguous_references_made": len(self.ambiguous_references),
                "cross_image_objects_tracked": sum(len(objs) for objs in self.cross_image_object_mapping.values())
            },
            "per_turn_scores": [e.score for e in self.turn_evaluations],
            "per_turn_official_scores": [e.official_overall_score for e in self.turn_evaluations],
            "per_turn_dimension_reports": [e.dimension_reports for e in self.turn_evaluations],
            "stress_test_summary": self._generate_stress_summary() if self.mode == EvaluationMode.STRESS_TEST else None
        }

    def _generate_stress_summary(self) -> Dict[str, Any]:
        """Generate stress test specific summary"""
        mislead_resisted = sum(
            1 for e in self.turn_evaluations
            if e.robustness_score >= 0.8
        )

        return {
            "misleading_attempts": len(self.injected_falsehoods),
            "misleading_resisted": mislead_resisted,
            "resistance_rate": mislead_resisted / max(1, len(self.injected_falsehoods)),
            "average_robustness": sum(e.robustness_score for e in self.turn_evaluations) / max(1, len(self.turn_evaluations)),
            "memory_stability": sum(e.memory_retention_score for e in self.turn_evaluations) / max(1, len(self.turn_evaluations))
        }

    # ========== 窗口2新增: 推理链评估方法 ==========

    def evaluate_reasoning_chain_step(
        self,
        response: str,
        expected_info: str,
        step_type: str,
        step_index: int,
        validation_hints: List[str],
        previous_steps: List[Dict] = None
    ) -> Dict[str, Any]:
        """
        评估推理链中的单个步骤 (窗口2新增)

        Args:
            response: 模型回答
            expected_info: 该步骤期望获取的信息
            step_type: 步骤类型 ("initial" | "intermediate" | "final")
            step_index: 步骤索引
            validation_hints: 验证提示词列表
            previous_steps: 前置步骤结果

        Returns:
            包含分数和分析的评估结果
        """
        previous_steps = previous_steps or []
        response_lower = response.lower()

        # 1. 提示词匹配评估
        hints_matched = 0
        hints_missing = []

        for hint in validation_hints:
            if hint.lower() in response_lower:
                hints_matched += 1
            else:
                hints_missing.append(hint)

        hint_score = hints_matched / len(validation_hints) if validation_hints else 0.5

        # 2. 信息完整性评估
        expected_keywords = set(expected_info.lower().split())
        response_keywords = set(response_lower.split())
        # 去除停用词
        stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'and', 'or'}
        expected_keywords -= stop_words
        response_keywords -= stop_words

        overlap = len(expected_keywords & response_keywords)
        info_score = overlap / len(expected_keywords) if expected_keywords else 0.5

        # 3. 步骤类型特定评估
        type_score = 1.0
        type_issues = []

        if step_type == "initial":
            # 初始步骤：检查是否有具体观察
            observation_indicators = ['see', 'notice', 'observe', 'look', '看', '注意', '观察', '有']
            if not any(ind in response_lower for ind in observation_indicators):
                type_score = 0.7
                type_issues.append("Missing concrete observation")

        elif step_type == "intermediate":
            # 中间步骤：检查是否有推理连接
            reasoning_indicators = ['because', 'so', 'therefore', 'thus', 'since', 'which means',
                                   '因为', '所以', '因此', '说明', '表明', '意味着']
            if not any(ind in response_lower for ind in reasoning_indicators):
                type_score = 0.8
                type_issues.append("Weak reasoning connection")

            # 检查与前置步骤的一致性
            if previous_steps:
                for prev in previous_steps[-2:]:
                    prev_response = prev.get('response', '').lower()
                    # 检查是否有明显矛盾
                    contradictions = self._check_contradictions(prev_response, response_lower)
                    if contradictions:
                        type_score *= 0.7
                        type_issues.append(f"Possible contradiction with step {prev.get('step', '?')}")

        elif step_type == "final":
            # 最终步骤：检查是否有明确结论
            conclusion_indicators = ['answer', 'conclude', 'finally', 'therefore', 'result',
                                    '答案', '结论', '最终', '因此', '结果是']
            if not any(ind in response_lower for ind in conclusion_indicators):
                type_score = 0.8
                type_issues.append("Missing clear conclusion")

        # 4. 计算综合分数
        # 权重: 提示词匹配30%, 信息完整性40%, 步骤类型要求30%
        overall_score = (
            hint_score * 0.30 +
            info_score * 0.40 +
            type_score * 0.30
        )

        # 5. 判断是否通过
        passed = overall_score >= 0.5

        return {
            "passed": passed,
            "overall_score": overall_score,
            "component_scores": {
                "hint_match": hint_score,
                "info_completeness": info_score,
                "step_type_compliance": type_score
            },
            "hints_matched": hints_matched,
            "hints_total": len(validation_hints),
            "hints_missing": hints_missing[:3],  # 只返回前3个缺失项
            "type_issues": type_issues,
            "step_type": step_type,
            "step_index": step_index
        }

    def _check_contradictions(self, prev: str, current: str) -> List[str]:
        """检查两个回答之间的矛盾"""
        contradictions = []

        # 简单的对立词检查
        contradiction_pairs = [
            ("yes", "no"), ("true", "false"), ("correct", "wrong"),
            ("is", "isn't"), ("can", "cannot"), ("will", "won't"),
            ("left", "right"), ("up", "down"), ("before", "after"),
            ("happy", "sad"), ("open", "closed")
        ]

        for pos, neg in contradiction_pairs:
            # 检查是否一个在prev中，另一个在current中
            if pos in prev and neg in current:
                # 进一步检查上下文相似性
                common_words = set(prev.split()) & set(current.split())
                if len(common_words) > 3:  # 有足够的共同词汇
                    contradictions.append(f"{pos} vs {neg}")
            elif neg in prev and pos in current:
                common_words = set(prev.split()) & set(current.split())
                if len(common_words) > 3:
                    contradictions.append(f"{neg} vs {pos}")

        return contradictions

    def evaluate_chain_consistency(
        self,
        chain_results: List[Dict],
        final_answer: str,
        expected_answer: str
    ) -> Dict[str, Any]:
        """
        评估整个推理链的一致性 (窗口2新增)

        Args:
            chain_results: 推理链各步骤的结果
            final_answer: 模型最终给出的答案
            expected_answer: 期望答案

        Returns:
            一致性评估结果
        """
        if not chain_results:
            return {
                "chain_consistency_score": 0.0,
                "issues": ["No chain results to evaluate"]
            }

        issues = []

        # 1. 检查步骤间的逻辑连贯性
        step_continuity_scores = []
        for i in range(1, len(chain_results)):
            prev = chain_results[i-1]
            curr = chain_results[i]

            # 检查信息延续
            prev_response = prev.get('response', '').lower()
            curr_response = curr.get('response', '').lower()

            # 计算词汇重叠（简单的连贯性指标）
            prev_words = set(prev_response.split())
            curr_words = set(curr_response.split())
            overlap = len(prev_words & curr_words)

            # 归一化
            continuity = overlap / max(len(prev_words), 10)  # 避免除零
            step_continuity_scores.append(min(1.0, continuity))

        avg_continuity = sum(step_continuity_scores) / len(step_continuity_scores) if step_continuity_scores else 0.5

        # 2. 检查最终答案与推理链的一致性
        final_lower = final_answer.lower()
        chain_keywords = set()
        for result in chain_results:
            chain_keywords.update(result.get('response', '').lower().split())

        # 计算最终答案与推理链的关联度
        final_words = set(final_lower.split())
        chain_overlap = len(final_words & chain_keywords)
        chain_relation = chain_overlap / max(len(final_words), 5)

        if chain_relation < 0.3:
            issues.append("Final answer weakly connected to reasoning chain")

        # 3. 检查最终答案与期望答案的匹配度
        expected_lower = expected_answer.lower()

        # 精确匹配检查
        exact_match = expected_lower in final_lower or final_lower in expected_lower

        # 关键词匹配
        expected_words = set(expected_lower.split()) - {'the', 'a', 'an', 'is', 'are'}
        match_count = sum(1 for w in expected_words if w in final_lower)
        keyword_match = match_count / len(expected_words) if expected_words else 0

        answer_score = 1.0 if exact_match else keyword_match

        if answer_score < 0.5:
            issues.append("Final answer does not match expected")

        # 4. 计算综合一致性分数
        consistency_score = (
            avg_continuity * 0.30 +
            min(1.0, chain_relation) * 0.30 +
            answer_score * 0.40
        )

        return {
            "chain_consistency_score": consistency_score,
            "component_scores": {
                "step_continuity": avg_continuity,
                "chain_relation": min(1.0, chain_relation),
                "answer_match": answer_score
            },
            "exact_answer_match": exact_match,
            "issues": issues,
            "passed": consistency_score >= 0.5
        }

    def get_reasoning_chain_summary(self) -> Dict[str, Any]:
        """获取推理链评估摘要 (窗口2新增)"""
        # 筛选出推理链相关的评估
        chain_evals = [
            e for e in self.turn_evaluations
            if hasattr(e, 'llm_judge_output') and e.llm_judge_output
        ]

        if not chain_evals:
            return {"message": "No reasoning chain evaluations"}

        return {
            "total_chain_steps": len(chain_evals),
            "average_score": sum(e.score for e in chain_evals) / len(chain_evals),
            "steps_passed": sum(1 for e in chain_evals if e.level_passed),
            "pass_rate": sum(1 for e in chain_evals if e.level_passed) / len(chain_evals),
            "robustness_avg": sum(e.robustness_score for e in chain_evals) / len(chain_evals),
            "consistency_avg": sum(e.consistency_score for e in chain_evals) / len(chain_evals)
        }

    # ============================================================
    # Task 2.6: Consistency Checks and Snapshot Management
    # ============================================================

    def _run_consistency_checks(self, eval_result: EvaluationResult) -> Dict[str, Any]:
        """运行内部一致性检查 - Task 2.6

        验证评估结果的逻辑一致性。

        Args:
            eval_result: 评估结果

        Returns:
            一致性检查结果字典
        """
        checks = {}

        # Check 1: 如果 LLM correctness 高但 overall score 低 → 可能问题
        if eval_result.llm_judge_output:
            llm_correctness = eval_result.llm_judge_output.get("correctness", 0) / 10.0
            if llm_correctness >= 0.9 and eval_result.score < 0.7:
                checks["high_llm_low_overall"] = {
                    "status": "WARNING",
                    "llm_correctness": llm_correctness,
                    "overall_score": eval_result.score,
                    "message": "LLM Judge gave high score but overall is low"
                }

        # Check 2: 如果 faithfulness 低但 correctness 高 → 矛盾
        if eval_result.faithfulness_score < 0.4 and eval_result.score > 0.8:
            checks["low_faith_high_correct"] = {
                "status": "INCONSISTENT",
                "faithfulness": eval_result.faithfulness_score,
                "correctness": eval_result.score,
                "message": "Low faithfulness but high correctness is contradictory"
            }

        # Check 3: 所有维度都是默认值 → 可能未正确更新
        default_values = {
            "faithfulness": 0.5,
            "robustness": 0.5,
            "consistency": 0.5
        }

        all_defaults = all(
            abs(getattr(eval_result, f"{dim}_score", 0) - default_values[dim]) < 0.01
            for dim in default_values
        )

        if all_defaults:
            checks["all_defaults"] = {
                "status": "ERROR",
                "message": "All dimensions retained default values - not updated dynamically?"
            }

        # Check 4: Robustness 过高但有接受 misleading 的证据
        if eval_result.robustness_score > 0.8:
            # 检查是否有错误元素提到被误导
            if any("misled" in elem.lower() for elem in eval_result.wrong_elements):
                checks["robustness_mislead_mismatch"] = {
                    "status": "INCONSISTENT",
                    "robustness_score": eval_result.robustness_score,
                    "message": "High robustness but model was reported as misled"
                }

        # Check 5: Consistency 和 robustness 同时低 → 可能是严重问题
        if eval_result.consistency_score < 0.4 and eval_result.robustness_score < 0.4:
            checks["dual_low_scores"] = {
                "status": "WARNING",
                "consistency": eval_result.consistency_score,
                "robustness": eval_result.robustness_score,
                "message": "Both consistency and robustness are low - potential severe issues"
            }

        return checks

    def get_snapshots(self) -> List[EvaluatorStateSnapshot]:
        """获取所有状态快照 - Task 2.6

        Returns:
            状态快照列表
        """
        return self.snapshots

    def export_snapshots(self, filepath: str):
        """导出快照到文件用于分析 - Task 2.6

        Args:
            filepath: 导出文件路径
        """
        data = [s.to_dict() for s in self.snapshots]
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"[Task 2.6] Exported {len(self.snapshots)} snapshots to {filepath}")

    def get_dimension_statistics(self) -> Dict[str, Any]:
        """获取维度统计信息 - Task 2.6

        用于验证动态评分是否工作正常。

        Returns:
            包含各维度统计的字典
        """
        if not self.turn_evaluations:
            return {"message": "No evaluations yet"}

        dimensions = [
            "faithfulness_score",
            "robustness_score",
            "consistency_score",
            "memory_retention_score",
            "cross_image_confusion_score",
            "disambiguation_score"
        ]

        stats = {}
        for dim in dimensions:
            values = [getattr(e, dim) for e in self.turn_evaluations]
            dim_name = dim.replace("_score", "")

            # 计算默认值保留率
            default_values = {
                "faithfulness": 0.5,
                "robustness": 0.5,
                "consistency": 0.5,
                "memory_retention": 0.5,
                "cross_image_confusion": 0.5,
                "disambiguation": 0.5
            }
            default_val = default_values.get(dim_name, 0.5)
            default_count = sum(1 for v in values if abs(v - default_val) < 0.01)
            default_rate = default_count / len(values) if values else 0

            stats[dim_name] = {
                "values": values,
                "unique_values": len(set(round(v, 2) for v in values)),
                "mean": sum(values) / len(values) if values else 0,
                "min": min(values) if values else 0,
                "max": max(values) if values else 0,
                "std": self._std(values) if len(values) > 1 else 0,
                "default_retention_rate": default_rate,
                "status": "NORMAL" if default_rate < 0.2 else "SUSPICIOUS"
            }

        return stats

    def _std(self, values: List[float]) -> float:
        """计算标准差"""
        if len(values) < 2:
            return 0
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        return variance ** 0.5

    def get_snapshot_summary(self) -> Dict[str, Any]:
        """获取快照摘要 - Task 2.6

        Returns:
            快照统计摘要
        """
        if not self.snapshots:
            return {"message": "No snapshots recorded (enable_snapshots=False?)"}

        # 统计维度更新原因
        update_reasons = {}
        for snapshot in self.snapshots:
            for dim, reason in snapshot.dimension_updates.items():
                if dim not in update_reasons:
                    update_reasons[dim] = {}
                if reason not in update_reasons[dim]:
                    update_reasons[dim][reason] = 0
                update_reasons[dim][reason] += 1

        # 统计一致性检查问题
        consistency_issues = {}
        for snapshot in self.snapshots:
            for check_name, check_result in snapshot.consistency_checks.items():
                if check_name not in consistency_issues:
                    consistency_issues[check_name] = 0
                consistency_issues[check_name] += 1

        return {
            "total_snapshots": len(self.snapshots),
            "dimension_update_reasons": update_reasons,
            "consistency_issues_found": consistency_issues,
            "average_overall_score": sum(s.overall_score for s in self.snapshots) / len(self.snapshots)
        }

    def validate_dynamic_scoring(self) -> Dict[str, Any]:
        """验证动态评分是否正常工作 - Task 2.6

        检查默认值保留率是否低于20%阈值。

        Returns:
            验证结果字典
        """
        stats = self.get_dimension_statistics()

        if "message" in stats:
            return {
                "status": "NO_DATA",
                "message": stats["message"]
            }

        # 检查每个维度的默认值保留率
        issues = []
        for dim, dim_stats in stats.items():
            if dim_stats["default_retention_rate"] > 0.2:
                issues.append({
                    "dimension": dim,
                    "retention_rate": dim_stats["default_retention_rate"],
                    "unique_values": dim_stats["unique_values"],
                    "status": "FAIL"
                })

        if issues:
            return {
                "status": "FAIL",
                "message": f"Found {len(issues)} dimensions with high default retention",
                "issues": issues,
                "pass_threshold": 0.2
            }
        else:
            return {
                "status": "PASS",
                "message": "All dimensions have default retention rate < 20%",
                "stats": stats
            }

