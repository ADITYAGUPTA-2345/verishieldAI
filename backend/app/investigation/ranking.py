"""Local, transparent retrieval ranking independent of the trained job model."""
import re
from difflib import SequenceMatcher
from .identity import company_tokens, normalized_company, words

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .schemas import Claim, Evidence, Source
from .urls import domain_label, registered_domain

INDEPENDENT_DOMAINS = {"linkedin.com", "internshala.com", "crunchbase.com", "builtin.com", "ambitionbox.com", "glassdoor.com", "indeed.com", "zaubacorp.com", "thecompanycheck.com", "tracxn.com"}


def entity_tokens(employer: str) -> list[str]:
    return company_tokens(employer)


def entity_score(employer: str, text: str) -> float:
    tokens = company_tokens(employer)
    if not tokens:
        return 0.0
    source_words = words(text[:80000])
    canonical = " ".join(tokens)
    normalized = " ".join(source_words)
    if re.search(r"(?<!\w)" + re.escape(canonical) + r"(?!\w)", normalized):
        return 1.0
    # A joined trading-name spelling must still include all identity tokens.
    if "".join(tokens) in source_words:
        return 1.0
    compact = "".join(tokens)
    if any("".join(source_words[i:i+size]) == compact for size in range(1, len(tokens)+1) for i in range(len(source_words)-size+1)):
        return 1.0
    # Partial identity can be diagnostic, never a perfect match or evidence gate.
    best = 0.0
    wanted = set(tokens)
    for index, token in enumerate(source_words):
        if token in wanted:
            window = set(source_words[max(0, index-len(tokens)):index+len(tokens)+2])
            best = max(best, len(wanted & window) / len(wanted))
    return min(0.79, best)


def name_similarity(employer: str, text: str) -> float:
    target = " ".join(company_tokens(employer))
    if not target:
        return 0.0
    if entity_score(employer, text) == 1:
        return 1.0
    tokens = words(text[:12000])
    wanted = set(company_tokens(employer))
    count = len(wanted)
    windows = [" ".join(tokens[max(0, i-1):i+count+1]) for i,t in enumerate(tokens) if t in wanted]
    return max((SequenceMatcher(None, target, window).ratio() for window in windows), default=0.0)


def evaluate_source(employer: str, url: str, title: str, text: str, claimed_website=None, confirmed_domains=None):
    entity = max(entity_score(employer, title), entity_score(employer, text))
    similarity = max(name_similarity(employer, title), name_similarity(employer, text))
    matched = entity == 1.0  # Necessary condition; careers/jobs never bypass it.
    domain = registered_domain(url)
    registered = (confirmed_domains or {}).get(normalized_company(employer), set())
    domain_match = float(bool(domain) and (domain in registered or domain_label(url).casefold() == "".join(company_tokens(employer))))
    if not matched:
        kind, relevance, reason = "unrelated", 0.0, "No complete normalized employer identity in title or retrieved text"
    elif domain in registered:
        kind, relevance, reason = "confirmed_official", 1.0, "Matching employer identity and operator-confirmed registered domain"
    elif domain in INDEPENDENT_DOMAINS and entity_score(employer, title) == 1:
        kind, relevance, reason = "independent_employer_related", 0.75, "Employer-specific page on an external publisher; content may be self-reported and claims remain unverified"
    else:
        kind, relevance, reason = "unverified_employer_related", 0.4, "Employer name matches; website ownership and independence are not established"
    if claimed_website and domain == registered_domain(claimed_website):
        domain_match = 1.0
        if kind != "confirmed_official":
            reason += "; supplied website is an unverified hint"
    return {"source_type": kind, "entity_match": round(entity, 4), "identity_matched": matched,
            "company_name_similarity": round(similarity, 4), "domain_match": domain_match,
            "source_relevance": relevance, "identity_reason": reason}


def source_signals(employer: str, url: str, title: str, text: str, claimed_website=None):
    signals = evaluate_source(employer, url, title, text, claimed_website)
    return signals["source_type"], signals["entity_match"], signals["source_relevance"]


def passages(text: str) -> list[str]:
    # Retain verbatim excerpts: no generated summaries, HTML interpretation, or
    # claiming search snippets were fetched page content. Cap CPU and output size.
    result = []
    for paragraph in re.split(r"\n\s*\n|\n|(?<=[.!?])\s+", text[:80000]):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        for index in range(0, min(len(paragraph), 2000), 450):
            result.append(paragraph[index:index + 450])
            if len(result) >= 120:
                return result
    return result


def rank_evidence(employer: str, claims: list[Claim], sources: list[Source], content: dict[str, str]) -> list[Evidence]:
    chunks = [(source, passage) for source in sources
              if source.identity_matched and source.source_type != "unrelated"
              and max(entity_score(employer, source.title), entity_score(employer, content[source.id])) == 1
              for passage in passages(content[source.id])]
    if not chunks or not claims:
        return []
    queries = [employer + " " + claim.text for claim in claims]
    try:
        # This is a new retrieval vectorizer fitted only to this investigation.
        # The frozen ML classifier and its training vocabulary are never changed.
        matrix = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, max_features=15000).fit_transform(queries + [p for _, p in chunks])
        similarities = cosine_similarity(matrix[:len(claims)], matrix[len(claims):])
    except ValueError:  # Empty vocabulary, e.g. punctuation-only remote content.
        return []
    evidence = []
    for claim_index, claim in enumerate(claims):
        candidates = []
        claim_terms = set(re.findall(r"\w+", claim.text.casefold())) - set(entity_tokens(employer)) - ENGLISH_STOP_WORDS
        claim_terms -= {"posting", "employer", "names", "job", "role", "position"}
        for chunk_index, (source, passage) in enumerate(chunks):
            similarity = float(similarities[claim_index, chunk_index])
            score = (0.35 * similarity + 0.25 * source.entity_match + 0.15 * source.company_name_similarity
                     + 0.15 * source.source_relevance + 0.10 * source.domain_match)
            source.cosine_similarity = max(source.cosine_similarity, round(similarity, 4))
            # An employer-name match and actual text overlap are both required.
            if source.source_type not in {"confirmed_official", "independent_employer_related"} or not source.identity_matched or source.entity_match < 1 or similarity < 0.08:
                continue
            if source.source_type != "confirmed_official" and entity_score(employer, passage) != 1:
                continue  # Do not cite generic job/navigation text from independent pages.
            passage_terms = set(re.findall(r"\w+", passage.casefold()))
            if claim.kind != "employer_identity" and not (claim_terms & passage_terms):
                continue  # Employer-name overlap alone cannot support a job claim.
            candidates.append((score, similarity, source, passage))
        candidates.sort(key=lambda candidate: (-candidate[0], candidate[2].url))
        selected = set()
        for score, similarity, source, passage in candidates:
            if source.id in selected:
                continue
            selected.add(source.id)
            source.rank_score = max(source.rank_score, round(score, 4))
            evidence.append(Evidence(claim_id=claim.id, source_id=source.id, url=source.url,
                                     excerpt=passage, cosine_similarity=round(similarity, 4), rank_score=round(score, 4)))
            if len(selected) == 2:
                break
    sources.sort(key=lambda source: (-source.rank_score, -source.source_relevance, source.url))
    return evidence
