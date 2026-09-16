"""
쇼핑검색광고 대시보드 - 공통 스타일 & 카드 컴포넌트
레퍼런스 디자인(다크 사이드바 + 카드형 KPI + 전주비/전월비/전년비 배지) 반영
"""

import re
import textwrap
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

ACCENT = "#2563EB"
SIDEBAR_BG = "#0F172A"
SIDEBAR_TEXT = "#CBD5E1"
SIDEBAR_TEXT_MUTED = "#64748B"
CARD_BG = "#FFFFFF"
PAGE_BG = "#F5F7FA"
UP_COLOR = "#16A34A"    # 증가 = 초록
DOWN_COLOR = "#DC2626"  # 감소 = 빨강


def inject_css(pin_filters: bool = True):
    """pin_filters=True면 상단 필터 영역을 스크롤해도 항상 보이게 고정한다(position:fixed).
    False면 일반 흐름대로 배치해 스크롤하면 같이 넘어간다 — 필터가 대시보드 영역을 가릴 때
    사이드바에서 끌 수 있게 만든 옵션."""
    pin_css = ("""
    div.st-key-page1_filters, div.st-key-page3_filters, div.st-key-page4_filters {
        position: fixed !important;
        top: 3.7rem;
        left: 22rem;
        right: 5rem;
        width: auto !important;
        z-index: 999;
        background: """ + PAGE_BG + """;
        padding: 10px 14px 8px 14px;
        border-bottom: 1px solid #E5E9F0;
        border-radius: 0 0 8px 8px;
        box-shadow: 0 2px 6px rgba(15, 23, 42, 0.06);
    }
    div.st-key-page1_filters + div {
        margin-top: 130px;
    }
    div.st-key-page3_filters + div, div.st-key-page4_filters + div {
        margin-top: 205px;
    }
    """) if pin_filters else ("""
    div.st-key-page1_filters, div.st-key-page3_filters, div.st-key-page4_filters {
        background: """ + PAGE_BG + """;
        padding: 10px 14px 8px 14px;
        border-bottom: 1px solid #E5E9F0;
        border-radius: 8px;
        margin-bottom: 10px;
    }
    """)
    st.markdown(textwrap.dedent(f"""
    <style>
    .stApp {{
        background-color: {PAGE_BG};
    }}
    section[data-testid="stSidebar"] {{
        background-color: {SIDEBAR_BG};
    }}
    section[data-testid="stSidebar"] * {{
        color: {SIDEBAR_TEXT} !important;
    }}
    section[data-testid="stSidebar"] hr {{
        border-color: #1E293B !important;
    }}
    section[data-testid="stSidebar"] .stRadio label span {{
        font-size: 0.92rem;
    }}
    section[data-testid="stSidebar"] div[role="radiogroup"] label {{
        padding: 6px 10px;
        border-radius: 8px;
        margin-bottom: 2px;
    }}
    section[data-testid="stSidebar"] div[role="radiogroup"] label:hover {{
        background-color: #1E293B;
    }}

    .eyebrow {{
        color: {ACCENT};
        font-size: 0.8rem;
        font-weight: 600;
        letter-spacing: 0.03em;
        margin-bottom: 2px;
    }}
    .page-title {{
        font-size: 1.7rem;
        font-weight: 700;
        color: #0F172A;
        margin-bottom: 2px;
    }}
    .page-sub {{
        color: #64748B;
        font-size: 0.88rem;
        margin-bottom: 18px;
    }}

    .kpi-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
        gap: 12px;
        margin-bottom: 8px;
    }}
    .kpi-card {{
        background: {CARD_BG};
        border: 1px solid #E5E9F0;
        border-radius: 12px;
        padding: 16px 18px;
        min-width: 0;
    }}
    .kpi-label {{
        color: #64748B;
        font-size: 0.8rem;
        font-weight: 600;
        margin-bottom: 6px;
    }}
    .kpi-value {{
        color: #0F172A;
        font-size: 1.55rem;
        font-weight: 700;
        margin-bottom: 10px;
        white-space: nowrap;
    }}
    .kpi-deltas {{
        display: flex;
        flex-direction: column;
        gap: 3px;
    }}
    .kpi-delta-row {{
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        gap: 6px;
        font-size: 0.8rem;
        line-height: 1.5;
    }}
    .kpi-delta-label {{
        color: #64748B;
        white-space: nowrap;
        flex-shrink: 0;
    }}
    .kpi-delta-value {{
        font-weight: 600;
        white-space: nowrap;
    }}
    .kpi-delta-value.up {{
        color: {UP_COLOR};
    }}
    .kpi-delta-value.down {{
        color: {DOWN_COLOR};
    }}
    .kpi-delta-value.flat {{
        color: #64748B;
        font-weight: 400;
    }}
    .kpi-delta-prev {{
        color: #94A3B8;
        font-weight: 400;
        margin-left: 3px;
        white-space: nowrap;
    }}
    .kpi-footnote {{
        color: #94A3B8;
        font-size: 0.72rem;
        margin-top: 6px;
    }}

    /* 카테고리 거래액 추이 분석 카드 (container key로 감싼 영역 전체에 카드 배경 적용) */
    div.st-key-cat_trend_card {{
        background: {CARD_BG};
        border: 1px solid #E5E9F0;
        border-radius: 14px;
        padding: 20px 22px 4px 22px;
        margin-bottom: 18px;
    }}
    div.st-key-cat_trend_card div[role="radiogroup"] {{
        gap: 4px;
    }}
    div.st-key-cat_trend_card div[role="radiogroup"] label {{
        background: #F1F5F9;
        border-radius: 8px;
        padding: 4px 12px;
        margin-right: 2px;
    }}
    div.st-key-cat_trend_card div[role="radiogroup"] label[data-selected="true"] {{
        background: {ACCENT};
    }}
    div.st-key-cat_trend_card div[role="radiogroup"] label[data-selected="true"] p {{
        color: white !important;
    }}
    div.st-key-cat_trend_card div[role="radiogroup"] label > div > div > div:first-child {{
        display: none;
    }}
    div.st-key-cat_trend_card div[role="radiogroup"] label {{
        transition: background-color 0.15s ease;
        cursor: pointer;
    }}

    /* 알약형 라디오 탭 — container key를 "pill_"로 시작하게 감싸면 어디서든 재사용 가능 */
    div[class*="st-key-pill_"] div[role="radiogroup"] {{
        gap: 4px;
        flex-wrap: wrap;
    }}
    div[class*="st-key-pill_"] div[role="radiogroup"] label {{
        background: #F1F5F9;
        border-radius: 8px;
        padding: 4px 12px;
        margin-right: 2px;
        transition: background-color 0.15s ease;
        cursor: pointer;
    }}
    div[class*="st-key-pill_"] div[role="radiogroup"] label[data-selected="true"] {{
        background: {ACCENT};
    }}
    div[class*="st-key-pill_"] div[role="radiogroup"] label[data-selected="true"] p {{
        color: white !important;
    }}
    div[class*="st-key-pill_"] div[role="radiogroup"] label > div > div > div:first-child {{
        display: none;
    }}

    /* 01페이지 '지표 선택' 알약 중 앞쪽 9개(핵심 지표)를 나머지와 다른 색으로 강조 */
    div.st-key-pill_trend_metric div[role="radiogroup"] label:nth-child(-n+9) {{
        background: #EFF6FF;
        border: 1px solid #BFDBFE;
    }}
    div.st-key-pill_trend_metric div[role="radiogroup"] label:nth-child(-n+9) p {{
        color: {ACCENT};
        font-weight: 700;
    }}
    div.st-key-pill_trend_metric div[role="radiogroup"] label[data-selected="true"]:nth-child(-n+9) {{
        background: {ACCENT};
        border-color: {ACCENT};
    }}
    div.st-key-pill_trend_metric div[role="radiogroup"] label[data-selected="true"]:nth-child(-n+9) p {{
        color: white !important;
    }}

    /* 범용 카드 래퍼 — container key를 "card_"로 시작하게 감싸면 흰 배경 카드로 렌더링 */
    div[class*="st-key-card_"] {{
        background: {CARD_BG};
        border: 1px solid #E5E9F0;
        border-radius: 14px;
        padding: 18px 20px 14px 20px;
        margin-bottom: 18px;
    }}
    div[class*="st-key-card_"] .section-title {{
        margin-top: 0;
    }}

    .trend-card-header {{
        display: flex; align-items: center; gap: 10px; margin-bottom: 2px;
    }}
    .trend-card-icon {{
        width: 34px; height: 34px; border-radius: 10px; background: #EFF6FF; color: {ACCENT};
        display: flex; align-items: center; justify-content: center; font-size: 1.1rem; flex-shrink: 0;
    }}
    .trend-card-title {{
        font-size: 1.1rem; font-weight: 700; color: #0F172A;
    }}
    .trend-card-sub {{
        font-size: 0.8rem; color: #64748B; margin: 2px 0 6px 44px;
    }}
    .trend-summary-grid {{
        display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin: 10px 0 16px 0;
    }}
    .trend-summary-box {{
        background: #F8FAFC; border: 1px solid #E5E9F0; border-radius: 10px; padding: 14px 16px;
        display: flex; gap: 10px; align-items: flex-start;
    }}
    .trend-summary-icon {{
        font-size: 1.1rem; flex-shrink: 0;
    }}
    .trend-summary-title {{
        font-size: 0.8rem; font-weight: 700; color: #0F172A; margin-bottom: 4px;
    }}
    .trend-summary-text {{
        font-size: 0.82rem; color: #475569; line-height: 1.55;
    }}

    .insight-box {{
        background: #EFF6FF;
        border: 1px solid #BFDBFE;
        border-left: 4px solid {ACCENT};
        border-radius: 10px;
        padding: 14px 18px;
        margin: 4px 0 20px 0;
    }}
    .insight-box.tone-danger {{
        background: #FEF2F2;
        border-color: #FECACA;
        border-left-color: {DOWN_COLOR};
    }}
    .insight-box.tone-success {{
        background: #F0FDF4;
        border-color: #BBF7D0;
        border-left-color: {UP_COLOR};
    }}
    .insight-title {{
        font-size: 0.8rem;
        font-weight: 700;
        color: {ACCENT};
        letter-spacing: 0.02em;
        margin-bottom: 8px;
    }}
    .insight-box.tone-danger .insight-title {{
        color: {DOWN_COLOR};
    }}
    .insight-box.tone-success .insight-title {{
        color: {UP_COLOR};
    }}
    .insight-line {{
        font-size: 0.88rem;
        color: #1E293B;
        line-height: 1.6;
        margin-bottom: 4px;
    }}
    .insight-line:last-child {{
        margin-bottom: 0;
    }}

    .kpi-tier-label {{
        color: #94A3B8;
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.02em;
        margin: 14px 0 6px 0;
    }}
    .kpi-grid-sm {{
        grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
        gap: 10px;
    }}
    .kpi-card-sm {{
        padding: 11px 14px;
    }}
    .kpi-card-sm .kpi-value {{
        font-size: 1.15rem;
        margin-bottom: 6px;
    }}
    .kpi-card-sm .kpi-label {{
        font-size: 0.72rem;
        margin-bottom: 4px;
    }}
    .kpi-card-sm .kpi-delta-row {{
        font-size: 0.72rem;
    }}

    .summary-note {{
        color: #64748B;
        font-size: 0.8rem;
        margin: 10px 0 6px 0;
    }}
    .section-title {{
        font-size: 1.02rem;
        font-weight: 700;
        color: #0F172A;
        border-left: 4px solid {ACCENT};
        padding-left: 8px;
        margin: 22px 0 10px 0;
    }}

    /* 필터 영역 안 st.columns() 행이 좁은 화면에서 줄바꿈되면(1줄→2~3줄) 박스 높이가
    늘어나서, 고정(fixed) 모드일 때 아래 margin-top과 안 맞아 본문과 겹치는 문제가 있었다.
    각 필터 행을 항상 한 줄로 고정(필요하면 가로 스크롤)해서 높이를 예측 가능하게 만든다. */
    div.st-key-page1_filters [data-testid="stHorizontalBlock"],
    div.st-key-page3_filters [data-testid="stHorizontalBlock"],
    div.st-key-page4_filters [data-testid="stHorizontalBlock"] {{
        flex-wrap: nowrap !important;
        overflow-x: auto;
    }}
    div.st-key-page1_filters [data-testid="stColumn"],
    div.st-key-page3_filters [data-testid="stColumn"],
    div.st-key-page4_filters [data-testid="stColumn"] {{
        flex-shrink: 0;
        min-width: fit-content;
    }}

    /* 상단 필터 영역 고정 여부 (사이드바 "필터 고정" 토글로 전환) */
    {pin_css}

    /* 비교표(render_comparison_table) — st.dataframe은 셀 일부만 스타일링을 못 해서
    (예: "▲21.4% (48.2백만)"에서 %만 색칠, 괄호값은 회색) raw HTML 테이블로 대체 */
    .dtbl-wrap {{
        overflow-x: auto;
        margin-bottom: 8px;
        border: 1px solid #E5E9F0;
        border-radius: 10px;
    }}
    table.dtbl {{
        width: 100%;
        border-collapse: collapse;
        font-size: 0.84rem;
    }}
    table.dtbl thead th {{
        background: #F8FAFC;
        color: #475569;
        font-weight: 600;
        text-align: left;
        padding: 8px 12px;
        border-bottom: 1px solid #E5E9F0;
        white-space: nowrap;
    }}
    table.dtbl tbody td {{
        padding: 7px 12px;
        border-bottom: 1px solid #F1F5F9;
        color: #0F172A;
        white-space: nowrap;
    }}
    table.dtbl tbody tr:last-child td {{
        border-bottom: none;
    }}
    table.dtbl tbody tr.dtbl-bold td {{
        font-weight: 700;
        background: #F1F5F9;
    }}
    .dtbl-delta {{
        font-weight: 600;
    }}
    .dtbl-delta.up {{ color: {UP_COLOR}; }}
    .dtbl-delta.down {{ color: {DOWN_COLOR}; }}
    .dtbl-delta.flat {{ color: #64748B; font-weight: 400; }}
    .dtbl-ref {{
        color: #94A3B8;
        font-weight: 400;
    }}
    </style>
    """), unsafe_allow_html=True)


def _delta_row(label: str, pct, prev_str: str = None) -> str:
    prev_html = f'<span class="kpi-delta-prev">({prev_str})</span>' if prev_str else ""
    if pct is None or pd.isna(pct):
        return (
            '<div class="kpi-delta-row">'
            f'<span class="kpi-delta-label">{label}</span>'
            f'<span class="kpi-delta-value flat">- {prev_html}</span>'
            '</div>'
        )
    cls = "up" if pct > 0 else ("down" if pct < 0 else "flat")
    arrow = "▲" if pct > 0 else ("▼" if pct < 0 else "-")
    return (
        '<div class="kpi-delta-row">'
        f'<span class="kpi-delta-label">{label}</span>'
        f'<span class="kpi-delta-value {cls}">{arrow} {abs(pct):.1f}% {prev_html}</span>'
        '</div>'
    )


def render_kpi_cards(cards: list, size: str = "lg", tier_label: str = None):
    """
    cards: [{
        "label": "거래액", "value": "39.2백만",
        "deltas": [("전주비", 12.3, "34.9백만"), ("전월비", -4.1, "40.9백만"), ("전년비", 8.0, "36.3백만")]
    }, ...]
    각 delta 튜플은 (라벨, 증감률(%), 이전기간 원값 문자열-선택) 형태.
    size="sm"이면 더 작은 보조 카드 스타일로 렌더링(메인 지표와 나머지 지표를 시각적으로 구분할 때 사용).
    tier_label을 주면 카드 그리드 위에 작은 구분 레이블(예: "보조 지표")을 붙인다.
    """
    if tier_label:
        st.markdown(f'<div class="kpi-tier-label">{tier_label}</div>', unsafe_allow_html=True)
    grid_cls = "kpi-grid kpi-grid-sm" if size == "sm" else "kpi-grid"
    card_cls = "kpi-card kpi-card-sm" if size == "sm" else "kpi-card"
    parts = [f'<div class="{grid_cls}">']
    for c in cards:
        rows = "".join(_delta_row(*d) for d in c["deltas"])
        parts.append(
            f'<div class="{card_cls}">'
            f'<div class="kpi-label">{c["label"]}</div>'
            f'<div class="kpi-value">{c["value"]}</div>'
            f'<div class="kpi-deltas">{rows}</div>'
            '</div>'
        )
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


