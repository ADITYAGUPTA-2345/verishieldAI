from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .config import MAX_TEXT_CHARS
from .security.schemas import Advisory, DomainAnalysis, EmailAnalysis, JobInformation


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=MAX_TEXT_CHARS)
    url: str | None = Field(default=None, max_length=4096)
    title: str | None = Field(default=None, max_length=500)
    employer_name: str | None = Field(default=None, min_length=2, max_length=100)
    structured_employer_name: str | None = Field(default=None, min_length=2, max_length=100)

    @field_validator("text")
    @classmethod
    def require_visible_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Page text must not be blank")
        return value.strip()


class Finding(BaseModel):
    rule_id: str
    label: str
    explanation: str
    evidence: str
    points: int


class MLPrediction(BaseModel):
    status: Literal["available", "unavailable"] = "unavailable"
    label: Literal["fraudulent", "legitimate"] | None = None
    fraud_probability: float | None = Field(default=None, ge=0, le=1)
    threshold: float | None = None
    model_version: str | None = None
    note: str = "Model not loaded. Train the model and restart the backend."


class AnalyzeResponse(BaseModel):
    advisory: Advisory | None = None
    job_information: JobInformation | None = None
    domain_analysis: DomainAnalysis | None = None
    email_analysis: EmailAnalysis | None = None
    risk_level: Literal["low", "medium", "high"]
    risk_score: int = Field(ge=0, le=100)
    summary: str
    findings: list[Finding]
    characters_analyzed: int
    engine: str = "explainable-rules-v1"
    ml_prediction: MLPrediction = Field(default_factory=MLPrediction)
    disclaimer: str = (
        "This is a rule-based screening aid, not a fraud verdict or a probability. "
        "A low score does not establish that a posting is legitimate. Verify the employer independently."
    )
