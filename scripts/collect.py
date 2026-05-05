#!/usr/bin/env python3
"""
Global Semiconductor Signal collector.

역할:
- GDELT에서 글로벌 반도체 뉴스 메타데이터 수집
- RSS에서 반도체 전문 매체/기업 뉴스룸 메타데이터 수집
- arXiv에서 반도체 관련 논문 메타데이터 수집
- docs/data/latest.json 파일 생성

중요:
- 뉴스 기사 전문은 긁어오지 않음
- 뉴스는 제목, 스니펫, 출처, 날짜, 원문 링크만 저장
- 논문은 제목, 저자, 초록, arXiv 링크, PDF 링크만 저장
"""

from __future__ import annotations

import calendar
import hashlib
import html
import json
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import feedparser
import requests


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "data" / "latest.json"

MAX_GDELT_NEWS = 80
MAX_RSS_NEWS = 120
MAX_PAPERS = 40

RSS_MAX_AGE_DAYS = 30
PAPER_MAX_AGE_DAYS = 180

REQUEST_TIMEOUT = 25

USER_AGENT = (
    "semiconductor-global-signal/1.3 "
    "(original-link-only collector; contact: repository owner)"
)

GDELT_ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"
ARXIV_ENDPOINT = "https://export.arxiv.org/api/query"

NEWS_QUERIES = [
    '(semiconductor OR "chip industry" OR foundry OR HBM OR DRAM OR NAND OR EUV)',
    '(TSMC OR ASML OR Intel OR Micron OR NVIDIA OR AMD)',
    '("Samsung Electronics" OR "SK hynix" OR "advanced packaging" OR "AI chip")',
    '(半導体 OR 半导体 OR 반도체 OR semiconducteur OR Halbleiter)'
]

ARXIV_QUERY = (
    'all:semiconductor OR all:transistor OR all:CMOS OR all:nanofabrication '
    'OR all:"semiconductor device" OR all:"advanced packaging" OR all:"AI accelerator"'
)

RSS_FEEDS = [
    {
        "name": "Samsung Global Newsroom",
        "url": "https://news.samsung.com/global/feed",
        "region": "Asia",
        "country": "South Korea",
        "source_group": "company"
    },
    {
        "name": "SK hynix Newsroom",
        "url": "https://news.skhynix.co.kr/feed/",
        "region": "Asia",
        "country": "South Korea",
        "source_group": "company"
    },
    {
        "name": "NVIDIA Press Room",
        "url": "https://nvidianews.nvidia.com/releases.xml",
        "region": "Americas",
        "country": "United States",
        "source_group": "company"
    },
    {
        "name": "NVIDIA Developer Blog",
        "url": "https://developer.nvidia.com/blog/feed",
        "region": "Americas",
        "country": "United States",
        "source_group": "company"
    },
    {
        "name": "AMD Press Releases",
        "url": "https://ir.amd.com/news-events/press-releases/rss",
        "region": "Americas",
        "country": "United States",
        "source_group": "company"
    },
    {
        "name": "Intel Newsroom",
        "url": "http://feeds.feedburner.com/IntelNewsroom?format=xml",
        "region": "Americas",
        "country": "United States",
        "source_group": "company"
    },
    {
        "name": "Semiconductor Engineering",
        "url": "https://semiengineering.com/feed/",
        "region": "Americas",
        "country": "United States",
        "source_group": "industry"
    },
    {
        "name": "Semiconductor Today",
        "url": "https://www.semiconductor-today.com/rss/news.xml",
        "region": "Europe",
        "country": "United Kingdom",
        "source_group": "industry"
    },
    {
        "name": "SemiWiki",
        "url": "https://semiwiki.com/feed/",
        "region": "Americas",
        "country": "United States",
        "source_group": "industry"
    },
    {
        "name": "EE Times Semiconductors",
        "url": "https://www.eetimes.com/tag/semiconductors/feed/",
        "region": "Americas",
        "country": "United States",
        "source_group": "industry"
    },
    {
        "name": "EE Times Asia",
        "url": "https://www.eetasia.com/feed/",
        "region": "Asia",
        "country": "",
        "source_group": "industry"
    },
    {
        "name": "The Register HPC",
        "url": "https://www.theregister.com/on_prem/hpc/headlines.atom",
        "region": "Europe",
        "country": "United Kingdom",
        "source_group": "industry"
    },
    {
        "name": "The Register AI ML",
        "url": "https://www.theregister.com/software/ai_ml/headlines.atom",
        "region": "Europe",
        "country": "United Kingdom",
        "source_group": "industry"
    }
    # 한국 반도체 / 산업 전문 매체
    {
        "name": "The Elec Semiconductor",
        "url": "https://www.thelec.kr/rss/S1N2.xml",
        "region": "Asia",
        "country": "South Korea",
        "source_group": "korean_industry"
    },
    {
        "name": "The Elec Materials Equipment",
        "url": "https://www.thelec.kr/rss/S1N3.xml",
        "region": "Asia",
        "country": "South Korea",
        "source_group": "korean_industry"
    },
    {
        "name": "ETNews Electronics",
        "url": "http://rss.etnews.com/06.xml",
        "region": "Asia",
        "country": "South Korea",
        "source_group": "korean_industry"
    },
    {
        "name": "ETNews Materials",
        "url": "http://rss.etnews.com/06064.xml",
        "region": "Asia",
        "country": "South Korea",
        "source_group": "korean_industry"
    },
    {
        "name": "ETNews Components",
        "url": "http://rss.etnews.com/06062.xml",
        "region": "Asia",
        "country": "South Korea",
        "source_group": "korean_industry"
    },
    {
        "name": "ETNews Equipment",
        "url": "http://rss.etnews.com/06061.xml",
        "region": "Asia",
        "country": "South Korea",
        "source_group": "korean_industry"
    },
    {
        "name": "KIPOST All Articles",
        "url": "https://www.kipost.net/rss/allArticle.xml",
        "region": "Asia",
        "country": "South Korea",
        "source_group": "korean_industry"
    },
]

