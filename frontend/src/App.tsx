import { useState } from 'react';
import { ThemeProvider } from './context/ThemeContext';
import { AuthProvider, useAuth } from './context/AuthContext';
import Sidebar from './components/layout/Sidebar';
import TopBar from './components/layout/TopBar';
import OverviewPage from './pages/OverviewPage';
import DatasetsPage from './pages/DatasetsPage';
import DataQualityPage from './pages/DataQualityPage';
import AnomalyPage from './pages/AnomalyPage';
import PipelinesPage from './pages/PipelinesPage';
import CopilotPage from './pages/CopilotPage';
import ReportsPage from './pages/ReportsPage';
import SettingsPage from './pages/SettingsPage';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import ErrorBoundary from './components/ui/ErrorBoundary';
import { mockAlerts } from './data/mockData';
import { Activity } from 'lucide-react';

const PAGE_TITLES: Record<string, string> = {
  overview: 'Overview',
  datasets: 'Datasets',
  quality: 'Data Quality',
  anomalies: 'Anomaly Detection',
  pipelines: 'Pipeline Monitor',
  copilot: 'AI Data Copilot',
  reports: 'Reports',
  settings: 'Settings',
};

function AppContent() {
  const { isAuthenticated, isLoading } = useAuth();
  const [authView, setAuthView] = useState<'login' | 'register'>('login');
  const [currentPage, setCurrentPage] = useState('overview');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const unreadAlerts = mockAlerts.filter(a => !a.read).length;

  if (isLoading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-zinc-950 text-zinc-100">
        <div className="w-10 h-10 rounded-xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center mb-3 animate-pulse">
          <Activity className="w-5 h-5 text-indigo-400" />
        </div>
        <p className="text-xs text-zinc-400">Loading DataPulse workspace...</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return authView === 'login' ? (
      <LoginPage onSwitchToRegister={() => setAuthView('register')} />
    ) : (
      <RegisterPage onSwitchToLogin={() => setAuthView('login')} />
    );
  }

  const renderPage = () => {
    switch (currentPage) {
      case 'overview': return <OverviewPage />;
      case 'datasets': return <DatasetsPage />;
      case 'quality': return <DataQualityPage />;
      case 'anomalies': return <AnomalyPage />;
      case 'pipelines': return <PipelinesPage />;
      case 'copilot': return <CopilotPage />;
      case 'reports': return <ReportsPage />;
      case 'settings': return <SettingsPage />;
      default: return <OverviewPage />;
    }
  };

  return (
    <div className="flex h-screen bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100 overflow-hidden">
      <Sidebar
        currentPage={currentPage}
        onNavigate={setCurrentPage}
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(prev => !prev)}
      />
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <TopBar
          title={PAGE_TITLES[currentPage]}
          onMenuToggle={() => setSidebarOpen(prev => !prev)}
          alertCount={unreadAlerts}
        />
        <main className="flex-1 overflow-y-auto">
          <ErrorBoundary key={currentPage} fallbackTitle={`Unable to load ${PAGE_TITLES[currentPage] || 'view'}`}>
            {renderPage()}
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </ThemeProvider>
  );
}
