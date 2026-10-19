"""All upstream responses here are MOCKS, never live evidence or ML labels."""
import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app, get_tinyfish_client
from backend.app.investigation.claims import extract_claims, extract_employer
from backend.app.investigation.ranking import source_signals
from backend.app.investigation.schemas import InvestigateRequest
from backend.app.investigation.service import investigate
from backend.app.investigation.tinyfish import FETCH_URL, SEARCH_URL, TinyFishClient
from backend.app.investigation.urls import public_url

MOCK_KEY = "unit-test-not-a-real-api-key"
MOCK_URL = "https://builtin.com/company/acme-robotics/jobs"
MOCK_TEXT = "Acme Robotics is hiring Python engineers. Our internships offer remote work. We do not charge a registration fee."


def request(**overrides):
    return InvestigateRequest(**{"text": "Employer: Acme Robotics\nAcme Robotics is hiring Python engineers.\nThe internship is remote.\nPay a registration fee before joining.", **overrides})


def run_mock(handler, payload=None, key=MOCK_KEY):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            return await investigate(payload or request(), TinyFishClient(key, http))
    return asyncio.run(run())


def success_handler(req):
    assert req.headers["X-API-Key"] == MOCK_KEY
    if req.url.host == "api.search.tinyfish.ai":
        assert "Acme Robotics" in req.url.params["query"]
        assert "Pay a registration fee" not in req.url.params["query"]
        return httpx.Response(200, json={"results": [
            {"url": "https://unrelated.org/robots", "title": "Other robots", "snippet": "Unrelated"},
            {"url": MOCK_URL, "title": "Acme Robotics Careers", "snippet": "Acme Robotics internships"},
        ]}, headers={"x-request-id": "mock-search-1"})
    assert str(req.url).rstrip("/") == FETCH_URL
    body = json.loads(req.content)
    assert body["ttl"] == 0
    assert body["format"] == "markdown"
    assert body["urls"][0] == MOCK_URL
    return httpx.Response(200, json={"results": [{"url": MOCK_URL, "final_url": MOCK_URL,
        "title": "Acme Robotics Careers", "text": MOCK_TEXT}], "errors": []}, headers={"x-request-id": "mock-fetch-1"})


@pytest.mark.parametrize("text,title,expected", [
    ("Company: Acme Robotics", None, "Acme Robotics"),
    ("About Acme Robotics\nWe build robots.", None, "Acme Robotics"),
    ("Acme Robotics is hiring Python engineers.", None, "Acme Robotics"),
    ("We are hiring", "Engineer at Acme Robotics | Jobs", "Acme Robotics"),
    ("We are hiring", None, None),
    ("Company: Confidential", None, None),
    ("Company: Acme\nCompany: Beta", None, None),
])
def test_employer_extraction(text, title, expected):
    assert extract_employer(text, title)[0] == expected


def test_employer_override_and_claim_categories():
    assert extract_employer("Company: Wrong", override="Acme Robotics")[0] == "Acme Robotics"
    claims = extract_claims("The internship is remote.\nSalary is $5000 monthly.\nPay a registration fee to join.\nWe are affiliated with a university.", "Acme Robotics")
    assert {claim.kind for claim in claims} >= {"employer_identity", "location", "compensation", "payment", "affiliation"}
    assert len(extract_claims("\n".join([f"We are hiring engineers for role {i}." for i in range(30)]), "Acme")) <= 8


@pytest.mark.parametrize("url", ["http://127.0.0.1/", "http://169.254.169.254/latest", "http://[::1]/", "http://localhost/", "http://secret.internal/", "https://user:password@example.com", "file:///etc/passwd", "javascript:alert(1)", "https://example.com:8000/", "https://example.com/\n"])
def test_unsafe_urls_rejected(url):
    assert public_url(url) is None
    with pytest.raises(ValueError):
        request(official_website=url)


def test_domain_lookalikes_not_promoted_to_company_domain():
    assert source_signals("Acme Robotics", MOCK_URL, "Acme Robotics", MOCK_TEXT)[0] == "independent_employer_related"
    assert source_signals("Acme Robotics", "https://acmerobotics.com.evil.org/", "Acme Robotics", MOCK_TEXT)[0] == "unverified_employer_related"


def test_missing_key_and_unknown_employer_make_no_requests():
    def should_not_run(req):
        pytest.fail("Unexpected HTTP request")
    assert run_mock(should_not_run, key="").status == "not_configured"
    assert run_mock(should_not_run, request(text="We are hiring a programmer.")).status == "needs_employer"


