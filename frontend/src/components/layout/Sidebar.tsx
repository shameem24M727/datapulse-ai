import { motion, AnimatePresence } from 'framer-motion';
import {
  LayoutDashboard,
  Database,
  ShieldCheck,
  AlertTriangle,
  GitBranch,
  Sparkles,
  FileBarChart2,
  Settings,
  ChevronLeft,
  ChevronRight,
  Zap,
  LogOut,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

interface NavItem {
  id: string;
  label: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
}

const NAV_ITEMS: NavItem[] = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard },
  { id: 'datasets', label: 'Datasets', icon: Database },
  { id: 'quality', label: 'Data Quality', icon: ShieldCheck },
  { id: 'anomalies', label: 'Anomaly Detection', icon: AlertTriangle },
  { id: 'pipelines', label: 'Pipeline Monitor', icon: GitBranch },
  { id: 'copilot', label: 'AI Copilot', icon: Sparkles },
  { id: 'reports', label: 'Reports', icon: FileBarChart2 },
  { id: 'settings', label: 'Settings', icon: Settings },
];

interface SidebarProps {
  currentPage: string;
  onNavigate: (page: string) => void;
  isOpen: boolean;
  onToggle: () => void;
}

export default function Sidebar({ currentPage, onNavigate, isOpen, onToggle }: SidebarProps) {
  const { user, logout } = useAuth();
  const initials = user?.full_name
    ? user.full_name
        .split(' ')
        .map((p) => p[0])
        .join('')
        .toUpperCase()
        .slice(0, 2)
    : (user?.email?.slice(0, 2).toUpperCase() || 'DP');
  const sidebarVariants = {
    open: { width: 240 },
    closed: { width: 68 },
  };

  return (
    <>
      {/* Mobile overlay */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            className="fixed inset-0 z-20 bg-black/60 backdrop-blur-sm md:hidden"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onToggle}
          />
        )}
      </AnimatePresence>

      <motion.aside
        className="relative z-30 flex flex-col h-screen bg-white dark:bg-zinc-900 border-r border-zinc-200 dark:border-zinc-800 flex-shrink-0 overflow-hidden transition-colors"
        variants={sidebarVariants}
        animate={isOpen ? 'open' : 'closed'}
        transition={{ type: 'spring', stiffness: 300, damping: 30 }}
      >
        {/* Logo / Wordmark */}
        <div className="flex items-center gap-3 px-4 py-5 border-b border-zinc-200 dark:border-zinc-800 min-h-[64px]">
          <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center shadow-md shadow-indigo-600/30">
            <Zap size={16} className="text-white" />
          </div>
          <AnimatePresence>
            {isOpen && (
              <motion.div
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -10 }}
                transition={{ duration: 0.15 }}
                className="overflow-hidden whitespace-nowrap"
              >
                <span className="text-zinc-900 dark:text-white font-bold text-base tracking-tight">DataPulse</span>
                <span className="text-indigo-600 dark:text-indigo-400 font-bold text-base tracking-tight"> AI</span>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-4 overflow-y-auto overflow-x-hidden">
          <ul className="space-y-1 px-2.5">
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon;
              const isActive = currentPage === item.id;
              return (
                <li key={item.id}>
                  <button
                    onClick={() => onNavigate(item.id)}
                    className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 group relative ${
                      isActive
                        ? 'bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 font-semibold'
                        : 'text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800'
                    }`}
                    title={!isOpen ? item.label : undefined}
                  >
                    <Icon
                      size={18}
                      className={`flex-shrink-0 transition-colors ${
                        isActive
                          ? 'text-indigo-600 dark:text-indigo-400'
                          : 'text-zinc-500 dark:text-zinc-400 group-hover:text-zinc-800 dark:group-hover:text-zinc-200'
                      }`}
                    />
                    <AnimatePresence>
                      {isOpen && (
                        <motion.span
                          initial={{ opacity: 0, x: -8 }}
                          animate={{ opacity: 1, x: 0 }}
                          exit={{ opacity: 0, x: -8 }}
                          transition={{ duration: 0.12 }}
                          className="whitespace-nowrap overflow-hidden"
                        >
                          {item.label}
                        </motion.span>
                      )}
                    </AnimatePresence>
                    {/* Tooltip for collapsed mode */}
                    {!isOpen && (
                      <div className="absolute left-full ml-2 px-2.5 py-1 bg-zinc-900 text-zinc-100 text-xs rounded-md whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50 shadow-lg">
                        {item.label}
                      </div>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>

        {/* User section */}
        <div className="border-t border-zinc-200 dark:border-zinc-800 p-3 overflow-hidden">
          <div className="flex items-center gap-3">
            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white text-xs font-bold shadow">
              {initials}
            </div>
            <AnimatePresence>
              {isOpen && (
                <motion.div
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -8 }}
                  transition={{ duration: 0.12 }}
                  className="flex-1 min-w-0 overflow-hidden flex items-center justify-between"
                >
                  <div className="min-w-0">
                    <p className="text-zinc-900 dark:text-zinc-100 text-xs font-medium truncate">
                      {user?.full_name || user?.email || 'User'}
                    </p>
                    <p className="text-zinc-500 text-[10px] truncate capitalize">
                      {user?.role?.replace('_', ' ') || 'Member'}
                    </p>
                  </div>
                  <button
                    onClick={logout}
                    title="Sign Out"
                    className="text-zinc-400 hover:text-rose-500 p-1 rounded transition-colors cursor-pointer"
                  >
                    <LogOut size={14} />
                  </button>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

        {/* Collapse/expand button */}
        <button
          onClick={onToggle}
          className="flex items-center justify-center h-10 border-t border-zinc-200 dark:border-zinc-800 text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
          title={isOpen ? 'Collapse sidebar' : 'Expand sidebar'}
        >
          {isOpen ? <ChevronLeft size={16} /> : <ChevronRight size={16} />}
        </button>
      </motion.aside>
    </>
  );
}
