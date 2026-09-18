import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from io import BytesIO
from datetime import timedelta

from utils import (
    load_data, aggregate, aggregate_by, format_value,
    yoy_same_weekday_dates, RATIO_DEFS, BASE_METRICS,
    format_million, format_roas_percent, UNIT_OPTIONS,
    get_period_bounds, period_label, build_2026_buckets, bucket_yoy_series,
    get_comparison_periods, build_ref_options, days_in_period,
    load_cattxn_data, aggregate_cattxn, aggregate_cattxn_by, cattxn_group_yoy_wow,
    cattxn_txn_type_breakdown, cattxn_daily_series,
    cattxn_period_buckets, cattxn_bucket_series, cattxn_flow_matrix, cattxn_group_trend_table,
    cattxn_weekly_changes, category_lag_correlation, category_lag_scatter_data, linear_trend,
    cattxn_share_series, ad_cost_vs_sa_ep_weekly, classify_comovement, flow_overview_buckets,
    recent_metric_buckets, metric_sparkline_table, category_revenue_forecast,
    load_ad_product_data, aggregate_ad_product, ad_product_group_compare,
    AD_PRODUCT_OWN_OPTIONS, AD_PRODUCT_BASE_METRICS,
    CATTXN_TXN_TYPE_OPTIONS, CATTXN_CHANNEL_OPTIONS, CATTXN_METRIC_OPTIONS,
)
from styles import (
    inject_css, render_kpi_cards, render_page_header, render_section_title,
    pct_change, format_delta_text, delta_cell_style, render_custom_funnel, render_insight_box,
    render_trend_card_header, render_trend_summary_boxes, render_colored_caption,
    render_comparison_table, render_monthly_comparison_table,
)

st.set_page_config(page_title="쇼핑검색광고 실적 대시보드", layout="wide")

# ── 쇼핑검색광고 / EP채널 구분 색상 (03페이지 테이블 공통) ──
AD_COL_COLOR = "#2563EB"   # 쇼핑검색광고 = 파랑
EP_COL_COLOR = "#0D9488"   # EP채널 = 청록


def style_channel_columns(styler, columns):
    """컬럼명에 '쇼핑검색광고'/'EP채널'이 포함된 컬럼을 각각 다른 색으로 강조."""
    ad_cols = [c for c in columns if "쇼핑검색광고" in c]
    ep_cols = [c for c in columns if "EP채널" in c]
    if ad_cols:
        styler = styler.set_properties(subset=ad_cols, **{"color": AD_COL_COLOR, "font-weight": "600"})
    if ep_cols:
        styler = styler.set_properties(subset=ep_cols, **{"color": EP_COL_COLOR, "font-weight": "600"})
    return styler


def style_channel_rows(row, label_col="지표"):
    """지표명(행 라벨)에 '쇼핑검색광고'/'EP채널'이 포함된 행 전체를 각각 다른 색으로 강조."""
    label = str(row.get(label_col, ""))
    if "쇼핑검색광고" in label:
        return [f"color: {AD_COL_COLOR}; font-weight: 600"] * len(row)
    if "EP채널" in label:
        return [f"color: {EP_COL_COLOR}; font-weight: 600"] * len(row)
    return [""] * len(row)

# ── 데이터 로드 ────────────────────────────────────────────────────
df = load_data()
MIN_DATE, MAX_DATE = df["date"].min().date(), df["date"].max().date()

cattxn_df = load_cattxn_data()
CATTXN_MIN_DATE, CATTXN_MAX_DATE = cattxn_df["date"].min().date(), cattxn_df["date"].max().date()
CATTXN_CATEGORY_LIST = sorted(cattxn_df["category"].unique())
CATTXN_BRAND_LIST = sorted(cattxn_df["brand"].unique())

# ── 쇼핑검색광고 리포트(NBOS 매칭, 대/중카테고리·브랜드 단위) — 있으면만 로드, 없어도 나머지 페이지는 정상 동작 ──
ad_product_df = load_ad_product_data()
if ad_product_df is not None:
    AD_PRODUCT_MIN_DATE, AD_PRODUCT_MAX_DATE = ad_product_df["date"].min().date(), ad_product_df["date"].max().date()
    AD_PRODUCT_LARGE_CAT_LIST = sorted(ad_product_df["대카테고리"].unique())

# 01페이지 '지표 선택' 알약 중 가장 자주 보는 핵심 9개 — 맨 앞에 배치하고 별도 색으로 강조한다.
CORE_METRICS = ["노출수", "클릭수", "CTR", "UV", "광고비", "거래액", "ROAS", "CR", "객단가"]
_all_metrics_raw = ["노출수", "클릭수", "UV", "광고비"] + list(RATIO_DEFS.keys()) + [
    "거래액", "거래액(총)", "결제고객수", "결제고객수(총)",
    "가입수", "첫구매수", "첫구매거래액", "신규고객수", "신규거래액",
]
ALL_METRICS = CORE_METRICS + [m for m in _all_metrics_raw if m not in CORE_METRICS]
ALL_METRICS = list(dict.fromkeys(ALL_METRICS))  # 중복 제거, 순서 유지

# 02페이지(전년비교) 지표 탭에서 쓰는 축소 지표셋 — ALL_METRICS(26개)는 탭으로 늘어놓기엔 너무 많아
# 핵심 10개만 알약 탭으로 노출한다. 그 외 지표는 01페이지 '지표 선택' 드롭다운에서 볼 수 있다.
WIDE_YOY_METRICS = ["거래액", "광고비", "ROAS", "CTR", "CPC", "UV", "결제고객수", "CR", "객단가", "순결제비중"]

# ── 사이드바 메뉴 ──────────────────────────────────────────────────
st.sidebar.markdown("### 🛍️ 쇼핑검색광고 · 네이버")
_menu_options = ["📋 01. 쇼핑검색광고 실적", "📈 02. 전년비교", "📊 03. 카테고리별 실적"]
if ad_product_df is not None:
    _menu_options.append("🎯 04. 상품군 효율(광고 리포트)")
menu = st.sidebar.radio("메뉴", _menu_options, label_visibility="collapsed")
if "01" in menu:
    menu = "쇼핑검색광고 실적"
elif "02" in menu:
    menu = "전년비교"
elif "03" in menu:
    menu = "카테고리별 실적"
else:
    menu = "상품군 효율"
st.sidebar.markdown("---")
unit = st.sidebar.radio("조회단위", UNIT_OPTIONS, horizontal=True)
st.sidebar.markdown("---")
st.sidebar.caption(f"데이터 기간\n\n{MIN_DATE} ~ {MAX_DATE}")
st.sidebar.markdown("---")
pin_filters = st.sidebar.checkbox(
    "📌 상단 필터 고정", value=True, key="pin_filters",
    help="켜두면 스크롤해도 상단 필터가 항상 보입니다. 끄면 필터가 본문과 같이 스크롤되어 "
         "화면을 가리지 않습니다.",
)
inject_css(pin_filters)


def to_excel_bytes(data: pd.DataFrame) -> bytes:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        data.to_excel(writer, index=False, sheet_name="data")
    return buf.getvalue()


MILLION_SCALE_METRICS = {"거래액", "광고비", "거래액(총)", "신규거래액", "첫구매거래액", "윈백거래액", "전환매출액", "판매액"}


def _to_million(vals):
    """차트에 꽂기 전에 원 단위 리스트를 백만원 단위로 나눈다 (Plotly 축 눈금의 기본 'M' 표기 대신
    ticksuffix='백만'을 쓰려면 데이터 자체를 미리 백만 단위로 스케일해둬야 한다)."""
    return [v / 1_000_000 if v is not None else None for v in vals]


def _money_axis(title: str = None, is_million: bool = True) -> dict:
    """금액(원) 축 설정 — is_million=True면 백만원 단위로 이미 스케일된 데이터를 전제로
    ticksuffix='백만'을 붙인다. Plotly 기본 SI접두어('20M' 등) 대신 '20.0백만'으로 보이게 한다."""
    d = dict(title=title)
    if is_million:
        d.update(tickformat=",.1f", ticksuffix="백만")
    return d


def _period_start(d, unit: str):
    ts = pd.Timestamp(d)
    if unit == "주별":
        return (ts - pd.Timedelta(days=ts.weekday())).date()
    if unit in ("월별", "월마감"):
        return ts.replace(day=1).date()
    return ts.date()


def _ensure_default_date(key, value, min_v=None, max_v=None):
    """date_input에 value=와 key= 세션스테이트를 동시에 주면 Streamlit이 경고를 낸다 — 대신
    최초 1회(또는 범위를 벗어났을 때)만 session_state를 미리 채워두고, 위젯 호출에는 value=를
    빼서 그 경고를 피한다."""
    cur = st.session_state.get(key)
    if cur is None or (min_v is not None and cur < min_v) or (max_v is not None and cur > max_v):
        st.session_state[key] = value


def _ensure_valid_select(key, options):
    """selectbox도 마찬가지 — index=와 key=를 같이 쓰면 경고가 나고, 조회단위를 바꿔 옵션
    목록 자체가 달라지면 이전 선택값이 새 목록에 없을 수도 있다. 둘 다 여기서 방어한다."""
    if st.session_state.get(key) not in options:
        st.session_state[key] = options[0]


def _quick_date_apply(unit, min_date, max_date, date_key, select_key, target_date):
    """버튼 on_click 콜백 — 스크립트 재실행 '직전'에 실행되므로 위젯이 이미 그려진 뒤에
    session_state를 건드려 StreamlitWidgetAlreadyInstantiatedError가 나는 걸 피할 수 있다."""
    target_date = max(min(target_date, max_date), min_date)
    if unit == "일별":
        st.session_state[date_key] = target_date
    else:
        opts = build_ref_options(unit, min_date, max_date)
        target_period = _period_start(target_date, unit)
        match = next((lbl for lbl, d in opts if _period_start(d, unit) == target_period), None)
        if match:
            st.session_state[select_key] = match


def render_quick_date_buttons(unit: str, min_date, max_date, date_key: str, select_key: str):
    """기준일자 위젯 옆에 오늘/어제 · 금주/전주 · 이번달/지난달 빠른 이동 버튼을 그린다.
    date_key는 일별일 때 쓰는 st.date_input의 key, select_key는 주/월/월마감일 때 쓰는
    st.selectbox의 key — 버튼을 누르면 해당 위젯의 session_state를 직접 갱신하고 rerun한다."""
    max_ts = pd.Timestamp(max_date)
    if unit == "일별":
        # 데이터가 D-1(또는 D-2) 반영이라 max_date 자체가 이미 "어제" 실적이라, 버튼 이름을
        # "오늘/어제"가 아니라 "전일(최신 반영일)/전전일"로 — 실제 오늘 데이터가 있다는 오해를 막는다.
        pairs = [("전일", max_date), ("전전일", (max_ts - pd.Timedelta(days=1)).date())]
    elif unit == "주별":
        pairs = [("금주", max_date), ("전주", (max_ts - pd.Timedelta(days=7)).date())]
    elif unit == "월별":
        this_month = max_ts.replace(day=1)
        last_month = (this_month - pd.Timedelta(days=1)).replace(day=1)
        pairs = [("이번달", this_month.date()), ("지난달", last_month.date())]
    else:  # 월마감 — 이미 마감된 달만 다루므로 "이번달" 대신 최근 두 마감월을 제공
        last_closed = (max_ts.replace(day=1) - pd.Timedelta(days=1)).replace(day=1)
        prev_closed = (last_closed - pd.Timedelta(days=1)).replace(day=1)
        pairs = [("지난달", last_closed.date()), ("전전달", prev_closed.date())]

    btn_cols = st.columns(len(pairs))
    for col, (label, target_date) in zip(btn_cols, pairs):
        with col:
            st.button(
                label, key=f"{date_key}__{label}_btn", use_container_width=True,
                on_click=_quick_date_apply,
                args=(unit, min_date, max_date, date_key, select_key, target_date),
            )


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _trend_xaxis(x_vals, is_daily: bool, tickformat: str = "%m/%d") -> dict:
    """추이 차트 x축 설정. 일별/주별(버킷 수가 많은 단위)은 실제 날짜축 + 기간 필터 버튼으로
    바꿔, 기본으로는 최근 90일만 보여주고 필요하면 버튼으로 기간을 바꿔 볼 수 있게 한다.
    월 단위는 버킷 수가 적어(최대 12개) 기존 카테고리축 그대로가 더 낫다."""
    if not is_daily:
        return dict(type="category", title=None)
    max_x = x_vals[-1]
    default_start = max(x_vals[0], max_x - pd.Timedelta(days=89))
    return dict(
        type="date", title=None, tickformat=tickformat,
        range=[default_start, max_x],
        rangeselector=dict(
            buttons=[
                dict(count=7, label="1주", step="day", stepmode="backward"),
                dict(count=1, label="1개월", step="month", stepmode="backward"),
                dict(count=3, label="3개월", step="month", stepmode="backward"),
                dict(count=6, label="6개월", step="month", stepmode="backward"),
                dict(step="all", label="전체"),
            ],
            x=0, y=1.15, xanchor="left", yanchor="bottom",
            font=dict(size=11),
            bgcolor="#F1F5F9", activecolor="#BFDBFE",
        ),
    )


