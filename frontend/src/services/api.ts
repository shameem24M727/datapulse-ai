import type {
  BackendDatasetDetail,
  BackendOverviewSummary,
  CopilotQueryResponse,
  CopilotSuggestionsResponse,
  CopilotMessage,
  BackendPipelineSummary,
  BackendPipelineDetail,
  PipelineMetricSnapshot,
  PipelineAlert,
  SimulatorStatus,
  UserProfile,
  Organization,
  AuthTokens,
} from '../types';

const BACKEND_URL = (
  import.meta.env.VITE_API_URL ||
  (import.meta.env.PROD ? 'https://datapulse-ai-backend.onrender.com' : '')
).replace(/\/+$/, '');

const API_BASE = BACKEND_URL ? `${BACKEND_URL}/api/v1` : '/api/v1';

export function getBackendBaseUrl(): string {
  return BACKEND_URL;
}

export function getWebSocketUrl(path: string): string {
  const token = getAccessToken();
  const tokenQuery = token ? `?token=${encodeURIComponent(token)}` : '';
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  if (BACKEND_URL) {
    const wsBase = BACKEND_URL.replace(/^http:/, 'ws:').replace(/^https:/, 'wss:');
    return `${wsBase}${cleanPath}${tokenQuery}`;
  }
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}${cleanPath}${tokenQuery}`;
}

// ── Token Storage & Authenticated Fetch Wrapper ──────────────────────────────

let inMemoryAccessToken: string | null = localStorage.getItem('datapulse_access_token');
let inMemoryRefreshToken: string | null = localStorage.getItem('datapulse_refresh_token');

export function getAccessToken(): string | null {
  return inMemoryAccessToken || localStorage.getItem('datapulse_access_token');
}

export function getRefreshToken(): string | null {
  return inMemoryRefreshToken || localStorage.getItem('datapulse_refresh_token');
}

export function setTokens(accessToken: string, refreshToken?: string | null) {
  inMemoryAccessToken = accessToken;
  localStorage.setItem('datapulse_access_token', accessToken);
  if (refreshToken) {
    inMemoryRefreshToken = refreshToken;
    localStorage.setItem('datapulse_refresh_token', refreshToken);
  }
}

export function clearTokens() {
  inMemoryAccessToken = null;
  inMemoryRefreshToken = null;
  localStorage.removeItem('datapulse_access_token');
  localStorage.removeItem('datapulse_refresh_token');
}

let refreshPromise: Promise<string | null> | null = null;

async function doRefreshToken(): Promise<string | null> {
  const rt = getRefreshToken();
  if (!rt) {
    clearTokens();
    return null;
  }
  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: rt }),
    });
    if (!res.ok) {
      clearTokens();
      return null;
    }
    const data: AuthTokens = await res.json();
    setTokens(data.access_token, data.refresh_token);
    return data.access_token;
  } catch {
    clearTokens();
    return null;
  } finally {
    refreshPromise = null;
  }
}

export async function authenticatedFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  let token = getAccessToken();
  const headers = new Headers(init?.headers || {});

  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  let res = await fetch(input, {
    ...init,
    headers,
  });

  // If 401 Unauthorized, attempt a single refresh
  if (res.status === 401 && getRefreshToken()) {
    if (!refreshPromise) {
      refreshPromise = doRefreshToken();
    }
    const newToken = await refreshPromise;
    if (newToken) {
      const retryHeaders = new Headers(init?.headers || {});
      retryHeaders.set('Authorization', `Bearer ${newToken}`);
      res = await fetch(input, {
        ...init,
        headers: retryHeaders,
      });
    }
  }

  return res;
}

// ── Authentication & Organization APIs ───────────────────────────────────────

export async function loginUser(email: string, password: string): Promise<AuthTokens> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });

  if (!res.ok) {
    let errMessage = 'Invalid credentials. Please try again.';
    try {
      const err = await res.json();
      errMessage = err.detail || errMessage;
    } catch {}
    throw new Error(errMessage);
  }

  const data: AuthTokens = await res.json();
  setTokens(data.access_token, data.refresh_token);
  return data;
}

export async function registerUser(payload: {
  email: string;
  password: string;
  full_name?: string;
  role?: string;
  organization_name?: string;
}): Promise<AuthTokens> {
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    let errMessage = 'Registration failed.';
    try {
      const err = await res.json();
      errMessage = err.detail || errMessage;
    } catch {}
    throw new Error(errMessage);
  }

  const data: AuthTokens = await res.json();
  setTokens(data.access_token, data.refresh_token);
  return data;
}

export async function logoutUser(): Promise<void> {
  const rt = getRefreshToken();
  try {
    await authenticatedFetch(`${API_BASE}/auth/logout`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: rt }),
    });
  } catch {
    // Continue cleanup even if server call fails
  } finally {
    clearTokens();
  }
}

export async function fetchCurrentUser(): Promise<UserProfile> {
  const res = await authenticatedFetch(`${API_BASE}/auth/me`);
  if (!res.ok) {
    throw new Error(`Failed to fetch current user: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchUserOrganizations(): Promise<Organization[]> {
  const res = await authenticatedFetch(`${API_BASE}/organizations/`);
  if (!res.ok) {
    throw new Error(`Failed to fetch organizations: ${res.statusText}`);
  }
  return res.json();
}

