# PromptLens - The API Auditor

PromptLens is an API Auditor proxy and prompt intelligence tool that sits between your application and LLM providers. It captures token usage, calculates costs, provides interactive usage analytics, and audits prompts offline for waste and redundancy.

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

> **Note on Semantic Analysis:**
> `sentence-transformers` and `torch` are optional for basic heuristics. If installed, the first run will download `all-MiniLM-L6-v2` (~90MB). If omitted, PromptLens continues running all non-semantic checks (exact duplicates, repeated whitespace/words, and verbose template grouping) without interruption.

### 2. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Dashboard runs at `http://localhost:5173`.

---

## Running the Prompt Analyzer

Run the analyzer via the command line:

```bash
# Analyze unanalyzed requests
python scripts/run_analyzer.py --limit 100

# Force re-analysis of already analyzed requests
python scripts/run_analyzer.py --limit 100 --reanalyze
```

Or trigger it via the REST API:
```bash
# Trigger analysis
curl -X POST "http://localhost:8000/api/analyze?limit=100&reanalyze=true"

# View flagged prompts
curl "http://localhost:8000/api/flags?page=1&page_size=20"

# View aggregate summary and estimated wasted tokens
curl "http://localhost:8000/api/flags/summary"
```

---

## Testing

PromptLens has a comprehensive test suite covering adapters, cost math, API endpoints, and analyzer heuristics:

```bash
pytest -v
```

All analyzer unit tests run offline using `FakeEmbedder` so tests are fast, deterministic, and require zero internet.
