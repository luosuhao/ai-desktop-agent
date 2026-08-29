"""Qwen2-VL-2B-TableNet 模型服务进程。

用 tablenet-venv 的 python 独立启动，加载一次模型常驻内存，通过 HTTP 提供服务：

    GET  /health   健康检查
    POST /predict  {"image_path": "...", "max_new_tokens": 2048} -> {"html": "..."}

启动示例（由 engine.py 自动拉起，也可手动启动）：
    tablenet-venv/Scripts/python.exe -m uvicorn tablenet.server:app \
        --host 127.0.0.1 --port 18000
"""

import os
import argparse

from fastapi import FastAPI
from pydantic import BaseModel
try:
    from .inference import load_model, predict_one, PROMPT, DEFAULT_MAX_NEW_TOKENS
except ImportError:  # python server.py 直接运行时
    from inference import load_model, predict_one, PROMPT, DEFAULT_MAX_NEW_TOKENS

app = FastAPI(title="Qwen2-VL-TableNet", version="1.0.0")

_MODEL = None  # (model, processor)


class PredictRequest(BaseModel):
    image_path: str
    max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS


def _get_model_dir() -> str:
    """模型目录：优先环境变量，否则从本文件位置一直向上找项目根下的模型目录。"""
    env_dir = os.environ.get("TABLENET_MODEL_DIR", "").strip()
    if env_dir and os.path.isfile(os.path.join(env_dir, "config.json")):
        return env_dir

    start = os.path.dirname(os.path.abspath(__file__))
    root = start
    while True:
        marker = os.path.join(root, "Qwen2-VL-2B-TableNet-PubTabNet-smallx2-v1",
                              "Qwen2-VL-2B-TableNet-PubTabNet-smallx2-v1")
        if os.path.isfile(os.path.join(marker, "config.json")):
            return marker
        parent = os.path.dirname(root)
        if parent == root:
            break
        root = parent
    raise FileNotFoundError(
        "未找到模型目录，请设置环境变量 TABLENET_MODEL_DIR 指向 "
        "Qwen2-VL-2B-TableNet-PubTabNet-smallx2-v1/Qwen2-VL-2B-TableNet-PubTabNet-smallx2-v1"
    )


@app.on_event("startup")
def _startup():
    global _MODEL
    model_dir = _get_model_dir()
    _MODEL = load_model(model_dir)
    print(f"[tablenet] model loaded from {model_dir}", flush=True)


@app.get("/health")
def health():
    return {
        "status": "ok" if _MODEL else "loading",
        "model_loaded": _MODEL is not None,
        "base_model": _get_model_dir(),
        "adapter": "",
    }


@app.post("/predict")
def predict(req: PredictRequest):
    if _MODEL is None:
        return {"html": "", "error": "model not loaded"}
    model, processor = _MODEL
    if not os.path.isfile(req.image_path):
        return {"html": "", "error": f"image not found: {req.image_path}"}
    html = predict_one(
        model, processor,
        image_path=req.image_path,
        max_new_tokens=req.max_new_tokens,
    )
    return {"html": html, "error": ""}


if __name__ == "__main__":
    import uvicorn
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("TABLENET_PORT", "18000")))
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)
