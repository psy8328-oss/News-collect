"""Google News RSS 검색 (한국어·한국 지정). PRD 4.1절 v1 주 소스."""
from __future__ import annotations

import calendar
import html
import re
from datetime import datetime, timezone

import feedparser
import requests

from core import USER_AGENT, make_article_id, to_kst_iso

PROVIDER = "google_news"
RSS_URL = "https://news.google.com/rss/search"
# Google News RSS는 검색어당 최대 100건만 준다. 100건을 받았는데 가장 오래된 기사가 범위 시작보다 새것이면
# 범위 앞부분이 잘린 것이다 (4단계 검토 #2). after:/before: 날짜 연산자는 RSS에서 제대로 동작하지 않았다(실측).
RESULT_CAP = 100
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(_TAG_RE.sub(" ", text or ""))).strip()


def _split_title(title: str, source: str) -> tuple[str, str]:
    """Google News 제목 끝의 ' - 언론사명'을 떼어 (제목, 언론사)로 돌려준다."""
    title = title.strip()
    suffix = f" - {source}"
    if source and title.endswith(suffix):
        # 언론사가 제목에 직접 이름을 붙여 'OO - 머니투데이 - 머니투데이'처럼 두 번 붙는 경우가 있다.
        while title.endswith(suffix):
            title = title[: -len(suffix)].strip()
        return title, source
    # source 태그가 없을 때는 마지막 ' - ' 뒤를 언론사로 본다.
    head, sep, tail = title.rpartition(" - ")
    if sep and head and tail and len(tail) <= 30:
        return head.strip(), source or tail.strip()
    return title, source


def _published(entry) -> str | None:
    parsed = entry.get("published_parsed")  # feedparser가 UTC struct_time으로 준다
    if not parsed:
        return None
    return to_kst_iso(datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc))


def search(query: str, since: datetime | None = None, timeout: float = 10.0) -> list[dict]:
    """since 가 주어지면 Google 검색 연산자 when:2d 로 최근 기사만 요청한다.

    when:1d 는 '실행 시각 기준 24시간'이라, 수집이 07:30에 늦게 돌면 전날 07:00~07:30 기사를 놓친다.
    그래서 넉넉히 2일을 요청하고, 정확한 시간 범위는 collector 에서 거른다.
    """
    q = f"{query} when:2d" if since is not None else query
    resp = requests.get(
        RSS_URL,
        params={"q": q, "hl": "ko", "gl": "KR", "ceid": "KR:ko"},
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
    )
    resp.raise_for_status()
    feed = feedparser.parse(resp.content)
    if feed.bozo and not feed.entries:
        raise ValueError(f"RSS 형식을 읽을 수 없음: {feed.bozo_exception}")

    articles = []
    for entry in feed.entries:
        url = entry.get("link", "").strip()
        raw_title = _strip_html(entry.get("title", ""))
        if not url or not raw_title:
            continue
        source = (entry.get("source") or {}).get("title", "").strip()
        title, source = _split_title(raw_title, source)

        # Google News RSS의 설명은 대부분 '제목 + 언론사' 링크라서 본문 요약이 아니다.
        # 제목과 같은 내용이면 비워 둔다.
        snippet = _strip_html(entry.get("summary", ""))
        if snippet.startswith(title):
            snippet = ""

        articles.append(
            {
                "id": make_article_id(url),
                "title": title,
                "url": url,
                "source": source,
                "published_at": _published(entry),
                "snippet": snippet,
                "provider": PROVIDER,
            }
        )
    return articles