def render_custom_funnel(stages: list, values: list, deltas: list = None, sub_labels: list = None,
                         colors: list = None, weak_index: int = None, weak_note: str = None,
                         yoy_deltas: list = None):
    """단계별 값이 크게 차이나도(예: 노출 vs 구매 1000배) 전 단계가 다 보이도록,
    폭을 실제 값 비율이 아니라 '보기 좋은' 고정 테이퍼로 그리는 커스텀 SVG 퍼널.
    stages: ["노출","클릭","방문(UV)","구매"]
    values: [1399895, 19605, 12479, 154]
    deltas: 각 단계 밑에 표시할 '직전 대비' 문자열 리스트 (없으면 생략)
    sub_labels: 각 단계 값 위에 작게 붙일 라벨(예: "기간 합계") 리스트 (없으면 생략)
    colors: 단계별 색 hex 리스트 (기본 파랑→하늘→주황→초록 진행)
    weak_index: 전환이 가장 부진한 단계의 인덱스 — 도형에 빨간 테두리, 통계 블록에 경고 배지를 붙인다 (없으면 생략)
    weak_note: weak_index 배지 옆에 붙일 짧은 설명 텍스트 (예: "CR 전년비 ▼24.9%")
    yoy_deltas: deltas 밑에 한 줄 더 붙일 전년비 문자열 리스트 (없으면 생략)
    """
    if colors is None:
        colors = ["#2563EB", "#0EA5E9", "#F59E0B", "#22C55E", "#8B5CF6", "#EC4899"]
    n = len(stages)
    width, shape_height = 300, 280
    # weak_index의 "⚠ 부진" 라벨은 도형 아래쪽에 붙는다 — 마지막 단계가 부진일 때 라벨이
    # shape_height를 넘어가 잘려 보이던 문제가 있어, 그 경우 viewBox 높이만 따로 늘려준다
    # (도형 자체 비율은 shape_height 기준 그대로 유지).
    height = shape_height + (22 if weak_index is not None else 0)
    cx = width / 2
    top_margin = 8
    usable_h = shape_height - 2 * top_margin
    seg_h = usable_h / n
    max_hw, min_hw = 135, 22
    half_widths = [max_hw - (max_hw - min_hw) * (i / n) for i in range(n + 1)]

    svg_parts = []
    for i in range(n):
        y0 = top_margin + seg_h * i
        y1 = top_margin + seg_h * (i + 1)
        hw0, hw1 = half_widths[i], half_widths[i + 1]
        points = f"{cx-hw0:.1f},{y0:.1f} {cx+hw0:.1f},{y0:.1f} {cx+hw1:.1f},{y1:.1f} {cx-hw1:.1f},{y1:.1f}"
        color = colors[i % len(colors)]
        stroke = f'stroke="{DOWN_COLOR}" stroke-width="3"' if i == weak_index else ""
        svg_parts.append(f'<polygon points="{points}" fill="{color}" opacity="0.94" {stroke} />')
        label_y = (y0 + y1) / 2
        svg_parts.append(
            f'<text x="{cx:.1f}" y="{label_y:.1f}" text-anchor="middle" dominant-baseline="middle" '
            f'fill="white" font-size="14" font-weight="700">{stages[i]}</text>'
        )
        if i == weak_index:
            svg_parts.append(
                f'<text x="{cx:.1f}" y="{y1 + 12:.1f}" text-anchor="middle" '
                f'fill="{DOWN_COLOR}" font-size="11" font-weight="700">⚠ 부진</text>'
            )
    svg = (
        f'<svg viewBox="0 0 {width} {height}" style="width:100%; max-width:300px; height:auto; display:block;">'
        + "".join(svg_parts) + '</svg>'
    )

    def _delta_color(text: str) -> str:
        if "▲" in text:
            return UP_COLOR
        if "▼" in text:
            return DOWN_COLOR
        return "#64748B"

    _paren_re = re.compile(r"^(.*?)(\s*\([^()]*\))?\s*$")

    def _delta_span(text: str, opacity: float = 1.0) -> str:
        """'전일비 ▲44.2% (95)' 같은 문자열에서 뒤의 '(95)' 비교 기준값만 회색·비볼드로
        분리 렌더링하고, 나머지(▲44.2% 등)만 증감 색상+볼드를 적용한다."""
        m = _paren_re.match(text)
        main = m.group(1).strip() if m else text
        paren = m.group(2).strip() if m and m.group(2) else ""
        opacity_css = f" opacity:{opacity};" if opacity != 1.0 else ""
        html = f'<span style="color:{_delta_color(text)};{opacity_css}">{main}</span>'
        if paren:
            html += f' <span style="color:#94A3B8; font-weight:400;{opacity_css}">{paren}</span>'
        return html

    stat_blocks = []
    for i, (label, val) in enumerate(zip(stages, values)):
        color = colors[i % len(colors)]
        is_weak = i == weak_index
        sub_span = (
            f'<span style="color:#94A3B8; font-size:0.72rem; font-weight:400;">{sub_labels[i]}</span>'
            if sub_labels and i < len(sub_labels) and sub_labels[i] else ""
        )
        has_delta = deltas and i < len(deltas) and deltas[i]
        has_yoy = yoy_deltas and i < len(yoy_deltas) and yoy_deltas[i]
        delta_parts = []
        if has_delta:
            delta_parts.append(_delta_span(deltas[i]))
        if has_yoy:
            delta_parts.append(_delta_span(yoy_deltas[i], opacity=0.85))
        delta_html = (
            f'<div style="font-size:0.76rem; font-weight:600; '
            f'display:flex; gap:8px; flex-wrap:wrap;">{" · ".join(delta_parts)}</div>'
        ) if delta_parts else ""
        weak_badge = (
            f'<span style="background:{DOWN_COLOR}; color:white; font-size:0.68rem; font-weight:700; '
            f'padding:1px 7px; border-radius:10px; margin-left:8px;">⚠ 가장 부진{f" · {weak_note}" if weak_note else ""}</span>'
            if is_weak else ""
        )
        val_str = val if isinstance(val, str) else f"{val:,.0f}"
        block_style = (
            f'border:1px solid {DOWN_COLOR}; background:#FEF2F2; border-radius:8px; padding:7px 10px; margin:2px 0;'
            if is_weak else
            'border-bottom:1px solid #F1F5F9; padding:8px 0;'
        )
        # 라벨+날짜/모드를 한 줄로, 값+증감을 한 줄로 묶어 세로 공간을 줄인다
        # (예전엔 라벨·날짜·값·증감이 각각 한 줄씩 4줄이라 카드가 불필요하게 길었음).
        stat_blocks.append(
            f'<div style="display:flex; align-items:flex-start; gap:10px; {block_style}">'
            f'<div style="width:9px; height:9px; border-radius:50%; background:{color}; '
            'margin-top:6px; flex-shrink:0;"></div>'
            '<div style="flex:1; min-width:0;">'
            '<div style="display:flex; align-items:baseline; gap:6px; flex-wrap:wrap;">'
            f'<span style="color:#64748B; font-size:0.8rem; font-weight:600;">{label}</span>'
            f'{sub_span}{weak_badge}'
            '</div>'
            '<div style="display:flex; align-items:baseline; gap:10px; flex-wrap:wrap; margin-top:2px;">'
            f'<div style="color:#0F172A; font-size:1.2rem; font-weight:700;">{val_str}</div>'
            f'{delta_html}'
            '</div>'
            '</div></div>'
        )

    html = (
        '<div style="display:flex; gap:26px; align-items:center; flex-wrap:wrap; '
        f'background:{CARD_BG}; border:1px solid #E5E9F0; border-radius:12px; padding:20px;">'
        f'<div style="flex-shrink:0; width:280px;">{svg}</div>'
        f'<div style="flex:1; min-width:200px;">{"".join(stat_blocks)}</div>'
        '</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def _md_bold_to_html(text: str) -> str:
    """render_insight_box는 unsafe_allow_html로 직접 렌더링하는 raw HTML이라
    st.markdown의 **볼드** 문법이 자동 변환되지 않는다 — 호출부는 편하게 **강조**를
    쓰게 두고, 여기서 <strong>으로 직접 바꿔준다."""
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)


