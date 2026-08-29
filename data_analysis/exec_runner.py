"""沙箱子进程运行器：由 executor.execute_code 通过 subprocess 调用。

用法: python exec_runner.py <code_file> <workdir> <fig_dir> <result_path> <timeout>
"""
import io
import json
import os
import sys
import time
import traceback

ALLOWED_IMPORTS = {
    "math", "numpy", "pandas", "matplotlib", "matplotlib.pyplot",
    "seaborn", "sklearn", "scipy", "scipy.stats", "scipy.optimize",
    "scipy.spatial", "statistics", "json", "csv", "re", "random",
    "datetime", "decimal", "itertools", "functools", "collections",
    "string", "typing", "warnings", "os", "sys",
}

SAFE_BUILTINS = {
    "print", "range", "len", "str", "int", "float", "bool", "abs",
    "round", "min", "max", "sum", "sorted", "enumerate", "zip", "dict",
    "list", "set", "tuple", "type", "isinstance", "format", "repr",
    "reversed", "any", "all", "pow", "divmod", "ord", "chr", "bytes",
    "hash", "frozenset", "id", "next", "iter", "map", "filter", "slice",
    "Exception", "ValueError", "TypeError", "KeyError", "IndexError",
    "ZeroDivisionError", "NotImplementedError", "StopIteration", "object",
    "super", "staticmethod", "classmethod", "property",
    "complex", "bin", "hex", "oct", "callable", "hasattr",
}


class _RestrictedImporter:
    def __init__(self):
        self._real_import = __import__

    def __call__(self, name, globals=None, locals=None, fromlist=(), level=0):
        if level != 0:
            raise ImportError("relative imports are not allowed")
        base = name.split(".")[0]
        if base not in ALLOWED_IMPORTS and not any(
                a == name or a.startswith(name + ".")
                or (a.endswith(".*") and name.startswith(a[:-1]))
                for a in ALLOWED_IMPORTS):
            raise ImportError(f"module '{name}' is not allowed in the sandbox")
        return self._real_import(name, globals, locals, fromlist, level)


def main():
    code_file, workdir, fig_dir, result_path, timeout = sys.argv[1:6]
    timeout = float(timeout)
    with open(code_file, encoding="utf-8") as f:
        code = f.read()
    os.makedirs(fig_dir, exist_ok=True)
    os.environ["MPLBACKEND"] = "Agg"
    if workdir:
        os.chdir(workdir)

    out, err = io.StringIO(), io.StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = out, err
    t0 = time.time()

    import builtins as _b
    safe = {b: getattr(_b, b) for b in SAFE_BUILTINS if hasattr(_b, b)}
    ns = {"__name__": "__main__", "__builtins__": safe}
    ns["__builtins__"]["__import__"] = _RestrictedImporter()

    try:
        compile(code, "<generated>", "exec")
    except SyntaxError as e:
        _finish(False, out.getvalue(), err.getvalue(), "SyntaxError", str(e),
                traceback.format_exc(limit=4), round(time.time() - t0, 3), fig_dir, result_path)
        return

    result_var = None
    try:
        exec(compile(code, "<generated>", "exec"), ns)
        for k in ("answer", "ans", "result", "output", "final_answer"):
            if k in ns and ns[k] is not None:
                result_var = ns[k]
                break
        if result_var is not None:
            try:
                out.write("\n[RESULT] " + repr(result_var))
            except Exception:
                pass
        # 保存打开的图表
        try:
            import matplotlib.pyplot as plt
            for i, num in enumerate(plt.get_fignums()):
                fig = plt.figure(num)
                p = os.path.join(fig_dir, f"figure_{i}.png")
                fig.savefig(p, dpi=100, bbox_inches="tight")
                plt.close(fig)
        except Exception:
            pass
        payload = {
            "success": True, "stdout": out.getvalue(), "stderr": err.getvalue(),
            "error_type": None, "error_msg": None,
            "duration": round(time.time() - t0, 3),
            "result_var": repr(result_var) if result_var is not None else None,
        }
    except BaseException as e:
        payload = {
            "success": False, "stdout": out.getvalue(), "stderr": err.getvalue(),
            "error_type": type(e).__name__, "error_msg": str(e),
            "traceback": traceback.format_exc(limit=8),
            "duration": round(time.time() - t0, 3),
            "result_var": None,
        }
    finally:
        sys.stdout, sys.stderr = old_out, old_err
    _finish(payload["success"], payload["stdout"], payload["stderr"],
            payload["error_type"], payload["error_msg"], payload.get("traceback"),
            payload["duration"], fig_dir, result_path, payload["result_var"])


def _finish(success, stdout, stderr, error_type, error_msg, traceback_text,
            duration, fig_dir, result_path, result_var=None):
    figs = []
    try:
        for fn in sorted(os.listdir(fig_dir)):
            if fn.endswith(".png"):
                figs.append(os.path.join(fig_dir, fn))
    except Exception:
        pass
    payload = {
        "success": success, "stdout": stdout, "stderr": stderr,
        "error_type": error_type, "error_msg": error_msg,
        "traceback": traceback_text, "duration": duration,
        "figures": figs, "result_var": result_var,
    }
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, default=str)


if __name__ == "__main__":
    main()
