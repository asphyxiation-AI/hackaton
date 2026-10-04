"""Импорт датасета, приоритеты по правилам ИНФО и ранжирование."""

import re
from io import BytesIO

import pandas as pd

DATASET_COLUMNS = {
    "Dataset 1 (тех. специалистам)": {
        "№": "id",
        "Группировка по признакам": "category",
        "Вес/приоритет": "priority",
        "Наименование": "title",
        "Дата": "date",
        "Источник": "source",
        "Желаемый вывод": "expected_output",
    },
    "Dataset 2 (рук-во и  работники)": {
        "№": "id",
        "Группировка по признакам": "category",
        "Дата": "date",
        "Источник": "source",
        "Форма вывода": "format",
        "Пример вывода": "expected_output",
    },
}

PRIORITY_RANK = {"Высокий": 3, "Средний": 2, "Низкий": 1, "Нормальный": 1, "Новости ТГ": 0}
RU_MARKERS = ("росси",)
ENERGY_MARKERS = ("энерг", "тэк", "электроэнерг", "атомн", "нефте", "нефтян")

SEARCH_FIELDS = {
    "technical": ("title", "expected_output", "category", "source"),
    "management": ("category", "expected_output", "format", "source"),
}
TEXT_FIELDS = ("title", "category", "expected_output", "format", "source")


def _source(file_path_or_bytes):
    if isinstance(file_path_or_bytes, (bytes, bytearray)):
        return BytesIO(file_path_or_bytes)
    return file_path_or_bytes


def _fmt(value) -> str:
    if value is None or pd.isna(value):
        return ""
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    return str(value).strip()


def _clean_tags(value) -> str:
    tags = []
    for line in str(value).splitlines():
        line = line.strip()
        if line:
            tags.append(re.sub(r"^\d+\.\s*", "", line))
    return "; ".join(tags)


def _category_kind(category) -> str:
    words = [w for w in re.split(r"[;\s]+", str(category).strip().lower()) if w]
    return words[0] if words else ""


def _text(article: dict, fields: tuple = TEXT_FIELDS) -> str:
    return "\n".join(str(article.get(k, "")) for k in fields if article.get(k))


def parse_dataset(file_path_or_bytes, sheet_name: str) -> list[dict]:
    """Разбирает лист датасета в список словарей."""
    columns = DATASET_COLUMNS.get(sheet_name)
    if columns is None:
        raise ValueError(f"Неизвестный лист: {sheet_name}")
    df = pd.read_excel(_source(file_path_or_bytes), sheet_name=sheet_name)
    df.columns = [str(c).strip() if c is not None else "" for c in df.columns]
    df = df.rename(columns=columns).dropna(subset=["id"])
    content = [c for c in columns.values() if c != "id"]
    df = df.dropna(subset=content, how="all")
    df["id"] = df["id"].map(lambda v: str(int(float(v))))
    df["category"] = df["category"].fillna("").map(_clean_tags)
    for col in ("priority", "title", "format", "source", "expected_output", "date"):
        if col in df.columns:
            df[col] = df[col].map(_fmt)
    return df[list(columns.values())].to_dict("records")


def parse_info(file_path_or_bytes, sheet_name: str) -> list[dict]:
    """Разбирает информационный лист в записи {field, value}."""
    df = pd.read_excel(_source(file_path_or_bytes), sheet_name=sheet_name)
    return [
        {"field": _fmt(row[1]), "value": _fmt(row[2])}
        for row in df.itertuples(index=False)
        if _fmt(row[1]) or _fmt(row[2])
    ]


def info_topics(file_path_or_bytes, sheet_name: str = "ИНФО_Dataset 2") -> list[str]:
    """Возвращает теги из поля «Группировка по признакам/тегам»."""
    topics = []
    for record in parse_info(file_path_or_bytes, sheet_name):
        if "тегам" in record["field"].lower():
            topics.extend(
                re.sub(r"^\d+\.\s*", "", line).strip()
                for line in record["value"].splitlines()
                if line.strip()
            )
    return topics


def calculate_priority_rules(article: dict) -> str:
    """Вычисляет приоритет по правилам ИНФО-листа."""
    kind = _category_kind(article.get("category"))
    text = _text(article)
    low = text.lower()

    if kind == "атака":
        is_ru = "РФ" in text or any(m in low for m in RU_MARKERS)
        if not is_ru:
            return "Низкий"
        return "Высокий" if any(m in low for m in ENERGY_MARKERS) else "Средний"

    if kind == "уязвимость":
        match = re.search(r"наличие эксплойт\w*[\s:]+(\w+)", low)
        if match:
            return "Средний" if match.group(1) in ("нет", "отсутствует") else "Высокий"
        return "Высокий" if "есть эксплойт" in low or "публичный эксплойт" in low else "Средний"

    if kind == "инфо":
        return "Новости ТГ" if "t.me" in low else "Нормальный"

    return article.get("priority") or "Нормальный"


def filter_and_rank_articles(
    articles: list[dict],
    user_interests: list[str],
    target_audience: str = "technical",
) -> list[dict]:
    """Ранжирует статьи по совпадению с интересами, сортирует по (score, priority)."""
    interests = [str(i).strip().lower() for i in user_interests if str(i).strip()]
    fields = SEARCH_FIELDS.get(target_audience, SEARCH_FIELDS["technical"])
    ranked = []
    for article in articles:
        item = dict(article)
        item["priority"] = calculate_priority_rules(item)
        text = _text(item, fields).lower()
        item["score"] = (
            1.0
            if not interests
            else round(sum(1 for interest in interests if interest in text) / len(interests), 2)
        )
        ranked.append(item)
    if interests:
        ranked = [item for item in ranked if item["score"] > 0]
    return sorted(ranked, key=lambda a: (-a["score"], -PRIORITY_RANK.get(a["priority"], 0)))