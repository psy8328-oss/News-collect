"""수집 결과를 data/YYYY-MM-DD.json 으로 저장하고 읽는다 (PRD 4.4절, 7.1절)."""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path

from core import KST, PROJECT_ROOT

DATA_DIR = PROJECT_ROOT / "data"
_FILE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\.json$")


def path_for(day: date, data_dir: Path = DATA_DIR) -> Path:
    return data_dir / f"{day.isoformat()}.json"


def save(payload: dict, data_dir: Path = DATA_DIR) -> Path:
    """payload 의 meta.collected_at(KST) 날짜로 파일 이름을 정해 저장한다.

    GitHub Actions 서버는 UTC이므로 KST 07:00 = UTC 전날 22:00 이다.
    파일 날짜는 반드시 KST로 변환한 뒤의 날짜를 쓴다.
    """
    collected_at = datetime.fromisoformat(payload["meta"]["collected_at"])
    day = collected_at.astimezone(KST).date()
    data_dir.mkdir(parents=True, exist_ok=True)
    path = path_for(day, data_dir)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)  # 쓰다가 실패해도 기존 파일이 깨지지 않게
    return path


class InvalidPayload(ValueError):
    """JSON 문법은 맞지만 형식(meta + articles)이 어긋난 파일."""


def normalize_payload(payload) -> dict:
    """형식을 검사하고 빠진 필드를 기본값으로 채운다 (4단계 검토 #6).

    - 최상위가 dict가 아니거나 articles가 리스트가 아니면 InvalidPayload.
    - 기사 중 dict가 아니거나 제목·URL이 없는 항목은 버린다.
    - 그 밖의 필드(score, categories, keywords 등)는 기본값으로 채워 화면이 KeyError로 멈추지 않게 한다.
    """
    if not isinstance(payload, dict) or not isinstance(payload.get("articles"), list):
        raise InvalidPayload("파일 형식이 올바르지 않습니다 (meta/articles 구조가 아님)")
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    articles = []
    for a in payload["articles"]:
        if not isinstance(a, dict) or not a.get("title") or not a.get("url"):
            continue
        try:
            a_score = float(a.get("score") or 0)
        except (TypeError, ValueError):
            a_score = 0.0
        articles.append({
            **a,
            "title": str(a["title"]),
            "url": str(a["url"]),
            "source": str(a.get("source") or ""),
            "snippet": str(a.get("snippet") or ""),
            "score": a_score,
            "categories": [str(c) for c in a.get("categories") or [] if c],
            "keywords": [str(k) for k in a.get("keywords") or [] if k],
        })
    for key in ("errors", "warnings"):
        if not isinstance(meta.get(key), list):
            meta[key] = []
    for key in ("counts", "window"):
        if not isinstance(meta.get(key), dict):
            meta[key] = {}
    return {"meta": meta, "articles": articles}


def load(day: date, data_dir: Path = DATA_DIR) -> dict:
    """파일을 읽어 형식을 검사한다. 문법 오류는 json.JSONDecodeError, 형식 오류는 InvalidPayload (둘 다 ValueError)."""
    return normalize_payload(json.loads(path_for(day, data_dir).read_text(encoding="utf-8")))


def list_dates(data_dir: Path = DATA_DIR) -> list[date]:
    """저장된 날짜 목록 (최신순)."""
    if not data_dir.exists():
        return []
    days = []
    for p in data_dir.iterdir():
        if _FILE_RE.match(p.name):
            try:
                days.append(date.fromisoformat(p.stem))
            except ValueError:
                continue
    return sorted(days, reverse=True)
