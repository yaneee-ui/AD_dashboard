"""
쇼핑검색광고 대시보드 - 공통 스타일 & 카드 컴포넌트
레퍼런스 디자인(다크 사이드바 + 카드형 KPI + 전주비/전월비/전년비 배지) 반영
"""

import textwrap
import pandas as pd
import streamlit as st

ACCENT = "#2563EB"
SIDEBAR_BG = "#0F172A"
SIDEBAR_TEXT = "#CBD5E1"
SIDEBAR_TEXT_MUTED = "#64748B"
CARD_BG = "#FFFFFF"
PAGE_BG = "#F5F7FA"
UP_COLOR = "#16A34A"    # 증가 = 초록
DOWN_COLOR = "#DC2626"  # 감소 = 빨강


def inject_css():
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
        grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
        gap: 14px;
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

    /* 상단 필터 영역 고정 (스크롤해도 항상 보이도록) */
    div.st-key-page1_filters, div.st-key-page3_filters {{
        position: fixed !important;
        top: 3.7rem;
        left: 22rem;
        right: 5rem;
        width: auto !important;
        z-index: 999;
        background: {PAGE_BG};
        padding: 10px 14px 8px 14px;
        border-bottom: 1px solid #E5E9F0;
        border-radius: 0 0 8px 8px;
        box-shadow: 0 2px 6px rgba(15, 23, 42, 0.06);
    }}
    div.st-key-page1_filters + div {{
        margin-top: 96px;
    }}
    div.st-key-page3_filters + div {{
        margin-top: 172px;
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


def render_kpi_cards(cards: list):
    """
    cards: [{
        "label": "거래액", "value": "39.2백만",
        "deltas": [("전주비", 12.3, "34.9백만"), ("전월비", -4.1, "40.9백만"), ("전년비", 8.0, "36.3백만")]
    }, ...]
    각 delta 튜플은 (라벨, 증감률(%), 이전기간 원값 문자열-선택) 형태.
    """
    parts = ['<div class="kpi-grid">']
    for c in cards:
        rows = "".join(_delta_row(*d) for d in c["deltas"])
        parts.append(
            '<div class="kpi-card">'
            f'<div class="kpi-label">{c["label"]}</div>'
            f'<div class="kpi-value">{c["value"]}</div>'
            f'<div class="kpi-deltas">{rows}</div>'
            '</div>'
        )
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


def render_custom_funnel(stages: list, values: list, deltas: list = None, sub_labels: list = None,
                         colors: list = None):
    """단계별 값이 크게 차이나도(예: 노출 vs 구매 1000배) 전 단계가 다 보이도록,
    폭을 실제 값 비율이 아니라 '보기 좋은' 고정 테이퍼로 그리는 커스텀 SVG 퍼널.
    stages: ["노출","클릭","방문(UV)","구매"]
    values: [1399895, 19605, 12479, 154]
    deltas: 각 단계 밑에 표시할 '직전 대비' 문자열 리스트 (없으면 생략)
    sub_labels: 각 단계 값 위에 작게 붙일 라벨(예: "기간 합계") 리스트 (없으면 생략)
    colors: 단계별 색 hex 리스트 (기본 파랑→하늘→주황→초록 진행)
    """
    if colors is None:
        colors = ["#2563EB", "#0EA5E9", "#F59E0B", "#22C55E", "#8B5CF6", "#EC4899"]
    n = len(stages)
    width, height = 300, 280
    cx = width / 2
    top_margin = 8
    usable_h = height - 2 * top_margin
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
        svg_parts.append(f'<polygon points="{points}" fill="{color}" opacity="0.94" />')
        label_y = (y0 + y1) / 2
        svg_parts.append(
            f'<text x="{cx:.1f}" y="{label_y:.1f}" text-anchor="middle" dominant-baseline="middle" '
            f'fill="white" font-size="14" font-weight="700">{stages[i]}</text>'
        )
    svg = (
        f'<svg viewBox="0 0 {width} {height}" style="width:100%; max-width:300px; height:auto; display:block;">'
        + "".join(svg_parts) + '</svg>'
    )

    stat_blocks = []
    for i, (label, val) in enumerate(zip(stages, values)):
        color = colors[i % len(colors)]
        sub_html = (
            f'<div style="color:#94A3B8; font-size:0.72rem; margin-top:1px;">{sub_labels[i]}</div>'
            if sub_labels and i < len(sub_labels) and sub_labels[i] else ""
        )
        delta_html = (
            f'<div style="color:#64748B; font-size:0.78rem; margin-top:3px;">{deltas[i]}</div>'
            if deltas and i < len(deltas) and deltas[i] else ""
        )
        val_str = val if isinstance(val, str) else f"{val:,.0f}"
        stat_blocks.append(
            '<div style="display:flex; align-items:flex-start; gap:10px; padding:11px 0; '
            'border-bottom:1px solid #F1F5F9;">'
            f'<div style="width:10px; height:10px; border-radius:50%; background:{color}; '
            'margin-top:7px; flex-shrink:0;"></div>'
            '<div>'
            f'<div style="color:#64748B; font-size:0.82rem; font-weight:600;">{label}</div>'
            f'{sub_html}'
            f'<div style="color:#0F172A; font-size:1.35rem; font-weight:700; margin-top:2px;">{val_str}</div>'
            f'{delta_html}'
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
    if delta is None or pd.isna(delta):
        return "-"
    if delta < 0:
        return f"▼{abs(delta):.1f}%"
    return f"+{delta:.1f}%"


def delta_cell_style(val: str) -> str:
    if isinstance(val, str) and val.startswith("▼"):
        return "color: #DC2626; font-weight: 600;"
    return ""