export async function switchOrganization(orgId: string): Promise<AuthTokens> {
  const res = await authenticatedFetch(`${API_BASE}/organizations/switch/${orgId}`, {
    method: 'POST',
  });
  if (!res.ok) {
    throw new Error(`Failed to switch organization: ${res.statusText}`);
  }
  const data: AuthTokens = await res.json();
  setTokens(data.access_token, data.refresh_token);
  return data;
}

export async function createOrganization(name: string, description?: string): Promise<Organization> {
  const res = await authenticatedFetch(`${API_BASE}/organizations/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, description }),
  });
  if (!res.ok) {
    let errMessage = 'Failed to create organization.';
    try {
      const err = await res.json();
      errMessage = err.detail || errMessage;
    } catch {}
    throw new Error(errMessage);
  }
  return res.json();
}

// ── Dataset APIs ─────────────────────────────────────────────────────────────

export async function uploadDatasetFile(file: File): Promise<BackendDatasetDetail> {
  const formData = new FormData();
  formData.append('file', file);

  const res = await authenticatedFetch(`${API_BASE}/datasets/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    let errMessage = 'Failed to upload dataset.';
    try {
      const errData = await res.json();
      errMessage = errData.detail || errMessage;
    } catch {
      errMessage = `Server error (${res.status} ${res.statusText})`;
    }
    throw new Error(errMessage);
  }

  return res.json();
}

