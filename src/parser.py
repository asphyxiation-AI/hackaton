"""Чтение входных документов: Excel, Word, текстовые файлы."""

from pathlib import Path

import pandas as pd
from docx import Document


def read_excel(path: str | Path) -> dict[str, pd.DataFrame]:
    """Возвращает словарь: имя листа -> DataFrame."""
    return pd.read_excel(path, sheet_name=None)


def read_docx(path: str | Path) -> str:
    """Возвращает текст документа Word."""
    return "\n".join(p.text for p in Document(path).paragraphs)


def read_text(path: str | Path) -> str:
    """Возвращает содержимое текстового файла."""
    return Path(path).read_text(encoding="utf-8")


PARSERS = {".xlsx": read_excel, ".xls": read_excel, ".docx": read_docx, ".txt": read_text}


def parse(path: str | Path):
    """Разбирает файл по расширению; UnknownFormatError при неподдержанном типе."""
    suffix = Path(path).suffix.lower()
    try:
        return PARSERS[suffix](path)
    except KeyError as exc:
        raise ValueError(f"Неподдерживаемый формат: {suffix}") from exc