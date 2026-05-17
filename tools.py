"""Tool implementations for the agent loop. Python-controlled, typed I/O."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import pandas as pd

from schemas import (
    AccountContext, PriorFilingResult, ProductFit, WhyNow,
    TriggerExtraction, Novelty, WatchlistEntry, ScoringResult,
    ToolTraceEntry,
)
from product_mapping import map_product_fit
from scoring import score_trigger

DATA_DIR = Path(__file__).parent / "data"

# Cache dataframes
_accounts_df: Optional[pd.DataFrame] = None
_workflows_df: Optional[pd.DataFrame] = None


def _load_accounts() -> pd.DataFrame:
    global _accounts_df
    if _accounts_df is None:
        _accounts_df = pd.read_excel(DATA_DIR / "prototype_accounts.xlsx")
    return _accounts_df


def _load_workflows() -> pd.DataFrame:
    global _workflows_df
    if _workflows_df is None:
        _workflows_df = pd.read_excel(DATA_DIR / "prototype_workflows.xlsx")
    return _workflows_df


# ============================================================
# Tool 1: get_account_context
# ============================================================
def get_account_context(ticker: str) -> AccountContext:
    """Look up synthetic entity and workflow context by ticker."""
    accounts = _load_accounts()
    workflows = _load_workflows()

    match = accounts[accounts["Ticker"].str.upper() == ticker.upper().strip()]
    if match.empty:
        return AccountContext(ticker=ticker, found=False)

    row = match.iloc[0]
    entity_id = str(row.get("entity_id", row.get("AccountId", "")))

    if "entity_id" in workflows.columns:
        context_rows = workflows[workflows["entity_id"] == entity_id]
    elif "Ticker" in workflows.columns:
        context_rows = workflows[workflows["Ticker"].str.upper() == ticker.upper().strip()]
    else:
        context_rows = workflows.iloc[0:0]
    workflow_context = context_rows.to_dict(orient="records") if not context_rows.empty else []

    return AccountContext(
        account_id=entity_id,
        account_name=str(row.get("entity_name", row.get("AccountName", ""))),
        ticker=str(row.get("Ticker", "")),
        domain=str(row.get("public_domain", row.get("WebsiteDomain", ""))),
        owner=str(row.get("review_owner", row.get("RepName", ""))),
        territory=str(row.get("workflow_queue", "")),
        segment=str(row.get("signal_category", row.get("Segment", ""))),
        activity_status=str(row.get("review_priority", row.get("AccountStatus", ""))),
        named_account_tier=str(row.get("evidence_status", row.get("NamedAccountTier", ""))),
        industry=str(row.get("Industry", "")),
        open_opportunities=workflow_context,
        notes=str(row.get("synthetic_context_note", row.get("Notes", ""))),
        tech_hints=str(row.get("technology_context", row.get("CurrentTechStack", ""))),
        industry_group=str(row.get("industry_group", "")),
        corpus_segment=str(row.get("corpus_segment", "")),
        source_type=str(row.get("source_type", "")),
        verification_status=str(row.get("verification_status", "")),
        found=True,
    )


# ============================================================
# Tool 2: check_prior_filing
# ============================================================
def check_prior_filing(ticker: str) -> PriorFilingResult:
    """Stub: check if we've seen prior filings from this company.
    In production, this would query a filing history store.
    For the demo, we return 'new' for all filings."""
    return PriorFilingResult(
        prior_filing_found=False,
        novelty=Novelty.NEW,
        delta_summary="No prior filings in the system for this company. This is a new signal.",
    )


# ============================================================
# Tool 3: get_product_fit (deterministic)
# ============================================================
def get_product_fit(
    trigger: TriggerExtraction,
    account: AccountContext,
    filing_text: str = "",
) -> ProductFit:
    """Deterministic workflow routing.

    ProductFit is a legacy compatibility schema; public copy treats it as
    workflow route / strategic relevance.
    """
    return map_product_fit(trigger, account, filing_text)


# ============================================================
# Tool 4: get_scoring (deterministic)
# ============================================================
def get_scoring(
    trigger: TriggerExtraction,
    account: AccountContext,
    novelty: Novelty = Novelty.UNKNOWN,
    filing_date: str = "",
) -> ScoringResult:
    """Deterministic scoring."""
    return score_trigger(trigger, account, novelty, filing_date)


# ============================================================
# Tool descriptions for the LLM (Claude tool_use format)
# ============================================================
TOOL_DEFINITIONS = [
    {
        "name": "get_account_context",
        "description": "Retrieve synthetic entity context and workflow hints for a company by ticker symbol. Returns public entity details, review queue, technology hints, and workflow context.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol (e.g. 'CLX', 'UNH')"
                }
            },
            "required": ["ticker"]
        }
    },
    {
        "name": "check_prior_filing",
        "description": "Check whether we have processed prior SEC filings from this company. Returns novelty assessment (new/changed/repeated).",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol"
                }
            },
            "required": ["ticker"]
        }
    },
    {
        "name": "generate_why_now",
        "description": "Generate a review-ready 'why now' summary combining the trigger evidence, synthetic entity context, and workflow route. Call this after you have entity context.",
        "input_schema": {
            "type": "object",
            "properties": {
                "trigger_summary": {
                    "type": "string",
                    "description": "Summary of the filing trigger and key evidence"
                },
                "account_summary": {
                    "type": "string",
                    "description": "Summary of entity context, review status, and workflow context"
                },
                "product_fit_summary": {
                    "type": "string",
                    "description": "Primary and secondary workflow route"
                }
            },
            "required": ["trigger_summary", "account_summary", "product_fit_summary"]
        }
    },
    {
        "name": "emit_watchlist_entry",
        "description": "Finalize and emit the watchlist entry. Call this ONLY when you have gathered enough information. Include your reasoning summary.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reasoning_summary": {
                    "type": "string",
                    "description": "2-3 sentence summary of your analysis and why this account deserves attention"
                },
                "recommended_action": {
                    "type": "string",
                    "description": "Specific deliverable-oriented review action. Start with Draft, Prepare, Refresh, or Update. Do not use generic routing language."
                },
                "confidence_note": {
                    "type": "string",
                    "description": "Note on confidence level and any caveats"
                }
            },
            "required": ["reasoning_summary", "recommended_action", "confidence_note"]
        }
    },
    {
        "name": "check_news_corroboration",
        "description": "Search recent news for corroborating coverage of the filing trigger. Returns matching headlines from Google News. Use this to validate that the filing signal has real-world news coverage and add context.",
        "input_schema": {
            "type": "object",
            "properties": {
                "company_name": {
                    "type": "string",
                    "description": "Company name to search for"
                },
                "trigger_type": {
                    "type": "string",
                    "enum": [
                        "cyber_incident",
                        "transformation",
                        "regulatory_compliance_pressure",
                        "data_privacy_security_risk",
                        "operating_scale_or_platform_change",
                        "reimbursement_or_commercial_model_pressure",
                    ],
                    "description": "Type of trigger to corroborate"
                }
            },
            "required": ["company_name", "trigger_type"]
        }
    },
]


def execute_tool(tool_name: str, tool_input: dict, context: dict) -> str:
    """Dispatch a tool call and return a string result for the LLM."""

    if tool_name == "get_account_context":
        result = get_account_context(tool_input["ticker"])
        # Format for LLM consumption
        if not result.found:
            return json.dumps({"found": False, "note": f"No account found for ticker {tool_input['ticker']}"})
        workflow_summary = []
        for item in result.open_opportunities:
            workflow_summary.append({
                "entity_id": item.get("entity_id", item.get("AccountId", "")),
                "signal_category": item.get("signal_category", item.get("UseCase", "")),
                "review_priority": item.get("review_priority", item.get("Stage", "")),
                "evidence_status": item.get("evidence_status", ""),
                "recommended_review_action": item.get("recommended_review_action", item.get("NextStep", "")),
            })
        return json.dumps({
            "found": True,
            "entity_name": result.account_name,
            "ticker": result.ticker,
            "industry": result.industry,
            "review_owner": result.owner,
            "workflow_queue": result.territory,
            "signal_category": result.segment,
            "review_priority": result.activity_status,
            "evidence_status": result.named_account_tier,
            "technology_context": result.tech_hints,
            "synthetic_context_note": result.notes,
            "workflow_context": workflow_summary,
        }, default=str)

    elif tool_name == "check_prior_filing":
        result = check_prior_filing(tool_input["ticker"])
        return json.dumps(result.model_dump())

    elif tool_name == "generate_why_now":
        # This will be handled by LLM call in agent.py
        # Return a marker so the agent loop knows to make the LLM call
        return "__WHY_NOW_LLM_CALL__"

    elif tool_name == "emit_watchlist_entry":
        # This is the terminal action - return the input as-is
        return json.dumps({"status": "emitted", **tool_input})

    elif tool_name == "check_news_corroboration":
        from news_feed import search_news
        result = search_news(
            company_name=tool_input.get("company_name", ""),
            trigger_type=tool_input.get("trigger_type", "cyber_incident"),
        )
        hits_summary = [{"title": h.title, "source": h.source, "date": h.pub_date} for h in result.hits[:3]]
        return json.dumps({
            "corroborated": result.corroborated,
            "num_articles": len(result.hits),
            "summary": result.summary,
            "headlines": hits_summary,
        })

    else:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})
