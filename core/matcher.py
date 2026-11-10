"""키워드 매칭과 제외어 필터 (PRD 3.1절, F-13).

어떤 검색어로 수집됐는지와 관계없이, 기사 제목·스니펫에 실제로 들어 있는 키워드를 찾아
keywords / categories 를 채운다. 제목·스니펫에 어떤 키워드도 없는 기사는 관련 없는 기사로 본다.

[제외어 두 종류]
- 가리기형: 제외어 안에 그 분야 키워드가 들어 있는 경우 (예: 회사 분야 '포스코퓨처엠' ⊃ '포스코',
  운임 분야 '택배 운임' ⊃ '운임'). 그 표현만 지우고 나머지 텍스트로 다시 매칭한다.
  → "포스코 3분기 실적… 포스코퓨처엠 부진" 은 '포스코'가 따로 있으므로 회사 분야로 남는다.
- 거부형: 그 밖의 제외어 (예: 회사 분야 '상임위'). 기사에 있으면 그 분야를 통째로 뺀다.
  → "NSC 상임위원회 개최" 는 회사 분야에서 빠진다.
어느 쪽이든 그 분야에만 적용하고, 다른 분야 매칭에는 영향을 주지 않는다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache


@dataclass
class CategoryMatch:
    name: str
    weight: float
    keywords: list[str]          # 실제로 걸린 키워드
    in_title: bool               # 이 분야 키워드가 하나라도 제목에 있는지


def _is_ascii_word(keyword: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9 ]+", keyword))


@lru_cache(maxsize=None)
def _pattern(keyword: str) -> re.Pattern:
    """키워드 검색용 정규식.

    - 키워드 안의 띄어쓰기는 있어도 없어도 된다 ('철강 가격' = '철강가격').
    - 기사 텍스트의 띄어쓰기는 지우지 않는다. 지우면 "현대제철 강관" 이 '철강'으로,
      "이후 판매" 가 '후판'으로 잘못 걸린다 (4단계 검토 #1).
    - 영문 약어(BHP, NSC, BDI, Vale)는 다른 영단어의 일부로 걸리지 않게 앞뒤가 영문·숫자가 아닐 때만,
      대소문자는 무시한다.
    """
    words = [re.escape(w) for w in keyword.split()]
    body = r"\s*".join(words)
    if _is_ascii_word(keyword):
        return re.compile(rf"(?<![A-Za-z0-9]){body}(?![A-Za-z0-9])", re.IGNORECASE)
    return re.compile(body)


def contains(text: str, keyword: str) -> bool:
    """text 안에 keyword가 있는지."""
    if not text or not keyword or not keyword.strip():
        return False
    return bool(_pattern(keyword).search(text))


def _mask(text: str, terms: list[str]) -> str:
    """가리기형 제외어를 지운다. 지운 자리에는 공백을 넣어 앞뒤 글자가 붙지 않게 한다."""
    for term in terms:
        text = _pattern(term).sub(" ", text)
    return text


def _split_excludes(cat: dict) -> tuple[list[str], list[str]]:
    """제외어를 (가리기형, 거부형)으로 나눈다."""
    keywords = cat.get("keywords") or []
    mask, veto = [], []
    for ex in cat.get("exclude") or []:
        (mask if any(contains(ex, kw) for kw in keywords) else veto).append(ex)
    return mask, veto


def match_categories(title: str, snippet: str, categories: list[dict]) -> list[CategoryMatch]:
    """분야별로 실제 매칭된 키워드를 찾는다. 제외어 처리 방식은 모듈 설명 참고."""
    result = []
    for cat in categories:
        mask, veto = _split_excludes(cat)
        if any(contains(f"{title} {snippet}", ex) for ex in veto):
            continue
        t, s = _mask(title, mask), _mask(snippet, mask)
        hits, in_title = [], False
        for kw in cat.get("keywords") or []:
            if contains(t, kw):
                hits.append(kw)
                in_title = True
            elif contains(s, kw):
                hits.append(kw)
        if hits:
            result.append(CategoryMatch(cat["name"], float(cat.get("weight", 1)), hits, in_title))
    return result


def apply_matches(articles: list[dict], categories: list[dict]) -> tuple[list[dict], int]:
    """각 기사에 keywords/categories 를 채우고, 매칭되는 분야가 없는 기사는 뺀다.

    돌려주는 값: (남은 기사 목록, 뺀 기사 수)
    """
    kept = []
    for art in articles:
        matches = match_categories(art.get("title", ""), art.get("snippet", ""), categories)
        if not matches:
            continue
        art["categories"] = [m.name for m in matches]
        art["keywords"] = list(dict.fromkeys(kw for m in matches for kw in m.keywords))
        art["_matches"] = matches  # 점수 계산용 (저장 전에 지움)
        kept.append(art)
    return kept, len(articles) - len(kept)
