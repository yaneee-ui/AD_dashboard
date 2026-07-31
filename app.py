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
    load_category_data, aggregate_category, aggregate_category_by,
    category_bucket_yoy_series, category_dual_channel_series,
    category_txn_type_breakdown, TXN_TYPE_OPTIONS,
    load_fitflop_data, fitflop_roas,
)
from styles import (
    inject_css, render_kpi_cards, render_page_header, render_section_title,
    pct_change, format_delta_text, delta_cell_style,
)

st.set_page_config(page_title="쇼핑검색광고 실적 대시보드", layout="wide")
inject_css()

# ── 데이터 로드 ────────────────────────────────────────────────────
df = load_data()
MIN_DATE, MAX_DATE = df["date"].min().date(), df["date"].max().date()

cat_df = load_category_data()
CAT_MIN_DATE, CAT_MAX_DATE = cat_df["date"].min().date(), cat_df["date"].max().date()
CATEGORY_LIST = sorted(cat_df["category"].unique())

ALL_METRICS = ["노출수", "클릭수", "UV", "광고비"] + list(RATIO_DEFS.keys()) + [
    "거래액", "거래액(총)", "결제고객수", "결제고객수(총)",
    "가입수", "첫구매수", "첫구매거래액", "신규고객수", "신규거래액",
]
ALL_METRICS = list(dict.fromkeys(ALL_METRICS))  # 중복 제거, 순서 유지

# ── 사이드바 메뉴 ──────────────────────────────────────────────────
st.sidebar.markdown("### 🛍️ 쇼핑검색광고 · 네이버")
menu = st.sidebar.radio(
    "메뉴",
    ["📋 01. 쇼핑검색광고 실적", "📈 02. 전년비교", "📊 03. 카테고리별 실적", "🧩 04. 핏플랍 제외 비교"],
    label_visibility="collapsed",
)
if "01" in menu:
    menu = "쇼핑검색광고 실적"
elif "02" in menu:
    menu = "전년비교"
elif "03" in menu:
    menu = "카테고리별 실적"
