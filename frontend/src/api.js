const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

// ==================== Phase 1-3 Endpoints ====================

export async function fetchSummary(params, signal) {
  const url = new URL(`${API_BASE}/api/stats/summary`);
  if (params.from) url.searchParams.append("from", params.from);
  if (params.to) url.searchParams.append("to", params.to);
  if (params.provider && params.provider !== "all") url.searchParams.append("provider", params.provider);

  const res = await fetch(url, { signal });
  if (!res.ok) throw new Error(`Failed to fetch summary: ${res.status}`);
  return res.json();
}

export async function fetchTimeline(params, signal) {
  const url = new URL(`${API_BASE}/api/stats/timeline`);
  url.searchParams.append("from", params.from);
  url.searchParams.append("to", params.to);
  url.searchParams.append("bucket", params.bucket || "day");
  if (params.provider && params.provider !== "all") url.searchParams.append("provider", params.provider);

  const res = await fetch(url, { signal });
  if (!res.ok) throw new Error(`Failed to fetch timeline: ${res.status}`);
  return res.json();
}

export async function fetchRequests(params, signal) {
  const url = new URL(`${API_BASE}/api/requests`);
  url.searchParams.append("page", params.page || 1);
  url.searchParams.append("page_size", params.page_size || 20);
  if (params.provider && params.provider !== "all") url.searchParams.append("provider", params.provider);
  if (params.status && params.status !== "all") url.searchParams.append("status", params.status);
  if (params.from) url.searchParams.append("from", params.from);
  if (params.to) url.searchParams.append("to", params.to);

  const res = await fetch(url, { signal });
  if (!res.ok) throw new Error(`Failed to fetch requests: ${res.status}`);
  return res.json();
}

export async function fetchRequestDetail(id, signal) {
  const res = await fetch(`${API_BASE}/api/requests/${id}`, { signal });
  if (!res.ok) {
    if (res.status === 404) throw new Error("Request not found");
    throw new Error(`Failed to fetch request detail: ${res.status}`);
  }
  return res.json();
}

// ==================== Phase 4-6 Endpoints ====================

/**
 * Triggers batch prompt analysis on the backend.
 * POST request - never aborted to ensure batch work is completed cleanly.
 */
export async function triggerAnalysis(params = {}) {
  const url = new URL(`${API_BASE}/api/analyze`);
  if (params.limit) url.searchParams.append("limit", params.limit);
  if (params.reanalyze) url.searchParams.append("reanalyze", "true");

  const res = await fetch(url, { method: "POST" });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || `Analysis failed: ${res.status}`);
  }
  return res.json();
}

export async function fetchFlags(params = {}, signal) {
  const url = new URL(`${API_BASE}/api/flags`);
  url.searchParams.append("page", params.page || 1);
  url.searchParams.append("page_size", params.page_size || 20);
  if (params.flag_type && params.flag_type !== "all") url.searchParams.append("flag_type", params.flag_type);
  if (params.severity && params.severity !== "all") url.searchParams.append("severity", params.severity);
  if (params.provider && params.provider !== "all") url.searchParams.append("provider", params.provider);
  if (params.request_id) url.searchParams.append("request_id", params.request_id);

  const res = await fetch(url, { signal });
  if (!res.ok) throw new Error(`Failed to fetch flags: ${res.status}`);
  return res.json();
}

export async function fetchFlagsSummary(signal) {
  const res = await fetch(`${API_BASE}/api/flags/summary`, { signal });
  if (!res.ok) throw new Error(`Failed to fetch flags summary: ${res.status}`);
  return res.json();
}

/**
 * Generates or regenerates a suggestion for a specific flag.
 * POST request - never aborted.
 */
export async function triggerSuggestion(flagId, regenerate = false) {
  const url = new URL(`${API_BASE}/api/suggest/${flagId}`);
  if (regenerate) url.searchParams.append("regenerate", "true");

  const res = await fetch(url, { method: "POST" });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || `Suggestion failed: ${res.status}`);
  }
  return res.json();
}

export async function fetchSuggestions(params = {}, signal) {
  const url = new URL(`${API_BASE}/api/suggestions`);
  if (params.page) url.searchParams.append("page", params.page);
  if (params.page_size) url.searchParams.append("page_size", params.page_size);
  if (params.method && params.method !== "all") url.searchParams.append("method", params.method);
  if (params.status && params.status !== "all") url.searchParams.append("status", params.status);
  if (params.flag_id != null) url.searchParams.append("flag_id", params.flag_id);

  const res = await fetch(url, { signal });
  if (!res.ok) throw new Error(`Failed to fetch suggestions: ${res.status}`);
  return res.json();
}

export async function fetchSuggestionsSummary(signal) {
  const res = await fetch(`${API_BASE}/api/suggestions/summary`, { signal });
  if (!res.ok) throw new Error(`Failed to fetch suggestions summary: ${res.status}`);
  return res.json();
}
