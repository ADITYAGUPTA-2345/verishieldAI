"""CSV inspection and deterministic cleaning; never imputes labels."""
import csv
import hashlib
from collections import Counter, defaultdict
from pathlib import Path

from .preprocessing import TEXT_FIELDS, combine_fields, normalize_text


def inspect_and_prepare(path: Path) -> tuple[list[dict], dict]:
    csv.field_size_limit(10_000_000)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        columns = reader.fieldnames or []
        missing = set((*TEXT_FIELDS, "fraudulent")) - set(columns)
        if missing:
            raise ValueError(f"Missing required columns: {sorted(missing)}")
        rows = list(reader)
    if not rows:
        raise ValueError("Dataset is empty")
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ValueError("CSV contains malformed rows")
    labels = Counter(row["fraudulent"].strip() for row in rows)
    if not set(labels) <= {"0", "1"} or set(labels) != {"0", "1"}:
        raise ValueError("fraudulent must contain both original labels 0 and 1; missing/invalid labels are not imputed")
    full = [tuple(row[c] for c in columns) for row in rows]
    without_id = [tuple(row[c] for c in columns if c != "job_id") for row in rows]
    texts = [normalize_text(combine_fields(row)) for row in rows]
    label_groups = defaultdict(set)
    for text, row in zip(texts, rows):
        label_groups[text].add(row["fraudulent"].strip())
    conflicts = sum(len(values) > 1 for values in label_groups.values())
    inspection = {
        "dataset_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "rows": len(rows), "columns": columns, "class_distribution": dict(labels),
        "missing_values": {c: sum(not row[c].strip() for row in rows) for c in columns},
        "full_row_duplicate_excess": len(full) - len(set(full)),
        "duplicates_excluding_job_id_excess": len(without_id) - len(set(without_id)),
        "normalized_model_text_duplicate_excess": len(texts) - len(set(texts)),
        "conflicting_text_groups": conflicts,
        "empty_text_rows": sum(not text for text in texts),
    }
    if conflicts:
        raise ValueError(f"Found {conflicts} normalized text groups with conflicting labels; review the source labels")
    prepared, seen = [], set()
    for index, (row, text) in enumerate(zip(rows, texts)):
        if not text or text in seen:
            continue
        seen.add(text)
        # Same description with different titles/metadata must stay in one fold.
        group = normalize_text(row["description"]) or text
        prepared.append({"text": combine_fields(row), "label": int(row["fraudulent"]),
                         "group": hashlib.sha256(group.encode()).hexdigest(),
                         "source_row": index + 2})
    inspection["cleaned_rows"] = len(prepared)
    inspection["cleaned_class_distribution"] = dict(Counter(str(r["label"]) for r in prepared))
    inspection["description_groups"] = len({r["group"] for r in prepared})
    return prepared, inspection
