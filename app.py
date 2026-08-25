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
    load_cattxn_data, aggregate_cattxn, aggregate_cattxn_by,
    cattxn_txn_type_breakdown, cattxn_daily_series,
    cattxn_period_buckets, cattxn_bucket_series, cattxn_flow_matrix,
    CATTXN_TXN_TYPE_OPTIONS, CATTXN_CHANNEL_OPTIONS, CATTXN_METRIC_OPTIONS,
)
from styles import (
    inject_css, render_kpi_cards, render_page_header, render_section_title,
    pct_change, format_delta_text, delta_cell_style,
)

st.set_page_config(page_title="쇼핑검색광고 실적 대시보드", layout="wide")
inject_css()

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

ALL_METRICS = ["노출수", "클릭수", "UV", "광고비"] + list(RATIO_DEFS.keys()) + [
    "거래액", "거래액(총)", "결제고객수", "결제고객수(총)",
    "가입수", "첫구매수", "첫구매거래액", "신규고객수", "신규거래액",
]
ALL_METRICS = list(dict.fromkeys(ALL_METRICS))  # 중복 제거, 순서 유지

# ── 사이드바 메뉴 ──────────────────────────────────────────────────
st.sidebar.markdown("### 🛍️ 쇼핑검색광고 · 네이버")
menu = st.sidebar.radio(
    "메뉴",
    ["📋 01. 쇼핑검색광고 실적", "📈 02. 전년비교", "📊 03. 카테고리별 실적"],
    label_visibility="collapsed",
)
if "01" in menu:
    menu = "쇼핑검색광고 실적"
elif "02" in menu:
    menu = "전년비교"
else:
    menu = "카테고리별 실적"
st.sidebar.markdown("---")
unit = st.sidebar.radio("조회단위", UNIT_OPTIONS, horizontal=True)
st.sidebar.markdown("---")
st.sidebar.caption(f"데이터 기간\n\n{MIN_DATE} ~ {MAX_DATE}")


def to_excel_bytes(data: pd.DataFrame) -> bytes:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        data.to_excel(writer, index=False, sheet_name="data")
    return buf.getvalue()


