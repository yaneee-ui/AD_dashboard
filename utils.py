"""
쇼핑검색광고 실적 대시보드 - 공통 유틸 함수
비율 지표는 절대 평균하지 않고, 분자/분모 base metric을 합산한 뒤 재계산합니다.
(EP 대시보드에서 확인된 것과 동일한 원칙)
"""

import glob
import os
import pandas as pd
import streamlit as st

# 실행 위치(cwd)에 의존하지 않도록, 이 파일 기준 절대경로로 지정.
# GitHub 웹 UI로 드래그앤드롭 업로드하면 폴더 구조 없이 리포 루트에
# 파일이 평평하게 올라가는 경우가 있어, data/ 폴더와 루트 둘 다 확인한다.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── ② 일일리포트[태블로] — 01(실적 흐름)/02(전년비교) 페이지의 기준 데이터 ──
_CANDIDATE_PATHS = [
    os.path.join(BASE_DIR, "data", "tableau_daily.csv"),
    os.path.join(BASE_DIR, "tableau_daily.csv"),
]
DATA_PATH = next((p for p in _CANDIDATE_PATHS if os.path.exists(p)), _CANDIDATE_PATHS[0])

# ── ③ 카테고리·브랜드별 정상/이월/입점 (태블로 원본, 01·02와 동일 소스) — 03페이지 기준 데이터 ──
_CATTXN_CANDIDATE_PATHS = [
    os.path.join(BASE_DIR, "data", "category_brand_txn_daily.csv"),
    os.path.join(BASE_DIR, "category_brand_txn_daily.csv"),
    os.path.join(BASE_DIR, "data", "category_txn_daily.csv"),  # 브랜드 없던 구버전 (하위호환)
    os.path.join(BASE_DIR, "category_txn_daily.csv"),
]
CATTXN_DATA_PATH = next(
    (p for p in _CATTXN_CANDIDATE_PATHS if os.path.exists(p)), _CATTXN_CANDIDATE_PATHS[0]
)

# ── ① 쇼핑검색광고 리포트(NBOS 매칭) — 지금은 어느 페이지에서도 직접 쓰지 않지만,
#     추후 상품/카테고리/브랜드 ROAS 매칭용으로 남겨둔 원본. 필요 시 load_ad_report_data()로 로드.
_AD_REPORT_CANDIDATE_PATHS = [
    os.path.join(BASE_DIR, "data", "shopping_ad_report_daily.csv"),
    os.path.join(BASE_DIR, "shopping_ad_report_daily.csv"),
]
AD_REPORT_DATA_PATH = next(
    (p for p in _AD_REPORT_CANDIDATE_PATHS if os.path.exists(p)), _AD_REPORT_CANDIDATE_PATHS[0]
)

_AD_PRODUCT_CANDIDATE_PATHS = [
    os.path.join(BASE_DIR, "data", "ad_product_category_daily.csv"),
    os.path.join(BASE_DIR, "ad_product_category_daily.csv"),
]
AD_PRODUCT_DATA_PATH = next(
    (p for p in _AD_PRODUCT_CANDIDATE_PATHS if os.path.exists(p)), _AD_PRODUCT_CANDIDATE_PATHS[0]
)
# 합본 CSV(124MB+)는 GitHub 100MB 파일당 제한 때문에 배포 저장소에는 못 올린다 — 대신
# build_ad_product_daily.py가 같이 만들어두는 연도별 조각(ad_product_category_daily_2025.csv 등)을
# 배포 환경에서 찾아 합쳐 쓴다. 로컬은 합본이 있으니 그쪽을 그대로 쓰고, 빠르다.
_AD_PRODUCT_SPLIT_GLOBS = [
    os.path.join(BASE_DIR, "data", "ad_product_category_daily_*.csv"),
    os.path.join(BASE_DIR, "ad_product_category_daily_*.csv"),
]

_CATEGORY_CANDIDATE_PATHS = [
    os.path.join(BASE_DIR, "data", "category_daily.csv"),
    os.path.join(BASE_DIR, "category_daily.csv"),
]
CATEGORY_DATA_PATH = next(
    (p for p in _CATEGORY_CANDIDATE_PATHS if os.path.exists(p)), _CATEGORY_CANDIDATE_PATHS[0]
)

_FITFLOP_CANDIDATE_PATHS = [
    os.path.join(BASE_DIR, "data", "fitflop_monthly.csv"),
    os.path.join(BASE_DIR, "fitflop_monthly.csv"),
]
FITFLOP_DATA_PATH = next(
    (p for p in _FITFLOP_CANDIDATE_PATHS if os.path.exists(p)), _FITFLOP_CANDIDATE_PATHS[0]
)

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
    "객단가", "CPM", "CPC", "CPUV", "광고비", "거래액(총)",
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
            + f"\n\nGitHub 리포지토리에 `tableau_daily.csv`가 실제로 커밋되어 있는지 "
              f"확인해주세요."
        )
        st.stop()
    df = pd.read_csv(DATA_PATH, parse_dates=["date"], encoding="utf-8-sig")
    df["연도"] = df["date"].dt.year
    df["월"] = df["date"].dt.month
    df["요일"] = df["date"].dt.dayofweek  # 0=월요일
    return df


@st.cache_data
def load_ad_report_data():
    """① 쇼핑검색광고 리포트(NBOS 매칭) 원본. 지금은 어느 페이지도 직접 쓰지 않지만,
    추후 상품/카테고리/브랜드 ROAS 매칭 기능에 쓸 수 있도록 남겨둔 로더."""
    if not os.path.exists(AD_REPORT_DATA_PATH):
        return None
    df = pd.read_csv(AD_REPORT_DATA_PATH, parse_dates=["date"], encoding="utf-8-sig")
    df["연도"] = df["date"].dt.year
    df["월"] = df["date"].dt.month
    df["요일"] = df["date"].dt.dayofweek
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
    if metric in ("ROAS", "ROAS(총)"):
        return f"{value * 100:,.0f}%"
    if metric in PERCENT_METRICS:
        return f"{value * 100:,.2f}%"
    if metric in MULT_METRICS:
        return f"{value:,.2f}x"
    if metric in CURRENCY_METRICS:
        return f"{value:,.0f}"
    return f"{value:,.0f}"


def yoy_same_weekday_dates(target_dates: pd.Series) -> pd.Series:
    """전년 동요일 매칭을 위해 364일(52주) 전 날짜를 반환."""
    return target_dates - pd.Timedelta(days=364)


# ── 카드 전용 포맷 (거래액/광고비: n.n백만, ROAS: %) ─────────────────
def format_million(value: float) -> str:
    if pd.isna(value):
        return "-"
    return f"{value / 1_000_000:,.1f}백만"


def format_roas_percent(value: float) -> str:
    if pd.isna(value):
        return "-"
    return f"{value * 100:,.0f}%"


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
        if start.date() == end.date():
            # 전년비 등에서 동요일까지만 truncate된 1일짜리 비교기간
            return f"{start.date()} ({weekday_kr[start.weekday()]})"
        return f"{start.date()} ~ {end.date()} (주)"
    if unit == "월마감":
        return f"{start.year}년 {start.month}월 · 월마감"
    # 월별: 전체 달이면 'YYYY년 M월', 부분월(전월비/전년비 truncation 등)이면 날짜범위 그대로 표기
    is_full_month = start.day == 1 and end.date() == (start + pd.offsets.MonthEnd(0)).date()
    if is_full_month:
        return f"{start.year}년 {start.month}월"
    return f"{start.date()} ~ {end.date()}"


def days_in_period(start: pd.Timestamp, end: pd.Timestamp) -> int:
    return (end - start).days + 1


