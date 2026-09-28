const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

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
  
  // The API requires 'from' and 'to'. The frontend must provide them.
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
