"""Load local filing/excerpt text and provenance metadata."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List, Optional

from schemas import FilingMeta

DATA_DIR = Path(__file__).parent / "data"
MANIFEST_PATH = DATA_DIR / "filings_manifest.csv"


def load_manifest(manifest_path: Path | None = None) -> List[FilingMeta]:
    """Read the filings manifest CSV into typed objects."""
    path = manifest_path or MANIFEST_PATH
    rows: List[FilingMeta] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            form_type = row.get("form_type", row.get("filing_type", "")).strip()
            local_text_path = row.get("local_text_path", row.get("text_path", "")).strip()
            source_url = row.get("source_url", row.get("filing_url", "")).strip()
            rows.append(
                FilingMeta(
                    company_name=row.get("company_name", "").strip(),
                    ticker=row.get("ticker", "").strip(),
                    filing_type=form_type,
                    form_type=form_type,
                    filing_date=row.get("filing_date", "").strip(),
                    filing_url=source_url,
                    source_url=source_url,
                    cik=row.get("cik", "").strip(),
                    accession_number=row.get("accession_number", row.get("source_reference", "")).strip(),
                    source_reference=row.get("source_reference", row.get("accession_number", "")).strip(),
                    filing_section=row.get("filing_section", "").strip(),
                    trigger_family=row.get("trigger_family", row.get("primary_trigger_hint", "")).strip(),
                    primary_trigger_hint=row.get("primary_trigger_hint", row.get("trigger_family", "")).strip(),
                    secondary_trigger_hint=row.get("secondary_trigger_hint", "").strip(),
                    source_type=row.get("source_type", "").strip(),
                    source_note=row.get("source_note", "").strip(),
                    notes=row.get("notes", "").strip(),
                    text_path=local_text_path,
                    local_text_path=local_text_path,
                    industry_group=row.get("industry_group", "").strip(),
                    industry_subsector=row.get("industry_subsector", "").strip(),
                    corpus_segment=row.get("corpus_segment", "").strip(),
                    verification_status=row.get("verification_status", "").strip(),
                )
            )
    return rows


def load_filing_text(meta: FilingMeta) -> str:
    """Load local filing or pre-parsed excerpt text."""
    base = Path(__file__).parent
    text_path = base / (meta.local_text_path or meta.text_path)
    if not text_path.exists():
        raise FileNotFoundError(f"Filing text not found: {text_path}")
    return text_path.read_text(encoding="utf-8")


def get_filing_by_ticker(ticker: str, manifest: List[FilingMeta] | None = None) -> Optional[FilingMeta]:
    """Find a filing by ticker (first match)."""
    if manifest is None:
        manifest = load_manifest()
    ticker_upper = ticker.upper().strip()
    for m in manifest:
        if m.ticker.upper() == ticker_upper:
            return m
    return None


def get_all_filings() -> Dict[str, tuple[FilingMeta, str]]:
    """Load all demo filings. Returns {ticker: (meta, text)}."""
    manifest = load_manifest()
    result = {}
    for m in manifest:
        try:
            text = load_filing_text(m)
            result[m.ticker] = (m, text)
        except FileNotFoundError:
            continue
    return result
