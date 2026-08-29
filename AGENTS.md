# AI Desktop System - Agent Configuration

## System Overview

This system implements an AI Desktop application with four core capabilities:
1. **Coding Agent** - Task understanding, code modification, testing, and iteration with Reasonix cache optimization and CodeGraph code understanding. Supports SWE-bench Lite batch evaluation.
2. **RAG & Document System** - Multi-format document parsing (PDF/Word/PPT/Excel/CSV/Image; UI 上传限 PDF/Word，后端保留全格式), hybrid vector+BM25 search, PDF 上传可选 TableNet 提取表格并入 RAG（`extract_tables=true`）, 文档问答 + **金融计算问答**（LLM 调 calculate 安全计算器）, 表格结构识别（已并入文档管理页）, LLM Wiki knowledge base.
3. **Skill System** - 5 built-in reusable skills (markdown-report / word-lab-report / doc-ppt-online / doc-ppt-offline / excel-ppt) + external skill loading, with file upload and result download support.
4. **金融数据分析** - 上传 CSV/Excel + 自然语言分析目标，调用项目根自包含的 data_analysis 包子进程（`python -m data_analysis.run_analysis`）生成并执行 Python 代码，完成金融指标计算、数据处理、统计分析与可视化，返回代码/执行日志/图表/中文解释；产物落 `outputs/finance-analysis/<run_id>/`。后端不打包 matplotlib/scipy（分析与绘图在子进程真实 python 完成）。

