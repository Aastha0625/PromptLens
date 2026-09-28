import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import argparse
from datetime import datetime, timezone, timedelta
import random
from app.database import SessionLocal, engine, Base
from app.models import RequestLog

PROVIDERS = ['groq', 'openai', 'anthropic', 'ollama']
MODELS = {
    'groq': ['llama-3.1-8b-instant', 'mixtral-8x7b-32768', 'llama3-70b-8192', 'unknown-model'],
    'openai': ['gpt-4o', 'gpt-3.5-turbo'],
    'anthropic': ['claude-3-5-sonnet-20240620'],
    'ollama': ['llama3']
}

LONG_PROMPT = "Explain the theory of relativity. " * 50

def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    
    rows = []
    for i in range(200):
        provider = random.choice(PROVIDERS)
        model = random.choice(MODELS[provider])
        
        latency_ms = random.uniform(100.0, 3000.0)
        status_code = random.choices([200, 429, 500], weights=[90, 5, 5])[0]
        
        input_t = random.randint(10, 1000)
        output_t = random.randint(10, 1000) if status_code == 200 else 0
        total_t = input_t + output_t
        
        if provider == 'ollama':
            cost = 0.0
        elif model == 'unknown-model':
            cost = None
        else:
            cost = (input_t * 0.001 / 1000) + (output_t * 0.002 / 1000)
            
        prompt_text = LONG_PROMPT if random.random() < 0.1 else f"Normal prompt {i}"
        reply_text = f"Reply for {i}" if status_code == 200 else None
        
        created_at = now - timedelta(days=random.uniform(0, 14))
        error = "Too many requests" if status_code == 429 else None
        
        rows.append(RequestLog(
            provider=provider,
            model=model,
            input_tokens=input_t,
            output_tokens=output_t,
            total_tokens=total_t,
            cost_usd=cost,
            latency_ms=latency_ms,
            status_code=status_code,
            prompt_text=prompt_text,
            reply_text=reply_text,
            error=error,
            created_at=created_at,
            is_demo=True
        ))
        
    db.add_all(rows)
    db.commit()
    db.close()
    print("Inserted 200 demo rows.")

def clear():
    db = SessionLocal()
    count = db.query(RequestLog).filter(RequestLog.is_demo == True).delete()
    db.commit()
    db.close()
    print(f"Deleted {count} demo rows.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Seed demo data")
    parser.add_argument('--clear', action='store_true', help="Clear demo data")
    args = parser.parse_args()
    
    if args.clear:
        clear()
    else:
        seed()
