"""
상품별 정상/이월/입점 거래액+주문고객수(광고·EP) 원본 -> product_txn_daily.csv 갱신 스크립트.

build_category_brand_revenue.py와 같은 피벗표 구조이되, 상품코드/상품명 두 컬럼이
더 있다 — 헤더가 3줄에 걸쳐 있고(행0: 광고/EP 상위 라벨, 행1: 광고/광고/EP/EP,
행2: 정상이월구분명/영업상품카테고리명/SAP대표브랜드코드/결제_일자(YYYYMMDD)/상품코드/
상품명/거래액/주문고객수/거래액/주문고객수), 앞 6개(식별 컬럼)는 이름으로 찾고 뒤
4개(거래액·주문고객수 x2, 광고→EP 순)는 이름이 겹쳐서 위치로 골라낸다 — 전부
build_category_brand_revenue.py와 동일한 규칙.

상품 단위라 용량이 커서(2026년 1년치만 약 40만행) 2025년분은 받지 않기로 했다
— MIN_DATE가 category_brand_txn_daily.csv보다 늦어도 정상이다. utils.py 쪽에서
cattxn과 별도로 자기 날짜범위를 갖도록 처리한다.

원본은 엑셀(.xlsx)로 올 수도, 피벗표를 "유니코드 텍스트(.csv, UTF-16 탭구분)"로
내보낸 형태로 올 수도 있어 둘 다 읽어본다(인코딩/구분자 조합을 순서대로 시도).

거래액 컬럼은 천단위 콤마가 섞인 문자열("160,364")로 올 때가 있어 숫자 변환 전에
콤마를 제거한다.

사용법:
    python build_product_revenue.py <원본.xlsx|원본.csv> [--out product_txn_daily.csv]

기존 CSV가 있으면, 새로 변환한 날짜는 새 값으로 덮어쓰고(재확정 반영) 그 외 기존
날짜는 유지한 채 합쳐서 저장한다 — 여러 번 실행해도 안전하다.
"""

import argparse
import os
import sys

import pandas as pd

EXPECTED_NCOLS = 10
ID_COLS = ["정상이월구분명", "영업상품카테고리명", "SAP대표브랜드코드", "결제_일자(YYYYMMDD)",
           "상품코드", "상품명"]
VALUE_OUT_COLS = ["ad_거래액", "ad_주문고객수", "ep_거래액", "ep_주문고객수"]


def _read_raw(raw_path: str) -> pd.DataFrame:
    ext = os.path.splitext(raw_path)[1].lower()
    if ext in (".xlsx", ".xls"):
        return pd.read_excel(raw_path, header=2)

    attempts = [
        dict(encoding="utf-16", sep="\t"),
        dict(encoding="utf-8-sig", sep=","),
        dict(encoding="cp949", sep=","),
    ]
    last_err = None
    for kwargs in attempts:
        try:
            df = pd.read_csv(raw_path, header=2, **kwargs)
            if df.shape[1] >= EXPECTED_NCOLS:
                return df
        except Exception as e:
            last_err = e
    raise last_err or ValueError("CSV를 읽을 수 없습니다 (인코딩/구분자 조합을 모두 시도했지만 실패).")


def _to_num(series: pd.Series) -> pd.Series:
    # pandas 버전에 따라 콤마 섞인 문자열 컬럼이 object가 아니라 전용 string dtype으로
    # 올 수 있어(dtype == object 비교로는 못 잡음), 숫자 dtype이 아니면 전부 문자열
    # 경유로 처리한다. astype(str)이 NaN을 "nan" 문자열로 바꿔버리는 것도 먼저 치환해둔다.
    if pd.api.types.is_numeric_dtype(series):
        return series.fillna(0)
    series = series.astype(str).str.replace(",", "", regex=False).str.strip()
    series = series.replace({"nan": None, "None": None, "NaT": None})
    return pd.to_numeric(series, errors="coerce").fillna(0)