def build_ref_options(unit: str, min_date, max_date):
    """조회단위가 주별/월별/월마감일 때, 기준일자를 날짜 대신 '주/월' 단위로 고를 수 있도록
    선택지 리스트 [(라벨, 대표날짜), ...] 를 최신순으로 반환한다. (일별은 date_input 그대로 사용)"""
    options = []
    max_ts = pd.Timestamp(max_date)

    if unit == "주별":
        cur = pd.Timestamp(min_date) - pd.Timedelta(days=pd.Timestamp(min_date).weekday())
        while cur <= max_ts:
            wk_end = min(cur + pd.Timedelta(days=6), max_ts)
            label = f"{cur.date()} ~ {wk_end.date()} (주)"
            options.append((label, cur.date()))
            cur += pd.Timedelta(days=7)
    else:  # 월별 / 월마감
        cur = pd.Timestamp(min_date).replace(day=1)
        while cur <= max_ts:
            month_end = cur + pd.offsets.MonthEnd(0)
            if unit == "월마감" and max_ts.normalize() < month_end.normalize():
                break  # 아직 마감되지 않은 진행 중인 달 이후는 선택지에서 제외
            options.append((f"{cur.year}년 {cur.month}월", cur.date()))
            cur += pd.DateOffset(months=1)

    return options[::-1]  # 최신이 먼저 나오도록


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


def bucket_yoy_series(df: pd.DataFrame, buckets, metric: str, mode: str = "누계", unit: str = "일별"):
    """buckets: build_2026_buckets() 결과. (labels, 올해값, 전년값) 튜플 반환.
    mode="일평균"이면 base(합산) metric만 해당 버킷의 일수로 나눠 일평균으로 환산한다.
    unit="월마감"이면 전년 비교를 364일 시프트(동요일비)가 아니라 '정확히 12개월 전 같은 달'
    (실제 마감 실적 기준)로 계산한다."""
    labels, cur_vals, prev_vals = [], [], []
    is_base = metric in BASE_METRICS
    for label, dates in buckets:
        n_days = len(dates)
        cur = df[df["date"].isin(dates)]

        if unit == "월마감":
            first = pd.Timestamp(dates[0])
            prev_start = first.replace(year=first.year - 1, day=1)
            prev_end = prev_start + pd.offsets.MonthEnd(0)
            prev = df[(df["date"] >= prev_start) & (df["date"] <= prev_end)]
        else:
            prev_dates = [pd.Timestamp(d) - pd.Timedelta(days=364) for d in dates]
            prev = df[df["date"].isin(prev_dates)]

        labels.append(label)

        cur_val = aggregate(cur)[metric] if not cur.empty else 0
        prev_val = aggregate(prev)[metric] if not prev.empty else None

        if mode == "일평균" and is_base and n_days:
            cur_val = cur_val / n_days
            if prev_val is not None:
                prev_val = prev_val / n_days

        cur_vals.append(cur_val)
        prev_vals.append(prev_val)
    return labels, cur_vals, prev_vals


def recent_metric_buckets(df: pd.DataFrame, unit: str, n: int = 12):
    """보조 지표 스파크라인용: 연도 제한 없이 전체 기간에서 조회단위 기준 최근 n개 구간을
    [(label, [dates...]), ...] 형태로 반환한다 (오래된 순 정렬)."""
    d = df.copy()
    if unit == "일별":
        dates_sorted = sorted(d["date"].unique())[-n:]
        return [(pd.Timestamp(dt).strftime("%m-%d"), [dt]) for dt in dates_sorted]
    if unit == "주별":
        d["_wk"] = d["date"] - pd.to_timedelta(d["date"].dt.weekday, unit="D")
        weeks = sorted(d["_wk"].unique())[-n:]
        return [
            (pd.Timestamp(wk).strftime("%m/%d") + "주", sorted(d.loc[d["_wk"] == wk, "date"].tolist()))
            for wk in weeks
        ]
    # 월별 / 월마감
    d["_ym"] = d["date"].dt.to_period("M")
    yms = sorted(d["_ym"].unique())[-n:]
    return [(str(ym), sorted(d.loc[d["_ym"] == ym, "date"].tolist())) for ym in yms]


def metric_sparkline_table(df: pd.DataFrame, buckets, metrics: list, mode: str = "일평균") -> pd.DataFrame:
    """지표별로 buckets 구간에 걸친 값 리스트(추이)와 최근값·직전 대비 증감률을 정리한 표.
    base metric은 mode='일평균'일 때 구간 일수로 나누고, 비율 지표는 그대로 둔다
    (합산이 아니라 aggregate()로 매 구간 재계산하므로 항상 정확하다)."""
    bucket_days = [max(len(dates), 1) for _, dates in buckets]
    rows = []
    for m in metrics:
        vals = []
        for (_, dates), n_days in zip(buckets, bucket_days):
            sub = df[df["date"].isin(dates)]
            v = aggregate(sub)[m] if not sub.empty else 0
            if mode == "일평균" and m in BASE_METRICS and n_days:
                v = v / n_days
            vals.append(v)
        latest = vals[-1] if vals else None
        prev = vals[-2] if len(vals) >= 2 else None
        delta_pct = ((latest - prev) / abs(prev) * 100) if prev else None
        rows.append({"지표": m, "추이": vals, "최근값": latest, "직전 대비": delta_pct})
    return pd.DataFrame(rows)


# ── 카드용 비교기간 (전일/전주/전월/전년비) ─────────────────────────
def get_comparison_periods(ref_date, unit: str, min_date, max_date):
    """조회단위 기준 '직전 동일단위' 기간 + 전월비 + 전년비 기간을 반환.
    반환: {"직전기간 라벨": (start, end), "전월비": (start, end), "전년비": (start, end)}
    (일별 조회 시에는 '직전기간'이 곧 전일비이므로 전월비만 별도로 추가됨)

    월마감을 제외한 모든 단위는 '현재기간(부분기간 포함)을 그대로 시프트'하는 방식으로
    비교기간을 만든다 — 즉 현재기간이 진행 중(예: 이번 주 1일치, 이번 달 17일치)이면
    전주비/전월비/전년비 전부 딱 그만큼의 일수만, 요일이 정렬된 위치로 truncate해서 비교한다.
    (예: 월별 현재기간이 8/1~17(부분월)이면 → 전월비는 7/1~17, 전년비는 8/2~18만 사용.
    전체 이전 달/이전 해를 그대로 가져오면 일수가 안 맞아 불공평한 비교가 됨.)

    월마감은 애초에 완결된 달만 다루므로 부분기간 이슈가 없어, 예외적으로 달력 기준
    정확히 이전 달/이전 해를 그대로 사용한다 (실제 마감 실적끼리 비교).
    """
    ref_ts = pd.Timestamp(ref_date)
    cur_start, cur_end = get_period_bounds(ref_date, unit, min_date, max_date)

    def shift_period(offset):
        s = max(cur_start - offset, pd.Timestamp(min_date))
        e = min(cur_end - offset, pd.Timestamp(max_date))
        return (s, e)

    if unit == "월마감":
        month_ref = ref_ts - pd.DateOffset(months=1)
        year_ref = ref_ts - pd.DateOffset(years=1)
        return {
            "전월비": get_period_bounds(month_ref.date(), unit, min_date, max_date),
            "전년비": get_period_bounds(year_ref.date(), unit, min_date, max_date),
        }

    if unit == "일별":
        immediate_label = "전일비"
    elif unit == "주별":
        immediate_label = "전주비"
    else:  # 월별
        immediate_label = "전월비"

    periods = {immediate_label: shift_period(pd.Timedelta(days=7) if unit == "주별" else
                                              pd.DateOffset(months=1) if unit == "월별" else
                                              pd.Timedelta(days=1))}
    if immediate_label != "전월비":
        periods["전월비"] = shift_period(pd.DateOffset(months=1))
    periods["전년비"] = shift_period(pd.Timedelta(days=364))

    return periods


# ════════════════════════════════════════════════════════════════
# 카테고리별 실적 (쇼핑검색광고 vs EP채널 비교)
# ════════════════════════════════════════════════════════════════
CATEGORY_BASE_METRICS = ["광고_거래액", "EP_거래액"]

