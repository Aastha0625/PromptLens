# PromptLens - Phase 1

PromptLens is an API Auditor proxy that sits between your app and an LLM API. It logs token usage and computes cost based on a configurable pricing schema, later allowing you to audit your prompts.

## Features

- Config-driven multi-provider support (OpenAI, Anthropic, Gemini, Groq, Ollama)
- Standardized logging format
- Asynchronous database saving via FastAPI BackgroundTasks
- Out-of-the-box cost calculations

## Setup and Run

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Add your API keys to the .env file (e.g. GROQ_API_KEY)
   ```

3. **Run the server:**
   ```bash
   uvicorn app.main:app --reload
   ```

## Testing

Tests run against fixtures saved in `tests/fixtures`, so no credits are consumed.
```bash
pytest tests/
```

## Example Usage (Groq)

With your server running and `GROQ_API_KEY` set in your `.env` file:

```bash
curl -X POST http://localhost:8000/proxy/groq \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3-8b-8192",
    "messages": [
      {
        "role": "user",
        "content": "Hello!"
      }
    ]
  }'
```