# ════════════════════════════════════════════════════════════════
# PAGE 1: 쇼핑검색광고 실적
# ════════════════════════════════════════════════════════════════
if menu == "쇼핑검색광고 실적":
    # ── 기준일자: 조회단위에 맞춰 일/주/월 단위로 선택 ──
    with st.container(key="page1_filters"):
        c_ref, c_quick, c_mode = st.columns([2, 1.6, 1.3])
        with c_ref:
            if unit == "일별":
                _ensure_default_date("page1_ref_date", MAX_DATE, MIN_DATE, MAX_DATE)
                ref_date = st.date_input("기준일자", min_value=MIN_DATE, max_value=MAX_DATE, key="page1_ref_date")
            else:
                ref_options = build_ref_options(unit, MIN_DATE, MAX_DATE)
                label_to_date = dict(ref_options)
                picker_label = "기준 주차" if unit == "주별" else "기준 월"
                _ensure_valid_select("page1_ref_select", list(label_to_date.keys()))
                chosen = st.selectbox(picker_label, list(label_to_date.keys()), key="page1_ref_select")
                ref_date = label_to_date[chosen]
        with c_quick:
            st.markdown("<div style='margin-top:1.8rem'></div>", unsafe_allow_html=True)
            render_quick_date_buttons(unit, MIN_DATE, MAX_DATE, "page1_ref_date", "page1_ref_select")
        with c_mode:
            mode = st.radio("표시방식", ["누계", "일평균"], horizontal=True, index=1)

    start_ts, end_ts = get_period_bounds(ref_date, unit, MIN_DATE, MAX_DATE)
    cur_label = period_label(start_ts, end_ts, unit)
    cur_days = days_in_period(start_ts, end_ts)

    render_page_header(
        eyebrow="쇼핑검색광고 · 네이버",
        title=f"쇼핑검색광고 실적 — {cur_label}",
        sub=f"조회단위: {unit}  ·  표시방식: {mode}  ·  집계기간: {start_ts.date()} ~ {end_ts.date()} ({cur_days}일)",
    )

    mask = (df["date"] >= start_ts) & (df["date"] <= end_ts)
    view = df.loc[mask].copy()

    if view.empty:
        st.warning("선택한 기간에 데이터가 없습니다.")
        st.stop()

    agg = aggregate(view)

    def scaled(metric, value, days):
        """누계/일평균 모드 적용: base(합산) metric만 일수로 나누고, 비율지표는 그대로 둔다."""
        if value is None:
            return None
        if mode == "일평균" and metric in BASE_METRICS and days:
            return value / days
        return value

    def format_kpi_value(metric, value):
        if value is None:
            return None
        if metric in ("거래액", "광고비", "거래액(총)"):
            return format_million(value)
        if metric in ("ROAS", "ROAS(총)"):
            return format_roas_percent(value)
        return format_value(metric, value)

    # ── 비교기간 (전일/전주/전월비 + 전년비) 산출 ──
    comp_periods = get_comparison_periods(ref_date, unit, MIN_DATE, MAX_DATE)
    comp_aggs = {}
    comp_days = {}
    for label, (p_start, p_end) in comp_periods.items():
        p_view = df[(df["date"] >= p_start) & (df["date"] <= p_end)]
        comp_aggs[label] = aggregate(p_view) if not p_view.empty else None
        comp_days[label] = days_in_period(p_start, p_end)

    def deltas_for(metric):
        out = []
        cur_v = scaled(metric, agg[metric], cur_days)
        for label, p_agg in comp_aggs.items():
            prev_raw = p_agg[metric] if p_agg else None
            prev_v = scaled(metric, prev_raw, comp_days[label])
            prev_str = format_kpi_value(metric, prev_v)
            out.append((label, pct_change(cur_v, prev_v), prev_str))
        return out

    # ── 가장 부진한 전환 구간 진단(퍼널용, 인사이트 박스에도 재사용): 물량이 아니라
    # '전환율'(CTR/UV-클릭율/CR) 기준으로 판단. 전년비가 있으면 그걸 우선 쓰고(더 안정적인
    # 시그널), 없으면 직전기간으로 대체한다.
    funnel_labels = ["노출", "클릭", "방문(UV)", "구매"]
    stage_rate_defs = [("CTR", 1), ("UV/클릭", 2), ("CR", 3)]  # (지표, funnel stage index)
    yoy_agg_avail = comp_aggs.get("전년비")
    rate_candidates = []
    for metric, idx in stage_rate_defs:
        cur_r = agg[metric]
        if yoy_agg_avail is not None:
            pct = pct_change(cur_r, yoy_agg_avail[metric])
            basis = "전년비"
        else:
            pct = None
            basis = None
        if pct is None:
            imm_label, imm_pct, _ = deltas_for(metric)[0]
            pct, basis = imm_pct, imm_label
        if pct is not None:
            rate_candidates.append((idx, metric, pct, basis))

    weak_index, weak_note = None, None
    if rate_candidates:
        w_idx, w_metric, w_pct, w_basis = min(rate_candidates, key=lambda x: x[2])
        if w_pct < 0:
            weak_index = w_idx
            weak_note = f"{w_metric} {w_basis} {format_delta_text(w_pct)}"

    # ── KPI 카드: 메인(거래액·광고비·ROAS·EP채널) + 보조 지표 2단 구성 ──
    def ep_revenue_raw(p_start, p_end):
        """cattxn_df(카테고리 데이터, D-2 반영) 기준 EP채널 거래액 합계. 기간이 cattxn 데이터
        범위를 벗어나면 클립해서 계산하고, 겹치는 데이터가 없으면 None."""
        c_start = max(p_start, pd.Timestamp(CATTXN_MIN_DATE))
        c_end = min(p_end, pd.Timestamp(CATTXN_MAX_DATE))
        if c_start > c_end:
            return None
        ep_view = cattxn_df[(cattxn_df["date"] >= c_start) & (cattxn_df["date"] <= c_end)]
        if ep_view.empty:
            return None
        return aggregate_cattxn(ep_view, "전체", "전체", "전체")["EP채널_거래액"]

    def ep_deltas_for():
        cur_raw = ep_revenue_raw(start_ts, end_ts)
        cur_v = (cur_raw / cur_days) if (mode == "일평균" and cur_raw is not None and cur_days) else cur_raw
        out = []
        for label, (p_start, p_end) in comp_periods.items():
            prev_raw = ep_revenue_raw(p_start, p_end)
            days = comp_days[label]
            prev_v = (prev_raw / days) if (mode == "일평균" and prev_raw is not None and days) else prev_raw
            prev_str = format_million(prev_v) if prev_v is not None else None
            out.append((label, pct_change(cur_v, prev_v), prev_str))
        return cur_v, out

    primary_metrics = ["거래액", "광고비", "ROAS"]
    primary_label_map = {"거래액": "순결제거래액"}
    primary_cards = []
    for m in primary_metrics:
        display_val = scaled(m, agg[m], cur_days)
        base_label = primary_label_map.get(m, m)
        label_txt = base_label if m not in BASE_METRICS else f"{base_label} · {mode}"
        primary_cards.append({"label": label_txt, "value": format_kpi_value(m, display_val), "deltas": deltas_for(m)})

    ep_cur_v, ep_deltas = ep_deltas_for()
    primary_cards.append({
        "label": f"EP채널 거래액 · {mode}",
        "value": format_million(ep_cur_v) if ep_cur_v is not None else "-",
        "deltas": ep_deltas,
    })

    render_kpi_cards(primary_cards, size="lg")
    st.markdown(
        '<div class="kpi-footnote">※ 광고비·거래액·ROAS는 쇼핑검색광고 핵심 지표이며, EP채널 거래액을 나란히 두어 '
        '광고 흐름과 EP 흐름을 함께 볼 수 있게 했습니다.</div>',
        unsafe_allow_html=True,
    )

    secondary_metrics = ["CR", "결제고객수", "UV", "거래액(총)", "ROAS(총)"]
    secondary_label_map = {"거래액(총)": "총결제거래액", "ROAS(총)": "총결제ROAS"}
    secondary_cards = []
    for m in secondary_metrics:
        display_val = scaled(m, agg[m], cur_days)
        base_label = secondary_label_map.get(m, m)
        label_txt = base_label if m not in BASE_METRICS else f"{base_label} · {mode}"
        secondary_cards.append({"label": label_txt, "value": format_kpi_value(m, display_val), "deltas": deltas_for(m)})

    render_kpi_cards(secondary_cards, size="sm", tier_label="보조 지표")
    st.markdown(
        '<div class="kpi-footnote">※ 거래액·광고비·UV 등 수량·금액 지표는 선택한 '
        f'표시방식({mode}) 기준이며, ROAS·CR·CTR 등 비율지표는 합산이 아닌 재산정한 값입니다.</div>',
        unsafe_allow_html=True,
    )
    comp_period_strs = [
        f"{label} = {period_label(p_start, p_end, unit)}"
        for label, (p_start, p_end) in comp_periods.items()
    ]
    st.caption("📅 비교대상 기간 — " + " · ".join(comp_period_strs))

    # ── 핵심 요약 (규칙 기반 자동 인사이트) ──
    insight_lines = []

    main_moves = []
    for m in ["거래액", "광고비", "ROAS"]:
        lbl, pct, _ = deltas_for(m)[0]
        if pct is not None:
            main_moves.append((m, lbl, pct))
    if main_moves:
        m, lbl, pct = max(main_moves, key=lambda x: abs(x[2]))
        insight_lines.append(f"메인 지표 중 **{m}**이 {lbl} {format_delta_text(pct)}로 가장 크게 움직였습니다.")

    sa_imm_label, sa_imm_pct, _ = deltas_for("거래액")[0]
    ep_imm_pct = ep_deltas[0][1] if ep_deltas else None
    if sa_imm_pct is not None and ep_imm_pct is not None:
        gap = ep_imm_pct - sa_imm_pct
        if gap > 10:
            insight_lines.append(
                f"EP채널 거래액({format_delta_text(ep_imm_pct)})이 쇼핑검색광고 거래액({format_delta_text(sa_imm_pct)})보다 "
                f"더 빠르게 늘고 있습니다 — 광고 확대 여지가 있는지 03페이지에서 확인해보세요."
            )
        elif gap < -10:
            insight_lines.append(
                f"쇼핑검색광고 거래액({format_delta_text(sa_imm_pct)})이 EP채널({format_delta_text(ep_imm_pct)})보다 "
                f"더 빠르게 늘고 있습니다 — 광고 효과가 상대적으로 뚜렷합니다."
            )

    if weak_index is not None:
        insight_lines.append(
            f"퍼널에서는 **{funnel_labels[weak_index]}** 전환 구간이 가장 부진합니다 ({weak_note}) — 아래 실적 퍼널을 확인하세요."
        )

    render_insight_box(insight_lines)

    # ── 실적요약 (직전기간 대비 + 전년비) 테이블 ──
    immediate_label = next(iter(comp_periods.keys()))
    prev_agg_for_table = comp_aggs.get(immediate_label)
    prev_days_for_table = comp_days[immediate_label]
    prev_start, prev_end = comp_periods[immediate_label]

    yoy_agg_for_table = comp_aggs.get("전년비")
    yoy_days_for_table = comp_days["전년비"]
    yoy_start, yoy_end = comp_periods["전년비"]

    render_section_title(f"실적요약 · {immediate_label} · 전년비 비교 ({mode})")

    summary_metrics = ["노출수", "클릭수", "CTR", "CR", "객단가", "결제고객수",
                       "CPC", "CPUV", "UV", "광고비", "거래액", "ROAS",
                       "거래액(총)", "ROAS(총)"]
    summary_label_map = {"거래액(총)": "총결제거래액", "ROAS(총)": "총결제ROAS"}
    prev_col_name = period_label(prev_start, prev_end, unit)
    yoy_col_name = f"전년({period_label(yoy_start, yoy_end, unit)})"
    rows = []
    for m in summary_metrics:
        cur_v = scaled(m, agg[m], cur_days)

        prev_raw = prev_agg_for_table[m] if prev_agg_for_table else None
        prev_v = scaled(m, prev_raw, prev_days_for_table)
        delta = pct_change(cur_v, prev_v)

        yoy_raw = yoy_agg_for_table[m] if yoy_agg_for_table else None
        yoy_v = scaled(m, yoy_raw, yoy_days_for_table)
        yoy_delta = pct_change(cur_v, yoy_v)

        rows.append({
            "지표": summary_label_map.get(m, m),
            prev_col_name: format_value(m, prev_v) if prev_v is not None else "-",
            cur_label: format_value(m, cur_v),
            f"{immediate_label}(%)": format_delta_text(delta),
            yoy_col_name: format_value(m, yoy_v) if yoy_v is not None else "-",
            "전년비(%)": format_delta_text(yoy_delta),
        })
    summary_df = pd.DataFrame(rows)

    st.dataframe(
        summary_df.style.map(delta_cell_style, subset=[f"{immediate_label}(%)", "전년비(%)"]),
        use_container_width=True, hide_index=True, height=460,
    )

    # ── 보조 지표 스냅샷 (최근 구간 추이) ──
    render_section_title(f"보조 지표 스냅샷 · 최근 구간 추이 ({unit}, {mode})")
    spark_metrics = ["노출수", "클릭수", "CTR", "CPC", "CPUV", "객단가", "순결제비중", "신규거래액", "가입수", "첫구매수"]
    spark_buckets = recent_metric_buckets(df, unit, n=12)
    spark_df = metric_sparkline_table(df, spark_buckets, spark_metrics, mode)
    spark_display = pd.DataFrame({
        "지표": spark_df["지표"],
        "추이": spark_df["추이"],
        "최근값": [format_value(m, v) for m, v in zip(spark_df["지표"], spark_df["최근값"])],
        "직전 대비": spark_df["직전 대비"].apply(format_delta_text),
    })
    st.dataframe(
        spark_display.style.map(delta_cell_style, subset=["직전 대비"]),
        column_config={
            "지표": st.column_config.TextColumn("지표", width="small"),
            "추이": st.column_config.LineChartColumn("추이", width="medium"),
            "최근값": st.column_config.TextColumn("최근값"),
            "직전 대비": st.column_config.TextColumn("직전 대비"),
        },
        use_container_width=True, hide_index=True,
        height=min(35 * (len(spark_display) + 1) + 3, 460),
    )
    st.caption(f"📅 최근 {len(spark_buckets)}개 구간({unit}) 기준 · {mode} — 메인 3지표(거래액·광고비·ROAS) 외에 "
              f"놓치기 쉬운 지표들을 한눈에 훑어보기 위한 표입니다. 지표별 세부 흐름은 아래 '지표 선택' 차트에서 확인하세요.")

    # ── 실적 퍼널 (노출 → 클릭 → 방문 → 구매) ──
    render_section_title(f"실적 퍼널 (노출 → 클릭 → 방문 → 구매) · {mode}")

    funnel_stages = ["노출수", "클릭수", "UV", "결제고객수"]
    funnel_cur_vals = [scaled(m, agg[m], cur_days) for m in funnel_stages]

    funnel_deltas = []
    funnel_yoy_deltas = []
    for m in funnel_stages:
        d = deltas_for(m)
        d_label, d_pct, d_prev = d[0]
        funnel_deltas.append(
            f"{d_label} {format_delta_text(d_pct)} ({d_prev})" if d_pct is not None and d_prev else
            (f"{d_label} {format_delta_text(d_pct)}" if d_pct is not None else f"{d_label} -")
        )
        yoy_entry = next((x for x in d if x[0] == "전년비"), None)
        yoy_pct = yoy_entry[1] if yoy_entry else None
        yoy_prev = yoy_entry[2] if yoy_entry else None
        funnel_yoy_deltas.append(
            f"전년비 {format_delta_text(yoy_pct)} ({yoy_prev})" if yoy_pct is not None and yoy_prev else
            (f"전년비 {format_delta_text(yoy_pct)}" if yoy_pct is not None else "전년비 -")
        )

    render_custom_funnel(
        funnel_labels, funnel_cur_vals, deltas=funnel_deltas, yoy_deltas=funnel_yoy_deltas,
        sub_labels=[f"{cur_label} · {mode}"] * 4,
        colors=["#2563EB", "#0EA5E9", "#F59E0B", "#22C55E"],
        weak_index=weak_index, weak_note=weak_note,
    )
    st.caption("💡 도형 폭은 값 비율이 아니라 보기 좋게 고정한 형태입니다 — 정확한 크기는 옆 숫자를 보세요.")
    st.caption(f"📅 전년비 기준: {'정확히 12개월 전 같은 달(마감 실적 기준)' if unit == '월마감' else '전년 동요일비(364일=52주 전, 요일 정렬)'}")
    if weak_index is not None:
        render_colored_caption(
            f"🔻 **{funnel_labels[weak_index]} 전환 구간이 가장 부진합니다** — {weak_note}. "
            "노출·클릭 등 물량이 아니라 단계별 전환율(CTR/UV·클릭율/CR) 기준 진단이라, "
            "트래픽은 늘어도 이 구간만 새는 중일 수 있습니다."
        )

    funnel_table_rows = []
    prev_val = None
    base_val = funnel_cur_vals[0] if funnel_cur_vals else None
    for flabel, fval in zip(funnel_labels, funnel_cur_vals):
        step_rate = (fval / prev_val * 100) if prev_val else None
        total_rate = (fval / base_val * 100) if base_val else None
        funnel_table_rows.append({
            "단계": flabel,
            "값": f"{fval:,.0f}",
            "이전 단계 대비": f"{step_rate:.1f}%" if step_rate is not None else "-",
            "노출 대비": f"{total_rate:.2f}%" if total_rate is not None else "-",
        })
        prev_val = fval
    st.dataframe(pd.DataFrame(funnel_table_rows), hide_index=True, use_container_width=True)
    st.caption(
        f"💡 '이전 단계 대비'는 CTR(클릭/노출) → UV/클릭 → CR(구매/UV) 순서와 같습니다. "
        f"참고: 객단가 {format_value('객단가', agg['객단가'])} · ROAS {format_value('ROAS', agg['ROAS'])} "
        f"(퍼널 단계에는 포함하지 않고 참고용으로만 표시)"
    )

    # ── 카테고리별 거래액 비중 (쇼핑검색광고) — cattxn_df 기준, D-2 반영 ──
    render_section_title(f"카테고리별 거래액 비중 (쇼핑검색광고) · {mode}")
    cat_txn_filter = st.radio(
        "정상/이월/입점", CATTXN_TXN_TYPE_OPTIONS, horizontal=True, key="page1_cat_txn_filter",
    )

    cat_start = max(start_ts, pd.Timestamp(CATTXN_MIN_DATE))
    cat_end = min(end_ts, pd.Timestamp(CATTXN_MAX_DATE))
    if cat_start > cat_end:
        st.info(f"이 기간에는 카테고리별 데이터가 아직 없습니다 (카테고리 데이터 최신일자: {CATTXN_MAX_DATE}).")
    else:
        cat_view = cattxn_df[(cattxn_df["date"] >= cat_start) & (cattxn_df["date"] <= cat_end)]
        cat_rank = aggregate_cattxn_by(cat_view, group_col="category", txn_type=cat_txn_filter)
        cat_rank = cat_rank[cat_rank["쇼핑검색광고_거래액"] > 0].sort_values(
            "쇼핑검색광고_거래액", ascending=False
        ).reset_index(drop=True)

        if cat_rank.empty:
            st.info("카테고리별 쇼핑검색광고 거래액 데이터가 없습니다.")
        else:
            cat_total = cat_rank["쇼핑검색광고_거래액"].sum()

            # 비교기간(직전기간 + 전년비)도 cattxn 자체 날짜범위 안에서 별도 산출
            cat_comp_periods = get_comparison_periods(ref_date, unit, CATTXN_MIN_DATE, CATTXN_MAX_DATE)
            cat_immediate_label = next(iter(cat_comp_periods.keys()))

            def _cat_period_series(period):
                if period is None:
                    return None
                p_start = max(period[0], pd.Timestamp(CATTXN_MIN_DATE))
                p_end = min(period[1], pd.Timestamp(CATTXN_MAX_DATE))
                if p_start > p_end:
                    return None
                p_view = cattxn_df[(cattxn_df["date"] >= p_start) & (cattxn_df["date"] <= p_end)]
                if p_view.empty:
                    return None
                return aggregate_cattxn_by(p_view, group_col="category", txn_type=cat_txn_filter).set_index("category")[
                    "쇼핑검색광고_거래액"
                ]

            cat_yoy_series = _cat_period_series(cat_comp_periods.get("전년비"))
            cat_imm_series = _cat_period_series(cat_comp_periods.get(cat_immediate_label))

            CAT_TOP_N = 8
            CAT_DONUT_COLORS = ["#1E40AF", "#2563EB", "#3B82F6", "#60A5FA", "#7DD3FC",
                                 "#93C5FD", "#0EA5E9", "#0284C7", "#CBD5E1"]
            top_rows = cat_rank.head(CAT_TOP_N)
            rest_sum = cat_rank["쇼핑검색광고_거래액"].iloc[CAT_TOP_N:].sum()
            rest_n = len(cat_rank) - CAT_TOP_N

            donut_labels = top_rows["category"].tolist()
            donut_values = top_rows["쇼핑검색광고_거래액"].tolist()
            if rest_sum > 0:
                donut_labels.append(f"기타 ({rest_n}개)")
                donut_values.append(rest_sum)

            col_donut, col_table = st.columns([1, 1.6])
            with col_donut:
                fig_cat_donut = go.Figure(go.Pie(
                    labels=donut_labels, values=donut_values, hole=0.62,
                    marker=dict(colors=CAT_DONUT_COLORS[:len(donut_labels)]),
                    textinfo="none", sort=False,
                ))
                fig_cat_donut.update_layout(
                    height=320, margin=dict(t=10, b=10, l=10, r=10),
                    legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.02, font=dict(size=11)),
                    annotations=[dict(
                        text=f"총 거래액<br><b>{format_million(cat_total)}</b>",
                        x=0.5, y=0.5, showarrow=False, font=dict(size=13),
                    )],
                )
                st.plotly_chart(fig_cat_donut, use_container_width=True)

            with col_table:
                cat_table_rows = []
                for _, r in cat_rank.iterrows():
                    cname = r["category"]
                    cur_v = r["쇼핑검색광고_거래액"]
                    share = (cur_v / cat_total * 100) if cat_total else None
                    yoy_v = cat_yoy_series.loc[cname] if cat_yoy_series is not None and cname in cat_yoy_series.index else None
                    imm_v = cat_imm_series.loc[cname] if cat_imm_series is not None and cname in cat_imm_series.index else None
                    yoy_pct = pct_change(cur_v, yoy_v) if yoy_v is not None else None
                    imm_pct = pct_change(cur_v, imm_v) if imm_v is not None else None
                    cat_table_rows.append({
                        "카테고리": cname,
                        "거래액": f"{cur_v:,.0f}",
                        "비중": f"{share:.1f}%" if share is not None else "-",
                        "전년동요일": format_delta_text(yoy_pct) if yoy_v is not None else "-",
                        "전년동요일 값": f"{yoy_v:,.0f}" if yoy_v is not None else "-",
                        cat_immediate_label: format_delta_text(imm_pct) if imm_v is not None else "-",
                        f"{cat_immediate_label} 값": f"{imm_v:,.0f}" if imm_v is not None else "-",
                    })
                cat_table_df = pd.DataFrame(cat_table_rows)
                render_comparison_table(cat_table_df, delta_cols=["전년동요일", cat_immediate_label])
            cat_comp_strs = [
                f"{lbl} = {p[0].date()} ~ {p[1].date()}" if p else f"{lbl} = 데이터 없음"
                for lbl, p in [(cat_immediate_label, cat_comp_periods.get(cat_immediate_label)),
                               ("전년비", cat_comp_periods.get("전년비"))]
            ]
            st.caption(
                f"ℹ️ 이 표는 2일 전 실적까지 반영됩니다 (최신일자: {CATTXN_MAX_DATE}) "
                f"· 집계기간: {cat_start.date()} ~ {cat_end.date()} · 비교대상 기간 — {' · '.join(cat_comp_strs)}"
            )
            st.caption("📁 데이터 출처: category_brand_txn_daily.csv ← 정상이월입점_RAW.xlsx (01·02페이지 태블로 원본과는 별도 집계)")

    # ── 추이 차트: 2026년 기준 + 전년비 비교선 (조회단위별 집계) ──
    render_section_title(f"2026년 추이 (전년비 비교) · {mode}")
    st.caption("지표 선택")
    with st.container(key="pill_trend_metric"):
        metric_choice = st.radio(
            "지표 선택", ALL_METRICS, index=ALL_METRICS.index("거래액"),
            horizontal=True, label_visibility="collapsed", key="trend_metric_choice",
        )

    show_combo = False
    if metric_choice == "거래액":
        show_combo = st.checkbox("광고비 · ROAS 함께 보기 (막대 + 보조축)", value=True, key="trend_combo")

    buckets = build_2026_buckets(df, unit)
    if not buckets:
        st.info("2026년 데이터가 없거나, 선택한 조회단위 기준으로 마감된 구간이 없습니다.")
    else:
        labels, cur_vals, prev_vals = bucket_yoy_series(df, buckets, metric_choice, mode, unit)
        axis_metric_label = metric_choice if metric_choice not in BASE_METRICS else f"{metric_choice} ({mode})"

        # ── 일별/주별은 버킷 수가 많아 카테고리축에 다 우겨넣으면 라벨이 겹쳐 읽기 어렵다.
        # 실제 날짜(date)축으로 바꾸고 레인지슬라이더 + 기본 최근 90일(주별은 약 12주) 확대 뷰를
        # 줘서, 평소엔 최근 구간만 깔끔하게 보고 필요하면 슬라이더를 끌어 전체 연도를 볼 수 있게 한다.
        # 월별/월마감은 버킷 수가 적어(최대 12개) 기존 카테고리축 그대로가 더 낫다.
        is_daily = (unit == "일별")
        use_date_axis = unit in ("일별", "주별")
        x_vals = [dates[0] for _, dates in buckets] if use_date_axis else labels
        line_mode = "lines" if is_daily else "lines+markers"

        show_ma = False
        if is_daily:
            show_ma = st.checkbox("7일 이동평균선 함께 보기 (일별 변동 완화)", value=False, key="trend_ma")

        def _ma7(vals):
            s = pd.Series(vals, dtype="float64")
            return s.rolling(7, min_periods=3).mean().tolist()

        fig = go.Figure()
        is_million_metric = metric_choice in MILLION_SCALE_METRICS

        if show_combo:
            _, ad_cost_vals, _ = bucket_yoy_series(df, buckets, "광고비", mode, unit)
            _, roas_vals, _ = bucket_yoy_series(df, buckets, "ROAS", mode, unit)
            roas_pct_vals = [round(v * 100, 1) if v is not None else None for v in roas_vals]
            ad_cost_plot = _to_million(ad_cost_vals)
            cur_plot, prev_plot = _to_million(cur_vals), _to_million(prev_vals)

            fig.add_trace(go.Bar(
                x=x_vals, y=ad_cost_plot, name="광고비", yaxis="y2",
                marker_color="rgba(148,163,184,0.55)",
            ))
            fig.add_trace(go.Scatter(
                x=x_vals, y=cur_plot, mode=line_mode, name="거래액(올해)",
                line=dict(width=2, color="#2563EB"),
                customdata=roas_pct_vals,
                hovertemplate="%{x}<br>거래액: %{y:,.1f}백만<br>ROAS: %{customdata}%<extra></extra>",
            ))
            fig.add_trace(go.Scatter(
                x=x_vals, y=prev_plot, mode=line_mode, name="거래액(전년비)",
                line=dict(width=2, dash="dash", color="#93C5FD"), connectgaps=True,
            ))
            if show_ma:
                fig.add_trace(go.Scatter(
                    x=x_vals, y=_ma7(cur_plot), mode="lines", name="거래액 7일 이동평균",
                    line=dict(width=3, color="#F59E0B"),
                ))
            fig.update_layout(
                height=480 if is_daily else 440,
                margin=dict(t=70 if use_date_axis else 20, b=20, l=10, r=10),
                xaxis=_trend_xaxis(x_vals, use_date_axis, "%m/%d"),
                yaxis=_money_axis(f"거래액 ({mode})"),
                yaxis2=dict(**_money_axis("광고비"), overlaying="y", side="right", showgrid=False),
                hovermode="closest",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
                dragmode="pan",
            )
            st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True})
            st.caption("📊 막대=광고비(우측 보조축) · 거래액 라인에 마우스를 올리면 해당 시점 ROAS%가 함께 표시됩니다."
                      + (" 마우스 스크롤로 확대/축소, 클릭한 채로 드래그하면 좌우 이동됩니다." if use_date_axis else "")
                      + (" 위쪽 버튼으로 기간(1주/1개월/3개월/6개월/전체)을 바꿔볼 수 있습니다." if use_date_axis else ""))
        else:
            cur_plot = _to_million(cur_vals) if is_million_metric else cur_vals
            prev_plot = _to_million(prev_vals) if is_million_metric else prev_vals
            fig.add_trace(go.Scatter(
                x=x_vals, y=cur_plot, mode=line_mode, name="2026년(올해)",
                line=dict(width=2),
            ))
            fig.add_trace(go.Scatter(
                x=x_vals, y=prev_plot, mode=line_mode, name="전년비",
                line=dict(width=2, dash="dash"), connectgaps=True,
            ))
            if show_ma:
                fig.add_trace(go.Scatter(
                    x=x_vals, y=_ma7(cur_plot), mode="lines", name="7일 이동평균",
                    line=dict(width=3, color="#F59E0B"),
                ))
            fig.update_layout(
                height=460 if is_daily else 420,
                margin=dict(t=70 if use_date_axis else 20, b=20, l=10, r=10),
                yaxis=_money_axis(axis_metric_label, is_million_metric),
                xaxis_title=None,
                xaxis=_trend_xaxis(x_vals, use_date_axis, "%m/%d"),
                hovermode="closest",
                dragmode="pan",
            )
            st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True})
            if use_date_axis:
                default_window_note = "최근 90일" if is_daily else "최근 약 12주"
                st.caption(f"💡 기본으로 {default_window_note}만 보여줍니다 — 마우스 스크롤로 확대/축소, "
                           "클릭한 채로 드래그하면 좌우 이동됩니다. 위쪽 버튼으로 1주/1개월/3개월/6개월/전체 기간을 바로 바꿔볼 수 있습니다.")

        yoy_basis = "정확히 12개월 전 같은 달(마감 실적 기준)" if unit == "월마감" else "전년 동요일비(364일=52주 전, 요일 정렬)"
        st.caption(f"📅 전년비 비교 기준: {yoy_basis}")


