"""Real-network smoke check: python -m backend.tools.verify_tinyfish.

Exit 0 requires successful Search AND a live Fetch with employer-matching content.
An optional website restricts that check to its registered domain. Neither a
successful fetch nor an optional website hint establishes official ownership.
"""
import argparse
import asyncio
import json
from pathlib import Path

from backend.app import config
from backend.app.investigation.schemas import InvestigateRequest
from backend.app.investigation.service import investigate, now
from backend.app.investigation.tinyfish import TinyFishClient
from backend.app.investigation.urls import registered_domain


async def verify(employer: str, website: str | None, output: Path) -> int:
    client = TinyFishClient(config.TINYFISH_API_KEY)  # Real HTTP only; no test transport.
    request = InvestigateRequest(text=f"Employer: {employer}", employer_name=employer,
                                 official_website=website)
    report = await investigate(request, client)
    calls = report.provider_calls
    matching_sources = [source for source in report.sources_retrieved
                        if source.entity_match == 1 and source.characters_retrieved >= 80
                        and (not request.official_website or registered_domain(source.url) == registered_domain(request.official_website))]
    passed = (any(c.operation == "search" and c.http_status == 200 for c in calls)
              and any(c.operation == "fetch" and c.http_status == 200 for c in calls)
              and bool(matching_sources))
    receipt = {
        "live_retrieval_verified": passed, "checked_at": now(),
        "transport": "real HTTP to TinyFish; no mock transport",
        "meaning": "Verifies live source retrieval only, not any job offer or employer claim.",
        "report": report.model_dump(),
    }
    # Defense in depth: even if an upstream page echoed the key, redact it from
    # both the saved receipt and terminal output. Never print raw exceptions.
    serialized = json.dumps(receipt, indent=2)
    if config.TINYFISH_API_KEY:
        serialized = serialized.replace(config.TINYFISH_API_KEY, "[REDACTED]")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(serialized, encoding="utf-8")
    print(json.dumps({"live_retrieval_verified": passed, "investigation_status": report.status,
                      "successful_employer_related_pages": len(matching_sources), "receipt": str(output)}, indent=2))
    return 0 if passed else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--employer", default="TinyFish")
    parser.add_argument("--website", default=None)
    parser.add_argument("--output", type=Path, default=config.BACKEND_DIR / "reports/live_tinyfish_verification.json")
    args = parser.parse_args()
    try:
        result = asyncio.run(verify(args.employer, args.website, args.output))
    except Exception:
        print("Live verification did not complete. Check package installation and public URL configuration. No successful live verification is claimed.")
        result = 2
    raise SystemExit(result)


if __name__ == "__main__":
    main()
