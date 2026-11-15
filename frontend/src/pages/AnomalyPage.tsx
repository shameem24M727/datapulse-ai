import { useState } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { motion, AnimatePresence } from 'framer-motion';
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Search,
  ShieldAlert,
  ChevronRight,
  X,
} from 'lucide-react';
import { mockAnomalies, anomalyHistoryData } from '../data/mockData';
import type { Anomaly } from '../types';

export default function AnomalyPage() {
  const [activeTab, setActiveTab] = useState<'all' | 'open' | 'investigating' | 'resolved'>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedAnomaly, setSelectedAnomaly] = useState<Anomaly | null>(null);

  // Filter anomalies based on tab and search
  const filteredAnomalies = mockAnomalies.filter((item) => {
    const matchesTab = activeTab === 'all' || item.status === activeTab;
    const matchesSearch =
      item.datasetName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.type.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.column.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.description.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesTab && matchesSearch;
  });

  const openCount = mockAnomalies.filter((a) => a.status === 'open').length;
  const investigatingCount = mockAnomalies.filter((a) => a.status === 'investigating').length;
  const resolvedCount = mockAnomalies.filter((a) => a.status === 'resolved').length;
  const criticalCount = mockAnomalies.filter((a) => a.severity === 'critical' && a.status !== 'resolved').length;

  return (
    <div className="p-4 md:p-8 max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-zinc-200 dark:border-zinc-800/80 pb-6">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
              Anomaly Detection
            </h1>
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20">
              <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-ping" />
              {criticalCount} Critical Active
            </span>
          </div>
          <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
            Statistical deviation alerts, distribution skew, schema changes, and automated root cause indicators.
          </p>
        </div>

        {/* Tab pills */}
        <div className="flex items-center bg-zinc-100 dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-lg p-1 self-start sm:self-auto">
          {(
            [
              { id: 'all', label: 'All', count: mockAnomalies.length },
              { id: 'open', label: 'Open', count: openCount },
              { id: 'investigating', label: 'Investigating', count: investigatingCount },
              { id: 'resolved', label: 'Resolved', count: resolvedCount },
            ] as const
          ).map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md transition-all ${
                activeTab === tab.id
                  ? 'bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 shadow-sm'
                  : 'text-zinc-500 dark:text-zinc-400 hover:text-zinc-800 dark:hover:text-zinc-200'
              }`}
            >
              {tab.label}
              <span
                className={`text-[10px] px-1.5 py-0.2 rounded-full font-semibold ${
                  activeTab === tab.id
                    ? 'bg-zinc-200 dark:bg-zinc-700 text-zinc-800 dark:text-zinc-200'
                    : 'bg-zinc-200/60 dark:bg-zinc-800 text-zinc-500'
                }`}
              >
                {tab.count}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-5 rounded-xl border border-zinc-200 dark:border-zinc-800/80 bg-white dark:bg-zinc-900">
          <div className="flex items-center justify-between text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wider mb-2">
            <span>Open Anomalies</span>
            <AlertTriangle className="text-rose-500" size={16} />
          </div>
          <div className="text-3xl font-extrabold text-rose-600 dark:text-rose-400">{openCount}</div>
          <span className="text-xs text-zinc-500 dark:text-zinc-400 mt-1 block">
            {criticalCount} critical severity
          </span>
        </div>

        <div className="p-5 rounded-xl border border-zinc-200 dark:border-zinc-800/80 bg-white dark:bg-zinc-900">
          <div className="flex items-center justify-between text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wider mb-2">
            <span>Under Review</span>
            <Clock className="text-amber-500" size={16} />
          </div>
          <div className="text-3xl font-extrabold text-amber-600 dark:text-amber-400">{investigatingCount}</div>
          <span className="text-xs text-zinc-500 dark:text-zinc-400 mt-1 block">
            Assigned to engineers
          </span>
        </div>

        <div className="p-5 rounded-xl border border-zinc-200 dark:border-zinc-800/80 bg-white dark:bg-zinc-900">
          <div className="flex items-center justify-between text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wider mb-2">
            <span>Resolved</span>
            <CheckCircle2 className="text-emerald-500" size={16} />
          </div>
          <div className="text-3xl font-extrabold text-emerald-600 dark:text-emerald-400">{resolvedCount}</div>
          <span className="text-xs text-zinc-500 dark:text-zinc-400 mt-1 block">
            Auto & manually fixed
          </span>
        </div>

        <div className="p-5 rounded-xl border border-zinc-200 dark:border-zinc-800/80 bg-white dark:bg-zinc-900">
          <div className="flex items-center justify-between text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wider mb-2">
            <span>Avg MTTD</span>
            <ShieldAlert className="text-indigo-500" size={16} />
          </div>
          <div className="text-3xl font-extrabold text-indigo-600 dark:text-indigo-400">4.2m</div>
          <span className="text-xs text-zinc-500 dark:text-zinc-400 mt-1 block">
            Automated detection lag
          </span>
        </div>
      </div>

      {/* Historical Anomaly Stacked Bar Chart */}
      <div className="p-5 md:p-6 rounded-xl border border-zinc-200 dark:border-zinc-800/80 bg-white dark:bg-zinc-900">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4">
          <div>
            <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
              Anomaly Incidents by Severity
            </h3>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              Daily frequency of detected statistical, schema, and rule-based exceptions
            </p>
          </div>
          <div className="flex items-center gap-3 text-xs">
            <span className="flex items-center gap-1.5 text-zinc-600 dark:text-zinc-400">
              <span className="w-2.5 h-2.5 rounded-sm bg-rose-500" /> Critical
            </span>
            <span className="flex items-center gap-1.5 text-zinc-600 dark:text-zinc-400">
              <span className="w-2.5 h-2.5 rounded-sm bg-amber-500" /> High
            </span>
            <span className="flex items-center gap-1.5 text-zinc-600 dark:text-zinc-400">
              <span className="w-2.5 h-2.5 rounded-sm bg-indigo-500" /> Medium
            </span>
            <span className="flex items-center gap-1.5 text-zinc-600 dark:text-zinc-400">
              <span className="w-2.5 h-2.5 rounded-sm bg-blue-500" /> Low
            </span>
          </div>
        </div>

        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={anomalyHistoryData} margin={{ top: 10, right: 10, left: -25, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#27272a" opacity={0.2} vertical={false} />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 11, fill: '#71717a' }}
                tickLine={false}
                axisLine={{ stroke: '#3f3f46', opacity: 0.3 }}
              />
              <YAxis
                tick={{ fontSize: 11, fill: '#71717a' }}
                tickLine={false}
                axisLine={false}
                allowDecimals={false}
              />
              <Tooltip
                content={({ active, payload }) => {
                  if (active && payload && payload.length) {
                    return (
                      <div className="bg-zinc-900 border border-zinc-800 p-3 rounded-lg shadow-xl text-xs space-y-1">
                        <p className="text-zinc-300 font-semibold mb-1">{payload[0].payload.date}</p>
                        {payload.map((entry) => (
                          <div key={entry.name} className="flex justify-between gap-4 text-zinc-400">
                            <span className="capitalize">{entry.name}:</span>
                            <span className="font-bold text-zinc-200">{entry.value}</span>
                          </div>
                        ))}
                      </div>
                    );
                  }
                  return null;
                }}
              />
              <Bar dataKey="critical" stackId="a" fill="#ef4444" radius={[0, 0, 0, 0]} />
              <Bar dataKey="high" stackId="a" fill="#f59e0b" radius={[0, 0, 0, 0]} />
              <Bar dataKey="medium" stackId="a" fill="#6366f1" radius={[0, 0, 0, 0]} />
              <Bar dataKey="low" stackId="a" fill="#3b82f6" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Anomalies Table / List */}
      <div className="p-5 md:p-6 rounded-xl border border-zinc-200 dark:border-zinc-800/80 bg-white dark:bg-zinc-900 space-y-4">
        {/* Search bar */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-2.5 text-zinc-400" size={16} />
            <input
              type="text"
              placeholder="Search by dataset, column, or anomaly type..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-4 py-2 text-sm bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700/80 rounded-lg text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 focus:outline-none focus:border-indigo-500 transition-colors"
            />
          </div>
          <span className="text-xs text-zinc-500 dark:text-zinc-400">
            Showing {filteredAnomalies.length} of {mockAnomalies.length} incidents
          </span>
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-zinc-200 dark:border-zinc-800 text-xs font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                <th className="pb-3 pr-4">Severity</th>
                <th className="pb-3 px-4">Anomaly Type</th>
                <th className="pb-3 px-4">Dataset & Target</th>
                <th className="pb-3 px-4">Affected Records</th>
                <th className="pb-3 px-4">Detected</th>
                <th className="pb-3 px-4">Status</th>
                <th className="pb-3 pl-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800/60 font-medium">
              {filteredAnomalies.map((anomaly) => (
                <tr
                  key={anomaly.id}
                  className="hover:bg-zinc-50/70 dark:hover:bg-zinc-800/40 transition-colors cursor-pointer"
                  onClick={() => setSelectedAnomaly(anomaly)}
                >
                  <td className="py-3.5 pr-4">
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-bold uppercase tracking-wider ${
                        anomaly.severity === 'critical'
                          ? 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20'
                          : anomaly.severity === 'high'
                          ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20'
                          : anomaly.severity === 'medium'
                          ? 'bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-500/20'
                          : 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20'
                      }`}
                    >
                      {anomaly.severity}
                    </span>
                  </td>

                  <td className="py-3.5 px-4 font-semibold text-zinc-900 dark:text-zinc-100">
                    {anomaly.type}
                  </td>

                  <td className="py-3.5 px-4">
                    <span className="text-zinc-900 dark:text-zinc-100 block">
                      {anomaly.datasetName}
                    </span>
                    <code className="text-xs text-indigo-600 dark:text-indigo-400 font-mono">
                      {anomaly.column}
                    </code>
                  </td>

                  <td className="py-3.5 px-4 text-zinc-700 dark:text-zinc-300">
                    {anomaly.affectedRecords.toLocaleString()}
                  </td>

                  <td className="py-3.5 px-4 text-xs text-zinc-500 dark:text-zinc-400">
                    {anomaly.detectedAt}
                  </td>

                  <td className="py-3.5 px-4">
                    <span
                      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium capitalize ${
                        anomaly.status === 'open'
                          ? 'bg-rose-500/10 text-rose-600 dark:text-rose-400'
                          : anomaly.status === 'investigating'
                          ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400'
                          : 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                      }`}
                    >
                      <span
                        className={`w-1.5 h-1.5 rounded-full ${
                          anomaly.status === 'open'
                            ? 'bg-rose-500'
                            : anomaly.status === 'investigating'
                            ? 'bg-amber-500'
                            : 'bg-emerald-500'
                        }`}
                      />
                      {anomaly.status}
                    </span>
                  </td>

                  <td className="py-3.5 pl-4 text-right">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedAnomaly(anomaly);
                      }}
                      className="px-2.5 py-1 text-xs font-medium rounded-md bg-zinc-100 dark:bg-zinc-800 hover:bg-zinc-200 dark:hover:bg-zinc-700 text-zinc-800 dark:text-zinc-200 transition-colors inline-flex items-center gap-1"
                    >
                      Investigate <ChevronRight size={12} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Investigation Slide-over / Modal */}
      <AnimatePresence>
        {selectedAnomaly && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="w-full max-w-lg bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-6 shadow-2xl space-y-5"
            >
              <div className="flex items-center justify-between border-b border-zinc-200 dark:border-zinc-800 pb-3">
                <div className="flex items-center gap-2">
                  <span
                    className={`px-2 py-0.5 rounded text-[11px] font-bold uppercase tracking-wider ${
                      selectedAnomaly.severity === 'critical'
                        ? 'bg-rose-500/10 text-rose-500 border border-rose-500/20'
                        : 'bg-amber-500/10 text-amber-500 border border-amber-500/20'
                    }`}
                  >
                    {selectedAnomaly.severity}
                  </span>
                  <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
                    {selectedAnomaly.type}
                  </h3>
                </div>
                <button
                  onClick={() => setSelectedAnomaly(null)}
                  className="p-1 rounded-md text-zinc-400 hover:text-zinc-100 transition-colors"
                >
                  <X size={18} />
                </button>
              </div>

              <div className="space-y-3 text-sm">
                <div>
                  <span className="text-xs text-zinc-500 uppercase font-semibold">Dataset</span>
                  <p className="text-zinc-900 dark:text-zinc-100 font-medium">
                    {selectedAnomaly.datasetName}
                  </p>
                </div>
                <div>
                  <span className="text-xs text-zinc-500 uppercase font-semibold">Target Column</span>
                  <p className="font-mono text-indigo-500 text-xs mt-0.5">
                    {selectedAnomaly.column}
                  </p>
                </div>
                <div>
                  <span className="text-xs text-zinc-500 uppercase font-semibold">Root Cause Finding</span>
                  <p className="text-zinc-700 dark:text-zinc-300 bg-zinc-50 dark:bg-zinc-800/60 p-3 rounded-lg border border-zinc-200 dark:border-zinc-700/60 mt-1 leading-relaxed text-xs">
                    {selectedAnomaly.description}
                  </p>
                </div>
                <div className="grid grid-cols-2 gap-3 pt-2">
                  <div className="p-3 rounded-lg bg-zinc-50 dark:bg-zinc-800/40 border border-zinc-200 dark:border-zinc-800">
                    <span className="text-[11px] text-zinc-500">Affected Records</span>
                    <p className="text-base font-bold text-zinc-900 dark:text-zinc-100">
                      {selectedAnomaly.affectedRecords.toLocaleString()}
                    </p>
                  </div>
                  <div className="p-3 rounded-lg bg-zinc-50 dark:bg-zinc-800/40 border border-zinc-200 dark:border-zinc-800">
                    <span className="text-[11px] text-zinc-500">Detected Lag</span>
                    <p className="text-base font-bold text-zinc-900 dark:text-zinc-100">
                      {selectedAnomaly.detectedAt}
                    </p>
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-zinc-200 dark:border-zinc-800">
                <button
                  onClick={() => setSelectedAnomaly(null)}
                  className="px-4 py-2 text-xs font-medium text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors"
                >
                  Close
                </button>
                <button
                  onClick={() => setSelectedAnomaly(null)}
                  className="px-4 py-2 text-xs font-semibold rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white transition-colors"
                >
                  Mark as Investigated
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
