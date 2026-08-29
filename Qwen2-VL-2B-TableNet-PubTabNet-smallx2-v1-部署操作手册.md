# Qwen2-VL-2B-TableNet-PubTabNet-smallx2-v1 部署操作手册

## 1. 模型说明

本模型用于把表格图片转换成完整 HTML 表格：

```text
Qwen2-VL-2B-TableNet-PubTabNet-smallx2-v1
```

它已经合并 TableNet 和 PubTabNet 两阶段 LoRA，部署时不需要再加载 adapter，也不使用 OCR。

模型包：

```text
Qwen2-VL-2B-TableNet-PubTabNet-smallx2-v1.tar.gz
```

归档 SHA-256：

```text
8f47c50cacfcd3095ab33cfda2eb56f7b55f91035331009629b1b119b4274207
```

模型包约 3.3 GB，解压后约 4.2 GB。

### 已验证推理参数

| 参数 | 值 |
|---|---:|
| 图片尺寸 | 280 x 280 |
| `max_new_tokens` | 2048 |
| 解码方式 | 贪心解码，`do_sample=False` |
| OCR | 不使用 |
| 默认提示词 | `你是一个HTML助手，目标是读取用户输入的表格图片，转换成HTML序列` |

不要擅自修改图片尺寸、提示词或解码参数，否则结果不能与现有评测直接比较。

### 200 条 PubTabNet validation 复测

| 指标 | 独立完整模型 |
|---|---:|
| TEDS | 0.720112 |
| Structure-only TEDS | 0.854898 |
| HTML Valid | 88.0% |
| 平均推理时间 | 3.77 秒/张，RTX 4090 D |

原 LoRA 加载方式的 TEDS 为 0.720443，合并后差值为 -0.000332，配对 95% 置信区间跨 0，可视为保持原性能。以上是 validation 结果，不是 1,000 条 holdout 结果。

## 2. 部署要求

推荐配置：

| 资源 | 最低建议 | 推荐 |
|---|---|---|
| 操作系统 | Ubuntu 20.04/22.04 | Ubuntu 22.04 |
| Python | 3.10 | 3.10 |
| GPU | Ampere 或更新，16 GB 显存 | RTX 3090/4090，24 GB 显存 |
| 内存 | 16 GB | 32 GB 以上 |
| 可用磁盘 | 10 GB | 20 GB 以上 |
| NVIDIA 驱动 | 支持 CUDA 12.1 | 535 或更新 |

现有服务实现固定使用 CUDA 和 BF16。没有 NVIDIA GPU、GPU 不支持 BF16，或显存不足时，不应直接照本手册上线。

目录约定：

```text
/opt/tablenet/
├── app/                       # 本项目代码
├── models/
│   ├── releases/
│   │   └── Qwen2-VL-2B-TableNet-PubTabNet-smallx2-v1/
│   └── current -> releases/Qwen2-VL-2B-TableNet-PubTabNet-smallx2-v1
├── input/                     # 服务可读取的输入图片
└── logs/
```

## 3. 校验和解压

Linux 校验：

```bash
cd /path/to/download
sha256sum Qwen2-VL-2B-TableNet-PubTabNet-smallx2-v1.tar.gz
```

macOS 校验：

```bash
shasum -a 256 Qwen2-VL-2B-TableNet-PubTabNet-smallx2-v1.tar.gz
```

输出必须包含本文第 1 节给出的 SHA-256。哈希不一致时不要部署，应重新下载。

解压并建立当前版本软链接：

```bash
sudo mkdir -p /opt/tablenet/models/releases
sudo tar -xzf Qwen2-VL-2B-TableNet-PubTabNet-smallx2-v1.tar.gz \
  -C /opt/tablenet/models/releases
sudo ln -sfn \
  /opt/tablenet/models/releases/Qwen2-VL-2B-TableNet-PubTabNet-smallx2-v1 \
  /opt/tablenet/models/current
```

校验解压后的 18 个文件：

```bash
cd /opt/tablenet/models/current
sha256sum -c SHA256SUMS
```

所有文件都必须显示 `OK`。关键文件包括：

```text
config.json
generation_config.json
model-00001-of-00002.safetensors
model-00002-of-00002.safetensors
model.safetensors.index.json
preprocessor_config.json
tokenizer.json
merge_manifest.json
SHA256SUMS
validation/
```

## 4. 安装运行环境

创建独立虚拟环境：

```bash
python3.10 -m venv /opt/tablenet/venv
source /opt/tablenet/venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
```

安装 CUDA 12.1 版 PyTorch：

```bash
pip install torch==2.1.2 --index-url https://download.pytorch.org/whl/cu121
```

安装推理服务依赖：

```bash
pip install \
  'transformers>=4.45,<4.49' \
  accelerate \
  peft \
  qwen-vl-utils \
  pillow \
  fastapi \
  uvicorn \
  numpy==1.26.4
```

