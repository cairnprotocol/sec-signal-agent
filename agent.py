"""Python-controlled agent loop. LLM reasons → Python executes tools → repeat."""
from __future__ import annotations

import json
import os
import re
from typing import Callable, Optional

from schemas import (
    TriggerExtraction, AccountContext, ProductFit, ScoringResult,
    WatchlistEntry, WhyNow, ToolTraceEntry,
    TriggerType, Novelty, RankBucket,
)
from tools import TOOL_DEFINITIONS, execute_tool, get_account_context, get_product_fit, get_scoring
from prompts import AGENT_SYSTEM, AGENT_USER_INIT, WHY_NOW_SYSTEM, WHY_NOW_USER

MAX_ITERATIONS = 6


def _lane_for_trigger(trigger_type: TriggerType) -> tuple[str, str]:
    if trigger_type in (TriggerType.DATA_PRIVACY_SECURITY_RISK, TriggerType.REGULATORY_COMPLIANCE_PRESSURE):
        return "trust_diligence", "Trust & Diligence"
    return "commercial_signal", "Commercial Signal"


def _lane_metadata(trigger_type: TriggerType) -> dict[str, str]:
    if trigger_type == TriggerType.DATA_PRIVACY_SECURITY_RISK:
        return {
            "review_lane": "Trust & Diligence",
            "scenario_label": "Privacy / security disclosure",
            "primary_user": "Trust/Security, Compliance, Quality reviewer",
            "deliverable_type": "Diligence packet",
        }
    if trigger_type == TriggerType.REGULATORY_COMPLIANCE_PRESSURE:
        return {
            "review_lane": "Trust & Diligence",
            "scenario_label": "Regulatory / compliance pressure",
            "primary_user": "Trust/Security, Compliance, Quality reviewer",
            "deliverable_type": "Diligence packet",
        }
    if trigger_type == TriggerType.REIMBURSEMENT_OR_COMMERCIAL_MODEL_PRESSURE:
        return {
            "review_lane": "Commercial Signal",
            "scenario_label": "Payer / commercial model pressure",
            "primary_user": "Partnerships / Commercial Strategy",
            "deliverable_type": "Partner brief",
        }
    return {
        "review_lane": "Commercial Signal",
        "scenario_label": "Platform / go-to-market change",
        "primary_user": "Partnerships / Commercial Strategy",
        "deliverable_type": "Partner brief",
    }


def _fallback_why_now(company_name: str, trigger: TriggerExtraction, workflow_route: str) -> str:
    lane_id, _ = _lane_for_trigger(trigger.trigger_type)

    if lane_id == "trust_diligence":
        if trigger.trigger_type == TriggerType.DATA_PRIVACY_SECURITY_RISK:
            return (
                f"{company_name} disclosed a cybersecurity, privacy, or security event that could appear in partner diligence or compliance review. "
                "Trust and Compliance teams should prepare comparable control evidence and partner Q&A before the issue comes up externally."
            )
        return (
            f"{company_name} disclosed regulatory or quality pressure that could shape partner diligence or compliance review. "
            "Trust and Compliance teams should prepare comparable oversight evidence and partner Q&A before the issue comes up externally."
        )

    if trigger.trigger_type == TriggerType.REIMBURSEMENT_OR_COMMERCIAL_MODEL_PRESSURE:
        return (
            f"{company_name} describes payer, reimbursement, or commercial model pressure that affects buyer priorities. "
            "Partnerships should use this as a brief for account planning, reimbursement discussion, or outreach timing."
        )

    return (
        f"{company_name} describes platform, channel, or go-to-market change that affects buyer priorities. "
        "Partnerships should use this as a brief for account planning, platform discussion, or outreach timing."
    )


def _fallback_recommended_action(company_name: str, trigger: TriggerExtraction, workflow_route: str) -> str:
    lane_id, _ = _lane_for_trigger(trigger.trigger_type)

    if lane_id == "trust_diligence":
        if trigger.trigger_type == TriggerType.REGULATORY_COMPLIANCE_PRESSURE:
            return f"Prepare a partner Q&A brief that summarizes {company_name}'s filing event and the compliance or quality questions likely to surface in diligence."
        return f"Draft a diligence packet that summarizes {company_name}'s filing event and gives the Trust lead partner-ready control evidence prompts."

    if trigger.trigger_type == TriggerType.REIMBURSEMENT_OR_COMMERCIAL_MODEL_PRESSURE:
        return f"Draft a one-page partner brief that links {company_name}'s reimbursement pressure to account priority for the Commercial Strategy lead."

    return f"Refresh the account plan to connect {company_name}'s operating change with a concrete Partnerships follow-up angle."