# ════════════════════════════════════════════════════════════════
# PAGE 2: 전년비교
# ════════════════════════════════════════════════════════════════
elif menu == "전년비교":
    render_page_header(
        eyebrow="쇼핑검색광고 · 네이버",
        title="전년비교",
        sub="일자별(전년 동요일) 및 월별 누적 기준으로 전년 대비 실적을 비교합니다.",
    )
    st.caption(
        f"📅 전년비 비교는 전년 동요일(364일 전, 요일 정렬) 기준입니다 · "
        f"데이터는 {MAX_DATE}까지 반영되어 있습니다 (그 이후 실적은 아직 집계 전)."
    )
    tab1, tab2, tab3 = st.tabs(["일자별 YoY (전년 동요일)", f"{unit} 종합 YoY", "📆 월별 실적 비교 (연간)"])

    # ── TAB 1: 일자별 YoY ──
    with tab1:
        with st.container(key="card_yoy1_filter"):
            render_section_title("🔍 비교 구간 선택")
            st.caption(f"조회단위({unit}) 기준으로 비교 구간을 고르면, 전년 동요일(364일 전)과 비교합니다.")

            yoy1_min_date = MIN_DATE + timedelta(days=364)
            if unit == "일별":
                _ensure_default_date("yoy_start", max(yoy1_min_date, MAX_DATE - timedelta(days=29)),
                                      yoy1_min_date, MAX_DATE)
                _ensure_default_date("yoy_end", MAX_DATE, yoy1_min_date, MAX_DATE)
                c1, c2 = st.columns(2)
                with c1:
                    cur_start = st.date_input(
                        "비교 시작일", min_value=yoy1_min_date, max_value=MAX_DATE, key="yoy_start",
                    )
                with c2:
                    cur_end = st.date_input(
                        "비교 종료일", min_value=yoy1_min_date, max_value=MAX_DATE, key="yoy_end",
                    )
            else:
                yoy1_options = build_ref_options(unit, MIN_DATE, MAX_DATE)
                yoy1_label_to_date = dict(yoy1_options)
                yoy1_labels = list(yoy1_label_to_date.keys())
                picker_label = {"주별": "주차", "월별": "월", "월마감": "마감월"}[unit]
                _ensure_valid_select("yoy_start_period", yoy1_labels)
                _ensure_valid_select("yoy_end_period", yoy1_labels)
                c1, c2 = st.columns(2)
                with c1:
                    yoy1_start_label = st.selectbox(f"비교 시작 {picker_label}", yoy1_labels, key="yoy_start_period")
                with c2:
                    yoy1_end_label = st.selectbox(f"비교 종료 {picker_label}", yoy1_labels, key="yoy_end_period")
                cur_start = get_period_bounds(yoy1_label_to_date[yoy1_start_label], unit, MIN_DATE, MAX_DATE)[0].date()
                cur_end = get_period_bounds(yoy1_label_to_date[yoy1_end_label], unit, MIN_DATE, MAX_DATE)[1].date()

            if cur_start > cur_end:
                st.error("시작 구간이 종료 구간보다 늦을 수 없습니다.")
                st.stop()

        cur_range = pd.date_range(cur_start, cur_end, freq="D")
        prev_range = yoy_same_weekday_dates(pd.Series(cur_range))

        cur_view = df[df["date"].isin(cur_range)].copy()
        prev_view = df[df["date"].isin(prev_range)].copy()

        if prev_view.empty:
            st.warning("전년 동요일에 해당하는 데이터가 없습니다. (데이터 시작일 이전)")
        else:
            cur_agg = aggregate(cur_view)
            prev_agg = aggregate(prev_view)

            with st.container(key="card_yoy1_result"):
                render_section_title("📊 지표 비교")
                st.caption("지표 선택")
                with st.container(key="pill_yoy_metric"):
                    metric_choice2 = st.radio(
                        "지표 선택", WIDE_YOY_METRICS, index=WIDE_YOY_METRICS.index("거래액"),
                        horizontal=True, label_visibility="collapsed", key="yoy_metric",
                    )

                v_cur, v_prev = cur_agg[metric_choice2], prev_agg[metric_choice2]
                delta_pct = pct_change(v_cur, v_prev)

                render_kpi_cards([
                    {
                        "label": f"올해 ({cur_start} ~ {cur_end})",
                        "value": format_value(metric_choice2, v_cur),
                        "deltas": [("전년비", delta_pct, format_value(metric_choice2, v_prev))]
                                  if delta_pct is not None else [],
                    },
                    {
                        "label": f"전년 동요일 ({prev_range.min().date()} ~ {prev_range.max().date()})",
                        "value": format_value(metric_choice2, v_prev),
                        "deltas": [],
                    },
                ])

                # 일자별 라인 비교 (순서상 매칭: n번째 날짜끼리)
                cur_sorted = cur_view.sort_values("date").reset_index(drop=True)
                prev_sorted = prev_view.sort_values("date").reset_index(drop=True)
                n = min(len(cur_sorted), len(prev_sorted))

                is_million2 = metric_choice2 in MILLION_SCALE_METRICS
                fig2_cur = _to_million(cur_sorted[metric_choice2][:n]) if is_million2 else cur_sorted[metric_choice2][:n]
                fig2_prev = _to_million(prev_sorted[metric_choice2][:n]) if is_million2 else prev_sorted[metric_choice2][:n]

                fig2 = go.Figure()
                fig2.add_trace(go.Scatter(
                    x=cur_sorted["date"][:n], y=fig2_cur,
                    mode="lines+markers", name="26년",
                    line=dict(width=2, color="#2563EB"),
                ))
                fig2.add_trace(go.Scatter(
                    x=cur_sorted["date"][:n], y=fig2_prev,
                    mode="lines+markers", name="전년 동요일",
                    line=dict(width=2, color="#93C5FD"),
                ))
                xaxis2 = dict(type="date", tickformat="%m/%d")
                if n <= 10:
                    # 비교 구간이 짧으면(예: 주 초반만 마감된 주차) Plotly가 하루 미만 단위로
                    # 눈금을 쪼개 "00:00, 06:00 ..." 처럼 표시하는 문제가 있어, 하루 단위로 고정한다.
                    xaxis2["dtick"] = "D1"
                fig2.update_layout(
                    height=420, margin=dict(t=20, b=20, l=10, r=10),
                    xaxis=xaxis2, yaxis=_money_axis(metric_choice2, is_million2), hovermode="closest",
                    dragmode="pan",
                )
                st.plotly_chart(fig2, use_container_width=True, config={"scrollZoom": True})

            with st.container(key="card_yoy1_table"):
                render_section_title("📋 일자별 상세")
                compare_table = pd.DataFrame({
                    "날짜(올해)": cur_sorted["date"][:n].dt.date,
                    "올해": cur_sorted[metric_choice2][:n],
                    "날짜(전년)": prev_sorted["date"][:n].dt.date,
                    "전년": prev_sorted[metric_choice2][:n],
                })
                compare_table["증감률(%)"] = [
                    pct_change(c, p) for c, p in zip(compare_table["올해"], compare_table["전년"])
                ]
                compare_table["증감률(%)"] = compare_table["증감률(%)"].apply(format_delta_text)
                st.dataframe(
                    compare_table.style.map(delta_cell_style, subset=["증감률(%)"]),
                    use_container_width=True, height=300,
                )
                st.download_button(
                    "📥 Excel 다운로드",
                    data=to_excel_bytes(compare_table),
                    file_name=f"일자별YoY_{cur_start}_{cur_end}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_yoy_daily",
                )

    # ── TAB 2: 조회단위 종합 YoY (여러 지표를 한 표에서 전년 동요일비 비교) ──
    with tab2:
        st.caption(f"사이드바 조회단위({unit}) 기준으로 2026년 각 구간을 전년 동일 구간(요일 정렬)과 "
                  "여러 지표를 한 번에 비교합니다.")
        with st.container(key="pill_wide_mode"):
            wide_mode = st.radio("표시방식", ["누계", "일평균"], horizontal=True, index=1, key="wide_yoy_mode")

        wide_metrics = WIDE_YOY_METRICS
        period_col = {"일별": "일자", "주별": "주차", "월별": "월", "월마감": "마감월"}[unit]

        def _wide_fmt(metric, value):
            if value is None or pd.isna(value):
                return "-"
            if metric == "ROAS":
                return format_roas_percent(value)
            return format_value(metric, value)

        wide_buckets = build_2026_buckets(df, unit)
        if not wide_buckets:
            st.info("2026년 데이터가 없거나, 선택한 조회단위 기준으로 마감된 구간이 없습니다.")
        else:
            labels = [b[0] for b in wide_buckets]
            start_dates = [b[1][0].date() for b in wide_buckets]
            metric_series = {
                m: bucket_yoy_series(df, wide_buckets, m, wide_mode, unit)[1:]  # (cur_vals, prev_vals)
                for m in wide_metrics
            }

            wide_raw_rows = []
            for i, (label, sdate) in enumerate(zip(labels, start_dates)):
                row = {period_col: label, "시작일자": sdate}
                for m in wide_metrics:
                    cur_vals, prev_vals = metric_series[m]
                    row[f"{m} · 전년"] = prev_vals[i]
                    row[f"{m} · 올해"] = cur_vals[i]
                    row[f"{m} · YoY%"] = pct_change(cur_vals[i], prev_vals[i])
                wide_raw_rows.append(row)
            wide_raw = pd.DataFrame(wide_raw_rows)

            # ── 요약: YoY%만 한눈에 (상단) ──
            with st.container(key="card_yoy2_summary"):
                render_section_title("📊 YoY% 요약")
                yoy_summary_cols = {period_col: wide_raw[period_col]}
                yoy_only_names = []
                for m in wide_metrics:
                    col = f"{m} · YoY%"
                    yoy_summary_cols[m] = wide_raw[col].apply(format_delta_text)
                    yoy_only_names.append(m)
                yoy_summary_display = pd.DataFrame(yoy_summary_cols)
                st.dataframe(
                    yoy_summary_display.style.map(delta_cell_style, subset=yoy_only_names),
                    use_container_width=True, hide_index=True, height=320,
                )

            # ── 상세: 지표별 전년/올해 원값 + YoY% ──
            with st.container(key="card_yoy2_detail"):
                render_section_title("📋 상세 (지표별 전년·올해 원값 포함)")
                display_cols = {period_col: wide_raw[period_col], "시작일자": wide_raw["시작일자"]}
                yoy_col_names = []
                for m in wide_metrics:
                    display_cols[f"{m} · 전년"] = wide_raw[f"{m} · 전년"].apply(lambda v, mm=m: _wide_fmt(mm, v))
                    display_cols[f"{m} · 올해"] = wide_raw[f"{m} · 올해"].apply(lambda v, mm=m: _wide_fmt(mm, v))
                    yoy_col = f"{m} · YoY%"
                    display_cols[yoy_col] = wide_raw[yoy_col].apply(format_delta_text)
                    yoy_col_names.append(yoy_col)
                wide_display = pd.DataFrame(display_cols)

                st.dataframe(
                    wide_display.style.map(delta_cell_style, subset=yoy_col_names),
                    use_container_width=True, hide_index=True, height=560,
                )
                st.download_button(
                    "📥 Excel 다운로드",
                    data=to_excel_bytes(wide_raw),
                    file_name=f"{unit}종합YoY_{start_dates[0]}_{start_dates[-1]}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_yoy_wide",
                )
                wide_yoy_basis = "정확히 12개월 전 같은 달(마감 실적 기준)" if unit == "월마감" else "전년 동요일비(364일=52주 전, 요일 정렬)"
                st.caption(
                    f"📅 전년비 비교 기준: {wide_yoy_basis} · 비율지표(ROAS·CTR·CR·객단가·순결제비중)는 "
                    "일자별 값을 평균내지 않고 분자/분모를 합산한 뒤 재계산한 값입니다."
                )

    # ── TAB 3: 월별 실적 비교 (연간, 26년|전년비|25년 매트릭스) ──
    with tab3:
        render_section_title("📆 월별 실적 비교 (연간)")
        render_monthly_comparison_table(
            df[["date", "거래액", "광고비", "UV", "결제고객수"]], "전체",
        )
        st.caption("📁 데이터 출처: tableau_daily.csv (01페이지와 동일 소스)")


