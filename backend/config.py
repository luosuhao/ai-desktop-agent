"""AI Desktop System Configuration"""
from typing import Optional, List, Dict
import json
import os


# Detect project root (parent of the backend directory) so outputs land in
# D:\暑期作业\AI桌面端系统\outputs instead of backend\outputs.
# Works both from the source backend/ and from the packaged exe
# (resources/backend): walk up from CWD until a directory containing AGENTS.md
# is found (the project root marker), then fall back to the old heuristic.
def _find_project_root(start: str):
    d = os.path.abspath(start)
    while True:
        if os.path.isfile(os.path.join(d, "AGENTS.md")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


_cwd = os.getcwd()
_project_root = _find_project_root(_cwd) or (
    os.path.dirname(os.path.abspath(_cwd))
    if os.path.basename(_cwd) in ('backend', 'server', 'app')
    else os.path.abspath(_cwd)
)


# ----- Qwen2-VL-TableNet 表格识别模型配置 -----
def _tablenet_model_dir() -> str:
    """模型目录：环境变量 TABLENET_MODEL_DIR 优先，否则自动探测项目根。"""
    env_dir = os.environ.get("TABLENET_MODEL_DIR", "").strip()
    if env_dir:
        return env_dir
    candidate = os.path.join(
        _project_root,
        "Qwen2-VL-2B-TableNet-PubTabNet-smallx2-v1",
        "Qwen2-VL-2B-TableNet-PubTabNet-smallx2-v1",
    )
    if os.path.isfile(os.path.join(candidate, "config.json")):
        return candidate
    return candidate  # 即使不存在也返回，由调用方给出明确错误


def _tablenet_venv_dir() -> str:
    env_dir = os.environ.get("TABLENET_VENV_DIR", "").strip()
    if env_dir:
        return env_dir
    return os.path.join(_project_root, "tablenet-venv")


TABLENET_MODEL_DIR = _tablenet_model_dir()
TABLENET_VENV_DIR = _tablenet_venv_dir()
TABLENET_PORT = int(os.environ.get("TABLENET_PORT", "18000"))


_DATA_DIR = os.environ.get("DATA_DIR", "").strip()


class Settings:
    """System configuration"""
    def __init__(self):
        self.api_host: str = "0.0.0.0"
        self.api_port: int = int(os.environ.get("API_PORT", "8000"))
        # DATA_DIR 让同一台机器可运行多个隔离实例（各自数据目录），默认行为不变
        self.data_dir: str = _DATA_DIR
        _base = _DATA_DIR or "."
        self.upload_dir: str = os.path.join(_base, "uploads")
        self.vector_db_dir: str = os.path.join(_base, "chroma_db")
        self.wiki_db_dir: str = os.path.join(_base, "wiki_db")
        if _DATA_DIR:
            self.output_dir: str = os.path.join(_project_root, _DATA_DIR, "outputs")
        else:
            self.output_dir: str = os.path.join(_project_root, "outputs")
        self.debug: bool = True
        self.max_retries: int = 3


settings = Settings()

# Auto-detect JDK and add to PATH for Coding Agent
_jdk_candidates = [
    r"C:\Program Files\Microsoft\jdk-17.0.19.10-hotspot\bin",
    r"C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot\bin",
    r"C:\Program Files\Java\jdk-17\bin",
]
for _p in _jdk_candidates:
    if os.path.isfile(os.path.join(_p, "javac.exe")):
        os.environ["PATH"] = _p + os.pathsep + os.environ.get("PATH", "")
        break

MODEL_CONFIG_FILE = "model_config.json"

_DEFAULT_PROVIDERS = {
    "online": {
        "name": "DeepSeek 在线",
        "provider": "deepseek",
        "api_key": "",
        "api_base": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "temperature": 0.7,
        "max_tokens": 393216,
        "context_length": 1000000
    },
    "local": {
        "name": "本地 Ollama",
        "provider": "ollama",
        "api_key": "ollama",
        "api_base": "http://localhost:11434/v1",
        "model": "qwen2.5:7b",
        "temperature": 0.7,
        "max_tokens": 8192,
        "context_length": 32768
    }
}


def get_default_model_config() -> dict:
    """Return default single-provider config (backward compat)"""
    p = _DEFAULT_PROVIDERS["online"]
    return {
        "provider": p["provider"],
        "api_key": p["api_key"],
        "api_base": p["api_base"],
        "model": p["model"],
        "temperature": p["temperature"],
        "max_tokens": p["max_tokens"],
        "context_length": p["context_length"]
    }


def load_model_config() -> dict:
    """Load config (backward compat: returns active provider's flat config)"""
    full = load_all_providers()
    active = full.get("active", "online")
    prov = full.get("providers", {}).get(active, _DEFAULT_PROVIDERS["online"])
    return dict(prov)  # flat dict for backward compat


def load_all_providers() -> dict:
    """Load full multi-provider config"""
    if os.path.exists(MODEL_CONFIG_FILE):
        try:
            with open(MODEL_CONFIG_FILE, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            # Check if it's the new multi-provider format
            if "providers" in data:
                return data
            # Old single-provider format → migrate
            prov = {
                "provider": data.get("provider", "deepseek"),
                "api_key": data.get("api_key", ""),
                "api_base": data.get("api_base", "https://api.deepseek.com/v1"),
                "model": data.get("model", "deepseek-chat"),
                "temperature": data.get("temperature", 0.7),
                "max_tokens": data.get("max_tokens", 393216),
                "context_length": data.get("context_length", 1000000)
            }
            return {"active": "online", "providers": {"online": prov, "local": dict(_DEFAULT_PROVIDERS["local"])}}
        except Exception:
            pass
    return {"active": "online", "providers": dict(_DEFAULT_PROVIDERS)}


def save_all_providers(data: dict):
    """Save full multi-provider config"""
    with open(MODEL_CONFIG_FILE, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_model_config(config: dict):
    """Save single-provider config (backward compat)"""
    full = load_all_providers()
    active = full.get("active", "online")
    full.setdefault("providers", {})[active] = {
        "name": config.get("name", active),
        "provider": config.get("provider", "deepseek"),
        "api_key": config.get("api_key", ""),
        "api_base": config.get("api_base", "https://api.deepseek.com/v1"),
        "model": config.get("model", "deepseek-chat"),
        "temperature": config.get("temperature", 0.7),
        "max_tokens": config.get("max_tokens", 393216),
        "context_length": config.get("context_length", 1000000)
    }
    save_all_providers(full)


def get_active_provider_name() -> str:
    """Return which provider is active: 'online' or 'local'"""
    full = load_all_providers()
    return full.get("active", "online")