def _get_api_key() -> str:
    """Get Claude credential from Streamlit secrets or env var."""
    try:
        import streamlit as st
        return st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        return os.environ.get("ANTHROPIC_API_KEY", "")


def _call_claude_tools(system: str, messages: list, tools: list) -> dict:
    """Call Claude API with tool_use."""
    import anthropic

    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured")
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        system=system,
        messages=messages,
        tools=tools,
    )
    return response


def _call_claude_why_now(trigger_summary: str, account_summary: str, product_fit_summary: str, filing_date: str = "") -> WhyNow:
    """Dedicated LLM call for why_now generation."""
    import anthropic
    from datetime import date

    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured")
    client = anthropic.Anthropic(api_key=api_key)

    user_prompt = WHY_NOW_USER.format(
        trigger_summary=trigger_summary,
        account_context=account_summary,
        primary_solution=product_fit_summary,
        secondary_solution="",
        competitor_context="",
        filing_date=filing_date or "unknown",
        today_date=date.today().isoformat(),
    )

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=800,
        system=WHY_NOW_SYSTEM,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = response.content[0].text
    # Parse JSON
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        data = json.loads(cleaned)
        return WhyNow(**data)
    except Exception:
        return WhyNow(
            summary=raw[:500],
            routing_angle="See summary",
            recommended_action="Review filing and route evidence packet",
            confidence_note="Auto-generated fallback",
        )


