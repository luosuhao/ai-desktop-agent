# -*- coding: utf-8 -*-
"""把本机的 Ollama 程序 + 模型打包成"便携版"到项目 ollama/ 目录，
别人复制整个项目后即可通过 start-ollama.bat 离线启动，无需安装 Ollama。

用法：
    python 打包便携Ollama.py

说明：
    - 默认跳过 cuda_v12（NVIDIA GPU 库，约 1.1GB），纯 CPU 推理、最兼容；
      如需 GPU 加速，把本脚本里的 skip_dirs 改成空集合再重跑即可。
    - 幂等：已存在的文件会跳过，可重复运行。
"""
import os
import shutil

PROJECT = os.path.dirname(os.path.abspath(__file__))
OLLAMA_PROG = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama")
OLLAMA_MODELS_SRC = os.path.join(os.path.expanduser("~"), ".ollama", "models")
DEST = os.path.join(PROJECT, "ollama")
SKIP_DIRS = {"cuda_v12"}  # 跳过 NVIDIA GPU 库（纯 CPU 最兼容）


def _copy_any(src, dst):
    if os.path.exists(dst):
        return False
    if os.path.isdir(src):
        shutil.copytree(src, dst)
    else:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
    return True


def main():
    ollama_exe = os.path.join(OLLAMA_PROG, "ollama.exe")
    lib_src = os.path.join(OLLAMA_PROG, "lib", "ollama")
    if not os.path.exists(ollama_exe):
        print("未找到 ollama.exe：", ollama_exe)
        return 1
    if not os.path.exists(lib_src):
        print("未找到 lib/ollama（含 llama-server.exe 推理引擎）：", lib_src)
        return 1
    if not os.path.exists(OLLAMA_MODELS_SRC):
        print("未找到模型目录：", OLLAMA_MODELS_SRC)
        return 1

    bin_dir = os.path.join(DEST, "bin")
    models_dir = os.path.join(DEST, "models")
    os.makedirs(bin_dir, exist_ok=True)
    os.makedirs(models_dir, exist_ok=True)

    # 1) ollama.exe
    if _copy_any(ollama_exe, os.path.join(bin_dir, "ollama.exe")):
        print("已拷贝 ollama.exe")

    # 2) lib/ollama（推理引擎 + CPU/GPU DLL，跳过 GPU 库）
    dst_lib = os.path.join(bin_dir, "lib", "ollama")
    os.makedirs(dst_lib, exist_ok=True)
    for item in os.listdir(lib_src):
        if item in SKIP_DIRS:
            print("跳过 GPU 库：", item)
            continue
        if _copy_any(os.path.join(lib_src, item), os.path.join(dst_lib, item)):
            print("已拷贝 lib/ollama/", item)

    # 3) 模型（blobs + manifests，可能较大）
    print("正在拷贝模型（约 4.4GB，请耐心等待）...")
    for item in os.listdir(OLLAMA_MODELS_SRC):
        if _copy_any(os.path.join(OLLAMA_MODELS_SRC, item), os.path.join(models_dir, item)):
            print("已拷贝 models/", item)

    # 4) 启动脚本 + 说明
    _write_start_bat()
    _write_readme()
    print("\n完成！便携 Ollama 位于：", DEST)
    print("启动：", os.path.join(DEST, "start-ollama.bat"))
    return 0


def _write_start_bat():
    content = (
        "@echo off\r\n"
        "rem 便携版 Ollama 启动脚本（离线、无需安装）\r\n"
        "set OLLAMA_MODELS=%~dp0models\r\n"
        "set OLLAMA_HOST=127.0.0.1:11434\r\n"
        '"%~dp0bin\\ollama.exe" serve\r\n'
    )
    with open(os.path.join(DEST, "start-ollama.bat"), "w", encoding="utf-8") as f:
        f.write(content)


def _write_readme():
    readme = """便携版 Ollama（纯 CPU）
========================================
本项目已内置 Ollama 程序与 qwen2.5 模型，复制整个项目到任意 Windows 电脑即可离线使用"本地 Ollama"，无需单独安装。

启动：
    双击 ollama\\start-ollama.bat
    它会在 127.0.0.1:11434 启动 Ollama 服务，并用项目内的模型目录。

然后在 AI 桌面端系统的模型配置中，把"本地 Ollama"的 api_base 保持为：
    http://localhost:11434/v1

注意事项：
1. 端口 11434 不能被其它程序占用（若被占，可改 start-ollama.bat 里的
   OLLAMA_HOST 端口，同时同步修改模型配置里的 api_base）。
2. 本便携版为纯 CPU 推理，未包含 NVIDIA GPU 库（cuda_v12）；
   如需 GPU 加速，在 打包便携Ollama.py 里把 SKIP_DIRS 改为空集后重跑即可（约 +1.1GB）。
3. 模型为 qwen2.5:7b，位于 ollama\\models。
4. 若要在 exe 打开时自动启动 Ollama，需在桌面端启动逻辑中调用 start-ollama.bat。
"""
    with open(os.path.join(DEST, "README.txt"), "w", encoding="utf-8") as f:
        f.write(readme)


if __name__ == "__main__":
    raise SystemExit(main())
