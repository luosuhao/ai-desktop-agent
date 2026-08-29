"""Skill Manager - Load, manage, and execute skills

Skills are reusable capability packages with:
- name, description, trigger conditions
- input/output schema
- workflow steps
- tool requirements
- templates
- validation criteria
"""

import os
import json
import importlib.util
from typing import List, Dict, Optional, Any, Callable
from datetime import datetime
from abc import ABC, abstractmethod


class Skill(ABC):
    """Base class for all skills
    Aligned with NVIDIA Verified Coding Agent Skills:
    - SKILL.md structured metadata (constraints/references/limitations)
    - Skill Card governance metadata
    - signature/hash integrity check"""

    def __init__(self):
        self.name = "base_skill"
        self.description = ""
        self.trigger = ""
        self.input_schema: Dict = {}
        self.workflow: List[str] = []
        self.tools: List[str] = []
        self.templates: Dict[str, str] = {}
        self.validation: List[str] = []
        self.examples: List[Dict] = []
        self.enabled = True
        self.version = "1.0.0"

        # ---- NVIDIA SKILL.md fields ----
        self.constraints: List[str] = []    # domain constraints / prohibited behavior
        self.references: List[str] = []     # official doc anchors
        self.limitations: List[str] = []    # known limitations / unsupported scenarios

        # ---- Skill Card governance fields ----
        self.owner = "AI Desktop System"
        self.lifecycle = "stable"           # stable / beta / deprecated
        self.risk_level = "low"             # low / medium / high
        self.permissions: Dict = {          # least-privilege boundary
            "file_write": True,
            "command_exec": False,
            "network": False
        }
        self.dependencies: List[str] = []

        # ---- Verification fields ----
        self.expected_hash = ""             # SHA-256 signature of skill definition
        self.signature_verified = False     # hash match result
        self.last_scan_time = ""

    @abstractmethod
    def execute(self, inputs: Dict, output_dir: str = "./outputs") -> Dict:
        """Execute the skill with given inputs"""
        pass

    def validate(self, inputs: Dict) -> List[str]:
        """Validate inputs against schema"""
        errors = []
        required = self.input_schema.get("required", [])
        for field in required:
            if field not in inputs or not inputs.get(field):
                errors.append(f"Missing required field: {field}")
        return errors

    def check_permissions(self, requested: Dict) -> List[str]:
        """Check if the skill's permission boundary allows requested operations.
        Returns list of violations (empty if all allowed)."""
        violations = []
        for op, allowed in requested.items():
            if allowed and not self.permissions.get(op, False):
                violations.append(f"Operation '{op}' not allowed by skill permission scope")
        return violations

    def compute_hash(self) -> str:
        """Compute SHA-256 signature over the skill's key definition attributes."""
        import hashlib
        payload = json.dumps({
            "name": self.name,
            "description": self.description,
            "trigger": self.trigger,
            "workflow": self.workflow,
            "tools": self.tools,
            "validation": self.validation,
            "version": self.version,
            "risk_level": self.risk_level,
            "permissions": self.permissions
        }, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def verify_signature(self) -> bool:
        """Verify the skill's signature (hash) if an expected hash is provided.
        Skills without an expected hash are 'unverified' (not automatically trusted)."""
        computed = self.compute_hash()
        if self.expected_hash:
            self.signature_verified = (computed == self.expected_hash)
        else:
            self.signature_verified = False
        self.last_scan_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return self.signature_verified

    def load_from_skillmd(self, path: str) -> bool:
        """Load skill metadata from a standard SKILL.md file (NVIDIA/agentskills.io format).
        Reads the YAML frontmatter (between leading --- markers) and applies fields.
        Returns True if loaded successfully."""
        try:
            import yaml
            if not os.path.exists(path):
                return False
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()

            # Extract YAML frontmatter between --- markers
            if not text.startswith("---"):
                return False
            parts = text.split("---", 2)
            if len(parts) < 3:
                return False
            meta = yaml.safe_load(parts[1])
            if not isinstance(meta, dict):
                return False

            # Apply metadata fields (only known attributes)
            field_map = {
                "name": "name",
                "version": "version",
                "description": "description",
                "trigger": "trigger",
                "owner": "owner",
                "lifecycle": "lifecycle",
                "risk_level": "risk_level",
                "permissions": "permissions",
                "dependencies": "dependencies",
                "constraints": "constraints",
                "references": "references",
                "limitations": "limitations",
                "validation": "validation",
                "workflow": "workflow",
                "tools": "tools",
            }
            for yaml_key, attr in field_map.items():
                if yaml_key in meta and meta[yaml_key] is not None:
                    value = meta[yaml_key]
                    # trigger is a list in SKILL.md; keep it joinable for matching
                    if yaml_key == "trigger" and isinstance(value, list):
                        value = " ".join(value)
                    setattr(self, attr, value)
            return True
        except Exception as e:
            print(f"[Skill] Failed to load SKILL.md {path}: {e}")
            return False

    def skill_card(self) -> Dict:
        """Return full NVIDIA-style Skill Card metadata for governance/audit."""
        return {
            "name": self.name,
            "version": self.version,
            "owner": self.owner,
            "lifecycle": self.lifecycle,
            "risk_level": self.risk_level,
            "dependencies": self.dependencies,
            "permissions": self.permissions,
            "signature": {
                "expected_hash": self.expected_hash,
                "computed_hash": self.compute_hash(),
                "verified": self.signature_verified
            },
            "last_scan_time": self.last_scan_time,
            "runtime_compatibility": ["AI Desktop System", "Coding Agent"],
            "known_limitations": self.limitations,
            "not_recommended_scenarios": [c for c in self.constraints if "禁止" in c or "not" in c.lower()]
        }

    def to_definition(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "trigger": self.trigger,
            "input_schema": self.input_schema,
            "workflow": self.workflow,
            "tools": self.tools,
            "templates": self.templates,
            "validation": self.validation,
            "examples": self.examples,
            "enabled": self.enabled,
            "version": self.version,
            "constraints": self.constraints,
            "references": self.references,
            "limitations": self.limitations,
            "owner": self.owner,
            "lifecycle": self.lifecycle,
            "risk_level": self.risk_level,
            "permissions": self.permissions,
            "dependencies": self.dependencies,
            "signature_verified": self.signature_verified,
            "last_scan_time": self.last_scan_time
        }


class SkillManager:
    """Manages skill loading, registration, and execution"""

    def __init__(self, skills_dir: str = "../skills"):
        self.skills_dir = os.path.abspath(skills_dir)
        self.skills: Dict[str, Skill] = {}
        self.execution_history: List[Dict] = []
        # Coding Agent shared instance, injected from main.py for skills that
        # delegate their LLM-driven steps (e.g. doc-ppt-offline → ppt-master).
        self.coding_agent = None
        self._register_builtin_skills()

    def _register_builtin_skills(self):
        """Register built-in skills"""
        from .markdown_report_skill import MarkdownReportSkill
        from .word_skill import WordSkill
        from .doc_ppt_online_skill import DocPptOnlineSkill
        from .doc_ppt_offline_skill import DocPptOfflineSkill
        from .excel_ppt_skill import ExcelPptSkill

        builtins = [
            MarkdownReportSkill(),
            WordSkill(),
            DocPptOnlineSkill(),
            DocPptOfflineSkill(),
            ExcelPptSkill()
        ]
        for skill in builtins:
            # Load metadata from standard SKILL.md if available
            manifest = os.path.join(self.skills_dir, "manifests", skill.name, "SKILL.md")
            skill.load_from_skillmd(manifest)
            # Re-sign with final attributes (first-party official skill)
            skill.expected_hash = skill.compute_hash()
            self.register(skill)

    def register(self, skill: Skill):
        """Register a skill (runs signature verification)"""
        skill.verify_signature()
        self.skills[skill.name] = skill

    def get_skill(self, name: str) -> Optional[Skill]:
        return self.skills.get(name)

    def list_skills(self) -> List[Dict]:
        return [s.to_definition() for s in self.skills.values()]

    def get_skill_cards(self) -> List[Dict]:
        """Return NVIDIA-style Skill Cards for all skills (governance metadata)."""
        cards = []
        for skill in self.skills.values():
            if skill.enabled or skill.lifecycle != "deprecated":
                cards.append(skill.skill_card())
        return cards

    def match_skills(self, task_description: str) -> List[Dict]:
        """Match skills to a task description.
        Scores: trigger word substring (+1 each), skill name mentioned (+3),
        and format keyword from skill name (e.g. 'ppt'/'excel'/'word'/'markdown') in task (+1)."""
        matched = []
        task_lower = task_description.lower()

        for skill in self.skills.values():
            if not skill.enabled:
                continue

            match_score = 0

            # 1. Trigger word matches (exact substring)
            trigger_words = skill.trigger.lower().split()
            for w in trigger_words:
                if w and w in task_lower:
                    match_score += 1

            # 2. Skill name mentioned in task
            if skill.name.lower() in task_lower:
                match_score += 3

            # 3. Format keyword from skill name appears in task
            name_lower = skill.name.lower()
            format_kw = None
            if 'ppt' in name_lower:
                format_kw = 'ppt'
            elif 'excel' in name_lower:
                format_kw = 'excel'
            elif 'word' in name_lower:
                format_kw = 'word'
            elif 'markdown' in name_lower:
                format_kw = 'markdown'
            if format_kw and format_kw in task_lower:
                match_score += 1

            if match_score > 0:
                matched.append({
                    "skill": skill.to_definition(),
                    "match_score": match_score
                })

        matched.sort(key=lambda x: -x["match_score"])
        return matched

    def execute_skill(self, skill_name: str, inputs: Dict,
                      output_dir: str = "./outputs") -> Dict:
        """Execute a skill and record history
        Includes: input validation, permission scope check, signature check, audit logging."""
        skill = self.get_skill(skill_name)
        if not skill:
            return {"success": False, "error": f"Skill not found: {skill_name}"}

        if not skill.enabled:
            return {"success": False, "error": f"Skill disabled: {skill_name}"}

        # Validate inputs
        validation_errors = skill.validate(inputs)
        if validation_errors:
            return {"success": False, "errors": validation_errors}

        # Signature check: unverified skills are flagged (not auto-blocked, but audited)
        skill.verify_signature()

        # Inject shared Coding Agent for skills that delegate LLM-driven steps
        if hasattr(skill, "coding_agent"):
            skill.coding_agent = getattr(self, "coding_agent", None)

        # Permission scope check (defense in depth)
        perm_request = inputs.get("_permissions", {})
        violations = skill.check_permissions(perm_request)
        if violations:
            return {"success": False, "errors": violations}

        # Execute
        start_time = datetime.now()
        try:
            result = skill.execute(inputs, output_dir)
            result["skill_name"] = skill_name
            result["started_at"] = start_time.isoformat()
            result["completed_at"] = datetime.now().isoformat()
            result["success"] = True
        except Exception as e:
            result = {
                "success": False,
                "skill_name": skill_name,
                "error": str(e),
                "started_at": start_time.isoformat(),
                "completed_at": datetime.now().isoformat()
            }

        # Audit log with governance metadata
        result["skill_version"] = skill.version
        result["risk_level"] = skill.risk_level
        result["hash_valid"] = skill.signature_verified
        result["lifecycle"] = skill.lifecycle

        self.execution_history.append(result)
        return result

    def get_history(self, limit: int = 20) -> List[Dict]:
        return self.execution_history[-limit:]

    def load_skill_from_file(self, file_path: str) -> Optional[Skill]:
        """Load a skill from a Python file.
        Runs the light-weight verification pipeline:
        structure check -> metadata completeness -> signature verification.
        Unverified skills are flagged (signature_verified=False), not auto-trusted."""
        try:
            spec = importlib.util.spec_from_file_location("custom_skill", file_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and issubclass(attr, Skill) and attr != Skill:
                    skill = attr()
                    # Load metadata from standard SKILL.md if available
                    manifest = os.path.join(self.skills_dir, "manifests", skill.name, "SKILL.md")
                    skill.load_from_skillmd(manifest)
                    # Metadata completeness check
                    missing = []
                    for field in ["name", "description", "trigger", "input_schema", "workflow"]:
                        if not getattr(skill, field, ""):
                            missing.append(field)
                    if missing:
                        skill.signature_verified = False
                        skill.last_scan_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        print(f"[Skill] {skill.name}: metadata incomplete ({missing}) - UNVERIFIED")
                    else:
                        skill.verify_signature()
                        status = "VERIFIED" if skill.signature_verified else "UNVERIFIED (no expected hash)"
                        print(f"[Skill] {skill.name} v{skill.version}: {status}")
                    self.register(skill)
                    return skill
        except Exception as e:
            print(f"Failed to load skill from {file_path}: {e}")
        return None

    def load_skills_from_directory(self, directory: str = None):
        """Load all skill files from a directory"""
        dir_path = directory or self.skills_dir
        if not os.path.exists(dir_path):
            return

        for f in os.listdir(dir_path):
            if f.endswith('_skill.py') and not f.startswith('__'):
                file_path = os.path.join(dir_path, f)
                self.load_skill_from_file(file_path)
