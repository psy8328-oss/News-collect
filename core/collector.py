"""수집 파이프라인 (PRD 6장).

실행:
    python -m core.collector              # 자동 수집 (전날 07:00 ~ 당일 07:00 KST), 파일 저장
    python -m core.collector --manual     # 지금부터 24시간 이내, 화면 출력만 (저장 안 함)

순서: 키워드 로드 → 두 소스 검색(F-01) → 시간 범위 필터(F-05) → 중복 제거(F-11, F-12)
     → 키워드 매칭·제외어(F-13) → 점수 계산(F-21) → 점수순 정렬 → 저장(F-31)
"""
from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

import yaml

from core import KST, PROJECT_ROOT, now_kst, store
from core.dedup import dedup_by_title, dedup_by_url
from core.matcher import apply_matches
from core.scorer import score
from core.sources import google_news, naver_news

CONFIG_PATH = PROJECT_ROOT / "config" / "keywords.yaml"
REQUEST_INTERVAL_SEC = 0.4  # 같은 소스에 연달아 요청할 때 간격 (PRD 5장 크롤링 예절)
CUTOFF_HOUR = 7  # 자동 수집 기준 시각 (KST)

TRIGGER_SCHEDULE = "schedule"
TRIGGER_MANUAL = "manual"


def load_categories(path: Path = CONFIG_PATH) -> list[dict]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    categories = data.get("categories") or []
    for cat in categories:
        cat.setdefault("weight", 1)
        cat["keywords"] = [str(k) for k in cat.get("keywords") or []]
        cat["exclude"] = [str(k) for k in cat.get("exclude") or []]
    return categories


def collection_window(trigger: str, collected_at: datetime) -> tuple[datetime, datetime]:
    """F-05: 수집 대상 기사의 발행 시각 범위 [start, end).

    - 자동 수집: 수집한 날(KST)의 07:00 을 끝으로 하는 24시간.
      예) 11-11 07:12 에 실행 → 11-10 07:00 ~ 11-11 07:00.
      GitHub Actions 가 늦게 돌아도 범위가 같으므로, 날마다 빈틈·겹침 없이 이어진다.
      07:00 전에 수동으로 돌린 경우에는 끝을 실행 시각으로 둔다.
    - 수동 수집: 실행 시각 기준 최근 24시간.
    """
    collected_at = collected_at.astimezone(KST)
    if trigger == TRIGGER_MANUAL:
        return collected_at - timedelta(hours=24), collected_at
    end = collected_at.replace(hour=CUTOFF_HOUR, minute=0, second=0, microsecond=0)
    end = min(end, collected_at)
    start = end.replace(hour=CUTOFF_HOUR, minute=0, second=0, microsecond=0) - timedelta(days=1)
    return start, end


