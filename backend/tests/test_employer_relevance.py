"""Regression fixtures are mocked pages, not claimed live web evidence."""
import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.investigation.claims import extract_employer
from backend.app.investigation.identity import build_queries, normalized_company
from backend.app.investigation.ranking import entity_score, evaluate_source
from backend.app.investigation.schemas import InvestigateRequest
from backend.app.investigation.service import investigate, investigation_context
from backend.app.investigation.tinyfish import TinyFishClient

EMPLOYER = "Legal Raasta Technologies Pvt. Ltd."
PAYLOAD = InvestigateRequest(text="About Careers\nCompany: Legal Raasta Technologies Pvt. Ltd.\nThis internship offers remote work.", title="Internship at Legal Raasta Technologies Pvt. Ltd.")


@pytest.mark.parametrize("generic", ["Careers", "Jobs", "Hiring", "Help", "Internship", "Find a Job", "Our Company", "Recruitment", "Pvt Ltd"])
def test_generic_heading_cannot_be_employer(generic):
    assert extract_employer(f"About {generic}\nWe are hiring.")[0] is None
    assert extract_employer(f"Company: {generic}")[0] is None
    assert extract_employer("Job text", override=generic)[0] is None
    assert entity_score(generic, "Jobs careers hiring help internship find a job") == 0
    assert build_queries(generic) == []


@pytest.mark.parametrize("page", [
    ("https://careers.microsoft.com/", "Microsoft Careers Stage", "Microsoft is hiring software engineers for internships."),
    ("https://jobs.aus.com/", "Careers at Allied Universal", "Allied Universal careers and security jobs. Apply for an internship."),
    ("https://jobs.example.com/", "Find a Job", "Find a job and careers hiring internship help."),
])
def test_unrelated_employers_never_receive_perfect_identity(page):
    signals = evaluate_source(EMPLOYER, *page)
    assert signals["entity_match"] == 0
    assert signals["company_name_similarity"] == 0
    assert not signals["identity_matched"]
    assert signals["source_type"] == "unrelated"


def test_correct_employer_and_explicit_priority():
    employer, method = extract_employer(PAYLOAD.text, PAYLOAD.title)
    assert normalized_company(employer) == "legal raasta technologies"
    assert method == "explicit_company_field"
    assert extract_employer("About Careers\nLegal Raasta Technologies Pvt. Ltd.\nInternship details")[1] == "legal_company_name_line"
    assert extract_employer("Company: Microsoft", override=EMPLOYER)[0].rstrip(".") == EMPLOYER.rstrip(".")
    assert extract_employer("Company: Microsoft", structured=EMPLOYER)[1] == "structured_job_posting"
    assert extract_employer("Company: Microsoft", override=EMPLOYER, structured="Other Company")[1] == "user_supplied"
    assert extract_employer(f"Company: {EMPLOYER}", structured="Careers")[1] == "explicit_company_field"


def test_company_normalization_keeps_identity_tokens_and_joined_brand():
    for value in [EMPLOYER, "LEGAL RAASTA TECHNOLOGIES PRIVATE LIMITED", "LegalRaasta Technologies Pvt Ltd"]:
        assert normalized_company(value) == "legal raasta technologies"
    assert entity_score(EMPLOYER, "LEGALRAASTA TECHNOLOGIES PRIVATE LIMITED is a company") == 1
    assert entity_score(EMPLOYER, "Legal technology jobs and Raasta vacancies") < 1
    assert normalized_company("Limited Run Inc") == "limited run"


def test_employer_specific_queries_recorded_in_preview():
    context = investigation_context(PAYLOAD)
    assert context["search_queries"] == [
        '"Legal Raasta Technologies Pvt Ltd" official website',
        '"Legal Raasta Technologies" careers',
        '"Legal Raasta Technologies" internship',
    ]
    with TestClient(app) as client:
        response = client.post("/investigate/preview", json=PAYLOAD.model_dump())
    assert response.status_code == 200
    assert response.json() == context


