"""AI Agent Manager - Core agent harness with model API adapters"""
import json
import os
import time
import hashlib
import subprocess
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime
from openai import OpenAI
from config import load_model_config


class ModelAdapter:
    """Model API adapter supporting OpenAI/DeepSeek/custom APIs"""

    def __init__(self, config: dict = None):
        self.config = config or load_model_config()
        self.client = OpenAI(
            api_key=self.config.get("api_key", ""),
            base_url=self.config.get("api_base", "https://api.openai.com/v1"),
            timeout=300.0  # 5 min per API call (Ollama local model is slow)
        )
        self.model = self.config.get("model", "gpt-4o")
        self.temperature = self.config.get("temperature", 0.7)
        self.max_tokens = self.config.get("max_tokens", 4096)

    def chat(self, messages: List[Dict], tools: List[Dict] = None) -> Dict:
        """Send chat completion request"""
        params = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if tools:
            params["tools"] = tools
            params["tool_choice"] = "auto"

        response = self.client.chat.completions.create(**params)
        result = response.choices[0].message

        return {
            "role": "assistant",
            "content": result.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in (result.tool_calls or [])
            ] if result.tool_calls else []
        }


class ToolRegistry:
    """Registry for agent tools"""

    def __init__(self):
        self._tools: Dict[str, Dict] = {}
        self._handlers: Dict[str, Callable] = {}

    def register(self, name: str, schema: Dict, handler: Callable):
        self._tools[name] = schema
        self._handlers[name] = handler

    def get_schemas(self) -> List[Dict]:
        return list(self._tools.values())

    def execute(self, name: str, arguments: Dict) -> str:
        handler = self._handlers.get(name)
        if not handler:
            return json.dumps({"error": f"Unknown tool: {name}"})
        try:
            result = handler(**arguments)
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)})