完整模型本身不需要 PEFT，但项目的 `qwen_api_server.py` 在导入阶段会导入 PEFT，因此服务环境仍需安装 `peft`。

检查 CUDA 和 BF16：

```bash
python - <<'PY'
import torch

print("torch:", torch.__version__)
print("cuda_available:", torch.cuda.is_available())
print("cuda_version:", torch.version.cuda)
print("gpu:", torch.cuda.get_device_name(0) if torch.cuda.is_available() else None)
print("bf16_supported:", torch.cuda.is_bf16_supported() if torch.cuda.is_available() else False)
PY
```

必须确认 `cuda_available: True` 和 `bf16_supported: True`。

## 5. 准备项目代码

将本项目放到：

```text
/opt/tablenet/app
```

FastAPI 服务至少需要 `qwen_api_server.py`。单图测试和批量评测还需要：

```text
test_main.py
evaluate_dataset.py
evaluate_clean_suite.py
utils/
```

## 6. 单图冒烟测试

准备一张真实表格图片：

```bash
sudo mkdir -p /opt/tablenet/input
sudo cp /path/to/table.png /opt/tablenet/input/table.png
```

运行：

```bash
source /opt/tablenet/venv/bin/activate
cd /opt/tablenet/app

python - <<'PY'
from test_main import PROMPT, load_model, predict_one

model, processor = load_model(
    "/opt/tablenet/models/current",
    adapter="",
)
html = predict_one(
    model=model,
    processor=processor,
    image_path="/opt/tablenet/input/table.png",
    max_new_tokens=2048,
    image_size=280,
    prompt=PROMPT,
)
print(html)
PY
```

验收条件：

- 模型不需要 adapter 即可加载。
- GPU 显存正常增长且没有 OOM。
- 输出包含 `<table`，通常包含 `<html>` 和 `</html>`。
- 输出不是空字符串或解释性文字。

## 7. 启动 FastAPI 服务

### 7.1 前台启动

```bash
source /opt/tablenet/venv/bin/activate
cd /opt/tablenet/app

CUDA_VISIBLE_DEVICES=0 \
TRANSFORMERS_OFFLINE=1 \
HF_HUB_OFFLINE=1 \
python qwen_api_server.py \
  --base-model /opt/tablenet/models/current \
  --adapter= \
  --host 127.0.0.1 \
  --port 8000 \
  --image-size 280
```

必须显式使用 `--adapter=`。如果省略，项目脚本会尝试加载默认 LoRA 路径，导致启动失败或加载错误模型。

不要启动多个 Uvicorn worker。每个 worker 都会加载一份模型并占用一份 GPU 显存。

### 7.2 健康检查

```bash
curl -s http://127.0.0.1:8000/health
```

预期结果：

```json
{
  "status": "ok",
  "model_loaded": true,
  "base_model": "/opt/tablenet/models/current",
  "adapter": ""
}
```

### 7.3 调用推理接口

接口接收服务器本机图片路径：

```bash
curl -sS -X POST http://127.0.0.1:8000/predict \
  -H 'Content-Type: application/json' \
  -d '{
    "image_path": "/opt/tablenet/input/table.png",
    "max_new_tokens": 2048
  }'
```

响应：

```json
{
  "html": "<html><body><table>...</table></body></html>"
}
```

请求约束：

- `image_path` 必须是服务进程可读取的绝对路径。
- `max_new_tokens` 推荐固定为 2048。
- 不要在生产请求中覆盖默认 prompt，除非重新评测。
- 单 GPU 建议一次只执行一个生成请求，由调用方队列控制并发。
- 返回值是模型生成的原始 HTML，浏览器展示前必须清洗并禁用脚本和外部资源。

当前 API 可以读取服务器本地任意可访问路径，因此不要直接暴露到公网。应部署在可信内网，或在前置服务中增加上传目录白名单、身份认证和请求限流。

## 8. 使用 systemd 后台运行

创建服务用户：

```bash
sudo useradd --system --home /opt/tablenet --shell /usr/sbin/nologin tablenet || true
sudo chown -R tablenet:tablenet /opt/tablenet
```

创建 `/etc/systemd/system/tablenet-qwen.service`：

```ini
[Unit]
Description=Qwen2-VL Table HTML API
After=network.target

[Service]
Type=simple
User=tablenet
Group=tablenet
WorkingDirectory=/opt/tablenet/app
Environment=CUDA_VISIBLE_DEVICES=0
Environment=TRANSFORMERS_OFFLINE=1
Environment=HF_HUB_OFFLINE=1
Environment=PYTHONUNBUFFERED=1
ExecStart=/opt/tablenet/venv/bin/python /opt/tablenet/app/qwen_api_server.py --base-model=/opt/tablenet/models/current --adapter= --host=127.0.0.1 --port=8000 --image-size=280
Restart=on-failure
RestartSec=10
TimeoutStartSec=300
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
```

