"""
② 일일리포트[태블로] 원본(엑셀) -> tableau_daily.csv 갱신 스크립트.

원본 시트는 첫 컬럼이 "기간_일자"(또는 "기간_일자+요일") 형식으로
"26-08-01 (토)" 처럼 2자리 연도+요일이 묶여 있고, 맨 마지막에 "총합계" 같은
합계 행이 붙어있는 경우가 있어 그 행은 제외한다. 나머지 컬럼(노출수~윈백거래액)은
tableau_daily.csv와 동일한 구성이라 그대로 옮기고, 날짜 문자열에서 실제 날짜만
뽑아 "date" 컬럼(YYYY-MM-DD)을 새로 만든다.

사용법:
    python build_tableau_daily.py <원본.xlsx> [--sheet Sheet2] [--out tableau_daily.csv]

기존 CSV가 있으면, 새로 변환한 날짜는 새 값으로 덮어쓰고(재확정 반영) 그 외
기존 날짜는 유지한 채 합쳐서 저장한다 — 여러 번 실행해도 안전하다.
"""

import argparse
import os
import re
import sys

import pandas as pd

DATE_COL_CANDIDATES = ["기간_일자+요일", "기간_일자"]
DATE_RE = re.compile(r"^(\d{2})-(\d{2})-(\d{2})")


def _parse_date(raw: str):
    if not isinstance(raw, str):
        return None
    m = DATE_RE.match(raw.strip())
    if not m:
        return None
    yy, mm, dd = m.groups()
    return pd.Timestamp(year=2000 + int(yy), month=int(mm), day=int(dd))


def convert(raw_path: str, sheet, out_path: str):
    print(f"원본 로드 중: {raw_path} (시트: {sheet or '첫 시트'})")
    df = pd.read_excel(raw_path, sheet_name=sheet if sheet else 0)

    date_col = next((c for c in DATE_COL_CANDIDATES if c in df.columns), None)
    if date_col is None:
        print(f"[오류] 날짜 컬럼을 찾을 수 없습니다 (후보: {DATE_COL_CANDIDATES}). "
              f"실제 컬럼: {list(df.columns)}")
        sys.exit(1)

    df["date"] = df[date_col].apply(_parse_date)
    before = len(df)
    df = df[df["date"].notna()].copy()
    dropped = before - len(df)
    if dropped:
        print(f"날짜로 해석 안 되는 행 {dropped}개 제외(합계 행 등으로 추정).")

    print(f"변환 완료: {len(df):,}행 ({df['date'].min().date()} ~ {df['date'].max().date()})")

    if os.path.exists(out_path):
        existing = pd.read_csv(out_path, encoding="utf-8-sig", parse_dates=["date"])
        new_dates = set(df["date"].unique())
        kept = existing[~existing["date"].isin(new_dates)]
        # 기존 CSV 컬럼 순서를 그대로 따르고, 새 데이터도 같은 컬럼 집합으로 맞춘다.
        df_aligned = df.reindex(columns=existing.columns)
        merged = pd.concat([kept, df_aligned], ignore_index=True)
        print(f"기존 파일 병합: 기존 {len(existing):,}행 중 겹치는 날짜 제외 {len(kept):,}행 유지 "
              f"+ 신규 {len(df):,}행 -> 총 {len(merged):,}행")
    else:
        merged = df

    merged["date"] = pd.to_datetime(merged["date"]).dt.date
    merged = merged.sort_values("date").reset_index(drop=True)
    merged.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"저장 완료: {out_path} (전체 날짜 범위: {merged['date'].min()} ~ {merged['date'].max()})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw_path", help="원본 엑셀 파일 경로")
    parser.add_argument("--sheet", default=None, help="시트명 (기본: 첫 번째 시트)")
    parser.add_argument("--out", default="tableau_daily.csv", help="출력 CSV 경로")
    args = parser.parse_args()
    convert(args.raw_path, args.sheet, args.out)
