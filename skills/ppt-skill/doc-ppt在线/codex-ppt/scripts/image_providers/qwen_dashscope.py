from __future__ import annotations

import asyncio
import base64
import json
import mimetypes
from pathlib import Path
import sys
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse
from urllib.request import Request, urlopen as default_urlopen

from .base import ImageProvider


UrlOpen = Callable[..., Any]
DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/api/v1"
GENERATION_PATH = "/services/aigc/multimodal-generation/generation"
USER_AGENT = "codex-ppt-skill/0.1 qwen-dashscope"
QWEN_MAX_OUTPUT_EDGE = 2048
QWEN_DEFAULT_SIZE = "2048*1152"


class QwenDashScopeImageProvider(ImageProvider):
    """DashScope/Model Studio adapter for Qwen Image generation and editing."""

    def __init__(
        self,
        *,
        api_key: Optional[str],
        base_url: Optional[str],
        urlopen: UrlOpen = default_urlopen,
    ) -> None:
        if not api_key:
            raise RuntimeError("DASHSCOPE_API_KEY is required for qwen-dashscope image calls.")
        self.api_key = api_key
        self.endpoint = _generation_endpoint(base_url)
        self._urlopen = urlopen

    def generate(self, payload: Dict[str, Any]) -> List[str]:
        return self._call(payload, image_paths=[])

    def edit(
        self,
        payload: Dict[str, Any],
        image_paths: List[Path],
        mask_path: Optional[Path],
    ) -> List[str]:
        if mask_path is not None:
            raise ValueError("Qwen Image HTTP editing does not support --mask in this adapter.")
        if len(image_paths) > 3:
            raise ValueError("Qwen Image editing supports at most 3 input images.")
        return self._call(payload, image_paths=image_paths)

    async def generate_batch(
        self,
        payload: Dict[str, Any],
        *,
        attempts: int,
        job_label: str,
    ) -> List[str]:
        last_exc: Optional[Exception] = None
        for attempt in range(1, attempts + 1):
            try:
                return await asyncio.to_thread(self.generate, payload)
            except Exception as exc:
                last_exc = exc
                if attempt == attempts:
                    raise
                sleep_s = min(60.0, 2.0**attempt)
                print(
                    f"{job_label} attempt {attempt}/{attempts} failed ({exc.__class__.__name__}); retrying in {sleep_s:.1f}s",
                    file=sys.stderr,
                )
                await asyncio.sleep(sleep_s)
        raise last_exc or RuntimeError("unknown error")

    def _call(self, payload: Dict[str, Any], *, image_paths: List[Path]) -> List[str]:
        request_payload = _dashscope_payload(payload, image_paths=image_paths)
        response = self._request_json(request_payload)
        image_values = _extract_image_outputs(response)
        if not image_values:
            raise RuntimeError(f"Qwen Image response did not include image outputs: {response}")
        return [self._output_to_b64(value) for value in image_values]

    def _request_json(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        request = Request(
            self.endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
            },
            method="POST",
        )
        with self._urlopen(request, timeout=600) as response:
            parsed = json.loads(response.read().decode("utf-8"))
        if not isinstance(parsed, dict):
            raise RuntimeError(f"Unexpected Qwen Image response: {parsed}")
        if parsed.get("code") or parsed.get("message") and "output" not in parsed:
            raise RuntimeError(f"Qwen Image API error: {parsed}")
        return parsed

    def _output_to_b64(self, value: str) -> str:
        if value.startswith("data:") and "," in value:
            return value.split(",", 1)[1]
        parsed = urlparse(value)
        if parsed.scheme in {"http", "https"}:
            request = Request(value, headers={"User-Agent": USER_AGENT}, method="GET")
            with self._urlopen(request, timeout=120) as response:
                return base64.b64encode(response.read()).decode("ascii")
        return value


def _generation_endpoint(base_url: Optional[str]) -> str:
    raw = (base_url or DEFAULT_BASE_URL).strip().rstrip("/")
    if raw.endswith(GENERATION_PATH):
        return raw
    return f"{raw}{GENERATION_PATH}"


def preview_endpoint(base_url: Optional[str]) -> str:
    return _generation_endpoint(base_url)


def normalize_qwen_size(size: Optional[str]) -> str:
    if not size or str(size).lower() == "auto":
        return QWEN_DEFAULT_SIZE
    normalized = str(size).strip().lower().replace("x", "*")
    parts = normalized.split("*")
    if len(parts) != 2:
        raise ValueError("Qwen Image size must be auto or WIDTHxHEIGHT/WIDTH*HEIGHT.")
    width, height = int(parts[0]), int(parts[1])
    max_edge = max(width, height)
    if max_edge > QWEN_MAX_OUTPUT_EDGE:
        scale = QWEN_MAX_OUTPUT_EDGE / max_edge
        width = max(1, int(round(width * scale)))
        height = max(1, int(round(height * scale)))
    return f"{width}*{height}"


def _dashscope_payload(payload: Dict[str, Any], *, image_paths: List[Path]) -> Dict[str, Any]:
    content: List[Dict[str, str]] = []
    for path in image_paths:
        content.append({"image": _image_to_data_url(path)})
    content.append({"text": str(payload["prompt"])})

    params: Dict[str, Any] = {
        "n": int(payload.get("n", 1)),
        "size": normalize_qwen_size(payload.get("size")),
        "watermark": False,
    }
    if payload.get("negative_prompt"):
        params["negative_prompt"] = payload["negative_prompt"]
    if payload.get("prompt_extend") is not None:
        params["prompt_extend"] = bool(payload["prompt_extend"])

    return {
        "model": str(payload.get("model", "qwen-image-2.0-pro")),
        "input": {"messages": [{"role": "user", "content": content}]},
        "parameters": params,
    }


def _extract_image_outputs(response: Dict[str, Any]) -> List[str]:
    outputs: List[str] = []
    choices = response.get("output", {}).get("choices")
    if isinstance(choices, list):
        for choice in choices:
            message = choice.get("message") if isinstance(choice, dict) else None
            content = message.get("content") if isinstance(message, dict) else None
            if not isinstance(content, list):
                continue
            for item in content:
                if isinstance(item, dict) and isinstance(item.get("image"), str):
                    outputs.append(item["image"])
    results = response.get("output", {}).get("results")
    if isinstance(results, list):
        for item in results:
            if isinstance(item, dict) and isinstance(item.get("url"), str):
                outputs.append(item["url"])
            elif isinstance(item, str):
                outputs.append(item)
    return outputs


def _image_to_data_url(path: Path) -> str:
    mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"