SPECIALIST_RSS_SOURCES = {
    "Semiconductor Engineering",
    "Semiconductor Today",
    "SemiWiki",
    "EE Times Semiconductors",
    "EE Times Asia",

    # Korea
    "The Elec Semiconductor",
    "The Elec Materials Equipment",
    "ETNews Electronics",
    "ETNews Materials",
    "ETNews Components",
    "ETNews Equipment"
}

COMPANY_SIGNAL_SOURCES = {
    "Samsung Global Newsroom",
    "SK hynix Newsroom",
    "NVIDIA Press Room",
    "NVIDIA Developer Blog",
    "AMD Press Releases",
    "Intel Newsroom"
}

SEMICONDUCTOR_KEYWORDS = [
    "semiconductor",
    "semiconductors",
    "chip",
    "chips",
    "chiplet",
    "chiplets",
    "foundry",
    "fab",
    "wafer",
    "silicon",
    "transistor",
    "cmos",
    "logic",
    "memory",
    "hbm",
    "dram",
    "nand",
    "sram",
    "euv",
    "duv",
    "lithography",
    "asml",
    "tsmc",
    "samsung",
    "sk hynix",
    "hynix",
    "intel",
    "micron",
    "nvidia",
    "amd",
    "qualcomm",
    "broadcom",
    "arm",
    "eda",
    "synopsys",
    "cadence",
    "advanced packaging",
    "cowos",
    "interposer",
    "substrate",
    "gan",
    "sic",
    "silicon carbide",
    "gallium nitride",
    "ai chip",
    "gpu",
    "accelerator",
    "data center",
    "datacenter",
    "server",
    "processor",
    "cpu",
    "xpu",
    "epyc",
    "xeon",
    "cuda",
    "inference",
    "training",
    "반도체",
    "파운드리",
    "메모리",
    "디램",
    "낸드",
    "半導体",
    "半导体"
    "반도체",
    "파운드리",
    "메모리",
    "디램",
    "DRAM",
    "낸드",
    "NAND",
    "HBM",
    "EUV",
    "노광",
    "식각",
    "증착",
    "패키징",
    "첨단 패키징",
    "후공정",
    "전공정",
    "소부장",
    "소재",
    "부품",
    "장비",
    "웨이퍼",
    "팹리스",
    "팹",
    "시스템반도체",
    "차량용 반도체",
    "AI 반도체",
    "온디바이스 AI",
    "삼성전자",
    "SK하이닉스",
    "하이닉스",
    "한미반도체",
    "원익IPS",
    "유진테크",
    "테스",
    "솔브레인",
    "동진쎄미켐",
]

