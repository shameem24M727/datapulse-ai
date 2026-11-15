import { useState, useEffect, useRef } from 'react';
import {
  Search,
  Filter,
  Plus,
  Eye,
  UploadCloud,
  FileSpreadsheet,
  FileText,
  Trash2,
  X,
  AlertTriangle,
  CheckCircle2,
  Loader2,
  RefreshCw,
  Sparkles,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { mockDatasets } from '../data/mockData';
import type { Dataset, BackendDatasetDetail } from '../types';
import {
  uploadDatasetFile,
  fetchIngestedDatasets,
  fetchDatasetDetail,
  deleteIngestedDataset,
} from '../services/api';
import { useAuth } from '../context/AuthContext';

function cn(...classes: (string | false | null | undefined)[]) {
  return classes.filter(Boolean).join(' ');
}

function formatNumber(n: number): string {
  return n.toLocaleString('en-US');
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function StatusBadge({ status }: { status: Dataset['status'] }) {
  const map: Record<Dataset['status'], string> = {
    healthy: 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20',
    warning: 'bg-amber-500/10 text-amber-500 border-amber-500/20',
    critical: 'bg-rose-500/10 text-rose-500 border-rose-500/20',
    processing: 'bg-blue-500/10 text-blue-500 border-blue-500/20',
  };
  return (
    <span
      className={cn(
        'inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border capitalize',
        map[status] || map.healthy,
      )}
    >
      {status}
    </span>
  );
}

function QualityScore({ score }: { score: number }) {
  const color =
    score >= 85
      ? 'text-emerald-500'
      : score >= 60
      ? 'text-amber-500'
      : 'text-rose-500';
  return <span className={cn('font-bold tabular-nums', color)}>{score.toFixed(0)}%</span>;
}

type StatusFilter = 'all' | Dataset['status'];

export default function DatasetsPage() {
  const { user } = useAuth();
  const isViewer = user?.role === 'viewer';
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [realDatasets, setRealDatasets] = useState<Dataset[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedDetail, setSelectedDetail] = useState<BackendDatasetDetail | null>(null);

  // Upload Modal State
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadBackendDatasets = async () => {
    setIsLoading(true);
    try {
      const items = await fetchIngestedDatasets();
      const mapped: Dataset[] = items.map((item) => ({
        id: item.id,
        name: item.name,
        source: `Direct Ingestion (${item.file_type.toUpperCase()})`,
        status: item.status,
        qualityScore: Math.round(item.quality_score),
        records: item.row_count,
        lastUpdated: new Date(item.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        size: formatBytes(item.file_size_bytes),
        tags: [item.file_type.toUpperCase(), 'ingested', 'live-db'],
        owner: 'System / User',
        isReal: true,
      }));
      setRealDatasets(mapped);
    } catch {
      // Backend not yet reachable or empty
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadBackendDatasets();
  }, []);

  // Combined datasets: Real ingested datasets first, followed by default mock datasets
  const allDatasets = [...realDatasets, ...mockDatasets];

  const filtered = allDatasets.filter((ds) => {
    const matchesSearch =
      ds.name.toLowerCase().includes(search.toLowerCase()) ||
      ds.source.toLowerCase().includes(search.toLowerCase()) ||
      ds.owner.toLowerCase().includes(search.toLowerCase());
    const matchesStatus = statusFilter === 'all' || ds.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setUploadFile(e.dataTransfer.files[0]);
      setUploadError(null);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setUploadFile(e.target.files[0]);
      setUploadError(null);
    }
  };

  const submitUpload = async () => {
    if (!uploadFile) return;
    setUploading(true);
    setUploadError(null);
    setUploadSuccess(null);

    try {
      const result = await uploadDatasetFile(uploadFile);
      setUploadSuccess(`Successfully ingested "${result.name}" with ${result.row_count.toLocaleString()} records.`);
      setUploadFile(null);
      await loadBackendDatasets();
      setTimeout(() => {
        setShowUploadModal(false);
        setUploadSuccess(null);
        openDetailModal(result.id);
      }, 1200);
    } catch (err: any) {
      setUploadError(err.message || 'Upload failed. Check file format or size.');
    } finally {
      setUploading(false);
    }
  };

  const openDetailModal = async (id: string) => {
    try {
      const detail = await fetchDatasetDetail(id);
      setSelectedDetail(detail);
    } catch {
      // If dataset is from mockData, create dummy detail view
      const found = mockDatasets.find((d) => d.id === id);
      if (found) {
        setSelectedDetail({
          id: found.id,
          name: found.name,
          original_filename: `${found.name.toLowerCase().replace(/ /g, '_')}.csv`,
          file_type: 'csv',
          file_size_bytes: 4 * 1024 * 1024,
          row_count: found.records,
          column_count: 8,
          status: found.status,
          quality_score: found.qualityScore,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          column_profiles: [
            { id: '1', column_name: 'id', data_type: 'Integer', total_count: found.records, null_count: 0, null_percentage: 0, unique_count: found.records, is_numeric: true, min_value: 1, max_value: found.records, mean_value: found.records / 2, median_value: found.records / 2, std_value: 100 },
            { id: '2', column_name: 'customer_email', data_type: 'String', total_count: found.records, null_count: Math.round(found.records * 0.05), null_percentage: 5.0, unique_count: Math.round(found.records * 0.95), is_numeric: false },
            { id: '3', column_name: 'spend_amount', data_type: 'Float', total_count: found.records, null_count: 0, null_percentage: 0, unique_count: 450, is_numeric: true, min_value: 10.5, max_value: 5800.0, mean_value: 340.2, median_value: 210.0, std_value: 85.0 },
          ],
          quality_report: {
            id: 'qr-1',
            overall_score: found.qualityScore,
            completeness_score: 95.0,
            uniqueness_score: 98.0,
            validity_score: 90.0,
            consistency_score: 92.0,
            duplicate_rows_count: 12,
            duplicate_rows_percentage: 0.1,
            total_cells: found.records * 8,
            null_cells: Math.round(found.records * 0.4),
            deductions_evidence: [
              { dimension: 'Completeness', impact: 'negative', score_effect: '-5 pts', message: 'Minor null occurrences detected in customer email fields.' },
              { dimension: 'Uniqueness', impact: 'positive', score_effect: '+0 pts', message: 'High distinct record integrity.' },
            ],
            created_at: new Date().toISOString(),
          },
          anomalies: [],
        });
      }
    }
  };

  const handleDelete = async (id: string, name: string) => {
    if (!window.confirm(`Are you sure you want to delete dataset "${name}"?`)) return;
    try {
      await deleteIngestedDataset(id);
      setRealDatasets((prev) => prev.filter((d) => d.id !== id));
      if (selectedDetail?.id === id) setSelectedDetail(null);
    } catch {
      // Mock delete locally
      setRealDatasets((prev) => prev.filter((d) => d.id !== id));
    }
  };

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 p-4 md:p-8 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-zinc-200 dark:border-zinc-800 pb-5">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
              Datasets Catalog
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-800">
              {allDatasets.length} total monitored ({realDatasets.length} live ingested)
            </span>
          </div>
          <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
            Ingest, profile, and observe relational tables, CSV files, and Excel spreadsheets.
          </p>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto">
          <button
            onClick={loadBackendDatasets}
            disabled={isLoading}
            className="p-2.5 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors"
            title="Refresh datasets from database"
          >
            <RefreshCw size={16} className={isLoading ? 'animate-spin' : ''} />
          </button>
          {!isViewer && (
            <button
              onClick={() => {
                setUploadFile(null);
                setUploadError(null);
                setUploadSuccess(null);
                setShowUploadModal(true);
              }}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold transition-colors shadow-sm"
            >
              <Plus size={16} />
              Ingest Dataset
            </button>
          )}
          {isViewer && (
            <span className="px-3 py-2 rounded-lg bg-zinc-100 dark:bg-zinc-800 text-xs text-zinc-500 dark:text-zinc-400 border border-zinc-200 dark:border-zinc-700">
              Viewer (Read-Only)
            </span>
          )}
        </div>
      </div>

      {/* Search + Filter Bar */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" />
          <input
            type="text"
            placeholder="Search datasets by name, source, or owner…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 rounded-lg bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 text-sm text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 focus:outline-none focus:border-indigo-500 transition"
          />
        </div>
        <div className="relative">
          <Filter className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400 pointer-events-none" />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
            className="pl-9 pr-8 py-2 rounded-lg bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 text-sm text-zinc-900 dark:text-zinc-100 focus:outline-none focus:border-indigo-500 appearance-none cursor-pointer"
          >
            <option value="all">All Statuses</option>
            <option value="healthy">Healthy (Score &gt;= 85)</option>
            <option value="warning">Warning (Score 60 - 84)</option>
            <option value="critical">Critical (Score &lt; 60)</option>
            <option value="processing">Processing</option>
          </select>
        </div>
      </div>

      {/* Datasets Table */}
      {filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl">
          <div className="w-12 h-12 rounded-full bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center mb-3">
            <Search className="w-5 h-5 text-zinc-400" />
          </div>
          <p className="text-zinc-800 dark:text-zinc-200 font-medium">No datasets found</p>
          <p className="text-zinc-500 dark:text-zinc-400 text-sm mt-1">
            Try adjusting your search criteria or upload a new CSV or Excel dataset.
          </p>
        </div>
      ) : (
        <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-200 dark:border-zinc-800 text-xs font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                  <th className="px-4 py-3.5 text-left">Dataset</th>
                  <th className="px-4 py-3.5 text-left">Status</th>
                  <th className="px-4 py-3.5 text-left">Quality Score</th>
                  <th className="px-4 py-3.5 text-left">Records Profiled</th>
                  <th className="px-4 py-3.5 text-left">Storage Size</th>
                  <th className="px-4 py-3.5 text-left">Ingested / Updated</th>
                  <th className="px-4 py-3.5 text-left">Source / Tags</th>
                  <th className="px-4 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800/80 font-medium">
                {filtered.map((ds) => (
                  <tr
                    key={ds.id}
                    className="hover:bg-zinc-50/70 dark:hover:bg-zinc-800/40 transition-colors"
                  >
                    <td className="px-4 py-4">
                      <div className="flex items-center gap-2.5">
                        <div className="w-8 h-8 rounded-lg bg-indigo-50 dark:bg-indigo-950/60 border border-indigo-200 dark:border-indigo-800/60 flex items-center justify-center text-indigo-600 dark:text-indigo-400 flex-shrink-0">
                          {ds.name.endsWith('.xlsx') || ds.tags?.includes('XLSX') ? (
                            <FileSpreadsheet size={16} />
                          ) : (
                            <FileText size={16} />
                          )}
                        </div>
                        <div>
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
                          <span className="text-xs text-zinc-500 dark:text-zinc-400 font-normal">
                            {ds.source}
                          </span>
                        </div>
                      </div>
                    </td>

                    <td className="px-4 py-4">
                      <StatusBadge status={ds.status} />
                    </td>

                    <td className="px-4 py-4">
                      <QualityScore score={ds.qualityScore} />
                    </td>

                    <td className="px-4 py-4 text-zinc-700 dark:text-zinc-300">
                      {formatNumber(ds.records)} rows
                    </td>

                    <td className="px-4 py-4 text-xs font-mono text-zinc-500 dark:text-zinc-400">
                      {ds.size}
                    </td>

                    <td className="px-4 py-4 text-xs text-zinc-500 dark:text-zinc-400">
                      {ds.lastUpdated}
                    </td>

                    <td className="px-4 py-4">
                      <div className="flex flex-wrap gap-1">
                        {ds.tags.slice(0, 2).map((tag) => (
                          <span
                            key={tag}
                            className="inline-flex items-center px-1.5 py-0.5 rounded text-[11px] bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 border border-zinc-200 dark:border-zinc-700"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    </td>

                    <td className="px-4 py-4 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => openDetailModal(ds.id)}
                          className="p-1.5 rounded-md hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-600 dark:text-zinc-400 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors inline-flex items-center gap-1 text-xs"
                          title="View profiling and quality findings"
                        >
                          <Eye size={15} />
                          View
                        </button>
                        {ds.isReal && !isViewer && (
                          <button
                            onClick={() => handleDelete(ds.id, ds.name)}
                            className="p-1.5 rounded-md hover:bg-rose-50 dark:hover:bg-rose-950/40 text-zinc-400 hover:text-rose-600 dark:hover:text-rose-400 transition-colors"
                            title="Delete dataset"
                          >
                            <Trash2 size={15} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Ingestion / Upload Modal */}
      <AnimatePresence>
        {showUploadModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="w-full max-w-lg bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-6 shadow-2xl space-y-5"
            >
              <div className="flex items-center justify-between border-b border-zinc-200 dark:border-zinc-800 pb-3">
                <div className="flex items-center gap-2">
                  <div className="p-2 rounded-lg bg-indigo-50 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400">
                    <UploadCloud size={20} />
                  </div>
                  <div>
                    <h3 className="text-base font-bold text-zinc-900 dark:text-zinc-100">
                      Ingest New Dataset
                    </h3>
                    <p className="text-xs text-zinc-500 dark:text-zinc-400">
                      Upload CSV or Excel files for automated profiling & quality analysis.
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setShowUploadModal(false)}
                  className="text-zinc-400 hover:text-zinc-100"
                >
                  <X size={18} />
                </button>
              </div>

              {/* Dropzone */}
              <div
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                className={cn(
                  'border-2 border-dashed rounded-xl p-8 flex flex-col items-center justify-center text-center cursor-pointer transition-all',
                  dragActive
                    ? 'border-indigo-500 bg-indigo-50/50 dark:bg-indigo-950/20'
                    : 'border-zinc-300 dark:border-zinc-700 bg-zinc-50/50 dark:bg-zinc-800/40 hover:border-zinc-400 dark:hover:border-zinc-600',
                )}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv,.xlsx,.xls"
                  onChange={handleFileChange}
                  className="hidden"
                />
                <div className="w-12 h-12 rounded-full bg-indigo-100 dark:bg-indigo-950/80 text-indigo-600 dark:text-indigo-400 flex items-center justify-center mb-3">
                  <FileSpreadsheet size={24} />
                </div>
                <p className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">
                  {uploadFile ? uploadFile.name : 'Click to select or drag and drop file here'}
                </p>
                <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
                  Supports .CSV, .XLSX, and .XLS files (up to 50MB)
                </p>
                {uploadFile && (
                  <span className="inline-block mt-2 text-xs font-mono bg-zinc-200 dark:bg-zinc-700 text-zinc-700 dark:text-zinc-200 px-2 py-0.5 rounded">
                    {formatBytes(uploadFile.size)}
                  </span>
                )}
              </div>

              {/* Feedback messages */}
              {uploadError && (
                <div className="flex items-start gap-2 p-3 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-xs text-rose-700 dark:text-rose-300">
                  <AlertTriangle size={15} className="mt-0.5 flex-shrink-0" />
                  <span>{uploadError}</span>
                </div>
              )}

              {uploadSuccess && (
                <div className="flex items-start gap-2 p-3 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-xs text-emerald-700 dark:text-emerald-300">
                  <CheckCircle2 size={15} className="mt-0.5 flex-shrink-0" />
                  <span>{uploadSuccess}</span>
                </div>
              )}

              {/* Actions */}
              <div className="flex items-center justify-end gap-3 pt-3 border-t border-zinc-200 dark:border-zinc-800">
                <button
                  type="button"
                  disabled={uploading}
                  onClick={() => setShowUploadModal(false)}
                  className="px-4 py-2 text-xs font-medium text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={!uploadFile || uploading}
                  onClick={submitUpload}
                  className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white transition-colors"
                >
                  {uploading ? (
                    <>
                      <Loader2 size={14} className="animate-spin" />
                      Analyzing & Ingesting...
                    </>
                  ) : (
                    'Start Ingestion'
                  )}
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Dataset Details Slide-over Drawer / Modal */}
      <AnimatePresence>
        {selectedDetail && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="w-full max-w-4xl max-h-[90vh] bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-6 shadow-2xl flex flex-col space-y-6 overflow-hidden"
            >
              {/* Header */}
              <div className="flex items-start justify-between border-b border-zinc-200 dark:border-zinc-800 pb-4">
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100">
                      {selectedDetail.name}
                    </h2>
                    <StatusBadge status={selectedDetail.status} />
                  </div>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
                    Filename: <code className="font-mono text-zinc-700 dark:text-zinc-300">{selectedDetail.original_filename}</code> · {selectedDetail.row_count.toLocaleString()} rows · {selectedDetail.column_count} columns
                  </p>
                </div>
                <button
                  onClick={() => setSelectedDetail(null)}
                  className="p-1 rounded-lg text-zinc-400 hover:text-zinc-100 transition-colors"
                >
                  <X size={20} />
                </button>
              </div>

              {/* Scrollable Content */}
              <div className="flex-1 overflow-y-auto space-y-6 pr-1">
                {/* Score & Dimensions */}
                {selectedDetail.quality_report && (
                  <div className="p-4 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-800/40 space-y-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Sparkles size={18} className="text-indigo-500" />
                        <h3 className="font-bold text-sm text-zinc-900 dark:text-zinc-100">
                          Data Quality Integrity Score
                        </h3>
                      </div>
                      <span className="text-2xl font-extrabold text-indigo-600 dark:text-indigo-400">
                        {selectedDetail.quality_report.overall_score.toFixed(1)}%
                      </span>
                    </div>

                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                      <div className="p-2.5 rounded-lg bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800">
                        <span className="text-zinc-500 uppercase block font-semibold text-[10px]">Completeness</span>
                        <span className="font-bold text-sm text-zinc-800 dark:text-zinc-200">
                          {selectedDetail.quality_report.completeness_score}%
                        </span>
                      </div>
                      <div className="p-2.5 rounded-lg bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800">
                        <span className="text-zinc-500 uppercase block font-semibold text-[10px]">Uniqueness</span>
                        <span className="font-bold text-sm text-zinc-800 dark:text-zinc-200">
                          {selectedDetail.quality_report.uniqueness_score}%
                        </span>
                      </div>
                      <div className="p-2.5 rounded-lg bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800">
                        <span className="text-zinc-500 uppercase block font-semibold text-[10px]">Validity</span>
                        <span className="font-bold text-sm text-zinc-800 dark:text-zinc-200">
                          {selectedDetail.quality_report.validity_score}%
                        </span>
                      </div>
                      <div className="p-2.5 rounded-lg bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800">
                        <span className="text-zinc-500 uppercase block font-semibold text-[10px]">Consistency</span>
                        <span className="font-bold text-sm text-zinc-800 dark:text-zinc-200">
                          {selectedDetail.quality_report.consistency_score}%
                        </span>
                      </div>
                    </div>

                    {/* Deductions Evidence */}
                    {selectedDetail.quality_report.deductions_evidence && selectedDetail.quality_report.deductions_evidence.length > 0 && (
                      <div className="space-y-1.5 pt-2">
                        <span className="text-xs font-semibold text-zinc-700 dark:text-zinc-300 block">
                          Score Evidence & Audited Findings:
                        </span>
                        <div className="space-y-1 text-xs">
                          {selectedDetail.quality_report.deductions_evidence.map((ev, i) => (
                            <div
                              key={i}
                              className={cn(
                                'p-2 rounded-lg flex items-start gap-2',
                                ev.impact === 'positive'
                                  ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300'
                                  : 'bg-amber-500/10 text-amber-700 dark:text-amber-300',
                              )}
                            >
                              <span className="font-bold">{ev.dimension}:</span>
                              <span>{ev.message}</span>
                              <span className="ml-auto font-mono text-[10px] opacity-80">{ev.score_effect}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Column Profiling Breakdown */}
                <div className="space-y-3">
                  <h3 className="font-bold text-sm text-zinc-900 dark:text-zinc-100">
                    Column Profiles & Statistical Summaries
                  </h3>
                  <div className="border border-zinc-200 dark:border-zinc-800 rounded-xl overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead>
                        <tr className="border-b border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-800/60 uppercase font-semibold text-zinc-500">
                          <th className="p-3">Column Name</th>
                          <th className="p-3">Inferred Type</th>
                          <th className="p-3">Missing (Null)</th>
                          <th className="p-3">Unique</th>
                          <th className="p-3">Min / Max</th>
                          <th className="p-3">Mean / Median</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
                        {selectedDetail.column_profiles.map((col) => (
                          <tr key={col.id} className="hover:bg-zinc-50/50 dark:hover:bg-zinc-800/30">
                            <td className="p-3 font-semibold text-zinc-900 dark:text-zinc-100">
                              {col.column_name}
                            </td>
                            <td className="p-3 font-mono text-zinc-600 dark:text-zinc-400">
                              {col.data_type}
                            </td>
                            <td className="p-3">
                              <span
                                className={cn(
                                  'font-semibold',
                                  col.null_count > 0 ? 'text-amber-500' : 'text-emerald-500',
                                )}
                              >
                                {col.null_count} ({col.null_percentage}%)
                              </span>
                            </td>
                            <td className="p-3 text-zinc-700 dark:text-zinc-300">
                              {col.unique_count.toLocaleString()}
                            </td>
                            <td className="p-3 font-mono text-zinc-600 dark:text-zinc-400">
                              {col.is_numeric && col.min_value != null && col.max_value != null
                                ? `${col.min_value} / ${col.max_value}`
                                : '—'}
                            </td>
                            <td className="p-3 font-mono text-zinc-600 dark:text-zinc-400">
                              {col.is_numeric && col.mean_value != null
                                ? `${col.mean_value.toFixed(1)} / ${col.median_value != null ? col.median_value.toFixed(1) : '—'}`
                                : '—'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Detected Anomalies */}
                {selectedDetail.anomalies && selectedDetail.anomalies.length > 0 && (
                  <div className="space-y-3">
                    <h3 className="font-bold text-sm text-zinc-900 dark:text-zinc-100 flex items-center gap-1.5">
                      <AlertTriangle size={16} className="text-rose-500" />
                      Detected Statistical Outliers & Anomalies ({selectedDetail.anomalies.length})
                    </h3>
                    <div className="space-y-2">
                      {selectedDetail.anomalies.map((anom) => (
                        <div
                          key={anom.id}
                          className="p-3 rounded-lg border border-rose-200 dark:border-rose-900/50 bg-rose-50/40 dark:bg-rose-950/20 text-xs space-y-1"
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-bold text-rose-700 dark:text-rose-300 uppercase tracking-wider text-[10px]">
                              {anom.anomaly_type.replace('_', ' ')} · Severity: {anom.severity}
                            </span>
                            <span className="text-zinc-500 font-mono text-[11px]">
                              Column: {anom.column_name}
                            </span>
                          </div>
                          <p className="text-zinc-700 dark:text-zinc-300">
                            {anom.description}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Footer */}
              <div className="pt-3 border-t border-zinc-200 dark:border-zinc-800 flex justify-end">
                <button
                  onClick={() => setSelectedDetail(null)}
                  className="px-4 py-2 text-xs font-semibold rounded-lg bg-zinc-100 dark:bg-zinc-800 hover:bg-zinc-200 dark:hover:bg-zinc-700 text-zinc-800 dark:text-zinc-200 transition-colors"
                >
                  Close
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
