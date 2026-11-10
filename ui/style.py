"""커스텀 CSS (한 곳에 모아 둔다).

- Streamlit 내부 클래스명(st-emotion-cache-*)에 의존하지 않고, 우리가 만든 nc-* 클래스만 꾸민다.
- 라이트/다크 모드 모두에서 읽히도록 글자색은 테마 글자색을 그대로 물려받고(inherit),
  배경·테두리는 반투명 색만 쓴다. 분야 색은 점·왼쪽 띠에만 쓰고 분야명은 글자로 함께 적는다.
"""
from __future__ import annotations

# 분야별 색. 서로 구분되는 색상(hue)으로 고르되, 색만으로 구분하지 않도록 태그에는 항상 분야명을 적는다.
CATEGORY_COLORS = {
    "철강": "#4F7CAC",      # 강철 청회색
    "철광석": "#B5533C",    # 녹·적철광
    "원료탄": "#6E7781",    # 석탄 회색
    "중국 정책": "#D1453B",  # 적색
    "철강 투자": "#2F8F5B",  # 녹색
    "철스크랩": "#9A7440",   # 갈색
    "운임": "#1A8FA3",      # 청록 (바다)
    "회사": "#7B61B0",      # 보라
}
DEFAULT_COLOR = "#8A94A3"


def color_for(category: str) -> str:
    return CATEGORY_COLORS.get(category, DEFAULT_COLOR)


CSS = """
<style>
/* ---------- 헤더 ---------- */
.nc-header { margin: 0 0 0.75rem 0; }
.nc-header h1 { font-size: 1.9rem; line-height: 1.25; margin: 0 0 0.25rem 0; padding: 0; }
.nc-header .nc-date { font-size: 1.1rem; font-weight: 600; margin: 0; }
.nc-header .nc-meta { font-size: 0.9rem; opacity: 0.72; margin: 0.15rem 0 0 0; }
.nc-summary { display: flex; flex-wrap: wrap; gap: 0.35rem 0.9rem; margin: 0.6rem 0 0 0;
  font-size: 0.9rem; }
.nc-summary span { white-space: nowrap; }

/* ---------- 분야 점 / 태그 / 점수 배지 ---------- */
.nc-dot { display: inline-block; width: 0.6rem; height: 0.6rem; border-radius: 50%;
  margin-right: 0.3rem; vertical-align: 0.05rem; }
.nc-tag { display: inline-flex; align-items: center; font-size: 0.78rem; line-height: 1.2;
  padding: 0.15rem 0.5rem; border-radius: 999px; border: 1px solid rgba(128,128,128,0.35);
  background: rgba(128,128,128,0.08); white-space: nowrap; }
.nc-score { display: inline-block; font-size: 0.78rem; font-weight: 700; line-height: 1.2;
  padding: 0.15rem 0.5rem; border-radius: 999px; white-space: nowrap;
  background: rgba(79,124,172,0.16); border: 1px solid rgba(79,124,172,0.45); }
.nc-score.high { background: rgba(209,69,59,0.14); border-color: rgba(209,69,59,0.5); }

/* ---------- 섹션 제목 ---------- */
.nc-section { font-size: 1.15rem; font-weight: 700; margin: 1.2rem 0 0.5rem 0; }
.nc-section small { font-weight: 400; opacity: 0.65; font-size: 0.85rem; margin-left: 0.4rem; }

/* ---------- 기사 카드 ---------- */
.nc-list { display: flex; flex-direction: column; gap: 0.6rem; }
.nc-card { border: 1px solid rgba(128,128,128,0.28); border-left-width: 4px; border-radius: 0.5rem;
  padding: 0.7rem 0.9rem; background: rgba(128,128,128,0.035); min-width: 0; }
.nc-card.top { padding: 0.9rem 1rem; background: rgba(79,124,172,0.06); }
.nc-title { font-size: 1.02rem; font-weight: 650; line-height: 1.45; margin: 0 0 0.3rem 0;
  overflow-wrap: anywhere; word-break: keep-all; }
.nc-card.top .nc-title { font-size: 1.12rem; }
.nc-title a { color: inherit !important; text-decoration: none; }
.nc-title a:hover { text-decoration: underline; }
.nc-info { font-size: 0.83rem; opacity: 0.75; margin: 0 0 0.35rem 0; overflow-wrap: anywhere; }
.nc-snippet { font-size: 0.9rem; line-height: 1.5; opacity: 0.88; margin: 0 0 0.45rem 0;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
  overflow-wrap: anywhere; }
.nc-tags { display: flex; flex-wrap: wrap; gap: 0.3rem; align-items: center; }
.nc-kw { font-size: 0.78rem; opacity: 0.65; overflow-wrap: anywhere; }

/* ---------- 상태 안내 ---------- */
.nc-empty { border: 1px dashed rgba(128,128,128,0.45); border-radius: 0.5rem; padding: 1.2rem 1rem;
  text-align: center; margin: 0.8rem 0; }
.nc-empty b { display: block; font-size: 1.02rem; margin-bottom: 0.3rem; }
.nc-empty span { opacity: 0.75; font-size: 0.9rem; }
.nc-banner { border-radius: 0.5rem; padding: 0.6rem 0.9rem; margin: 0.5rem 0; font-size: 0.9rem;
  border: 1px solid rgba(214,150,30,0.55); background: rgba(214,150,30,0.12); }

/* ---------- 모바일 ---------- */
@media (max-width: 640px) {
  .nc-header h1 { font-size: 1.45rem; }
  .nc-header .nc-date { font-size: 1rem; }
  .nc-card, .nc-card.top { padding: 0.65rem 0.75rem; }
  .nc-title, .nc-card.top .nc-title { font-size: 1rem; }
}
</style>
"""
