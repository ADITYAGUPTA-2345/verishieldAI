"""Registered-domain and lookalike indicators; never discovers ownership by guess."""
import ipaddress
import re
from urllib.parse import urlsplit

import idna

from ..investigation.identity import normalized_company
from ..investigation.trust import load_confirmed_domains
from ..investigation.urls import domain_label, registered_domain
from .schemas import DomainAnalysis, SecurityFinding

RECRUITMENT_PLATFORMS = frozenset({
    "linkedin.com", "indeed.com", "internshala.com", "glassdoor.com", "builtin.com",
    "greenhouse.io", "lever.co", "ashbyhq.com", "workdayjobs.com", "myworkdayjobs.com",
    "smartrecruiters.com", "naukri.com", "wellfound.com", "workable.com",
})
# Limited, documented confusable set. Never presented as a complete homograph detector.
SUBSTITUTIONS = str.maketrans({"0": "o", "1": "l", "3": "e", "4": "a", "5": "s", "7": "t",
    "\u0430": "a", "\u0435": "e", "\u043e": "o", "\u0440": "p", "\u0441": "c", "\u0443": "y",
    "\u0445": "x", "\u0456": "i", "\u0458": "j", "\u0455": "s", "\u04cf": "l", "\u03bf": "o"})


def host_details(value: str | None) -> tuple[str | None, str | None, str | None]:
    """Normalize an HTTP(S) URL or bare domain with IDNA/UTS46; no resolution."""
    if not value or any(ord(c) < 33 for c in value) or "\\" in value or len(value) > 4096:
        return None, None, None
    try:
        parsed = urlsplit(value if "://" in value else "https://" + value)
        if parsed.scheme not in {"http", "https"} or parsed.username is not None or parsed.password is not None:
            return None, None, None
        host = (parsed.hostname or "").rstrip(".")
        try:
            ipaddress.ip_address(host)
            return host.lower(), host.lower(), None
        except ValueError:
            pass
        ascii_host = idna.encode(host, uts46=True, std3_rules=True).decode("ascii").lower()
        unicode_host = idna.decode(ascii_host)
        return ascii_host, unicode_host, registered_domain("https://" + ascii_host) or None
    except (ValueError, UnicodeError, idna.IDNAError):
        return None, None, None


def edit_similarity(first: str, second: str) -> float:
    """One minus Levenshtein distance / max length, bounded domain-label inputs."""
    if not first or not second:
        return 0.0
    previous = list(range(len(second) + 1))
    for index, left in enumerate(first, 1):
        current = [index]
        for other, right in enumerate(second, 1):
            current.append(min(current[-1]+1, previous[other]+1, previous[other-1]+(left != right)))
        previous = current
    return 1 - previous[-1] / max(len(first), len(second))


def established_domains(employer: str | None, investigation=None, registry=None) -> tuple[list[str], list[str], str]:
    registry = load_confirmed_domains() if registry is None else registry
    confirmed = set()
    for value in registry.get(normalized_company(employer or ""), set()):
        _, _, domain = host_details(value)
        if domain:
            confirmed.add(domain)
    candidates, live_confirmed = set(), False
    for source in getattr(investigation, "sources_retrieved", []):
        _, _, domain = host_details(source.url)
        if not domain:
            continue
        if source.source_type == "confirmed_official" and source.identity_matched and domain in confirmed:
            live_confirmed = True
        elif source.source_type == "unverified_employer_related":
            candidates.add(domain)
    basis = ("Operator-reviewed registry; matching official page also retrieved by TinyFish." if live_confirmed
             else "Operator-reviewed employer-domain registry." if confirmed
             else "No independently established employer domain available. Search mentions and supplied website hints do not establish ownership.")
    return sorted(confirmed), sorted(candidates - confirmed), basis


def compare_domain(value: str | None, employer: str | None, official_domains: list[str], *, platform_exception: bool = True) -> DomainAnalysis:
    host, unicode_host, domain = host_details(value)
    result = DomainAnalysis(status="unavailable", employer_name=employer, hostname=host,
        unicode_hostname=unicode_host, registered_domain=domain,
        established_employer_domains=sorted(set(official_domains)), message="Domain verification is unavailable: no established employer domain.")
    def finding(code, severity, explanation, target=None, similarity=None):
        result.findings.append(SecurityFinding(code=code, severity=severity, explanation=explanation,
            observed_domain=domain or host, compared_domain=target, similarity=similarity))
    if host and any(label.startswith("xn--") for label in host.split(".")):
        finding("idn_domain", "info", "This hostname uses IDN/punycode. Internationalized domains can be legitimate; inspect its Unicode and ASCII spellings.")
    if not official_domains:
        return result
    if not host:
        result.message = "Domain verification is unavailable: no usable current website URL."
        return result
    if domain in official_domains:
        result.status = "match"
        result.message = "Current website is within an established employer registered domain; the offer itself is not verified."
        finding("employer_domain_match", "info", result.message, domain)
        return result
    if platform_exception and domain in RECRUITMENT_PLATFORMS:
        result.status = "third_party"
        result.message = "Known third-party recruitment platform. A domain difference alone is not an impersonation finding. Employer authorization is unverified."
        finding("third_party_recruitment_platform", "info", result.message)
        return result
    result.status = "review"
    result.message = "Review the recruitment website against the established employer domains."
    if domain:
        finding("registered_domain_mismatch", "low", "Recruitment website registered domain differs from the operator-established employer domain. This may be a legitimate third party and is not proof of fraud.", official_domains[0])
    else:
        finding("unrecognized_registered_domain", "info", "No public-suffix registered domain was recognized; do not assume the hostname is an employer-owned domain.")
    observed_label = domain_label("https://" + (domain or host)) if domain else host.split(".")[0]
    try:
        display_label = idna.decode(observed_label)
    except (ValueError, idna.IDNAError):
        display_label = observed_label
    for official in official_domains:
        target_label = domain_label("https://" + official)
        try:
            target_label = idna.decode(target_label)
        except (ValueError, idna.IDNAError):
            pass
        if host.startswith(official + ".") or ("." + official + ".") in host:
            finding("misleading_subdomain", "high", "The established employer domain appears inside a different hostname, not as its registered domain.", official)
        similarity = edit_similarity(display_label, target_label)
        if len(target_label) >= 4 and similarity >= 0.80:
            finding("lookalike_domain", "medium", "A different domain label closely resembles the established employer's label (normalized edit distance). Similarity is an indicator, not ownership proof.", official, round(similarity, 4))
        skeleton = display_label.translate(SUBSTITUTIONS).replace("rn", "m").replace("vv", "w")
        if display_label != target_label and skeleton == target_label:
            finding("character_substitution", "high", "The different domain resembles the established employer label after common character/confusable substitutions.", official, round(similarity, 4))
        compact = re.sub(r"[^a-z0-9]", "", display_label)
        if len(target_label) >= 4 and target_label in compact and display_label != target_label:
            finding("employer_name_affix", "medium", "An unrelated registered-domain label embeds the established employer label with extra words or characters.", official)
    return result


def analyze_website(value, employer, investigation=None, registry=None) -> DomainAnalysis:
    official, candidates, basis = established_domains(employer, investigation, registry)
    result = compare_domain(value, employer, official)
    result.candidate_domains = candidates
    result.establishment_basis = basis
    return result
