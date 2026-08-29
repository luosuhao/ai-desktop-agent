import React, { useState, useEffect } from 'react';
import {
  Card, Row, Col, Typography, Input, Button, Tag, Space,
  Collapse, message, Table, Divider, Alert, Select, Upload, Checkbox, Tabs,
} from 'antd';
import { FileTextOutlined, UploadOutlined } from '@ant-design/icons';
import {
  recognizeTable, uploadDocument, getDocumentTables,
  recognizePdfTables, getTablenetStatus, outputFileUrl,
} from '../api';

const { Text, Paragraph } = Typography;
const { TextArea } = Input;
const { Panel } = Collapse;
const { Dragger } = Upload;

interface Props {
  onDocumentUploaded?: () => void;
}

/** 表格识别面板：通用表格结构识别 + PDF 表格识别（Qwen2-VL-TableNet）。
 *  已并入文档管理页。Excel 导入会走文档上传接口，故提供 onDocumentUploaded 刷新列表。 */
const TableRecognitionPanel: React.FC<Props> = ({ onDocumentUploaded }) => {
  // 通用表格结构识别
  const [source, setSource] = useState('text');
  const [content, setContent] = useState('');
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [uploadedFileName, setUploadedFileName] = useState('');

  // PDF 表格识别（Qwen2-VL-TableNet）
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [pdfResult, setPdfResult] = useState<any>(null);
  const [tablenetStatus, setTablenetStatus] = useState<any>(null);
  const [pageFallback, setPageFallback] = useState(false);

  useEffect(() => {
    getTablenetStatus()
      .then(res => setTablenetStatus(res.data))
      .catch(() => setTablenetStatus({ available: false, error: '无法连接后端' }));
  }, []);

  const handleFileImport = async (file: File) => {
    const ext = file.name.split('.').pop()?.toLowerCase();
    try {
      const text = await file.text();

      if (ext === 'csv') {
        setSource('csv');
        setContent(text);
        setUploadedFileName(file.name);
        message.success(`已导入 CSV: ${file.name}`);
      } else if (ext === 'xlsx' || ext === 'xls') {
        // Upload Excel to backend for parsing, then use result
        const res = await uploadDocument(file, false);
        // Get table from the parsed document
        const docId = res.data.document_id;
        const docRes = await getDocumentTables(docId);
        const tables = docRes.data.tables || [];
        if (tables.length > 0) {
          setContent(tables[0].markdown || '');
          setSource('markdown');
          setUploadedFileName(file.name);
          message.success(`已导入 Excel: ${file.name} (${tables.length}个表格)`);
          onDocumentUploaded?.();
        } else {
          message.warning('Excel中未找到表格');
        }
      } else if (ext === 'md') {
        setSource('markdown');
        setContent(text);
        setUploadedFileName(file.name);
        message.success(`已导入 Markdown: ${file.name}`);
      } else if (ext === 'html' || ext === 'htm') {
        setSource('html');
        setContent(text);
        setUploadedFileName(file.name);
        message.success(`已导入 HTML: ${file.name}`);
      } else {
        // Default: try as text
        setSource('text');
        setContent(text);
        setUploadedFileName(file.name);
        message.success(`已导入: ${file.name}`);
      }
    } catch (e) {
      message.error('文件读取失败');
    }
    return false;
  };

  const handleRecognize = async () => {
    if (!content.trim()) {
      message.warning('请输入表格内容');
      return;
    }
    setLoading(true);
    try {
      const res = await recognizeTable({
        source,
        content,
        table_id: 'test_table_1',
      });
      setResult(res.data);
    } catch (e) {
      message.error('Recognition failed');
    }
    setLoading(false);
  };

  const handlePdfRecognize = async () => {
    if (!pdfFile) {
      message.warning('请先选择 PDF 文件');
      return;
    }
    if (!tablenetStatus?.available) {
      message.warning('模型服务不可用，正在等待启动，首次加载模型需要数十秒...');
    }
    setPdfLoading(true);
    setPdfResult(null);
    try {
      const res = await recognizePdfTables(pdfFile, pageFallback);
      if (res.data.success) {
        setPdfResult(res.data);
        message.success(`识别完成，共 ${res.data.tables_count} 张表`);
      } else {
        message.error(res.data.error || '识别失败');
      }
    } catch (e: any) {
      message.error('PDF 识别失败: ' + (e?.response?.data?.detail || e?.message || '未知错误'));
    }
    setPdfLoading(false);
    // 刷新模型服务状态
    getTablenetStatus().then(r => setTablenetStatus(r.data)).catch(() => {});
  };

  const pdfOutputUrl = (name: string) =>
    pdfResult ? outputFileUrl(`tablenet/${pdfResult.run_id}/${name}`) : '#';

  const modelTag = (
    <Tag color={tablenetStatus?.available ? 'green' : 'orange'}>
      模型: {tablenetStatus?.available ? '服务就绪' : '未启动/加载中'}
    </Tag>
  );

  return (
    <Tabs>
      {/* ---- 通用表格结构识别 ---- */}
      <Tabs.TabPane tab="通用表格识别" key="general">
        <Row gutter={16}>
          <Col span={10}>
            <CardInput
              source={source} setSource={setSource}
              uploadedFileName={uploadedFileName} setUploadedFileName={setUploadedFileName}
              content={content} setContent={setContent}
              handleFileImport={handleFileImport}
              handleRecognize={handleRecognize} loading={loading}
            />
            {result && (
              <Card title="表格分析" size="small" style={{ marginTop: 16 }}>
                <Space wrap>
                  <Tag color="blue">行: {result.complexity?.rows}</Tag>
                  <Tag color="green">列: {result.complexity?.cols}</Tag>
                  <Tag>{result.complexity?.total_cells} 单元格</Tag>
                  {result.complexity?.merged_cells_count > 0 &&
                    <Tag color="orange">合并: {result.complexity.merged_cells_count}</Tag>}
                  {result.complexity?.has_multi_level_headers &&
                    <Tag color="red">多层表头</Tag>}
                  {result.complexity?.is_complex &&
                    <Tag color="purple">复杂表格</Tag>}
                </Space>
              </Card>
            )}
          </Col>
          <Col span={14}>
            {result && (
              <>
                <Card title="识别结果 - Markdown" size="small" style={{ marginBottom: 16 }}>
                  <pre style={{
                    background: '#f8f8f8', padding: 12, borderRadius: 6,
                    overflow: 'auto', fontSize: 13, whiteSpace: 'pre-wrap',
                  }}>
                    {result.markdown}
                  </pre>
                </Card>

                <Card title="结构化数据" size="small" style={{ marginBottom: 16 }}>
                  {result.table?.headers && result.table?.data_rows && (
                    <Table
                      size="small"
                      dataSource={result.table.data_rows.map((row: string[], i: number) => ({
                        key: i,
                        ...Object.fromEntries(result.table.headers.map((h: string, j: number) => [h, row[j] || '']))
                      }))}
                      columns={result.table.headers?.map((h: string) => ({
                        title: h, dataIndex: h, key: h, ellipsis: true,
                      })) || []}
                      pagination={false}
                      scroll={{ x: 'max-content' }}
                    />
                  )}
                </Card>

                <Collapse>
                  <Panel header="JSON 结构" key="1">
                    <pre style={{ fontSize: 12, maxHeight: 300, overflow: 'auto' }}>
                      {JSON.stringify(result.table, null, 2)}
                    </pre>
                  </Panel>
                  <Panel header="CSV 导出" key="2">
                    <pre style={{ fontSize: 12, maxHeight: 200, overflow: 'auto' }}>
                      {result.csv}
                    </pre>
                  </Panel>
                </Collapse>

                {result.saved_files && (
                  <Card title="保存的文件" size="small" style={{ marginTop: 8 }}>
                    <Space>
                      <Button
                        type="link"
                        icon={<FileTextOutlined />}
                        href={outputFileUrl(result.saved_files.md)}
                        target="_blank"
                        size="small"
                      >
                        下载 Markdown (.md)
                      </Button>
                      <Button
                        type="link"
                        icon={<FileTextOutlined />}
                        href={outputFileUrl(result.saved_files.csv)}
                        target="_blank"
                        size="small"
                      >
                        下载 CSV (.csv)
                      </Button>
                    </Space>
                  </Card>
                )}
              </>
            )}
          </Col>
        </Row>
      </Tabs.TabPane>

      {/* ---- PDF 表格识别（Qwen2-VL-TableNet） ---- */}
      <Tabs.TabPane tab={<Space>PDF 表格识别 (TableNet){modelTag}</Space>} key="pdf">
        <Row gutter={16}>
          <Col span={10}>
            <Card
              title="从 PDF 识别表格"
              size="small"
              extra={modelTag}
            >
              <Space direction="vertical" style={{ width: '100%' }}>
                <Dragger
                  showUploadList={false}
                  accept=".pdf,.png,.jpg,.jpeg"
                  beforeUpload={(file) => { setPdfFile(file); message.info(`已选择: ${file.name}`); return false; }}
                  style={{ padding: 8 }}
                >
                  <p><UploadOutlined style={{ fontSize: 20 }} /></p>
                  <p style={{ fontSize: 12 }}>上传 PDF 文件或图表，识别其中的表格</p>
                </Dragger>
                {pdfFile && (
                  <Tag closable onClose={() => setPdfFile(null)}>
                    PDF: {pdfFile.name}
                  </Tag>
                )}
                <Checkbox
                  checked={pageFallback}
                  onChange={e => setPageFallback(e.target.checked)}
                >
                  页面未检测到表格时，整页作为图片识别
                </Checkbox>
                <Button
                  type="primary"
                  onClick={handlePdfRecognize}
                  loading={pdfLoading}
                  block
                >
                  {pdfLoading ? '识别中（首次加载模型需数十秒）...' : '开始识别 PDF 表格'}
                </Button>
                {!tablenetStatus?.available && (
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    点击后将自动启动模型服务进程（tablenet-venv），首次加载约 30-120 秒。
                  </Text>
                )}
              </Space>
            </Card>
          </Col>
          <Col span={14}>
            {pdfResult && (
              <Card title={`PDF 表格识别结果（${pdfResult.tables_count} 张表）`} size="small">
                <Paragraph>
                  <Text type="secondary">输出目录（绝对路径）：</Text>
                  <br />
                  <Text code>{pdfResult.run_dir}</Text>
                </Paragraph>
                <Space wrap style={{ marginBottom: 12 }}>
                  <Button type="link" size="small" icon={<FileTextOutlined />} href={pdfOutputUrl('result.md')} target="_blank">
                    汇总 Markdown
                  </Button>
                  <Button type="link" size="small" icon={<FileTextOutlined />} href={pdfOutputUrl('result.html')} target="_blank">
                    汇总 HTML
                  </Button>
                  <Button type="link" size="small" icon={<FileTextOutlined />} href={pdfOutputUrl('index.json')} target="_blank">
                    index.json
                  </Button>
                </Space>
                <Collapse>
                  {(pdfResult.tables || []).map((t: any, i: number) => (
                    <Panel
                      key={i}
                      header={
                        <span>
                          表格 {i + 1} · 第 {t.page} 页 · {t.source === 'page' ? '整页' : (t.source === 'image' ? '图片' : '检测区域')}
                          {t.error ? <Tag color="red">失败</Tag> : (t.html ? <Tag color="green">成功</Tag> : <Tag color="orange">空结果</Tag>)}
                        </span>
                      }
                    >
                      {t.error && <Alert type="warning" showIcon message={t.error} style={{ marginBottom: 8 }} />}
                      <Space wrap style={{ marginBottom: 8 }}>
                        <Button
                          type="link" size="small" icon={<FileTextOutlined />}
                          href={pdfOutputUrl(`table_${t.page}_${t.index}.png`)} target="_blank"
                        >
                          表格图片
                        </Button>
                        <Button
                          type="link" size="small" icon={<FileTextOutlined />}
                          href={pdfOutputUrl(`table_${t.page}_${t.index}.html`)} target="_blank"
                        >
                          单表 HTML
                        </Button>
                      </Space>
                      {t.html ? (
                        <>
                          <Text strong>HTML 渲染预览（沙箱，无脚本）：</Text>
                          <iframe
                            sandbox=""
                            title={`table-${i}`}
                            srcDoc={t.html}
                            style={{ width: '100%', height: 320, border: '1px solid #eee', borderRadius: 6, background: '#fff' }}
                          />
                          <Divider style={{ margin: '12px 0' }} />
                          <Text strong>Markdown：</Text>
                          <pre style={{ background: '#f8f8f8', padding: 12, borderRadius: 6, overflow: 'auto', fontSize: 13, whiteSpace: 'pre-wrap' }}>
                            {t.markdown || '(无法转换为 Markdown)'}
                          </pre>
                        </>
                      ) : (
                        <Text type="secondary">未生成 HTML（识别失败或空结果）</Text>
                      )}
                    </Panel>
                  ))}
                </Collapse>
              </Card>
            )}
          </Col>
        </Row>
      </Tabs.TabPane>
    </Tabs>
  );
};

