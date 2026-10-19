# Company impersonation indicators

The local security modules compare registered domains, not just words in a URL. They do not determine whether a business owns a domain or whether an offer is fraudulent.

## Trust boundary

An established employer domain must come from the existing operator-reviewed registry described in [TinyFish integration](tinyfish_integration.md). TinyFish can corroborate a matching registered domain with an identity-matched official page. A search mention, an employer-related source, or a user-supplied website cannot establish ownership. Unverified domain candidates remain separate. Without a registry entry, the result reports domain verification unavailable.

Only record domains after checking independent evidence of ownership. Do not add an entry simply to clear a warning. The registry is not populated automatically.

## Algorithm

1. Parse the supplied HTTP(S) URL; reject credentials, malformed hosts, and unusable input. IP addresses do not produce employer registered domains.
2. Normalize Unicode hostnames with IDNA/UTS46 and expose ASCII and Unicode spellings. Use the existing offline `tldextract` public/private suffix snapshot to extract the registered domain. No DNS request is made.
3. Accept the established registered domain and its organizational subdomains as a namespace match. This does not authenticate the sender or offer.
4. Recognize a limited list of recruitment/ATS platforms. A platform domain mismatch alone does not produce an impersonation warning.
5. For different domains, report the mismatch and compare employer labels using normalized Levenshtein similarity: `1 - distance / max(lengths)`. Similarity of at least 0.8, with labels at least four characters long, is a lookalike indicator. Check extra employer-label affixes, embedded official domains in misleading subdomains, and a limited set of digit/Unicode character substitutions.
6. Report IDN/punycode use as informational. Legitimate internationalized domains are not automatically suspicious.

The response includes the current hostname, registered domain, established domains, establishment basis, candidate domains, and explainable findings with compared domains. Similarity is an indicator, not evidence of intent or a fraud probability.

## API and manual checks

`POST /analyze` and `POST /investigate` include additive `domain_analysis`, `email_analysis`, `job_information`, and `advisory` fields. Investigation reuses retrieved sources; these checks make no additional TinyFish requests. Existing API fields remain available.

Run `python -m pytest backend/tests/test_domain_security.py backend/tests/test_security_assessments.py -q` in the project environment. Controlled tests cover exact/subdomain matches, lookalikes, misleading subdomains, IDNs, third-party platforms, and missing authority. These fixtures are not live evidence.

For a browser check, load the extension, scan a public job page, and inspect section 6. With no reviewed employer-domain entry it must state that verification is unavailable. With an independently checked registry entry, repeat the scan to inspect the compared domains. Use controlled test pages for suspicious-host demonstrations; do not visit hostile sites to test the detector.

## Limitations

Subsidiaries, acquisitions, agency recruiting, alternate brands, and delegated domains can produce benign mismatches. The reviewed registry can become stale. Platform and confusable lists are incomplete. A matching domain can be compromised; a platform can host a fraudulent listing. No certificate, DNS ownership, domain age, reputation, or account-authentication checks are performed.