# 거래유형(정상/이월/입점) 선택에 따라 어떤 원천 컬럼을 합산할지 매핑
TXN_TYPE_OPTIONS = ["전체", "정상", "이월", "입점"]
TXN_TYPE_COLS = {
    "전체": ("광고_거래액", "EP_거래액"),
    "정상": ("광고_정상", "EP_정상"),
    "이월": ("광고_이월", "EP_이월"),
    "입점": ("광고_입점", "EP_입점"),
}


@st.cache_data
def load_category_data():
    if not os.path.exists(CATEGORY_DATA_PATH):
        st.error(
            f"카테고리 데이터 파일을 찾을 수 없습니다.\n\n"
            f"다음 경로를 확인했습니다:\n"
            + "\n".join(f"- `{p}`" for p in _CATEGORY_CANDIDATE_PATHS)
            + f"\n\nGitHub 리포지토리에 `category_daily.csv`가 실제로 커밋되어 있는지 확인해주세요."
        )
        st.stop()
    df = pd.read_csv(CATEGORY_DATA_PATH, parse_dates=["date"], encoding="utf-8-sig")
    for c in ["광고_이월", "광고_입점", "광고_정상", "EP_이월", "EP_입점", "EP_정상"]:
        if c not in df.columns:
            df[c] = 0
        df[c] = df[c].fillna(0)
    df["광고_거래액"] = df["광고_이월"] + df["광고_입점"] + df["광고_정상"]
    df["EP_거래액"] = df["EP_이월"] + df["EP_입점"] + df["EP_정상"]
    df["연도"] = df["date"].dt.year
    return df


def aggregate_category(df: pd.DataFrame, txn_type: str = "전체") -> dict:
    """선택한 거래유형(전체/정상/이월/입점) 기준으로 광고_거래액/EP_거래액을 합산."""
    ad_col, ep_col = TXN_TYPE_COLS[txn_type]
    return {
        "광고_거래액": df[ad_col].sum(),
        "EP_거래액": df[ep_col].sum(),
    }


def aggregate_category_by(df: pd.DataFrame, group_col: str = "category", txn_type: str = "전체") -> pd.DataFrame:
    """카테고리별로 선택한 거래유형 기준 광고_거래액/EP_거래액을 합산한 DataFrame 반환."""
    ad_col, ep_col = TXN_TYPE_COLS[txn_type]
    grouped = df.groupby(group_col)[[ad_col, ep_col]].sum().reset_index()
    grouped.columns = [group_col, "광고_거래액", "EP_거래액"]
    return grouped


def category_txn_type_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """선택된 기간(+카테고리 범위)에 대해 정상/이월/입점 유형별 광고·EP 거래액 구성을 반환."""
    rows = []
    for t in ["정상", "이월", "입점"]:
        ad_col, ep_col = TXN_TYPE_COLS[t]
        rows.append({"거래유형": t, "쇼핑검색광고 거래액": df[ad_col].sum(), "EP채널 거래액": df[ep_col].sum()})
    return pd.DataFrame(rows)


def category_bucket_yoy_series(df: pd.DataFrame, buckets, value_col: str, mode: str = "누계"):
    """build_2026_buckets() 결과를 그대로 받아, 카테고리 데이터의 특정 합산 컬럼(광고_거래액/EP_거래액)에
    대해 (labels, 올해값, 전년값)을 반환한다. mode='일평균'이면 버킷 일수로 나눈다."""
    labels, cur_vals, prev_vals = [], [], []
    for label, dates in buckets:
        n_days = len(dates)
        cur_val = df.loc[df["date"].isin(dates), value_col].sum()
        prev_dates = [pd.Timestamp(d) - pd.Timedelta(days=364) for d in dates]
        prev_mask = df["date"].isin(prev_dates)
        prev_val = df.loc[prev_mask, value_col].sum() if prev_mask.any() else None

        if mode == "일평균" and n_days:
            cur_val = cur_val / n_days
            if prev_val is not None:
                prev_val = prev_val / n_days

        labels.append(label)
        cur_vals.append(cur_val)
        prev_vals.append(prev_val)
    return labels, cur_vals, prev_vals


def category_dual_channel_series(df: pd.DataFrame, buckets, txn_type: str = "전체", mode: str = "누계"):
    """동일 기간에 대해 쇼핑검색광고 거래액 흐름과 EP채널 거래액 흐름을 나란히 비교하기 위한
    (labels, 광고값, EP값) 튜플 반환. 전년비 없이 같은 기간의 두 채널만 비교한다."""
    ad_col, ep_col = TXN_TYPE_COLS[txn_type]
    labels, ad_vals, ep_vals = [], [], []
    for label, dates in buckets:
        n_days = len(dates)
        mask = df["date"].isin(dates)
        ad_val = df.loc[mask, ad_col].sum()
        ep_val = df.loc[mask, ep_col].sum()
        if mode == "일평균" and n_days:
            ad_val = ad_val / n_days
            ep_val = ep_val / n_days
        labels.append(label)
        ad_vals.append(ad_val)
        ep_vals.append(ep_val)
    return labels, ad_vals, ep_vals


# ════════════════════════════════════════════════════════════════
# 핏플랍(브랜드) 영향 제외 비교
# ════════════════════════════════════════════════════════════════
@st.cache_data
def load_fitflop_data():
    """월별 자사(정상+이월) 거래액/광고비 vs 핏플랍 거래액/광고비, 핏플랍 제외 값까지 포함된 데이터."""
    if not os.path.exists(FITFLOP_DATA_PATH):
        st.error(
            f"핏플랍 비교 데이터 파일을 찾을 수 없습니다.\n\n"
            f"다음 경로를 확인했습니다:\n"
            + "\n".join(f"- `{p}`" for p in _FITFLOP_CANDIDATE_PATHS)
            + f"\n\nGitHub 리포지토리에 `fitflop_monthly.csv`가 실제로 커밋되어 있는지 확인해주세요."
        )
        st.stop()
    df = pd.read_csv(FITFLOP_DATA_PATH, dtype={"ym": str}, encoding="utf-8-sig")
    df["ym_label"] = df["ym"].str[:4] + "년 " + df["ym"].str[4:6].astype(int).astype(str) + "월"
    return df


def fitflop_roas(row, col_ad, col_cost):
    cost = row[col_cost]
    if pd.isna(cost) or cost == 0:
        return None
    return row[col_ad] / cost


def fitflop_yoy_table(ff_df: pd.DataFrame, metric: str) -> pd.DataFrame:
    """metric in {거래액, 광고비, ROAS}에 대해 월별로 (올해/전년/전년비)를
    포함(자사 전체)과 제외(핏플랍 제외) 두 기준으로 나란히 계산한 표를 반환.
    2026년 각 월과 전년 동월(2025)이 모두 있는 월만 포함."""
    all_col = {"거래액": "자사_거래액", "광고비": "자사_광고비"}
    ex_col = {"거래액": "핏플랍제외_거래액", "광고비": "핏플랍제외_광고비"}

    by_ym = ff_df.set_index("ym")
    rows = []
    for m in range(1, 13):
        cur_ym, prev_ym = f"2026{m:02d}", f"2025{m:02d}"
        if cur_ym not in by_ym.index or prev_ym not in by_ym.index:
            continue
        cur, prev = by_ym.loc[cur_ym], by_ym.loc[prev_ym]

        if metric == "ROAS":
            cur_all = fitflop_roas(cur, "자사_거래액", "자사_광고비")
            prev_all = fitflop_roas(prev, "자사_거래액", "자사_광고비")
            cur_ex = fitflop_roas(cur, "핏플랍제외_거래액", "핏플랍제외_광고비")
            prev_ex = fitflop_roas(prev, "핏플랍제외_거래액", "핏플랍제외_광고비")
        else:
            cur_all, prev_all = cur[all_col[metric]], prev[all_col[metric]]
            cur_ex, prev_ex = cur[ex_col[metric]], prev[ex_col[metric]]

        def _yoy(c, p):
            if c is None or p is None or pd.isna(c) or pd.isna(p) or p == 0:
                return None
            return (c - p) / abs(p) * 100

        rows.append({
            "월": f"{m}월",
            "포함_올해": cur_all, "포함_전년": prev_all, "포함_전년비": _yoy(cur_all, prev_all),
            "제외_올해": cur_ex, "제외_전년": prev_ex, "제외_전년비": _yoy(cur_ex, prev_ex),
        })
    return pd.DataFrame(rows)


