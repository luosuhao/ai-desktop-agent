/** API service for backend communication */
import axios from 'axios';

// In Electron desktop app, use the backend URL from preload
// In browser dev mode, use relative path (Vite proxy)
const electronBackend = (window as any).electronAPI?.getBackendUrl?.() || '';
const baseURL = electronBackend ? `${electronBackend}/api` : '/api';

const api = axios.create({
  baseURL,
  timeout: 1800000, // 30 min (Ollama / agent-driven skill generation is slow)
});

// 生成输出文件下载 URL：
// - Web 版（vite 代理）返回相对路径 /api/outputs/...
// - 桌面版（file:// 协议）返回完整后端地址 http://127.0.0.1:18327/api/outputs/...
export const getBackendOrigin = () => (window as any).electronAPI?.getBackendUrl?.() || '';
export const outputFileUrl = (path: string) => `${getBackendOrigin()}/api/outputs/${path}`;

// Model Config / Providers
export const getModelConfig = () => api.get('/models/config');
export const updateModelConfig = (config: any) => api.post('/models/config', config);
export const getProviders = () => api.get('/models/providers');
export const switchProvider = (name: string) => api.post('/models/switch', { provider: name });
export const saveProviders = (data: any) => api.post('/models/providers', data);
export const chat = (messages: any[], tools?: any[]) =>
  api.post('/models/chat', { messages, tools });

// Agent
export const executeAgentTask = (task: any) => api.post('/agent/execute', task);
export const getCacheMetrics = () => api.get('/agent/cache-metrics');
export const resetCacheMetrics = () => api.post('/agent/cache-metrics/reset');
export const resetAgent = () => api.post('/agent/reset');
export const getCheckpoints = () => api.get('/agent/checkpoints');
export const rollbackCheckpoint = (checkpointId: string) => api.post(`/agent/rollback/${checkpointId}`);

// Conversation sessions
export const listSessions = () => api.get('/agent/sessions');
export const createSession = () => api.post('/agent/sessions');
export const getSession = (id: string) => api.get(`/agent/sessions/${id}`);
export const switchSession = (id: string) => api.post(`/agent/sessions/${id}/switch`);
export const deleteSession = (id: string) => api.delete(`/agent/sessions/${id}`);

// File versions & diff
export const getFileVersions = () => api.get('/agent/file-versions');
export const getFileContent = (file: string, version: number) =>
  api.get(`/agent/file-content?file=${encodeURIComponent(file)}&version=${version}`);
export const getFileDiff = (file: string, fromV: number, toV: number) =>
  api.get(`/agent/file-diff?file=${encodeURIComponent(file)}&from_v=${fromV}&to_v=${toV}`);

// CodeGraph
export const buildCodeGraph = (path: string) => api.post(`/codegraph/build?path=${encodeURIComponent(path)}`);
export const queryCodeGraph = (symbol: string) => api.get(`/codegraph/query?symbol=${encodeURIComponent(symbol)}`);
export const getCodeGraphStats = () => api.get('/codegraph/stats');
export const getCodeGraphTree = () => api.get('/codegraph/tree');

// Documents
export const uploadDocument = (file: File, extractTables = false) => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('extract_tables', String(extractTables));
  return api.post('/documents/upload', formData);
};
export const listDocuments = () => api.get('/documents');
export const getDocument = (id: string) => api.get(`/documents/${id}`);
export const deleteDocument = (id: string) => api.delete(`/documents/${id}`);

// RAG
export const searchRag = (query: any) => api.post('/rag/search', query);
export const qaQuery = (query: any) => api.post('/rag/qa', query);
export const financeQa = (query: any) => api.post('/rag/finance-qa', query);

// 金融数据分析（data_analysis）
export const financeAnalysisStatus = () => api.get('/finance-analysis/status');
export const financeDataAnalysis = (file: File, question: string) => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('question', question);
  return api.post('/finance-analysis/run', formData);
};

// Tables
export const recognizeTable = (data: any) => api.post('/tables/recognize', data);
export const getDocumentTables = (docId: string) => api.get(`/tables/document/${docId}`);

// PDF 表格识别（Qwen2-VL-TableNet）
export const recognizePdfTables = (file: File, pageFallback = false) => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('page_fallback', String(pageFallback));
  return api.post('/tables/pdf-recognize', formData);
};
export const getTablenetStatus = () => api.get('/tables/tablenet/status');

// Wiki
export const getWikiStats = () => api.get('/wiki/stats');
export const searchWiki = (query: string) => api.get(`/wiki/search?query=${encodeURIComponent(query)}`);
export const clearWiki = () => api.post('/wiki/clear');

// Skills
export const listSkills = () => api.get('/skills');
export const matchSkills = (description: string) => api.post('/skills/match', { description });
export const executeSkill = (skillName: string, inputs: any) =>
  api.post('/skills/execute', { skill_name: skillName, inputs });
export const getSkillHistory = () => api.get('/skills/history');
export const clearSkillHistory = () => api.post('/skills/history/clear');
export const getSkillCards = () => api.get('/skills/cards');

// Agent
export const uploadCodeFile = (file: File) => {
  const formData = new FormData();
  formData.append('file', file);
  return api.post('/agent/upload', formData);
};

// Evaluation
export const getCodingEval = () => api.get('/evaluation/coding');
export const getRagEval = () => api.get('/evaluation/rag');
export const getSkillsEval = () => api.get('/evaluation/skills');
export const getAllEval = () => api.get('/evaluation/all');

// System
export const getSystemStatus = () => api.get('/system/status');

export default api;
