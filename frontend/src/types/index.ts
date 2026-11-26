export type Theme = 'light' | 'dark';

export interface Dataset {
  id: string;
  name: string;
  source: string;
  status: 'healthy' | 'warning' | 'critical' | 'processing';
  qualityScore: number;
  records: number;
  lastUpdated: string;
  size: string;
  tags: string[];
  owner: string;
  isReal?: boolean;
}

export interface ColumnProfile {
  id: string;
  column_name: string;
  data_type: string;
  total_count: number;
  null_count: number;
  null_percentage: number;
  unique_count: number;
  is_numeric: boolean;
  min_value?: number | null;
  max_value?: number | null;
  mean_value?: number | null;
  median_value?: number | null;
  std_value?: number | null;
  top_values?: { value: string; count: number; percentage: number }[] | null;
}

export interface QualityReportEvidence {
  dimension: string;
  impact: 'positive' | 'negative';
  score_effect: string;
  message: string;
}

export interface QualityReport {
  id: string;
  overall_score: number;
  completeness_score: number;
  uniqueness_score: number;
  validity_score: number;
  consistency_score: number;
  duplicate_rows_count: number;
  duplicate_rows_percentage: number;
  total_cells: number;
  null_cells: number;
  deductions_evidence?: QualityReportEvidence[] | null;
  created_at: string;
}

export interface IngestedAnomaly {
  id: string;
  column_name: string;
  anomaly_type: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  affected_rows: number;
  description: string;
  details?: Record<string, any> | null;
  detected_at: string;
}

export interface BackendDatasetDetail {
  id: string;
  name: string;
  original_filename: string;
  file_type: string;
  file_size_bytes: number;
  row_count: number;
  column_count: number;
  status: 'healthy' | 'warning' | 'critical' | 'processing';
  quality_score: number;
  created_at: string;
  updated_at: string;
  column_profiles: ColumnProfile[];
  quality_report?: QualityReport | null;
  anomalies?: IngestedAnomaly[];
}

export interface BackendOverviewSummary {
  total_datasets: number;
  average_quality_score: number;
  total_records_monitored: number;
  total_anomalies: number;
  critical_anomalies: number;
  status_breakdown: {
    healthy: number;
    warning: number;
    critical: number;
  };
  recent_activities: Activity[];
}

export interface Anomaly {
  id: string;
  datasetId: string;
  datasetName: string;
  type: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  status: 'open' | 'investigating' | 'resolved';
  detectedAt: string;
  description: string;
  affectedRecords: number;
  column: string;
}

export interface Pipeline {
  id: string;
  name: string;
  status: 'running' | 'success' | 'failed' | 'paused';
  lastRun: string;
  nextRun: string;
  successRate: number;
  avgDuration: string;
  source: string;
  destination: string;
  schedule: string;
  recentRuns: PipelineRun[];
}

export interface PipelineRun {
  id: string;
  startedAt: string;
  duration: string;
  status: 'success' | 'failed' | 'running';
  recordsProcessed: number;
}

export interface QualityMetric {
  name: string;
  score: number;
  trend: 'up' | 'down' | 'stable';
  change: number;
}

export interface Alert {
  id: string;
  title: string;
  description: string;
  severity: 'info' | 'warning' | 'error' | 'critical';
  timestamp: string;
  datasetName?: string;
  read: boolean;
}

export interface Activity {
  id: string;
  type: 'upload' | 'scan' | 'alert' | 'pipeline' | 'report';
  title: string;
  description: string;
  timestamp: string;
  user?: string;
}

export interface Report {
  id: string;
  name: string;
  type: 'quality' | 'anomaly' | 'pipeline' | 'custom';
  createdAt: string;
  status: 'ready' | 'generating' | 'failed';
  size: string;
  format: 'PDF' | 'CSV' | 'JSON';
}

export interface NavItem {
  id: string;
  label: string;
  icon: string;
  path: string;
}

export interface CopilotMetric {
  label: string;
  value: string;
  status?: 'good' | 'warn' | 'bad';
}

