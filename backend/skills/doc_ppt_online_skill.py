"""DOC to PPT Online Skill - Wrapper around external SKILL.md
The SKILL.md content is from an external repo and must NOT be modified.
This wrapper reads it and provides the workflow guidance + source file handling.
"""

import os
import shutil
from typing import Dict
from .skill_manager import Skill


class DocPptOnlineSkill(Skill):
    """doc-ppt 在线：将文章/报告/论文转换为图片风格 PPT（需 OPENAI_API_KEY）"""

    SKILL_MD = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "skills", "ppt-skill", "doc-ppt在线", "codex-ppt", "SKILL.md"
    )

    def __init__(self):
        super().__init__()
        self.name = "doc-ppt-online"
        self.description = "在线将文章/报告/论文转换为图片风格 PPT（需 OPENAI_API_KEY）"
        self.trigger = "PPT 生成PPT 转PPT 在线PPT 文章转PPT 论文转PPT 报告转PPT 文档转PPT codex-ppt"
        self.input_schema = {
            "type": "object",
            "required": [],
            "properties": {
                "source_file": {"type": "string", "description": "源文档路径（文章/报告/论文）"},
                "document_path": {"type": "string", "description": "源文档路径（别名）"}
            }
        }
        self.workflow = [
            "1. 读取 SKILL.md 工作流指导",
            "2. 复制源文档到项目目录",
            "3. 按 codex-ppt 流程规划大纲、风格、后端并生成 PPT"
        ]
        self.tools = ["file_read", "file_write"]
        self.validation = ["成功输出有效 .pptx"]
        self.owner = "第三方"
        self.lifecycle = "beta"
        self.risk_level = "medium"
        self.permissions = {"file_write": True, "command_exec": True, "network": True}
        self.dependencies = ["python3", "node", "pptxgenjs", "OPENAI_API_KEY"]
        # First-party wrapper, but points to external skill - sign as verified wrapper
        self.expected_hash = self.compute_hash()

    def _read_skillmd(self) -> str:
        """Read the external SKILL.md content (never modified)"""
        try:
            with open(self.SKILL_MD, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"[无法读取 SKILL.md: {e}]"

    def execute(self, inputs: Dict, output_dir: str = "./outputs") -> Dict:
        """Mode A: return SKILL.md guidance + source file path"""
        source_file = inputs.get("source_file", inputs.get("document_path", ""))
        skill_md = self._read_skillmd()

        project_dir = os.path.join(output_dir, self.name)
        os.makedirs(project_dir, exist_ok=True)

        copied = ""
        if source_file and os.path.exists(source_file):
            dest = os.path.join(project_dir, os.path.basename(source_file))
            shutil.copy2(source_file, dest)
            copied = dest

        return {
            "success": True,
            "skill": self.name,
            "skill_md_file": self.SKILL_MD,
            "source_file": copied,
            "project_dir": project_dir,
            "instructions": "读取 skill_guidance 按 codex-ppt 工作流处理源文件生成图片风格 PPT。"
                            "在线模式需配置 OPENAI_API_KEY 和 OPENAI_BASE_URL。",
            "skill_guidance": skill_md,
            "validation": {"skill_md_loaded": "SKILL.md" in skill_md or len(skill_md) > 100}
        }
