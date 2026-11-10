"""뉴스 수집·추천 앱의 핵심 로직 (화면과 무관한 부분)."""
from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# 모든 날짜·시각은 한국 시간 기준으로 다룬다 (PRD: 매일 07:00 KST 수집).
KST = ZoneInfo("Asia/Seoul")

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 브라우저가 아닌 프로그램이라는 것을 숨기지 않되, 일반적인 형태의 User-Agent를 쓴다.
USER_AGENT = "Mozilla/5.0 (compatible; SteelNewsCollector/0.1)"


def now_kst() -> datetime:
    return datetime.now(KST)


def to_kst_iso(dt: datetime | None) -> str | None:
    """datetime을 KST 기준 ISO 8601 문자열로 바꾼다. 시간대가 없으면 UTC로 간주한다."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(KST).isoformat(timespec="seconds")


def make_article_id(url: str) -> str:
    """URL 해시로 기사 ID를 만든다 (PRD 7.1절)."""
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
