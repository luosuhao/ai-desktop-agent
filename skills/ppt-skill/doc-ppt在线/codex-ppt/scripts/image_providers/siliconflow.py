from __future__ import annotations

import asyncio
import base64
import json
import mimetypes
from pathlib import Path
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse
from urllib.request import Request, urlopen as default_urlopen

from .base import ImageProvider


UrlOpen = Callable[..., Any]
DEFAULT_BASE_URL = "https://api.siliconflow.cn/v1"
GENERATIONS_PATH = "/images/generations"
USER_AGENT = "codex-ppt-skill/0.1 siliconflow"
DEFAULT_GENERATE_MODEL = "Qwen/Qwen-Image"
DEFAULT_EDIT_MODEL = "Qwen/Qwen-Image-Edit-2509"
SILICONFLOW_MAX_OUTPUTS = 4

RECOMMENDED_SIZES: Tuple[Tuple[int, int], ...] = (
    (1328, 1328),
    (1664, 928),
    (928, 1664),
    (1472, 1140),
    (1140, 1472),
    (1584, 1056),
    (1056, 1584),
)


class SiliconFlowImageProvider(ImageProvider):
    """SiliconFlow adapter for Qwen Image generation and editing."""

    def __init__(
        self,
        *,
        api_key: Optional[str],
        base_url: Optional[str],
        urlopen: UrlOpen = default_urlopen,
    ) -> None:
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for siliconflow image calls.")
        self.api_key = api_key
        self.endpoint = _generations_endpoint(base_url)
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
            raise ValueError("SiliconFlow Qwen Image editing does not support --mask in this adapter.")
        if len(image_paths) > 3:
            raise ValueError("SiliconFlow Qwen Image editing supports at most 3 input images.")
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
        request_payload = _siliconflow_payload(payload, image_paths=image_paths)
        response = self._request_json(request_payload)
        image_values = _extract_image_outputs(response)
        if not image_values:
            raise RuntimeError(f"SiliconFlow response did not include image outputs: {response}")
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
            raise RuntimeError(f"Unexpected SiliconFlow response: {parsed}")
        if parsed.get("code") or parsed.get("message") and "images" not in parsed:
            raise RuntimeError(f"SiliconFlow API error: {parsed}")
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


def _generations_endpoint(base_url: Optional[str]) -> str:
    raw = (base_url or DEFAULT_BASE_URL).strip().rstrip("/")
    if raw.endswith(GENERATIONS_PATH):
        return raw
    return f"{raw}{GENERATIONS_PATH}"


def preview_endpoint(base_url: Optional[str]) -> str:
    return _generations_endpoint(base_url)


def normalize_siliconflow_size(size: Optional[str]) -> str:
    if not size or str(size).lower() == "auto":
        return "1664x928"
    raw = str(size).strip().lower().replace("*", "x")
    parsed = _parse_size(raw)
    if parsed is None:
        raise ValueError("SiliconFlow image_size must be auto or WIDTHxHEIGHT/WIDTH*HEIGHT.")
    if parsed in RECOMMENDED_SIZES:
        return f"{parsed[0]}x{parsed[1]}"
    width, height = parsed
    target_ratio = width / height
    best = min(RECOMMENDED_SIZES, key=lambda item: abs((item[0] / item[1]) - target_ratio))
    return f"{best[0]}x{best[1]}"


def siliconflow_model_for_operation(model: str, operation: str) -> str:
    if operation == "edit" and model.lower() == DEFAULT_GENERATE_MODEL.lower():
        return DEFAULT_EDIT_MODEL
    if operation == "generate" and "image-edit" in model.lower():
        return DEFAULT_GENERATE_MODEL
    return model


def siliconflow_effective_size(payload: Dict[str, Any], operation: str) -> Optional[str]:
    model = siliconflow_model_for_operation(str(payload.get("model", DEFAULT_GENERATE_MODEL)), operation)
    if "image-edit" in model.lower():
        return None
    return normalize_siliconflow_size(payload.get("size"))


def _siliconflow_payload(payload: Dict[str, Any], *, image_paths: List[Path]) -> Dict[str, Any]:
    operation = "edit" if image_paths else "generate"
    model = siliconflow_model_for_operation(str(payload.get("model", DEFAULT_GENERATE_MODEL)), operation)
    request_payload: Dict[str, Any] = {
        "model": model,
        "prompt": str(payload["prompt"]),
    }

    n = int(payload.get("n", 1))
    if n < 1 or n > SILICONFLOW_MAX_OUTPUTS:
        raise ValueError(f"SiliconFlow batch_size must be between 1 and {SILICONFLOW_MAX_OUTPUTS}.")
    request_payload["batch_size"] = n

    if "image-edit" not in model.lower():
        request_payload["image_size"] = normalize_siliconflow_size(payload.get("size"))
    if payload.get("negative_prompt"):
        request_payload["negative_prompt"] = payload["negative_prompt"]
    if payload.get("num_inference_steps") is not None:
        request_payload["num_inference_steps"] = int(payload["num_inference_steps"])
    if payload.get("cfg") is not None:
        request_payload["cfg"] = float(payload["cfg"])
    if payload.get("seed") is not None:
        request_payload["seed"] = int(payload["seed"])

    for idx, path in enumerate(image_paths, start=1):
        key = "image" if idx == 1 else f"image{idx}"
        request_payload[key] = _image_to_data_url(path)

    return request_payload


def _extract_image_outputs(response: Dict[str, Any]) -> List[str]:
    outputs: List[str] = []
    images = response.get("images")
    if isinstance(images, list):
        for item in images:
            if isinstance(item, dict):
                if isinstance(item.get("url"), str):
                    outputs.append(item["url"])
                elif isinstance(item.get("b64_json"), str):
                    outputs.append(item["b64_json"])
            elif isinstance(item, str):
                outputs.append(item)
    return outputs


def _parse_size(size: str) -> Optional[Tuple[int, int]]:
    parts = size.split("x")
    if len(parts) != 2:
        return None
    try:
        width, height = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    if width < 1 or height < 1:
        return None
    return width, height


def _image_to_data_url(path: Path) -> str:
    mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"
