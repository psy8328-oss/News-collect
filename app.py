"""철강·원자재 뉴스 앱.

- 저장된 날짜별 수집 결과를 점수순으로 보여준다 (F-41). 상위 5건은 '주요 뉴스'로 따로.
- 사이드바: 날짜·분야·최소 점수·검색어 필터와 초기화 (F-42, F-45), 지금 수집 버튼 (F-43).
- 마지막 수집 시각·건수 (F-44), CSV 내려받기 (F-33).
화면 조각(HTML)은 ui/components.py, 스타일은 ui/style.py 에 있다.
"""
from __future__ import annotations

from datetime import date

import streamlit as st

from core import collector, now_kst, store
from ui import components as c
from ui import fmt
from ui.export import to_csv_bytes
from ui.style import CSS

st.set_page_config(page_title="철강·원자재 뉴스", page_icon="📰", layout="wide")
st.html(CSS)

TOP_N = 5        # 주요 뉴스 개수
PAGE_SIZE = 20   # '더 보기' 한 번에 늘어나는 기사 수 (첫 화면 로딩 시간을 줄이려고 30→20, 4단계 검토 #7)

# 위젯의 session_state 키
K_DAY, K_CATS, K_MIN, K_QUERY, K_SHOWN = "f_day", "f_categories", "f_min_score", "f_query", "shown"


@st.cache_data(show_spinner=False)
def load_day(day_iso: str, mtime: float) -> dict:
    """JSON 읽기 캐시. 파일이 바뀌면(mtime) 다시 읽는다."""
    return store.load(date.fromisoformat(day_iso))


@st.cache_data(show_spinner=False)
def category_names() -> list[str]:
    return [cat["name"] for cat in collector.load_categories()]


def reset_filters() -> None:
    # on_click 콜백은 위젯을 그리기 전에 실행되므로 위젯 값을 바꿀 수 있다.
    st.session_state[K_CATS] = []
    st.session_state[K_MIN] = 0.0
    st.session_state[K_QUERY] = ""
    st.session_state[K_SHOWN] = PAGE_SIZE


def show_more() -> None:
    st.session_state[K_SHOWN] = st.session_state.get(K_SHOWN, PAGE_SIZE) + PAGE_SIZE


def run_manual_collect() -> None:
    bar = st.sidebar.progress(0.0, text="수집 준비 중…")
    with st.spinner("최근 24시간 뉴스를 수집하는 중입니다. 1분 정도 걸립니다…"):
        try:
            payload = collector.collect(
                trigger=collector.TRIGGER_MANUAL,
                log=lambda *_: None,
                progress=lambda done, total: bar.progress(done / total, text=f"수집 중 {done}/{total}"),
            )
        finally:
            bar.empty()
    st.session_state["manual_payload"] = payload
    # 위젯이 이미 그려진 뒤에는 key 값을 바꿀 수 없으므로, 다음 실행 때 반영한다.
    st.session_state["pending_view"] = "manual"


# ================================================================ 사이드바
dates = store.list_dates()
manual_payload = st.session_state.get("manual_payload")

with st.sidebar:
    view = "saved"
    if manual_payload:
        if "pending_view" in st.session_state:
            st.session_state["view"] = st.session_state.pop("pending_view")
        view = st.radio(
            "보기", ["saved", "manual"], key="view",
            format_func=lambda v: "저장된 수집분 (매일 07시)" if v == "saved" else "수동 수집 결과 (저장 안 됨)",
        )

    payload, day = None, None
    if dates:
        # 보기(저장분/수동)를 오가도 고른 날짜가 유지되도록, 같은 key의 위젯을 항상 그린다 (4단계 검토 #12).
        if st.session_state.get(K_DAY) not in dates:
            st.session_state.pop(K_DAY, None)
        day = st.selectbox("날짜", dates, key=K_DAY, format_func=fmt.day_short, disabled=view == "manual",
                           help="수동 수집 결과를 보는 동안에는 날짜를 바꿀 수 없습니다." if view == "manual" else None)
    else:
        st.selectbox("날짜", ["저장된 날짜 없음"], disabled=True)

    if view == "manual":
        payload = manual_payload
    elif day is not None:
        try:
            payload = load_day(day.isoformat(), store.path_for(day).stat().st_mtime)
        except (OSError, ValueError) as exc:  # 문법 오류(JSONDecodeError)·형식 오류(InvalidPayload) 모두 ValueError
            st.error(f"{fmt.day_short(day)} 파일을 읽지 못했습니다: {exc}")

    articles_all = payload["articles"] if payload else []
    max_score = max((float(a["score"]) for a in articles_all), default=0.0)
    slider_max = max(max_score, 1.0)
    st.session_state.setdefault(K_MIN, 0.0)
    if st.session_state[K_MIN] > slider_max:  # 날짜를 바꿔 최대 점수가 줄어든 경우
        st.session_state[K_MIN] = 0.0

    st.multiselect("분야", category_names(), key=K_CATS, placeholder="전체 분야")
    st.slider("최소 점수", 0.0, slider_max, step=0.5, key=K_MIN)
    st.text_input("제목 검색", key=K_QUERY, placeholder="예: 감산, 포스코")
    st.button("필터 초기화", on_click=reset_filters, width="stretch")

    st.divider()
    st.caption("7시 이후 새 기사가 궁금할 때")
    if st.button("지금 수집", type="primary", width="stretch",
                 help="최근 24시간 뉴스를 지금 수집합니다. 결과는 화면에만 보이고 저장되지 않습니다."):
        run_manual_collect()
        st.rerun()

