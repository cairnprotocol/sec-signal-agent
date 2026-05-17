"""Lightweight news corroboration via Google News RSS. No credential required."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import List, Optional
from urllib.parse import quote_plus

import requests

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
REQUEST_TIMEOUT = 8

# Keywords that suggest a filing-corroborating signal
CYBER_KEYWORDS = [
    "ransomware", "cyber", "breach", "hack", "data breach",
    "cybersecurity incident", "cyberattack", "unauthorized access",
    "systems outage", "data leak",
]
TRANSFORM_KEYWORDS = [
    "ERP", "SAP", "cloud migration", "digital transformation",
    "platform migration", "technology modernization",
]


@dataclass
class NewsHit:
    title: str = ""
    link: str = ""
    pub_date: str = ""
    source: str = ""


@dataclass
class NewsCorroboration:
    company: str = ""
    query_used: str = ""
    hits: List[NewsHit] = field(default_factory=list)
    corroborated: bool = False
    summary: str = ""


def search_news(company_name: str, trigger_type: str = "cyber_incident", max_results: int = 5) -> NewsCorroboration:
    """Search Google News RSS for corroborating headlines.

    Args:
        company_name: Company to search for
        trigger_type: 'cyber_incident' or 'transformation'
        max_results: Max headlines to return

    Returns:
        NewsCorroboration with matching headlines
    """

    # Build query based on trigger type
    if trigger_type == "cyber_incident":
        keywords = "cybersecurity OR ransomware OR breach OR cyberattack"
    else:
        keywords = "ERP OR cloud migration OR digital transformation"

    query = f'"{company_name}" {keywords}'
    url = GOOGLE_NEWS_RSS.format(query=quote_plus(query))

    result = NewsCorroboration(company=company_name, query_used=query)

    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers={
            "User-Agent": "Mozilla/5.0 (compatible; DemoAgent/1.0)"
        })
        resp.raise_for_status()

        # Parse RSS XML
        root = ET.fromstring(resp.content)
        items = root.findall(".//item")

        for item in items[:max_results]:
            title = item.findtext("title", "")
            link = item.findtext("link", "")
            pub_date = item.findtext("pubDate", "")
            source = item.findtext("source", "")

            result.hits.append(NewsHit(
                title=title,
                link=link,
                pub_date=pub_date,
                source=source,
            ))

        result.corroborated = len(result.hits) > 0
        if result.hits:
            result.summary = f"Found {len(result.hits)} news articles corroborating the signal. Latest: \"{result.hits[0].title}\" ({result.hits[0].source})"
        else:
            result.summary = "No corroborating news articles found."

    except Exception as e:
        result.summary = f"News search unavailable: {str(e)[:100]}"

    return result


def search_news_for_ticker(ticker: str, company_name: str, trigger_type: str = "cyber_incident") -> NewsCorroboration:
    """Convenience wrapper that tries company name first, then ticker."""
    result = search_news(company_name, trigger_type)

    # If no hits with company name, try ticker
    if not result.corroborated and ticker:
        result = search_news(ticker, trigger_type)
        result.company = company_name

    return result


# ── Tool definition for the agent ──────────────────────────
NEWS_TOOL_DEFINITION = {
    "name": "check_news_corroboration",
    "description": "Search recent news for corroborating coverage of the filing trigger. Returns matching headlines from Google News. Use this to validate that the filing signal has real-world coverage.",
    "input_schema": {
        "type": "object",
        "properties": {
            "company_name": {
                "type": "string",
                "description": "Company name to search for"
            },
            "trigger_type": {
                "type": "string",
                "enum": ["cyber_incident", "transformation"],
                "description": "Type of trigger to corroborate"
            }
        },
        "required": ["company_name", "trigger_type"]
    }
}


if __name__ == "__main__":
    # Quick test
    result = search_news("DaVita", "cyber_incident")
    print(f"Company: {result.company}")
    print(f"Corroborated: {result.corroborated}")
    print(f"Summary: {result.summary}")
    for h in result.hits:
        print(f"  - {h.title} ({h.source}, {h.pub_date})")
