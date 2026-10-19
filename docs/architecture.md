# System architecture

## Execution boundaries

VeriShield is a local-first Chrome extension and Python service. There is no hosted dashboard, account system, database, payment system, or background page monitor.

```mermaid
sequenceDiagram
    participant User
    participant Popup as Chrome popup
    participant Page as Active page
    participant API as FastAPI
    participant Model as Local rules and ML artifact
    participant TF as TinyFish Search/Fetch
    User->>Popup: Scan This Page
    Popup->>Page: Inject extractPageText via activeTab + scripting
    Page-->>Popup: Visible text, title, URL, single JobPosting employer
    Popup->>API: POST /analyze
    API->>Model: Rule matches and saved-pipeline inference
    Model-->>API: Independent rule and ML outputs
    API-->>Popup: Analysis response
    Popup->>API: POST /investigate/preview
    API-->>Popup: Selected employer and generated queries (local)
    User->>Popup: Correct employer; Investigate Employer
    Popup->>API: POST /investigate
    API->>TF: Employer-specific Search queries
    TF-->>API: Candidate URLs, titles and snippets
    API->>TF: Fetch up to four selected public URLs, ttl=0
    TF-->>API: Page text, final URLs, per-page errors
    API->>API: Identity recheck, claim/passages ranking
    API-->>Popup: Sources, related excerpts, exclusions, unverified claims
```

## Code ownership

| Module | Actual responsibility |
| --- | --- |
| extension/manifest.json | MV3 popup, activeTab/scripting permissions, localhost API host permission |
| extension/popup.js | User actions, top-frame rendered text, bounded JobPosting JSON-LD parsing, API client, safe textContent/source-link rendering |
| backend/app/main.py | Lifespan model loading, /health, /analyze, /investigate/preview, /investigate |
| backend/app/analyzer.py | Seven independent regex rules; each fires at most once |
| backend/app/config.py | Process/dotenv configuration and model path |
| backend/app/investigation/claims.py | Conservative employer selection, navigation filtering, prioritized claim extraction |
| backend/app/investigation/identity.py | Company normalization and three quoted search queries |
| backend/app/investigation/tinyfish.py | Fixed TinyFish endpoints, secret header, bounded UTF-8 JSON responses and sanitized errors |
| backend/app/investigation/service.py | Retrieval orchestration, source filtering, hashes and report assembly |
| backend/app/investigation/ranking.py | Entity gate, publisher categorization, separate TF-IDF/cosine retrieval ranking |
| backend/app/investigation/urls.py | Public URL screening and offline registered-domain extraction |
| backend/app/investigation/trust.py | Optional human-reviewed domain registry; website hints do not confer trust |
| backend/app/investigation/text.py | Narrow, disclosed mojibake repair for investigation display |
| ml/data.py, ml/preprocessing.py, ml/train.py | Original CSV validation, deduplication, grouping, training and actual evaluation |
| ml/inference.py | Trusted Joblib loading and model inference; never training inside requests |

## Separate outputs

The rule engine returns low/medium/high concern and points: thresholds 20 and 50, sum capped at 100. These are neither ML probabilities nor fraud verdicts.

The saved classifier returns an independently named label and class-weighted probability at threshold 0.5. Missing/corrupt/version-incompatible artifacts are reported unavailable, while rules remain usable. The artifact loads once per service lifespan.

Investigation returns relevance and uncertainty, not a combined fraud score. Confirmed official sources require both a reviewed registry domain and fetched name matching. External employer profiles may be self-reported. Unrelated pages never support claims. Every extracted claim remains in unverified_claims until a human checks it; there is no automated truth-verification engine.

## Boundaries, state and failure handling

- /analyze and /investigate/preview make no external network calls.
- Only an explicit investigation sends an employer query and public source URLs to TinyFish; the whole job description is not forwarded.
- Page bodies are not persisted by normal API routes. Manual verification CLI writes a local ignored receipt. Uvicorn access logs record route/status, not request bodies.
- No API key is included in the extension or API response. Provider errors use fixed codes, not raw error bodies. HTTPX does not follow provider redirects or inherit ambient proxy settings for key-bearing calls.
- The extension extracts at most 50,000 characters and reports truncation. It excludes URL query/fragment from the original page context. Page paths/titles/text can still contain personal information; scan intentionally.
- Investigations have an 85-second total deadline, 30-second provider per-URL budget, maximum four pages, 3 MiB provider response bound, 80,000 retained characters per page, and two concurrent investigations per backend process. Extra concurrent requests get HTTP 429.
- The popup waits up to 100 seconds for investigation and must remain open; no durable background job exists.
- Invalid inputs return HTTP 422. Missing identity/key, auth/quota/network errors, empty/blocked pages and partial retrieval are explicit report states.

## Domain, email, and advisory layer

`backend/app/security/domains.py` normalizes IDNA hosts and reuses offline registered-domain parsing and the reviewed employer-domain registry. It checks namespace matches, misleading subdomains, edit similarity, affixes, limited confusables, and recognized platform exceptions. Search mentions never establish ownership.

`backend/app/security/emails.py` extracts recruitment-context addresses after job/navigation and private-account filtering, then compares their domains using the same authority boundary. Public providers remain informational. No email, DNS, or authentication requests are sent.

`schemas.py` defines additive Pydantic findings. `assessment.py` enriches responses with `job_information`, `domain_analysis`, `email_analysis`, and `advisory`. `advisory.py` selects conservative categories and recommendations without synthesizing a fraud probability.

`/analyze` preserves the original rule and ML inference paths and adds local assessments. `/investigate` reuses the existing report and performs local enrichment in a worker thread with the same saved classifier; it makes no extra TinyFish calls. The training pipeline and artifact are unchanged. The popup displays eight sections in a scrolling dashboard, distinguishes predictions from evidence, and preserves safe clickable source links. Recognized private mail/account URLs are blocked before page extraction; this guard is incomplete and does not replace deliberate public-page scanning.

See [domain algorithm and limitations](domain_impersonation.md) and [email verification scope](recruitment_email_verification.md). Tests use controlled domains and mocked HTTP; fixtures do not claim live ownership.

## Local service deployment

The documented service is loopback development on 127.0.0.1:8000. Extension host permissions authorize its own cross-origin API calls; permissive CORS is not added. This is not an access-control boundary for other local software. Authentication, rate limits per user, durable jobs, audit storage, and production hosting remain future work.
