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

// ==================== Prompt Studio: Real-Time Audit (Hitakshi Track) ====================

const FLUFF_PATTERNS = [
  /^(hello|hey|hi|good\s+(morning|afternoon|evening))\s+(chatgpt|ai|assistant|claude|gemini)?[!,.]*\s*/i,
  /^(i\s+hope\s+you\s+(are\s+having|have)\s+a\s+(great|wonderful|good|nice|productive)\s+day[!,.]*\s*)/i,
  /^(could|can|would)\s+you\s+(please\s+)?(kindly\s+)?(help\s+me(\s+with|\s+to)?|assist\s+me(\s+with|\s+in)?)\s*/i,
  /^(i\s+was\s+wondering\s+if\s+you\s+could\s+(possibly\s+)?(help\s+me|assist\s+me)\s*(with)?\s*)/i,
  /^(please\s+kindly\s+)/i,
  /(\s*(thank\s+you(\s+so\s+much|\s+very\s+much)?(\s+in\s+advance)?[!.]*)\s*)$/i,
  /(\s*(thanks(\s+a\s+lot|\s+in\s+advance)?[!.]*)\s*)$/i,
  /(\s*(i\s+(really\s+)?appreciate\s+(it|your\s+help)[!.]*)\s*)$/i
];

function estimateTokens(text) {
  if (!text || !text.trim()) return 0;
  // Approximation ~4 chars per token, min 1 per word
  const words = text.trim().split(/\s+/).length;
  const chars = text.length;
  return Math.max(words, Math.round(chars / 3.8));
}

function localAuditPrompt(rawText) {
  if (!rawText || !rawText.trim()) {
    return {
      original_prompt: '',
      optimized_prompt: '',
      tokens_original: 0,
      tokens_optimized: 0,
      tokens_saved: 0,
      efficiency_score: 100,
      flaws_detected: [],
      explanations: ['Prompt is empty.']
    };
  }

  let text = rawText;
  const flaws = [];
  const explanations = [];

  // 1. Remove conversational fluff
  let fluffStripped = false;
  for (const pattern of FLUFF_PATTERNS) {
    if (pattern.test(text)) {
      text = text.replace(pattern, '').trim();
      fluffStripped = true;
    }
  }
  if (fluffStripped) {
    flaws.push('conversational_fluff');
    explanations.push('Removed polite conversational greetings, preamble, or trailing filler.');
  }

  // 2. Collapse excessive whitespace & repeated blank lines
  const originalWsLen = text.length;
  text = text.replace(/[ \t]{4,}/g, ' ');
  text = text.replace(/\n{3,}/g, '\n\n');
  if (originalWsLen - text.length > 10) {
    flaws.push('repeated_content');
    explanations.push('Collapsed consecutive blank lines and redundant whitespace.');
  }

  // 3. Remove exact duplicate sentences
  const sentenceRegex = /([^.?!]+[.?!]+)/g;
  const rawSentences = text.match(sentenceRegex);
  if (rawSentences && rawSentences.length > 1) {
    const seen = new Set();
    const unique = [];
    let dupCount = 0;
    for (const s of rawSentences) {
      const normalized = s.trim().toLowerCase();
      if (seen.has(normalized)) {
        dupCount++;
      } else {
        seen.add(normalized);
        unique.push(s);
      }
    }
    if (dupCount > 0) {
      text = unique.join(' ').trim();
      flaws.push('redundant_sentences');
      explanations.push(`Removed ${dupCount} exact duplicate sentence${dupCount > 1 ? 's' : ''}.`);
    }
  }

  // Capitalize first letter if needed
  if (text.length > 0) {
    text = text.charAt(0).toUpperCase() + text.slice(1);
  }

  const origTokens = estimateTokens(rawText);
  const optTokens = estimateTokens(text);
  const savedTokens = Math.max(0, origTokens - optTokens);
  
  let score = 100;
  if (origTokens > 0) {
    const wasteRatio = savedTokens / origTokens;
    score = Math.max(20, Math.min(100, Math.round(100 - (wasteRatio * 100))));
  }

  if (flaws.length === 0) {
    explanations.push('Prompt is already concise and well-structured. No waste detected.');
  }

  return {
    original_prompt: rawText,
    optimized_prompt: text,
    tokens_original: origTokens,
    tokens_optimized: optTokens,
    tokens_saved: savedTokens,
    efficiency_score: score,
    flaws_detected: flaws,
    explanations
  };
}

export async function auditPrompt(payload, signal) {
  try {
    const res = await fetch(`${API_BASE}/api/audit-prompt`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal
    });

    if (res.ok) {
      return await res.json();
    }
  } catch (err) {
    if (err.name === 'AbortError') throw err;
  }

  // Fallback heuristic if endpoint is unavailable
  return localAuditPrompt(payload.prompt_text || '');
}
