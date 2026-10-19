"""Conservative, deterministic extraction. Unknown employers require user input."""
import re

from .schemas import Claim
from .identity import normalized_company, valid_company
from .text import repair_text

NAME = r"([\w][\w &.,'’()\-]{1,99}?)"
GENERIC = {"we", "us", "our company", "the company", "company", "confidential", "confidential company", "employer", "a company"}


def clean_name(value: str) -> str | None:
    name = re.split(r"\s+(?:is hiring|is looking|are hiring|offers?|seeks?)\b|[|;]", value, flags=re.I)[0].strip(" .,:-\t")
    if 2 <= len(name) <= 100 and name.casefold() not in GENERIC and valid_company(name) and not re.search(r"https?://|@", name):
        return name
    return None


def extract_employer(text: str, title: str | None = None, override: str | None = None, structured: str | None = None) -> tuple[str | None, str]:
    text = repair_text(text)
    title = repair_text(title) if title else title
    if override:
        return clean_name(override), "user_supplied"
    if structured and (name := clean_name(structured)):
        return name, "structured_job_posting"
    patterns = [
        (rf"(?im)^\s*(?:employer|company|company name|hiring organization)\s*:\s*{NAME}\s*$", "explicit_company_field"),
        (rf"(?im)^[ \t]*(?:employer|company|company name)[ \t]*\n[ \t]*{NAME}[ \t]*$", "explicit_company_field"),
        (r"(?im)^[ \t]*([\w][\w &.,'’()\-]{1,90}\b(?:Pvt\.?\s+Ltd\.?|Private\s+Limited|LLC|Inc\.?))[ \t]*$", "legal_company_name_line"),
        (rf"(?im)^\s*about\s+{NAME}\s*[:\n]", "about_heading"),
        (rf"(?im)^\s*{NAME}\s+is\s+(?:hiring|recruiting|seeking)\b", "hiring_sentence"),
    ]
    for pattern, method in patterns:
        names = {normalized_company(name): name for match in re.finditer(pattern, text) if (name := clean_name(match.group(1)))}
        if len(names) > 1:
            return None, "ambiguous_multiple_employers"
        if names:
            return next(iter(names.values())), method
    if title:
        match = re.search(rf"\bat\s+{NAME}(?:\s*[|–—]|$)", title, re.I)
        if match and (name := clean_name(match.group(1))):
            return name, "page_title_at_company"
    return None, "not_detected"


# These are website chrome, not assertions about the selected job.
NOISE = re.compile(
    r"^(?:salary\s+search\s*:|(?:related|similar|recommended|other|more)\s+(?:jobs?|internships?|vacancies)|"
    r"(?:advertisements?|sponsored|promoted)(?:\s|$)|people\s+also\s+(?:viewed|searched)|"
    r"(?:browse|find|search|explore)\s+(?:a\s+|for\s+)?(?:jobs?|internships?)|"
    r"(?:jobs?|internships?)\s+(?:by|near|for students)|salary\s+(?:guide|calculator)|"
    r"\d[\d,]*\s+.{0,120}\b(?:job\s+vacancies|jobs|vacancies|internships)\b)", re.I)
JOB_SECTION = re.compile(
    r"^(?:full job description|job description|about (?:the job|the internship|this role|the role|the position)|"
    r"responsibilities|requirements|qualifications|eligibility|benefits|perks|compensation|salary|"
    r"about (?:the company|company|the employer)|job details|how to apply|recruitment process|certifications)\s*:?$", re.I)
NAV_SECTION = re.compile(r"^(?:related|similar|recommended|other|more)\s+(?:jobs?|internships?|vacancies)|"
                         r"^(?:advertisements?|sponsored jobs|people also viewed|popular searches|footer|navigation|explore jobs)\s*:?$", re.I)


def is_navigation(value: str) -> bool:
    value = value.strip(" \t-\u2022#")
    return bool(NOISE.search(value) or re.fullmatch(
        r"(?:home|careers|jobs|internships?|help|sign in|sign up|create job alert|apply now|"
        r"privacy policy|terms and conditions|salary search|saved jobs)", value, re.I))