COUNTRY_REGION = {
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

    value = html.unescape(str(value))
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def limit_text(value: str, max_len: int = 420) -> str:
    value = clean_text(value)

    if len(value) <= max_len:
        return value

    return value[:max_len].rstrip() + "..."


def normalize_url(url: str) -> str:
    if not url:
        return ""

    try:
        parsed = urlsplit(clean_text(url))
        query_pairs = parse_qsl(parsed.query, keep_blank_values=True)

        filtered_pairs = [
            (key, value)
            for key, value in query_pairs
            if not key.lower().startswith("utm_")
            and key.lower() not in {"fbclid", "gclid", "mc_cid", "mc_eid"}
        ]

        normalized_query = urlencode(filtered_pairs, doseq=True)

        return urlunsplit(
            (
                parsed.scheme,
                parsed.netloc.lower(),
                parsed.path.rstrip("/"),
                normalized_query,
                ""
            )
        )
    except Exception:
        return clean_text(url)


def parse_gdelt_date(value: str | None) -> str:
    if not value:
        return ""

    for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%d%H%M%S"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            pass

    return value


def parse_struct_time(value) -> str:
    if not value:
        return ""

    try:
        timestamp = calendar.timegm(value)
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
    except Exception:
        return ""


def parse_datetime_safe(value: str | None) -> datetime | None:
    if not value:
        return None

    value = clean_text(value)

    try:
        if value.endswith("Z"):
            value = value.replace("Z", "+00:00")

        dt = datetime.fromisoformat(value)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(timezone.utc)
    except Exception:
        pass

    common_formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d"
    ]

    for fmt in common_formats:
        try:
            dt = datetime.strptime(value, fmt)

            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

            return dt.astimezone(timezone.utc)
        except Exception:
            continue

    return None


def is_recent_enough(published_at: str, max_age_days: int, allow_unknown: bool = True) -> bool:
    dt = parse_datetime_safe(published_at)

    if dt is None:
        return allow_unknown

    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)

    return dt >= cutoff


def infer_region(country: str | None) -> str:
    if not country:
        return "Global"

    return COUNTRY_REGION.get(country, "Global")


def is_semiconductor_relevant(title: str, snippet: str, source_name: str) -> bool:
    if source_name in SPECIALIST_RSS_SOURCES:
        return True

    text = f"{title} {snippet}".lower()

    if source_name in COMPANY_SIGNAL_SOURCES:
        company_signal_keywords = [
            "ai",
            "gpu",
            "accelerator",
            "data center",
            "datacenter",
            "server",
            "compute",
            "inference",
            "training",
            "processor",
            "cpu",
            "xpu",
            "epyc",
            "xeon",
            "cuda",
            "hbm",
            "memory",
            "foundry",
            "semiconductor",
            "chip"
        ]

        if any(keyword in text for keyword in company_signal_keywords):
            return True

    return any(keyword.lower() in text for keyword in SEMICONDUCTOR_KEYWORDS)


def http_get_json(url: str, params: dict) -> dict:
    last_error: Exception | None = None

    for attempt in range(3):
        try:
            response = requests.get(
                url,
                params=params,
                timeout=REQUEST_TIMEOUT,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "application/json,text/plain,*/*"
                }
            )

            if response.status_code == 429:
                wait_seconds = 10 * (attempt + 1)
                print(f"[WARN] 429 Too Many Requests. sleep={wait_seconds}s")
                time.sleep(wait_seconds)
                continue

            response.raise_for_status()

            text = response.text.strip()

            if not text:
                raise ValueError("Empty response from API")

            try:
                return response.json()
            except json.JSONDecodeError:
                return json.loads(text, strict=False)

        except Exception as exc:
            last_error = exc

            if attempt < 2:
                time.sleep(3 * (attempt + 1))
                continue

    raise last_error if last_error else RuntimeError("Unknown JSON request error")


