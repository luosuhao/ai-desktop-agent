"""CodeGraph - Code repository understanding module

Analyzes code structure using static analysis:
- Symbol graph: function/class/variable definitions
- Call graph: function call relationships
- Import graph: module dependency analysis
- Test graph: test-to-source mapping
"""

import os
import re
import json
from typing import Dict, List, Set, Optional, Any
from collections import defaultdict


class SymbolInfo:
    def __init__(self, name: str, kind: str, file_path: str,
                 line_start: int, line_end: int, parent: Optional[str] = None):
        self.name = name
        self.kind = kind  # function, class, method, variable, import
        self.file_path = file_path
        self.line_start = line_start
        self.line_end = line_end
        self.parent = parent
        self.calls: List[str] = []
        self.called_by: List[str] = []


class CodeGraph:
    """Code graph for repository understanding"""

    def __init__(self, repo_path: str = "."):
        self.repo_path = os.path.abspath(repo_path)
        self.symbols: Dict[str, SymbolInfo] = {}  # key -> SymbolInfo
        self.file_symbols: Dict[str, List[str]] = defaultdict(list)  # file -> [symbol keys]
        self.imports: Dict[str, Set[str]] = defaultdict(set)  # file -> set of imports
        self.dependencies: Dict[str, Set[str]] = defaultdict(set)  # file -> depends on
        self.test_files: List[str] = []
        self.all_files: Dict[str, Dict] = {}  # relpath -> {name, path, size, ext, is_code}
        self.has_built = False
        self.last_repo_path = ""

    CODE_EXTS = {'.py', '.js', '.ts', '.jsx', '.tsx', '.cpp', '.c', '.h', '.hpp', '.java', '.go', '.rs'}
    ALL_EXTS = {'.py', '.js', '.ts', '.jsx', '.tsx', '.cpp', '.c', '.h', '.hpp', '.java', '.go', '.rs',
                '.md', '.bat', '.txt', '.json', '.csv', '.html', '.css', '.yaml', '.yml', '.toml', '.ini',
                '.docx', '.pptx', '.xlsx', '.pdf', '.png', '.jpg', '.jpeg', '.svg', '.xml', '.cfg'}

    def build(self, extensions: List[str] = None) -> Dict:
        """Build the code graph by scanning the repository"""
        if extensions is None:
            extensions = list(self.ALL_EXTS)

        files_scanned = 0
        all_found = 0
        for root, dirs, files in os.walk(self.repo_path):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('node_modules', '__pycache__', 'venv')]

            for f in files:
                ext = os.path.splitext(f)[1].lower()
                filepath = os.path.join(root, f)
                relpath = os.path.relpath(filepath, self.repo_path)

                # Track every file (for file tree display)
                try:
                    fsize = os.path.getsize(filepath)
                except OSError:
                    fsize = 0
                self.all_files[relpath] = {
                    "name": f, "path": relpath, "ext": ext,
                    "size": fsize, "is_code": ext in self.CODE_EXTS
                }
                all_found += 1

                # Only analyze code files for symbols
                if ext in extensions:
                    if ext in self.CODE_EXTS:
                        if self._is_test_file(relpath):
                            self.test_files.append(relpath)
                        self._analyze_file(relpath, ext)
                        files_scanned += 1

        # Build call graph and dependency graph
        self._build_call_graph()
        self._build_dependency_graph()
        self.has_built = True
        self.last_repo_path = self.repo_path

        return {
            "total_files": len(self.all_files),
            "code_files": sum(1 for info in self.all_files.values() if info.get("is_code")),
            "symbols_count": len(self.symbols),
            "test_files_count": len(self.test_files),
            "import_relations": sum(len(v) for v in self.imports.values())
        }

    def _is_test_file(self, path: str) -> bool:
        test_patterns = ['test_', '_test', 'tests/', 'spec_', '_spec']
        return any(p in path.lower() for p in test_patterns)

    def _analyze_file(self, relpath: str, ext: str):
        fullpath = os.path.join(self.repo_path, relpath)
        try:
            with open(fullpath, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
        except Exception:
            return

        if ext == '.py':
            self._analyze_python(relpath, content)
        elif ext in ('.js', '.ts', '.jsx', '.tsx'):
            self._analyze_jsts(relpath, content)
        elif ext in ('.cpp', '.c', '.h', '.hpp'):
            self._analyze_cpp(relpath, content)

    def _analyze_python(self, relpath: str, content: str):
        lines = content.split('\n')
        current_class = None
        current_function = None
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # Imports
            if m := re.match(r'^(from\s+\S+\s+)?import\s+(\S+)', stripped):
                self.imports[relpath].add(m.group(0))

            # Class definition
            if m := re.match(r'^class\s+(\w+)', stripped):
                name = m.group(1)
                key = f"{relpath}:{name}"
                self.symbols[key] = SymbolInfo(name, 'class', relpath, i + 1, i + 1)
                self.file_symbols[relpath].append(key)
                current_class = name
                current_function = None

            # Function definition
            if m := re.match(r'^async?\s+def\s+(\w+)', stripped):
                name = m.group(1)
                if name.startswith('_') and not name.startswith('__'):
                    kind = 'private_function'
                elif current_class:
                    kind = 'method'
                else:
                    kind = 'function'
                key = f"{relpath}:{name}"
                parent = f"{relpath}:{current_class}" if current_class else None
                self.symbols[key] = SymbolInfo(name, kind, relpath, i + 1, i + 1, parent)
                self.file_symbols[relpath].append(key)
                current_function = name

            # Track function/class ending (simplified)
            if stripped == '' or (i < len(lines) - 1 and not lines[i + 1].startswith((' ', '\t'))):
                if current_function:
                    key = f"{relpath}:{current_function}"
                    if key in self.symbols:
                        self.symbols[key].line_end = i
                elif current_class and not current_function:
                    key = f"{relpath}:{current_class}"
                    if key in self.symbols:
                        self.symbols[key].line_end = i

            # Call detection
            if current_function:
                for call_match in re.finditer(r'(\w+)\s*\(', stripped):
                    callee = call_match.group(1)
                    if callee not in ('if', 'elif', 'while', 'for', 'with', 'def', 'class',
                                      'return', 'yield', 'print', 'len', 'range', 'int',
                                      'str', 'float', 'list', 'dict', 'set', 'tuple',
                                      'self', 'cls', 'super', 'not', 'and', 'or',
                                      'in', 'is', 'assert', 'raise', 'import', 'from',
                                      'try', 'except', 'finally', 'as', 'pass', 'del',
                                      'break', 'continue', 'global', 'nonlocal', 'lambda'):
                        func_key = f"{relpath}:{current_function}"
                        if func_key in self.symbols:
                            self.symbols[func_key].calls.append(callee)
            i += 1

    def _analyze_jsts(self, relpath: str, content: str):
        lines = content.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # Imports
            if m := re.match(r'^import\s+.*\s+from\s+[\'"]', stripped):
                self.imports[relpath].add(stripped)
            if m := re.match(r'^const\s+\w+\s*=\s*require\(', stripped):
                self.imports[relpath].add(stripped)

            # Function declarations
            if m := re.match(r'^(?:export\s+)?(?:async\s+)?function\s+(\w+)', stripped):
                name = m.group(1)
                key = f"{relpath}:{name}"
                self.symbols[key] = SymbolInfo(name, 'function', relpath, i + 1, i + 1)
                self.file_symbols[relpath].append(key)

            # Arrow functions
            if m := re.match(r'^(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(', stripped):
                name = m.group(1)
                key = f"{relpath}:{name}"
                self.symbols[key] = SymbolInfo(name, 'const_function', relpath, i + 1, i + 1)
                self.file_symbols[relpath].append(key)

            # Class declarations
            if m := re.match(r'^(?:export\s+)?class\s+(\w+)', stripped):
                name = m.group(1)
                key = f"{relpath}:{name}"
                self.symbols[key] = SymbolInfo(name, 'class', relpath, i + 1, i + 1)
                self.file_symbols[relpath].append(key)
            i += 1

    def _analyze_cpp(self, relpath: str, content: str):
        lines = content.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # Includes as imports
            if m := re.match(r'#include\s+[<"](\S+)[>"]', stripped):
                self.imports[relpath].add(f"#include {m.group(1)}")

            # Function definitions
            if m := re.match(
                r'^(?:virtual\s+)?(?:static\s+)?(?:inline\s+)?'
                r'(?:const\s+)?(?:\w+(?:::\w+)*\s+)?(?:\w+\s*\*?\s+)?'
                r'(\w+)\s*\([^)]*\)\s*(?:const\s*)?(?:override\s*)?(?:=\s*0\s*)?[{;]',
                stripped
            ):
                name = m.group(1)
                if name not in ('if', 'while', 'for', 'switch', 'catch'):
                    key = f"{relpath}:{name}"
                    self.symbols[key] = SymbolInfo(name, 'function', relpath, i + 1, i + 1)
                    self.file_symbols[relpath].append(key)

            # Class declarations
            if m := re.match(r'^class\s+(\w+)', stripped):
                name = m.group(1)
                key = f"{relpath}:{name}"
                self.symbols[key] = SymbolInfo(name, 'class', relpath, i + 1, i + 1)
                self.file_symbols[relpath].append(key)
            i += 1

    def _build_call_graph(self):
        """Build call graph by resolving function calls to symbol keys"""
        # Map short names to full keys
        name_to_keys = defaultdict(list)
        for key, sym in self.symbols.items():
            name_to_keys[sym.name].append(key)

        for key, sym in self.symbols.items():
            resolved_calls = []
            for callee_name in sym.calls:
                if callee_name in name_to_keys:
                    resolved_calls.extend(name_to_keys[callee_name])
            # Update call relationships
            sym.calls = resolved_calls
            for callee_key in resolved_calls:
                if callee_key in self.symbols:
                    self.symbols[callee_key].called_by.append(key)

    def _build_dependency_graph(self):
        """Build file dependency graph from imports"""
        for filepath, imports in self.imports.items():
            for imp in imports:
                # Try to resolve import to a file
                resolved = self._resolve_import(filepath, imp)
                if resolved:
                    self.dependencies[filepath].add(resolved)

    def _resolve_import(self, from_file: str, import_stmt: str) -> Optional[str]:
        """Resolve an import statement to a file path"""
        # Simple resolution for Python
        if 'import ' in import_stmt:
            parts = import_stmt.replace('from ', '').replace('import ', '').split()
            module = parts[0].strip()
            # Convert module path to file path
            module_path = module.replace('.', '/')
            for ext in ['.py', '/__init__.py']:
                candidate = module_path + ext
                full_candidate = os.path.join(self.repo_path, candidate)
                if os.path.exists(full_candidate):
                    return candidate
        return None

    def find_related_files(self, file_path: str) -> List[str]:
        """Find files related to a given file via imports"""
        related = set()
        # Files that import this file
        for f, deps in self.dependencies.items():
            if file_path in deps:
                related.add(f)
        # Files this file imports
        for dep in self.dependencies.get(file_path, set()):
            related.add(dep)
        return list(related)

    def find_test_for_file(self, file_path: str) -> List[str]:
        """Find test files for a given source file"""
        base = os.path.splitext(file_path)[0]
        related = []
        for test_file in self.test_files:
            if base in test_file or os.path.splitext(test_file)[0] == base + '_test':
                related.append(test_file)
        return related

    def query_symbol(self, name: str) -> List[Dict]:
        """Search for a symbol by name"""
        results = []
        for key, sym in self.symbols.items():
            if name.lower() in sym.name.lower():
                results.append({
                    "name": sym.name,
                    "kind": sym.kind,
                    "file": sym.file_path,
                    "line_start": sym.line_start,
                    "line_end": sym.line_end,
                    "calls": sym.calls[:10],
                    "called_by": sym.called_by[:10]
                })
        return results

    def get_file_summary(self, file_path: str) -> Dict:
        """Get summary of symbols in a file"""
        symbols = self.file_symbols.get(file_path, [])
        return {
            "file": file_path,
            "symbols_count": len(symbols),
            "symbols": [
                {
                    "name": self.symbols[s].name,
                    "kind": self.symbols[s].kind,
                    "lines": f"{self.symbols[s].line_start}-{self.symbols[s].line_end}"
                }
                for s in symbols if s in self.symbols
            ],
            "imports_count": len(self.imports.get(file_path, set())),
            "related_files": self.find_related_files(file_path)
        }

    def get_stats(self) -> Dict:
        return {
            "total_files": len(self.all_files),
            "code_files": sum(1 for info in self.all_files.values() if info.get("is_code")),
            "files_with_symbols": len(self.file_symbols),
            "total_symbols": len(self.symbols),
            "test_files": len(self.test_files),
            "total_imports": sum(len(v) for v in self.imports.values()),
            "symbols_by_kind": dict(defaultdict(int,
                {k: sum(1 for s in self.symbols.values() if s.kind == k)
                 for k in set(s.kind for s in self.symbols.values())}
            )) if self.symbols else {}
        }

    def get_file_tree(self) -> Dict:
        """Build a hierarchical file tree of all scanned files"""
        tree = {"name": os.path.basename(self.repo_path) or "root", "type": "directory", "children": [], "files": 0}
        for fpath in sorted(self.all_files.keys()):
            parts = fpath.replace("\\", "/").split("/")
            current = tree
            for i, part in enumerate(parts):
                if i == len(parts) - 1:
                    # File node
                    symbols = [
                        {"name": self.symbols[s].name, "kind": self.symbols[s].kind,
                         "lines": f"{self.symbols[s].line_start}-{self.symbols[s].line_end}"}
                        for s in self.file_symbols.get(fpath, []) if s in self.symbols
                    ]
                    finfo = self.all_files.get(fpath, {})
                    current["children"].append({
                        "name": part, "type": "file",
                        "path": fpath, "ext": finfo.get("ext", ""),
                        "size": finfo.get("size", 0),
                        "is_code": finfo.get("is_code", False),
                        "symbols": symbols,
                        "imports": list(self.imports.get(fpath, set()))[:10] if finfo.get("is_code") else []
                    })
                    current["files"] = current.get("files", 0) + 1
                else:
                    # Directory node
                    found = None
                    for c in current["children"]:
                        if c["name"] == part and c["type"] == "directory":
                            found = c
                            break
                    if not found:
                        found = {"name": part, "type": "directory", "children": [], "files": 0}
                        current["children"].append(found)
                    current = found
        return tree

    def get_context_for_task(self, task_description: str) -> Dict:
        """Given a task description, find relevant code context

        This helps the agent understand which files are relevant.
        """
        # Extract keywords from task
        keywords = re.findall(r'\b[a-zA-Z_]\w{2,}\b', task_description)
        relevant_files = defaultdict(float)  # file -> relevance score

        for keyword in keywords:
            for key, sym in self.symbols.items():
                if keyword.lower() in sym.name.lower():
                    relevant_files[sym.file_path] += 1.0

        # Sort by relevance
        sorted_files = sorted(relevant_files.items(), key=lambda x: -x[1])

        return {
            "task_keywords": keywords[:20],
            "relevant_files": [
                {
                    "file": f,
                    "relevance": round(score, 1),
                    "summary": self.get_file_summary(f)
                }
                for f, score in sorted_files[:10]
            ]
        }
