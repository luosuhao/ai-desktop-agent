"""Excel to PPT Skill - Wrapper around external SKILL.md
The SKILL.md content is from an external repo and must NOT be modified.
This wrapper reads it and provides the workflow guidance + source file handling.
"""

import os
import shutil
import subprocess
import sys
from typing import Dict
from .skill_manager import Skill


class ExcelPptSkill(Skill):
    """excel-ppt：从 Excel 工作簿生成原生 PowerPoint 模板填充的 PPT 内容规划产物"""

    SKILL_MD = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "skills", "ppt-skill", "excel-ppt", "ppt-template-generator", "SKILL.md"
    )

    def __init__(self):
        super().__init__()
        self.name = "excel-ppt"
        self.description = "从 Excel 工作簿生成 PPT 内容规划产物（原生 PowerPoint 模板填充）"
        self.trigger = "PPT 生成PPT 转PPT Excel转PPT 表格转PPT excel-ppt 数据PPT"
        self.input_schema = {
            "type": "object",
            "required": [],
            "properties": {
                "source_file": {"type": "string", "description": "源 Excel 文件路径"},
                "document_path": {"type": "string", "description": "源文档路径（别名）"}
            }
        }
        self.workflow = [
            "1. 读取 SKILL.md 工作流指导",
            "2. 复制源 Excel 到项目目录",
            "3. 解析 Excel 生成 excel-content-manifest.json 与 slide-plan.json"
        ]
        self.tools = ["file_read", "file_write"]
        self.validation = ["成功输出 PPT 内容规划产物"]
        self.owner = "第三方"
        self.lifecycle = "beta"
        self.risk_level = "medium"
        self.permissions = {"file_write": True, "command_exec": True, "network": False}
        self.dependencies = ["python3", "openpyxl", "python-pptx"]
        # First-party wrapper, but points to external skill - sign as verified wrapper
        self.expected_hash = self.compute_hash()

    def _read_skillmd(self) -> str:
        """Read the external SKILL.md content (never modified)"""
        try:
            with open(self.SKILL_MD, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"[无法读取 SKILL.md: {e}]"

    # Full pipeline steps (in order) following the skill's SKILL.md
    PIPELINE_SCRIPTS = [
        ("excel_intake.py", "excel-content-manifest.json"),
        ("visual_asset_planner.py", "visual-asset-plan.json"),
        ("python_visual_renderer.py", None),  # renders table/chart PNGs
        ("sheet_md_asset_builder.py", "sheet-md-manifest.json"),
        ("ppt_generation_plan_builder.py", "ppt-generation-plan.json"),
        ("pptx_step3b_composer.py", None),   # composes PPTX
        ("pptx_step6_qa.py", None),          # QA
    ]

    def _scripts_dir(self) -> str:
        return os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "skills", "ppt-skill", "excel-ppt", "ppt-template-generator", "scripts"
        )

    def _run_pipeline(self, xlsx_path: str, intake_dir: str, logs: list, generated_files: list) -> bool:
        """Run the full excel->ppt pipeline. Returns True if PPTX produced."""
        scripts = self._scripts_dir()
        intake_abs = os.path.abspath(intake_dir)
        manifest_path = os.path.join(intake_abs, "excel-content-manifest.json")

        for script, marker in self.PIPELINE_SCRIPTS:
            script_path = os.path.join(scripts, script)
            if script == "excel_intake.py":
                cmd = [sys.executable, script_path, os.path.abspath(xlsx_path), "--output-dir", intake_abs]
            elif script == "visual_asset_planner.py":
                cmd = [sys.executable, script_path, manifest_path, "--pretty"]
            elif script == "python_visual_renderer.py":
                cmd = [sys.executable, script_path, os.path.join(intake_abs, "visual-asset-plan.json"), "--pretty"]
            elif script == "sheet_md_asset_builder.py":
                cmd = [sys.executable, script_path, manifest_path, "--pretty"]
            elif script == "ppt_generation_plan_builder.py":
                cmd = [sys.executable, script_path, intake_abs, "--template-id", "fund-pension-annuity", "--pretty"]
            elif script in ("pptx_step3b_composer.py", "pptx_step6_qa.py"):
                cmd = [sys.executable, script_path, intake_abs]
            else:
                continue

            try:
                r = subprocess.run(cmd, capture_output=True, timeout=300)
                if r.stdout.strip():
                    logs.append(f"[{script}] {r.stdout.decode('utf-8', errors='replace')[:300]}")
                if r.stderr.strip():
                    logs.append(f"[{script} err] {r.stderr.decode('utf-8', errors='replace')[:300]}")
            except Exception as e:
                logs.append(f"[{script}] ERROR: {e}")

        # Collect all generated files
        for root, dirs, files in os.walk(intake_abs):
            for f in files:
                full = os.path.join(root, f)
                generated_files.append(os.path.relpath(full, intake_abs).replace("\\", "/"))

        # Check for PPTX output
        out_dir = os.path.join(intake_abs, "output")
        pptx_files = []
        if os.path.isdir(out_dir):
            pptx_files = [f for f in os.listdir(out_dir) if f.endswith(".pptx")]
        return len(pptx_files) > 0

    def execute(self, inputs: Dict, output_dir: str = "./outputs") -> Dict:
        """Run the full excel->ppt pipeline to produce a complete PPTX"""
        source_file = inputs.get("source_file", inputs.get("document_path", ""))
        skill_md = self._read_skillmd()

        project_dir = os.path.join(output_dir, self.name)
        intake_dir = os.path.join(project_dir, "intake")
        os.makedirs(intake_dir, exist_ok=True)

        # Resolve source file (may be relative to backend CWD, e.g. uploads/xxx.xlsx)
        resolved_source = source_file
        if source_file and not os.path.exists(source_file):
            for base in [".", "..", "./uploads", "../uploads", "../ppt-skill"]:
                cand = os.path.join(base, source_file)
                if os.path.exists(cand):
                    resolved_source = cand
                    break

        if not resolved_source or not os.path.exists(resolved_source):
            return {
                "success": False,
                "skill": self.name,
                "error": f"源文件不存在: {source_file}",
                "instructions": "请先上传 Excel 文件再执行。",
                "skill_guidance": skill_md,
            }

        logs = []
        generated_files = []
        pptx_ok = False
        try:
            pptx_ok = self._run_pipeline(resolved_source, intake_dir, logs, generated_files)
        except Exception as e:
            return {
                "success": False,
                "skill": self.name,
                "error": str(e),
                "logs": logs,
                "skill_guidance": skill_md,
            }

        pptx_path = ""
        out_dir = os.path.join(intake_dir, "output")
        if os.path.isdir(out_dir):
            for f in os.listdir(out_dir):
                if f.endswith(".pptx"):
                    pptx_path = os.path.join(out_dir, f)
                    break

        manifest_path = os.path.join(intake_dir, "excel-content-manifest.json")
        plan_path = os.path.join(intake_dir, "ppt-generation-plan.json")

        return {
            "success": pptx_ok,
            "skill": self.name,
            "skill_md_file": self.SKILL_MD,
            "source_file": os.path.abspath(resolved_source),
            "project_dir": project_dir,
            "intake_dir": intake_dir,
            "pptx_file": pptx_path,
            "pptx_generated": pptx_ok,
            "manifest_path": manifest_path if os.path.exists(manifest_path) else "",
            "manifest_generated": os.path.exists(manifest_path),
            "generation_plan_path": plan_path if os.path.exists(plan_path) else "",
            "generated_files": generated_files,
            "generated_files_count": len(generated_files),
            "logs": logs,
            "instructions": "已按 ppt-template-generator 完整流水线生成 PPT：intake→视觉规划→渲染→文本层→生成计划→PPTX 组合→QA。"
                            "PPTX 文件见 pptx_file。",
            "skill_guidance": skill_md,
            "validation": {
                "skill_md_loaded": "SKILL.md" in skill_md or len(skill_md) > 100,
                "manifest_generated": os.path.exists(manifest_path),
                "pptx_generated": pptx_ok,
                "files_generated": len(generated_files)
            }
        }