def test_official_domain_requires_established_registry_and_identity():
    registry = {"legal raasta technologies": {"legalraasta.com"}}
    text = "Legal Raasta Technologies Private Limited offers services."
    official = evaluate_source(EMPLOYER, "https://www.legalraasta.com/about", EMPLOYER, text, confirmed_domains=registry)
    assert official["source_type"] == "confirmed_official"
    for url in ["https://legalraasta.com.evil.org/", "https://legalraasta-careers.com/", "https://legalraasta.com.fake.in/"]:
        signals = evaluate_source(EMPLOYER, url, EMPLOYER, text, confirmed_domains=registry)
        assert signals["source_type"] == "unverified_employer_related"
        assert signals["domain_match"] == 0
    claimed = evaluate_source(EMPLOYER, "https://www.legalraasta.com/", EMPLOYER, text, claimed_website="https://legalraasta.com/")
    assert claimed["source_type"] == "unverified_employer_related"
    assert evaluate_source(EMPLOYER, "https://legalraasta.com/", "Microsoft Careers", "Microsoft Jobs", confirmed_domains=registry)["source_type"] == "unrelated"


def test_generic_search_results_excluded_and_no_fetch_performed():
    queries = []
    def handler(req):
        assert req.method == "GET", "Unrelated sources must not reach Fetch"
        queries.append(req.url.params["query"])
        return httpx.Response(200, json={"results": [
            {"url": "https://careers.microsoft.com/", "title": "Microsoft Careers Stage", "snippet": "Microsoft careers internships"},
            {"url": "https://jobs.aus.com/", "title": "Careers at Allied Universal", "snippet": "Allied Universal jobs hiring"},
            {"url": "https://jobs.example.com/", "title": "Find a Job", "snippet": "Careers jobs help internships"},
        ]})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            return await investigate(PAYLOAD, TinyFishClient("test-only", http))
    report = asyncio.run(run())
    assert len(queries) == 3 and queries == report.search_queries
    assert not report.sources_retrieved
    assert not report.supporting_evidence
    assert len(report.excluded_sources) == 3
    assert report.message == "Insufficient employer-specific evidence retrieved."
    assert report.verification_status == "insufficient_evidence"


def test_page_identity_rechecked_after_fetch_and_independent_evidence_retained():
    independent = "https://internshala.com/company/legal-raasta"
    redirect = "https://fake.example.com/legal-raasta"
    def handler(req):
        if req.method == "GET":
            return httpx.Response(200, json={"results": [
                {"url": independent, "title": EMPLOYER, "snippet": "Legal Raasta Technologies internships"},
                {"url": redirect, "title": EMPLOYER, "snippet": "Legal Raasta Technologies careers"},
            ]})
        return httpx.Response(200, json={"results": [
            {"url": independent, "title": EMPLOYER, "text": "Legal Raasta Technologies Pvt Ltd advertises internship opportunities."},
            {"url": redirect, "final_url": "https://careers.microsoft.com/", "title": "Microsoft Careers Stage", "text": "Microsoft careers jobs and internships."},
        ], "errors": []})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            return await investigate(PAYLOAD, TinyFishClient("test-only", http), confirmed_domains={})
    report = asyncio.run(run())
    assert len(report.sources_retrieved) == 1
    assert report.sources_retrieved[0].source_type == "independent_employer_related"
    assert report.supporting_evidence
    assert all(e.url == independent for e in report.supporting_evidence)
    assert any(e.stage == "fetch" and "microsoft.com" in e.url for e in report.excluded_sources)
    assert not any(s.source_type == "confirmed_official" for s in report.sources_retrieved)


def test_matching_unknown_domain_is_retrieved_but_cannot_support_claims():
    url = "https://unverified.example.com/legal-raasta"
    def handler(req):
        if req.method == "GET":
            return httpx.Response(200, json={"results": [{"url": url, "title": EMPLOYER}]})
        return httpx.Response(200, json={"results": [{"url": url, "title": EMPLOYER, "text": "Legal Raasta Technologies Pvt Ltd offers internship opportunities."}], "errors": []})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            return await investigate(PAYLOAD, TinyFishClient("test-only", http), confirmed_domains={})
    report = asyncio.run(run())
    assert len(report.sources_retrieved) == 1
    assert not report.supporting_evidence
    assert report.message == "Insufficient employer-specific evidence retrieved."
