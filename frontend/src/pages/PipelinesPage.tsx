import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Activity,
  Play,
  Square,
  Plus,
  Radio,
  Wifi,
  WifiOff,
  AlertTriangle,
  Zap,
  CheckCircle2,
  Clock,
  Trash2,
  ShieldAlert,
  Sliders,
  ChevronDown,
  Loader2,
  X,
  Sparkles,
  Heart,
  Check,
  CheckCheck,
  RefreshCw,
  Info,
} from 'lucide-react';
import type {
  BackendPipelineSummary,
  BackendPipelineDetail,
  PipelineMetricSnapshot,
  PipelineAnomaly,
  PipelineAlert,
  SimulatorStatus,
  PipelineTelemetryUpdate,
} from '../types';
import {
  fetchPipelines,
  fetchPipelineDetail,
  createPipeline,
  startPipeline,
  stopPipeline,
  deletePipeline,
  fetchPipelineMetrics,
  fetchPipelineAlerts,
  startSimulator,
  stopSimulator,
  fetchSimulatorStatus,
  acknowledgeAlert,
  resolveAlert,
  checkPipelineHealth,
  getWebSocketUrl,
} from '../services/api';
import { useAuth } from '../context/AuthContext';

function cn(...classes: (string | false | null | undefined)[]) {
  return classes.filter(Boolean).join(' ');
}

type ConnectionStatus = 'connected' | 'connecting' | 'reconnecting' | 'disconnected' | 'fallback_polling';

