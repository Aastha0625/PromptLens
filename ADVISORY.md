# PromptLens: Project Advisory & Team Execution Guide

> **Audience:** Core Project Team (Akshat, Hitakshi)  
> **Project Title:** PromptLens — The LLM API Auditor & Prompt Intelligence Suite  
> **Repository Root:** `E:\Major project`  

---

## 1. Project Overview & Complete Architecture Workflow

PromptLens is an enterprise-grade LLM proxy, auditor, and prompt optimization intelligence tool. It intercepts API traffic between client applications and major LLM providers to track costs, monitor latencies, detect token waste offline, and safely suggest optimized prompt rewrites.

### System Architecture Workflow

```mermaid
flowchart TD
    Client["Client Application / Postman / cURL"] -->|POST /proxy/{provider}| Proxy["PromptLens Reverse Proxy (FastAPI)"]
    
    subgraph ProxyLayer ["Proxy & Adapter Layer (Phase 1)"]
        Proxy --> Adapter["Provider Adapter (YAML Configs)"]
        Adapter --> Upstream["Upstream LLM (OpenAI / Anthropic / Gemini / Groq / Ollama)"]
        Upstream -->|Response Payload| Proxy
        Proxy -->|Log Request, Reply, Tokens, Cost, Latency| DB[("SQLite DB (promptlens.db)")]
        Proxy -->|Normalized Response JSON| Client
    end

    subgraph AnalyticsLayer ["Analytics & Reporting API (Phase 2)"]
        DB --> StatsAPI["API Stats Router (/api/stats/summary, /api/stats/timeline, /api/requests)"]
    end

    subgraph IntelligenceLayer ["Prompt Intelligence Engine (Phases 4 & 5)"]
        DB --> Analyzer["Batch Prompt Analyzer (/api/analyze)"]
        Analyzer --> Flags["Prompt Flags Table (redundant_sentences, repeated_content, verbose_for_template)"]
        Flags --> SuggestionEngine["Suggestion Engine (/api/suggest/{flag_id})"]
        SuggestionEngine --> Tier1["Tier 1: Rule-Based Deterministic Shortening (0 cost)"]
        SuggestionEngine --> Tier2["Tier 2: LLM Rewrite (Optimizer Model) + Semantic Verification (Cosine Sim >= 0.85)"]
        Tier2 --> OptimizerLog["Optimizer Usage Tracking (Cost transparency)"]
    end

    subgraph DashboardLayer ["Dashboard UI (Phases 3 & 6)"]
        StatsAPI --> UI["React 18 + Vite SPA"]
        Flags --> UI
        SuggestionEngine --> UI
        UI --> Tab1["Tab 1: Overview (Live Stats, Recharts Timeline, Request Logs)"]
        UI --> Tab2["Tab 2: Prompt Insights (Audit Cards, Flags Table, Side-by-Side Prompt Diff, Copy)"]
    end
```

---

## 2. What Is Completed & Working (Phases 1 – 6)