export async function fetchIngestedDatasets(): Promise<BackendDatasetDetail[]> {
  const res = await authenticatedFetch(`${API_BASE}/datasets/`);
  if (!res.ok) {
    throw new Error(`Failed to fetch datasets: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchDatasetDetail(id: string): Promise<BackendDatasetDetail> {
  const res = await authenticatedFetch(`${API_BASE}/datasets/${id}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch dataset details for ID ${id}`);
  }
  return res.json();
}

export async function deleteIngestedDataset(id: string): Promise<{ message: string; id: string }> {
  const res = await authenticatedFetch(`${API_BASE}/datasets/${id}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    throw new Error(`Failed to delete dataset: ${res.statusText}`);
  }
  return res.json();
}

// ── Overview APIs ────────────────────────────────────────────────────────────

export async function fetchOverviewSummary(): Promise<BackendOverviewSummary> {
  const res = await authenticatedFetch(`${API_BASE}/overview/summary`);
  if (!res.ok) {
    throw new Error(`Failed to fetch overview summary: ${res.statusText}`);
  }
  return res.json();
}

// ── Copilot APIs ─────────────────────────────────────────────────────────────

export async function queryCopilot(datasetId: string, question: string): Promise<CopilotQueryResponse> {
  const res = await authenticatedFetch(`${API_BASE}/copilot/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dataset_id: datasetId, question }),
  });

  if (!res.ok) {
    let errMessage = 'Copilot query failed.';
    try {
      const errData = await res.json();
      errMessage = errData.detail || errMessage;
    } catch {
      errMessage = `Server error (${res.status} ${res.statusText})`;
    }
    throw new Error(errMessage);
  }

  return res.json();
}

export async function fetchCopilotSuggestions(datasetId: string): Promise<CopilotSuggestionsResponse> {
  const res = await authenticatedFetch(`${API_BASE}/copilot/suggestions/${datasetId}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch suggestions: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchCopilotHistory(datasetId: string): Promise<CopilotMessage[]> {
  const res = await authenticatedFetch(`${API_BASE}/copilot/history/${datasetId}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch chat history: ${res.statusText}`);
  }
  return res.json();
}

export async function clearCopilotHistory(datasetId: string): Promise<{ message: string; deleted_count: number }> {
  const res = await authenticatedFetch(`${API_BASE}/copilot/history/${datasetId}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    throw new Error(`Failed to clear history: ${res.statusText}`);
  }
  return res.json();
}

// ── Pipeline & Streaming Telemetry APIs ──────────────────────────────────────

export async function fetchPipelines(statusFilter?: string): Promise<BackendPipelineSummary[]> {
  const url = statusFilter
    ? `${API_BASE}/pipelines/?status=${encodeURIComponent(statusFilter)}`
    : `${API_BASE}/pipelines/`;
  const res = await authenticatedFetch(url);
  if (!res.ok) {
    throw new Error(`Failed to fetch pipelines: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchPipelineDetail(pipelineId: string): Promise<BackendPipelineDetail> {
  const res = await authenticatedFetch(`${API_BASE}/pipelines/${pipelineId}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch pipeline detail: ${res.statusText}`);
  }
  return res.json();
}

export async function createPipeline(payload: any): Promise<BackendPipelineSummary> {
  const res = await authenticatedFetch(`${API_BASE}/pipelines/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    let errMessage = 'Failed to create pipeline.';
    try {
      const err = await res.json();
      errMessage = err.detail || errMessage;
    } catch {}
    throw new Error(errMessage);
  }
  return res.json();
}

export async function startPipeline(pipelineId: string): Promise<BackendPipelineSummary> {
  const res = await authenticatedFetch(`${API_BASE}/pipelines/${pipelineId}/start`, {
    method: 'POST',
  });
  if (!res.ok) {
    throw new Error(`Failed to start pipeline: ${res.statusText}`);
  }
  return res.json();
}

export async function stopPipeline(pipelineId: string): Promise<BackendPipelineSummary> {
  const res = await authenticatedFetch(`${API_BASE}/pipelines/${pipelineId}/stop`, {
    method: 'POST',
  });
  if (!res.ok) {
    throw new Error(`Failed to stop pipeline: ${res.statusText}`);
  }
  return res.json();
}

export async function deletePipeline(pipelineId: string): Promise<{ message: string; id: string }> {
  const res = await authenticatedFetch(`${API_BASE}/pipelines/${pipelineId}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    throw new Error(`Failed to delete pipeline: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchPipelineMetrics(pipelineId: string, limit: number = 30): Promise<PipelineMetricSnapshot[]> {
  const res = await authenticatedFetch(`${API_BASE}/pipelines/${pipelineId}/metrics?limit=${limit}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch pipeline metrics: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchPipelineAlerts(pipelineId: string, unresolvedOnly: boolean = false): Promise<PipelineAlert[]> {
  const res = await authenticatedFetch(`${API_BASE}/pipelines/${pipelineId}/alerts?unresolved_only=${unresolvedOnly}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch pipeline alerts: ${res.statusText}`);
  }
  return res.json();
}

export async function startSimulator(pipelineId: string, config?: any): Promise<SimulatorStatus> {
  const res = await authenticatedFetch(`${API_BASE}/pipelines/${pipelineId}/simulator/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config || { rate_records_per_sec: 5.0, batch_size: 1 }),
  });
  if (!res.ok) {
    throw new Error(`Failed to start simulator: ${res.statusText}`);
  }
  return res.json();
}

export async function stopSimulator(pipelineId: string): Promise<SimulatorStatus> {
  const res = await authenticatedFetch(`${API_BASE}/pipelines/${pipelineId}/simulator/stop`, {
    method: 'POST',
  });
  if (!res.ok) {
    throw new Error(`Failed to stop simulator: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchSimulatorStatus(pipelineId: string): Promise<SimulatorStatus> {
  const res = await authenticatedFetch(`${API_BASE}/pipelines/${pipelineId}/simulator/status`);
  if (!res.ok) {
    throw new Error(`Failed to fetch simulator status: ${res.statusText}`);
  }
  return res.json();
}

export async function acknowledgeAlert(alertId: string): Promise<PipelineAlert> {
  const res = await authenticatedFetch(`${API_BASE}/pipelines/alerts/${alertId}/acknowledge`, {
    method: 'POST',
  });
  if (!res.ok) {
    throw new Error(`Failed to acknowledge alert: ${res.statusText}`);
  }
  return res.json();
}

export async function resolveAlert(alertId: string): Promise<PipelineAlert> {
  const res = await authenticatedFetch(`${API_BASE}/pipelines/alerts/${alertId}/resolve`, {
    method: 'POST',
  });
  if (!res.ok) {
    throw new Error(`Failed to resolve alert: ${res.statusText}`);
  }
  return res.json();
}

export async function checkPipelineHealth(pipelineId: string, maxInactiveSeconds: number = 600): Promise<{
  pipeline_id: string;
  name: string;
  status: string;
  health_score: number;
  success_rate: number;
  avg_latency_ms: number;
  last_ingestion_at: string | null;
}> {
  const res = await authenticatedFetch(`${API_BASE}/pipelines/${pipelineId}/health-check?max_inactive_seconds=${maxInactiveSeconds}`, {
    method: 'POST',
  });
  if (!res.ok) {
    throw new Error(`Failed to check pipeline health: ${res.statusText}`);
  }
  return res.json();
}
