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
