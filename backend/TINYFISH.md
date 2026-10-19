# TinyFish employer investigation

VeriShield keeps three independent outputs: rule findings, the existing frozen ML classifier, and public-web employer evidence. `POST /analyze` remains local. `POST /investigate` performs the optional web investigation. The ML training pipeline is unchanged.

## Configuration on Windows

1. Get an API key from https://agent.tinyfish.ai/api-keys .
2. Create `backend/.env` (not `.env.txt`) with this line, replacing the placeholder locally:

```dotenv
TINYFISH_API_KEY=your_actual_key
```

If the file does not exist, PowerShell can create it from the example:

```powershell
Copy-Item backend/.env.example backend/.env
```

Edit the file locally. Do not put the key into extension code, shell command arguments, screenshots, chat, or a commit. Both `.env` and `.env.*` files are ignored, with `.env.example` deliberately allowed. No key value is printed by the diagnostic tools. Environment variables override dotenv files; backend/.env takes precedence over legacy root .env settings when no process variable is defined. Restart the server after changing a key.

From the repository root with Python 3.12:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

The existing trained artifact must remain in `ml/artifacts/job_classifier.joblib`. There is no need to retrain for this integration.

## Test real TinyFish retrieval

Run this explicit manual diagnostic from a second terminal:

```powershell
.\.venv\Scripts\python.exe -m backend.tools.verify_tinyfish
$LASTEXITCODE
```

It uses the real configured key to search for the specified employer (TinyFish by default) and fetch matching public pages with `ttl=0`. It does not use mock HTTP or fixed evidence. Exit code 0 and `live_retrieval_verified: true` require BOTH successful Search and Fetch responses and at least 80 characters of employer-matching fetched text from an employer-matching page (restricted to the claimed domain only when `--website` is supplied). HTTP 200 alone does not pass verification. Exit code 2 means the test did not establish live retrieval.

The ignored `backend/reports/live_tinyfish_verification.json` receipt includes the check time, returned URLs and titles, actual excerpts, content hashes, source lengths, available provider request IDs, warnings, and status. It contains no key or request headers. Check the timestamp before using it as a current run receipt. A passing receipt verifies retrieval, not the legitimacy of an employer or job offer.

To test a different employer and claimed company website:

```powershell
.\.venv\Scripts\python.exe -m backend.tools.verify_tinyfish --employer Microsoft --website https://www.microsoft.com/
```

The diagnostic and investigation endpoint can consume your TinyFish account allowance. No automatic retries are made on quota/authentication errors.

## Test the complete extension

1. Open `chrome://extensions`, enable Developer mode, and reload VeriShield AI (or Load unpacked and select `extension`). No additional Chrome permissions are required.
2. Open an HTTP(S) job page, open the popup, and click **Scan This Page**. Confirm the existing rule results and ML prediction appear.
3. Under **Investigate employer**, optionally supply the correct employer name and its claimed public website. If extraction is ambiguous or missing, the report requests an employer name instead of guessing.
4. Click **Investigate Employer** and keep the popup open for up to 90 seconds.
5. Review the investigation status, retrieved source links, passages, rankings, and unverified claims. An official-looking domain is only a candidate, and a high similarity score does not establish truth.

The popup sends the job text to your local backend as before. Only a short employer query and selected public URLs go from the backend to TinyFish, not the entire job description. Company names and URLs can still reveal the posting you are investigating. No credentials are sent to source websites by this code.

## API example

With the backend running:

