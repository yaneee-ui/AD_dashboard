# 쇼핑검색광고 실적 대시보드

네이버 쇼핑검색광고(+ EP채널 비교) 실적을 조회하고 전년 대비 비교하는 Streamlit 대시보드입니다.

## 데이터 소스 구조

| 소스 | 파일 | 포함 지표 | 용도 |
|---|---|---|---|
| **① 쇼핑검색광고 리포트** (NBOS 매칭) | `shopping_ad_report_daily.csv`, `category_daily.csv` | 노출/클릭/광고비 + NBOS 판매액, 카테고리별 거래액 | 카테고리별 실적(03), EP 상관관계 분석(05) |
| **② 일일리포트[태블로]** | `tableau_daily.csv` | 거래액, 구매건수 등 전체 큰 흐름 | 쇼핑검색광고 실적(01), 전년비교(02) |

`shopping_ad_report_daily.csv`는 현재 어느 페이지에서도 직접 쓰이진 않지만, 추후 상품/브랜드별
ROAS 매칭 기능에 쓸 수 있도록 남겨뒀습니다 (`utils.py`의 `load_ad_report_data()`).

## 구성

```
shopping-ad-dashboard/
├── app.py                          # 메인 대시보드 (5개 페이지, 사이드바 메뉴)
├── utils.py                        # 데이터 로드 + 비율지표 재계산 + 기간/비교/상관분석 로직
├── styles.py                       # 다크 사이드바 + KPI 카드 + 배지 스타일 컴포넌트
├── converter_app.py                # 원본 리포트 → 대시보드용 CSV 변환기 (별도 실행)
├── data/
│   ├── tableau_daily.csv           # ② 일일리포트[태블로] (01·02 페이지 기준)
│   ├── shopping_ad_report_daily.csv # ① 쇼핑검색광고 리포트 아카이브 (현재 미사용, 추후 대비)
│   ├── category_daily.csv          # ① 카테고리별 쇼핑검색광고/EP채널 거래액
│   └── fitflop_monthly.csv         # 핏플랍 브랜드 제외 비교용 월별 데이터
├── requirements.txt
└── README.md
```

## 대시보드 페이지

1. **쇼핑검색광고 실적** — 기준일자(일/주/월 단위 선택) + 표시방식(누계/일평균), KPI 카드
   (전일·전주·전월비 + 전년비 배지), 실적요약 비교 테이블, 2026년 추이(전년비 비교선) 차트, 원본 데이터 다운로드
   → **② 일일리포트[태블로] 기준**
2. **전년비교** — 일자별 YoY(전년 동일 요일 매칭) / 월별 누적 YoY → **② 일일리포트[태블로] 기준**
3. **카테고리별 실적** — 카테고리(12개)별 쇼핑검색광고 vs EP채널 거래액 비교, 거래유형(정상/이월/입점)
   필터, 랭킹 차트/테이블, 카테고리별 거래액 흐름 비교 → **① 쇼핑검색광고 리포트 기준**
4. **핏플랍 제외 비교** — 특정 브랜드 퇴점으로 인한 거래액·광고비 왜곡을 제외하고 자사 실적의
   실제 흐름/전년비를 비교 (월별)
5. **EP 상관관계 분석** — 카테고리별로 쇼핑검색광고 확대가 EP 거래액 상승과 연결되는지, 시차별
   상관관계 랭킹 + 산점도로 점검 (현재는 카테고리별 광고비 원본이 없어 광고 거래액을 대리지표로 사용)

## 비율 지표 처리 원칙

CTR, CR, 객단가, ROAS, 순결제비중 등 비율 지표는 절대 **일자별 값의 평균을 내지 않습니다.**
대신 `utils.py`의 `RATIO_DEFS`에 정의된 분자/분모 원천값(base metric)을 먼저 합산한 뒤
재계산하여, 어떤 기간으로 집계하든 정확한 값이 나오도록 했습니다.

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

## 데이터 갱신 (매번 반복되는 작업 → 변환기 웹앱 사용)

모든 원본 리포트가 **매번 전체 누적 기간을 다시 추출하는 형태**이므로, 새 리포트를 받을 때마다
증분 병합할 필요 없이 그냥 전체를 다시 변환해서 기존 CSV를 통째로 교체하면 됩니다.

`converter_app.py`가 이 작업을 해주는 별도 웹앱입니다:

```bash
streamlit run converter_app.py
```

- **① 일일리포트[태블로] 탭**: 일자별 RAW 엑셀 업로드 → `tableau_daily.csv` 다운로드
  (맨 아래 "총합계" 같은 합계 행이 있어도 자동으로 제외합니다)
- **② 카테고리별 실적 탭**: `네이버_쇼검_ep거래액_상세_YYYYMMDD.csv` 업로드 → `category_daily.csv` 다운로드

각 탭에서 변환 후 행 수·날짜 범위·날짜 누락 여부를 바로 확인할 수 있고,
다운로드한 파일로 GitHub 리포의 `data/` 폴더 안 동일한 이름의 파일을 교체(덮어쓰기)하면 됩니다.

이 변환기도 `app.py`처럼 Streamlit Community Cloud에 별도 앱으로 배포해두면(Main file path를
`converter_app.py`로 지정), 매번 로컬 실행 없이 웹에서 바로 변환할 수 있습니다.
