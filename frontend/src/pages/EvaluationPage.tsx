import React, { useState, useEffect } from 'react';
import {
  Card, Row, Col, Statistic, Table, Tag, Typography, Spin, Collapse,
  Tabs, Descriptions, Divider, Progress, Space, Button,
} from 'antd';
import {
  ExperimentOutlined, CheckCircleOutlined, CloseCircleOutlined,
  RobotOutlined, FileSearchOutlined, AppstoreOutlined, ReloadOutlined,
} from '@ant-design/icons';
import {
  getAllEval, getCodingEval, getRagEval, getSkillsEval,
} from '../api';

const { Text, Title, Paragraph } = Typography;
const { Panel } = Collapse;

const EvaluationPage: React.FC = () => {
  const [allEval, setAllEval] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadAll();
  }, []);

  const loadAll = async () => {
    setLoading(true);
    try {
      const res = await getAllEval();
      setAllEval(res.data);
    } catch (e) { /* ignore */ }
    setLoading(false);
  };

  if (loading) return <Spin />;

  const coding = allEval?.coding || {};
  const rag = allEval?.rag || {};
  const skills = allEval?.skills || {};

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Title level={4} style={{ margin: 0 }}>实验评测面板</Title>
        <Button icon={<ReloadOutlined />} onClick={loadAll}>刷新</Button>
      </div>

      {/* Summary Cards */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={8}>
          <Card size="small">
            <Statistic
              title="Coding Agent - 缓存命中率"
              value={coding.cache_hit_rate || 0}
              suffix="%"
              prefix={<RobotOutlined />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small">
            <Statistic
              title="RAG - 文档/块/页面"
              value={`${rag.documents || 0} / ${rag.chunks || 0} / ${rag.wiki_pages || 0}`}
              prefix={<FileSearchOutlined />}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small">
            <Statistic
              title="Skills - 成功率"
              value={skills.success_rate || 0}
              suffix="%"
              prefix={<AppstoreOutlined />}
              valueStyle={{ color: skills.success_rate >= 50 ? '#52c41a' : '#faad14' }}
            />
          </Card>
        </Col>
      </Row>

      <Tabs defaultActiveKey="coding" items={[
        {
          key: 'coding',
          label: <span><RobotOutlined /> Coding Agent</span>,
          children: (
            <Row gutter={16}>
              <Col span={12}>
                <Card title="Cache Metrics" size="small">
                  <Descriptions column={2} size="small">
                    <Descriptions.Item label="总请求数">{coding.total_requests || 0}</Descriptions.Item>
                    <Descriptions.Item label="缓存命中率">{coding.cache_hit_rate || 0}%</Descriptions.Item>
                    <Descriptions.Item label="平均延迟">{coding.avg_latency_ms || 0}ms</Descriptions.Item>
                    <Descriptions.Item label="节省Token">{(coding.input_tokens_saved || 0).toLocaleString()}</Descriptions.Item>
                  </Descriptions>
                </Card>
              </Col>
              <Col span={12}>
                <Card title="性能指标" size="small">
                  <Progress type="circle" percent={coding.cache_hit_rate || 0}
                    strokeColor="#52c41a" size={100}
                    format={pct => `${pct}%`} />
                  <div style={{ marginTop: 8 }}>
                    <Text>延迟: {coding.avg_latency_ms || 0}ms | </Text>
                    <Text>Token节省: {(coding.input_tokens_saved || 0).toLocaleString()}</Text>
                  </div>
                </Card>
              </Col>
            </Row>
          )
        },
        {
          key: 'rag',
          label: <span><FileSearchOutlined /> RAG 文档系统</span>,
          children: (
            <Row gutter={16}>
              <Col span={12}>
                <Card title="文档统计" size="small">
                  <Descriptions column={2} size="small">
                    <Descriptions.Item label="文档数">{rag.documents || 0}</Descriptions.Item>
                    <Descriptions.Item label="文档块">{rag.chunks || 0}</Descriptions.Item>
                    <Descriptions.Item label="Wiki页面">{rag.wiki_pages || 0}</Descriptions.Item>
                    <Descriptions.Item label="向量索引">
                      <Tag color={rag.index_ready ? 'green' : 'default'}>
                        {rag.index_ready ? '已就绪' : '未就绪'}
                      </Tag>
                    </Descriptions.Item>
                  </Descriptions>
                </Card>
              </Col>
              <Col span={12}>
                <Card title="RAG 评估项" size="small">
                  <div style={{ marginBottom: 8 }}>
                    <CheckCircleOutlined style={{ color: '#52c41a' }} /> PDF解析
                    <Tag style={{ marginLeft: 8 }}>支持</Tag>
                  </div>
                  <div style={{ marginBottom: 8 }}>
                    <CheckCircleOutlined style={{ color: '#52c41a' }} /> 表格识别
                    <Tag style={{ marginLeft: 8 }}>支持</Tag>
                  </div>
                  <div style={{ marginBottom: 8 }}>
                    <CheckCircleOutlined style={{ color: '#52c41a' }} /> 混合检索
                    <Tag style={{ marginLeft: 8 }}>Vector + BM25</Tag>
                  </div>
                  <div style={{ marginBottom: 8 }}>
                    <CheckCircleOutlined style={{ color: '#52c41a' }} /> 证据溯源
                    <Tag style={{ marginLeft: 8 }}>支持</Tag>
                  </div>
                  <div>
                    <CheckCircleOutlined style={{ color: '#52c41a' }} /> LLM Wiki
                    <Tag style={{ marginLeft: 8 }}>支持</Tag>
                  </div>
                </Card>
              </Col>
            </Row>
          )
        },
        {
          key: 'skills',
          label: <span><AppstoreOutlined /> Skill 系统</span>,
          children: (
            <Row gutter={16}>
              <Col span={12}>
                <Card title="Skill 统计" size="small">
                  <Descriptions column={2} size="small">
                    <Descriptions.Item label="总Skills">{skills.total || 0}</Descriptions.Item>
                    <Descriptions.Item label="执行次数">{skills.executions || 0}</Descriptions.Item>
                    <Descriptions.Item label="成功率">{skills.success_rate || 0}%</Descriptions.Item>
                  </Descriptions>
                  <Divider />
                  <Text strong>内置 Skills:</Text>
                  <ul>
                    <li>LaTeX 论文/报告生成</li>
                    <li>Word 实验报告生成</li>
                    <li>PPT 汇报生成</li>
                    <li>数据分析</li>
                  </ul>
                </Card>
              </Col>
              <Col span={12}>
                <Card title="Skill 评估项" size="small">
                  <div style={{ marginBottom: 8 }}>
                    <CheckCircleOutlined style={{ color: '#52c41a' }} /> Trigger匹配
                    <Tag style={{ marginLeft: 8 }}>按需加载</Tag>
                  </div>
                  <div style={{ marginBottom: 8 }}>
                    <CheckCircleOutlined style={{ color: '#52c41a' }} /> 文件生成
                    <Tag style={{ marginLeft: 8 }}>.tex/.docx/.pptx</Tag>
                  </div>
                  <div style={{ marginBottom: 8 }}>
                    <CheckCircleOutlined style={{ color: '#52c41a' }} /> 自动验证
                    <Tag style={{ marginLeft: 8 }}>有</Tag>
                  </div>
                  <div style={{ marginBottom: 8 }}>
                    <CheckCircleOutlined style={{ color: '#52c41a' }} /> Java代码生成
                    <Tag style={{ marginLeft: 8 }}>有</Tag>
                  </div>
                  <div style={{ marginBottom: 8 }}>
                    <CloseCircleOutlined style={{ color: '#ff4d4f' }} /> LaTeX编译
                    <Tag style={{ marginLeft: 8 }}>需本地安装</Tag>
                  </div>
                </Card>
              </Col>
            </Row>
          )
        },
      ]} />
    </div>
  );
};

export default EvaluationPage;
