"""Additive assessment shared by local scans and completed investigations."""
from datetime import datetime, timezone

from ..investigation.claims import extract_employer
from .advisory import build_advisory
from .domains import analyze_website
from .emails import analyze_emails
from .schemas import JobInformation


def attach_assessments(result, request, investigation=None):
    employer = (investigation.employer_name if investigation is not None else
                extract_employer(request.text, request.title, request.employer_name, request.structured_employer_name)[0])
    result.domain_analysis = analyze_website(request.url, employer, investigation)
    result.email_analysis = analyze_emails(request.text, request.url, employer, result.domain_analysis.established_employer_domains)
    result.job_information = JobInformation(job_title=request.title, employer_name=employer,
        current_website=request.url, analyzed_at=datetime.now(timezone.utc).isoformat())
    result.advisory = build_advisory(result.risk_score, result.ml_prediction.status == 'available',
        result.ml_prediction.label, result.domain_analysis, result.email_analysis, len(request.text),
        getattr(investigation,'status',None))
    return result
