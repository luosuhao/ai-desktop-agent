"""模型服务客户端（主后端使用）。

首次调用时自动用 tablenet-venv 的 python 拉起 tablenet.server 服务进程，
之后通过本地 HTTP 调用。服务常驻，避免每次请求重新加载模型。
主后端不 import torch/transformers，保持轻量。
"""

import os
import sys
import time
import shutil
import subprocess
from typing import Optional

import httpx

try:
    from config import settings
    try:
        from config import _project_root as _CONFIG_PROJECT_ROOT
    except ImportError:
        _CONFIG_PROJECT_ROOT = None
except ImportError:
    settings = None
    _CONFIG_PROJECT_ROOT = None

DEFAULT_PORT = 18000


def _find_root_from(start: str) -> str:
    d = os.path.abspath(start)
    while True:
        if os.path.isfile(os.path.join(d, "AGENTS.md")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def _project_root_candidates() -> list:
    """按优先级返回可能的项目根（含 AGENTS.md 的目录），去重保序。

    覆盖：源码运行（config 探测 / CWD 向上）、PyInstaller 打包（resources 向上
    走到项目根，此时模型与 venv 在项目根旁边）。
    """
    cands = []
    for c in (_CONFIG_PROJECT_ROOT, _find_root_from(os.getcwd())):
        if c:
            cands.append(c)
    # 打包后：从 backend.exe 位置向上找 AGENTS.md（exe 安装在本项目目录树内时可用）
    if getattr(sys, "frozen", False):
        r = _find_root_from(os.path.dirname(os.path.abspath(sys.executable)))
        if r:
            cands.append(r)
    seen, out = set(), []
    for c in cands:
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def model_dir() -> str:
    env_dir = os.environ.get("TABLENET_MODEL_DIR", "").strip()
    if env_dir:
        return env_dir
    for root in _project_root_candidates():
        m = os.path.join(root, "Qwen2-VL-2B-TableNet-PubTabNet-smallx2-v1",
                         "Qwen2-VL-2B-TableNet-PubTabNet-smallx2-v1")
        if os.path.isfile(os.path.join(m, "config.json")):
            return m
    if _CONFIG_PROJECT_ROOT:
        return os.path.join(_CONFIG_PROJECT_ROOT, "Qwen2-VL-2B-TableNet-PubTabNet-smallx2-v1",
                            "Qwen2-VL-2B-TableNet-PubTabNet-smallx2-v1")
    return ""


def venv_python() -> str:
    env_dir = os.environ.get("TABLENET_VENV_DIR", "").strip()
    if env_dir:
        py = os.path.join(env_dir, "Scripts", "python.exe")
        if os.path.isfile(py):
            return py
        py = os.path.join(env_dir, "bin", "python")
        if os.path.isfile(py):
            return py
    for root in _project_root_candidates():
        py = os.path.join(root, "tablenet-venv", "Scripts", "python.exe")
        if os.path.isfile(py):
            return py
    return shutil.which("python") or sys.executable


def _backend_source_dir() -> str:
    """返回含 tablenet/server.py 的后端源码目录（模型服务进程的 cwd）。"""
    # 1) 源码运行：本文件 backend/tablenet/engine.py -> backend/
    src = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if os.path.isfile(os.path.join(src, "tablenet", "server.py")):
        return src
    # 2) 打包运行：backend.exe 位于 resources/backend/dist/backend.exe
    if getattr(sys, "frozen", False):
        cand = os.path.dirname(os.path.dirname(os.path.abspath(sys.executable)))
        if os.path.isfile(os.path.join(cand, "tablenet", "server.py")):
            return cand
    # 3) 项目根下 backend/
    for root in _project_root_candidates():
        b = os.path.join(root, "backend")
        if os.path.isfile(os.path.join(b, "tablenet", "server.py")):
            return b
    return src


def port() -> int:
    return int(os.environ.get("TABLENET_PORT", str(DEFAULT_PORT)))


def _base_url() -> str:
    return f"http://127.0.0.1:{port()}"


class TableNetEngine:
    """懒启动 + 常驻本地模型服务。"""

    def __init__(self):
        self._proc: Optional[subprocess.Popen] = None
        self._client = httpx.Client(timeout=600.0)  # 首次加载模型可能很久

    # ---- 进程管理 ----

    def _service_alive(self) -> bool:
        try:
            r = self._client.get(f"{_base_url()}/health", timeout=3.0)
            return r.status_code == 200 and r.json().get("model_loaded") is True
        except Exception:
            return False

    def _spawn(self):
        py = venv_python()
        backend_dir = _backend_source_dir()
        cmd = [
            py, "-m", "uvicorn", "tablenet.server:app",
            "--host", "127.0.0.1", "--port", str(port()),
        ]
        env = dict(os.environ)
        env.setdefault("TRANSFORMERS_OFFLINE", "1")
        env.setdefault("HF_HUB_OFFLINE", "1")
        if not os.environ.get("TABLENET_MODEL_DIR"):
            mdir = model_dir()
            if mdir:
                env["TABLENET_MODEL_DIR"] = mdir
        self._proc = subprocess.Popen(
            cmd,
            cwd=backend_dir,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    def _ensure_service(self) -> bool:
        if self._service_alive():
            return True
        if self._proc is None or self._proc.poll() is not None:
            self._spawn()
        # 等待健康检查（模型加载可能 30-120s）
        deadline = time.time() + 300
        while time.time() < deadline:
            try:
                r = self._client.get(f"{_base_url()}/health", timeout=5.0)
                if r.status_code == 200 and r.json().get("model_loaded"):
                    return True
                if r.status_code == 200 and r.json().get("status") == "ok":
                    return True
            except Exception:
                pass
            if self._proc is not None and self._proc.poll() is not None:
                return False
            time.sleep(2)
        return False

    # ---- 对外接口 ----

    def status(self) -> dict:
        alive = self._service_alive()
        return {
            "available": alive,
            "model_dir": model_dir(),
            "port": port(),
            "model_loaded": alive,
        }

    def predict(self, image_path: str, max_new_tokens: int = 2048) -> dict:
        if not self._ensure_service():
            return {"html": "", "error": "模型服务不可用，请检查 tablenet-venv 与模型目录"}
        try:
            r = self._client.post(
                f"{_base_url()}/predict",
                json={"image_path": os.path.abspath(image_path), "max_new_tokens": max_new_tokens},
            )
            r.raise_for_status()
            data = r.json()
            if data.get("error"):
                return {"html": "", "error": data["error"]}
            return data
        except Exception as e:
            return {"html": "", "error": f"模型推理请求失败: {e}"}

    def shutdown(self):
        if self._proc is not None and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except Exception:
                pass
        self._client.close()


# 全局单例
engine = TableNetEngine()
