import React, { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import {
  Sparkles,
  Send,
  User,
  Database,
  Trash2,
  AlertCircle,
  Lightbulb,
  CheckCircle2,
  Loader2,
  ChevronDown,
  FileSpreadsheet,
  FileText,
  ShieldAlert,
  RefreshCw,
} from 'lucide-react';
import type { BackendDatasetDetail, CopilotMessage, CopilotMetric } from '../types';
import {
  fetchIngestedDatasets,
  fetchDatasetDetail,
  fetchCopilotSuggestions,
  fetchCopilotHistory,
  clearCopilotHistory,
  queryCopilot,
} from '../services/api';

function cn(...classes: (string | false | null | undefined)[]) {
  return classes.filter(Boolean).join(' ');
}

// Lightweight, safe markdown formatter for assistant answers
function MarkdownContent({ content }: { content?: string | null }) {
  const safeContent = typeof content === 'string' ? content : String(content ?? '');
  const lines = safeContent.split('\n');

  return (
    <div className="space-y-2 text-sm leading-relaxed">
      {lines.map((line, idx) => {
        const trimmed = (line || '').trim();

        // Empty line
        if (!trimmed) {
          return <div key={idx} className="h-1" />;
        }

        // Headings (### or ##)
        if (trimmed.startsWith('### ')) {
          return (
            <h4
              key={idx}
              className="text-sm font-bold text-zinc-900 dark:text-zinc-100 pt-2 pb-1 border-b border-zinc-200/50 dark:border-zinc-800/50"
            >
              {formatInlineText(trimmed.replace('### ', ''))}
            </h4>
          );
        }
        if (trimmed.startsWith('## ')) {
          return (
            <h3 key={idx} className="text-base font-bold text-zinc-900 dark:text-zinc-100 pt-2 pb-1">
              {formatInlineText(trimmed.replace('## ', ''))}
            </h3>
          );
        }

        // Blockquote / Notes
        if (trimmed.startsWith('> ')) {
          return (
            <div
              key={idx}
              className="p-2.5 rounded-lg bg-zinc-100 dark:bg-zinc-800/60 border-l-4 border-indigo-500 text-xs text-zinc-600 dark:text-zinc-300 italic"
            >
              {formatInlineText(trimmed.replace('> ', ''))}
            </div>
          );
        }

        // Bullet points
        if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
          return (
            <div key={idx} className="flex items-start gap-2 text-xs md:text-sm text-zinc-700 dark:text-zinc-300 pl-2">
              <span className="text-indigo-500 font-bold mt-1">•</span>
              <span className="flex-1">{formatInlineText(trimmed.replace(/^[-*]\s+/, ''))}</span>
            </div>
          );
        }

        // Numbered list
        const numMatch = trimmed.match(/^(\d+)\.\s+(.*)/);
        if (numMatch) {
          return (
            <div key={idx} className="flex items-start gap-2 text-xs md:text-sm text-zinc-700 dark:text-zinc-300 pl-2">
              <span className="font-semibold text-indigo-500 text-xs mt-0.5">{numMatch[1]}.</span>
              <span className="flex-1">{formatInlineText(numMatch[2])}</span>
            </div>
          );
        }

        // Normal paragraph
        return (
          <p key={idx} className="text-xs md:text-sm text-zinc-800 dark:text-zinc-200">
            {formatInlineText(line)}
          </p>
        );
      })}
    </div>
  );
}

// Parses inline bold (**text**) and code (`text`)
function formatInlineText(text?: string | null): React.ReactNode[] {
  if (!text || typeof text !== 'string') return [];
  const parts = text.split(/(\*\*.*?\*\*|`.*?`)/g);

  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return (
        <strong key={i} className="font-semibold text-zinc-900 dark:text-zinc-100">
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return (
        <code
          key={i}
          className="px-1.5 py-0.5 rounded text-[11px] font-mono bg-zinc-100 dark:bg-zinc-800 text-indigo-600 dark:text-indigo-400 border border-zinc-200 dark:border-zinc-700"
        >
          {part.slice(1, -1)}
        </code>
      );
    }
    return part;
  });
}

