"""金融数据分析（独立可移植包）。

用法（命令行）：
    python -m data_analysis.run_analysis --data 数据文件 --question "分析目标"
或
    python data_analysis/run_analysis.py --data 数据文件 --question "分析目标"
"""
from .analyzer import FinancialDataAnalysis

__all__ = ["FinancialDataAnalysis"]
