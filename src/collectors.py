"""Сбор свежих новостей из внешних источников (RSS / HTML).

Возвращает статьи в том же формате, что и ``parse_dataset`` из ``src.processor``,
чтобы их можно было пропускать через существующий конвейер:
``filter_and_rank_articles`` → ``generate_digest``.

Поля статьи:
    id          — уникальный идентификатор (MD5 от источника + заголовка + ссылки)
    category    — категория / тег (по умолчанию «инфо»)
    priority    — приоритет (по умолчанию «Нормальный»; пересчитывается
                  правилами ИНФО в ``calculate_priority_rules``)
    title       — заголовок новости
    expected_output — аннотация / описание (используется генератором дайджеста)
    date        — дата публикации (YYYY-MM-DD)
    source      — имя источника (домен или подпись)
    link        — URL оригинала
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from urllib.parse import urljoin, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

REQUEST_TIMEOUT = 15

DEFAULT_SOURCES: list[str] = [
    "https://ria.ru/product_informatsionnaya-bezopasnost/",
    "https://www.infowatch.ru/analytics/novosti-ib",
    "https://www.forbes.ru/tegi/informacionnaya-bezopasnost",
    "https://www.kaspersky.ru/about/press-releases?sub=03%3A%3AНовости о киберугрозах",
    "https://safe-surf.ru/specialists/news/",
    "https://www.securitylab.ru/news/",
    "https://xakep.ru/news/",
    "https://cisoclub.ru/news/",
    "https://www.kommersant.ru/rubric/3",
    "https://www.anti-malware.ru/news/",
    "https://www.tadviser.ru/index.php/Категория:Информационная_безопасность",
]


def _article_id(source: str, title: str, link: str) -> str:
    raw = f"{source}|{title}|{link}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]


def _parse_date(entry) -> str:
    for field in ("published_parsed", "updated_parsed"):
        if entry.get(field):
            try:
                return datetime(*entry[field][:6]).strftime("%Y-%m-%d")
            except Exception:
                pass
    return datetime.now().strftime("%Y-%m-%d")


def _clean_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fetch_rss(url: str, source_name: str | None = None, limit: int = 10) -> list[dict]:
    """Забирает новости из RSS-ленты по URL."""
    source_name = source_name or urlparse(url).netloc
    try:
        feed = feedparser.parse(url)
    except Exception:
        return []

    articles: list[dict] = []
    for entry in feed.entries[:limit]:
        title = _clean_html(entry.get("title", ""))
        link = entry.get("link", "") or url
        summary = _clean_html(entry.get("summary") or entry.get("description") or "")
        if not title:
            continue
        articles.append(
            {
                "id": _article_id(source_name, title, link),
                "category": "инфо",
                "priority": "Нормальный",
                "title": title,
                "expected_output": summary[:400],
                "date": _parse_date(entry),
                "source": source_name,
                "link": link,
            }
        )
    return articles


def fetch_html(url: str, source_name: str | None = None, limit: int = 10) -> list[dict]:
    """Забирает новости из HTML-страницы (простой fallback без RSS)."""
    source_name = source_name or urlparse(url).netloc
    try:
        resp = requests.get(
            url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT
        )
        resp.raise_for_status()
    except Exception:
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    articles: list[dict] = []
    seen: set[str] = set()

    candidates = soup.find_all(["article", "h1", "h2", "h3"])
    for tag in candidates:
        title = tag.get_text(" ", strip=True)
        title = _clean_html(title)
        if not title or title in seen or len(title) < 10:
            continue

        link = None
        a = tag.find("a") or tag.find_parent("a")
        if a and a.get("href"):
            link = urljoin(url, a["href"])

        if not link:
            continue

        seen.add(title)
        articles.append(
            {
                "id": _article_id(source_name, title, link),
                "category": "инфо",
                "priority": "Нормальный",
                "title": title,
                "expected_output": "",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "source": source_name,
                "link": link,
            }
        )
        if len(articles) >= limit:
            break

    return articles


def collect_source(url: str, limit: int = 10) -> list[dict]:
    """Пытается RSS, при неудаче — HTML."""
    articles = fetch_rss(url, limit=limit)
    if articles:
        return articles
    return fetch_html(url, limit=limit)


def collect_all(
    sources: list[str] | None = None,
    limit_per_source: int = 5,
) -> list[dict]:
    """Собирает новости из списка источников."""
    if sources is None:
        sources = DEFAULT_SOURCES

    all_articles: list[dict] = []
    for url in sources:
        try:
            all_articles.extend(collect_source(url.strip(), limit=limit_per_source))
        except Exception:
            continue
    return all_articles