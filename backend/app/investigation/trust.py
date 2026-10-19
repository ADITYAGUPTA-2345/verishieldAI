"""Optional operator-confirmed domains. No automatic trust from a URL hint."""
import json
from pathlib import Path

from .identity import normalized_company
from .urls import public_url, registered_domain


def load_confirmed_domains() -> dict[str, set[str]]:
    path = Path(__file__).resolve().parents[2] / 'confirmed_employers.json'
    if not path.is_file():
        return {}
    try:
        rows = json.loads(path.read_text(encoding='utf-8-sig'))
        result = {}
        for row in rows:
            name = normalized_company(row['employer'])
            website = public_url(row['website'])
            evidence = public_url(row['verification_url'])
            if name and website and evidence and row.get('verified_by'):
                result.setdefault(name, set()).add(registered_domain(website))
        return result
    except (ValueError, TypeError, KeyError):
        return {}  # Invalid registry never establishes official status.