1. **Phase 1: Reverse Proxy & Multi-Provider Adapters**
   - Declarative YAML adapters in [`providers/`](file:///E:/Major%20project/providers/) for OpenAI, Anthropic, Gemini, Groq, and Ollama.
   - Non-blocking asynchronous logging using FastAPI `BackgroundTasks`.
   - Exact token & cost accounting using [`pricing.yaml`](file:///E:/Major%20project/pricing.yaml) with student free-tier support.
2. **Phase 2: Analytics & Read API**
   - SQLite WAL mode database (`promptlens.db`).
   - Time-bucketed statistics (`/api/stats/summary`), zero-filled timeline aggregation (`/api/stats/timeline`), and paginated request drill-down (`/api/requests`).
3. **Phase 3: Overview Dashboard UI**
   - Single-page React 18 + Vite frontend with Recharts, plain CSS, native `fetch()`, and `AbortController` cancellation.
   - Filter bar with date presets (`Last 24h`, `Last 7d`, `Last 14d`, `All`), provider selection, and status filters.
4. **Phase 4: Prompt Analyzer Engine**
   - Offline batch prompt waste scanner (`POST /api/analyze`).
   - Detects:
     - `redundant_sentences`: Exact string matching and semantic cosine similarity ($\ge 0.90$).
     - `repeated_content`: Blank line spam, excessive spaces, and repeating n-grams outside code blocks.
     - `verbose_for_template`: SQL `GROUP BY` template outlier detection ($\ge 3\times$ baseline token usage).
   - Idempotent re-runs safely replace old flags per request.
5. **Phase 5: Suggestion Engine**
   - `POST /api/suggest/{flag_id}` generates prompt shortening suggestions:
     - **Tier 1 (Rule-Based)**: Deterministic, instant cleanup of exact duplicates and whitespace runs (0 LLM cost).
     - **Tier 2 (LLM Rewrite)**: Feature-flagged optimizer model (e.g. Groq `openai/gpt-oss-20b`) for verbose templates.
   - Guardrails: Preflight checks, length reduction validation, and embedding similarity verification against baseline replies.
   - Optimizer overhead tracking: Logs PromptLens's self-usage to `optimizer_usage` to disclose runtime overhead.
6. **Phase 6: Prompt Insights Dashboard UI**
   - Seamless top tab navigation (`Overview` vs. `Prompt Insights`) maintaining filter and scroll states.
   - Summary cards displaying flagged requests, total flags by severity, estimated wasted tokens, usable suggestions, rule-based vs. verified LLM savings, and tool runtime overhead.
   - "Run analysis" action with interactive loading states, first-run model download notes, and completion banners.
   - Flags table with severity badges, filters, pagination, and detail modal.
   - Side-by-side prompt viewer (original vs. rewritten), plain-English explanations, honest status badges, and one-click clipboard copy.

---

## 3. Environment Setup & Configuration

### Prerequisites
- **Python**: 3.10 or 3.11 installed.
- **Node.js**: v18+ and `npm` installed.
- **Git**: Installed.

### 1. Backend `.env` File Configuration
In the project root (`E:\Major project`), ensure a `.env` file exists with the following keys:

```env
# Database Path
DATABASE_URL=sqlite:///promptlens.db

# Provider API Keys for Proxy Interception
GROQ_API_KEY=gsk_your_groq_api_key_here
OPENAI_API_KEY=sk-your_openai_key_here
ANTHROPIC_API_KEY=sk-ant-your_anthropic_key_here
GEMINI_API_KEY=your_gemini_key_here

# Phase 5: Suggestion Engine (Tier 2 LLM Optimizer)
ENABLE_LLM_REWRITE=true
OPTIMIZER_PROVIDER=groq
OPTIMIZER_MODEL=openai/gpt-oss-20b
OPTIMIZER_API_KEY=gsk_your_groq_optimizer_key_here
```

> [!NOTE]
> If you do not have an OpenAI or Anthropic key, you can test everything using **Groq** (free tier) and **Ollama** (local). Groq is currently configured with the active fast model `openai/gpt-oss-20b`.

---

## 4. How to Run Frontend & Backend

### 1. Start the Backend Server (Terminal 1)
```powershell
cd "E:\Major project"

# Activate the Python virtual environment
.\venv\Scripts\activate

# Launch FastAPI server with live reload
uvicorn app.main:app --reload --port 8000
```
* **Interactive Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **Backend Health Check**: [http://localhost:8000/api/stats/summary](http://localhost:8000/api/stats/summary)

### 2. Start the Frontend Dashboard (Terminal 2)
```powershell
cd "E:\Major project\frontend"

# Install dependencies if not already done
npm install

# Start Vite development server
npm run dev
```
* **Dashboard URL**: [http://localhost:5173](http://localhost:5173)

### 3. Utility Scripts & Testing
```powershell
cd "E:\Major project"

# Seed 200 demo request rows into promptlens.db for testing:
.\venv\Scripts\python.exe scripts/seed_demo_data.py

# Clear all demo data:
.\venv\Scripts\python.exe scripts/seed_demo_data.py --clear

# Run offline batch prompt analyzer manually:
.\venv\Scripts\python.exe scripts/run_analyzer.py

# Run prompt suggestion generator manually:
.\venv\Scripts\python.exe scripts/run_suggestions.py

# Run the complete test suite:
.\venv\Scripts\pytest.exe -v -m "not slow"
```

---

## 5. Work Division: Remaining Features

To complete the major project without overlapping work, the remaining milestones are split into two decoupled tracks:

```mermaid
graph LR
    subgraph AkshatTrack ["Akshat: Backend Systems & Real-Time Intelligence"]
        A1["1. SSE Streaming Proxy Support"]
        A2["2. Semantic Response Cache Layer"]
        A3["3. Automated Scheduled Audit & Webhook Alerts"]
    end

    subgraph HitakshiTrack ["Hitakshi: UI Intelligence & Analytics Reporting"]
        H1["1. Visual Word/Sentence Diff Viewer"]
        H2["2. Interactive 'Test Rewrite' Playground"]
        H3["3. PDF / CSV Audit Report Export"]
        H4["4. Provider & Budget Settings UI"]
    end
```

### Division of Ownership

| Member | Domain & Ownership | Primary Files Owned |
| :--- | :--- | :--- |
| **Akshat** | **Backend Proxy & Optimization Intelligence**<br>• Server-Sent Events (SSE) Streaming Proxy (`stream=true`)<br>• Prompt Caching & Deduplication Layer (zero-token exact/semantic cache)<br>• Background Scheduled Auditor & Webhook Alerts (Slack/Discord/Email) | `app/proxy.py`<br>`app/cache.py`<br>`app/scheduler.py`<br>`tests/test_streaming.py`<br>`tests/test_cache.py` |
| **Hitakshi** | **Frontend Experience, Visual Diff & Analytics Reporting**<br>• In-browser side-by-side visual diff (red/green word deletion)<br>• Interactive "Test Rewrite" modal playground (run original vs rewritten live)<br>• CSV / PDF Audit Report Exporter for presentations<br>• Model latency percentile charts (p50/p90/p99) and Budget Alert settings | `frontend/src/components/SuggestionView.jsx`<br>`frontend/src/components/RewritePlayground.jsx`<br>`frontend/src/components/ExportModal.jsx`<br>`frontend/src/components/SettingsModal.jsx`<br>`frontend/src/App.css` |

---

## 6. Antigravity Prompt for Akshat (Backend Track)

Copy and paste this entire prompt into Antigravity:

````markdown
You are an expert Python/FastAPI engineer working on PromptLens (an LLM API proxy and intelligence auditor).
Repository directory: E:\Major project
Virtual environment: E:\Major project\venv\Scripts\python.exe

### Context:
Phases 1-6 are complete. The backend currently has:
- Reverse proxy at `/proxy/{provider}` (OpenAI, Anthropic, Gemini, Groq, Ollama) logging to SQLite (`promptlens.db`).
- Offline prompt analyzer (`/api/analyze`) and suggestion engine (`/api/suggest/{flag_id}`).
- Full pytest suite passing (36 tests).

### Your Mission (Akshat's Track):
Implement the following three backend capabilities without breaking existing endpoints or test suites:

1. **Streaming Proxy Support (SSE)**:
   - In `app/proxy.py`, remove the `"Streaming is not supported yet"` 400 rejection when `body.get("stream") is True`.
   - Forward upstream streaming chunks as `text/event-stream` using `StreamingResponse`.
   - Accumulate chunks in memory during streaming so that when the stream completes, the full reply text, token counts, cost, and latency are logged to SQLite via background tasks just like non-streaming requests.

2. **Prompt Response Cache (Zero-Token Deduplication)**:
   - Create `app/cache.py` with an in-memory or SQLite-backed cache table (`cached_responses`).
   - If an incoming prompt matches an existing request (same provider, model, prompt text) within a configurable TTL (e.g. 24h), return the cached response immediately with `X-PromptLens-Cache: HIT`.
   - Log the request with `cost_usd: 0.0` and mark it as a cache hit so the dashboard reflects 100% token savings.

3. **Scheduled Background Audit & Webhook Alerts**:
   - Create a background task / cron runner in `app/scheduler.py` that periodically triggers `run_analysis()` every X hours.
   - If total estimated wasted tokens or cost exceed a threshold, send an alert payload to a configured webhook URL (Discord/Slack format).

### Constraints:
- Do not modify existing frontend files.
- Keep SQLite WAL mode intact and maintain `PRAGMA foreign_keys = ON`.
- Write comprehensive unit tests in `tests/test_streaming.py` and `tests/test_cache.py`.
- Run `pytest -v` to ensure all existing and new tests pass.
````

---

## 7. Antigravity Prompt for Hitakshi (Frontend Track)

Copy and paste this entire prompt into Antigravity:

````markdown
You are an expert React/Frontend engineer working on PromptLens (an LLM API proxy and intelligence auditor).
Repository directory: E:\Major project\frontend
Backend API: http://localhost:8000

### Context:
Phases 1-6 are complete. The frontend is built with React 18, Vite, plain JavaScript, and plain CSS (no Tailwind, no third-party UI component libraries).
Top navigation has two tabs: "Overview" and "Prompt Insights".
All existing endpoints in `src/api.js` use native `fetch()` with `AbortController`.

### Your Mission (Hitakshi's Track):
Implement the following four UX intelligence capabilities in the frontend without breaking existing features:

1. **Visual Word & Sentence Diff in Suggestions**:
   - In `src/components/SuggestionView.jsx`, enhance the side-by-side prompt boxes.
   - Provide a toggle button: "Split View" vs "Visual Diff".
   - In Visual Diff mode, compute character/word-level changes between `originalPromptText` and `rewritten_prompt` (using simple LCS or word split) and highlight removed text in light red strikethrough and preserved text cleanly.

2. **Interactive "Test Rewrite" Playground**:
   - In `src/components/FlagDetail.jsx`, add a "Test Rewrite Live" button when a rewritten prompt exists.
   - Opens a sub-panel allowing the user to send both the original and rewritten prompt to `/proxy/{provider}` through the dashboard, comparing both replies side by side with real-time latency and token differences.

3. **Audit Report Export (CSV / PDF)**:
   - Add an "Export Report" button in the header of `src/components/InsightsTab.jsx`.
   - Generates a downloadable CSV containing all flagged prompts, flag types, estimated token waste, and savings.
   - Provides a clean print-friendly CSS stylesheet so printing to PDF (`window.print()`) creates a clean executive report for project presentations.

4. **Latency Percentile & Model Breakdown Chart**:
   - In `src/components/UsageChart.jsx` (or a new card in `Overview`), add a toggle for "Latency Percentiles" displaying p50, p90, and p99 response times over time.

### Constraints:
- Stick to pure React 18, Vite, plain CSS in `src/App.css`, and Recharts. Do not install Tailwind, MUI, or Bootstrap.
- Maintain existing tab switching state preservation in `App.jsx`.
- Run `npm run build` inside `frontend/` to ensure zero compilation or styling errors.
````

---

## 8. Verification & Delivery Checklist Before Final Submission

- [ ] Backend runs with zero errors: `uvicorn app.main:app --reload --port 8000`
- [ ] Frontend builds with zero errors: `npm run build`
- [ ] Automated tests pass: `pytest -v -m "not slow"`
- [ ] No orphaned records in SQLite: dependent flags, analyses, and suggestions are cleanly cascading.
- [ ] Active tabs show clean transparent styling with blue underline indicator.
- [ ] Both team members pull and merge using clean feature branches (`feature/streaming-cache` and `feature/ui-diff-export`).
