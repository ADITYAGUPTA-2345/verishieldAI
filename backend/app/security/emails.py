"""Recruitment-context email namespace checks; no contact or DNS/network calls."""
import re
from urllib.parse import urlsplit

from ..investigation.claims import JOB_SECTION, job_sentences
from .domains import compare_domain, host_details
from .schemas import EmailAnalysis, RecruitmentEmail, SecurityFinding

PUBLIC_PROVIDERS = frozenset({'gmail.com','googlemail.com','outlook.com','hotmail.com','live.com','yahoo.com','ymail.com','icloud.com','me.com','aol.com','proton.me','protonmail.com','mail.com','gmx.com','gmx.de','zoho.com'})
EMAIL = re.compile(r"(?<![\w.+-])([A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64})@([^\W_](?:[^\W_]|-)*(?:\.[^\W_](?:[^\W_]|-)*)+)", re.UNICODE)
PRIVATE_CONTEXT = re.compile(r'\b(?:signed\s+in|logged\s+in|my\s+account|your\s+account|account\s+settings|email\s+preferences|unsubscribe|sign\s+out|log\s+out|inbox|sent\s+mail|drafts|password|recovery\s+email)\b', re.I)
RECRUITMENT_CONTEXT = re.compile(r'\b(?:apply|applications?|recruit(?:er|ment|ing)?|hiring|hr|send\s+(?:your\s+)?(?:cv|resume)|talent\s+acquisition)\b', re.I)
RECRUITMENT_LOCAL = re.compile(r'^(?:hr|jobs?|careers?|recruit(?:er|ment|ing)?|hiring|talent)(?:[._+-]|$)', re.I)


def private_interface(url: str | None) -> bool:
    if not url:
        return False
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or '').lower()
        return (host in {'mail.google.com','outlook.live.com','outlook.office.com','outlook.office365.com','mail.yahoo.com','mail.proton.me'}
                or bool(re.search(r'/(?:inbox|messaging|messages|account|settings)(?:/|$)', parsed.path, re.I)))
    except ValueError:
        return True


def assess_email(address: str, employer: str | None, official_domains: list[str]) -> RecruitmentEmail | None:
    local, raw_domain = address.rsplit('@', 1)
    host, _, domain = host_details(raw_domain)
    if not host or not domain:
        return None
    compared = compare_domain('https://' + host, employer, official_domains)
    if compared.status == 'match':
        category = 'domain_match' if host in official_domains else 'organizational_subdomain'
        explanation = ('Email domain matches an operator-established employer domain.' if category == 'domain_match'
                       else 'Email domain is a subdomain within an operator-established employer namespace. Delegation and mailbox authorization are not verified.')
    elif domain in PUBLIC_PROVIDERS:
        category = 'public_provider'
        explanation = 'Public email provider. This is not proof of fraud or employer affiliation; independently confirm the recruiter.'
        compared.findings = [finding for finding in compared.findings if finding.code == 'idn_domain']
        compared.findings.append(SecurityFinding(code='public_email_provider', severity='info', explanation=explanation, observed_domain=host))
    elif compared.status == 'third_party':
        category = 'third_party_domain'
        explanation = 'Known recruitment-platform domain; it may be a relay or third party. Recruiter authorization is not verified.'
    elif compared.status == 'unavailable':
        category = 'unverified_domain'
        explanation = 'Email-domain verification is unavailable because no employer domain has been independently established.'
    elif any(f.severity in {'medium', 'high'} for f in compared.findings):
        category = 'potential_impersonation'
        explanation = 'Potential domain impersonation indicator: this different email domain resembles an established employer domain. This is not a fraud verdict.'
    else:
        category = 'different_domain'
        explanation = 'Recruitment email domain differs from the established employer domain. A legitimate agency or service is possible; independently check authorization.'
    return RecruitmentEmail(address=local+'@'+host, email_domain=host, registered_domain=domain,
        established_employer_domains=official_domains, assessment=category,
        explanation=explanation+' A domain match does not verify the mailbox, sender, or offer.', findings=compared.findings)


def analyze_emails(text: str, url: str | None, employer: str | None, official_domains: list[str]) -> EmailAnalysis:
    result = EmailAnalysis(status='no_emails', message='No recruitment email detected.')
    if private_interface(url):
        result.scope_note = 'Recruitment email extraction skipped for a recognized private account/mail interface.'
        return result
    # Account headers and addresses can occupy separate DOM lines. Never treat
    # a following HR-looking account address as recruitment context by itself.
    safe_lines, account_block = [], False
    for line in text.splitlines():
        if PRIVATE_CONTEXT.search(line):
            account_block = True
            continue
        explicit_recruitment = bool(RECRUITMENT_CONTEXT.search(EMAIL.sub("", line)))
        if JOB_SECTION.fullmatch(line.strip()) or explicit_recruitment:
            account_block = False
        if account_block:
            continue
        safe_lines.append(line)
    seen = set()
    for sentence, in_job in job_sentences("\n".join(safe_lines)):
        if PRIVATE_CONTEXT.search(sentence):
            continue
        for match in EMAIL.finditer(sentence):
            local, raw_domain = match.groups()
            positive = bool(RECRUITMENT_CONTEXT.search(sentence[:match.start()] + ' ' + sentence[match.end():]))
            positive = positive or bool(RECRUITMENT_LOCAL.match(local))
            positive = positive or (in_job and bool(re.search(r'\b(?:email|contact)\s*:', sentence, re.I)))
            if not positive:
                continue
            assessed = assess_email(local+'@'+raw_domain.rstrip('.'), employer, official_domains)
            if assessed is None:
                continue
            key = assessed.address.casefold()
            if key in seen:
                continue
            seen.add(key)
            if len(result.emails) == 10:
                result.truncated = True
                break
            result.emails.append(assessed)
        if result.truncated:
            break
    if result.emails:
        result.status = 'assessed'
        result.message = f'Assessed {len(result.emails)} recruitment email address(es). Domain checks do not authenticate a sender.'
    return result
