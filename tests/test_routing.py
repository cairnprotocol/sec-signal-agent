import pytest

from product_mapping import map_product_fit
from schemas import AccountContext, TriggerExtraction, TriggerType, UrgencyTier


def trigger(trigger_type):
    return TriggerExtraction(
        trigger_detected=True,
        trigger_type=trigger_type,
        urgency_tier=UrgencyTier.TIER_2,
        confidence=0.9,
        evidence_quotes=["verified filing evidence"],
    )


def account():
    return AccountContext(account_name="Demo Company", ticker="DEMO", found=True)


@pytest.mark.parametrize(
    ("trigger_type", "lane", "scenario", "required_tags", "forbidden_tags"),
    [
        (
            TriggerType.DATA_PRIVACY_SECURITY_RISK,
            "Trust & Diligence",
            "Privacy / security disclosure",
            {"trust_diligence", "privacy_security", "security_diligence"},
            {"commercial_signal", "platform_systems", "payer_pressure"},
        ),
        (
            TriggerType.REGULATORY_COMPLIANCE_PRESSURE,
            "Trust & Diligence",
            "Regulatory / compliance pressure",
            {"trust_diligence", "regulatory_compliance"},
            {"commercial_signal", "platform_systems", "payer_pressure"},
        ),
        (
            TriggerType.OPERATING_SCALE_OR_PLATFORM_CHANGE,
            "Commercial Signal",
            "Platform / go-to-market change",
            {"commercial_signal", "platform_change", "platform_systems", "partnerships"},
            {"trust_diligence", "privacy_security", "security_diligence"},
        ),
        (
            TriggerType.REIMBURSEMENT_OR_COMMERCIAL_MODEL_PRESSURE,
            "Commercial Signal",
            "Payer / commercial model pressure",
            {"commercial_signal", "reimbursement", "commercial_model", "payer_pressure"},
            {"trust_diligence", "privacy_security", "security_diligence"},
        ),
    ],
)
def test_trigger_type_maps_to_expected_review_lane_and_tags(
    trigger_type, lane, scenario, required_tags, forbidden_tags
):
    fit = map_product_fit(trigger(trigger_type), account(), filing_text="verified public filing excerpt")

    assert fit.primary_solution == lane
    assert fit.secondary_solution == scenario
    assert required_tags.issubset(set(fit.rationale_tags))
    assert forbidden_tags.isdisjoint(set(fit.rationale_tags))


def test_privacy_language_adds_data_governance_only_for_trust_lane():
    fit = map_product_fit(
        trigger(TriggerType.DATA_PRIVACY_SECURITY_RISK),
        account(),
        filing_text="The company is subject to privacy and sensitive data requirements.",
    )

    assert fit.primary_solution == "Trust & Diligence"
    assert "data_governance" in fit.rationale_tags
    assert "platform_systems" not in fit.rationale_tags
