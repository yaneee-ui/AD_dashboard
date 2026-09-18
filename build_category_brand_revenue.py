"""
카테고리·브랜드별 정상/이월/입점 거래액+주문고객수(광고·EP) 원본(엑셀) ->
category_brand_txn_daily.csv 갱신 스크립트.

원본은 엑셀 피벗표를 그대로 내보낸 형식이라 헤더가 3줄에 걸쳐 있다:
    행0: (병합) "AF대분류명"이 광고/EP 두 그룹을 감싸는 상위 라벨
    행1: "광고" / "EP" (각각 거래액·주문고객수 두 컬럼씩 아래에 붙음)
    행2: 정상이월구분명 / 영업상품카테고리명 / SAP대표브랜드코드 / 결제_일자(YYYYMMDD) /
         거래액 / 주문고객수 / 거래액 / 주문고객수   (광고·EP 둘 다 "거래액"/"주문고객수"라
         이름이 겹쳐서, 그 4개는 헤더 이름이 아니라 뒤에서부터 위치로 골라낸다)
앞 4개(정상이월구분명/영업상품카테고리명/SAP대표브랜드코드/결제_일자)는 이름으로 찾는다 —
내보낼 때마다 이 4개의 순서가 바뀌는 경우가 있었다(2026-09-18: 결제_일자가 맨 앞으로
이동). 뒤 4개(거래액·주문고객수 x2, 광고→EP 순)는 이름이 겹쳐서 그럴 수 없지만, 항상
앞 4개 다음의 마지막 4자리라는 구조 자체는 안 바뀌어서 위치로 골라내도 안전하다.

그리고 병합 셀 내보내기라 "그룹의 첫 행에만 값이 있고 나머지 행은 비어있는" 컬럼이
있다 — 그룹 내 다음 행들에 값을 그대로 채워 넣는(forward-fill) 전처리가 필요하다.
어떤 컬럼이 그 대상인지는 내보내기마다 다를 수 있어서(2026-09-18: 이전엔 SAP대표
브랜드코드가 그 대상이고 결제_일자는 매 행 채워져 있었는데, 이번엔 반대로 결제_일자/
정상이월구분명/영업상품카테고리명이 그 대상이고 SAP대표브랜드코드가 매 행 채워져
있음), 결측치가 있는 컬럼만 그때그때 자동으로 골라 ffill한다.

사용법:
    python build_category_brand_revenue.py <원본.xlsx> [--out category_brand_txn_daily.csv]

기존 CSV가 있으면, 새로 변환한 날짜는 새 값으로 덮어쓰고(재확정 반영) 그 외 기존
날짜는 유지한 채 합쳐서 저장한다 — 여러 번 실행해도 안전하다.
"""

import argparse
import os
import sys

import pandas as pd

EXPECTED_NCOLS = 8
ID_COLS = ["정상이월구분명", "영업상품카테고리명", "SAP대표브랜드코드", "결제_일자(YYYYMMDD)"]
VALUE_OUT_COLS = ["ad_거래액", "ad_주문고객수", "ep_거래액", "ep_주문고객수"]


def convert(raw_path: str, out_path: str):
    print(f"원본 로드 중: {raw_path}")
    raw = pd.read_excel(raw_path, header=2)

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
    })
    for out_name, col_pos in zip(VALUE_OUT_COLS, range(EXPECTED_NCOLS - 4, EXPECTED_NCOLS)):
        df[out_name] = raw.iloc[:, col_pos]

    # 병합 셀 내보내기라 일부 컬럼(어느 컬럼인지는 내보내기마다 다름)이 그룹 첫 행에만
    # 값이 있다 — 결측치가 있는 식별 컬럼만 그대로 채워 넣는다(위 docstring 참고).
    blank_id_cols = [c for c in ["date", "txn_type", "category", "brand"] if df[c].isna().any()]
    if blank_id_cols:
        df[blank_id_cols] = df[blank_id_cols].ffill()

    # 날짜 컬럼이 문자열("20250101")로 올 때도, 숫자(20250101.0)로 올 때도 있어(엑셀 셀
    # 서식 차이) 숫자 경유로 통일한 뒤 파싱한다 — astype(str)을 바로 쓰면 float일 때
    # "20250101.0"이 돼서 %Y%m%d 파싱이 전부 실패(NaT)한다.
    df["date"] = pd.to_datetime(
        pd.to_numeric(df["date"], errors="coerce").astype("Int64").astype(str),
        format="%Y%m%d", errors="coerce",
    )
    before = len(df)
    df = df[df["date"].notna()].copy()
    dropped = before - len(df)
    if dropped:
        print(f"날짜로 해석 안 되는 행 {dropped}개 제외.")

    for c in ["ad_거래액", "ad_주문고객수", "ep_거래액", "ep_주문고객수"]:
        df[c] = df[c].fillna(0)

    # 그룹(txn_type/category/brand/date) 안에서도 여러 행으로 쪼개져 있을 수 있어 합산.
    agg = df.groupby(["date", "txn_type", "category", "brand"], as_index=False)[
        ["ad_거래액", "ad_주문고객수", "ep_거래액", "ep_주문고객수"]
    ].sum()
    print(f"변환 완료: {before:,}행 -> {len(agg):,}행 "
          f"({agg['date'].min().date()} ~ {agg['date'].max().date()})")

    if os.path.exists(out_path):
        existing = pd.read_csv(out_path, parse_dates=["date"], encoding="utf-8-sig")
        new_dates = set(agg["date"].unique())
        kept = existing[~existing["date"].isin(new_dates)]
        agg_aligned = agg.reindex(columns=existing.columns)
        merged = pd.concat([kept, agg_aligned], ignore_index=True)
        print(f"기존 파일 병합: 기존 {len(existing):,}행 중 겹치는 날짜 제외 {len(kept):,}행 유지 "
              f"+ 신규 {len(agg):,}행 -> 총 {len(merged):,}행")
    else:
        merged = agg[["date", "txn_type", "category", "brand", "ad_거래액", "ad_주문고객수",
                       "ep_거래액", "ep_주문고객수"]]

    merged = merged.sort_values(["date", "category", "brand"]).reset_index(drop=True)
    merged.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"저장 완료: {out_path} (전체 날짜 범위: {merged['date'].min()} ~ {merged['date'].max()})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw_path", help="원본 엑셀 파일 경로")
    parser.add_argument("--out", default="category_brand_txn_daily.csv", help="출력 CSV 경로")
    args = parser.parse_args()
    convert(args.raw_path, args.out)
