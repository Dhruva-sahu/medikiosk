const BASE = '/api/v1';

function getToken(): string | null {
  return localStorage.getItem('swasthya_setu_token');
}

export function setToken(token: string) {
  localStorage.setItem('swasthya_setu_token', token);
}

export function clearToken() {
  localStorage.removeItem('swasthya_setu_token');
}

export function getStoredUser() {
  const raw = localStorage.getItem('swasthya_setu_user');
  return raw ? JSON.parse(raw) : null;
}

export function setStoredUser(user: any) {
  localStorage.setItem('swasthya_setu_user', JSON.stringify(user));
}

async function request<T = any>(
  path: string,
  opts: RequestInit = {},
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(opts.headers as Record<string, string> || {}),
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  // Don't set Content-Type for FormData
  if (!(opts.body instanceof FormData)) {
    headers['Content-Type'] = headers['Content-Type'] || 'application/json';
  }
  const res = await fetch(`${BASE}${path}`, { ...opts, headers });
  if (res.status === 401) {
    clearToken();
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || err.message || 'Request failed');
  }
  const json = await res.json();
  // Normalize: backend returns either {success, data} or raw Pydantic model
  if (json && typeof json === 'object' && 'success' in json && 'data' in json) {
    return json.data;
  }
  return json;
}

// Helper to extract data from potentially wrapped responses
function extractData(res: any): any {
  if (res && typeof res === 'object' && 'success' in res && 'data' in res) {
    return res.data;
  }
  return res;
}

export const api = {
  // Auth
  register: (data: any) =>
    request('/auth/register', { method: 'POST', body: JSON.stringify(data) }),
  login: (data: any) =>
    request('/auth/login', { method: 'POST', body: JSON.stringify(data) }),
  me: () => request('/auth/me'),

  // Consent
  grantConsent: (data: any) =>
    request('/consent', { method: 'POST', body: JSON.stringify(data) }),

  // Intake
  startIntake: (data: { language: string; mode: string }) =>
    request('/intake/start', { method: 'POST', body: JSON.stringify(data) }),
  getSession: (sessionId: string) =>
    request(`/intake/sessions/${sessionId}`),
  getNextQuestion: (sessionId: string) =>
    request(`/intake/sessions/${sessionId}/next-question`),
  submitAnswer: (sessionId: string, data: any) =>
    request(`/intake/sessions/${sessionId}/answer`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  submitSession: (sessionId: string, data: any = {}) =>
    request(`/intake/sessions/${sessionId}/submit`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // Documents
  uploadDocument: (file: File, sessionId?: string) => {
    const formData = new FormData();
    formData.append('file', file);
    if (sessionId) formData.append('session_id', sessionId);
    return request('/documents/upload', {
      method: 'POST',
      body: formData,
    });
  },
  myDocuments: () => request('/documents/mine'),

  // Speech
  transcribe: (audioBlob: Blob, language: string) => {
    const formData = new FormData();
    formData.append('audio', audioBlob);
    formData.append('language', language);
    return request('/speech/transcribe', { method: 'POST', body: formData });
  },
  synthesizeSpeech: async (text: string, language: string): Promise<Blob> => {
    const token = getToken();
    const formData = new FormData();
    formData.append('text', text);
    formData.append('language', language);
    const res = await fetch(`${BASE}/speech/synthesize`, {
      method: 'POST',
      body: formData,
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    return res.blob();
  },

  // Clinician
  dashboard: () => request('/clinician/dashboard'),
  queue: (priorityOnly?: boolean) =>
    request(`/clinician/queue${priorityOnly ? '?priority_only=true' : ''}`),
  getCase: (sessionId: string) =>
    request(`/clinician/case/${sessionId}`),
  updateCaseStatus: (sessionId: string, status: string) =>
    request(`/clinician/case/${sessionId}/status?status=${status}`, {
      method: 'POST',
    }),
  addNote: (sessionId: string, data: { note_type: string; content: string; is_private?: boolean }) =>
    request(`/clinician/case/${sessionId}/note`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  verifyField: (data: { target_type: string; target_id: string; status: string; modified_value?: string }) =>
    request('/clinician/verify', { method: 'POST', body: JSON.stringify(data) }),
  timeline: (patientId: string) =>
    request(`/clinician/timeline/${patientId}`),
  integrationsStatus: () =>
    request('/clinician/integrations/status'),

  // Integrations
  exportFhir: (resourceTypes?: string[]) =>
    request('/integrations/fhir/export', {
      method: 'POST',
      body: JSON.stringify({ resource_types: resourceTypes }),
    }),
  linkAbdm: (abhaId: string) =>
    request('/integrations/abdm/link', {
      method: 'POST',
      body: JSON.stringify({ abha_id: abhaId }),
    }),
  hisPush: (sessionId: string) =>
    request(`/integrations/his/push/${sessionId}`, { method: 'POST' }),

  // System
  health: () => request('/health'),
};
