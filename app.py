"""Streamlit-интерфейс: загрузка датасета, ранжирование и дайджесты."""

from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from src.exporter import export_to_docx, export_to_markdown
from src.generator import generate_digest
from src.llm import LLMClient
from src.processor import filter_and_rank_articles, info_topics, parse_dataset

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


st.set_page_config(page_title="ИИ-ассистент для энергетики", page_icon="⚡")
st.title("⚡ ИИ-ассистент для энергетики")

uploaded = st.file_uploader("Файл датасета (xlsx)", type="xlsx")
if uploaded:
    payload, source_label = uploaded.getvalue(), uploaded.name
else:
    path = find_dataset()
    payload, source_label = path.read_bytes(), str(path) if path else None
    if path is None:
        st.warning("Файл «Датасет с примерами_v4.0.xlsx» не найден — загрузите его или положите в data/raw/")

if payload:
    audience_label = st.radio("Аудитория / лист", list(SHEETS))
    sheet = SHEETS[audience_label]

    articles = parse_dataset(payload, sheet)
    try:
        topics = info_topics(payload)
    except Exception:
        topics = DEFAULT_TOPICS
    default = [t for t in topics if t in DEFAULT_TOPICS] or topics[:2]
    interests = st.multiselect("Интересы / теги", topics, default=default)

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
        st.dataframe(pd.DataFrame(rows, columns=DISPLAY_COLUMNS), use_container_width=True, hide_index=True)

        with st.expander("📨 Дайджест"):
            audience_key = AUDIENCE[sheet]
            digest_key = f"digest_{audience_key}"
            if st.button("Сформировать дайджест"):
                with st.spinner("Генерация дайджеста..."):
                    try:
                        st.session_state[digest_key] = generate_digest(ranked, audience_key, LLMClient())
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
                )
                st.download_button(
                    "Скачать .docx",
                    data=Path(docx_path).read_bytes(),
                    file_name=Path(docx_path).name,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )