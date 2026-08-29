"""金融数据分析独立包的 LLM 封装（DeepSeek，OpenAI 兼容接口）。

提供 chat() 与 token 用量统计。API Key 读取顺序：环境变量（os.environ）优先，
其次为本包 config 中解析到的 .env。
"""
import os
import time

from . import config

_client = None
_client_created = False


def _get_client():
    """惰性创建 OpenAI 客户端。"""
    global _client, _client_created
    if not _client_created:
        import openai

        _client = openai.OpenAI(
            api_key=os.environ.get("DEEPSEEK_API_KEY") or config.DEEPSEEK_API_KEY,
            base_url=config.DEEPSEEK_BASE_URL,
            timeout=120,
            max_retries=2,
        )
        _client_created = True
    return _client


USAGE_LOG = []  # 每次调用的 {model, prompt_tokens, completion_tokens, total_tokens, latency, label}


def chat(messages, model=None, temperature=None, max_tokens=None,
         json_mode=False, label="", seed=42, max_retries=4):
    """调用 LLM。

    messages: [{role, content}]
    返回 dict: {text, prompt_tokens, completion_tokens, total_tokens, latency, model, ok}
    """
    model = model or config.DEFAULT_MODEL
    temperature = config.DEFAULT_TEMPERATURE if temperature is None else temperature
    max_tokens = max_tokens or config.DEFAULT_MAX_TOKENS
    kwargs = dict(model=model, messages=messages, max_tokens=max_tokens,
                  temperature=temperature, seed=seed)
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    if "reasoner" in model:
        kwargs.pop("temperature", None)
        kwargs.pop("seed", None)

    last_err = None
    for attempt in range(max_retries):
        try:
            t0 = time.time()
            client = _get_client()
            resp = client.chat.completions.create(**kwargs)
            latency = time.time() - t0
            usage = resp.usage
            record = {
                "model": model, "latency": round(latency, 2),
                "prompt_tokens": usage.prompt_tokens if usage else 0,
                "completion_tokens": usage.completion_tokens if usage else 0,
                "total_tokens": usage.total_tokens if usage else 0,
                "label": label,
            }
            USAGE_LOG.append(record)
            return {
                "text": resp.choices[0].message.content or "",
                "prompt_tokens": record["prompt_tokens"],
                "completion_tokens": record["completion_tokens"],
                "total_tokens": record["total_tokens"],
                "latency": latency, "model": model, "ok": True,
            }
        except Exception as e:
            last_err = e
            time.sleep(2 * (attempt + 1))
    return {"text": "", "prompt_tokens": 0, "completion_tokens": 0,
            "total_tokens": 0, "latency": 0, "model": model, "ok": False,
            "error": str(last_err)}


def token_summary():
    total_in = sum(r["prompt_tokens"] for r in USAGE_LOG)
    total_out = sum(r["completion_tokens"] for r in USAGE_LOG)
    n = len(USAGE_LOG)
    return {
        "n_calls": n,
        "prompt_tokens": total_in,
        "completion_tokens": total_out,
        "total_tokens": total_in + total_out,
        "avg_total": round((total_in + total_out) / n, 1) if n else 0,
    }
