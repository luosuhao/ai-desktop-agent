"""模型单图冒烟测试（用 tablenet-venv 运行）。

用法：
    tablenet-venv/Scripts/python.exe backend/tablenet/smoke_test.py <表格图片路径>

验收：输出包含 <table>，通常包含 <html> 与 </html>；不为空串。
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from inference import load_model, predict_one, PROMPT, DEFAULT_MAX_NEW_TOKENS  # noqa: E402


def _find_model_dir():
    env_dir = os.environ.get("TABLENET_MODEL_DIR", "").strip()
    if env_dir:
        return env_dir
    start = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(start)
    for _ in range(4):
        marker = os.path.join(root, "Qwen2-VL-2B-TableNet-PubTabNet-smallx2-v1",
                              "Qwen2-VL-2B-TableNet-PubTabNet-smallx2-v1")
        if os.path.isfile(os.path.join(marker, "config.json")):
            return marker
        parent = os.path.dirname(root)
        if parent == root:
            break
        root = parent
    raise FileNotFoundError("未找到模型目录，请设置 TABLENET_MODEL_DIR")


def main():
    image_path = sys.argv[1] if len(sys.argv) > 1 else ""
    if not image_path or not os.path.isfile(image_path):
        print("用法: python smoke_test.py <表格图片路径>")
        sys.exit(2)

    model_dir = _find_model_dir()
    print(f"[smoke] loading model from {model_dir}", flush=True)
    t0 = time.time()
    model, processor = load_model(model_dir)
    print(f"[smoke] model loaded in {time.time() - t0:.1f}s", flush=True)

    t1 = time.time()
    html = predict_one(model, processor, image_path=image_path,
                       max_new_tokens=DEFAULT_MAX_NEW_TOKENS, prompt=PROMPT)
    dt = time.time() - t1
    print(f"[smoke] inference took {dt:.1f}s", flush=True)
    print("[smoke] prompt:", PROMPT)
    print("[smoke] output:")
    print(html)
    has_table = "<table" in html.lower()
    print(f"\n[smoke] contains <table>: {has_table}")
    print(f"[smoke] {'PASS' if (has_table and html.strip()) else 'FAIL'}")


if __name__ == "__main__":
    main()
