"""관련도 점수 계산 (PRD 4.3절, F-21)."""
from __future__ import annotations

from datetime import datetime, timedelta

from core.matcher import CategoryMatch

TITLE_FACTOR = 2.0
SNIPPET_FACTOR = 1.0
FRESH_6H_BONUS = 2.0
FRESH_24H_BONUS = 1.0
MULTI_CATEGORY_BONUS = 1.0


def recency_bonus(published_at: datetime | None, reference: datetime) -> float:
    """최신성 보너스. reference 기준 6시간 이내 +2, 24시간 이내 +1.

    reference 는 수집 범위의 끝이다 (자동 수집 = 당일 07:00, 수동 수집 = 실행 시각).
    화면을 연 시각이나 실제 실행 시각이 아니므로, Actions가 늦게 돌아도 같은 파일의 점수는 같다.
    """
    if published_at is None:
        return 0.0
    age = reference - published_at
    if age <= timedelta(hours=6):
        return FRESH_6H_BONUS
    if age <= timedelta(hours=24):
        return FRESH_24H_BONUS
    return 0.0


def score(matches: list[CategoryMatch], published_at: datetime | None, reference: datetime) -> float:
    """점수 = Σ(분야 가중치 × 위치 계수) + 최신성 보너스 + 다중 분야 보너스

    [같은 분야의 키워드가 여러 개 걸린 경우]
    분야당 한 번만 더한다. 위치 계수는 그 분야 키워드 중 하나라도 제목에 있으면 ×2, 아니면 ×1.
    예) '철광석 가격 급등' 은 '철광석'과 '철광석 가격'이 둘 다 걸리지만 철광석 분야 5×2 = 10 한 번만.
    키워드마다 더하면 '철광석'처럼 확장 키워드가 겹치는 분야가 부당하게 높아지기 때문이다.

    [다중 분야 보너스] 서로 다른 분야가 2개 이상 걸리면 +1.
    """
    total = sum(
        m.weight * (TITLE_FACTOR if m.in_title else SNIPPET_FACTOR) for m in matches
    )
    total += recency_bonus(published_at, reference)
    if len({m.name for m in matches}) >= 2:
        total += MULTI_CATEGORY_BONUS
    return round(total, 2)