def _parse(iso: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(iso) if iso else None
    except ValueError:
        return None


def filter_window(articles: list[dict], start: datetime, end: datetime) -> list[dict]:
    """발행 시각이 [start, end) 안인 기사만 남긴다. 발행 시각을 모르는 기사는 확인할 수 없으므로 뺀다."""
    return [a for a in articles if (t := _parse(a.get("published_at"))) and start <= t < end]


def truncated(found: list[dict], cap: int, start: datetime) -> bool:
    """소스의 건수 상한까지 받았는데 가장 오래된 기사가 범위 시작보다 새것이면, 범위 앞부분이 잘린 것이다."""
    if len(found) < cap:
        return False
    times = [t for a in found if (t := _parse(a.get("published_at")))]
    return bool(times) and min(times) > start


def process(raw: list[dict], categories: list[dict], start: datetime, end: datetime) -> tuple[list[dict], dict]:
    """수집한 기사를 거르고·합치고·점수를 매긴다. (기사 목록, 단계별 건수)를 돌려준다.

    최신성 보너스는 수집 범위의 끝(end)을 기준으로 계산한다. 자동 수집은 실행이 늦어져도 end가
    07:00으로 고정이라 점수가 실행 시각에 흔들리지 않고, 수동 수집은 end = 실행 시각이다 (4단계 검토 #4).
    """
    in_window = filter_window(raw, start, end)
    after_url = dedup_by_url(in_window)
    after_title = dedup_by_title(after_url)
    matched, unmatched = apply_matches(after_title, categories)
    for art in matched:
        art["score"] = score(art.pop("_matches"), _parse(art.get("published_at")), end)
    matched.sort(key=lambda a: (a["score"], a.get("published_at") or ""), reverse=True)
    counts = {
        "raw": len(raw),
        "in_window": len(in_window),
        "after_url_dedup": len(after_url),
        "after_dedup": len(after_title),
        "no_keyword_match": unmatched,
        "final": len(matched),
    }
    return matched, counts


def collect(trigger: str = TRIGGER_SCHEDULE, categories: list[dict] | None = None,
            log=print, progress=None) -> dict:
    """모든 분야·키워드를 두 소스에서 검색해 PRD 7.1절 형식의 payload를 돌려준다.

    한 소스나 한 키워드가 실패해도 나머지는 계속 수집하고, 실패는 meta.errors에 쌓는다.
    progress(done, total) 콜백이 있으면 진행률을 알려준다 (화면의 진행 막대용).
    """
    categories = categories if categories is not None else load_categories()
    collected_at = now_kst()
    start, end = collection_window(trigger, collected_at)
    errors: list[dict] = []
    warnings: list[str] = []
    provider_counts: Counter = Counter()
    raw: list[dict] = []

    sources = [(google_news.PROVIDER, google_news.search, google_news.RESULT_CAP)]
    if naver_news.get_credentials():
        sources.append((naver_news.PROVIDER, naver_news.search, naver_news.RESULT_CAP))
    else:
        msg = "네이버 API 키가 없어 네이버 뉴스는 건너뜀 (Google News만 수집)"
        warnings.append(msg)
        log(f"[경고] {msg}")

    # 같은 검색어가 두 분야에 있어도 한 번만 검색한다.
    queries = list(dict.fromkeys(kw for cat in categories for kw in cat["keywords"]))
    total, done = len(queries) * len(sources), 0
    truncated_queries: dict[str, list[str]] = {}
    for keyword in queries:
        for provider, search, cap in sources:
            try:
                found = search(keyword, since=start)
            except Exception as exc:  # 네트워크 오류, 응답 형식 오류 등
                errors.append({"provider": provider, "keyword": keyword,
                               "message": f"{type(exc).__name__}: {exc}"[:300]})
                log(f"[오류] {provider} / {keyword}: {type(exc).__name__}")
                found = []
            if truncated(found, cap, start):
                truncated_queries.setdefault(provider, []).append(keyword)
            raw.extend(found)
            provider_counts[provider] += len(found)
            done += 1
            if progress:
                progress(done, total)
            time.sleep(REQUEST_INTERVAL_SEC)

    for provider, kws in truncated_queries.items():
        msg = (f"{provider}: 검색 결과 상한에 걸려 범위 앞부분 기사가 빠졌을 수 있는 검색어 {len(kws)}개 "
               f"({', '.join(kws[:8])}{' 등' if len(kws) > 8 else ''})")
        warnings.append(msg)
        log(f"[경고] {msg}")

    articles, stage_counts = process(raw, categories, start, end)
    category_counts = Counter(c for a in articles for c in a["categories"])

    return {
        "meta": {
            "collected_at": collected_at.isoformat(timespec="seconds"),
            "finished_at": now_kst().isoformat(timespec="seconds"),
            "trigger": trigger,
            "window": {"start": start.isoformat(timespec="seconds"),
                       "end": end.isoformat(timespec="seconds")},
            "counts": {**{p: provider_counts[p] for p, _, _ in sources}, **stage_counts},
            "category_counts": {c["name"]: category_counts.get(c["name"], 0) for c in categories},
            "errors": errors,
            "warnings": warnings,
        },
        "articles": articles,
    }


def main(argv: list[str] | None = None) -> int:
    # Windows 콘솔/파이프에서도 한글이 깨지지 않게
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="철강·원자재 뉴스 수집")
    parser.add_argument("--manual", action="store_true",
                        help="최근 24시간 기준으로 수집하고 결과만 출력 (파일 저장 안 함, F-04와 같은 동작)")
    args = parser.parse_args(argv)
    trigger = TRIGGER_MANUAL if args.manual else TRIGGER_SCHEDULE

    print(f"수집 시작: {now_kst():%Y-%m-%d %H:%M:%S} KST ({trigger})")
    payload = collect(trigger=trigger)
    meta = payload["meta"]
    print(f"수집 범위: {meta['window']['start']} ~ {meta['window']['end']}")

    print("\n[단계별 건수]")
    for name, n in meta["counts"].items():
        print(f"  {name:<18} {n:>5}")
    print("\n[분야별 기사 수 (한 기사가 여러 분야에 속할 수 있음)]")
    for name, n in meta["category_counts"].items():
        print(f"  {name:<8} {n:>5}")
    print(f"\n오류 {len(meta['errors'])}건, 경고 {len(meta['warnings'])}건")

    print("\n[점수 상위 10건]")
    for a in payload["articles"][:10]:
        print(f"  {a['score']:>5.1f}  {'/'.join(a['categories'])}  {a['title'][:60]}")

    if args.manual:
        print("\n수동 수집은 저장하지 않습니다.")
        return 0 if payload["articles"] else 1
    if not payload["articles"]:
        # 모두 실패했을 때 기존 파일을 빈 결과로 덮어쓰지 않는다. GitHub Actions에서 실패로 보이게 한다.
        print("수집된 기사가 0건이라 저장하지 않습니다.")
        return 1
    path = store.save(payload)
    print(f"저장: {path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
