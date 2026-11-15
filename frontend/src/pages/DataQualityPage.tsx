import { useState, useEffect } from 'react';
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { motion } from 'framer-motion';
import {
  ShieldCheck,
  CheckCircle2,
  TrendingUp,
  FileCheck,
  Layers,
  Calendar,
} from 'lucide-react';
import {
  qualityTrendData,
  qualityDimensionsData,
  mockDatasets,
} from '../data/mockData';
import type { Dataset } from '../types';
import { fetchIngestedDatasets } from '../services/api';

export default function DataQualityPage() {
  const [timeRange, setTimeRange] = useState<'7d' | '30d' | '90d'>('30d');
  const [selectedDimension, setSelectedDimension] = useState<string | null>(null);
  const [liveDatasets, setLiveDatasets] = useState<Dataset[]>([]);

  useEffect(() => {
    fetchIngestedDatasets()
      .then((items) => {
        const mapped: Dataset[] = items.map((item) => ({
          id: item.id,
          name: item.name,
          source: `Direct Ingestion (${item.file_type.toUpperCase()})`,
          status: item.status,
          qualityScore: Math.round(item.quality_score),
          records: item.row_count,
          lastUpdated: 'Recently ingested',
          size: `${(item.file_size_bytes / 1024).toFixed(1)} KB`,
          tags: [item.file_type.toUpperCase(), 'ingested'],
          owner: 'Live Platform',
          isReal: true,
        }));
        setLiveDatasets(mapped);
      })
      .catch(() => {});
  }, []);

  const allQualityDatasets = [...liveDatasets, ...mockDatasets];

  const dimensionCards = [
    {
      name: 'Completeness',
      score: 91,
      change: '+2.4%',
      status: 'optimal',
      desc: 'Null and missing value checks across all mandatory schema fields',
      color: 'emerald',
      icon: CheckCircle2,
    },
    {
      name: 'Accuracy',
      score: 87,
      change: '+1.1%',
      status: 'optimal',
      desc: 'Format, regex validation, and business rule conformance',
      color: 'emerald',
      icon: ShieldCheck,
    },
    {
      name: 'Consistency',
      score: 83,
      change: '-0.8%',
      status: 'warning',
      desc: 'Cross-table referential integrity and synchronized definitions',
      color: 'amber',
      icon: Layers,
    },
    {
      name: 'Uniqueness',
      score: 95,
      change: '+0.5%',
      status: 'optimal',
      desc: 'Primary key duplication and distinct record integrity checks',
      color: 'emerald',
      icon: FileCheck,
    },
  ];

  return (
    <div className="p-4 md:p-8 max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-zinc-200 dark:border-zinc-800/80 pb-6">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
              Data Quality Observability
            </h1>
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              Global Health 88/100
            </span>
          </div>
          <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
            Continuous automated profiling, constraint validation, and multi-dimensional quality tracking.
          </p>
        </div>

        {/* Time range picker */}
        <div className="flex items-center bg-zinc-100 dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-lg p-1 self-start sm:self-auto">
          {(['7d', '30d', '90d'] as const).map((range) => (
            <button
              key={range}
              onClick={() => setTimeRange(range)}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all ${
                timeRange === range
                  ? 'bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 shadow-sm'
                  : 'text-zinc-500 dark:text-zinc-400 hover:text-zinc-800 dark:hover:text-zinc-200'
              }`}
            >
              Last {range}
            </button>
          ))}
        </div>
      </div>

      {/* 4 Dimension Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {dimensionCards.map((dim, idx) => {
          const Icon = dim.icon;
          return (
            <motion.div
              key={dim.name}
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.08, duration: 0.3 }}
              onClick={() => setSelectedDimension(selectedDimension === dim.name ? null : dim.name)}
              className={`p-5 rounded-xl border transition-all cursor-pointer ${
                selectedDimension === dim.name
                  ? 'border-indigo-500 ring-2 ring-indigo-500/20 bg-indigo-50/50 dark:bg-indigo-950/20'
                  : 'border-zinc-200 dark:border-zinc-800/80 bg-white dark:bg-zinc-900 hover:border-zinc-300 dark:hover:border-zinc-700'
              }`}
            >
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                  {dim.name}
                </span>
                <div
                  className={`p-2 rounded-lg ${
                    dim.color === 'emerald'
                      ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                      : 'bg-amber-500/10 text-amber-600 dark:text-amber-400'
                  }`}
                >
                  <Icon size={16} />
                </div>
              </div>

              <div className="flex items-baseline justify-between mb-2">
                <span className="text-3xl font-extrabold text-zinc-900 dark:text-zinc-100">
                  {dim.score}%
                </span>
                <span
                  className={`text-xs font-semibold flex items-center gap-0.5 ${
                    dim.change.startsWith('+')
                      ? 'text-emerald-600 dark:text-emerald-400'
                      : 'text-amber-600 dark:text-amber-400'
                  }`}
                >
                  <TrendingUp size={12} />
                  {dim.change}
                </span>
              </div>

              {/* Progress bar */}
              <div className="w-full h-1.5 bg-zinc-100 dark:bg-zinc-800 rounded-full overflow-hidden mb-3">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${
                    dim.score >= 90
                      ? 'bg-emerald-500'
                      : dim.score >= 80
                      ? 'bg-indigo-500'
                      : 'bg-amber-500'
                  }`}
                  style={{ width: `${dim.score}%` }}
                />
              </div>

              <p className="text-xs text-zinc-500 dark:text-zinc-400 leading-relaxed">
                {dim.desc}
              </p>
            </motion.div>
          );
        })}
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Quality Score Trend (AreaChart) */}
        <div className="lg:col-span-2 p-5 md:p-6 rounded-xl border border-zinc-200 dark:border-zinc-800/80 bg-white dark:bg-zinc-900">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
                Quality Score Historical Trend
              </h3>
              <p className="text-xs text-zinc-500 dark:text-zinc-400">
                Aggregated daily quality index across all connected pipelines and data stores
              </p>
            </div>
            <span className="text-xs font-medium px-2.5 py-1 rounded bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 flex items-center gap-1">
              <Calendar size={12} /> Rolling Average
            </span>
          </div>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={qualityTrendData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="qualityGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#6366f1" stopOpacity={0.35} />
                    <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" opacity={0.3} vertical={false} />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 11, fill: '#71717a' }}
                  tickLine={false}
                  axisLine={{ stroke: '#3f3f46', opacity: 0.3 }}
                />
                <YAxis
                  domain={[60, 100]}
                  tick={{ fontSize: 11, fill: '#71717a' }}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={(val) => `${val}%`}
                />
                <Tooltip
                  content={({ active, payload }) => {
                    if (active && payload && payload.length) {
                      return (
                        <div className="bg-zinc-900 border border-zinc-800 p-2.5 rounded-lg shadow-xl text-xs">
                          <p className="text-zinc-400 font-medium">{payload[0].payload.date}</p>
                          <p className="text-indigo-400 font-bold text-sm mt-0.5">
                            Score: {payload[0].value}%
                          </p>
                          {payload[0].payload.anomalies !== undefined && (
                            <p className="text-zinc-400 text-[11px] mt-0.5">
                              {payload[0].payload.anomalies} anomalies detected
                            </p>
                          )}
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="score"
                  stroke="#6366f1"
                  strokeWidth={2.5}
                  fillOpacity={1}
                  fill="url(#qualityGradient)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Dimension Radar/Bar Breakdown */}
        <div className="p-5 md:p-6 rounded-xl border border-zinc-200 dark:border-zinc-800/80 bg-white dark:bg-zinc-900">
          <div className="mb-4">
            <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
              Dimension Scores
            </h3>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              6 Core Observability Pillars
            </p>
          </div>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={qualityDimensionsData}
                layout="vertical"
                margin={{ top: 5, right: 20, left: 20, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#27272a" opacity={0.2} />
                <XAxis
                  type="number"
                  domain={[0, 100]}
                  tick={{ fontSize: 10, fill: '#71717a' }}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={(val) => `${val}%`}
                />
                <YAxis
                  type="category"
                  dataKey="dimension"
                  tick={{ fontSize: 11, fill: '#a1a1aa' }}
                  tickLine={false}
                  axisLine={false}
                  width={85}
                />
                <Tooltip
                  content={({ active, payload }) => {
                    if (active && payload && payload.length) {
                      return (
                        <div className="bg-zinc-900 border border-zinc-800 p-2 rounded-lg shadow-xl text-xs">
                          <p className="text-zinc-300 font-semibold">{payload[0].payload.dimension}</p>
                          <p className="text-indigo-400 font-bold">{payload[0].value}%</p>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <Bar dataKey="score" radius={[0, 4, 4, 0]} barSize={14}>
                  {qualityDimensionsData.map((entry, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={
                        entry.score >= 90
                          ? '#10b981'
                          : entry.score >= 80
                          ? '#6366f1'
                          : '#f59e0b'
                      }
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Dataset Quality Breakdown Table */}
      <div className="p-5 md:p-6 rounded-xl border border-zinc-200 dark:border-zinc-800/80 bg-white dark:bg-zinc-900">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-6">
          <div>
            <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
              Dataset Quality Breakdown
            </h3>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              Real-time validation scores across all indexed operational datasets
            </p>
          </div>
          <span className="text-xs text-zinc-500 dark:text-zinc-400">
            {allQualityDatasets.length} datasets monitored ({liveDatasets.length} live ingested)
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-zinc-200 dark:border-zinc-800 text-xs font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                <th className="pb-3 pr-4">Dataset</th>
                <th className="pb-3 px-4">Source</th>
                <th className="pb-3 px-4">Records</th>
                <th className="pb-3 px-4">Status</th>
                <th className="pb-3 px-4 text-right">Quality Score</th>
                <th className="pb-3 pl-4 text-right">Integrity Level</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800/60 font-medium">
              {allQualityDatasets.map((ds) => (
                <tr
                  key={ds.id}
                  className="hover:bg-zinc-50/70 dark:hover:bg-zinc-800/40 transition-colors"
                >
                  <td className="py-3.5 pr-4">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-zinc-900 dark:text-zinc-100">
                        {ds.name}
                      </span>
                      {ds.isReal && (
                        <span className="text-[10px] font-bold px-1.5 py-0.2 rounded bg-indigo-600 text-white">
                          LIVE
                        </span>
                      )}
                    </div>
                    <span className="block text-xs font-normal text-zinc-500 dark:text-zinc-400">
                      Owner: {ds.owner}
                    </span>
                  </td>
                  <td className="py-3.5 px-4 text-xs text-zinc-500 dark:text-zinc-400">
                    {ds.source}
                  </td>
                  <td className="py-3.5 px-4 text-xs text-zinc-700 dark:text-zinc-300">
                    {ds.records.toLocaleString()}
                  </td>
                  <td className="py-3.5 px-4">
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold capitalize ${
                        ds.status === 'healthy'
                          ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20'
                          : ds.status === 'warning'
                          ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20'
                          : ds.status === 'critical'
                          ? 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20'
                          : 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20'
                      }`}
                    >
                      {ds.status}
                    </span>
                  </td>
                  <td className="py-3.5 px-4 text-right">
                    <span
                      className={`font-bold ${
                        ds.qualityScore >= 85
                          ? 'text-emerald-600 dark:text-emerald-400'
                          : ds.qualityScore >= 60
                          ? 'text-amber-600 dark:text-amber-400'
                          : 'text-rose-600 dark:text-rose-400'
                      }`}
                    >
                      {ds.qualityScore}%
                    </span>
                  </td>
                  <td className="py-3.5 pl-4 text-right">
                    <div className="inline-flex items-center gap-2">
                      <div className="w-24 h-2 bg-zinc-100 dark:bg-zinc-800 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full ${
                            ds.qualityScore >= 85
                              ? 'bg-emerald-500'
                              : ds.qualityScore >= 60
                              ? 'bg-amber-500'
                              : 'bg-rose-500'
                          }`}
                          style={{ width: `${ds.qualityScore}%` }}
                        />
                      </div>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