def run_agent(
    trigger: TriggerExtraction,
    filing_meta: dict,
    filing_text: str = "",
    on_step: Optional[Callable] = None,
) -> WatchlistEntry:
    """
    Run the agent loop.

    Args:
        trigger: structured trigger from extractor
        filing_meta: dict with company_name, ticker, filing_type, filing_date
        filing_text: original filing text (for product mapping)
        on_step: optional callback(step_type, detail) for streaming UI updates

    Returns:
        WatchlistEntry
    """

    def emit(step_type: str, detail: str):
        if on_step:
            on_step(step_type, detail)

    ticker = filing_meta["ticker"]
    tool_trace: list[ToolTraceEntry] = []
    account_ctx: Optional[AccountContext] = None
    product_fit: Optional[ProductFit] = None
    scoring_result: Optional[ScoringResult] = None
    why_now: Optional[WhyNow] = None
    novelty = Novelty.UNKNOWN
    final_reasoning = ""
    final_action = ""
    final_confidence = ""

    # Build initial message
    evidence_str = "\n".join(f"- {q}" for q in trigger.evidence_quotes)
    init_msg = AGENT_USER_INIT.format(
        company_name=filing_meta["company_name"],
        ticker=ticker,
        filing_type=filing_meta["filing_type"],
        filing_date=filing_meta["filing_date"],
        trigger_type=trigger.trigger_type.value,
        urgency_tier=trigger.urgency_tier.value,
        confidence=trigger.confidence,
        short_summary=trigger.short_summary,
        evidence_quotes=evidence_str,
    )

    messages = [{"role": "user", "content": init_msg}]

    emit("agent_start", f"Starting agent loop for {filing_meta['company_name']} ({ticker})")

    for iteration in range(MAX_ITERATIONS):
        emit("iteration", f"Iteration {iteration + 1}/{MAX_ITERATIONS}")

        # Call Claude with tools
        try:
            response = _call_claude_tools(AGENT_SYSTEM, messages, TOOL_DEFINITIONS)
        except Exception as e:
            emit("error", f"LLM call failed: {e}")
            break

        # Process response blocks
        assistant_content = response.content
        stop_reason = response.stop_reason

        # Collect text reasoning
        reasoning_parts = []
        tool_calls = []

        for block in assistant_content:
            if block.type == "text":
                reasoning_parts.append(block.text)
                emit("reasoning", block.text)
            elif block.type == "tool_use":
                tool_calls.append(block)

        # Add assistant message to conversation
        messages.append({"role": "assistant", "content": assistant_content})

        # If no tool calls, we're done (shouldn't happen but handle gracefully)
        if not tool_calls:
            emit("agent_done", "Agent finished reasoning without tool call")
            if reasoning_parts:
                final_reasoning = " ".join(reasoning_parts)
            break

        # Process each tool call
        tool_results = []
        for tc in tool_calls:
            tool_name = tc.name
            tool_input = tc.input
            tool_id = tc.id

            emit("tool_call", f"Calling: {tool_name}({json.dumps(tool_input, default=str)[:200]})")

            # Execute tool
            if tool_name == "generate_why_now":
                # Special: this triggers a separate LLM call
                emit("tool_call", "Generating review-ready 'why now' summary...")
                try:
                    why_now = _call_claude_why_now(
                        trigger_summary=tool_input.get("trigger_summary", trigger.short_summary),
                        account_summary=tool_input.get("account_summary", ""),
                        product_fit_summary=tool_input.get("product_fit_summary", ""),
                        filing_date=filing_meta.get("filing_date", ""),
                    )
                    result_str = json.dumps(why_now.model_dump())
                except Exception as e:
                    result_str = json.dumps({"error": str(e)})
                    why_now = WhyNow(summary=f"Generation failed: {e}")

                trace = ToolTraceEntry(
                    tool_name=tool_name,
                    inputs=tool_input,
                    result_summary=why_now.summary[:200] if why_now else "failed",
                    reason="Generate review-ready summary",
                )

            elif tool_name == "emit_watchlist_entry":
                # Terminal action
                final_reasoning = tool_input.get("reasoning_summary", "")
                final_action = tool_input.get("recommended_action", "")
                final_confidence = tool_input.get("confidence_note", "")
                result_str = json.dumps({"status": "emitted"})

                trace = ToolTraceEntry(
                    tool_name=tool_name,
                    inputs=tool_input,
                    result_summary="Watchlist entry emitted",
                    reason="Final emission",
                )
                tool_trace.append(trace)
                emit("tool_result", f"{tool_name}: Entry emitted")

                # Add tool result to messages so conversation is valid
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": result_str,
                })
                messages.append({"role": "user", "content": tool_results})
                emit("agent_done", "Agent completed - watchlist entry emitted")

                # Run deterministic steps now
                if account_ctx is None:
                    account_ctx = get_account_context(ticker)
                if product_fit is None:
                    product_fit = get_product_fit(trigger, account_ctx, filing_text)
                scoring_result = get_scoring(trigger, account_ctx, novelty, filing_meta.get("filing_date", ""))

                return _build_entry(
                    filing_meta, trigger, account_ctx, product_fit,
                    scoring_result, why_now, tool_trace,
                    final_reasoning, final_action, final_confidence, novelty,
                )

            else:
                # Standard tool execution
                result_str = execute_tool(tool_name, tool_input, {})

                # Side-effect: capture account context
                if tool_name == "get_account_context":
                    account_ctx = get_account_context(tool_input["ticker"])
                    # Also compute product fit deterministically
                    product_fit = get_product_fit(trigger, account_ctx, filing_text)
                    # And scoring
                    scoring_result = get_scoring(trigger, account_ctx, novelty, filing_meta.get("filing_date", ""))

                elif tool_name == "check_prior_filing":
                    from tools import check_prior_filing
                    prior = check_prior_filing(tool_input["ticker"])
                    novelty = prior.novelty

                trace = ToolTraceEntry(
                    tool_name=tool_name,
                    inputs=tool_input,
                    result_summary=result_str[:300],
                    reason=f"Agent requested {tool_name}",
                )

            tool_trace.append(trace)
            emit("tool_result", f"{tool_name}: {result_str[:200]}")

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": result_str,
            })

        # Add all tool results back
        messages.append({"role": "user", "content": tool_results})

    # Fallback: if we hit max iterations without emit
    emit("fallback", "Max iterations reached — forcing watchlist entry emission")

    if account_ctx is None:
        account_ctx = get_account_context(ticker)
        tool_trace.append(ToolTraceEntry(
            tool_name="get_account_context",
            inputs={"ticker": ticker},
            result_summary="Loaded synthetic entity and workflow context.",
            reason="Pre-run deterministic demo mode",
        ))
    if product_fit is None:
        product_fit = get_product_fit(trigger, account_ctx, filing_text)
        tool_trace.append(ToolTraceEntry(
            tool_name="get_product_fit",
            inputs={"trigger_type": trigger.trigger_type.value, "ticker": ticker},
            result_summary=f"Mapped to review lane: {product_fit.primary_solution}",
            reason="Deterministic demo packet generation",
        ))
    if scoring_result is None:
        scoring_result = get_scoring(trigger, account_ctx, novelty, filing_meta.get("filing_date", ""))
        tool_trace.append(ToolTraceEntry(
            tool_name="get_scoring",
            inputs={"trigger_type": trigger.trigger_type.value, "filing_date": filing_meta.get("filing_date", "")},
            result_summary=f"Computed priority score: {scoring_result.final_score}",
            reason="Deterministic demo packet generation",
        ))

    workflow_route = product_fit.primary_solution if product_fit else (account_ctx.territory if account_ctx else "Review Queue")
    if not final_reasoning:
        final_reasoning = "Review packet generated from verified filing evidence and deterministic routing rules."
    if not final_confidence:
        final_confidence = "Manual review recommended"
    if not final_action:
        final_action = _fallback_recommended_action(filing_meta["company_name"], trigger, workflow_route)
    if why_now is None:
        why_now = WhyNow(
            summary=_fallback_why_now(filing_meta["company_name"], trigger, workflow_route),
            routing_angle=workflow_route,
            routing_note="Deterministic fallback summary generated without a live LLM call.",
            recommended_action=final_action,
            confidence_note=final_confidence or "Deterministic fallback generated from local source text.",
        )
        tool_trace.append(ToolTraceEntry(
            tool_name="generate_why_now",
            inputs={"trigger_summary": trigger.short_summary, "review_lane": workflow_route},
            result_summary=why_now.summary,
            reason="Review packet generated from verified filing evidence and deterministic routing rules",
        ))

    return _build_entry(
        filing_meta, trigger, account_ctx, product_fit,
        scoring_result, why_now, tool_trace,
        final_reasoning, final_action, final_confidence, novelty,
    )


