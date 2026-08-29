"""AI Desktop System - FastAPI Backend Server

Unified API for:
- Model configuration and chat
- Coding Agent with Reasonix + CodeGraph
- Document parsing, RAG, and LLM Wiki
- Table structure recognition
- Skill management and execution
- Evaluation and testing
"""

import os
import json
import uuid
import shutil
from typing import List, Dict, Optional, Any
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel

from config import settings, load_model_config, save_model_config, load_all_providers, save_all_providers, get_active_provider_name
from agent import CodingAgent, ModelAdapter, ToolRegistry
from agent.reasonix import OptimizedAgentLoop, CacheMetrics
from agent.codegraph import CodeGraph
from rag.document_parser import DocumentParser, ParsedDocument
from rag.table_recognizer import TableRecognizer, TableStructure, analyze_table_complexity
from rag.vector_store import VectorStore
from rag.llm_wiki import LLMWiki
from rag.pdf_table_recognition import recognize_pdf_tables, recognize_image_tables, merge_tablenet_tables
from rag.finance_qa import finance_qa
from finance_analysis import run_finance_analysis, finance_analysis_status
from tablenet.engine import engine as tablenet_engine, venv_python as tablenet_venv_python
from skills import SkillManager

app = FastAPI(title="AI Desktop System", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount frontend dist for production/standalone mode
# Look in multiple locations: CWD, env var, relative to module
_frontend_candidates = [
    os.environ.get("FRONTEND_DIST", ""),
    os.path.join(os.getcwd(), "..", "frontend", "dist"),
    os.path.join(os.getcwd(), "frontend", "dist"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "dist"),
]
_frontend_dist = ""
for _p in _frontend_candidates:
    if _p and os.path.isfile(os.path.join(_p, "index.html")):
        _frontend_dist = _p
        break
if _frontend_dist:
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import HTMLResponse
    _assets = os.path.join(_frontend_dist, "assets")
    if os.path.isdir(_assets):
        app.mount("/assets", StaticFiles(directory=_assets), name="assets")
    @app.exception_handler(StarletteHTTPException)
    async def _serve_frontend(request, exc):
        # 仅对非 API 路径的 404 做 SPA 兜底；API 异常按原状态码透传
        if exc.status_code == 404 and not request.url.path.startswith("/api/"):
            idx_html = os.path.join(_frontend_dist, "index.html")
            if os.path.isfile(idx_html):
                return HTMLResponse(content=open(idx_html, encoding="utf-8").read())
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
    @app.get("/")
    async def _root():
        idx_html = os.path.join(_frontend_dist, "index.html")
        if os.path.isfile(idx_html):
            return HTMLResponse(content=open(idx_html, encoding="utf-8").read())
        return {"status": "ok", "system": "AI Desktop System", "version": "1.0.0"}

# Global instances
model_adapter = ModelAdapter()
coding_agent = CodingAgent(model_adapter)
optimized_loop = OptimizedAgentLoop(coding_agent)
code_graph = CodeGraph()
vector_store = VectorStore(settings.vector_db_dir)
llm_wiki = LLMWiki(settings.wiki_db_dir)
skill_manager = SkillManager()
# Share the Coding Agent with skills that delegate LLM-driven steps (e.g. doc-ppt-offline)
skill_manager.coding_agent = coding_agent
# Load external skills from the skills/ directory (with signature verification)
skill_manager.load_skills_from_directory()

# Upload directories
os.makedirs(settings.upload_dir, exist_ok=True)
os.makedirs(settings.output_dir, exist_ok=True)

# In-memory document store
documents_store: Dict[str, ParsedDocument] = {}


# ===== Conversation Sessions (conversation history + independent rollback) =====

CONVERSATION_FILE = os.path.join(settings.output_dir, "conversation_history.json")
conversation_sessions: Dict[str, Dict] = {}  # session_id -> session dict
active_session_id: Optional[str] = None


def _load_sessions():
    """Load conversation sessions from disk"""
    global conversation_sessions
    if os.path.exists(CONVERSATION_FILE):
        try:
            with open(CONVERSATION_FILE, "r", encoding="utf-8") as f:
                conversation_sessions = json.load(f)
        except Exception:
            conversation_sessions = {}


def _save_sessions():
    """Persist conversation sessions to disk"""
    try:
        os.makedirs(os.path.dirname(CONVERSATION_FILE), exist_ok=True)
        with open(CONVERSATION_FILE, "w", encoding="utf-8") as f:
            json.dump(conversation_sessions, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _new_session_id() -> str:
    return f"session_{uuid.uuid4().hex[:8]}"


def _save_current_session_state():
    """Save active agent's checkpoints/versions/messages to the active session"""
    global active_session_id
    if active_session_id and active_session_id in conversation_sessions:
        conversation_sessions[active_session_id]["checkpoints"] = coding_agent.checkpoints
        conversation_sessions[active_session_id]["file_versions"] = coding_agent.file_versions


def _load_session_state(sid: str):
    """Load a session's checkpoints/versions into the coding agent"""
    global active_session_id
    s = conversation_sessions.get(sid, {})
    coding_agent.checkpoints = list(s.get("checkpoints", []))
    coding_agent.file_versions = dict(s.get("file_versions", {}))
    active_session_id = sid


_load_sessions()


# ===== API Routes =====

# Root route is registered at the top of the file (after frontend mount)


# ----- Model Configuration / Provider Management -----

def _apply_model_config(config: dict):
    """Apply a config dict to the global model adapter"""
    global model_adapter, coding_agent, optimized_loop
    model_adapter = ModelAdapter(config)
    coding_agent.adapter = model_adapter
    optimized_loop.agent = coding_agent


@app.get("/api/models/config")
async def get_model_config():
    """Get active provider config (backward compat)"""
    return load_model_config()


@app.post("/api/models/config")
async def update_model_config(config: Dict):
    """Update active provider config (backward compat)"""
    save_model_config(config)
    _apply_model_config(config)
    return {"success": True, "config": config}


@app.get("/api/models/providers")
async def get_providers():
    """Get all provider configs with active status"""
    import asyncio
    full = load_all_providers()
    active = full.get("active", "online")
    providers = full.get("providers", {})

    result = {"active": active, "providers": {}}
    for name, cfg in providers.items():
        reachable = False
        error = None
        base = cfg.get("api_base", "")
        try:
            from urllib.parse import urlparse
            parsed = urlparse(base)
            host = parsed.hostname or "localhost"
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            # Try host, and fall back to 127.0.0.1 for "localhost"
            # (Windows may resolve localhost to IPv6 ::1 while service listens on IPv4)
            candidates = [host]
            if host.lower() == "localhost":
                candidates.append("127.0.0.1")
            # Async TCP connectivity check (non-blocking)
            for candidate in candidates:
                try:
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(candidate, port), timeout=2.0
                    )
                    writer.close()
                    await writer.wait_closed()
                    reachable = True
                    error = None
                    break
                except Exception as e:
                    error = e.__class__.__name__
        except Exception as e:
            error = e.__class__.__name__
        result["providers"][name] = dict(cfg)
        result["providers"][name]["_reachable"] = reachable
        result["providers"][name]["_error"] = error
    return result


@app.post("/api/models/switch")
async def switch_provider(data: Dict):
    """Switch active provider: {"provider": "online"} or {"provider": "local"}"""
    target = data.get("provider", "")
    full = load_all_providers()
    if target not in full.get("providers", {}):
        raise HTTPException(400, f"Unknown provider: {target}")
    full["active"] = target
    save_all_providers(full)
    _apply_model_config(full["providers"][target])
    return {"success": True, "active": target, "config": full["providers"][target]}


@app.post("/api/models/providers")
async def save_providers(data: Dict):
    """Save all provider configs: {"providers": {...}}"""
    full = load_all_providers()
    if "providers" in data:
        for name, cfg in data["providers"].items():
            full.setdefault("providers", {})[name] = cfg
    if "active" in data:
        full["active"] = data["active"]
    save_all_providers(full)
    # Re-apply active provider
    active = full.get("active", "online")
    _apply_model_config(full.get("providers", {}).get(active, {}))
    return {"success": True}


@app.post("/api/models/chat")
async def chat(messages: List[Dict], tools: Optional[List[Dict]] = None):
    """Simple chat completion"""
    result = model_adapter.chat(messages, tools)
    return result


# ----- Coding Agent -----

@app.post("/api/agent/execute")
async def execute_agent_task(task: Dict):
    """Execute a coding agent task"""
    global active_session_id
    description = task.get("description", "")
    use_cache = task.get("use_cache", True)
    repo_summary = task.get("repo_summary", "")
    max_rounds = task.get("max_rounds", 20)
    session_id = task.get("session_id", active_session_id)
    messages = task.get("messages", [])

    # 若无有效会话（如后端重启后 active_session_id 为 None），自动创建一个，
    # 保证每次执行的内容都会进入对话历史，避免聊天丢失。
    if not session_id or session_id not in conversation_sessions:
        _save_current_session_state()
        session_id = _new_session_id()
        now = datetime.now().isoformat()
        conversation_sessions[session_id] = {
            "id": session_id, "title": "新对话", "created_at": now, "updated_at": now,
            "messages": [], "checkpoints": [], "file_versions": {}
        }
        active_session_id = session_id
    elif session_id != active_session_id:
        # If a specific session is targeted, load its checkpoints/versions
        _load_session_state(session_id)

    if use_cache:
        result = optimized_loop.execute_with_cache(
            task_description=description,
            repo_summary=repo_summary,
            max_rounds=max_rounds
        )
    else:
        result = coding_agent.execute_task(
            task_description=description,
            max_rounds=max_rounds
        )

    # Save messages + state to the session (session_id 现在必然有效)
    s = conversation_sessions[session_id]
    s["messages"] = messages
    s["checkpoints"] = coding_agent.checkpoints
    s["file_versions"] = coding_agent.file_versions
    # Auto-title from first user message
    if s.get("title") == "新对话":
        first_user = next((m for m in messages if m.get("role") == "user"), None)
        if first_user:
            s["title"] = first_user["content"][:30]
    s["updated_at"] = datetime.now().isoformat()
    active_session_id = session_id
    _save_sessions()
    # 返回 session_id，方便前端立即绑定当前会话
    result["session_id"] = session_id

    return result


@app.get("/api/agent/cache-metrics")
async def get_cache_metrics():
    return optimized_loop.cache_metrics.get_report()


# Register cache-metrics/reset via add_api_route (more reliable than decorator in some environments)
async def reset_cache_metrics():
    """Reset cache metrics to zero"""
    optimized_loop.cache_metrics.reset()
    return {"success": True, "message": "Cache metrics reset"}

if not any("/cache-metrics/reset" in getattr(r, "path", "") for r in app.routes):
    app.add_api_route("/api/agent/cache-metrics/reset", reset_cache_metrics, methods=["POST"])

# Also register directly to ensure route is available
app.add_api_route("/api/agent/cache-metrics/clear", reset_cache_metrics, methods=["POST"])


@app.post("/api/agent/reset")
async def reset_agent():
    """Reset agent state"""
    global coding_agent, optimized_loop
    coding_agent = CodingAgent(model_adapter)
    optimized_loop = OptimizedAgentLoop(coding_agent)
    return {"success": True}


UPLOAD_CODE_DIR = os.path.join(settings.upload_dir, "code")


@app.post("/api/agent/upload")
async def upload_code_file(file: UploadFile = File(...)):
    """Upload a code file for the Coding Agent to modify"""
    os.makedirs(UPLOAD_CODE_DIR, exist_ok=True)
    content = await file.read()
    filepath = os.path.join(UPLOAD_CODE_DIR, file.filename or "unknown")
    with open(filepath, "wb") as f:
        f.write(content)
    return {
        "success": True,
        "filename": file.filename or "unknown",
        "path": os.path.relpath(filepath).replace("\\", "/"),
        "size": len(content)
    }


@app.get("/api/agent/checkpoints")
async def get_checkpoints():
    """Get all checkpoints from current agent state"""
    cps = coding_agent.checkpoints
    result = []
    for cp in cps:
        ts = cp.get("timestamp", "")
        time_str = ""
        if ts:
            import time as _time
            time_str = _time.strftime("%Y-%m-%d %H:%M:%S", _time.localtime(ts))
        result.append({
            "id": cp["id"],
            "timestamp": ts,
            "time_str": time_str,
            "files": [k for k in cp["snapshot"].keys() if k and k.strip()] if isinstance(cp.get("snapshot"), dict) else []
        })
    return {"checkpoints": result, "count": len(result)}


@app.post("/api/agent/rollback/{checkpoint_id}")
async def rollback_checkpoint(checkpoint_id: str):
    """Rollback to a previous checkpoint.
    Restores old file content and deletes new files created after that checkpoint."""
    cps = coding_agent.checkpoints
    target_idx = -1
    for i, cp in enumerate(cps):
        if cp["id"] == checkpoint_id:
            target_idx = i
            break

    if target_idx == -1:
        return {"success": False, "error": f"Checkpoint {checkpoint_id} not found"}

    target_cp = cps[target_idx]
    snapshot = target_cp.get("snapshot", {})
    restored = []
    deleted_new = []
    removed_cp_ids = [checkpoint_id]  # versions tied to these checkpoints should be pruned

    # Phase 1: restore snapshot files
    for fpath, content in snapshot.items():
        if not fpath or not fpath.strip():
            continue
        try:
            full = coding_agent._resolve_path(fpath)
            fdir = os.path.dirname(full)
            if fdir:
                os.makedirs(fdir, exist_ok=True)
            with open(full, "w", encoding="utf-8") as f:
                f.write(content)
            restored.append(fpath)
        except Exception as e:
            return {"success": False, "error": f"Failed to restore {fpath}: {e}"}

    # Phase 2: delete new files created after this checkpoint
    for cp in cps[target_idx + 1:]:
        if cp.get("is_new_file") and cp.get("new_file_path"):
            new_path = cp["new_file_path"]
            full = coding_agent._resolve_path(new_path)
            try:
                if os.path.exists(full):
                    os.remove(full)
                    deleted_new.append(new_path)
                    removed_cp_ids.append(cp["id"])
                # Clean up Java .class files
                class_file = full.rsplit('.', 1)[0] + '.class'
                if os.path.exists(class_file):
                    os.remove(class_file)
            except Exception as e:
                pass  # non-critical

    # Prune version history: remove versions created by the rolled-back checkpoint
    # and any deleted new files
    coding_agent._prune_versions(removed_cp_ids)

    # Remove the rolled-back checkpoint
    coding_agent.checkpoints = [c for c in cps if c["id"] != checkpoint_id]

    # Persist updated state back to the active session
    _save_current_session_state()
    _save_sessions()

    return {
        "success": True,
        "restored_files": restored,
        "deleted_new_files": deleted_new,
        "checkpoint_id": checkpoint_id
    }


# ----- Conversation Sessions -----

@app.get("/api/agent/sessions")
async def list_sessions():
    """List all saved conversation sessions"""
    result = []
    for sid, s in conversation_sessions.items():
        result.append({
            "id": sid,
            "title": s.get("title", "新对话"),
            "created_at": s.get("created_at", ""),
            "updated_at": s.get("updated_at", ""),
            "message_count": len(s.get("messages", [])),
            "checkpoint_count": len(s.get("checkpoints", []))
        })
    # Sort by updated_at desc (most recent first)
    result.sort(key=lambda x: x["updated_at"], reverse=True)
    return {"sessions": result, "active": active_session_id, "count": len(result)}


@app.post("/api/agent/sessions")
async def create_session():
    """Create a new conversation session (and activate it)"""
    global active_session_id
    # Save current session state before switching
    _save_current_session_state()
    sid = _new_session_id()
    now = datetime.now().isoformat()
    conversation_sessions[sid] = {
        "id": sid,
        "title": "新对话",
        "created_at": now,
        "updated_at": now,
        "messages": [],
        "checkpoints": [],
        "file_versions": {}
    }
    active_session_id = sid
    coding_agent.checkpoints = []
    coding_agent.file_versions = {}
    _save_sessions()
    return {"success": True, "session_id": sid}


@app.get("/api/agent/sessions/{session_id}")
async def get_session(session_id: str):
    """Get a session's detail (messages, checkpoints, versions)"""
    s = conversation_sessions.get(session_id)
    if not s:
        return {"success": False, "error": "Session not found"}
    return {
        "success": True,
        "session": {
            "id": s["id"],
            "title": s.get("title", "新对话"),
            "created_at": s.get("created_at", ""),
            "updated_at": s.get("updated_at", ""),
            "messages": s.get("messages", []),
            "checkpoints": s.get("checkpoints", []),
            "file_versions": s.get("file_versions", {})
        }
    }


@app.post("/api/agent/sessions/{session_id}/switch")
async def switch_session(session_id: str):
    """Switch to a conversation session (loads its messages + checkpoints + versions)"""
    if session_id not in conversation_sessions:
        return {"success": False, "error": "Session not found"}
    # Save current session state before switching
    _save_current_session_state()
    _load_session_state(session_id)
    s = conversation_sessions[session_id]
    return {
        "success": True,
        "session_id": session_id,
        "messages": s.get("messages", []),
        "checkpoints": s.get("checkpoints", []),
        "file_versions": s.get("file_versions", {})
    }


@app.delete("/api/agent/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a conversation session"""
    global active_session_id
    if session_id not in conversation_sessions:
        return {"success": False, "error": "Session not found"}
    del conversation_sessions[session_id]
    if active_session_id == session_id:
        active_session_id = None
        coding_agent.checkpoints = []
        coding_agent.file_versions = {}
    _save_sessions()
    return {"success": True}


# ----- File Versions & Diff -----

@app.get("/api/agent/file-versions")
async def get_file_versions():
    """Get version history for all edited files"""
    return {"files": coding_agent.get_file_versions()}


@app.get("/api/agent/file-content")
async def get_file_content(file: str, version: int):
    """Get the full content of a specific file version"""
    return coding_agent.get_file_content(file, version)


@app.get("/api/agent/file-diff")
async def get_file_diff(file: str, from_v: int = 0, to_v: int = 0):
    """Get unified diff between two versions of a file"""
    return coding_agent.get_file_diff(file, from_v, to_v if to_v else None)


# ----- CodeGraph -----

@app.post("/api/codegraph/build")
async def build_codegraph(path: str = Query(".", description="Repository path")):
    """Build code graph for a repository"""
    code_graph.repo_path = os.path.abspath(path)
    stats = code_graph.build()
    file_tree = code_graph.get_file_tree()
    return {"success": True, "stats": stats, "file_tree": file_tree}


@app.get("/api/codegraph/query")
async def query_codegraph(symbol: str):
    """Search for symbols in code graph"""
    results = code_graph.query_symbol(symbol)
    return {"results": results, "total": len(results)}


@app.get("/api/codegraph/file")
async def get_file_graph(file_path: str):
    """Get file summary from code graph"""
    summary = code_graph.get_file_summary(file_path)
    return summary


@app.get("/api/codegraph/stats")
async def get_codegraph_stats():
    return code_graph.get_stats()


@app.get("/api/codegraph/tree")
async def get_codegraph_tree():
    """Get the current CodeGraph file tree and stats (if already built)"""
    if not code_graph.has_built:
        return {"success": False, "built": False, "stats": None, "file_tree": None}
    return {
        "success": True, "built": True,
        "stats": code_graph.get_stats(),
        "file_tree": code_graph.get_file_tree(),
        "repo_path": code_graph.last_repo_path
    }


@app.post("/api/codegraph/context")
async def get_task_context(task_description: str):
    """Get relevant code context for a task"""
    context = code_graph.get_context_for_task(task_description)
    return context


# ----- Document Management -----

@app.post("/api/documents/upload")
async def upload_document(file: UploadFile = File(...),
                          extract_tables: bool = Form(False)):
    """Upload and parse a document. PDF + extract_tables=true 时额外调用
    Qwen2-VL-TableNet 提取表格并并入 RAG 索引（失败自动回退启发式解析）。"""
    doc_id = str(uuid.uuid4())[:8]
    file_ext = os.path.splitext(file.filename)[1].lower()
    save_path = os.path.join(settings.upload_dir, f"{doc_id}{file_ext}")

    with open(save_path, "wb") as f:
        f.write(await file.read())

    # Parse document
    parsed = DocumentParser.parse(save_path, doc_id)
    parsed.metadata["filename"] = file.filename
    parsed.metadata["file_size"] = os.path.getsize(save_path)

    # TableNet 表格提取（可选，PDF 专用）
    tablenet_meta = {"attempted": False}
    if extract_tables and file_ext == ".pdf":
        tablenet_meta["attempted"] = True
        try:
            rec = recognize_pdf_tables(
                save_path, filename=file.filename,
                engine=tablenet_engine, page_fallback=False,
            )
            merged = merge_tablenet_tables(parsed, rec)
            tablenet_meta.update({
                "run_id": rec.get("run_id", ""),
                "tables_count": merged,
                "available": tablenet_engine.status().get("available", False),
            })
            if merged == 0:
                parsed.parse_errors.append(
                    "TableNet 未识别出表格，保留启发式表格解析")
            # 合并后重新生成 chunks（_generate_chunks 会重置 doc.chunks）
            DocumentParser._generate_chunks(parsed)
        except Exception as e:
            parsed.parse_errors.append(f"TableNet 失败，已回退启发式解析: {e}")
            tablenet_meta["error"] = str(e)
            tablenet_meta["available"] = False
    parsed.metadata["tablenet"] = tablenet_meta

    documents_store[doc_id] = parsed

    # Index into vector store
    vector_store.add_documents(parsed.chunks)

    # Build LLM Wiki
    llm_wiki.build_from_document(parsed)

    return {
        "success": True,
        "document_id": doc_id,
        "filename": file.filename,
        "file_type": file_ext,
        "file_size": parsed.metadata.get("file_size", 0),
        "page_count": parsed.metadata.get("page_count", 0),
        "tables_count": len(parsed.tables),
        "chunks_count": len(parsed.chunks),
        "parse_errors": parsed.parse_errors,
        "parse_time": parsed.metadata.get("parse_time", ""),
        "tablenet": tablenet_meta
    }


@app.get("/api/documents")
async def list_documents():
    """List all uploaded documents"""
    docs = []
    for doc_id, parsed in documents_store.items():
        docs.append({
            "id": doc_id,
            "filename": parsed.filename or parsed.metadata.get("filename", ""),
            "file_type": parsed.file_type,
            "file_size": parsed.metadata.get("file_size", 0),
            "page_count": parsed.metadata.get("page_count", 0),
            "tables_count": len(parsed.tables),
            "chunks_count": len(parsed.chunks),
            "parse_errors": parsed.parse_errors,
            "upload_time": parsed.metadata.get("upload_time", "")
        })
    return {"documents": docs, "total": len(docs)}


@app.get("/api/documents/{doc_id}")
async def get_document(doc_id: str):
    """Get document details"""
    parsed = documents_store.get(doc_id)
    if not parsed:
        raise HTTPException(404, "Document not found")

    return {
        "id": doc_id,
        "filename": parsed.filename,
        "file_type": parsed.file_type,
        "pages": parsed.pages,
        "tables": parsed.tables,
        "metadata": parsed.metadata,
        "chunks_count": len(parsed.chunks)
    }


@app.delete("/api/documents/{doc_id}")
async def delete_document(doc_id: str):
    """Delete a document"""
    if doc_id in documents_store:
        del documents_store[doc_id]
        vector_store.remove_documents(doc_id)
        return {"success": True}
    raise HTTPException(404, "Document not found")


# ----- RAG & QA -----

@app.post("/api/rag/search")
async def search_rag(query: Dict):
    """Search documents using RAG"""
    q = query.get("query", "")
    top_k = query.get("top_k", 5)
    method = query.get("method", "hybrid")
    use_rerank = query.get("use_rerank", True)

    results = vector_store.search(q, top_k, method, use_rerank)
    return results


@app.post("/api/rag/qa")
async def qa(query: Dict):
    """Question answering over documents"""
    q = query.get("query", "")
    doc_ids = query.get("document_ids", None)
    top_k = query.get("top_k", 5)

    # Search for relevant chunks
    search_results = vector_store.search(q, top_k, "hybrid", True,
                                         document_ids=doc_ids)
    chunks = search_results.get("results", [])

    # Build answer context
    context_parts = []
    evidence_list = []
    for r in chunks:
        context_parts.append(f"[{r.get('chunk_type', 'text')}] {r['content']}")
        evidence_list.append(r)

    context = "\n\n".join(context_parts)

    # Generate answer using model
    messages = [
        {"role": "system", "content": "You are a document QA assistant. Answer based on the provided context. Always cite the source document, page number, and evidence location."},
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {q}\n\nAnswer with evidence:"}
    ]
    answer_result = model_adapter.chat(messages)

    return {
        "query": q,
        "answer": answer_result.get("content", ""),
        "evidence": evidence_list,
        "total_evidence": len(evidence_list)
    }


@app.post("/api/rag/finance-qa")
async def finance_qa_endpoint(query: Dict):
    """金融计算问答：RAG 检索 + LLM 通过服务器计算器工具精确计算。

    请求体可选 document_ids 限定文档范围；优先注入选中文档的全部表格块，
    让模型基于真实表格数字调用 calculate 工具得到精确结果。
    """
    try:
        return finance_qa(query, vector_store, model_adapter)
    except Exception as e:
        return JSONResponse(
            {"success": False, "error": f"金融问答失败: {e}", "detail": str(e)},
            status_code=500,
        )


# ----- 金融数据分析（data_analysis 包子进程） -----

@app.get("/api/finance-analysis/status")
def finance_analysis_status_api():
    """检查 data_analysis 可用性（python 解释器 + 依赖）。"""
    return finance_analysis_status()


@app.post("/api/finance-analysis/run")
def finance_analysis_run_api(file: UploadFile = File(...), question: str = Form("")):
    """上传 CSV/Excel + 分析目标，调用 data_analysis 包生成代码分析并返回结果。"""
    try:
        return run_finance_analysis(file.file, file.filename or "data.xlsx", question)
    except Exception as e:
        return JSONResponse(
            {"success": False, "error": f"金融数据分析失败: {e}", "detail": str(e)},
            status_code=500,
        )


# ----- Table Recognition -----

@app.post("/api/tables/recognize")
async def recognize_table(data: Dict):
    """Recognize table structure from text/markdown/CSV"""
    source = data.get("source", "text")
    content = data.get("content", "")
    table_id = data.get("table_id", "table_1")

    if source == "csv":
        # CSV text content (not file path), parse directly
        import csv, io
        table = TableRecognizer.recognize_from_text(content.replace(',', '\t'), table_id)
        table.id = f"csv:{table_id}"
    elif source == "markdown":
        table = TableRecognizer.recognize_from_markdown(content, table_id)
    elif source == "html":
        table = TableRecognizer.recognize_from_html(content, table_id)
    else:
        table = TableRecognizer.recognize_from_text(content, table_id)

    complexity = analyze_table_complexity(table)

    # Save to file
    import uuid
    file_id = str(uuid.uuid4())[:8]
    md_content = table.to_markdown()
    csv_content = table.to_csv()
    save_dir = os.path.join(settings.output_dir, "tables")
    os.makedirs(save_dir, exist_ok=True)
    md_path = os.path.join(save_dir, f"table_{file_id}.md")
    csv_path = os.path.join(save_dir, f"table_{file_id}.csv")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write(csv_content)

    return {
        "success": True,
        "table": table.to_json(),
        "markdown": md_content,
        "csv": csv_content,
        "complexity": complexity,
        "saved_files": {
            "md": f"tables/table_{file_id}.md",
            "csv": f"tables/table_{file_id}.csv"
        }
    }


@app.get("/api/tables/document/{doc_id}")
async def get_document_tables(doc_id: str):
    """Get all tables from a document"""
    parsed = documents_store.get(doc_id)
    if not parsed:
        raise HTTPException(404, "Document not found")

    tables_result = []
    for i, t in enumerate(parsed.tables):
        table = TableRecognizer.recognize_from_text(
            t.get("markdown", ""),
            f"{doc_id}_t{i}"
        )
        tables_result.append({
            "index": i,
            "source": t.get("source", ""),
            "page_number": t.get("page_num", 1),
            "rows": t.get("rows", 0),
            "cols": t.get("cols", 0),
            "headers": t.get("headers", []),
            "structure": table.to_json(),
            "markdown": t.get("markdown", ""),
            "complexity": analyze_table_complexity(table)
        })

    return {"document_id": doc_id, "tables": tables_result, "total": len(tables_result)}


# ----- PDF 表格识别（Qwen2-VL-TableNet）-----

@app.get("/api/tables/tablenet/status")
async def tablenet_status():
    """模型服务可用性、模型目录与 venv 路径。"""
    st = tablenet_engine.status()
    st["model_dir_exists"] = os.path.isfile(os.path.join(st.get("model_dir", ""), "config.json"))
    st["venv_python"] = tablenet_venv_python()
    st["venv_exists"] = os.path.isfile(st["venv_python"])
    return st


@app.post("/api/tables/pdf-recognize")
async def pdf_recognize_tables(
    file: UploadFile = File(...),
    page_fallback: bool = Form(False),
):
    """上传 PDF 或图片/图表，调用 Qwen2-VL-TableNet 模型识别其中的表格。

    PDF 走渲染+检测流水线；图片直接送模型推理。
    输出统一写到 项目根/outputs/tablenet/<run_id>/。
    首次调用会自动拉起模型服务进程（加载模型需数十秒）。
    """
    ext = os.path.splitext(file.filename)[1].lower()
    if ext != ".pdf" and ext not in (".png", ".jpg", ".jpeg", ".bmp", ".tiff"):
        raise HTTPException(400, "仅支持 PDF 或图片文件")

    doc_id = str(uuid.uuid4())[:8]
    save_path = os.path.join(settings.upload_dir, f"tablenet_{doc_id}{ext}")
    with open(save_path, "wb") as f:
        f.write(await file.read())

    try:
        if ext == ".pdf":
            result = recognize_pdf_tables(
                save_path,
                filename=file.filename,
                engine=tablenet_engine,
                page_fallback=page_fallback,
            )
        else:
            result = recognize_image_tables(
                save_path,
                filename=file.filename,
                engine=tablenet_engine,
            )
        result["pdf_recognition_available"] = tablenet_engine.status().get("available", False)
        return result
    except Exception as e:
        return JSONResponse(
            {"success": False, "error": f"表格识别失败: {e}", "detail": str(e)},
            status_code=500,
        )


# ----- LLM Wiki -----

@app.get("/api/wiki/stats")
async def get_wiki_stats():
    return llm_wiki.get_stats()


@app.post("/api/wiki/clear")
async def clear_wiki():
    """Clear all wiki pages and vector store"""
    llm_wiki.clear()
    vector_store.clear()
    documents_store.clear()
    return {"success": True, "message": "知识库已清空"}


@app.get("/api/wiki/search")
async def search_wiki(query: str):
    results = llm_wiki.search_pages(query)
    return {"results": results, "total": len(results)}


@app.get("/api/wiki/document/{doc_id}")
async def get_wiki_pages(doc_id: str):
    pages = llm_wiki.get_document_pages(doc_id)
    return {
        "document_id": doc_id,
        "pages": [
            {
                "id": p.id,
                "title": p.title,
                "type": p.page_type,
                "content": p.content[:500],
                "metadata": p.metadata
            }
            for p in pages
        ],
        "total": len(pages)
    }


# ----- Skills -----

@app.get("/api/skills")
async def list_skills():
    """List all available skills"""
    return {"skills": skill_manager.list_skills(), "total": len(skill_manager.skills)}


@app.get("/api/skills/cards")
async def get_skill_cards():
    """Get NVIDIA-style Skill Cards for all skills (governance metadata)"""
    return {"cards": skill_manager.get_skill_cards(), "total": len(skill_manager.get_skill_cards())}


@app.post("/api/skills/match")
async def match_skills(task: Dict):
    """Match skills to a task description"""
    description = task.get("description", "")
    matched = skill_manager.match_skills(description)
    return {"matched": matched, "total": len(matched)}


@app.post("/api/skills/execute")
async def execute_skill(request: Dict):
    """Execute a skill"""
    skill_name = request.get("skill_name", "")
    inputs = request.get("inputs", {})
    output_dir = request.get("output_dir", settings.output_dir)

    result = skill_manager.execute_skill(skill_name, inputs, output_dir)
    return result


@app.get("/api/skills/history")
async def get_skill_history(limit: int = 20):
    return {"history": skill_manager.get_history(limit)}


@app.post("/api/skills/history/clear")
async def clear_skill_history():
    """Clear the skill execution history"""
    skill_manager.execution_history.clear()
    return {"success": True, "message": "执行历史已清空"}


# ----- Evaluation -----

@app.get("/api/evaluation/coding")
async def evaluate_coding():
    """Get coding agent evaluation metrics"""
    metrics = optimized_loop.cache_metrics.get_report()
    return {
        "category": "coding",
        "metrics": metrics,
        "summary": "Coding Agent evaluation results"
    }


@app.get("/api/evaluation/rag")
async def evaluate_rag():
    """Get RAG evaluation metrics"""
    stats = vector_store.get_stats()
    wiki_stats = llm_wiki.get_stats()
    return {
        "category": "rag",
        "metrics": {
            "total_chunks": stats.get("total_chunks", 0),
            "wiki_pages": wiki_stats.get("total_pages", 0),
            "documents_count": len(documents_store),
            "index_ready": stats.get("index_ready", False)
        },
        "summary": "RAG system evaluation"
    }


@app.get("/api/evaluation/skills")
async def evaluate_skills():
    """Get skill evaluation metrics"""
    history = skill_manager.get_history(10)
    success_count = sum(1 for h in history if h.get("success"))
    return {
        "category": "skills",
        "metrics": {
            "total_skills": len(skill_manager.skills),
            "total_executions": len(history),
            "success_count": success_count,
            "success_rate": round(success_count / max(len(history), 1) * 100, 2)
        },
        "summary": "Skill system evaluation"
    }


@app.get("/api/evaluation/all")
async def get_all_evaluations():
    """Get all evaluation results"""
    coding = optimized_loop.cache_metrics.get_report()
    rag_stats = vector_store.get_stats()
    wiki_stats = llm_wiki.get_stats()
    skill_history = skill_manager.get_history(10)
    skill_success = sum(1 for h in skill_history if h.get("success"))

    return {
        "coding": {
            "cache_hit_rate": coding.get("cache_hit_rate", 0),
            "avg_latency_ms": coding.get("avg_latency_ms", 0),
            "total_requests": coding.get("total_requests", 0),
            "input_tokens_saved": coding.get("input_tokens_saved", 0)
        },
        "rag": {
            "documents": len(documents_store),
            "chunks": rag_stats.get("total_chunks", 0),
            "wiki_pages": wiki_stats.get("total_pages", 0)
        },
        "skills": {
            "total": len(skill_manager.skills),
            "executions": len(skill_history),
            "success_rate": round(skill_success / max(len(skill_history), 1) * 100, 2)
        },
        "summary": "Comprehensive evaluation results"
    }


# ----- File Downloads & Outputs -----

@app.get("/api/outputs/{filename:path}")
async def get_output_file(filename: str):
    """Download a generated output file (search recursively)"""
    # Direct path first
    filepath = os.path.join(settings.output_dir, filename)
    if os.path.exists(filepath):
        return FileResponse(filepath)

    # Search recursively in output subdirectories
    for root, dirs, files in os.walk(settings.output_dir):
        if filename in files:
            return FileResponse(os.path.join(root, filename))

    # Try matching by basename
    basename = os.path.basename(filename)
    for root, dirs, files in os.walk(settings.output_dir):
        for f in files:
            if f == basename or f == filename:
                return FileResponse(os.path.join(root, f))

    raise HTTPException(404, f"File not found: {filename}")


@app.get("/api/uploads/{filename:path}")
async def get_upload_file(filename: str):
    """Download an uploaded file"""
    filepath = os.path.join(settings.upload_dir, filename)
    if os.path.exists(filepath):
        return FileResponse(filepath)
    raise HTTPException(404, "File not found")


# ----- System -----

@app.get("/api/system/status")
async def system_status():
    """Get system status"""
    return {
        "status": "running",
        "documents_count": len(documents_store),
        "vector_store_ready": vector_store.index_ready,
        "wiki_pages": llm_wiki.get_stats().get("total_pages", 0),
        "skills_count": len(skill_manager.skills),
        "model_configured": bool(model_adapter.config.get("api_key")),
        "upload_dir": settings.upload_dir,
        "output_dir": settings.output_dir
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
