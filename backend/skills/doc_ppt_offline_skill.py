"""DOC to PPT Offline Skill — delegates the full ppt-master workflow to the
Coding Agent, which reads SKILL.md and executes the pipeline faithfully with
automated defaults (no Confirm UI / live preview / image generation).

The ppt-master skill (skills/ppt-skill/doc-ppt离线/) is an agent-driven
interactive workflow. This wrapper is intentionally thin: it stages the source
file in a fresh per-run workspace, delegates execution to the Coding Agent
(following SKILL.md step by step, using default options for every interactive
step), then locates the produced PPTX and copies it to the outputs root.
"""

import os
import re
import shutil
from datetime import datetime
from typing import Dict, List

from .skill_manager import Skill


class DocPptOfflineSkill(Skill):
    """doc-ppt 离线：严格按 ppt-master(SKILL.md) 流程自动生成原生可编辑 PPT"""

    SKILL_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "skills", "ppt-skill", "doc-ppt离线",
    )
    SKILL_MD = os.path.join(SKILL_DIR, "SKILL.md")
    SCRIPTS_DIR = os.path.join(SKILL_DIR, "scripts")

    def __init__(self):
        super().__init__()
        self.name = "doc-ppt-offline"
        self.description = "离线将 Word/DOCX/PDF/PPT 等源文档按 ppt-master(SKILL.md) 流程自动生成原生可编辑 PPT"
        self.trigger = "PPT 生成PPT 转PPT 离线PPT Word转PPT DOCX转PPT 文档转PPT 原生PPT ppt-master 生成演示文稿 做PPT 使用模板"
        self.input_schema = {
            "type": "object",
            "required": [],
            "properties": {
                "source_file": {"type": "string", "description": "源文档路径（Word/PDF/PPT/Excel 等）"},
                "document_path": {"type": "string", "description": "源文档路径（别名）"}
            }
        }
        self.workflow = [
            "1. 严格读取 SKILL.md 并按 Step1-Step7 流程执行",
            "2. 使用国泰基金标准模板（固定模板模式），交互确认项全部采用默认值",
            "3. AI 代理按策略师/执行器角色生成设计稿与逐页 SVG",
            "4. 质量检查、讲稿拆分、finalize、导出原生 PPTX",
        ]
        self.tools = ["file_read", "file_write", "command_exec"]
        self.validation = ["成功输出可编辑原生 PPTX"]
        self.owner = "第三方 (ppt-master)"
        self.lifecycle = "beta"
        self.risk_level = "medium"
        self.permissions = {"file_write": True, "command_exec": True, "network": False}
        self.dependencies = ["python3", "python-pptx", "AI 编码代理"]
        # Injected by SkillManager at execution time (set on main.py startup)
        self.coding_agent = None
        # First-party wrapper, but points to external skill - sign as verified wrapper
        self.expected_hash = self.compute_hash()

    # ------------------------------------------------------------------ #
    # helpers
    # ------------------------------------------------------------------ #
    def _read_skillmd(self) -> str:
        """Read the external SKILL.md content (never modified)"""
        try:
            with open(self.SKILL_MD, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"[无法读取 SKILL.md: {e}]"

    def _resolve_source(self, source_file: str) -> str:
        if not source_file:
            return ""
        candidates = [source_file]
        for base in [".", "..", "./uploads", "../uploads", "../ppt-skill"]:
            candidates.append(os.path.join(base, source_file))
        for cand in candidates:
            if os.path.exists(cand):
                return cand
        return ""

    def _build_agent_task(self, workspace: str, source_file: str, user_description: str) -> str:
        """Minimal launch prompt — SKILL.md owns all routing & flow.

        The wrapper does not re-implement mode routing, palette, page
        structure or script commands: the agent reads SKILL.md and follows it
        exactly, including Step 3 routing (free design vs registered deck).
        """
        return f"""你正在作为 PPT Master 技能的执行器，把用户的文档按 skill 流程转换为原生 PPTX。

【用户请求】
{user_description or "（用户未提供额外描述，按文档内容生成 PPT）"}

【你的任务】
严格按 SKILL.md 执行：先 read_file {self.SKILL_MD}，从 Step 1 到 Step 7 完整执行，包括 Step 3 的模式路由（根据上面【用户请求】的措辞决定走"自由设计"还是"使用注册模板 deck"），不要跳过、不要改写、不要自作主张改变任何步骤。按 SKILL.md 的要求读取它指定的参考文件与模板。

【自动化执行模式（桌面端无人值守，最高优先级）】
- 所有交互/阻塞步骤（Step 4 的八项确认、Confirm UI、Step 6 的 live preview / svg_editor）直接采用 skill 的默认值处理；不要启动任何服务器，不要等待用户输入。
- 图片获取（Step 5）：本环境为离线，不要运行 image_gen / image_search / latex_render，不要生成需联网获取的新图片。

【路径】
- 源文档: {source_file}
- 工作目录(所有产物必须放在这里): {workspace}
- skill 根目录: {self.SKILL_DIR}
- 所有脚本用 `python` 运行（Windows 没有 python3）。

【结束】导出成功后，汇报最终 pptx 的绝对路径与页数。不要输出多余大段解释。"""

    def _delegate(self, workspace: str, source_file: str, user_description: str, logs: List[str]) -> Dict:
        if not self.coding_agent:
            logs.append("[agent] 未注入 coding_agent，无法自动生成。")
            return {"error": "coding_agent 未注入（后端未配置模型）"}
        # ppt-master scripts (convert / finalize / export) can exceed the
        # default 60s command timeout; give the agent's shell a long budget
        if hasattr(self.coding_agent, "command_timeout"):
            self.coding_agent.command_timeout = 900
        task = self._build_agent_task(workspace, source_file, user_description)
        try:
            result = self.coding_agent.execute_task(task, max_rounds=60)
            logs.append(f"[agent] 完成 {result.get('rounds', 0)} 轮，编辑文件 {len(result.get('edited_files', []))} 个。")
            return result
        except Exception as e:
            logs.append(f"[agent] 执行异常: {e}")
            return {"error": str(e)}

    def _find_pptx(self, workspace: str) -> str:
        # the agent follows SKILL.md and creates the project next to the
        # workspace (e.g. <output>/doc-ppt-offline/<run_id>_ppt169_<date>/),
        # so search the workspace AND its parent, preferring this run's id
        candidates = []
        for root_dir in [workspace, os.path.dirname(workspace)]:
            if not os.path.isdir(root_dir):
                continue
            for root, dirs, files in os.walk(root_dir):
                for f in files:
                    if f.endswith(".pptx") and not f.startswith("~$"):
                        candidates.append(os.path.join(root, f))
        if not candidates:
            return ""
        run_id = os.path.basename(workspace)
        for c in candidates:
            if run_id in c:
                return c
        candidates.sort(key=os.path.getmtime, reverse=True)
        return candidates[0]

    def _find_project(self, workspace: str) -> str:
        candidates = []
        for root_dir in [workspace, os.path.dirname(workspace)]:
            if not os.path.isdir(root_dir):
                continue
            for root, dirs, files in os.walk(root_dir):
                if "spec_lock.md" in files:
                    candidates.append(root)
        if not candidates:
            return ""
        run_id = os.path.basename(workspace)
        for c in candidates:
            if run_id in c:
                return c
        candidates.sort(key=lambda p: os.path.getmtime(os.path.join(p, "spec_lock.md")), reverse=True)
        return candidates[0]

    # ------------------------------------------------------------------ #
    # Skill entry
    # ------------------------------------------------------------------ #
    def execute(self, inputs: Dict, output_dir: str = "./outputs") -> Dict:
        source_file = inputs.get("source_file", inputs.get("document_path", ""))
        user_description = inputs.get("description", "")
        skill_md = self._read_skillmd()

        resolved_source = self._resolve_source(source_file)
        if not resolved_source:
            return {
                "success": False,
                "skill": self.name,
                "error": f"源文件不存在: {source_file}",
                "instructions": "请先上传 Word/PDF/PPT/Excel 等源文件再执行。",
                "skill_guidance": skill_md,
            }

        # 每次运行生成独立、可识别的目录（源文件名 + 时分秒），避免覆盖上一次结果
        stem = os.path.splitext(os.path.basename(resolved_source))[0]
        stem = re.sub(r'[^\w\-.]+', '_', stem).strip('._')[:40] or 'deck'
        run_id = f"{stem}_{datetime.now().strftime('%H%M%S')}"

        workspace = os.path.join(output_dir, self.name, run_id)
        os.makedirs(workspace, exist_ok=True)

        logs = []

        # 1. stage the source file in the workspace
        src_copy = os.path.join(workspace, "source" + os.path.splitext(resolved_source)[1])
        shutil.copy2(resolved_source, src_copy)
        logs.append(f"[setup] 源文件已复制到 {os.path.basename(src_copy)}")

        # 2. delegate the whole SKILL.md pipeline to the Coding Agent
        agent_result = self._delegate(workspace, src_copy, user_description, logs)
        agent_ok = "error" not in agent_result

        # 3. locate the produced pptx (project dir detected from spec_lock.md)
        project_path = self._find_project(workspace) if agent_ok else ""
        pptx_path = self._find_pptx(workspace) if agent_ok else ""

        # 4. copy the final pptx to a discoverable top-level location
        top_pptx = ""
        if pptx_path:
            top_pptx = os.path.join(output_dir, f"{run_id}.pptx")
            try:
                shutil.copy2(pptx_path, top_pptx)
                logs.append(f"[export] 已在 outputs 顶层生成副本: {top_pptx}")
            except Exception as e:
                logs.append(f"[export] 复制顶层副本失败: {e}")
                top_pptx = pptx_path

        # 5. collect key generated artifacts
        svg_count = 0
        if project_path and os.path.isdir(os.path.join(project_path, "svg_output")):
            svg_count = len([f for f in os.listdir(os.path.join(project_path, "svg_output"))
                             if f.endswith(".svg")])
        generated_files = []
        if project_path:
            for rel in ["design_spec.md", "spec_lock.md", "notes/total.md"]:
                p = os.path.join(project_path, rel)
                if os.path.exists(p):
                    generated_files.append(rel.replace("\\", "/"))
            if os.path.isdir(os.path.join(project_path, "svg_output")):
                generated_files.append("svg_output/")
            if pptx_path:
                generated_files.append(os.path.relpath(pptx_path, project_path).replace("\\", "/"))

        return {
            "success": bool(pptx_path),
            "skill": self.name,
            "skill_md_file": self.SKILL_MD,
            "source_file": os.path.abspath(resolved_source),
            "project_dir": project_path,
            "run_id": run_id,
            "pptx_file": top_pptx or pptx_path,
            "pptx_source": pptx_path,
            "pptx_generated": bool(pptx_path),
            "svg_pages": svg_count,
            "agent_rounds": agent_result.get("rounds", 0) if isinstance(agent_result, dict) else 0,
            "agent_edited_files": agent_result.get("edited_files", []) if isinstance(agent_result, dict) else [],
            "generated_files": generated_files,
            "generated_files_count": len(generated_files),
            "logs": logs,
            "instructions": "已按 ppt-master(SKILL.md) 流程自动生成原生可编辑 PPTX。",
            "skill_guidance": skill_md,
            "validation": {
                "skill_md_loaded": "SKILL.md" in skill_md or len(skill_md) > 100,
                "svg_generated": svg_count > 0,
                "pptx_generated": bool(pptx_path),
                "agent_completed": agent_ok,
            },
        }