def convert(raw_path: str, out_path: str):
    print(f"원본 로드 중: {raw_path}")
    raw = _read_raw(raw_path)

    if raw.shape[1] != EXPECTED_NCOLS:
        print(f"[오류] 예상한 컬럼 수({EXPECTED_NCOLS})와 다릅니다: {raw.shape[1]}개\n"
              f"실제 컬럼: {list(raw.columns)}")
        sys.exit(1)
    missing_id = [c for c in ID_COLS if c not in raw.columns]
    if missing_id:
        print(f"[오류] 다음 컬럼을 찾을 수 없습니다: {missing_id}\n"
              f"실제 컬럼: {list(raw.columns)}")
        sys.exit(1)

    df = pd.DataFrame({
        "txn_type": raw["정상이월구분명"],
        "category": raw["영업상품카테고리명"],
        "brand": raw["SAP대표브랜드코드"],
        "date": raw["결제_일자(YYYYMMDD)"],
        "product_code": raw["상품코드"],
        "product_name": raw["상품명"],
    })
    for out_name, col_pos in zip(VALUE_OUT_COLS, range(EXPECTED_NCOLS - 4, EXPECTED_NCOLS)):
        df[out_name] = _to_num(raw.iloc[:, col_pos])

    blank_id_cols = [c for c in ["date", "txn_type", "category", "brand", "product_code", "product_name"]
                     if df[c].isna().any()]
    if blank_id_cols:
        df[blank_id_cols] = df[blank_id_cols].ffill()

    df["date"] = pd.to_datetime(
        pd.to_numeric(df["date"], errors="coerce").astype("Int64").astype(str),
        format="%Y%m%d", errors="coerce",
    )
    before = len(df)
    df = df[df["date"].notna()].copy()
    dropped = before - len(df)
    if dropped:
        print(f"날짜로 해석 안 되는 행 {dropped}개 제외.")

    agg = df.groupby(
        ["date", "txn_type", "category", "brand", "product_code", "product_name"], as_index=False
    )[VALUE_OUT_COLS].sum()
    print(f"변환 완료: {before:,}행 -> {len(agg):,}행 "
          f"({agg['date'].min().date()} ~ {agg['date'].max().date()}, 상품 {agg['product_code'].nunique():,}개)")

    out_cols = ["date", "txn_type", "category", "brand", "product_code", "product_name"] + VALUE_OUT_COLS
    if os.path.exists(out_path):
        existing = pd.read_csv(out_path, parse_dates=["date"], encoding="utf-8-sig")
        new_dates = set(agg["date"].unique())
        kept = existing[~existing["date"].isin(new_dates)]
        agg_aligned = agg.reindex(columns=existing.columns)
        merged = pd.concat([kept, agg_aligned], ignore_index=True)
        print(f"기존 파일 병합: 기존 {len(existing):,}행 중 겹치는 날짜 제외 {len(kept):,}행 유지 "
              f"+ 신규 {len(agg):,}행 -> 총 {len(merged):,}행")
    else:
        merged = agg[out_cols]

    merged = merged.sort_values(["date", "category", "product_code"]).reset_index(drop=True)
    merged.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"저장 완료: {out_path} (전체 날짜 범위: {merged['date'].min()} ~ {merged['date'].max()})")

    _write_half_splits(merged, out_path)


def _write_half_splits(merged: pd.DataFrame, out_path: str):
    """합본이 GitHub 권장 상한(50MB)을 넘기 쉬워 합본은 .gitignore하고, 반기별 조각
    (product_txn_daily_2026H1.csv 등)을 커밋한다 — utils.load_product_txn_data()가 합본이
    없으면(배포 환경) 조각을 합쳐서 읽는다."""
    stem, ext = os.path.splitext(out_path)
    half = merged["date"].dt.month.apply(lambda m: "H1" if m <= 6 else "H2")
    for (year, h), g in merged.groupby([merged["date"].dt.year, half]):
        split_path = f"{stem}_{year}{h}{ext}"
        g.to_csv(split_path, index=False, encoding="utf-8-sig")
        print(f"  반기별 분할 저장: {split_path} ({len(g):,}행, {os.path.getsize(split_path) / 1_000_000:.1f}MB)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw_path", help="원본 파일 경로 (.xlsx 또는 .csv)")
    parser.add_argument("--out", default="product_txn_daily.csv", help="출력 CSV 경로")
    args = parser.parse_args()
    convert(args.raw_path, args.out)
