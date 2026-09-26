import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger("api_doctor.llm_client")


class GroqLLMClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ) -> None:
        raw_key = api_key if api_key is not None else settings.groq_api_key
        self.api_key = raw_key.strip() if isinstance(raw_key, str) and raw_key.strip() else None
        self.model = model or settings.groq_model
        self.timeout = timeout if timeout is not None else settings.groq_timeout_seconds

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def reason(self, prompt: str) -> str | None:
        if not self.is_configured:
            return None

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {
                                "role": "system",
                                "content": (
                                    "You are API Doctor, an expert production backend debugging assistant. "
                                    "Provide concise, accurate root cause analysis and actionable debugging insights."
                                ),
                            },
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.2,
                    },
                )
                response.raise_for_status()
                data: dict[str, Any] = response.json()
                choices = data.get("choices")
                if choices and isinstance(choices, list) and len(choices) > 0:
                    message = choices[0].get("message", {})
                    content = message.get("content")
                    if content and isinstance(content, str):
                        return content.strip()
                return None
        except httpx.TimeoutException:
            logger.warning("Groq API request timed out after %.1f seconds; falling back to deterministic diagnosis.", self.timeout)
            return None
        except httpx.HTTPStatusError as exc:
            logger.warning("Groq API returned HTTP error %s; falling back to deterministic diagnosis.", exc.response.status_code)
            return None
        except httpx.RequestError as exc:
            logger.warning("Groq API network request failed (%s); falling back to deterministic diagnosis.", exc.__class__.__name__)
            return None
        except Exception as exc:
            logger.warning("Unexpected error during Groq LLM inference (%s); falling back to deterministic diagnosis.", exc.__class__.__name__)
            return None


