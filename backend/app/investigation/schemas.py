from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ..schemas import AnalyzeRequest
from .urls import public_url
from ..security.schemas import Advisory, DomainAnalysis, EmailAnalysis, JobInformation


class InvestigateRequest(AnalyzeRequest):
    structured_employer_name: str | None = Field(default=None, min_length=2, max_length=100)
    employer_name: str | None = Field(default=None, min_length=2, max_length=100)
    official_website: str | None = Field(default=None, max_length=2048)

    @field_validator("employer_name", "structured_employer_name")
    @classmethod
    def valid_name(cls, value):
        if value is not None and (not value.strip() or any(ord(c) < 32 for c in value)):
            raise ValueError("Use a plain employer name without control characters")
        return value.strip() if value else value

    @field_validator("official_website")
    @classmethod
    def valid_website(cls, value):
        if value is not None and not public_url(value):
            raise ValueError("Company website must be a public HTTP(S) URL without credentials")
        return public_url(value) if value else None


class Claim(BaseModel):
    id: str
    text: str
    kind: str


class Source(BaseModel):
    id: str
    url: str
    requested_url: str
    title: str
    source_type: Literal["confirmed_official", "independent_employer_related", "unverified_employer_related", "unrelated"]
    entity_match: float
    identity_matched: bool = False
    company_name_similarity: float = 0
    domain_match: float = 0
    identity_reason: str = "Employer identity not established"
    source_relevance: float
    cosine_similarity: float = 0
    rank_score: float = 0
    retrieved_at: str
    characters_retrieved: int
    content_sha256: str
    excerpt: str
    encoding_repaired: bool = False


class Evidence(BaseModel):
    claim_id: str
    source_id: str
    url: str
    excerpt: str
    cosine_similarity: float
    rank_score: float
    interpretation: str = "Related source passage, not confirmation of the claim. Review identity, context, dates, and any negation."


class UnverifiedClaim(BaseModel):
    claim_id: str
    text: str
    reason: str
    related_source_ids: list[str] = Field(default_factory=list)


class RetrievalCall(BaseModel):
    operation: Literal["search", "fetch"]
    http_status: int
    request_id: str | None = None


class ExcludedSource(BaseModel):
    source_type: Literal["unrelated"] = "unrelated"
    url: str
    title: str
    stage: str
    reason: str
    entity_match: float = 0
    company_name_similarity: float = 0


class InvestigationReport(BaseModel):
    domain_analysis: DomainAnalysis | None = None
    email_analysis: EmailAnalysis | None = None
    advisory: Advisory | None = None
    job_information: JobInformation | None = None
    employer_name: str | None
    employer_extraction: str
    normalized_employer: str | None = None
    search_queries: list[str] = Field(default_factory=list)
    excluded_sources: list[ExcludedSource] = Field(default_factory=list)
    verification_status: str = "insufficient_evidence"
    status: Literal["needs_employer", "not_configured", "evidence_found", "partial", "no_sources", "failed", "timeout"]
    message: str
    claims: list[Claim] = Field(default_factory=list)
    sources_retrieved: list[Source] = Field(default_factory=list)
    supporting_evidence: list[Evidence] = Field(default_factory=list)
    unverified_claims: list[UnverifiedClaim] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    provider_calls: list[RetrievalCall] = Field(default_factory=list)
    checked_at: str
    provider: str = "TinyFish Search + Fetch"
    limitations: str = "Only operator-reviewed registered domains are labeled official. External platform pages may be self-reported. Name matching and lexical relevance do not verify an offer, identity, or claim truth. Missing evidence is not evidence of fraud."
