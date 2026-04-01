"""
LLM Client for M3Bench User Simulator
======================================

Handles API calls to both the core model (thinking) and target model (image).

配置方式 (按优先级):
1. 直接传参给 LLMClient()
2. 环境变量: M3BENCH_API_URL, M3BENCH_API_KEY, M3BENCH_CORE_MODEL, M3BENCH_TARGET_MODEL
3. 默认值 (如果设置了默认值)

环境变量示例:
export M3BENCH_API_URL="https://api.openai.com/v1/chat/completions"
export M3BENCH_API_KEY="sk-your-api-key-here"
export M3BENCH_CORE_MODEL="gpt-4o"
export M3BENCH_TARGET_MODEL="gpt-4o"
"""

import requests
import json
import base64
import time
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
import logging

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

# Default fallback values (用户应该通过环境变量或参数覆盖这些值)
DEFAULT_API_URL = "https://globalai.vip/v1/chat/completions"
DEFAULT_API_KEY = "sk-PcyvuAqtt0yHsP88Mga584zkJIeP7VrSC2l4QOaK0wGpSx3R"
# DEFAULT_CORE_MODEL = "gemini-3-pro-image-preview"
DEFAULT_CORE_MODEL = "gpt-5.2"
# DEFAULT_TARGET_MODEL = "kimi-k2.5"
DEFAULT_TARGET_MODEL = "kimi-k2.5"
DEFAULT_WEAK_MODEL = "gpt-3.5-turbo"