# ════════════════════════════════════════════════════════════════
# EP 상관관계 분석 (쇼핑검색광고 확대 → EP 거래액 동반 상승 카테고리 점검)
# ════════════════════════════════════════════════════════════════
def category_weekly_changes(cat_df: pd.DataFrame) -> pd.DataFrame:
    """카테고리별 주간(월요일 시작) 광고_거래액/EP_거래액 합계와 전주 대비 증감률(%)을 반환.
    광고_거래액은 카테고리별 실제 광고비 원본이 없을 때 '얼마나 밀었는지'의 대리지표로 사용.
    직전 주 값이 0이라 증감률이 무한대(inf)가 되는 경우는 NaN 처리해 상관계수 계산에서 제외한다."""
    import numpy as np
    df = cat_df.copy()
    df["_wk"] = df["date"] - pd.to_timedelta(df["date"].dt.weekday, unit="D")
    weekly = df.groupby(["category", "_wk"])[["광고_거래액", "EP_거래액"]].sum().reset_index()
    weekly = weekly.sort_values(["category", "_wk"]).reset_index(drop=True)
    weekly["광고_증감률"] = weekly.groupby("category")["광고_거래액"].pct_change() * 100
    weekly["EP_증감률"] = weekly.groupby("category")["EP_거래액"].pct_change() * 100
    weekly[["광고_증감률", "EP_증감률"]] = weekly[["광고_증감률", "EP_증감률"]].replace(
        [np.inf, -np.inf], np.nan
    )
    return weekly


def category_lag_correlation(weekly_df: pd.DataFrame, max_lag: int = 2, min_samples: int = 4) -> pd.DataFrame:
    """카테고리별로 '광고 증감률(t) vs EP 증감률(t+lag)' 상관계수를 lag 0~max_lag까지 계산.
    표본이 min_samples 미만이면 해당 lag는 None. best_lag/best_corr은 절댓값 기준 최고 상관 lag."""
    rows = []
    for cat, g in weekly_df.groupby("category"):
        g = g.sort_values("_wk").reset_index(drop=True)
        row = {"category": cat}
        best_lag, best_corr, n_used = 0, None, 0
        for lag in range(0, max_lag + 1):
            ad = g["광고_증감률"]
            ep = g["EP_증감률"].shift(-lag)
            valid = ad.notna() & ep.notna()
            n = int(valid.sum())
            corr = ad[valid].corr(ep[valid]) if n >= min_samples else None
            row[f"lag{lag}"] = corr
            row[f"n_lag{lag}"] = n
            if corr is not None and (best_corr is None or abs(corr) > abs(best_corr)):
                best_corr, best_lag, n_used = corr, lag, n
        row["best_lag"] = best_lag
        row["best_corr"] = best_corr
        row["best_n"] = n_used
        rows.append(row)
    result = pd.DataFrame(rows)
    result["_abs_corr"] = result["best_corr"].abs()
    return result.sort_values("_abs_corr", ascending=False).drop(columns="_abs_corr").reset_index(drop=True)


def category_lag_scatter_data(weekly_df: pd.DataFrame, category: str, lag: int) -> pd.DataFrame:
    """선택 카테고리 + lag에 대한 산점도용 (주차, 광고_증감률, EP_증감률) 데이터."""
    g = weekly_df[weekly_df["category"] == category].sort_values("_wk").reset_index(drop=True)
    ad = g["광고_증감률"]
    ep = g["EP_증감률"].shift(-lag)
    valid = ad.notna() & ep.notna()
    out = pd.DataFrame({
        "주차": g.loc[valid, "_wk"],
        "광고_증감률": ad[valid],
        "EP_증감률": ep[valid],
    }).reset_index(drop=True)
    return out


def linear_trend(x: pd.Series, y: pd.Series):
    """단순 선형회귀 (기울기, 절편) 반환. numpy만 사용."""
    if len(x) < 2:
        return None, None
    import numpy as np
    slope, intercept = np.polyfit(x, y, 1)
    return slope, intercept


# ════════════════════════════════════════════════════════════════
# 카테고리·브랜드별 정상/이월/입점 실적 (태블로 원본, 01·02와 동일 소스) — 03페이지
# ════════════════════════════════════════════════════════════════
CATTXN_TXN_TYPE_OPTIONS = ["전체", "정상", "이월", "입점"]
CATTXN_CHANNEL_OPTIONS = ["쇼핑검색광고", "EP채널"]
CATTXN_METRIC_OPTIONS = ["거래액", "주문고객수", "객단가"]


@st.cache_data
def load_cattxn_data():
    if not os.path.exists(CATTXN_DATA_PATH):
        st.error(
            f"카테고리·브랜드별 정상/이월/입점 데이터 파일을 찾을 수 없습니다.\n\n"
            f"다음 경로를 확인했습니다:\n"
            + "\n".join(f"- `{p}`" for p in _CATTXN_CANDIDATE_PATHS)
            + f"\n\nGitHub 리포지토리에 `category_brand_txn_daily.csv`가 실제로 커밋되어 있는지 확인해주세요."
        )
        st.stop()
    df = pd.read_csv(CATTXN_DATA_PATH, parse_dates=["date"], encoding="utf-8-sig")
    for c in ["ad_거래액", "ad_주문고객수", "ep_거래액", "ep_주문고객수"]:
        df[c] = df[c].fillna(0)
    if "brand" not in df.columns:
        df["brand"] = "전체"  # 구버전(브랜드 없는) 파일 하위호환
    df["연도"] = df["date"].dt.year
    return df


def _cattxn_scope(df: pd.DataFrame, txn_type: str = "전체", category: str = "전체", brand: str = "전체") -> pd.DataFrame:
    scope = df
    if txn_type != "전체":
        scope = scope[scope["txn_type"] == txn_type]
    if category != "전체":
        scope = scope[scope["category"] == category]
    if brand != "전체":
        scope = scope[scope["brand"] == brand]
    return scope


def _cattxn_derive(sums: dict) -> dict:
    """ad_거래액/ad_주문고객수/ep_거래액/ep_주문고객수 합계 딕셔너리에서 객단가까지 파생."""
    out = {
        "쇼핑검색광고_거래액": sums["ad_거래액"],
        "쇼핑검색광고_주문고객수": sums["ad_주문고객수"],
        "EP채널_거래액": sums["ep_거래액"],
        "EP채널_주문고객수": sums["ep_주문고객수"],
    }
    out["쇼핑검색광고_객단가"] = (
        out["쇼핑검색광고_거래액"] / out["쇼핑검색광고_주문고객수"] if out["쇼핑검색광고_주문고객수"] else 0
    )
    out["EP채널_객단가"] = (
        out["EP채널_거래액"] / out["EP채널_주문고객수"] if out["EP채널_주문고객수"] else 0
    )
    return out


def aggregate_cattxn(df: pd.DataFrame, txn_type: str = "전체", category: str = "전체", brand: str = "전체") -> dict:
    """선택한 거래유형/카테고리/브랜드 기준으로 채널별 거래액/주문고객수 합산 + 객단가 파생."""
    scope = _cattxn_scope(df, txn_type, category, brand)
    sums = {c: scope[c].sum() for c in ["ad_거래액", "ad_주문고객수", "ep_거래액", "ep_주문고객수"]}
    return _cattxn_derive(sums)