export default function CopilotPage() {
  const [datasets, setDatasets] = useState<BackendDatasetDetail[]>([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState<string>('');
  const [selectedDataset, setSelectedDataset] = useState<BackendDatasetDetail | null>(null);

  const [messages, setMessages] = useState<CopilotMessage[]>([]);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [inputPrompt, setInputPrompt] = useState('');

  const [loadingDatasets, setLoadingDatasets] = useState<boolean>(true);
  const [loadingHistory, setLoadingHistory] = useState<boolean>(false);
  const [querying, setQuerying] = useState<boolean>(false);
  const [clearing, setClearing] = useState<boolean>(false);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, querying]);

  // Load datasets on mount
  const loadDatasets = async () => {
    setLoadingDatasets(true);
    setErrorBanner(null);
    try {
      const data = await fetchIngestedDatasets();
      const datasetList = Array.isArray(data) ? data : [];
      setDatasets(datasetList);
      if (datasetList.length > 0) {
        setSelectedDatasetId((prev) => (prev ? prev : datasetList[0].id));
        setSelectedDataset((prev) => (prev ? prev : datasetList[0]));
      } else {
        setSelectedDatasetId('');
        setSelectedDataset(null);
      }
    } catch (err: any) {
      console.error('Failed to load datasets for Copilot:', err);
      setErrorBanner(
        err?.message || 'Could not connect to FastAPI backend. Ensure the backend server is running.'
      );
    } finally {
      setLoadingDatasets(false);
    }
  };

  useEffect(() => {
    loadDatasets();
  }, []);

  // When selected dataset changes, load full detail, history & dynamic suggestions
  useEffect(() => {
    if (!selectedDatasetId) {
      setSelectedDataset(null);
      setMessages([]);
      setSuggestions([]);
      return;
    }

    const summary = datasets.find((d) => d.id === selectedDatasetId) || null;
    setSelectedDataset((prev) => (prev?.id === selectedDatasetId ? prev : summary));

    async function loadDatasetContext() {
      setLoadingHistory(true);
      setErrorBanner(null);
      try {
        // 1. Fetch full details (anomalies, column profiles, quality report)
        try {
          const detail = await fetchDatasetDetail(selectedDatasetId);
          if (detail && detail.id === selectedDatasetId) {
            setSelectedDataset(detail);
          }
        } catch (detailErr) {
          console.warn('Could not load detailed dataset info, using summary:', detailErr);
        }

        // 2. Fetch dynamic suggestions tailored to actual profiling & anomalies
        try {
          const sugRes = await fetchCopilotSuggestions(selectedDatasetId);
          setSuggestions(Array.isArray(sugRes?.suggestions) ? sugRes.suggestions : []);
        } catch (sugErr: any) {
          console.warn('Failed to load copilot suggestions:', sugErr);
          setSuggestions([]);
        }

        // 3. Fetch stored conversation history
        try {
          const histRes = await fetchCopilotHistory(selectedDatasetId);
          setMessages(Array.isArray(histRes) ? histRes : []);
        } catch (histErr: any) {
          console.warn('Failed to load copilot history:', histErr);
          setMessages([]);
        }
      } catch (err: any) {
        console.error('Failed to load copilot context:', err);
        setErrorBanner(err?.message || 'Failed to load conversation history for this dataset.');
      } finally {
        setLoadingHistory(false);
      }
    }

    loadDatasetContext();
  }, [selectedDatasetId, datasets]);

  const handleSend = async (questionText?: string) => {
    const questionToSend = (questionText || inputPrompt).trim();
    if (!questionToSend || !selectedDatasetId || querying) return;

    setErrorBanner(null);
    setInputPrompt('');

    // Optimistically add user message
    const tempUserMsg: CopilotMessage = {
      id: `temp-${Date.now()}`,
      dataset_id: selectedDatasetId,
      role: 'user',
      content: questionToSend,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);
    setQuerying(true);

    try {
      const response = await queryCopilot(selectedDatasetId, questionToSend);

      const assistantMsg: CopilotMessage = {
        id: `assist-${Date.now()}`,
        dataset_id: selectedDatasetId,
        role: 'assistant',
        content: response?.answer || 'Response generated without text content.',
        metrics: Array.isArray(response?.metrics) ? response.metrics : undefined,
        recommendations: Array.isArray(response?.recommendations) ? response.recommendations : undefined,
        model_used: response?.model,
        created_at: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      console.error('Query copilot error:', err);
      const friendlyError = err?.message || 'Failed to generate response. Please try again.';
      setErrorBanner(friendlyError);

      const assistantErrorMsg: CopilotMessage = {
        id: `error-${Date.now()}`,
        dataset_id: selectedDatasetId,
        role: 'assistant',
        content: `⚠️ **Unable to complete analysis**: ${friendlyError}\n\n*If Gemini API is not configured or unavailable, DataPulse grounded profiling fallback will assist.*`,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistantErrorMsg]);
    } finally {
      setQuerying(false);
    }
  };

  const handleClearHistory = async () => {
    if (!selectedDatasetId) return;
    if (!window.confirm('Are you sure you want to clear conversation history for this dataset?')) {
      return;
    }
    setClearing(true);
    try {
      await clearCopilotHistory(selectedDatasetId);
      setMessages([]);
    } catch (err: any) {
      console.error('Failed to clear history:', err);
      setErrorBanner(err?.message || 'Failed to clear history on backend.');
    } finally {
      setClearing(false);
    }
  };

  const qualityScore = Number(selectedDataset?.quality_score ?? 0);
  const rowCount = Number(selectedDataset?.row_count ?? 0);
  const columnCount = Number(selectedDataset?.column_count ?? 0);
  const anomaliesCount = Array.isArray(selectedDataset?.anomalies) ? selectedDataset.anomalies.length : 0;

  return (
    <div className="p-4 md:p-6 lg:p-8 max-w-5xl mx-auto h-full min-h-[500px] flex flex-col justify-between overflow-hidden">
      {/* Header & Dataset Observability Bar */}
      <div className="space-y-3 flex-shrink-0 mb-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-zinc-200 dark:border-zinc-800/80 pb-3">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-indigo-500/10 text-indigo-500 border border-indigo-500/20">
              <Sparkles size={22} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl md:text-2xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
                  DataPulse AI Copilot
                </h1>
                <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                  Active
                </span>
              </div>
              <p className="text-xs text-zinc-500 dark:text-zinc-400">
                Grounded conversational intelligence for data quality profiling, root causes, and pipeline remediation.
              </p>
            </div>
          </div>

          {/* Dataset Selector Dropdown & Actions */}
          <div className="flex items-center gap-2">
            <div className="relative min-w-[220px]">
              <select
                value={selectedDatasetId}
                onChange={(e) => setSelectedDatasetId(e.target.value)}
                disabled={loadingDatasets || datasets.length === 0}
                className={cn(
                  'w-full appearance-none px-3.5 py-2 pr-9 text-xs font-medium rounded-xl border transition-colors',
                  'bg-white dark:bg-zinc-900 border-zinc-200 dark:border-zinc-800 text-zinc-800 dark:text-zinc-200',
                  'focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500',
                  'disabled:opacity-50 cursor-pointer'
                )}
              >
                {datasets.length === 0 ? (
                  <option value="">No ingested datasets found</option>
                ) : (
                  datasets.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name} ({(d.row_count ?? 0).toLocaleString()} rows, {Number(d.quality_score ?? 0).toFixed(0)}%)
                    </option>
                  ))
                )}
              </select>
              <ChevronDown
                size={14}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-400 pointer-events-none"
              />
            </div>

            {selectedDatasetId && (
              <button
                onClick={handleClearHistory}
                disabled={clearing || messages.length === 0}
                title="Clear conversation history for this dataset"
                className="p-2 rounded-xl border border-zinc-200 dark:border-zinc-800 text-zinc-400 hover:text-rose-500 hover:border-rose-500/30 bg-white dark:bg-zinc-900 transition-colors disabled:opacity-40 cursor-pointer"
              >
                {clearing ? <Loader2 size={16} className="animate-spin" /> : <Trash2 size={16} />}
              </button>
            )}

            <button
              onClick={loadDatasets}
              disabled={loadingDatasets}
              title="Refresh datasets"
              className="p-2 rounded-xl border border-zinc-200 dark:border-zinc-800 text-zinc-400 hover:text-indigo-500 hover:border-indigo-500/30 bg-white dark:bg-zinc-900 transition-colors disabled:opacity-40 cursor-pointer"
            >
              <RefreshCw size={16} className={loadingDatasets ? 'animate-spin' : ''} />
            </button>
          </div>
        </div>

        {/* Selected Dataset Telemetry Pill Bar */}
        {selectedDataset && (
          <div className="flex flex-wrap items-center gap-2 p-2.5 rounded-xl bg-zinc-50 dark:bg-zinc-900/60 border border-zinc-200/80 dark:border-zinc-800 text-xs">
            <div className="flex items-center gap-1.5 font-semibold text-zinc-900 dark:text-zinc-100 pr-2 border-r border-zinc-200 dark:border-zinc-800">
              {selectedDataset.file_type?.toLowerCase() === 'xlsx' ? (
                <FileSpreadsheet size={15} className="text-emerald-500" />
              ) : (
                <FileText size={15} className="text-blue-500" />
              )}
              <span>{selectedDataset.name}</span>
            </div>

            <div className="flex items-center gap-1 text-zinc-600 dark:text-zinc-400">
              <span>Records:</span>
              <strong className="text-zinc-800 dark:text-zinc-200 font-semibold">
                {rowCount.toLocaleString()}
              </strong>
            </div>

            <div className="flex items-center gap-1 text-zinc-600 dark:text-zinc-400">
              <span>Columns:</span>
              <strong className="text-zinc-800 dark:text-zinc-200 font-semibold">
                {columnCount}
              </strong>
            </div>

            <div className="flex items-center gap-1.5 ml-auto">
              <span
                className={cn(
                  'px-2 py-0.5 rounded-md font-bold text-[11px] border',
                  qualityScore >= 85
                    ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20'
                    : qualityScore >= 60
                    ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20'
                    : 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20'
                )}
              >
                Health: {qualityScore.toFixed(1)}%
              </span>

              {anomaliesCount > 0 && (
                <span className="px-2 py-0.5 rounded-md font-bold text-[11px] bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20 flex items-center gap-1">
                  <ShieldAlert size={12} />
                  {anomaliesCount} Anomalies
                </span>
              )}
            </div>
          </div>
        )}

        {/* Error notification banner */}
        {errorBanner && (
          <div className="flex items-center gap-2 p-3 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/60 text-xs text-rose-800 dark:text-rose-300">
            <AlertCircle size={16} className="text-rose-600 flex-shrink-0" />
            <span className="flex-1">{errorBanner}</span>
            <button
              onClick={() => setErrorBanner(null)}
              className="text-xs font-semibold underline hover:no-underline ml-2 cursor-pointer"
            >
              Dismiss
            </button>
          </div>
        )}
      </div>

      {/* Messages Stream */}
      <div className="flex-1 min-h-0 overflow-y-auto space-y-4 pr-2 py-2">
        {loadingDatasets || loadingHistory ? (
          <div className="flex flex-col items-center justify-center h-48 text-zinc-400 gap-2.5">
            <Loader2 size={24} className="animate-spin text-indigo-500" />
            <p className="text-xs font-medium">Loading dataset intelligence context...</p>
          </div>
        ) : datasets.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-56 text-center border border-dashed border-zinc-200 dark:border-zinc-800 rounded-2xl p-6 bg-zinc-50/50 dark:bg-zinc-900/20">
            <Database size={36} className="text-zinc-400 mb-2" />
            <h3 className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">
              No Ingested Datasets Found
            </h3>
            <p className="text-xs text-zinc-500 dark:text-zinc-400 max-w-sm mt-1 mb-4">
              Upload a CSV or Excel dataset in the Datasets screen to activate AI Copilot analysis, root-cause investigation, and quality recommendations.
            </p>
          </div>
        ) : messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-56 text-center border border-dashed border-zinc-200 dark:border-zinc-800 rounded-2xl p-6 bg-zinc-50/50 dark:bg-zinc-900/30">
            <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 text-indigo-500 flex items-center justify-center mb-3">
              <Sparkles size={24} />
            </div>
            <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
              DataPulse Intelligence Copilot Ready
            </h3>
            <p className="text-xs text-zinc-500 dark:text-zinc-400 max-w-md mt-1 mb-4">
              Ask any question about <strong>{selectedDataset?.name || 'your dataset'}</strong>. The Copilot analyzes actual column profiles, quality score deductions, and detected statistical anomalies without hallucination.
            </p>
            {suggestions.length > 0 && (
              <div className="flex flex-wrap justify-center gap-2 max-w-lg">
                {suggestions.map((sug, i) => (
                  <button
                    key={i}
                    onClick={() => handleSend(sug)}
                    className="text-xs px-3 py-1.5 rounded-lg border border-indigo-200 dark:border-indigo-900/60 bg-indigo-50/60 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300 hover:bg-indigo-100 dark:hover:bg-indigo-900/60 transition-colors cursor-pointer"
                  >
                    {sug}
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          messages.map((msg) => (
            <motion.div
              key={msg.id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2 }}
              className={cn('flex gap-3', msg.role === 'user' ? 'justify-end' : 'justify-start')}
            >
              {msg.role === 'assistant' && (
                <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white flex-shrink-0 shadow-md shadow-indigo-600/20">
                  <Sparkles size={16} />
                </div>
              )}

              <div
                className={cn(
                  'max-w-2xl rounded-2xl p-4 text-sm leading-relaxed',
                  msg.role === 'user'
                    ? 'bg-indigo-600 text-white rounded-tr-none'
                    : 'bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800/90 text-zinc-800 dark:text-zinc-200 rounded-tl-none shadow-sm'
                )}
              >
                {msg.role === 'user' ? (
                  <div className="whitespace-pre-line text-sm">{msg.content}</div>
                ) : (
                  <MarkdownContent content={msg.content} />
                )}

                {/* Metric pills if available */}
                {Array.isArray(msg.metrics) && msg.metrics.length > 0 && (
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mt-3 pt-3 border-t border-zinc-100 dark:border-zinc-800">
                    {msg.metrics.map((m: CopilotMetric, i: number) => (
                      <div
                        key={i}
                        className="p-2 rounded-lg bg-zinc-50 dark:bg-zinc-800/60 border border-zinc-200/80 dark:border-zinc-700/60 text-xs"
                      >
                        <span className="text-[10px] text-zinc-500 uppercase block font-semibold">
                          {m.label}
                        </span>
                        <span
                          className={cn(
                            'font-bold',
                            m.status === 'bad'
                              ? 'text-rose-600 dark:text-rose-400'
                              : m.status === 'warn'
                              ? 'text-amber-600 dark:text-amber-400'
                              : 'text-zinc-900 dark:text-zinc-100'
                          )}
                        >
                          {m.value}
                        </span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Recommendations block */}
                {Array.isArray(msg.recommendations) && msg.recommendations.length > 0 && (
                  <div className="mt-3.5 pt-3 border-t border-zinc-100 dark:border-zinc-800/80 space-y-1.5">
                    <span className="text-xs font-semibold text-indigo-600 dark:text-indigo-400 flex items-center gap-1">
                      <Lightbulb size={13} /> Recommended Actions:
                    </span>
                    <ul className="space-y-1.5 text-xs text-zinc-600 dark:text-zinc-400">
                      {msg.recommendations.map((rec: string, i: number) => (
                        <li key={i} className="flex items-start gap-1.5">
                          <CheckCircle2 size={13} className="text-emerald-500 mt-0.5 flex-shrink-0" />
                          <span>{rec}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Timestamp & Model indicator */}
                <div className="flex items-center justify-between text-[10px] mt-2.5 pt-2 border-t border-zinc-100/50 dark:border-zinc-800/50 text-zinc-400">
                  <span>
                    {msg.model_used
                      ? `Generated via ${msg.model_used}`
                      : msg.role === 'assistant'
                      ? 'DataPulse Intelligence Engine'
                      : 'User Prompt'}
                  </span>
                  <span>
                    {msg.created_at
                      ? new Date(msg.created_at).toLocaleTimeString([], {
                          hour: '2-digit',
                          minute: '2-digit',
                        })
                      : ''}
                  </span>
                </div>
              </div>

              {msg.role === 'user' && (
                <div className="w-8 h-8 rounded-lg bg-zinc-200 dark:bg-zinc-800 flex items-center justify-center text-zinc-700 dark:text-zinc-300 flex-shrink-0">
                  <User size={16} />
                </div>
              )}
            </motion.div>
          ))
        )}

        {/* Querying pulse loader */}
        {querying && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex gap-3 justify-start"
          >
            <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white flex-shrink-0 shadow-md shadow-indigo-600/20">
              <Sparkles size={16} className="animate-spin" />
            </div>
            <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800/90 rounded-2xl rounded-tl-none p-3.5 shadow-sm text-xs text-zinc-500 dark:text-zinc-400 flex items-center gap-2">
              <Loader2 size={14} className="animate-spin text-indigo-500" />
              <span>Analyzing dataset profiling telemetry and synthesizing remediation advice...</span>
            </div>
          </motion.div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Footer: Dynamic Suggestion Chips & Input Bar */}
      <div className="pt-3 flex-shrink-0 space-y-2.5">
        {/* Dynamic Prompt Suggestions */}
        {suggestions.length > 0 && (
          <div className="flex items-center gap-2 overflow-x-auto pb-1 text-xs no-scrollbar">
            <span className="text-zinc-400 flex items-center gap-1 flex-shrink-0 font-medium">
              <Sparkles size={12} /> Suggested:
            </span>
            {suggestions.map((prompt, idx) => (
              <button
                key={idx}
                onClick={() => handleSend(prompt)}
                disabled={querying || !selectedDatasetId}
                className="whitespace-nowrap px-3 py-1.5 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 text-zinc-700 dark:text-zinc-300 hover:border-indigo-500 hover:text-indigo-500 text-xs transition-colors disabled:opacity-40 cursor-pointer"
              >
                {prompt}
              </button>
            ))}
          </div>
        )}

        {/* Text Input Bar */}
        <div className="relative flex items-center bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-1.5 shadow-sm focus-within:border-indigo-500 transition-colors">
          <input
            type="text"
            placeholder={
              selectedDataset
                ? `Ask DataPulse Copilot about ${selectedDataset.name} (e.g. root causes, missing values, quality)...`
                : 'Select an ingested dataset to start chatting...'
            }
            value={inputPrompt}
            onChange={(e) => setInputPrompt(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            disabled={querying || !selectedDatasetId}
            className="flex-1 bg-transparent px-3 py-2 text-sm text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 outline-none disabled:opacity-40"
          />
          <button
            onClick={() => handleSend()}
            disabled={!inputPrompt.trim() || querying || !selectedDatasetId}
            className="p-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:hover:bg-indigo-600 text-white transition-colors cursor-pointer"
          >
            {querying ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
          </button>
        </div>

        {/* Engine status footer */}
        <div className="flex items-center justify-between text-[11px] text-zinc-400 px-1">
          <span className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 inline-block animate-pulse" />
            Official Google Gemini API + DataPulse Grounded Engine
          </span>
          <span className="font-mono">DataPulse AI v0.3.0</span>
        </div>
      </div>
    </div>
  );
}
