from typing import Literal

from pydantic import BaseModel, Field


class SecurityFinding(BaseModel):
    code: str
    severity: Literal["info", "low", "medium", "high"]
    explanation: str
    observed_domain: str | None = None
    compared_domain: str | None = None
    similarity: float | None = Field(default=None, ge=0, le=1)


class DomainAnalysis(BaseModel):
    status: Literal["unavailable", "match", "review", "third_party"]
    employer_name: str | None = None
    hostname: str | None = None
    unicode_hostname: str | None = None
    registered_domain: str | None = None
    established_employer_domains: list[str] = Field(default_factory=list)
    candidate_domains: list[str] = Field(default_factory=list)
    establishment_basis: str = "No independently established employer domain available."
    findings: list[SecurityFinding] = Field(default_factory=list)
    message: str
    limitations: str = "Offline namespace comparison, not proof of site ownership, offer authenticity, or fraud. Domain differences and IDNs can be legitimate. No DNS, WHOIS, or certificate checks are performed."

class RecruitmentEmail(BaseModel):
    address: str
    email_domain: str
    registered_domain: str | None = None
    established_employer_domains: list[str] = Field(default_factory=list)
    assessment: Literal['domain_match', 'organizational_subdomain', 'potential_impersonation', 'different_domain', 'public_provider', 'third_party_domain', 'unverified_domain']
    explanation: str
    findings: list[SecurityFinding] = Field(default_factory=list)


class EmailAnalysis(BaseModel):
    status: Literal['no_emails', 'assessed']
    message: str
    emails: list[RecruitmentEmail] = Field(default_factory=list)
    truncated: bool = False
    scope_note: str = 'Only recruitment-context addresses in submitted visible job text are assessed. No mail is sent; no mailbox, MX, SPF, DKIM or DMARC verification is performed.'

class Advisory(BaseModel):
    category: Literal['No major warning indicators detected', 'Review recommended', 'Elevated warning indicators', 'Insufficient information']
    reasons: list[str] = Field(default_factory=list)
    recommendation: str
    basis: str = 'Deterministic advisory from separate rule findings, ML class, domain and email indicators. Not a combined fraud probability.'


class JobInformation(BaseModel):
    job_title: str | None = None
    employer_name: str | None = None
    current_website: str | None = None
    analyzed_at: str
