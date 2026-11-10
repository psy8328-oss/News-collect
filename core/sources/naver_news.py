"""네이버 검색 API (뉴스). PRD 4.1절 v1 보조 소스.

API 키는 환경변수(NAVER_CLIENT_ID, NAVER_CLIENT_SECRET) → st.secrets 순서로 찾는다.
GitHub Actions에서는 환경변수, Streamlit 앱에서는 st.secrets를 쓰게 된다.
"""
from __future__ import annotations

import html
import os
import re
import time
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import requests

from core import USER_AGENT, make_article_id, to_kst_iso

PROVIDER = "naver"
API_URL = "https://openapi.naver.com/v1/search/news.json"
_TAG_RE = re.compile(r"<[^>]+>")


class MissingCredentials(Exception):
    """네이버 API 키가 설정되지 않음."""


def get_credentials() -> tuple[str, str] | None:
    cid = os.environ.get("NAVER_CLIENT_ID", "").strip()
    secret = os.environ.get("NAVER_CLIENT_SECRET", "").strip()
    if cid and secret:
        return cid, secret
    try:  # Streamlit 앱 안에서 실행될 때
        import streamlit as st

        cid = str(st.secrets.get("NAVER_CLIENT_ID", "")).strip()
        secret = str(st.secrets.get("NAVER_CLIENT_SECRET", "")).strip()
        if cid and secret:
            return cid, secret
    except Exception:  # secrets.toml 이 없거나 Streamlit 밖에서 실행
        pass
    return None


def _clean(text: str) -> str:
    """<b> 태그와 &quot; 같은 HTML 엔티티를 제거한다."""
    return re.sub(r"\s+", " ", html.unescape(_TAG_RE.sub("", text or ""))).strip()


def _source_from_url(url: str) -> str:
    """네이버 API는 언론사명을 주지 않으므로 원문 주소의 도메인으로 대신한다."""
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def _published(pub_date: str) -> str | None:
    try:
        return to_kst_iso(parsedate_to_datetime(pub_date))
    except (TypeError, ValueError):
        return None


# 최신순 100건 × 최대 10쪽 (네이버 API의 start 최대값 1000). since 보다 오래된 기사가 나오면 바로 멈추므로
# 기사가 적은 키워드는 1쪽만 읽는다. '포스코'처럼 하루 수백 건인 키워드도 24시간치를 덮기 위해 늘렸다 (4단계 검토 #2).
MAX_PAGES = 10
RESULT_CAP = MAX_PAGES * 100  # 이만큼 받았는데도 범위 시작에 못 미치면 결과가 잘린 것


def search(
    query: str, since: datetime | None = None, timeout: float = 10.0, display: int = 100
) -> list[dict]:
    """최신순으로 검색한다. since 가 주어지면 그보다 오래된 기사가 나올 때까지 최대 MAX_PAGES쪽을 읽는다."""
    creds = get_credentials()
    if creds is None:
        raise MissingCredentials("NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 이 설정되지 않음")
    cid, secret = creds

    items: list[dict] = []
    for page in range(MAX_PAGES if since is not None else 1):
        resp = requests.get(
            API_URL,
            params={"query": query, "display": display, "start": 1 + page * display, "sort": "date"},
            headers={
                "X-Naver-Client-Id": cid,
                "X-Naver-Client-Secret": secret,
                "User-Agent": USER_AGENT,
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        page_items = resp.json().get("items", [])
        items.extend(page_items)
        if len(page_items) < display:
            break
        oldest = _published(page_items[-1].get("pubDate", ""))
        if since is None or oldest is None or datetime.fromisoformat(oldest) < since:
            break
        time.sleep(0.2)

    articles = []
    for item in items:
        url = (item.get("originallink") or item.get("link") or "").strip()
        title = _clean(item.get("title", ""))
        if not url or not title:
            continue
        articles.append(
            {
                "id": make_article_id(url),
                "title": title,
                "url": url,
                "source": _source_from_url(url),
                "published_at": _published(item.get("pubDate", "")),
                "snippet": _clean(item.get("description", "")),
                "provider": PROVIDER,
            }
        )
    return articles