# ================================================================ 본문
now = now_kst()

if payload is None:
    st.html(c.header("철강·원자재 뉴스", fmt.day_long(now.date()), "", {}))
    if dates:  # 파일은 있는데 읽지 못한 경우
        st.html(c.empty("이 날짜의 수집 결과를 읽을 수 없습니다.",
                            "다른 날짜를 골라 보세요."))
    else:
        st.html(c.empty("아직 수집된 뉴스가 없습니다.",
                            "매일 아침 7시에 자동으로 수집됩니다. 지금 보려면 사이드바의 '지금 수집'을 누르세요."))
    st.stop()

meta = payload["meta"]
counts = meta.get("counts", {})
window = meta.get("window", {})

if view == "manual":
    day_label = "수동 수집 결과"
else:
    day_label = fmt.day_long(day)
meta_line = (
    f"{fmt.clock(meta.get('collected_at'))} 수집 · 기사 {len(articles_all)}건 · "
    f"범위 {fmt.clock(window.get('start'))} ~ {fmt.clock(window.get('end'))}"
)
category_counts = {name: sum(name in a["categories"] for a in articles_all) for name in category_names()}
st.html(c.header("철강·원자재 뉴스", day_label, meta_line, category_counts))

if view == "manual":
    st.html(c.banner("수동 수집 결과입니다. 저장되지 않으며, 페이지를 새로 고치면 사라집니다. "
                         "사이드바의 '보기'에서 저장된 수집분으로 돌아갈 수 있습니다."))
if meta.get("errors") or meta.get("warnings"):
    n_err = len(meta.get("errors", []))
    label = f"수집 상태: 오류 {n_err}건" if n_err else "수집 상태: 참고 사항"
    with st.expander(label, expanded=False):
        for w in meta.get("warnings", []):
            st.write(f"- {w}")
        for err in meta.get("errors", []):
            st.text(f"{err.get('provider')} / {err.get('keyword')}: {err.get('message')}")
        if n_err:
            st.caption("오류가 난 검색어만 빠졌고, 나머지는 정상 수집되었습니다.")

# ---------------------------------------------------------------- 필터 적용
selected = st.session_state[K_CATS]
min_score = st.session_state[K_MIN]
query = st.session_state[K_QUERY].strip()
filtered = [
    a for a in articles_all
    if float(a["score"]) >= min_score
    and (not selected or set(a["categories"]) & set(selected))
    and (not query or query.lower() in a["title"].lower())
]

# 필터가 바뀌면 '더 보기' 개수를 처음으로 돌린다.
signature = (view, str(day), tuple(selected), min_score, query)
if st.session_state.get("filter_sig") != signature:
    st.session_state["filter_sig"] = signature
    st.session_state[K_SHOWN] = PAGE_SIZE

filter_note = []
if selected:
    filter_note.append("분야: " + ", ".join(selected))
if min_score > 0:
    filter_note.append(f"{min_score:g}점 이상")
if query:
    filter_note.append(f"검색: {query}")

if not articles_all:
    st.html(c.empty("이 수집분에는 관련 기사가 없습니다.",
                        "검색 결과가 모두 수집 범위 밖이었거나 키워드와 맞지 않았습니다."))
    st.stop()

if not filtered:
    st.html(c.empty("조건에 맞는 기사가 없습니다.",
                        " · ".join(filter_note) + " — 필터를 바꾸거나 초기화해 보세요."))
    st.button("필터 초기화", on_click=reset_filters, key="reset_main")
    st.stop()

# ---------------------------------------------------------------- 목록
col_n, col_csv = st.columns([3, 1], vertical_alignment="center")
col_n.html(c.section(f"{len(filtered)}건", " · ".join(filter_note) or "점수 높은 순"))
col_csv.download_button(
    # 누를 때만 CSV를 만든다 (페이지를 열 때마다 만들지 않도록, 4단계 검토 #7)
    "CSV 내려받기", lambda rows=filtered: to_csv_bytes(rows),
    file_name=f"steel_news_{(meta.get('collected_at') or '')[:10]}{'_manual' if view == 'manual' else ''}.csv",
    mime="text/csv", width="stretch",
)

top, rest = filtered[:TOP_N], filtered[TOP_N:]
st.html(c.section("주요 뉴스", f"상위 {len(top)}건"))
st.html(c.card_list(top, now, top=True))

if rest:
    shown = st.session_state.get(K_SHOWN, PAGE_SIZE)
    st.html(c.section("전체 기사", f"{min(shown, len(rest))} / {len(rest)}건 표시"))
    st.html(c.card_list(rest[:shown], now))
    if shown < len(rest):
        st.button(f"더 보기 ({len(rest) - shown}건 남음)", on_click=show_more, width="stretch")
