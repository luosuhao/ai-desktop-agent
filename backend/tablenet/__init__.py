"""Qwen2-VL-2B-TableNet-PubTabNet-smallx2-v1 集成包。

模型推理运行在独立 venv（tablenet-venv）中，主后端通过 engine.py 以本地 HTTP
服务的方式调用，避免把 torch/transformers 打进主后端环境。
"""