Delivered as both a **Web version** (browser-based, via `启动桌面端.bat`) and a **native desktop client** (Electron, `AI桌面端系统.exe`).

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│   Web: 启动桌面端.bat    |   Desktop: AI桌面端系统.exe        │
│   (Browser @ localhost:3000) | (Electron native window)      │
├──────────────────────────────────────────────────────────────┤
│               React Frontend (Vite 5 + Ant Design)            │
│          Red-white theme, 8 pages, dark→light migration       │
├──────────────────────────────────────────────────────────────┤
│               FastAPI Backend (Port 18327, 35+ APIs)          │
├──────────┬──────────────────────────┬──────────────────────────┤
│Coding    │ Document + Table         │ Skill                    │
│Agent     │ (表格识别已并入文档管理)  │ Manager                  │
├──────────┤ Parser / RAG / Vector    ├──────────────────────────┤
│Reasonix  │ / LLM Wiki / finance-qa  │ Markdown Report          │
│Cache     │ / TableNet(提取+识别)    │ Word, PPT                │
│CodeGraph │ Text/CSV/MD/HTML/PDF/图  │                          │
│          │ / 金融数据分析            │                          │
│          │   (data_analysis 子进程)  │                          │
└──────────┴──────────────────────────┴──────────────────────────┘
```

## Agent Capabilities

### Coding Agent
- File read/write operations with UTF-8 support
- Shell command execution with timeout handling
- Checkpoint/rollback system for safe code modification
- Checkpoints stored in persistent `self.checkpoints` list (cross-task survival)
- Rollback only deletes the used checkpoint, others remain for multi-level rollback
- Rollback also deletes newly created files (via `_save_initial_files()` initial-file scan)
- Multi-round task execution with error recovery (max 20 rounds)
- 8 tools: read_file, write_file, execute_command, create_checkpoint, rollback_checkpoint, list_directory, run_tests, get_git_diff
- **File version tracking** (`self.file_versions`): every write_file creates a version record (original/new/modified) with full content
- **Diff generation**: unified diff between any two versions via Python difflib
- **Conversation sessions**: each chat session saves its own messages/checkpoints/file_versions; switching sessions keeps rollback independent; persisted to `outputs/conversation_history.json`
- DeepSeek API tool_calls message format fix (content=null when tool_calls present)

### Skill System (NVIDIA-aligned)
- 5 built-in skills: markdown-report, word-lab-report, doc-ppt-online, doc-ppt-offline, excel-ppt
- SKILL.md standard files (YAML metadata + workflow) per skill
- Skill Card governance metadata (owner, lifecycle, risk_level, permissions, signature)
- Signature verification + least-privilege permission scope (unverified third-party flagged)
- Skill-aware writing standards: markdown = lightweight GFM technical note; word = formal numbered report (1/1.1/1.1.1, 图X/表X labels, GB/T 7714)
- doc-ppt-offline & excel-ppt run full native pipelines to produce .pptx

### Reasonix Cache Optimization
- Stable prefix prompts for cache efficiency (session ID, repo summary)
- Cache hit rate monitoring with real-time metrics
- Token cost tracking and cost savings estimation
- Rolling task state compression (summarizes every 5 rounds)
- Session-based metrics: hit rate, latency, input/output tokens

### CodeGraph
- Symbol extraction (functions, classes, methods, variables)
- Call graph analysis (function call relationships)
- Import dependency mapping (cross-file dependency analysis)
- Test file association (auto-matching test files)
- Task-relevant context suggestion (keyword-based symbol matching)
- Supported languages: Python, JavaScript, TypeScript, C, C++

### Tool Call Message Format
- Both `agent/__init__.py` (execute_task) and `agent/reasonix.py` (execute_with_cache) construct assistant messages correctly
- When content is empty and tool_calls exist: content is set to `None`
- This satisfies DeepSeek API's strict message format validation

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/system/status` | GET | System status (docs, wiki, skills, model) |
| `/api/models/config` | GET/POST | Model configuration (DeepSeek/OpenAI) |
| `/api/models/chat` | POST | Chat completion |
| `/api/agent/execute` | POST | Execute agent task (with/without cache) |
| `/api/agent/cache-metrics` | GET | Get Reasonix cache statistics |
| `/api/agent/cache-metrics/reset` | POST | Reset cache metrics |
| `/api/agent/reset` | POST | Reset agent state |
| `/api/agent/file-versions` | GET | Get version history for all edited files |
| `/api/agent/file-content` | GET | Get a specific file version's full content |
| `/api/agent/file-diff` | GET | Get unified diff between two versions |
| `/api/agent/sessions` | GET | List conversation sessions |
| `/api/agent/sessions` | POST | Create a new session |
| `/api/agent/sessions/{id}` | GET | Get session detail (messages/checkpoints/versions) |
| `/api/agent/sessions/{id}/switch` | POST | Switch active session |
| `/api/agent/sessions/{id}` | DELETE | Delete a session |
| `/api/codegraph/build` | POST | Build code graph from repository path |
| `/api/codegraph/query` | GET | Search symbols by name |
| `/api/codegraph/file` | GET | Get file symbol summary |
| `/api/codegraph/stats` | GET | CodeGraph statistics |
| `/api/codegraph/context` | POST | Task-relevant code context |
| `/api/documents/upload` | POST | Upload & parse document（后端 8 格式；UI 上传限 PDF/Word）；PDF+`extract_tables=true` 时调用 TableNet 提取表格并入 RAG |
| `/api/documents` | GET | List documents |
| `/api/documents/{id}` | GET | Document detail |
| `/api/documents/{id}` | DELETE | Delete document |
| `/api/rag/search` | POST | Hybrid search (vector+BM25+rerank)，支持 document_ids/chunk_type 过滤 |
| `/api/rag/qa` | POST | Document Q&A with evidence，支持 document_ids |
| `/api/rag/finance-qa` | POST | 金融计算问答：注入选中文档表格块 + LLM 调用 calculate 计算器工具（safe_eval）精确计算，返回 answer/evidence/calculation_steps |
| `/api/finance-analysis/run` | POST | 金融数据分析：上传 CSV/Excel + 分析目标 → data_analysis 子进程生成并执行代码，返回代码/执行日志/解释/图表（`outputs/finance-analysis/<run_id>/`） |
| `/api/finance-analysis/status` | GET | 金融数据分析可用性（python 解释器 + data_analysis 依赖检测） |
| `/api/tables/recognize` | POST | Table recognition (text/md/csv/html) |
| `/api/tables/document/{id}` | GET | Get all tables from document |
| `/api/tables/pdf-recognize` | POST | 表格识别：上传 PDF 或图片/图表，调用 Qwen2-VL-TableNet 识别表格（PDF 走渲染+检测流水线，图片直通模型），输出到 outputs/tablenet/<run_id>/ |
| `/api/tables/tablenet/status` | GET | Qwen2-VL-TableNet 模型服务状态（模型目录/venv/可用性） |
| `/api/wiki/stats` | GET | LLM Wiki statistics |
| `/api/wiki/search` | GET | Search wiki pages |
| `/api/wiki/document/{id}` | GET | Document wiki pages |
| `/api/skills` | GET | List all skills |
| `/api/skills/cards` | GET | Get Skill Card governance metadata |
| `/api/skills/match` | POST | Match skills to task description |
| `/api/skills/execute` | POST | Execute a skill |
| `/api/skills/history` | GET | Skill execution history |
| `/api/skills/history/clear` | POST | Clear skill execution history |
| `/api/outputs/{filename}` | GET | Download generated file (recursive search) |
| `/api/uploads/{filename}` | GET | Download uploaded file |
| `/api/evaluation/coding` | GET | Coding Agent metrics |
| `/api/evaluation/rag` | GET | RAG system metrics |
| `/api/evaluation/skills` | GET | Skill system metrics |
| `/api/evaluation/all` | GET | Comprehensive evaluation |