export interface CopilotQueryResponse {
  answer: string;
  metrics?: CopilotMetric[];
  recommendations?: string[];
  dataset_id: string;
  dataset_name: string;
  model: string;
  is_fallback: boolean;
  evidence_used?: string[];
}

export interface CopilotMessage {
  id: string;
  dataset_id: string;
  role: 'user' | 'assistant';
  content: string;
  recommendations?: string[];
  metrics?: CopilotMetric[];
  model_used?: string;
  created_at: string;
}

export interface CopilotSuggestionsResponse {
  dataset_id: string;
  dataset_name: string;
  suggestions: string[];
}

export interface BackendPipelineSummary {
  id: string;
  name: string;
  description?: string | null;
  source: string;
  destination: string;
  status: 'active' | 'stopped' | 'degraded' | 'error';
  health_score: number;
  schedule: string;
  total_records_ingested: number;
  total_records_processed: number;
  total_records_failed: number;
  success_rate: number;
  avg_latency_ms: number;
  current_throughput_rps: number;
  last_ingestion_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface PipelineMetricSnapshot {
  id: string;
  pipeline_id: string;
  timestamp: string;
  records_in_interval: number;
  records_processed: number;
  records_failed: number;
  throughput_rps: number;
  avg_latency_ms: number;
  error_rate: number;
  status: string;
}

export interface PipelineAlert {
  id: string;
  pipeline_id: string;
  severity: 'info' | 'warning' | 'error' | 'critical' | 'low' | 'medium' | 'high';
  alert_type: string;
  title: string;
  description: string;
  dedup_key: string;
  occurrence_count: number;
  first_occurred_at: string;
  last_occurred_at: string;
  resolved: boolean;
  resolved_at?: string | null;
  acknowledged: boolean;
  acknowledged_at?: string | null;
  evidence?: Record<string, any> | null;
  created_at?: string;
}

export interface PipelineAnomaly {
  id: string;
  pipeline_id: string;
  column_name: string;
  anomaly_type: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  description: string;
  metric_value?: number | null;
  expected_range?: Record<string, any> | null;
  record_sample?: Record<string, any> | null;
  detected_at: string;
}

export interface BackendPipelineDetail extends BackendPipelineSummary {
  schema_definition: {
    fields: Array<{
      name: string;
      type: string;
      required?: boolean;
      description?: string;
    }>;
    strict?: boolean;
  };
  metric_snapshots: PipelineMetricSnapshot[];
  alerts: PipelineAlert[];
  anomalies: PipelineAnomaly[];
}

export interface SimulatorStatus {
  pipeline_id: string;
  is_running: boolean;
  rate_records_per_sec: number;
  batch_size: number;
  records_generated: number;
  started_at?: string | null;
  is_simulated: boolean;
}

export interface PipelineTelemetryUpdate {
  type: 'initial_state' | 'telemetry_update' | 'status_change' | 'alert_created' | 'alert_updated';
  pipeline_id: string;
  timestamp: string;
  pipeline?: BackendPipelineSummary;
  batch_summary?: {
    records_received: number;
    records_accepted: number;
    records_rejected: number;
    latency_ms: number;
  };
  recent_snapshots?: PipelineMetricSnapshot[];
  recent_anomalies?: PipelineAnomaly[];
  recent_alerts?: PipelineAlert[];
  recent_violations?: Array<{ record_sample: any; error: any }>;
  latest_snapshot?: PipelineMetricSnapshot;
  alert?: PipelineAlert;
  status?: string;
  is_simulator_running?: boolean;
}

export interface UserProfile {
  id: string;
  email: string;
  full_name?: string | null;
  role: 'admin' | 'data_engineer' | 'analyst' | 'viewer';
  is_active: boolean;
  default_organization_id?: string | null;
  active_organization_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  description?: string | null;
  is_active: boolean;
  role?: string;
  created_at: string;
  updated_at: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token?: string;
  token_type: string;
  expires_in: number;
}

export interface AuthResponse {
  tokens: AuthTokens;
  user: UserProfile;
  organization?: Organization | null;
}

export interface AuthState {
  user: UserProfile | null;
  organization: Organization | null;
  organizations: Organization[];
  isAuthenticated: boolean;
  isLoading: boolean;
}
