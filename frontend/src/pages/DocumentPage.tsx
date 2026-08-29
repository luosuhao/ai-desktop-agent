import React, { useState, useEffect } from 'react';
import {
  Card, Upload, Button, message, List, Tag, Typography, Input, Space,
  Collapse, Spin, Row, Col, Divider, Table, Alert, Modal, Checkbox, Switch,
} from 'antd';
import {
  UploadOutlined, FileTextOutlined, DeleteOutlined,
  SearchOutlined, QuestionCircleOutlined, FileExcelOutlined, ReloadOutlined,
} from '@ant-design/icons';
import {
  uploadDocument, listDocuments, getDocument, deleteDocument,
  searchRag, qaQuery, financeQa, getDocumentTables,
} from '../api';
import TableRecognitionPanel from '../components/TableRecognitionPanel';

const { Text, Paragraph, Title } = Typography;
const { TextArea } = Input;
const { Panel } = Collapse;

const DocumentPage: React.FC = () => {
  const [docs, setDocs] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedDoc, setSelectedDoc] = useState<any>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [qaQuery_text, setQaQuery] = useState('');
  const [qaResult, setQaResult] = useState<any>(null);
  const [qaLoading, setQaLoading] = useState(false);
  const [docDetail, setDocDetail] = useState<any>(null);
  const [extractTables, setExtractTables] = useState(false);
  const [financeMode, setFinanceMode] = useState(false);

  useEffect(() => { loadDocuments(); }, []);

  const loadDocuments = async () => {
    setLoading(true);
    try {
      const res = await listDocuments();
      setDocs(res.data.documents || []);
    } catch (e) {
      message.error('Failed to load documents');
    }
    setLoading(false);
  };

  const handleUpload = async (file: File) => {
    try {
      const res = await uploadDocument(file, extractTables);
      const tn = res.data?.tablenet;
      if (tn?.attempted) {
        if (tn.error) {
          message.warning(`表格提取失败，已回退普通解析: ${tn.error}`);
        } else if ((tn.tables_count || 0) === 0) {
          message.info('未识别出表格（保留普通文本解析）');
        } else {
          message.success(`提取到 ${tn.tables_count} 个表格`);
        }
      }
      message.success(`Document uploaded: ${file.name}`);
      loadDocuments();
      return res.data;
    } catch (e) {
      message.error('Upload failed');
      return null;
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteDocument(id);
      message.success('Document deleted');
      loadDocuments();
      if (selectedDoc?.id === id) setSelectedDoc(null);
    } catch (e) {
      message.error('Delete failed');
    }
  };

  const handleViewDoc = async (id: string) => {
    try {
      const res = await getDocument(id);
      setDocDetail(res.data);
    } catch (e) {
      message.error('Failed to load document');
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    try {
      const res = await searchRag({ query: searchQuery, top_k: 5, method: 'hybrid' });
      setSearchResults(res.data.results || []);
    } catch (e) {
      message.error('Search failed');
    }
  };

  const handleQA = async () => {
    if (!qaQuery_text.trim()) return;
    setQaLoading(true);
    setQaResult(null);
    try {
      const res = financeMode
        ? await financeQa({
            query: qaQuery_text,
            top_k: 8,
            document_ids: selectedDoc ? [selectedDoc.id] : undefined,
          })
        : await qaQuery({ query: qaQuery_text, top_k: 5 });
      setQaResult(res.data);
    } catch (e) {
      message.error('QA failed');
    }
    setQaLoading(false);
  };

  return (
    <div>
      <Row gutter={16}>
        <Col span={8}>
          <Card title="文档列表" size="small" style={{ marginBottom: 16 }}
            extra={<Button size="small" icon={<ReloadOutlined />} onClick={loadDocuments}>刷新</Button>}
          >
            <Checkbox
              checked={extractTables}
              onChange={e => setExtractTables(e.target.checked)}
              style={{ marginBottom: 8 }}
            >
              提取表格 (TableNet，PDF 首次上传需加载模型约 1-2 分钟)
            </Checkbox>
            <Upload.Dragger
              multiple={false}
              showUploadList={false}
              beforeUpload={(file) => {
                const ext = file.name.split('.').pop()?.toLowerCase();
                if (ext !== 'pdf' && ext !== 'docx') {
                  message.warning('仅支持 PDF/Word 文件');
                  return false;
                }
                handleUpload(file);
                return false;
              }}
              accept=".pdf,.docx"
            >
              <p><UploadOutlined style={{ fontSize: 24 }} /></p>
              <p>拖拽或点击上传文档</p>
              <p style={{ fontSize: 12, color: '#888' }}>仅支持 PDF/Word 文档</p>
            </Upload.Dragger>

            <List
              style={{ marginTop: 12, maxHeight: 400, overflow: 'auto' }}
              loading={loading}
              dataSource={docs}
              renderItem={(doc: any) => (
                <List.Item
                  style={{ cursor: 'pointer' }}
                  onClick={() => { setSelectedDoc(doc); handleViewDoc(doc.id); }}
                  actions={[
                    <Button type="text" danger size="small" icon={<DeleteOutlined />}
                      onClick={(e) => { e.stopPropagation(); handleDelete(doc.id); }} />
                  ]}
                >
                  <List.Item.Meta
                    avatar={doc.file_type === '.pdf' ? <FileTextOutlined /> : <FileExcelOutlined />}
                    title={<Text style={{ fontSize: 13 }}>{doc.filename}</Text>}
                    description={
                      <div>
                        <Tag>{doc.file_type}</Tag>
                        <Tag>{doc.page_count}页</Tag>
                        <Tag>{doc.tables_count}表</Tag>
                      </div>
                    }
                  />
                </List.Item>
              )}
              locale={{ emptyText: '暂无文档' }}
            />
          </Card>

          {/* Document Detail */}
          {docDetail && (
            <Card title="文档详情" size="small">
              <Collapse>
                <Panel header={`${docDetail.pages?.length || 0} 页`} key="pages">
                  {docDetail.pages?.slice(0, 3).map((p: any, i: number) => (
                    <div key={i} style={{ marginBottom: 8 }}>
                      <Text strong>Page {p.page_num}:</Text>
                      <Paragraph ellipsis={{ rows: 3 }} style={{ fontSize: 12 }}>
                        {p.text?.slice(0, 300) || '(empty)'}
                      </Paragraph>
                    </div>
                  ))}
                </Panel>
                <Panel header={`${docDetail.tables?.length || 0} 个表格`} key="tables">
                  {docDetail.tables?.map((t: any, i: number) => (
                    <div key={i} style={{ fontSize: 12, marginBottom: 12 }}>
                      <Text strong>Table {i + 1}</Text>
                      {t.source && <Tag>{t.source}</Tag>}
                      <Tag>{t.rows}x{t.cols}</Tag>
                      {t.run_id && (
                        <a
                          href={`/api/outputs/tablenet/${t.run_id}/result.html`}
                          target="_blank"
                          rel="noreferrer"
                        >
                          原始结果
                        </a>
                      )}
                      {t.headers?.length > 0 && t.data?.length > 0 ? (
                        <Table
                          size="small"
                          rowKey="key"
                          pagination={{ pageSize: 8, showSizeChanger: false }}
                          columns={t.headers.map((h: string, ci: number) => ({
                            title: h || `列${ci + 1}`,
                            dataIndex: `c${ci}`,
                            key: ci,
                            render: (v: string) => v || '',
                          }))}
                          dataSource={t.data.map((row: string[], ri: number) => {
                            const obj: Record<string, string> = { key: `${i}-${ri}` };
                            row.forEach((cell, ci) => { obj[`c${ci}`] = cell; });
                            return obj;
                          })}
                        />
                      ) : (
                        <Paragraph ellipsis={{ rows: 2 }}>{t.markdown}</Paragraph>
                      )}
                    </div>
                  ))}
                </Panel>
              </Collapse>
            </Card>
          )}
        </Col>

        <Col span={16}>
          {/* RAG Search */}
          <Card title="RAG 搜索" size="small" style={{ marginBottom: 16 }}>
            <Space>
              <Input.Search
                placeholder="输入搜索关键词..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                onSearch={handleSearch}
                style={{ width: 400 }}
              />
            </Space>
            {searchResults.length > 0 && (
              <List
                style={{ marginTop: 12 }}
                dataSource={searchResults}
                renderItem={(r: any, i: number) => (
                  <List.Item>
                    <div>
                      <Space>
                        <Tag color="blue">{r.chunk_type}</Tag>
                        {r.page_number && <Tag>Page {r.page_number}</Tag>}
                        <Tag>Score: {r.score}</Tag>
                      </Space>
                      <Paragraph ellipsis={{ rows: 3 }} style={{ margin: '4px 0', fontSize: 13 }}>
                        {r.content}
                      </Paragraph>
                      <Text type="secondary" style={{ fontSize: 12 }}>来源: {r.document_name}</Text>
                    </div>
                  </List.Item>
                )}
              />
            )}
          </Card>

          {/* QA */}
          <Card
            title="文档问答"
            size="small"
            extra={
              <Space>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  金融计算模式
                </Text>
                <Switch
                  checked={financeMode}
                  onChange={setFinanceMode}
                  checkedChildren="开"
                  unCheckedChildren="关"
                />
              </Space>
            }
          >
            <Space direction="vertical" style={{ width: '100%' }}>
              <TextArea
                rows={2}
                value={qaQuery_text}
                onChange={e => setQaQuery(e.target.value)}
                placeholder={
                  financeMode
                    ? '输入金融计算问题...&#10;例如: 2022年营业收入同比增长率是多少？（需先在上方列表选中文档）'
                    : '输入问题...&#10;例如: 表格中销售额最高的月份是哪个？'
                }
              />
              <Space>
                <Button
                  type="primary"
                  icon={<QuestionCircleOutlined />}
                  onClick={handleQA}
                  loading={qaLoading}
                >
                  提问
                </Button>
                {financeMode && !selectedDoc && (
                  <Text type="warning" style={{ fontSize: 12 }}>
                    建议在上方选中文档以限定检索范围
                  </Text>
                )}
              </Space>
            </Space>

            {qaResult && (
              <div style={{ marginTop: 16 }}>
                <Card size="small" style={{ background: '#fafafa', border: '1px solid #f0f0f0' }}>
                  <Text strong>回答:</Text>
                  <Paragraph style={{ marginTop: 8, whiteSpace: 'pre-wrap' }}>
                    {qaResult.answer}
                  </Paragraph>
                </Card>

                {qaResult.calculation_steps?.length > 0 && (
                  <Card size="small" style={{ marginTop: 8 }} title="计算过程">
                    <List
                      size="small"
                      dataSource={qaResult.calculation_steps}
                      renderItem={(s: any) => (
                        <List.Item>
                          <Space wrap>
                            <Tag color="green">{s.label}</Tag>
                            <Text code>{s.expression}</Text>
                            <Text>=</Text>
                            <Text strong>{s.result}</Text>
                          </Space>
                        </List.Item>
                      )}
                    />
                  </Card>
                )}

                {qaResult.evidence?.length > 0 && (
                  <Collapse style={{ marginTop: 8 }}>
                    <Panel header={`证据 (${qaResult.evidence.length} 条)`} key="1">
                      {qaResult.evidence.map((e: any, i: number) => (
                        <div key={i} style={{ marginBottom: 8, fontSize: 13 }}>
                          <Space>
                            <Tag color="blue">{e.chunk_type}</Tag>
                            {e.page_number && <Tag>Page {e.page_number}</Tag>}
                            <Text type="secondary">{e.document_name}</Text>
                          </Space>
                          <Paragraph ellipsis={{ rows: 2 }}>{e.content}</Paragraph>
                        </div>
                      ))}
                    </Panel>
                  </Collapse>
                )}
              </div>
            )}
          </Card>
        </Col>
      </Row>

      <Card title="表格识别" size="small" style={{ marginTop: 16 }}>
        <TableRecognitionPanel onDocumentUploaded={loadDocuments} />
      </Card>
    </div>
  );
};

export default DocumentPage;
