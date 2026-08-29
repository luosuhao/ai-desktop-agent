import React, { useState, useEffect } from 'react';
import {
  Card, Row, Col, List, Tag, Typography, Button, Modal, Descriptions,
  Collapse, message, Space, Input, Select, Alert, Steps, Divider, Upload,
} from 'antd';
import {
  AppstoreOutlined, PlayCircleOutlined, FileTextOutlined,
  CheckCircleOutlined, HistoryOutlined, UploadOutlined,
  InboxOutlined, ReloadOutlined,
} from '@ant-design/icons';
import { listSkills, matchSkills, executeSkill, getSkillHistory, clearSkillHistory, uploadDocument, chat } from '../api';

const { Text, Paragraph, Title } = Typography;
const { TextArea } = Input;
const { Panel } = Collapse;
const { Dragger } = Upload;

const SkillPage: React.FC = () => {
  const [skills, setSkills] = useState<any[]>([]);
  const [history, setHistory] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedSkill, setSelectedSkill] = useState<any>(null);
  const [detailVisible, setDetailVisible] = useState(false);
  const [execVisible, setExecVisible] = useState(false);
  const [taskDesc, setTaskDesc] = useState('');
  const [matchedSkills, setMatchedSkills] = useState<any[]>([]);
  const [execResult, setExecResult] = useState<any>(null);
  const [executingSkill, setExecutingSkill] = useState<string | null>(null);
  const [uploadedFiles, setUploadedFiles] = useState<any[]>([]);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    loadSkills();
    loadHistory();
  }, []);

  const loadSkills = async () => {
    setLoading(true);
    try {
      const res = await listSkills();
      setSkills(res.data.skills || []);
    } catch (e) { message.error('Failed to load skills'); }
    setLoading(false);
  };

  const [historyLoading, setHistoryLoading] = useState(false);

  const loadHistory = async () => {
    setHistoryLoading(true);
    try {
      const res = await getSkillHistory();
      setHistory(res.data.history || []);
      message.success('执行历史已刷新');
    } catch (e) { message.error('刷新失败'); }
    setHistoryLoading(false);
  };

  const handleMatch = async () => {
    if (!taskDesc.trim()) return;
    try {
      const res = await matchSkills(taskDesc);
      setMatchedSkills(res.data.matched || []);
    } catch (e) { message.error('Match failed'); }
  };

  const handleResetExec = () => {
    setTaskDesc('');
    setUploadedFiles([]);
    setMatchedSkills([]);
    setExecResult(null);
    message.success('已重置，可开始新任务');
  };

  const handleUpload = async (file: File) => {
    setUploading(true);
    try {
      const res = await uploadDocument(file);
      const filePath = res.data?.document_id ? `uploads/${res.data.document_id}${res.data.file_type}` : file.name;
      setUploadedFiles(prev => [...prev, { file, result: res.data, name: file.name, path: filePath }]);
      message.success(`上传成功: ${file.name}`);
    } catch (e) {
      message.error('上传失败');
    }
    setUploading(false);
    return false;
  };

  const handleExecute = async (skillName: string) => {
    setExecutingSkill(skillName);
    setExecResult(null);

    const desc = taskDesc || 'Untitled Task';
    let inputs: any = { description: desc };

    // Try to generate content from uploaded file using AI (skill-aware prompt)
    let aiContent = '';
    const isWordSkill = skillName.includes('word');
    if (uploadedFiles.length > 0) {
      try {
        const fileList = uploadedFiles.map(f => f.name).join(', ');
        const sysPrompt = isWordSkill
          ? '你是实验报告撰写助手。你将撰写适配Microsoft Word排版的正式实验室实验报告，只输出纯正文文本，禁止Markdown语法。严格使用 1/1.1/1.1.1 多级数字章节编号；图片标注「图X 标题」放图下、表格标注「表X 标题」放表上；参考文献按 GB/T 7714；使用规范学术书面语，遵循标准实验报告完整框架：绪论→原理→实验方案→结果分析→结论。'
          : '你是技术文档撰写助手。你将使用标准GFM Markdown撰写技术报告。标题层级最多4级；行文简洁侧重技术逻辑与数据展示；无需生成正式图编号表编号、不需要严格GB/T7714参考文献；支持公式、代码块、Markdown表格；输出仅Markdown文本。';
        const msg = {
          role: 'user',
          content: `任务描述: ${desc}\n\n上传文件: ${fileList}\n\n请根据任务描述和上传文件内容，${isWordSkill ? '生成一份正式实验报告的章节内容（绪论/实验原理/实验环境与方案/实验结果与数据分析/实验结论）。' : '生成一份技术报告的章节内容（概述/方案与原理/实验设置/结果与分析/总结）。'}请用中文回答。`
        };
        const aiRes = await chat([{ role: 'system', content: sysPrompt }, msg]);
        aiContent = aiRes.data?.content || '';
      } catch (e) {
        // AI call failed, continue with defaults
      }
    }

    if (skillName.includes('word')) {
      inputs.title = desc;
      inputs.author = 'AI Desktop System';
      inputs.course = '实验报告';
      if (aiContent) {
        inputs.sections = [
          { title: '实验目的', content: aiContent.slice(0, 500), level: 'section' },
          { title: '实验原理', content: aiContent.length > 500 ? aiContent.slice(500, 1000) : '基于AI桌面端系统自动生成实验报告。', level: 'section' },
          { title: '实验步骤', content: '1. 上传数据文件\n2. 配置模型参数\n3. 执行Skill生成文档\n4. 下载查看结果', level: 'section' },
          { title: '实验结果', content: aiContent.slice(0, 300), level: 'section' },
          { title: '实验结论', content: 'AI桌面端系统成功根据输入文件生成了完整的实验报告。', level: 'section' },
        ];
      } else {
        inputs.sections = [
          { title: '实验目的', content: desc, level: 'section' },
          { title: '实验原理', content: '本实验基于AI桌面端系统的Skill能力自动生成实验报告文档。', level: 'section' },
          { title: '实验步骤', content: '1. 配置模型参数\n2. 输入任务描述\n3. 调用Word技能\n4. 生成实验报告文档', level: 'section' },
          { title: '实验结果', content: '成功生成Word格式实验报告，包含封面、目录、正文内容和表格。', level: 'section' },
          { title: '实验结论', content: 'AI桌面端系统能够根据任务描述自动生成结构完整的Word实验报告。', level: 'section' },
        ];
      }
    } else if (skillName.includes('markdown') || skillName.includes('report')) {
      inputs.title = desc;
      inputs.author = 'AI Desktop System';
      inputs.sections = [
        { title: '摘要', content: aiContent || '本文档由AI桌面端系统自动生成。', level: 'section' },
        { title: '引言', content: desc, level: 'section' },
        { title: '方法', content: '使用AI桌面端系统的Markdown技能自动生成论文框架和内容。', level: 'section' },
        { title: '结果', content: aiContent ? aiContent.slice(0, 500) : '成功生成Markdown文档。', level: 'section' },
        { title: '结论', content: 'AI桌面端系统能够自动生成结构完整的Markdown论文。', level: 'section' },
      ];
    } else if (skillName.includes('doc-ppt') || skillName.includes('excel-ppt')) {
      // 新 ppt 技能：doc-ppt-online / doc-ppt-offline / excel-ppt，使用上传的源文件
      inputs.source_file = uploadedFiles.length > 0 ? uploadedFiles[0].path : '';
      inputs.document_path = uploadedFiles.length > 0 ? uploadedFiles[0].path : '';
      inputs.description = desc;
    } else {
      inputs.title = desc;
      inputs.sections = [{ title: '概述', content: aiContent || desc, level: 'section' }];
    }

    // Add uploaded files info to all inputs
    if (uploadedFiles.length > 0) {
      inputs.figures = uploadedFiles.map(f => f.name);
    }

    try {
      const res = await executeSkill(skillName, inputs);
      setExecResult(res.data);
      loadHistory();
    } catch (e) {
      message.error('Execution failed');
    }
    setExecutingSkill(null);
  };

  return (
    <div>
      <Row gutter={16}>
        <Col span={8}>
          <Card title={
            <Space><AppstoreOutlined /> Skill 列表 ({skills.length})</Space>
          } size="small" style={{ marginBottom: 16 }}
            extra={<Button size="small" icon={<ReloadOutlined />} onClick={loadSkills}>刷新</Button>}
          >
            <List
              loading={loading}
              dataSource={skills}
              renderItem={(skill: any) => (
                <List.Item
                  style={{ alignItems: 'flex-start', flexWrap: 'nowrap' }}
                  actions={[
                    <Button size="small" onClick={() => {
                      setSelectedSkill(skill);
                      setDetailVisible(true);
                    }}>详情</Button>,
                    <Button size="small" type="primary" icon={<PlayCircleOutlined />}
                      onClick={() => {
                        setSelectedSkill(skill);
                        setExecVisible(true);
                      }}>运行</Button>,
                  ]}
                >
                  <List.Item.Meta
                    avatar={<AppstoreOutlined />}
                    title={skill.name}
                    description={
                      <Space size={[2, 2]} wrap style={{ flexWrap: 'wrap' }}>
                        <Tag style={{ fontSize: 10 }}>{skill.version}</Tag>
                        {skill.signature_verified === false ? (
                          <Tag color="orange" style={{ fontSize: 10 }}>⚠ 未验证</Tag>
                        ) : (
                          <Tag color="blue" style={{ fontSize: 10 }}>已验证</Tag>
                        )}
                        <Tag color={skill.risk_level === 'low' ? 'green' : 'orange'} style={{ fontSize: 10 }}>
                          {skill.risk_level || 'low'} 风险
                        </Tag>
                      </Space>
                    }
                  />
                </List.Item>
              )}
            />
          </Card>

          <Card title={<Space><HistoryOutlined /> 执行历史</Space>} size="small"
            extra={<Space>
              <Button size="small" icon={<ReloadOutlined />} onClick={loadHistory} loading={historyLoading}>刷新</Button>
              <Button size="small" danger onClick={() => {
                Modal.confirm({
                  title: '清空执行历史？',
                  content: '将删除所有执行记录，此操作不可恢复。',
                  okText: '确认清空',
                  okType: 'danger',
                  cancelText: '取消',
                  onOk: async () => {
                    try {
                      await clearSkillHistory();
                      setHistory([]);
                      message.success('执行历史已清空');
                    } catch (_) { message.error('清空失败'); }
                  },
                });
              }}>清空</Button>
            </Space>}
          >
            <List
              loading={historyLoading}
              dataSource={history.slice(-10).reverse()}
              renderItem={(h: any) => (
                <List.Item>
                  <div style={{ fontSize: 13 }}>
                    <Space>
                      <Tag>{h.skill_name}</Tag>
                      {h.success ? <Tag color="green">成功</Tag> : <Tag color="red">失败</Tag>}
                    </Space>
                    <br />
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {h.completed_at || ''}
                    </Text>
                  </div>
                </List.Item>
              )}
              locale={{ emptyText: '暂无执行记录' }}
            />
          </Card>
        </Col>

        <Col span={16}>
          <Card title="执行 Skill" size="small" style={{ marginBottom: 16 }}
            extra={<Button size="small" icon={<ReloadOutlined />} onClick={handleResetExec}>重置</Button>}
          >
            <Space direction="vertical" style={{ width: '100%' }}>
              <TextArea
                rows={3}
                value={taskDesc}
                onChange={e => setTaskDesc(e.target.value)}
                placeholder="输入任务描述...&#10;例如: 生成一份数据分析报告"
              />
              <Dragger
                multiple={false}
                showUploadList={false}
                beforeUpload={handleUpload}
                accept=".csv,.xlsx,.xls,.pdf,.png,.jpg,.jpeg,.docx,.pptx,.md,.txt"
                style={{ padding: 8 }}
              >
                <p><UploadOutlined style={{ fontSize: 20 }} /></p>
                <p style={{ fontSize: 12 }}>点击或拖拽上传文件</p>
              </Dragger>
              {uploadedFiles.length > 0 && (
                <div>
                  <Text strong>已上传文件:</Text>
                  {uploadedFiles.map((f, i) => (
                    <Tag key={i} closable onClose={() => {
                      setUploadedFiles(prev => prev.filter((_, j) => j !== i));
                    }}>{f.name}</Tag>
                  ))}
                </div>
              )}
              <Button onClick={handleMatch} disabled={!taskDesc.trim() && uploadedFiles.length === 0}>匹配 Skill</Button>
            </Space>

            {matchedSkills.length > 0 && (
              <div style={{ marginTop: 12 }}>
                <Text strong>匹配结果:</Text>
                {matchedSkills.map((m: any, i: number) => (
                  <Card key={i} size="small" style={{ marginTop: 8 }}>
                    <Space>
                      <Tag color="blue">{m.skill.name}</Tag>
                      <Tag>匹配度: {m.match_score}</Tag>
                      <Button size="small" type="primary"
                        onClick={() => handleExecute(m.skill.name)}
                        loading={executingSkill === m.skill.name}
                      >
                        执行
                      </Button>
                    </Space>
                    <Paragraph ellipsis={{ rows: 2 }} style={{ marginTop: 4 }}>
                      {m.skill.description}
                    </Paragraph>
                  </Card>
                ))}
              </div>
            )}
          </Card>

          {execResult && (
            <Card title="执行结果" size="small">
              {execResult.success ?
                <Alert type="success" message="执行成功" showIcon /> :
                <Alert type="error" message={`失败: ${execResult.error}`} showIcon />}

              {/* 结果位置（绝对路径，便于在文件系统中定位） */}
              {execResult.pptx_file && (
                <div style={{ marginTop: 8, padding: 10, background: '#f6ffed', border: '1px solid #b7eb8f', borderRadius: 6 }}>
                  <Text strong>结果位置:</Text>
                  <div style={{ marginTop: 4 }}>
                    <Text code copyable style={{ wordBreak: 'break-all', fontSize: 12 }}>
                      {execResult.pptx_file}
                    </Text>
                  </div>
                  {execResult.project_dir && (
                    <div style={{ marginTop: 4 }}>
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        项目目录: {execResult.project_dir}
                      </Text>
                    </div>
                  )}
                </div>
              )}

              {execResult.logs && (
                <Collapse style={{ marginTop: 8 }}>
                  <Panel header="执行日志" key="1">
                    <pre style={{ fontSize: 12, maxHeight: 300, overflow: 'auto' }}>
                      {execResult.logs.join('\n')}
                    </pre>
                  </Panel>
                </Collapse>
              )}

              {execResult.validation && (
                <div style={{ marginTop: 8 }}>
                  <Text strong>验证结果:</Text>
                  {Object.entries(execResult.validation).map(([k, v]: any) => (
                    <div key={k}>
                      <Tag color={v ? 'green' : 'red'}>{k}: {v ? '✓' : '✗'}</Tag>
                    </div>
                  ))}
                </div>
              )}

              {execResult.generated_files?.length > 0 && (
                <div style={{ marginTop: 8 }}>
                  <Text strong>生成文件:</Text>
                  {execResult.generated_files.map((f: string, i: number) => {
                    const fname = f.split('\\').pop() || f.split('/').pop() || f;
                    return (
                      <div key={i} style={{ margin: '4px 0' }}>
                        <Button
                          type="link"
                          icon={<FileTextOutlined />}
                          href={`/api/outputs/${encodeURIComponent(fname)}`}
                          target="_blank"
                          size="small"
                        >
                          {fname}
                        </Button>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Direct output fields from skills */}
              {execResult.docx_file && (
                <div style={{ marginTop: 8 }}>
                  <Text strong>Word 文件:</Text>
                  <Button type="link" href={`/api/outputs/${encodeURIComponent(execResult.docx_file.split('\\').pop() || execResult.docx_file.split('/').pop())}`} target="_blank" size="small">
                    {execResult.docx_file.split('\\').pop() || execResult.docx_file.split('/').pop()}
                  </Button>
                </div>
              )}
              {execResult.tex_file && (
                <div style={{ marginTop: 8 }}>
                  <Text strong>LaTeX 文件:</Text>
                  <Button type="link" href={`/api/outputs/${encodeURIComponent(execResult.tex_file.split('\\').pop() || execResult.tex_file.split('/').pop())}`} target="_blank" size="small">
                    {execResult.tex_file.split('\\').pop() || execResult.tex_file.split('/').pop()}
                  </Button>
                </div>
              )}
              {execResult.pdf_file && (
                <div style={{ marginTop: 8 }}>
                  <Text strong>PDF 文件:</Text>
                  <Button type="link" href={`/api/outputs/${encodeURIComponent(execResult.pdf_file.split('\\').pop() || execResult.pdf_file.split('/').pop())}`} target="_blank" size="small">
                    {execResult.pdf_file.split('\\').pop() || execResult.pdf_file.split('/').pop()}
                  </Button>
                </div>
              )}
              {execResult.code_file && (
                <div style={{ marginTop: 8 }}>
                  <Text strong>代码文件:</Text>
                  <Button type="link" href={`/api/outputs/${encodeURIComponent(execResult.code_file.split('\\').pop() || execResult.code_file.split('/').pop())}`} target="_blank" size="small">
                    {execResult.code_file.split('\\').pop() || execResult.code_file.split('/').pop()}
                  </Button>
                </div>
              )}
              {execResult.report && (
                <Collapse style={{ marginTop: 8 }} size="small">
                  <Panel header="分析报告预览" key="report">
                    <pre style={{ fontSize: 12, maxHeight: 300, overflow: 'auto', whiteSpace: 'pre-wrap' }}>
                      {execResult.report}
                    </pre>
                  </Panel>
                </Collapse>
              )}
            </Card>
          )}
        </Col>
      </Row>

      {/* Skill Detail Modal */}
      <Modal
        title={`Skill: ${selectedSkill?.name}`}
        open={detailVisible}
        onCancel={() => setDetailVisible(false)}
        footer={null}
        width={700}
      >
        {selectedSkill && (
          <div>
            {/* Verification status banner (NVIDIA Verified principle) */}
            {selectedSkill.signature_verified ? (
              <Alert type="success" showIcon style={{ marginBottom: 12 }}
                message="已验证签名" description={`扫描时间: ${selectedSkill.last_scan_time || 'N/A'}`} />
            ) : (
              <Alert type="warning" showIcon style={{ marginBottom: 12 }}
                message="未验证技能" description="未提供签名哈希，默认视为不可信。加载外部技能时请核验来源。" />
            )}

            <Descriptions column={1} size="small">
              <Descriptions.Item label="名称">{selectedSkill.name}</Descriptions.Item>
              <Descriptions.Item label="版本">{selectedSkill.version}</Descriptions.Item>
              <Descriptions.Item label="描述">{selectedSkill.description}</Descriptions.Item>
              <Descriptions.Item label="触发词">{selectedSkill.trigger}</Descriptions.Item>
            </Descriptions>

            {/* Skill Card governance metadata */}
            <Divider />
            <Text strong>Skill Card（治理元数据）</Text>
            <Descriptions column={2} size="small" style={{ marginTop: 8 }}>
              <Descriptions.Item label="归属">{selectedSkill.owner || 'AI Desktop System'}</Descriptions.Item>
              <Descriptions.Item label="生命周期">
                <Tag color={selectedSkill.lifecycle === 'stable' ? 'green' : selectedSkill.lifecycle === 'beta' ? 'orange' : 'red'}>
                  {selectedSkill.lifecycle}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="风险等级">
                <Tag color={selectedSkill.risk_level === 'low' ? 'green' : selectedSkill.risk_level === 'medium' ? 'orange' : 'red'}>
                  {selectedSkill.risk_level}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="依赖">{selectedSkill.dependencies?.join(', ') || '无'}</Descriptions.Item>
              <Descriptions.Item label="权限" span={2}>
                {selectedSkill.permissions ? (
                  <Space size={4} wrap>
                    {Object.entries(selectedSkill.permissions).map(([k, v]) => (
                      <Tag key={k} color={v ? 'blue' : 'default'} style={{ fontSize: 11 }}>
                        {k}: {v ? '允许' : '禁止'}
                      </Tag>
                    ))}
                  </Space>
                ) : '未定义'}
              </Descriptions.Item>
            </Descriptions>

            {(selectedSkill.limitations?.length > 0 || selectedSkill.constraints?.length > 0) && (
              <>
                <Divider />
                {selectedSkill.limitations?.length > 0 && (
                  <>
                    <Text strong>已知限制:</Text>
                    <ul>
                      {selectedSkill.limitations.map((l: string, i: number) => (
                        <li key={i}><Text style={{ fontSize: 13 }}>{l}</Text></li>
                      ))}
                    </ul>
                  </>
                )}
                {selectedSkill.constraints?.length > 0 && (
                  <>
                    <Text strong>约束规则:</Text>
                    <ul>
                      {selectedSkill.constraints.map((c: string, i: number) => (
                        <li key={i}><Text style={{ fontSize: 13 }}>{c}</Text></li>
                      ))}
                    </ul>
                  </>
                )}
              </>
            )}

            <Divider />
            <Text strong>工作流:</Text>
            <Steps
              direction="vertical"
              size="small"
              current={-1}
              items={selectedSkill.workflow?.map((w: string) => ({ title: w })) || []}
            />

            <Divider />
            <Text strong>验证标准:</Text>
            <ul>
              {selectedSkill.validation?.map((v: string, i: number) => (
                <li key={i}><Text style={{ fontSize: 13 }}>{v}</Text></li>
              ))}
            </ul>

            <Divider />
            <Text strong>工具:</Text>
            <Space wrap>
              {selectedSkill.tools?.map((t: string, i: number) => (
                <Tag key={i}>{t}</Tag>
              ))}
            </Space>
          </div>
        )}
      </Modal>

      {/* Exec Modal */}
      <Modal
        title={`运行 Skill: ${selectedSkill?.name}`}
        open={execVisible}
        onCancel={() => setExecVisible(false)}
        onOk={() => {
          if (selectedSkill) {
            handleExecute(selectedSkill.name);
            setExecVisible(false);
          }
        }}
        confirmLoading={!!executingSkill}
        width={600}
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <Text>{selectedSkill?.description}</Text>
          <TextArea
            rows={3}
            value={taskDesc}
            onChange={e => setTaskDesc(e.target.value)}
            placeholder="输入任务描述..."
          />
          <Text type="secondary">
            触发词: {selectedSkill?.trigger}
          </Text>
        </Space>
      </Modal>
    </div>
  );
};

export default SkillPage;
