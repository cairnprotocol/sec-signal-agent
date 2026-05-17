"""Typed schemas for the SEC signal agent prototype."""
from __future__ import annotations

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class TriggerType(str, Enum):
    CYBER_INCIDENT = "cyber_incident"
    TRANSFORMATION = "transformation"
    REGULATORY_COMPLIANCE_PRESSURE = "regulatory_compliance_pressure"
    DATA_PRIVACY_SECURITY_RISK = "data_privacy_security_risk"
    OPERATING_SCALE_OR_PLATFORM_CHANGE = "operating_scale_or_platform_change"
    REIMBURSEMENT_OR_COMMERCIAL_MODEL_PRESSURE = "reimbursement_or_commercial_model_pressure"
    NONE = "none"


class UrgencyTier(str, Enum):
    TIER_1 = "tier_1"  # 48h - act now
    TIER_2 = "tier_2"  # 1 week - pursue soon
    NONE = "none"


class Novelty(str, Enum):
    NEW = "new"
    CHANGED = "changed"
    REPEATED = "repeated"
    UNKNOWN = "unknown"


class RankBucket(str, Enum):
    HOT = "hot"
    WARM = "warm"
    MONITOR = "monitor"
    SKIP = "skip"


# --- LLM Call #1 output ---
class TriggerExtraction(BaseModel):
    trigger_detected: bool = False
    trigger_type: TriggerType = TriggerType.NONE
    urgency_tier: UrgencyTier = UrgencyTier.NONE
    confidence: float = 0.0
    extraction_error: Optional[str] = None
    short_summary: str = ""
    evidence_quotes: List[str] = Field(default_factory=list)
    filing_sections_used: List[str] = Field(default_factory=list)


# --- Account context from Excel join ---
class AccountContext(BaseModel):
    account_id: str = ""
    account_name: str = ""
    ticker: str = ""
    domain: str = ""
    owner: str = ""
    territory: str = ""
    segment: str = ""
    activity_status: str = ""
    named_account_tier: str = ""
    industry: str = ""
    open_opportunities: List[dict] = Field(default_factory=list)
    notes: str = ""
    tech_hints: str = ""
    industry_group: str = ""
    corpus_segment: str = ""
    source_type: str = ""
    verification_status: str = ""
    found: bool = False


# --- Deterministic product mapping ---
class ProductFit(BaseModel):
    primary_solution: str = ""
    secondary_solution: str = ""
    competitor_context: str = ""
    rationale_tags: List[str] = Field(default_factory=list)


# --- Prior filing check ---
class PriorFilingResult(BaseModel):
    prior_filing_found: bool = False
    novelty: Novelty = Novelty.UNKNOWN
    delta_summary: str = ""


# --- Scoring ---
class ScoringResult(BaseModel):
    signal_strength: float = 0.0
    account_fit: float = 0.0
    urgency: float = 0.0
    novelty_score: float = 0.0
    final_score: float = 0.0
    rank_bucket: RankBucket = RankBucket.SKIP


# --- Why Now (LLM or template) ---
class WhyNow(BaseModel):
    summary: str = ""
    routing_angle: str = ""
    routing_note: str = ""
    recommended_action: str = ""
    confidence_note: str = ""


# --- Tool trace entry ---
class ToolTraceEntry(BaseModel):
    tool_name: str
    inputs: dict = Field(default_factory=dict)
    result_summary: str = ""
    reason: str = ""


# --- Final watchlist entry ---
class WatchlistEntry(BaseModel):
    account_id: str = ""
    account_name: str = ""
    ticker: str = ""
    filing_type: str = ""
    filing_date: str = ""
    trigger_type: TriggerType = TriggerType.NONE
    urgency_tier: UrgencyTier = UrgencyTier.NONE
    novelty: Novelty = Novelty.UNKNOWN
    final_score: float = 0.0
    rank_bucket: RankBucket = RankBucket.SKIP
    primary_solution: str = ""
    secondary_solution: str = ""
    competitor_context: str = ""
    review_lane: str = ""
    scenario_label: str = ""
    primary_user: str = ""
    deliverable_type: str = ""
    why_now: str = ""
    recommended_action: str = ""
    owner: str = ""
    workflow_queue: str = ""
    territory: str = ""
    evidence_quotes: List[str] = Field(default_factory=list)
    reasoning_summary: str = ""
    tool_trace: List[ToolTraceEntry] = Field(default_factory=list)
    confidence_note: str = ""
    rationale_tags: List[str] = Field(default_factory=list)
    source_type: str = ""
    source_note: str = ""
    source_url: str = ""
    accession_number: str = ""
    filing_section: str = ""
    industry_group: str = ""
    corpus_segment: str = ""
    verification_status: str = ""
    human_review_required: bool = True


# --- Filing metadata ---
class FilingMeta(BaseModel):
    company_name: str = ""
    ticker: str = ""
    filing_type: str = ""
    form_type: str = ""
    filing_date: str = ""
    filing_url: str = ""
    source_url: str = ""
    cik: str = ""
    accession_number: str = ""
    source_reference: str = ""
    filing_section: str = ""
    trigger_family: str = ""
    primary_trigger_hint: str = ""
    secondary_trigger_hint: str = ""
    source_type: str = ""
    source_note: str = ""
    notes: str = ""
    text_path: str = ""
    local_text_path: str = ""
    industry_group: str = ""
    industry_subsector: str = ""
    corpus_segment: str = ""
    verification_status: str = ""
    sections_path: str = ""