# ════════════════════════════════════════════════════════════════
# PAGE 1: 쇼핑검색광고 실적
# ════════════════════════════════════════════════════════════════
if menu == "쇼핑검색광고 실적":
    # ── 기준일자: 조회단위에 맞춰 일/주/월 단위로 선택 ──
    with st.container(key="page1_filters"):
        c_ref, c_mode = st.columns([2.5, 1.5])
        with c_ref:
            if unit == "일별":
                ref_date = st.date_input("기준일자", value=MAX_DATE,
                                          min_value=MIN_DATE, max_value=MAX_DATE)
            else:
                ref_options = build_ref_options(unit, MIN_DATE, MAX_DATE)
                label_to_date = dict(ref_options)
                picker_label = "기준 주차" if unit == "주별" else "기준 월"
                chosen = st.selectbox(picker_label, list(label_to_date.keys()), index=0)
                ref_date = label_to_date[chosen]
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

    # ── KPI 카드 ──
    kpi_metrics = ["거래액", "광고비", "ROAS", "CR", "결제고객수", "UV", "거래액(총)", "ROAS(총)"]
    kpi_label_map = {
        "거래액": "순결제거래액",
        "거래액(총)": "총결제거래액",
        "ROAS(총)": "총결제ROAS",
    }
    cards = []
    for m in kpi_metrics:
        display_val = scaled(m, agg[m], cur_days)
        base_label = kpi_label_map.get(m, m)
        label_txt = base_label if m not in BASE_METRICS else f"{base_label} · {mode}"
        value_str = format_kpi_value(m, display_val)
        cards.append({"label": label_txt, "value": value_str, "deltas": deltas_for(m)})

    render_kpi_cards(cards)
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

    # ── 추이 차트: 2026년 기준 + 전년비 비교선 (조회단위별 집계) ──
    render_section_title(f"2026년 추이 (전년비 비교) · {mode}")
    metric_choice = st.selectbox("지표 선택", ALL_METRICS,
                                  index=ALL_METRICS.index("거래액"))

    show_combo = False
    if metric_choice == "거래액":
        show_combo = st.checkbox("광고비 · ROAS 함께 보기 (막대 + 보조축)", value=True, key="trend_combo")

    buckets = build_2026_buckets(df, unit)
    if not buckets:
        st.info("2026년 데이터가 없거나, 선택한 조회단위 기준으로 마감된 구간이 없습니다.")
    else:
        labels, cur_vals, prev_vals = bucket_yoy_series(df, buckets, metric_choice, mode, unit)
        axis_metric_label = metric_choice if metric_choice not in BASE_METRICS else f"{metric_choice} ({mode})"

        fig = go.Figure()

        if show_combo:
            _, ad_cost_vals, _ = bucket_yoy_series(df, buckets, "광고비", mode, unit)
            _, roas_vals, _ = bucket_yoy_series(df, buckets, "ROAS", mode, unit)
            roas_pct_vals = [round(v * 100, 1) if v is not None else None for v in roas_vals]

            fig.add_trace(go.Bar(
                x=labels, y=ad_cost_vals, name="광고비", yaxis="y2",
                marker_color="rgba(148,163,184,0.55)",
            ))
            fig.add_trace(go.Scatter(
                x=labels, y=cur_vals, mode="lines+markers", name="거래액(올해)",
                line=dict(width=2, color="#2563EB"),
                customdata=roas_pct_vals,
                hovertemplate="%{x}<br>거래액: %{y:,.0f}<br>ROAS: %{customdata}%<extra></extra>",
            ))
            fig.add_trace(go.Scatter(
                x=labels, y=prev_vals, mode="lines+markers", name="거래액(전년비)",
                line=dict(width=2, dash="dash", color="#93C5FD"), connectgaps=True,
            ))
            fig.update_layout(
                height=440, margin=dict(t=20, b=20, l=10, r=10),
                xaxis=dict(type="category", title=None),
                yaxis=dict(title=f"거래액 ({mode})"),
                yaxis2=dict(title="광고비", overlaying="y", side="right", showgrid=False),
                hovermode="x unified",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            )
            st.plotly_chart(fig, use_container_width=True)
            st.caption("📊 막대=광고비(우측 보조축) · 거래액 라인에 마우스를 올리면 해당 시점 ROAS%가 함께 표시됩니다.")
        else:
            fig.add_trace(go.Scatter(
                x=labels, y=cur_vals, mode="lines+markers", name="2026년(올해)",
                line=dict(width=2),
            ))
            fig.add_trace(go.Scatter(
                x=labels, y=prev_vals, mode="lines+markers", name="전년비",
                line=dict(width=2, dash="dash"), connectgaps=True,
            ))
            fig.update_layout(
                height=420, margin=dict(t=20, b=20, l=10, r=10),
                yaxis_title=axis_metric_label, xaxis_title=None,
                xaxis=dict(type="category"),
                hovermode="x unified",
            )
            st.plotly_chart(fig, use_container_width=True)

        yoy_basis = "정확히 12개월 전 같은 달(마감 실적 기준)" if unit == "월마감" else "전년 동요일비(364일=52주 전, 요일 정렬)"
        st.caption(f"📅 전년비 비교 기준: {yoy_basis}")


