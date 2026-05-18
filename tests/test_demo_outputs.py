import json
from pathlib import Path

from filing_loader import load_filing_text, load_manifest
from schemas import WatchlistEntry


DEMO_OUTPUT_PATH = Path("demo_outputs/prerun_watchlist.json")
EXPECTED_TRACE_STEPS = [
    "source_loaded",
    "trigger_extracted",
    "get_account_context",
    "check_prior_filing",
    "get_scoring",
    "get_product_fit",
    "emit_watchlist_entry",
]


def load_demo_output():
    return json.loads(DEMO_OUTPUT_PATH.read_text(encoding="utf-8"))


def test_prerun_demo_json_loads_and_matches_schema():
    rows = load_demo_output()
    entries = [WatchlistEntry(**row) for row in rows]

    assert len(entries) == 16
    assert all(entry.source_type == "public_edgar_preparsed_excerpt" for entry in entries)
    assert all(entry.verification_status == "verified_public_edgar_excerpt" for entry in entries)
    assert all(entry.review_lane in {"Trust & Diligence", "Commercial Signal"} for entry in entries)
    assert all(entry.human_review_required for entry in entries)


def test_prerun_demo_evidence_quotes_match_local_source_text():
    manifest = {meta.ticker: meta for meta in load_manifest()}
    misses = []

    for row in load_demo_output():
        source_text = load_filing_text(manifest[row["ticker"]])
        for quote in row["evidence_quotes"]:
            if quote not in source_text:
                misses.append((row["ticker"], quote))

    assert misses == []


def test_prerun_demo_audit_trace_is_deterministic_and_item_specific():
    rows = load_demo_output()
    trace_sequences = []

    for row in rows:
        entry = WatchlistEntry(**row)
        assert [step.tool_name for step in entry.tool_trace] == EXPECTED_TRACE_STEPS
        assert entry.tool_trace[0].inputs["ticker"] == entry.ticker
        assert entry.tool_trace[-1].inputs["review_lane"] == entry.review_lane
        assert "fallback" not in " ".join(step.result_summary.lower() for step in entry.tool_trace)
        trace_sequences.append(tuple(step.result_summary for step in entry.tool_trace))

    assert len(set(trace_sequences)) == len(rows)