## Configuration

Edit `model_config.json` or use the Settings page in the UI:
- API provider (DeepSeek, OpenAI, Custom)
- API key and base URL
- Model name and parameters
- Temperature (0-2), Max tokens (max 393216 for DeepSeek)
- Context length (1,000,000)

## Running

### Web Version (Browser)
```bash
# Backend (no hot-reload to avoid outputs/ triggering restart, port 18327)
cd backend
pip install -r requirements.txt
python run.py
# -> http://localhost:18327

# Frontend
cd frontend
npm install
npm run dev
# -> http://localhost:3000 (Vite proxies /api to :18327)
```

### Desktop Client (Electron Native Window)
```bash
# Prerequisites: Python installed, npm packages installed
# 1. Build frontend
cd frontend && npm run build

# 2. Package Electron app (use mirror for China)
set ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/
cd desktop && npm run dist

# 3. Run the unpacked version
desktop/dist/win-unpacked/AI桌面端系统.exe
```

Double-click `AI桌面端系统.exe` to launch the native window. The Electron app:
- Starts Python backend as a hidden child process
- Creates a 1400x900 native window with system tray
- Loads frontend from `resources/frontend/dist/index.html` (file:// protocol)
- API calls go to `http://127.0.0.1:18327/api` via preload bridge

## SWE-bench Lite Evaluation

```bash
# Install datasets library
pip install datasets

# Download dataset (uses hf-mirror.com for China)
python test_data/coding/_download_swe_bench.py

# Batch test (300 instances, 12 repos)
set PYTHONIOENCODING=utf-8
python test_data/coding/batch_test_swe_bench.py --limit 10
```

## Project Structure

```
/data_analysis/        - 金融数据分析独立可移植包（自包含，可单独拷贝运行）
  analyzer.py          - 核心 FinancialDataAnalysis：读 CSV/Excel → LLM 生成代码 → 沙箱执行 → 解释
  run_analysis.py      - 命令行入口（--data/--question/--out-dir/--json）
  config.py            - 配置（读 .env：本文件夹 → 父目录）
  llm.py               - DeepSeek LLM 封装（Token 统计）
  executor.py          - 沙箱执行器（subprocess，exec_runner.py）
  exec_runner.py       - 沙箱子进程（受限 imports/builtins，matplotlib 出图）
  prompts.py / extract.py - 任务专用 Prompt / 代码提取
/backend/              - FastAPI Python backend
  /agent/              - Coding Agent, Reasonix cache, CodeGraph
    __init__.py        - ModelAdapter, ToolRegistry, CodingAgent (tool_calls fix)
    reasonix.py        - CacheMetrics, OptimizedAgentLoop (tool_calls fix)
    codegraph.py       - CodeGraph (Python/JS/TS/C++ support)
  /rag/                - Document + Table + Vector + LLM Wiki + 金融问答
    document_parser.py - 8 format parser (PDF/Word/PPT/Excel/CSV/Image/MD/TXT)
    table_recognizer.py- TableStructure with data_rows, 4 input formats
    vector_store.py    - Vector + BM25 + hybrid + rerank search（支持 document_ids/chunk_type 过滤）
    llm_wiki.py        - WikiPage: doc cards, chapters, concepts, tables
    pdf_table_recognition.py - PDF/图片 表格识别流水线 + merge_tablenet_tables（并入文档 RAG）
    finance_qa.py      - 金融计算问答：safe_eval 安全计算器 + calculate 工具 + 编排
  /tablenet/           - Qwen2-VL-TableNet 表格识别模型集成（独立 venv 服务）
    inference.py       - 推理核心（严格按部署手册参数，只读模型目录）
    server.py          - 模型服务进程（tablenet-venv 运行，/health + /predict）
    engine.py          - 后端客户端：懒启动 + 常驻本地服务（port 18000）
    smoke_test.py      - 单图冒烟测试
  /skills/             - 4 built-in skills
    markdown_report_skill.py - Markdown report generation
    word_skill.py      - Word report with cover, TOC, tables
    ppt_skill.py       - PPT with slides, tables, figures
    skill_manager.py   - Skill base class + loader + executor
  /models/             - Pydantic data models
  main.py              - FastAPI app with 37+ endpoints
  config.py            - Settings + model config JSON I/O
  finance_analysis.py  - 金融数据分析端点：暂存上传文件 → 子进程调 data_analysis 包（python -m）→ 返回结构化结果
  run.py               - Entry point (reload=False)
/frontend/             - React TypeScript frontend (red-white theme)
  /src/pages/          - 8 page components
    AgentPage.tsx      - Coding Agent + CodeGraph + Cache metrics
    DocumentPage.tsx   - 上传(PDF/Word) + RAG 搜索 + 问答 + 金融计算问答 + 表格识别（并入）
    FinanceDataAnalysisPage.tsx - 金融数据分析：上传 CSV/Excel + 分析目标 → 图表/解释/代码/日志
    WikiPage.tsx       - LLM Wiki browse and search
    SkillPage.tsx      - Skill list, match, execute, file upload, download
    EvaluationPage.tsx - Unified evaluation dashboard
    ModelConfigPage.tsx- Model parameter configuration
  /src/components/
    TableRecognitionPanel.tsx - 表格识别面板（通用识别 + PDF/图片识别两个 Tab，嵌入文档管理页）
  /src/api/index.ts    - 35+ API functions via axios
  vite.config.ts       - Vite + proxy to port 18327, base: './'
/desktop/              - Electron desktop client
  main.js              - Electron main process (backend subprocess, 1400x900 window, tray)
  preload.js           - Bridge: getBackendUrl -> http://127.0.0.1:18327
  launcher.js          - Lightweight launcher (browser mode)
  package.json         - electron-builder config (NSIS installer)
  icon.ico             - App icon
  /dist/win-unpacked/  - Portable version
    AI桌面端系统.exe    - Executable (with resources/ bundled)
/skills/               - External skills (dynamic loading)
  format_check_skill.py- Document format checker
/test_data/            - Test data
  /coding/swe_bench_lite/
    instances.json     - 300 SWE-bench Lite instances
    instances.txt      - Same data in TXT format
    batch_results_*.json - Batch test results
  batch_test_swe_bench.py - Batch testing script
首次配置.bat            - 多人分发：每台机器跑一次（设 TABLENET_* 环境变量、校验/修复 venv）
修复venv.ps1            - 自动修复 tablenet-venv 的 pyvenv.cfg（探测本机 Python 3.11）
启动第二实例.bat        - 同机再开一个隔离实例（18329 + data2 + 共享 18000）
AI桌面端系统操作手册.md      - Operation manual (Chinese)
AI桌面端系统汇报.pptx         - Presentation PPT (14 slides)
AGENTS.md               - This file
```

## Multi-user deployment（多人独立运行）

形态：**每人一台电脑整份拷贝项目文件夹**，各自双击 `desktop/dist/win-unpacked/AI桌面端系统.exe`，完全隔离、无需登录。

- **首次配置**：每台机器跑 `首次配置.bat`（设 `TABLENET_MODEL_DIR`/`TABLENET_VENV_DIR`，校验 venv；不可移植时用 `修复venv.ps1` 改 `pyvenv.cfg` 指向本机 Python 3.11）。
- **分发前提**：① 拷贝整份文件夹（模型 4.4GB + venv，共 8-10GB）；② 分发前清 `outputs/`、`uploads/`、`chroma_db/`、`wiki_db/`、`conversation_history.json`；③ DeepSeek key 共用或各自填 `backend/model_config.json`。
- **只拷 win-unpacked 应用包**：文档/RAG/金融问答/Agent 可用，**表格识别不可用**（模型与 venv 在项目根，不在包内）；**金融数据分析不可用**（需项目根 `data_analysis/` 包 + 装有其依赖的 python，`python -m data_analysis.run_analysis` 才能运行）。
- **金融数据分析依赖**：运行时子进程解析 python 的顺序为 `DATA_ANALYSIS_PYTHON` 环境变量 → 源码模式下 `sys.executable` → `shutil.which("python")` → `sys.executable`。目标机需 `pip install -r data_analysis/requirements.txt`（openai/pandas/numpy/matplotlib/openpyxl）；DeepSeek key 自动取自 `backend/model_config.json` 活跃 Provider，无需另配 `.env`。
- **同机多实例**：`DATA_DIR` 环境变量隔离数据目录（`config.py`），`启动第二实例.bat` 用 backend.exe + `API_PORT=18329` + `DATA_DIR=data2` + 共享 `TABLENET_PORT=18000`（engine 先健康检查复用模型服务，不会双起）。同机只能一个 exe 占 18327。
