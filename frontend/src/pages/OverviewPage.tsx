import { useEffect, useState } from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { motion } from 'framer-motion';
import {
  AlertTriangle,
  GitBranch,
  Upload,
  ScanLine,
  Bell,
  TrendingUp,
  Activity,
} from 'lucide-react';
import {
  qualityTrendData,
  mockAlerts,
  mockActivities,
} from '../data/mockData';
import type { Alert, Activity as ActivityType, BackendOverviewSummary } from '../types';
import { fetchOverviewSummary } from '../services/api';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function cn(...classes: (string | false | null | undefined)[]) {
  return classes.filter(Boolean).join(' ');
}

interface StatCardProps {
  title: string;
  value: string;
  subtitle: string;
  valueClass: string;
  trend?: string;
  index: number;
}

function StatCard({ title, value, subtitle, valueClass, trend, index }: StatCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.1, duration: 0.4, ease: 'easeOut' }}
      className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-5 flex flex-col gap-3"
    >
      <span className="text-xs font-medium uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
        {title}
      </span>
      <div className="flex items-end justify-between">
        <span className={cn('text-3xl font-bold', valueClass)}>{value}</span>
        {trend && (
          <span className="flex items-center gap-1 text-xs text-emerald-400 font-medium">
            <TrendingUp className="w-3 h-3" />
            {trend}
          </span>
        )}
      </div>
      <span className="text-sm text-zinc-500 dark:text-zinc-400">{subtitle}</span>
    </motion.div>
  );
}

function SeverityBadge({ severity }: { severity: Alert['severity'] }) {
  const map: Record<Alert['severity'], string> = {
    info: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
    warning: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    error: 'bg-red-500/10 text-red-400 border-red-500/20',
    critical: 'bg-red-500/10 text-red-400 border-red-500/20',
  };
  return (
    <span
      className={cn(
        'inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border capitalize',
        map[severity],
      )}
    >
      {severity}
    </span>
  );
}

function ActivityIcon({ type }: { type: ActivityType['type'] }) {
  const map: Record<ActivityType['type'], React.ReactNode> = {
    upload: <Upload className="w-4 h-4 text-indigo-400" />,
    scan: <ScanLine className="w-4 h-4 text-emerald-400" />,
    alert: <AlertTriangle className="w-4 h-4 text-amber-400" />,
    pipeline: <GitBranch className="w-4 h-4 text-blue-400" />,
    report: <Bell className="w-4 h-4 text-purple-400" />,
  };
  return (
    <div className="w-8 h-8 rounded-lg bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center flex-shrink-0">
      {map[type] ?? <Activity className="w-4 h-4 text-zinc-400" />}
    </div>
  );
}

// ─── Main Page ─────────────────────────────────────────────────────────────────

