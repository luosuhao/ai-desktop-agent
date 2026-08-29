"""金融数据分析独立包的配置：读取 .env 中的 API Key 与模型参数。

.env 查找顺序：环境变量 → 本文件夹 .env → 父目录 .env（均使用 setdefault，不覆盖已存在的环境变量）。
"""
import os
import pathlib

BASE_DIR = pathlib.Path(__file__).resolve().parent
PARENT_DIR = BASE_DIR.parent


def _load_dotenv(path):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


_load_dotenv(BASE_DIR / ".env")
_load_dotenv(PARENT_DIR / ".env")

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEFAULT_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

DEFAULT_TEMPERATURE = float(os.environ.get("DEFAULT_TEMPERATURE", "0.0"))
DEFAULT_MAX_TOKENS = int(os.environ.get("DEFAULT_MAX_TOKENS", "4096"))
# 代码生成类调用使用更大的输出上限（避免长代码被截断）
CODE_GEN_MAX_TOKENS = 8192

# 代码执行沙箱超时（秒）
EXEC_TIMEOUT = 15