# ════════════════════════════════════════════════════════════════
# PAGE 2: 전년비교
# ════════════════════════════════════════════════════════════════
elif menu == "전년비교":
    render_page_header(
        eyebrow="쇼핑검색광고 · 네이버",
        title="전년비교",
        sub="일자별(전년 동일 요일) 및 월별 누적 기준으로 전년 대비 실적을 비교합니다.",
    )
    tab1, tab2 = st.tabs(["일자별 YoY (전년 동일 요일)", "월별 누적 YoY"])

    # ── TAB 1: 일자별 YoY ──
    with tab1:
        st.caption("선택한 기간을 기준으로, 전년 동일 요일(364일 전)과 비교합니다.")

        c1, c2 = st.columns(2)
        with c1:
            cur_start = st.date_input(
                "비교 시작일", value=MAX_DATE - timedelta(days=6),
                min_value=MIN_DATE + timedelta(days=364), max_value=MAX_DATE,
                key="yoy_start",
            )
        with c2:
            cur_end = st.date_input(
                "비교 종료일", value=MAX_DATE,
                min_value=MIN_DATE + timedelta(days=364), max_value=MAX_DATE,
                key="yoy_end",
            )

        if cur_start > cur_end:
            st.error("시작일이 종료일보다 늦을 수 없습니다.")
            st.stop()

        cur_range = pd.date_range(cur_start, cur_end, freq="D")
        prev_range = yoy_same_weekday_dates(pd.Series(cur_range))

        cur_view = df[df["date"].isin(cur_range)].copy()
        prev_view = df[df["date"].isin(prev_range)].copy()

        if prev_view.empty:
            st.warning("전년 동일 요일에 해당하는 데이터가 없습니다. (데이터 시작일 이전)")
        else:
            cur_agg = aggregate(cur_view)
            prev_agg = aggregate(prev_view)

            metric_choice2 = st.selectbox(
                "지표 선택", ["UV", "거래액", "광고비", "ROAS", "CR", "CTR",
                             "신규거래액", "첫구매수", "가입수"],
                key="yoy_metric",
            )

            v_cur, v_prev = cur_agg[metric_choice2], prev_agg[metric_choice2]
            delta_pct = pct_change(v_cur, v_prev)

            m1, m2, m3 = st.columns(3)
            m1.metric(f"올해 ({cur_start} ~ {cur_end})", format_value(metric_choice2, v_cur))
            m2.metric(f"전년 동일요일 ({prev_range.min().date()} ~ {prev_range.max().date()})",
                      format_value(metric_choice2, v_prev))
            m3.metric("증감률", format_delta_text(delta_pct))

            # 일자별 라인 비교 (순서상 매칭: n번째 날짜끼리)
            cur_sorted = cur_view.sort_values("date").reset_index(drop=True)
            prev_sorted = prev_view.sort_values("date").reset_index(drop=True)
            n = min(len(cur_sorted), len(prev_sorted))

            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(
                x=cur_sorted["date"][:n], y=cur_sorted[metric_choice2][:n],
                mode="lines+markers", name="올해",
            ))
            fig2.add_trace(go.Scatter(
                x=cur_sorted["date"][:n], y=prev_sorted[metric_choice2][:n],
                mode="lines+markers", name="전년(동일요일)",
                line=dict(dash="dash"),
            ))
            fig2.update_layout(
                height=420, margin=dict(t=20, b=20, l=10, r=10),
                yaxis_title=metric_choice2, hovermode="x unified",
            )
            st.plotly_chart(fig2, use_container_width=True)

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

    # ── TAB 2: 월별 누적 YoY ──
    with tab2:
        st.caption("월 단위로 올해와 전년 실적을 비교합니다. (겹치는 월만 표시)")

        monthly = aggregate_by(df.assign(ym=df["date"].dt.to_period("M")), "ym")
        monthly["연도"] = monthly["ym"].dt.year
        monthly["월"] = monthly["ym"].dt.month

        years = sorted(monthly["연도"].unique())
        if len(years) < 2:
            st.warning("비교할 연도 데이터가 충분하지 않습니다.")
        else:
            c1, c2 = st.columns(2)
            with c1:
                year_cur = st.selectbox("비교 연도", years[::-1], index=0)
            with c2:
                year_prev = st.selectbox("기준(전년) 연도", years[::-1],
                                          index=min(1, len(years) - 1))

            metric_choice3 = st.selectbox(
                "지표 선택", ["UV", "거래액", "광고비", "ROAS", "CR", "CTR",
                             "신규거래액", "첫구매수", "가입수"],
                key="yoy_month_metric",
            )

            cur_m = monthly[monthly["연도"] == year_cur].set_index("월")
            prev_m = monthly[monthly["연도"] == year_prev].set_index("월")
            common_months = sorted(set(cur_m.index) & set(prev_m.index))

            if not common_months:
                st.warning("두 연도 간 겹치는 월이 없습니다.")
            else:
                bar_df = pd.DataFrame({
                    "월": [f"{m}월" for m in common_months],
                    f"{year_cur}": [cur_m.loc[m, metric_choice3] for m in common_months],
                    f"{year_prev}": [prev_m.loc[m, metric_choice3] for m in common_months],
                })
                bar_df["YoY(%)"] = [
                    pct_change(bar_df.loc[i, f"{year_cur}"], bar_df.loc[i, f"{year_prev}"])
                    for i in bar_df.index
                ]

                fig3 = go.Figure()
                fig3.add_trace(go.Bar(x=bar_df["월"], y=bar_df[f"{year_prev}"],
                                       name=f"{year_prev}", marker_color="lightgray"))
                fig3.add_trace(go.Bar(x=bar_df["월"], y=bar_df[f"{year_cur}"],
                                       name=f"{year_cur}", marker_color="#4C78A8"))
                fig3.update_layout(
                    barmode="group", height=440,
                    margin=dict(t=20, b=20, l=10, r=10),
                    yaxis_title=metric_choice3, hovermode="x unified",
                )
                st.plotly_chart(fig3, use_container_width=True)

                display_bar_df = bar_df.copy()
                display_bar_df["YoY(%)"] = display_bar_df["YoY(%)"].apply(format_delta_text)
                st.dataframe(
                    display_bar_df.style.format({f"{year_cur}": "{:,.1f}", f"{year_prev}": "{:,.1f}"})
                                        .map(delta_cell_style, subset=["YoY(%)"]),
                    use_container_width=True,
                )
                st.download_button(
                    "📥 Excel 다운로드",
                    data=to_excel_bytes(bar_df),
                    file_name=f"월별YoY_{year_cur}_vs_{year_prev}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_yoy_month",
                )