def _colorize_deltas(text: str) -> str:
    """format_delta_text가 만든 ▲/▼ 증감 표기를 KPI 카드·표와 동일한 초록/빨강으로
    칠해준다 — insight-line은 raw HTML이라 이것도 직접 처리해야 한다."""
    text = re.sub(r"(▲[^\s%]*%?)", rf'<span style="color:{UP_COLOR}; font-weight:600;">\1</span>', text)
    text = re.sub(r"(▼[^\s%]*%?)", rf'<span style="color:{DOWN_COLOR}; font-weight:600;">\1</span>', text)
    return text


def render_colored_caption(text: str):
    """st.caption 대체 — st.caption은 raw HTML을 못 받아 ▲/▼ 증감 표기에 색을 못 입힌다.
    본문에 **볼드**를 써도 되고(자동 <strong> 변환), ▲/▼ 뒤 숫자%는 자동으로 초록/빨강 처리된다."""
    st.markdown(
        f'<div style="color:#64748B; font-size:0.82rem; line-height:1.5; margin:4px 0 14px 0;">'
        f'{_colorize_deltas(_md_bold_to_html(text))}</div>',
        unsafe_allow_html=True,
    )


def render_insight_box(lines: list, title: str = "핵심 요약", tone: str = "info"):
    """규칙 기반 자동 인사이트 박스. lines: 이미 계산된 지표로 만든 짧은 문장 리스트.
    (실시간 LLM 호출 아님 — 매번 같은 데이터면 항상 같은 문장이 나오는 결정적 요약이라
    신뢰도가 높고, API 키·비용·지연이 없다.) lines가 비어있으면 아무것도 그리지 않는다.
    tone: "info"(기본, 파랑) | "danger"(빨강 — 부진/경고용) | "success"(초록 — 우수/개선용)."""
    if not lines:
        return
    icon = {"danger": "⚠️", "success": "✅"}.get(tone, "💡")
    tone_cls = f" tone-{tone}" if tone in ("danger", "success") else ""
    items = "".join(
        f'<div class="insight-line">• {_colorize_deltas(_md_bold_to_html(line))}</div>' for line in lines
    )
    st.markdown(
        f'<div class="insight-box{tone_cls}"><div class="insight-title">{icon} {title}</div>{items}</div>',
        unsafe_allow_html=True,
    )


