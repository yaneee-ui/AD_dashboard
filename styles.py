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
DOWN_COLOR = "#DC2626"  # 감소 = 빨강 (강조), 증가는 별도 강조색 없이 +표기


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
        grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
        gap: 14px;
        margin-bottom: 8px;
    }}
    .kpi-card {{
        background: {CARD_BG};
        border: 1px solid #E5E9F0;
        border-radius: 12px;
        padding: 16px 18px;
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
        flex-wrap: wrap;
        gap: 6px;
    }}
    .kpi-badge {{
        font-size: 0.74rem;
        font-weight: 600;
        padding: 2px 7px;
        border-radius: 6px;
    }}
    .kpi-badge.up {{
        color: #334155;
        background: #F1F5F9;
    }}
    .kpi-badge.down {{
        color: {DOWN_COLOR};
        background: #FEF2F2;
    }}
    .kpi-badge.flat {{
        color: #64748B;
        background: #F1F5F9;
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


def _delta_badge(label: str, pct) -> str:
    if pct is None or pd.isna(pct):
        return f'<span class="kpi-badge flat">{label} -</span>'
    if pct > 0:
        return f'<span class="kpi-badge up">+{pct:.1f}% {label}</span>'
    if pct < 0:
        return f'<span class="kpi-badge down">▼{abs(pct):.1f}% {label}</span>'
    return f'<span class="kpi-badge flat">+0.0% {label}</span>'


def render_kpi_cards(cards: list):
    """
    cards: [{"label": "거래액", "value": "39.2백만", "deltas": [("전주비", 12.3), ("전월비", -4.1), ("전년비", 8.0)]}, ...]
    """
    parts = ['<div class="kpi-grid">']
    for c in cards:
        badges = "".join(_delta_badge(lbl, pct) for lbl, pct in c["deltas"])
        parts.append(
            '<div class="kpi-card">'
            f'<div class="kpi-label">{c["label"]}</div>'
            f'<div class="kpi-value">{c["value"]}</div>'
            f'<div class="kpi-deltas">{badges}</div>'
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
