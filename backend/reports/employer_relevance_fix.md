# Employer relevance correction and actual live check

The exact failed Legal Raasta request was not retained, so its historical extracted employer cannot be recovered. The old code reproducibly accepted About Careers as employer Careers, then gave careers pages a perfect entity score for that generic token. Recruitment domains could also bypass employer identity during candidate selection.

## Corrected extraction and searches

Explicit input employer: Legal Raasta Technologies Pvt. Ltd
Normalized identity: legal raasta technologies
Live extraction method: user_supplied
The backend regression fixture also extracts the same employer from a Company field beneath an About Careers heading.

- `"Legal Raasta Technologies Pvt Ltd" official website`
- `"Legal Raasta Technologies" careers`
- `"Legal Raasta Technologies" internship`

## Actual TinyFish results

Checked at: 2026-10-19T16:52:03.368192+00:00 (UTC).
Retrieval check: True. Status: evidence_found. Verification status: employer_related_sources_only.
Three Search requests and one live Fetch returned HTTP 200. This run did not establish an official employer domain or validate an internship offer.

| Actual fetched page | Category | Entity match | Characters used | Decision |
| --- | --- | ---: | ---: | --- |
| [LegalRaasta Technologies Pvt Ltd Careers and Employment / Indeed.com ](https://in.indeed.com/cmp/Legalraasta-Technologies-Pvt-Ltd-2) | independent_employer_related | 1.00 | 2386 | Accepted as employer-related context: complete normalized company name in fetched title/text; external platform content may be self-reported. |
| [8 Legal Raasta Technologies Jobs and Vacancies - 19 October 2026 / Indeed ](https://in.indeed.com/q-legal-raasta-technologies-jobs.html) | independent_employer_related | 1.00 | 5559 | Accepted as employer-related context: complete normalized company name in fetched title/text; external platform content may be self-reported. |
| [LegalRaasta Technologies Pvt. Ltd. / LinkedIn ](https://in.linkedin.com/company/legalraasta) | independent_employer_related | 1.00 | 8884 | Accepted as employer-related context: complete normalized company name in fetched title/text; external platform content may be self-reported. |
| [Legal Raasta Technologies Pvt. Ltd. Careers & Employment / Internshala ](https://internshala.com/company/legal-raasta-technologies-pvt-ltd-1608355563/careers/) | independent_employer_related | 1.00 | 347 | Accepted as employer-related context: complete normalized company name in fetched title/text; external platform content may be self-reported. |

Unrelated source exclusions in this particular live run: 0. No Microsoft Careers, Allied Universal, or generic Find a Job page was returned in this run. Mocked regression tests independently verify rejection of those pages; they are not presented as live exclusions.

No domain was added to the operator-confirmed registry. All claims remain unverified. The original live receipt, including actual excerpts, hashes and provider request IDs, is Git-ignored at backend/reports/live_tinyfish_verification_legal_raasta.json.

## Revised evidence gate

Generic employer identities are invalid. Matching normalizes punctuation/case/word joins and strips trailing corporate suffixes while preserving Legal, Raasta and Technologies. Whole company identity is mandatory both before Fetch and after redirects. Noncontiguous/partial matches cannot score 1.00.

Candidates are ranked with 35% TF-IDF cosine similarity, 25% entity match, 15% company-name similarity, 15% source relevance, and 10% registered-domain comparison. Only confirmed official or employer-specific external publisher pages can support claims; unverified related pages are displayed separately. External-source excerpts must themselves name the employer. Text similarity never verifies claim truth.

## Validation

Final validation: 73 backend/ML tests passed (one existing Starlette deprecation warning); 3 mocked extension behavior tests passed; JavaScript syntax checks passed. Existing ML inference tests use the actual local artifact and dataset, and the artifact SHA-256 still matches its original evaluation report. No real TinyFish responses are used by automated tests. Chrome was not manually loaded during this validation.
