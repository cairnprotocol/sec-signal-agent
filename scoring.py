"""Deterministic scoring for trigger + account context."""
from __future__ import annotations

from datetime import date, timedelta

from schemas import (
    TriggerExtraction, AccountContext, ScoringResult,
    TriggerType, UrgencyTier, Novelty, RankBucket,
)


# Weights
TRIGGER_TYPE_WEIGHT = {
    TriggerType.CYBER_INCIDENT: 0.9,
    TriggerType.TRANSFORMATION: 0.7,
    TriggerType.REGULATORY_COMPLIANCE_PRESSURE: 0.75,
    TriggerType.DATA_PRIVACY_SECURITY_RISK: 0.85,
    TriggerType.OPERATING_SCALE_OR_PLATFORM_CHANGE: 0.7,
    TriggerType.REIMBURSEMENT_OR_COMMERCIAL_MODEL_PRESSURE: 0.8,
    TriggerType.NONE: 0.0,
}

URGENCY_WEIGHT = {
    UrgencyTier.TIER_1: 1.0,
    UrgencyTier.TIER_2: 0.6,
    UrgencyTier.NONE: 0.2,
}

TIER_WEIGHT = {
    "Tier 1": 1.0,
    "Tier 2": 0.7,
    "Verified": 1.0,
    "Review Ready": 0.8,
    "Evidence packet ready": 0.8,
    "Synthetic": 0.6,
    "": 0.4,
}

STATUS_WEIGHT = {
    "Expansion Target": 0.9,
    "Win-back": 0.8,
    "Prospect": 0.6,
    "High": 0.9,
    "Medium": 0.7,
    "Monitor": 0.5,
    "Review": 0.8,
    "": 0.4,
}

NOVELTY_WEIGHT = {
    Novelty.NEW: 1.0,
    Novelty.CHANGED: 0.8,
    Novelty.REPEATED: 0.3,
    Novelty.UNKNOWN: 0.6,
}


def _compute_recency(filing_date_str: str) -> float:
    """Compute recency score based on filing age.
    <3 months  → 1.0  (urgent)
    3-6 months → 0.75 (pressing)
    6-12 months → 0.5  (relevant)
    12-24 months → 0.3  (aging)
    >24 months → 0.15  (historical)
    """
    try:
        parts = filing_date_str.split("-")
        filing = date(int(parts[0]), int(parts[1]), int(parts[2]))
        age_days = (date.today() - filing).days

        if age_days <= 90:
            return 1.0
        elif age_days <= 180:
            return 0.75
        elif age_days <= 365:
            return 0.5
        elif age_days <= 730:
            return 0.3
        else:
            return 0.15
    except Exception:
        return 0.5  # default if date parsing fails


def score_trigger(
    trigger: TriggerExtraction,
    account: AccountContext,
    novelty: Novelty = Novelty.UNKNOWN,
    filing_date: str = "",
) -> ScoringResult:
    """Compute a deterministic score from trigger + account context + recency."""

    # Signal strength: trigger type weight × confidence
    signal = TRIGGER_TYPE_WEIGHT.get(trigger.trigger_type, 0.0) * trigger.confidence

    # Entity fit: evidence status + review priority + workflow context
    tier_score = TIER_WEIGHT.get(account.named_account_tier, 0.4)
    status_score = STATUS_WEIGHT.get(account.activity_status, 0.4)
    # Legacy compatibility: open_opportunities now carries synthetic workflow context.
    opp_bonus = 0.15 if account.open_opportunities else 0.0
    account_fit = min(1.0, (tier_score * 0.5 + status_score * 0.4 + opp_bonus))

    # Urgency
    urgency = URGENCY_WEIGHT.get(trigger.urgency_tier, 0.2)

    # Novelty
    nov_score = NOVELTY_WEIGHT.get(novelty, 0.6)

    # Recency (time decay)
    recency = _compute_recency(filing_date) if filing_date else 0.5

    # Composite: weighted average (recency gets meaningful weight)
    final = (
        signal * 0.25
        + account_fit * 0.20
        + urgency * 0.15
        + nov_score * 0.10
        + recency * 0.30
    )
    final = round(min(1.0, final), 3)

    # Bucket definitions used by the public UI:
    # Hot >= 0.80; Warm >= 0.55; Monitor >= 0.35; Skip < 0.35.
    if final >= 0.80:
        bucket = RankBucket.HOT
    elif final >= 0.55:
        bucket = RankBucket.WARM
    elif final >= 0.35:
        bucket = RankBucket.MONITOR
    else:
        bucket = RankBucket.SKIP

    return ScoringResult(
        signal_strength=round(signal, 3),
        account_fit=round(account_fit, 3),
        urgency=urgency,
        novelty_score=nov_score,
        final_score=final,
        rank_bucket=bucket,
    )