def render_trend_card_header(icon: str, title: str, sub: str):
    """카테고리 거래액 추이 분석 카드의 상단 아이콘+제목+부제. cat_trend_card 컨테이너 안에서 호출."""
    st.markdown(
        f'<div class="trend-card-header"><div class="trend-card-icon">{icon}</div>'
        f'<div class="trend-card-title">{title}</div></div>'
        f'<div class="trend-card-sub">{sub}</div>',
        unsafe_allow_html=True,
    )


def render_trend_summary_boxes(boxes: list):
    """카드 하단 2단 요약 박스. boxes: [{"icon":"📈","title":"인사이트","text":"..."}, ...] (보통 2개)."""
    parts = ['<div class="trend-summary-grid">']
    for b in boxes:
        parts.append(
            f'<div class="trend-summary-box"><div class="trend-summary-icon">{b["icon"]}</div>'
            f'<div><div class="trend-summary-title">{b["title"]}</div>'
            f'<div class="trend-summary-text">{_colorize_deltas(_md_bold_to_html(b["text"]))}</div></div></div>'
        )
    parts.append('</div>')
    st.markdown("".join(parts), unsafe_allow_html=True)


def render_page_header(eyebrow: str, title: str, sub: str):
    st.markdown(
        f'<div class="eyebrow">{eyebrow}</div>'
        f'<div class="page-title">{title}</div>'
        f'<div class="page-sub">{sub}</div>',
        unsafe_allow_html=True,
    )


