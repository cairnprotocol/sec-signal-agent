from schemas import AccountContext, Novelty, RankBucket, TriggerExtraction, TriggerType, UrgencyTier
from scoring import score_trigger


def trigger(trigger_type, urgency, confidence):
    return TriggerExtraction(
        trigger_detected=True,
        trigger_type=trigger_type,
        urgency_tier=urgency,
        confidence=confidence,
        evidence_quotes=["verified filing evidence"],
    )


def account(tier="", status="", has_context=False):
    return AccountContext(
        account_name="Demo Company",
        ticker="DEMO",
        named_account_tier=tier,
        activity_status=status,
        open_opportunities=[{"context": "synthetic review context"}] if has_context else [],
        found=True,
    )


def test_priority_bucket_hot_for_high_confidence_security_trigger():
    result = score_trigger(
        trigger(TriggerType.DATA_PRIVACY_SECURITY_RISK, UrgencyTier.TIER_1, 1.0),
        account("Tier 1", "High", has_context=True),
        novelty=Novelty.NEW,
    )

    assert result.rank_bucket == RankBucket.HOT
    assert result.final_score >= 0.80


def test_priority_bucket_warm_for_relevant_mid_urgency_trigger():
    result = score_trigger(
        trigger(TriggerType.DATA_PRIVACY_SECURITY_RISK, UrgencyTier.TIER_2, 0.7),
        account("Tier 2", "Medium", has_context=True),
        novelty=Novelty.UNKNOWN,
    )

    assert result.rank_bucket == RankBucket.WARM
    assert 0.55 <= result.final_score < 0.80


def test_priority_bucket_monitor_for_lower_confidence_platform_trigger():
    result = score_trigger(
        trigger(TriggerType.OPERATING_SCALE_OR_PLATFORM_CHANGE, UrgencyTier.NONE, 0.5),
        account(),
        novelty=Novelty.REPEATED,
    )

    assert result.rank_bucket == RankBucket.MONITOR
    assert 0.35 <= result.final_score < 0.55


def test_priority_bucket_skip_for_no_actionable_trigger():
    result = score_trigger(
        trigger(TriggerType.NONE, UrgencyTier.NONE, 0.0),
        account(),
        novelty=Novelty.REPEATED,
    )

    assert result.rank_bucket == RankBucket.SKIP
    assert result.final_score < 0.35
