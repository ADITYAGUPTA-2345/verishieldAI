"""Integration of additive security fields with real local ML and mocked web data."""
from types import SimpleNamespace

import httpx
from fastapi.testclient import TestClient

from backend.app.main import app, get_tinyfish_client
from backend.app.security import domains
from backend.app.security.advisory import build_advisory
from backend.app.security.domains import analyze_website, compare_domain
from backend.app.security.emails import analyze_emails
from backend.app.investigation.tinyfish import TinyFishClient

REGISTRY = {'acme robotics': {'acmerobotics.com'}}


def test_search_mention_or_official_label_cannot_establish_ownership():
    report = SimpleNamespace(sources_retrieved=[SimpleNamespace(url='https://acmerobotics.com/',source_type='confirmed_official',identity_matched=True)])
    result = analyze_website('https://acmerobotics-careers.com','Acme Robotics',report,registry={})
    assert result.status == 'unavailable'
    assert not result.established_employer_domains


def test_candidates_are_not_established_domains():
    report = SimpleNamespace(sources_retrieved=[SimpleNamespace(url='https://acme-candidate.com/',source_type='unverified_employer_related',identity_matched=True)])
    result = analyze_website('https://acme-candidate.com','Acme Robotics',report,registry={})
    assert result.candidate_domains == ['acme-candidate.com']
    assert not result.established_employer_domains


def test_legitimate_idn_namespace_is_not_automatically_flagged():
    result = compare_domain('https://m\u00fcnchen.com','Munich',['xn--mnchen-3ya.com'])
    assert result.status == 'match'
    assert all(f.severity == 'info' for f in result.findings)


def test_conservative_advisory_categories_do_not_invent_a_probability():
    ordinary = compare_domain('https://acmerobotics.com','Acme Robotics',['acmerobotics.com'])
    public = analyze_emails('Apply by email to recruiter@gmail.com',None,'Acme Robotics',['acmerobotics.com'])
    assert build_advisory(0,True,'legitimate',ordinary,public,150).category == 'No major warning indicators detected'
    assert build_advisory(0,True,'fraudulent',ordinary,public,150).category == 'Review recommended'
    unknown = analyze_website('https://example.com','Acme Robotics',registry={})
    assert build_advisory(0,True,'legitimate',unknown,public,150).category == 'Insufficient information'
    spoof = compare_domain('https://acmerob0tics.com','Acme Robotics',['acmerobotics.com'])
    advisory = build_advisory(0,True,'legitimate',spoof,public,150)
    assert advisory.category == 'Elevated warning indicators'
    assert set(advisory.model_dump()) == {'category','reasons','recommendation','basis'}


def test_analyze_keeps_ml_and_rules_and_adds_security_without_web_calls(monkeypatch):
    monkeypatch.setattr(domains,'load_confirmed_domains',lambda:REGISTRY)
    with TestClient(app) as client:
        response = client.post('/analyze',json={'text':'Company: Acme Robotics\nWe are hiring engineering interns.\nApply to recruitment@acmerob0tics.com','url':'https://acmerobotics-careers-example.com/job','title':'Engineering Internship'})
    assert response.status_code == 200
    result = response.json()
    assert result['ml_prediction']['status'] == 'available'
    assert result['risk_score'] == 0
    assert result['domain_analysis']['registered_domain'] == 'acmerobotics-careers-example.com'
    assert result['email_analysis']['emails'][0]['assessment'] == 'potential_impersonation'
    assert result['advisory']['category'] == 'Elevated warning indicators'
    assert result['job_information']['employer_name'] == 'Acme Robotics'


def test_investigation_reuses_results_and_adds_no_tinyfish_calls(monkeypatch):
    import backend.app.investigation.service as service
    monkeypatch.setattr(domains,'load_confirmed_domains',lambda:REGISTRY)
    monkeypatch.setattr(service,'load_confirmed_domains',lambda:REGISTRY)
    calls = []
    def handler(request):
        calls.append(request.method)
        if request.method == 'GET':
            return httpx.Response(200,json={'results':[{'url':'https://acmerobotics.com/careers','title':'Acme Robotics Careers'}]})
        return httpx.Response(200,json={'results':[{'url':'https://acmerobotics.com/careers','title':'Acme Robotics Careers','text':'Acme Robotics offers engineering internships. Verify our open positions here.'}],'errors':[]})
    async def factory():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            yield TinyFishClient('test-only-key',http)
    app.dependency_overrides[get_tinyfish_client] = factory
    try:
        with TestClient(app) as client:
            response = client.post('/investigate',json={'text':'Company: Acme Robotics\nWe offer internships. Apply to jobs@acmerobotics.com','url':'https://linkedin.com/jobs/123'})
        assert response.status_code == 200
        result = response.json()
        assert calls == ['GET','GET','GET','POST']
        assert result['domain_analysis']['status'] == 'third_party'
        assert 'also retrieved' in result['domain_analysis']['establishment_basis']
        assert result['email_analysis']['emails'][0]['assessment'] == 'domain_match'
        assert result['sources_retrieved'][0]['source_type'] == 'confirmed_official'
        assert result['job_information']['employer_name'] == 'Acme Robotics'
        assert result['advisory']
    finally:
        app.dependency_overrides.clear()


def test_private_header_and_following_account_address_are_not_collected():
    text = 'Signed in as\nhr@gmail.com\nJob description\nContact: alice@acmerobotics.com'
    result = analyze_emails(text,'https://example.com/job','Acme Robotics',['acmerobotics.com'])
    assert [email.address for email in result.emails] == ['alice@acmerobotics.com']
