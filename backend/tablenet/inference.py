"""Qwen2-VL-2B-TableNet-PubTabNet-smallx2-v1 推理核心。

严格遵循部署手册已验证的推理参数（不得修改，否则结果不能与现有评测比较）：
- 图片尺寸 280 x 280（对应像素数约束 280*280 = 78400）
- max_new_tokens = 2048
- 贪心解码 do_sample = False
- 不使用 OCR
- 固定提示词：你是一个HTML助手，目标是读取用户输入的表格图片，转换成HTML序列

模型本身只读，不写入、不修改模型目录内任何文件。
"""

import os
import re
import torch
from typing import Optional

# 手册固定提示词，输出格式为 <html><body><table>...</table></body></html>
PROMPT = "你是一个HTML助手，目标是读取用户输入的表格图片，转换成HTML序列"

# 图片尺寸 280 x 280 → 像素数上限（Qwen2VL SmartResize 的 min/max_pixels）
TARGET_PIXELS = 280 * 280
DEFAULT_MAX_NEW_TOKENS = 2048


def load_model(
    model_dir: str,
    device: Optional[str] = None,
    max_pixels: int = TARGET_PIXELS,
    min_pixels: int = TARGET_PIXELS,
):
    """加载合并后的完整模型（无需 adapter，不使用 OCR）。

    返回 (model, processor)。显存不足时自动回退到 device_map="auto"（加速库会
    把放不下的层卸载到 CPU），不影响模型文件。
    """
    from transformers import Qwen2VLForConditionalGeneration, AutoProcessor

    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    kwargs = {
        "torch_dtype": torch.bfloat16 if torch.cuda.is_available() else torch.float32,
        "device_map": "auto" if torch.cuda.is_available() else "cpu",
        "trust_remote_code": False,
    }

    model = Qwen2VLForConditionalGeneration.from_pretrained(model_dir, **kwargs)
    processor = AutoProcessor.from_pretrained(
        model_dir,
        min_pixels=min_pixels,
        max_pixels=max_pixels,
        trust_remote_code=False,
    )
    return model, processor


def _sanitize_html(raw: str) -> str:
    """清洗模型生成的 HTML，去掉脚本、事件属性和外部资源，避免前端 XSS。"""
    if not raw:
        return raw
    # 去掉脚本/iframe/object/embed/style/link/meta 块
    for tag in ("script", "iframe", "object", "embed", "style", "link", "meta", "form", "button"):
        raw = re.sub(rf"<\s*{tag}[^>]*>.*?</\s*{tag}\s*>", "", raw, flags=re.DOTALL | re.IGNORECASE)
        raw = re.sub(rf"<\s*{tag}[^>]*/?\s*>", "", raw, flags=re.IGNORECASE)
    # 去掉所有事件属性和危险的协议/引用
    raw = re.sub(r"\son\w+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s(href|src)\s*=\s*[\"']?\s*(javascript:|data:text/html)", "", raw, flags=re.IGNORECASE)
    return raw


def predict_one(
    model,
    processor,
    image_path: str,
    prompt: str = PROMPT,
    max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS,
) -> str:
    """把表格图片转成 HTML 序列（完整 <html>...</html>），返回清洗后的文本。"""
    from qwen_vl_utils import process_vision_info

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image_path},
                {"type": "text", "text": prompt},
            ],
        }
    ]

    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    image_inputs, video_inputs = process_vision_info(messages)

    inputs = processor(
        text=[text],
        images=image_inputs,
        videos=video_inputs,
        padding=True,
        return_tensors="pt",
    ).to(model.device)

    pad_token_id = processor.tokenizer.pad_token_id or model.config.pad_token_id or 151643

    with torch.no_grad():
        generated_ids = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            use_cache=True,
            pad_token_id=pad_token_id,
        )

    generated_ids_trimmed = [
        out[len(inp):] for inp, out in zip(inputs.input_ids, generated_ids)
    ]
    output_text = processor.batch_decode(
        generated_ids_trimmed,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False,
    )
    return _sanitize_html((output_text[0] if output_text else "").strip())


def extract_table_html(html: str) -> str:
    """从完整 HTML 中取出 <table> 片段（用于拼装汇总页面）。"""
    m = re.search(r"<table[^>]*>.*?</table>", html, flags=re.DOTALL | re.IGNORECASE)
    return m.group(0) if m else html