def aggregate_cattxn_by(df: pd.DataFrame, group_col: str = "category", txn_type: str = "전체",
                        category: str = "전체", brand: str = "전체") -> pd.DataFrame:
    """카테고리 또는 브랜드별로 채널별 거래액/주문고객수 합산 + 객단가 파생한 DataFrame 반환.
    group_col='category'일 때는 category 필터를 적용하지 않는 게 자연스럽고(전체 카테고리 랭킹),
    group_col='brand'일 때는 category로 범위를 좁힌 뒤 그 안에서 브랜드 랭킹을 볼 수 있다."""
    scope_category = "전체" if group_col == "category" else category
    scope = _cattxn_scope(df, txn_type, scope_category, brand if group_col != "brand" else "전체")
    grouped = scope.groupby(group_col)[["ad_거래액", "ad_주문고객수", "ep_거래액", "ep_주문고객수"]].sum()
    grouped["쇼핑검색광고_거래액"] = grouped["ad_거래액"]
    grouped["쇼핑검색광고_주문고객수"] = grouped["ad_주문고객수"]
    grouped["EP채널_거래액"] = grouped["ep_거래액"]
    grouped["EP채널_주문고객수"] = grouped["ep_주문고객수"]
    grouped["쇼핑검색광고_객단가"] = grouped.apply(
        lambda r: (r["ad_거래액"] / r["ad_주문고객수"]) if r["ad_주문고객수"] else 0, axis=1
    )
    grouped["EP채널_객단가"] = grouped.apply(
        lambda r: (r["ep_거래액"] / r["ep_주문고객수"]) if r["ep_주문고객수"] else 0, axis=1
    )
    return grouped.reset_index()


def cattxn_txn_type_breakdown(df: pd.DataFrame, category: str = "전체", brand: str = "전체") -> pd.DataFrame:
    """선택된 카테고리/브랜드 범위에 대해 정상/이월/입점 유형별 광고·EP 거래액/주문고객수 구성을 반환."""
    scope = _cattxn_scope(df, "전체", category, brand)
    rows = []
    for t in ["정상", "이월", "입점"]:
        sub = scope[scope["txn_type"] == t]
        rows.append({
            "거래유형": t,
            "쇼핑검색광고 거래액": sub["ad_거래액"].sum(),
            "쇼핑검색광고 주문고객수": sub["ad_주문고객수"].sum(),
            "EP채널 거래액": sub["ep_거래액"].sum(),
            "EP채널 주문고객수": sub["ep_주문고객수"].sum(),
        })
    return pd.DataFrame(rows)


def cattxn_daily_series(df: pd.DataFrame, channel: str, metric: str, txn_type: str,
                        category: str, start, end, brand: str = "전체"):
    """EP 대시보드 스타일 '실적 추이' 차트용: 임의 날짜범위(조회단위 버킷과 무관)의
    일별 시계열 + 전년 동요일(364일 전) 비교 시계열을 함께 반환.
    channel: '쇼핑검색광고' | 'EP채널'  /  metric: '거래액' | '주문고객수' | '객단가'
    반환: (date_range, cur_vals(list), prev_vals(list, None 포함 가능))
    """
    prefix = "ad" if channel == "쇼핑검색광고" else "ep"
    rev_col, cnt_col = f"{prefix}_거래액", f"{prefix}_주문고객수"

    scope = _cattxn_scope(df, txn_type, category, brand)
    daily = scope.groupby("date")[[rev_col, cnt_col]].sum()

    def _metric_series(sub: pd.DataFrame):
        if metric == "거래액":
            return sub[rev_col]
        if metric == "주문고객수":
            return sub[cnt_col]
        denom = sub[cnt_col].replace(0, pd.NA)
        return sub[rev_col] / denom

    date_range = pd.date_range(pd.Timestamp(start), pd.Timestamp(end), freq="D")

    cur_daily = daily.reindex(date_range)
    cur_daily[[rev_col, cnt_col]] = cur_daily[[rev_col, cnt_col]].fillna(0)
    cur_vals = _metric_series(cur_daily)

    prev_range = date_range - pd.Timedelta(days=364)
    prev_daily = daily.reindex(prev_range)
    prev_daily[[rev_col, cnt_col]] = prev_daily[[rev_col, cnt_col]].fillna(0)
    prev_daily.index = date_range
    prev_vals = _metric_series(prev_daily)

    return date_range, cur_vals.tolist(), prev_vals.tolist()


def cattxn_period_buckets(df: pd.DataFrame, unit: str):
    """'실적 추이' 차트용 주별/월별 버킷 생성 (오래된 순으로 정렬).
    주별: 라벨 'M월 W주차' (해당 월 안에서 몇 번째 주 월요일인지로 카운트)
    월별: 2026년 데이터만, 라벨 'YYYY-MM'
    반환: [(label, [dates...]), ...]
    """
    if unit == "주별":
        d = df[df["연도"] == 2026].copy()
        d["_wk"] = d["date"] - pd.to_timedelta(d["date"].dt.weekday, unit="D")
        weeks = sorted(d["_wk"].unique())
        month_counts = {}
        buckets = []
        for wk in weeks:
            wk_ts = pd.Timestamp(wk)
            key = (wk_ts.year, wk_ts.month)
            month_counts[key] = month_counts.get(key, 0) + 1
            label = f"{wk_ts.month}월 {month_counts[key]}주차"
            dates = sorted(d.loc[d["_wk"] == wk, "date"].unique())
            buckets.append((label, dates))
        return buckets

    # 월별: 2026년만 (레퍼런스 EP 대시보드와 동일하게 올해 범위로 표시)
    d = df[df["연도"] == 2026].copy()
    d["_ym"] = d["date"].dt.to_period("M")
    buckets = []
    for ym, g in sorted(d.groupby("_ym"), key=lambda x: x[0]):
        label = f"{ym.year}-{ym.month:02d}"
        dates = sorted(g["date"].unique())
        buckets.append((label, dates))
    return buckets


def cattxn_bucket_series(df: pd.DataFrame, buckets, channel: str, metric: str, txn_type: str, category: str,
                         brand: str = "전체"):
    """cattxn_period_buckets() 결과를 받아 (labels, 올해값, 전년동요일값) 반환.
    전년 비교는 버킷을 구성하는 각 날짜를 364일 시프트해서 재집계 — 요일 정렬 유지."""
    prefix = "ad" if channel == "쇼핑검색광고" else "ep"
    rev_col, cnt_col = f"{prefix}_거래액", f"{prefix}_주문고객수"
    scope = _cattxn_scope(df, txn_type, category, brand)

    def _metric(rev, cnt):
        if metric == "거래액":
            return rev
        if metric == "주문고객수":
            return cnt
        return (rev / cnt) if cnt else None

    labels, cur_vals, prev_vals = [], [], []
    for label, dates in buckets:
        cur_sub = scope[scope["date"].isin(dates)]
        cur_rev, cur_cnt = cur_sub[rev_col].sum(), cur_sub[cnt_col].sum()

        prev_dates = [pd.Timestamp(d) - pd.Timedelta(days=364) for d in dates]
        prev_sub = scope[scope["date"].isin(prev_dates)]
        prev_rev, prev_cnt = prev_sub[rev_col].sum(), prev_sub[cnt_col].sum()

        labels.append(label)
        cur_vals.append(_metric(cur_rev, cur_cnt))
        prev_vals.append(_metric(prev_rev, prev_cnt) if not prev_sub.empty else None)

    return labels, cur_vals, prev_vals