else:
    menu = "핏플랍 제외 비교"
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
        mode = st.radio("표시방식", ["누계", "일평균"], horizontal=True)

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
        if metric in ("거래액", "광고비"):
            return format_million(value)
        if metric == "ROAS":
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
    kpi_metrics = ["거래액", "광고비", "ROAS", "UV", "결제고객수", "첫구매수"]
    cards = []
    for m in kpi_metrics:
        display_val = scaled(m, agg[m], cur_days)
        label_txt = m if m not in BASE_METRICS else f"{m} · {mode}"
        value_str = format_kpi_value(m, display_val)
        cards.append({"label": label_txt, "value": value_str, "deltas": deltas_for(m)})

    render_kpi_cards(cards)
    st.markdown(
        '<div class="kpi-footnote">※ 거래액·광고비·UV 등 수량·금액 지표는 선택한 '
        f'표시방식({mode}) 기준이며, ROAS·CR·CTR 등 비율지표는 합산이 아닌 재산정한 값입니다.</div>',
        unsafe_allow_html=True,
    )

    # ── 실적요약 (직전기간 대비) 테이블 ──
    immediate_label = next(iter(comp_periods.keys()))
    prev_agg_for_table = comp_aggs.get(immediate_label)
    prev_days_for_table = comp_days[immediate_label]
    prev_start, prev_end = comp_periods[immediate_label]

    render_section_title(f"실적요약 · {immediate_label} 비교 ({mode})")

    summary_metrics = ["노출수", "클릭수", "CTR", "CR", "객단가", "결제고객수",
                       "CPC", "CPUV", "UV", "광고비", "거래액", "ROAS"]
    prev_col_name = period_label(prev_start, prev_end, unit)
    rows = []
    for m in summary_metrics:
        cur_v = scaled(m, agg[m], cur_days)
        prev_raw = prev_agg_for_table[m] if prev_agg_for_table else None
        prev_v = scaled(m, prev_raw, prev_days_for_table)
        delta = pct_change(cur_v, prev_v)
        rows.append({
            "지표": m,
            prev_col_name: format_value(m, prev_v) if prev_v is not None else "-",
            cur_label: format_value(m, cur_v),
            f"{immediate_label}(%)": format_delta_text(delta),
        })
    summary_df = pd.DataFrame(rows)

    st.dataframe(
        summary_df.style.map(delta_cell_style, subset=[f"{immediate_label}(%)"]),
        use_container_width=True, hide_index=True, height=460,
    )

    # ── 추이 차트: 2026년 기준 + 전년비 비교선 (조회단위별 집계) ──
    render_section_title(f"2026년 추이 (전년비 비교) · {mode}")
    metric_choice = st.selectbox("지표 선택", ALL_METRICS,
                                  index=ALL_METRICS.index("거래액"))

    buckets = build_2026_buckets(df, unit)
    if not buckets:
        st.info("2026년 데이터가 없거나, 선택한 조회단위 기준으로 마감된 구간이 없습니다.")
    else:
        labels, cur_vals, prev_vals = bucket_yoy_series(df, buckets, metric_choice, mode)
        axis_metric_label = metric_choice if metric_choice not in BASE_METRICS else f"{metric_choice} ({mode})"

        fig = go.Figure()
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

    # ── 데이터 테이블 & 다운로드 ──
    render_section_title(f"{unit} 원본 데이터 · {cur_label}")
    display_cols = ["date"] + ALL_METRICS
    display_df = view[display_cols].sort_values("date", ascending=False)
    st.dataframe(display_df, use_container_width=True, height=350)

    st.download_button(
        "📥 Excel 다운로드",
        data=to_excel_bytes(display_df),
        file_name=f"쇼핑검색광고_실적_{start_ts.date()}_{end_ts.date()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


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
# PAGE 3: 카테고리별 실적 (쇼핑검색광고 vs EP채널 비교)
# ════════════════════════════════════════════════════════════════
elif menu == "카테고리별 실적":
    c_ref, c_mode = st.columns([2.5, 1.5])
    with c_ref:
        if unit == "일별":
            cat_ref_date = st.date_input("기준일자", value=CAT_MAX_DATE,
                                          min_value=CAT_MIN_DATE, max_value=CAT_MAX_DATE,
                                          key="cat_ref_date")
        else:
            cat_ref_options = build_ref_options(unit, CAT_MIN_DATE, CAT_MAX_DATE)
            cat_label_to_date = dict(cat_ref_options)
            picker_label = "기준 주차" if unit == "주별" else "기준 월"
            cat_chosen = st.selectbox(picker_label, list(cat_label_to_date.keys()),
                                       index=0, key="cat_ref_select")
            cat_ref_date = cat_label_to_date[cat_chosen]
    with c_mode:
        cat_mode = st.radio("표시방식", ["누계", "일평균"], horizontal=True, key="cat_mode")

    c_cat, c_txn = st.columns([2, 2])
    with c_cat:
        category_filter = st.selectbox("카테고리", ["전체"] + CATEGORY_LIST, key="cat_filter")
    with c_txn:
        txn_type = st.selectbox("거래유형", TXN_TYPE_OPTIONS, key="cat_txn_type")

    cat_start_ts, cat_end_ts = get_period_bounds(cat_ref_date, unit, CAT_MIN_DATE, CAT_MAX_DATE)
    cat_cur_label = period_label(cat_start_ts, cat_end_ts, unit)
    cat_cur_days = days_in_period(cat_start_ts, cat_end_ts)
    cat_scope_suffix = f" · {category_filter}" if category_filter != "전체" else ""
    txn_suffix = f" · {txn_type}" if txn_type != "전체" else ""

    render_page_header(
        eyebrow="쇼핑검색광고 · EP채널",
        title=f"카테고리별 실적 — {cat_cur_label}{cat_scope_suffix}{txn_suffix}",
        sub=f"조회단위: {unit}  ·  표시방식: {cat_mode}  ·  집계기간: {cat_start_ts.date()} ~ {cat_end_ts.date()} ({cat_cur_days}일)",
    )

    cat_mask = (cat_df["date"] >= cat_start_ts) & (cat_df["date"] <= cat_end_ts)
    cat_view = cat_df.loc[cat_mask].copy()
    cat_view_scope = cat_view if category_filter == "전체" else cat_view[cat_view["category"] == category_filter]

    if cat_view_scope.empty:
        st.warning("선택한 기간/카테고리에 데이터가 없습니다.")
        st.stop()

    cat_agg = aggregate_category(cat_view_scope, txn_type)

    def cat_scaled(value, days):
        if value is None:
            return None
        if cat_mode == "일평균" and days:
            return value / days
        return value

    # ── 비교기간 (전일/전주/전월비 + 전년비) ──
    cat_comp_periods = get_comparison_periods(cat_ref_date, unit, CAT_MIN_DATE, CAT_MAX_DATE)
    cat_comp_aggs, cat_comp_days = {}, {}
    for label, (p_start, p_end) in cat_comp_periods.items():
        p_view = cat_df[(cat_df["date"] >= p_start) & (cat_df["date"] <= p_end)]
        if category_filter != "전체":
            p_view = p_view[p_view["category"] == category_filter]
        cat_comp_aggs[label] = aggregate_category(p_view, txn_type) if not p_view.empty else None
        cat_comp_days[label] = days_in_period(p_start, p_end)

    def cat_deltas_for(metric):
        out = []
        cur_v = cat_scaled(cat_agg[metric], cat_cur_days)
        for label, p_agg in cat_comp_aggs.items():
            prev_raw = p_agg[metric] if p_agg else None
            prev_v = cat_scaled(prev_raw, cat_comp_days[label])
            prev_str = format_million(prev_v) if prev_v is not None else None
            out.append((label, pct_change(cur_v, prev_v), prev_str))
        return out

    # ── KPI 카드: 쇼핑검색광고 거래액 / EP채널 거래액 (동일 기간 비교) ──
    cards = []
    for m, channel_name in [("광고_거래액", "쇼핑검색광고"), ("EP_거래액", "EP채널")]:
        display_val = cat_scaled(cat_agg[m], cat_cur_days)
        value_str = format_million(display_val)
        label_txt = f"{channel_name} 거래액 · {cat_mode}{txn_suffix}"
        cards.append({"label": label_txt, "value": value_str, "deltas": cat_deltas_for(m)})

    render_kpi_cards(cards)
    st.markdown(
        f'<div class="kpi-footnote">※ 거래액은 선택한 표시방식({cat_mode}) · 거래유형({txn_type}) 기준입니다.</div>',
        unsafe_allow_html=True,
    )

    # ── 거래유형별 구성 (정상/이월/입점) ──
    render_section_title(f"거래유형별 구성 · {cat_cur_label}{cat_scope_suffix}")
    breakdown_df = category_txn_type_breakdown(cat_view_scope)
    breakdown_display = pd.DataFrame({
        "거래유형": breakdown_df["거래유형"],
        "쇼핑검색광고 거래액": breakdown_df["쇼핑검색광고 거래액"].apply(
            lambda v: format_million(v / cat_cur_days if cat_mode == "일평균" and cat_cur_days else v)
        ),
        "EP채널 거래액": breakdown_df["EP채널 거래액"].apply(
            lambda v: format_million(v / cat_cur_days if cat_mode == "일평균" and cat_cur_days else v)
        ),
    })
    st.dataframe(breakdown_display, use_container_width=True, hide_index=True)
    st.caption("※ 거래유형 필터와 무관하게 정상/이월/입점 구성을 항상 보여줍니다.")

    # ── 카테고리별 비교 (그룹 막대차트, 항상 전체 12개 카테고리 기준) ──
    render_section_title(f"카테고리별 비교 · {cat_cur_label} ({cat_mode}{txn_suffix})")
    cat_rank = aggregate_category_by(cat_view, "category", txn_type)
    if cat_mode == "일평균" and cat_cur_days:
        cat_rank["광고_거래액"] = cat_rank["광고_거래액"] / cat_cur_days
        cat_rank["EP_거래액"] = cat_rank["EP_거래액"] / cat_cur_days
    cat_rank = cat_rank.sort_values("광고_거래액", ascending=False)

    fig_cat = go.Figure()
    fig_cat.add_trace(go.Bar(x=cat_rank["category"], y=cat_rank["EP_거래액"],
                              name="EP채널", marker_color="#CBD5E1"))
    fig_cat.add_trace(go.Bar(x=cat_rank["category"], y=cat_rank["광고_거래액"],
                              name="쇼핑검색광고", marker_color="#2563EB"))
    fig_cat.update_layout(
        barmode="group", height=420, margin=dict(t=20, b=20, l=10, r=10),
        yaxis_title=f"거래액 ({cat_mode})", hovermode="x unified",
    )
    st.plotly_chart(fig_cat, use_container_width=True)

    cat_table_display = pd.DataFrame({
        "카테고리": cat_rank["category"],
        "쇼핑검색광고 거래액": cat_rank["광고_거래액"].apply(format_million),
        "EP채널 거래액": cat_rank["EP_거래액"].apply(format_million),
    })
    st.dataframe(cat_table_display, use_container_width=True, hide_index=True, height=440)

    st.download_button(
        "📥 Excel 다운로드",
        data=to_excel_bytes(cat_rank),
        file_name=f"카테고리별실적_{cat_start_ts.date()}_{cat_end_ts.date()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="dl_category_rank",
    )

    # ── 2026년 추이: 쇼핑검색광고 vs EP채널 거래액 흐름 직접 비교 (동일 기간, 보조축) ──
    render_section_title(f"거래액 흐름 비교 (쇼핑검색광고 vs EP채널) · {cat_mode}{cat_scope_suffix or ' · 전체'}{txn_suffix}")
    trend_scope = cat_df if category_filter == "전체" else cat_df[cat_df["category"] == category_filter]

    cat_buckets = build_2026_buckets(trend_scope, unit)
    if not cat_buckets:
        st.info("2026년 데이터가 없거나, 선택한 조회단위 기준으로 마감된 구간이 없습니다.")
    else:
        cat_labels, ad_vals, ep_vals = category_dual_channel_series(
            trend_scope, cat_buckets, txn_type, cat_mode
        )

        fig_trend = go.Figure()
        fig_trend.add_trace(go.Scatter(
            x=cat_labels, y=ad_vals, mode="lines+markers", name="쇼핑검색광고",
            line=dict(width=2, color="#2563EB"),
        ))
        fig_trend.add_trace(go.Scatter(
            x=cat_labels, y=ep_vals, mode="lines+markers", name="EP채널",
            line=dict(width=2, color="#94A3B8"), yaxis="y2",
        ))
        fig_trend.update_layout(
            height=440, margin=dict(t=20, b=20, l=10, r=60),
            yaxis=dict(title=f"쇼핑검색광고 거래액 ({cat_mode})"),
            yaxis2=dict(title=f"EP채널 거래액 ({cat_mode})", overlaying="y", side="right"),
            xaxis=dict(type="category", title=None),
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        )
        st.plotly_chart(fig_trend, use_container_width=True)
        st.caption("※ 두 채널의 규모 차이가 커서 좌/우 보조축으로 나눠 흐름(패턴)을 비교합니다. 절대값은 KPI 카드/테이블을 참고하세요.")

    # ── 원본 데이터 테이블 & 다운로드 (정상/이월/입점 원천 포함) ──
    render_section_title(f"{unit} 원본 데이터 · {cat_cur_label}{cat_scope_suffix}")
    cat_display_cols = ["date", "category",
                        "광고_정상", "광고_이월", "광고_입점", "광고_거래액",
                        "EP_정상", "EP_이월", "EP_입점", "EP_거래액"]
    cat_display_df = cat_view_scope[cat_display_cols].sort_values(
        ["date", "category"], ascending=[False, True]
    )
    st.dataframe(cat_display_df, use_container_width=True, height=350)
    st.download_button(
        "📥 Excel 다운로드",
        data=to_excel_bytes(cat_display_df),
        file_name=f"카테고리별_원본데이터_{cat_start_ts.date()}_{cat_end_ts.date()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="dl_category_raw",
    )


# ════════════════════════════════════════════════════════════════
# PAGE 4: 핏플랍 제외 비교
# ════════════════════════════════════════════════════════════════
else:
    ff_df = load_fitflop_data().sort_values("ym").reset_index(drop=True)
    ff_df["ROAS_전체"] = ff_df.apply(lambda r: fitflop_roas(r, "자사_거래액", "자사_광고비"), axis=1)
    ff_df["ROAS_제외"] = ff_df.apply(lambda r: fitflop_roas(r, "핏플랍제외_거래액", "핏플랍제외_광고비"), axis=1)

    ff_month = st.selectbox("기준월", ff_df["ym_label"].tolist()[::-1], index=0, key="ff_month")
    ff_row = ff_df[ff_df["ym_label"] == ff_month].iloc[0]

    render_page_header(
        eyebrow="쇼핑검색광고 · 네이버",
        title=f"핏플랍 제외 비교 — {ff_month}",
        sub="핏플랍 브랜드 퇴점으로 인한 거래액·광고비 왜곡을 제외하고, 자사(정상+이월) 실적의 실제 흐름을 비교합니다.",
    )

    st.markdown(
        '<div class="kpi-footnote">※ 이 페이지는 월별 데이터만 제공됩니다 '
        '(핏플랍 광고비 원본이 월 단위로만 제공되어, 일/주 단위로는 분리할 수 없습니다). '
        '핏플랍 거래액은 정상+이월 기준이며 입점 거래는 제외했습니다.</div>',
        unsafe_allow_html=True,
    )

    render_section_title(f"{ff_month} 요약 — 포함 vs 제외")

    def _fmt_amt(v):
        return format_million(v) if pd.notna(v) else "-"

    def _fmt_roas(v):
        return format_roas_percent(v) if pd.notna(v) else "-"

    summary_rows = [
        {
            "지표": "거래액",
            "포함 (자사 전체)": _fmt_amt(ff_row["자사_거래액"]),
            "핏플랍": _fmt_amt(ff_row["핏플랍_거래액"]),
            "제외 (핏플랍 제외)": _fmt_amt(ff_row["핏플랍제외_거래액"]),
        },
        {
            "지표": "광고비",
            "포함 (자사 전체)": _fmt_amt(ff_row["자사_광고비"]),
            "핏플랍": _fmt_amt(ff_row["핏플랍_광고비"]),
            "제외 (핏플랍 제외)": _fmt_amt(ff_row["핏플랍제외_광고비"]),
        },
        {
            "지표": "ROAS",
            "포함 (자사 전체)": _fmt_roas(ff_row["ROAS_전체"]),
            "핏플랍": "-",
            "제외 (핏플랍 제외)": _fmt_roas(ff_row["ROAS_제외"]),
        },
    ]
    st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

    render_section_title("월별 추이 — 포함(자사 전체) vs 제외(핏플랍 제외)")
    ff_metric = st.selectbox("지표 선택", ["거래액", "광고비", "ROAS"], key="ff_metric")

    if ff_metric == "거래액":
        col_all, col_ex, yaxis_lbl = "자사_거래액", "핏플랍제외_거래액", "거래액"
    elif ff_metric == "광고비":
        col_all, col_ex, yaxis_lbl = "자사_광고비", "핏플랍제외_광고비", "광고비"
    else:
        col_all, col_ex, yaxis_lbl = "ROAS_전체", "ROAS_제외", "ROAS"

    fig_ff = go.Figure()
    fig_ff.add_trace(go.Scatter(
        x=ff_df["ym_label"], y=ff_df[col_all], mode="lines+markers",
        name="포함 (자사 전체)", line=dict(width=2, color="#94A3B8"),
    ))
    fig_ff.add_trace(go.Scatter(
        x=ff_df["ym_label"], y=ff_df[col_ex], mode="lines+markers",
        name="제외 (핏플랍 제외)", line=dict(width=2, color="#2563EB"),
    ))
    fig_ff.update_layout(
        height=420, margin=dict(t=20, b=20, l=10, r=10),
        yaxis_title=yaxis_lbl, xaxis=dict(type="category", title=None),
        hovermode="x unified",
    )
    st.plotly_chart(fig_ff, use_container_width=True)
    st.caption("※ 핏플랍이 퇴점한 이후(2025-11~)에는 핏플랍 거래액·광고비가 0이라 두 선이 겹칩니다.")

    render_section_title("월별 원본 데이터")
    ff_display = pd.DataFrame({
        "월": ff_df["ym_label"],
        "자사 거래액(전체)": ff_df["자사_거래액"].apply(_fmt_amt),
        "핏플랍 거래액": ff_df["핏플랍_거래액"].apply(_fmt_amt),
        "핏플랍 제외 거래액": ff_df["핏플랍제외_거래액"].apply(_fmt_amt),
        "자사 광고비(전체)": ff_df["자사_광고비"].apply(_fmt_amt),
        "핏플랍 광고비": ff_df["핏플랍_광고비"].apply(_fmt_amt),
        "핏플랍 제외 광고비": ff_df["핏플랍제외_광고비"].apply(_fmt_amt),
        "ROAS(전체)": ff_df["ROAS_전체"].apply(_fmt_roas),
        "ROAS(제외)": ff_df["ROAS_제외"].apply(_fmt_roas),
    })
    st.dataframe(ff_display, use_container_width=True, hide_index=True, height=440)

    st.download_button(
        "📥 Excel 다운로드",
        data=to_excel_bytes(ff_df),
        file_name="핏플랍_제외_비교_월별.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="dl_fitflop",
    )
