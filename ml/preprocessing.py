"""Stateless text normalization shared by training and saved inference pipeline."""
import html
import re

TEXT_FIELDS = ("title", "company_profile", "description", "requirements", "benefits")


def normalize_text(text: str | None) -> str:
    value = html.unescape(text or "")
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip().lower()


def combine_fields(row: dict) -> str:
    return " ".join(row.get(field) or "" for field in TEXT_FIELDS)