def category_revenue_forecast(cattxn_df: pd.DataFrame, categories: list, channel: str, txn_type: str = "전체",
                              days_actual: int = 30, days_forecast: int = 14, trend_days: int = 14) -> dict:
    """카테고리별 최근 days_actual일 실제 일별 거래액 + 최근 trend_days일 기울기로 만든
    단순 선형추세 예측(days_forecast일치)과 잔차 기반 불확실성 밴드를 반환한다.
    엄밀한 통계 예측이 아니라 "최근 추세가 이어지면"이라는 대략적 방향성 참고용이다.
    channel: '전체'(SA+EP 합산) | '쇼핑검색광고' | 'EP채널'
    반환: {category: {actual_dates, actual_vals, forecast_dates, forecast_vals, band_upper, band_lower}}"""
    import numpy as np

    max_date = cattxn_df["date"].max()
    actual_start = max_date - pd.Timedelta(days=days_actual - 1)
    scope = cattxn_df if txn_type == "전체" else cattxn_df[cattxn_df["txn_type"] == txn_type]

    def _rev(sub: pd.DataFrame) -> pd.Series:
        if channel == "쇼핑검색광고":
            return sub["ad_거래액"]
        if channel == "EP채널":
            return sub["ep_거래액"]
        return sub["ad_거래액"] + sub["ep_거래액"]

    date_range = pd.date_range(actual_start, max_date, freq="D")
    result = {}
    for cat in categories:
        cat_scope = scope[scope["category"] == cat].copy()
        cat_scope["_rev"] = _rev(cat_scope)
        daily = cat_scope.groupby("date")["_rev"].sum().reindex(date_range, fill_value=0)

        trend_window = daily.iloc[-trend_days:]
        x = np.arange(len(trend_window))
        slope, intercept = linear_trend(pd.Series(x), pd.Series(trend_window.values))

        forecast_dates = list(pd.date_range(max_date + pd.Timedelta(days=1), periods=days_forecast, freq="D"))
        forecast_vals, band_upper, band_lower = [], [], []
        if slope is not None:
            resid = trend_window.values - (slope * x + intercept)
            resid_std = float(np.std(resid)) if len(resid) > 1 else 0.0
            last_x = len(trend_window) - 1
            for i in range(1, days_forecast + 1):
                fv = max(slope * (last_x + i) + intercept, 0)
                band = resid_std * (1 + 0.12 * i)
                forecast_vals.append(fv)
                band_upper.append(fv + band)
                band_lower.append(max(fv - band, 0))

        result[cat] = {
            "actual_dates": list(daily.index), "actual_vals": daily.tolist(),
            "forecast_dates": forecast_dates, "forecast_vals": forecast_vals,
            "band_upper": band_upper, "band_lower": band_lower,
        }
    return result


def cattxn_flow_matrix(df: pd.DataFrame, buckets, channel: str, txn_type: str = "전체", top_n: int = 7,
                       group_by: str = "category", category: str = "전체", brand: str = "전체"):
    """카테고리별(또는 브랜드별) 거래액 흐름(누적영역 차트)용: 버킷 x 그룹 매트릭스를 만들고,
    거래액 상위 top_n개만 개별로 두고 나머지는 '기타'로 묶는다.
    group_by='brand'이면 category로 범위를 좁힌 뒤 그 안에서 브랜드별로 나눌 수 있다.
    반환: (labels, category_order, values_dict) — values_dict[카테고리] = [버킷별 거래액 리스트]
    """
    prefix = "ad" if channel == "쇼핑검색광고" else "ep"
    rev_col = f"{prefix}_거래액"
    scope_category = category if group_by == "brand" else "전체"
    scope = _cattxn_scope(df, txn_type, scope_category, brand if group_by != "brand" else "전체")

    labels = [b[0] for b in buckets]
    matrix = {}
    for label, dates in buckets:
        sub = scope[scope["date"].isin(dates)]
        matrix[label] = sub.groupby(group_by)[rev_col].sum()

    all_groups = sorted(set().union(*[m.index for m in matrix.values()])) if matrix else []
    totals = pd.Series({g: sum(matrix[l].get(g, 0) for l in labels) for g in all_groups})
    top_groups = totals.sort_values(ascending=False).head(top_n).index.tolist()
    other_groups = [g for g in all_groups if g not in top_groups]

    values_dict = {g: [matrix[l].get(g, 0) for l in labels] for g in top_groups}
    if other_groups:
        values_dict["기타"] = [sum(matrix[l].get(g, 0) for g in other_groups) for l in labels]

    group_order = top_groups + (["기타"] if other_groups else [])
    return labels, group_order, values_dict


def cattxn_group_trend_table(df: pd.DataFrame, buckets, channel: str, txn_type: str = "전체",
                             group_by: str = "category", category: str = "전체", brand: str = "전체",
                             mode: str = "일평균") -> pd.DataFrame:
    """카테고리별(또는 브랜드별) 거래액 추이를 스파크라인 표용으로 정리.
    반환 컬럼: group(카테고리/브랜드명), trend(버킷별 거래액 리스트), latest(최근 버킷 값),
    prev(직전 버킷 값), delta_pct(증감률).

    mode='일평균'이면 버킷별 합계를 해당 버킷의 실제 일수로 나눈다 — 특히 마지막 버킷이
    아직 끝나지 않은 부분주(예: 7일 중 3일치)일 때, 이걸 그대로 이전 완결주(7일)와 비교하면
    실제로는 안 줄었는데도 큰 폭으로 하락한 것처럼 보이는 착시가 생긴다. 일평균으로 맞추면
    부분 기간이어도 공정하게 비교된다."""
    prefix = "ad" if channel == "쇼핑검색광고" else "ep"
    rev_col = f"{prefix}_거래액"
    scope_category = category if group_by == "brand" else "전체"
    scope_brand = brand if group_by != "brand" else "전체"
    scope = _cattxn_scope(df, txn_type, scope_category, scope_brand)

    bucket_days = [max(len(dates), 1) for _, dates in buckets]

    groups = sorted(scope[group_by].unique())
    rows = []
    for g in groups:
        g_scope = scope[scope[group_by] == g]
        raw_vals = [g_scope[g_scope["date"].isin(dates)][rev_col].sum() for _, dates in buckets]
        if mode == "일평균":
            vals = [v / d for v, d in zip(raw_vals, bucket_days)]
        else:
            vals = raw_vals
        latest = vals[-1] if vals else 0
        prev = vals[-2] if len(vals) >= 2 else None
        delta_pct = ((latest - prev) / prev * 100) if prev else None
        rows.append({"group": g, "trend": vals, "latest": latest, "prev": prev, "delta_pct": delta_pct})

    result = pd.DataFrame(rows)
    return result.sort_values("latest", ascending=False).reset_index(drop=True)


def cattxn_weekly_changes(df: pd.DataFrame, group_by: str = "category", txn_type: str = "전체",
                          category: str = "전체", brand: str = "전체") -> pd.DataFrame:
    """카테고리(또는 브랜드)별 주간(월요일 시작) 광고_거래액/EP_거래액 일평균과 전주 대비 증감률(%).
    EP 연관성(시차 상관관계) 분석용 — 전체 기간(2025~) 사용해 표본을 최대한 확보한다.
    카테고리별 실제 광고비 원본이 없어, 광고_거래액을 '얼마나 밀었는지'의 대리지표로 사용.
    group_by='brand'이면 category로 범위를 좁힌 뒤 그 안에서 브랜드별로 분석할 수 있다.
    마지막 주(아직 끝나지 않은 부분주)가 있어도 일평균으로 맞춰서 공정하게 비교한다."""
    import numpy as np
    scope_category = category if group_by == "brand" else "전체"
    scope_brand = brand if group_by != "brand" else "전체"
    scope = _cattxn_scope(df, txn_type, scope_category, scope_brand)

    d = scope.copy()
    d["_wk"] = d["date"] - pd.to_timedelta(d["date"].dt.weekday, unit="D")
    grouped = d.groupby([group_by, "_wk"])
    weekly = grouped[["ad_거래액", "ep_거래액"]].sum().reset_index()
    day_counts = grouped["date"].nunique().reset_index(name="_days")
    weekly = weekly.merge(day_counts, on=[group_by, "_wk"])
    weekly["ad_거래액"] = weekly["ad_거래액"] / weekly["_days"]
    weekly["ep_거래액"] = weekly["ep_거래액"] / weekly["_days"]
    weekly = weekly.drop(columns="_days")
    weekly = weekly.rename(columns={group_by: "category", "ad_거래액": "광고_거래액", "ep_거래액": "EP_거래액"})
    weekly = weekly.sort_values(["category", "_wk"]).reset_index(drop=True)
    weekly["광고_증감률"] = weekly.groupby("category")["광고_거래액"].pct_change() * 100
    weekly["EP_증감률"] = weekly.groupby("category")["EP_거래액"].pct_change() * 100
    weekly[["광고_증감률", "EP_증감률"]] = weekly[["광고_증감률", "EP_증감률"]].replace(
        [np.inf, -np.inf], np.nan
    )
    return weekly