# ════════════════════════════════════════════════════════════════
# PAGE 3: 카테고리별 실적 (정상/이월/입점, 쇼핑검색광고 vs EP채널)
# ════════════════════════════════════════════════════════════════
elif menu == "카테고리별 실적":
    with st.container(key="page3_filters"):
        c_ref, c_quick, c_mode = st.columns([2, 1.6, 1.3])
        with c_ref:
            if unit == "일별":
                _ensure_default_date("cattxn_ref_date", CATTXN_MAX_DATE, CATTXN_MIN_DATE, CATTXN_MAX_DATE)
                cattxn_ref_date = st.date_input("기준일자", min_value=CATTXN_MIN_DATE, max_value=CATTXN_MAX_DATE,
                                                 key="cattxn_ref_date")
            else:
                cattxn_ref_options = build_ref_options(unit, CATTXN_MIN_DATE, CATTXN_MAX_DATE)
                cattxn_label_to_date = dict(cattxn_ref_options)
                picker_label = "기준 주차" if unit == "주별" else "기준 월"
                _ensure_valid_select("cattxn_ref_select", list(cattxn_label_to_date.keys()))
                cattxn_chosen = st.selectbox(picker_label, list(cattxn_label_to_date.keys()),
                                              key="cattxn_ref_select")
                cattxn_ref_date = cattxn_label_to_date[cattxn_chosen]
        with c_quick:
            st.markdown("<div style='margin-top:1.8rem'></div>", unsafe_allow_html=True)
            render_quick_date_buttons(unit, CATTXN_MIN_DATE, CATTXN_MAX_DATE, "cattxn_ref_date", "cattxn_ref_select")
        with c_mode:
            cattxn_mode = st.radio("표시방식", ["누계", "일평균"], horizontal=True, index=1, key="cattxn_mode")

        c_txn, c_cat, c_brand = st.columns([2, 2, 2])
        with c_txn:
            cattxn_txn_filter = st.selectbox("정상/이월/입점", CATTXN_TXN_TYPE_OPTIONS, key="cattxn_txn_filter")
        with c_cat:
            cattxn_category_filter = st.selectbox("카테고리", ["전체"] + CATTXN_CATEGORY_LIST, key="cattxn_cat_filter")
        with c_brand:
            cattxn_brand_filter = st.selectbox("브랜드", ["전체"] + CATTXN_BRAND_LIST, key="cattxn_brand_filter")

    cattxn_start_ts, cattxn_end_ts = get_period_bounds(cattxn_ref_date, unit, CATTXN_MIN_DATE, CATTXN_MAX_DATE)
    cattxn_cur_label = period_label(cattxn_start_ts, cattxn_end_ts, unit)
    cattxn_cur_days = days_in_period(cattxn_start_ts, cattxn_end_ts)
    cattxn_cat_suffix = f" · {cattxn_category_filter}" if cattxn_category_filter != "전체" else ""
    cattxn_brand_suffix = f" · {cattxn_brand_filter}" if cattxn_brand_filter != "전체" else ""
    cattxn_txn_suffix = f" · {cattxn_txn_filter}" if cattxn_txn_filter != "전체" else ""

    render_page_header(
        eyebrow="쇼핑검색광고 · EP채널",
        title=f"카테고리별 실적 — {cattxn_cur_label}{cattxn_cat_suffix}{cattxn_brand_suffix}{cattxn_txn_suffix}",
        sub=f"조회단위: {unit}  ·  표시방식: {cattxn_mode}  ·  집계기간: {cattxn_start_ts.date()} ~ {cattxn_end_ts.date()} ({cattxn_cur_days}일)",
    )
    st.caption(
        f"ℹ️ 이 데이터는 2일 전 실적까지 반영됩니다 (최신일자: {CATTXN_MAX_DATE}). "
        f"01·02페이지의 일일리포트[태블로]는 1일 전 실적까지 반영됩니다 (최신일자: {MAX_DATE}) — "
        f"두 페이지의 '오늘' 기준이 하루 차이날 수 있습니다."
    )

    cattxn_mask = (cattxn_df["date"] >= cattxn_start_ts) & (cattxn_df["date"] <= cattxn_end_ts)
    cattxn_view = cattxn_df.loc[cattxn_mask]

    if cattxn_view.empty:
        st.warning("선택한 기간에 데이터가 없습니다.")
        st.stop()

    cattxn_agg = aggregate_cattxn(cattxn_view, cattxn_txn_filter, cattxn_category_filter, cattxn_brand_filter)
    CATTXN_BASE_METRICS = {"쇼핑검색광고_거래액", "쇼핑검색광고_주문고객수", "EP채널_거래액", "EP채널_주문고객수"}

    def cattxn_scaled(metric, value, days):
        if value is None:
            return None
        if cattxn_mode == "일평균" and metric in CATTXN_BASE_METRICS and days:
            return value / days
        return value

    def format_cattxn_kpi_value(metric, value):
        """KPI 카드 전용: 거래액류는 백만 단위로 축약 표시."""
        if value is None or pd.isna(value):
            return "-"
        if "거래액" in metric:
            return format_million(value)
        return f"{value:,.0f}"

    def format_cattxn_table_value(metric, value):
        """테이블 전용: 원 단위 그대로 표시 (백만 축약 안 함)."""
        if value is None or pd.isna(value):
            return "-"
        return f"{value:,.0f}"

    # ── 비교기간 (전일/전주/전월비 + 전년비) ──
    cattxn_comp_periods = get_comparison_periods(cattxn_ref_date, unit, CATTXN_MIN_DATE, CATTXN_MAX_DATE)
    cattxn_comp_aggs, cattxn_comp_days = {}, {}
    for label, (p_start, p_end) in cattxn_comp_periods.items():
        p_view = cattxn_df[(cattxn_df["date"] >= p_start) & (cattxn_df["date"] <= p_end)]
        cattxn_comp_aggs[label] = (
            aggregate_cattxn(p_view, cattxn_txn_filter, cattxn_category_filter, cattxn_brand_filter) if not p_view.empty else None
        )
        cattxn_comp_days[label] = days_in_period(p_start, p_end)

    def cattxn_deltas_for(metric):
        out = []
        cur_v = cattxn_scaled(metric, cattxn_agg[metric], cattxn_cur_days)
        for label, p_agg in cattxn_comp_aggs.items():
            prev_raw = p_agg[metric] if p_agg else None
            prev_v = cattxn_scaled(metric, prev_raw, cattxn_comp_days[label])
            prev_str = format_cattxn_kpi_value(metric, prev_v)
            out.append((label, pct_change(cur_v, prev_v), prev_str))
        return out

    # ── 쇼핑검색광고 광고비 · ROAS (카테고리별 광고비 원본이 없어 '전체 채널' 기준) ──
    df_period_view = df[(df["date"] >= cattxn_start_ts) & (df["date"] <= cattxn_end_ts)]
    total_ad_agg = aggregate(df_period_view) if not df_period_view.empty else None

    total_ad_comp_aggs = {}
    for label, (p_start, p_end) in cattxn_comp_periods.items():
        p_view = df[(df["date"] >= p_start) & (df["date"] <= p_end)]
        total_ad_comp_aggs[label] = aggregate(p_view) if not p_view.empty else None

    def total_ad_scaled(metric, value, days):
        if value is None:
            return None
        if cattxn_mode == "일평균" and metric == "광고비" and days:
            return value / days
        return value

    def total_ad_deltas_for(metric):
        out = []
        cur_v = total_ad_scaled(metric, total_ad_agg[metric] if total_ad_agg else None, cattxn_cur_days)
        for label, p_agg in total_ad_comp_aggs.items():
            prev_raw = p_agg[metric] if p_agg else None
            prev_v = total_ad_scaled(metric, prev_raw, cattxn_comp_days[label])
            if metric == "광고비":
                prev_str = format_million(prev_v) if prev_v is not None else None
            else:
                prev_str = format_roas_percent(prev_v) if prev_v is not None else None
            out.append((label, pct_change(cur_v, prev_v), prev_str))
        return out

    # ── KPI 카드 ──
    cattxn_kpi_metrics = ["쇼핑검색광고_거래액", "EP채널_거래액", "쇼핑검색광고_객단가", "EP채널_객단가"]
    cattxn_cards = []
    for m in cattxn_kpi_metrics:
        display_val = cattxn_scaled(m, cattxn_agg[m], cattxn_cur_days)
        label_txt = m.replace("_", " · ") + (f" · {cattxn_mode}" if m in CATTXN_BASE_METRICS else "")
        value_str = format_cattxn_kpi_value(m, display_val)
        cattxn_cards.append({"label": label_txt, "value": value_str, "deltas": cattxn_deltas_for(m)})

    ad_cost_val = total_ad_scaled("광고비", total_ad_agg["광고비"] if total_ad_agg else None, cattxn_cur_days)
    roas_val = total_ad_agg["ROAS"] if total_ad_agg else None
    cattxn_cards.append({
        "label": f"쇼핑검색광고 · 광고비(전체채널) · {cattxn_mode}",
        "value": format_million(ad_cost_val) if ad_cost_val is not None else "-",
        "deltas": total_ad_deltas_for("광고비"),
    })
    cattxn_cards.append({
        "label": "쇼핑검색광고 · ROAS(전체채널)",
        "value": format_roas_percent(roas_val) if roas_val is not None else "-",
        "deltas": total_ad_deltas_for("ROAS"),
    })

    render_kpi_cards(cattxn_cards)
    st.markdown(
        f'<div class="kpi-footnote">※ 거래액·주문고객수는 선택한 표시방식({cattxn_mode}) 기준이며, '
        f'객단가는 거래액÷주문고객수로 재산정한 값입니다. 광고비·ROAS는 카테고리별 광고비 원본이 없어 '
        f'<b>쇼핑검색광고 전체 채널 기준</b>입니다(카테고리 필터와 무관, 01페이지와 동일 소스).</div>',
        unsafe_allow_html=True,
    )
    cattxn_comp_strs = [
        f"{label} = {period_label(p_start, p_end, unit)}"
        for label, (p_start, p_end) in cattxn_comp_periods.items()
    ]
    st.caption("📅 비교대상 기간 — " + " · ".join(cattxn_comp_strs))

    # ── 핵심 요약 (규칙 기반 자동 인사이트) ──
    page3_insight_lines = []

    sa_lbl, sa_pct, _ = cattxn_deltas_for("쇼핑검색광고_거래액")[0]
    ep_lbl, ep_pct, _ = cattxn_deltas_for("EP채널_거래액")[0]
    if sa_pct is not None and ep_pct is not None:
        gap = ep_pct - sa_pct
        if gap > 10:
            page3_insight_lines.append(
                f"EP채널 거래액({format_delta_text(ep_pct)})이 쇼핑검색광고({format_delta_text(sa_pct)})보다 "
                f"{sa_lbl} 기준 더 빠르게 늘고 있습니다."
            )
        elif gap < -10:
            page3_insight_lines.append(
                f"쇼핑검색광고 거래액({format_delta_text(sa_pct)})이 EP채널({format_delta_text(ep_pct)})보다 "
                f"{sa_lbl} 기준 더 빠르게 늘고 있습니다."
            )

    roas_lbl, roas_pct, _ = total_ad_deltas_for("ROAS")[0]
    if roas_pct is not None and abs(roas_pct) > 10:
        direction = "개선" if roas_pct > 0 else "악화"
        page3_insight_lines.append(
            f"쇼핑검색광고 ROAS(전체채널)가 {roas_lbl} {format_delta_text(roas_pct)}로 {direction}됐습니다."
        )

    page3_weekly = cattxn_weekly_changes(
        cattxn_df, group_by="category", txn_type=cattxn_txn_filter,
        category=cattxn_category_filter, brand=cattxn_brand_filter,
    )
    page3_latest = page3_weekly.sort_values("_wk").groupby("category").tail(1)
    page3_classes = page3_latest.apply(
        lambda r: classify_comovement(r["광고_증감률"], r["EP_증감률"]), axis=1
    )
    good_n = int((page3_classes == "🟢 동반상승").sum())
    bad_n = int((page3_classes == "🔴 광고잠식 의심").sum())
    if good_n or bad_n:
        page3_insight_lines.append(
            f"최근 완결 주 기준 🟢 동반상승 카테고리 {good_n}개, 🔴 광고잠식 의심 카테고리 {bad_n}개 — "
            "자세한 목록은 'EP 연관성 분석' 탭에서 확인하세요."
        )

    render_insight_box(page3_insight_lines)

    # ── 실적요약 (직전기간 · 전년비) ──
    cattxn_immediate_label = next(iter(cattxn_comp_periods.keys()))
    cattxn_prev_agg = cattxn_comp_aggs.get(cattxn_immediate_label)
    cattxn_prev_days = cattxn_comp_days[cattxn_immediate_label]
    cattxn_prev_start, cattxn_prev_end = cattxn_comp_periods[cattxn_immediate_label]

    cattxn_yoy_agg = cattxn_comp_aggs.get("전년비")
    cattxn_yoy_days = cattxn_comp_days["전년비"]
    cattxn_yoy_start, cattxn_yoy_end = cattxn_comp_periods["전년비"]

    render_section_title(f"실적요약 · {cattxn_immediate_label} · 전년비 비교 ({cattxn_mode})")

    cattxn_summary_metrics = [
        "쇼핑검색광고_거래액", "쇼핑검색광고_주문고객수", "쇼핑검색광고_객단가",
        "EP채널_거래액", "EP채널_주문고객수", "EP채널_객단가",
    ]
    cattxn_prev_col = period_label(cattxn_prev_start, cattxn_prev_end, unit)
    cattxn_yoy_col = f"전년({period_label(cattxn_yoy_start, cattxn_yoy_end, unit)})"
    cattxn_rows = []
    for m in cattxn_summary_metrics:
        cur_v = cattxn_scaled(m, cattxn_agg[m], cattxn_cur_days)
        prev_raw = cattxn_prev_agg[m] if cattxn_prev_agg else None
        prev_v = cattxn_scaled(m, prev_raw, cattxn_prev_days)
        yoy_raw = cattxn_yoy_agg[m] if cattxn_yoy_agg else None
        yoy_v = cattxn_scaled(m, yoy_raw, cattxn_yoy_days)
        cattxn_rows.append({
            "지표": m.replace("_", " · "),
            cattxn_prev_col: format_cattxn_table_value(m, prev_v),
            cattxn_cur_label: format_cattxn_table_value(m, cur_v),
            f"{cattxn_immediate_label}(%)": format_delta_text(pct_change(cur_v, prev_v)),
            cattxn_yoy_col: format_cattxn_table_value(m, yoy_v),
            "전년비(%)": format_delta_text(pct_change(cur_v, yoy_v)),
        })
    cattxn_summary_df = pd.DataFrame(cattxn_rows)
    st.dataframe(
        cattxn_summary_df.style
            .apply(style_channel_rows, axis=1)
            .map(delta_cell_style, subset=[f"{cattxn_immediate_label}(%)", "전년비(%)"]),
        use_container_width=True, hide_index=True,
    )

    # ══════════════════════════════════════════════════════════
    # 탭으로 분리: 흐름 비교를 맨 앞에 (가장 많이 찾는 뷰)
    # ══════════════════════════════════════════════════════════
    tab_flow, tab_syn, tab_cat, tab_brand, tab_txn = st.tabs([
        "📈 채널 흐름 비교", "🔗 EP 연관성 분석", "📦 카테고리별 상세", "🏷️ 브랜드별 상세", "🔀 거래유형 구성",
    ])

    def _normalize_series(vals):
        base = next((v for v in vals if v not in (None, 0)), None)
        if not base:
            return [None] * len(vals)
        return [(v / base * 100) if v is not None else None for v in vals]

    def _render_single_trend(x_vals, cur_vals, prev_vals, channel_label, metric_label,
                             show_yoy, x_categorical, prev_label="전년 동요일"):
        is_money = metric_label == "거래액"
        cur_plot = _to_million(cur_vals) if is_money else cur_vals
        prev_plot = _to_million(prev_vals) if is_money else prev_vals
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=x_vals, y=cur_plot, mode="lines+markers", name="26년",
                                  line=dict(width=2, color="#2563EB")))
        if show_yoy:
            fig.add_trace(go.Scatter(x=x_vals, y=prev_plot, mode="lines+markers", name=prev_label,
                                      line=dict(width=2, color="#93C5FD")))
        layout = dict(height=440, margin=dict(t=20, b=20, l=10, r=10),
                      yaxis=_money_axis(f"{channel_label} {metric_label}", is_money),
                      xaxis_title=None, hovermode="closest", dragmode="pan")
        if x_categorical:
            layout["xaxis"] = dict(type="category")
        fig.update_layout(**layout)
        st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True})

    def _render_compare_trend(x_vals, ad_vals, ep_vals, metric_label, x_categorical, normalize=False):
        if normalize:
            ad_norm, ep_norm = _normalize_series(ad_vals), _normalize_series(ep_vals)
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=x_vals, y=ad_norm, mode="lines+markers", name="쇼핑검색광고(지수)",
                                      line=dict(width=2, color="#2563EB")))
            fig.add_trace(go.Scatter(x=x_vals, y=ep_norm, mode="lines+markers", name="EP채널(지수)",
                                      line=dict(width=2, color="#0D9488")))
            layout = dict(
                height=440, margin=dict(t=20, b=20, l=10, r=10),
                yaxis_title="지수 (시작 시점=100)", xaxis_title=None, hovermode="closest",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
                dragmode="pan",
            )
            if x_categorical:
                layout["xaxis"] = dict(type="category")
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True})
            st.caption("💡 두 채널을 시작 시점=100으로 지수화해서 같은 축에 겹쳐 그렸습니다 — "
                      "선이 비슷하게 움직이면 흐름이 유사한 것이고, 벌어지면 다르게 움직이는 것입니다.")
        else:
            is_money = metric_label == "거래액"
            ad_plot = _to_million(ad_vals) if is_money else ad_vals
            ep_plot = _to_million(ep_vals) if is_money else ep_vals
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=x_vals, y=ad_plot, mode="lines+markers", name="쇼핑검색광고",
                                      line=dict(width=2, color="#2563EB")))
            fig.add_trace(go.Scatter(x=x_vals, y=ep_plot, mode="lines+markers", name="EP채널",
                                      line=dict(width=2, color="#94A3B8"), yaxis="y2"))
            layout = dict(
                height=440, margin=dict(t=20, b=20, l=10, r=60),
                yaxis=_money_axis(f"쇼핑검색광고 {metric_label}", is_money),
                yaxis2=dict(**_money_axis(f"EP채널 {metric_label}", is_money), overlaying="y", side="right"),
                xaxis_title=None, hovermode="closest",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
                dragmode="pan",
            )
            if x_categorical:
                layout["xaxis"] = dict(type="category")
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True})
            st.caption("📊 두 채널의 규모 차이가 커서 좌/우 보조축으로 나눠 표시했습니다 — "
                      "절대값 그대로 비교하고 싶을 때 사용하세요 (흐름 패턴 비교는 '지수화' 옵션을 추천합니다).")

    # ══════════════════════════════════════════════════════════
    # 탭 1: 채널 흐름 비교 (가장 자주 찾는 뷰 — 맨 앞으로)
    # ══════════════════════════════════════════════════════════
    with tab_flow:
        trend_channel_options = CATTXN_CHANNEL_OPTIONS + ["쇼핑검색광고 vs EP채널 (흐름 비교)"]

        c1, c2, c6 = st.columns([2.5, 3, 2.5])
        with c1:
            trend_channel = st.radio("채널", trend_channel_options, horizontal=True,
                                     index=2, key="cattxn_trend_channel")
        with c2:
            trend_metric = st.radio("지표", CATTXN_METRIC_OPTIONS, horizontal=True, key="cattxn_trend_metric")
        with c6:
            trend_txn_type = st.radio("정상/이월/입점", CATTXN_TXN_TYPE_OPTIONS, horizontal=True, key="cattxn_trend_txn")

        is_compare_mode = trend_channel == "쇼핑검색광고 vs EP채널 (흐름 비교)"
        normalize_flow = False
        if is_compare_mode:
            normalize_flow = st.radio(
                "비교 방식", ["지수화 (시작=100, 겹쳐보기 · 흐름 비교에 추천)", "실제값 (보조축)"],
                horizontal=True, key="cattxn_trend_normalize",
            ) == "지수화 (시작=100, 겹쳐보기 · 흐름 비교에 추천)"

        if unit == "일별":
            # ── 일별: 날짜 범위 피커 ──
            default_trend_start = max(CATTXN_MAX_DATE - timedelta(days=29), CATTXN_MIN_DATE)

            def _reset_trend_range():
                st.session_state["cattxn_trend_range"] = (default_trend_start, CATTXN_MAX_DATE)

            if is_compare_mode:
                c3, c4 = st.columns([3, 1])
                show_yoy_line = False
            else:
                c3, c4, c5 = st.columns([3, 1, 1.3])
            with c3:
                trend_range = st.date_input(
                    "기간", value=(default_trend_start, CATTXN_MAX_DATE),
                    min_value=CATTXN_MIN_DATE, max_value=CATTXN_MAX_DATE, key="cattxn_trend_range",
                )
            with c4:
                st.markdown("<div style='margin-top:1.8rem'></div>", unsafe_allow_html=True)
                st.button("🔄 최근으로", key="cattxn_trend_recent", on_click=_reset_trend_range)
            if not is_compare_mode:
                with c5:
                    st.markdown("<div style='margin-top:1.8rem'></div>", unsafe_allow_html=True)
                    show_yoy_line = st.checkbox("전년 비교선 표시", value=True, key="cattxn_trend_yoy")

            if isinstance(trend_range, tuple) and len(trend_range) == 2:
                t_start, t_end = trend_range
            else:
                t_start = t_end = trend_range[0] if isinstance(trend_range, tuple) else trend_range

            if t_start > t_end:
                st.error("시작일이 종료일보다 늦을 수 없습니다.")
            elif is_compare_mode:
                t_dates, ad_vals, _ = cattxn_daily_series(
                    cattxn_df, "쇼핑검색광고", trend_metric, trend_txn_type, cattxn_category_filter, t_start, t_end, cattxn_brand_filter
                )
                _, ep_vals, _ = cattxn_daily_series(
                    cattxn_df, "EP채널", trend_metric, trend_txn_type, cattxn_category_filter, t_start, t_end, cattxn_brand_filter
                )
                _render_compare_trend(t_dates, ad_vals, ep_vals, trend_metric, x_categorical=False, normalize=normalize_flow)
                st.caption(f"📅 기간: {t_start} ~ {t_end}")
            else:
                t_dates, t_cur, t_prev = cattxn_daily_series(
                    cattxn_df, trend_channel, trend_metric, trend_txn_type, cattxn_category_filter, t_start, t_end, cattxn_brand_filter
                )
                _render_single_trend(t_dates, t_cur, t_prev, trend_channel, trend_metric, show_yoy_line, x_categorical=False)
                st.caption(f"📅 기간: {t_start} ~ {t_end}" + ("  ·  전년 비교선: 364일(52주) 전 동요일 매칭" if show_yoy_line else ""))

        elif unit == "주별":
            # ── 주별: 'M월 W주차' 슬라이더 ──
            all_weeks = cattxn_period_buckets(cattxn_df, "주별")
            week_labels = [b[0] for b in all_weeks]
            default_n = min(12, len(week_labels))
            default_week_range = (week_labels[-default_n], week_labels[-1])

            def _reset_week_range():
                st.session_state["cattxn_trend_week_range"] = default_week_range

            if is_compare_mode:
                c3, c4 = st.columns([4, 1])
                show_yoy_line = False
            else:
                c3, c4, c5 = st.columns([4, 1, 1.3])
            with c3:
                st.caption("주차 범위")
                week_range = st.select_slider(
                    "주차 범위", options=week_labels, value=default_week_range,
                    key="cattxn_trend_week_range", label_visibility="collapsed",
                )
            with c4:
                st.button("🔄 최근으로", key="cattxn_trend_week_recent", on_click=_reset_week_range)
            if not is_compare_mode:
                with c5:
                    show_yoy_line = st.checkbox("전년 비교선 표시", value=True, key="cattxn_trend_week_yoy")

            start_idx, end_idx = week_labels.index(week_range[0]), week_labels.index(week_range[1])
            if start_idx > end_idx:
                st.error("시작 주차가 종료 주차보다 늦을 수 없습니다.")
            else:
                sel_buckets = all_weeks[start_idx:end_idx + 1]
                if is_compare_mode:
                    labels, ad_vals, _ = cattxn_bucket_series(
                        cattxn_df, sel_buckets, "쇼핑검색광고", trend_metric, trend_txn_type, cattxn_category_filter,
                        brand=cattxn_brand_filter
                    )
                    _, ep_vals, _ = cattxn_bucket_series(
                        cattxn_df, sel_buckets, "EP채널", trend_metric, trend_txn_type, cattxn_category_filter,
                        brand=cattxn_brand_filter
                    )
                    _render_compare_trend(labels, ad_vals, ep_vals, trend_metric, x_categorical=True, normalize=normalize_flow)
                else:
                    labels, cur_vals, prev_vals = cattxn_bucket_series(
                        cattxn_df, sel_buckets, trend_channel, trend_metric, trend_txn_type, cattxn_category_filter,
                        brand=cattxn_brand_filter
                    )
                    _render_single_trend(labels, cur_vals, prev_vals, trend_channel, trend_metric, show_yoy_line,
                                         x_categorical=True, prev_label="전년 동일주차")
                st.caption(f"📅 주차: {week_range[0]} ~ {week_range[1]}"
                          + ("  ·  전년 비교선: 동일 주차(364일 전) 매칭" if not is_compare_mode and show_yoy_line else ""))

        else:  # 월별 / 월마감
            # ── 월별: 선택 없이 2026년 전체 표시 (레퍼런스와 동일) ──
            all_months = cattxn_period_buckets(cattxn_df, "월별")

            if is_compare_mode:
                show_yoy_line = False
            else:
                show_yoy_line = st.checkbox("전년 비교선 표시", value=True, key="cattxn_trend_month_yoy")

            if not all_months:
                st.info("2026년 데이터가 없습니다.")
            elif is_compare_mode:
                labels, ad_vals, _ = cattxn_bucket_series(
                    cattxn_df, all_months, "쇼핑검색광고", trend_metric, trend_txn_type, cattxn_category_filter,
                    brand=cattxn_brand_filter
                )
                _, ep_vals, _ = cattxn_bucket_series(
                    cattxn_df, all_months, "EP채널", trend_metric, trend_txn_type, cattxn_category_filter,
                    brand=cattxn_brand_filter
                )
                _render_compare_trend(labels, ad_vals, ep_vals, trend_metric, x_categorical=True, normalize=normalize_flow)
                st.caption("📅 2026년 전체")
            else:
                labels, cur_vals, prev_vals = cattxn_bucket_series(
                    cattxn_df, all_months, trend_channel, trend_metric, trend_txn_type, cattxn_category_filter,
                    brand=cattxn_brand_filter
                )
                _render_single_trend(labels, cur_vals, prev_vals, trend_channel, trend_metric, show_yoy_line,
                                     x_categorical=True, prev_label="전년 동월(동요일 기준)")
                st.caption("📅 2026년 전체" + ("  ·  전년 비교선: 동월 동요일(364일 전) 매칭" if show_yoy_line else ""))

        # ── SA/EP 거래액 비중 추이 (조회단위 기준 최근 구간) ──
        render_section_title(f"SA/EP 거래액 비중 추이 · {unit}")
        share_buckets = flow_overview_buckets(cattxn_df, unit)
        share_labels, sa_share, ep_share = cattxn_share_series(
            cattxn_df, share_buckets, cattxn_txn_filter, cattxn_category_filter, cattxn_brand_filter
        )
        fig_share = go.Figure()
        fig_share.add_trace(go.Scatter(x=share_labels, y=sa_share, mode="lines+markers", name="SA(쇼핑검색광고) 비중",
                                       line=dict(width=2, color="#2563EB"), stackgroup="one"))
        fig_share.add_trace(go.Scatter(x=share_labels, y=ep_share, mode="lines+markers", name="EP채널 비중",
                                       line=dict(width=2, color="#0D9488"), stackgroup="one"))
        fig_share.update_layout(
            height=380, margin=dict(t=20, b=20, l=10, r=10),
            xaxis=dict(type="category", title=None), yaxis=dict(title="비중 (%)", range=[0, 100]),
            hovermode="closest",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            dragmode="pan",
        )
        st.plotly_chart(fig_share, use_container_width=True, config={"scrollZoom": True})
        st.caption(f"📅 {share_labels[0]} ~ {share_labels[-1]}  ·  SA와 EP를 합쳐 100%로 보고 비중 변화를 봅니다. "
                  f"SA 비중이 늘고 있다면 광고 의존도가 커지고 있다는 뜻이고, 줄고 있다면 EP가 상대적으로 더 크고 있다는 뜻입니다.")

        # ── SA×EP 통합 흐름: 광고비 · 거래액 · ROAS · EP채널 (메인 3지표 + EP 흐름 한 화면) ──
        render_section_title(f"SA×EP 통합 흐름 — 광고비 · 거래액 · ROAS · EP채널 · {unit}")
        overview = ad_cost_vs_sa_ep_weekly(df, cattxn_df, share_buckets, cattxn_txn_filter)
        roas_pct = (overview["ROAS"] * 100).round(1)
        ad_cost_m = _to_million(overview["광고비"])
        sa_rev_m = _to_million(overview["SA_거래액"])
        ep_rev_m = _to_million(overview["EP_거래액"])

        fig_overview = go.Figure()
        fig_overview.add_trace(go.Bar(
            x=overview["주차"], y=ad_cost_m, name="광고비(전체채널·일평균)", yaxis="y2",
            marker_color="rgba(148,163,184,0.55)",
        ))
        fig_overview.add_trace(go.Scatter(
            x=overview["주차"], y=sa_rev_m, mode="lines+markers", name="쇼핑검색광고 거래액(일평균)",
            line=dict(width=2, color="#2563EB"),
            customdata=roas_pct, hovertemplate="%{x}<br>SA 거래액: %{y:,.1f}백만<br>ROAS: %{customdata}%<extra></extra>",
        ))
        fig_overview.add_trace(go.Scatter(
            x=overview["주차"], y=ep_rev_m, mode="lines+markers", name="EP채널 거래액(일평균)",
            line=dict(width=2, color="#0D9488"),
        ))
        fig_overview.update_layout(
            height=440, margin=dict(t=20, b=20, l=10, r=10),
            xaxis=dict(type="category", title=None),
            yaxis=_money_axis("거래액(일평균)"),
            yaxis2=dict(**_money_axis("광고비(일평균)"), overlaying="y", side="right", showgrid=False),
            hovermode="closest",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            dragmode="pan",
        )
        st.plotly_chart(fig_overview, use_container_width=True, config={"scrollZoom": True})
        st.caption(
            "📊 막대=광고비(우측 보조축, 전체채널) · SA 거래액 라인에 마우스를 올리면 해당 시점 ROAS%가 함께 표시됩니다 · "
            "EP채널 거래액은 SA와 같은 좌측 축에서 나란히 비교합니다."
        )

        ad_vs_total_display = pd.DataFrame({
            unit: overview["주차"],
            "광고비(일평균)": overview["광고비"].apply(lambda v: f"{v:,.0f}" if pd.notna(v) else "-"),
            "ROAS": overview["ROAS"].apply(lambda v: f"{v * 100:,.0f}%" if pd.notna(v) else "-"),
            "SA 거래액(일평균)": overview["SA_거래액"].apply(lambda v: f"{v:,.0f}"),
            "EP 거래액(일평균)": overview["EP_거래액"].apply(lambda v: f"{v:,.0f}"),
            "광고비 증감률": overview["광고비_증감률"].apply(format_delta_text),
            "SA 증감률": overview["SA_거래액_증감률"].apply(format_delta_text),
            "EP 증감률": overview["EP_거래액_증감률"].apply(format_delta_text),
        })
        st.dataframe(
            ad_vs_total_display.style.map(
                delta_cell_style, subset=["광고비 증감률", "SA 증감률", "EP 증감률"]
            ),
            use_container_width=True, hide_index=True,
        )
        st.caption(
            "💡 광고비가 늘어난 구간에 SA뿐 아니라 EP 증감률도 같이 플러스면 '광고가 전체 수요를 키운' 것이고, "
            "SA는 늘고 EP는 그대로거나 줄면 '광고가 SA 안에서만 도는(EP를 못 키우는)' 신호일 수 있습니다. "
            "광고비·ROAS는 카테고리 구분 없는 전체 채널 기준(01페이지와 동일 소스)입니다."
        )

    # ══════════════════════════════════════════════════════════
    # 탭 1.5: EP 연관성 분석 (시너지 카테고리 찾기)
    # ══════════════════════════════════════════════════════════
    with tab_syn:
        st.markdown(
            '<div class="kpi-footnote">※ 카테고리별 실제 광고비 원본이 없어, 쇼핑검색광고 거래액 증감률을 '
            '"얼마나 밀었는지"의 대리지표로 사용합니다. 상관관계는 인과관계를 증명하지 않으며, '
            '계절성 등 다른 요인이 같이 작용할 수 있습니다. 전체 기간(2025년~) 주간 데이터를 사용합니다.</div>',
            unsafe_allow_html=True,
        )

        syn_group_label = st.radio("분석 단위", ["카테고리", "브랜드"], horizontal=True, key="syn_group")
        syn_group_by = "category" if syn_group_label == "카테고리" else "brand"

        if syn_group_by == "brand" and cattxn_category_filter == "전체":
            st.info("브랜드 단위 분석은 카테고리를 하나 선택하면(상단 필터) 그 안에서 브랜드별로 비교합니다. "
                   "지금은 카테고리가 '전체'라 전체 브랜드를 대상으로 분석합니다.")

        syn_weekly = cattxn_weekly_changes(
            cattxn_df, group_by=syn_group_by, txn_type=cattxn_txn_filter,
            category=cattxn_category_filter, brand=cattxn_brand_filter,
        )
        syn_corr = category_lag_correlation(syn_weekly, max_lag=2, min_samples=4)

        render_section_title(f"{syn_group_label}별 시차 상관관계 랭킹")
        st.caption("lag0=같은 주, lag1=1주 후, lag2=2주 후 EP 반응. '최고 시점'은 절댓값 기준 가장 강한 상관관계가 나타난 시차입니다.")

        syn_corr_display = pd.DataFrame({
            syn_group_label: syn_corr["category"],
            "lag0(동주)": syn_corr["lag0"].apply(lambda v: f"{v:.2f}" if pd.notna(v) else "-"),
            "lag1(1주후)": syn_corr["lag1"].apply(lambda v: f"{v:.2f}" if pd.notna(v) else "-"),
            "lag2(2주후)": syn_corr["lag2"].apply(lambda v: f"{v:.2f}" if pd.notna(v) else "-"),
            "최고 시점": syn_corr["best_lag"].apply(lambda v: "동주" if v == 0 else f"{v}주 후"),
            "최고 상관계수": syn_corr["best_corr"].apply(lambda v: f"{v:.2f}" if pd.notna(v) else "-"),
            "표본수(주)": syn_corr["best_n"],
        })
        st.dataframe(syn_corr_display, use_container_width=True, hide_index=True,
                    height=min(35 * (len(syn_corr_display) + 1) + 3, 460))

        render_section_title(f"{syn_group_label}별 SA↔EP 동행 분석 (최근 완결 주 기준)")
        latest_moves = syn_weekly.sort_values("_wk").groupby("category").tail(1)[
            ["category", "광고_증감률", "EP_증감률"]
        ].reset_index(drop=True)
        latest_moves["분류"] = latest_moves.apply(
            lambda r: classify_comovement(r["광고_증감률"], r["EP_증감률"]), axis=1
        )
        latest_moves = latest_moves.sort_values("광고_증감률", ascending=False)

        comove_display = pd.DataFrame({
            syn_group_label: latest_moves["category"],
            "SA 매출 증감": latest_moves["광고_증감률"].apply(format_delta_text),
            "EP 매출 증감": latest_moves["EP_증감률"].apply(format_delta_text),
            "분류": latest_moves["분류"],
        })
        st.dataframe(
            comove_display.style.map(delta_cell_style, subset=["SA 매출 증감", "EP 매출 증감"]),
            use_container_width=True, hide_index=True,
            height=min(35 * (len(comove_display) + 1) + 3, 460),
        )
        st.caption(
            "💡 🟢 동반상승(SA·EP 같이 오름, 시너지) · 🔵 SA단독 성장(SA만 오르고 EP는 그대로) · "
            "🔴 광고잠식 의심(SA는 늘었는데 EP는 줄어듦) · ⚪ 동반하락 · ⚫ 변화 미미(±5%p 이내) · 🟡 혼조. "
            "직전 주 대비 증감률, 가장 최근 완결 주 기준입니다."
        )

        render_section_title(f"{syn_group_label}별 산점도 (광고 증감률 vs EP 증감률)")
        syn_valid = syn_corr[(syn_corr["best_corr"].notna()) & (syn_corr["best_n"] >= 8)]
        syn_valid_items = syn_valid["category"].tolist()

        if not syn_valid_items:
            st.info("상관관계를 계산할 수 있는 표본(주 8개 이상)이 부족합니다.")
        else:
            sc1, sc2 = st.columns([2, 2])
            with sc1:
                syn_pick = st.selectbox(syn_group_label, syn_valid_items, index=0, key="syn_pick")
            default_syn_lag = int(syn_corr.loc[syn_corr["category"] == syn_pick, "best_lag"].iloc[0])
            with sc2:
                syn_lag = st.radio(
                    "시차(lag)", [0, 1, 2], index=default_syn_lag, horizontal=True,
                    format_func=lambda v: "동주" if v == 0 else f"{v}주 후", key="syn_lag",
                )

            syn_scatter = category_lag_scatter_data(syn_weekly, syn_pick, syn_lag)

            if len(syn_scatter) < 3:
                st.info("산점도를 그리기엔 표본이 부족합니다.")
            else:
                syn_r = syn_scatter["광고_증감률"].corr(syn_scatter["EP_증감률"])
                syn_slope, syn_intercept = linear_trend(syn_scatter["광고_증감률"], syn_scatter["EP_증감률"])

                fig_syn = go.Figure()
                fig_syn.add_trace(go.Scatter(
                    x=syn_scatter["광고_증감률"], y=syn_scatter["EP_증감률"],
                    mode="markers", name="주간 데이터",
                    marker=dict(color="#2563EB", size=8, opacity=0.7),
                ))
                if syn_slope is not None:
                    x_range = [syn_scatter["광고_증감률"].min(), syn_scatter["광고_증감률"].max()]
                    y_range = [syn_slope * x + syn_intercept for x in x_range]
                    fig_syn.add_trace(go.Scatter(
                        x=x_range, y=y_range, mode="lines", name="추세선",
                        line=dict(color="#94A3B8", dash="dash"),
                    ))
                fig_syn.update_layout(
                    height=440, margin=dict(t=20, b=20, l=10, r=10),
                    xaxis_title="쇼핑검색광고 거래액 증감률 (%, 전주비)",
                    yaxis_title=f"EP 거래액 증감률 (%, {'동주' if syn_lag == 0 else f'{syn_lag}주 후'})",
                    hovermode="closest",
                    dragmode="pan",
                )
                st.plotly_chart(fig_syn, use_container_width=True, config={"scrollZoom": True})
                st.caption(
                    f"상관계수 r = {syn_r:.2f} · 표본 {len(syn_scatter)}개 주 · {syn_pick}, "
                    f"{'동주' if syn_lag == 0 else f'{syn_lag}주 후'} 기준 — "
                    f"r이 클수록(0.5 이상) 광고 확대가 EP 반응과 같이 움직이는(시너지) 경향이 강합니다."
                )

    # ══════════════════════════════════════════════════════════
    # 탭 2: 카테고리별 상세
    # ══════════════════════════════════════════════════════════
    with tab_cat:
        # ── 카테고리 거래액 추이 분석 카드 (실제 30일 + 14일 추세 예측) ──
        with st.container(key="cat_trend_card"):
            render_trend_card_header(
                "📊", "카테고리 거래액 추이 분석",
                "채널별 카테고리 일별 거래액 추세와 14일 추세 예측 (실제 최근 30일 · 정상/이월/입점 전체 기준)",
            )
            tc1, tc2 = st.columns([1.6, 4])
            with tc1:
                trend_channel_pick = st.radio(
                    "채널", ["전체", "쇼핑검색광고", "EP채널"], horizontal=True, key="cat_trend_channel_pick",
                )
            recent30_start = pd.Timestamp(CATTXN_MAX_DATE) - timedelta(days=29)
            recent30 = cattxn_df[cattxn_df["date"] >= recent30_start]
            if trend_channel_pick == "쇼핑검색광고":
                recent30_rev = recent30.groupby("category")["ad_거래액"].sum()
            elif trend_channel_pick == "EP채널":
                recent30_rev = recent30.groupby("category")["ep_거래액"].sum()
            else:
                recent30_rev = recent30.groupby("category").apply(
                    lambda g: g["ad_거래액"].sum() + g["ep_거래액"].sum()
                )
            default_cats = recent30_rev.sort_values(ascending=False).head(5).index.tolist()
            with tc2:
                trend_cat_pick = st.multiselect(
                    "카테고리 선택 (최근 30일 거래액 상위 5개 기본)", CATTXN_CATEGORY_LIST,
                    default=default_cats, key="cat_trend_cat_pick",
                )

            if not trend_cat_pick:
                st.info("카테고리를 1개 이상 선택하세요.")
            else:
                trend_forecast = category_revenue_forecast(
                    cattxn_df, trend_cat_pick, trend_channel_pick, txn_type="전체",
                    days_actual=30, days_forecast=14, trend_days=14,
                )
                trend_forecast_m = {
                    cat: {
                        "actual_dates": d["actual_dates"], "actual_vals": _to_million(d["actual_vals"]),
                        "forecast_dates": d["forecast_dates"], "forecast_vals": _to_million(d["forecast_vals"]),
                        "band_upper": _to_million(d["band_upper"]), "band_lower": _to_million(d["band_lower"]),
                    } for cat, d in trend_forecast.items()
                }
                palette = ["#1E293B", "#2563EB", "#0EA5E9", "#8B5CF6", "#F59E0B", "#22C55E", "#EC4899"]

                fig_trend = go.Figure()
                boundary_date, forecast_end = None, None
                for i, cat in enumerate(trend_cat_pick):
                    d = trend_forecast_m[cat]
                    color = palette[i % len(palette)]
                    fig_trend.add_trace(go.Scatter(
                        x=d["actual_dates"], y=d["actual_vals"], mode="lines", name=cat,
                        line=dict(width=2, color=color), legendgroup=cat,
                    ))
                    if d["forecast_vals"]:
                        boundary_date = d["actual_dates"][-1]
                        forecast_end = d["forecast_dates"][-1]
                        fx = [boundary_date] + d["forecast_dates"]
                        fy = [d["actual_vals"][-1]] + d["forecast_vals"]
                        fig_trend.add_trace(go.Scatter(
                            x=fx, y=fy, mode="lines+markers", name=f"{cat}(예측)",
                            line=dict(width=2, color=color, dash="dot"),
                            marker=dict(size=5, symbol="circle-open"),
                            legendgroup=cat, showlegend=False,
                        ))
                        band_x = [boundary_date] + d["forecast_dates"] + d["forecast_dates"][::-1] + [boundary_date]
                        band_y = ([d["actual_vals"][-1]] + d["band_upper"]
                                  + d["band_lower"][::-1] + [d["actual_vals"][-1]])
                        fig_trend.add_trace(go.Scatter(
                            x=band_x, y=band_y, mode="none", fill="toself",
                            fillcolor=_hex_to_rgba(color, 0.10),
                            legendgroup=cat, showlegend=False, hoverinfo="skip",
                        ))
                if boundary_date is not None:
                    fig_trend.add_vrect(x0=boundary_date, x1=forecast_end,
                                        fillcolor="#F1F5F9", opacity=0.6, layer="below", line_width=0)
                    fig_trend.add_vline(x=boundary_date, line_width=1, line_dash="dash", line_color="#CBD5E1")
                fig_trend.update_layout(
                    height=420, margin=dict(t=10, b=10, l=10, r=10),
                    yaxis=_money_axis("거래액"), xaxis_title=None,
                    hovermode="closest",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
                    dragmode="pan",
                )
                st.plotly_chart(fig_trend, use_container_width=True, config={"scrollZoom": True})
                if boundary_date is not None:
                    st.caption(f"📅 실제: {trend_forecast[trend_cat_pick[0]]['actual_dates'][0].date()} ~ "
                              f"{boundary_date.date()}  ·  예측: {boundary_date.date()} ~ {forecast_end.date()} "
                              "(연한 배경 = 예측 구간)")

                # ── 인사이트 + 예측 요약 (규칙 기반) ──
                recent7_totals = {cat: sum(trend_forecast[cat]["actual_vals"][-7:]) for cat in trend_cat_pick}
                top_cat = max(recent7_totals, key=recent7_totals.get) if recent7_totals else None

                def _volatility(vals):
                    s = pd.Series(vals)
                    return (s.std() / s.mean()) if s.mean() else None

                stability = {cat: _volatility(trend_forecast[cat]["actual_vals"]) for cat in trend_cat_pick}
                stable_valid = {c: v for c, v in stability.items() if v is not None}
                stable_cat = min(stable_valid, key=stable_valid.get) if stable_valid else None

                insight_parts = []
                if top_cat:
                    insight_parts.append(f"**{top_cat}** 카테고리가 최근 7일 거래액을 가장 크게 견인하고 있습니다.")
                if stable_cat and stable_cat != top_cat:
                    insight_parts.append(f"**{stable_cat}** 카테고리는 변동성이 가장 낮아 안정적인 흐름을 보이고 있습니다.")
                insight_text = " ".join(insight_parts) or "선택한 카테고리의 데이터가 충분하지 않습니다."

                growth_parts = []
                for cat in trend_cat_pick:
                    d = trend_forecast[cat]
                    if d["forecast_vals"]:
                        last7_avg = sum(d["actual_vals"][-7:]) / 7
                        fcst7_avg = sum(d["forecast_vals"][:7]) / min(7, len(d["forecast_vals"]))
                        if last7_avg:
                            growth_parts.append((cat, (fcst7_avg - last7_avg) / last7_avg * 100))

                forecast_text = "예측을 계산할 데이터가 부족합니다."
                if growth_parts:
                    avg_growth = sum(g for _, g in growth_parts) / len(growth_parts)
                    best_cat, best_growth = max(growth_parts, key=lambda x: x[1])
                    direction = "증가" if avg_growth >= 0 else "감소"
                    forecast_text = (
                        f"선택 카테고리 평균 거래액은 향후 1주 기준 직전 7일 대비 {abs(avg_growth):.1f}% {direction}할 "
                        f"것으로 추정되며, **{best_cat}** 카테고리의 성장세가 가장 두드러질 전망입니다."
                    )

                render_trend_summary_boxes([
                    {"icon": "📈", "title": "인사이트", "text": insight_text},
                    {"icon": "✨", "title": "예측 요약 (추세 기반, 참고용)", "text": forecast_text},
                ])
                st.caption("⚠️ 예측은 최근 14일 선형추세를 단순 연장한 대략적 방향성 참고용입니다 "
                          "(계절성·프로모션·광고 예산 변경 등은 반영되지 않습니다).")

        render_section_title("카테고리·브랜드별 거래액 추이")
        fc0, fc1 = st.columns([2, 2])
        with fc0:
            flow_group_label = st.radio("그룹 기준", ["카테고리", "브랜드"], horizontal=True, key="cattxn_flow_group")
        with fc1:
            flow_channel = st.radio("채널", CATTXN_CHANNEL_OPTIONS, horizontal=True, key="cattxn_flow_channel")

        flow_group_by = "category" if flow_group_label == "카테고리" else "brand"

        if unit == "일별":
            flow_range = pd.date_range(max(CATTXN_MAX_DATE - timedelta(days=29), CATTXN_MIN_DATE), CATTXN_MAX_DATE)
            flow_buckets = [(d.strftime("%m-%d"), [d]) for d in flow_range]
            flow_period_note = f"최근 {len(flow_buckets)}일 · 일별"
        elif unit == "주별":
            all_weeks_flow = cattxn_period_buckets(cattxn_df, "주별")
            flow_buckets = all_weeks_flow[-12:]
            flow_period_note = f"{flow_buckets[0][0]} ~ {flow_buckets[-1][0]}" if flow_buckets else ""
        else:
            flow_buckets = cattxn_period_buckets(cattxn_df, "월별")
            flow_period_note = "2026년 전체 · 월별"

        if not flow_buckets:
            st.info("표시할 데이터가 없습니다.")
        else:
            trend_table = cattxn_group_trend_table(
                cattxn_df, flow_buckets, flow_channel, cattxn_txn_filter,
                group_by=flow_group_by, category=cattxn_category_filter, brand=cattxn_brand_filter,
                mode=cattxn_mode,
            )
            latest_col_label = "최근 일평균 거래액" if cattxn_mode == "일평균" else "최근 거래액"
            trend_display = pd.DataFrame({
                flow_group_label: trend_table["group"],
                "추이": trend_table["trend"],
                latest_col_label: trend_table["latest"],
                "직전 대비": trend_table["delta_pct"],
            })
            st.dataframe(
                trend_display,
                column_config={
                    flow_group_label: st.column_config.TextColumn(flow_group_label, width="small"),
                    "추이": st.column_config.LineChartColumn("추이", width="medium", y_min=0),
                    latest_col_label: st.column_config.NumberColumn(latest_col_label, format="%d"),
                    "직전 대비": st.column_config.NumberColumn("직전 대비", format="%.1f%%"),
                },
                use_container_width=True, hide_index=True,
                height=min(35 * (len(trend_display) + 1) + 3, 560),
            )
            st.caption(f"📅 {flow_period_note}  ·  {'일평균' if cattxn_mode == '일평균' else '누계'} 기준, 거래액이 큰 순서로 정렬했습니다. "
                      f"마지막 구간이 아직 끝나지 않은 부분기간이어도 일평균으로 맞춰서 공정하게 비교됩니다.")

        render_section_title(f"카테고리별 비교(스냅샷) · {cattxn_cur_label} ({cattxn_mode}{cattxn_txn_suffix})")
        cattxn_rank_metric = st.radio("비교 지표", ["거래액", "객단가"], horizontal=True, key="cattxn_rank_metric")

        cattxn_rank = aggregate_cattxn_by(cattxn_view, "category", cattxn_txn_filter, brand=cattxn_brand_filter)
        ad_col = f"쇼핑검색광고_{cattxn_rank_metric}"
        ep_col = f"EP채널_{cattxn_rank_metric}"
        if cattxn_mode == "일평균" and cattxn_cur_days and cattxn_rank_metric == "거래액":
            cattxn_rank[ad_col] = cattxn_rank[ad_col] / cattxn_cur_days
            cattxn_rank[ep_col] = cattxn_rank[ep_col] / cattxn_cur_days
        cattxn_rank = cattxn_rank.sort_values(ad_col, ascending=False)

        cattxn_is_million = cattxn_rank_metric == "거래액"
        fig_cattxn = go.Figure()
        fig_cattxn.add_trace(go.Bar(
            x=cattxn_rank["category"],
            y=_to_million(cattxn_rank[ep_col]) if cattxn_is_million else cattxn_rank[ep_col],
            name="EP채널", marker_color="#CBD5E1"))
        fig_cattxn.add_trace(go.Bar(
            x=cattxn_rank["category"],
            y=_to_million(cattxn_rank[ad_col]) if cattxn_is_million else cattxn_rank[ad_col],
            name="쇼핑검색광고", marker_color="#2563EB"))
        fig_cattxn.update_layout(
            barmode="group", height=420, margin=dict(t=20, b=20, l=10, r=10),
            yaxis=_money_axis(f"{cattxn_rank_metric} ({cattxn_mode})" if cattxn_is_million else "객단가", cattxn_is_million),
            hovermode="closest",
            dragmode="pan",
        )
        st.plotly_chart(fig_cattxn, use_container_width=True, config={"scrollZoom": True})

        cattxn_table_display = pd.DataFrame({
            "카테고리": cattxn_rank["category"],
            f"쇼핑검색광고 {cattxn_rank_metric}": cattxn_rank[ad_col].apply(lambda v: format_cattxn_table_value(cattxn_rank_metric, v)),
            f"EP채널 {cattxn_rank_metric}": cattxn_rank[ep_col].apply(lambda v: format_cattxn_table_value(cattxn_rank_metric, v)),
        })
        st.dataframe(
            style_channel_columns(cattxn_table_display.style, cattxn_table_display.columns),
            use_container_width=True, hide_index=True,
        )

        st.download_button(
            "📥 Excel 다운로드",
            data=to_excel_bytes(cattxn_rank),
            file_name=f"카테고리별실적_{cattxn_start_ts.date()}_{cattxn_end_ts.date()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="dl_cattxn_rank",
        )

        # ── 카테고리별 거래액 랭킹 · 전년비·전주비(EP리포트 스타일) ──
        render_section_title(f"카테고리별 거래액 랭킹 · 전년비·{cattxn_immediate_label}{cattxn_txn_suffix}")
        cattxn_cat_yoy_channel = st.radio(
            "채널", ["전체(Total)", "쇼핑검색광고", "EP채널"], horizontal=True, key="cattxn_cat_yoy_channel",
        )
        cattxn_cat_yoy = cattxn_group_yoy_wow(
            cattxn_df, "category", cattxn_start_ts, cattxn_end_ts, cattxn_comp_periods,
            cattxn_txn_filter, brand=cattxn_brand_filter,
            channel="전체" if cattxn_cat_yoy_channel == "전체(Total)" else cattxn_cat_yoy_channel,
        )
        if cattxn_cat_yoy.empty:
            st.info("표시할 데이터가 없습니다.")
        else:
            cat_yoy_cols = {
                "카테고리": cattxn_cat_yoy["category"],
                "거래액": cattxn_cat_yoy["거래액"].apply(
                    lambda v: format_million(v / cattxn_cur_days) if cattxn_mode == "일평균" and cattxn_cur_days else format_million(v)
                ),
                "비중": cattxn_cat_yoy["비중"].apply(lambda v: f"{v:.1f}%"),
            }
            comp_pct_cols = []
            for lbl in cattxn_comp_periods:
                cat_yoy_cols[lbl] = cattxn_cat_yoy[f"{lbl}(%)"].apply(format_delta_text)
                comp_pct_cols.append(lbl)
                cat_yoy_cols[f"{lbl} 값"] = cattxn_cat_yoy[f"{lbl}_이전값"].apply(
                    lambda v: format_million(v / cattxn_cur_days) if cattxn_mode == "일평균" and cattxn_cur_days else format_million(v)
                )
            cat_yoy_display = pd.DataFrame(cat_yoy_cols)
            render_comparison_table(cat_yoy_display, delta_cols=comp_pct_cols)
            st.caption(f"📅 전년비 기준: 전년 동요일비(364일=52주 전, 요일 정렬) · 거래액은 {cattxn_cat_yoy_channel} 기준입니다.")
            st.caption("📅 비교대상 기간 — " + " · ".join(cattxn_comp_strs))
            st.caption("📁 데이터 출처: category_brand_txn_daily.csv ← 정상이월입점_RAW.xlsx (01·02페이지 태블로 원본과는 별도 집계)")

    # ══════════════════════════════════════════════════════════
    # 탭 3: 브랜드별 상세
    # ══════════════════════════════════════════════════════════
    with tab_brand:
        brand_scope_note = f" · {cattxn_category_filter} 안에서" if cattxn_category_filter != "전체" else " · 전체 카테고리"
        render_section_title(f"브랜드별 비교(스냅샷){brand_scope_note} · {cattxn_cur_label} ({cattxn_mode}{cattxn_txn_suffix})")
        cattxn_brand_rank_metric = st.radio("비교 지표", ["거래액", "객단가"], horizontal=True, key="cattxn_brand_rank_metric")

        cattxn_brand_rank = aggregate_cattxn_by(cattxn_view, "brand", cattxn_txn_filter, category=cattxn_category_filter)
        brand_ad_col = f"쇼핑검색광고_{cattxn_brand_rank_metric}"
        brand_ep_col = f"EP채널_{cattxn_brand_rank_metric}"
        if cattxn_mode == "일평균" and cattxn_cur_days and cattxn_brand_rank_metric == "거래액":
            cattxn_brand_rank[brand_ad_col] = cattxn_brand_rank[brand_ad_col] / cattxn_cur_days
            cattxn_brand_rank[brand_ep_col] = cattxn_brand_rank[brand_ep_col] / cattxn_cur_days
        cattxn_brand_rank = cattxn_brand_rank.sort_values(brand_ad_col, ascending=False)
        cattxn_brand_rank_top = cattxn_brand_rank.head(15)

        brand_is_million = cattxn_brand_rank_metric == "거래액"
        fig_brand = go.Figure()
        fig_brand.add_trace(go.Bar(
            x=cattxn_brand_rank_top["brand"],
            y=_to_million(cattxn_brand_rank_top[brand_ep_col]) if brand_is_million else cattxn_brand_rank_top[brand_ep_col],
            name="EP채널", marker_color="#CBD5E1"))
        fig_brand.add_trace(go.Bar(
            x=cattxn_brand_rank_top["brand"],
            y=_to_million(cattxn_brand_rank_top[brand_ad_col]) if brand_is_million else cattxn_brand_rank_top[brand_ad_col],
            name="쇼핑검색광고", marker_color="#2563EB"))
        fig_brand.update_layout(
            barmode="group", height=420, margin=dict(t=20, b=20, l=10, r=10),
            yaxis=_money_axis(f"{cattxn_brand_rank_metric} ({cattxn_mode})" if brand_is_million else "객단가", brand_is_million),
            xaxis=dict(type="category"), hovermode="closest",
            dragmode="pan",
        )
        st.plotly_chart(fig_brand, use_container_width=True, config={"scrollZoom": True})
        st.caption(f"※ 전체 {len(cattxn_brand_rank)}개 브랜드 중 상위 15개만 차트에 표시합니다. 전체 목록은 아래 표·다운로드에서 확인하세요.")

        cattxn_brand_table_display = pd.DataFrame({
            "브랜드": cattxn_brand_rank["brand"],
            f"쇼핑검색광고 {cattxn_brand_rank_metric}": cattxn_brand_rank[brand_ad_col].apply(lambda v: format_cattxn_table_value(cattxn_brand_rank_metric, v)),
            f"EP채널 {cattxn_brand_rank_metric}": cattxn_brand_rank[brand_ep_col].apply(lambda v: format_cattxn_table_value(cattxn_brand_rank_metric, v)),
        })
        st.dataframe(
            style_channel_columns(cattxn_brand_table_display.style, cattxn_brand_table_display.columns),
            use_container_width=True, hide_index=True, height=350,
        )

        st.download_button(
            "📥 Excel 다운로드",
            data=to_excel_bytes(cattxn_brand_rank),
            file_name=f"브랜드별실적_{cattxn_start_ts.date()}_{cattxn_end_ts.date()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="dl_cattxn_brand_rank",
        )

        # ── 브랜드별 거래액 랭킹 · 전년비·전주비(EP리포트 스타일) ──
        render_section_title(f"브랜드별 거래액 랭킹{brand_scope_note} · 전년비·{cattxn_immediate_label}{cattxn_txn_suffix}")
        cattxn_brand_yoy_channel = st.radio(
            "채널", ["전체(Total)", "쇼핑검색광고", "EP채널"], horizontal=True, key="cattxn_brand_yoy_channel",
        )
        cattxn_brand_yoy = cattxn_group_yoy_wow(
            cattxn_df, "brand", cattxn_start_ts, cattxn_end_ts, cattxn_comp_periods,
            cattxn_txn_filter, category=cattxn_category_filter,
            channel="전체" if cattxn_brand_yoy_channel == "전체(Total)" else cattxn_brand_yoy_channel,
        )
        if cattxn_brand_yoy.empty:
            st.info("표시할 데이터가 없습니다.")
        else:
            brand_yoy_cols = {
                "브랜드": cattxn_brand_yoy["brand"],
                "거래액": cattxn_brand_yoy["거래액"].apply(
                    lambda v: format_million(v / cattxn_cur_days) if cattxn_mode == "일평균" and cattxn_cur_days else format_million(v)
                ),
                "비중": cattxn_brand_yoy["비중"].apply(lambda v: f"{v:.1f}%"),
            }
            brand_comp_pct_cols = []
            for lbl in cattxn_comp_periods:
                brand_yoy_cols[lbl] = cattxn_brand_yoy[f"{lbl}(%)"].apply(format_delta_text)
                brand_comp_pct_cols.append(lbl)
                brand_yoy_cols[f"{lbl} 값"] = cattxn_brand_yoy[f"{lbl}_이전값"].apply(
                    lambda v: format_million(v / cattxn_cur_days) if cattxn_mode == "일평균" and cattxn_cur_days else format_million(v)
                )
            brand_yoy_display = pd.DataFrame(brand_yoy_cols)
            render_comparison_table(brand_yoy_display, delta_cols=brand_comp_pct_cols)
            st.caption(f"※ 전체 {len(brand_yoy_display)}개 브랜드입니다. "
                      f"📅 전년비 기준: 전년 동요일비(364일=52주 전, 요일 정렬) · 거래액은 {cattxn_brand_yoy_channel} 기준입니다.")
            st.caption("📅 비교대상 기간 — " + " · ".join(cattxn_comp_strs))
            st.caption("📁 데이터 출처: category_brand_txn_daily.csv ← 정상이월입점_RAW.xlsx (01·02페이지 태블로 원본과는 별도 집계)")

    # ══════════════════════════════════════════════════════════
    # 탭 4: 거래유형 구성
    # ══════════════════════════════════════════════════════════
    with tab_txn:
        render_section_title(f"정상/이월/입점별 구성 · {cattxn_cur_label}{cattxn_cat_suffix}{cattxn_brand_suffix}")
        cattxn_breakdown = cattxn_txn_type_breakdown(cattxn_view, cattxn_category_filter, cattxn_brand_filter)
        cattxn_breakdown_display = pd.DataFrame({
            "정상/이월/입점": cattxn_breakdown["거래유형"],
            "쇼핑검색광고 거래액": cattxn_breakdown["쇼핑검색광고 거래액"].apply(lambda v: f"{v:,.0f}"),
            "쇼핑검색광고 주문고객수": cattxn_breakdown["쇼핑검색광고 주문고객수"].apply(lambda v: f"{v:,.0f}"),
            "EP채널 거래액": cattxn_breakdown["EP채널 거래액"].apply(lambda v: f"{v:,.0f}"),
            "EP채널 주문고객수": cattxn_breakdown["EP채널 주문고객수"].apply(lambda v: f"{v:,.0f}"),
        })
        st.dataframe(
            style_channel_columns(cattxn_breakdown_display.style, cattxn_breakdown_display.columns),
            use_container_width=True, hide_index=True,
        )
        st.caption("※ 정상/이월/입점 필터와 무관하게 구성을 항상 보여줍니다.")

        # ── 정상/이월/입점 × 카테고리 · 연간 누계(전년 vs 올해) 한눈에 보기 ──
        cattxn_wide_cur_year = cattxn_end_ts.year
        cattxn_wide_prev_year = cattxn_wide_cur_year - 1
        cattxn_wide_cur_start = max(pd.Timestamp(year=cattxn_wide_cur_year, month=1, day=1), pd.Timestamp(CATTXN_MIN_DATE))
        cattxn_wide_cur_end = cattxn_end_ts
        try:
            cattxn_wide_prev_end = pd.Timestamp(year=cattxn_wide_prev_year, month=cattxn_end_ts.month, day=cattxn_end_ts.day)
        except ValueError:  # 2/29처럼 전년에 없는 날짜면 그 달 마지막날로
            cattxn_wide_prev_end = pd.Timestamp(year=cattxn_wide_prev_year, month=cattxn_end_ts.month, day=1) + pd.offsets.MonthEnd(0)
        cattxn_wide_prev_start = max(pd.Timestamp(year=cattxn_wide_prev_year, month=1, day=1), pd.Timestamp(CATTXN_MIN_DATE))

        render_section_title(
            f"정상/이월/입점 × 카테고리 · 연간 비교 ({cattxn_wide_prev_year}년 vs {cattxn_wide_cur_year}년, {cattxn_mode})"
        )
        cattxn_wide_channel = st.radio(
            "채널", ["전체(Total)", "쇼핑검색광고", "EP채널"], horizontal=True, key="cattxn_wide_channel",
        )
        cattxn_wide_cur_days = (cattxn_wide_cur_end - cattxn_wide_cur_start).days + 1
        cattxn_wide_prev_days = (cattxn_wide_prev_end - cattxn_wide_prev_start).days + 1
        st.caption(
            f"📅 {cattxn_wide_prev_year}년: {cattxn_wide_prev_start.date()} ~ {cattxn_wide_prev_end.date()}  ·  "
            f"{cattxn_wide_cur_year}년: {cattxn_wide_cur_start.date()} ~ {cattxn_wide_cur_end.date()} "
            f"(기준일자와 같은 월/일까지 누계 — 연간 진행 정도를 맞춰서 비교합니다) · "
            f"상단 표시방식({cattxn_mode})을 따릅니다."
        )

        def _cattxn_year_group_totals(y_start, y_end):
            sub = cattxn_df[(cattxn_df["date"] >= y_start) & (cattxn_df["date"] <= y_end)]
            g = sub.groupby(["txn_type", "category"])[["ad_거래액", "ep_거래액"]].sum()
            if cattxn_wide_channel == "쇼핑검색광고":
                return g["ad_거래액"]
            if cattxn_wide_channel == "EP채널":
                return g["ep_거래액"]
            return g["ad_거래액"] + g["ep_거래액"]

        cattxn_wide_cur_totals = _cattxn_year_group_totals(cattxn_wide_cur_start, cattxn_wide_cur_end)
        cattxn_wide_prev_totals = _cattxn_year_group_totals(cattxn_wide_prev_start, cattxn_wide_prev_end)

        cattxn_wide_txn_types = ["정상", "이월", "입점"]
        cattxn_wide_groups = ["합계"] + cattxn_wide_txn_types  # 열 합계(정상+이월+입점)를 맨 앞에
        cattxn_wide_rows = []
        for cat in CATTXN_CATEGORY_LIST:
            row = {"카테고리": cat}
            cat_cur_total, cat_prev_total = 0, 0
            for t in cattxn_wide_txn_types:
                cur_v = cattxn_wide_cur_totals.get((t, cat), 0)
                prev_v = cattxn_wide_prev_totals.get((t, cat), 0)
                row[f"{t} · {cattxn_wide_prev_year}년"] = prev_v
                row[f"{t} · {cattxn_wide_cur_year}년"] = cur_v
                row[f"{t} · 전년비"] = pct_change(cur_v, prev_v)
                cat_cur_total += cur_v
                cat_prev_total += prev_v
            row[f"합계 · {cattxn_wide_prev_year}년"] = cat_prev_total
            row[f"합계 · {cattxn_wide_cur_year}년"] = cat_cur_total
            row["합계 · 전년비"] = pct_change(cat_cur_total, cat_prev_total)
            cattxn_wide_rows.append(row)
        cattxn_wide_df = pd.DataFrame(cattxn_wide_rows)

        # 행 합계("합계(전체)" 행): 카테고리 전체를 다 더한 줄 — 맨 위에 고정 노출(스크롤해도
        # 헤더 바로 아래라 항상 보임)되도록 맨 앞에 둔다.
        cattxn_wide_total_row = {"카테고리": "합계(전체)"}
        for g in cattxn_wide_groups:
            prev_col, cur_col = f"{g} · {cattxn_wide_prev_year}년", f"{g} · {cattxn_wide_cur_year}년"
            prev_sum, cur_sum = cattxn_wide_df[prev_col].sum(), cattxn_wide_df[cur_col].sum()
            cattxn_wide_total_row[prev_col] = prev_sum
            cattxn_wide_total_row[cur_col] = cur_sum
            cattxn_wide_total_row[f"{g} · 전년비"] = pct_change(cur_sum, prev_sum)
        cattxn_wide_df = pd.concat([pd.DataFrame([cattxn_wide_total_row]), cattxn_wide_df], ignore_index=True)

        def _wide_scaled(v, is_prev_col):
            if cattxn_mode != "일평균":
                return v
            days = cattxn_wide_prev_days if is_prev_col else cattxn_wide_cur_days
            return v / days if days else v

        cattxn_wide_display_cols = {"카테고리": cattxn_wide_df["카테고리"]}
        cattxn_wide_pct_cols = []
        for g in cattxn_wide_groups:
            prev_col, cur_col = f"{g} · {cattxn_wide_prev_year}년", f"{g} · {cattxn_wide_cur_year}년"
            pct_col = f"{g} · 전년비"
            cattxn_wide_display_cols[cur_col] = cattxn_wide_df[cur_col].apply(lambda v: f"{_wide_scaled(v, False):,.0f}")
            cattxn_wide_display_cols[pct_col] = cattxn_wide_df[pct_col].apply(format_delta_text)
            cattxn_wide_display_cols[f"{pct_col} 값"] = cattxn_wide_df[prev_col].apply(lambda v: f"{_wide_scaled(v, True):,.0f}")
            cattxn_wide_pct_cols.append(pct_col)
        cattxn_wide_display = pd.DataFrame(cattxn_wide_display_cols)

        render_comparison_table(cattxn_wide_display, delta_cols=cattxn_wide_pct_cols, bold_rows={"합계(전체)"})
        st.caption("💡 맨 왼쪽 \"합계\" 열 = 정상+이월+입점 합산 · 맨 위 \"합계(전체)\" 행 = 전체 카테고리 합산")
        st.caption("📁 데이터 출처: category_brand_txn_daily.csv ← 정상이월입점_RAW.xlsx (01·02페이지 태블로 원본과는 별도 집계)")
        st.download_button(
            "📥 Excel 다운로드",
            data=to_excel_bytes(cattxn_wide_df),
            file_name=f"정상이월입점_카테고리_연간비교_{cattxn_wide_prev_year}_{cattxn_wide_cur_year}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="dl_cattxn_wide_year",
        )


