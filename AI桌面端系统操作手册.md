# AI 桌面端系统操作手册

> **项目**：Agent高级开发大作业
> **版本**：1.6.0
> **技术栈**：Python FastAPI + React TypeScript + Ant Design

---

## 目录

1. [系统概述](#1-系统概述)
2. [环境准备与安装](#2-环境准备与安装)
3. [系统启动](#3-系统启动)
4. [桌面启动器](#4-桌面启动器)
5. [模型配置与 Provider 切换](#5-模型配置与-provider-切换)
6. [Coding Agent 使用](#6-coding-agent-使用)
7. [文档管理与问答](#7-文档管理与问答)
8. [金融数据分析](#8-金融数据分析)
9. [表格结构识别](#9-表格结构识别)
10. [LLM Wiki 知识库](#10-llm-wiki-知识库)
11. [Skill 系统](#11-skill-系统)
12. [实验评测面板](#12-实验评测面板)
13. [API 参考](#13-api-参考)
14. [常见问题与故障排除](#14-常见问题与故障排除)

---

## 1. 系统概述

AI 桌面端系统是一个集成 **Coding Agent**、**RAG 文档系统**、**Skill 技能系统** 和 **金融数据分析** 的综合智能桌面平台，面向真实工程代码、复杂文档和数据分析任务。采用**红白主题**（白色主体 + 红色点缀）界面设计。

### 系统架构

```
┌──────────────────────────────────────────────────────────────┐
│    启动桌面端.bat（Web版）或 AI桌面端系统.exe（桌面客户端）    │
├──────────────────────────────────────────────────────────────┤
│                    React 前端 (Vite, 端口3000)                │
├──────────────────────────────────────────────────────────────┤
│                     Python 后端 (端口18327)                    │
├────────────┬─────────────┬──────────────┬───────────────────┤
│ Coding     │ 文档 + RAG  │ 金融数据分析 │ Skill 技能        │
│ Agent      │ 解析/检索/  │ (子进程调用  │ 系统              │
│            │ 表格识别    │ data_analysis)│                   │
├────────────┼─────────────┼──────────────┼───────────────────┤
│ Reasonix   │ 向量存储    │ LLM 生成代码 │ Markdown/Word/PPT  │
│ CodeGraph  │ LLM Wiki    │ 沙箱执行+绘图 │ 数据分析/格式检查 │
│            │ TableNet    │ + 结果解释    │                   │
└────────────┴─────────────┴──────────────┴───────────────────┘
```

### 核心模块

| 模块 | 功能 |
|------|------|
| **Coding Agent** | 代码理解、任务规划、文件编辑、命令执行、测试验证、Checkpoint 回滚（跨任务持久化）、对话历史记录（会话独立回滚） |
| **RAG 文档系统** | 多格式文档解析、向量检索、表格识别、LLM Wiki、证据溯源问答 |
| **Skill 技能系统** | Markdown 报告、Word 实验报告、doc-ppt 在线/离线、excel-ppt（5 个技能，NVIDIA 规范） |
| **金融数据分析** | 上传 CSV/Excel + 自然语言分析目标，子进程调用 data_analysis 包生成并执行 Python 代码，完成金融指标计算、统计分析与可视化（详见第 8 章） |

---

## 2. 环境准备与安装

### 系统要求

| 组件 | 要求 |
|------|------|
| 操作系统 | Windows 10/11 |
| Python | 3.9+ |
| Node.js | 18+ |
| npm | 9+ |
| 内存 | 4GB+ |
| 磁盘空间 | 2GB+ |

### 2.1 后端依赖安装

```bash
cd backend
pip install -r requirements.txt
```

### 2.2 前端依赖安装

```bash
cd frontend
npm install
```

### 2.3 可选依赖

- **JDK 17**：用于 Java 代码编译执行（已安装于 `C:\Program Files\Microsoft\jdk-17.0.19.10-hotspot`）
- **Ollama**：用于本地大模型离线推理（需自行安装）
- **Markdown 报告**：无需额外依赖，直接生成 .md 文件

### 2.4 PDF 表格识别环境（Qwen2-VL-TableNet）

该功能需要独立的模型推理环境（不影响主后端依赖）：

```bash
# 1) 创建独立虚拟环境（仅用于模型推理）
python -m venv tablenet-venv

# 2) 安装依赖（需 NVIDIA GPU，支持 CUDA 12.1 / BF16）
tablenet-venv/Scripts/pip install torch==2.1.2+cu121 --index-url https://download.pytorch.org/whl/cu121
tablenet-venv/Scripts/pip install "transformers==4.48.3" "qwen-vl-utils" accelerate pillow numpy==1.26.4
tablenet-venv/Scripts/pip install "torchvision==0.16.2+cu121" --index-url https://download.pytorch.org/whl/cu121

# 3) 确认模型包已解压到项目根：
#    Qwen2-VL-2B-TableNet-PubTabNet-smallx2-v1/Qwen2-VL-2B-TableNet-PubTabNet-smallx2-v1/
```

模型加载约占用 4.7GB 显存，首次调用模型服务需加载约 10-60 秒。详见 9.2 节。

---

## 3. 系统启动

### 3.1 方式一：双击批处理启动器

双击项目根目录下的 **`启动桌面端.bat`**，自动启动后端 + 前端 + 打开浏览器。

### 3.2 方式二：命令行（开发模式）

**终端 1 — 启动后端**：
```bash
cd backend
python run.py
```
服务运行在：http://localhost:8000

**终端 2 — 启动前端**：
```bash
cd frontend
npm run dev
```
页面访问：http://localhost:3000

### 3.3 注意事项

- 后端使用 `reload=False` 启动，避免 `outputs/` 目录变动导致热重载重启
- 批处理启动器中后端端口为 **18327**（避免与其它服务冲突）

---

## 4. 桌面启动器

系统提供两种启动方式：

### 4.1 Web 版（批处理启动器）

> 路径：`启动桌面端.bat`（项目根目录）

Windows 批处理脚本，在隐藏窗口中启动后端和前端，等待就绪后自动打开浏览器。关闭终端窗口即可停止所有服务。

### 4.2 桌面客户端（Electron 原生窗口）

> 路径：`desktop/dist/win-unpacked/AI桌面端系统.exe`

基于 Electron 包装的原生 Windows 桌面应用程序，无需浏览器，自带独立窗口。

**特点：**
- 原生窗口（1400×900，最小 1000×700）
- 隐藏启动 Python 后端子进程（无控制台窗口）
- 系统托盘常驻，支持最小化到托盘
- 关闭窗口自动退出后端
- 前端编译产物内置于 `resources/frontend/dist/`
- 后端 Python 源码内置于 `resources/backend/`

**启动流程：**
1. 双击 `AI桌面端系统.exe`
2. 自动创建系统托盘图标
3. 后台启动 Python 后端（端口 18327）
4. 弹出主窗口（先显示空白，后端就绪后加载前端）
5. 后端最长等待 45 秒，超时显示错误页面

**技术栈：** Electron 22 + electron-builder 24（NSIS 安装包）

**打包命令：**
```bash
cd frontend && npm run build    # 构建前端到 dist/
cd desktop && npm run dist      # 打包为 NSIS 安装包
```

输出产物位于 `desktop/dist/`：
- `win-unpacked/AI桌面端系统.exe` — 绿色免安装版
- `AI桌面端系统 Setup 1.0.0.exe` — NSIS 安装包

---

## 5. 模型配置与 Provider 切换

> 路径：左侧菜单 → **模型配置**

系统支持同时配置两个模型 Provider，并一键切换：

| Provider | 适用场景 | 依赖 |
|----------|----------|------|
| **DeepSeek 在线** | 联网时使用，效果最好 | 需要 API Key 和网络 |
| **本地 Ollama** | 断网时使用，安全可控 | 需要安装 Ollama 和模型 |

### 5.1 配置界面

配置页面分为左右两栏，分别对应在线和本地两个 Provider，顶部状态栏显示当前使用和连接状态。

### 5.2 切换方式

- 点击 Provider 卡片上的 **"切换到此"** 按钮
- 切换后立即生效，状态栏实时显示连接状态

---

## 6. Coding Agent 使用

> 路径：左侧菜单 → **Coding Agent**

Coding Agent 是一个能够理解任务、读写代码、执行命令、运行测试的智能编程助手。采用**对话式交互**界面，类似 ChatGPT。

### 6.1 对话式操作

```
┌──────────────────────────────────────────────┐
│  Coding Agent                    [+ 新对话]   │
├──────────────────────────────────────────────┤
│                                              │
│  ┌─ 用户 ───────────────────────────────┐    │
│  │ 在outputs创建Fibonacci.java...        │    │
│  └──────────────────────────────────────┘    │
│                                              │
│  ┌─ Agent ───────────────────────────────┐    │
│  │ ✅ 完成 | 7 轮 | 3.5s | 1 快照         │    │
│  │ 已读文件: Fibonacci.java              │    │
│  │ 修改文件: Fibonacci.java              │    │
│  │ [查看详情 ▸]                          │    │
│  └──────────────────────────────────────┘    │
│                                              │
│  ┌─ 用户 ───────────────────────────────┐    │
│  │ 编译并运行它                         │    │
│  └──────────────────────────────────────┘    │
│                                              │
│  ┌─ Agent ───────────────────────────────┐    │
│  │ ✅ 完成 | 3 轮                        │    │
│  │ F(1) = 0, F(2) = 1, ...              │    │
│  └──────────────────────────────────────┘    │
│                                              │
│  ┌──────────────────────────────────────┐    │
│  │ 输入任务描述... (Enter 发送)  [发送]  │    │
│  └──────────────────────────────────────┘    │
└──────────────────────────────────────────────┘
```

**操作方式**：
1. 在底部输入框输入任务描述
2. 按 `Enter` 发送，`Shift+Enter` 换行
3. Agent 的执行结果显示在蓝色气泡中
4. 反复输入可以持续对话，上下文保持连续

### 6.2 新对话

点击右上角 **"[+] 新对话"** 按钮：
- 清空当前对话消息列表
- 重置 Agent 内部状态
- **不会删除**已生成的文件
- 适合开始一个全新的任务

### 6.3 测试文件

系统提供测试文件用于验证 Coding Agent 功能，位于 `test_data/coding/` 目录：

```
test_data/coding/
├── java_test/
│   ├── Calculator.java       ← 除零 bug，需修复
│   └── README.md
│
├── multi_file/
│   ├── GradeManager.java     ← 空列表 bug，需修复
│   ├── Student.java
│   ├── Main.java
│   └── README.md
│
└── python_test/
    ├── data_processor.py     ← 多个 bug + 待实现函数
    ├── test_data_processor.py ← 单元测试
    └── scores.csv

└── repo_test/                ← 新增：工业级 Java 项目测试（3 Bug + TODO）
    ├── RepoEntity.java       ← 实体类
    ├── RepoService.java      ← 服务接口（含 TODO）
    ├── RepoServiceImpl.java  ← 3 个 Bug
    ├── RepoConstants.java    ← 常量类
    ├── RepoMain.java         ← 测试运行器
    └── README.md
```

### 6.4 测试用例详解

#### 测试 1：Java 单文件 Bug 修复（Calculator.java）

| 项目 | 内容 |
|------|------|
| **测试文件** | `test_data/coding/java_test/Calculator.java` |
| **Bug 类型** | 除零异常（ArithmeticException） |
| **Bug 位置** | 第 21 行：`return a / b;` —— 当 `b == 0` 时抛出异常 |
| **触发方式** | `main` 方法第 29 行调用 `calc.divide(10, 0)` |

**测试步骤**：
1. 在 Coding Agent 输入框设置目标文件夹为 `test_data/coding/java_test/`
2. 输入任务描述并发送
3. 验证 Agent 行为

**任务 1a —— 修复 Bug**：
> 修复 Calculator.java 中除以零的 bug

| 验证点 | 预期结果 |
|--------|----------|
| Agent 读取文件 | 正确读取 Calculator.java 全部源码 |
| Agent 调用 write_file 修改 | 修改第 21 行的 divide 方法，添加除零检查 |
| 修改后内容示例 | 应在方法开头添加 `if (b == 0) { System.out.println("Error: division by zero"); return 0; }` |
| Agent 调用 javac 编译 | 编译无错误 |
| Agent 调用 java 运行 | 输出包含 `10 / 0 = 0` 和错误提示信息，不抛异常 |
| 自动创建 Checkpoint | 修改前自动创建快照，可回滚到原始版本 |
| 最终验证 | 所有 math 运算均正常输出，程序正常退出 |

**任务 1b —— 新增功能**：
> 给 Calculator 添加一个 power 方法，计算 a 的 b 次方

| 验证点 | 预期结果 |
|--------|----------|
| Agent 读取文件 | 正确读取现有代码 |
| Agent 生成新方法 | 添加 `public double power(int a, int b)` 方法 |
| 编译运行 | `javac` 编译通过，`java` 运行输出 power 计算结果 |
| 方法正确性 | 例如 2^3 = 8, 5^0 = 1, 3^2 = 9 |

**任务 1c —— 批量操作**：
> 修复除零 bug，添加 power 方法和 factorial 方法，然后编译运行

| 验证点 | 预期结果 |
|--------|----------|
| 多任务连续执行 | Agent 在一次对话中连续完成 3 个修改 |
| 上下文保持 | Agent 记住之前的修改，不重复已修复逻辑 |
| Checkpoint 管理 | 产生 3 个自动快照，可分别回滚到任意版本 |

---

#### 测试 2：多文件 Java 项目修复（GradeManager）

| 项目 | 内容 |
|------|------|
| **测试文件** | `test_data/coding/multi_file/GradeManager.java` |
| **关联文件** | `Student.java`（学生类）、`Main.java`（入口测试） |
| **Bug 类型** | 空列表除零异常（ArithmeticException） |
| **Bug 位置** | 第 29 行：`return total / students.size();` —— students 为空时崩溃 |

**任务 2a —— 修复空列表 Bug**：
> 修复 GradeManager.java 中空列表 bug

| 验证点 | 预期结果 |
|--------|----------|
| Agent 读取多个文件 | 正确读取 GradeManager.java 以及相关类 Student.java |
| Bug 修复方案 | 在 getAverageGrade() 方法中检查 students 是否为空，为空返回 0 |
| 编译验证 | javac 编译所有 .java 文件（自动包含 Student.java） |
| 行为验证 | 空列表时返回 0.0，有学生时正常计算平均分 |

**任务 2b —— 添加新功能**：
> 给 GradeManager 添加 getTopStudent 方法，返回成绩最高的学生

| 验证点 | 预期结果 |
|--------|----------|
| 方法签名 | `public Student getTopStudent()` |
| 空列表处理 | 列表为空时返回 null |
| 逻辑正确性 | 遍历 students，比较 grade，返回最高分学生 |
| 编译运行 | 编译通过，运行后输出正确的最高分学生信息 |
| Main.java 兼容 | 不破坏 Main.java 中已有的测试逻辑 |

**任务 2c —— 复杂重构**：
> 重构 GradeManager：添加 getAverageGrade(String subject) 按科目统计平均分，添加 getPassRate(double passingScore) 方法计算及格率，添加 removeStudent(String name) 方法，并更新 Main.java 测试所有新功能

| 验证点 | 预期结果 |
|--------|----------|
| 跨文件修改 | 修改 GradeManager.java 和 Main.java |
| 方法正确性 | 各新方法功能正确，边界情况（空列表、null 参数）有处理 |
| 编译运行 | 全部编译通过，输出清晰的测试结果 |

---

#### 测试 3：Python 多 Bug 修复（data_processor.py）

| 项目 | 内容 |
|------|------|
| **测试文件** | `test_data/coding/python_test/data_processor.py` |
| **单元测试** | `test_data/coding/python_test/test_data_processor.py` |
| **数据文件** | `test_data/coding/python_test/scores.csv` |
| **Bug 类型** | × 2（除零 + 目录创建）+ 1 个 TODO 待实现函数 |

**Bug 1 —— calculate_average 空列表崩溃**（第 28 行）：
```python
def calculate_average(numbers):
    total = sum(numbers)
    return total / len(numbers)  # BUG: 当 numbers 为空时 ZeroDivisionError
```

**Bug 2 —— save_report 不创建目录**（第 53 行）：
```python
def save_report(stats, output_path):
    with open(output_path, 'w') as f:  # BUG: 如果 output_path 的目录不存在则 FileNotFoundError
```

**TODO —— filter_outliers 函数**（第 67 行注释）：
```python
# TODO: Add a function filter_outliers(data, column, threshold)
# 过滤掉 column 列中超过平均值 threshold 个标准差的行
```

**任务 3a —— 修复全部 Bug**：
> 修复 data_processor.py 中的所有 bug

| 验证点 | 预期结果 |
|--------|----------|
| 识别 Bug 1 | 发现 calculate_average 的空列表除零问题 |
| 修复 Bug 1 | 添加 `if not numbers: return 0` 或者 `if len(numbers) == 0: return 0` |
| 识别 Bug 2 | 发现 save_report 不会自动创建输出目录 |
| 修复 Bug 2 | 在打开文件前添加 `os.makedirs(os.path.dirname(output_path), exist_ok=True)` |
| 编译运行 | `python data_processor.py` 正常执行无异常 |

**任务 3b —— 实现 TODO 函数并运行单元测试**：
> 实现 data_processor.py 中的 filter_outliers 函数，然后运行 test_data_processor.py 验证

| 验证点 | 预期结果 |
|--------|----------|
| 函数签名 | `def filter_outliers(data, column, threshold)` |
| 函数逻辑 | 计算 column 列的均值和标准差，返回 `abs(value - mean) <= threshold * std` 的行 |
| 边界处理 | data 为空返回空列表，column 不存在返回原数据 |
| 单元测试执行 | `python test_data_processor.py` 全部测试通过（至少 3 个测试用例）|
| 测试覆盖率 | 空列表、正常值、异常值过滤均验证 |

**任务 3c —— 完整数据流程实操**：
> 读取 scores.csv 文件，计算所有数值列的统计信息（min/max/avg/count），过滤掉异常值，将结果保存到 outputs/report.txt

| 验证点 | 预期结果 |
|--------|----------|
| CSV 读取 | 使用 load_data 或 csv 模块正确读取 scores.csv |
| 统计计算 | 各列的 min、max、avg、count 正确 |
| 异常值过滤 | 使用 filter_outliers 过滤后数据合理 |
| 文件保存 | outputs/report.txt 正确生成，内容包含完整分析报告 |
| 端到端验证 | 整个流程：读取 → 分析 → 过滤 → 保存全部成功 |

---

#### 测试 4：Python 扩展功能测试（scores.csv 数据分析）

| 项目 | 内容 |
|------|------|
| **数据文件** | `test_data/coding/python_test/scores.csv` |

**任务 4**：
> 编写一个 Python 脚本，读取 scores.csv，计算每门课程的平均分、最高分、最低分和及格率（>=60 分），输出统计报表

| 验证点 | 预期结果 |
|--------|----------|
| Agent 新建脚本 | 使用 write_file 创建新 Python 文件 |
| CSV 解析 | 正确读取 scores.csv 的列结构 |
| 统计正确性 | 每门课程的平均分、最高分、最低分、及格率计算正确 |
| 运行输出 | 脚本执行后输出格式化的统计报表 |
| 文件保存 | 脚本保存到项目目录下，可直接查看 |

---

#### 测试 5：Checkpoint 快照回滚测试

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 1 | 设置目标文件夹为 test_data/coding/java_test，发送"修复 Calculator.java 的除零 bug" | Agent 完成修复，自动创建 Checkpoint |
| 2 | 在右侧 Checkpoint 面板点击"刷新快照列表" | 列表中显示自动创建的 Checkpoint |
| 3 | 修改文件后，再次发送"添加 power 方法" | Agent 添加方法，创建第二个 Checkpoint |
| 4 | 点击第一个 Checkpoint 的"回滚到此快照"按钮 | 文件恢复到原始状态（除零 bug 恢复） |
| 5 | 验证回滚效果 | 重新编译运行，确认 divide(10, 0) 再次抛出异常 |
| 6 | 点击第二个 Checkpoint 回滚 | 恢复到 power 方法添加后的状态 |

**回滚机制验证**：
- 回滚后 Checkpoint 自动移除（防止连环回滚）
- 回滚仅影响快照中记录的文件，不修改其他文件
- 回滚操作通过 `/api/agent/rollback/{checkpoint_id}` API 完成

---

#### 测试 6：目标文件夹 + 上传文件协同测试

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 1 | 目标文件夹留空，不上传文件，直接发送"创建一个 Hello.java" | Agent 在项目根目录创建 Hello.java |
| 2 | 设置目标文件夹为 test_data/coding/java_test/ | 底部状态栏显示目标路径 |
| 3 | 发送"创建一个新的 TestHello.java" | 文件创建在目标文件夹内 |
| 4 | 点击上传文件按钮，选择 Student.java | 文件被上传至后端 uploads/code/ 目录 |
| 5 | 发送"读取已上传的 Student.java 并输出其内容" | Agent 读取上传的文件并处理 |

---

#### 测试 7：工业级 Java 项目修复（Repo 银行间回购系统）

| 项目 | 内容 |
|------|------|
| **测试目录** | `test_data/coding/repo_test/` |
| **Bug 类型** | × 3（日志格式 + 逻辑错误 + 集合类型错误）+ 1 个 TODO |
| **源文件** | 从金融行业实际项目脱敏简化 |

**Bug 1 —— 日志格式错误**（RepoServiceImpl.java 中多处）：
```java
System.out.println("RepoServiceImpl add completed, success: {]" + true);
// BUG: 应使用 {} 而非 {]，日志参数无法正常填充
```

**Bug 2 —— createTime 为 null**（RepoServiceImpl.java add 方法）：
```java
entity.setCreateTime(null);  // BUG: 应设为 new Date()
```

**Bug 3 —— HashSet 不保持顺序**（RepoServiceImpl.java getDictionary 方法）：
```java
Set<Map<String, String>> createBySet = new HashSet<>();
// BUG: 应使用 LinkedHashSet 保持插入顺序
```

**TODO —— batchApprove 批量审批**（RepoService.java + RepoServiceImpl.java）：
```java
// TODO: Add batchApprove(List<String> ids, String isApproval) method
```

**任务 7a —— 修复全部 Bug**：
> 修复 RepoServiceImpl.java 中的所有 bug

| 验证点 | 预期结果 |
|--------|----------|
| Agent 读取文件 | 正确读取 RepoServiceImpl.java 全部源码 |
| 识别 Bug 1 | 发现 `{]` 应为 `{}`，替换所有出现位置 |
| 识别 Bug 2 | 发现 `setCreateTime(null)` 应为 `setCreateTime(new Date())` |
| 识别 Bug 3 | 发现 `HashSet` 应改为 `LinkedHashSet` |
| 编译运行 | `javac RepoMain.java && java RepoMain` 正常执行 |
| 输出验证 | 日志格式正确，createTime 不为 null，字典顺序与插入一致 |

**任务 7b —— 实现 TODO 并验证**：
> 实现 RepoService 中的 batchApprove 方法，然后运行 RepoMain 验证

| 验证点 | 预期结果 |
|--------|----------|
| 接口新增 | RepoService.java 中添加 `batchApprove(List<String> ids, String isApproval)` |
| 方法签名 | 返回 `int`（成功审批的记录数），参数为 ID 列表和审批状态 |
| 逻辑正确性 | 遍历 IDs，逐条调用 approval 逻辑，统计成功数 |
| 异常处理 | list 为空返回 0，null 元素跳过不崩溃 |
| 编译运行 | 编译通过，运行不报错 |

**任务 7c —— 完整重构**：
> 修复 RepoServiceImpl.java 中的 3 个 Bug，实现 batchApprove 方法，运行 RepoMain.java 验证全部功能

| 验证点 | 预期结果 |
|--------|----------|
| 4 项任务一次性完成 | Agent 在一次对话中连续完成 4 个修改 |
| 跨文件修改 | 修改 RepoServiceImpl.java 和 RepoService.java |
| 端到端验证 | `javac RepoMain.java && java RepoMain` 输出全部正确 |
| Checkpoint 管理 | 为每个修改的文件创建 Checkpoint，支持逐级回滚 |

---

### 6.7 查看 Cache 指标

右侧面板显示 Reasonix 缓存优化指标：

| 指标 | 说明 |
|------|------|
| 命中率 | 缓存命中百分比（越高越好） |
| 请求数 | 总 API 调用次数 |
| 平均延迟 | 每次 API 调用的平均响应时间 |
| 节省 Token | 缓存减少的输入 token 数 |
| 节省成本 | 估算的费用节省 |

### 6.8 CodeGraph 代码图谱

CodeGraph 是一个代码地图生成器，扫描项目文件并以文件树形式展示。

**操作步骤**：
1. 输入 **仓库路径**（如 `D:\AI桌面端系统`）
2. 点击 **构建代码图谱**
3. 系统扫描所有文件，生成层级文件树

**CodeGraph 特点**：
- 显示项目内所有文件和文件夹的层级结构
- 代码文件（`[C]`）和非代码文件（`[F]`）用标签区分
- 点击任意文件右侧弹出详情面板，显示路径、大小、符号列表
- 构建结果跨页面不丢失（`GET /api/codegraph/tree` 持久化）

### 6.9 Checkpoint 快照回滚

每次 `write_file` 覆盖已有文件时，自动创建快照，支持回滚到任意历史状态。

**操作**：
1. 右侧 Checkpoint 面板点击 **"刷新快照列表"**
2. 点击具体快照的 **"回滚到此快照"** 按钮
3. 文件恢复到修改前的内容

### 6.10 代码版本 / Diff 查看

右侧 **"代码版本 / Diff"** 卡片展示每个文件的版本历史与代码变更，支持查看某版本代码和该版本引入的修改。

**版本生成机制**：每次 `write_file` 修改文件时自动记录一个新版本，形成版本链：

```
Calculator.java:
  V1(原始) ──修改──▶ V2(修复除零) ──修改──▶ V3(添加power)
```

| 版本标签 | 含义 |
|----------|------|
| `V1 [original]` | 文件原始内容 |
| `Vn [modified]` | 第 n 次修改后的内容 |
| `V1 [new]` | 新建的文件 |

**操作**：
1. 执行一个生成/修改代码的任务
2. 右侧"代码版本 / Diff"卡片自动刷新，显示文件版本列表
3. 点击某版本（如 V2）
4. 选择 **Diff** 模式：查看该版本相对前一版本的修改（**红色=删除行，绿色=新增行**）
5. 选择 **代码** 模式：查看该版本的完整代码

**回滚联动**：回滚到某 Checkpoint 后，版本列表自动刷新，可继续查看对应版本的代码与 Diff。

### 6.11 对话历史记录（会话独立回滚）

系统支持保存多个对话会话，每个会话独立保存消息、Checkpoint 快照和文件版本，可随时切换查看，回滚互不影响，并持久化到磁盘。

**操作**：
1. 右侧顶部 **"对话历史"** 面板列出所有会话（标题 + 消息数 + 快照数）
2. 点击某会话 → 切换加载该会话的消息、Checkpoint 和版本
3. **"新对话"** 按钮 → 创建新会话
4. 会话删除按钮（🗑）→ 移除该会话（有确认弹窗）
5. 会话标题自动取首条用户消息

**独立性验证**：
- 会话 A 完成"修复除零"任务后，切到会话 B 做"GradeManager 重构"，互不影响
- 切回会话 A，可继续查看消息、回滚当时的 Checkpoint
- 数据持久化到 `outputs/conversation_history.json`，重启应用后历史保留

### 6.12 页面状态保持（Keep-Alive）

切换功能页面时，原页面的状态（对话内容、表单、Checkpoint、版本列表等）自动保留，不丢失。

**说明**：
- 已访问过的页面保持挂载，切换时用 `display: none` 隐藏而非卸载
- 首次进入某页才加载数据，后续切换不重复请求
- 各页提供 **"刷新"** 按钮，需要更新数据时手动点击
- 完全退出应用或刷新浏览器（F5）后状态重置

---

## 7. 文档管理与问答

> 路径：左侧菜单 → **文档管理**

支持上传、解析、检索和问答多种格式的文档；**表格识别已并入本页底部**（通用表格识别 + PDF/图片识别，详见第 8 章）。

### 7.1 支持的文档格式

**界面仅允许上传 PDF / Word (.docx)**（上传时会拦截其他格式）；后端 API 仍兼容全部格式（供表格识别等模块内部使用）。

| 格式 | 说明 |
|------|------|
| PDF | 使用 pdfminer 或 PyPDF2 解析；**勾选"提取表格"上传时额外调用 Qwen2-VL-TableNet 提取表格并入 RAG**（需模型服务，首次加载数十秒） |
| Word (.docx) | 使用 python-docx 解析（打包版需含 lxml，已修复） |

> 说明：上传区上方有 **"提取表格 (TableNet，PDF 首次上传需加载模型约 1-2 分钟)"** 复选框；勾选后上传的 PDF 会先用表格识别模型提取表格，表格数据进入 RAG，可被搜索与文档问答使用（金融问答尤其依赖此数据）。

### 7.2 测试用例详解

#### 测试 1：PDF 文档上传与解析

**准备**：使用 `test_data/coding/金融研报.pdf` 文件。

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 1 | 拖拽或点击上传区域，选择 `金融研报.pdf` | 文件上传成功，API 返回解析结果 |
| 2 | 检查返回数据 | `success: true`，包含 `document_id`、`page_count`、`tables_count`、`chunks_count` |
| 3 | 验证文档列表 | 左侧文档列表中显示"金融研报.pdf"，标签显示页数和表格数 |
| 4 | 点击文档 | 右侧显示文档详情，包含各页文本内容预览和表格列表 |

**验证点**：
| 验证项 | 预期 |
|--------|------|
| 文档类型识别 | `file_type` 为 `.pdf` |
| 页数计数 | 正确检测 PDF 总页数 |
| 文本提取 | 每页文本正确提取，无乱码 |
| 表格检测 | PDF 中表格被识别并提取为结构化数据 |
| 分块生成 | `chunks_count > 0`，文本按 500 字重叠分块 |
| 解析时间 | `parse_time` 字段记录了解析耗时 |

#### 测试 2：多格式上传兼容性测试

> **注意**：界面上传区域已限制为 PDF/Word，下列其他格式需通过后端 API 直接测试（`POST /api/documents/upload`），或改回前端 accept 后验证。

| 文件类型 | 上传操作 | 预期结果 |
|----------|----------|----------|
| PDF | 上传 PDF | 成功解析，提取文本与表格 |
| Word (.docx) | 上传 Word 文档 | 成功解析，提取段落文本和表格（打包版需含 lxml，已修复） |
| PPT (.pptx) | 上传 PPT 文件 | 按幻灯片提取文本，识别幻灯片内表格 |
| Excel (.xlsx) | 上传 Excel 文件 | 按工作表提取，表格结构完整（含表头和数据） |
| CSV (.csv) | 上传 CSV 文件 | 正确解析，自动检测编码（utf-8/utf-8-sig/gbk） |
| 图片 (.png) | 上传含文字的图片 | 如 OCR 可用则提取文字，无法识别则返回提示 |
| Markdown (.md) | 上传 Markdown 文件 | 直接读取内容，自动检测 Markdown 表格 |
| TXT (.txt) | 上传纯文本文件 | 自动尝试 utf-8/gbk/gb2312 编码 |

#### 测试 3：RAG 混合检索

**准备**：先上传至少一个 PDF 文档。

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 1 | 在"RAG搜索"输入框输入关键词 | 输入时无异常 |
| 2 | 点击搜索（或按回车） | 前端调用 POST `/api/rag/search` |
| 3 | 查看搜索结果 | 返回结果包含：片段内容、来源文档名、页码、chunk_type、score |

**验证不同检索方法**（后端直接测试）：

| 方法 | 请求参数 | 预期结果 |
|------|----------|----------|
| 向量检索 | `{"query": "...", "method": "vector", "top_k": 5}` | 基于语义相似度返回结果 |
| BM25 检索 | `{"query": "...", "method": "bm25", "top_k": 5}` | 基于关键词匹配返回结果 |
| 混合检索 | `{"query": "...", "method": "hybrid", "top_k": 5}` | 结合向量和 BM25，使用 0.5:0.5 加权 |
| 重排序 | `{"query": "...", "use_rerank": true}` | 在初筛基础上按查询词重叠度重新排序 |

**混合检索权重验证**：
- 混合检索时 alpha=0.5，向量分和 BM25 分分别归一化后加权平均
- 最终 score = 0.5 × norm_vec_score + 0.5 × norm_bm25_score
- 重排序增加 term_overlap（40%）和 proximity（20%）信号，与原始分（40%）组合

#### 测试 4：证据溯源问答

**准备**：上传一个 PDF 文档并完成索引。

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 1 | 在"文档问答"输入框输入问题 | 如"表格中销售额最高的年份是哪个？" |
| 2 | 点击"提问"按钮 | 显示 loading 状态，调用 POST `/api/rag/qa` |
| 3 | 查看回答 | 返回 AI 生成的答案，引用来源文档和页码 |
| 4 | 查看"证据"折叠面板 | 显示检索到的相关片段列表，每条包含：文档名、页码、chunk_type、片段内容 |

**验证点**：
| 验证项 | 预期 |
|--------|------|
| 答案相关性 | 答案基于上下文生成，与问题相关 |
| 证据引用 | 每个证据包含 document_id、filename、page_number、chunk_type |
| 上下文构建 | 将 top_k=5 个检索片段拼接为 context，格式为 `[chunk_type] content` |
| 错误处理 | 无文档时返回空结果，不崩溃 |

**推荐测试问题**：
- "文档中提到了哪些关键数据？"
- "表格数据有哪些特征？"
- "文档的结论是什么？"

#### 测试 5：文档删除

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 1 | 上传文档，确认出现在列表中 | 列表更新，显示新文档 |
| 2 | 点击文档右侧的删除按钮（垃圾桶图标） | 文档从列表中移除，向量索引同步删除 |
| 3 | 验证删除 | 再次搜索已删除文档的内容，返回空结果 |

**删除机制验证**：
- 前端调用 DELETE `/api/documents/{doc_id}`
- 后端同步移除：`documents_store`、`vector_store` 中该文档的所有 chunks
- 已生成的 LLM Wiki 页面不会自动清除（需调用 wiki/clear）

#### 测试 6：PDF 表格提取 + 金融计算问答

**准备**：`test_data/finance_sample.pdf`（含财务表格：营业收入/营业成本/毛利润/净利润/总资产 × 2020-2022）。

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 1 | 勾选"提取表格"，上传 `finance_sample.pdf` | 提示"提取到 N 个表格"，文档列表显示表格数 |
| 2 | 点击该文档 | 文档详情中表格 `source=tablenet`，展示表头与结构化数据 |
| 3 | 在"文档问答"卡片打开 **金融计算模式**（Switch 开关） | 输入框提示变为金融问题示例 |
| 4 | 输入"2022年营业收入同比增长率是多少？"并提问 | 返回答案引用精确数字 |
| 5 | 查看"计算过程"卡片 | 显示 `(885.7-661.8)/661.8*100 = 33.83...` |

**验证点**：
| 验证项 | 预期 |
|--------|------|
| 表格进入 RAG | RAG 搜索"营业收入"命中 `chunk_type=table` |
| 金融问答调计算器 | `calculation_steps` 含 `calculate` 工具结果（精确算术，非心算） |
| 数据引用 | 答案数字来自表格真实值，计算过程透明可见 |
| 普通问答不受影响 | 关闭金融模式后走 `/api/rag/qa` 普通问答 |

---

## 8. 金融数据分析

> 路径：左侧菜单 → **金融数据分析**

支持上传 CSV / Excel 金融数据文件，填写自然语言分析目标（如"计算2022和2023年的营业收入增长率、毛利率并绘图"），系统自动完成金融指标计算、数据处理、统计分析与可视化，并给出中文结果解释。

**实现方式**：后端将上传文件暂存到 `outputs/finance-analysis/<run_id>/source/`，以子进程方式运行项目根自包含的 `data_analysis` 包（`python -m data_analysis.run_analysis`，DeepSeek key 自动取自后端 `model_config.json` 活跃 Provider）。`data_analysis` 调用 LLM 生成 Python 代码 → 沙箱执行（受限环境 + 超时）→ 保存图表（matplotlib）→ LLM 解释结果。分析与绘图在子进程真实 python 中完成，**后端 backend.exe 不打包 matplotlib/scipy**。

**使用步骤**：

| 步骤 | 操作 | 说明 |
|------|------|------|
| 1 | 左侧菜单点击「金融数据分析」 | 进入分析页 |
| 2 | 拖拽或点击上传 CSV / Excel 文件 | 支持 `.csv` / `.xlsx` / `.xls` |
| 3 | 在文本框填写分析目标 | 例如"计算2022和2023年的营业收入增长率、毛利率并绘图" |
| 4 | 点击「开始分析」 | 生成代码 → 沙箱执行 → 解释，约需 30-90 秒 |
| 5 | 查看结果 | 中文解释、图表（可预览）、生成代码与执行日志（折叠面板）、Token 用量 |

**输出**：结果保存于 `outputs/finance-analysis/<run_id>/`（每次运行唯一目录，不覆盖），含 `source/`（上传的数据文件）、`figures/`（图表 PNG）、`result.json`（结构化结果）。

### 8.1 测试用例详解

#### 测试 1：Excel 财务数据分析并绘图

**准备**：`test_data/示例公司财务数据.xlsx`（营业收入/成本/毛利/净利润/总资产/所有者权益/总负债 × 2020-2023）。

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 1 | 上传 `示例公司财务数据.xlsx` | 显示数据列名 |
| 2 | 填写"计算2022和2023年的营业收入增长率、毛利率并绘图" | 按钮转 loading |
| 3 | 点击「开始分析」 | 约 30-90 秒后显示结果 |
| 4 | 检查结果 | `success=true`，含中文解释、图表 PNG、生成代码、执行日志 |

**验证点**：
| 验证项 | 预期 |
|--------|------|
| 指标计算 | 营业收入增长率 = (本期-上期)/上期；毛利率 = 毛利/营业收入 |
| 图表生成 | `figures/` 下有 PNG，前端可预览 |
| 结果解释 | LLM 结合金融背景给出中文分析 |
| 唯一目录 | 每次运行新建 `<文件名>_<时间戳>` 目录，不覆盖上次 |

#### 测试 2：依赖不可用提示

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 1 | 在缺少 data_analysis 依赖的 python 环境运行 | 页面顶部黄色警告"data_analysis 依赖不可用"，提示 `pip install -r data_analysis/requirements.txt` 或设 `DATA_ANALYSIS_PYTHON` |
| 2 | 缺依赖时点「开始分析」 | 后端返回 `error`，界面提示失败 |

---

## 9. 表格结构识别

> 路径：**文档管理** 页 → 底部 **"表格识别"** 卡片（原独立"表格识别"菜单页已并入，含两个页签：**通用表格识别**、**PDF 表格识别 (TableNet)**）

支持两类识别方式：
1. **通用表格识别**（页签 1）：从文本、Markdown、CSV、HTML 四种格式输入中识别表格结构（规则解析，无需模型）。
2. **PDF/图片 表格识别**（页签 2）：上传 PDF 或图片/图表，调用 Qwen2-VL-2B-TableNet-PubTabNet-smallx2-v1 模型将表格图片转换为完整 HTML（详见 9.2）。

### 9.1 测试用例详解

#### 测试 1：文本格式（Tab/空格分隔）

**输入**（在文本框中粘贴）：
```
姓名\t年龄\t城市
张三\t25\t北京
李四\t30\t上海
王五\t28\t广州
```

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 1 | 选择输入格式为"文本格式 (Tab/空格分隔)" | 下拉框显示对应选项 |
| 2 | 粘贴上述内容到文本框 | 内容正常显示 |
| 3 | 点击"识别表格结构" | loading 后显示识别结果 |

**验证点**：
| 验证项 | 预期 |
|--------|------|
| 行数 | rows = 4（含表头） |
| 列数 | cols = 3（姓名/年龄/城市） |
| 表头 | headers = ["姓名", "年龄", "城市"] |
| Markdown 输出 | 正确转换为 Markdown 表格格式 |
| CSV 输出 | 正确转换为 CSV 格式（逗号分隔） |
| 数据结构 | JSON 中的 data_rows 包含 3 行数据 |

#### 测试 2：Markdown 表格

**输入**：
```markdown
| 产品 | 销售额 | 利润 |
|------|--------|------|
| A | 100 | 30 |
| B | 200 | 50 |
| C | 150 | 45 |
```

**验证点**：
| 验证项 | 预期 |
|--------|------|
| 格式检测 | 识别为 Markdown 表格，跳过分隔行（`---|---`） |
| 表头提取 | 第一行作为 headers |
| 数据行 | 3 行数据正确提取 |
| 导出 | Markdown 和 CSV 均为有效格式 |

#### 测试 3：CSV 格式

**输入**（从文件导入 CSV）：
```csv
姓名,科目,成绩
张三,数学,85
李四,数学,92
王五,数学,78
```

| 验证项 | 预期 |
|--------|------|
| CSV 解析 | 逗号分隔，第一行为表头 |
| 自动检测 | 选择 CSV 格式时以 Tab 替换逗号后按文本解析 |
| 表格一致性 | 与"文本"格式识别结果一致 |

#### 测试 4：HTML 表格

**输入**：
```html
<table>
  <tr><th>姓名</th><th>年龄</th></tr>
  <tr><td>张三</td><td>25</td></tr>
  <tr><td>李四</td><td>30</td></tr>
</table>
```

**验证点**：
| 验证项 | 预期 |
|--------|------|
| HTML 解析 | 正确提取 `<table>` 标签内容 |
| th/td 区分 | `<th>` 标记为 is_header=true |
| colspan/rowspan | 支持合并单元格检测 |
| 标签清理 | 嵌套标签（如 `<b>`）被移除，只保留文本 |

#### 测试 5：合并单元格（HTML 格式）

**输入**：
```html
<table>
  <tr><th rowspan="2">姓名</th><th colspan="2">成绩</th></tr>
  <tr><th>数学</th><th>语文</th></tr>
  <tr><td>张三</td><td>85</td><td>90</td></tr>
  <tr><td>李四</td><td>92</td><td>88</td></tr>
</table>
```

**预期结果**：
- merged_cells 中包含 2 个合并单元格记录
- `is_complex = true`（因为有合并单元格）
- colspan/rowspan 信息正确保留在 JSON 结构中

#### 测试 6：表格复杂度分析

复杂度分析的输出示例：
```json
{
  "rows": 5,
  "cols": 4,
  "total_cells": 15,
  "merged_cells_count": 2,
  "has_multi_level_headers": true,
  "empty_cells": 1,
  "empty_cell_ratio": 0.067,
  "is_complex": true
}
```

| 判定条件 | 结果 |
|----------|------|
| merged_cells_count > 0 | 复杂表格 |
| header_rows > 1 | 多层表头 |
| 仅简单表格 | `is_complex = false` |

#### 测试 7：文件导出验证

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 1 | 识别任意表格后，点击"下载 Markdown" | 下载 `.md` 文件，内容为 Markdown 表格格式 |
| 2 | 点击"下载 CSV" | 下载 `.csv` 文件，内容为逗号分隔 |
| 3 | 文件保存路径 | 文件保存至 `outputs/tables/` 目录 |
| 4 | 文件名格式 | `table_{uuid8}.md` 和 `table_{uuid8}.csv` |

### 9.2 PDF/图片 表格识别（Qwen2-VL-TableNet）

> 文档管理页 → **"表格识别"卡片 → "PDF 表格识别 (TableNet)"页签** → **"从 PDF 识别表格"** 上传区（支持 `.pdf` / `.png` / `.jpg` / `.jpeg`）

上传 PDF 或图片/图表，系统将：

- **PDF**：用 PyMuPDF 把每一页渲染为图片 → pdfplumber 检测表格区域（网格线 + 文字对齐两种策略）并裁剪 → 逐张表格图片调用模型输出 HTML。
- **图片/图表**：直接把原图送模型推理（不走 PDF 渲染/检测流水线），结果中标注"图片"。
- 汇总结果统一保存到 `outputs/tablenet/<run_id>/`（每次运行生成唯一目录，不覆盖）。

**操作步骤**：

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 1 | 上传 PDF 或图片文件（png/jpg/jpeg） | 卡片内显示已选文件名 |
| 2 | （可选）勾选"页面未检测到表格时，整页作为图片识别"（仅 PDF 生效） | 无表格页面回退整页识别 |
| 3 | 点击"开始识别 PDF 表格" | 首次点击自动启动模型服务（加载约 10-60 秒），随后逐表识别 |
| 4 | 查看结果 | 每张表显示沙箱 HTML 预览、Markdown、单表图片/HTML 链接、汇总文件 |

**输出目录** `outputs/tablenet/<run_id>/`：

| 文件 | 说明 |
|------|------|
| `input.pdf` | 上传的 PDF 副本 |
| `page_N.png` | 每页渲染图 |
| `table_N_M.png` | 裁剪出的表格图片 |
| `table_N_M.html` | 单张表的模型输出 HTML |
| `result.md` | 所有表格的 Markdown 汇总 |
| `result.html` | 所有表格的 HTML 汇总（浏览器可直接打开） |
| `index.json` | 元数据（来源、模型、推理参数、表格清单） |

**模型说明**（模型包已就绪，推理参数与评测保持一致，勿修改）：

| 参数 | 值 |
|---|---|
| 模型 | Qwen2-VL-2B-TableNet-PubTabNet-smallx2-v1（已合并 LoRA，无需 adapter） |
| 模型目录 | 项目根 `Qwen2-VL-2B-TableNet-PubTabNet-smallx2-v1/Qwen2-VL-2B-TableNet-PubTabNet-smallx2-v1`（只读） |
| 推理环境 | 独立 venv `tablenet-venv`（torch 2.1.2+cu121 / transformers 4.48.3 / qwen-vl-utils） |
| 图片尺寸 | 280 × 280 |
| max_new_tokens | 2048 |
| 解码 | 贪心（`do_sample=False`），无 OCR |
| 提示词 | `你是一个HTML助手，目标是读取用户输入的表格图片，转换成HTML序列` |

**部署要求**：

- 需要 NVIDIA GPU（支持 BF16），模型加载约占用 4.7GB 显存（RTX 4050 6GB 可运行，显存不足时自动 CPU 卸载兜底）。
- 模型服务由后端自动拉起（监听 `127.0.0.1:18000`），常驻复用；首次加载模型耗时约 10-60 秒。
- exe 绿色版中模型与 venv 不打进包，靠从 `resources/backend` 向上找到项目根定位；**若把 exe 拷贝到其他机器/目录**，需设置环境变量 `TABLENET_MODEL_DIR`（模型目录）和 `TABLENET_VENV_DIR`（venv 目录）。

**测试用例**（使用 `test_data/sample_table.pdf`）：

| 验证项 | 预期 |
|--------|------|
| 表格检测 | pdfplumber 检出表格区域并裁剪出 `table_1_1.png` |
| 模型输出 | 返回完整 `<html><body><table>...</table></body></html>` |
| Markdown 汇总 | `result.md` 首行为表头 + 分隔行 + 数据行，无重复表头 |
| 输出落盘 | 文件保存至 `outputs/tablenet/`，每次运行唯一目录不覆盖 |
| 整页回退 | 无表格页面（如纯文本）勾选回退后，整页作为图片识别并输出 |

---

## 10. LLM Wiki 知识库

> 路径：左侧菜单 → **LLM Wiki**

LLM Wiki 将上传的文档自动组织为结构化的知识页面。

### 10.1 清空知识库

点击搜索栏右上角的 **"清空知识库"** 按钮，可一键删除所有 Wiki 页面、向量索引和文档记录。开启新任务前建议清理旧数据。

### 10.2 测试用例详解

#### 测试 1：文档上传后 Wiki 自动构建

**准备**：在"文档管理"页面上传一个文档（PDF/Word/Markdown 均可）。

| 验证项 | 预期结果 |
|--------|----------|
| 服务器端自动构建 | 上传文档后自动调用 `llm_wiki.build_from_document()` |
| 文档卡片生成 | 创建 `document_card` 类型页面，包含文件名、类型、页数、解析时间 |
| 章节摘要生成 | 每页创建一个 `chapter_summary` 类型页面，内容为该页文本前 500 字符 |
| 表格描述生成 | 文档中每个表格创建一个 `table_desc` 类型页面 |
| 概念提取 | 自动提取高频大写术语（如"东部""西部""产品A"等）作为 `concept` 页面 |
| 统计更新 | 刷新后 `total_pages` 正确反映所有页面数量 |

#### 测试 2：Wiki 搜索

**准备**：已有至少一个文档被解析并构建 Wiki。

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 1 | 在搜索框输入关键词（如文档标题中的词） | 显示匹配结果 |
| 2 | 查看结果 | 每个结果包含：page_id、title、type、content（前 300 字）、score |
| 3 | 验证评分 | - 标题匹配：+3 分<br>- 内容匹配：按词频加分<br>- 文件名匹配：+2 分<br>- 最终分归一化到 [0, 1] |

**搜索类型覆盖**：
| 搜索类型 | 关键词示例 | 预期匹配页面类型 |
|----------|------------|------------------|
| 按文件名 | 文档名的一部分 | document_card |
| 按章节 | 正文关键词 | chapter_summary |
| 按概念 | 提取的高频词 | concept |
| 按表格 | "Table"、"数据"等 | table_desc |

#### 测试 3：清空知识库

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 1 | 确认已有 Wiki 页面（total_pages > 0） | 统计面板显示数据 |
| 2 | 点击"清空知识库"按钮 | 弹出确认对话框，提示不可恢复 |
| 3 | 点击"确认清空" | 提示"知识库已清空" |
| 4 | 验证清空效果 | total_pages = 0, documents = 0 |
| 5 | 后端状态 | `/api/wiki/stats` 返回全 0，`vector_store` 清空，`documents_store` 清空 |

**清空机制验证**：
- 调用 POST `/api/wiki/clear`
- 同步清空：`llm_wiki.clear()` → `vector_store.clear()` → `documents_store.clear()`
- 清空后上传新文档，Wiki 从头开始构建
- 开启新任务前建议执行清空，避免旧数据干扰

#### 测试 4：Wiki 持久化验证

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 1 | 上传文档，确认 Wiki 页面生成 | Wiki 页面数 > 0 |
| 2 | 重启后端服务（重启 Python 进程） | 服务重新启动 |
| 3 | 访问 LLM Wiki 页面 | 页面数据从 `wiki_db/wiki_data.json` 恢复 |
| 4 | 验证持久化 | 之前上传文档的 Wiki 页面仍然存在 |

**持久化机制**：
- 页面数据存储于 `wiki_db/wiki_data.json`
- 每次 `add_page()` 和 `clear()` 后自动 `_save()`
- 启动时 `_load()` 从磁盘恢复
- 向量索引存储于 `chroma_db/index_meta.json`（简化版元数据）

---

## 11. Skill 系统

> 路径：左侧菜单 → **Skill 管理**

内置 5 个 Skill：Markdown 报告、Word 实验报告、doc-ppt 在线/离线、excel-ppt。支持从 `skills/` 目录加载外部 Skill。

### 11.1 内置 Skill 清单

| 名称 | 描述 | 触发词 | 说明 |
|------|------|--------|------|
| markdown-report-skill | 轻量 GFM Markdown 技术报告 | 生成报告, 生成论文, Markdown, 论文, 报告 | 技术笔记风，无正式图号表号 |
| word-lab-report-skill | 正式 Word 实验报告 | 生成Word, 实验报告, Word报告, 文档 | 1/1.1/1.1.1 编号 + GB/T 7714 |
| doc-ppt-online | 在线文章→图片风格 PPT | PPT, 生成PPT, 转PPT, 在线PPT | 需 OPENAI_API_KEY |
| doc-ppt-offline | 离线 DOCX→原生可编辑 PPT | PPT, 生成PPT, 转PPT, 离线PPT | 完整流水线产出 PPTX |
| excel-ppt | Excel→PPT 内容规划 | PPT, 生成PPT, 转PPT, Excel转PPT | 完整流水线产出 PPTX |

### 11.2 撰写标准（两技能职责彻底拆分）

**markdown-report-skill（轻量化、线上阅读优先）**：
- 严格 GFM：标题 #~#### 最多 4 级，行内/块公式，带语言标记代码块
- 结构范式：概述→方案/原理→实验设置→结果与分析→总结（按需裁剪）
- 不加正式图号表号、不做严格 GB/T 7714，文风偏技术笔记

**word-lab-report-skill（线下正式归档）**：
- 严格章节编号 1 / 1.1 / 1.1.1
- 图片标注「图X 标题」放图下方、表格标注「表X 标题」放表上方
- 参考文献按 GB/T 7714，使用正式学术书面语
- 禁止 Markdown 语法，代码统一放附录

### 11.3 测试用例详解

#### 测试 1：Skill 列表加载与刷新

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 1 | 进入 Skill 管理页面 | 左侧列表显示 5 个技能，含版本/验证/风险标签 |
| 2 | 点击"刷新" | 列表重新加载 |
| 3 | 点击"详情" | 弹出 Modal 显示名称、描述、触发词、风险等级、权限、依赖 |
| 4 | 查看验证状态 | 内置技能显示"已验证"，风险标签清晰（low 绿 / medium 橙） |

#### 测试 2：Trigger 匹配测试

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 1 | 输入任务描述（如"使用doc-ppt-online生成ppt"） | "匹配 Skill"按钮可用（描述或文件至少一个非空） |
| 2 | 点击"匹配 Skill" | 按匹配度排序显示匹配结果 |
| 3 | 验证匹配 | 技能名出现在任务中得分最高，格式关键词（ppt/excel/word）也参与计分 |

**匹配规则**：触发词子串 +1 分，技能名出现 +3 分，格式关键词 +1 分，从高到低排序。

#### 测试 3：Markdown 报告生成

**任务**：输入"生成项目报告"，选择 markdown-report-skill 执行。

| 验证项 | 预期结果 |
|--------|----------|
| Markdown 文件生成 | 输出 `outputs/{title}.md` |
| GFM 语法 | `#` 标题、表格、代码块、公式规范 |
| 章节结构 | 不足 3 章自动补全（概述/方案/总结） |
| 写作指令 | 返回 `writing_guide` 字段 |

#### 测试 4：Word 实验报告生成

**任务**：输入"生成化学实验报告"，选择 word-lab-report-skill 执行。

| 验证项 | 预期结果 |
|--------|----------|
| docx 生成 | 输出 `outputs/{title}.docx` |
| 章节自动编号 | 1 / 1.1 / 1.1.1 三级编号 |
| 章节自动补全 | 不足 5 章自动补全（绪论→原理→环境与方案→结果→结论） |
| 图文标注 | 表X 标题在表上方，图X 标题在图下方 |
| 参考文献 | GB/T 7714 格式 |
| 去 Markdown | 内容无 `#` `**` 等标记 |

#### 测试 5：doc-ppt-online 执行

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 1 | 上传 DOCX/Word 文件 | 显示已上传文件名 |
| 2 | 输入"生成ppt" | 匹配到 doc-ppt-online |
| 3 | 点击"执行" | 返回 SKILL.md 指导 + 源文件复制到项目目录（需配 OPENAI_API_KEY 才可实际生成） |

#### 测试 6：doc-ppt-offline 执行

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 1 | 上传 DOCX 文件 | 显示已上传文件名 |
| 2 | 匹配并执行 doc-ppt-offline | 运行完整流水线（抽取→文本层→设计→原生PPTX） |
| 3 | 验证 | `outputs/doc-ppt-offline/.../native_draft.pptx` 生成，执行结果 `pptx_generated: ✓` |

#### 测试 7：excel-ppt 执行

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 1 | 上传 Excel 文件 | 显示已上传文件名 |
| 2 | 匹配并执行 excel-ppt | 运行完整流水线（intake→规划→渲染→组合） |
| 3 | 验证 | `outputs/excel-ppt/.../fund-pension-annuity-step3b-draft.pptx` 生成 |

#### 测试 8：执行历史与清空

| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 1 | 执行多个技能 | 执行历史显示记录（技能名/成功/时间） |
| 2 | 点击"刷新" | 历史重新加载，提示"执行历史已刷新" |
| 3 | 点击"清空" | 确认弹窗后清空所有执行记录 |
| 4 | 执行技能后点击"重置" | 任务描述、上传文件、匹配结果、执行结果全部清空，可开始新任务 |


## 12. 实验评测面板

> 路径：左侧菜单 → **实验评测**

综合显示系统各模块的运行指标和评估结果。

### 12.1 测试用例详解

#### 测试 1：Cache 指标验证

**验证 API**：GET `/api/evaluation/coding`

| 指标 | 验证方法 |
|------|----------|
| cache_hit_rate | 多次执行 Agent 任务后 > 0（第二次起命中） |
| total_requests | 等于已执行的 API 调用次数 |
| avg_latency_ms | 每次调用的平均响应时间 |
| input_tokens_saved | 缓存命中时估算的 token 节省（命中 token × 0.9） |
| estimated_cost_saved_usd | 按 $0.15/M input tokens 估算 |

**手动测试步骤**：
| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 1 | 进入评测面板 | 显示 Coding Agent 缓存命中率、RAG 统计、Skill 成功率 |
| 2 | 返回 Coding Agent 执行一个任务 | 任务成功完成（≥2 轮） |
| 3 | 再次进入评测面板 | 缓存命中率 > 0，请求数增加 |
| 4 | 点击 Cache 指标面板的"重置"按钮 | 所有指标归零 |
| 5 | 验证归零 | 命中率 = 0%，请求数 = 0 |

**Cache 工作机制**：
- 系统使用 OptimizedAgentLoop 进行缓存优化
- Session ID 固定，超过 1 轮请求后 prefix 稳定，计为 cache hit
- 每 5 轮进行状态压缩（roll_task_state），保留最近 30 条消息
- cache hit 时 input_tokens_saved += input_tokens × 0.9

#### 测试 2：RAG 评测验证

**验证 API**：GET `/api/evaluation/rag`

| 指标 | 验证方法 |
|------|----------|
| total_chunks | 等于所有文档的分块总数 |
| wiki_pages | 等于所有生成的 Wiki 页面数 |
| documents_count | 等于已上传尚未删除的文档数 |
| index_ready | 当 documents_count > 0 时为 true |

**测试步骤**：
| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 1 | 确认当前文档数为 0 | RAG 评测中 documents=0, chunks=0 |
| 2 | 上传一个文档（如 PDF） | 评测面板显示 documents=1, chunks>0 |
| 3 | 上传第二个文档 | 文档数增加，chunks 和 wiki_pages 相应增加 |
| 4 | 删除一个文档 | 文档数减少，chunks 减少，wiki_pages 不变 |
| 5 | 清空知识库 | 所有指标归零 |

**RAG 评估项面板**（前端 UI 硬编码清单）：
| 功能 | 状态 |
|------|------|
| PDF 解析 | ✓ 支持 |
| 表格识别 | ✓ 支持 |
| 混合检索 | ✓ Vector + BM25 |
| 证据溯源 | ✓ 支持 |
| LLM Wiki | ✓ 支持 |

#### 测试 3：Skill 评测验证

**验证 API**：GET `/api/evaluation/skills`

| 指标 | 验证方法 |
|------|----------|
| total_skills | 等于已注册的 Skill 数（4 内置 + 外部加载） |
| total_executions | 等于已执行的 Skill 调用次数 |
| success_count | execution 中 success=true 的次数 |
| success_rate | success_count / total_executions × 100 |

**测试步骤**：
| 步骤 | 操作 | 预期结果 |
|------|------|----------|
| 1 | 确认当前 Skill 数 ≥ 4 | 显示至少 4 个内置 Skill |
| 2 | 执行一个成功的 Skill（如 Markdown） | executions 增加 1，success_count 增加 1 |
| 3 | 执行一个失败的 Skill（如缺少参数） | executions 增加 1，success_count 不变 |
| 4 | 验证成功率 | 成功率 = 成功次数 / 总执行次数 |
| 5 | 确认 UI 显示 | 成功率 < 50% 黄色，≥50% 绿色 |

**Skill 评估项面板**（前端 UI 硬编码清单）：
| 功能 | 状态 |
|------|------|
| Trigger 匹配 | ✓ 按需加载 |
| 文件生成 | ✓ .md/.docx/.pptx |
| 自动验证 | ✓ 有 |
| Java 代码生成 | ✓ 有 |
| Markdown 报告 | ✓ 无需编译 |

#### 测试 4：综合评测面板完整性验证

**验证 API**：GET `/api/evaluation/all`

| 操作 | 预期结果 |
|------|----------|
| 页面加载 | 3 个统计卡片显示：Coding Agent 命中率、RAG 文档/块/页面数、Skill 成功率 |
| Tab 切换 | 3 个 Tab（Coding Agent、RAG 文档系统、Skill 系统）可正常切换 |
| Coding Agent Tab | 显示 Cache Metrics 表单 + 性能指标的环形进度条 |
| RAG Tab | 显示文档统计 + RAG 评估项清单 |
| Skill Tab | 显示 Skill 统计 + Skill 评估项清单 |

#### 测试 5：数据一致性验证

| 验证项目 | 操作 | 预期结果 |
|----------|------|----------|
| 后端聚合 | GET `/api/evaluation/all` | coding、rag、skills 三个维度数据齐全 |
| coding 数据 | 比较 GET `/api/evaluation/coding` 与 `/api/agent/cache-metrics` | cache_hit_rate、avg_latency_ms 等一致 |
| rag 数据 | 比较 GET `/api/evaluation/rag` 与 `/api/system/status` | documents_count、wiki_pages 一致 |
| skills 数据 | 比较 GET `/api/evaluation/skills` 与 `/api/skills/history` | 执行次数、成功率计算一致 |
| 前端展示 | 前端调用 `/api/evaluation/all` 渲染 | 3 个统计卡片 + 4 个 Tab 内容均与实际数据匹配 |

---

## 13. API 参考

后端提供 RESTful API，基础路径为 `http://localhost:8000`（开发模式）或 `http://localhost:18327`（启动器模式）。

### 13.1 系统状态

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 健康检查 |
| GET | `/api/system/status` | 系统状态 |

### 13.2 模型配置与 Provider

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/models/config` | 获取当前活跃 Provider 配置 |
| POST | `/api/models/config` | 更新当前活跃 Provider 配置 |
| GET | `/api/models/providers` | 获取所有 Provider 配置 + 连接状态 |
| POST | `/api/models/switch` | 切换活跃 Provider |
| POST | `/api/models/providers` | 批量保存所有 Provider 配置 |

### 13.3 Coding Agent

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/agent/execute` | 执行任务 |
| GET | `/api/agent/cache-metrics` | 缓存指标 |
| POST | `/api/agent/cache-metrics/reset` | 重置缓存指标 |
| POST | `/api/agent/reset` | 重置 Agent |
| GET | `/api/agent/checkpoints` | 获取快照列表 |
| POST | `/api/agent/rollback/{id}` | 回滚到指定快照 |
| GET | `/api/agent/file-versions` | 获取所有文件的版本历史 |
| GET | `/api/agent/file-content` | 获取指定文件版本的完整内容 |
| GET | `/api/agent/file-diff` | 获取两个版本间的代码 Diff |
| GET | `/api/agent/sessions` | 列出所有对话会话 |
| POST | `/api/agent/sessions` | 新建会话 |
| GET | `/api/agent/sessions/{id}` | 获取会话详情 |
| POST | `/api/agent/sessions/{id}/switch` | 切换会话 |
| DELETE | `/api/agent/sessions/{id}` | 删除会话 |

### 13.4 CodeGraph

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/codegraph/build` | 构建代码图谱（返回树形结构） |
| GET | `/api/codegraph/tree` | 获取已构建的文件树和统计 |
| GET | `/api/codegraph/query` | 查询符号 |
| GET | `/api/codegraph/stats` | 统计数据 |

### 13.5 文档管理 / RAG / 表格

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/documents/upload` | 上传文档（后端 8 格式；UI 限 PDF/Word）；表单 `extract_tables=true` 时 PDF 用 TableNet 提取表格并入 RAG |
| GET | `/api/documents` | 文档列表 |
| DELETE | `/api/documents/{id}` | 删除文档 |
| POST | `/api/rag/search` | 检索文档（支持 `document_ids`/`chunk_type` 过滤） |
| POST | `/api/rag/qa` | 文档问答（支持 `document_ids`） |
| POST | `/api/rag/finance-qa` | 金融计算问答（注入选中文档表格块 + LLM 调 calculate 安全计算器，返回 `calculation_steps`） |
| POST | `/api/tables/recognize` | 识别表格（文本/Markdown/CSV/HTML） |
| GET | `/api/tables/document/{id}` | 取文档内所有表格 |
| POST | `/api/tables/pdf-recognize` | 表格识别：上传 PDF 或图片/图表，Qwen2-VL-TableNet 识别表格（PDF 走渲染+检测，图片直通模型） |
| GET | `/api/tables/tablenet/status` | 模型服务状态（模型目录 / venv / 可用性） |

### 13.6 金融数据分析

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/finance-analysis/run` | 上传 CSV/Excel + 分析目标 → 子进程调 data_analysis 生成并执行代码，返回代码/执行日志/解释/图表（`outputs/finance-analysis/<run_id>/`） |
| GET | `/api/finance-analysis/status` | 金融数据分析可用性检测（python 解释器 + data_analysis 依赖） |

### 13.7 LLM Wiki / Skill / 评测

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/wiki/stats` | Wiki 统计 |
| POST | `/api/wiki/clear` | 清空知识库 |
| GET | `/api/skills` | Skill 列表 |
| GET | `/api/skills/cards` | Skill Card 治理元数据 |
| POST | `/api/skills/match` | 触发词匹配 |
| POST | `/api/skills/execute` | 执行 Skill |
| GET | `/api/skills/history` | 执行历史 |
| POST | `/api/skills/history/clear` | 清空执行历史 |
| GET | `/api/evaluation/all` | 综合评测 |

---

## 14. 常见问题与故障排除

### 14.1 后端启动失败

```bash
pip install -r requirements.txt
netstat -ano | findstr :8000
python --version  # 需要 3.9+
```

### 14.2 前端启动失败

```bash
rm -rf node_modules
npm install
node --version  # 需要 18+
```

### 14.3 PDF 表格识别失败（模型服务不可用）

| 现象 | 原因 | 解决 |
|------|------|------|
| 状态显示"模型：未启动/加载中" | 首次调用正在加载模型 | 等待 10-60 秒，首次加载完成后常驻复用 |
| `No module named 'cryptography'` | 打包版缺依赖 | 已修复（backend.spec 不再排除 cryptography），请使用重新打包的 exe |
| 模型服务不可用 | `tablenet-venv` 或模型目录缺失 | 检查项目根存在 `tablenet-venv` 与 `Qwen2-VL-2B-TableNet-PubTabNet-smallx2-v1/` |
| exe 中识别失败 | exe 被拷贝到其他目录，找不到模型/venv | 设置环境变量 `TABLENET_MODEL_DIR`、`TABLENET_VENV_DIR`，或用 Web 版 |
| 拷贝到别的机器后 `venv\Scripts\python.exe` 无法启动 | **tablenet-venv 不可移植**：`pyvenv.cfg` 写死 base Python 路径（如 `home=D:\Python`） | 跑 `首次配置.bat`（自动调 `修复venv.ps1` 探测本机 Python 3.11 并改写 `pyvenv.cfg`），或在本机装 Python 3.11.9 到同一路径 |
| docx 上传报 `No module named 'lxml'` | 打包版 backend.spec 曾排除 lxml（python-docx/pptx 依赖它） | 已修复（移除 lxml 排除），请使用重新打包的 exe |
| CUDA OOM | 显存不足（需 ≥4.7GB） | 关闭其他 GPU 程序；系统会自动 CPU 卸载兜底，但更慢 |

### 14.4 多人使用 / 多实例

- **每人独立运行**：整份拷贝项目文件夹，各自双击 exe 即可（完全隔离）。分发前先跑 `首次配置.bat` 处理 venv，并清理 `outputs/`、`uploads/`、`chroma_db/`、`wiki_db/`、`conversation_history.json`。
- **只拷 win-unpacked 应用包**：文档/RAG/金融问答/Agent 可用，**表格识别不可用**（模型与 venv 在项目根，不在包内）；**金融数据分析不可用**（需项目根 `data_analysis/` 包 + 装有其依赖的 python）。
- **同一台电脑跑第二个实例**：运行 `启动第二实例.bat`（端口 18329 + `data2` 数据目录 + 共享表格识别 18000）；两个实例数据完全隔离。同机只能一个 exe 占 18327，其余用该脚本。

### 14.5 Coding Agent 任务执行失败

| 原因 | 解决 |
|------|------|
| API 调用超时 | 检查当前 Provider 连接状态 |
| `javac` 未找到 | 系统已自动注入 JDK 路径 |
| 文件路径错误 | 已修复为自动以项目根目录为准 |

### 14.6 启动器无法打开

确认 Python 和 Node.js 已安装且 `pip install` 和 `npm install` 已完成。

### 14.7 本地模型（Ollama）无法连接

确认 Ollama 已启动（`ollama serve`）且模型已下载（`ollama list`）。

### 14.8 金融数据分析依赖不可用

| 现象 | 原因 | 解决 |
|------|------|------|
| 金融数据分析页顶部黄色警告"data_analysis 依赖不可用" | 运行 python 缺少 data_analysis 包或其依赖（openai/pandas/numpy/matplotlib/openpyxl） | 执行 `pip install -r data_analysis/requirements.txt`；或设环境变量 `DATA_ANALYSIS_PYTHON` 指向装好依赖的 python |
| exe 中点击「开始分析」报错/失败 | 打包环境解析到的 python 无依赖，或项目根无 `data_analysis/` 目录 | 拷贝整份项目（含 `data_analysis/` 文件夹）；设 `DATA_ANALYSIS_PYTHON`；首次执行需联网调用 DeepSeek（key 自动取自 `backend/model_config.json`） |
| 分析结果中图表不显示 | 子进程 python 缺 matplotlib | 同"依赖不可用"，安装 `data_analysis/requirements.txt` |

---

## 附录

### A. 项目目录结构

```
大作业/
├── AGENTS.md
├── 启动桌面端.bat
├── 首次配置.bat                 # 多人分发：每台机器跑一次（设环境变量、校验/修复 venv）
├── 修复venv.ps1                 # 自动修复 tablenet-venv 的 pyvenv.cfg（探测本机 Python 3.11）
├── 启动第二实例.bat             # 同机再开一个隔离实例（18329 + data2 + 共享 18000）
├── start_backend.bat
├── start_frontend.bat
├── AI桌面端系统操作手册.md
├── tablenet-venv/               # PDF 表格识别模型的独立推理环境（不在主后端依赖中）
├── Qwen2-VL-2B-TableNet-PubTabNet-smallx2-v1/   # 已训练模型（只读，勿修改）
├── data_analysis/               # 金融数据分析独立可移植包（自包含，可单独拷贝运行）
│   ├── analyzer.py              # 核心 FinancialDataAnalysis（生成代码→沙箱执行→解释）
│   ├── run_analysis.py          # 命令行入口（--data/--question/--out-dir/--json）
│   ├── config.py / llm.py       # 配置（.env）/ DeepSeek 封装
│   ├── executor.py / exec_runner.py  # 沙箱代码执行（受限环境 + 超时 + matplotlib 出图）
│   └── prompts.py / extract.py  # 任务专用 Prompt / 代码提取
│
├── backend/                     # Python 后端
│   ├── main.py                  # API 路由（37+ 端点）
│   ├── config.py                # 配置管理 + 双 Provider + tablenet 路径
│   ├── finance_analysis.py      # 金融数据分析端点（暂存上传文件 → 子进程调 data_analysis 包）
│   ├── run.py                   # 启动入口
│   ├── model_config.json        # 双 Provider 配置
│   ├── agent/                   # Coding Agent
│   │   ├── __init__.py          # 核心 Agent 逻辑
│   │   ├── reasonix.py          # 缓存优化
│   │   └── codegraph.py         # 代码图谱
│   ├── rag/                     # RAG 系统（解析/检索/Wiki/金融问答）
│   │   ├── pdf_table_recognition.py  # PDF/图片 表格识别流水线 + merge_tablenet_tables（并入文档 RAG）
│   │   └── finance_qa.py             # 金融计算问答（safe_eval 安全计算器 + calculate 工具）
│   ├── tablenet/                # Qwen2-VL-TableNet 集成（独立 venv 服务）
│   │   ├── inference.py         # 推理核心（固定参数，只读模型目录）
│   │   ├── server.py            # 模型服务进程（/health + /predict）
│   │   ├── engine.py            # 后端客户端（懒启动 + 常驻本地服务）
│   │   └── smoke_test.py        # 单图冒烟测试
│   ├── skills/                  # Skill 系统（5 内置技能）
│   └── dist/                    # PyInstaller 打包产物（backend.exe）
│
├── frontend/                    # React 前端
│   ├── vite.config.ts           # Vite 配置（proxy:18327 + base:'./'）
│   └── src/
│       ├── pages/               # 8 个页面（原独立 TablePage 已并入 DocumentPage）
│       │   ├── AgentPage.tsx        # 对话式 Coding Agent
│       │   ├── ModelConfigPage.tsx  # 双 Provider 配置
│       │   ├── WikiPage.tsx         # LLM Wiki + 清空按钮
│       │   ├── DocumentPage.tsx     # 文档管理 + RAG 问答 + 金融问答 + 表格识别
│       │   ├── FinanceDataAnalysisPage.tsx  # 金融数据分析（上传 CSV/Excel → 图表/解释）
│       │   ├── SkillPage.tsx        # Skill 管理
│       │   └── EvaluationPage.tsx   # 实验评测面板
│       └── components/
│           └── TableRecognitionPanel.tsx  # 表格识别面板（通用 + PDF/图片两个 Tab）
│
├── desktop/                     # Electron 桌面客户端
│   ├── main.js                  # Electron 主进程
│   ├── preload.js               # 桥接层（注入后端 URL）
│   ├── launcher.js              # 轻量启动器
│   ├── package.json             # electron-builder 配置
│   ├── icon.ico                 # 应用图标
│   └── dist/
│       └── win-unpacked/
│           └── AI桌面端系统.exe  # 绿色版 exe（含 resources/）
│
├── test_data/coding/            # Coding Agent 测试文件
│   ├── java_test/               # Java 单文件 Bug 修复测试
│   ├── multi_file/              # 多文件 Java 项目测试
│   ├── python_test/             # Python 代码修复测试
│   └── repo_test/               # 工业级 Java 项目 3Bug+1TODO
├── test_data/
│   ├── make_table_pdf.py        # 生成带表格的测试 PDF
│   ├── make_finance_pdf.py      # 生成财务表格测试 PDF（finance_sample.pdf）
│   ├── e2e_tablenet_test.py     # PDF 表格识别端到端冒烟脚本
│   ├── sample_table.pdf         # 示例测试 PDF
│   ├── finance_sample.pdf/png   # 财务表格测试 PDF / 图片（验证金融问答 + 图片识别）
│   ├── 示例公司财务数据.xlsx     # 金融数据分析测试 Excel（营业收入/成本/净利/总资产 × 2020-2023）
│   ├── test_word.docx           # 测试 Word 文档
│   └── test_ppt.pptx            # 测试 PPT 文档
│
└── skills/                      # 外部 Skill
    └── format_check_skill.py    # 文档格式检查
```

### B. 已修复的问题清单

| 问题 | 修复 |
|------|------|
| Coding Agent 路径解析错误 | 增加 project_root 自动检测 |
| Agent 状态累积 | 每次 execute_task 重置 task_state |
| Agent 不调用 write_file 写盘 | 强化 system prompt |
| API 超时导致 500 | 设置 timeout=120s |
| JDK 不在 PATH 中 | execute_command 自动注入 JDK |
| File tree 页面切换后丢失 | GET /api/codegraph/tree 持久化 |
| model_config 单 Provider | 改为双 Provider（online + local） |
| 缺少清空知识库 | 新增 wiki/clear API |
| Coding Agent 单次提交无历史 | 改为对话流界面，消息持久可见 |
| 缺少新对话功能 | 新增 "新对话" 按钮 + /api/agent/reset |
| Checkpoint 跨任务丢失 | 从 task_state 移到实例级 self.checkpoints，跨任务持久保存 |
| 回滚后 Checkpoint 被删 | 改为仅删除被回滚的那个，其余保留支持多级回滚 |
| 启动桌面端.bat 闪退 | 修复引号冲突、编码乱码、路径错误、增加超时限制 |
| Vite 代理端口不匹配 | 修正为 18327（与启动器端口一致）|
| 暗黑主题 | 改为红白主题（白色 + 红色点缀），defaultAlgorithm |
| docx/pptx 上传解析失败 | backend.spec 曾排除 lxml（python-docx/pptx 依赖），已移除排除并重打包 |
| 表格识别与文档管理割裂 | 表格识别并入文档管理页（TableRecognitionPanel），删除独立 TablePage |
| 文档上传格式过多 | 界面限制为 PDF/Word（后端仍保留全格式）|
| PDF 表格识别仅支持 PDF | 支持图片/图表（recognize_image_tables 直通模型）|
| `/api/rag/qa` 忽略 document_ids | 接入向量库过滤（search 支持 document_ids/chunk_type）|
| wiki 页面时间戳被重置 | `llm_wiki._load()` 恢复 created_at/updated_at |
| API 错误被转成 404/HTML | SPA 异常处理器仅对非 `/api/` 的 404 兜底，API 按原状态码返回 |

### C. 实测验证记录（2026年7月14日）

以下为对 6 个 Coding Agent 测试用例的实际运行结果，验证环境为 DeepSeek 在线 Provider。

#### 测试 1：Java 单文件 Bug 修复（Calculator.java）

| 用例 | Agent 执行结果 | 关键行为验证 |
|------|---------------|-------------|
| 1a 修复除零 Bug | **5 轮 / 7.8s** | read_file→create_checkpoint→write_file(添加if(b==0)检查)→javac编译→java运行→输出"10 / 0 = 0" |
| 1b 添加 power 方法 | **5 轮 / 10.0s** | 添加power(int,int)方法，处理负指数，验证 2^3=8, 5^0=1 |
| 1c 批量操作验证 | 编译运行 | 全部4个方法(add/subtract/multiply/divide/power)均正常输出，exit_code=0 |

#### 测试 2：多文件 Java 项目修复（GradeManager）

| 用例 | Agent 执行结果 | 关键行为验证 |
|------|---------------|-------------|
| 2a 修复空列表 Bug | **11 轮 / 15.98s** | 读取3个文件(GradeManager/Student/Main)，添加`isEmpty()`检查，修复整数除法的`double`转型 |
| 2b 添加 getTopStudent | **10 轮 / 14.82s** | 添加方法+更新Main.java测试，输出"Top student: Bob: 92"，空列表测试输出"None" |

#### 测试 3：Python 多 Bug 修复（data_processor.py）

| 用例 | Agent 执行结果 | 关键行为验证 |
|------|---------------|-------------|
| 3a 修复全部 Bug | **6 轮 / 13.58s** | 修复calculate_average空列表(return 0.0)+save_report目录创建(os.makedirs) |
| 3b 实现 filter_outliers | **12 轮** | 实现filter_outliers函数，扩充测试用例，**11个单元测试全部通过(OK)** |
| 3c 完整数据流程 | **5 轮** | read scores.csv→统计分析→IQR法过滤→保存report.txt→验证文件内容 |

#### 测试 4：Python 扩展功能测试（scores.csv 分析）

| Agent 执行结果 | 关键行为验证 |
|---------------|-------------|
| **4 轮** | 新建analyze_scores.py→读取CSV→计算avg=86.12/max=95/min=76/及格率100%→表格化输出→exit_code=0 |

#### 测试 5：Checkpoint 快照回滚

| 步骤 | 验证结果 |
|------|---------|
| 执行修复任务 | 自动创建 2 个 Checkpoint（手动create_checkpoint+write_file自动快照） |
| API 查询快照列表 | GET /api/agent/checkpoints 返回 2 条记录，含 id、timestamp、files 列表 |
| 回滚到 cp 快照 | POST /api/agent/rollback/cp_xxx 返回 success, restored_files |
| 验证回滚效果 | 文件恢复原始状态，javac+java 运行确认真实触发 ArithmeticException: / by zero |

#### 测试 6：目标文件夹 + 上传文件协同

| 步骤 | 验证结果 |
|------|---------|
| 无目标文件夹 | Agent 在项目根目录创建 HelloWorld.java，编译运行输出"Hello World" |
| 指定目标文件夹 | Agent 在 test_data/coding/java_test/ 创建 TestNew.java，输出正确 |
| 上传文件读取 | /api/agent/upload 上传 Student.java(382 bytes)→Agent 搜索→找到并读取文件内容 |

#### 综合指标

| 指标 | 值 |
|------|----|
| 总执行任务数 | 10 次 Agent 调用 |
| 平均任务轮数 | 6.5 轮 |
| 平均任务耗时 | ~12.4s |
| Cache 命中率 | 90.12% |
| 总 API 调用次数 | 81 次 |
| 估算节省成本 | $0.0385 |
| 测试通过率 | **100%**（全部 6 个测试用例通过） |

---

> **最后更新**：2026年7月15日
> **作者**：AI Desktop System
