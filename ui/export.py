"""CSV 내려받기 (F-33).

pandas 대신 표준 라이브러리 csv 를 쓴다. pandas는 하위 모듈이 수천 개라, 불러오기만 해도
Streamlit 파일 감시가 새 세션마다 모듈 목록을 훑는 시간이 크게 늘어 첫 화면이 2초 이상 늦어졌다 (4단계 검토 #7).
"""
from __future__ import annotations

import csv
import io

from ui import fmt

COLUMNS = ["점수", "제목", "언론사", "발행시각", "분야", "키워드", "스니펫", "링크"]

# 엑셀이 수식으로 해석하는 첫 글자. 기사 제목·스니펫은 외부 텍스트라 수식 삽입을 막는다 (4단계 검토 #11).
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def csv_safe(value):
    """글자가 =, +, -, @ 등으로 시작하면 앞에 '를 붙여 엑셀이 수식으로 실행하지 않게 한다."""
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


def to_csv_bytes(articles: list[dict]) -> bytes:
    """화면에 보이는 기사 목록을 CSV로. 엑셀에서 한글이 깨지지 않게 utf-8-sig(BOM)로 인코딩한다."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(COLUMNS)
    for a in articles:
        writer.writerow([
            a.get("score", 0),
            csv_safe(a.get("title", "")),
            csv_safe(a.get("source", "")),
            fmt.clock(a.get("published_at")),
            csv_safe(", ".join(a.get("categories") or [])),
            csv_safe(", ".join(a.get("keywords") or [])),
            csv_safe(a.get("snippet", "")),
            csv_safe(a.get("url", "")),
        ])
    return buf.getvalue().encode("utf-8-sig")
