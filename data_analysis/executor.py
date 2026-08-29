"""安全的 Python 代码执行器（沙箱）。

通过 subprocess 在独立进程中运行代码（可跨平台、兼容 Streamlit），
提供真实的执行超时；捕获 stdout/stderr；自动保存 matplotlib 图表。
返回统一的执行结果字典。
"""
import json
import os
import subprocess
import sys
import tempfile
import time


def execute_code(code, timeout=None, workdir=None, fig_dir=None):
    """执行代码并返回统一结果字典。

    返回:
      {success, stdout, stderr, error_type, error_msg, traceback,
       duration, figures(list[path]), result_var, timed_out}
    """
    timeout = timeout or 15
    fig_dir = fig_dir or tempfile.mkdtemp(prefix="agent_figs_")
    os.makedirs(fig_dir, exist_ok=True)

    tmpdir = tempfile.mkdtemp(prefix="agent_exec_")
    code_file = os.path.join(tmpdir, "code.py")
    result_path = os.path.join(tmpdir, "result.json")
    with open(code_file, "w", encoding="utf-8") as f:
        f.write(code)

    runner = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exec_runner.py")
    cmd = [sys.executable, runner, code_file,
           workdir or os.getcwd(), fig_dir, result_path, str(timeout)]

    t0 = time.time()
    timed_out = False
    try:
        proc = subprocess.run(cmd, timeout=timeout, capture_output=True, text=True)
    except subprocess.TimeoutExpired as e:
        timed_out = True
        payload = {
            "success": False, "stdout": "", "stderr": "",
            "error_type": "TimeoutError",
            "error_msg": f"代码执行超过 {timeout} 秒被终止",
            "traceback": None,
            "duration": round(time.time() - t0, 3),
            "figures": [], "result_var": None, "timed_out": True,
        }
        return payload

    if os.path.exists(result_path):
        with open(result_path, encoding="utf-8") as f:
            payload = json.load(f)
        payload["timed_out"] = False
        if "traceback" not in payload:
            payload["traceback"] = None
    else:
        payload = {
            "success": False, "stdout": proc.stdout or "",
            "stderr": proc.stderr or "",
            "error_type": "ProcessError",
            "error_msg": "子进程异常退出，未返回结果",
            "traceback": (proc.stderr or "")[:2000],
            "duration": round(time.time() - t0, 3),
            "figures": [], "result_var": None, "timed_out": False,
        }
    return payload


def extract_last_number(stdout):
    """从执行输出中提取最后一个数字，用于数值答案判定。"""
    import re
    nums = re.findall(r"[-+]?\d+(?:\.\d+)?", (stdout or "").replace(",", ""))
    if not nums:
        return None
    return float(nums[-1])
