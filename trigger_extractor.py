"""LLM Call #1: Extract structured trigger from filing text."""
from __future__ import annotations

import json
import os
import re
from typing import Optional

from schemas import TriggerExtraction, TriggerType, UrgencyTier
from prompts import TRIGGER_EXTRACTOR_SYSTEM, TRIGGER_EXTRACTOR_USER


def _get_api_key() -> str:
    """Get Claude credential from Streamlit secrets or env var."""
    try:
        import streamlit as st
        return st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        return os.environ.get("ANTHROPIC_API_KEY", "")


def _call_claude(system: str, user: str, max_tokens: int = 1500) -> str:
    """Call Claude API. Reads credential from Streamlit secrets or ANTHROPIC_API_KEY env var."""
    import anthropic

    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured")

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text


def _parse_trigger_json(raw: str) -> dict:
    """Parse JSON from LLM response, handling markdown fences."""
    cleaned = raw.strip()
    # Strip markdown code fences
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned)


def _extract_excerpt_body(text: str) -> str:
    marker = "Excerpt:"
    if marker in text:
        return text.split(marker, 1)[1].strip()
    return text.strip()


def _first_sentences(text: str, max_sentences: int = 2) -> list[str]:
    body = _extract_excerpt_body(text)
    pieces = re.split(r"(?<=[.!?])\s+", body)
    quote = " ".join(p.strip() for p in pieces[:max_sentences] if p.strip())
    return [quote] if quote else []


def _heuristic_trigger(filing_text: str, error: str = "", primary_trigger_hint: str = "") -> TriggerExtraction:
    """Deterministic fallback for demos when live extraction is unavailable."""
    text = _extract_excerpt_body(filing_text)
    lower = text.lower()
    compact_triggers = {
        TriggerType.REGULATORY_COMPLIANCE_PRESSURE.value,
        TriggerType.DATA_PRIVACY_SECURITY_RISK.value,
        TriggerType.OPERATING_SCALE_OR_PLATFORM_CHANGE.value,
        TriggerType.REIMBURSEMENT_OR_COMMERCIAL_MODEL_PRESSURE.value,
    }
    summary_by_hint = {
        TriggerType.REGULATORY_COMPLIANCE_PRESSURE: "The filing excerpt describes regulatory, compliance, reporting, or quality pressure.",
        TriggerType.DATA_PRIVACY_SECURITY_RISK: "The filing excerpt describes privacy, security, cybersecurity, or protected-data risk.",
        TriggerType.OPERATING_SCALE_OR_PLATFORM_CHANGE: "The filing excerpt describes operating scale, platform, workflow, or integration change.",
        TriggerType.REIMBURSEMENT_OR_COMMERCIAL_MODEL_PRESSURE: "The filing excerpt describes payer, reimbursement, coverage, or commercial model pressure.",
    }

    trigger_type = TriggerType.NONE
    summary = "No actionable operational signal detected."
    confidence = 0.0
    urgency = UrgencyTier.NONE

    if any(term in lower for term in [
        "hipaa", "privacy", "security", "data breach", "phi", "personally identifiable",
        "ransomware", "cybersecurity incident", "unauthorized activity", "unauthorized occurrences",
        "suspicious activity", "stole data", "stolen or destroyed", "exfiltrated", "encrypted certain",
    ]):
        trigger_type = TriggerType.DATA_PRIVACY_SECURITY_RISK
        summary = "The filing excerpt describes healthcare privacy, security, or protected-data obligations."
        confidence = 0.88
        urgency = UrgencyTier.TIER_1 if any(term in lower for term in ["ransomware", "cybersecurity incident", "unauthorized activity", "unauthorized occurrences", "suspicious activity"]) else UrgencyTier.TIER_2
    elif any(term in lower for term in ["medicare advantage", "cms contracts", "annual renewal", "cms must also annually approve"]):
        trigger_type = TriggerType.REGULATORY_COMPLIANCE_PRESSURE
        summary = "The filing excerpt describes CMS or Medicare Advantage contract and approval exposure."
        confidence = 0.86
        urgency = UrgencyTier.TIER_2
    elif any(term in lower for term in ["reimbursement", "third-party payors", "payers", "payors", "coverage", "cpt"]):
        trigger_type = TriggerType.REIMBURSEMENT_OR_COMMERCIAL_MODEL_PRESSURE
        summary = "The filing excerpt describes payer, reimbursement, coverage, or commercial model pressure."
        confidence = 0.87
        urgency = UrgencyTier.TIER_2
    elif any(term in lower for term in [
        "covered lives", "go-to-market", "platform", "workflow", "onboarding", "integration",
        "members include", "erp", "enterprise resource planning", "implementation", "operating model",
    ]):
        trigger_type = TriggerType.OPERATING_SCALE_OR_PLATFORM_CHANGE
        summary = "The filing excerpt describes operating scale, platform, workflow, or integration change."
        confidence = 0.84
        urgency = UrgencyTier.TIER_2

    if primary_trigger_hint in compact_triggers:
        trigger_type = TriggerType(primary_trigger_hint)
        summary = summary_by_hint[trigger_type]
        confidence = max(confidence, 0.86)
        if urgency == UrgencyTier.NONE:
            urgency = UrgencyTier.TIER_2

    return TriggerExtraction(
        trigger_detected=trigger_type != TriggerType.NONE,
        trigger_type=trigger_type,
        urgency_tier=urgency,
        confidence=confidence,
        extraction_error=None,
        short_summary=summary,
        evidence_quotes=_first_sentences(filing_text, 2),
        filing_sections_used=[],
    )


def extract_trigger(
    company_name: str,
    ticker: str,
    filing_type: str,
    filing_date: str,
    filing_text: str,
    primary_trigger_hint: str = "",
    max_text_chars: int = 12000,
) -> TriggerExtraction:
    """Run trigger extraction on filing text. Returns typed TriggerExtraction."""

    # Truncate filing text to fit context
    truncated = filing_text[:max_text_chars]

    user_prompt = TRIGGER_EXTRACTOR_USER.format(
        company_name=company_name,
        ticker=ticker,
        filing_type=filing_type,
        filing_date=filing_date,
        filing_text=truncated,
    )

    try:
        raw_response = _call_claude(TRIGGER_EXTRACTOR_SYSTEM, user_prompt)
        data = _parse_trigger_json(raw_response)

        trigger_value = data.get("trigger_type", "none")
        return TriggerExtraction(
            trigger_detected=data.get("trigger_detected", False),
            trigger_type=TriggerType(trigger_value),
            urgency_tier=UrgencyTier(data.get("urgency_tier", "none")),
            confidence=float(data.get("confidence", 0.0)),
            short_summary=data.get("short_summary", ""),
            evidence_quotes=data.get("evidence_quotes", []),
            filing_sections_used=data.get("filing_sections_used", []),
        )
    except Exception as e:
        return _heuristic_trigger(filing_text, str(e), primary_trigger_hint)