class CodingAgent:
    """Core Coding Agent with task planning, execution, and rollback"""

    def __init__(self, model_adapter: ModelAdapter = None):
        self.adapter = model_adapter or ModelAdapter()
        self.tools = ToolRegistry()
        # Determine project root: if CWD is a "backend" dir, use its parent
        _cwd = os.getcwd()
        if os.path.basename(_cwd).lower() in ('backend', 'server', 'app'):
            self.project_root = os.path.dirname(_cwd)
        else:
            self.project_root = _cwd
        self.checkpoints: List[Dict] = []
        self.initial_files: set = set()  # Files that existed before the task started
        self.file_versions: Dict[str, List[Dict]] = {}  # file_path -> list of version records
        self.task_state = {
            "task_id": "",
            "description": "",
            "plan": [],
            "current_step": 0,
            "read_files": [],
            "edited_files": [],
            "test_results": [],
            "errors": []
        }
        self.conversation_history: List[Dict] = []
        # Timeout for the execute_command tool (skill pipelines can be slow;
        # skill wrappers may raise this, e.g. doc-ppt-offline sets 900s)
        self.command_timeout = 60
        self._register_default_tools()

    def _register_default_tools(self):
        """Register 8 default agent tools: read/write/list/command/checkpoint/rollback/tests/diff"""
        self.tools.register("read_file", {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read file contents",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Path to file"}
                    },
                    "required": ["file_path"]
                }
            }
        }, self._read_file)

        self.tools.register("write_file", {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "Write content to file (auto-creates checkpoint if file exists)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Path to file"},
                        "content": {"type": "string", "description": "Content to write"}
                    },
                    "required": ["file_path", "content"]
                }
            }
        }, self._write_file)

        self.tools.register("execute_command", {
            "type": "function",
            "function": {
                "name": "execute_command",
                "description": "Execute a shell command (javac/java/python etc.)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "Shell command to run"},
                        "work_dir": {"type": "string", "description": "Working directory", "default": "."}
                    },
                    "required": ["command"]
                }
            }
        }, self._execute_command)

        self.tools.register("create_checkpoint", {
            "type": "function",
            "function": {
                "name": "create_checkpoint",
                "description": "Create snapshot of current file state(s) before making changes",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "files": {"type": "array", "items": {"type": "string"}, "description": "List of file paths to snapshot"}
                    },
                    "required": ["files"]
                }
            }
        }, self._create_checkpoint)

        self.tools.register("rollback_checkpoint", {
            "type": "function",
            "function": {
                "name": "rollback_checkpoint",
                "description": "Rollback to a previous checkpoint (restores old content, deletes new files)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "checkpoint_id": {"type": "string", "description": "Checkpoint ID to rollback to"}
                    },
                    "required": ["checkpoint_id"]
                }
            }
        }, self._rollback_checkpoint)

        self.tools.register("list_directory", {
            "type": "function",
            "function": {
                "name": "list_directory",
                "description": "List files and directories in a given path (structured output)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Directory path to list"}
                    },
                    "required": ["path"]
                }
            }
        }, self._list_directory)

        self.tools.register("run_tests", {
            "type": "function",
            "function": {
                "name": "run_tests",
                "description": "Compile and run Java tests, returning structured results",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "test_dir": {"type": "string", "description": "Directory containing test files"},
                        "compile_only": {"type": "boolean", "description": "Only compile, don't run", "default": False}
                    },
                    "required": ["test_dir"]
                }
            }
        }, self._run_tests)

        self.tools.register("get_git_diff", {
            "type": "function",
            "function": {
                "name": "get_git_diff",
                "description": "Show code changes using git diff, or list edited files for non-git repos",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Specific file to diff (optional)", "default": ""}
                    }
                }
            }
        }, self._get_git_diff)

    def _resolve_path(self, file_path: str) -> str:
        """Resolve a file path relative to project root"""
        if os.path.isabs(file_path):
            return file_path
        return os.path.normpath(os.path.join(self.project_root, file_path))

    def _save_initial_files(self):
        """Scan all existing files in the project before task starts.
        Used by rollback to distinguish new files from modified files."""
        self.initial_files = set()
        for root, dirs, files in os.walk(self.project_root):
            # Skip hidden and common ignore dirs
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('__pycache__', 'node_modules', 'venv', 'chroma_db', 'wiki_db', 'outputs', 'uploads')]
            for f in files:
                relpath = os.path.relpath(os.path.join(root, f), self.project_root)
                self.initial_files.add(relpath.replace('\\', '/'))

    def _read_file(self, file_path: str) -> Dict:
        try:
            full_path = self._resolve_path(file_path)
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.task_state["read_files"].append(file_path)
            return {"success": True, "content": content, "path": file_path}
        except Exception as e:
            return {"success": False, "error": f"File not found or unreadable: {file_path} ({str(e)})"}

    def _normalize_path(self, file_path: str) -> str:
        """Normalize any file path to a consistent relative path (forward slashes).
        Ensures the same physical file always uses the same key in file_versions."""
        full = self._resolve_path(file_path)
        rel = os.path.relpath(os.path.abspath(full), self.project_root)
        return rel.replace('\\', '/')

    def _write_file(self, file_path: str, content: str) -> Dict:
        try:
            full_path = self._resolve_path(file_path)
            file_exists = os.path.exists(full_path)
            normalized_path = self._normalize_path(file_path)

            # Auto-checkpoint: snapshot existing file before overwriting
            if file_exists:
                with open(full_path, "r", encoding="utf-8") as f:
                    old_content = f.read()
                # If this is the first write to this file, record the original content as version 1
                if normalized_path not in self.file_versions:
                    self._record_version(normalized_path, old_content, "", "original")
                cp_id = f"cp_auto_{int(time.time())}"
                self.checkpoints.append({
                    "id": cp_id,
                    "snapshot": {file_path: old_content},
                    "timestamp": time.time(),
                    "is_new_file": False
                })
                # Record a new version for this file (the modified content)
                self._record_version(normalized_path, content, cp_id, "modified")
            else:
                cp_id = f"cp_new_{int(time.time())}"
                self.checkpoints.append({
                    "id": cp_id,
                    "snapshot": {},  # empty snapshot = new file marker
                    "timestamp": time.time(),
                    "is_new_file": True,
                    "new_file_path": normalized_path
                })
                # Record a new version for this file
                self._record_version(normalized_path, content, cp_id, "new")

            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            self.task_state["edited_files"].append(file_path)

            return {"success": True, "path": file_path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _record_version(self, file_path: str, content: str, checkpoint_id: str, change_type: str):
        """Record a version entry for a file"""
        if file_path not in self.file_versions:
            self.file_versions[file_path] = []
        version_num = len(self.file_versions[file_path]) + 1
        self.file_versions[file_path].append({
            "version": version_num,
            "content": content,
            "checkpoint_id": checkpoint_id,
            "change_type": change_type,  # 'original', 'new', 'modified'
            "timestamp": time.time()
        })

    def _execute_command(self, command: str, work_dir: str = ".") -> Dict:
        try:
            import subprocess
            env = os.environ.copy()
            # Ensure JDK bin is in PATH for javac/java
            _jdk_bin = r"C:\Program Files\Microsoft\jdk-17.0.19.10-hotspot\bin"
            if os.path.isfile(os.path.join(_jdk_bin, "javac.exe")):
                env["PATH"] = _jdk_bin + os.pathsep + env.get("PATH", "")
            # Resolve work_dir relative to project root
            resolved_cwd = self._resolve_path(work_dir) if work_dir else self.project_root
            result = subprocess.run(
                command, shell=True, cwd=resolved_cwd,
                capture_output=True, text=True, timeout=self.command_timeout,
                env=env
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Command timed out"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _create_checkpoint(self, files: List[str]) -> Dict:
        checkpoint_id = f"cp_{int(time.time())}"
        snapshot = {}
        for f in files:
            full = self._resolve_path(f)
            if os.path.exists(full):
                with open(full, "r", encoding="utf-8") as fh:
                    snapshot[f] = fh.read()
        self.checkpoints.append({
            "id": checkpoint_id,
            "snapshot": snapshot,
            "timestamp": time.time(),
            "is_new_file": False
        })
        return {"success": True, "checkpoint_id": checkpoint_id, "files_count": len(snapshot)}

    def _rollback_checkpoint(self, checkpoint_id: str) -> Dict:
        """Rollback: restore old content AND delete new files created after checkpoint"""
        target_cp = None
        target_idx = -1
        for i, cp in enumerate(self.checkpoints):
            if cp["id"] == checkpoint_id:
                target_cp = cp
                target_idx = i
                break

        if not target_cp:
            return {"success": False, "error": f"Checkpoint {checkpoint_id} not found"}

        restored = []
        deleted_new_files = []
        removed_cp_ids = [checkpoint_id]  # versions tied to these checkpoints should be pruned
        errors = []

        # Phase 1: restore snapshot files (for existing files)
        snapshot = target_cp.get("snapshot", {})
        for fpath, content in snapshot.items():
            if not fpath or not fpath.strip():
                continue
            try:
                full = self._resolve_path(fpath)
                fdir = os.path.dirname(full)
                if fdir:
                    os.makedirs(fdir, exist_ok=True)
                with open(full, "w", encoding="utf-8") as fh:
                    fh.write(content)
                restored.append(fpath)
            except Exception as e:
                errors.append(f"Failed to restore {fpath}: {e}")

        # Phase 2: delete new files that were created AFTER this checkpoint
        # (checkpoints after target_idx that are new-file markers)
        for cp in self.checkpoints[target_idx + 1:]:
            if cp.get("is_new_file") and cp.get("new_file_path"):
                new_path = cp["new_file_path"]
                full = self._resolve_path(new_path)
                try:
                    if os.path.exists(full):
                        os.remove(full)
                        deleted_new_files.append(new_path)
                        removed_cp_ids.append(cp["id"])
                        # Also remove .class files for Java
                        class_file = full.rsplit('.', 1)[0] + '.class'
                        if os.path.exists(class_file):
                            os.remove(class_file)
                except Exception as e:
                    errors.append(f"Failed to delete new file {new_path}: {e}")

        # Prune version history: remove versions created by the rolled-back checkpoint
        # and any deleted new files
        self._prune_versions(removed_cp_ids)

        return {
            "success": True,
            "checkpoint_id": checkpoint_id,
            "restored_files": restored,
            "deleted_new_files": deleted_new_files,
            "errors": errors
        }

    def _prune_versions(self, removed_cp_ids):
        """Remove file versions that belong to the given checkpoint IDs.
        Drops files with no remaining versions."""
        removed_set = set(removed_cp_ids)
        for path in list(self.file_versions.keys()):
            versions = self.file_versions[path]
            kept = [v for v in versions if v["checkpoint_id"] not in removed_set]
            if kept:
                self.file_versions[path] = kept
            else:
                del self.file_versions[path]

    def get_file_versions(self) -> Dict:
        """Return version history for all edited files"""
        result = {}
        for path, versions in self.file_versions.items():
            result[path] = [
                {
                    "version": v["version"],
                    "checkpoint_id": v["checkpoint_id"],
                    "change_type": v["change_type"],
                    "timestamp": v["timestamp"],
                    "size": len(v["content"])
                }
                for v in versions
            ]
        return result

    def get_file_content(self, file_path: str, version: int) -> Dict:
        """Return the full content of a specific file version"""
        path = self._normalize_path(file_path)
        versions = self.file_versions.get(path, [])
        for v in versions:
            if v["version"] == version:
                return {"success": True, "file": path, "version": version, "content": v["content"]}
        return {"success": False, "error": f"Version {version} not found for {path}"}

    def get_file_diff(self, file_path: str, from_v: int = 0, to_v: int = None) -> Dict:
        """Generate unified diff between two versions of a file.
        from_v=0 means the empty/original baseline. to_v defaults to the latest version."""
        import difflib
        path = self._normalize_path(file_path)
        versions = self.file_versions.get(path, [])
        if not versions:
            return {"success": False, "error": f"No versions found for {path}"}

        if to_v is None:
            to_v = versions[-1]["version"]

        def content_of(v):
            for rec in versions:
                if rec["version"] == v:
                    return rec["content"]
            return None

        to_content = content_of(to_v)
        if to_content is None:
            return {"success": False, "error": f"Version {to_v} not found"}

        if from_v == 0:
            from_content = ""
        else:
            from_content = content_of(from_v)
            if from_content is None:
                return {"success": False, "error": f"Version {from_v} not found"}

        diff_lines = list(difflib.unified_diff(
            from_content.splitlines(keepends=True),
            to_content.splitlines(keepends=True),
            fromfile=f"{path}@v{from_v}" if from_v else f"{path}@(empty)",
            tofile=f"{path}@v{to_v}",
            lineterm='\n'
        ))

        return {
            "success": True,
            "file": path,
            "from_version": from_v,
            "to_version": to_v,
            "diff": "".join(diff_lines),
            "has_changes": len(diff_lines) > 0
        }

    def _list_directory(self, path: str) -> Dict:
        """List files and directories in a structured format"""
        try:
            full_path = self._resolve_path(path)
            if not os.path.exists(full_path):
                return {"success": False, "error": f"Directory not found: {path}"}
            if not os.path.isdir(full_path):
                return {"success": False, "error": f"Not a directory: {path}"}

            items = []
            for entry in sorted(os.listdir(full_path)):
                entry_path = os.path.join(full_path, entry)
                is_dir = os.path.isdir(entry_path)
                try:
                    size = os.path.getsize(entry_path) if not is_dir else 0
                except OSError:
                    size = 0
                items.append({
                    "name": entry,
                    "is_directory": is_dir,
                    "size": size,
                    "extension": os.path.splitext(entry)[1].lower() if not is_dir else ""
                })

            return {
                "success": True,
                "path": path,
                "items": items,
                "total_items": len(items)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _run_tests(self, test_dir: str, compile_only: bool = False) -> Dict:
        """Compile and optionally run Java tests"""
        try:
            test_path = self._resolve_path(test_dir)
            if not os.path.isdir(test_path):
                return {"success": False, "error": f"Test directory not found: {test_dir}"}

            env = os.environ.copy()
            _jdk_bin = r"C:\Program Files\Microsoft\jdk-17.0.19.10-hotspot\bin"
            if os.path.isfile(os.path.join(_jdk_bin, "javac.exe")):
                env["PATH"] = _jdk_bin + os.pathsep + env.get("PATH", "")

            results = []
            all_passed = True

            # Find all .java files
            java_files = [f for f in os.listdir(test_path) if f.endswith('.java')]
            if not java_files:
                return {"success": False, "error": f"No Java files found in {test_dir}"}

            # Compile all .java files
            escaped_files = [f.replace(' ', '" "') for f in java_files]
            compile_cmd = "javac " + " ".join(escaped_files)
            compile_result = subprocess.run(
                compile_cmd, shell=True, cwd=test_path,
                capture_output=True, text=True, timeout=60, env=env
            )

            if compile_result.returncode != 0:
                return {
                    "success": False,
                    "compile_errors": compile_result.stderr,
                    "stdout": compile_result.stdout,
                    "tests_run": 0,
                    "tests_passed": 0
                }

            if compile_only:
                return {
                    "success": True,
                    "compile_result": "Compilation successful",
                    "files_compiled": len(java_files),
                    "tests_run": 0,
                    "tests_passed": 0
                }

            # Run each file that has a main method
            for jf in java_files:
                class_name = jf[:-5]  # Remove .java
                run_result = subprocess.run(
                    f"java {class_name}", shell=True, cwd=test_path,
                    capture_output=True, text=True, timeout=60, env=env
                )
                passed = run_result.returncode == 0
                if not passed:
                    all_passed = False
                results.append({
                    "class": class_name,
                    "passed": passed,
                    "stdout": run_result.stdout,
                    "stderr": run_result.stderr,
                    "exit_code": run_result.returncode
                })

            # Record in task_state
            self.task_state["test_results"].extend(results)

            return {
                "success": all_passed,
                "tests_run": len(results),
                "tests_passed": sum(1 for r in results if r["passed"]),
                "results": results
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Test execution timed out"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _get_git_diff(self, file_path: str = "") -> Dict:
        """Show code changes. Uses git diff if available, otherwise lists edited files."""
        try:
            # Try git diff first
            git_cmd = ["git", "diff"]
            if file_path:
                git_cmd.append(file_path)

            git_result = subprocess.run(
                git_cmd, cwd=self.project_root,
                capture_output=True, text=True, timeout=15
            )

            if git_result.returncode == 0 and git_result.stdout.strip():
                return {
                    "success": True,
                    "source": "git",
                    "diff": git_result.stdout,
                    "has_changes": True
                }

            # No git repo or no git diff — list files edited in the current task
            edited = self.task_state.get("edited_files", [])
            read_files = self.task_state.get("read_files", [])

            changes = []
            for f in edited:
                changes.append({
                    "file": f,
                    "status": "modified"
                })

            return {
                "success": True,
                "source": "task_state" if not (git_result.returncode == 0 and git_result.stdout.strip()) else "git",
                "has_changes": len(changes) > 0,
                "edited_files": changes,
                "note": "Not a git repository or no changes tracked by git. Showing task-level edits." if not (git_result.returncode == 0 and git_result.stdout.strip()) else ""
            }

        except Exception as e:
            # Fallback: show task_state edits
            edited = self.task_state.get("edited_files", [])
            changes = [{"file": f, "status": "modified"} for f in edited]
            return {
                "success": True,
                "source": "task_state",
                "has_changes": len(changes) > 0,
                "edited_files": changes,
                "note": f"git not available, showing task-level edits. Error: {str(e)}"
            }

    def execute_task(self, task_description: str, max_rounds: int = 20) -> Dict:
        """Execute a coding task through the agent loop"""
        # Save initial file state and reset task state
        self._save_initial_files()
        self.task_state = {
            "task_id": hashlib.md5(task_description.encode()).hexdigest()[:8],
            "description": task_description,
            "plan": [],
            "current_step": 0,
            "read_files": [],
            "edited_files": [],
            "test_results": [],
            "errors": []
        }

        system_prompt = f"""You are an AI Coding Agent. Your task:
{task_description}

CRITICAL RULES:
1. You MUST use write_file() to save any generated code. DO NOT just print code in chat.
2. Default to writing Java code unless the task explicitly specifies another language.
3. After writing code, use run_tests() or execute_command() to compile and verify.
4. Use list_directory() to explore the project structure when needed.
5. Use get_git_diff() to review changes before finalizing.
6. Create checkpoints before editing existing files.

Available tools:
- read_file(path): Read file contents
- write_file(path, content): Save code to file (auto-creates checkpoint)
- execute_command(cmd, work_dir): Run shell/compile commands
- create_checkpoint(files): Manual checkpoint before editing
- rollback_checkpoint(checkpoint_id): Undo changes
- list_directory(path): Browse project structure
- run_tests(test_dir): Compile and run Java tests
- get_git_diff(file_path): Show code changes

Recommended workflow:
1. list_directory → understand structure
2. read_file → understand existing code
3. create_checkpoint → save state before editing
4. write_file → make changes
5. run_tests / execute_command → compile and test
6. get_git_diff → review changes

Project root: {self.project_root}. Use relative paths like "test_data/coding/java_test/Calculator.java"."""

        messages = [{"role": "system", "content": system_prompt}]
        tool_schemas = self.tools.get_schemas()
        round_num = 0

        while round_num < max_rounds:
            round_num += 1
            response = self.adapter.chat(messages, tool_schemas)

            # Build assistant message (omit content if empty to satisfy API)
            assistant_msg = {"role": "assistant"}
            if response.get("content"):
                assistant_msg["content"] = response["content"]
            if response["tool_calls"]:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc["id"],
                        "type": tc["type"],
                        "function": {
                            "name": tc["function"]["name"],
                            "arguments": tc["function"]["arguments"]
                        }
                    }
                    for tc in response["tool_calls"]
                ]
                if "content" not in assistant_msg:
                    assistant_msg["content"] = None
            messages.append(assistant_msg)

            if not response["tool_calls"]:
                break

            for tc in response["tool_calls"]:
                func_name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    args = {}

                result = self.tools.execute(func_name, args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result
                })

        return {
            "task_id": self.task_state["task_id"],
            "description": task_description,
            "rounds": round_num,
            "read_files": self.task_state["read_files"],
            "edited_files": self.task_state["edited_files"],
            "checkpoints_count": len(self.checkpoints),
            "conversation_history": messages
        }