```powershell
$payload = @{
    text = "Employer: Microsoft`nMicrosoft is hiring software engineers."
    employer_name = 'Microsoft'
    official_website = 'https://www.microsoft.com/'
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/investigate -ContentType 'application/json' -Body $payload | ConvertTo-Json -Depth 10
```

This is an input example, not a claim that a particular job is open. Returned evidence must be inspected. Optional `title` and `url` follow the existing request contract. `url` identifies the original posting so it can be excluded from corroboration.

The structured response includes `employer_name`, `employer_extraction`, `claims`, `sources_retrieved`, `supporting_evidence`, `unverified_claims`, `status`, `message`, `warnings`, `provider_calls`, and `checked_at`. Related passages are not labeled as verified facts. In this version every extracted claim remains unverified until independently reviewed.

## Method and limits

- Employer extraction prioritizes the explicit user override, then one JobPosting hiringOrganization supplied by the extension, explicit Company/Employer fields, legal company-name lines, About headings, hiring sentences, and finally a page title containing `at Company`. Generic headings such as About Careers/Jobs/Help/Internship are rejected. Multiple employers and unknown names require a user correction. This is heuristic extraction, not identity verification. The extension clears stale overrides on a new scan and previews the employer via the local `/investigate/preview` route.
- Claims are short identity, advertised-role, recruitment, location, compensation, payment, and affiliation statements (up to eight). Surrounding page navigation may be mistaken for a claim; inspect the original wording.
- TinyFish Search uses three quoted, employer-specific queries: the full name + official website, the suffix-normalized name + careers, and that name + internship. All generated queries and the extraction method are returned in the report. Candidates need a complete normalized company-name match before Fetch, except a user-supplied URL may be fetched as an explicitly unverified hint. A careers/jobs keyword or ATS platform cannot bypass this identity gate. Up to four pages are fetched. Pages are checked again after redirects; rejected URLs, titles, scores, and reasons appear in excluded_sources diagnostics.
- Search snippets help select URLs but never become fetched-page evidence. Fetch-returned text provides verbatim excerpts, timestamps, and SHA-256 hashes. Original posting URLs, unsafe redirect URLs, unrequested page results, duplicate final URLs, and empty content are excluded. Public URL validation rejects credentials, private literal addresses, local names, and nonstandard ports. TinyFish's server also validates DNS and redirects; this app does not directly fetch arbitrary source URLs.
- Local TF-IDF uses unigrams/bigrams. Ranking is `0.35 * cosine similarity + 0.25 * entity match + 0.15 * company-name similarity + 0.15 * source relevance + 0.10 * domain comparison`. A complete normalized identity match is mandatory; partial/scattered matches score below 1 and cannot become evidence. Corporate suffixes are removed only at the end; meaningful tokens such as Legal, Raasta, and Technologies remain. Joined brand spellings such as LegalRaasta are recognized. Only confirmed official or employer-specific external publisher pages can support claims; unknown-domain matches stay unverified. External-page excerpts must themselves name the employer. Job claims additionally require non-employer term overlap. Top two passages per claim are returned. Similarity is never factual verification.
- The retrieval vectorizer is separate from the saved ML pipeline and never retrains or changes that model. No external LLM or goal-driven TinyFish Agent/Research API is called.
- Content is bounded to 80,000 characters per page for ranking, 120 passages per page, and a 3 MiB provider response limit. Evidence excerpts are at most 450 characters. Pages can be incomplete, stale, blocked, or unrelated; shared brand names and lookalikes remain ambiguous.
- Negation, dates, salaries, affiliations, identity, and offer authenticity require human checking. A no-fee policy can be lexically similar to a fee request; the app displays the original wording rather than treating it as confirmation. Lack of results does not prove fraud.

## Failure behavior

Statuses include `needs_employer`, `not_configured`, `evidence_found`, `partial`, `no_sources`, `failed`, and `timeout`. Authentication, access denial, quota exhaustion, rate limits, HTTP errors, malformed responses, network failure, and per-page failures are explicit. Provider error bodies and request headers are never returned or logged. Successful partial pages remain available where possible. There is an 85-second investigation budget, a 30-second provider per-page timeout, and at most two concurrent investigations per backend process; extra requests receive HTTP 429. Local scanning and ML inference remain independent of these failures.

## Automated tests

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests ml/tests -q
node --check extension/popup.js
```

TinyFish tests use `httpx.MockTransport` and clearly marked test fixtures. They do not consume live account allowance and are not proof of live retrieval. Existing ML tests still exercise the actual local model and source CSV.

## Official documentation reviewed

