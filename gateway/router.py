import os
import time
from pathlib import Path
from typing import List, Dict
from dotenv import load_dotenv
from litellm import completion
from gateway.guardrails import scrub_secrets

# Explicitly load .env from the root project folder
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=ENV_PATH)

PRIMARY_MODEL = "gemini/gemini-2.5-flash"
FALLBACK_MODEL = "groq/llama-3.1-8b-instant"

LAST_CALL_TIMESTAMP = 0.0
MIN_CALL_INTERVAL_SEC = 2.0

def call_llm_gateway(
    messages: List[Dict[str, str]],
    temperature: float = 0.1,
    max_tokens: int = 1500
) -> str:
    global LAST_CALL_TIMESTAMP

    # Inbound Guardrail: Scrub secrets
    scrubbed_messages = [
        {"role": m["role"], "content": scrub_secrets(m["content"])}
        for m in messages
    ]

    elapsed = time.time() - LAST_CALL_TIMESTAMP
    if elapsed < MIN_CALL_INTERVAL_SEC:
        time.sleep(MIN_CALL_INTERVAL_SEC - elapsed)
    LAST_CALL_TIMESTAMP = time.time()

    gemini_key = os.getenv("GEMINI_API_KEY")
    groq_key = os.getenv("GROQ_API_KEY")

    if not gemini_key:
        print(f"[GATEWAY ERROR] GEMINI_API_KEY not found at {ENV_PATH}")

    try:
        response = completion(
            model=PRIMARY_MODEL,
            messages=scrubbed_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=gemini_key,
            timeout=30
        )
        return response.choices[0].message.content.strip()

    except Exception as primary_err:
        print(f"\n[GATEWAY WARNING] Primary model ({PRIMARY_MODEL}) failed: {primary_err}")
        print(f"[GATEWAY INFO] Tripping circuit breaker -> Failing over to {FALLBACK_MODEL}...")

        try:
            response = completion(
                model=FALLBACK_MODEL,
                messages=scrubbed_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                api_key=groq_key,
                timeout=25
            )
            return response.choices[0].message.content.strip()
        except Exception as fallback_err:
            raise RuntimeError(f"All LLM providers in gateway failed! Fallback error: {fallback_err}")