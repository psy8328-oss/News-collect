"""중복 제거 (PRD 4.2절, F-11 / F-12).

Google News RSS 링크는 news.google.com 리다이렉트 주소라서, 네이버가 주는 원문 URL과
같은 기사여도 URL이 다르다. 그래서 URL 비교만으로는 부족하고 제목 유사도 비교가 꼭 필요하다.
"""
from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from rapidfuzz import fuzz, process

# 0~100. 이 값 이상이면 같은 기사로 본다.
# 실측(11-10)에서 90~94 구간에 같은 사건 기사가 여럿 있어 90을 유지한다.
# 대신 짧은 제목에서 두 글자 차이로 반대 뜻 기사("파업 돌입"/"파업 철회")가 합쳐지지 않도록
# 반대말 쌍이 갈리는 제목은 합치지 않는다 (4단계 검토 #3).
TITLE_SIMILARITY_THRESHOLD = 90

# 한쪽 제목에만 앞말이, 다른 쪽에만 뒷말이 있으면 다른 기사로 본다.
OPPOSITE_WORDS = [
    ("돌입", "철회"), ("상승", "하락"), ("인상", "인하"), ("증가", "감소"), ("확대", "축소"),
    ("급등", "급락"), ("강세", "약세"), ("흑자", "적자"), ("재개", "중단"), ("가결", "부결"),
    ("승인", "불허"), ("합의", "결렬"), ("반등", "반락"), ("증산", "감산"), ("완화", "강화"),
]

# URL에서 지워도 기사가 바뀌지 않는 추적용 파라미터
_TRACKING_PARAMS = {"fbclid", "gclid", "igshid", "ref", "oc", "from", "cmpid", "mc_cid", "mc_eid"}
_TRACKING_PREFIXES = ("utm_",)

# 제목 맨 앞·맨 뒤의 말머리만 지운다: [단독], (종합2보), [미국 인사이트 11월 2주차], [포스코] 등.
# 제목 중간 괄호는 내용의 일부이므로 남긴다 ("포스코(POSCO)" vs "포스코(KG스틸)", 4단계 검토 #3).
_BRACKET = r"[\[\(【<〈《][^\]\)】>〉》]{1,20}[\]\)】>〉》]"
_LEADING_BRACKETS_RE = re.compile(rf"^\s*(?:{_BRACKET}\s*)+")
_TRAILING_BRACKETS_RE = re.compile(rf"(?:\s*{_BRACKET})+\s*$")
_NON_WORD_RE = re.compile(r"[^0-9A-Za-z가-힣]+")


def normalize_url(url: str) -> str:
    """대소문자·www·추적 파라미터·끝의 / ·#조각을 정리한 비교용 URL."""
    parts = urlsplit(url.strip())
    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in _TRACKING_PARAMS and not k.lower().startswith(_TRACKING_PREFIXES)
    ]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), host, path, urlencode(sorted(query)), ""))


def normalize_title(title: str) -> str:
    """말머리·특수문자·공백을 지운 비교용 제목."""
    t = _LEADING_BRACKETS_RE.sub("", title or "")
    t = _TRAILING_BRACKETS_RE.sub("", t)
    return _NON_WORD_RE.sub("", t).lower()


def _opposite(a: str, b: str) -> bool:
    """두 (정규화된) 제목이 반대말 쌍으로 갈리는지."""
    for x, y in OPPOSITE_WORDS:
        if (x in a and y in b and x not in b and y not in a) or (y in a and x in b and y not in b and x not in a):
            return True
    return False


def _merge(keep: dict, other: dict) -> dict:
    """같은 기사 두 건을 하나로 합친다.

    - 스니펫은 더 긴 쪽 (Google News는 스니펫이 비어 있고 네이버는 있다)
    - URL은 원문 주소를 우선 (Google News 리다이렉트 주소보다 네이버의 원문 주소가 낫다)
    - 언론사는 도메인(예: hankyung.com)보다 언론사명(예: 한국경제)을 우선, 비어 있으면 무조건 채움
    - URL을 바꾸면 id·provider도 그 기사 것으로 바꾼다 (URL과 출처 정보가 어긋나지 않게)
    - 발행일시는 더 이른 쪽, 매칭 키워드·providers는 합친다
    """
    if len(other.get("snippet") or "") > len(keep.get("snippet") or ""):
        keep["snippet"] = other["snippet"]
    if "news.google.com" in keep.get("url", "") and "news.google.com" not in other.get("url", ""):
        keep["url"] = other["url"]
        keep["id"] = other["id"]
        if other.get("provider"):
            keep["provider"] = other["provider"]
    keep_src, other_src = keep.get("source") or "", other.get("source") or ""
    if other_src and (not keep_src or ("." in keep_src and "." not in other_src)):
        keep["source"] = other_src
    times = [t for t in (keep.get("published_at"), other.get("published_at")) if t]
    keep["published_at"] = min(times) if times else None
    for field in ("keywords", "categories", "providers"):
        merged = list(dict.fromkeys((keep.get(field) or []) + (other.get(field) or [])))
        if merged:
            keep[field] = merged
    return keep


def _ensure_providers(articles: list[dict]) -> None:
    for a in articles:
        a.setdefault("providers", [a["provider"]] if a.get("provider") else [])


def dedup_by_url(articles: list[dict]) -> list[dict]:
    """F-11: 정규화한 URL이 같은 기사를 하나로 합친다. 처음 나온 순서를 유지한다."""
    _ensure_providers(articles)
    seen: dict[str, dict] = {}
    for art in articles:
        key = normalize_url(art["url"])
        if key in seen:
            _merge(seen[key], art)
        else:
            seen[key] = art
    return list(seen.values())


def dedup_by_title(articles: list[dict], threshold: int = TITLE_SIMILARITY_THRESHOLD) -> list[dict]:
    """F-12: 정규화한 제목의 유사도가 threshold 이상이면 같은 기사로 묶는다."""
    _ensure_providers(articles)
    kept: list[dict] = []
    kept_titles: list[str] = []
    for art in articles:
        norm = normalize_title(art["title"])
        if not norm:
            kept.append(art)
            kept_titles.append("")  # 비교 대상에서 사실상 제외
            continue
        candidates = process.extract(norm, kept_titles, scorer=fuzz.ratio, score_cutoff=threshold, limit=5)
        match = next((c for c in candidates if not _opposite(norm, c[0])), None)
        if match is not None:
            _merge(kept[match[2]], art)
        else:
            kept.append(art)
            kept_titles.append(norm)
    return kept


def dedup(articles: list[dict], threshold: int = TITLE_SIMILARITY_THRESHOLD) -> list[dict]:
    return dedup_by_title(dedup_by_url(articles), threshold)
