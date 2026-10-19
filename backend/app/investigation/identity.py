"""Employer identity normalization shared by extraction, queries and retrieval."""
import re

SUFFIXES = {'inc', 'incorporated', 'ltd', 'limited', 'llc', 'corp', 'corporation', 'plc', 'pvt', 'private'}
GENERIC = {'careers','career','jobs','job','hiring','help','internship','internships','recruitment','recruiting','employment','opportunity','opportunities','find','a','an','the','at','apply','now','about','home','contact','us','we','our','team','company','employer','confidential','official','website','organization','profile'}


def words(value: str) -> list[str]:
    value = re.sub(r'([a-z])([A-Z])', r'\1 \2', value)
    value = re.sub(r'\bp\s*\.\s*v\s*\.\s*t\s*\.?', ' pvt ', value, flags=re.I)
    return re.findall(r'[^\W_]+', value.casefold())


def company_tokens(value: str) -> list[str]:
    tokens = words(value)
    while tokens and tokens[-1] in SUFFIXES:
        tokens.pop()
    return [token for token in tokens if token not in GENERIC]


def normalized_company(value: str) -> str:
    return ' '.join(company_tokens(value))


def valid_company(value: str) -> bool:
    tokens = company_tokens(value)
    return bool(tokens) and any(len(token) >= 2 and not token.isdigit() for token in tokens)


def build_queries(employer: str, text: str = '') -> list[str]:
    if not valid_company(employer):
        return []
    # Keep readable original capitalization without punctuation/search operators.
    full = ' '.join(re.findall(r'[^\W_]+', employer))
    core_words = re.findall(r'[^\W_]+', employer)
    while core_words and core_words[-1].casefold() in SUFFIXES:
        core_words.pop()
    core = ' '.join(core_words)
    return list(dict.fromkeys([f'"{full}" official website', f'"{core}" careers', f'"{core}" internship']))