def render_section_title(text: str):
    st.markdown(f'<div class="section-title">{text}</div>', unsafe_allow_html=True)


def pct_change(cur, prev):
    if prev is None or pd.isna(prev) or prev == 0:
        return None
    try:
        return (cur - prev) / abs(prev) * 100
    except Exception:
        return None


def format_delta_text(delta) -> str:
    """증감률 텍스트를 카드(KPI)와 동일한 ▲(증가)/▼(감소) 기호로 통일해서 반환.
    0%(변화 없음)는 기호 없이 표기한다."""
    if delta is None or pd.isna(delta):
        return "-"
    if delta > 0:
        return f"▲{delta:.1f}%"
    if delta < 0:
        return f"▼{abs(delta):.1f}%"
    return "0.0%"


def render_comparison_table(df: pd.DataFrame, delta_cols: list, bold_rows: set = None):
    """비교(전년비/전월비 등) 컬럼과 그 옆의 "{컬럼명} 값"(비교대상 실제값) 컬럼을 한 셀로
    합쳐서 raw HTML 테이블로 렌더링한다 — st.dataframe(Styler)은 셀 안 일부만 스타일링을
    못 해서, 지금까지는 "전년비" | "전년비 값" 두 컬럼으로 쪼개 보여줬는데, EP_dashboard의
    render_bpu_comparison_table 방식(raw HTML 테이블)을 가져와 "▲21.4% (48.2백만)"처럼
    한 셀에 색상+회색 참고값을 같이 넣는다.

    df: 이미 표시용으로 포맷된 문자열 컬럼들로 구성 (숫자 포맷/▲▼ 기호 처리는 호출부에서 끝낸 상태).
    delta_cols: "▲21.4%" 같은 문자열이 든 컬럼명 리스트. 같은 이름 뒤에 " 값"이 붙은 컬럼이
        df에 있으면 그 값을 괄호로 묶어 같은 셀에 회색으로 붙이고, 그 " 값" 컬럼 자체는
        별도 열로는 표시하지 않는다.
    bold_rows: 첫 번째 표시 컬럼 값이 이 set에 있는 행을 볼드+음영 처리(예: "합계" 행 강조).
    """
    value_cols = {d: f"{d} 값" for d in delta_cols if f"{d} 값" in df.columns}
    display_cols = [c for c in df.columns if c not in value_cols.values()]

    def _delta_cell(pct_str, val_str) -> str:
        pct_str = "-" if pct_str is None or (isinstance(pct_str, float) and pd.isna(pct_str)) else str(pct_str)
        cls = "up" if pct_str.startswith("▲") else ("down" if pct_str.startswith("▼") else "flat")
        has_val = val_str is not None and not (isinstance(val_str, float) and pd.isna(val_str)) and str(val_str) != "-"
        ref = f' <span class="dtbl-ref">({val_str})</span>' if has_val else ""
        return f'<span class="dtbl-delta {cls}">{pct_str}</span>{ref}'

    header_html = "".join(f"<th>{c}</th>" for c in display_cols)
    body_rows = []
    for _, row in df.iterrows():
        is_bold = bold_rows is not None and row[display_cols[0]] in bold_rows
        tr_cls = ' class="dtbl-bold"' if is_bold else ""
        cells = []
        for c in display_cols:
            if c in value_cols:
                cells.append(f"<td>{_delta_cell(row[c], row[value_cols[c]])}</td>")
            else:
                cells.append(f"<td>{row[c]}</td>")
        body_rows.append(f"<tr{tr_cls}>{''.join(cells)}</tr>")

    st.markdown(
        f'<div class="dtbl-wrap"><table class="dtbl"><thead><tr>{header_html}</tr></thead>'
        f'<tbody>{"".join(body_rows)}</tbody></table></div>',
        unsafe_allow_html=True,
    )


