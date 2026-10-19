"""Offline controlled fixtures, not claims about real domain owners."""
import pytest

from backend.app.security.domains import analyze_website, compare_domain, edit_similarity

OFFICIAL = ["acmerobotics.com"]


def codes(result):
    return {finding.code for finding in result.findings}


def test_exact_and_organizational_subdomain_match():
    for url in ["https://acmerobotics.com/job", "https://careers.acmerobotics.com/"]:
        result = compare_domain(url, "Acme Robotics", OFFICIAL)
        assert result.status == "match"
        assert "registered_domain_mismatch" not in codes(result)


@pytest.mark.parametrize("url,code", [
    ("https://acmerobotics-careers-example.com", "employer_name_affix"),
    ("https://acmerobotics.com.fakejobs.org", "misleading_subdomain"),
    ("https://acmerob0tics.com", "character_substitution"),
    ("https://acmerobotic.com", "lookalike_domain"),
    ("https://acmerobotics.org", "lookalike_domain"),
])
def test_impersonation_indicators(url, code):
    result = compare_domain(url, "Acme Robotics", OFFICIAL)
    assert result.status == "review"
    assert code in codes(result)
    assert result.registered_domain not in OFFICIAL


def test_punycode_and_unicode_are_equivalent_and_disclosed():
    # Cyrillic o inside a Latin-looking label.
    result = compare_domain("https://acmerob\u043etics.com", "Acme Robotics", OFFICIAL)
    again = compare_domain("https://" + result.hostname, "Acme Robotics", OFFICIAL)
    assert result.hostname.startswith("xn--")
    assert "idn_domain" in codes(result)
    assert "character_substitution" in codes(result)
    assert again.model_dump() == result.model_dump()


def test_missing_official_and_untrusted_website_hint_do_not_establish_ownership():
    result = analyze_website("https://acmerobotics.com", "Acme Robotics", registry={})
    assert result.status == "unavailable"
    assert not result.established_employer_domains
    assert not result.findings


def test_third_party_platform_is_not_a_mismatch_warning():
    result = compare_domain("https://www.linkedin.com/jobs/123", "Acme Robotics", OFFICIAL)
    assert result.status == "third_party"
    assert all(f.severity == "info" for f in result.findings)
    assert "registered_domain_mismatch" not in codes(result)


def test_registry_is_normalized_and_no_url_or_ip_is_falsely_matched():
    result = analyze_website("https://careers.acmerobotics.com/", "Acme Robotics Inc", registry={"acme robotics": {"acmerobotics.com"}})
    assert result.status == "match"
    assert compare_domain(None, "Acme", OFFICIAL).status == "unavailable"
    assert compare_domain("http://127.0.0.1/", "Acme", OFFICIAL).registered_domain is None
    assert edit_similarity("acme", "acme") == 1
