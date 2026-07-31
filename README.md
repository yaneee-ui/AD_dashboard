# 쇼핑검색광고 실적 대시보드

네이버 쇼핑검색광고 일자별 실적을 조회하고 전년 대비 비교하는 Streamlit 대시보드입니다.

## 구성

```
shopping-ad-dashboard/
├── app.py                      # 메인 앱 (사이드바: 실적 / 전년비교)
├── utils.py                    # 데이터 로드 + 비율지표 재계산 로직
├── data/
│   └── shopping_ad_daily.csv   # 일자별 원천 데이터 (25-01-01 ~ 26-07-30)
├── requirements.txt
└── README.md
```

## 페이지

1. **쇼핑검색광고 실적**
   - 기간 필터(직접선택/최근7일/최근30일/이번달/전체)
   - 핵심 지표 카드 (UV, 거래액, 광고비, ROAS, CR, CTR, 신규/첫구매/가입 지표)
   - 지표 선택형 일자별 추이 차트
   - 데이터 테이블 + Excel 다운로드

2. **전년비교**
   - **일자별 YoY**: 전년 동일 요일(364일 전) 기준 비교, 라인 차트 + 증감률 테이블
   - **월별 누적 YoY**: 두 연도의 겹치는 월을 막대 그래프로 비교, YoY% 포함

## 비율 지표 처리 원칙

CTR, CR, 객단가, ROAS, 순결제비중 등 비율 지표는 절대 **일자별 값의 평균을 내지 않습니다.**
대신 `utils.py`의 `RATIO_DEFS`에 정의된 분자/분모 원천값(base metric)을 먼저 합산한 뒤
재계산하여, 어떤 기간으로 집계하든 정확한 값이 나오도록 했습니다.
(EP 대시보드에서 확인된 것과 동일한 원칙 — 일자별 비율을 그대로 평균하면 왜곡됩니다.)

## 로컬 실행

```bash
pip install -r requirements.txt
streamlit run app.py
```

## GitHub 업로드 & Streamlit Community Cloud 배포

```bash
git init
git add .
git commit -m "Initial commit: 쇼핑검색광고 실적 대시보드"
git branch -M main
git remote add origin <YOUR_GITHUB_REPO_URL>
git push -u origin main
```

이후 [share.streamlit.io](https://share.streamlit.io) 에서 New app → 방금 만든 repo 선택 →
Main file path를 `app.py`로 지정하면 배포됩니다.

## 데이터 갱신

새로운 일일리포트 RAW 엑셀을 받으면, 아래 스크립트로 `data/shopping_ad_daily.csv`를 다시 생성하세요.

```python
import pandas as pd

df = pd.read_excel("일일리포트_쇼핑검색광고_RAW.xlsx", sheet_name="Sheet1")
df["date"] = pd.to_datetime(
    df["기간_일자+요일"].str.split(" ").str[0], format="%y-%m-%d"
)
df = df.sort_values("date").reset_index(drop=True)
df.to_csv("data/shopping_ad_daily.csv", index=False, encoding="utf-8-sig")
```
