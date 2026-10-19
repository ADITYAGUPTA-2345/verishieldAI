"""Bounded employer investigation; every evidence excerpt comes from Fetch."""
import asyncio
import hashlib
import re
from datetime import datetime, timezone

from .claims import extract_claims, extract_employer
from .ranking import evaluate_source, rank_evidence
from .identity import build_queries, normalized_company
from .trust import load_confirmed_domains
from .schemas import ExcludedSource, InvestigationReport, InvestigateRequest, Source, UnverifiedClaim
from .tinyfish import TinyFishClient, TinyFishError
from .urls import public_url, same_page
from .text import repair_text


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def text_field(row: dict, key: str, limit: int, repair: bool = True) -> str:
    value = row.get(key)
    if not isinstance(value, str):
        return ""
    value = value[:limit]
    return repair_text(value) if repair else value


def investigation_context(request: InvestigateRequest) -> dict:
    employer, method = extract_employer(request.text, request.title, request.employer_name, request.structured_employer_name)
    return {"employer_name": employer, "employer_extraction": method,
            "normalized_employer": normalized_company(employer) if employer else None,
            "search_queries": build_queries(employer, request.text) if employer else []}


async def investigate(request: InvestigateRequest, client: TinyFishClient, confirmed_domains=None) -> InvestigationReport:
    context = investigation_context(request)
    employer, method = context["employer_name"], context["employer_extraction"]
    confirmed_domains = load_confirmed_domains() if confirmed_domains is None else confirmed_domains
    claims = extract_claims(request.text, employer, request.title)
    report = InvestigationReport(employer_name=employer, employer_extraction=method,
        status="needs_employer", message="Could not identify one employer confidently. Enter the employer name and retry.",
        claims=claims, checked_at=now(), normalized_employer=context["normalized_employer"], search_queries=context["search_queries"])
    report.unverified_claims = [UnverifiedClaim(claim_id=c.id, text=c.text, reason="No independent corroboration yet.") for c in claims]
    if not employer:
        report.verification_status = "needs_employer"
        return report
    if not client.configured:
        report.status = "not_configured"
        report.message = "Set TINYFISH_API_KEY in backend/.env and restart the backend. No web request was made."
        return report

    async def retrieve():
        # Only a bounded employer query leaves the backend, not raw job-page text.
        # Strip search operators and quotes from the employer rather than executing
        # query syntax supplied by a posting.
        results = []
        for query in report.search_queries:
            try:
                results.extend(await client.search(query))
            except TinyFishError as error:
                if str(error) in {"authentication_failed", "access_denied", "rate_limited", "quota_exhausted"} or (not results and not request.official_website):
                    raise
                report.warnings.append("search_" + str(error))
                break
        candidates = []
        if request.official_website:
            candidates.append((2.0, request.official_website))
            report.warnings.append("The supplied company website is a claim, not authenticated ownership.")
        excluded_urls = set()
        for row in results:
            url = public_url(row.get("url"))
            if not url or same_page(url, request.url):
                continue
            title = text_field(row, "title", 500)
            snippet = text_field(row, "snippet", 2000)
            signals = evaluate_source(employer, url, title, snippet, request.official_website, confirmed_domains)
            if signals["identity_matched"]:
                candidates.append((0.6 * signals["entity_match"] + 0.4 * signals["source_relevance"], url))
            elif url not in excluded_urls:
                excluded_urls.add(url)
                report.excluded_sources.append(ExcludedSource(url=url, title=title, stage="search", reason=signals["identity_reason"], entity_match=signals["entity_match"], company_name_similarity=signals["company_name_similarity"]))
        candidates.sort(key=lambda candidate: (-candidate[0], candidate[1]))
        urls = list(dict.fromkeys(url for _, url in candidates if not same_page(url, request.url)))[:4]
        if not urls:
            return
        fetched = await client.fetch(urls)
        content, seen_final = {}, set()
        for row in fetched["results"][:10]:
            if not isinstance(row, dict):
                report.warnings.append("invalid_page_result")
                continue
            requested = public_url(row.get("url"))
            final = public_url(row.get("final_url") or row.get("url"))
            raw_text = text_field(row, "text", 80000, repair=False).strip()
            text = repair_text(raw_text)
            if requested not in urls or not final or same_page(final, request.url) or not text:
                report.warnings.append("page_rejected_or_empty")
                continue
            if final in seen_final:
                continue
            seen_final.add(final)
            raw_title = text_field(row, "title", 500, repair=False)
            title = repair_text(raw_title)
            signals = evaluate_source(employer, final, title, text, request.official_website, confirmed_domains)
            if not signals["identity_matched"]:
                report.excluded_sources.append(ExcludedSource(url=final, title=title, stage="fetch", reason=signals["identity_reason"], entity_match=signals["entity_match"], company_name_similarity=signals["company_name_similarity"]))
                continue
            source = Source(id=f"source-{len(report.sources_retrieved)+1}", url=final,
                requested_url=requested, title=title or final, **signals, retrieved_at=now(),
                characters_retrieved=len(raw_text), content_sha256=hashlib.sha256(raw_text.encode("utf-8")).hexdigest(), excerpt=text[:450],
                encoding_repaired=(text != raw_text or title != raw_title))
            content[source.id] = text
            report.sources_retrieved.append(source)
        for error in fetched.get("errors", [])[:10]:
            # Error messages may echo credentials or arbitrary provider text.
            # Return only fixed codes, never the provider's error body.
            allowed = {"timeout", "bot_blocked", "login_required", "page_not_found", "target_unreachable", "target_http_error", "empty_content", "invalid_url", "invalid_redirect_url", "proxy_error", "content_too_large"}
            code = error.get("error") if isinstance(error, dict) else None
            report.warnings.append("fetch_" + (code if isinstance(code, str) and code in allowed else "page_failed"))
        if len(seen_final) < len(urls) and not fetched.get("errors"):
            report.warnings.append("Some requested pages were not returned by TinyFish.")
        if not report.sources_retrieved and fetched.get("errors"):
            raise TinyFishError("timeout" if all(isinstance(e, dict) and e.get("error") == "timeout" for e in fetched["errors"]) else "page_fetch_failed")
        report.supporting_evidence = rank_evidence(employer, claims, report.sources_retrieved, content)

    failure = None
    try:
        await asyncio.wait_for(retrieve(), timeout=85)
    except asyncio.TimeoutError:
        failure = "timeout"
    except TinyFishError as error:
        failure = str(error)
    report.provider_calls = client.calls.copy()
    report.checked_at = now()
    if failure:
        report.warnings.append(failure)
        report.status = "partial" if report.sources_retrieved else ("timeout" if failure == "timeout" else "failed")
        report.message = f"Investigation did not finish: {failure}. No claim has been verified."
    elif report.supporting_evidence:
        report.verification_status = "official_domain_established" if any(s.source_type == "confirmed_official" for s in report.sources_retrieved) else "employer_related_sources_only"
        report.status = "partial" if any(w.startswith(("search_", "fetch_", "page_", "Some ")) for w in report.warnings) else "evidence_found"
        report.message = "Retrieved related employer passages. Review the sources; the offer and claims remain unverified."
    else:
        report.status = "no_sources"
        report.message = "Insufficient employer-specific evidence retrieved."
    for claim in report.unverified_claims:
        claim.related_source_ids = list(dict.fromkeys(e.source_id for e in report.supporting_evidence if e.claim_id == claim.claim_id))
        claim.reason = "Related text found, but lexical similarity cannot verify this claim." if claim.related_source_ids else "No relevant independent passage found in the retrieved pages."
    return report