def cattxn_share_series(df: pd.DataFrame, buckets, txn_type: str = "전체",
                        category: str = "전체", brand: str = "전체"):
    """버킷별 SA(쇼핑검색광고)/EP채널 거래액 비중(%) 추이. 둘의 합을 100%로 본다.
    반환: (labels, sa_share_list, ep_share_list)"""
    scope = _cattxn_scope(df, txn_type, category, brand)
    labels, sa_share, ep_share = [], [], []
    for label, dates in buckets:
        sub = scope[scope["date"].isin(dates)]
        sa = sub["ad_거래액"].sum()
        ep = sub["ep_거래액"].sum()
        total = sa + ep
        labels.append(label)
        sa_share.append(sa / total * 100 if total else None)
        ep_share.append(ep / total * 100 if total else None)
    return labels, sa_share, ep_share


def ad_cost_vs_sa_ep_weekly(main_df: pd.DataFrame, cattxn_df: pd.DataFrame, weeks, txn_type: str = "전체"):
    """구간별(일/주/월 등 buckets 형태 무관) 광고비·ROAS(전체채널, 태블로 소스) vs SA·EP 거래액
    (전체 카테고리) 비교. '광고 확대가 SA뿐 아니라 EP까지 같이 키우는지(전체 파이를 키우는지)'
    검증용. 마지막 구간이 아직 끝나지 않은 부분기간이어도, 그리고 광고비 원본(main_df)이
    cattxn_df보다 커버 기간이 짧아도(데이터 소스별 반영 지연 차이) 각각 실제 있는 일수로
    나눠 공정하게 비교한다.
    반환 컬럼: 주차, 광고비, ROAS, SA_거래액, EP_거래액, 광고비_증감률, SA_증감률, EP_증감률
    (광고비·SA_거래액·EP_거래액은 일평균, ROAS는 해당 구간 재계산 값)"""
    scope = cattxn_df if txn_type == "전체" else cattxn_df[cattxn_df["txn_type"] == txn_type]
    rows = []
    for label, dates in weeks:
        n_days = max(len(dates), 1)
        ad_view = main_df[main_df["date"].isin(dates)]
        n_ad_days = ad_view["date"].nunique()
        ad_agg = aggregate(ad_view) if not ad_view.empty else None
        ad_cost = (ad_agg["광고비"] / n_ad_days) if ad_agg and n_ad_days else None
        roas = ad_agg["ROAS"] if ad_agg else None
        sub = scope[scope["date"].isin(dates)]
        sa = sub["ad_거래액"].sum() / n_days
        ep = sub["ep_거래액"].sum() / n_days
        rows.append({"주차": label, "광고비": ad_cost, "ROAS": roas, "SA_거래액": sa, "EP_거래액": ep})
    result = pd.DataFrame(rows)
    for col in ["광고비", "SA_거래액", "EP_거래액"]:
        result[f"{col}_증감률"] = result[col].pct_change() * 100
    return result


def flow_overview_buckets(cattxn_df: pd.DataFrame, unit: str, n_recent: int = 12):
    """SA×EP 통합 흐름 섹션용 버킷. 조회단위(unit)에 맞춰 [(label, [dates...]), ...]를 반환한다.
    일별=최근 n_recent일, 주별=최근 n_recent주, 월별/월마감=2026년 전체 월."""
    max_date = pd.Timestamp(cattxn_df["date"].max())
    if unit == "일별":
        min_date = pd.Timestamp(cattxn_df["date"].min())
        start = max(max_date - pd.Timedelta(days=n_recent - 1), min_date)
        rng = pd.date_range(start, max_date, freq="D")
        return [(d.strftime("%m-%d"), [d]) for d in rng]
    if unit == "주별":
        return cattxn_period_buckets(cattxn_df, "주별")[-n_recent:]
    return cattxn_period_buckets(cattxn_df, "월별")


# ════════════════════════════════════════════════════════════════
# 쇼핑검색광고 리포트(NBOS 매칭, 대카테고리/중카테고리/브랜드 단위) — 상품군 효율
# build_ad_product_daily.py로 원본(상품 단위)을 미리 집계한 CSV를 읽는다.
# ROAS는 반드시 "판매액"(NBOS 매칭 실매출) 기준으로만 계산한다 — 원본의 "전환매출액"은
# 광고 플랫폼 자체 귀속(간접전환 포함) 기준이라 실매출과 크게 괴리될 수 있어 애초에
# 집계 단계에서 제외했다.
# ════════════════════════════════════════════════════════════════
AD_PRODUCT_OWN_OPTIONS = ["전체", "자사", "입점"]
AD_PRODUCT_BASE_METRICS = ["노출수", "클릭수", "광고비", "구매수량", "판매액"]


@st.cache_data
def load_ad_product_data():
    if os.path.exists(AD_PRODUCT_DATA_PATH):
        df = pd.read_csv(AD_PRODUCT_DATA_PATH, parse_dates=["date"], encoding="utf-8-sig")
    else:
        split_paths = []
        for pattern in _AD_PRODUCT_SPLIT_GLOBS:
            split_paths = sorted(glob.glob(pattern))
            if split_paths:
                break
        if not split_paths:
            return None
        df = pd.concat(
            [pd.read_csv(p, parse_dates=["date"], encoding="utf-8-sig") for p in split_paths],
            ignore_index=True,
        )
    df["연도"] = df["date"].dt.year
    return df


def _ad_product_scope(df: pd.DataFrame, own: str = "전체", large_cat: str = "전체",
                      mid_cat: str = "전체", brand: str = "전체") -> pd.DataFrame:
    scope = df
    if own != "전체":
        scope = scope[scope["자사/입점"] == own]
    if large_cat != "전체":
        scope = scope[scope["대카테고리"] == large_cat]
    if mid_cat != "전체":
        scope = scope[scope["중카테고리"] == mid_cat]
    if brand != "전체":
        scope = scope[scope["브랜드명"] == brand]
    return scope


def _ad_product_derive(sums: dict) -> dict:
    sums["ROAS"] = (sums["판매액"] / sums["광고비"]) if sums["광고비"] else 0
    sums["CTR"] = (sums["클릭수"] / sums["노출수"]) if sums["노출수"] else 0
    sums["CVR"] = (sums["구매수량"] / sums["클릭수"]) if sums["클릭수"] else 0
    sums["객단가"] = (sums["판매액"] / sums["구매수량"]) if sums["구매수량"] else 0
    return sums


def aggregate_ad_product(df: pd.DataFrame, own: str = "전체", large_cat: str = "전체",
                         mid_cat: str = "전체", brand: str = "전체") -> dict:
    scope = _ad_product_scope(df, own, large_cat, mid_cat, brand)
    sums = {c: scope[c].sum() for c in AD_PRODUCT_BASE_METRICS}
    return _ad_product_derive(sums)