- [TinyFish Search API reference](https://docs.tinyfish.ai/search-api/reference): GET `https://api.search.tinyfish.ai`, query parameters and result URLs/snippets.
- [TinyFish Fetch API reference](https://docs.tinyfish.ai/fetch-api/reference): POST `https://api.fetch.tinyfish.ai`, `ttl=0`, returned text/final URLs, per-page errors.
- [Authentication](https://docs.tinyfish.ai/authentication): backend `X-API-Key` authentication.

Documentation reviewed on 19 October 2026. These are actual Search/Fetch REST calls implemented using the existing HTTPX dependency, not an Agent API simulation.

## Relevance regression and official-domain policy

The old extractor could interpret `About Careers` as employer `Careers`. The old bag-of-words entity matcher then returned 1.00 for unrelated careers pages. Source selection also admitted recruitment platforms without an employer identity match. The exact old Legal Raasta request was not retained, so its actual extracted name cannot be reconstructed from the current files.

The new response includes `normalized_employer`, `search_queries`, `verification_status`, and `excluded_sources`. The UI groups confirmed official, independent-domain employer-related, and unverified employer-related pages. Excluded unrelated pages are shown only under diagnostics. When no trustworthy supporting passages survive, the UI says **Insufficient employer-specific evidence retrieved.**

“Independent employer-related” means a company-specific page hosted on a recognized external publisher; LinkedIn, Indeed, or Internshala content may be employer-authored or user-submitted and does not independently verify a claim. Unknown ownership is always disclosed. All extracted claims remain unverified.

No domain is pre-declared official in this repository. To establish one after independent human review, copy `backend/confirmed_employers.example.json` to `backend/confirmed_employers.json` and add reviewed records using this schema:

```json
[
  {
    "employer": "Full reviewed employer name",
    "website": "https://example.com/",
    "verification_url": "https://example.com/about",
    "verified_by": "Reviewer and review date"
  }
]
```

This is a format illustration, not a verified employer entry. Only review-backed entries belong in the registry. A request's `official_website` hint cannot establish official status. Even registry-listed domains require matching employer identity in the fetched page. Registered-domain comparisons use the offline Public Suffix List to reject lookalike suffixes/subdomains.

Run backend/ML and extension behavior regression checks:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests ml/tests -q
node --test extension/tests/popup.test.cjs
node --check extension/popup.js
```

Repeat a real Legal Raasta investigation without assuming any official domain:

```powershell
.\.venv\Scripts\python.exe -m backend.tools.verify_tinyfish --employer "Legal Raasta Technologies Pvt. Ltd." --output backend/reports/live_tinyfish_verification_legal_raasta.json
```

A live diagnostic's input contains only the explicitly supplied employer identity; it is a retrieval test, not verification of the original internship advertisement.

## Claim filtering and Unicode handling

Claim extraction filters Salary Search links, numbered vacancy headings, generic navigation, and related-job/advertisement blocks. It favors labeled job-description sections, while retaining a fallback for pages without standard headings. Concrete payment requests, salary guarantees, certifications, and affiliations are prioritized before the eight-claim cap. The extension's existing rendered-page extraction and ML input are unchanged.

Filtering is heuristic and English-oriented. Unlabeled ads/related content mixed into a job description may still slip through; unusual layouts can lose valid claims. Claims are assertions to investigate, not verified facts.

TinyFish JSON is explicitly decoded as UTF-8 (with optional UTF-8 BOM). Already-correct Hindi, accents, currency symbols, and emoji are preserved through FastAPI and popup textContent. Recognizable UTF-8 punctuation/currency mistakenly decoded as CP1252/Latin-1 is conservatively repaired for investigation display. Arbitrary byte loss, replacement characters, and every possible historic encoding cannot be recovered. Valid standalone accented characters are not stripped.

The popup's corrupted punctuation literals were fixed and now use Unicode escapes in JavaScript source to avoid Windows editor/shell encoding mix-ups. When retrieved title/text is repaired, the source has encoding_repaired=true and the popup discloses that fact. Evidence excerpts then reflect repaired display text rather than byte-verbatim provider text; content_sha256 still identifies the original bounded, trimmed fetched text before repair. Existing saved receipts are not rewritten.

Regression tests cover the reported unwanted headings, claim priority, related-job suppression, valid Unicode, known mojibake, misleading HTTP charset declarations, original content hashes, and popup rendering. No LLM API or new dependency was added.
