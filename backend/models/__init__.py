"""Data models for AI Desktop System"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class MessageRole(str, Enum):
    system = "system"
    user = "user"
    assistant = "assistant"
    tool = "tool"


class Message(BaseModel):
    role: MessageRole
    content: str
    tool_call_id: Optional[str] = None
    tool_name: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class Conversation(BaseModel):
    id: str
    title: str = ""
    messages: List[Message] = []
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


# Coding Agent Models
class AgentTask(BaseModel):
    id: str
    description: str
    status: str = "pending"  # pending, planning, executing, testing, completed, failed
    plan: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)


class FileEdit(BaseModel):
    file_path: str
    old_content: str = ""
    new_content: str = ""
    status: str = "pending"  # pending, applied, rolled_back


class PatchResult(BaseModel):
    file_path: str
    diff: str
    applied: bool = False
    success: bool = False
    error: Optional[str] = None


class TestResult(BaseModel):
    command: str
    output: str
    exit_code: int
    success: bool = False
    duration_ms: int = 0


class Checkpoint(BaseModel):
    id: str
    task_id: str
    snapshot: Dict[str, str]  # file_path -> content
    created_at: datetime = Field(default_factory=datetime.now)


# RAG Models
class DocumentInfo(BaseModel):
    id: str
    filename: str
    file_type: str  # pdf, docx, pptx, xlsx, csv, png, jpg, md, txt
    file_size: int = 0
    page_count: int = 0
    status: str = "uploaded"  # uploaded, parsing, parsed, indexing, indexed, failed
    error_message: Optional[str] = None
    uploaded_at: datetime = Field(default_factory=datetime.now)
    parsed_at: Optional[datetime] = None


class DocumentChunk(BaseModel):
    id: str
    document_id: str
    content: str
    chunk_type: str = "text"  # text, table, image, formula, title
    page_number: Optional[int] = None
    metadata: Dict[str, Any] = {}


class TableResult(BaseModel):
    id: str
    document_id: str
    page_number: int
    rows: int = 0
    cols: int = 0
    headers: List[str] = []
    data: List[List[str]] = []
    merge_info: Optional[Dict] = None  # merged cell info
    markdown: str = ""
    confidence: float = 0.0


class SearchResult(BaseModel):
    chunk_id: str
    document_id: str
    document_name: str
    content: str
    chunk_type: str
    page_number: Optional[int] = None
    score: float = 0.0
    evidence: Dict[str, Any] = {}


class QAQuery(BaseModel):
    query: str
    document_ids: Optional[List[str]] = None
    top_k: int = 5


class QAResult(BaseModel):
    query: str
    answer: str
    evidence: List[SearchResult] = []
    confidence: float = 0.0


# LLM Wiki Models
class WikiPage(BaseModel):
    id: str
    document_id: str
    title: str
    page_type: str = "document_card"  # document_card, chapter_summary, concept, table_desc, image_desc
    content: str
    metadata: Dict[str, Any] = {}


# Skill Models
class SkillDefinition(BaseModel):
    name: str
    description: str
    trigger: str
    input_schema: Dict[str, Any] = {}
    workflow: List[str] = []
    tools: List[str] = []
    templates: Dict[str, str] = {}
    validation: List[str] = []
    examples: List[Dict] = []
    enabled: bool = True
    version: str = "1.0.0"


class SkillExecution(BaseModel):
    id: str
    skill_name: str
    status: str = "pending"  # pending, running, completed, failed
    plan: List[str] = []
    outputs: Dict[str, str] = {}
    logs: List[str] = []
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# Evaluation Models
class EvalMetric(BaseModel):
    name: str
    value: float
    unit: str = "%"
    description: str = ""


class EvalResult(BaseModel):
    id: str
    category: str  # coding, rag, table, skill
    metrics: List[EvalMetric] = []
    success_cases: List[str] = []
    failure_cases: List[Dict] = []
    summary: str = ""
    created_at: datetime = Field(default_factory=datetime.now)