# ════════════════════════════════════════════════════════════════
# PAGE 3: 카테고리별 실적 (정상/이월/입점, 쇼핑검색광고 vs EP채널)
# ════════════════════════════════════════════════════════════════
else:
    with st.container(key="page3_filters"):
        c_ref, c_mode = st.columns([2.5, 1.5])
        with c_ref:
            if unit == "일별":
                cattxn_ref_date = st.date_input("기준일자", value=CATTXN_MAX_DATE,
                                                 min_value=CATTXN_MIN_DATE, max_value=CATTXN_MAX_DATE,
                                                 key="cattxn_ref_date")
            else:
                cattxn_ref_options = build_ref_options(unit, CATTXN_MIN_DATE, CATTXN_MAX_DATE)
                cattxn_label_to_date = dict(cattxn_ref_options)
                picker_label = "기준 주차" if unit == "주별" else "기준 월"
                cattxn_chosen = st.selectbox(picker_label, list(cattxn_label_to_date.keys()),
                                              index=0, key="cattxn_ref_select")
                cattxn_ref_date = cattxn_label_to_date[cattxn_chosen]
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
    tab_flow, tab_cat, tab_brand, tab_txn = st.tabs([
        "📈 채널 흐름 비교", "📦 카테고리별 상세", "🏷️ 브랜드별 상세", "🔀 거래유형 구성",
    ])

    def _normalize_series(vals):
        base = next((v for v in vals if v not in (None, 0)), None)
        if not base:
            return [None] * len(vals)
        return [(v / base * 100) if v is not None else None for v in vals]

    def _render_single_trend(x_vals, cur_vals, prev_vals, channel_label, metric_label,
                             show_yoy, x_categorical, prev_label="전년 동요일"):
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=x_vals, y=cur_vals, mode="lines+markers", name="26년",
                                  line=dict(width=2, color="#2563EB")))
        if show_yoy:
            fig.add_trace(go.Scatter(x=x_vals, y=prev_vals, mode="lines+markers", name=prev_label,
                                      line=dict(width=2, color="#93C5FD")))
        layout = dict(height=440, margin=dict(t=20, b=20, l=10, r=10),
                      yaxis_title=f"{channel_label} {metric_label}", xaxis_title=None, hovermode="x unified")
        if x_categorical:
            layout["xaxis"] = dict(type="category")
        fig.update_layout(**layout)
        st.plotly_chart(fig, use_container_width=True)

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
                yaxis_title="지수 (시작 시점=100)", xaxis_title=None, hovermode="x unified",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            )
            if x_categorical:
                layout["xaxis"] = dict(type="category")
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)
            st.caption("💡 두 채널을 시작 시점=100으로 지수화해서 같은 축에 겹쳐 그렸습니다 — "
                      "선이 비슷하게 움직이면 흐름이 유사한 것이고, 벌어지면 다르게 움직이는 것입니다.")
        else:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=x_vals, y=ad_vals, mode="lines+markers", name="쇼핑검색광고",
                                      line=dict(width=2, color="#2563EB")))
            fig.add_trace(go.Scatter(x=x_vals, y=ep_vals, mode="lines+markers", name="EP채널",
                                      line=dict(width=2, color="#94A3B8"), yaxis="y2"))
            layout = dict(
                height=440, margin=dict(t=20, b=20, l=10, r=60),
                yaxis=dict(title=f"쇼핑검색광고 {metric_label}"),
                yaxis2=dict(title=f"EP채널 {metric_label}", overlaying="y", side="right"),
                xaxis_title=None, hovermode="x unified",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            )
            if x_categorical:
                layout["xaxis"] = dict(type="category")
            fig.update_layout(**layout)
            st.plotly_chart(fig, use_container_width=True)
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

    # ══════════════════════════════════════════════════════════
    # 탭 2: 카테고리별 상세
    # ══════════════════════════════════════════════════════════
    with tab_cat:
        render_section_title("카테고리·브랜드별 거래액 흐름")
        fc0, fc1, fc2 = st.columns([2, 2, 2])
        with fc0:
            flow_group_label = st.radio("그룹 기준", ["카테고리", "브랜드"], horizontal=True, key="cattxn_flow_group")
        with fc1:
            flow_channel = st.radio("채널", CATTXN_CHANNEL_OPTIONS, horizontal=True, key="cattxn_flow_channel")
        with fc2:
            flow_mode = st.radio("표시", ["절대값", "비중(%)"], horizontal=True, key="cattxn_flow_mode")

        flow_group_by = "category" if flow_group_label == "카테고리" else "brand"
        flow_group_unit = "카테고리" if flow_group_by == "category" else "브랜드"

        if unit == "일별":
            flow_range = pd.date_range(max(CATTXN_MAX_DATE - timedelta(days=29), CATTXN_MIN_DATE), CATTXN_MAX_DATE)
            flow_buckets = [(d.strftime("%m-%d"), [d]) for d in flow_range]
            flow_period_note = f"최근 {len(flow_buckets)}일"
        elif unit == "주별":
            all_weeks_flow = cattxn_period_buckets(cattxn_df, "주별")
            flow_buckets = all_weeks_flow[-12:]
            flow_period_note = f"{flow_buckets[0][0]} ~ {flow_buckets[-1][0]}" if flow_buckets else ""
        else:
            flow_buckets = cattxn_period_buckets(cattxn_df, "월별")
            flow_period_note = "2026년 전체"

        if not flow_buckets:
            st.info("표시할 데이터가 없습니다.")
        else:
            f_labels, f_cats, f_values = cattxn_flow_matrix(
                cattxn_df, flow_buckets, flow_channel, cattxn_txn_filter,
                group_by=flow_group_by, category=cattxn_category_filter, brand=cattxn_brand_filter,
            )

            if flow_mode == "비중(%)":
                totals_per_bucket = [sum(f_values[c][i] for c in f_cats) for i in range(len(f_labels))]
                display_values = {
                    c: [(v / totals_per_bucket[i] * 100) if totals_per_bucket[i] else 0 for i, v in enumerate(f_values[c])]
                    for c in f_cats
                }
                y_title = "비중 (%)"
            else:
                display_values = f_values
                y_title = f"거래액 ({flow_channel})"

            palette = ["#2563EB", "#0EA5E9", "#22C55E", "#F59E0B", "#EF4444", "#8B5CF6", "#EC4899", "#94A3B8"]
            fig_flow = go.Figure()
            for i, c in enumerate(f_cats):
                fig_flow.add_trace(go.Scatter(
                    x=f_labels, y=display_values[c], mode="lines", name=c,
                    stackgroup="one", line=dict(width=0.5, color=palette[i % len(palette)]),
                ))
            fig_flow.update_layout(
                height=460, margin=dict(t=20, b=20, l=10, r=10),
                xaxis=dict(type="category", title=None), yaxis_title=y_title,
                hovermode="x unified",
            )
            st.plotly_chart(fig_flow, use_container_width=True)
            st.caption(f"📅 {flow_period_note}  ·  거래액 상위 7개 {flow_group_unit}는 개별로, 나머지는 '기타'로 묶어 표시합니다."
                      + (f" (카테고리 = {cattxn_category_filter} 범위 안에서 브랜드 비교)" if flow_group_by == "brand" and cattxn_category_filter != "전체" else ""))

        render_section_title(f"카테고리별 비교(스냅샷) · {cattxn_cur_label} ({cattxn_mode}{cattxn_txn_suffix})")
        cattxn_rank_metric = st.radio("비교 지표", ["거래액", "객단가"], horizontal=True, key="cattxn_rank_metric")

        cattxn_rank = aggregate_cattxn_by(cattxn_view, "category", cattxn_txn_filter, brand=cattxn_brand_filter)
        ad_col = f"쇼핑검색광고_{cattxn_rank_metric}"
        ep_col = f"EP채널_{cattxn_rank_metric}"
        if cattxn_mode == "일평균" and cattxn_cur_days and cattxn_rank_metric == "거래액":
            cattxn_rank[ad_col] = cattxn_rank[ad_col] / cattxn_cur_days
            cattxn_rank[ep_col] = cattxn_rank[ep_col] / cattxn_cur_days
        cattxn_rank = cattxn_rank.sort_values(ad_col, ascending=False)

        fig_cattxn = go.Figure()
        fig_cattxn.add_trace(go.Bar(x=cattxn_rank["category"], y=cattxn_rank[ep_col],
                                     name="EP채널", marker_color="#CBD5E1"))
        fig_cattxn.add_trace(go.Bar(x=cattxn_rank["category"], y=cattxn_rank[ad_col],
                                     name="쇼핑검색광고", marker_color="#2563EB"))
        fig_cattxn.update_layout(
            barmode="group", height=420, margin=dict(t=20, b=20, l=10, r=10),
            yaxis_title=f"{cattxn_rank_metric} ({cattxn_mode})" if cattxn_rank_metric == "거래액" else "객단가",
            hovermode="x unified",
        )
        st.plotly_chart(fig_cattxn, use_container_width=True)

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

        fig_brand = go.Figure()
        fig_brand.add_trace(go.Bar(x=cattxn_brand_rank_top["brand"], y=cattxn_brand_rank_top[brand_ep_col],
                                    name="EP채널", marker_color="#CBD5E1"))
        fig_brand.add_trace(go.Bar(x=cattxn_brand_rank_top["brand"], y=cattxn_brand_rank_top[brand_ad_col],
                                    name="쇼핑검색광고", marker_color="#2563EB"))
        fig_brand.update_layout(
            barmode="group", height=420, margin=dict(t=20, b=20, l=10, r=10),
            yaxis_title=f"{cattxn_brand_rank_metric} ({cattxn_mode})" if cattxn_brand_rank_metric == "거래액" else "객단가",
            xaxis=dict(type="category"), hovermode="x unified",
        )
        st.plotly_chart(fig_brand, use_container_width=True)
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
