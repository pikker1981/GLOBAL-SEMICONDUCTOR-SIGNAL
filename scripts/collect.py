#!/usr/bin/env python3
"""
Global Semiconductor Signal collector.

- GDELT global semiconductor news
- RSS semiconductor/company/Korean industry news
- K-INVEST Korean stock market insight news
- K-POLITICS Korean political news
- arXiv semiconductor papers

This script stores titles, snippets, source, date, and original links only.
It does not republish full news articles.
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
from urllib.parse import parse_qsl, quote_plus, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import feedparser
import requests

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "data" / "latest.json"

MAX_GDELT_NEWS = 80
MAX_RSS_NEWS = 120
MAX_K_INVEST_NEWS = 80
MAX_K_POLITICS_NEWS = 120
MAX_PAPERS = 40

RSS_MAX_AGE_DAYS = 30
K_INVEST_MAX_AGE_DAYS = 14
K_POLITICS_MAX_AGE_DAYS = 7
PAPER_MAX_AGE_DAYS = 180
REQUEST_TIMEOUT = 25
USER_AGENT = "semiconductor-global-signal/1.5 original-link-only"

GDELT_ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"
ARXIV_ENDPOINT = "https://export.arxiv.org/api/query"

NEWS_QUERIES = [
    '(semiconductor OR "chip industry" OR foundry OR HBM OR DRAM OR NAND OR EUV)',
    '(TSMC OR ASML OR Intel OR Micron OR NVIDIA OR AMD)',
    '("Samsung Electronics" OR "SK hynix" OR "advanced packaging" OR "AI chip")',
    '(半導体 OR 半导体 OR 반도체 OR semiconducteur OR Halbleiter)',
]

K_POLITICS_GDELT_QUERIES = [
    '(대통령 OR 대통령실 OR 국회 OR 여당 OR 야당 OR 정당 OR 정부 OR 장관 OR 총리)',
    '(선거 OR 총선 OR 대선 OR 지방선거 OR 공천 OR 여론조사 OR 국정감사)',
    '(정치 OR 국회의원 OR 더불어민주당 OR 국민의힘 OR 개혁신당 OR 조국혁신당)',
    '(외교 OR 국방 OR 북한 OR 안보 OR 한미 OR 한일 OR 한중)',
]

ARXIV_QUERY = (
    'all:semiconductor OR all:transistor OR all:CMOS OR all:nanofabrication '
    'OR all:"semiconductor device" OR all:"advanced packaging" OR all:"AI accelerator"'
)

RSS_FEEDS = [
    {"name": "Samsung Global Newsroom", "url": "https://news.samsung.com/global/feed", "region": "Asia", "country": "South Korea"},
    {"name": "SK hynix Newsroom", "url": "https://news.skhynix.co.kr/feed/", "region": "Asia", "country": "South Korea"},
    {"name": "NVIDIA Press Room", "url": "https://nvidianews.nvidia.com/releases.xml", "region": "Americas", "country": "United States"},
    {"name": "NVIDIA Developer Blog", "url": "https://developer.nvidia.com/blog/feed", "region": "Americas", "country": "United States"},
    {"name": "AMD Press Releases", "url": "https://ir.amd.com/news-events/press-releases/rss", "region": "Americas", "country": "United States"},
    {"name": "Intel Newsroom", "url": "http://feeds.feedburner.com/IntelNewsroom?format=xml", "region": "Americas", "country": "United States"},
    {"name": "Semiconductor Engineering", "url": "https://semiengineering.com/feed/", "region": "Americas", "country": "United States"},
    {"name": "Semiconductor Today", "url": "https://www.semiconductor-today.com/rss/news.xml", "region": "Europe", "country": "United Kingdom"},
    {"name": "SemiWiki", "url": "https://semiwiki.com/feed/", "region": "Americas", "country": "United States"},
    {"name": "EE Times Asia", "url": "https://www.eetasia.com/feed/", "region": "Asia", "country": ""},
    {"name": "The Register HPC", "url": "https://www.theregister.com/on_prem/hpc/headlines.atom", "region": "Europe", "country": "United Kingdom"},
    {"name": "The Register AI ML", "url": "https://www.theregister.com/software/ai_ml/headlines.atom", "region": "Europe", "country": "United Kingdom"},
    {"name": "The Elec Semiconductor", "url": "https://www.thelec.kr/rss/S1N2.xml", "region": "Asia", "country": "South Korea"},
    {"name": "The Elec Materials Equipment", "url": "https://www.thelec.kr/rss/S1N3.xml", "region": "Asia", "country": "South Korea"},
    {"name": "ETNews Electronics", "url": "http://rss.etnews.com/06.xml", "region": "Asia", "country": "South Korea"},
    {"name": "ETNews Materials", "url": "http://rss.etnews.com/06064.xml", "region": "Asia", "country": "South Korea"},
    {"name": "ETNews Components", "url": "http://rss.etnews.com/06062.xml", "region": "Asia", "country": "South Korea"},
    {"name": "ETNews Equipment", "url": "http://rss.etnews.com/06061.xml", "region": "Asia", "country": "South Korea"},
    {"name": "KIPOST All Articles", "url": "https://www.kipost.net/rss/allArticle.xml", "region": "Asia", "country": "South Korea"},
]

K_INVEST_RSS_FEEDS = [
    {"name": "Hankyung Finance", "url": "https://www.hankyung.com/feed/finance", "region": "Asia", "country": "South Korea"},
    {"name": "Hankyung Economy", "url": "https://www.hankyung.com/feed/economy", "region": "Asia", "country": "South Korea"},
    {"name": "Maeil Business Securities", "url": "https://www.mk.co.kr/rss/50200011/", "region": "Asia", "country": "South Korea"},
    {"name": "Maeil Business Economy", "url": "https://www.mk.co.kr/rss/30100041/", "region": "Asia", "country": "South Korea"},
    {"name": "Maeil Business Corporate", "url": "https://www.mk.co.kr/rss/50100032/", "region": "Asia", "country": "South Korea"},
    {"name": "Yonhap Infomax Securities", "url": "https://news.einfomax.co.kr/rss/S1N2.xml", "region": "Asia", "country": "South Korea"},
    {"name": "Yonhap Infomax IB Company", "url": "https://news.einfomax.co.kr/rss/S1N7.xml", "region": "Asia", "country": "South Korea"},
    {"name": "EToday Market", "url": "https://rss.etoday.co.kr/eto/market_news.xml", "region": "Asia", "country": "South Korea"},
    {"name": "EToday Finance", "url": "https://rss.etoday.co.kr/eto/finance_news.xml", "region": "Asia", "country": "South Korea"},
    {"name": "EToday Economy", "url": "https://rss.etoday.co.kr/eto/economy_news.xml", "region": "Asia", "country": "South Korea"},
    {"name": "EToday Industry", "url": "https://rss.etoday.co.kr/eto/industry_news.xml", "region": "Asia", "country": "South Korea"},
]

K_POLITICS_RSS_FEEDS = [
    {"name": "Hankyung Politics", "url": "https://www.hankyung.com/feed/politics", "region": "Asia", "country": "South Korea"},
    {"name": "Maeil Business Politics", "url": "https://www.mk.co.kr/rss/30200030/", "region": "Asia", "country": "South Korea"},
    {"name": "Donga Politics", "url": "https://rss.donga.com/politics.xml", "region": "Asia", "country": "South Korea"},
    {"name": "MBN Politics", "url": "https://www.mbn.co.kr/rss/politics/", "region": "Asia", "country": "South Korea"},
    {"name": "Korea.kr Policy News", "url": "https://www.korea.kr/rss/policy.xml", "region": "Asia", "country": "South Korea"},
    {"name": "Yonhap News TV Politics", "url": "https://www.yonhapnewstv.co.kr/category/news/politics/feed/", "region": "Asia", "country": "South Korea"},
]

K_POLITICS_GOOGLE_NEWS_QUERIES = [
    "대통령 OR 대통령실",
    "국회 OR 정당 OR 여당 OR 야당",
    "선거 OR 대선 OR 총선 OR 지방선거",
    "정부 OR 장관 OR 국무총리",
    "정치권 OR 국회의원",
    "외교 국방 북한 안보",
]

SPECIALIST_RSS_SOURCES = {
    "Semiconductor Engineering", "Semiconductor Today", "SemiWiki", "EE Times Semiconductors", "EE Times Asia",
    "The Elec Semiconductor", "The Elec Materials Equipment", "ETNews Electronics", "ETNews Materials", "ETNews Components", "ETNews Equipment",
}

COMPANY_SIGNAL_SOURCES = {
    "Samsung Global Newsroom", "SK hynix Newsroom", "NVIDIA Press Room", "NVIDIA Developer Blog", "AMD Press Releases", "Intel Newsroom",
}

SEMICONDUCTOR_KEYWORDS = [
    "semiconductor", "semiconductors", "chip", "chips", "chiplet", "foundry", "fab", "wafer", "silicon", "transistor", "cmos",
    "memory", "hbm", "dram", "nand", "euv", "lithography", "asml", "tsmc", "samsung", "sk hynix", "hynix", "intel", "micron",
    "nvidia", "amd", "ai chip", "gpu", "accelerator", "data center", "processor", "cpu", "advanced packaging",
    "반도체", "파운드리", "메모리", "디램", "낸드", "노광", "식각", "증착", "패키징", "첨단 패키징", "후공정", "전공정", "소부장",
    "소재", "부품", "장비", "웨이퍼", "팹리스", "시스템반도체", "차량용 반도체", "AI 반도체", "삼성전자", "SK하이닉스", "하이닉스",
    "한미반도체", "원익IPS", "유진테크", "테스", "솔브레인", "동진쎄미켐", "半導体", "半导体"
]

K_INVEST_KEYWORDS = [
    "코스피", "코스닥", "증시", "주식", "주가", "상장사", "시가총액", "시총", "실적", "어닝", "영업이익", "순이익", "매출",
    "컨센서스", "목표주가", "투자의견", "증권사", "리포트", "수급", "외국인", "기관", "연기금", "순매수", "순매도", "공매도",
    "자사주", "배당", "밸류업", "PER", "PBR", "ROE", "환율", "금리", "FOMC", "반도체", "HBM", "AI 반도체", "2차전지",
    "배터리", "바이오", "조선", "방산", "원전", "전력기기", "자동차", "로봇", "IPO", "공모주", "유상증자", "무상증자", "권리락"
]

K_POLITICS_KEYWORDS = [
    "대통령", "대통령실", "청와대", "국회", "국회의원", "여당", "야당", "정당", "더불어민주당", "민주당", "국민의힘",
    "개혁신당", "조국혁신당", "정치권", "정부", "장관", "국무총리", "총리", "국정감사", "청문회", "법안", "개정안",
    "예산안", "특검", "탄핵", "선거", "대선", "총선", "지방선거", "공천", "여론조사", "지지율", "외교", "국방", "북한", "안보", "한미", "한일", "한중"
]

COUNTRY_REGION = {
    "China": "Asia", "Taiwan": "Asia", "Japan": "Asia", "South Korea": "Asia", "Korea, South": "Asia", "India": "Asia", "Singapore": "Asia",
    "Malaysia": "Asia", "Vietnam": "Asia", "Thailand": "Asia", "Indonesia": "Asia", "Philippines": "Asia", "Israel": "Asia",
    "Netherlands": "Europe", "Germany": "Europe", "France": "Europe", "United Kingdom": "Europe", "Ireland": "Europe", "Italy": "Europe", "Spain": "Europe",
    "Sweden": "Europe", "Finland": "Europe", "Norway": "Europe", "Austria": "Europe", "Belgium": "Europe", "Switzerland": "Europe", "Poland": "Europe", "Czech Republic": "Europe",
    "United States": "Americas", "United States of America": "Americas", "Canada": "Americas", "Mexico": "Americas", "Brazil": "Americas", "Argentina": "Americas", "Chile": "Americas"
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
    source_type: str = ""
    insight_type: str = ""


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
    return value if len(value) <= max_len else value[:max_len].rstrip() + "..."


def normalize_url(url: str) -> str:
    if not url:
        return ""
    try:
        parsed = urlsplit(clean_text(url))
        query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
        filtered_pairs = [
            (key, value)
            for key, value in query_pairs
            if not key.lower().startswith("utm_") and key.lower() not in {"fbclid", "gclid", "mc_cid", "mc_eid"}
        ]
        return urlunsplit((parsed.scheme, parsed.netloc.lower(), parsed.path.rstrip("/"), urlencode(filtered_pairs, doseq=True), ""))
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
    for fmt in ["%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
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
    return dt >= datetime.now(timezone.utc) - timedelta(days=max_age_days)


def infer_region(country: str | None) -> str:
    if not country:
        return "Global"
    return COUNTRY_REGION.get(country, "Global")


def contains_keyword(title: str, snippet: str, keywords: list[str]) -> bool:
    text = f"{title} {snippet}".lower()
    return any(keyword.lower() in text for keyword in keywords)


def is_semiconductor_relevant(title: str, snippet: str, source_name: str) -> bool:
    if source_name in SPECIALIST_RSS_SOURCES:
        return True
    if source_name in COMPANY_SIGNAL_SOURCES:
        if contains_keyword(title, snippet, ["ai", "gpu", "accelerator", "data center", "server", "processor", "cpu", "hbm", "memory", "foundry", "semiconductor", "chip"]):
            return True
    return contains_keyword(title, snippet, SEMICONDUCTOR_KEYWORDS)


def is_k_invest_relevant(title: str, snippet: str) -> bool:
    return contains_keyword(title, snippet, K_INVEST_KEYWORDS)


def is_k_politics_relevant(title: str, snippet: str) -> bool:
    return contains_keyword(title, snippet, K_POLITICS_KEYWORDS)


def http_get_json(url: str, params: dict) -> dict:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT, "Accept": "application/json,text/plain,*/*"})
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
                headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml,application/atom+xml,application/xml,text/xml,text/html,*/*"},
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
    return clean_text(article.get("sourceCountry") or article.get("sourcecountry") or article.get("source_country") or article.get("sourceCountryCode") or "")


def get_gdelt_source(article: dict) -> str:
    return clean_text(article.get("sourceCommonName") or article.get("sourcecommonname") or article.get("domain") or article.get("source") or "Unknown")


def get_gdelt_title(article: dict) -> str:
    return clean_text(article.get("title") or article.get("name") or "")


def get_gdelt_url(article: dict) -> str:
    return normalize_url(article.get("url") or article.get("url_mobile") or article.get("link") or "")


def get_gdelt_snippet(article: dict, title: str) -> str:
    snippet = clean_text(article.get("snippet") or article.get("description") or article.get("summary") or "")
    return limit_text(snippet or title)


def fetch_gdelt_by_queries(queries: list[str], max_items: int, source_type: str, insight_type: str, max_age_days: int, require_relevance: bool = False, relevance_keywords: list[str] | None = None) -> list[FeedItem]:
    items: list[FeedItem] = []
    for query in queries:
        params = {"query": query, "mode": "ArtList", "format": "json", "maxrecords": 50, "sort": "HybridRel", "timespan": f"{max_age_days * 24}h"}
        print(f"[INFO] {source_type} GDELT query: {query}")
        try:
            data = http_get_json(GDELT_ENDPOINT, params)
        except Exception as exc:
            print(f"[WARN] {source_type} GDELT query failed: {exc}")
            continue
        articles = data.get("articles", [])
        print(f"[INFO] {source_type} GDELT articles: {len(articles)}")
        for article in articles:
            title = get_gdelt_title(article)
            url = get_gdelt_url(article)
            if not title or not url:
                continue
            country = get_gdelt_country(article)
            source = get_gdelt_source(article)
            published_at = parse_gdelt_date(article.get("seendate"))
            snippet = get_gdelt_snippet(article, title)
            if require_relevance and relevance_keywords and not contains_keyword(title, snippet, relevance_keywords):
                continue
            items.append(
                FeedItem(
                    id=stable_id(source_type.lower(), url, title),
                    type="news",
                    region=infer_region(country) if country else "Asia",
                    country=country or "South Korea",
                    source=source,
                    published_at=published_at,
                    title=title,
                    snippet=snippet,
                    url=url,
                    content_mode=f"{source_type.lower().replace('-', '_')}_gdelt_snippet_only",
                    source_type=source_type,
                    insight_type=insight_type,
                )
            )
        time.sleep(5)
    return dedupe(items)[:max_items]


def fetch_gdelt_news() -> list[FeedItem]:
    return fetch_gdelt_by_queries(NEWS_QUERIES, MAX_GDELT_NEWS, "GDELT", "semiconductor", 2)


def fetch_k_politics_gdelt_news() -> list[FeedItem]:
    return fetch_gdelt_by_queries(K_POLITICS_GDELT_QUERIES, MAX_K_POLITICS_NEWS, "K-POLITICS", "korean_politics", K_POLITICS_MAX_AGE_DAYS, True, K_POLITICS_KEYWORDS)


def get_entry_summary(entry) -> str:
    summary = entry.get("summary") or entry.get("description") or entry.get("subtitle") or ""
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


def parse_feed_entries(feeds: list[dict], max_age_days: int, max_items: int, source_type: str, insight_type: str, relevance_fn) -> list[FeedItem]:
    items: list[FeedItem] = []
    for feed in feeds:
        name = feed["name"]
        url = feed["url"]
        print(f"[INFO] {source_type} feed: {name} / {url}")
        try:
            raw = http_get_text(url)
            parsed = feedparser.parse(raw)
        except Exception as exc:
            print(f"[WARN] {source_type} feed failed: {name} / {exc}")
            continue
        if getattr(parsed, "bozo", False):
            print(f"[WARN] {source_type} parse warning: {name} / {getattr(parsed, 'bozo_exception', '')}")
        entries = parsed.entries or []
        print(f"[INFO] {source_type} entries: {name} / {len(entries)}")
        kept_count = old_count = irrelevant_count = 0
        for entry in entries[:60]:
            title = clean_text(entry.get("title"))
            link = normalize_url(clean_text(entry.get("link")))
            snippet = get_entry_summary(entry)
            published_at = get_entry_date(entry)
            if not title or not link:
                continue
            if not is_recent_enough(published_at, max_age_days, allow_unknown=True):
                old_count += 1
                continue
            if not relevance_fn(title, snippet, name):
                irrelevant_count += 1
                continue
            items.append(
                FeedItem(
                    id=stable_id(source_type.lower(), link, title),
                    type="news",
                    region=feed.get("region", "Asia"),
                    country=feed.get("country", "South Korea"),
                    source=name,
                    published_at=published_at,
                    title=title,
                    snippet=snippet,
                    url=link,
                    content_mode=f"{source_type.lower().replace('-', '_')}_rss_snippet_only",
                    source_type=source_type,
                    insight_type=insight_type,
                )
            )
            kept_count += 1
        print(f"[INFO] {source_type} kept: {name} / {kept_count} (old={old_count}, irrelevant={irrelevant_count})")
        time.sleep(2)
    return dedupe(items)[:max_items]


def fetch_rss_news() -> list[FeedItem]:
    return parse_feed_entries(RSS_FEEDS, RSS_MAX_AGE_DAYS, MAX_RSS_NEWS, "RSS", "semiconductor", lambda t, s, n: is_semiconductor_relevant(t, s, n))


def fetch_k_invest_news() -> list[FeedItem]:
    return parse_feed_entries(K_INVEST_RSS_FEEDS, K_INVEST_MAX_AGE_DAYS, MAX_K_INVEST_NEWS, "K-INVEST", "korean_stock", lambda t, s, n: is_k_invest_relevant(t, s))


def google_news_rss_url(query: str) -> str:
    return f"https://news.google.com/rss/search?q={quote_plus(query + ' when:7d')}&hl=ko&gl=KR&ceid=KR:ko"


def fetch_k_politics_google_news() -> list[FeedItem]:
    google_feeds = [{"name": f"Google News Politics: {query}", "url": google_news_rss_url(query), "region": "Asia", "country": "South Korea"} for query in K_POLITICS_GOOGLE_NEWS_QUERIES]
    return parse_feed_entries(google_feeds, K_POLITICS_MAX_AGE_DAYS, MAX_K_POLITICS_NEWS, "K-POLITICS", "korean_politics", lambda t, s, n: is_k_politics_relevant(t, s))


def fetch_k_politics_rss_news() -> list[FeedItem]:
    return parse_feed_entries(K_POLITICS_RSS_FEEDS, K_POLITICS_MAX_AGE_DAYS, MAX_K_POLITICS_NEWS, "K-POLITICS", "korean_politics", lambda t, s, n: is_k_politics_relevant(t, s))


def fetch_k_politics_news() -> list[FeedItem]:
    rss_items = fetch_k_politics_rss_news()
    google_items = fetch_k_politics_google_news()
    gdelt_items = fetch_k_politics_gdelt_news()
    return dedupe([*rss_items, *google_items, *gdelt_items])[:MAX_K_POLITICS_NEWS]


def fetch_arxiv_papers() -> list[FeedItem]:
    params = {"search_query": ARXIV_QUERY, "start": 0, "max_results": MAX_PAPERS, "sortBy": "submittedDate", "sortOrder": "descending"}
    try:
        response = requests.get(ARXIV_ENDPOINT, params=params, timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
    except Exception as exc:
        print(f"[WARN] arXiv query failed: {exc}")
        return []
    ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
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
        items.append(FeedItem(stable_id("paper", url, title), "paper", "Global", "", "arXiv", published_at, title, url, abstract=abstract, authors=authors, pdf_url=pdf_url, content_mode="open_abstract", source_type="arXiv", insight_type="paper"))
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
    k_invest_news = fetch_k_invest_news()
    k_politics_news = fetch_k_politics_news()
    papers = fetch_arxiv_papers()

    news = dedupe([*k_politics_news, *k_invest_news, *rss_news, *gdelt_news])
    items = sort_items(dedupe([*news, *papers]))

    payload = {
        "meta": {
            "generated_at": now_iso_kst(),
            "gdelt_news_count": len(gdelt_news),
            "rss_news_count": len(rss_news),
            "k_invest_news_count": len(k_invest_news),
            "k_politics_news_count": len(k_politics_news),
            "news_count": len(news),
            "paper_count": len(papers),
            "total_count": len(items),
            "rss_max_age_days": RSS_MAX_AGE_DAYS,
            "k_invest_max_age_days": K_INVEST_MAX_AGE_DAYS,
            "k_politics_max_age_days": K_POLITICS_MAX_AGE_DAYS,
            "paper_max_age_days": PAPER_MAX_AGE_DAYS,
            "policy": "Original links only. No full news republication. Not investment advice.",
            "sources": ["GDELT", "RSS", "K-INVEST", "K-POLITICS", "arXiv"],
            "rss_feeds": [feed["name"] for feed in RSS_FEEDS],
            "k_invest_feeds": [feed["name"] for feed in K_INVEST_RSS_FEEDS],
            "k_politics_feeds": [feed["name"] for feed in K_POLITICS_RSS_FEEDS],
            "k_politics_google_news_queries": K_POLITICS_GOOGLE_NEWS_QUERIES,
        },
        "items": [asdict(item) for item in items],
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT}")
    print(f"Items: {len(items)} / News: {len(news)} / GDELT: {len(gdelt_news)} / RSS: {len(rss_news)} / K-INVEST: {len(k_invest_news)} / K-POLITICS: {len(k_politics_news)} / Papers: {len(papers)}")


if __name__ == "__main__":
    main()
