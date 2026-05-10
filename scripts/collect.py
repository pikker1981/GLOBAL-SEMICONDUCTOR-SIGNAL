#!/usr/bin/env python3
"""
Global Semiconductor Signal collector.

- GDELT 글로벌 반도체 뉴스
- RSS 반도체/기업/한국 산업 뉴스
- K-INVEST 한국 주식 투자 인사이트 기사
- arXiv 반도체 논문

원칙: 기사 전문 재게시 금지. 제목, 스니펫, 출처, 날짜, 원문 링크만 저장.
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

USER_AGENT = "semiconductor-global-signal/1.4 original-link-only"
GDELT_ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"
ARXIV_ENDPOINT = "https://export.arxiv.org/api/query"

NEWS_QUERIES = [
    '(semiconductor OR "chip industry" OR foundry OR HBM OR DRAM OR NAND OR EUV)',
    '(TSMC OR ASML OR Intel OR Micron OR NVIDIA OR AMD)',
    '("Samsung Electronics" OR "SK hynix" OR "advanced packaging" OR "AI chip")',
    '(半導体 OR 半导体 OR 반도체 OR semiconducteur OR Halbleiter)',
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
    {"name": "EE Times Semiconductors", "url": "https://www.eetimes.com/tag/semiconductors/feed/", "region": "Americas", "country": "United States"},
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

K_POLITICS_GDELT_QUERIES = [
    '(대통령 OR 대통령실 OR 국회 OR 여당 OR 야당 OR 정당 OR 정부 OR 장관 OR 총리)',
    '(선거 OR 총선 OR 대선 OR 지방선거 OR 공천 OR 여론조사 OR 국정감사)',
    '(정치 OR 국회의원 OR 더불어민주당 OR 국민의힘 OR 개혁신당 OR 조국혁신당)',
    '(외교 OR 국방 OR 북한 OR 안보 OR 한미 OR 한일 OR 한중)',
]

SPECIALIST_RSS_SOURCES = {
    "Semiconductor Engineering", "Semiconductor Today", "SemiWiki",
    "EE Times Semiconductors", "EE Times Asia", "The Elec Semiconductor",
    "The Elec Materials Equipment", "ETNews Electronics", "ETNews Materials",
    "ETNews Components", "ETNews Equipment"
}

COMPANY_SIGNAL_SOURCES = {
    "Samsung Global Newsroom", "SK hynix Newsroom", "NVIDIA Press Room",
    "NVIDIA Developer Blog", "AMD Press Releases", "Intel Newsroom"
}

SEMICONDUCTOR_KEYWORDS = [
    "semiconductor", "semiconductors", "chip", "chips", "chiplet", "foundry", "fab", "wafer",
    "silicon", "transistor", "cmos", "logic", "memory", "hbm", "dram", "nand", "sram",
    "euv", "duv", "lithography", "asml", "tsmc", "samsung", "sk hynix", "hynix",
    "intel", "micron", "nvidia", "amd", "qualcomm", "broadcom", "arm", "eda",
    "synopsys", "cadence", "advanced packaging", "cowos", "interposer", "substrate",
    "gan", "sic", "silicon carbide", "gallium nitride", "ai chip", "gpu", "accelerator",
    "data center", "datacenter", "server", "processor", "cpu", "xpu", "epyc", "xeon", "cuda",
    "inference", "training", "반도체", "파운드리", "메모리", "디램", "낸드", "노광",
    "식각", "증착", "패키징", "첨단 패키징", "후공정", "전공정", "소부장", "소재",
    "부품", "장비", "웨이퍼", "팹리스", "팹", "시스템반도체", "차량용 반도체",
    "AI 반도체", "온디바이스 AI", "삼성전자", "SK하이닉스", "하이닉스", "한미반도체",
    "원익IPS", "유진테크", "테스", "솔브레인", "동진쎄미켐", "半導体", "半导体"
]

K_INVEST_KEYWORDS = [
    "코스피", "코스닥", "증시", "주식", "주가", "상장사", "시가총액", "시총", "실적",
    "어닝", "영업이익", "순이익", "매출", "컨센서스", "목표주가", "투자의견",
    "증권사", "리포트", "수급", "외국인", "기관", "연기금", "개인투자자", "순매수",
    "순매도", "공매도", "자사주", "배당", "밸류업", "저평가", "고평가", "PER", "PBR",
    "ROE", "환율", "금리", "국채", "미국채", "FOMC", "반도체", "HBM", "AI 반도체",
    "2차전지", "배터리", "바이오", "조선", "방산", "원전", "전력기기", "화장품",
    "자동차", "로봇", "IPO", "공모주", "유상증자", "무상증자", "권리락", "인적분할", "물적분할"
]


K_POLITICS_KEYWORDS = [
    "대통령", "대통령실", "청와대", "국회", "국회의원", "여당", "야당", "정당",
    "더불어민주당", "민주당", "국민의힘", "개혁신당", "조국혁신당", "정치권",
    "정부", "장관", "국무총리", "총리", "국정감사", "청문회", "법안", "개정안",
    "예산안", "특검", "탄핵", "선거", "대선", "총선", "지방선거", "공천",
    "여론조사", "지지율", "외교", "국방", "북한", "안보", "한미", "한일", "한중"
]

COUNTRY_REGION = {
    "China": "Asia", "Taiwan": "Asia", "Japan": "Asia", "South Korea": "Asia",
    "Korea, South": "Asia", "India": "Asia", "Singapore": "Asia", "Malaysia": "Asia",
    "Vietnam": "Asia", "Thailand": "Asia", "Indonesia": "Asia", "Philippines": "Asia",
    "Israel": "Asia", "Netherlands": "Europe", "Germany": "Europe", "France": "Europe",
    "United Kingdom": "Europe", "Ireland": "Europe", "Italy": "Europe", "Spain": "Europe",
    "Sweden": "Europe", "Finland": "Europe", "Norway": "Europe", "Austria": "Europe",
    "Belgium": "Europe", "Switzerland": "Europe", "Poland": "Europe", "Czech Republic": "Europe",
    "United States": "Americas", "United States of America": "Americas", "Canada": "Americas",
    "Mexico": "Americas", "Brazil": "Americas", "Argentina": "Americas", "Chile": "Americas",
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
        pairs = parse_qsl(parsed.query, keep_blank_values=True)
        filtered = [(k, v) for k, v in pairs if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid", "mc_cid", "mc_eid"}]
        return urlunsplit((parsed.scheme, parsed.netloc.lower(), parsed.path.rstrip("/"), urlencode(filtered, doseq=True), ""))
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
        return datetime.fromtimestamp(calendar.timegm(value), tz=timezone.utc).isoformat()
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
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
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
    return COUNTRY_REGION.get(country or "", "Global")


def is_semiconductor_relevant(title: str, snippet: str, source_name: str) -> bool:
    if source_name in SPECIALIST_RSS_SOURCES:
        return True
    text = f"{title} {snippet}".lower()
    if source_name in COMPANY_SIGNAL_SOURCES:
        company_keys = ["ai", "gpu", "accelerator", "data center", "datacenter", "server", "compute", "inference", "training", "processor", "cpu", "hbm", "memory", "foundry", "semiconductor", "chip"]
        if any(k in text for k in company_keys):
            return True
    return any(k.lower() in text for k in SEMICONDUCTOR_KEYWORDS)


def is_k_invest_relevant(title: str, snippet: str) -> bool:
    text = f"{title} {snippet}".lower()
    return any(k.lower() in text for k in K_INVEST_KEYWORDS)



def is_k_politics_relevant(title: str, snippet: str) -> bool:
    text = f"{title} {snippet}".lower()
    return any(k.lower() in text for k in K_POLITICS_KEYWORDS)

def http_get_json(url: str, params: dict) -> dict:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT, "Accept": "application/json,text/plain,*/*"})
            if response.status_code == 429:
                wait = 10 * (attempt + 1)
                print(f"[WARN] 429 Too Many Requests. sleep={wait}s")
                time.sleep(wait)
                continue
            response.raise_for_status()
            text = response.text.strip()
            try:
                return response.json()
            except json.JSONDecodeError:
                return json.loads(text, strict=False)
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(3 * (attempt + 1))
    raise last_error if last_error else RuntimeError("Unknown JSON request error")


def http_get_text(url: str) -> str:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml,application/atom+xml,application/xml,text/xml,text/html,*/*"})
            if response.status_code == 429:
                wait = 10 * (attempt + 1)
                print(f"[WARN] RSS 429 Too Many Requests. sleep={wait}s url={url}")
                time.sleep(wait)
                continue
            response.raise_for_status()
            return response.text
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(3 * (attempt + 1))
    raise last_error if last_error else RuntimeError("Unknown text request error")


def fetch_gdelt_news() -> list[FeedItem]:
    items: list[FeedItem] = []
    for query in NEWS_QUERIES:
        params = {"query": query, "mode": "ArtList", "format": "json", "maxrecords": 50, "sort": "HybridRel", "timespan": "48h"}
        print(f"[INFO] GDELT query: {query}")
        try:
            data = http_get_json(GDELT_ENDPOINT, params)
        except Exception as exc:
            print(f"[WARN] GDELT query failed: {exc}")
            continue
        articles = data.get("articles", [])
        print(f"[INFO] GDELT articles: {len(articles)}")
        for article in articles:
            title = clean_text(article.get("title") or article.get("name") or "")
            url = normalize_url(article.get("url") or article.get("url_mobile") or article.get("link") or "")
            if not title or not url:
                continue
            country = clean_text(article.get("sourceCountry") or article.get("sourcecountry") or article.get("source_country") or "")
            source = clean_text(article.get("sourceCommonName") or article.get("sourcecommonname") or article.get("domain") or "Unknown")
            published_at = parse_gdelt_date(article.get("seendate"))
            snippet = limit_text(article.get("snippet") or article.get("description") or title)
            items.append(FeedItem(stable_id("gdelt", url, title), "news", infer_region(country), country, source, published_at, title, url, snippet=snippet, content_mode="snippet_only", source_type="GDELT"))
        time.sleep(5)
    return dedupe(items)[:MAX_GDELT_NEWS]


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


def fetch_rss_news() -> list[FeedItem]:
    items: list[FeedItem] = []
    for feed in RSS_FEEDS:
        name, url = feed["name"], feed["url"]
        print(f"[INFO] RSS feed: {name} / {url}")
        try:
            parsed = feedparser.parse(http_get_text(url))
        except Exception as exc:
            print(f"[WARN] RSS feed failed: {name} / {exc}")
            continue
        entries = parsed.entries or []
        print(f"[INFO] RSS entries: {name} / {len(entries)}")
        kept = old = irrelevant = 0
        for entry in entries[:60]:
            title = clean_text(entry.get("title"))
            link = normalize_url(clean_text(entry.get("link")))
            snippet = get_entry_summary(entry)
            published_at = get_entry_date(entry)
            if not title or not link:
                continue
            if not is_recent_enough(published_at, RSS_MAX_AGE_DAYS, allow_unknown=True):
                old += 1
                continue
            if not is_semiconductor_relevant(title, snippet, name):
                irrelevant += 1
                continue
            items.append(FeedItem(stable_id("rss", link, title), "news", feed.get("region", "Global"), feed.get("country", ""), name, published_at, title, link, snippet=snippet, content_mode="rss_snippet_only", source_type="RSS"))
            kept += 1
        print(f"[INFO] RSS kept: {name} / {kept} (old={old}, irrelevant={irrelevant})")
        time.sleep(2)
    return dedupe(items)[:MAX_RSS_NEWS]


def fetch_k_invest_news() -> list[FeedItem]:
    items: list[FeedItem] = []
    for feed in K_INVEST_RSS_FEEDS:
        name, url = feed["name"], feed["url"]
        print(f"[INFO] K-INVEST feed: {name} / {url}")
        try:
            parsed = feedparser.parse(http_get_text(url))
        except Exception as exc:
            print(f"[WARN] K-INVEST feed failed: {name} / {exc}")
            continue
        entries = parsed.entries or []
        print(f"[INFO] K-INVEST entries: {name} / {len(entries)}")
        kept = old = irrelevant = 0
        for entry in entries[:60]:
            title = clean_text(entry.get("title"))
            link = normalize_url(clean_text(entry.get("link")))
            snippet = get_entry_summary(entry)
            published_at = get_entry_date(entry)
            if not title or not link:
                continue
            if not is_recent_enough(published_at, K_INVEST_MAX_AGE_DAYS, allow_unknown=True):
                old += 1
                continue
            if not is_k_invest_relevant(title, snippet):
                irrelevant += 1
                continue
            items.append(FeedItem(stable_id("k-invest", link, title), "news", feed.get("region", "Asia"), feed.get("country", "South Korea"), name, published_at, title, link, snippet=snippet, content_mode="k_invest_rss_snippet_only", source_type="K-INVEST", insight_type="korean_stock"))
            kept += 1
        print(f"[INFO] K-INVEST kept: {name} / {kept} (old={old}, irrelevant={irrelevant})")
        time.sleep(2)
    return dedupe(items)[:MAX_K_INVEST_NEWS]



def fetch_k_politics_rss_news() -> list[FeedItem]:
    items: list[FeedItem] = []

    for feed in K_POLITICS_RSS_FEEDS:
        name, url = feed["name"], feed["url"]
        print(f"[INFO] K-POLITICS feed: {name} / {url}")

        try:
            parsed = feedparser.parse(http_get_text(url))
        except Exception as exc:
            print(f"[WARN] K-POLITICS feed failed: {name} / {exc}")
            continue

        entries = parsed.entries or []
        print(f"[INFO] K-POLITICS entries: {name} / {len(entries)}")

        kept = old = irrelevant = 0

        for entry in entries[:60]:
            title = clean_text(entry.get("title"))
            link = normalize_url(clean_text(entry.get("link")))
            snippet = get_entry_summary(entry)
            published_at = get_entry_date(entry)

            if not title or not link:
                continue

            if not is_recent_enough(published_at, K_POLITICS_MAX_AGE_DAYS, allow_unknown=True):
                old += 1
                continue

            if not is_k_politics_relevant(title, snippet):
                irrelevant += 1
                continue

            items.append(
                FeedItem(
                    id=stable_id("k-politics", link, title),
                    type="news",
                    region=feed.get("region", "Asia"),
                    country=feed.get("country", "South Korea"),
                    source=name,
                    published_at=published_at,
                    title=title,
                    url=link,
                    snippet=snippet,
                    content_mode="k_politics_rss_snippet_only",
                    source_type="K-POLITICS",
                    insight_type="korean_politics"
                )
            )
            kept += 1

        print(f"[INFO] K-POLITICS kept: {name} / {kept} (old={old}, irrelevant={irrelevant})")
        time.sleep(2)

    return dedupe(items)[:MAX_K_POLITICS_NEWS]


def google_news_rss_url(query: str) -> str:
    return f"https://news.google.com/rss/search?q={quote_plus(query + ' when:7d')}&hl=ko&gl=KR&ceid=KR:ko"


def fetch_k_politics_google_news() -> list[FeedItem]:
    feeds = [
        {
            "name": f"Google News Politics: {query}",
            "url": google_news_rss_url(query),
            "region": "Asia",
            "country": "South Korea"
        }
        for query in K_POLITICS_GOOGLE_NEWS_QUERIES
    ]

    items: list[FeedItem] = []

    for feed in feeds:
        name, url = feed["name"], feed["url"]
        print(f"[INFO] K-POLITICS Google feed: {name} / {url}")

        try:
            parsed = feedparser.parse(http_get_text(url))
        except Exception as exc:
            print(f"[WARN] K-POLITICS Google feed failed: {name} / {exc}")
            continue

        entries = parsed.entries or []
        print(f"[INFO] K-POLITICS Google entries: {name} / {len(entries)}")

        for entry in entries[:60]:
            title = clean_text(entry.get("title"))
            link = normalize_url(clean_text(entry.get("link")))
            snippet = get_entry_summary(entry)
            published_at = get_entry_date(entry)

            if not title or not link:
                continue

            if not is_recent_enough(published_at, K_POLITICS_MAX_AGE_DAYS, allow_unknown=True):
                continue

            if not is_k_politics_relevant(title, snippet):
                continue

            items.append(
                FeedItem(
                    id=stable_id("k-politics-google", link, title),
                    type="news",
                    region="Asia",
                    country="South Korea",
                    source=name,
                    published_at=published_at,
                    title=title,
                    url=link,
                    snippet=snippet,
                    content_mode="k_politics_google_news_snippet_only",
                    source_type="K-POLITICS",
                    insight_type="korean_politics"
                )
            )

        time.sleep(2)

    return dedupe(items)[:MAX_K_POLITICS_NEWS]


def fetch_k_politics_gdelt_news() -> list[FeedItem]:
    items: list[FeedItem] = []

    for query in K_POLITICS_GDELT_QUERIES:
        params = {
            "query": query,
            "mode": "ArtList",
            "format": "json",
            "maxrecords": 50,
            "sort": "HybridRel",
            "timespan": f"{K_POLITICS_MAX_AGE_DAYS * 24}h"
        }

        print(f"[INFO] K-POLITICS GDELT query: {query}")

        try:
            data = http_get_json(GDELT_ENDPOINT, params)
        except Exception as exc:
            print(f"[WARN] K-POLITICS GDELT query failed: {exc}")
            continue

        articles = data.get("articles", [])
        print(f"[INFO] K-POLITICS GDELT articles: {len(articles)}")

        for article in articles:
            title = clean_text(article.get("title") or article.get("name") or "")
            url = normalize_url(article.get("url") or article.get("url_mobile") or article.get("link") or "")

            if not title or not url:
                continue

            snippet = limit_text(article.get("snippet") or article.get("description") or title)

            if not is_k_politics_relevant(title, snippet):
                continue

            country = clean_text(
                article.get("sourceCountry")
                or article.get("sourcecountry")
                or article.get("source_country")
                or "South Korea"
            )
            source = clean_text(
                article.get("sourceCommonName")
                or article.get("sourcecommonname")
                or article.get("domain")
                or "Unknown"
            )
            published_at = parse_gdelt_date(article.get("seendate"))

            items.append(
                FeedItem(
                    id=stable_id("k-politics-gdelt", url, title),
                    type="news",
                    region=infer_region(country) if country else "Asia",
                    country=country or "South Korea",
                    source=source,
                    published_at=published_at,
                    title=title,
                    url=url,
                    snippet=snippet,
                    content_mode="k_politics_gdelt_snippet_only",
                    source_type="K-POLITICS",
                    insight_type="korean_politics"
                )
            )

        time.sleep(5)

    return dedupe(items)[:MAX_K_POLITICS_NEWS]


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
        abstract = limit_text(entry.findtext("atom:summary", default="", namespaces=ns), 900)
        published_at = clean_text(entry.findtext("atom:published", default="", namespaces=ns))
        url = normalize_url(clean_text(entry.findtext("atom:id", default="", namespaces=ns)))
        if not is_recent_enough(published_at, PAPER_MAX_AGE_DAYS, allow_unknown=True):
            continue
        authors = [clean_text(a.findtext("atom:name", default="", namespaces=ns)) for a in entry.findall("atom:author", ns)]
        authors = [a for a in authors if a]
        pdf_url = ""
        for link in entry.findall("atom:link", ns):
            if link.attrib.get("title") == "pdf" or link.attrib.get("type") == "application/pdf":
                pdf_url = normalize_url(link.attrib.get("href", ""))
                break
        if not title or not url:
            continue
        items.append(FeedItem(stable_id("paper", url, title), "paper", "Global", "", "arXiv", published_at, title, url, abstract=abstract, authors=authors, pdf_url=pdf_url, content_mode="open_abstract", source_type="arXiv"))
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
    print(
        f"Items: {len(items)} / "
        f"News: {len(news)} / "
        f"GDELT: {len(gdelt_news)} / "
        f"RSS: {len(rss_news)} / "
        f"K-INVEST: {len(k_invest_news)} / "
        f"K-POLITICS: {len(k_politics_news)} / "
        f"Papers: {len(papers)}"
    )


if __name__ == "__main__":
    main()
