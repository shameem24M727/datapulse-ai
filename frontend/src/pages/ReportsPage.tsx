import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  FileBarChart2,
  Download,
  Plus,
  FileText,
  Clock,
  CheckCircle2,
  FileSpreadsheet,
  FileCode,
  Sparkles,
  Search,
} from 'lucide-react';
import { mockReports } from '../data/mockData';
import type { Report } from '../types';

export default function ReportsPage() {
  const [activeTab, setActiveTab] = useState<'all' | 'quality' | 'anomaly' | 'pipeline' | 'custom'>('all');
  const [reportsList, setReportsList] = useState<Report[]>(mockReports);
  const [searchQuery, setSearchQuery] = useState('');
  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const [newReportName, setNewReportName] = useState('');
  const [newReportType, setNewReportType] = useState<Report['type']>('quality');
  const [newReportFormat, setNewReportFormat] = useState<Report['format']>('PDF');

  const filteredReports = reportsList.filter((rep) => {
    const matchesTab = activeTab === 'all' || rep.type === activeTab;
    const matchesSearch = rep.name.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesTab && matchesSearch;
  });

  const readyCount = reportsList.filter((r) => r.status === 'ready').length;
  const generatingCount = reportsList.filter((r) => r.status === 'generating').length;

  const handleGenerate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newReportName.trim()) return;

    const newReport: Report = {
      id: `rep-${Date.now()}`,
      name: newReportName,
      type: newReportType,
      createdAt: 'Just now',
      status: 'generating',
      size: 'Generating...',
      format: newReportFormat,
    };

    setReportsList([newReport, ...reportsList]);
    setNewReportName('');
    setShowGenerateModal(false);

    // Simulate completion after 3 seconds
    setTimeout(() => {
      setReportsList((current) =>
        current.map((r) =>
          r.id === newReport.id
            ? { ...r, status: 'ready', size: '2.1 MB' }
            : r
        )
      );
    }, 3000);
  };

  const getFormatIcon = (format: Report['format']) => {
    switch (format) {
      case 'PDF':
        return <FileText size={16} className="text-rose-500" />;
      case 'CSV':
        return <FileSpreadsheet size={16} className="text-emerald-500" />;
      case 'JSON':
        return <FileCode size={16} className="text-amber-500" />;
    }
  };

  return (
    <div className="p-4 md:p-8 max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-zinc-200 dark:border-zinc-800/80 pb-6">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
            Observability Reports
          </h1>
          <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
            Automated compliance audits, executive health digests, and SLA performance summaries.
          </p>
        </div>

        <button
          onClick={() => setShowGenerateModal(true)}
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-sm transition-colors shadow-sm self-start sm:self-auto"
        >
          <Plus size={16} />
          Create Report
        </button>
      </div>

      {/* Summary Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="p-5 rounded-xl border border-zinc-200 dark:border-zinc-800/80 bg-white dark:bg-zinc-900">
          <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400 mb-2">
            <span>Total Reports</span>
            <FileBarChart2 size={16} className="text-indigo-500" />
          </div>
          <div className="text-3xl font-extrabold text-zinc-900 dark:text-zinc-100">
            {reportsList.length}
          </div>
          <span className="text-xs text-zinc-500 dark:text-zinc-400 mt-1 block">
            Archived across all projects
          </span>
        </div>

        <div className="p-5 rounded-xl border border-zinc-200 dark:border-zinc-800/80 bg-white dark:bg-zinc-900">
          <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400 mb-2">
            <span>Ready for Export</span>
            <CheckCircle2 size={16} className="text-emerald-500" />
          </div>
          <div className="text-3xl font-extrabold text-emerald-600 dark:text-emerald-400">
            {readyCount}
          </div>
          <span className="text-xs text-zinc-500 dark:text-zinc-400 mt-1 block">
            Instant PDF, CSV, and JSON downloads
          </span>
        </div>

        <div className="p-5 rounded-xl border border-zinc-200 dark:border-zinc-800/80 bg-white dark:bg-zinc-900">
          <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400 mb-2">
            <span>Processing Queue</span>
            <Clock size={16} className="text-blue-500" />
          </div>
          <div className="text-3xl font-extrabold text-blue-600 dark:text-blue-400">
            {generatingCount}
          </div>
          <span className="text-xs text-zinc-500 dark:text-zinc-400 mt-1 block">
            Compiling audit logs
          </span>
        </div>
      </div>

      {/* Quick Generate Templates */}
      <div>
        <h3 className="text-sm font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400 mb-3">
          Quick Report Templates
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[
            {
              title: 'Weekly Quality Digest',
              desc: 'High-level metric overview for stakeholders with trends & health indicators.',
              format: 'PDF',
              type: 'quality' as const,
            },
            {
              title: 'Anomaly & Drift Audit',
              desc: 'Detailed breakdown of all statistical variances, schema changes, and impacted rows.',
              format: 'CSV',
              type: 'anomaly' as const,
            },
            {
              title: 'Pipeline SLA & Throughput',
              desc: 'Execution durations, retry frequency, and failure root causes for data engineering.',
              format: 'PDF',
              type: 'pipeline' as const,
            },
          ].map((tmpl, idx) => (
            <div
              key={idx}
              className="p-5 rounded-xl border border-zinc-200 dark:border-zinc-800/80 bg-white dark:bg-zinc-900 hover:border-indigo-500/50 transition-all flex flex-col justify-between gap-4"
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold px-2 py-0.5 rounded bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-300">
                    {tmpl.format}
                  </span>
                  <Sparkles size={14} className="text-indigo-500" />
                </div>
                <h4 className="font-semibold text-zinc-900 dark:text-zinc-100 text-sm">
                  {tmpl.title}
                </h4>
                <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1 leading-relaxed">
                  {tmpl.desc}
                </p>
              </div>
              <button
                onClick={() => {
                  setNewReportName(tmpl.title);
                  setNewReportType(tmpl.type);
                  setNewReportFormat(tmpl.format as any);
                  setShowGenerateModal(true);
                }}
                className="w-full py-2 px-3 text-xs font-medium rounded-lg border border-zinc-200 dark:border-zinc-700/80 hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-800 dark:text-zinc-200 transition-colors text-center"
              >
                Use Template
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Reports Table Section */}
      <div className="p-5 md:p-6 rounded-xl border border-zinc-200 dark:border-zinc-800/80 bg-white dark:bg-zinc-900 space-y-4">
        {/* Filter bar */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          {/* Tabs */}
          <div className="flex items-center bg-zinc-100 dark:bg-zinc-800/60 border border-zinc-200 dark:border-zinc-700/60 rounded-lg p-1 overflow-x-auto">
            {(['all', 'quality', 'anomaly', 'pipeline', 'custom'] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-3 py-1.5 text-xs font-medium rounded-md capitalize transition-all whitespace-nowrap ${
                  activeTab === tab
                    ? 'bg-white dark:bg-zinc-700 text-zinc-900 dark:text-zinc-100 shadow-sm'
                    : 'text-zinc-500 dark:text-zinc-400 hover:text-zinc-800 dark:hover:text-zinc-200'
                }`}
              >
                {tab}
              </button>
            ))}
          </div>

          {/* Search */}
          <div className="relative max-w-xs w-full">
            <Search className="absolute left-3 top-2.5 text-zinc-400" size={15} />
            <input
              type="text"
              placeholder="Search reports..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 text-xs bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-lg text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 focus:outline-none focus:border-indigo-500"
            />
          </div>
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-zinc-200 dark:border-zinc-800 text-xs font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                <th className="pb-3 pr-4">Report Name</th>
                <th className="pb-3 px-4">Category</th>
                <th className="pb-3 px-4">Format</th>
                <th className="pb-3 px-4">Size</th>
                <th className="pb-3 px-4">Generated</th>
                <th className="pb-3 px-4">Status</th>
                <th className="pb-3 pl-4 text-right">Download</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800/60 font-medium">
              {filteredReports.map((report) => (
                <tr
                  key={report.id}
                  className="hover:bg-zinc-50/70 dark:hover:bg-zinc-800/40 transition-colors"
                >
                  <td className="py-3.5 pr-4">
                    <div className="flex items-center gap-2.5">
                      {getFormatIcon(report.format)}
                      <span className="font-semibold text-zinc-900 dark:text-zinc-100">
                        {report.name}
                      </span>
                    </div>
                  </td>

                  <td className="py-3.5 px-4">
                    <span className="text-xs font-medium uppercase px-2 py-0.5 rounded bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-300">
                      {report.type}
                    </span>
                  </td>

                  <td className="py-3.5 px-4 text-xs font-mono text-zinc-500 dark:text-zinc-400">
                    {report.format}
                  </td>

                  <td className="py-3.5 px-4 text-xs text-zinc-600 dark:text-zinc-400">
                    {report.size}
                  </td>

                  <td className="py-3.5 px-4 text-xs text-zinc-500 dark:text-zinc-400">
                    {report.createdAt}
                  </td>

                  <td className="py-3.5 px-4">
                    <span
                      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium capitalize ${
                        report.status === 'ready'
                          ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                          : report.status === 'generating'
                          ? 'bg-blue-500/10 text-blue-600 dark:text-blue-400'
                          : 'bg-rose-500/10 text-rose-600 dark:text-rose-400'
                      }`}
                    >
                      <span
                        className={`w-1.5 h-1.5 rounded-full ${
                          report.status === 'ready'
                            ? 'bg-emerald-500'
                            : report.status === 'generating'
                            ? 'bg-blue-500 animate-pulse'
                            : 'bg-rose-500'
                        }`}
                      />
                      {report.status}
                    </span>
                  </td>

                  <td className="py-3.5 pl-4 text-right">
                    <button
                      disabled={report.status !== 'ready'}
                      onClick={() =>
                        alert(`Export started for ${report.name} (${report.format})`)
                      }
                      className="p-1.5 rounded-md hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-600 dark:text-zinc-400 hover:text-indigo-500 disabled:opacity-30 disabled:hover:text-zinc-400 transition-colors inline-flex items-center gap-1 text-xs"
                      title="Download file"
                    >
                      <Download size={15} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Generate Report Modal */}
      <AnimatePresence>
        {showGenerateModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="w-full max-w-md bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-6 shadow-2xl space-y-5"
            >
              <div className="flex items-center justify-between border-b border-zinc-200 dark:border-zinc-800 pb-3">
                <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
                  Generate Custom Report
                </h3>
                <button
                  onClick={() => setShowGenerateModal(false)}
                  className="text-zinc-400 hover:text-zinc-100 text-sm"
                >
                  ✕
                </button>
              </div>

              <form onSubmit={handleGenerate} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300 uppercase mb-1">
                    Report Title
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g., Q4 Data Health Compliance Digest"
                    value={newReportName}
                    onChange={(e) => setNewReportName(e.target.value)}
                    className="w-full px-3 py-2 text-sm bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-lg text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 focus:outline-none focus:border-indigo-500"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300 uppercase mb-1">
                      Type
                    </label>
                    <select
                      value={newReportType}
                      onChange={(e) => setNewReportType(e.target.value as any)}
                      className="w-full px-3 py-2 text-sm bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-lg text-zinc-900 dark:text-zinc-100 focus:outline-none focus:border-indigo-500"
                    >
                      <option value="quality">Quality</option>
                      <option value="anomaly">Anomaly</option>
                      <option value="pipeline">Pipeline</option>
                      <option value="custom">Custom</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300 uppercase mb-1">
                      Export Format
                    </label>
                    <select
                      value={newReportFormat}
                      onChange={(e) => setNewReportFormat(e.target.value as any)}
                      className="w-full px-3 py-2 text-sm bg-zinc-50 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-lg text-zinc-900 dark:text-zinc-100 focus:outline-none focus:border-indigo-500"
                    >
                      <option value="PDF">PDF Document</option>
                      <option value="CSV">CSV Spreadsheet</option>
                      <option value="JSON">Raw JSON</option>
                    </select>
                  </div>
                </div>

                <div className="flex items-center justify-end gap-3 pt-4 border-t border-zinc-200 dark:border-zinc-800">
                  <button
                    type="button"
                    onClick={() => setShowGenerateModal(false)}
                    className="px-4 py-2 text-xs font-medium text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-4 py-2 text-xs font-semibold rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white transition-colors"
                  >
                    Start Export
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
