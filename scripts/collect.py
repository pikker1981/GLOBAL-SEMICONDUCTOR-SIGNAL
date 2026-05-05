#!/usr/bin/env python3
"""
Global Semiconductor Signal collector.

역할:
- GDELT에서 글로벌 반도체 뉴스 메타데이터 수집
- arXiv에서 반도체 관련 논문 메타데이터 수집
- docs/data/latest.json 파일 생성

중요:
- 뉴스 기사 전문은 긁어오지 않음
- 뉴스는 제목, 스니펫, 출처, 날짜, 원문 링크만 저장
- 논문은 제목, 저자, 초록, arXiv 링크, PDF 링크만 저장
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo

import requests


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "data" / "latest.json"

MAX_NEWS = 80
MAX_PAPERS = 40
REQUEST_TIMEOUT = 25

USER_AGENT = (
    "semiconductor-global-signal/1.0 "
    "(original-link-only collector; contact: repository owner)"
)

GDELT_ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"
ARXIV_ENDPOINT = "https://export.arxiv.org/api/query"

NEWS_QUERIES = [
    'semiconductor OR "chip industry" OR foundry OR HBM OR DRAM OR NAND OR EUV OR ASML OR TSMC OR "SK hynix" OR "Samsung Electronics" OR Intel OR Micron OR "advanced packaging"',
    '半導体 OR 半导体 OR 반도체 OR semiconducteur OR Halbleiter'
]

ARXIV_QUERY = (
    'all:semiconductor OR all:transistor OR all:CMOS OR all:nanofabrication '
    'OR all:"semiconductor device" OR all:"advanced packaging" OR all:"AI accelerator"'
)

COUNTRY_REGION = {
    # Asia
    "China": "Asia",
    "Taiwan": "Asia",
    "Japan": "Asia",
    "South Korea": "Asia",
    "Korea, South": "Asia",
    "India": "Asia",
    "Singapore": "Asia",
    "Malaysia": "Asia",
    "Vietnam": "Asia",
    "Thailand": "Asia",
    "Indonesia": "Asia",
    "Philippines": "Asia",
    "Israel": "Asia",

    # Europe
    "Netherlands": "Europe",
    "Germany": "Europe",
    "France": "Europe",
    "United Kingdom": "Europe",
    "Ireland": "Europe",
    "Italy": "Europe",
    "Spain": "Europe",
    "Sweden": "Europe",
    "Finland": "Europe",
    "Norway": "Europe",
    "Austria": "Europe",
    "Belgium": "Europe",
    "Switzerland": "Europe",
    "Poland": "Europe",
    "Czech Republic": "Europe",

    # Americas
    "United States": "Americas",
    "United States of America": "Americas",
    "Canada": "Americas",
    "Mexico": "Americas",
    "Brazil": "Americas",
    "Argentina": "Americas",
    "Chile": "Americas"
}


@dataclass
class FeedItem:
    id: str
    type: str
    region: str
    country: str
    source: str
    published_at: str
    title: str
    url: str
    snippet: str = ""
    abstract: str = ""
    authors: list[str] | None = None
    pdf_url: str = ""
    content_mode: str = "snippet_only"


def now_iso_kst() -> str:
    return datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")


def stable_id(*parts: str) -> str:
    raw = "|".join(part for part in parts if part)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def clean_text(value: str | None) -> str:
    if not value:
        return ""

    value = html.unescape(value)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def parse_gdelt_date(value: str | None) -> str:
    if not value:
        return ""

    for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%d%H%M%S"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            pass

    return value


def infer_region(country: str | None) -> str:
    if not country:
        return "Global"

    return COUNTRY_REGION.get(country, "Global")


def http_get_json(url: str, params: dict) -> dict:
    response = requests.get(
        url,
        params=params,
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": USER_AGENT}
    )
    response.raise_for_status()

    return response.json()


def get_gdelt_country(article: dict) -> str:
    return clean_text(
        article.get("sourceCountry")
        or article.get("sourcecountry")
        or article.get("source_country")
        or ""
    )


def get_gdelt_source(article: dict) -> str:
    return clean_text(
        article.get("sourceCommonName")
        or article.get("sourcecommonname")
        or article.get("domain")
        or "Unknown"
    )


def get_gdelt_snippet(article: dict, title: str) -> str:
    snippet = clean_text(
        article.get("snippet")
        or article.get("description")
        or article.get("summary")
        or ""
    )

    return snippet or title


def fetch_gdelt_news() -> list[FeedItem]:
    items: list[FeedItem] = []

    for query in NEWS_QUERIES:
        params = {
            "query": query,
            "mode": "ArtList",
            "format": "json",
            "maxrecords": 75,
            "sort": "HybridRel",
            "timespan": "48h"
        }

        try:
            data = http_get_json(GDELT_ENDPOINT, params)
        except Exception as exc:
            print(f"[WARN] GDELT query failed: {exc}")
            continue

        for article in data.get("articles", []):
            title = clean_text(article.get("title"))
            url = article.get("url") or ""

            if not title or not url:
                continue

            country = get_gdelt_country(article)
            source = get_gdelt_source(article)
            published_at = parse_gdelt_date(article.get("seendate"))
            snippet = get_gdelt_snippet(article, title)

            items.append(
                FeedItem(
                    id=stable_id("news", url, title),
                    type="news",
                    region=infer_region(country),
                    country=country,
                    source=source,
                    published_at=published_at,
                    title=title,
                    snippet=snippet,
                    url=url,
                    content_mode="snippet_only"
                )
            )

        time.sleep(1)

    return dedupe(items)[:MAX_NEWS]


def fetch_arxiv_papers() -> list[FeedItem]:
    params = {
        "search_query": ARXIV_QUERY,
        "start": 0,
        "max_results": MAX_PAPERS,
        "sortBy": "submittedDate",
        "sortOrder": "descending"
    }

    try:
        response = requests.get(
            ARXIV_ENDPOINT,
            params=params,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": USER_AGENT}
        )
        response.raise_for_status()
    except Exception as exc:
        print(f"[WARN] arXiv query failed: {exc}")
        return []

    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "arxiv": "http://arxiv.org/schemas/atom"
    }

    root = ET.fromstring(response.text)
    items: list[FeedItem] = []

    for entry in root.findall("atom:entry", ns):
        title = clean_text(entry.findtext("atom:title", default="", namespaces=ns))
        abstract = clean_text(entry.findtext("atom:summary", default="", namespaces=ns))
        published_at = clean_text(entry.findtext("atom:published", default="", namespaces=ns))
        url = clean_text(entry.findtext("atom:id", default="", namespaces=ns))

        authors = []

        for author in entry.findall("atom:author", ns):
            name = clean_text(author.findtext("atom:name", default="", namespaces=ns))

            if name:
                authors.append(name)

        pdf_url = ""

        for link in entry.findall("atom:link", ns):
            if link.attrib.get("title") == "pdf" or link.attrib.get("type") == "application/pdf":
                pdf_url = link.attrib.get("href", "")
                break

        if not title or not url:
            continue

        items.append(
            FeedItem(
                id=stable_id("paper", url, title),
                type="paper",
                region="Global",
                country="",
                source="arXiv",
                published_at=published_at,
                title=title,
                abstract=abstract,
                authors=authors,
                url=url,
                pdf_url=pdf_url,
                content_mode="open_abstract"
            )
        )

    return items[:MAX_PAPERS]


def dedupe(items: Iterable[FeedItem]) -> list[FeedItem]:
    seen: set[str] = set()
    deduped: list[FeedItem] = []

    for item in items:
        key = item.url or item.id

        if key in seen:
            continue

        seen.add(key)
        deduped.append(item)

    return deduped


def sort_items(items: list[FeedItem]) -> list[FeedItem]:
    def key(item: FeedItem) -> str:
        return item.published_at or ""

    return sorted(items, key=key, reverse=True)


def main() -> None:
    news = fetch_gdelt_news()
    papers = fetch_arxiv_papers()
    items = sort_items(dedupe([*news, *papers]))

    payload = {
        "meta": {
            "generated_at": now_iso_kst(),
            "news_count": len(news),
            "paper_count": len(papers),
            "total_count": len(items),
            "policy": "Original links only. No full news republication.",
            "sources": [
                "GDELT",
                "arXiv"
            ]
        },
        "items": [asdict(item) for item in items]
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"Wrote {OUTPUT}")
    print(f"Items: {len(items)} / News: {len(news)} / Papers: {len(papers)}")


if __name__ == "__main__":
    main()
