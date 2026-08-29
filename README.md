## ai-desktop-agent
面向真实工程场景的 AI 桌面智能系统,以多轮 Coding Agent 为核心,实现任务理解、代码修改、测试迭代与批量评测的全流程自动化,并集成 RAG 文档问答与技能系统,交付 Web/Electron 双端。

#核心功能
1. Coding Agent
• 多轮任务执行与错误恢复，Checkpoint 检查点回滚机制，保障代码修改安全

• 内置 8 大工具：读写文件、执行命令、创建/回滚检查点、运行测试、查看 Git 差异等

• Reasonix 缓存优化：稳定前缀提示词提升缓存命中率，实时监控命中率与 Token 成本

• CodeGraph 代码理解：符号提取、调用图分析、导入依赖映射、测试文件自动关联（支持 Python / JS / TS / C / C++）

• 文件版本追踪与差异生成，多会话隔离独立回滚

• 支持 SWE-bench Lite 批量评测

2. RAG 文档问答
• 多格式文档解析：PDF / Word / PPT / Excel / CSV / 图片 等 8 种格式

• 混合检索：向量 + BM25 + 重排序，支持按文档过滤

• 金融计算问答：注入表格块 + LLM 调用安全计算器，精确计算财务指标

• 表格结构识别：接入 Qwen2-VL-TableNet 模型，从 PDF / 图片中提取表格并并入 RAG

• LLM Wiki 知识库

3. 技能系统（Skill System）
• 内置 5 个技能：Markdown 报告、Word 实验报告、在线/离线 PPT、Excel 转 PPT

• 遵循 SKILL.md 标准，配套 Skill Card 治理元数据（负责人、生命周期、风险等级、权限、签名）

• 支持外部技能动态加载、文件上传与结果下载

4. 金融数据分析
• 上传 CSV / Excel + 自然语言分析目标

• 子进程自动生成并执行 Python 代码，完成指标计算、数据处理、统计分析与可视化

• 返回代码、执行日志、图表与中文解释

#快速开始
模型与依赖资源体积较大，不在 Git 仓库内，请通过网盘下载完整包（见下方「资源下载」）。
Web 版
Copy code to clipboard
# 后端（端口 18327）
cd backend

pip install -r requirements.txt

python run.py

# 前端（端口 3000，自动代理 /api 到 18327）
cd frontend

npm install

npm run dev
桌面版
Copy code to clipboard
# 构建前端
cd frontend && npm run build

# 打包 Electron（国内可加镜像加速）
set ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/

cd desktop && npm run dist

# 运行解压版
desktop/dist/win-unpacked/AI桌面端系统.exe
模型配置
在 UI「设置」页或编辑 backend/model_config.json，配置 API 提供商（DeepSeek / OpenAI / 自定义）、API Key、模型名与参数。该文件含个人 API Key，已被 Git 忽略，不会上传。

#文档
• AI桌面端系统操作手册.md — 详细操作手册

• AGENTS.md — 系统架构与开发说明

• Qwen2-VL-2B-TableNet-PubTabNet-smallx2-v1-部署操作手册.md — 表格识别模型部署说明

# 资源下载
完整打包程序（模型、依赖资源）不在Git仓库内，请通过网盘获取：

- 链接：https://pan.baidu.com/s/1pnvzwKTko5lpL0FzjkoRDA
- 
- 提取码：`7r64`

下载 `AI桌面端系统.zip` 即可。