# 월별 실적 비교(연간) 표 기본 지표 세트: (라벨, 분자컬럼, 분모컬럼, 비율여부, 배율, %표시여부, 백만단위여부)
# 비율지표(ROAS/CR/객단가)는 일별 값을 평균하지 않고, 그 달의 분자/분모를 각각 합산한 뒤
# 재계산한다(대시보드 전체에서 쓰는 원칙과 동일).
DEFAULT_MONTHLY_METRICS = [
    ("거래액", "거래액", None, False, 1.0, False, True),
    ("광고비", "광고비", None, False, 1.0, False, True),
    ("ROAS", "거래액", "광고비", True, 100.0, True, False),
    ("UV", "UV", None, False, 1.0, False, False),
    ("결제고객수", "결제고객수", None, False, 1.0, False, False),
    ("CR", "결제고객수", "UV", True, 100.0, True, False),
    ("객단가", "거래액", "결제고객수", True, 1.0, False, False),
]


def render_monthly_comparison_table(df: pd.DataFrame, title: str, metric_defs: list = None, caption_extra: str = ""):
    """올해(1월~최신월) | 전년비 | 전년 월별 실적 비교 매트릭스 (지표×월).
    df: "date" 컬럼 + metric_defs가 참조하는 원본(분자/분모) 컬럼을 가진 일별 데이터
    (이미 원하는 범위로 필터링된 상태여야 함 — 이 함수는 그대로 월별로 합산만 한다).
    진행 중인 당월은 실제 날짜까지의 값만 쓰고, 그 달의 전년비만 '동요일 매칭'
    (올해 실제 존재하는 날짜들을 364일씩 당겨 전년의 그 날짜들만 비교)으로 공정하게 계산한다.
    EP_dashboard의 render_bpu_comparison_table/월별 실적 비교 표와 같은 방식으로, 행을
    클릭하면 강조되는 인터랙션까지 포함해서 iframe(components.html)으로 렌더링한다 —
    부모 문서 CSS를 상속받지 않으므로 필요한 스타일을 이 안에 그대로 넣는다."""
    if metric_defs is None:
        metric_defs = DEFAULT_MONTHLY_METRICS

    st.markdown(f"**{title}**")
    if df is None or df.empty:
        st.info("데이터가 없습니다.")
        return

    d = df.copy()
    d["date"] = pd.to_datetime(d["date"])
    abs_last = d["date"].max()
    cur_year, prev_year, cur_month = abs_last.year, abs_last.year - 1, abs_last.month

    def _monthly_actual(year, num_col, den_col, is_ratio, scale):
        vals = []
        for m in range(1, 13):
            m_start = pd.Timestamp(year, m, 1)
            m_end = (m_start + pd.offsets.MonthBegin(1)) - pd.Timedelta(days=1)
            if m_start > abs_last:
                vals.append(None)
                continue
            md = d[(d["date"] >= m_start) & (d["date"] <= min(m_end, abs_last))]
            if md.empty:
                vals.append(None)
                continue
            if is_ratio:
                den_sum = md[den_col].sum()
                vals.append((md[num_col].sum() / den_sum * scale) if den_sum else None)
            else:
                vals.append(md[num_col].sum())
        return vals

    def _cur_month_yoy_matched(num_col, den_col, is_ratio, scale):
        cur_start = pd.Timestamp(cur_year, cur_month, 1)
        cur_dates = d[(d["date"] >= cur_start) & (d["date"] <= abs_last)]["date"].unique()
        if len(cur_dates) == 0:
            return None, []
        matched = [pd.Timestamp(x) - pd.Timedelta(days=364) for x in cur_dates]
        md = d[d["date"].isin(matched)]
        if md.empty:
            return None, matched
        if is_ratio:
            den_sum = md[den_col].sum()
            return ((md[num_col].sum() / den_sum * scale) if den_sum else None), matched
        return md[num_col].sum(), matched

    def _fmt(v, is_pct, is_million):
        if v is None or pd.isna(v):
            return "-"
        if is_pct:
            return f"{v:.1f}%"
        if is_million:
            return f"{v / 1_000_000:,.1f}백만"
        return f"{v:,.0f}"

    def _delta_span(v):
        if v is None or pd.isna(v):
            return "<span class='delta neutral'>-</span>"
        if v > 0:
            return f"<span class='delta up'>▲{v:.1f}%</span>"
        if v < 0:
            return f"<span class='delta down'>▼{abs(v):.1f}%</span>"
        return "<span class='delta neutral'>0.0%</span>"

    last_day_label = f"~{abs_last.month}/{abs_last.day}"
    CUR_HL = "border-left:2px solid #F59E0B;border-right:2px solid #F59E0B;"
    CUR_HL_TOP = CUR_HL + "border-top:4px solid #F59E0B;"
    CUR_HL_BOTTOM = CUR_HL + "border-bottom:4px solid #F59E0B;"

    _, matched_dates = _cur_month_yoy_matched(metric_defs[0][1], metric_defs[0][2], metric_defs[0][3], metric_defs[0][4])
    if matched_dates:
        p_start, p_end = min(matched_dates), max(matched_dates)
        prev_day_label = f"{p_start.month}/{p_start.day}~{p_end.month}/{p_end.day}"
    else:
        prev_day_label = last_day_label

    def _th(m, day_label=None):
        dl = day_label if day_label is not None else last_day_label
        hl = CUR_HL_TOP if m == cur_month else ""
        lbl = f"{m}월{f'({dl})' if m == cur_month else ''}"
        return f"<th style='white-space:nowrap;{hl}'>{lbl}</th>"

    headers_cur = "".join(_th(m) for m in range(1, cur_month + 1))
    headers_yoy = "".join(_th(m) for m in range(1, cur_month + 1))
    headers_prev = "".join(_th(m, prev_day_label) for m in range(1, cur_month + 1))

    def _td(v, m, is_pct=False, is_million=False, is_delta=False, is_last_row=False):
        if m == cur_month:
            hl = CUR_HL_BOTTOM if is_last_row else CUR_HL
        else:
            hl = ""
        content = _delta_span(v) if is_delta else _fmt(v, is_pct, is_million)
        return f"<td style='text-align:right;white-space:nowrap;{hl}'>{content}</td>"

    rows_html = ""
    for i, (label, num_col, den_col, is_ratio, scale, is_pct, is_million) in enumerate(metric_defs):
        is_last = i == len(metric_defs) - 1
        v_cur = _monthly_actual(cur_year, num_col, den_col, is_ratio, scale)
        v_prev = _monthly_actual(prev_year, num_col, den_col, is_ratio, scale)
        v_prev[cur_month - 1], _ = _cur_month_yoy_matched(num_col, den_col, is_ratio, scale)
        cells_cur = "".join(_td(v_cur[m - 1], m, is_pct, is_million, is_last_row=is_last) for m in range(1, cur_month + 1))
        cells_prev = "".join(_td(v_prev[m - 1], m, is_pct, is_million, is_last_row=is_last) for m in range(1, cur_month + 1))
        cells_yoy = "".join(
            _td(pct_change(v_cur[m - 1], v_prev[m - 1]) if v_cur[m - 1] is not None else None,
                m, is_delta=True, is_last_row=is_last)
            for m in range(1, cur_month + 1)
        )
        rows_html += (
            f"<tr class='mc-row' data-i='{i}'><td class='m' style='white-space:nowrap;'>{label}</td>"
            f"{cells_cur}{cells_yoy}{cells_prev}</tr>"
        )

    n_rows = len(metric_defs)
    frame_h = 76 + n_rows * 30

    doc = f"""
<html><head><style>
  body {{ margin:0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }}
  .mtbl {{ min-width:100%; width:max-content; border-collapse:collapse; font-size:0.72rem;
    background:#fff; border:1px solid #E5E9F0; border-radius:8px; overflow:hidden; table-layout:auto; }}
  .mtbl thead th {{ background:#F8FAFC; color:#475569; font-weight:600; text-align:left;
    padding:4px 6px; border-bottom:1px solid #E5E9F0; font-size:0.66rem; white-space:nowrap; }}
  .mtbl tbody td {{ padding:4px 6px; border-bottom:1px solid #F1F5F9; color:#0F172A; white-space:nowrap; }}
  .mtbl tbody tr:last-child td {{ border-bottom:none; }}
  .mtbl td.m {{ font-weight:500; }}
  .delta.up {{ color:{UP_COLOR}; font-weight:600; }}
  .delta.down {{ color:{DOWN_COLOR}; font-weight:600; }}
  .delta.neutral {{ color:#9ca3af; font-weight:600; }}
  .mc-row {{ cursor:pointer; transition:background .15s; }}
  .mc-row:hover {{ background:#F8FAFC; }}
  .mc-row.sel {{ background:#EFF6FF; }}
  .mc-row.sel td.m {{ color:{ACCENT}; font-weight:700; }}
</style></head><body>
  <div style="overflow-x:auto;"><table class="mtbl">
    <thead>
      <tr><th rowspan="2" style="white-space:nowrap;">구분</th>
      <th colspan="{cur_month}" style="text-align:center;background:#EEF2FF;white-space:nowrap;">{cur_year}년</th>
      <th colspan="{cur_month}" style="text-align:center;background:#FEF3C7;white-space:nowrap;">전년비</th>
      <th colspan="{cur_month}" style="text-align:center;background:#F3F4F6;white-space:nowrap;">{prev_year}년</th></tr>
      <tr>{headers_cur}{headers_yoy}{headers_prev}</tr>
    </thead>
    <tbody>{rows_html}</tbody>
  </table></div>
<script>
(function() {{
  var rows = Array.prototype.slice.call(document.querySelectorAll('.mc-row'));
  rows.forEach(function(r) {{
    r.addEventListener('click', function() {{ r.classList.toggle('sel'); }});
  }});
  function _resizeToContent() {{
    var h = document.body.scrollHeight;
    if (window.frameElement) {{
      window.frameElement.style.height = h + 'px';
      window.frameElement.setAttribute('height', h);
    }}
  }}
  _resizeToContent();
  window.addEventListener('load', _resizeToContent);
  setTimeout(_resizeToContent, 100);
}})();
</script>
</body></html>
"""
    components.html(doc, height=frame_h, scrolling=False)
    cap = "일할계산(마감예상) 없이, 진행 중인 달은 있는 날짜까지의 실제값만 보여줘요. 행을 클릭하면 강조됩니다."
    if caption_extra:
        cap += f" {caption_extra}"
    st.caption(cap)


def delta_cell_style(val: str) -> str:
    """▲(증가)=초록, ▼(감소)=빨강 — 표 전체에서 KPI 카드와 동일한 색 규칙을 쓰기 위한 스타일러."""
    if isinstance(val, str):
        if val.startswith("▲"):
            return f"color: {UP_COLOR}; font-weight: 600;"
        if val.startswith("▼"):
            return f"color: {DOWN_COLOR}; font-weight: 600;"
    return ""
