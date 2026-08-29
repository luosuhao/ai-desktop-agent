"""Skill System - Reusable capability packages for document generation

Skills extend the AI Desktop system with:
- Markdown report generation
- Word lab report generation
- PPT presentation generation
- Data analysis / Math Modeling C problem
"""

from .skill_manager import SkillManager, Skill
from .markdown_report_skill import MarkdownReportSkill
from .word_skill import WordSkill
from .doc_ppt_online_skill import DocPptOnlineSkill
from .doc_ppt_offline_skill import DocPptOfflineSkill
from .excel_ppt_skill import ExcelPptSkill
