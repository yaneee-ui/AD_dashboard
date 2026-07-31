"""
쇼핑검색광고 실적 대시보드 - 공통 유틸 함수
비율 지표는 절대 평균하지 않고, 분자/분모 base metric을 합산한 뒤 재계산합니다.
(EP 대시보드에서 확인된 것과 동일한 원칙)
"""

import os
import pandas as pd
import streamlit as st

# 실행 위치(cwd)에 의존하지 않도록, 이 파일 기준 절대경로로 지정.
# GitHub 웹 UI로 드래그앤드롭 업로드하면 폴더 구조 없이 리포 루트에
# 파일이 평평하게 올라가는 경우가 있어, data/ 폴더와 루트 둘 다 확인한다.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_CANDIDATE_PATHS = [
    os.path.join(BASE_DIR, "data", "shopping_ad_daily.csv"),
    os.path.join(BASE_DIR, "shopping_ad_daily.csv"),
]
DATA_PATH = next((p for p in _CANDIDATE_PATHS if os.path.exists(p)), _CANDIDATE_PATHS[0])

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
    if not os.path.exists(DATA_PATH):
        st.error(
            f"데이터 파일을 찾을 수 없습니다.\n\n"
            f"다음 경로를 확인했습니다:\n"
            + "\n".join(f"- `{p}`" for p in _CANDIDATE_PATHS)
            + f"\n\nGitHub 리포지토리에 `shopping_ad_daily.csv`가 실제로 커밋되어 있는지 "
              f"확인해주세요."
        )
        st.stop()
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


# ── 카드 전용 포맷 (거래액/광고비: n.n백만, ROAS: %) ─────────────────
def format_million(value: float) -> str:
    if pd.isna(value):
        return "-"
    return f"{value / 1_000_000:,.1f}백만"


def format_roas_percent(value: float) -> str:
    if pd.isna(value):
        return "-"
    return f"{value * 100:,.1f}%"


# ── 조회단위(일별/주별/월별/월마감) 기준 기간 산출 ─────────────────────
UNIT_OPTIONS = ["일별", "주별", "월별", "월마감"]


def get_period_bounds(ref_date, unit: str, min_date, max_date):
    """기준일자 + 조회단위 → (start, end) 기간 경계 (둘 다 pd.Timestamp)."""
    ref_ts = pd.Timestamp(ref_date)

    if unit == "일별":
        start = end = ref_ts
    elif unit == "주별":
        start = ref_ts - pd.Timedelta(days=ref_ts.weekday())  # 월요일
        end = start + pd.Timedelta(days=6)
    elif unit == "월별":
        start = ref_ts.replace(day=1)
        end = start + pd.offsets.MonthEnd(0)
    else:  # 월마감: 기준일자가 속한 달이 아직 안 끝났으면 직전 '완결'된 달을 사용
        last_day_of_month = ref_ts + pd.offsets.MonthEnd(0)
        if ref_ts.normalize() < last_day_of_month.normalize():
            end = ref_ts.replace(day=1) - pd.Timedelta(days=1)
            start = end.replace(day=1)
        else:
            start = ref_ts.replace(day=1)
            end = last_day_of_month

    start = max(start, pd.Timestamp(min_date))
    end = min(end, pd.Timestamp(max_date))
    return start, end


def period_label(start: pd.Timestamp, end: pd.Timestamp, unit: str) -> str:
    weekday_kr = ["월", "화", "수", "목", "금", "토", "일"]
    if unit == "일별":
        return f"{start.date()} ({weekday_kr[start.weekday()]})"
    if unit == "주별":
        return f"{start.date()} ~ {end.date()} (주)"
    suffix = " · 월마감" if unit == "월마감" else ""
    return f"{start.year}년 {start.month}월{suffix}"


def build_2026_buckets(df: pd.DataFrame, unit: str):
    """2026년 데이터를 조회단위로 나눠 [(label, [dates...]), ...] 리스트 반환 (정렬됨)."""
    d2026 = df[df["연도"] == 2026].copy()
    max_date = df["date"].max()
    buckets = []

    if unit == "일별":
        for d in sorted(d2026["date"].unique()):
            d = pd.Timestamp(d)
            buckets.append((d.strftime("%m-%d"), [d]))

    elif unit == "주별":
        d2026["_wk"] = d2026["date"] - pd.to_timedelta(d2026["date"].dt.weekday, unit="D")
        for wk, g in sorted(d2026.groupby("_wk"), key=lambda x: x[0]):
            dates = sorted(g["date"].tolist())
            buckets.append((f"{wk.strftime('%m/%d')}주", dates))

    else:  # 월별 / 월마감
        d2026["_ym"] = d2026["date"].dt.to_period("M")
        for ym, g in sorted(d2026.groupby("_ym"), key=lambda x: x[0]):
            if unit == "월마감" and max_date.normalize() < ym.end_time.normalize():
                continue  # 아직 마감되지 않은(진행 중인) 월은 제외
            dates = sorted(g["date"].tolist())
            buckets.append((f"{ym.month}월", dates))

    return buckets


def bucket_yoy_series(df: pd.DataFrame, buckets, metric: str):
    """buckets: build_2026_buckets() 결과. (labels, 올해값, 전년값) 튜플 반환."""
    labels, cur_vals, prev_vals = [], [], []
    for label, dates in buckets:
        cur = df[df["date"].isin(dates)]
        prev_dates = [pd.Timestamp(d) - pd.Timedelta(days=364) for d in dates]
        prev = df[df["date"].isin(prev_dates)]
        labels.append(label)
        cur_vals.append(aggregate(cur)[metric] if not cur.empty else 0)
        prev_vals.append(aggregate(prev)[metric] if not prev.empty else None)
    return labels, cur_vals, prev_vals


# ── 카드용 비교기간 (전일/전주/전월/전년비) ─────────────────────────
def get_comparison_periods(ref_date, unit: str, min_date, max_date):
    """조회단위 기준 '직전 동일단위' 기간 + 전월비 + 전년비 기간을 반환.
    반환: {"직전기간 라벨": (start, end), "전월비": (start, end), "전년비": (start, end)}
    (일별 조회 시에는 '직전기간'이 곧 전일비이므로 전월비만 별도로 추가됨)
    """
    ref_ts = pd.Timestamp(ref_date)

    if unit == "일별":
        immediate_label = "전일비"
        immediate_ref = ref_ts - pd.Timedelta(days=1)
    elif unit == "주별":
        immediate_label = "전주비"
        immediate_ref = ref_ts - pd.Timedelta(days=7)
    else:  # 월별 / 월마감
        immediate_label = "전월비"
        immediate_ref = ref_ts - pd.DateOffset(months=1)

    periods = {immediate_label: get_period_bounds(immediate_ref.date(), unit, min_date, max_date)}

    if immediate_label != "전월비":
        month_ref = ref_ts - pd.DateOffset(months=1)
        periods["전월비"] = get_period_bounds(month_ref.date(), unit, min_date, max_date)

    year_ref = ref_ts - pd.Timedelta(days=364)
    periods["전년비"] = get_period_bounds(year_ref.date(), unit, min_date, max_date)

    return periods
