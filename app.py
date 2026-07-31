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
    get_comparison_periods,
)
from styles import inject_css, render_kpi_cards, render_page_header, render_section_title, pct_change

st.set_page_config(page_title="쇼핑검색광고 실적 대시보드", layout="wide")
inject_css()

# ── 데이터 로드 ────────────────────────────────────────────────────
df = load_data()
MIN_DATE, MAX_DATE = df["date"].min().date(), df["date"].max().date()

ALL_METRICS = ["노출수", "클릭수", "UV", "광고비"] + list(RATIO_DEFS.keys()) + [
    "거래액", "거래액(총)", "결제고객수", "결제고객수(총)",
    "가입수", "첫구매수", "첫구매거래액", "신규고객수", "신규거래액",
]
ALL_METRICS = list(dict.fromkeys(ALL_METRICS))  # 중복 제거, 순서 유지

# ── 사이드바 메뉴 ──────────────────────────────────────────────────
st.sidebar.markdown("### 🛍️ 쇼핑검색광고 · 네이버")
menu = st.sidebar.radio("메뉴", ["📋 01. 쇼핑검색광고 실적", "📈 02. 전년비교"], label_visibility="collapsed")
menu = "쇼핑검색광고 실적" if "01" in menu else "전년비교"
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
    # ── 기준일자 (사이드바 조회단위에 맞춰 기간 산출) ──
    ref_date = st.date_input("기준일자", value=MAX_DATE,
                              min_value=MIN_DATE, max_value=MAX_DATE)

    start_ts, end_ts = get_period_bounds(ref_date, unit, MIN_DATE, MAX_DATE)
    cur_label = period_label(start_ts, end_ts, unit)

    render_page_header(
        eyebrow="쇼핑검색광고 · 네이버",
        title=f"쇼핑검색광고 실적 — {cur_label}",
        sub=f"조회단위: {unit}  ·  집계기간: {start_ts.date()} ~ {end_ts.date()}",
    )

    mask = (df["date"] >= start_ts) & (df["date"] <= end_ts)
    view = df.loc[mask].copy()

    if view.empty:
        st.warning("선택한 기간에 데이터가 없습니다.")
        st.stop()

    agg = aggregate(view)

    # ── 비교기간 (전일/전주/전월비 + 전년비) 산출 ──
    comp_periods = get_comparison_periods(ref_date, unit, MIN_DATE, MAX_DATE)
    comp_aggs = {}
    for label, (p_start, p_end) in comp_periods.items():
        p_view = df[(df["date"] >= p_start) & (df["date"] <= p_end)]
        comp_aggs[label] = aggregate(p_view) if not p_view.empty else None

    def deltas_for(metric):
        out = []
        for label, p_agg in comp_aggs.items():
            prev_val = p_agg[metric] if p_agg else None
            out.append((label, pct_change(agg[metric], prev_val)))
        return out

    # ── KPI 카드 ──
    kpi_metrics = ["거래액", "광고비", "ROAS", "UV", "결제고객수", "첫구매수"]
    cards = []
    for m in kpi_metrics:
        if m in ("거래액", "광고비"):
            value_str = format_million(agg[m])
        elif m == "ROAS":
            value_str = format_roas_percent(agg[m])
        else:
            value_str = format_value(m, agg[m])
        cards.append({"label": m, "value": value_str, "deltas": deltas_for(m)})

    render_kpi_cards(cards)
    st.markdown(
        '<div class="kpi-footnote">※ 거래액·광고비는 기간 합계 기준(백만원)이며, '
        'ROAS·CR·CTR 등 비율지표는 합산이 아닌 재산정한 값입니다.</div>',
        unsafe_allow_html=True,
    )

    # ── 실적요약 (직전기간 대비) 테이블 ──
    immediate_label = next(iter(comp_periods.keys()))
    prev_agg_for_table = comp_aggs.get(immediate_label)
    prev_start, prev_end = comp_periods[immediate_label]

    render_section_title(f"실적요약 · {immediate_label} 비교")

    summary_metrics = ["노출수", "클릭수", "CTR", "CR", "객단가", "결제고객수",
                       "CPC", "CPUV", "UV", "광고비", "거래액", "ROAS"]
    prev_col_name = period_label(prev_start, prev_end, unit)
    rows = []
    for m in summary_metrics:
        cur_v = agg[m]
        prev_v = prev_agg_for_table[m] if prev_agg_for_table else None
        delta = pct_change(cur_v, prev_v)
        rows.append({
            "지표": m,
            prev_col_name: format_value(m, prev_v) if prev_v is not None else "-",
            cur_label: format_value(m, cur_v),
            f"{immediate_label}(%)": f"{delta:+.1f}%" if delta is not None else "-",
        })
    summary_df = pd.DataFrame(rows)

    def _color_delta(val):
        if isinstance(val, str) and val.endswith("%") and val not in ("-",):
            try:
                num = float(val.replace("%", "").replace("+", ""))
                color = "#DC2626" if num > 0 else ("#2563EB" if num < 0 else "#64748B")
                return f"color: {color}; font-weight: 600;"
            except ValueError:
                return ""
        return ""

    st.dataframe(
        summary_df.style.map(_color_delta, subset=[f"{immediate_label}(%)"]),
        use_container_width=True, hide_index=True, height=460,
    )

    # ── 추이 차트: 2026년 기준 + 전년비 비교선 (조회단위별 집계) ──
    render_section_title("2026년 추이 (전년비 비교)")
    metric_choice = st.selectbox("지표 선택", ALL_METRICS,
                                  index=ALL_METRICS.index("거래액"))

    buckets = build_2026_buckets(df, unit)
    if not buckets:
        st.info("2026년 데이터가 없거나, 선택한 조회단위 기준으로 마감된 구간이 없습니다.")
    else:
        labels, cur_vals, prev_vals = bucket_yoy_series(df, buckets, metric_choice)

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
            yaxis_title=metric_choice, xaxis_title=None,
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
else:
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
            delta_pct = ((v_cur - v_prev) / v_prev * 100) if v_prev else 0

            m1, m2, m3 = st.columns(3)
            m1.metric(f"올해 ({cur_start} ~ {cur_end})", format_value(metric_choice2, v_cur))
            m2.metric(f"전년 동일요일 ({prev_range.min().date()} ~ {prev_range.max().date()})",
                      format_value(metric_choice2, v_prev))
            m3.metric("증감률", f"{delta_pct:+.1f}%")

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
            compare_table["증감률(%)"] = (
                (compare_table["올해"] - compare_table["전년"]) / compare_table["전년"] * 100
            ).round(1)
            st.dataframe(compare_table, use_container_width=True, height=300)
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
                bar_df["YoY(%)"] = (
                    (bar_df[f"{year_cur}"] - bar_df[f"{year_prev}"])
                    / bar_df[f"{year_prev}"] * 100
                ).round(1)

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

                st.dataframe(
                    bar_df.style.format({f"{year_cur}": "{:,.1f}",
                                          f"{year_prev}": "{:,.1f}"}),
                    use_container_width=True,
                )
                st.download_button(
                    "📥 Excel 다운로드",
                    data=to_excel_bytes(bar_df),
                    file_name=f"월별YoY_{year_cur}_vs_{year_prev}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_yoy_month",
                )
