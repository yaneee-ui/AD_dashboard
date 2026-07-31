"""
쇼핑검색광고 실적 대시보드 - 공통 유틸 함수
비율 지표는 절대 평균하지 않고, 분자/분모 base metric을 합산한 뒤 재계산합니다.
(EP 대시보드에서 확인된 것과 동일한 원칙)
"""

import pandas as pd
import streamlit as st

DATA_PATH = "data/shopping_ad_daily.csv"

# ── 합산 가능한 base metric (분자/분모 원천값) ─────────────────────────
BASE_METRICS = [
    "노출수", "클릭수", "UV", "광고비",
    "거래액", "거래액(총)",
    "결제고객수", "결제고객수(총)",
    "가입수", "첫구매수", "첫구매거래액",
    "신규고객수", "신규거래액",
    "윈백고객수", "윈백거래액",
]

# ── 비율 지표: (지표명, 분자, 분모, 배수) ─────────────────────────────
# 배수 1000 인 경우는 CPM처럼 *1000 하는 지표
RATIO_DEFS = {
    "CTR":        ("클릭수", "노출수", 1),
    "CR":         ("결제고객수", "UV", 1),
    "객단가":      ("거래액", "결제고객수", 1),
    "CPM":        ("광고비", "노출수", 1000),
    "CPC":        ("광고비", "클릭수", 1),
    "CPUV":       ("광고비", "UV", 1),
    "ROAS":       ("거래액", "광고비", 1),
    "순결제비중":   ("거래액", "거래액(총)", 1),
    "ROAS(총)":    ("거래액(총)", "광고비", 1),
    "UV/클릭":     ("UV", "클릭수", 1),
    "CR(총)":      ("결제고객수(총)", "UV", 1),
    "객단가(총)":   ("거래액(총)", "결제고객수(총)", 1),
    "가입률":      ("가입수", "UV", 1),
    "가입CPA":     ("광고비", "가입수", 1),
    "첫구매율":     ("첫구매수", "UV", 1),
    "첫구매CPA":    ("광고비", "첫구매수", 1),
    "첫구매비중":   ("첫구매거래액", "거래액", 1),
    "신규비중":    ("신규거래액", "거래액", 1),
}

PERCENT_METRICS = {
    "CTR", "CR", "순결제비중", "UV/클릭", "CR(총)", "가입률", "첫구매율",
    "첫구매비중", "신규비중",
}

CURRENCY_METRICS = {
    "객단가", "CPM", "CPC", "CPUV", "광고비", "거래액", "거래액(총)",
    "객단가(총)", "가입CPA", "첫구매CPA", "첫구매거래액", "신규거래액", "윈백거래액",
}

MULT_METRICS = {"ROAS", "ROAS(총)"}


@st.cache_data
def load_data():
    df = pd.read_csv(DATA_PATH, parse_dates=["date"], encoding="utf-8-sig")
    df["연도"] = df["date"].dt.year
    df["월"] = df["date"].dt.month
    df["요일"] = df["date"].dt.dayofweek  # 0=월요일
    return df


def aggregate(df: pd.DataFrame) -> dict:
    """base metric은 합산, 비율 지표는 합산된 분자/분모로 재계산."""
    result = {m: df[m].sum() for m in BASE_METRICS}
    for name, (num, den, mult) in RATIO_DEFS.items():
        denom_val = result.get(den, df[den].sum() if den in df.columns else None)
        numer_val = result.get(num, df[num].sum() if num in df.columns else None)
        result[name] = (numer_val / denom_val * mult) if denom_val else 0
    return result


def aggregate_by(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    """group_col 기준으로 base metric 합산 후 비율 재계산, DataFrame 반환."""
    grouped = df.groupby(group_col)[BASE_METRICS].sum().reset_index()
    for name, (num, den, mult) in RATIO_DEFS.items():
        grouped[name] = grouped.apply(
            lambda r: (r[num] / r[den] * mult) if r[den] else 0, axis=1
        )
    return grouped


def format_value(metric: str, value: float) -> str:
    if pd.isna(value):
        return "-"
    if metric in PERCENT_METRICS:
        return f"{value * 100:,.2f}%"
    if metric in MULT_METRICS:
        return f"{value:,.2f}x"
    if metric in CURRENCY_METRICS:
        return f"₩{value:,.0f}"
    return f"{value:,.0f}"


def yoy_same_weekday_dates(target_dates: pd.Series) -> pd.Series:
    """전년 동일 요일 매칭을 위해 364일(52주) 전 날짜를 반환."""
    return target_dates - pd.Timedelta(days=364)
