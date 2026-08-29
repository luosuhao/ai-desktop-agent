import React, { useState, useRef, useEffect } from 'react';
import {
  Card, Input, Button, message, Spin, Collapse, Tag, Statistic, Row, Col,
  Space, Typography, Divider, Modal, Upload,
} from 'antd';
import {
  SendOutlined, ReloadOutlined, FileOutlined, FolderOpenOutlined,
  CheckCircleOutlined, RollbackOutlined,
  PlusOutlined, RobotOutlined, UploadOutlined, ClockCircleOutlined,
} from '@ant-design/icons';
import { executeAgentTask, getCacheMetrics, resetCacheMetrics, getCheckpoints, rollbackCheckpoint, uploadCodeFile, getFileVersions, getFileDiff, getFileContent, listSessions, createSession, switchSession, deleteSession } from '../api';

const { TextArea } = Input;
const { Panel } = Collapse;
const { Text } = Typography;

interface Message {
  id: string;
  role: 'user' | 'agent';
  content: string;
  result?: any;
  timestamp: Date;
}

const AgentPage: React.FC = () => {
  const [taskDesc, setTaskDesc] = useState('');
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [metrics, setMetrics] = useState<any>(null);
  const [checkpoints, setCheckpoints] = useState<any[]>([]);
  const [rollingBack, setRollingBack] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState<any[]>([]);
  const [targetFolder, setTargetFolder] = useState('');
  const [fileVersions, setFileVersions] = useState<any>({});
  const [selectedFile, setSelectedFile] = useState<string>('');
  const [selectedVersion, setSelectedVersion] = useState<number>(0);
  const [diffText, setDiffText] = useState('');
  const [versionContent, setVersionContent] = useState('');
  const [showDiffMode, setShowDiffMode] = useState<'diff' | 'content'>('diff');
  const [sessions, setSessions] = useState<any[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string>('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const loadSessions = async () => {
    try {
      const res = await listSessions();
      setSessions(res.data.sessions || []);
      setActiveSessionId(res.data.active || '');
    } catch (_) {}
  };

  const handleCreateSession = async () => {
    try {
      const res = await createSession();
      setActiveSessionId(res.data.session_id);
      setMessages([]);
      setUploadedFiles([]);
      setTargetFolder('');
      setCheckpoints([]);
      setFileVersions({});
      setDiffText('');
      setVersionContent('');
      await loadSessions();
      message.success('已开始新对话');
    } catch (_) { message.error('创建新对话失败'); }
  };

  const handleSwitchSession = async (sid: string) => {
    try {
      const res = await switchSession(sid);
      setActiveSessionId(sid);
      // Load saved messages
      const savedMessages = (res.data.messages || []).map((m: any) => ({
        ...m,
        timestamp: m.timestamp ? new Date(m.timestamp) : new Date(),
      }));
      setMessages(savedMessages);
      setCheckpoints(res.data.checkpoints || []);
      setFileVersions(res.data.file_versions || {});
      setDiffText('');
      setVersionContent('');
      setSelectedFile('');
      setSelectedVersion(0);
      await loadSessions();
    } catch (_) { message.error('切换对话失败'); }
  };

  const handleDeleteSession = async (sid: string) => {
    try {
      await deleteSession(sid);
      if (sid === activeSessionId) {
        setMessages([]);
        setCheckpoints([]);
        setFileVersions({});
      }
      await loadSessions();
      message.success('已删除对话');
    } catch (_) { message.error('删除对话失败'); }
  };

  useEffect(() => { loadSessions(); }, []);

  const loadFileVersions = async () => {
    try {
      const res = await getFileVersions();
      setFileVersions(res.data.files || {});
    } catch (_) {}
  };

  const handleSelectVersion = async (file: string, version: number) => {
    setSelectedFile(file);
    setSelectedVersion(version);
    // Load the version content and the diff
    try {
      const [diffRes, contentRes] = await Promise.all([
        getFileDiff(file, version - 1, version),
        getFileContent(file, version),
      ]);
      setDiffText(diffRes.data.diff || '');
      setVersionContent(contentRes.data.content || '');
    } catch (_) {}
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleExecute = async () => {
    if (!taskDesc.trim() && uploadedFiles.length === 0) {
      message.warning('请输入任务描述');
      return;
    }

    // Build task description with context
    let description = taskDesc.trim();
    const contexts: string[] = [];
    if (targetFolder) contexts.push(`目标文件夹: ${targetFolder}`);
    if (uploadedFiles.length > 0) contexts.push(`已上传: ${uploadedFiles.map(f => f.path).join(', ')}`);
    if (contexts.length > 0) {
      description = `[${contexts.join('; ')}] ${description}`;
    }

    const userMsg: Message = {
      id: `user_${Date.now()}`,
      role: 'user',
      content: (targetFolder ? `[${targetFolder}] ` : '') + (taskDesc || `处理 ${uploadedFiles.length} 个文件`),
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);
    setTaskDesc('');

    try {
      const res = await executeAgentTask({
        description,
        use_cache: true,
        repo_summary: '',
        max_rounds: 15,
        session_id: activeSessionId,
        messages: [...messages, userMsg].map(m => ({ role: m.role, content: m.content })),
      });
      const agentMsg: Message = {
        id: `agent_${Date.now()}`,
        role: 'agent',
        content: `任务完成 (${res.data.rounds} 轮)`,
        result: res.data,
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, agentMsg]);

      const m = await getCacheMetrics();
      setMetrics(m.data);
      loadCheckpoints();
      loadFileVersions();
      loadSessions();
    } catch (e: any) {
      const errMsg: Message = {
        id: `agent_${Date.now()}`,
        role: 'agent',
        content: `执行失败: ${e.message}`,
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errMsg]);
      message.error('Agent execution failed');
    }
    setLoading(false);
  };

  const handleNewChat = () => {
    if (messages.length === 0) return;
    Modal.confirm({
      title: '开始新对话',
      content: '将创建新对话，当前对话历史会保存，可随时切换回滚。',
      okText: '确认',
      cancelText: '取消',
      onOk: async () => {
        await handleCreateSession();
      },
    });
  };

  const handleUpload = async (file: File) => {
    const ext = file.name.split('.').pop()?.toLowerCase();
    const allowed = ['java', 'py', 'js', 'ts', 'tsx', 'jsx', 'cpp', 'c', 'h', 'hpp', 'go', 'rs', 'txt', 'md', 'json', 'xml', 'yaml', 'yml', 'toml', 'ini', 'cfg', 'sh', 'bat'];
    if (ext && !allowed.includes(ext)) { message.warning(`不支持: .${ext}`); return false; }
    try {
      const res = await uploadCodeFile(file);
      setUploadedFiles(prev => [...prev, res.data]);
    } catch (_) { message.error('上传失败'); }
    return false;
  };

  const handleRemoveFile = (index: number) => setUploadedFiles(prev => prev.filter((_, i) => i !== index));

  const loadMetrics = async () => {
    try { const m = await getCacheMetrics(); setMetrics(m.data); } catch (_) {}
  };

  const loadCheckpoints = async () => {
    try { const res = await getCheckpoints(); setCheckpoints(res.data.checkpoints || []); } catch (_) {}
  };

  const handleRollback = async (cpId: string) => {
    setRollingBack(true);
    try {
      const res = await rollbackCheckpoint(cpId);
      if (res.data.success) {
        message.success(`回滚成功: ${res.data.restored_files?.length || 0} 个文件已恢复`);
        loadCheckpoints();
        loadFileVersions();
      } else { message.error(`回滚失败: ${res.data.error}`); }
    } catch (_) { message.error('回滚请求失败'); }
    setRollingBack(false);
  };

  useEffect(() => { loadMetrics(); }, []);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleExecute(); }
  };

  return (
    <Row gutter={16}>
      <Col span={16}>
        <Card title="Coding Agent"
          extra={
            messages.length > 0 ? (
              <Button size="small" icon={<PlusOutlined />} onClick={handleNewChat}>新对话</Button>
            ) : null
          }
          style={{ marginBottom: 16 }}
        >
          {/* Target folder & uploaded files bar */}
          <div style={{
            background: '#fafafa', borderRadius: 6, padding: '8px 12px', marginBottom: 12,
            display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center',
            border: '1px solid #f0f0f0',
          }}>
            <FolderOpenOutlined style={{ color: '#e84435' }} />
            <Input
              size="small"
              placeholder="目标文件夹路径（可选），如 D:\my-project\src"
              value={targetFolder}
              onChange={e => setTargetFolder(e.target.value)}
              style={{ width: 320 }}
            />
            <Upload beforeUpload={handleUpload} showUploadList={false}
              accept=".java,.py,.js,.ts,.cpp,.c,.h,.go,.rs,.txt,.md,.json">
              <Button size="small" icon={<UploadOutlined />}>上传文件</Button>
            </Upload>
            <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
              {uploadedFiles.map((f, i) => (
                <Tag key={i} closable onClose={() => handleRemoveFile(i)} color="blue" style={{ fontSize: 11, margin: 0 }}>
                  {f.filename}
                </Tag>
              ))}
            </div>
          </div>

          {/* Message list */}
          <div style={{
            maxHeight: 420, overflow: 'auto', marginBottom: 12,
            display: 'flex', flexDirection: 'column', gap: 12,
          }}>
            {messages.length === 0 && !loading && (
              <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>
                <RobotOutlined style={{ fontSize: 48, color: '#ddd' }} />
                <p style={{ marginTop: 12 }}>设置目标文件夹 → 上传文件（可选）→ 输入修改要求</p>
              </div>
            )}
            {messages.map(msg => (
              <div key={msg.id}>
                {msg.role === 'user' ? (
                  <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 4 }}>
                    <div style={{
                      background: '#e84435', color: '#fff', borderRadius: '12px 12px 4px 12px',
                      padding: '10px 16px', maxWidth: '85%', wordBreak: 'break-word',
                    }}>
                      <Text style={{ color: '#fff', whiteSpace: 'pre-wrap' }}>{msg.content}</Text>
                    </div>
                  </div>
                ) : (
                  <div style={{ display: 'flex', marginBottom: 4 }}>
                    <div style={{
                      background: '#fff', borderRadius: '12px 12px 12px 4px',
                      padding: '12px 16px', maxWidth: '85%', width: '100%',
                      border: '1px solid #f0f0f0',
                    }}>
                      {msg.result ? <AgentResult result={msg.result} /> : <Text type="danger">{msg.content}</Text>}
                    </div>
                  </div>
                )}
              </div>
            ))}
            {loading && (
              <div style={{ display: 'flex', marginBottom: 4 }}>
                <div style={{ background: '#fafafa', borderRadius: '12px 12px 12px 4px', padding: '12px 16px', border: '1px solid #f0f0f0' }}>
                  <Spin size="small" /> <Text style={{ marginLeft: 8 }}>Agent 执行中...</Text>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div style={{ borderTop: '1px solid #f0f0f0', paddingTop: 12 }}>
            <TextArea rows={2} value={taskDesc} onChange={e => setTaskDesc(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入修改要求... (Enter 发送)" />
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                {targetFolder ? `目标: ${targetFolder}` : '设置目标文件夹后操作指定目录的文件'}
                {uploadedFiles.length > 0 && ` | ${uploadedFiles.length} 文件已上传`}
              </Text>
              <Button type="primary" icon={<SendOutlined />} onClick={handleExecute} loading={loading}>发送</Button>
            </div>
          </div>
        </Card>
      </Col>

      <Col span={8}>
        {/* 对话历史 */}
        <Card title={`对话历史 (${sessions.length})`} size="small" style={{ marginBottom: 16 }}
          extra={<Button size="small" icon={<ReloadOutlined />} onClick={loadSessions}>刷新</Button>}
        >
          <Button size="small" type="primary" icon={<PlusOutlined />} onClick={handleCreateSession} block style={{ marginBottom: 8 }}>
            新对话
          </Button>
          {sessions.length > 0 ? (
            <div style={{ maxHeight: 200, overflow: 'auto' }}>
              {sessions.map((s: any) => (
                <div key={s.id} style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '4px 6px', marginBottom: 4, borderRadius: 4, cursor: 'pointer', fontSize: 12,
                  background: s.id === activeSessionId ? '#fff1f0' : '#fafafa',
                  border: s.id === activeSessionId ? '1px solid #ffa39e' : '1px solid #f0f0f0',
                }}
                onClick={() => handleSwitchSession(s.id)}
                >
                  <div style={{ overflow: 'hidden' }}>
                    <div style={{ fontWeight: s.id === activeSessionId ? 600 : 400, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {s.title}
                    </div>
                    <Text type="secondary" style={{ fontSize: 10 }}>
                      {s.message_count} 消息 | {s.checkpoint_count} 快照
                    </Text>
                  </div>
                  <Button type="text" danger size="small" style={{ fontSize: 10 }}
                    onClick={(e) => { e.stopPropagation(); Modal.confirm({
                      title: '删除此对话？', okText: '删除', okType: 'danger', cancelText: '取消',
                      onOk: () => handleDeleteSession(s.id),
                    }); }}>
                    🗑
                  </Button>
                </div>
              ))}
            </div>
          ) : <Text type="secondary" style={{ fontSize: 12 }}>暂无历史对话</Text>}
        </Card>

        <Card title="Cache 指标" size="small" style={{ marginBottom: 16 }}
          extra={<Button size="small" icon={<ReloadOutlined />} onClick={async () => { try { await resetCacheMetrics(); const m = await getCacheMetrics(); setMetrics(m.data); message.success('Cache 已清空'); } catch (_) { message.error('重置失败'); } }}>重置</Button>}
        >
          {metrics ? (
            <Row gutter={[8, 8]}>
              <Col span={12}><Statistic title="命中率" value={metrics.cache_hit_rate} suffix="%" valueStyle={{ color: '#52c41a' }} /></Col>
              <Col span={12}><Statistic title="请求数" value={metrics.total_requests} /></Col>
              <Col span={12}><Statistic title="平均延迟" value={metrics.avg_latency_ms} suffix="ms" /></Col>
              <Col span={12}><Statistic title="节省 Token" value={metrics.input_tokens_saved} /></Col>
              <Col span={24}><Statistic title="节省成本" prefix="$" value={metrics.estimated_cost_saved_usd} precision={4} /></Col>
            </Row>
          ) : <Text type="secondary">暂无数据</Text>}
        </Card>

        <Card title="Checkpoint 快照" size="small" style={{ marginBottom: 16 }}>
          <Space direction="vertical" style={{ width: '100%' }}>
            <Button size="small" onClick={loadCheckpoints} block>刷新快照列表 ({checkpoints.length})</Button>
            {checkpoints.length > 0 ? (
              <div style={{ maxHeight: 200, overflow: 'auto' }}>
                {checkpoints.map((cp: any) => (
                  <Card key={cp.id} size="small" style={{ marginBottom: 4, background: '#fff' }}>
                    <Space direction="vertical" style={{ width: '100%' }} size={2}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <Text style={{ fontSize: 12, color: '#999' }}>{cp.id}</Text>
                        {cp.time_str && (
                          <Text style={{ fontSize: 11, color: '#888' }}>
                            <ClockCircleOutlined style={{ marginRight: 4 }} />{cp.time_str}
                          </Text>
                        )}
                      </div>
                      <Text style={{ fontSize: 12 }}>文件: {(cp.files || []).join(', ') || '(无)'}</Text>
                      <Button size="small" type="primary" danger icon={<RollbackOutlined />}
                        loading={rollingBack} onClick={() => handleRollback(cp.id)}>回滚到此快照</Button>
                    </Space>
                  </Card>
                ))}
              </div>
            ) : <Text type="secondary" style={{ fontSize: 12 }}>暂无快照</Text>}
          </Space>
        </Card>

        {/* 代码版本 / Diff */}
        <Card title="代码版本 / Diff" size="small" style={{ marginBottom: 16 }}
          extra={<Button size="small" icon={<ReloadOutlined />} onClick={loadFileVersions}>刷新</Button>}
        >
          {Object.keys(fileVersions).length === 0 ? (
            <Text type="secondary" style={{ fontSize: 12 }}>暂无文件版本记录（执行任务后自动生成）</Text>
          ) : (
            <Collapse ghost size="small">
              {Object.entries(fileVersions).map(([file, versions]: [string, any]) => (
                <Panel key={file} header={`${file.split('/').pop()} (${(versions as any[]).length} 个版本)`} >
                  <Space direction="vertical" style={{ width: '100%' }} size={4}>
                    {(versions as any[]).map((v) => (
                      <div key={v.version} style={{
                        display: 'flex', alignItems: 'center', gap: 6,
                        padding: '4px 6px', borderRadius: 4,
                        cursor: 'pointer', fontSize: 12,
                        background: selectedFile === file && selectedVersion === v.version ? '#fff1f0' : '#fafafa',
                        border: selectedFile === file && selectedVersion === v.version ? '1px solid #ffa39e' : '1px solid #f0f0f0',
                      }}
                      onClick={() => handleSelectVersion(file, v.version)}
                      >
                        <Tag color={v.change_type === 'new' ? 'green' : v.change_type === 'original' ? 'blue' : 'orange'}
                          style={{ fontSize: 10, margin: 0 }}>
                          V{v.version}
                        </Tag>
                        <Text style={{ fontSize: 11, color: '#666' }}>{v.change_type}</Text>
                        <Text style={{ fontSize: 10, color: '#999' }}>{v.size} 字符</Text>
                      </div>
                    ))}
                  </Space>
                </Panel>
              ))}
            </Collapse>
          )}

          {selectedFile && (
            <div style={{ marginTop: 12, borderTop: '1px solid #f0f0f0', paddingTop: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                <Text strong style={{ fontSize: 12 }}>{selectedFile.split('/').pop()} V{selectedVersion}</Text>
                <Space size={4}>
                  <Button size="small" type={showDiffMode === 'diff' ? 'primary' : 'default'}
                    onClick={() => setShowDiffMode('diff')}>Diff</Button>
                  <Button size="small" type={showDiffMode === 'content' ? 'primary' : 'default'}
                    onClick={() => setShowDiffMode('content')}>代码</Button>
                </Space>
              </div>
              {showDiffMode === 'diff' ? (
                <DiffViewer diff={diffText} />
              ) : (
                <pre style={{
                  fontSize: 11, background: '#f8f8f8', padding: 8, borderRadius: 4,
                  maxHeight: 300, overflow: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-all', color: '#333',
                }}>
                  {versionContent || '(空)'}
                </pre>
              )}
            </div>
          )}
        </Card>
      </Col>
    </Row>
  );
};

/** Map file extension to language label */
const extLang = (path: string): string => {
  const m = path.match(/\.(\w+)$/);
  if (!m) return 'text';
  const map: Record<string, string> = {
    java: 'java', py: 'python', js: 'javascript', ts: 'typescript',
    jsx: 'jsx', tsx: 'tsx', cpp: 'cpp', c: 'c', h: 'cpp', hpp: 'cpp',
    go: 'go', rs: 'rust', html: 'html', css: 'css', json: 'json',
    xml: 'xml', yaml: 'yaml', yml: 'yaml', md: 'markdown', sh: 'bash',
    bat: 'batch', txt: 'text', cfg: 'ini', ini: 'ini', toml: 'toml',
  };
  return map[m[1]] || 'text';
};

/** Extract tool call trace from conversation_history, pairing each call with its result */
const extractToolTrace = (history: any[]) => {
  const trace: { name: string; args: any; argsText: string; result: string; success: boolean }[] = [];
  if (!history) return trace;

  // Build a map of tool_call_id -> result content
  const resultMap: Record<string, string> = {};
  for (const msg of history) {
    if (msg.role === 'tool' && msg.tool_call_id) {
      resultMap[msg.tool_call_id] = msg.content || '';
    }
  }

  for (const msg of history) {
    if (!msg.tool_calls) continue;
    for (const tc of msg.tool_calls) {
      const name = tc.function?.name || 'unknown';
      let args: any = {};
      let argsText = '';
      try {
        argsText = tc.function?.arguments || '';
        args = JSON.parse(argsText);
      } catch (_) { /* keep empty */ }

      const rawResult = resultMap[tc.id] || '';
      let success = false;
      try {
        const parsed = JSON.parse(rawResult);
        success = parsed.success !== false;
      } catch (_) { success = rawResult.length > 0; }

      trace.push({ name, args, argsText, result: rawResult, success });
    }
  }
  return trace;
};

/** Summarize tool arguments for display */
const summarizeArgs = (name: string, args: any): string => {
  try {
    if (name === 'write_file') return `文件: ${args.file_path || '?'}`;
    if (name === 'read_file') return `文件: ${args.file_path || '?'}`;
    if (name === 'execute_command') return `命令: ${args.command || '?'}`;
    if (name === 'list_directory') return `路径: ${args.path || '.'}`;
    if (name === 'run_tests') return `目录: ${args.test_dir || '?'}`;
    if (name === 'get_git_diff') return args.file_path ? `文件: ${args.file_path}` : '全部变更';
    if (name === 'create_checkpoint') return `文件数: ${(args.files || []).length}`;
    if (name === 'rollback_checkpoint') return `Checkpoint: ${args.checkpoint_id || '?'}`;
    return JSON.stringify(args).slice(0, 80);
  } catch (_) { return ''; }
};

/** Render a unified diff with color coding (red=removed, green=added) */
const DiffViewer: React.FC<{ diff: string }> = ({ diff }) => {
  if (!diff) return <Text type="secondary" style={{ fontSize: 12 }}>无代码变更</Text>;
  const lines = diff.split('\n');
  return (
    <div style={{
      background: '#fff', border: '1px solid #e8e8e8', borderRadius: 4,
      maxHeight: 300, overflow: 'auto', fontFamily: "'Cascadia Code', monospace", fontSize: 11,
    }}>
      {lines.map((line, i) => {
        let bg = '#fff';
        let color = '#333';
        if (line.startsWith('@@')) { bg = '#f6f8fa'; color = '#24292e'; }
        else if (line.startsWith('+')) { bg = '#e6ffec'; color = '#1a7f37'; }
        else if (line.startsWith('-')) { bg = '#ffebe9'; color = '#cf222e'; }
        else if (line.startsWith(' ')) { bg = '#fff'; color = '#333'; }
        return (
          <div key={i} style={{
            padding: '0 6px', whiteSpace: 'pre', background: bg, color,
            borderBottom: '1px solid #f6f8fa',
          }}>
            {line || ' '}
          </div>
        );
      })}
    </div>
  );
};

const AgentResult: React.FC<{ result: any }> = ({ result }) => {
  // Use edited_files from backend as primary source (more reliable than parsing conversation_history)
  const writeFiles = (result.edited_files || []).map((f: string) => ({
    path: f,
    content: '',
    isNew: false,
  }));
  const toolTrace = extractToolTrace(result.conversation_history);

  return (
    <div>
      <Space style={{ marginBottom: 8 }}>
        <Tag color="green" icon={<CheckCircleOutlined />}>完成</Tag>
        <Tag>{result.rounds} 轮</Tag>
        {result.total_time_seconds && <Tag>{result.total_time_seconds.toFixed(1)}s</Tag>}
        <Tag color="purple">{result.checkpoints_count || 0} 快照</Tag>
        {toolTrace.length > 0 && <Tag color="blue">{toolTrace.length} 工具调用</Tag>}
      </Space>
      {result.read_files?.length > 0 && (
        <div style={{ marginBottom: 4 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>已读文件:</Text>
          <div>{result.read_files.map((f: string, i: number) => (
            <Tag key={i} style={{ fontSize: 11 }}><FileOutlined /> {f}</Tag>
          ))}</div>
        </div>
      )}
      {result.edited_files?.length > 0 && (
        <div style={{ marginBottom: 4 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>修改/生成文件:</Text>
          <div>{result.edited_files.map((f: string, i: number) => (
            <Tag key={i} color="orange" style={{ fontSize: 11 }}><FileOutlined /> {f}</Tag>
          ))}</div>
        </div>
      )}
      <Collapse ghost size="small">
        <Panel header={`查看详情 (${writeFiles.length} 个文件)`} key="1">
          {result.task_id && <p style={{ fontSize: 12, color: '#999' }}>Task ID: {result.task_id}</p>}
          {writeFiles.length === 0 && <Text type="secondary" style={{ fontSize: 12 }}>没有生成或修改代码</Text>}
          {writeFiles.map((f: any, i: number) => (
            <div key={i} style={{ marginBottom: 12, border: '1px solid #e8e8e8', borderRadius: 6, overflow: 'hidden' }}>
              <div style={{
                background: '#fafafa', padding: '4px 10px', fontSize: 12,
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                borderBottom: '1px solid #e8e8e8',
              }}>
                <span><FileOutlined style={{ marginRight: 6 }} />{f.path}</span>
                <Tag color={f.isNew ? 'green' : 'orange'} style={{ fontSize: 10, margin: 0 }}>
                  {f.isNew ? '生成' : '修改'}
                </Tag>
              </div>
              {f.isNew ? (
                <pre style={{
                  margin: 0, padding: 10, fontSize: 12, lineHeight: 1.5,
                  background: '#f8f8f8', color: '#333', overflow: 'auto',
                  maxHeight: 500, fontFamily: "'Cascadia Code', 'Fira Code', monospace",
                }}>
                  <code>{f.content}</code>
                </pre>
              ) : (
                <div style={{ padding: '8px 10px', fontSize: 12, color: '#999', background: '#fafafa' }}>
                  文件已修改，代码变更见磁盘上的实际文件
                </div>
              )}
            </div>
          ))}

          {/* Tool call trace */}
          {toolTrace.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <Divider style={{ margin: '8px 0' }} />
              <Text strong style={{ fontSize: 13 }}>工具调用记录</Text>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
                {toolTrace.map((t, i) => (
                  <div key={i} style={{
                    border: '1px solid #e8e8e8', borderRadius: 6, padding: '6px 10px',
                    background: t.success ? '#fafff8' : '#fffaf5',
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                      <Tag color={t.success ? 'green' : 'orange'} style={{ fontSize: 10, margin: 0 }}>
                        {t.success ? '✓' : '✗'} {t.name}
                      </Tag>
                      <Text style={{ fontSize: 12, color: '#555' }}>{summarizeArgs(t.name, t.args)}</Text>
                    </div>
                    {t.result && (
                      <div style={{ marginTop: 4 }}>
                        <Collapse ghost size="small">
                          <Panel header={`结果 (${t.result.length} 字符)`} key="result">
                            <pre style={{
                              fontSize: 11, color: '#666', whiteSpace: 'pre-wrap', wordBreak: 'break-all',
                              background: '#f8f8f8', padding: 8, borderRadius: 4, maxHeight: 200, overflow: 'auto',
                            }}>
                              {t.result}
                            </pre>
                          </Panel>
                        </Collapse>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </Panel>
      </Collapse>
    </div>
  );
};

export default AgentPage;