def aggregate_ad_product_by(df: pd.DataFrame, group_col: str, own: str = "전체",
                            large_cat: str = "전체", mid_cat: str = "전체") -> pd.DataFrame:
    """group_col(대카테고리/중카테고리/브랜드명) 기준으로 집계 + ROAS·CTR·CVR 재계산.
    group_col='중카테고리'/'브랜드명'일 때는 large_cat(/mid_cat)으로 범위를 좁힌 뒤
    그 안에서 순위를 매기는 용도로 쓴다."""
    scope = _ad_product_scope(df, own, large_cat, mid_cat)
    grouped = scope.groupby(group_col)[AD_PRODUCT_BASE_METRICS].sum().reset_index()
    grouped["ROAS"] = grouped.apply(lambda r: (r["판매액"] / r["광고비"]) if r["광고비"] else 0, axis=1)
    grouped["CTR"] = grouped.apply(lambda r: (r["클릭수"] / r["노출수"]) if r["노출수"] else 0, axis=1)
    grouped["CVR"] = grouped.apply(lambda r: (r["구매수량"] / r["클릭수"]) if r["클릭수"] else 0, axis=1)
    return grouped


def _pct_change_simple(cur, prev):
    if cur is None or prev is None or pd.isna(cur) or pd.isna(prev) or prev == 0:
        return None
    return (cur - prev) / abs(prev) * 100


def ad_product_group_compare(df: pd.DataFrame, group_col: str, cur_start, cur_end, prev_start, prev_end,
                             own: str = "전체", large_cat: str = "전체", mid_cat: str = "전체") -> pd.DataFrame:
    """group_col(대카테고리/중카테고리/브랜드명) 기준으로 현재기간 vs 비교기간의
    판매액/광고비/ROAS/CTR/CVR을 나란히 계산하고, 판매액·ROAS·CVR 증감률(%)을 덧붙인다.
    카테고리별 액션(광고비 증액/점검) 판단을 위한 랭킹 표에 쓴다."""
    scope = _ad_product_scope(df, own, large_cat, mid_cat)
    cur = scope[(scope["date"] >= pd.Timestamp(cur_start)) & (scope["date"] <= pd.Timestamp(cur_end))]
    prev = scope[(scope["date"] >= pd.Timestamp(prev_start)) & (scope["date"] <= pd.Timestamp(prev_end))]

    def _agg_by(sub: pd.DataFrame) -> pd.DataFrame:
        g = sub.groupby(group_col)[AD_PRODUCT_BASE_METRICS].sum()
        g["ROAS"] = g.apply(lambda r: (r["판매액"] / r["광고비"]) if r["광고비"] else 0, axis=1)
        g["CTR"] = g.apply(lambda r: (r["클릭수"] / r["노출수"]) if r["노출수"] else 0, axis=1)
        g["CVR"] = g.apply(lambda r: (r["구매수량"] / r["클릭수"]) if r["클릭수"] else 0, axis=1)
        g["객단가"] = g.apply(lambda r: (r["판매액"] / r["구매수량"]) if r["구매수량"] else 0, axis=1)
        return g

    cur_g = _agg_by(cur)
    prev_g = _agg_by(prev)
    all_groups = sorted(set(cur_g.index) | set(prev_g.index))

    rows = []
    for g in all_groups:
        c = cur_g.loc[g] if g in cur_g.index else None
        p = prev_g.loc[g] if g in prev_g.index else None
        row = {group_col: g}
        for metric in AD_PRODUCT_BASE_METRICS + ["ROAS", "CTR", "CVR", "객단가"]:
            row[metric] = c[metric] if c is not None else 0
        row["판매액_증감"] = _pct_change_simple(c["판매액"] if c is not None else None,
                                              p["판매액"] if p is not None else None)
        row["판매액_증감액"] = (c["판매액"] if c is not None else 0) - (p["판매액"] if p is not None else 0)
        row["판매액_전기"] = p["판매액"] if p is not None else 0
        row["광고비_증감"] = _pct_change_simple(c["광고비"] if c is not None else None,
                                             p["광고비"] if p is not None else None)
        row["광고비_전기"] = p["광고비"] if p is not None else 0
        row["ROAS_증감"] = _pct_change_simple(c["ROAS"] if c is not None else None,
                                             p["ROAS"] if p is not None else None)
        row["ROAS_전기"] = p["ROAS"] if p is not None else 0
        row["CVR_증감"] = _pct_change_simple(c["CVR"] if c is not None else None,
                                            p["CVR"] if p is not None else None)
        row["CVR_전기"] = p["CVR"] if p is not None else 0
        row["성과"] = classify_ad_product_performance(row["판매액_증감"], row["ROAS_증감"], row["구매수량"])
        rows.append(row)

    if not rows:
        # 해당 기간·필터 조합에 데이터가 전혀 없으면 rows=[]가 되는데, pd.DataFrame([])는
        # 컬럼이 아예 없는(0x0) 프레임이 돼서 이후 .sort_values("판매액_증감", ...) 등에서
        # KeyError가 난다 — 빈 데이터라도 항상 같은 컬럼 스키마를 갖도록 명시한다.
        cols = [group_col] + AD_PRODUCT_BASE_METRICS + [
            "ROAS", "CTR", "CVR", "객단가", "판매액_증감", "판매액_증감액", "판매액_전기",
            "광고비_증감", "광고비_전기",
            "ROAS_증감", "ROAS_전기", "CVR_증감", "CVR_전기", "성과",
        ]
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(rows)


def classify_ad_product_performance(sale_pct, roas_pct, cur_purchases: float = None,
                                    min_purchases: int = 1, threshold: float = 5.0):
    """판매액 증감 x ROAS 증감 조합으로 카테고리/브랜드 성과를 분류.
    threshold(%p) 이내는 '변화 미미'로 취급. 04페이지 랭킹표에서 액션 우선순위를
    한눈에 보기 위한 배지.
    cur_purchases(이번 기간 구매수량)가 min_purchases 미만이면 등락률이 아무리 커도
    "🟢 우수"/"🔴 부진"으로 분류하지 않는다 — 예: 지난주 1건→이번주 2건처럼 표본이 극히
    작을 때 +100%처럼 과장된 등락률만 보고 우수/부진으로 잘못 판단하는 걸 막기 위함."""
    if sale_pct is None or roas_pct is None or pd.isna(sale_pct) or pd.isna(roas_pct):
        return "-"
    if cur_purchases is not None and cur_purchases < min_purchases:
        return "⚪ 표본 부족(구매 거의 없음)"
    if sale_pct > threshold and roas_pct > threshold:
        return "🟢 우수(증액 검토)"
    if sale_pct > threshold and roas_pct < -threshold:
        return "🟡 물량↑효율↓(점검 필요)"
    if sale_pct < -threshold and roas_pct > threshold:
        return "🔵 효율 개선(회복 여지)"
    if sale_pct < -threshold and roas_pct < -threshold:
        return "🔴 부진(축소·재검토)"
    if abs(sale_pct) <= threshold and abs(roas_pct) <= threshold:
        return "⚫ 변화 미미"
    return "⚪ 혼조"


def classify_comovement(sa_pct, ep_pct, threshold: float = 5.0):
    """SA/EP 증감률 조합으로 동행 패턴을 분류. threshold 이하는 '변화 미미'로 취급."""
    if sa_pct is None or ep_pct is None or pd.isna(sa_pct) or pd.isna(ep_pct):
        return "-"
    if sa_pct > threshold and ep_pct > threshold:
        return "🟢 동반상승"
    if sa_pct > threshold and ep_pct < -threshold:
        return "🔴 광고잠식 의심"
    if sa_pct > threshold and abs(ep_pct) <= threshold:
        return "🔵 SA단독 성장"
    if sa_pct < -threshold and ep_pct < -threshold:
        return "⚪ 동반하락"
    if abs(sa_pct) <= threshold and abs(ep_pct) <= threshold:
        return "⚫ 변화 미미"
    return "🟡 혼조"
