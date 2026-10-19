"""Deterministic advisory categories, never a fabricated combined probability."""
from .schemas import Advisory, DomainAnalysis, EmailAnalysis


def build_advisory(rule_score: int, ml_available: bool, ml_label: str | None,
                   domain: DomainAnalysis, emails: EmailAnalysis, text_length: int,
                   investigation_status: str | None = None) -> Advisory:
    scoped = [('website', finding) for finding in domain.findings]
    scoped += [('recruitment email', finding) for email in emails.emails for finding in email.findings]
    order = {'high': 3, 'medium': 2, 'low': 1, 'info': 0}
    scoped.sort(key=lambda item: -order[item[1].severity])
    findings = [finding for _, finding in scoped]
    reasons = list(dict.fromkeys(scope.capitalize()+': '+finding.explanation for scope, finding in scoped if finding.severity != 'info'))
    if rule_score:
        reasons.append(f'Configured suspicious-pattern rules contributed {rule_score}/100 rule points; these are not probabilities.')
    if ml_available and ml_label == 'fraudulent':
        reasons.append('The local classifier predicted the fraudulent class; its output is not a calibrated fraud probability.')
    elevated = rule_score >= 50 or any(f.severity == 'high' for f in findings)
    review = bool(reasons)
    missing = []
    if not domain.employer_name:
        missing.append('Employer identity was not identified.')
    if not domain.established_employer_domains:
        missing.append('No employer domain is independently established; domain/email ownership comparisons are unavailable.')
    if not ml_available:
        missing.append('The trained model is unavailable for this response.')
    if text_length < 80:
        missing.append('The submitted text is short; important job details may be missing.')
    if investigation_status in {'failed','timeout','no_sources','not_configured','needs_employer'}:
        missing.append('Employer investigation did not provide sufficient independently reviewable evidence.')
    category = ('Elevated warning indicators' if elevated else 'Review recommended' if review else
                'Insufficient information' if missing else 'No major warning indicators detected')
    if elevated or review:
        if any(f.severity != 'info' for f in findings):
            scope, primary = next(item for item in scoped if item[1].severity != 'info')
            detail = {
                'character_substitution': 'resembles the established employer domain after common character substitutions',
                'misleading_subdomain': 'embeds the established employer domain inside a different hostname',
                'lookalike_domain': 'closely resembles, but differs from, an established employer domain',
                'employer_name_affix': 'embeds the employer label with extra characters or words',
                'registered_domain_mismatch': 'differs from an established employer domain',
            }.get(primary.code, 'has a configured warning indicator')
            recommendation = f'Additional verification is recommended because the {scope} domain {primary.observed_domain or "provided"} {detail}. Confirm the offer through an independently established employer contact.'
        elif rule_score:
            recommendation = f'Additional verification is recommended because configured suspicious patterns produced {rule_score}/100 rule points. Review the matched text and verify the offer independently.'
        else:
            recommendation = 'The local model predicted the fraudulent class. Its output is not a calibrated fraud probability. Independently verify the employer and offer.'
    elif missing:
        recommendation = 'Insufficient information for a complete advisory. ' + ' '.join(missing[:2]) + ' Verify the employer and offer independently.'
    else:
        recommendation = 'No major configured warning indicators were detected. This does not establish that the offer is genuine.'
    return Advisory(category=category, reasons=reasons+missing, recommendation=recommendation)
