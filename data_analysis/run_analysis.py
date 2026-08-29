"""金融数据分析命令行入口（独立可移植）。

用法（推荐，在项目根目录运行）：
    python -m data_analysis.run_analysis --data data/sample_data/示例公司财务数据.xlsx \
        --question "计算2022和2023年的营业收入增长率、毛利率并绘图"

也可直接运行：
    python data_analysis/run_analysis.py --data <文件> --question "问题"

可选参数：
    --no-task-prompt   关闭任务专用 Prompt（对应消融实验）
    --no-code          关闭代码执行，仅由 LLM 直接推理（对应消融实验）
    --model <名称>     覆盖模型（默认 deepseek-chat）
    --temperature <值> 覆盖 temperature（默认 0.0）
    --max-tokens <值>  覆盖最大输出 Token
    --out-dir <路径>   图表输出目录（默认 data_analysis/output）
"""
import argparse
import os
import shutil
import sys

# 保证以 "python data_analysis/run_analysis.py" 运行时父目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_analysis import config
from data_analysis.analyzer import FinancialDataAnalysis


def main():
    ap = argparse.ArgumentParser(description="金融数据分析命令行工具")
    ap.add_argument("--data", required=True, help="数据文件路径（CSV/Excel）")
    ap.add_argument("--question", required=True, help="分析目标，如：计算2022和2023年的营业收入增长率")
    ap.add_argument("--no-task-prompt", action="store_true", help="关闭任务专用 Prompt")
    ap.add_argument("--no-code", action="store_true", help="关闭代码执行，仅 LLM 推理")
    ap.add_argument("--model", default=None, help="模型名称")
    ap.add_argument("--temperature", type=float, default=None, help="temperature")
    ap.add_argument("--max-tokens", type=int, default=None, help="最大输出 Token")
    ap.add_argument("--out-dir", default=None, help="图表输出目录")
    ap.add_argument("--json", default=None, help="结果 JSON 输出路径（供外部程序结构化读取）")
    args = ap.parse_args()

    data_path = os.path.abspath(args.data)
    if not os.path.exists(data_path):
        print(f"[错误] 数据文件不存在：{data_path}")
        sys.exit(1)

    out_dir = args.out_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
    os.makedirs(out_dir, exist_ok=True)

    print("=" * 60)
    print("金融数据分析")
    print(f"数据文件：{data_path}")
    print(f"分析目标：{args.question}")
    print(f"模型：{args.model or config.DEFAULT_MODEL} | "
          f"任务专用Prompt：{'关' if args.no_task_prompt else '开'} | "
          f"代码执行：{'关' if args.no_code else '开'}")
    print("=" * 60)

    agent = FinancialDataAnalysis(
        model=args.model,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        task_prompt=not args.no_task_prompt,
        allow_code=not args.no_code,
    )

    records = agent.run(args.question, data_path)

    print("\n[结果] 分析完成：", "成功" if records.get("success") else "失败")
    copied = []
    if records.get("code"):
        print("\n" + "─" * 60 + "\n[生成代码]\n" + "─" * 60)
        print(records["code"])
    if records.get("exec") is not None:
        ex = records["exec"]
        print("\n" + "─" * 60 + "\n[执行日志]\n" + "─" * 60)
        if not ex.get("success"):
            print(f"执行失败：{ex.get('error_type')}: {ex.get('error_msg')}")
        print(ex.get("stdout", "") or "(无输出)")
    if records.get("figures"):
        # 复制图表到输出目录
        copied = []
        for i, fp in enumerate(records["figures"]):
            if os.path.exists(fp):
                dst = os.path.join(out_dir, f"figure_{i}.png")
                shutil.copyfile(fp, dst)
                copied.append(dst)
        print("\n[图表] 已保存到：")
        for c in copied:
            print("  ", c)
    if records.get("interpretation"):
        print("\n" + "─" * 60 + "\n[结果解释]\n" + "─" * 60)
        print(records["interpretation"])

    from data_analysis import llm
    summary = llm.token_summary()
    print("\n" + "─" * 60)
    print("[Token 用量] ", summary)

    if args.json:
        import json
        json_result = {
            "success": bool(records.get("success")),
            "question": records.get("question"),
            "data_path": records.get("data_path"),
            "columns": records.get("columns"),
            "code": records.get("code"),
            "reason_only": records.get("reason_only", False),
            "interpretation": records.get("interpretation"),
            "exec": records.get("exec"),
            "figures": copied,
            "token_summary": summary,
        }
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(json_result, f, ensure_ascii=False, indent=2)
        print(f"[JSON] 结果已写入 {args.json}")


if __name__ == "__main__":
    main()
