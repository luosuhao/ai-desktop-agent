"""金融数据分析端点逻辑：把用户上传的 CSV/Excel 与自然语言分析目标，
交给项目根的自包含 data_analysis 包，以子进程方式运行并返回结构化结果。

设计要点：
- backend.exe 不打包 data_analysis / matplotlib / scipy —— 分析与绘图都在
  子进程的真实 python 中完成（与 tablenet 用专用 venv 起子进程同理）。
- 运行目录统一为 outputs/finance-analysis/<run_id>/（唯一，不覆盖）。
- DeepSeek Key 直接取自后端 model_config.json（active provider），
  用户无需另配 data_analysis 的 .env。
"""
import json
import os
import shutil
import subprocess
import sys
import time

from config import settings, load_model_config

ANALYSIS_TIMEOUT = 600  # 秒，覆盖代码生成 + 沙箱执行 + 结果解释


def resolve_analysis_python():
    """选择运行 data_analysis 的 python 解释器：
    1) DATA_ANALYSIS_PYTHON 环境变量显式指定（如专用 venv 的 python.exe）
    2) 项目内置的 data_analysis 专用 venv：<project_root>/data_analysis/.venv
       （把 data_analysis 依赖与后端钉死的环境隔离，互不冲突）
    3) 源码模式下优先复用当前后端进程的解释器
    4) PATH 中的 python
    5) 兜底 sys.executable"""
    env_py = os.environ.get("DATA_ANALYSIS_PYTHON", "").strip()
    if env_py and os.path.isfile(env_py):
        return env_py
    try:
        bundled_venv = os.path.join(
            _project_root(), "data_analysis", ".venv", "Scripts", "python.exe")
        if os.path.isfile(bundled_venv):
            return bundled_venv
    except Exception:
        pass
    if not getattr(sys, "frozen", False):
        return sys.executable
    py = shutil.which("python")
    if py:
        return py
    return sys.executable


def _project_root():
    """项目根：settings.output_dir 的上层。DATA_DIR 隔离模式下再多退一层。"""
    if settings.data_dir:
        return os.path.dirname(os.path.dirname(settings.output_dir))
    return os.path.dirname(settings.output_dir)


def _provider_env():
    """从后端 active provider 配置取 DeepSeek（或 Ollama）连接参数，
    注入子进程环境，使 data_analysis 无需独立 .env。"""
    prov = load_model_config()
    env = os.environ.copy()
    # 子进程 stdout 是管道时 Windows 下 locale 编码不稳定（GBK/ascii），
    # 强制 UTF-8 输出，父进程用 encoding="utf-8" 解码，避免中文路径打印崩溃。
    env.setdefault("PYTHONIOENCODING", "utf-8")
    if prov.get("api_key"):
        env.setdefault("DEEPSEEK_API_KEY", prov["api_key"])
        env.setdefault("DEEPSEEK_BASE_URL", prov.get("api_base") or "https://api.deepseek.com")
        env.setdefault("DEEPSEEK_MODEL", prov.get("model") or "deepseek-chat")
    return env


def run_finance_analysis(file_obj, filename: str, question: str):
    """执行一次金融数据分析。file_obj 为已打开的上传文件对象。

    返回结构：{success, run_id, question, columns, code, interpretation,
               exec, figures(list[outputs相对路径]), token_summary, error}
    """
    error_prefix = "金融数据分析失败"

    def _fail(msg, **extra):
        out = {"success": False, "error": f"{error_prefix}: {msg}"}
        out.update(extra)
        return out

    if not filename.lower().endswith((".csv", ".xlsx", ".xls")):
        return _fail("仅支持 CSV / Excel（.csv/.xlsx/.xls）文件")
    if not (question or "").strip():
        return _fail("请填写分析目标")

    # 唯一运行目录（不覆盖上次结果）
    stem = os.path.splitext(os.path.basename(filename))[0]
    ts = time.strftime("%Y%m%d_%H%M%S")
    base = os.path.join(settings.output_dir, "finance-analysis")
    os.makedirs(base, exist_ok=True)
    run_dir = os.path.join(base, f"{stem}_{ts}")
    n = 1
    while os.path.exists(run_dir):
        run_dir = os.path.join(base, f"{stem}_{ts}_{n}")
        n += 1
    source_dir = os.path.join(run_dir, "source")
    fig_dir = os.path.join(run_dir, "figures")
    os.makedirs(source_dir)
    os.makedirs(fig_dir)

    source_path = os.path.join(source_dir, os.path.basename(filename))
    file_obj.seek(0)
    with open(source_path, "wb") as f:
        f.write(file_obj.read())

    result_json = os.path.join(run_dir, "result.json")
    py = resolve_analysis_python()
    cmd = [py, "-m", "data_analysis.run_analysis",
           "--data", source_path,
           "--question", question,
           "--out-dir", fig_dir,
           "--json", result_json]
    env = _provider_env()

    try:
        proc = subprocess.run(cmd, cwd=_project_root(), env=env,
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=ANALYSIS_TIMEOUT)
    except subprocess.TimeoutExpired:
        return _fail(f"分析超过 {ANALYSIS_TIMEOUT} 秒被终止", run_id=os.path.basename(run_dir))

    if not os.path.exists(result_json):
        return _fail("分析进程异常退出，未生成结果",
                     run_id=os.path.basename(run_dir),
                     stdout=(proc.stdout or "")[-1500:],
                     stderr=(proc.stderr or "")[-1500:])

    with open(result_json, encoding="utf-8") as f:
        result = json.load(f)

    figures = []
    for p in result.get("figures", []):
        if os.path.exists(p):
            figures.append(os.path.relpath(p, settings.output_dir).replace("\\", "/"))

    return {
        "success": bool(result.get("success")),
        "run_id": os.path.basename(run_dir),
        "question": result.get("question"),
        "columns": result.get("columns"),
        "code": result.get("code"),
        "interpretation": result.get("interpretation"),
        "exec": result.get("exec"),
        "figures": figures,
        "token_summary": result.get("token_summary"),
        "error": None if result.get("success") else "分析未完成（详见执行日志）",
    }


def finance_analysis_status():
    """检查 data_analysis 是否可用：python 可解析、依赖可导入。"""
    py = resolve_analysis_python()
    check_code = (
        "import data_analysis, pandas, numpy, matplotlib, openpyxl, openai; "
        "import matplotlib.pyplot"
    )
    try:
        # 与 run 命令一致：以项目根为 cwd，python -c 才能 import data_analysis
        proc = subprocess.run([py, "-c", check_code], cwd=_project_root(),
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=30)
        ok = proc.returncode == 0
        detail = (proc.stderr or proc.stdout or "").strip()[:500] if not ok else ""
    except Exception as e:
        ok = False
        detail = str(e)
    return {
        "available": ok,
        "python": py,
        "detail": detail or None,
    }