export default function OverviewPage() {
  const [hour, setHour] = useState(() => new Date().getHours());
  const [backendSummary, setBackendSummary] = useState<BackendOverviewSummary | null>(null);

  useEffect(() => {
    const id = setInterval(() => setHour(new Date().getHours()), 60_000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    fetchOverviewSummary()
      .then((data) => setBackendSummary(data))
      .catch(() => {});
  }, []);

  const greeting =
    hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';

  const totalDatasetsMonitored = backendSummary
    ? backendSummary.total_datasets
    : 8;

  const activeAnomaliesCount = backendSummary
    ? backendSummary.total_anomalies
    : 3;

  const statCards: StatCardProps[] = [
    {
      title: 'Overall Health Score',
      value: backendSummary && backendSummary.total_datasets > 0
        ? `${Math.round(backendSummary.average_quality_score)}/100`
        : '88/100',
      subtitle: backendSummary && backendSummary.total_datasets > 0
        ? 'Real-time database aggregated'
        : 'Excellent — up from last week',
      valueClass: 'text-emerald-500',
      trend: '+3 from last week',
      index: 0,
    },
    {
      title: 'Datasets Monitored',
      value: `${totalDatasetsMonitored}`,
      subtitle: backendSummary && backendSummary.total_datasets > 0
        ? `${backendSummary.total_datasets} ingested live in DB`
        : '2 require attention',
      valueClass: 'text-indigo-500',
      index: 1,
    },
    {
      title: 'Active Anomalies',
      value: `${activeAnomaliesCount}`,
      subtitle: backendSummary && backendSummary.critical_anomalies > 0
        ? `${backendSummary.critical_anomalies} critical detected`
        : '1 critical',
      valueClass: 'text-amber-500',
      index: 2,
    },
    {
      title: 'Pipeline Health',
      value: '80%',
      subtitle: '1 failed, 1 paused',
      valueClass: 'text-blue-500',
      index: 3,
    },
  ];

  const recentAlerts = mockAlerts.slice(0, 3);
  const combinedActivities = backendSummary?.recent_activities?.length
    ? [...backendSummary.recent_activities, ...mockActivities].slice(0, 5)
    : mockActivities.slice(0, 4);

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 p-6 space-y-6">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
      >
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
          {greeting}, Alex 👋
        </h1>
        <p className="text-zinc-500 dark:text-zinc-400 mt-1">
          Here's your data health summary for today.
        </p>
      </motion.div>

      {/* Stat Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((card) => (
          <StatCard key={card.title} {...card} />
        ))}
      </div>

      {/* Main Grid: Quality Chart (2/3) + Activity (1/3) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Quality Trend Chart */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2, duration: 0.4 }}
          className="lg:col-span-2 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-5 flex flex-col gap-4"
        >
          <div>
            <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
              Quality Score Trend
            </h2>
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
              Historical 30-day health performance across all data contracts
            </p>
          </div>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart
                data={qualityTrendData}
                margin={{ top: 8, right: 8, left: -20, bottom: 0 }}
              >
                <defs>
                  <linearGradient id="scoreGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#6366f1" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="#3f3f46"
                  opacity={0.3}
                />
                <XAxis
                  dataKey="date"
                  tick={{ fill: '#71717a', fontSize: 11 }}
                  axisLine={{ stroke: '#3f3f46', opacity: 0.4 }}
                  tickLine={false}
                />
                <YAxis
                  domain={[60, 100]}
                  tick={{ fill: '#71717a', fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={(v) => `${v}`}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#18181b',
                    borderColor: '#27272a',
                    borderRadius: '8px',
                    fontSize: '12px',
                    color: '#f4f4f5',
                  }}
                  formatter={(val: any) => [`${val}/100`, 'Quality Score']}
                />
                <Area
                  type="monotone"
                  dataKey="score"
                  stroke="#6366f1"
                  strokeWidth={2}
                  fill="url(#scoreGrad)"
                  dot={{ r: 3, fill: '#6366f1' }}
                  activeDot={{ r: 5, fill: '#818cf8' }}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </motion.div>

        {/* Recent Activity */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3, duration: 0.4 }}
          className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-5 flex flex-col gap-4"
        >
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
              Recent Activity
            </h2>
            <span className="text-xs text-zinc-500 dark:text-zinc-400">
              Live audit
            </span>
          </div>

          <div className="space-y-3 divide-y divide-zinc-100 dark:divide-zinc-800/80">
            {combinedActivities.map((act) => (
              <div key={act.id} className="pt-3 first:pt-0 flex items-start gap-3">
                <ActivityIcon type={act.type} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-zinc-800 dark:text-zinc-200 truncate">
                    {act.title}
                  </p>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5 truncate">
                    {act.description}
                  </p>
                  <span className="text-[11px] text-zinc-400 dark:text-zinc-500 mt-1 block">
                    {act.timestamp}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </motion.div>
      </div>

      {/* Recent Alerts */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.35, duration: 0.4 }}
        className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-5 space-y-4"
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
              Active Alerts & Diagnostics
            </h2>
            <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
          </div>
          <span className="text-xs text-zinc-500 dark:text-zinc-400">
            Automated notifications
          </span>
        </div>

        <div className="space-y-2">
          {recentAlerts.map((alert) => (
            <div
              key={alert.id}
              className="flex items-center justify-between p-3 rounded-lg bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200/80 dark:border-zinc-800 gap-3"
            >
              <div className="flex items-center gap-3 min-w-0">
                <SeverityBadge severity={alert.severity} />
                <div className="min-w-0">
                  <p className="text-sm font-medium text-zinc-800 dark:text-zinc-200 truncate">
                    {alert.title}
                  </p>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5 truncate">
                    {alert.description}
                  </p>
                </div>
              </div>
              <span className="text-xs text-zinc-400 dark:text-zinc-500 whitespace-nowrap flex-shrink-0">
                {alert.timestamp}
              </span>
            </div>
          ))}
        </div>
      </motion.div>
    </div>
  );
}