def _build_entry(
    filing_meta: dict,
    trigger: TriggerExtraction,
    account: AccountContext,
    product_fit: ProductFit,
    scoring: ScoringResult,
    why_now: Optional[WhyNow],
    tool_trace: list[ToolTraceEntry],
    reasoning: str,
    action: str,
    confidence: str,
    novelty: Novelty,
) -> WatchlistEntry:
    """Assemble the final WatchlistEntry from all components."""
    lane_meta = _lane_metadata(trigger.trigger_type)
    review_lane = lane_meta["review_lane"]

    return WatchlistEntry(
        account_id=account.account_id if account else "",
        account_name=filing_meta["company_name"],
        ticker=filing_meta["ticker"],
        filing_type=filing_meta["filing_type"],
        filing_date=filing_meta["filing_date"],
        trigger_type=trigger.trigger_type,
        urgency_tier=trigger.urgency_tier,
        novelty=novelty,
        final_score=scoring.final_score if scoring else 0.0,
        rank_bucket=scoring.rank_bucket if scoring else RankBucket.SKIP,
        primary_solution=product_fit.primary_solution if product_fit else "",
        secondary_solution=product_fit.secondary_solution if product_fit else "",
        competitor_context=product_fit.competitor_context if product_fit else "",
        review_lane=review_lane,
        scenario_label=lane_meta["scenario_label"],
        primary_user=lane_meta["primary_user"],
        deliverable_type=lane_meta["deliverable_type"],
        why_now=why_now.summary if why_now else "",
        recommended_action=action or (why_now.recommended_action if why_now else ""),
        owner=account.owner if account else "",
        workflow_queue=review_lane,
        territory=review_lane,
        evidence_quotes=trigger.evidence_quotes,
        reasoning_summary=reasoning,
        tool_trace=tool_trace,
        confidence_note=confidence,
        rationale_tags=product_fit.rationale_tags if product_fit else [],
        source_type=filing_meta.get("source_type", ""),
        source_note=filing_meta.get("source_note", ""),
        source_url=filing_meta.get("source_url", filing_meta.get("filing_url", "")),
        accession_number=filing_meta.get("accession_number", filing_meta.get("source_reference", "")),
        filing_section=filing_meta.get("filing_section", ""),
        industry_group=filing_meta.get("industry_group", account.industry_group if account else ""),
        corpus_segment=filing_meta.get("corpus_segment", account.corpus_segment if account else ""),
        verification_status=filing_meta.get("verification_status", account.verification_status if account else ""),
        human_review_required=True,
    )
