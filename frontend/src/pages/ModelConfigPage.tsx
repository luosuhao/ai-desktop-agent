import React, { useState, useEffect } from 'react';
import {
  Card, Form, Input, InputNumber, Button, message, Descriptions, Tag, Spin, Row, Col, Space, Divider, Typography,
} from 'antd';
import {
  CloudServerOutlined, LaptopOutlined, SwapOutlined, CheckCircleOutlined, CloseCircleOutlined, ReloadOutlined,
} from '@ant-design/icons';
import { getProviders, switchProvider, saveProviders, getSystemStatus } from '../api';

const PROVIDER_META: Record<string, { label: string; color: string; icon: any }> = {
  online: { label: '在线 (DeepSeek)', color: '#1677ff', icon: <CloudServerOutlined /> },
  local: { label: '本地 (Ollama)', color: '#52c41a', icon: <LaptopOutlined /> },
};

const ModelConfigPage: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [providers, setProviders] = useState<any>({});
  const [active, setActive] = useState<string>('online');
  const [systemStatus, setSystemStatus] = useState<any>(null);
  const [switching, setSwitching] = useState(false);

  const loadData = async () => {
    setLoading(true);
    try {
      const [pRes, sRes] = await Promise.all([getProviders(), getSystemStatus()]);
      setProviders(pRes.data.providers || {});
      setActive(pRes.data.active || 'online');
      setSystemStatus(sRes.data);
    } catch { message.error('加载配置失败'); }
    setLoading(false);
  };

  useEffect(() => { loadData(); }, []);

  const handleSwitch = async (target: string) => {
    setSwitching(true);
    try {
      const res = await switchProvider(target);
      setActive(res.data.active);
      message.success(`已切换到: ${PROVIDER_META[target]?.label || target}`);
      // Reload to refresh connectivity
      loadData();
    } catch { message.error('切换失败'); }
    setSwitching(false);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await saveProviders({ providers });
      message.success('配置已保存');
      // Re-apply active provider
      await switchProvider(active);
    } catch { message.error('保存失败'); }
    setSaving(false);
  };

  const updateProviderField = (name: string, field: string, value: any) => {
    setProviders((prev: any) => ({
      ...prev,
      [name]: { ...prev[name], [field]: value },
    }));
  };

  if (loading) return <Spin style={{ display: 'block', marginTop: 100 }} />;

  const activeProvider = providers[active];
  const otherKey = active === 'online' ? 'local' : 'online';
  const otherProvider = providers[otherKey];

  return (
    <div>
      {/* Status bar */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Row gutter={16} align="middle">
          <Col flex="auto">
            <Space size="large">
              <span>
                当前使用: <Tag color={PROVIDER_META[active]?.color} style={{ fontSize: 13, padding: '2px 10px' }}>
                  {PROVIDER_META[active]?.icon} {PROVIDER_META[active]?.label}
                </Tag>
              </span>
              {activeProvider?._reachable ? (
                <Tag icon={<CheckCircleOutlined />} color="success">已连接</Tag>
              ) : (
                <Tag icon={<CloseCircleOutlined />} color="error">无法连接</Tag>
              )}
              {activeProvider?.model && <Tag>{activeProvider.model}</Tag>}
            </Space>
          </Col>
          <Col>
            <Button
              icon={<SwapOutlined />}
              onClick={() => handleSwitch(otherKey)}
              loading={switching}
            >
              切换到 {PROVIDER_META[otherKey]?.label}
            </Button>
            <Button icon={<ReloadOutlined />} onClick={loadData} style={{ marginLeft: 8 }}>
              刷新
            </Button>
          </Col>
        </Row>
      </Card>

      <Row gutter={16}>
        {/* Online Provider */}
        <Col span={12}>
          <Card
            title={<><CloudServerOutlined style={{ color: '#1677ff' }} /> DeepSeek 在线</>}
            size="small"
            extra={active === 'online' ? <Tag color="blue">当前</Tag> :
              <Button size="small" onClick={() => handleSwitch('online')} loading={switching}>切换到此</Button>}
          >
            {renderProviderForm('online', providers, updateProviderField)}
          </Card>
        </Col>

        {/* Local Provider */}
        <Col span={12}>
          <Card
            title={<><LaptopOutlined style={{ color: '#52c41a' }} /> 本地 Ollama</>}
            size="small"
            extra={active === 'local' ? <Tag color="green">当前</Tag> :
              <Button size="small" onClick={() => handleSwitch('local')} loading={switching}>切换到此</Button>}
          >
            {renderProviderForm('local', providers, updateProviderField)}
          </Card>
        </Col>
      </Row>

      <Divider />

      <Space style={{ marginBottom: 16 }}>
        <Button type="primary" onClick={handleSave} loading={saving}>保存所有配置</Button>
        <Button onClick={loadData} loading={loading}>刷新状态</Button>
      </Space>

      {/* System status */}
      {systemStatus && (
        <Card title="系统状态" size="small">
          <Descriptions column={4} size="small">
            <Descriptions.Item label="服务状态"><Tag color="green">{systemStatus.status}</Tag></Descriptions.Item>
            <Descriptions.Item label="当前模型">{activeProvider?.model || '-'}</Descriptions.Item>
            <Descriptions.Item label="文档数">{systemStatus.documents_count}</Descriptions.Item>
            <Descriptions.Item label="Skill 数">{systemStatus.skills_count}</Descriptions.Item>
            <Descriptions.Item label="向量库">
              {systemStatus.vector_store_ready ? <Tag color="green">就绪</Tag> : <Tag>空</Tag>}
            </Descriptions.Item>
            <Descriptions.Item label="Wiki 页面">{systemStatus.wiki_pages}</Descriptions.Item>
          </Descriptions>
        </Card>
      )}
    </div>
  );
};

const renderProviderForm = (
  name: string,
  providers: any,
  updateField: (name: string, field: string, value: any) => void,
) => {
  const p = providers[name] || {};
  const isActive = false; // visual only
  return (
    <Form layout="vertical" size="small">
      <Form.Item label="名称">
        <Input value={p.name || name} onChange={e => updateField(name, 'name', e.target.value)} />
      </Form.Item>
      <Form.Item label="API Base URL">
        <Input value={p.api_base || ''} onChange={e => updateField(name, 'api_base', e.target.value)} />
      </Form.Item>
      <Form.Item label="API Key">
        <Input.Password value={p.api_key || ''} onChange={e => updateField(name, 'api_key', e.target.value)} />
      </Form.Item>
      <Form.Item label="Model">
        <Input value={p.model || ''} onChange={e => updateField(name, 'model', e.target.value)} />
      </Form.Item>
      <Form.Item label="Temperature">
        <InputNumber min={0} max={2} step={0.1} style={{ width: '100%' }}
          value={p.temperature} onChange={v => updateField(name, 'temperature', v)} />
      </Form.Item>
      <Form.Item label="Max Tokens">
        <InputNumber min={256} max={393216} step={512} style={{ width: '100%' }}
          value={p.max_tokens} onChange={v => updateField(name, 'max_tokens', v)} />
      </Form.Item>
      <Form.Item label="连接状态">
        {p._reachable ? (
          <Tag icon={<CheckCircleOutlined />} color="success">可连接</Tag>
        ) : (
          <Space>
            <Tag icon={<CloseCircleOutlined />} color="error">不可达</Tag>
            {p._error && <Text type="secondary" style={{ fontSize: 12 }}>{p._error}</Text>}
          </Space>
        )}
      </Form.Item>
    </Form>
  );
};

const { Text } = Typography;

export default ModelConfigPage;