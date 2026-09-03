"""
Centralized Google Gemini API Client for Project Khet2Kitchen (K2K).
Configured with official google-genai SDK, structured JSON output, and multi-model failover.
"""
import json
import logging
from typing import List, Dict, Any, Optional
from django.conf import settings
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# Preferred models in order of latency, multimodal capability, and quota stability
PRIMARY_MODELS = [
    getattr(settings, 'GEMINI_MODEL_NAME', 'gemini-3.5-flash-lite'),
    'gemini-flash-latest',
    'gemini-3.7-flash',
    'gemini-3.6-flash'
]


def get_gemini_client() -> Optional[genai.Client]:
    """
    Initializes and returns the official Google GenAI client.
    """
    api_key = getattr(settings, 'GEMINI_API_KEY', None)
    if not api_key:
        logger.warning("GEMINI_API_KEY is not configured in settings.")
        return None
    try:
        return genai.Client(api_key=api_key)
    except Exception as e:
        logger.error(f"Failed to initialize Google GenAI Client: {e}")
        return None


def call_gemini_structured_json(
    contents: List[Any],
    system_instruction: Optional[str] = None,
    preferred_model: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Calls Google Gemini with structured JSON output enforced.
    Tries candidate models if 503 or transient network errors occur.
    """
    client = get_gemini_client()
    if not client:
        return None

    models_to_try = [preferred_model] if preferred_model else []
    for m in PRIMARY_MODELS:
        if m and m not in models_to_try:
            models_to_try.append(m)

    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        system_instruction=system_instruction
    ) if system_instruction else types.GenerateContentConfig(
        response_mime_type="application/json"
    )

    for model_name in models_to_try:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=config
            )
            if response and response.text:
                cleaned_text = response.text.strip()
                # Remove possible markdown fences if returned
                if cleaned_text.startswith("```json"):
                    cleaned_text = cleaned_text[7:]
                elif cleaned_text.startswith("```"):
                    cleaned_text = cleaned_text[3:]
                if cleaned_text.endswith("```"):
                    cleaned_text = cleaned_text[:-3]
                
                parsed_json = json.loads(cleaned_text.strip())
                logger.info(f"Gemini call succeeded using model: {model_name}")
                return parsed_json
        except Exception as e:
            logger.warning(f"Gemini call failed with model {model_name}: {e}. Trying next candidate model...")
            continue

    logger.error("All candidate Gemini models failed to respond.")
    return None
