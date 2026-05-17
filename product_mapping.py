"""Deterministic workflow routing based on trigger type and entity context."""
from __future__ import annotations

from schemas import TriggerExtraction, AccountContext, ProductFit, TriggerType

# Keywords for secondary route detection.
GOVERNANCE_KEYWORDS = ["ai agent", "copilot", "model governance", "data governance", "dspm", "privacy", "sensitive data"]


def map_product_fit(
    trigger: TriggerExtraction,
    account: AccountContext,
    filing_text: str = "",
) -> ProductFit:
    """Map trigger + entity context to a deterministic workflow route.

    The schema still uses ProductFit for compatibility with the original
    prototype. Public-facing copy treats these values as workflow routes.
    """

    text_lower = filing_text.lower()
    tech_lower = account.tech_hints.lower() if account.tech_hints else ""
    combined = text_lower + " " + tech_lower

    primary = ""
    secondary = ""
    routing_context = ""
    tags: list[str] = []

    # --- Primary routing based on compact public trigger lanes ---
    if trigger.trigger_type == TriggerType.REGULATORY_COMPLIANCE_PRESSURE:
        primary = "Trust & Diligence"
        secondary = "Regulatory / compliance pressure"
        routing_context = "Compliance readiness brief"
        tags.extend(["trust_diligence", "regulatory_compliance", "quality_reporting"])

    elif trigger.trigger_type == TriggerType.DATA_PRIVACY_SECURITY_RISK:
        primary = "Trust & Diligence"
        secondary = "Privacy / security disclosure"
        routing_context = "Diligence packet"
        tags.extend(["trust_diligence", "privacy_security", "security_diligence"])

    elif trigger.trigger_type == TriggerType.OPERATING_SCALE_OR_PLATFORM_CHANGE:
        primary = "Commercial Signal"
        secondary = "Platform / go-to-market change"
        routing_context = "Partner brief"
        tags.extend(["commercial_signal", "platform_change", "platform_systems", "partnerships"])

    elif trigger.trigger_type == TriggerType.REIMBURSEMENT_OR_COMMERCIAL_MODEL_PRESSURE:
        primary = "Commercial Signal"
        secondary = "Payer / commercial model pressure"
        routing_context = "Partner brief"
        tags.extend(["commercial_signal", "reimbursement", "commercial_model", "payer_pressure"])

    elif trigger.trigger_type == TriggerType.CYBER_INCIDENT:
        primary = "Trust & Diligence"
        secondary = "Privacy / security disclosure"
        routing_context = "Diligence packet"
        tags.extend(["trust_diligence", "privacy_security", "security_diligence"])

    elif trigger.trigger_type == TriggerType.TRANSFORMATION:
        primary = "Commercial Signal"
        secondary = "Platform / go-to-market change"
        routing_context = "Partner brief"
        tags.extend(["commercial_signal", "platform_change", "platform_systems", "partnerships"])

    if any(kw in combined for kw in GOVERNANCE_KEYWORDS):
        if trigger.trigger_type in (
            TriggerType.DATA_PRIVACY_SECURITY_RISK,
            TriggerType.REGULATORY_COMPLIANCE_PRESSURE,
        ):
            tags.append("data_governance")

    return ProductFit(
        primary_solution=primary,
        secondary_solution=secondary,
        competitor_context=routing_context,
        rationale_tags=tags,
    )
