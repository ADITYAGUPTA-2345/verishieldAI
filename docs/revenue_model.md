# Proposed revenue model

## Current state

VeriShield is a hackathon prototype. No billing, paid plans, organizational accounts, institutional contracts, customer revenue, or validated willingness-to-pay study exists. This document is a business hypothesis, not a claim of traction or a financial forecast. No market-size or growth statistics are asserted.

## Intended users and possible buyers

Individual students and job seekers need an understandable second look at suspicious offers. Placement offices and training institutions may want a consistent applicant-support workflow. Whether these users value paid access requires interviews and a pilot, not inference from classifier accuracy.

## Possible offerings (future work)

| Hypothesis | Value proposition | Validation needed |
| --- | --- | --- |
| Free local applicant screening | Accessible rules and ML screening without per-scan model API costs | Usability, trust, false-alarm impact, real-page effectiveness |
| Optional paid web-investigation allowance | Cover employer-source retrieval costs for frequent users | Cost per useful report, willingness to pay, quota handling |
| Institutional subscription | Applicant-support teams could review more offers consistently | Buyer interviews, privacy needs, staff time saved, procurement feasibility |
| Integration/API offering | Platforms could incorporate a documented screening workflow | Partner demand, service reliability, evidence quality, licensing and support obligations |

Only the existing local tool and optional TinyFish retrieval are implemented. Team review, quotas per customer, payments, hosted APIs and dashboards would require additional development.

## Costs and pricing discipline

Costs would include web retrieval/allowances, hosting for any future managed deployment, monitoring, support, security, and legal/privacy review. Local TF-IDF inference avoids an external model API, but still consumes local compute and needs maintenance. Do not assume a provider's current free tier will cover a commercial service indefinitely.

Before selecting prices, measure actual retrieval usage, completion rate, meaningful-source yield, support burden and infrastructure cost. A useful calculation for a future pilot is contribution per active customer = actual collected revenue - attributable retrieval/hosting/payment/support costs. No input values or margins are invented here.

## Trust and incentives

Do not sell employer-verification badges based on name similarity or suppress findings for payment. Do not monetize collected applicant/page content. Clearly distinguish screening from adjudicating fraud, and preserve the user's ability to inspect evidence and uncertainty.

## Proposed validation sequence

1. Run opt-in user interviews with applicants and placement staff.
2. Test real-page usability and independently labeled fraud performance.
3. Measure cost and yield of useful employer investigations under current provider terms.
4. Trial an institutional workflow only after access controls and privacy safeguards exist.
5. Set pricing only after demand and sustainable unit economics are observed.

These steps are future plans, not completed work or commitments.
