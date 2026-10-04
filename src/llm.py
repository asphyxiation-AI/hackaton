"""Универсальный клиент для OpenAI-совместимых LLM API."""

import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


class LLMClient:
    """Провайдер/модель меняются через параметры или env без правки кода."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.model = model or os.getenv("MODEL_NAME", "gpt-oss-120b")
        self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def complete(self, system_prompt: str, user_prompt: str, json_mode: bool = False) -> str:
        """Одиночный запрос к чат-модели; json_mode форсирует JSON-ответ."""
        kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            **kwargs,
        )
        return response.choices[0].message.content