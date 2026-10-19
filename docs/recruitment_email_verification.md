# Recruitment email domain assessment

The local email module assesses publicly displayed recruitment addresses in the submitted job text. It never sends email or contacts a recruiter. Domain findings do not establish mailbox ownership, deliverability, or a sender's authorization.

## Collection and privacy

The extension retains click-triggered visible-page extraction and blocks recognized private mail/account URLs before extraction. This guard is heuristic, not a universal private-content detector: scan public job pages deliberately. The backend also skips recognized private interfaces and account-related text blocks.

Email extraction uses the existing job-section/navigation filtering. It favors application/recruitment instructions, recruitment-style mailbox names, and labeled email/contact lines within a job section. Hidden fields, other tabs, private APIs, and mailto-only hidden addresses are not collected. The parser supports ASCII local parts and IDNA domains, deduplicates addresses, and assesses at most ten relevant addresses. It may miss ambiguous or obfuscated contact information.

## Assessments

| Assessment | Meaning |
| --- | --- |
| Domain match | Registered domain matches an established employer domain |
| Organizational subdomain | Address is under the established organizational namespace |
| Potential impersonation | Lookalike, character substitution, affix, or misleading subdomain indicator |
| Different domain | Mismatch requiring context; agency or alternate-domain use may be legitimate |
| Public provider | Known provider such as Gmail or Outlook; informational, not proof of fraud |
| Third-party domain | Recognized recruitment platform; mismatch alone is not suspicious |
| Unverified domain | No independently established employer domain is available |

Each address includes its normalized domain, compared employer domains, explanation, and findings. Missing addresses return **No recruitment email detected.** The authority boundary and comparison algorithms are documented in [domain impersonation](domain_impersonation.md).

No SMTP, MX, SPF, DKIM, DMARC, breach lookup, or sender verification is performed. A real employer-domain address can still be spoofed in webpage text.

## Dashboard and testing

Section 7 displays addresses as text, without an automatic contact action. Section 8 uses deterministic recommendations derived from actual findings. High-severity indicators or existing rule points of at least 50 produce an elevated advisory; lesser warnings, rule findings, or a fraudulent ML class recommend review. Missing information is disclosed. Signals are never combined into a fraud probability.

Run `python -m pytest backend/tests/test_email_security.py backend/tests/test_security_assessments.py -q`. Controlled fixtures cover organization subdomains, suspicious addresses, public providers, private-account text, missing addresses, and unknown ownership. For a manual demonstration, use a local public-style job fixture with an explicit employer and application email, then scan and inspect sections 6–8. Without an independently reviewed registry entry, the dashboard must disclose unavailable ownership verification. Do not treat a fictional test registry entry as live verification.
