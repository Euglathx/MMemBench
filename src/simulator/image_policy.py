"""
Image Injection Policy for M3Bench
===================================

Phase 2 Task 2.5: Multi-Image Strategy Unification

This module provides unified image sending strategies for both
StrategicSimulator and LLMUserSimulator to ensure consistent
image injection behavior across the framework.
"""

from enum import Enum
from typing import List, Set
import logging

logger = logging.getLogger(__name__)


class ImageInjectionPolicy(str, Enum):
    """Image injection策略枚举

    Defines different strategies for sending images to the target VLM across multiple turns.
    """

    # 每个 turn 发送所有图像 (推荐用于多模态测试)
    SEND_ALL_EVERY_TURN = "send_all_every_turn"

    # 逐个发送图像 (用于测试渐进式信息披露)
    PROGRESSIVE = "progressive"

    # 仅在第一个 turn 发送所有图像
    SEND_ALL_FIRST_TURN = "send_all_first_turn"

    # 根据 action 类型决定
    ACTION_DEPENDENT = "action_dependent"


class ImagePolicyManager:
    """管理图像发送策略的决策

    This class encapsulates the logic for determining which images to send
    on each turn, based on the configured policy.

    Attributes:
        policy: The image injection policy to use
        images_shown_indices: Set of image indices that have been shown (for PROGRESSIVE mode)
    """

    def __init__(self, policy: ImageInjectionPolicy = ImageInjectionPolicy.SEND_ALL_EVERY_TURN):
        """Initialize the image policy manager

        Args:
            policy: The image injection policy to use (default: SEND_ALL_EVERY_TURN)
        """
        self.policy = policy
        self.images_shown_indices: Set[int] = set()
        self.exposed_indices: Set[int] = set()
        self.last_sent_indices: List[int] = []
        self.last_prior_exposed_indices: List[int] = []

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"[ImagePolicy] Initialized with policy: {policy}")

    def _finalize_selection(self, selected_indices: List[int], all_images: List[str]) -> List[str]:
        """Record per-turn image accounting and return selected image paths."""
        self.last_prior_exposed_indices = sorted(self.exposed_indices)
        self.last_sent_indices = list(selected_indices)
        self.exposed_indices.update(selected_indices)
        return [all_images[idx] for idx in selected_indices]

    def get_images_to_send(
        self,
        all_images: List[str],
        turn: int,
        action: str
    ) -> List[str]:
        """根据策略决定发送哪些图像

        Args:
            all_images: 所有可用图像路径列表
            turn: 当前 turn 编号 (1-indexed)
            action: 当前 action 类型 (e.g., "guidance", "follow_up", etc.)

        Returns:
            应该发送的图像路径列表
        """
        if not all_images:
            self.last_prior_exposed_indices = sorted(self.exposed_indices)
            self.last_sent_indices = []
            return []

        if self.policy == ImageInjectionPolicy.SEND_ALL_EVERY_TURN:
            # 每个turn发送所有图像 - 推荐策略
            return self._finalize_selection(list(range(len(all_images))), all_images)

        elif self.policy == ImageInjectionPolicy.PROGRESSIVE:
            # 逐个发送图像
            if action == "guidance":
                # 在 guidance action 时发送下一个未显示的图像
                for idx, _img in enumerate(all_images):
                    if idx not in self.images_shown_indices:
                        self.images_shown_indices.add(idx)
                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug(f"[ImagePolicy] PROGRESSIVE: Sending image {idx}")
                        return self._finalize_selection([idx], all_images)
                # 所有图像都已显示
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("[ImagePolicy] PROGRESSIVE: All images already shown")
                return self._finalize_selection([], all_images)
            else:
                # 非 guidance action: 不发送新图像
                return self._finalize_selection([], all_images)

        elif self.policy == ImageInjectionPolicy.SEND_ALL_FIRST_TURN:
            # 仅在第一个turn发送所有图像
            if turn == 1:
                return self._finalize_selection(list(range(len(all_images))), all_images)
            else:
                return self._finalize_selection([], all_images)

        elif self.policy == ImageInjectionPolicy.ACTION_DEPENDENT:
            # 根据action类型决定
            if action in ["guidance", "follow_up"]:
                # guidance 和 follow_up: 发送所有图像
                return self._finalize_selection(list(range(len(all_images))), all_images)
            else:
                # 其他 action: 不发送图像
                return self._finalize_selection([], all_images)

        else:
            # Default: 发送所有图像
            logger.warning(f"[ImagePolicy] Unknown policy: {self.policy}, defaulting to send all")
            return self._finalize_selection(list(range(len(all_images))), all_images)

    def get_last_sent_indices(self) -> List[int]:
        """Get local image indices sent in the most recent turn."""
        return list(self.last_sent_indices)

    def get_last_prior_exposed_indices(self) -> List[int]:
        """Get local image indices already exposed before the most recent turn."""
        return list(self.last_prior_exposed_indices)

    def get_exposed_indices(self) -> List[int]:
        """Get all local image indices exposed so far, including the current turn."""
        return sorted(self.exposed_indices)

    def reset(self):
        """重置策略状态 (主要用于 PROGRESSIVE 模式)

        Clears the tracking of which images have been shown.
        Call this when starting a new task.
        """
        self.images_shown_indices.clear()
        self.exposed_indices.clear()
        self.last_sent_indices = []
        self.last_prior_exposed_indices = []
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("[ImagePolicy] Reset images_shown_indices and image accounting state")
