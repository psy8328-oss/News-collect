"""HTML 조각을 만드는 함수들.

기사 제목·스니펫·언론사·URL은 모두 외부에서 온 텍스트이므로 반드시 html.escape 를 거친다.
app.py 는 이 HTML을 st.html 로 그린다. st.html 도 DOMPurify로 한 번 더 거르지만, 그것에만 기대지 않고
여기서 직접 이스케이프한다 (이전에는 st.markdown(unsafe_allow_html=True)를 썼다).
HTML은 줄바꿈 없이 한 줄로 이어 붙인다. 다시 st.markdown 으로 바꾸더라도 마크다운이 들여쓰기를
코드 블록으로 바꾸지 않게 하기 위해서다.
"""
from __future__ import annotations

from datetime import date, datetime
from html import escape

from ui import fmt
from ui.style import color_for

HIGH_SCORE = 15.0  # 이 점수 이상은 배지를 강조색으로


def e(text) -> str:
    return escape(str(text or ""), quote=True)


def safe_url(url: str) -> str:
    """http(s) 주소만 링크로 쓴다. javascript: 같은 주소는 막는다."""
    url = (url or "").strip()
    return e(url) if url.lower().startswith(("http://", "https://")) else "#"


def dot(category: str) -> str:
    return f'<span class="nc-dot" style="background:{color_for(category)}"></span>'


def tag(category: str) -> str:
    return f'<span class="nc-tag">{dot(category)}{e(category)}</span>'


def score_badge(score: float) -> str:
    cls = "nc-score high" if score >= HIGH_SCORE else "nc-score"
    return f'<span class="{cls}" title="관련도 점수">{score:g}점</span>'


def header(title: str, day_label: str, meta_line: str, category_counts: dict[str, int]) -> str:
    summary = "".join(
        f"<span>{dot(name)}{e(name)} <b>{n}</b></span>"
        for name, n in category_counts.items() if n
    )
    return (
        f'<div class="nc-header"><h1>{e(title)}</h1>'
        f'<p class="nc-date">{e(day_label)}</p>'
        f'<p class="nc-meta">{e(meta_line)}</p>'
        + (f'<div class="nc-summary" aria-label="분야별 기사 수">{summary}</div>' if summary else "")
        + "</div>"
    )


def section(title: str, note: str = "") -> str:
    return f'<div class="nc-section">{e(title)}' + (f"<small>{e(note)}</small>" if note else "") + "</div>"


def card(article: dict, now: datetime, top: bool = False) -> str:
    cats = article.get("categories") or []
    border = color_for(cats[0]) if cats else "#8A94A3"
    rel = fmt.relative(article.get("published_at"), now)
    when = fmt.clock(article.get("published_at"))
    info = " · ".join(p for p in [
        e(article.get("source") or "언론사 미상"),
        f"{e(rel)} ({e(when)})" if rel else e(when),
    ] if p)
    snippet = article.get("snippet") or ""
    keywords = ", ".join(article.get("keywords") or [])
    return (
        f'<div class="nc-card{" top" if top else ""}" style="border-left-color:{border}">'
        f'<div class="nc-title"><a href="{safe_url(article.get("url", ""))}" target="_blank" '
        f'rel="noopener noreferrer">{e(article.get("title"))}</a></div>'
        f'<div class="nc-info">{info}</div>'
        + (f'<div class="nc-snippet">{e(snippet)}</div>' if snippet else "")
        + f'<div class="nc-tags">{score_badge(float(article.get("score") or 0))}'
        + "".join(tag(c) for c in cats)
        + (f'<span class="nc-kw">키워드: {e(keywords)}</span>' if keywords else "")
        + "</div></div>"
    )


def card_list(articles: list[dict], now: datetime, top: bool = False) -> str:
    return '<div class="nc-list">' + "".join(card(a, now, top) for a in articles) + "</div>"


def empty(title: str, detail: str = "") -> str:
    return f'<div class="nc-empty"><b>{e(title)}</b><span>{e(detail)}</span></div>'


def banner(text: str) -> str:
    return f'<div class="nc-banner">{e(text)}</div>'


def day_label(d: date) -> str:
    return fmt.day_long(d)
