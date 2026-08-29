import React, { useState, useEffect } from 'react';
import {
  Card, Row, Col, Statistic, Input, List, Tag, Typography, Spin, Empty, Collapse, Space, Button, Modal, message,
} from 'antd';
import { BookOutlined, FileTextOutlined, TableOutlined, ExperimentOutlined, DeleteOutlined, ReloadOutlined } from '@ant-design/icons';
import { getWikiStats, searchWiki, clearWiki } from '../api';

const { Text, Paragraph } = Typography;
const { Search } = Input;
const { Panel } = Collapse;

const WikiPage: React.FC = () => {
  const [stats, setStats] = useState<any>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const loadStats = () => {
    getWikiStats().then(r => setStats(r.data)).catch(() => {});
  };

  useEffect(() => {
    loadStats();
  }, []);

  const handleSearch = async (query: string) => {
    setSearchQuery(query);
    if (!query.trim()) {
      setResults([]);
      return;
    }
    setLoading(true);
    try {
      const res = await searchWiki(query);
      setResults(res.data.results || []);
    } catch (e) { /* ignore */ }
    setLoading(false);
  };

  const handleClear = () => {
    Modal.confirm({
      title: '确认清空知识库？',
      content: '将删除所有 Wiki 页面、向量索引和文档记录，此操作不可恢复。',
      okText: '确认清空',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await clearWiki();
          message.success('知识库已清空');
          setStats({ total_pages: 0, by_type: {}, documents: 0 });
          setResults([]);
        } catch { message.error('清空失败'); }
      },
    });
  };

  const typeIcons: Record<string, React.ReactNode> = {
    document_card: <FileTextOutlined />,
    chapter_summary: <BookOutlined />,
    concept: <ExperimentOutlined />,
    table_desc: <TableOutlined />,
  };

  const typeColors: Record<string, string> = {
    document_card: 'blue',
    chapter_summary: 'green',
    concept: 'purple',
    table_desc: 'orange',
    image_desc: 'cyan',
  };

  return (
    <div>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card size="small">
            <Statistic title="总页面" value={stats?.total_pages || 0} prefix={<BookOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="文档卡片" value={stats?.by_type?.document_card || 0} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="章节摘要" value={stats?.by_type?.chapter_summary || 0} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="概念页面" value={stats?.by_type?.concept || 0} />
          </Card>
        </Col>
      </Row>

      <Card title="LLM Wiki 搜索" size="small"
        extra={
          <Space>
            <Button size="small" icon={<ReloadOutlined />} onClick={loadStats}>刷新</Button>
            {stats?.total_pages > 0 && (
              <Button danger size="small" icon={<DeleteOutlined />} onClick={handleClear}>
                清空知识库
              </Button>
            )}
          </Space>
        }
      >
        <Search
          placeholder="搜索知识库..."
          allowClear
          enterButton
          onSearch={handleSearch}
          style={{ maxWidth: 500, marginBottom: 16 }}
        />

        {loading ? <Spin /> : results.length > 0 ? (
          <List
            dataSource={results}
            renderItem={(item: any) => (
              <List.Item>
                <div style={{ width: '100%' }}>
                  <Space>
                    {typeIcons[item.type] || <FileTextOutlined />}
                    <Text strong>{item.title}</Text>
                    <Tag color={typeColors[item.type] || 'default'}>{item.type}</Tag>
                    <Tag>Score: {item.score}</Tag>
                  </Space>
                  <Paragraph ellipsis={{ rows: 2 }} style={{ marginTop: 4, fontSize: 13 }}>
                    {item.content}
                  </Paragraph>
                  {item.document_id && (
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      文档: {item.document_id}
                    </Text>
                  )}
                </div>
              </List.Item>
            )}
          />
        ) : searchQuery ? (
          <Empty description="无匹配结果" />
        ) : (
          <Empty description="输入关键词搜索知识库" />
        )}
      </Card>
    </div>
  );
};

export default WikiPage;
