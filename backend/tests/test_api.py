import pytest
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok", "service": "verishield-ai"}


def test_ordinary_posting_has_no_indicators():
    response = client.post("/analyze", json={"text": "Software engineering internship. Python and SQL required. Apply through our careers portal."})
    assert response.status_code == 200
    data = response.json()
    assert data["risk_score"] == 0
    assert data["risk_level"] == "low"
    assert data["findings"] == []
    assert "not a fraud verdict" in data["disclaimer"]


def test_multiple_indicators_with_evidence():
    text = "Pay a registration fee. Guaranteed job. Contact only on Telegram. Act now!"
    data = client.post("/analyze", json={"text": text, "title": "Job", "url": "https://example.com/job"}).json()
    assert data["risk_level"] == "high"
    assert data["risk_score"] == 80
    assert {f["rule_id"] for f in data["findings"]} == {"upfront_payment", "guaranteed_hiring", "messaging_only", "pressure"}
    assert all(f["evidence"] in text for f in data["findings"])


@pytest.mark.parametrize("text", ["", "   ", "x" * 200001, None],
                         ids=["empty", "whitespace", "oversized", "null"])
def test_invalid_text(text):
    assert client.post("/analyze", json={"text": text}).status_code == 422


def test_missing_text_and_unknown_fields():
    assert client.post("/analyze", json={}).status_code == 422
    assert client.post("/analyze", json={"text": "job", "secret": "not allowed"}).status_code == 422


def test_repetition_does_not_inflate_score():
    data = client.post("/analyze", json={"text": "PAY A TRAINING FEE. " * 20}).json()
    assert data["risk_score"] == 35
    assert data["risk_level"] == "medium"
    assert len(data["findings"]) == 1


def test_whitespace_normalization_and_score_cap():
    text = "Pay a\nregistration fee. Provide your bank details. Guaranteed job. Easy money. Apply immediately. Contact only on WhatsApp. Buy gift cards."
    data = client.post("/analyze", json={"text": text}).json()
    assert len(data["findings"]) == 7
    assert data["risk_score"] == 100


def test_title_and_url_are_not_fetched_or_scored():
    data = client.post("/analyze", json={"text": "Engineering role", "title": "Guaranteed job", "url": "http://127.0.0.1/private"}).json()
    assert data["risk_score"] == 0
