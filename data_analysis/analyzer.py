"""金融数据分析：读取 CSV/Excel，根据分析目标生成并执行 Python 代码，
完成金融指标计算、数据处理、统计分析、可视化与结果解释。

本模块为独立可移植版本，包内自带 config/llm/executor/prompts/extract，
不依赖主系统 financial_agent 包。
"""
import os

from . import config
from . import executor
from . import llm as llm_module
from . import prompts
from .extract import extract_python_code

DATA_PREAMBLE = (
    "数据文件：{path}\n"
    "数据已通过 pandas 加载为 df，列名为：{cols}\n"
    "数据前 5 行预览：\n{preview}\n"
    "请基于以上数据编写完整 Python 代码完成分析任务。"
)


class FinancialDataAnalysis:
    def __init__(self, model=None, temperature=None, max_tokens=None,
                 task_prompt=True, allow_code=True, max_fix_attempts=2):
        self.model = model or config.DEFAULT_MODEL
        self.temperature = config.DEFAULT_TEMPERATURE if temperature is None else temperature
        self.max_tokens = max_tokens or config.DEFAULT_MAX_TOKENS
        self.task_prompt = task_prompt
        self.allow_code = allow_code
        self.max_fix_attempts = max_fix_attempts

    def load_preview(self, data_path):
        import pandas as pd
        path = str(data_path)
        if path.lower().endswith(".xlsx") or path.lower().endswith(".xls"):
            df = pd.read_excel(path)
        else:
            df = pd.read_csv(path)
        preview = df.head(5).to_string()
        cols = ", ".join(str(c) for c in df.columns)
        return df, cols, preview

    def _gen_code(self, question, data_path, cols, preview, fix_error=None):
        system = prompts.system_prompt("data_analysis", self.task_prompt)
        user = DATA_PREAMBLE.format(path=data_path, cols=cols, preview=preview) + \
            f"\n\n分析任务：{question}\n" + \
            "请输出完整 Python 代码块（读取数据、计算指标、print 输出关键结果、必要时用 matplotlib 绘图并 plt.savefig('figure.png')）。"
        if fix_error:
            user += f"\n\n上次运行错误：{fix_error}\n请修正代码后重新输出完整代码。"
        resp = llm_module.chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            model=self.model, temperature=self.temperature,
            max_tokens=max(self.max_tokens, config.CODE_GEN_MAX_TOKENS), label="data_analysis_gen",
        )
        return extract_python_code(resp["text"])

    def _interpret(self, question, stdout, figures, exec_result):
        system = prompts.system_prompt("data_analysis", self.task_prompt)
        user = (f"分析任务：{question}\n\n程序运行输出：\n{stdout[:3000]}\n\n"
                f"请结合金融背景，用中文解释数值结果、趋势与含义，指出关键结论。")
        resp = llm_module.chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            model=self.model, temperature=self.temperature,
            max_tokens=self.max_tokens, label="data_analysis_interpret",
        )
        return resp["text"]

    def run(self, question, data_path):
        df, cols, preview = self.load_preview(data_path)
        records = {"question": question, "data_path": str(data_path),
                   "columns": cols, "code": None, "exec": None,
                   "interpretation": None, "figures": [], "success": False}

        if not self.allow_code:
            # 消融：无代码执行，由 LLM 直接推理
            system = prompts.system_prompt("data_analysis", self.task_prompt)
            user = (f"数据文件：{data_path}\n列名：{cols}\n预览：\n{preview}\n\n"
                    f"分析任务：{question}\n请直接基于上述数据信息进行推理计算，给出数值结果与分析，不要编写代码。")
            resp = llm_module.chat(
                [{"role": "system", "content": system}, {"role": "user", "content": user}],
                model=self.model, temperature=self.temperature,
                max_tokens=self.max_tokens, label="data_analysis_reason",
            )
            records["interpretation"] = resp["text"]
            records["reason_only"] = True
            records["success"] = True
            return records

        code = self._gen_code(question, data_path, cols, preview)
        records["code"] = code
        last = None
        for _ in range(self.max_fix_attempts + 1):
            last = executor.execute_code(code, timeout=config.EXEC_TIMEOUT,
                                         workdir=str(os.getcwd()))
            if last["success"]:
                break
            err = f"{last.get('error_type')}: {last.get('error_msg')}"
            if "TimeoutError" in err:
                break
            code = self._gen_code(question, data_path, cols, preview, fix_error=err)
            records["code"] = code

        records["exec"] = last
        if last.get("figures"):
            records["figures"] = last["figures"]
        if last["success"]:
            records["interpretation"] = self._interpret(
                question, last.get("stdout", ""), last.get("figures", []), last)
            records["success"] = True
        return records
