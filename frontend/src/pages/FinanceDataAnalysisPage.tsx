import React, { useState, useEffect } from 'react';
import {
  Card, Upload, Input, Button, Alert, Collapse, Typography, Space, message,
} from 'antd';
import { InboxOutlined, PlayCircleOutlined } from '@ant-design/icons';
import {
  financeDataAnalysis, financeAnalysisStatus, outputFileUrl,
} from '../api';

const { TextArea } = Input;
const { Title, Paragraph, Text } = Typography;
const { Panel } = Collapse;

interface AnalysisResult {
  success: boolean;
  run_id?: string;
  question?: string;
  columns?: string;
  code?: string;
  interpretation?: string;
  figures?: string[];
  exec?: any;
  token_summary?: any;
  error?: string;
}

const FinanceDataAnalysisPage: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [status, setStatus] = useState<any>(null);

  useEffect(() => {
    financeAnalysisStatus().then(res => setStatus(res.data)).catch(() => {});
  }, []);

  const handleAnalyze = async () => {
    if (!file) { message.warning('请先选择 CSV / Excel 数据文件'); return; }
    if (!question.trim()) { message.warning('请填写分析目标'); return; }
    setLoading(true);
    setResult(null);
    try {
      const res = await financeDataAnalysis(file, question.trim());
      setResult(res.data);
      if (!res.data?.success) message.error(res.data?.error || '分析失败');
    } catch (e: any) {
      message.error(e?.response?.data?.error || '分析请求失败');
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  const beforeUpload = (f: File) => {
    const okExt = ['.csv', '.xlsx', '.xls'];
    const ext = f.name.slice(f.name.lastIndexOf('.')).toLowerCase();
    if (!okExt.includes(ext)) {
      message.warning('仅支持 CSV / Excel（.csv/.xlsx/.xls）文件');
      return Upload.LIST_IGNORE;
    }
    if (f.size > 50 * 1024 * 1024) {
      message.warning('文件过大（>50MB）');
      return Upload.LIST_IGNORE;
    }
    setFile(f);
    return false;
  };

  const execLog = result?.exec
    ? (result.exec.success
        ? (result.exec.stdout || '(无输出)')
        : `执行失败：${result.exec.error_type}: ${result.exec.error_msg}\n\n${result.exec.stdout || ''}`)
    : '';

  return (
    <div>
      <Title level={4} style={{ marginTop: 0 }}>金融数据分析</Title>
      <Paragraph type="secondary">
        上传 CSV / Excel 金融数据文件，填写分析目标（如"计算2022和2023年的营业收入增长率、毛利率并绘图"），
        系统将生成并执行 Python 代码完成指标计算、统计分析与可视化。
      </Paragraph>

      {status && !status.available && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message="data_analysis 依赖不可用"
          description={
            <span>
              当前 Python（{status.python}）缺少 data_analysis 依赖。请执行{' '}
              <Text code>pip install -r data_analysis/requirements.txt</Text>，或设置{' '}
              <Text code>DATA_ANALYSIS_PYTHON</Text> 指向装有依赖的 python。
              {status.detail && <div style={{ marginTop: 4 }}>{status.detail}</div>}
            </span>
          }
        />
      )}

      <Card size="small" style={{ marginBottom: 16 }}>
        <Space direction="vertical" style={{ width: '100%' }} size={12}>
          <Upload.Dragger
            accept=".csv,.xlsx,.xls"
            maxCount={1}
            beforeUpload={beforeUpload}
            onRemove={() => setFile(null)}
            fileList={file ? [{ uid: '-1', name: file.name, status: 'done' }] : []}
            showUploadList
          >
            <p className="ant-upload-drag-icon"><InboxOutlined /></p>
            <p className="ant-upload-text">点击或拖拽上传 CSV / Excel 数据文件</p>
            <p className="ant-upload-hint">支持 .csv / .xlsx / .xls</p>
          </Upload.Dragger>
          <TextArea
            rows={3}
            placeholder="分析目标，例如：计算2022和2023年的营业收入增长率、净利润增长率、毛利率并绘图"
            value={question}
            onChange={e => setQuestion(e.target.value)}
          />
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            loading={loading}
            onClick={handleAnalyze}
            block
          >
            {loading ? '分析中（生成代码 + 执行 + 解释，约需 30-90 秒）…' : '开始分析'}
          </Button>
        </Space>
      </Card>

      {loading && (
        <Card size="small" style={{ textAlign: 'center' }}>
          <Paragraph type="secondary" style={{ margin: 0 }}>正在生成并执行分析代码，请稍候…</Paragraph>
        </Card>
      )}

      {result && !loading && (
        <Card
          size="small"
          title="分析结果"
          extra={result.run_id && <Text type="secondary" style={{ fontSize: 12 }}>{result.run_id}</Text>}
        >
          {!result.success && result.error && (
            <Alert type="error" showIcon message={result.error} style={{ marginBottom: 12 }} />
          )}

          {result.columns && (
            <Paragraph style={{ marginBottom: 8 }}>
              <Text strong>数据列：</Text>
              <Text type="secondary">{result.columns}</Text>
            </Paragraph>
          )}

          {result.interpretation && (
            <Paragraph
              style={{ whiteSpace: 'pre-wrap', background: '#fafafa', padding: 12, borderRadius: 6 }}
            >
              {result.interpretation}
            </Paragraph>
          )}

          {result.figures && result.figures.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <Text strong>图表：</Text>
              <div style={{ marginTop: 8 }}>
                {result.figures.map((p, i) => (
                  <img
                    key={p}
                    src={outputFileUrl(p)}
                    alt={`figure_${i}`}
                    style={{
                      maxWidth: '100%', marginBottom: 12, border: '1px solid #f0f0f0',
                      borderRadius: 4, display: 'block',
                    }}
                  />
                ))}
              </div>
            </div>
          )}

          <Collapse size="small">
            {result.code && (
              <Panel header="生成代码" key="code">
                <pre style={{ whiteSpace: 'pre-wrap', margin: 0, maxHeight: 360, overflow: 'auto' }}>
                  {result.code}
                </pre>
              </Panel>
            )}
            {execLog && (
              <Panel header="执行日志" key="exec">
                <pre style={{ whiteSpace: 'pre-wrap', margin: 0, maxHeight: 240, overflow: 'auto' }}>
                  {execLog}
                </pre>
              </Panel>
            )}
          </Collapse>

          {result.token_summary && (
            <Text type="secondary" style={{ fontSize: 12 }}>
              Token 用量：{result.token_summary.n_calls ?? 0} 次调用，
              共 {result.token_summary.total_tokens ?? 0} tokens
            </Text>
          )}
        </Card>
      )}
    </div>
  );
};

export default FinanceDataAnalysisPage;
