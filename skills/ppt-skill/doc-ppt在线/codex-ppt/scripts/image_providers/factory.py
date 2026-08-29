from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse

from .atlascloud import AtlasCloudImageProvider
from .base import ImageProvider
from .openai_compatible import OpenAICompatibleImageProvider
from .qwen_dashscope import QwenDashScopeImageProvider
from .siliconflow import SiliconFlowImageProvider


def create_image_provider(
    *,
    api_key: Optional[str],
    base_url: Optional[str],
    model: Optional[str] = None,
    provider: Optional[str] = None,
    dashscope_api_key: Optional[str] = None,
    dashscope_base_url: Optional[str] = None,
) -> ImageProvider:
    if _is_siliconflow_provider(provider, base_url):
        return SiliconFlowImageProvider(api_key=api_key, base_url=base_url)
    if _is_qwen_dashscope_provider(provider, model):
        return QwenDashScopeImageProvider(
            api_key=dashscope_api_key,
            base_url=dashscope_base_url,
        )
    if _is_atlascloud_base_url(base_url):
        return AtlasCloudImageProvider(api_key=api_key, base_url=base_url)
    return OpenAICompatibleImageProvider(api_key=api_key, base_url=base_url)


def _is_atlascloud_base_url(base_url: Optional[str]) -> bool:
    if not base_url:
        return False
    hostname = urlparse(base_url).hostname or ""
    return "atlascloud.ai" in hostname.lower()


def _is_qwen_dashscope_provider(provider: Optional[str], model: Optional[str]) -> bool:
    if provider and provider.strip().lower() in {"siliconflow", "silicon-flow"}:
        return False
    if provider and provider.strip().lower() in {"qwen", "qwen-image", "qwen-dashscope", "dashscope"}:
        return True
    return "qwen-image" in str(model or "").lower()


def _is_siliconflow_provider(provider: Optional[str], base_url: Optional[str]) -> bool:
    if provider and provider.strip().lower() in {"siliconflow", "silicon-flow"}:
        return True
    if not base_url:
        return False
    hostname = urlparse(base_url).hostname or ""
    return "siliconflow" in hostname.lower()