def http_get_text(url: str) -> str:
    last_error: Exception | None = None

    for attempt in range(3):
        try:
            response = requests.get(
                url,
                timeout=REQUEST_TIMEOUT,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "application/rss+xml,application/atom+xml,application/xml,text/xml,text/html,*/*"
                }
            )

            if response.status_code == 429:
                wait_seconds = 10 * (attempt + 1)
                print(f"[WARN] RSS 429 Too Many Requests. sleep={wait_seconds}s url={url}")
                time.sleep(wait_seconds)
                continue

            response.raise_for_status()
            return response.text

        except Exception as exc:
            last_error = exc

            if attempt < 2:
                time.sleep(3 * (attempt + 1))
                continue

    raise last_error if last_error else RuntimeError("Unknown text request error")


def get_gdelt_country(article: dict) -> str:
    return clean_text(
        article.get("sourceCountry")
        or article.get("sourcecountry")
        or article.get("source_country")
        or article.get("sourceCountryCode")
        or ""
    )


def get_gdelt_source(article: dict) -> str:
    return clean_text(
        article.get("sourceCommonName")
        or article.get("sourcecommonname")
        or article.get("domain")
        or article.get("source")
        or "Unknown"
    )


def get_gdelt_title(article: dict) -> str:
    return clean_text(
        article.get("title")
        or article.get("name")
        or ""
    )


def get_gdelt_url(article: dict) -> str:
    return normalize_url(
        article.get("url")
        or article.get("url_mobile")
        or article.get("link")
        or ""
    )


def get_gdelt_snippet(article: dict, title: str) -> str:
    snippet = clean_text(
        article.get("snippet")
        or article.get("description")
        or article.get("summary")
        or ""
    )

    return limit_text(snippet or title)


