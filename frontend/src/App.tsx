import { useState, useEffect, useRef, useCallback } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import LoginPage from './pages/LoginPage';
import ConfigSetupPage from './pages/ConfigSetupPage';
import { IviPage } from './pages/IviPage';
import { SurgeryPage } from './pages/SurgeryPage';
import { DashboardBedPage } from './pages/DashboardBedPage';
import { StatsOpPage } from './pages/StatsOpPage';
import { StatsFeePage } from './pages/StatsFeePage';
import SheetsSettingsPage from './pages/SheetsSettingsPage';
import TemplatesSettingsPage from './pages/TemplatesSettingsPage';
import BugReportPage from './pages/BugReportPage';
import PricingPage from './pages/PricingPage';
import { TaskStatsPage } from './pages/TaskStatsPage';
import { PlaceholderPage } from './pages/PlaceholderPage';
import { Sidebar, type ToolId } from './components/Sidebar';
import { BackgroundTasksIndicator } from './components/BackgroundTasksIndicator';
import { useIdleTimer } from './hooks/useIdleTimer';
import { IdleWarningModal } from './components/IdleWarningModal';

// Loading Screen Component
function LoadingScreen() {
  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: '#F5F5F7',
    }}>
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: '16px',
      }}>
        <div style={{
          width: '40px',
          height: '40px',
          border: '3px solid #e5e7eb',
          borderTopColor: '#3b82f6',
          borderRadius: '50%',
          animation: 'spin 1s linear infinite',
        }} />
        <p style={{ color: '#6b7280', fontSize: '0.875rem' }}>載入中...</p>
        <style>{`
          @keyframes spin {
            to { transform: rotate(360deg); }
          }
        `}</style>
      </div>
    </div>
  );
}

