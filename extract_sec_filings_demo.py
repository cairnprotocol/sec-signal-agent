from __future__ import annotations

import csv
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

# Demo extractor for SEC filings.
# Goal: get clean-enough text for an agent prototype quickly.
# Not a production-grade parser.

USER_AGENT = "DemoPrototype/1.0 your_email@example.com"
REQUEST_TIMEOUT = 30
SLEEP_SECONDS = 0.5


@dataclass
class FilingRow:
    company_name: str
    ticker: str
    filing_type: str
    filing_date: str
    filing_url: str
    trigger_family: str = ""
    notes: str = ""


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def read_manifest(path: Path) -> List[FilingRow]:
    rows: List[FilingRow] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(
                FilingRow(
                    company_name=row.get("company_name", "").strip(),
                    ticker=row.get("ticker", "").strip(),
                    filing_type=row.get("filing_type", "").strip(),
                    filing_date=row.get("filing_date", "").strip(),
                    filing_url=row.get("filing_url", "").strip(),
                    trigger_family=row.get("trigger_family", "").strip(),
                    notes=row.get("notes", "").strip(),
                )
            )
    return rows


def fetch_html(url: str) -> str:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Encoding": "gzip, deflate",
        "Host": "www.sec.gov",
    }
    response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.text


def strip_html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    # Remove obvious noise.
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    # Tables can be useful in production, but for the demo they often add noise.
    for tag in soup.find_all(["table"]):
        tag.decompose()

    text = soup.get_text("\n")

    # Decode common whitespace artifacts.
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_sections(clean_text: str, filing_type: str) -> Dict[str, Optional[str]]:
    upper = clean_text.upper()

    patterns = {
        "item_1_05": r"ITEM\s+1\.05",
        "item_8_01": r"ITEM\s+8\.01",
        "item_1a": r"ITEM\s+1A\b|RISK\s+FACTORS",
        "mda": r"MANAGEMENT[’'`S\s]+DISCUSSION\s+AND\s+ANALYSIS",
        "business": r"ITEM\s+1\b|BUSINESS",
    }

    matches: Dict[str, Optional[int]] = {}
    for key, pattern in patterns.items():
        m = re.search(pattern, upper)
        matches[key] = m.start() if m else None

    ordered_hits = sorted(
        [(k, v) for k, v in matches.items() if v is not None],
        key=lambda x: x[1],
    )

    sections: Dict[str, Optional[str]] = {k: None for k in patterns.keys()}
    for idx, (key, start) in enumerate(ordered_hits):
        end = len(clean_text)
        if idx + 1 < len(ordered_hits):
            end = ordered_hits[idx + 1][1]
        snippet = clean_text[start:end].strip()
        # Keep snippets bounded so they are easy to feed to the model.
        sections[key] = snippet[:25000]

    # Filing-type friendly default payload.
    if filing_type.upper() == "8-K":
        preferred = sections.get("item_1_05") or sections.get("item_8_01") or clean_text[:30000]
    else:
        preferred = sections.get("mda") or sections.get("item_1a") or clean_text[:30000]

    sections["preferred_text"] = preferred
    return sections


def build_output_record(row: FilingRow, text_path: str, sections_path: str) -> Dict[str, str]:
    return {
        "company_name": row.company_name,
        "ticker": row.ticker,
        "filing_type": row.filing_type,
        "filing_date": row.filing_date,
        "filing_url": row.filing_url,
        "trigger_family": row.trigger_family,
        "notes": row.notes,
        "clean_text_path": text_path,
        "sections_json_path": sections_path,
    }


def process_manifest(manifest_path: Path, output_dir: Path) -> None:
    rows = read_manifest(manifest_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = output_dir / "raw_html"
    text_dir = output_dir / "clean_text"
    sections_dir = output_dir / "sections"
    raw_dir.mkdir(exist_ok=True)
    text_dir.mkdir(exist_ok=True)
    sections_dir.mkdir(exist_ok=True)

    summary_rows: List[Dict[str, str]] = []

    for idx, row in enumerate(rows, start=1):
        stem = f"{idx:02d}_{slugify(row.ticker or row.company_name)}_{slugify(row.filing_type)}_{row.filing_date}"
        print(f"Processing {idx}/{len(rows)}: {row.company_name} | {row.filing_type} | {row.filing_url}")

        html = fetch_html(row.filing_url)
        clean_text = strip_html_to_text(html)
        sections = extract_sections(clean_text, row.filing_type)

        raw_path = raw_dir / f"{stem}.html"
        text_path = text_dir / f"{stem}.txt"
        sections_path = sections_dir / f"{stem}.json"

        raw_path.write_text(html, encoding="utf-8")
        text_path.write_text(clean_text, encoding="utf-8")
        sections_path.write_text(json.dumps(sections, indent=2, ensure_ascii=False), encoding="utf-8")

        summary_rows.append(build_output_record(row, str(text_path), str(sections_path)))
        time.sleep(SLEEP_SECONDS)

    summary_path = output_dir / "extracted_manifest.csv"
    with summary_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"Done. Output written to: {output_dir}")
    print(f"Summary manifest: {summary_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Brute-force SEC filing extractor for demo prototypes.")
    parser.add_argument("--manifest", required=True, help="Path to CSV manifest with filing URLs.")
    parser.add_argument("--output-dir", default="demo_filings", help="Directory for extracted outputs.")
    args = parser.parse_args()

    process_manifest(Path(args.manifest), Path(args.output_dir))
