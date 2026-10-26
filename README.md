# PromptLens - The API Auditor

PromptLens is an API Auditor proxy and prompt intelligence tool that sits between your application and LLM providers. It captures token usage, calculates costs, provides interactive usage analytics, audits prompts offline for waste and redundancy, and generates verifiable prompt shortening suggestions.

---

## Architecture & Features

1. **Proxy & Adapter Layer (Phase 1):**
   - Config-driven YAML multi-provider adapters (`openai`, `anthropic`, `gemini`, `groq`, `ollama`).
   - Normalizes requests and replies into a standard schema.
   - Non-blocking async logging using FastAPI `BackgroundTasks`.
   - Token & cost calculation with student free-tier support (`is_free_tier`).

2. **Analytics & Aggregation Layer (Phase 2):**
   - SQLite with WAL mode.
   - Summary statistics (`/api/stats/summary`), zero-filled timeline aggregation (`/api/stats/timeline`), and paginated request queries (`/api/requests`).

3. **Dashboard UI (Phase 3):**
   - Single-page React 18 + Vite frontend with Recharts, plain CSS, native `fetch()`, and request cancellation via `AbortController`.

4. **Prompt Analyzer - Detection Only (Phase 4):**
   - Runs **offline in batch**, completely decoupled from the proxy request path to maintain zero latency overhead.
   - Detects three waste patterns without calling external LLM APIs:
     - **`redundant_sentences`**: Exact string matching and semantic similarity (via `all-MiniLM-L6-v2` with cosine similarity $\ge 0.90$).
     - **`repeated_content`**: 5+ blank lines, 20+ consecutive spaces, 4+ repeated words.
     - **`verbose_for_template`**: SQL `GROUP BY` template outlier detection ($\ge 3\times$ minimum tokens for templates with 3+ occurrences).
   - Fully idempotent: re-runs safely replace old flags per request.
   - Lazy model loading: falls back gracefully without crashing if `sentence-transformers` is absent.

5. **Suggestion Engine - Rewrite & Verification (Phase 5):**
   - **Tier 1 (Rule-Based, zero LLM calls):** Deterministically removes duplicate sentences using analyzer spans and collapses whitespace/word runs outside fenced code blocks.
   - **Tier 2 (LLM-Based, verbose template outliers):** Feature-flagged behind `ENABLE_LLM_REWRITE`. Uses a separate optimizer key and model so user proxy quotas are never touched.
   - **Semantic Verification:** Reuses `all-MiniLM-L6-v2` to verify semantic preservation between the stored original reply and the new reply from the rewrite (cosine similarity $\ge 0.85 \implies$ `status="ok"`).
   - **Tool Overhead Transparency:** Logs internal rewrite/verify API usage to `optimizer_usage` to show exact tool runtime cost.

---

## Setup & Execution

### 1. Backend Setup

```bash
# Activate virtual environment
.\venv\Scripts\activate   # Windows
# or source venv/bin/activate (Linux/macOS)

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env

# Run FastAPI server
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Dashboard runs at `http://localhost:5173`.

---

## Configuring the Optimizer (Phase 5 Tier 2)

By default, Tier 2 LLM rewriting is disabled (`ENABLE_LLM_REWRITE=False`). To enable it with a dedicated key:

1. Add the optimizer configuration to your `.env` file:
   ```env
   ENABLE_LLM_REWRITE=true
   OPTIMIZER_PROVIDER=groq
   OPTIMIZER_MODEL=llama-3.1-8b-instant
   OPTIMIZER_API_KEY=your_optimizer_key_here
   ```
2. When enabled, requesting suggestions for `verbose_for_template` flags will execute Tier 2 shortening and verify reply consistency without spending your proxy application quota.

---

## Running the Suggestion Engine

Run the batch suggestion generator via the CLI:

```bash
# Generate suggestions for un-suggested flags
python scripts/run_suggestions.py --limit 20

# Force re-generation of existing suggestions
python scripts/run_suggestions.py --limit 20 --regenerate
```

Or call the Suggestion REST endpoints:

```bash
# 1. Generate or fetch suggestion for a specific flag
curl -X POST "http://localhost:8000/api/suggest/1"

# 2. Force re-generation for a flag
curl -X POST "http://localhost:8000/api/suggest/1?regenerate=true"

# 3. List paginated suggestions (filter by method or status)
curl "http://localhost:8000/api/suggestions?page=1&page_size=20&status=ok"

# 4. View aggregate suggestion summary, separate savings, and optimizer overhead cost
curl "http://localhost:8000/api/suggestions/summary"
```

---

## Testing

PromptLens has a comprehensive test suite across all 5 phases:

```bash
pytest -v
```

All tests run completely offline without external network calls using `FakeEmbedder` and `FakeOptimizerClient`.
