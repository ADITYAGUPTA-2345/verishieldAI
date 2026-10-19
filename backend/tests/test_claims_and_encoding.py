"""Targeted claim-noise and Unicode regressions; upstream HTTP is mocked."""
import hashlib
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app, get_tinyfish_client
from backend.app.investigation.claims import extract_claims
from backend.app.investigation.text import repair_text
from backend.app.investigation.tinyfish import TinyFishClient

EMPLOYER = "Legal Raasta Technologies Pvt. Ltd."
HEADINGS = [
    "600 Internship For Students Job Vacancies in Delhi",
    "Salary Search: AI Intern salaries in Delhi",
    "Salary Search: Agriculture Marketing internships",
    "Related jobs",
    "Sponsored internships in Delhi",
    "Find a Job",
]


@pytest.mark.parametrize("heading", HEADINGS)
def test_website_headings_are_not_claims_or_advertised_roles(heading):
    claims = extract_claims(heading, EMPLOYER, title=heading)
    assert [claim.kind for claim in claims] == ["employer_identity"]


def test_job_description_survives_noise_and_related_job_blocks():
    text = "\n".join([
        *HEADINGS[:3], "Job description", "We offer a remote internship.",
        "You must pay a registration fee before joining.",
        "Related jobs", "We guarantee a salary of $9000 for an unrelated job.",
        "Salary Search: Agriculture Marketing internships", "Requirements",
        "Our company is ISO 27001 certified.", "We are affiliated with a university.",
    ])
    claims = extract_claims(text, EMPLOYER, "AI Internship at Legal Raasta Technologies")
    assert {claim.kind for claim in claims} >= {"employer_identity", "payment", "certification", "affiliation", "location"}
    assert not any("unrelated" in claim.text or "Salary Search" in claim.text or "600 Internship" in claim.text for claim in claims)


def test_high_priority_promises_are_kept_before_claim_cap():
    text = "Job description\n" + "\n".join([f"This role offers remote work in location {i}." for i in range(20)])
    text += "\nPay a registration fee before joining.\nWe guarantee a salary of $5000 monthly.\nOur company is ISO 27001 certified.\nWe are affiliated with a university."
    claims = extract_claims(text, EMPLOYER)
    assert len(claims) == 8
    assert {claim.kind for claim in claims} >= {"payment", "compensation", "certification", "affiliation", "employer_identity"}
    assert any("guarantee a salary" in claim.text for claim in claims)


def test_no_section_heading_still_extracts_job_assertions_and_unicode():
    text = "We are hiring engineering interns.\nSalary: \u20b910,000\u2013\u20b915,000 monthly.\nWe never charge an application fee."
    claims = extract_claims(text, EMPLOYER)
    assert {claim.kind for claim in claims} >= {"recruitment", "compensation", "payment"}
    assert any("\u20b910,000\u2013\u20b915,000" in claim.text for claim in claims)


@pytest.mark.parametrize("encoding", ["cp1252", "latin1"])
def test_known_mojibake_is_repaired_without_whole_document_reencoding(encoding):
    punctuation = "\u2013 \u2014 \u2026 \u00b7 \u20b9"
    broken = punctuation.encode("utf-8").decode(encoding)
    value = "\u00c2ngela, S\u00e3o Paulo, \u0926\u093f\u0932\u094d\u0932\u0940 \U0001f6e1 " + broken
    assert repair_text(value) == "\u00c2ngela, S\u00e3o Paulo, \u0926\u093f\u0932\u094d\u0932\u0940 \U0001f6e1 " + punctuation
    assert repair_text(repair_text(value)) == repair_text(value)


def test_valid_unicode_is_never_stripped_or_replaced():
    value = "\u00c2ngela \u00e9l\u00e8ve \u0926\u093f\u0932\u094d\u0932\u0940 \u20b910,000\u2013\u20b915,000 \U0001f600"
    assert repair_text(value) == value


@pytest.mark.parametrize("broken", [False, True], ids=["valid-utf8", "already-mojibaked-text"])
def test_utf8_tinyfish_fastapi_response_and_raw_content_hash(broken):
    url = "https://builtin.com/company/acme-robotics/jobs"
    proper = "Acme Robotics offers internships \u2013 salary \u20b910,000 in \u0926\u093f\u0932\u094d\u0932\u0940. Caf\u00e9 \U0001f600"
    raw = proper.replace("\u2013", "\u2013".encode("utf-8").decode("cp1252")) if broken else proper
    def handler(request):
        if request.method == "GET":
            payload = {"results": [{"url": url, "title": "Acme Robotics Careers"}]}
        else:
            payload = {"results": [{"url": url, "title": "Acme Robotics Careers", "text": raw}], "errors": []}
        # Even a wrong HTTP charset must not turn UTF-8 JSON into mojibake.
        return httpx.Response(200, content=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                              headers={"content-type": "application/json; charset=iso-8859-1"})
    async def factory():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            yield TinyFishClient("mock-not-a-real-key", http)
    app.dependency_overrides[get_tinyfish_client] = factory
    try:
        with TestClient(app) as client:
            response = client.post("/investigate", json={"text": "Employer: Acme Robotics\nWe offer internships.", "employer_name": "Acme Robotics"})
        assert response.status_code == 200
        data = json.loads(response.content.decode("utf-8"))
        source = data["sources_retrieved"][0]
        assert source["excerpt"] == proper
        assert source["encoding_repaired"] is broken
        assert source["content_sha256"] == hashlib.sha256(raw.encode("utf-8")).hexdigest()
        assert data["supporting_evidence"]
        assert all(item["excerpt"] in proper for item in data["supporting_evidence"])
        assert any("\u2013 salary \u20b910,000 in \u0926\u093f\u0932\u094d\u0932\u0940" in item["excerpt"] for item in data["supporting_evidence"])
    finally:
        app.dependency_overrides.clear()