# ════════════════════════════════════════════════════════════════
# PAGE 4: 상품군 효율 — 쇼핑검색광고 리포트(NBOS 매칭, 대/중카테고리·브랜드 단위)
# 03페이지(태블로 기반)와 데이터 소스·카테고리 체계가 다른 별도 페이지.
# ════════════════════════════════════════════════════════════════
elif menu == "상품군 효율":
    with st.container(key="page4_filters"):
        c_ref, c_quick, c_mode = st.columns([2, 1.6, 1.3])
        with c_ref:
            if unit == "일별":
                _ensure_default_date("adprod_ref_date", AD_PRODUCT_MAX_DATE, AD_PRODUCT_MIN_DATE, AD_PRODUCT_MAX_DATE)
                ap_ref_date = st.date_input("기준일자", min_value=AD_PRODUCT_MIN_DATE, max_value=AD_PRODUCT_MAX_DATE,
                                            key="adprod_ref_date")
            else:
                ap_ref_options = build_ref_options(unit, AD_PRODUCT_MIN_DATE, AD_PRODUCT_MAX_DATE)
                if not ap_ref_options:
                    st.info(f"'{unit}' 단위로 마감된 구간이 아직 없습니다 (보유 기간: "
                            f"{AD_PRODUCT_MIN_DATE} ~ {AD_PRODUCT_MAX_DATE}). 사이드바에서 '일별'을 선택해주세요.")
                    st.stop()
                ap_label_to_date = dict(ap_ref_options)
                ap_picker_label = "기준 주차" if unit == "주별" else "기준 월"
                _ensure_valid_select("adprod_ref_select", list(ap_label_to_date.keys()))
                ap_chosen = st.selectbox(ap_picker_label, list(ap_label_to_date.keys()), key="adprod_ref_select")
                ap_ref_date = ap_label_to_date[ap_chosen]
        with c_quick:
            st.markdown("<div style='margin-top:1.8rem'></div>", unsafe_allow_html=True)
            render_quick_date_buttons(unit, AD_PRODUCT_MIN_DATE, AD_PRODUCT_MAX_DATE, "adprod_ref_date", "adprod_ref_select")
        with c_mode:
            ap_mode = st.radio("표시방식", ["누계", "일평균"], horizontal=True, index=1, key="adprod_mode")

        # 대/중카테고리 선택지를 "지금 고른 기준일자/기간" 범위로 좁히기 위해, 자사/입점 위젯보다
        # 먼저 기간부터 계산해둔다 (예전엔 전체 기간 통틀어 데이터가 있었는지로만 걸러서,
        # 이번 달엔 실적이 하나도 없는 카테고리가 계속 선택지에 남는 문제가 있었음).
        ap_start_ts, ap_end_ts = get_period_bounds(ap_ref_date, unit, AD_PRODUCT_MIN_DATE, AD_PRODUCT_MAX_DATE)

        c_own, c_large, c_mid = st.columns([1.5, 2, 2])
        with c_own:
            ap_own = st.selectbox("자사/입점", AD_PRODUCT_OWN_OPTIONS, key="adprod_own")
        with c_large:
            # 자사/입점 + 현재 선택한 기간에 실제로 데이터가 있는 대카테고리만 선택지로 보여준다
            # (없는 조합을 골라 빈 화면을 보는 걸 방지).
            ap_period_scope = ad_product_df[
                (ad_product_df["date"] >= ap_start_ts) & (ad_product_df["date"] <= ap_end_ts)
            ]
            if ap_own != "전체":
                ap_period_scope = ap_period_scope[ap_period_scope["자사/입점"] == ap_own]
            ap_large_options = ["전체"] + sorted(ap_period_scope["대카테고리"].unique())
            _ensure_valid_select("adprod_large", ap_large_options)
            ap_large = st.selectbox("대카테고리", ap_large_options, key="adprod_large")
        with c_mid:
            ap_mid_scope = ap_period_scope
            if ap_large != "전체":
                ap_mid_scope = ap_mid_scope[ap_mid_scope["대카테고리"] == ap_large]
            ap_mid_options = ["전체"] + sorted(ap_mid_scope["중카테고리"].unique())
            _ensure_valid_select("adprod_mid", ap_mid_options)
            ap_mid = st.selectbox("중카테고리", ap_mid_options, key="adprod_mid")
    ap_cur_label = period_label(ap_start_ts, ap_end_ts, unit)
    ap_cur_days = days_in_period(ap_start_ts, ap_end_ts)
    ap_scope_note = " · ".join(
        v for v in [ap_own if ap_own != "전체" else None, ap_large if ap_large != "전체" else None,
                    ap_mid if ap_mid != "전체" else None] if v
    )

    render_page_header(
        eyebrow="쇼핑검색광고 리포트 · NBOS 매칭",
        title=f"상품군 효율 — {ap_cur_label}" + (f" · {ap_scope_note}" if ap_scope_note else ""),
        sub=f"조회단위: {unit}  ·  표시방식: {ap_mode}  ·  집계기간: {ap_start_ts.date()} ~ {ap_end_ts.date()} ({ap_cur_days}일)",
    )
    st.markdown(
        '<div class="kpi-footnote">※ 이 페이지의 대카테고리·중카테고리·브랜드명은 03페이지(태블로 기반, EP 비교)와 '
        '체계가 다른 이 광고 리포트 자체의 분류입니다 — 서로 직접 매핑되지 않습니다. '
        '<b>판매액</b>은 NBOS 매칭 실매출 기준이며, 광고 플랫폼이 자체 귀속하는 "전환매출액"과는 다릅니다 — '
        '전환매출액은 간접전환까지 넓게 잡아 실매출보다 크게 부풀려질 수 있어 ROAS 계산에서 의도적으로 제외했습니다. '
        f'현재 데이터 보유 기간: {AD_PRODUCT_MIN_DATE} ~ {AD_PRODUCT_MAX_DATE} '
        '(과거 기간은 원본을 추가로 변환해 순차적으로 백필 예정이며, 기간이 늘어날수록 전주비·전월비·전년비가 순차 활성화됩니다).</div>',
        unsafe_allow_html=True,
    )

    ap_view = ad_product_df[(ad_product_df["date"] >= ap_start_ts) & (ad_product_df["date"] <= ap_end_ts)]
    if ap_view.empty:
        st.warning("선택한 기간에 데이터가 없습니다.")
        st.stop()

    ap_agg = aggregate_ad_product(ap_view, ap_own, ap_large, ap_mid)

    def ap_scaled(metric, value, days):
        if value is None:
            return None
        if ap_mode == "일평균" and metric in AD_PRODUCT_BASE_METRICS and days:
            return value / days
        return value

    # ── 비교기간 (전일/전주/전월비 + 전년비) — 보유 기간이 짧으면 일부만 존재 ──
    ap_comp_periods = get_comparison_periods(ap_ref_date, unit, AD_PRODUCT_MIN_DATE, AD_PRODUCT_MAX_DATE)
    ap_comp_aggs, ap_comp_days = {}, {}
    for label, (p_start, p_end) in ap_comp_periods.items():
        p_view = ad_product_df[(ad_product_df["date"] >= p_start) & (ad_product_df["date"] <= p_end)]
        ap_comp_aggs[label] = aggregate_ad_product(p_view, ap_own, ap_large, ap_mid) if not p_view.empty else None
        ap_comp_days[label] = days_in_period(p_start, p_end)

    def ap_format_value(metric, value):
        if value is None:
            return None
        if metric in ("판매액", "광고비"):
            return format_million(value)
        if metric == "ROAS":
            return format_roas_percent(value)
        if metric == "CVR":
            return f"{value * 100:.2f}%"
        return f"{value:,.0f}"  # 구매수량 · 객단가

    def ap_deltas_for(metric):
        out = []
        cur_v = ap_scaled(metric, ap_agg[metric], ap_cur_days)
        for label, p_agg in ap_comp_aggs.items():
            prev_raw = p_agg[metric] if p_agg else None
            prev_v = ap_scaled(metric, prev_raw, ap_comp_days[label])
            out.append((label, pct_change(cur_v, prev_v), ap_format_value(metric, prev_v)))
        return out

    ap_kpi_metrics = ["판매액", "광고비", "ROAS", "CVR", "구매수량", "객단가"]
    ap_kpi_label_map = {
        "판매액": "판매액", "광고비": "광고비", "ROAS": "ROAS(판매액 기준)", "CVR": "CR(구매/클릭)",
        "구매수량": "구매건수", "객단가": "객단가",
    }
    ap_cards = []
    for m in ap_kpi_metrics:
        v = ap_scaled(m, ap_agg[m], ap_cur_days)
        ap_cards.append({"label": ap_kpi_label_map[m], "value": ap_format_value(m, v), "deltas": ap_deltas_for(m)})
    render_kpi_cards(ap_cards)
    ap_comp_strs = [
        f"{label} = {period_label(p_start, p_end, unit) if p_start <= p_end else '데이터 없음(보유 기간 밖)'}"
        for label, (p_start, p_end) in ap_comp_periods.items()
    ]
    st.caption("📅 비교대상 기간 — " + " · ".join(ap_comp_strs) +
              "  (해당 기간에 데이터가 아직 없으면 배지가 '-'로 표시됩니다)")

    ap_immediate_label = next(iter(ap_comp_periods.keys()))
    ap_prev_start, ap_prev_end = ap_comp_periods[ap_immediate_label]

    # ── 핵심 요약 (규칙 기반 자동 인사이트) — 대카테고리 기준 성과 분포를 항상 보여준다 ──
    ap_default_rank = ad_product_group_compare(
        ad_product_df, "대카테고리", ap_start_ts, ap_end_ts, ap_prev_start, ap_prev_end,
        ap_own, ap_large, ap_mid,
    )
    ap_insight_lines = []
    if not ap_default_rank.empty:
        perf_counts = ap_default_rank["성과"].value_counts()
        good_n = int(perf_counts.get("🟢 우수(증액 검토)", 0))
        watch_n = int(perf_counts.get("🟡 물량↑효율↓(점검 필요)", 0))
        bad_n = int(perf_counts.get("🔴 부진(축소·재검토)", 0))
        if good_n or watch_n or bad_n:
            ap_insight_lines.append(
                f"대카테고리 {len(ap_default_rank)}개 중 🟢 우수 {good_n}개 · 🟡 점검 필요 {watch_n}개 · "
                f"🔴 부진 {bad_n}개입니다 ({ap_immediate_label} 기준)."
            )
        top_sale = ap_default_rank.sort_values("판매액_증감", ascending=False, na_position="last").iloc[0]
        if pd.notna(top_sale["판매액_증감"]) and top_sale["판매액_증감"] > 10:
            ap_insight_lines.append(
                f"**{top_sale['대카테고리']}**의 판매액이 {ap_immediate_label} {format_delta_text(top_sale['판매액_증감'])}로 "
                f"가장 큰 폭으로 늘었습니다 (ROAS {format_delta_text(top_sale['ROAS_증감']) if pd.notna(top_sale['ROAS_증감']) else '-'})."
            )
        bottom_sale = ap_default_rank.sort_values("판매액_증감", ascending=True, na_position="last").iloc[0]
        if pd.notna(bottom_sale["판매액_증감"]) and bottom_sale["판매액_증감"] < -10:
            ap_insight_lines.append(
                f"**{bottom_sale['대카테고리']}**의 판매액이 {ap_immediate_label} {format_delta_text(bottom_sale['판매액_증감'])}로 "
                f"가장 크게 줄었습니다."
            )
        # 증감률(%)만 보면 기저값이 작은 카테고리가 과장돼 보일 수 있어, 절대 증감액(원) 기준
        # 1위도 같이 보여준다 — 실제 매출 영향이 가장 큰 곳이 어디인지 놓치지 않기 위함.
        top_abs = ap_default_rank.sort_values("판매액_증감액", ascending=False).iloc[0]
        if top_abs["판매액_증감액"] > 0:
            ap_insight_lines.append(
                f"절대액 기준으로는 **{top_abs['대카테고리']}**의 판매액이 {ap_immediate_label} 가장 크게 늘었습니다 "
                f"({format_million(top_abs['판매액_전기'])} → {format_million(top_abs['판매액'])}, "
                f"▲{format_million(top_abs['판매액_증감액'])} 증가)."
            )
        bottom_abs = ap_default_rank.sort_values("판매액_증감액", ascending=True).iloc[0]
        if bottom_abs["판매액_증감액"] < 0:
            ap_insight_lines.append(
                f"절대액 기준으로는 **{bottom_abs['대카테고리']}**의 판매액이 {ap_immediate_label} 가장 크게 줄었습니다 "
                f"({format_million(bottom_abs['판매액_전기'])} → {format_million(bottom_abs['판매액'])}, "
                f"▼{format_million(abs(bottom_abs['판매액_증감액']))} 감소)."
            )
    render_insight_box(ap_insight_lines)

    # ── 실적 퍼널 (노출 → 클릭 → 구매) — 상단 자사/입점·대/중카테고리 필터를 그대로 반영.
    # ad_product 리포트에는 UV(방문) 개념이 없어(광고 클릭→매칭된 구매만 추적) 01페이지와
    # 달리 3단계로 구성한다.
    ap_title_col, ap_title_pill_col = st.columns([2.4, 1.6])
    with ap_title_col:
        render_section_title(
            f"실적 퍼널 (노출 → 클릭 → 구매)" + (f" · {ap_scope_note}" if ap_scope_note else "") + f" · {ap_mode}"
        )
    with ap_title_pill_col:
        st.markdown("<div style='margin-top:26px'></div>", unsafe_allow_html=True)
        with st.container(key="pill_ap_diag_metric"):
            ap_diag_metric = st.radio(
                "정렬 기준(TOP5)", ["구매전환", "판매액"], horizontal=True,
                label_visibility="collapsed", key="adprod_diag_metric",
            )
    ap_funnel_stages = ["노출수", "클릭수", "구매수량"]
    ap_funnel_labels = ["노출", "클릭", "구매"]
    ap_funnel_vals = [ap_scaled(m, ap_agg[m], ap_cur_days) for m in ap_funnel_stages]

    ap_funnel_deltas = []
    ap_funnel_yoy_deltas = []
    for m in ap_funnel_stages:
        d = ap_deltas_for(m)
        d_label, d_pct, d_prev = d[0]
        ap_funnel_deltas.append(
            f"{d_label} {format_delta_text(d_pct)} ({d_prev})" if d_pct is not None and d_prev else
            (f"{d_label} {format_delta_text(d_pct)}" if d_pct is not None else f"{d_label} -")
        )
        yoy_entry = next((x for x in d if x[0] == "전년비"), None)
        yoy_pct = yoy_entry[1] if yoy_entry else None
        yoy_prev = yoy_entry[2] if yoy_entry else None
        ap_funnel_yoy_deltas.append(
            f"전년비 {format_delta_text(yoy_pct)} ({yoy_prev})" if yoy_pct is not None and yoy_prev else
            (f"전년비 {format_delta_text(yoy_pct)}" if yoy_pct is not None else "전년비 -")
        )

    # 물량이 아니라 전환율(CTR=클릭/노출, CVR=구매/클릭) 기준으로 가장 부진한 구간 진단 —
    # 01페이지 퍼널과 동일한 방식, 전년비가 있으면 우선 사용하고 없으면 직전기간으로 대체.
    ap_stage_rate_defs = [("CTR", 1), ("CVR", 2)]  # (지표, 퍼널 단계 인덱스)
    ap_yoy_agg = ap_comp_aggs.get("전년비")
    ap_rate_candidates = []
    for metric, idx in ap_stage_rate_defs:
        cur_r = ap_agg[metric]
        pct, basis = (pct_change(cur_r, ap_yoy_agg[metric]), "전년비") if ap_yoy_agg is not None else (None, None)
        if pct is None:
            imm_label, imm_pct, _ = ap_deltas_for(metric)[0]
            pct, basis = imm_pct, imm_label
        if pct is not None:
            ap_rate_candidates.append((idx, metric, pct, basis))

    ap_weak_index, ap_weak_note = None, None
    if ap_rate_candidates:
        w_idx, w_metric, w_pct, w_basis = min(ap_rate_candidates, key=lambda x: x[2])
        if w_pct < 0:
            ap_weak_index, ap_weak_note = w_idx, f"{w_metric} {w_basis} {format_delta_text(w_pct)}"

    ap_funnel_col, ap_diag_col = st.columns([2.3, 1.7])
    with ap_funnel_col:
        render_custom_funnel(
            ap_funnel_labels, ap_funnel_vals, deltas=ap_funnel_deltas, yoy_deltas=ap_funnel_yoy_deltas,
            sub_labels=[f"{ap_cur_label} · {ap_mode}"] * 3,
            colors=["#2563EB", "#0EA5E9", "#22C55E"],
            weak_index=ap_weak_index, weak_note=ap_weak_note,
        )
        if ap_weak_index is not None:
            render_colored_caption(f"🔻 **{ap_funnel_labels[ap_weak_index]} 전환 구간이 가장 부진합니다** — {ap_weak_note}.")
        st.caption("💡 상단 필터(자사/입점·대카테고리·중카테고리)를 바꾸면 이 퍼널도 그 범위로 다시 계산됩니다.")
        st.caption(f"📅 전년비 기준: {'정확히 12개월 전 같은 달(마감 실적 기준)' if unit == '월마감' else '전년 동요일비(364일=52주 전, 요일 정렬)'}")

    with ap_diag_col:
        # 상단 필터와 무관하게 항상 "전체" 기준으로 대카테고리별 부진/우수 순위를 보여준다 —
        # 필터를 하나하나 바꿔보지 않아도 어디가 문제인지 바로 알 수 있게.
        # 대/중카테고리 필터는 무시(카테고리를 굳이 안 좁혀도 전체를 훑어보려는 패널의 목적과
        # 맞지 않으므로)하지만, 자사/입점은 "보고 있는 관점" 자체를 바꾸는 선택이라 반영한다.
        # (정렬 기준 알약 버튼은 위쪽 섹션 타이틀 옆으로 이동 — ap_diag_metric은 거기서 정의됨)
        ap_diag_sort_col = "CVR_증감" if ap_diag_metric == "구매전환" else "판매액_증감"
        ap_diag_label = "CVR" if ap_diag_metric == "구매전환" else "판매액"
        ap_diag_other_col = "판매액_증감" if ap_diag_metric == "구매전환" else "CVR_증감"
        ap_diag_other_label = "판매액" if ap_diag_metric == "구매전환" else "CVR"

        ap_diag_rank = ad_product_group_compare(
            ad_product_df, "대카테고리", ap_start_ts, ap_end_ts, ap_prev_start, ap_prev_end,
            ap_own, "전체", "전체",
        )
        ap_diag_valid = ap_diag_rank[ap_diag_rank[ap_diag_sort_col].notna()]
        ap_diag_worst = ap_diag_valid.sort_values(ap_diag_sort_col).head(5)
        ap_diag_best = ap_diag_valid.sort_values(ap_diag_sort_col, ascending=False).head(5)
        ap_own_note = ap_own if ap_own != "전체" else "자사+입점 전체"

        def _diag_lines(rows, positive: bool):
            lines = []
            for _, row in rows.iterrows():
                if (row[ap_diag_sort_col] > 0) != positive:
                    continue
                prev_v, cur_v = row.get(f"{ap_diag_label}_전기"), row.get(ap_diag_label)
                change_str = (
                    f" ({ap_format_value(ap_diag_label, prev_v)} → {ap_format_value(ap_diag_label, cur_v)})"
                    if prev_v is not None and cur_v is not None else ""
                )
                lines.append(
                    f"**{row['대카테고리']}** — {ap_diag_label} {format_delta_text(row[ap_diag_sort_col])}"
                    f"{change_str} · {ap_diag_other_label} {format_delta_text(row[ap_diag_other_col])}"
                )
            return lines

        worst_lines = _diag_lines(ap_diag_worst, positive=False)
        render_insight_box(
            worst_lines or [f"{ap_own_note} 기준, 카테고리 전반에서 뚜렷한 {ap_diag_metric} 부진 신호가 없습니다."],
            title=f"{ap_diag_metric} 부진 TOP5 ({ap_immediate_label} · {ap_own_note} · 카테고리 필터 무관)",
            tone="danger",
        )
        best_lines = _diag_lines(ap_diag_best, positive=True)
        render_insight_box(
            best_lines or [f"{ap_own_note} 기준, 카테고리 전반에서 뚜렷한 {ap_diag_metric} 개선 신호가 없습니다."],
            title=f"{ap_diag_metric} 우수 TOP5 ({ap_immediate_label} · {ap_own_note} · 카테고리 필터 무관)",
            tone="success",
        )

    render_section_title("랭킹 · 직전기간 대비 증감")
    ap_r1, ap_r2, ap_r3 = st.columns([2.2, 2.5, 2])
    with ap_r1:
        ap_group_label = st.radio("기준", ["대카테고리", "중카테고리", "브랜드"], horizontal=True, key="adprod_group")
    with ap_r2:
        ap_sort_metric = st.radio("정렬", ["판매액", "광고비", "ROAS", "판매액 증감률"], horizontal=True, key="adprod_sort")
    with ap_r3:
        ap_perf_filter = st.radio("성과 필터", ["전체", "🟢 우수만", "🔴 부진만"], horizontal=True, key="adprod_perf_filter")
    ap_group_col = {"대카테고리": "대카테고리", "중카테고리": "중카테고리", "브랜드": "브랜드명"}[ap_group_label]

    ap_rank = ad_product_group_compare(
        ad_product_df, ap_group_col, ap_start_ts, ap_end_ts, ap_prev_start, ap_prev_end,
        ap_own, ap_large, ap_mid,
    ) if ap_group_col != "대카테고리" else ap_default_rank.copy()

    # 중카테고리는 대카테고리 하위 분류라 부모가 뭔지 같이 안 보이면 헷갈린다 — 대카테고리 필터가
    # 특정 카테고리로 좁혀져 있으면 전부 그 값, "전체"면 원본에서 최빈 대카테고리를 찾아 붙인다.
    if ap_group_col == "중카테고리":
        if ap_large != "전체":
            ap_rank["대카테고리"] = ap_large
        else:
            _midcat_map = ad_product_df.groupby("중카테고리")["대카테고리"].agg(
                lambda s: s.mode().iat[0] if len(s.mode()) else s.iloc[0]
            ).to_dict()
            ap_rank["대카테고리"] = ap_rank["중카테고리"].map(_midcat_map)

    if ap_perf_filter == "🟢 우수만":
        ap_rank = ap_rank[ap_rank["성과"] == "🟢 우수(증액 검토)"]
    elif ap_perf_filter == "🔴 부진만":
        ap_rank = ap_rank[ap_rank["성과"] == "🔴 부진(축소·재검토)"]

    ap_sort_col = "판매액_증감" if ap_sort_metric == "판매액 증감률" else ap_sort_metric
    ap_rank = ap_rank.sort_values(ap_sort_col, ascending=False, na_position="last")
    ap_rank_total = len(ap_rank)
    if ap_group_col == "브랜드명":
        ap_rank = ap_rank.head(20)

    if ap_rank.empty:
        st.info("조건에 해당하는 항목이 없습니다.")
    else:
        # st.dataframe은 마크다운(**볼드**)을 텍스트 그대로 렌더링하지 않아서(글자 단위 스타일
        # 불가) "이전"/"현재"를 아예 별도 컬럼으로 나누고, "현재" 컬럼 전체에 Styler로
        # font-weight를 줘서 굵게 강조한다.
        ap_display = pd.DataFrame({
            **({"대카테고리": ap_rank["대카테고리"]} if ap_group_col == "중카테고리" else {}),
            ap_group_label: ap_rank[ap_group_col],
            "성과": ap_rank["성과"],
            f"판매액 (이전)": ap_rank["판매액_전기"].apply(lambda v: f"{v:,.0f}"),
            f"판매액 (현재)": ap_rank["판매액"].apply(lambda v: f"{v:,.0f}"),
            f"판매액 {ap_immediate_label}": ap_rank["판매액_증감"].apply(format_delta_text),
            f"광고비 (이전)": ap_rank["광고비_전기"].apply(lambda v: f"{v:,.0f}"),
            f"광고비 (현재)": ap_rank["광고비"].apply(lambda v: f"{v:,.0f}"),
            f"광고비 {ap_immediate_label}": ap_rank["광고비_증감"].apply(format_delta_text),
            f"ROAS (이전)": ap_rank["ROAS_전기"].apply(lambda v: f"{v * 100:,.0f}%"),
            f"ROAS (현재)": ap_rank["ROAS"].apply(lambda v: f"{v * 100:,.0f}%"),
            f"ROAS {ap_immediate_label}": ap_rank["ROAS_증감"].apply(format_delta_text),
            f"CR(구매/클릭) (이전)": ap_rank["CVR_전기"].apply(lambda v: f"{v * 100:.2f}%"),
            f"CR(구매/클릭) (현재)": ap_rank["CVR"].apply(lambda v: f"{v * 100:.2f}%"),
            f"CR {ap_immediate_label}": ap_rank["CVR_증감"].apply(format_delta_text),
            "구매건수": ap_rank["구매수량"].apply(lambda v: f"{v:,.0f}"),
            "객단가": ap_rank["객단가"].apply(lambda v: f"{v:,.0f}"),
        })
        ap_current_cols = ["판매액 (현재)", "광고비 (현재)", "ROAS (현재)", "CR(구매/클릭) (현재)"]
        st.dataframe(
            ap_display.style.map(
                delta_cell_style,
                subset=[f"판매액 {ap_immediate_label}", f"광고비 {ap_immediate_label}",
                        f"ROAS {ap_immediate_label}", f"CR {ap_immediate_label}"],
            ).set_properties(subset=ap_current_cols, **{"font-weight": "700", "color": "#0F172A"}),
            use_container_width=True, hide_index=True,
            height=min(35 * (len(ap_display) + 1) + 3, 560),
        )
    ap_prev_label_str = period_label(ap_prev_start, ap_prev_end, unit) if ap_prev_start <= ap_prev_end else "데이터 없음(보유 기간 밖)"
    st.caption(
        f"📅 비교기준: {ap_immediate_label} = {ap_prev_label_str}  ·  "
        + (f"※ 전체 {ap_rank_total}개 브랜드 중 {ap_sort_metric} 상위 20개만 표시합니다.  ·  " if ap_group_col == "브랜드명" else "")
        + "💡 🟢 우수(판매액·ROAS 동반상승)=증액 검토 · 🟡 물량↑효율↓=소재/입찰 점검 · "
          "🔵 효율 개선=회복 여지 · 🔴 부진(둘 다 하락)=축소·재검토 대상입니다. (±5%p 이내 변화는 ⚫ 변화 미미로 취급)"
    )
