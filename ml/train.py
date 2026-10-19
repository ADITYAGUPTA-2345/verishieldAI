"""Run from the repo root: python -m ml.train. No network access is used."""
import argparse
import hashlib
import json
import platform
import warnings
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import scipy
import sklearn
from sklearn.exceptions import ConvergenceWarning
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, precision_recall_fscore_support
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline

from .data import inspect_and_prepare
from .preprocessing import TEXT_FIELDS, normalize_text

ROOT = Path(__file__).resolve().parents[1]
SEED = 42


def build_pipeline() -> Pipeline:
    return Pipeline([
        ("tfidf", TfidfVectorizer(preprocessor=normalize_text, lowercase=False,
                                  ngram_range=(1, 2), min_df=2, max_features=60000,
                                  sublinear_tf=True)),
        ("classifier", LogisticRegression(class_weight="balanced", solver="liblinear",
                                           C=1.0, max_iter=1000, random_state=SEED)),
    ])


def split_records(records: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    y = np.array([r["label"] for r in records])
    groups = np.array([r["group"] for r in records])
    if min(Counter(y).values()) < 5 or len(set(groups)) < 5:
        raise ValueError("Need at least five rows per class and five description groups for a five-fold stratified group split")
    # Use the first fold selected in advance, never select a fold by model score.
    splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=SEED)
    train, test = next(splitter.split(np.zeros(len(y)), y, groups))
    if set(y[train]) != {0, 1} or set(y[test]) != {0, 1}:
        raise ValueError("Both labels must occur in train and test; more independent minority groups are needed")
    if set(groups[train]) & set(groups[test]):
        raise AssertionError("Description groups overlap across train and test")
    return train, test


def train(dataset: Path, artifact: Path, report_dir: Path) -> dict:
    records, inspection = inspect_and_prepare(dataset)
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "dataset_inspection.json").write_text(json.dumps(inspection, indent=2), encoding="utf-8")
    train_indices, test_indices = split_records(records)
    texts = [r["text"] for r in records]
    y = np.array([r["label"] for r in records])
    pipeline = build_pipeline()
    # Vocabulary, IDF statistics and balanced class weights see ONLY training rows.
    with warnings.catch_warnings():
        warnings.simplefilter("error", ConvergenceWarning)
        pipeline.fit([texts[i] for i in train_indices], y[train_indices])
    predictions = pipeline.predict([texts[i] for i in test_indices])
    precision, recall, f1, _ = precision_recall_fscore_support(y[test_indices], predictions, average="binary", pos_label=1, zero_division=0)
    versions = {"python": platform.python_version(), "scikit_learn": sklearn.__version__,
                "numpy": np.__version__, "scipy": scipy.__version__, "joblib": joblib.__version__}
    split = {"method": "first fold of StratifiedGroupKFold(n_splits=5, shuffle=True)",
             "seed": SEED, "train_rows": len(train_indices), "test_rows": len(test_indices),
             "train_class_distribution": dict(Counter(str(v) for v in y[train_indices])),
             "test_class_distribution": dict(Counter(str(v) for v in y[test_indices])),
             "description_group_overlap": 0, "combined_text_overlap": len({texts[i] for i in train_indices} & {texts[i] for i in test_indices})}
    report = {
        "dataset_sha256": inspection["dataset_sha256"], "versions": versions,
        "trained_at_utc": datetime.now(timezone.utc).isoformat(), "split": split,
        "text_fields": list(TEXT_FIELDS), "threshold": 0.5,
        "parameters": {"ngram_range": [1, 2], "min_df": 2, "max_features": 60000,
                       "sublinear_tf": True, "C": 1.0, "class_weight": "balanced", "solver": "liblinear", "max_iter": 1000},
        "accuracy": float(accuracy_score(y[test_indices], predictions)),
        "precision": float(precision), "recall": float(recall), "f1": float(f1),
        "positive_label": "fraudulent (1)", "confusion_matrix_order": ["legitimate (0)", "fraudulent (1)"],
        "confusion_matrix": confusion_matrix(y[test_indices], predictions, labels=[0, 1]).tolist(),
        "classification_report": classification_report(y[test_indices], predictions, labels=[0, 1], target_names=["legitimate", "fraudulent"], output_dict=True, zero_division=0),
        "majority_baseline_accuracy": float(np.mean(y[test_indices] == 0)),
        "vocabulary_size": len(pipeline.named_steps["tfidf"].vocabulary_),
        "limitations": "Single historical holdout; not company-disjoint or temporal. Near-duplicates and shared templates may remain. Browser page text differs from curated dataset text. Balanced model probabilities are not calibrated fraud likelihoods.",
    }
    artifact.parent.mkdir(parents=True, exist_ok=True)
    # Bundle the ENTIRE fitted preprocessing/classification pipeline with provenance.
    bundle = {"format_version": 1, "pipeline": pipeline, "metadata": report}
    temporary = artifact.with_suffix(".tmp")
    joblib.dump(bundle, temporary, compress=3)
    temporary.replace(artifact)
    report["artifact_sha256"] = hashlib.sha256(artifact.read_bytes()).hexdigest()
    (report_dir / "evaluation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    manifest = {"dataset_sha256": inspection["dataset_sha256"],
                "train_source_csv_rows": [records[i]["source_row"] for i in train_indices],
                "test_source_csv_rows": [records[i]["source_row"] for i in test_indices]}
    (report_dir / "split_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "ml/data/fake_job_postings.csv")
    parser.add_argument("--artifact", type=Path, default=ROOT / "ml/artifacts/job_classifier.joblib")
    parser.add_argument("--reports", type=Path, default=ROOT / "ml/reports")
    args = parser.parse_args()
    if not args.data.is_file():
        parser.error(f"Dataset not found: {args.data}. Place the original fake_job_postings.csv in ml/data/ (see ml/README.md).")
    report = train(args.data, args.artifact, args.reports)
    print(json.dumps({key: report[key] for key in ("accuracy", "precision", "recall", "f1", "confusion_matrix", "split")}, indent=2))


if __name__ == "__main__":
    main()