export default function PipelinesPage() {
  const { user } = useAuth();
  const isViewer = user?.role === 'viewer';
  const [pipelines, setPipelines] = useState<BackendPipelineSummary[]>([]);
  const [selectedPipelineId, setSelectedPipelineId] = useState<string>('');
  const [pipelineDetail, setPipelineDetail] = useState<BackendPipelineDetail | null>(null);

  // Live WebSocket & Telemetry State
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('disconnected');
  const [metricSnapshots, setMetricSnapshots] = useState<PipelineMetricSnapshot[]>([]);
  const [liveAnomalies, setLiveAnomalies] = useState<PipelineAnomaly[]>([]);
  const [liveViolations, setLiveViolations] = useState<Array<{ record_sample: any; error: any }>>([]);
  const [liveAlerts, setLiveAlerts] = useState<PipelineAlert[]>([]);
  const [filterUnresolved, setFilterUnresolved] = useState<boolean>(false);
  const [expandedAlertIds, setExpandedAlertIds] = useState<Set<string>>(new Set());
  const [activeTab, setActiveTab] = useState<'metrics' | 'anomalies' | 'violations' | 'alerts'>('metrics');

  // Simulator State
  const [simulatorStatus, setSimulatorStatus] = useState<SimulatorStatus | null>(null);
  const [simulatorRate, setSimulatorRate] = useState<number>(5);
  const [simulatorBatch, setSimulatorBatch] = useState<number>(1);
  const [showSimulatorModal, setShowSimulatorModal] = useState<boolean>(false);

  // Create Pipeline Modal State
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [newPipelineName, setNewPipelineName] = useState<string>('');
  const [newPipelineSource, setNewPipelineSource] = useState<string>('Kafka - events-topic');
  const [newPipelineDest, setNewPipelineDest] = useState<string>('Snowflake - events_warehouse');
  const [newFields, setNewFields] = useState<Array<{ name: string; type: string; required: boolean }>>([
    { name: 'event_id', type: 'string', required: true },
    { name: 'user_id', type: 'string', required: true },
    { name: 'amount', type: 'float', required: true },
    { name: 'currency', type: 'string', required: false },
  ]);

  // Loading & Error States
  const [loadingPipelines, setLoadingPipelines] = useState<boolean>(true);
  const [actionLoading, setActionLoading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // WebSocket Ref & Reconnect Management
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef<number>(0);
  const reconnectTimeoutRef = useRef<any>(null);
  const pollingIntervalRef = useRef<any>(null);

  // ── 1. Load Initial Pipelines List ──────────────────────────────────────────

  const loadPipelines = useCallback(async () => {
    try {
      setLoadingPipelines(true);
      const data = await fetchPipelines();
      setPipelines(data);
      if (data.length > 0 && !selectedPipelineId) {
        setSelectedPipelineId(data[0].id);
      }
    } catch (err: any) {
      console.error('Failed to load pipelines:', err);
      setErrorMessage(err.message || 'Failed to connect to backend.');
    } finally {
      setLoadingPipelines(false);
    }
  }, [selectedPipelineId]);

  useEffect(() => {
    loadPipelines();
  }, [loadPipelines]);

  // ── 2. Load Selected Pipeline Details & Simulator Status ────────────────────

  const loadPipelineDetailData = useCallback(async (id: string) => {
    if (!id) return;
    try {
      const detail = await fetchPipelineDetail(id);
      setPipelineDetail(detail);
      setMetricSnapshots(detail.metric_snapshots || []);
      setLiveAnomalies(detail.anomalies || []);
      setLiveAlerts(detail.alerts || []);

      const sim = await fetchSimulatorStatus(id);
      setSimulatorStatus(sim);
    } catch (err: any) {
      console.error('Error fetching pipeline detail:', err);
    }
  }, []);

  useEffect(() => {
    if (selectedPipelineId) {
      loadPipelineDetailData(selectedPipelineId);
    }
  }, [selectedPipelineId, loadPipelineDetailData]);

  // ── 3. WebSocket Connection with Exponential Backoff & REST Fallback ────────

  const connectWebSocket = useCallback((pipelineId: string) => {
    if (!pipelineId) return;

    // Clean up any existing connection
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
    }

    setConnectionStatus('connecting');

    const wsUrl = getWebSocketUrl(`/api/v1/pipelines/${pipelineId}/ws`);

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnectionStatus('connected');
        reconnectAttemptsRef.current = 0;
        setErrorMessage(null);
      };

      ws.onmessage = (event) => {
        try {
          const packet: PipelineTelemetryUpdate = JSON.parse(event.data);

          if (packet.type === 'initial_state' || packet.type === 'telemetry_update') {
            if (packet.pipeline) {
              setPipelineDetail((prev) => {
                if (!prev) return prev;
                return {
                  ...prev,
                  ...packet.pipeline!,
                };
              });
              setPipelines((prev) =>
                prev.map((p) => (p.id === packet.pipeline!.id ? { ...p, ...packet.pipeline! } : p))
              );
            }

            if (packet.latest_snapshot) {
              setMetricSnapshots((prev) => {
                const updated = [...prev, packet.latest_snapshot!];
                return updated.slice(-30); // Keep last 30 for chart
              });
            } else if (packet.recent_snapshots) {
              setMetricSnapshots(packet.recent_snapshots.slice(-30));
            }

            if (packet.recent_anomalies && packet.recent_anomalies.length > 0) {
              setLiveAnomalies((prev) => [...packet.recent_anomalies!, ...prev].slice(0, 50));
            }

            if (packet.recent_violations && packet.recent_violations.length > 0) {
              setLiveViolations((prev) => [...packet.recent_violations!, ...prev].slice(0, 50));
            }

            if (packet.recent_alerts && packet.recent_alerts.length > 0) {
              setLiveAlerts(packet.recent_alerts);
            }

            if (typeof packet.is_simulator_running === 'boolean') {
              setSimulatorStatus((prev) => (prev ? { ...prev, is_running: packet.is_simulator_running! } : null));
            }
          } else if (packet.type === 'alert_created') {
            if (packet.alert) {
              const newAlert = packet.alert;
              setLiveAlerts((prev) => {
                const idx = prev.findIndex((a) => a.id === newAlert.id);
                if (idx >= 0) {
                  const copy = [...prev];
                  copy[idx] = newAlert;
                  return copy;
                }
                return [newAlert, ...prev];
              });
            }
          } else if (packet.type === 'alert_updated') {
            if (packet.alert) {
              const updatedAlert = packet.alert;
              setLiveAlerts((prev) =>
                prev.map((a) => (a.id === updatedAlert.id ? { ...a, ...updatedAlert } : a))
              );
            }
          } else if (packet.type === 'status_change') {
            if (packet.status) {
              setPipelineDetail((prev) => (prev ? { ...prev, status: packet.status as any } : null));
              setPipelines((prev) =>
                prev.map((p) => (p.id === pipelineId ? { ...p, status: packet.status as any } : p))
              );
            }
          }
        } catch (e) {
          console.error('Failed to parse WebSocket packet:', e);
        }
      };

      ws.onerror = () => {
        // Will trigger onclose
      };

      ws.onclose = (event) => {
        setConnectionStatus('disconnected');

        // Only attempt reconnect if not intentionally closed
        if (event.code !== 1000 && event.code !== 4004) {
          if (reconnectAttemptsRef.current < 5) {
            const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 10000);
            reconnectAttemptsRef.current += 1;
            setConnectionStatus('reconnecting');
            reconnectTimeoutRef.current = setTimeout(() => {
              connectWebSocket(pipelineId);
            }, delay);
          } else {
            // Graceful fallback to REST polling every 5s
            setConnectionStatus('fallback_polling');
            pollingIntervalRef.current = setInterval(async () => {
              try {
                const metrics = await fetchPipelineMetrics(pipelineId, 30);
                setMetricSnapshots(metrics);
                const detail = await fetchPipelineDetail(pipelineId);
                setPipelineDetail(detail);
              } catch {}
            }, 5000);
          }
        }
      };
    } catch {
      setConnectionStatus('fallback_polling');
    }
  }, []);

  useEffect(() => {
    if (selectedPipelineId) {
      connectWebSocket(selectedPipelineId);
    }
    return () => {
      if (wsRef.current) {
        wsRef.current.close(1000, 'Page navigation / unmount');
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
    };
  }, [selectedPipelineId, connectWebSocket]);

  // ── 4. Lifecycle Actions (Start/Stop Pipeline & Simulator) ───────────────────

  const handleTogglePipeline = async () => {
    if (!selectedPipelineId || !pipelineDetail) return;
    setActionLoading(true);
    try {
      if (pipelineDetail.status === 'active') {
        const updated = await stopPipeline(selectedPipelineId);
        setPipelineDetail((prev) => (prev ? { ...prev, status: updated.status } : null));
      } else {
        const updated = await startPipeline(selectedPipelineId);
        setPipelineDetail((prev) => (prev ? { ...prev, status: updated.status } : null));
      }
      await loadPipelines();
    } catch (err: any) {
      setErrorMessage(err.message || 'Action failed.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleToggleSimulator = async () => {
    if (!selectedPipelineId) return;
    setActionLoading(true);
    try {
      if (simulatorStatus?.is_running) {
        const res = await stopSimulator(selectedPipelineId);
        setSimulatorStatus(res);
      } else {
        const res = await startSimulator(selectedPipelineId, {
          rate_records_per_sec: simulatorRate,
          batch_size: simulatorBatch,
          anomaly_rate: 0.05,
          schema_violation_rate: 0.03,
          duplicate_rate: 0.02,
        });
        setSimulatorStatus(res);
        setShowSimulatorModal(false);
      }
    } catch (err: any) {
      setErrorMessage(err.message || 'Simulator toggle failed.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleDeletePipeline = async () => {
    if (!selectedPipelineId || !pipelineDetail) return;
    if (!window.confirm(`Are you sure you want to delete pipeline "${pipelineDetail.name}"?`)) {
      return;
    }
    try {
      await deletePipeline(selectedPipelineId);
      setSelectedPipelineId('');
      setPipelineDetail(null);
      await loadPipelines();
    } catch (err: any) {
      setErrorMessage(err.message || 'Delete failed.');
    }
  };

  const handleCreatePipelineSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newPipelineName.trim()) return;

    try {
      setActionLoading(true);
      const created = await createPipeline({
        name: newPipelineName.trim(),
        source: newPipelineSource,
        destination: newPipelineDest,
        schedule: 'Real-time Continuous',
        schema_definition: {
          fields: newFields,
          strict: false,
        },
      });
      setShowCreateModal(false);
      setNewPipelineName('');
      await loadPipelines();
      setSelectedPipelineId(created.id);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to create pipeline.');
    } finally {
      setActionLoading(false);
    }
  };

  // ── 5. Alert Management & Health Audit Handlers ───────────────────────────

  const toggleAlertExpanded = (alertId: string) => {
    setExpandedAlertIds((prev) => {
      const next = new Set(prev);
      if (next.has(alertId)) next.delete(alertId);
      else next.add(alertId);
      return next;
    });
  };

  const handleAcknowledgeAlert = async (alertId: string) => {
    try {
      setActionLoading(true);
      const updated = await acknowledgeAlert(alertId);
      setLiveAlerts((prev) => prev.map((a) => (a.id === alertId ? updated : a)));
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to acknowledge alert.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleResolveAlert = async (alertId: string) => {
    try {
      setActionLoading(true);
      const updated = await resolveAlert(alertId);
      setLiveAlerts((prev) => prev.map((a) => (a.id === alertId ? updated : a)));
      if (selectedPipelineId) {
        const detail = await fetchPipelineDetail(selectedPipelineId);
        setPipelineDetail(detail);
      }
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to resolve alert.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleRunHealthCheck = async () => {
    if (!selectedPipelineId) return;
    try {
      setActionLoading(true);
      const res = await checkPipelineHealth(selectedPipelineId);
      setPipelineDetail((prev) => (prev ? { ...prev, health_score: res.health_score } : null));
      const alerts = await fetchPipelineAlerts(selectedPipelineId);
      setLiveAlerts(alerts);
    } catch (err: any) {
      setErrorMessage(err.message || 'Health audit failed.');
    } finally {
      setActionLoading(false);
    }
  };

  // ── Helpers ─────────────────────────────────────────────────────────────────

  const formatChartTime = (iso: string) => {
    try {
      const d = new Date(iso);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch {
      return iso;
    }
  };

  return (
    <div className="p-4 md:p-8 max-w-7xl mx-auto space-y-6 min-h-screen">
      {/* Header & Controls Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-zinc-200 dark:border-zinc-800/80 pb-5">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-indigo-500/10 text-indigo-500 border border-indigo-500/20">
              <Activity size={22} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl md:text-2xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
                  Live Pipeline Monitor
                </h1>
                <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                  Real-time Telemetry
                </span>
              </div>
              <p className="text-xs text-zinc-500 dark:text-zinc-400">
                Continuous event stream ingestion, live throughput, schema validation, and 3σ outlier observability.
              </p>
            </div>
          </div>
        </div>

        {/* Global Action Buttons */}
        <div className="flex items-center gap-2.5">
          {!isViewer && (
            <button
              onClick={() => setShowCreateModal(true)}
              className="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white transition-colors shadow-sm"
            >
              <Plus size={15} />
              Create Pipeline
            </button>
          )}
          {isViewer && (
            <span className="px-2.5 py-1 rounded-lg bg-zinc-100 dark:bg-zinc-800 text-[11px] text-zinc-500 dark:text-zinc-400 border border-zinc-200 dark:border-zinc-700">
              Viewer (Read-Only)
            </span>
          )}
        </div>
      </div>

      {/* Pipeline Selector & Live Connection Telemetry Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-2xl bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 shadow-sm">
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-xs font-semibold text-zinc-500 dark:text-zinc-400">Pipeline:</span>
          <div className="relative min-w-[240px]">
            <select
              value={selectedPipelineId}
              onChange={(e) => setSelectedPipelineId(e.target.value)}
              disabled={loadingPipelines || pipelines.length === 0}
              className="w-full appearance-none px-3.5 py-1.5 pr-8 text-xs font-medium rounded-xl border bg-zinc-50 dark:bg-zinc-800/80 border-zinc-200 dark:border-zinc-700 text-zinc-800 dark:text-zinc-200 focus:outline-none focus:border-indigo-500"
            >
              {pipelines.length === 0 ? (
                <option value="">No pipelines registered</option>
              ) : (
                pipelines.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({p.status.toUpperCase()})
                  </option>
                ))
              )}
            </select>
            <ChevronDown size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-400 pointer-events-none" />
          </div>

          {pipelineDetail && (
            <div className="flex items-center gap-2">
              <span
                className={cn(
                  'px-2.5 py-0.5 rounded-full text-[11px] font-bold uppercase border capitalize',
                  pipelineDetail.status === 'active'
                    ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20'
                    : pipelineDetail.status === 'degraded'
                    ? 'bg-amber-500/10 text-amber-500 border-amber-500/20'
                    : 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20'
                )}
              >
                {pipelineDetail.status}
              </span>
              <span
                className={cn(
                  'px-2.5 py-0.5 rounded-full text-[11px] font-bold border flex items-center gap-1',
                  (pipelineDetail.health_score ?? 100) >= 80
                    ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20'
                    : (pipelineDetail.health_score ?? 100) >= 50
                    ? 'bg-amber-500/10 text-amber-500 border-amber-500/20'
                    : 'bg-rose-500/10 text-rose-500 border-rose-500/20'
                )}
              >
                <Heart size={11} />
                Health: {(pipelineDetail.health_score ?? 100).toFixed(0)}%
              </span>
              <span className="text-xs text-zinc-400">
                {pipelineDetail.source} → {pipelineDetail.destination}
              </span>
            </div>
          )}
        </div>

        {/* Live Status Indicators & Controls */}
        <div className="flex items-center gap-2">
          {/* WebSocket Connection Pill */}
          <div
            className={cn(
              'flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium border',
              connectionStatus === 'connected'
                ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20'
                : connectionStatus === 'reconnecting' || connectionStatus === 'connecting'
                ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20'
                : connectionStatus === 'fallback_polling'
                ? 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20'
                : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-500 border-zinc-300 dark:border-zinc-700'
            )}
          >
            {connectionStatus === 'connected' ? (
              <>
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
                </span>
                <span>Live WebSocket</span>
              </>
            ) : connectionStatus === 'reconnecting' ? (
              <>
                <Loader2 size={12} className="animate-spin text-amber-500" />
                <span>Reconnecting...</span>
              </>
            ) : connectionStatus === 'fallback_polling' ? (
              <>
                <Wifi size={12} className="text-blue-500" />
                <span>REST Polling Fallback</span>
              </>
            ) : (
              <>
                <WifiOff size={12} />
                <span>Disconnected</span>
              </>
            )}
          </div>

          {/* Simulator Toggle Button */}
          {selectedPipelineId && !isViewer && (
            <button
              onClick={() => {
                if (simulatorStatus?.is_running) {
                  handleToggleSimulator();
                } else {
                  setShowSimulatorModal(true);
                }
              }}
              disabled={actionLoading}
              className={cn(
                'flex items-center gap-1.5 px-3 py-1 text-xs font-semibold rounded-lg border transition-all',
                simulatorStatus?.is_running
                  ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/30 animate-pulse'
                  : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 border-zinc-200 dark:border-zinc-700 hover:border-indigo-500'
              )}
            >
              <Radio size={13} className={simulatorStatus?.is_running ? 'text-amber-500' : 'text-zinc-400'} />
              <span>{simulatorStatus?.is_running ? 'Simulator Active' : 'Run Simulator'}</span>
            </button>
          )}

          {/* Pipeline Start/Stop Button */}
          {pipelineDetail && !isViewer && (
            <button
              onClick={handleTogglePipeline}
              disabled={actionLoading}
              className={cn(
                'flex items-center gap-1.5 px-3 py-1 text-xs font-semibold rounded-lg border transition-colors',
                pipelineDetail.status === 'active'
                  ? 'bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 border-zinc-200 dark:border-zinc-700 hover:text-rose-500'
                  : 'bg-emerald-600 hover:bg-emerald-500 text-white border-transparent'
              )}
            >
              {pipelineDetail.status === 'active' ? (
                <>
                  <Square size={12} />
                  Stop
                </>
              ) : (
                <>
                  <Play size={12} />
                  Start
                </>
              )}
            </button>
          )}

          {pipelineDetail && !isViewer && (
            <button
              onClick={handleDeletePipeline}
              title="Delete pipeline"
              className="p-1.5 rounded-lg text-zinc-400 hover:text-rose-500 hover:bg-rose-500/10 transition-colors"
            >
              <Trash2 size={15} />
            </button>
          )}
        </div>
      </div>

      {/* Error Banner */}
      {errorMessage && (
        <div className="flex items-center justify-between p-3 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/60 text-xs text-rose-800 dark:text-rose-300">
          <div className="flex items-center gap-2">
            <AlertTriangle size={15} className="text-rose-500 flex-shrink-0" />
            <span>{errorMessage}</span>
          </div>
          <button onClick={() => setErrorMessage(null)} className="text-xs underline hover:no-underline">
            Dismiss
          </button>
        </div>
      )}

      {/* Live Observability Telemetry Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-4 flex items-center gap-3.5 shadow-sm">
          <div
            className={cn(
              'p-2.5 rounded-xl',
              (pipelineDetail?.health_score ?? 100) >= 80
                ? 'bg-emerald-500/10 text-emerald-500'
                : (pipelineDetail?.health_score ?? 100) >= 50
                ? 'bg-amber-500/10 text-amber-500'
                : 'bg-rose-500/10 text-rose-500'
            )}
          >
            <Heart size={20} />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <p className="text-[11px] font-medium uppercase tracking-wider text-zinc-400">Health Index</p>
              <button
                onClick={handleRunHealthCheck}
                disabled={actionLoading}
                title="Audit pipeline health & inactivity now"
                className="text-zinc-400 hover:text-indigo-500 transition-colors"
              >
                <RefreshCw size={11} className={actionLoading ? 'animate-spin' : ''} />
              </button>
            </div>
            <p
              className={cn(
                'text-2xl font-bold mt-0.5',
                (pipelineDetail?.health_score ?? 100) >= 80
                  ? 'text-emerald-500'
                  : (pipelineDetail?.health_score ?? 100) >= 50
                  ? 'text-amber-500'
                  : 'text-rose-500'
              )}
            >
              {(pipelineDetail?.health_score ?? 100).toFixed(1)}%
            </p>
            <span className="text-[10px] text-zinc-400">
              {(pipelineDetail?.health_score ?? 100) >= 80
                ? 'Optimal operational state'
                : (pipelineDetail?.health_score ?? 100) >= 50
                ? 'Degraded - review alerts'
                : 'Critical health warning'}
            </span>
          </div>
        </div>

        <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-4 flex items-center gap-3.5 shadow-sm">
          <div className="p-2.5 rounded-xl bg-indigo-500/10 text-indigo-500">
            <Zap size={20} />
          </div>
          <div>
            <p className="text-[11px] font-medium uppercase tracking-wider text-zinc-400">Total Ingested</p>
            <p className="text-2xl font-bold text-zinc-900 dark:text-zinc-100 mt-0.5">
              {(pipelineDetail?.total_records_ingested ?? 0).toLocaleString()}
            </p>
            <span className="text-[10px] text-zinc-400">
              {(pipelineDetail?.total_records_processed ?? 0).toLocaleString()} accepted
            </span>
          </div>
        </div>

        <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-4 flex items-center gap-3.5 shadow-sm">
          <div className="p-2.5 rounded-xl bg-blue-500/10 text-blue-500 relative">
            <Activity size={20} />
            {pipelineDetail?.status === 'active' && (
              <span className="absolute top-1 right-1 flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500" />
              </span>
            )}
          </div>
          <div>
            <p className="text-[11px] font-medium uppercase tracking-wider text-zinc-400">Live Throughput</p>
            <p className="text-2xl font-bold text-blue-500 mt-0.5">
              {(pipelineDetail?.current_throughput_rps ?? 0).toFixed(1)} <span className="text-xs font-normal">rec/s</span>
            </p>
            <span className="text-[10px] text-zinc-400">Real-time ingestion rate</span>
          </div>
        </div>

        <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-4 flex items-center gap-3.5 shadow-sm">
          <div className="p-2.5 rounded-xl bg-emerald-500/10 text-emerald-500">
            <CheckCircle2 size={20} />
          </div>
          <div>
            <p className="text-[11px] font-medium uppercase tracking-wider text-zinc-400">Success Rate</p>
            <p className="text-2xl font-bold text-emerald-500 mt-0.5">
              {(pipelineDetail?.success_rate ?? 100).toFixed(1)}%
            </p>
            <span className="text-[10px] text-zinc-400">
              {(pipelineDetail?.total_records_failed ?? 0).toLocaleString()} failed records
            </span>
          </div>
        </div>

        <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-4 flex items-center gap-3.5 shadow-sm">
          <div className="p-2.5 rounded-xl bg-purple-500/10 text-purple-500">
            <Clock size={20} />
          </div>
          <div>
            <p className="text-[11px] font-medium uppercase tracking-wider text-zinc-400">Avg Latency</p>
            <p className="text-2xl font-bold text-purple-500 mt-0.5">
              {(pipelineDetail?.avg_latency_ms ?? 0).toFixed(2)} <span className="text-xs font-normal">ms</span>
            </p>
            <span className="text-[10px] text-zinc-400">Processing & validation duration</span>
          </div>
        </div>
      </div>

      {/* Real-time Time Series Telemetry Chart */}
      <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-5 shadow-sm">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
          <div>
            <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
              Live Stream Throughput & Processing Latency
              <span className="flex h-2 w-2 relative">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500" />
              </span>
            </h2>
            <p className="text-xs text-zinc-400">
              Real-time telemetry snapshots broadcasted via WebSocket every batch interval.
            </p>
          </div>
        </div>

        {metricSnapshots.length === 0 ? (
          <div className="h-56 flex flex-col items-center justify-center text-center text-zinc-400 border border-dashed border-zinc-200 dark:border-zinc-800 rounded-xl">
            <Activity size={32} className="text-zinc-400 mb-2" />
            <p className="text-xs">Waiting for incoming stream events...</p>
            <p className="text-[11px] text-zinc-500 mt-1">Start the simulator or ingest JSON records to watch live charts.</p>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={metricSnapshots} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
              <defs>
                <linearGradient id="throughputGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.0} />
                </linearGradient>
                <linearGradient id="latencyGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#a855f7" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#a855f7" stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(113,113,122,0.15)" />
              <XAxis dataKey="timestamp" tickFormatter={formatChartTime} tick={{ fontSize: 10, fill: '#a1a1aa' }} />
              <YAxis yAxisId="left" tick={{ fontSize: 10, fill: '#a1a1aa' }} />
              <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 10, fill: '#a1a1aa' }} />
              <Tooltip
                contentStyle={{
                  background: '#18181b',
                  border: '1px solid #3f3f46',
                  borderRadius: '8px',
                  fontSize: '12px',
                  color: '#f4f4f5',
                }}
                labelFormatter={(label) => formatChartTime(String(label))}
              />
              <Area
                yAxisId="left"
                type="monotone"
                dataKey="throughput_rps"
                name="Throughput (rec/s)"
                stroke="#3b82f6"
                strokeWidth={2}
                fillOpacity={1}
                fill="url(#throughputGrad)"
              />
              <Area
                yAxisId="right"
                type="monotone"
                dataKey="avg_latency_ms"
                name="Latency (ms)"
                stroke="#a855f7"
                strokeWidth={2}
                fillOpacity={1}
                fill="url(#latencyGrad)"
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Stream Observability Tabs: Anomalies, Schema Violations, Alerts, Schema */}
      <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl overflow-hidden shadow-sm">
        <div className="flex items-center gap-1 p-2 border-b border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950/50">
          <button
            onClick={() => setActiveTab('metrics')}
            className={cn(
              'px-3.5 py-1.5 text-xs font-semibold rounded-xl transition-colors',
              activeTab === 'metrics'
                ? 'bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 shadow-xs'
                : 'text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200'
            )}
          >
            Configured Schema ({pipelineDetail?.schema_definition?.fields?.length ?? 0} fields)
          </button>
          <button
            onClick={() => setActiveTab('anomalies')}
            className={cn(
              'px-3.5 py-1.5 text-xs font-semibold rounded-xl transition-colors flex items-center gap-1.5',
              activeTab === 'anomalies'
                ? 'bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 shadow-xs'
                : 'text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200'
            )}
          >
            <ShieldAlert size={14} className="text-rose-500" />
            <span>Statistical Anomalies ({liveAnomalies.length})</span>
          </button>
          <button
            onClick={() => setActiveTab('violations')}
            className={cn(
              'px-3.5 py-1.5 text-xs font-semibold rounded-xl transition-colors flex items-center gap-1.5',
              activeTab === 'violations'
                ? 'bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 shadow-xs'
                : 'text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200'
            )}
          >
            <AlertTriangle size={14} className="text-amber-500" />
            <span>Schema Violations ({liveViolations.length})</span>
          </button>
          <button
            onClick={() => setActiveTab('alerts')}
            className={cn(
              'px-3.5 py-1.5 text-xs font-semibold rounded-xl transition-colors flex items-center gap-1.5',
              activeTab === 'alerts'
                ? 'bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 shadow-xs'
                : 'text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200'
            )}
          >
            <AlertTriangle
              size={14}
              className={liveAlerts.some((a) => !a.resolved) ? 'text-rose-500' : 'text-zinc-400'}
            />
            <span>Pipeline Alerts ({liveAlerts.length})</span>
            {liveAlerts.filter((a) => !a.resolved).length > 0 && (
              <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-rose-500 text-white font-bold">
                {liveAlerts.filter((a) => !a.resolved).length}
              </span>
            )}
          </button>
        </div>

        <div className="p-5">
          {activeTab === 'metrics' && (
            <div className="space-y-3">
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-zinc-200 dark:border-zinc-800 text-left text-zinc-400">
                      <th className="pb-2 font-medium">Field Name</th>
                      <th className="pb-2 font-medium">Data Type</th>
                      <th className="pb-2 font-medium">Constraint</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
                    {pipelineDetail?.schema_definition?.fields?.map((f, i) => (
                      <tr key={i} className="hover:bg-zinc-50 dark:hover:bg-zinc-800/40">
                        <td className="py-2.5 font-mono text-zinc-800 dark:text-zinc-200 font-semibold">{f.name}</td>
                        <td className="py-2.5">
                          <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-zinc-100 dark:bg-zinc-800 text-indigo-500">
                            {f.type}
                          </span>
                        </td>
                        <td className="py-2.5">
                          {f.required ? (
                            <span className="text-rose-500 font-semibold">REQUIRED (Non-null)</span>
                          ) : (
                            <span className="text-zinc-400">Optional</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {activeTab === 'anomalies' && (
            <div className="space-y-3">
              {liveAnomalies.length === 0 ? (
                <div className="p-8 text-center text-xs text-zinc-400">
                  Zero statistical outliers detected. All numerical stream values fall within normal 3σ variance boundaries.
                </div>
              ) : (
                liveAnomalies.map((anom, i) => (
                  <div
                    key={anom.id || i}
                    className="p-3.5 rounded-xl border border-rose-200 dark:border-rose-900/50 bg-rose-50/50 dark:bg-rose-950/20 text-xs flex items-start gap-3"
                  >
                    <ShieldAlert size={16} className="text-rose-500 mt-0.5 flex-shrink-0" />
                    <div className="flex-1 space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-rose-900 dark:text-rose-200">
                          [{anom.severity.toUpperCase()}] {anom.column_name} ({anom.anomaly_type})
                        </span>
                        <span className="text-[10px] text-zinc-400">
                          {new Date(anom.detected_at).toLocaleTimeString()}
                        </span>
                      </div>
                      <p className="text-zinc-600 dark:text-zinc-300">{anom.description}</p>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}

          {activeTab === 'violations' && (
            <div className="space-y-3">
              {liveViolations.length === 0 ? (
                <div className="p-8 text-center text-xs text-zinc-400">
                  No schema violations recorded. All ingested events match the defined pipeline schema.
                </div>
              ) : (
                liveViolations.map((v, i) => (
                  <div
                    key={i}
                    className="p-3.5 rounded-xl border border-amber-200 dark:border-amber-900/50 bg-amber-50/50 dark:bg-amber-950/20 text-xs flex items-start gap-3"
                  >
                    <AlertTriangle size={16} className="text-amber-500 mt-0.5 flex-shrink-0" />
                    <div className="flex-1 space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-amber-900 dark:text-amber-200">
                          {v.error?.code || 'SCHEMA_VIOLATION'}: Field `{v.error?.field}`
                        </span>
                      </div>
                      <p className="text-zinc-600 dark:text-zinc-300">{v.error?.message}</p>
                      <pre className="p-2 rounded bg-white dark:bg-zinc-900 font-mono text-[10px] text-zinc-600 dark:text-zinc-400 overflow-x-auto">
                        {JSON.stringify(v.record_sample, null, 2)}
                      </pre>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}

          {activeTab === 'alerts' && (
            <div className="space-y-4">
              {/* Alert Filters and Health Audit Header */}
              <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-xl bg-zinc-50 dark:bg-zinc-950/60 border border-zinc-200 dark:border-zinc-800 text-xs">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-zinc-700 dark:text-zinc-300">Filter:</span>
                  <button
                    onClick={() => setFilterUnresolved(false)}
                    className={cn(
                      'px-2.5 py-1 rounded-lg font-medium transition-colors',
                      !filterUnresolved
                        ? 'bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 shadow-xs border border-zinc-200 dark:border-zinc-700'
                        : 'text-zinc-400 hover:text-zinc-200'
                    )}
                  >
                    All Alerts ({liveAlerts.length})
                  </button>
                  <button
                    onClick={() => setFilterUnresolved(true)}
                    className={cn(
                      'px-2.5 py-1 rounded-lg font-medium transition-colors',
                      filterUnresolved
                        ? 'bg-rose-500/10 text-rose-500 border border-rose-500/20'
                        : 'text-zinc-400 hover:text-zinc-200'
                    )}
                  >
                    Unresolved Only ({liveAlerts.filter((a) => !a.resolved).length})
                  </button>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={handleRunHealthCheck}
                    disabled={actionLoading}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-semibold bg-zinc-100 dark:bg-zinc-800 hover:bg-zinc-200 dark:hover:bg-zinc-700 text-zinc-700 dark:text-zinc-300 border border-zinc-300 dark:border-zinc-700 transition-colors"
                  >
                    <RefreshCw size={12} className={actionLoading ? 'animate-spin' : ''} />
                    Audit Inactivity & Health
                  </button>
                </div>
              </div>

              {/* Alert List */}
              {(() => {
                const displayedAlerts = filterUnresolved
                  ? liveAlerts.filter((a) => !a.resolved)
                  : liveAlerts;

                if (displayedAlerts.length === 0) {
                  return (
                    <div className="p-8 text-center text-xs text-zinc-400 border border-dashed border-zinc-200 dark:border-zinc-800 rounded-xl">
                      {filterUnresolved
                        ? 'Zero active unresolved alerts. Pipeline health is 100% stable.'
                        : 'No alerts recorded for this pipeline.'}
                    </div>
                  );
                }

                return displayedAlerts.map((alert) => {
                  const isExpanded = expandedAlertIds.has(alert.id);
                  const isCritical = alert.severity === 'critical';
                  const isWarning = alert.severity === 'warning';
                  const isError = alert.severity === 'error';

                  return (
                    <div
                      key={alert.id}
                      className={cn(
                        'p-4 rounded-xl border text-xs space-y-3 transition-colors',
                        alert.resolved
                          ? 'bg-zinc-50/50 dark:bg-zinc-950/40 border-zinc-200 dark:border-zinc-800 opacity-75'
                          : isCritical
                          ? 'bg-rose-50/40 dark:bg-rose-950/20 border-rose-200 dark:border-rose-900/60'
                          : isError
                          ? 'bg-rose-50/30 dark:bg-rose-950/15 border-rose-200 dark:border-rose-900/50'
                          : 'bg-amber-50/30 dark:bg-amber-950/15 border-amber-200 dark:border-amber-900/50'
                      )}
                    >
                      {/* Alert Header Row */}
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <AlertTriangle
                            size={16}
                            className={cn(
                              'flex-shrink-0',
                              alert.resolved
                                ? 'text-zinc-400'
                                : isCritical || isError
                                ? 'text-rose-500'
                                : 'text-amber-500'
                            )}
                          />
                          <span className="font-bold text-zinc-900 dark:text-zinc-100 text-sm">
                            {alert.title}
                          </span>
                          <span
                            className={cn(
                              'px-2 py-0.5 rounded-full text-[10px] font-bold uppercase border',
                              alert.resolved
                                ? 'bg-zinc-100 dark:bg-zinc-800 text-zinc-400 border-zinc-300 dark:border-zinc-700'
                                : isCritical
                                ? 'bg-rose-500/10 text-rose-500 border-rose-500/20'
                                : isError
                                ? 'bg-rose-500/10 text-rose-500 border-rose-500/20'
                                : isWarning
                                ? 'bg-amber-500/10 text-amber-500 border-amber-500/20'
                                : 'bg-blue-500/10 text-blue-500 border-blue-500/20'
                            )}
                          >
                            {alert.severity}
                          </span>
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-zinc-100 dark:bg-zinc-800 text-zinc-500 border border-zinc-200 dark:border-zinc-700">
                            {alert.alert_type}
                          </span>
                        </div>

                        {/* Status Badges & Occurrence Counter */}
                        <div className="flex items-center gap-2">
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-indigo-500/10 text-indigo-500 border border-indigo-500/20">
                            Occurrences: {alert.occurrence_count}
                          </span>

                          {alert.resolved ? (
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-500 border border-emerald-500/20 flex items-center gap-1">
                              <CheckCheck size={11} /> Resolved
                            </span>
                          ) : alert.acknowledged ? (
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-500/10 text-blue-500 border border-blue-500/20 flex items-center gap-1">
                              <Check size={11} /> Acknowledged
                            </span>
                          ) : (
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/10 text-amber-500 border border-amber-500/20">
                              Active / Unresolved
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Alert Description */}
                      <p className="text-zinc-700 dark:text-zinc-300">{alert.description}</p>

                      {/* Timestamp Footnote & Evidence Toggle */}
                      <div className="flex flex-wrap items-center justify-between gap-3 text-[11px] text-zinc-400 pt-1 border-t border-zinc-200/50 dark:border-zinc-800/50">
                        <div className="flex items-center gap-3">
                          <span>First: {new Date(alert.first_occurred_at).toLocaleTimeString()}</span>
                          <span>Last: {new Date(alert.last_occurred_at).toLocaleTimeString()}</span>
                          {alert.acknowledged_at && (
                            <span className="text-blue-400">
                              Ack: {new Date(alert.acknowledged_at).toLocaleTimeString()}
                            </span>
                          )}
                          {alert.resolved_at && (
                            <span className="text-emerald-400">
                              Resolved: {new Date(alert.resolved_at).toLocaleTimeString()}
                            </span>
                          )}
                        </div>

                        {/* Action Buttons */}
                        <div className="flex items-center gap-2">
                          {alert.evidence && Object.keys(alert.evidence).length > 0 && (
                            <button
                              onClick={() => toggleAlertExpanded(alert.id)}
                              className="px-2.5 py-1 rounded text-[11px] font-medium bg-zinc-100 dark:bg-zinc-800 hover:bg-zinc-200 dark:hover:bg-zinc-700 text-zinc-700 dark:text-zinc-300 transition-colors flex items-center gap-1"
                            >
                              <Info size={11} />
                              {isExpanded ? 'Hide Evidence' : 'View Evidence'}
                            </button>
                          )}

                          {!alert.acknowledged && !alert.resolved && (
                            <button
                              onClick={() => handleAcknowledgeAlert(alert.id)}
                              disabled={actionLoading}
                              className="px-2.5 py-1 rounded text-[11px] font-semibold bg-blue-600 hover:bg-blue-500 text-white transition-colors flex items-center gap-1"
                            >
                              <Check size={11} />
                              Acknowledge
                            </button>
                          )}

                          {!alert.resolved && (
                            <button
                              onClick={() => handleResolveAlert(alert.id)}
                              disabled={actionLoading}
                              className="px-2.5 py-1 rounded text-[11px] font-semibold bg-emerald-600 hover:bg-emerald-500 text-white transition-colors flex items-center gap-1"
                            >
                              <CheckCheck size={11} />
                              Resolve Alert
                            </button>
                          )}
                        </div>
                      </div>

                      {/* Collapsible Evidence Inspector */}
                      {isExpanded && alert.evidence && (
                        <div className="p-3 rounded-xl bg-zinc-900 border border-zinc-800 font-mono text-[11px] text-zinc-300 space-y-1">
                          <p className="text-zinc-500 text-[10px] uppercase font-bold tracking-wider">
                            Structured Diagnostic Evidence:
                          </p>
                          <pre className="overflow-x-auto text-emerald-400">
                            {JSON.stringify(alert.evidence, null, 2)}
                          </pre>
                        </div>
                      )}
                    </div>
                  );
                });
              })()}
            </div>
          )}
        </div>
      </div>

      {/* Simulator Control Modal */}
      <AnimatePresence>
        {showSimulatorModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="w-full max-w-md bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-6 shadow-xl space-y-4"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-indigo-600 dark:text-indigo-400 font-bold text-sm">
                  <Sliders size={18} />
                  <span>Configure Stream Simulator</span>
                </div>
                <button onClick={() => setShowSimulatorModal(false)} className="text-zinc-400 hover:text-zinc-600">
                  <X size={18} />
                </button>
              </div>

              <div className="p-3 rounded-xl bg-indigo-50/60 dark:bg-indigo-950/30 border border-indigo-200/80 dark:border-indigo-800/50 text-[11px] text-indigo-900 dark:text-indigo-200">
                <strong>Development Simulator:</strong> Emits synthetic JSON records tagged with{' '}
                <code className="font-mono">is_simulated: true</code> to evaluate real-time throughput and anomaly detection without external producers.
              </div>

              <div className="space-y-3 text-xs">
                <div>
                  <label className="block text-zinc-600 dark:text-zinc-400 mb-1">
                    Ingestion Rate: <strong>{simulatorRate} records/sec</strong>
                  </label>
                  <input
                    type="range"
                    min="1"
                    max="30"
                    value={simulatorRate}
                    onChange={(e) => setSimulatorRate(Number(e.target.value))}
                    className="w-full accent-indigo-600"
                  />
                </div>

                <div>
                  <label className="block text-zinc-600 dark:text-zinc-400 mb-1">
                    Batch Size: <strong>{simulatorBatch} per tick</strong>
                  </label>
                  <input
                    type="range"
                    min="1"
                    max="10"
                    value={simulatorBatch}
                    onChange={(e) => setSimulatorBatch(Number(e.target.value))}
                    className="w-full accent-indigo-600"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  onClick={() => setShowSimulatorModal(false)}
                  className="px-3.5 py-1.5 text-xs rounded-xl border border-zinc-200 dark:border-zinc-700 text-zinc-600 dark:text-zinc-400"
                >
                  Cancel
                </button>
                <button
                  onClick={handleToggleSimulator}
                  disabled={actionLoading}
                  className="px-4 py-1.5 text-xs font-semibold rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white"
                >
                  Start Stream
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Create Pipeline Modal */}
      <AnimatePresence>
        {showCreateModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="w-full max-w-lg bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-6 shadow-xl space-y-4 max-h-[90vh] overflow-y-auto"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-zinc-900 dark:text-zinc-100 font-bold text-base">
                  <Sparkles size={18} className="text-indigo-500" />
                  <span>Register Data Pipeline</span>
                </div>
                <button onClick={() => setShowCreateModal(false)} className="text-zinc-400 hover:text-zinc-600">
                  <X size={18} />
                </button>
              </div>

              <form onSubmit={handleCreatePipelineSubmit} className="space-y-4 text-xs">
                <div>
                  <label className="block text-zinc-600 dark:text-zinc-400 mb-1 font-medium">Pipeline Name</label>
                  <input
                    type="text"
                    required
                    value={newPipelineName}
                    onChange={(e) => setNewPipelineName(e.target.value)}
                    placeholder="e.g. User Activity Stream"
                    className="w-full px-3 py-2 rounded-xl border bg-zinc-50 dark:bg-zinc-800/80 border-zinc-200 dark:border-zinc-700 text-zinc-900 dark:text-zinc-100"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-zinc-600 dark:text-zinc-400 mb-1 font-medium">Source</label>
                    <input
                      type="text"
                      value={newPipelineSource}
                      onChange={(e) => setNewPipelineSource(e.target.value)}
                      className="w-full px-3 py-2 rounded-xl border bg-zinc-50 dark:bg-zinc-800/80 border-zinc-200 dark:border-zinc-700 text-zinc-900 dark:text-zinc-100"
                    />
                  </div>
                  <div>
                    <label className="block text-zinc-600 dark:text-zinc-400 mb-1 font-medium">Destination</label>
                    <input
                      type="text"
                      value={newPipelineDest}
                      onChange={(e) => setNewPipelineDest(e.target.value)}
                      className="w-full px-3 py-2 rounded-xl border bg-zinc-50 dark:bg-zinc-800/80 border-zinc-200 dark:border-zinc-700 text-zinc-900 dark:text-zinc-100"
                    />
                  </div>
                </div>

                {/* Schema Field Builder */}
                <div className="space-y-2 pt-2 border-t border-zinc-200 dark:border-zinc-800">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-zinc-700 dark:text-zinc-300">Expected Schema Fields</span>
                    <button
                      type="button"
                      onClick={() => setNewFields([...newFields, { name: '', type: 'string', required: false }])}
                      className="text-indigo-500 hover:text-indigo-400 font-semibold"
                    >
                      + Add Field
                    </button>
                  </div>

                  <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                    {newFields.map((field, idx) => (
                      <div key={idx} className="flex items-center gap-2">
                        <input
                          type="text"
                          required
                          placeholder="field_name"
                          value={field.name}
                          onChange={(e) => {
                            const updated = [...newFields];
                            updated[idx].name = e.target.value;
                            setNewFields(updated);
                          }}
                          className="flex-1 px-2.5 py-1.5 rounded-lg border bg-zinc-50 dark:bg-zinc-800/80 border-zinc-200 dark:border-zinc-700 text-zinc-900 dark:text-zinc-100 font-mono text-xs"
                        />
                        <select
                          value={field.type}
                          onChange={(e) => {
                            const updated = [...newFields];
                            updated[idx].type = e.target.value;
                            setNewFields(updated);
                          }}
                          className="px-2 py-1.5 rounded-lg border bg-zinc-50 dark:bg-zinc-800/80 border-zinc-200 dark:border-zinc-700 text-zinc-800 dark:text-zinc-200 text-xs"
                        >
                          <option value="string">string</option>
                          <option value="integer">integer</option>
                          <option value="float">float</option>
                          <option value="boolean">boolean</option>
                          <option value="datetime">datetime</option>
                        </select>
                        <label className="flex items-center gap-1 text-[11px] text-zinc-500">
                          <input
                            type="checkbox"
                            checked={field.required}
                            onChange={(e) => {
                              const updated = [...newFields];
                              updated[idx].required = e.target.checked;
                              setNewFields(updated);
                            }}
                            className="accent-indigo-600 rounded"
                          />
                          Req
                        </label>
                        {newFields.length > 1 && (
                          <button
                            type="button"
                            onClick={() => setNewFields(newFields.filter((_, i) => i !== idx))}
                            className="text-zinc-400 hover:text-rose-500"
                          >
                            <X size={14} />
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                </div>

                <div className="flex justify-end gap-2 pt-3 border-t border-zinc-200 dark:border-zinc-800">
                  <button
                    type="button"
                    onClick={() => setShowCreateModal(false)}
                    className="px-3.5 py-1.5 text-xs rounded-xl border border-zinc-200 dark:border-zinc-700 text-zinc-600 dark:text-zinc-400"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={actionLoading || !newPipelineName.trim()}
                    className="px-4 py-1.5 text-xs font-semibold rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white disabled:opacity-40"
                  >
                    Register Pipeline
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