加载并启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now tablenet-qwen
sudo systemctl status tablenet-qwen
```

查看日志：

```bash
sudo journalctl -u tablenet-qwen -f
```

重启或停止：

```bash
sudo systemctl restart tablenet-qwen
sudo systemctl stop tablenet-qwen
```

## 9. 批量评测

按项目数据格式运行 200 条评测：

```bash
source /opt/tablenet/venv/bin/activate
cd /opt/tablenet/app

python evaluate_dataset.py \
  --base-model /opt/tablenet/models/current \
  --adapter= \
  --model-id packaged-smallx2-v1 \
  --test-json /path/to/data_vl_val.json \
  --output-jsonl /opt/tablenet/logs/predictions.jsonl \
  --limit 200 \
  --batch-size 8 \
  --image-size 280 \
  --max-new-tokens 2048 \
  --ocr-mode none
```

模型包内已经包含本次 200 条复测记录：

```text
validation/pubtabnet-validation-200-predictions.jsonl
validation/pubtabnet-validation-200-run.json
validation/packaged-vs-adapter-summary.json
```

## 10. 上线验收清单

- [ ] 归档 SHA-256 与本文一致。
- [ ] `sha256sum -c SHA256SUMS` 全部通过。
- [ ] CUDA 和 BF16 检查通过。
- [ ] `/health` 返回 `model_loaded: true`。
- [ ] `/health` 中 `adapter` 为空字符串。
- [ ] 单图输出包含完整表格 HTML。
- [ ] 图片尺寸为 280 x 280。
- [ ] `max_new_tokens` 为 2048。
- [ ] `do_sample=False`，没有随机采样。
- [ ] 没有注入 OCR 文本或坐标。
- [ ] 单 GPU 并发限制为 1。
- [ ] API 没有直接暴露到公网。
- [ ] 已记录模型目录、归档哈希和部署时间。

## 11. 监控

GPU 监控：

```bash
watch -n 2 nvidia-smi
```

服务应记录或监控：

- `/health` 成功率
- 请求成功数和失败数
- 推理耗时 P50/P95/P99
- 空输出比例
- HTML 合法率
- OOM、CUDA error 和服务重启次数

## 12. 常见故障

### CUDA 不可用

1. 检查 `nvidia-smi`。
2. 确认安装的是 CUDA 版 PyTorch，不是 CPU 版。
3. 确认容器启动时挂载了 GPU。

### CUDA out of memory

1. 确认只有一个服务进程和一个 worker。
2. 将调用并发限制为 1。
3. 关闭其他 GPU 进程。
4. 保持图片尺寸 280 和 `max_new_tokens=2048`。
5. 优先使用 24 GB GPU。

### 启动时寻找默认 LoRA

如果日志提示找不到 `./output/lora-1000`，说明遗漏了空 adapter 参数。启动命令必须包含：

```text
--adapter=
```

### 模型尝试联网下载

```bash
export TRANSFORMERS_OFFLINE=1
export HF_HUB_OFFLINE=1
```

并确认 `--base-model` 是本地绝对路径。

### 输出不是完整 HTML

检查：

1. 提示词是否被修改。
2. `max_new_tokens` 是否小于 2048。
3. 图片是否为真实表格图片。
4. 图片路径是否正确。
5. 是否错误加入 OCR 文本或坐标。

业务端应将不含 `<table` 或 HTML 解析失败的结果标记为失败，不要静默展示。

### 结果与评测不一致

确认参数：

```text
image_size=280
max_new_tokens=2048
do_sample=False
adapter=""
ocr_mode=none
```

同时确认模型目录 SHA-256 校验全部通过。

## 13. 升级与回滚

升级流程：

1. 将新模型解压到新的 `models/releases/<version>` 目录。
2. 校验新模型内部 SHA-256。
3. 在独立端口完成健康检查和单图冒烟。
4. 更新 `current` 软链接。
5. 重启服务。

```bash
sudo ln -sfn /opt/tablenet/models/releases/<new-version> /opt/tablenet/models/current
sudo systemctl restart tablenet-qwen
```

回滚：

```bash
sudo ln -sfn \
  /opt/tablenet/models/releases/Qwen2-VL-2B-TableNet-PubTabNet-smallx2-v1 \
  /opt/tablenet/models/current
sudo systemctl restart tablenet-qwen
curl -s http://127.0.0.1:8000/health
```

至少保留一个经过验证的旧版本，不要原地覆盖模型目录。

## 14. 使用限制

- 本模型面向表格图片转 HTML，不是通用 OCR 服务。
- 推理阶段加入 PaddleOCR 会降低本次实验的 TEDS，因此默认部署禁止 OCR 注入。
- 模型可能产生识别错误、结构错误或非法 HTML，调用方必须保留失败处理。
- HTML 在浏览器渲染前必须清洗，并禁用脚本和外部资源。
- 建议记录输入图片标识、输出 HTML、模型版本、耗时和错误码。
- 未完成独立 holdout 评测前，不应将 validation 指标表述为最终泛化性能。
