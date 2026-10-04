"""Генерация дайджеста через LLM-клиент."""

from config.prompts import EXECUTIVE_DIGEST_PROMPT, TECHNICAL_DIGEST_PROMPT
from src.llm import LLMClient

DIGEST_PROMPTS = {
    "technical": TECHNICAL_DIGEST_PROMPT,
    "management": EXECUTIVE_DIGEST_PROMPT,
}
AUDIENCE_LABELS = {
    "technical": "технических специалистов",
    "management": "руководства и работников",
}
CONTEXT_FIELDS = ("id", "category", "priority", "date", "source")


def _serialize(article: dict) -> str:
    summary = article.get("title") or article.get("expected_output") or ""
    meta = ", ".join(str(article[k]) for k in CONTEXT_FIELDS if article.get(k))
    return f"- {meta}\n  {str(summary)[:400]}"


def generate_digest(selected_articles: list[dict], audience: str, llm_client: LLMClient) -> str:
    """Формирует батч-запрос к LLM и возвращает Markdown-дайджест."""
    system_prompt = DIGEST_PROMPTS.get(audience, EXECUTIVE_DIGEST_PROMPT)
    label = AUDIENCE_LABELS.get(audience, AUDIENCE_LABELS["management"])
    records = "\n".join(_serialize(article) for article in selected_articles)
    user_prompt = f"Составь дайджест для {label} по публикациям:\n\n{records}"
    return llm_client.complete(system_prompt, user_prompt)