function ProtectedApp() {
  const { isAuthenticated, logout } = useAuth();
  const [activeTool, setActiveTool] = useState<ToolId>('ivi');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [autoCollapsed, setAutoCollapsed] = useState(false);
  const mainRef = useRef<HTMLDivElement>(null);

  // =========================================================================
  // 閒置自動登出
  // =========================================================================
  const [showIdleWarning, setShowIdleWarning] = useState(false);

  const { resetTimer } = useIdleTimer({
    onIdle: () => setShowIdleWarning(true),
    enabled: isAuthenticated, // 只在已登入時啟用
    // idleTimeoutMs 使用 hook 預設值 (1.5 分鐘)
  });

  const handleIdleContinue = useCallback(() => {
    setShowIdleWarning(false);
    resetTimer();
  }, [resetTimer]);

  const handleIdleLogout = useCallback(() => {
    setShowIdleWarning(false);
    logout();
  }, [logout]);

  // 監測內容區域是否需要水平滾動，自動收合 sidebar
  const checkContentOverflow = useCallback(() => {
    if (!mainRef.current) return;

    const main = mainRef.current;
    // 檢查內容是否超出可視區域
    const hasHorizontalScroll = main.scrollWidth > main.clientWidth;

    // 只在 surgery 頁面自動收合
    if (activeTool === 'surgery' && hasHorizontalScroll && !sidebarCollapsed) {
      setSidebarCollapsed(true);
      setAutoCollapsed(true);
    }
  }, [activeTool, sidebarCollapsed]);

  // 當切換到 surgery 頁面時，檢查是否需要收合
  useEffect(() => {
    // 在 surgery 頁面且之前自動收合過，保持收合狀態
    // 其他頁面恢復展開
    if (activeTool !== 'surgery' && autoCollapsed) {
      setSidebarCollapsed(false);
      setAutoCollapsed(false);
    }
  }, [activeTool, autoCollapsed]);

  // 監聽視窗大小變化
  useEffect(() => {
    const handleResize = () => {
      // 使用 setTimeout 確保 DOM 已更新
      setTimeout(checkContentOverflow, 100);
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [checkContentOverflow]);

  // 在頁面切換後檢查溢出
  useEffect(() => {
    // 延遲檢查，確保內容已渲染
    const timer = setTimeout(checkContentOverflow, 200);
    return () => clearTimeout(timer);
  }, [activeTool, checkContentOverflow]);

  // 手動切換時重置自動收合狀態
  const handleToggleSidebar = () => {
    setSidebarCollapsed(prev => !prev);
    setAutoCollapsed(false);
  };

  if (!isAuthenticated) {
    return <LoginPage />;
  }

  const renderContent = () => {
    switch (activeTool) {
      case 'ivi':
        return <IviPage />;
      case 'surgery':
        return <SurgeryPage onNavigate={(path) => setActiveTool(path as ToolId)} />;
      case 'bed':
        return <DashboardBedPage />;
      case 'stats_op':
        return <StatsOpPage />;
      case 'stats_fee':
        return <StatsFeePage />;
      case 'sheets_settings':
        return <SheetsSettingsPage />;
      case 'templates_settings':
        return <TemplatesSettingsPage />;
      case 'opd_order':
        return <PlaceholderPage title="門診系統開單" description="門診系統開單功能建置中" />;
      case 'nhi_review':
        return <PlaceholderPage title="健保事審" description="健保事審功能建置中" />;
      case 'opd_set':
        return <PlaceholderPage title="門診系統組套" description="門診系統組套設定建置中" />;
      case 'bug_report':
        return <BugReportPage />;
      case 'pricing':
        return <PricingPage onNavigate={(path) => setActiveTool(path as ToolId)} />;
      case 'task_stats':
        return <TaskStatsPage />;
      default:
        return <IviPage />;
    }
  };

  return (
    <div style={{
      display: 'flex',
      minHeight: '100vh',
      backgroundColor: '#f5f7fa',
      fontFamily: '"Manrope", "Noto Sans", sans-serif',
    }}>
      <Sidebar
        activeTool={activeTool}
        onToolSelect={setActiveTool}
        collapsed={sidebarCollapsed}
        onToggleCollapse={handleToggleSidebar}
      />
      <main
        ref={mainRef}
        style={{
          flex: 1,
          overflow: 'auto',
          backgroundColor: '#f5f7fa',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* 主要內容 */}
        <div style={{ flex: 1 }}>
          {renderContent()}
        </div>

        {/* Background Tasks Indicator */}
        <div style={{ position: 'fixed', top: '24px', right: '24px', zIndex: 100 }}>
          <BackgroundTasksIndicator />
        </div>
      </main>

      {/* 閒置警告 Modal */}
      {showIdleWarning && (
        <IdleWarningModal
          onContinue={handleIdleContinue}
          onLogout={handleIdleLogout}
        />
      )}
    </div>
  );
}

function App() {
  // Config check state
  const [configStatus, setConfigStatus] = useState<{
    checked: boolean;
    exists: boolean;
    path: string;
  }>({ checked: false, exists: false, path: '' });

  // Check config on mount
  useEffect(() => {
    const checkConfig = async () => {
      try {
        const res = await fetch('/api/config/status');
        const data = await res.json();
        setConfigStatus({
          checked: true,
          exists: data.exists,
          path: data.path,
        });
      } catch {
        // If we can't reach the backend, assume config exists and let login handle errors
        setConfigStatus({ checked: true, exists: true, path: '' });
      }
    };

    checkConfig();
  }, []);

  // Loading state
  if (!configStatus.checked) {
    return <LoadingScreen />;
  }

  // Config setup required
  if (!configStatus.exists) {
    return (
      <ConfigSetupPage
        configPath={configStatus.path}
        onComplete={() => {
          // Reload the page to reinitialize with new config
          window.location.reload();
        }}
      />
    );
  }

  // Normal app flow
  return (
    <AuthProvider>
      <ProtectedApp />
    </AuthProvider>
  );
}

export default App;
