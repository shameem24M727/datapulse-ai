import { useState } from 'react';
import { motion } from 'framer-motion';
import {
  User,
  Sun,
  Moon,
  Bell,
  Database,
  Key,
  Check,
  Copy,
} from 'lucide-react';
import { useTheme } from '../context/ThemeContext';
import { useAuth } from '../context/AuthContext';

export default function SettingsPage() {
  const { theme, toggleTheme } = useTheme();
  const { user, activeOrg } = useAuth();
  const [activeTab, setActiveTab] = useState<'profile' | 'appearance' | 'notifications' | 'integrations'>('profile');

  const initials = user?.full_name
    ? user.full_name
        .split(' ')
        .map((p) => p[0])
        .join('')
        .toUpperCase()
        .slice(0, 2)
    : (user?.email?.slice(0, 2).toUpperCase() || 'DP');

  // Local state for notification toggles
  const [notifications, setNotifications] = useState({
    criticalAnomalies: true,
    schemaDrift: true,
    pipelineFailures: true,
    weeklyDigest: false,
    slaBreach: true,
  });

  const [copiedKey, setCopiedKey] = useState(false);

  const copyApiKey = () => {
    navigator.clipboard?.writeText('dp_live_9f81a7b2901c43d8984920');
    setCopiedKey(true);
    setTimeout(() => setCopiedKey(false), 2000);
  };

  const integrations = [
    {
      name: 'PostgreSQL Primary',
      type: 'Relational Database',
      endpoint: 'prod-db-01.internal:5432/analytics',
      status: 'connected',
      lastSync: '2 min ago',
    },
    {
      name: 'Apache Kafka',
      type: 'Event Streaming Broker',
      endpoint: 'kafka-prod.corp:9092 [3 clusters]',
      status: 'connected',
      lastSync: 'Continuous',
    },
    {
      name: 'Google BigQuery',
      type: 'Cloud Data Warehouse',
      endpoint: 'gcp-project: datapulse-prod-dw',
      status: 'connected',
      lastSync: '14 min ago',
    },
    {
      name: 'Snowflake Analytics',
      type: 'Cloud Warehouse',
      endpoint: 'acme.snowflakecomputing.com',
      status: 'connected',
      lastSync: '1 hour ago',
    },
    {
      name: 'Salesforce CRM',
      type: 'SaaS Application API',
      endpoint: 'api.salesforce.com/v58.0',
      status: 'connected',
      lastSync: '3 hours ago',
    },
    {
      name: 'Databricks Lakehouse',
      type: 'Unified Analytics Engine',
      endpoint: 'dbc-workspace-east.cloud.databricks.com',
      status: 'disconnected',
      lastSync: 'Not configured',
    },
  ];

  return (
    <div className="p-4 md:p-8 max-w-5xl mx-auto space-y-8">
      {/* Header */}
      <div className="border-b border-zinc-200 dark:border-zinc-800/80 pb-6">
        <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
          Platform Settings
        </h1>
        <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
          Manage workspace preferences, display themes, alerting rules, and data sources.
        </p>
      </div>

      {/* Tabs navigation */}
      <div className="flex border-b border-zinc-200 dark:border-zinc-800 space-x-6 text-sm font-medium">
        {[
          { id: 'profile', label: 'Account Profile', icon: User },
          { id: 'appearance', label: 'Appearance & Theme', icon: Sun },
          { id: 'notifications', label: 'Alerting Preferences', icon: Bell },
          { id: 'integrations', label: 'Data Sources & Connectors', icon: Database },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`flex items-center gap-2 pb-3 relative transition-colors ${
                isActive
                  ? 'text-indigo-600 dark:text-indigo-400 font-semibold'
                  : 'text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200'
              }`}
            >
              <Icon size={16} />
              {tab.label}
              {isActive && (
                <motion.div
                  layoutId="activeSettingsTab"
                  className="absolute bottom-0 left-0 right-0 h-0.5 bg-indigo-600 dark:bg-indigo-400"
                />
              )}
            </button>
          );
        })}
      </div>

      {/* TAB CONTENT: PROFILE */}
      {activeTab === 'profile' && (
        <div className="space-y-6">
          <div className="p-6 rounded-xl border border-zinc-200 dark:border-zinc-800/80 bg-white dark:bg-zinc-900 space-y-6">
            <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
              User Profile
            </h3>

            <div className="flex items-center gap-4">
              <div className="w-16 h-16 rounded-2xl bg-indigo-600 flex items-center justify-center text-white text-xl font-bold shadow-lg shadow-indigo-600/30">
                {initials}
              </div>
              <div>
                <h4 className="text-base font-bold text-zinc-900 dark:text-zinc-100">
                  {user?.full_name || 'Platform User'}
                </h4>
                <p className="text-xs text-zinc-500 dark:text-zinc-400">
                  {user?.role ? user.role.replace('_', ' ').toUpperCase() : 'USER'} · {activeOrg?.name || 'Default Workspace'}
                </p>
                <span className="inline-block mt-1 text-[11px] font-semibold text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full capitalize">
                  {user?.role ? user.role.replace('_', ' ') : 'Member'}
                </span>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
              <div>
                <label className="block text-xs font-semibold text-zinc-500 uppercase mb-1">
                  Email Address
                </label>
                <input
                  type="email"
                  readOnly
                  value={user?.email || 'user@datapulse.internal'}
                  className="w-full px-3 py-2 text-sm bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700/80 rounded-lg text-zinc-900 dark:text-zinc-100 outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-500 uppercase mb-1">
                  Active Workspace / Organization
                </label>
                <input
                  type="text"
                  readOnly
                  value={activeOrg?.name || 'Default Workspace'}
                  className="w-full px-3 py-2 text-sm bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700/80 rounded-lg text-zinc-900 dark:text-zinc-100 outline-none"
                />
              </div>
            </div>
          </div>

          {/* API Key Box */}
          <div className="p-6 rounded-xl border border-zinc-200 dark:border-zinc-800/80 bg-white dark:bg-zinc-900 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
                  <Key size={16} className="text-indigo-500" /> API Access Key
                </h3>
                <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
                  Used for CI/CD pipeline integration and programmatic metadata ingestion.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <input
                type="password"
                readOnly
                value="dp_live_9f81a7b2901c43d8984920"
                className="font-mono text-xs w-full max-w-md px-3 py-2 bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700/80 rounded-lg text-zinc-700 dark:text-zinc-300 outline-none"
              />
              <button
                onClick={copyApiKey}
                className="px-3 py-2 text-xs font-medium rounded-lg border border-zinc-200 dark:border-zinc-700 hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-700 dark:text-zinc-300 transition-colors inline-flex items-center gap-1.5"
              >
                {copiedKey ? <Check size={14} className="text-emerald-500" /> : <Copy size={14} />}
                {copiedKey ? 'Copied' : 'Copy Key'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* TAB CONTENT: APPEARANCE */}
      {activeTab === 'appearance' && (
        <div className="space-y-6">
          <div className="p-6 rounded-xl border border-zinc-200 dark:border-zinc-800/80 bg-white dark:bg-zinc-900 space-y-5">
            <div>
              <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
                Interface Theme
              </h3>
              <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
                Choose your preferred styling mode. Preference is saved automatically in your browser.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-lg">
              {/* Dark Theme Card */}
              <div
                onClick={() => theme === 'light' && toggleTheme()}
                className={`p-4 rounded-xl border cursor-pointer transition-all ${
                  theme === 'dark'
                    ? 'border-indigo-500 ring-2 ring-indigo-500/20 bg-zinc-900'
                    : 'border-zinc-200 dark:border-zinc-800 bg-zinc-950 opacity-80 hover:opacity-100'
                }`}
              >
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Moon size={18} className="text-indigo-400" />
                    <span className="font-semibold text-sm text-zinc-100">Dark Mode</span>
                  </div>
                  {theme === 'dark' && (
                    <span className="w-2 h-2 rounded-full bg-indigo-500" />
                  )}
                </div>
                <div className="h-16 rounded-lg bg-zinc-900 border border-zinc-800 p-2 flex flex-col justify-between">
                  <div className="w-16 h-2 bg-zinc-700 rounded" />
                  <div className="flex gap-1.5">
                    <div className="w-8 h-4 bg-zinc-800 rounded" />
                    <div className="w-12 h-4 bg-indigo-500/30 rounded" />
                  </div>
                </div>
              </div>

              {/* Light Theme Card */}
              <div
                onClick={() => theme === 'dark' && toggleTheme()}
                className={`p-4 rounded-xl border cursor-pointer transition-all ${
                  theme === 'light'
                    ? 'border-indigo-500 ring-2 ring-indigo-500/20 bg-zinc-50'
                    : 'border-zinc-200 dark:border-zinc-800 bg-white opacity-80 hover:opacity-100'
                }`}
              >
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Sun size={18} className="text-amber-500" />
                    <span className="font-semibold text-sm text-zinc-900">Light Mode</span>
                  </div>
                  {theme === 'light' && (
                    <span className="w-2 h-2 rounded-full bg-indigo-500" />
                  )}
                </div>
                <div className="h-16 rounded-lg bg-zinc-100 border border-zinc-200 p-2 flex flex-col justify-between">
                  <div className="w-16 h-2 bg-zinc-300 rounded" />
                  <div className="flex gap-1.5">
                    <div className="w-8 h-4 bg-zinc-200 rounded" />
                    <div className="w-12 h-4 bg-indigo-500/30 rounded" />
                  </div>
                </div>
              </div>
            </div>

            <div className="pt-2 text-xs text-zinc-500 dark:text-zinc-400">
              Active mode: <strong className="capitalize text-zinc-900 dark:text-zinc-100">{theme}</strong>
            </div>
          </div>
        </div>
      )}

      {/* TAB CONTENT: NOTIFICATIONS */}
      {activeTab === 'notifications' && (
        <div className="p-6 rounded-xl border border-zinc-200 dark:border-zinc-800/80 bg-white dark:bg-zinc-900 space-y-6">
          <div>
            <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
              Alert Trigger Rules
            </h3>
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
              Configure real-time automated dispatch for anomaly detections and pipeline outages.
            </p>
          </div>

          <div className="divide-y divide-zinc-200 dark:divide-zinc-800 space-y-4">
            {[
              {
                id: 'criticalAnomalies' as const,
                title: 'Critical Anomaly Outliers',
                desc: 'Instant alert when null rates or statistical deviation exceed 5-sigma bounds.',
              },
              {
                id: 'schemaDrift' as const,
                title: 'Schema Drift Detection',
                desc: 'Alert when column data types change or unexpected fields appear in upstream topics.',
              },
              {
                id: 'pipelineFailures' as const,
                title: 'Pipeline Execution Failures',
                desc: 'Dispatch incident notifications when scheduled ETL jobs crash or fail constraints.',
              },
              {
                id: 'slaBreach' as const,
                title: 'Data Freshness & SLA Breaches',
                desc: 'Alert when datasets have not received expected batch updates within SLA window.',
              },
              {
                id: 'weeklyDigest' as const,
                title: 'Weekly Observability Summary Digest',
                desc: 'Consolidated PDF health report emailed every Monday at 08:00 UTC.',
              },
            ].map((item) => (
              <div key={item.id} className="pt-4 flex items-center justify-between gap-4">
                <div>
                  <h4 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                    {item.title}
                  </h4>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5 max-w-xl">
                    {item.desc}
                  </p>
                </div>
                <button
                  onClick={() =>
                    setNotifications((prev) => ({
                      ...prev,
                      [item.id]: !prev[item.id],
                    }))
                  }
                  className={`w-11 h-6 rounded-full transition-colors relative flex items-center p-0.5 ${
                    notifications[item.id] ? 'bg-indigo-600' : 'bg-zinc-300 dark:bg-zinc-700'
                  }`}
                >
                  <motion.div
                    animate={{ x: notifications[item.id] ? 20 : 2 }}
                    className="w-4 h-4 rounded-full bg-white shadow-sm"
                  />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB CONTENT: INTEGRATIONS */}
      {activeTab === 'integrations' && (
        <div className="space-y-6">
          <div className="p-6 rounded-xl border border-zinc-200 dark:border-zinc-800/80 bg-white dark:bg-zinc-900 space-y-4">
            <div>
              <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
                Connected Data Ecosystem
              </h3>
              <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
                Databases, object stores, and streaming brokers monitored by DataPulse AI agents.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
              {integrations.map((item, idx) => (
                <div
                  key={idx}
                  className="p-4 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-900/60 flex flex-col justify-between gap-3"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <h4 className="font-semibold text-sm text-zinc-900 dark:text-zinc-100">
                        {item.name}
                      </h4>
                      <span className="text-xs text-zinc-500 dark:text-zinc-400">
                        {item.type}
                      </span>
                    </div>
                    <span
                      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold capitalize ${
                        item.status === 'connected'
                          ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                          : 'bg-zinc-200 dark:bg-zinc-800 text-zinc-500'
                      }`}
                    >
                      <span
                        className={`w-1.5 h-1.5 rounded-full ${
                          item.status === 'connected' ? 'bg-emerald-500' : 'bg-zinc-400'
                        }`}
                      />
                      {item.status}
                    </span>
                  </div>

                  <code className="text-xs font-mono text-zinc-600 dark:text-zinc-400 truncate">
                    {item.endpoint}
                  </code>

                  <div className="flex items-center justify-between text-xs text-zinc-500 pt-2 border-t border-zinc-200/80 dark:border-zinc-800">
                    <span>Sync: {item.lastSync}</span>
                    <button
                      onClick={() => alert(`Settings for ${item.name}`)}
                      className="text-indigo-600 dark:text-indigo-400 hover:underline font-medium"
                    >
                      {item.status === 'connected' ? 'Configure' : 'Connect'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
