# TinyFish integration and evidence retrieval

## Implemented API use

The backend uses the documented [TinyFish Search](https://docs.tinyfish.ai/search-api/reference) and [Fetch](https://docs.tinyfish.ai/fetch-api/reference) REST APIs through HTTPX:

- GET `https://api.search.tinyfish.ai` with an employer-specific query.
- POST `https://api.fetch.tinyfish.ai` with up to four URLs, format=markdown, ttl=0, no requested links/images, and per_url_timeout_ms=30000.
- Authentication: backend-only X-API-Key header. No external LLM, TinyFish Agent, or Research API is called.

Get a key from https://agent.tinyfish.ai/api-keys . Copy `backend/.env.example` to `backend/.env` only when it does not already exist, set TINYFISH_API_KEY locally, and restart FastAPI. Never publish the file. Requests may consume the account's allowance; live diagnostics are manual, not part of pytest.

## Request sequence

1. `/investigate/preview` selects the employer locally and shows generated queries. No key/web request is needed for the preview.
2. `/investigate` extracts up to eight relevant claims, discovers URLs through Search, and rechecks identity after Fetch.
3. Search snippets select candidates; they are never represented as fetched page evidence.
4. Fetched passages are locally ranked and returned with source URLs, timestamps, hashes, exclusions and uncertainty.

A user-provided employer overrides structured JobPosting metadata, which precedes explicit Company/Employer text and lower-confidence heuristics. Generic Careers/Jobs/Hiring/Help/Internship identities are invalid. The extension clears stale overrides between scans. Multiple ambiguous names require user correction.

For Legal Raasta Technologies Pvt. Ltd., queries are:

```text
"Legal Raasta Technologies Pvt Ltd" official website
"Legal Raasta Technologies" careers
"Legal Raasta Technologies" internship
```

Names are normalized for case, punctuation and joined brand spellings. Only trailing corporate suffixes are removed; Legal, Raasta and Technologies remain meaningful identity tokens. A partial/scattered match cannot score 1.00. A careers/jobs URL or ATS domain cannot bypass employer matching. The original posting itself is excluded as corroboration.

## Source categories and trust

| Category | Admission and interpretation |
| --- | --- |
| confirmed_official | Fetched identity match plus registered domain in an operator-reviewed local registry |
| independent_employer_related | Employer-specific page on a recognized external publisher; may still be self-reported |
| unverified_employer_related | Company name matches, but ownership/independence is not established; not supporting evidence |
| unrelated | Incomplete identity match; excluded from supporting claims and shown in diagnostics |

No domain is pre-declared official. `official_website` is an unverified hint, not a trust override. For a reviewed entry, copy `backend/confirmed_employers.example.json` to `backend/confirmed_employers.json` and record employer, website, verification_url and verified_by after independent human review. See [operator details](../backend/TINYFISH.md). A domain comparison uses the offline Public Suffix List, so `company.com.evil.org` is not `company.com`.

## Evidence ranking

A separate local TF-IDF vectorizer uses unigrams/bigrams and cosine similarity, with up to 15,000 features for an investigation. Passage ranking is:

```text
0.35 * cosine similarity
+ 0.25 * employer entity match
+ 0.15 * company-name similarity
+ 0.15 * source relevance
+ 0.10 * registered-domain comparison
```

Complete identity matching is mandatory, regardless of score. Only confirmed official or employer-specific external publisher sources can support claims. Independent-domain excerpts must themselves name the employer. Non-identity job claims additionally require lexical overlap beyond the company name; cosine similarity must reach 0.08. At most two source passages per claim are returned.

The code does not understand every negation/date or independently verify an offer. A no-fee policy can resemble a fee request. Excerpts provide context, not a verified/false fact label. Every extracted claim remains unverified. No trustworthy supporting passage produces: **Insufficient employer-specific evidence retrieved.**

## Claim scope and Unicode

Claim extraction prefers job-description sections and concrete employer, payment, salary guarantee, affiliation and certification assertions. Navigation, numbered vacancy headings, Salary Search links and related-job/ad blocks are filtered. This is English-oriented heuristics, not semantic understanding; unusual layouts can lose valid claims or retain noise.

Provider JSON is decoded as UTF-8. Valid accents, Hindi, currency symbols and emoji are preserved. Recognizable mojibake is conservatively repaired for display; source.encoding_repaired discloses changes, while content_sha256 identifies the original bounded/trimmed text before repair. Repaired excerpts are not byte-verbatim originals. Arbitrary lost bytes cannot be recovered.

## Limits and failures

The total budget is 85 seconds, provider per-URL budget 30 seconds, provider response cap 3 MiB, retained text cap 80,000 characters/page, and maximum four fetched URLs. Ranking uses at most 120 passages/page and 450-character excerpts. Two investigations can run concurrently per backend process; excess requests receive HTTP 429.

Reports distinguish needs_employer, not_configured, evidence_found, partial, no_sources, failed and timeout. Auth/access/quota errors, malformed JSON, network issues and per-page failures use sanitized codes rather than provider bodies. Successful partial pages can remain available. Rules and ML do not depend on TinyFish availability.

## Actual live retrieval and reproduction

A local check on 19 October 2026 successfully performed three employer-specific searches and live Fetch for Legal Raasta. Actual fetched pages included:

- https://in.indeed.com/cmp/Legalraasta-Technologies-Pvt-Ltd-2
- https://in.indeed.com/q-legal-raasta-technologies-jobs.html
- https://in.linkedin.com/company/legalraasta
- https://internshala.com/company/legal-raasta-technologies-pvt-ltd-1608355563/careers/

They were admitted as employer-related external pages after full name matching, not official-site or internship verification. That run reported evidence_found and employer_related_sources_only; availability/content may change. The local ignored receipt contains provider request IDs and content hashes. No raw receipt or copied page body is bundled in the public source release.

Repeat explicitly:

```powershell
.\.venv\Scripts\python.exe -m backend.tools.verify_tinyfish --employer "Legal Raasta Technologies Pvt. Ltd." --output backend/reports/live_tinyfish_verification_submission.json
```

Exit 0 and live_retrieval_verified=true require successful Search and Fetch with at least 80 characters of employer-matching fetched text. Optional --website restricts the check to that claimed registered domain; it does not establish official ownership. A successful check proves retrieval only. Tests use HTTPX MockTransport and cannot count as live evidence.

Public web content retains its owners' rights. Do not imply affiliation with the named employer, platforms, or TinyFish, or publish personal data copied from a posting.
