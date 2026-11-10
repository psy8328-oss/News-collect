"""날짜·시각 표시 형식."""
from __future__ import annotations

from datetime import date, datetime

from core import KST

WEEKDAYS = "월화수목금토일"


def parse(iso: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(iso).astimezone(KST) if iso else None
    except ValueError:
        return None


def day_short(d: date) -> str:
    """2026-11-10 (화)"""
    return f"{d:%Y-%m-%d} ({WEEKDAYS[d.weekday()]})"


def day_long(d: date) -> str:
    """2026년 11월 10일 (화)"""
    return f"{d.year}년 {d.month}월 {d.day}일 ({WEEKDAYS[d.weekday()]})"


def clock(iso: str | None, with_date: bool = True) -> str:
    dt = parse(iso)
    if dt is None:
        return "-"
    return dt.strftime("%m-%d %H:%M" if with_date else "%H:%M")


def relative(iso: str | None, now: datetime) -> str:
    """'3시간 전' 형식. 일주일이 넘으면 빈 문자열."""
    dt = parse(iso)
    if dt is None:
        return ""
    sec = (now - dt).total_seconds()
    if sec < 60:
        return "방금"
    if sec < 3600:
        return f"{int(sec // 60)}분 전"
    if sec < 86400:
        return f"{int(sec // 3600)}시간 전"
    if sec < 7 * 86400:
        return f"{int(sec // 86400)}일 전"
    return ""