def job_sentences(text: str) -> list[tuple[str, bool]]:
    """Prefer labeled job sections, skipping related-job/ad blocks. Body fallback
    remains available for sites without standard markup or section headings.
    """
    sentences = []
    blocked, in_job = False, False
    for line in repair_text(text).splitlines():
        line = line.strip(" \t\u2022#")
        if not line:
            continue
        if JOB_SECTION.fullmatch(line):
            blocked, in_job = False, True
            continue
        if NAV_SECTION.search(line):
            blocked, in_job = True, False
            continue
        if blocked or is_navigation(line):
            continue
        for sentence in re.split(r"(?<=[.!?])\s+", line):
            sentence = sentence.strip(" \t\u2022")
            if 15 <= len(sentence) <= 450 and not is_navigation(sentence):
                sentences.append((sentence, in_job))
    return sentences


def extract_claims(text: str, employer: str | None, title: str | None = None) -> list[Claim]:
    # Gather and prioritize before applying the eight-claim cap. Payment demands
    # and concrete promises must not lose out to earlier low-value website text.
    candidates = []
    if employer:
        candidates.append((1000, f"The posting names {employer} as the employer.", "employer_identity"))
    title = repair_text(title or "").strip()
    if title and not is_navigation(title) and re.search(r"\b(?:intern(?:ship)?|engineer|developer|analyst|assistant|manager|designer|role|position)\b", title, re.I):
        candidates.append((30, title[:300], "advertised_role"))
    categories = [
        ("payment", 100, r"\b(?:registration|application|training|processing)\s+(?:fee|payment)|\b(?:pay|send|submit|transfer|deposit|fee)\b.*\b(?:fee|deposit|payment|before|join|apply|start)\b"),
        ("compensation", 95, r"\b(?:guaranteed|guarantee|assured|promise[ds]?)\b.*\b(?:salary|income|earnings|stipend|pay)\b|\b(?:salary|income|earnings|stipend|pay)\b.*\b(?:guaranteed|assured)\b"),
        ("certification", 90, r"\b(?:certified|certification|accredited|accreditation|iso\s*\d+)\b"),
        ("affiliation", 85, r"\b(?:partner(?:ed|ship)?|affiliated|affiliation|authorized|authorised)\b"),
        ("compensation", 70, r"[$\u20b9\u20ac\u00a3]\s*\d|\b(?:salary|compensation|stipend|earn)\b"),
        ("location", 40, r"\b(?:based in|located in|headquartered|location:|remote|work from home)\b"),
        ("recruitment", 60, r"\b(?:guaranteed\s+(?:job|placement)|no\s+interview|(?:we|company)\s+(?:are\s+|is\s+)?(?:hiring|recruiting|seeking)|(?:offer|promise|guarantee|receive|provide|will|duration|required|hiring|recruiting|seeking))\b"),
    ]
    for sentence, in_job in job_sentences(text):
        # Outside explicit sections, require a concrete assertion or job context.
        # Bare mentions of internship/salary are insufficient.
        context = in_job or bool(re.search(r"\b(?:we|our|you|your|this internship|this role|the internship|the role|candidates?|applicants?|registration fee|guarantee[ds]?|certified|affiliated|salary|stipend)\b|[$\u20b9\u20ac\u00a3]\s*\d", sentence, re.I))
        context = context or bool(employer and normalized_company(employer) in normalized_company(sentence))
        if not context:
            continue
        category = next(((kind, score) for kind, score, pattern in categories if re.search(pattern, sentence, re.I)), None)
        if category:
            kind, score = category
            candidates.append((score + (10 if in_job else 0), sentence, kind))
    candidates.sort(key=lambda candidate: -candidate[0])  # Stable original order for ties.
    claims, seen = [], set()
    for _, sentence, kind in candidates:
        key = sentence.casefold()
        if key not in seen:
            seen.add(key)
            claims.append(Claim(id=f"claim-{len(claims)+1}", text=sentence, kind=kind))
        if len(claims) == 8:
            break
    return claims
