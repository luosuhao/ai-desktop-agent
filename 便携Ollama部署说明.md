# AI桌面端系统 便携/离线部署说明

本项目支持"**复制整个项目即可离线运行**"，内置两块可离线/隔离的运行时：
- **便携版 Ollama**（本地大模型，无需对方安装 Ollama）
- **data_analysis 独立 venv**（金融数据分析依赖隔离，避免污染后端环境）

---

# 第一部分 便携版 Ollama（本地大模型）

## 一、目录结构

```
AI桌面端系统/
├── ollama/                          ← 便携 Ollama（约 4.5GB，纯 CPU）
│   ├── bin/
│   │   ├── ollama.exe               ← Ollama 程序
│   │   └── lib/ollama/              ← 推理引擎 llama-server.exe + CPU 库
│   ├── models/                      ← qwen2.5:7b 模型（blobs + manifests）
│   ├── start-ollama.bat             ← 手动启动脚本（双击即用）
│   └── README.txt
├── 打包便携Ollama.py                ← 重新打包脚本
└── 便携Ollama部署说明.md            ← 本文档
```

## 二、首次打包（在已安装 Ollama 的电脑上）

1. 本机安装 Ollama，并已拉取模型：`ollama pull qwen2.5:7b`
2. 在项目根目录运行：

   ```
   python 打包便携Ollama.py
   ```

3. 产物：项目 `ollama\` 目录（约 4.5GB，**纯 CPU**，跳过 NVIDIA GPU 库）
   - 如需 GPU 加速：打开脚本把 `SKIP_DIRS` 改为 `set()` 后重跑（体积 +约 1.1GB）

> 脚本幂等：已存在的文件会跳过，可重复运行。

## 三、部署到另一台电脑

1. 把**整个项目**复制到目标电脑（务必包含 `ollama\` 目录）
2. 启动方式二选一：
   - **方式 A（推荐，自动启动）**：直接打开 `AI桌面端系统.exe`，或运行 `启动桌面端.bat`。后端启动时会自动拉起便携 Ollama。
   - **方式 B（手动）**：双击 `ollama\start-ollama.bat`。
3. 在"模型配置"里，确保"本地 Ollama"的 api_base 为 `http://localhost:11434/v1`（默认即是）。

## 四、自动启动机制（backend/run.py）

- 后端启动时先检测 `127.0.0.1:11434` 是否有服务
- **已有**（系统 Ollama 或之前启动的便携版）→ 跳过，不重复启动
- **没有** 且项目内有便携版 → 自动拉起 `ollama\bin\ollama.exe serve`，并设置
  - `OLLAMA_MODELS` → `项目根\ollama\models`
  - `OLLAMA_HOST` → `127.0.0.1:11434`

网页版与 exe 都走 `backend/run.py`，所以一份逻辑两端都生效。

## 五、Ollama 常见问题

| 问题 | 原因 / 解决 |
|---|---|
| 显示"不可连" | `ollama serve` 没在运行，或 11434 端口被其它程序占用 |
| 端口被占 | 改 `start-ollama.bat` 里的 `OLLAMA_HOST` 端口，同时同步改模型配置的 api_base |
| 想用 GPU 加速 | 重跑打包脚本（不跳过 `cuda_v12`），体积 +约 1.1GB |
| 换机器后模型为空 | 确认 `ollama\models` 完整；或重新打包拷贝 |
| 需要其它模型 | 在本机 `ollama pull` 后重新打包 |
| 生成很慢 | 纯 CPU 推理属正常（7B 模型约 8–20 秒/次回答） |

---

# 第二部分 data_analysis 独立 venv（金融数据分析依赖隔离）

## 一、是什么

`data_analysis` 是项目根的自包含金融数据分析包（读 CSV/Excel → 计算指标 + 绘图 + 解释），后端以**子进程**方式调用它。

它的依赖（`openai>=1.40`、新版 pandas/scipy/matplotlib 等）与后端钉死的环境（`openai==1.6.1`、`fastapi==0.104.1` 需 `anyio<4`）**互相冲突**，因此用**独立 venv 隔离**，两者互不污染。

## 二、在本机构建 venv（首次）

```bash
python -m venv data_analysis\.venv
data_analysis\.venv\Scripts\python.exe -m pip install -r data_analysis\requirements.txt
```

构建完成后，后端会自动使用它，无需手动配置。

## 三、后端如何选择 python（backend/finance_analysis.py::resolve_analysis_python）

优先级：
1. `DATA_ANALYSIS_PYTHON` 环境变量（显式指定，如专用 venv 的 python.exe）
2. **自动检测** `<项目根>\data_analysis\.venv\Scripts\python.exe`
3. 源码模式下回退当前后端 python
4. PATH 中的 python / sys.executable

## 四、复制到另一台电脑

- **venv 是本机专用**（内部是绝对路径），复制项目后需在目标机**重建**：

  ```bash
  python -m venv data_analysis\.venv
  data_analysis\.venv\Scripts\python.exe -m pip install -r data_analysis\requirements.txt
  ```

- 或设置 `DATA_ANALYSIS_PYTHON` 指向目标机的 venv python
- 没有 venv 时后端会自动回退到当前 python（不会崩，只是可能缺依赖）

## 五、常见问题

| 问题 | 解决 |
|---|---|
| 提示"data_analysis 依赖不可用" | 检查 `data_analysis\.venv` 是否存在并已装依赖；**不要在共享环境直接 pip install**（会污染后端） |
| 后端 openai/anyio 被升级冲突 | 恢复后端钉死版本：`python -m pip install "openai==1.6.1" "anyio<4"` |
| 需要 DATA_ANALYSIS_PYTHON | `setx DATA_ANALYSIS_PYTHON "<venv>\Scripts\python.exe"`（新开窗口生效） |