def fetch_gdelt_news() -> list[FeedItem]:
    items: list[FeedItem] = []

    for query in NEWS_QUERIES:
        params = {
            "query": query,
            "mode": "ArtList",
            "format": "json",
            "maxrecords": 50,
            "sort": "HybridRel",
            "timespan": "48h"
        }

        print(f"[INFO] GDELT query: {query}")

        try:
            data = http_get_json(GDELT_ENDPOINT, params)
        except Exception as exc:
            print(f"[WARN] GDELT query failed: {exc}")
            continue

        articles = data.get("articles", [])

        print(f"[INFO] GDELT articles: {len(articles)}")

        for article in articles:
            title = get_gdelt_title(article)
            url = get_gdelt_url(article)

            if not title or not url:
                continue

            country = get_gdelt_country(article)
            source = get_gdelt_source(article)
            published_at = parse_gdelt_date(article.get("seendate"))
            snippet = get_gdelt_snippet(article, title)

            items.append(
                FeedItem(
                    id=stable_id("gdelt", url, title),
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

        time.sleep(5)

    return dedupe(items)[:MAX_GDELT_NEWS]


def get_entry_summary(entry) -> str:
    summary = (
        entry.get("summary")
        or entry.get("description")
        or entry.get("subtitle")
        or ""
    )

    if not summary and entry.get("content"):
        try:
            summary = entry.get("content")[0].get("value", "")
        except Exception:
            summary = ""

    return limit_text(summary)


def get_entry_date(entry) -> str:
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        parsed = entry.get(key)

        if parsed:
            return parse_struct_time(parsed)

    for key in ("published", "updated", "created"):
        value = clean_text(entry.get(key))

        if value:
            return value

    return ""


def fetch_rss_news() -> list[FeedItem]:
    items: list[FeedItem] = []

    for feed in RSS_FEEDS:
        name = feed["name"]
        url = feed["url"]

        print(f"[INFO] RSS feed: {name} / {url}")

        try:
            raw = http_get_text(url)
            parsed = feedparser.parse(raw)
        except Exception as exc:
            print(f"[WARN] RSS feed failed: {name} / {exc}")
            continue

        if getattr(parsed, "bozo", False):
            print(f"[WARN] RSS parse warning: {name} / {getattr(parsed, 'bozo_exception', '')}")

        entries = parsed.entries or []

        print(f"[INFO] RSS entries: {name} / {len(entries)}")

        kept_count = 0
        old_count = 0
        irrelevant_count = 0

        for entry in entries[:60]:
            title = clean_text(entry.get("title"))
            link = normalize_url(clean_text(entry.get("link")))
            snippet = get_entry_summary(entry)
            published_at = get_entry_date(entry)

            if not title or not link:
                continue

            if not is_recent_enough(published_at, RSS_MAX_AGE_DAYS, allow_unknown=True):
                old_count += 1
                continue

            if not is_semiconductor_relevant(title, snippet, name):
                irrelevant_count += 1
                continue

            items.append(
                FeedItem(
                    id=stable_id("rss", link, title),
                    type="news",
                    region=feed.get("region", "Global"),
                    country=feed.get("country", ""),
                    source=name,
                    published_at=published_at,
                    title=title,
                    snippet=snippet,
                    url=link,
                    content_mode="rss_snippet_only"
                )
            )

            kept_count += 1

        print(
            f"[INFO] RSS kept: {name} / {kept_count} "
            f"(old={old_count}, irrelevant={irrelevant_count})"
        )

        time.sleep(2)

    return dedupe(items)[:MAX_RSS_NEWS]


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
        abstract = limit_text(entry.findtext("atom:summary", default="", namespaces=ns), max_len=900)
        published_at = clean_text(entry.findtext("atom:published", default="", namespaces=ns))
        url = normalize_url(clean_text(entry.findtext("atom:id", default="", namespaces=ns)))

        if not is_recent_enough(published_at, PAPER_MAX_AGE_DAYS, allow_unknown=True):
            continue

        authors = []

        for author in entry.findall("atom:author", ns):
            name = clean_text(author.findtext("atom:name", default="", namespaces=ns))

            if name:
                authors.append(name)

        pdf_url = ""

        for link in entry.findall("atom:link", ns):
            if link.attrib.get("title") == "pdf" or link.attrib.get("type") == "application/pdf":
                pdf_url = normalize_url(link.attrib.get("href", ""))
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
        key = normalize_url(item.url) or item.id

        if key in seen:
            continue

        seen.add(key)
        deduped.append(item)

    return deduped


def sort_items(items: list[FeedItem]) -> list[FeedItem]:
    return sorted(items, key=lambda item: item.published_at or "", reverse=True)


def main() -> None:
    gdelt_news = fetch_gdelt_news()
    rss_news = fetch_rss_news()
    papers = fetch_arxiv_papers()

    news = dedupe([*rss_news, *gdelt_news])
    items = sort_items(dedupe([*news, *papers]))

    payload = {
        "meta": {
            "generated_at": now_iso_kst(),
            "gdelt_news_count": len(gdelt_news),
            "rss_news_count": len(rss_news),
            "news_count": len(news),
            "paper_count": len(papers),
            "total_count": len(items),
            "rss_max_age_days": RSS_MAX_AGE_DAYS,
            "paper_max_age_days": PAPER_MAX_AGE_DAYS,
            "policy": "Original links only. No full news republication.",
            "sources": [
                "GDELT",
                "RSS",
                "arXiv"
            ],
            "rss_feeds": [
                feed["name"] for feed in RSS_FEEDS
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
    print(
        f"Items: {len(items)} / "
        f"News: {len(news)} / "
        f"GDELT: {len(gdelt_news)} / "
        f"RSS: {len(rss_news)} / "
        f"Papers: {len(papers)}"
    )


if __name__ == "__main__":
    main()
