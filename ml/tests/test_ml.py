import csv
import json
from pathlib import Path

import joblib
import numpy as np
import pytest
from fastapi.testclient import TestClient

import backend.app.main as api
from ml.data import inspect_and_prepare
from ml.inference import ModelPredictor
from ml.preprocessing import combine_fields, normalize_text
from ml.train import ROOT, build_pipeline, split_records

DATA = ROOT / "ml/data/fake_job_postings.csv"
ARTIFACT = ROOT / "ml/artifacts/job_classifier.joblib"


@pytest.fixture(scope="module")
def records():
    if not DATA.exists():
        pytest.skip("Original dataset required for data-dependent tests")
    return inspect_and_prepare(DATA)[0]


def test_normalization_handles_missing_html_and_whitespace():
    assert normalize_text(None) == ""
    assert normalize_text("<p>PYTHON &amp; SQL</p>\n  Engineer") == "python & sql engineer"
    assert normalize_text(combine_fields({"title": "Engineer", "description": None})).strip() == "engineer"


def test_pipeline_configuration():
    pipeline = build_pipeline()
    assert pipeline.named_steps["classifier"].class_weight == "balanced"
    assert pipeline.named_steps["classifier"].random_state == 42
    assert pipeline.named_steps["tfidf"].preprocessor is normalize_text
    assert not hasattr(pipeline.named_steps["tfidf"], "vocabulary_")


def test_required_columns_and_labels_are_validated(tmp_path):
    invalid = tmp_path / "invalid.csv"
    invalid.write_text("title,fraudulent\nEngineer,1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Missing required columns"):
        inspect_and_prepare(invalid)
    invalid.write_text("title,company_profile,description,requirements,benefits,fraudulent\nEngineer,,Description,,,\n", encoding="utf-8")
    with pytest.raises(ValueError, match="labels"):
        inspect_and_prepare(invalid)


def test_duplicate_removal_on_original_rows(tmp_path):
    if not DATA.exists():
        pytest.skip("Original dataset required")
    with DATA.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    legitimate = next(row for row in rows if row["fraudulent"] == "0")
    fraudulent = next(row for row in rows if row["fraudulent"] == "1")
    path = tmp_path / "original_rows.csv"
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(legitimate))
        writer.writeheader()
        writer.writerows([legitimate, legitimate, fraudulent])
    cleaned, report = inspect_and_prepare(path)
    assert len(cleaned) == 2
    assert report["full_row_duplicate_excess"] == 1
    assert report["normalized_model_text_duplicate_excess"] == 1


def test_split_is_reproducible_disjoint_and_has_both_classes(records):
    train, test = split_records(records)
    again_train, again_test = split_records(records)
    assert np.array_equal(train, again_train)
    assert np.array_equal(test, again_test)
    assert set(train).isdisjoint(test)
    assert len(train) + len(test) == len(records)
    assert {records[i]["group"] for i in train}.isdisjoint(records[i]["group"] for i in test)
    assert {records[i]["text"] for i in train}.isdisjoint(records[i]["text"] for i in test)
    assert {records[i]["label"] for i in train} == {0, 1}
    assert {records[i]["label"] for i in test} == {0, 1}


@pytest.fixture(scope="module")
def predictor():
    if not ARTIFACT.exists():
        pytest.skip("Train on the real dataset first for artifact tests")
    return ModelPredictor(ARTIFACT)


def test_saved_pipeline_round_trip_matches_real_input(predictor, records, tmp_path):
    _, test = split_records(records)
    text = records[test[0]]["text"]
    expected = predictor.predict(text)
    path = tmp_path / "roundtrip.joblib"
    joblib.dump({"format_version": 1, "pipeline": predictor.pipeline, "metadata": predictor.metadata}, path)
    assert ModelPredictor(path).predict(text) == expected
    assert 0 <= expected["fraud_probability"] <= 1
    assert expected["label"] in {"legitimate", "fraudulent"}


def test_saved_idf_statistics_use_training_only(predictor, records):
    train, _ = split_records(records)
    vectorizer = predictor.pipeline.named_steps["tfidf"]
    analyzer = vectorizer.build_analyzer()
    # Independently recompute document frequency for a fixed sample of learned terms.
    terms = sorted(vectorizer.vocabulary_)[::max(1, len(vectorizer.vocabulary_) // 15)]
    frequencies = dict.fromkeys(terms, 0)
    for index in train:
        tokens = set(analyzer(records[index]["text"]))
        for term in terms:
            frequencies[term] += term in tokens
    for term, count in frequencies.items():
        expected = np.log((1 + len(train)) / (1 + count)) + 1
        assert vectorizer.idf_[vectorizer.vocabulary_[term]] == pytest.approx(expected)


def test_report_metrics_match_saved_model_holdout(predictor, records):
    _, test = split_records(records)
    predictions = predictor.pipeline.predict([records[i]["text"] for i in test])
    truth = np.array([records[i]["label"] for i in test])
    from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support
    report = json.loads((ROOT / "ml/reports/evaluation.json").read_text(encoding="utf-8"))
    precision, recall, f1, _ = precision_recall_fscore_support(truth, predictions, average="binary", zero_division=0)
    assert report["accuracy"] == pytest.approx(accuracy_score(truth, predictions))
    assert report["precision"] == pytest.approx(precision)
    assert report["recall"] == pytest.approx(recall)
    assert report["f1"] == pytest.approx(f1)
    assert report["confusion_matrix"] == confusion_matrix(truth, predictions).tolist()


def test_api_inference_uses_trained_model_without_changing_rules(predictor, records, monkeypatch):
    monkeypatch.setattr(api, "MODEL_PATH", ARTIFACT)
    _, test = split_records(records)
    text = records[test[0]]["text"][:50000]
    from backend.app.analyzer import analyze
    with TestClient(api.app) as client:
        response = client.post("/analyze", json={"text": text})
    assert response.status_code == 200
    data = response.json()
    assert data["ml_prediction"] == predictor.predict(text)
    assert data["risk_score"] == analyze(text).risk_score
    assert data["findings"] == [finding.model_dump() for finding in analyze(text).findings]


@pytest.mark.parametrize("corrupt", [False, True], ids=["missing", "corrupt"])
def test_unavailable_model_preserves_rule_analysis(tmp_path, monkeypatch, corrupt):
    path = tmp_path / "model.joblib"
    if corrupt:
        path.write_bytes(b"invalid artifact")
    monkeypatch.setattr(api, "MODEL_PATH", path)
    with TestClient(api.app) as client:
        response = client.post("/analyze", json={"text": "Pay a registration fee."})
        assert client.get("/health").status_code == 200
    assert response.status_code == 200
    data = response.json()
    assert data["risk_score"] == 35
    assert data["ml_prediction"]["status"] == "unavailable"
    assert data["ml_prediction"]["fraud_probability"] is None