class LLMClient:
    """Client for interacting with LLM APIs"""

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        core_model: Optional[str] = None,
        target_model: Optional[str] = None,
        weak_model: Optional[str] = None,
        timeout: int = 60
    ):
        """
        Initialize LLM client.

        Args:
            api_url: API endpoint URL (从环境变量 M3BENCH_API_URL 读取，或使用默认值)
            api_key: API key (从环境变量 M3BENCH_API_KEY 读取，或使用默认值)
            core_model: Model name for the core/thinking model (从环境变量 M3BENCH_CORE_MODEL 读取)
            target_model: Model name for the target/image model (从环境变量 M3BENCH_TARGET_MODEL 读取)
            weak_model: Model name for filler content
            timeout: Request timeout in seconds
        """
        # 优先级: 传参 > 环境变量 > 默认值
        self.api_url = api_url or os.getenv("M3BENCH_API_URL") or DEFAULT_API_URL
        self.api_key = api_key or os.getenv("M3BENCH_API_KEY") or DEFAULT_API_KEY
        self.core_model = core_model or os.getenv("M3BENCH_CORE_MODEL") or DEFAULT_CORE_MODEL
        self.target_model = target_model or os.getenv("M3BENCH_TARGET_MODEL") or DEFAULT_TARGET_MODEL
        self.weak_model = weak_model or os.getenv("M3BENCH_WEAK_MODEL") or DEFAULT_WEAK_MODEL
        self.timeout = timeout

        # 检查配置是否有效
        if not self.api_key or self.api_key.startswith("sk-PcyvuAqtt0y"):
            logger.warning(
                "使用默认API密钥。建议通过环境变量 M3BENCH_API_KEY 或参数设置您自己的密钥。"
            )

        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        logger.info(f"LLMClient初始化: api_url={self.api_url}, core_model={self.core_model}, target_model={self.target_model}")

    def _encode_image(self, image_path: str, max_size_mb: float = 5.0) -> Optional[str]:
        """
        Encode image to base64, with size checking and compression if needed.

        Args:
            image_path: Path to image file
            max_size_mb: Maximum allowed size in MB (default: 5MB)

        Returns:
            Base64 encoded image string, or None if failed
        """
        path = Path(image_path)
        if not path.exists():
            logger.warning(f"Image not found: {image_path}")
            return None

        try:
            # 读取原始图像数据
            with open(path, "rb") as f:
                image_data = f.read()

            # 检查原始文件大小
            file_size_mb = len(image_data) / (1024 * 1024)

            # 如果图像过大，尝试压缩
            if file_size_mb > max_size_mb:
                logger.warning(f"Image {image_path} is too large ({file_size_mb:.2f}MB > {max_size_mb}MB). Attempting compression...")
                try:
                    from PIL import Image
                    import io

                    # 打开图像
                    img = Image.open(path)

                    # 计算缩放比例
                    scale = (max_size_mb / file_size_mb) ** 0.5  # 平方根因为是二维
                    new_width = int(img.width * scale * 0.9)  # 稍微再小一点以确保在限制内
                    new_height = int(img.height * scale * 0.9)

                    # 调整大小
                    img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

                    # 保存到内存
                    buffer = io.BytesIO()
                    img_format = img.format or 'JPEG'

                    if img_format == 'JPEG' or img_format == 'JPG':
                        img_resized.save(buffer, format='JPEG', quality=85, optimize=True)
                    elif img_format == 'PNG':
                        img_resized.save(buffer, format='PNG', optimize=True)
                    else:
                        # 其他格式转为JPEG
                        if img_resized.mode in ('RGBA', 'LA', 'P'):
                            img_resized = img_resized.convert('RGB')
                        img_resized.save(buffer, format='JPEG', quality=85, optimize=True)

                    image_data = buffer.getvalue()
                    new_size_mb = len(image_data) / (1024 * 1024)
                    logger.info(f"Compressed image from {file_size_mb:.2f}MB to {new_size_mb:.2f}MB")

                except ImportError:
                    logger.error("PIL/Pillow not installed. Cannot compress large images. Install with: pip install Pillow")
                    logger.error(f"Skipping image {image_path} due to size constraint")
                    return None
                except Exception as e:
                    logger.error(f"Failed to compress image {image_path}: {e}")
                    return None

            # Base64编码
            encoded = base64.b64encode(image_data).decode("utf-8")

            # 检查编码后的大小（base64会增加约33%）
            encoded_size_mb = len(encoded) / (1024 * 1024)
            if encoded_size_mb > max_size_mb * 1.5:
                logger.error(f"Encoded image still too large ({encoded_size_mb:.2f}MB). Skipping.")
                return None

            return encoded

        except Exception as e:
            logger.error(f"Failed to encode image {image_path}: {e}")
            return None

    def _get_image_mime_type(self, image_path: str) -> str:
        """Get MIME type from file extension"""
        ext = Path(image_path).suffix.lower()
        mime_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp"
        }
        return mime_types.get(ext, "image/jpeg")

    def call_core_model(
        self,
        messages: List[Dict[str, Any]],
        max_tokens: int = 2000,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """
        Call the core model (thinking model) with retry logic.

        Args:
            messages: Chat messages
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            API response dict with 'content' and 'reasoning_content'
        """
        payload = {
            "model": self.core_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                response = requests.post(
                    self.api_url,
                    headers=self.headers,
                    json=payload,
                    timeout=self.timeout
                )

                if response.status_code == 200:
                    result = response.json()
                    choice = result.get("choices", [{}])[0]
                    message = choice.get("message", {})

                    return {
                        "success": True,
                        "content": message.get("content", ""),
                        "reasoning_content": message.get("reasoning_content", ""),
                        "finish_reason": choice.get("finish_reason", ""),
                        "usage": result.get("usage", {})
                    }
                else:
                    last_error = f"API error: {response.status_code} - {response.text[:200]}"
                    logger.warning(f"Core model attempt {attempt+1} failed: {last_error}")

            except Exception as e:
                last_error = str(e)
                logger.warning(f"Core model attempt {attempt+1} exception: {e}")

            # Wait before retry
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)

        logger.error(f"Core model call failed after {MAX_RETRIES} attempts: {last_error}")
        return {
            "success": False,
            "error": last_error
        }

    def call_target_model(
        self,
        messages: List[Dict[str, Any]],
        images: Optional[List[str]] = None,
        max_tokens: int = 1000,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """
        Call the target model (image model).

        Args:
            messages: Chat messages
            images: List of image paths to include
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            API response dict with 'content'
        """
        original_images = list(images or [])
        request_image_count = 0

        # Build messages with images if provided
        processed_messages = []

        for msg in messages:
            if msg["role"] == "user" and images:
                # Add images to the first user message
                content = []

                # Add images first
                for img_path in images:
                    base64_img = self._encode_image(img_path)
                    if base64_img:
                        mime_type = self._get_image_mime_type(img_path)
                        content.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_img}"
                            }
                        })
                        request_image_count += 1

                # Add text content
                content.append({
                    "type": "text",
                    "text": msg["content"]
                })

                processed_messages.append({
                    "role": "user",
                    "content": content
                })

                # Only add images to first user message
                images = None
            else:
                processed_messages.append(msg)

        payload = {
            "model": self.target_model,
            "messages": processed_messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }

        # 检查payload大小
        payload_size_mb = None
        try:
            payload_size = len(json.dumps(payload))
            payload_size_mb = payload_size / (1024 * 1024)
            if payload_size_mb > 10:
                logger.warning(f"Large payload detected: {payload_size_mb:.2f}MB. This may cause API errors.")
            else:
                logger.debug(f"Payload size: {payload_size_mb:.2f}MB")
        except Exception as e:
            logger.debug(f"Could not calculate payload size: {e}")

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                response = requests.post(
                    self.api_url,
                    headers=self.headers,
                    json=payload,
                    timeout=self.timeout
                )

                if response.status_code == 200:
                    result = response.json()
                    choice = result.get("choices", [{}])[0]
                    message = choice.get("message", {})

                    return {
                        "success": True,
                        "content": message.get("content", ""),
                        "finish_reason": choice.get("finish_reason", ""),
                        "usage": result.get("usage", {}),
                        "status_code": response.status_code,
                        "request_image_count": request_image_count,
                        "response_metadata": {
                            "id": result.get("id"),
                            "model": result.get("model"),
                            "created": result.get("created"),
                        },
                        "receipt_metadata": result.get("attachments") or result.get("multimodal_receipt") or None,
                    }
                else:
                    last_error = f"API error: {response.status_code} - {response.text[:500]}"
                    logger.warning(f"Target model attempt {attempt+1} failed: {last_error}")

                    # 特殊处理503错误
                    if response.status_code == 503:
                        payload_size_display = f"{payload_size_mb:.2f}MB" if isinstance(payload_size_mb, (int, float)) else "unknown"
                        logger.error(
                            f"503 Service Unavailable - 可能原因:\n"
                            f"  1. 请求体过大 (当前payload约 {payload_size_display})\n"
                            f"  2. 服务器过载\n"
                            f"  3. 图像格式不支持\n"
                            f"  4. API暂时不可用\n"
                            f"  响应内容: {response.text[:500]}"
                        )
                    elif response.status_code == 413:
                        payload_size_display = f"{payload_size_mb:.2f}MB" if isinstance(payload_size_mb, (int, float)) else "unknown"
                        logger.error(f"413 Payload Too Large - 请求体太大: {payload_size_display}")
                    elif response.status_code == 400:
                        logger.error(f"400 Bad Request - 请求格式错误: {response.text[:500]}")

            except Exception as e:
                last_error = str(e)
                logger.warning(f"Target model attempt {attempt+1} exception: {e}")

            # Wait before retry
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)

        logger.error(f"Target model call failed after {MAX_RETRIES} attempts: {last_error}")
        return {
            "success": False,
            "error": last_error,
            "status_code": None,
            "request_image_count": request_image_count,
            "response_metadata": {
                "attempted_image_count": len(original_images),
            },
            "receipt_metadata": None,
        }

    def test_connection(self) -> Dict[str, bool]:
        """Test connection to both models"""
        results = {}

        # Test core model
        core_result = self.call_core_model([
            {"role": "user", "content": "Say 'OK'"}
        ], max_tokens=10)
        results["core_model"] = core_result.get("success", False)

        # Test target model
        target_result = self.call_target_model([
            {"role": "user", "content": "Say 'OK'"}
        ], max_tokens=10)
        results["target_model"] = target_result.get("success", False)

        return results

    def call_weak_model(
        self,
        messages: List[Dict[str, Any]],
        max_tokens: int = 500,
        temperature: float = 0.9
    ) -> Dict[str, Any]:
        """
        Call the weak/cheap model for filler content generation.
        Used for pseudo multi-turn to save costs on verbose content.

        Args:
            messages: Chat messages
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (higher for more varied filler)

        Returns:
            API response dict with 'content'
        """
        payload = {
            "model": self.weak_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                response = requests.post(
                    self.api_url,
                    headers=self.headers,
                    json=payload,
                    timeout=self.timeout
                )

                if response.status_code == 200:
                    result = response.json()
                    choice = result.get("choices", [{}])[0]
                    message = choice.get("message", {})

                    return {
                        "success": True,
                        "content": message.get("content", ""),
                        "finish_reason": choice.get("finish_reason", ""),
                        "usage": result.get("usage", {})
                    }
                else:
                    last_error = f"API error: {response.status_code} - {response.text[:200]}"
                    logger.warning(f"Weak model attempt {attempt+1} failed: {last_error}")

            except Exception as e:
                last_error = str(e)
                logger.warning(f"Weak model attempt {attempt+1} exception: {e}")

            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)

        logger.error(f"Weak model call failed after {MAX_RETRIES} attempts: {last_error}")
        return {
            "success": False,
            "error": last_error
        }


# Test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    client = LLMClient()
    print("Testing LLM Client...")

    # Test connection
    results = client.test_connection()
    print(f"Core model: {'OK' if results['core_model'] else 'FAILED'}")
    print(f"Target model: {'OK' if results['target_model'] else 'FAILED'}")

    # Test core model with longer response
    print("\n--- Core Model Test ---")
    response = client.call_core_model([
        {"role": "user", "content": "What is 2+2? Think step by step."}
    ])
    if response["success"]:
        print(f"Content: {response['content']}")
        print(f"Reasoning: {response['reasoning_content'][:200]}...")