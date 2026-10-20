"""
HymnFlow -- Gemini API Key Rotator
Uses the new official google-genai SDK.
Cycles through all 10 API keys automatically.
"""

from google import genai
from google.genai import types
from config import GEMINI_API_KEYS
import logging

logger = logging.getLogger(__name__)


class GeminiKeyRotator:
    def __init__(self):
        if not GEMINI_API_KEYS:
            raise ValueError(
                "No Gemini API keys found. "
                "Add GEMINI_API_KEYS to your .env file as a comma-separated list."
            )
        self.keys = GEMINI_API_KEYS
        self.current_index = 0
        self.failed_keys = set()
        logger.info(f"GeminiKeyRotator ready with {len(self.keys)} API key(s).")

    @property
    def current_key(self) -> str:
        return self.keys[self.current_index]

    def get_client(self) -> genai.Client:
        return genai.Client(api_key=self.current_key)

    def rotate(self) -> bool:
        self.failed_keys.add(self.current_index)
        for i in range(len(self.keys)):
            next_index = (self.current_index + i + 1) % len(self.keys)
            if next_index not in self.failed_keys:
                self.current_index = next_index
                logger.warning(
                    f"Rotated to Gemini key #{self.current_index + 1} "
                    f"({len(self.failed_keys)} key(s) exhausted today)."
                )
                return True
        logger.error("All Gemini API keys are exhausted for today.")
        return False

    def reset_failed_keys(self):
        self.failed_keys.clear()
        self.current_index = 0
        logger.info("Gemini key rotation reset for new day.")

    def generate_with_retry(
        self,
        prompt: str,
        model: str = "gemini-2.5-flash",
        max_retries: int = None,
        response_schema=None,
    ) -> str:
        """
        Send a prompt to Gemini with automatic key rotation on quota errors.
        Uses response_mime_type=application/json + response_schema when a
        schema is provided -- this guarantees valid JSON and prevents truncation.
        """
        if max_retries is None:
            max_retries = len(self.keys)

        last_error = None

        # Build config -- use structured output when schema provided
        if response_schema is not None:
            config = types.GenerateContentConfig(
                temperature=0.85,
                max_output_tokens=8192,
                response_mime_type="application/json",
                response_schema=response_schema,
            )
        else:
            config = types.GenerateContentConfig(
                temperature=0.85,
                max_output_tokens=2048,
            )

        for attempt in range(max_retries):
            try:
                client = self.get_client()
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=config,
                )
                return response.text

            except Exception as e:
                error_msg = str(e).lower()
                last_error = e

                if any(word in error_msg for word in [
                    "quota", "rate limit", "429", "resource exhausted",
                    "too many requests", "daily limit", "resource_exhausted"
                ]):
                    logger.warning(
                        f"Key #{self.current_index + 1} hit quota limit. "
                        f"Rotating... (attempt {attempt + 1}/{max_retries})"
                    )
                    if not self.rotate():
                        break
                else:
                    logger.error(f"Gemini API error: {e}")
                    raise

        raise RuntimeError(
            f"All {len(self.keys)} Gemini API keys failed. Last error: {last_error}"
        )


# Singleton instance used across the whole app
rotator = GeminiKeyRotator()
