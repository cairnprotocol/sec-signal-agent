"""SEC Signal Agent — Streamlit Dashboard"""
from __future__ import annotations

import json
import time
from pathlib import Path

import streamlit as st

from schemas import WatchlistEntry, TriggerType, RankBucket
from filing_loader import load_manifest, load_filing_text
from trigger_extractor import extract_trigger
from agent import run_agent

DEMO_OUTPUT = Path(__file__).parent / "demo_outputs" / "prerun_watchlist.json"

# ── Page config ──────────────────────────────────────────────
st.set_page_config(
    page_title="SEC Signal Agent",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ───────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=DM+Sans:wght@400;500;700&display=swap');

    .stApp { font-family: 'DM Sans', sans-serif; }

    /* ── Theme-aware CSS variables ── */
    :root {
        --card-bg: #ffffff;
        --card-border: #e2e8f0;
        --card-shadow: rgba(0,0,0,0.06);
        --tag-bg: #f1f5f9;
        --tag-color: #475569;
        --tag-cyber-bg: #fef2f2;
        --tag-cyber-color: #dc2626;
        --tag-transform-bg: #eff6ff;
        --tag-transform-color: #2563eb;
        --tag-warm-bg: #fffbeb;
        --tag-warm-color: #d97706;
        --trace-bg: #f8fafc;
        --trace-border: #e2e8f0;
        --step-reasoning-bg: #f0fdf4;
        --step-tool-bg: #eff6ff;
        --step-result-bg: #f8fafc;
        --step-done-bg: #fefce8;
        --text-primary: #1a1a2e;
        --text-secondary: #475569;
    }

    /* Dark mode overrides — Streamlit adds data-theme or .stApp has dark bg */
    @media (prefers-color-scheme: dark) {
        :root {
            --card-bg: #1e1e2e;
            --card-border: #333355;
            --card-shadow: rgba(0,0,0,0.3);
            --tag-bg: #2a2a3e;
            --tag-color: #c4c4d4;
            --tag-cyber-bg: #3d1f1f;
            --tag-cyber-color: #f87171;
            --tag-transform-bg: #1e2a4a;
            --tag-transform-color: #60a5fa;
            --tag-warm-bg: #3d3520;
            --tag-warm-color: #fbbf24;
            --trace-bg: #1a1a2e;
            --trace-border: #333355;
            --step-reasoning-bg: #1a2e1a;
            --step-tool-bg: #1a1e3e;
            --step-result-bg: #1e1e2e;
            --step-done-bg: #2e2d1a;
            --text-primary: #e2e2f0;
            --text-secondary: #a0a0b8;
        }
    }

    /* Also detect Streamlit's own dark theme class */
    [data-testid="stAppViewContainer"][style*="background-color: rgb(14"],
    [data-testid="stAppViewContainer"][style*="background-color: rgb(17"],
    .stApp[data-theme="dark"] {
        --card-bg: #1e1e2e;
        --card-border: #333355;
        --card-shadow: rgba(0,0,0,0.3);
        --tag-bg: #2a2a3e;
        --tag-color: #c4c4d4;
        --tag-cyber-bg: #3d1f1f;
        --tag-cyber-color: #f87171;
        --tag-transform-bg: #1e2a4a;
        --tag-transform-color: #60a5fa;
        --tag-warm-bg: #3d3520;
        --tag-warm-color: #fbbf24;
        --trace-bg: #1a1a2e;
        --trace-border: #333355;
        --step-reasoning-bg: #1a2e1a;
        --step-tool-bg: #1a1e3e;
        --step-result-bg: #1e1e2e;
        --step-done-bg: #2e2d1a;
        --text-primary: #e2e2f0;
        --text-secondary: #a0a0b8;
    }

    .metric-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border-radius: 12px;
        padding: 20px;
        color: white;
        text-align: center;
        border: 1px solid #2a2a4a;
    }
    .metric-card h2 { margin: 0; font-size: 2.2rem; font-weight: 700; }
    .metric-card p { margin: 4px 0 0; opacity: 0.7; font-size: 0.85rem; }

    .watchlist-card {
        background: var(--card-bg);
        border: 1px solid var(--card-border);
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 16px;
        box-shadow: 0 1px 3px var(--card-shadow);
        color: var(--text-primary);
    }

    .bucket-hot {
        border-left: 5px solid #ef4444;
    }
    .bucket-warm {
        border-left: 5px solid #f59e0b;
    }
    .bucket-monitor {
        border-left: 5px solid #3b82f6;
    }

    .tag {
        display: inline-block;
        background: var(--tag-bg);
        color: var(--tag-color);
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.75rem;
        margin: 2px;
        font-family: 'JetBrains Mono', monospace;
    }

    .tag-cyber { background: var(--tag-cyber-bg); color: var(--tag-cyber-color); }
    .tag-transform { background: var(--tag-transform-bg); color: var(--tag-transform-color); }
    .tag-hot { background: var(--tag-cyber-bg); color: var(--tag-cyber-color); font-weight: 600; }
    .tag-warm { background: var(--tag-warm-bg); color: var(--tag-warm-color); font-weight: 600; }

    .score-big {
        font-size: 2rem;
        font-weight: 700;
        font-family: 'JetBrains Mono', monospace;
    }

    .tool-trace {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.78rem;
        background: var(--trace-bg);
        border: 1px solid var(--trace-border);
        border-radius: 8px;
        padding: 12px 16px;
        margin: 4px 0;
        color: var(--text-primary);
    }

    .step-log {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.8rem;
        padding: 6px 12px;
        margin: 2px 0;
        border-radius: 6px;
        color: var(--text-primary);
    }
    .step-reasoning { background: var(--step-reasoning-bg); border-left: 3px solid #22c55e; }
    .step-tool { background: var(--step-tool-bg); border-left: 3px solid #3b82f6; }
    .step-result { background: var(--step-result-bg); border-left: 3px solid #94a3b8; }
    .step-done { background: var(--step-done-bg); border-left: 3px solid #eab308; }
</style>
""", unsafe_allow_html=True)


def load_prerun_entries() -> list[WatchlistEntry]:
    """Load pre-computed watchlist entries."""
    if not DEMO_OUTPUT.exists():
        return []
    data = json.loads(DEMO_OUTPUT.read_text())
    return [WatchlistEntry(**d) for d in data]


def trigger_label(trigger_type: TriggerType) -> str:
    return trigger_type.value.replace("_", " ").upper()


def source_line(entry: WatchlistEntry) -> str:
    section = f" · {entry.filing_section}" if entry.filing_section else ""
    return f"Source: {entry.filing_type}{section} · SEC EDGAR"


def render_entry_card(entry: WatchlistEntry, show_trace: bool = True):
    """Render a single watchlist entry as a card."""
    review_lane = entry.review_lane or entry.primary_solution or entry.workflow_queue or entry.territory

    bucket_class = {
        RankBucket.HOT: "bucket-hot",
        RankBucket.WARM: "bucket-warm",
        RankBucket.MONITOR: "bucket-monitor",
    }.get(entry.rank_bucket, "")

    bucket_label = {
        RankBucket.HOT: "HOT",
        RankBucket.WARM: "WARM",
        RankBucket.MONITOR: "MONITOR",
    }.get(entry.rank_bucket, "SKIP")

    trigger_class = "tag-cyber" if entry.trigger_type in (
        TriggerType.CYBER_INCIDENT,
        TriggerType.DATA_PRIVACY_SECURITY_RISK,
    ) else "tag-transform"

    st.markdown(f'<div class="watchlist-card {bucket_class}">', unsafe_allow_html=True)

    col1, col2, col3 = st.columns([3, 1, 1])

    with col1:
        st.markdown(f"### {entry.account_name} ({entry.ticker})")
        st.markdown(
            f'<span class="tag {trigger_class}">{trigger_label(entry.trigger_type)}</span> '
            f'<span class="tag">{entry.filing_type}</span> '
            f'<span class="tag">{entry.filing_date}</span> '
            f'<span class="tag">{entry.urgency_tier.value.replace("_", " ").upper()}</span>',
            unsafe_allow_html=True,
        )
        if entry.industry_group:
            st.markdown(f"Industry: {entry.industry_group}")

    with col2:
        st.markdown(f'<div class="score-big">{entry.final_score:.0%}</div>', unsafe_allow_html=True)
        st.caption(bucket_label)

    with col3:
        st.markdown(f"**Review Lane:** {review_lane}")

    # Source + Why Now
    if entry.source_url:
        st.markdown(f"{source_line(entry)} · [Open filing]({entry.source_url})")
    else:
        st.caption(source_line(entry))

    if entry.why_now:
        st.markdown("**Why Now**")
        st.info(entry.why_now)

    # Route + Action
    col_a, col_b = st.columns(2)
    with col_a:
        if entry.scenario_label:
            st.markdown(f"**Scenario:** {entry.scenario_label}")
        if entry.primary_user:
            st.markdown(f"**Primary User:** {entry.primary_user}")
        if entry.deliverable_type:
            st.markdown(f"**Deliverable:** {entry.deliverable_type}")
    with col_b:
        if entry.recommended_action:
            st.markdown(f"**Recommended Review Action:** {entry.recommended_action}")

    # Expandable sections
    with st.expander("Evidence Quotes"):
        for q in entry.evidence_quotes:
            st.markdown(f"> {q}")

    with st.expander("Source Details"):
        st.write({
            "source_type": entry.source_type,
            "verification_status": entry.verification_status,
            "corpus_segment": entry.corpus_segment,
            "accession_number": entry.accession_number,
            "filing_section": entry.filing_section,
        })

    if show_trace and entry.tool_trace:
        with st.expander("Audit Trace"):
            for t in entry.tool_trace:
                t_dict = t if isinstance(t, dict) else t.model_dump() if hasattr(t, 'model_dump') else t
                tool_name = t_dict.get("tool_name", t_dict.get("tool_name", ""))
                reason = t_dict.get("reason", "")
                result = t_dict.get("result_summary", "")[:200]
                st.markdown(
                    f'<div class="tool-trace">'
                    f'<strong>{tool_name}</strong> — {reason}<br>'
                    f'<span style="opacity:0.7">{result}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    with st.expander("Reasoning Summary"):
        st.write(entry.reasoning_summary)
        if entry.confidence_note:
            st.caption(f"Review status: {entry.confidence_note}")
        if entry.rationale_tags:
            tags_html = " ".join(f'<span class="tag">{t}</span>' for t in entry.rationale_tags)
            st.markdown(tags_html, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


# ── SIDEBAR ──────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## SEC Signal Agent")
    st.caption("Regulated Workflow Review Prototype")
    st.divider()

    mode = st.radio(
        "Mode",
        ["Pre-run Demo", "Live Run"],
        help="Pre-run loads saved results. Live Run processes a filing end-to-end.",
    )

    st.divider()
    st.markdown("### Filters")
    corpus_filter = st.selectbox(
        "Corpus",
        ["Healthcare EDGAR", "Other Industries EDGAR", "All"],
        index=0,
    )

    st.divider()
    st.markdown("### Architecture")
    st.markdown("""
    1. **Filing ingestion** → clean text
    2. **Trigger extraction** → LLM call #1
    3. **Agent loop** → tool-calling reasoning
    4. **Deterministic scoring** → Python
    5. **Evidence packet emission** → ranked card
    """)

    st.divider()
    st.caption("Python controller · Claude API · Streamlit")
    st.caption("Deterministic scoring · Visible audit trace")


# ── MAIN CONTENT ─────────────────────────────────────────────
st.markdown("# SEC Filing Signal Agent")
st.markdown("*An agent that reads peer SEC filings, scores their diligence and commercial impact on a digital health company, and emits source-grounded review packets for Trust, Compliance, and Partnerships teams.*")
st.divider()

if mode == "Pre-run Demo":
    entries = load_prerun_entries()

    if not entries:
        st.warning(
            "No pre-run results found. Run `python demo_runner.py --all` first, "
            "or switch to Live Run mode."
        )
        st.stop()

    def passes_filters(entry: WatchlistEntry) -> bool:
        if corpus_filter == "Healthcare EDGAR" and entry.corpus_segment != "healthcare_edgar_core":
            return False
        if corpus_filter == "Other Industries EDGAR" and entry.corpus_segment != "cross_industry_edgar_examples":
            return False
        return True

    entries = [e for e in entries if passes_filters(e)]
    hot_count = sum(1 for e in entries if e.rank_bucket == RankBucket.HOT)
    warm_count = sum(1 for e in entries if e.rank_bucket == RankBucket.WARM)

    trigger_counts: dict[str, int] = {}
    for e in entries:
        trigger_counts[e.trigger_type.value] = trigger_counts.get(e.trigger_type.value, 0) + 1

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            f'<div class="metric-card"><h2>{len(entries)}</h2><p>Signals Detected</p></div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f'<div class="metric-card"><h2 style="color:#ef4444">{hot_count}</h2><p>Hot Signals</p></div>',
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f'<div class="metric-card"><h2 style="color:#f59e0b">{warm_count}</h2><p>Warm Signals</p></div>',
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            f'<div class="metric-card"><h2>{len(trigger_counts)}</h2><p>Trigger Types</p></div>',
            unsafe_allow_html=True,
        )

    with st.expander("Priority Bucket Definitions", expanded=False):
        st.markdown(
            """
            | Bucket | Meaning | Action |
            | --- | --- | --- |
            | Hot | High-confidence, high-urgency item | Produce the lane-specific packet or brief this week |
            | Warm | Relevant item with useful evidence | Review in weekly planning or corroborate with account context |
            | Monitor | Weak, early, or lower-priority item | Track but do not produce a deliverable yet |
            | Skip | Not actionable for the active workflow | Exclude from the default review queue |
            """
        )

    st.divider()
    if not entries:
        st.warning("No entries match the current filters.")
        st.stop()

    lane_options = ["Trust & Diligence", "Commercial Signal"]
    selected_lane = st.selectbox(
        "Filter by review lane",
        ["All Lanes"] + lane_options,
    )

    # Render cards
    for entry in entries:
        entry_lane = entry.review_lane or entry.primary_solution or entry.workflow_queue or entry.territory
        if selected_lane != "All Lanes" and entry_lane != selected_lane:
            continue
        render_entry_card(entry)

else:
    # ── LIVE RUN MODE ────────────────────────────────────────
    st.markdown("### Run the agent on a filing")

    manifest = load_manifest()
    ticker_options = [f"{m.ticker} — {m.company_name} ({m.filing_type})" for m in manifest]

    selected = st.selectbox("Select a filing", ticker_options)

    if st.button("Run Agent", type="primary"):
        idx = ticker_options.index(selected)
        meta = manifest[idx]

        try:
            filing_text = load_filing_text(meta)
        except FileNotFoundError:
            st.error(f"Filing text not found for {meta.ticker}")
            st.stop()

        # Step log container
        step_container = st.container()
        result_container = st.container()

        steps_placeholder = step_container.empty()
        steps_log: list[str] = []

        def on_step(step_type: str, detail: str):
            icon = {
                "agent_start": "🚀", "iteration": "🔄", "reasoning": "🧠",
                "tool_call": "🔧", "tool_result": "📋", "agent_done": "✅",
                "fallback": "⚠️", "error": "❌",
            }.get(step_type, "📌")

            css_class = {
                "reasoning": "step-reasoning",
                "tool_call": "step-tool",
                "tool_result": "step-result",
                "agent_done": "step-done",
            }.get(step_type, "step-result")

            steps_log.append(
                f'<div class="step-log {css_class}">'
                f'{icon} <strong>{step_type}</strong>: {detail[:300]}'
                f'</div>'
            )
            steps_placeholder.markdown("\n".join(steps_log), unsafe_allow_html=True)

        # Run extraction
        with st.spinner("Extracting trigger from filing..."):
            trigger = extract_trigger(
                company_name=meta.company_name,
                ticker=meta.ticker,
                filing_type=meta.filing_type,
                filing_date=meta.filing_date,
                filing_text=filing_text,
                primary_trigger_hint=meta.primary_trigger_hint,
            )

        on_step("extraction", f"Trigger: {trigger.trigger_type.value} | Confidence: {trigger.confidence}")
        on_step("extraction", f"Summary: {trigger.short_summary}")

        if not trigger.trigger_detected:
            st.warning("No actionable trigger detected in this filing.")
            st.stop()

        # Run agent
        with st.spinner("Running agent loop..."):
            filing_meta = {
                "company_name": meta.company_name,
                "ticker": meta.ticker,
                "filing_type": meta.filing_type,
                "filing_date": meta.filing_date,
                "source_type": meta.source_type,
                "source_note": meta.source_note,
                "source_url": meta.source_url,
                "accession_number": meta.accession_number,
                "filing_section": meta.filing_section,
                "industry_group": meta.industry_group,
                "corpus_segment": meta.corpus_segment,
                "verification_status": meta.verification_status,
            }
            entry = run_agent(
                trigger=trigger,
                filing_meta=filing_meta,
                filing_text=filing_text,
                on_step=on_step,
            )

        st.divider()
        with result_container:
            st.markdown("### Evidence Packet")
            render_entry_card(entry)
