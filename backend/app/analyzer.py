"""Deterministic indicators. Each distinct rule contributes points only once.

Scores describe matched warning indicators, never ML confidence or fraud probability.
The rules deliberately favor explainability over broad coverage.
"""

import re
from dataclasses import dataclass

from .schemas import AnalyzeResponse, Finding


@dataclass(frozen=True)
class Rule:
    id: str
    label: str
    pattern: str
    points: int
    explanation: str


RULES = (
    Rule("upfront_payment", "Upfront payment requested",
         r"\b(?:pay\s+(?:(?:a|an|the)\s+)?(?:registration|application|training|processing|security)\s+(?:fee|deposit)|(?:registration|application|training|processing)\s+fee\s+(?:is\s+)?(?:required|mandatory)|(?:send|pay)\s+(?:us\s+)?(?:money|a\s+deposit)\s+(?:to|before)\s+(?:apply|start|join))\b",
         35, "Requests for payment to apply, train, or start work deserve independent verification."),
    Rule("sensitive_information", "Sensitive information requested early",
         r"\b(?:send|share|provide|submit)\s+(?:your\s+)?(?:bank\s+(?:details|account)|(?:aadhaar|aadhar|pan|social\s+security)\s+(?:number|card)|passport\s+(?:copy|number)|otp|password)\b",
         30, "Requests for financial details, identity documents, passwords, or OTPs can enable identity theft. Check the hiring stage and recipient."),
    Rule("guaranteed_hiring", "Guaranteed hiring claim",
         r"\b(?:guaranteed\s+(?:job|placement|hiring|selection)|(?:job|selection|placement)\s+(?:is\s+)?guaranteed|no\s+interview\s+(?:required|needed))\b",
         20, "Guaranteed selection or hiring without an interview can indicate an unreliable recruitment process."),
    Rule("easy_money", "Unrealistic earnings language",
         r"\b(?:easy\s+money|(?:earn|make)\s+(?:up\s+to\s+)?(?:[$₹€£]\s*)?[\d,]+\s*(?:dollars|rupees|usd|inr)?\s*(?:per|a|/)\s*(?:day|week)\s+(?:with\s+)?(?:no|little|minimal)\s+(?:work|effort)|unlimited\s+(?:income|earnings))\b",
         20, "Promises of easy or unlimited income may be misleading. Verify pay, duties, and employment terms."),
    Rule("pressure", "Urgency or pressure to act",
         r"\b(?:act\s+now|(?:pay|apply|register)\s+immediately|(?:offer|opportunity)\s+expires\s+(?:today|in\s+\d+\s+hours)|limited\s+slots\s+(?:left|available))\b",
         10, "Pressure to act quickly can discourage proper checks; urgency alone is not proof of fraud."),
    Rule("messaging_only", "Messaging-only recruitment",
         r"\b(?:(?:contact|message|apply|interview)\s+(?:us\s+)?(?:only\s+(?:on|via|through)\s+(?:whatsapp|telegram)|(?:on|via|through)\s+(?:whatsapp|telegram)\s+only))\b",
         15, "An exclusively messaging-based process may be harder to verify. Seek an official company contact."),
    Rule("money_transfer", "Unusual payment or money transfer duties",
         r"\b(?:buy\s+(?:gift\s+cards|crypto(?:currency)?)|(?:receive|deposit)\s+(?:a\s+)?check\s+and\s+(?:send|transfer)|(?:send|transfer)\s+(?:funds|money)\s+(?:to|on\s+behalf\s+of)\s+(?:clients|customers|our\s+company))\b",
         35, "Gift cards, crypto purchases, or moving funds for an employer are warning signs of payment scams."),
)


def analyze(text: str) -> AnalyzeResponse:
    # Collapse whitespace so rules also match text split across visible elements.
    normalized = re.sub(r"\s+", " ", text).strip()
    findings = []
    for rule in RULES:
        match = re.search(rule.pattern, normalized, re.IGNORECASE)
        if match:
            findings.append(Finding(
                rule_id=rule.id, label=rule.label, explanation=rule.explanation,
                evidence=normalized[max(0, match.start() - 55):min(len(normalized), match.end() + 55)],
                points=rule.points,
            ))
    score = min(100, sum(f.points for f in findings))
    level = "high" if score >= 50 else "medium" if score >= 20 else "low"
    summary = (
        f"Matched {len(findings)} suspicious pattern(s). Review the evidence before proceeding."
        if findings else "No configured suspicious patterns matched the submitted text."
    )
    return AnalyzeResponse(risk_level=level, risk_score=score, summary=summary,
                           findings=findings, characters_analyzed=len(text))