def test_real_contract_mocked_ranking_and_verbatim_evidence():
    report = run_mock(success_handler)
    assert report.status == "evidence_found"
    assert len(report.sources_retrieved) == 1
    assert report.sources_retrieved[0].source_type == "independent_employer_related"
    assert report.supporting_evidence
    assert all(e.excerpt in MOCK_TEXT for e in report.supporting_evidence)
    assert all(e.cosine_similarity > 0 and 0 <= e.rank_score <= 1 for e in report.supporting_evidence)
    assert len(report.unverified_claims) == len(report.claims)
    assert {c.operation for c in report.provider_calls} == {"search", "fetch"}
    # Negated policy must never silently become a verified payment claim.
    assert all("cannot verify" in c.reason or "No relevant" in c.reason for c in report.unverified_claims)


@pytest.mark.parametrize("status,code", [(401,"authentication_failed"), (403,"access_denied"), (402,"quota_exhausted"), (429,"rate_limited"), (503,"upstream_http_error")])
def test_http_failures_are_explicit_and_do_not_leak_secrets(status, code):
    report = run_mock(lambda req: httpx.Response(status, text=f"sensitive response {MOCK_KEY}"))
    assert report.status == "failed"
    assert code in " ".join(report.warnings)
    assert MOCK_KEY not in report.model_dump_json()
    assert not report.supporting_evidence


def test_timeout_and_network_failures():
    def timeout(req):
        raise httpx.ReadTimeout("do not echo request details", request=req)
    assert run_mock(timeout).status == "timeout"
    report = run_mock(timeout, request(official_website=MOCK_URL))
    assert report.status == "timeout"
    assert "timeout" in report.warnings
    def network(req):
        raise httpx.ConnectError("private failure text", request=req)
    report = run_mock(network)
    assert report.status == "failed"
    assert "network_error" in report.warnings
    assert "private failure text" not in report.model_dump_json()


def test_invalid_json_and_empty_results_do_not_create_evidence():
    report = run_mock(lambda req: httpx.Response(200, text="not json"))
    assert report.status == "failed"
    assert "invalid_response" in report.warnings
    report = run_mock(lambda req: httpx.Response(200, json={"results": []}))
    assert report.status == "no_sources"
    assert not report.supporting_evidence


def test_fetch_failure_and_partial_success():
    def handler(req):
        if req.url.host == "api.search.tinyfish.ai":
            return httpx.Response(200, json={"results": [{"url": MOCK_URL, "title": "Acme Robotics"}, {"url": "https://acmerobotics.com/about", "title": "Acme Robotics"}]})
        return httpx.Response(200, json={"results": [{"url": MOCK_URL, "title": "Acme Robotics Careers", "text": MOCK_TEXT}], "errors": [{"url": "https://acmerobotics.com/about", "error": "timeout"}]})
    report = run_mock(handler)
    assert report.status == "partial"
    assert report.sources_retrieved
    assert "fetch_timeout" in report.warnings


def test_invalid_redirect_and_original_posting_not_used_as_evidence():
    def handler(req):
        if req.url.host == "api.search.tinyfish.ai":
            return httpx.Response(200, json={"results": [{"url": MOCK_URL, "title": "Acme Robotics"}]})
        return httpx.Response(200, json={"results": [{"url": MOCK_URL, "final_url": "http://127.0.0.1/", "text": MOCK_TEXT}], "errors": []})
    assert not run_mock(handler).sources_retrieved
    assert not run_mock(handler, request(url=MOCK_URL)).sources_retrieved


def test_search_snippets_are_not_page_evidence():
    def handler(req):
        if req.url.host == "api.search.tinyfish.ai":
            return httpx.Response(200, json={"results": [{"url": MOCK_URL, "title": "Acme Robotics Careers", "snippet": MOCK_TEXT}]})
        return httpx.Response(200, json={"results": [], "errors": [{"url": MOCK_URL, "error": "bot_blocked"}]})
    report = run_mock(handler)
    assert not report.supporting_evidence
    assert not report.sources_retrieved


def test_investigate_api_with_mocked_http_keeps_analyze_local():
    async def factory():
        async with httpx.AsyncClient(transport=httpx.MockTransport(success_handler)) as http:
            yield TinyFishClient(MOCK_KEY, http)
    app.dependency_overrides[get_tinyfish_client] = factory
    try:
        with TestClient(app) as client:
            result = client.post("/investigate", json=request().model_dump())
            assert result.status_code == 200
            assert result.json()["status"] == "evidence_found"
            local = client.post("/analyze", json={"text": "Pay a registration fee."}).json()
            assert local["risk_score"] == 35
            assert local["ml_prediction"]["status"] == "available"
    finally:
        app.dependency_overrides.clear()
