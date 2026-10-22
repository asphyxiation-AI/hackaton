"""Streamlit-интерфейс: загрузка датасета, сбор новостей, ранжирование и дайджесты."""

from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from src.collectors import collect_all, DEFAULT_SOURCES
from src.exporter import export_to_docx, export_to_markdown
from src.generator import generate_digest
from src.llm import LLMClient
from src.processor import (
    filter_and_rank_articles,
    info_topics,
    parse_dataset,
)

SHEETS = {
    "Технические специалисты (Dataset 1)": "Dataset 1 (тех. специалистам)",
    "Руководство (Dataset 2)": "Dataset 2 (рук-во и  работники)",
}
AUDIENCE = {
    "Dataset 1 (тех. специалистам)": "technical",
    "Dataset 2 (рук-во и  работники)": "management",
}
DEFAULT_TOPICS = ["В РФ", "Энергетика", "Промышленность"]
DISPLAY_COLUMNS = ["ID", "Категория", "Приоритет", "Релевантность", "Дата", "Название/Суть", "Источник"]
OUTPUT_DIR = Path("data/output")


def find_dataset() -> Path | None:
    for base in (Path("data/raw"), Path(".")):
        for path in base.glob("*.xlsx"):
            if path.name.startswith("Датасет"):
                return path
    return None


def render_digest_block(ranked: list[dict], audience_key: str, key_suffix: str) -> None:
    """Блок формирования дайджеста и экспорта (общий для обоих режимов)."""
    with st.expander("📨 Дайджест"):
        digest_key = f"digest_{audience_key}_{key_suffix}"
        if st.button("Сформировать дайджест", key=f"btn_{key_suffix}"):
            with st.spinner("Генерация дайджеста..."):
                try:
                    st.session_state[digest_key] = generate_digest(
                        ranked, audience_key, LLMClient()
                    )
                except Exception as exc:
                    st.error(f"Ошибка LLM: {exc}")
        digest = st.session_state.get(digest_key)
        if digest:
            st.markdown(digest)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            md_path = export_to_markdown(digest, str(OUTPUT_DIR / f"digest_{audience_key}_{stamp}.md"))
            docx_path = export_to_docx(digest, str(OUTPUT_DIR / f"digest_{audience_key}_{stamp}.docx"))
            st.download_button(
                "Скачать .md",
                data=Path(md_path).read_bytes(),
                file_name=Path(md_path).name,
                mime="text/markdown",
                key=f"dl_md_{key_suffix}",
            )
            st.download_button(
                "Скачать .docx",
                data=Path(docx_path).read_bytes(),
                file_name=Path(docx_path).name,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key=f"dl_docx_{key_suffix}",
            )


st.set_page_config(page_title="ИИ-ассистент для энергетики", page_icon="⚡")
st.title("⚡ ИИ-ассистент для энергетики")

mode = st.radio(
    "Источник данных",
    ["Локальный файл (xlsx)", "Сбор из источников (RSS / HTML)"],
    horizontal=True,
)

if mode == "Локальный файл (xlsx)":
    uploaded = st.file_uploader("Файл датасета (xlsx)", type="xlsx")
    if uploaded:
        payload, source_label = uploaded.getvalue(), uploaded.name
    else:
        path = find_dataset()
        payload, source_label = path.read_bytes(), str(path) if path else None
        if path is None:
            st.warning("Файл «Датасет с примерами_v4.0.xlsx» не найден — загрузите его или положите в data/raw/")

    if payload:
        audience_label = st.radio("Аудитория / лист", list(SHEETS), key="file_audience")
        sheet = SHEETS[audience_label]

        articles = parse_dataset(payload, sheet)
        try:
            topics = info_topics(payload)
        except Exception:
            topics = DEFAULT_TOPICS
        default = [t for t in topics if t in DEFAULT_TOPICS] or topics[:2]
        interests = st.multiselect("Интересы / теги", topics, default=default, key="file_interests")

        ranked = filter_and_rank_articles(articles, interests, AUDIENCE[sheet])
        if not ranked:
            st.info("Нет статей, релевантных выбранным интересам.")
        else:
            rows = [
                {
                    "ID": item["id"],
                    "Категория": item["category"],
                    "Приоритет": item["priority"],
                    "Релевантность": item["score"],
                    "Дата": item["date"],
                    "Название/Суть": (item.get("title") or item.get("expected_output") or "")[:120],
                    "Источник": item["source"][:80],
                }
                for item in ranked
            ]
            st.dataframe(pd.DataFrame(rows, columns=DISPLAY_COLUMNS), width="stretch", hide_index=True)
            render_digest_block(ranked, AUDIENCE[sheet], "file")

else:
    st.subheader("Сбор новостей из внешних источников")
    st.caption(
        "По каждому URL пробуется RSS, при отсутствии — парсинг HTML. "
        "По умолчанию используются источники из ИНФО-листа датасета."
    )

    sources_input = st.text_area(
        "URL источников (по одному на строку)",
        value="\n".join(DEFAULT_SOURCES),
        height=150,
    )
    limit_per_source = st.slider("Максимум статей с одного источника", 1, 20, 5)
    collect_btn = st.button("Собрать новости", type="primary")

    if collect_btn:
        sources = [s.strip() for s in sources_input.splitlines() if s.strip()]
        with st.spinner("Идёт сбор новостей… это может занять время"):
            try:
                articles = collect_all(sources, limit_per_source=limit_per_source)
            except Exception as exc:
                st.error(f"Ошибка сбора: {exc}")
                articles = []

        if articles:
            st.success(f"Собрано статей: {len(articles)}")
            audience_label = st.radio("Аудитория", list(SHEETS), key="collect_audience")
            sheet = SHEETS[audience_label]
            topics = DEFAULT_TOPICS
            default = [t for t in topics if t in DEFAULT_TOPICS] or topics[:2]
            interests = st.multiselect("Интересы / теги", topics, default=default, key="collect_interests")

            ranked = filter_and_rank_articles(articles, interests, AUDIENCE[sheet])
            if not ranked:
                st.info("Нет статей, релевантных выбранным интересам.")
            else:
                rows = [
                    {
                        "ID": item["id"],
                        "Категория": item["category"],
                        "Приоритет": item["priority"],
                        "Релевантность": item["score"],
                        "Дата": item["date"],
                        "Название/Суть": (item.get("title") or item.get("expected_output") or "")[:120],
                        "Источник": item["source"][:80],
                    }
                    for item in ranked
                ]
                st.dataframe(pd.DataFrame(rows, columns=DISPLAY_COLUMNS), width="stretch", hide_index=True)
                render_digest_block(ranked, AUDIENCE[sheet], "collect")
        else:
            st.warning("Не удалось собрать статьи. Проверьте URL и подключение к интернету.")