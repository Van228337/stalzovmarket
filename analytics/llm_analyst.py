"""Autonomous LLM Market Analyst using Groq API (llama-3.3-70b-versatile).

Feeds digest.json + prompts/llm_analyst.md into Groq LLM API and saves the structured
expert report to data/latest_llm_analysis.md.
"""

import json
import logging
import os
from pathlib import Path
import sys
from typing import Any, Dict, Optional
import httpx
from dotenv import load_dotenv

# Ensure project root is available in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("llm-analyst")


async def run_llm_analysis(
    digest_path: str = "data/digest.json",
    prompt_path: str = "prompts/llm_analyst.md",
    output_path: str = "data/latest_llm_analysis.md",
) -> Optional[str]:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        logger.warning("GROQ_API_KEY is not configured in .env. Skipping LLM generation.")
        return None

    base_url = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    # Read system prompt and market digest
    if not os.path.exists(digest_path):
        logger.error(f"Digest file not found at {digest_path}")
        return None

    with open(prompt_path, "r", encoding="utf-8") as f:
        system_prompt = f.read()

    with open(digest_path, "r", encoding="utf-8") as f:
        digest_content = f.read()

    user_message = f"Вот актуальный JSON-дайджест рынка STALCRAFT:\n\n```json\n{digest_content}\n```\n\nПроведи детальный анализ согласно инструкциям."

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.2, # Low temperature for accurate quantitative analysis
        "max_tokens": 2048,
    }

    logger.info(f"Sending digest to Groq API ({model})...")
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                reply = data["choices"][0]["message"]["content"]
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(reply)
                logger.info(f"LLM analysis completed and saved to {output_path}")
                return reply
            else:
                logger.error(f"Groq API error {resp.status_code}: {resp.text}")
                return None
    except Exception as e:
        logger.error(f"Error communicating with Groq API: {e}")
        return None


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_llm_analysis())