const CardInput: React.FC<{
  source: string;
  setSource: (v: string) => void;
  uploadedFileName: string;
  setUploadedFileName: (v: string) => void;
  content: string;
  setContent: (v: string) => void;
  handleFileImport: (f: File) => any;
  handleRecognize: () => void;
  loading: boolean;
}> = ({ source, setSource, uploadedFileName, setUploadedFileName, content, setContent, handleFileImport, handleRecognize, loading }) => (
  <Card title="表格输入" size="small">
    <Space direction="vertical" style={{ width: '100%' }}>
      <Select value={source} onChange={setSource} style={{ width: 200 }}>
        <Select.Option value="text">文本格式 (Tab/空格分隔)</Select.Option>
        <Select.Option value="markdown">Markdown 表格</Select.Option>
        <Select.Option value="csv">CSV 格式</Select.Option>
        <Select.Option value="html">HTML 表格</Select.Option>
      </Select>

      <Dragger
        showUploadList={false}
        beforeUpload={handleFileImport}
        accept=".csv,.xlsx,.xls,.md,.html,.htm,.txt"
        style={{ padding: 8 }}
      >
        <p><UploadOutlined style={{ fontSize: 20 }} /></p>
        <p style={{ fontSize: 12 }}>从文件导入（CSV/Excel/Markdown/HTML/TXT）</p>
      </Dragger>
      {uploadedFileName && (
        <Tag closable onClose={() => { setUploadedFileName(''); }}>
          已导入: {uploadedFileName}
        </Tag>
      )}

      <TextArea
        rows={6}
        value={content}
        onChange={e => setContent(e.target.value)}
        placeholder={`输入表格内容...\n示例:\n姓名\t年龄\t城市\n张三\t25\t北京\n李四\t30\t上海`}
      />

      <Button type="primary" onClick={handleRecognize} loading={loading}>
        识别表格结构
      </Button>
    </Space>
  </Card>
);

export default TableRecognitionPanel;
