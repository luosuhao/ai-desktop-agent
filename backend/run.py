"""Run script for AI Desktop System backend"""
import os
import socket
import subprocess
import time

import uvicorn
from config import settings, _find_project_root

LOCAL_OLLAMA_PORT = 11434


def _ensure_portable_ollama():
    """If nothing is listening on the local Ollama port and a bundled portable
    Ollama exists (project root /ollama/bin/ollama.exe), start it so the
    '本地 Ollama' provider works offline on any machine that copied the project."""
    try:
        host, port = "127.0.0.1", LOCAL_OLLAMA_PORT

        # Already serving (system Ollama or a previously-started portable)? skip.
        try:
            with socket.create_connection((host, port), timeout=0.5):
                print(f"[ollama] 本机 {host}:{port} 已有 Ollama 服务，跳过便携版启动。")
                return
        except OSError:
            pass

        # Locate the portable bundle: <project_root>/ollama/bin/ollama.exe
        project_root = _find_project_root(os.getcwd()) or "."
        ollama_dir = os.path.join(project_root, "ollama")
        exe = os.path.join(ollama_dir, "bin", "ollama.exe")
        if not os.path.exists(exe):
            print(f"[ollama] 未找到便携 Ollama，跳过自动启动: {exe}")
            return

        env = dict(os.environ)
        env["OLLAMA_MODELS"] = os.path.join(ollama_dir, "models")
        env["OLLAMA_HOST"] = f"{host}:{port}"

        creationflags = 0
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            creationflags |= subprocess.CREATE_NO_WINDOW
        if hasattr(subprocess, "DETACHED_PROCESS"):
            creationflags |= subprocess.DETACHED_PROCESS

        subprocess.Popen(
            [exe, "serve"],
            cwd=ollama_dir,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=creationflags,
            close_fds=True,
        )
        print(f"[ollama] 已拉起便携 Ollama（离线，模型目录 {env['OLLAMA_MODELS']}）")

        # Wait briefly for it to bind the port
        for _ in range(20):
            try:
                with socket.create_connection((host, port), timeout=0.3):
                    print(f"[ollama] 便携 Ollama 已就绪: {exe}")
                    return
            except OSError:
                time.sleep(0.3)
        print("[ollama] 便携 Ollama 启动后仍未监听 11434，请检查 start-ollama.bat 手动启动。")
    except Exception as e:
        print(f"[ollama] 自动启动便携 Ollama 失败: {e}")


if __name__ == "__main__":
    print(f"Starting AI Desktop System backend...")
    print(f"API: http://{settings.api_host}:{settings.api_port}")
    print(f"Docs: http://{settings.api_host}:{settings.api_port}/docs")
    _ensure_portable_ollama()
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False
    )
