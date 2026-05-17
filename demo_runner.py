"""CLI demo runner. Processes all demo filings and saves pre-run watchlist."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from schemas import WatchlistEntry
from filing_loader import load_manifest, load_filing_text
from trigger_extractor import extract_trigger
from agent import run_agent

OUTPUT_DIR = Path(__file__).parent / "demo_outputs"


def run_single(ticker: str | None = None, verbose: bool = True):
    """Run the processing path on a single filing by ticker, or first in manifest."""
    manifest = load_manifest()

    if ticker:
        matches = [m for m in manifest if m.ticker.upper() == ticker.upper()]
        if not matches:
            print(f"No filing found for ticker: {ticker}")
            return None
        meta = matches[0]
    else:
        meta = manifest[0]

    filing_text = load_filing_text(meta)

    def on_step(step_type, detail):
        if verbose:
            prefix = {
                "agent_start": "🚀",
                "iteration": "🔄",
                "reasoning": "🧠",
                "tool_call": "🔧",
                "tool_result": "📋",
                "agent_done": "✅",
                "fallback": "⚠️",
                "error": "❌",
            }.get(step_type, "  ")
            print(f"  {prefix} [{step_type}] {detail[:300]}")

    # Step 1: Trigger extraction
    if verbose:
        print(f"\n{'='*60}")
        print(f"Processing: {meta.company_name} ({meta.ticker})")
        print(f"Filing: {meta.filing_type} | {meta.filing_date}")
        print(f"{'='*60}")
        print("\n📄 Step 1: Extracting trigger from filing...")

    trigger = extract_trigger(
        company_name=meta.company_name,
        ticker=meta.ticker,
        filing_type=meta.filing_type,
        filing_date=meta.filing_date,
        filing_text=filing_text,
        primary_trigger_hint=meta.primary_trigger_hint,
    )

    if verbose:
        print(f"   Trigger: {trigger.trigger_type.value} | Confidence: {trigger.confidence}")
        print(f"   Summary: {trigger.short_summary}")
        for q in trigger.evidence_quotes[:3]:
            print(f"   Evidence: \"{q[:120]}...\"")

    if trigger.extraction_error:
        if verbose:
            print(f"   Trigger extraction failed. Skipping agent loop. Error: {trigger.extraction_error}")
        return None

    if not trigger.trigger_detected:
        if verbose:
            print("   No trigger detected. Skipping agent loop.")
        return None

    # Step 2: Agent loop
    if verbose:
        print(f"\n🤖 Step 2: Running agent loop...")

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

    if verbose:
        print(f"\n{'='*60}")
        print(f"RESULT: {entry.account_name}")
        print(f"  Score: {entry.final_score} | Bucket: {entry.rank_bucket.value}")
        print(f"  Workflow route: {entry.primary_solution}")
        print(f"  Why Now: {entry.why_now[:200]}")
        print(f"  Action: {entry.recommended_action}")
        print(f"  Tools used: {len(entry.tool_trace)}")
        print(f"{'='*60}\n")

    return entry


def run_all(verbose: bool = True):
    """Process all demo filings and save watchlist."""
    manifest = load_manifest()
    entries: list[WatchlistEntry] = []
    processed = 0
    signals = 0
    no_signal = 0
    extraction_failures = 0

    for meta in manifest:
        try:
            filing_text = load_filing_text(meta)
        except FileNotFoundError:
            if verbose:
                print(f"⚠️  Skipping {meta.ticker}: filing text not found")
            continue

        if verbose:
            print(f"\n{'='*60}")
            print(f"Processing: {meta.company_name} ({meta.ticker})")
            print(f"{'='*60}")

        processed += 1

        # Extract trigger
        trigger = extract_trigger(
            company_name=meta.company_name,
            ticker=meta.ticker,
            filing_type=meta.filing_type,
            filing_date=meta.filing_date,
            filing_text=filing_text,
            primary_trigger_hint=meta.primary_trigger_hint,
        )

        if trigger.extraction_error:
            extraction_failures += 1
            if verbose:
                print(f"   Trigger extraction failed for {meta.ticker}. Skipping. Error: {trigger.extraction_error}")
            continue

        if not trigger.trigger_detected:
            no_signal += 1
            if verbose:
                print(f"   No trigger detected for {meta.ticker}. Skipping.")
            continue

        signals += 1

        if verbose:
            print(f"   Trigger: {trigger.trigger_type.value} | Confidence: {trigger.confidence}")

        # Run agent
        def on_step(step_type, detail):
            if verbose:
                prefix = {
                    "agent_start": "🚀", "iteration": "🔄", "reasoning": "🧠",
                    "tool_call": "🔧", "tool_result": "📋", "agent_done": "✅",
                    "fallback": "⚠️", "error": "❌",
                }.get(step_type, "  ")
                print(f"  {prefix} [{step_type}] {detail[:200]}")

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
        entries.append(entry)

    # Sort by score descending
    entries.sort(key=lambda e: e.final_score, reverse=True)

    # Save
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "prerun_watchlist.json"

    output_data = [json.loads(e.model_dump_json()) for e in entries]
    output_path.write_text(json.dumps(output_data, indent=2, ensure_ascii=False))

    if verbose:
        print(f"\n{'='*60}")
        print("Run summary")
        print(f"  Processed filings: {processed}")
        print(f"  Signals processed: {signals}")
        print(f"  Clean no-signal filings: {no_signal}")
        print(f"  Extraction failures: {extraction_failures}")
        print(f"{'='*60}")
        print(f"\n{'='*60}")
        print(f"Saved {len(entries)} watchlist entries to {output_path}")
        print(f"{'='*60}")
        for i, e in enumerate(entries, 1):
            print(f"  {i}. {e.account_name} ({e.ticker}) — {e.rank_bucket.value} — {e.final_score}")

    return entries


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SEC Signal Agent - Demo Runner")
    parser.add_argument("--ticker", help="Run for a single ticker")
    parser.add_argument("--all", action="store_true", help="Run all demo filings")
    parser.add_argument("--quiet", action="store_true", help="Suppress verbose output")
    args = parser.parse_args()

    if args.all:
        run_all(verbose=not args.quiet)
    elif args.ticker:
        run_single(ticker=args.ticker, verbose=not args.quiet)
    else:
        print("Usage: python demo_runner.py --ticker CLX")
        print("       python demo_runner.py --all")
