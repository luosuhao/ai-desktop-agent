import React, { useState, useEffect } from 'react';
import {
  Layout, Menu, ConfigProvider, theme, Typography,
} from 'antd';
import {
  RobotOutlined, FileSearchOutlined,
  AppstoreOutlined, ExperimentOutlined, SettingOutlined,
  BarChartOutlined, BookOutlined,
} from '@ant-design/icons';
import { getSystemStatus } from './api';
import logo from './assets/logo.png';
import ModelConfigPage from './pages/ModelConfigPage';
import AgentPage from './pages/AgentPage';
import DocumentPage from './pages/DocumentPage';
import SkillPage from './pages/SkillPage';
import EvaluationPage from './pages/EvaluationPage';
import WikiPage from './pages/WikiPage';
import FinanceDataAnalysisPage from './pages/FinanceDataAnalysisPage';

const { Header, Sider, Content } = Layout;
const { Title } = Typography;

const RED_PRIMARY = '#e84435';

const menuItems = [
  { key: 'agent', icon: <RobotOutlined />, label: 'Coding Agent' },
  { key: 'documents', icon: <FileSearchOutlined />, label: '文档管理' },
  { key: 'finance', icon: <BarChartOutlined />, label: '金融数据分析' },
  { key: 'wiki', icon: <BookOutlined />, label: 'LLM Wiki' },
  { key: 'skills', icon: <AppstoreOutlined />, label: 'Skill 管理' },
  { key: 'evaluation', icon: <ExperimentOutlined />, label: '实验评测' },
  { key: 'settings', icon: <SettingOutlined />, label: '模型配置' },
];

const App: React.FC = () => {
  const [currentPage, setCurrentPage] = useState('agent');
  const [collapsed, setCollapsed] = useState(false);
  const [systemStatus, setSystemStatus] = useState<any>(null);
  // Keep-alive: track pages that have been visited so they stay mounted (state preserved)
  const [visitedPages, setVisitedPages] = useState<Set<string>>(new Set(['agent']));

  useEffect(() => {
    getSystemStatus().then(res => setSystemStatus(res.data)).catch(() => {});
  }, []);

  const getPageComponent = (key: string) => {
    switch (key) {
      case 'agent': return <AgentPage />;
      case 'documents': return <DocumentPage />;
      case 'finance': return <FinanceDataAnalysisPage />;
      case 'wiki': return <WikiPage />;
      case 'skills': return <SkillPage />;
      case 'evaluation': return <EvaluationPage />;
      case 'settings': return <ModelConfigPage />;
      default: return <AgentPage />;
    }
  };

  // Render all visited pages, hiding inactive ones (keep state on switch)
  const renderAllPages = () => menuItems.map(({ key }) => {
    if (!visitedPages.has(key)) return null;  // not yet visited - don't mount
    return (
      <div key={key} style={{ display: key === currentPage ? 'block' : 'none' }}>
        {getPageComponent(key)}
      </div>
    );
  });

  const handleMenuClick = (key: string) => {
    setCurrentPage(key);
    setVisitedPages(prev => new Set(prev).add(key));
  };

  return (
    <ConfigProvider
      theme={{
        algorithm: theme.defaultAlgorithm,
        token: {
          colorPrimary: RED_PRIMARY,
          borderRadius: 6,
        },
      }}
    >
      <Layout style={{ minHeight: '100vh', background: '#f5f5f5' }}>
        <Sider
          collapsible
          collapsed={collapsed}
          onCollapse={setCollapsed}
          width={220}
          style={{ background: '#fff', borderRight: '1px solid #f0f0f0' }}
        >
          <div style={{
            height: 64, display: 'flex', alignItems: 'center', justifyContent: 'center',
            borderBottom: `2px solid ${RED_PRIMARY}`, padding: '0 8px', overflow: 'hidden',
          }}>
            <img
              src={logo}
              alt="AI Desktop"
              style={{ height: collapsed ? 24 : 36, maxWidth: '100%', objectFit: 'contain' }}
            />
          </div>
          <Menu
            theme="light"
            mode="inline"
            selectedKeys={[currentPage]}
            items={menuItems}
            onClick={({ key }) => handleMenuClick(key)}
            style={{ borderRight: 0 }}
          />
          {systemStatus && (
            <div style={{
              position: 'absolute', bottom: 0, width: '100%',
              padding: 12, fontSize: 12, color: '#999',
              borderTop: '1px solid #f0f0f0',
              textAlign: 'center', background: '#fff',
            }}>
              {!collapsed && `Models: ${systemStatus.model_configured ? '✓' : '✗'}`}
            </div>
          )}
        </Sider>
        <Layout>
          <Header style={{
            background: '#fff', padding: '0 24px',
            borderBottom: `2px solid ${RED_PRIMARY}`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Title level={4} style={{ margin: 0, color: RED_PRIMARY, textAlign: 'center' }}>
              AI 桌面端系统
            </Title>
          </Header>
          <Content style={{ margin: 16, padding: 24, background: '#fff', borderRadius: 8, minHeight: 360 }}>
            {renderAllPages()}
          </Content>
        </Layout>
      </Layout>
    </ConfigProvider>
  );
};

export default App;
