"""LLM Prompt Packager & Exporter.

Combines market digest and system instructions into a single ready-to-paste
text file that user can send to ChatGPT, Claude, DeepSeek, or Gemini.
"""

import json
import logging
import os
from pathlib import Path
import sys

# Ensure project root is available in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("export-for-llm")


def export_llm_bundle(
    digest_path: str = "data/digest.json",
    prompt_path: str = "prompts/llm_analyst.md",
    output_path: str = "data/prompt_for_external_llm.txt",
) -> str:
    if not os.path.exists(digest_path):
        logger.error(f"Digest not found at {digest_path}")
        return ""

    with open(prompt_path, "r", encoding="utf-8") as f:
        instructions = f.read()

    with open(digest_path, "r", encoding="utf-8") as f:
        digest_data = json.load(f)

    # Format into a clean, readable payload
    bundle = (
        "================================================================================\n"
        "СИСТЕМНЫЕ ИНСТРУКЦИИ ДЛЯ ИИ-АНАЛИТИКА (СКОПИРУЙТЕ ВЕСЬ ТЕКСТ В ЧАТ):\n"
        "================================================================================\n\n"
        f"{instructions}\n\n"
        "================================================================================\n"
        "АКТУАЛЬНЫЙ ДАЙДЖЕСТ РЫНКА (ДАННЫЕ АУКЦИОНА STALCRAFT RU):\n"
        "================================================================================\n\n"
        "```json\n"
        f"{json.dumps(digest_data, ensure_ascii=False, indent=2)}\n"
        "```\n\n"
        "================================================================================\n"
        "ЗАДАЧА: Проанализируй этот дайджест, выдели самые безопасные и ликвидные сделки,\n"
        "укажи точные цены покупки и продажи, срок и риски по каждому лоту.\n"
        "================================================================================\n"
    )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(bundle)

    logger.info(f"LLM analysis bundle exported to {output_path} ({len(bundle)} characters)")
    return bundle


if __name__ == "__main__":
    export_llm_bundle()
