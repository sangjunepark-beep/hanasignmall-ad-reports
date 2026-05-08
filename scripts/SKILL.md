---
name: ceo-ad-report
description: "하나사인몰 박상준 차장 대표보고용 광고 보고서 자동 생성. 일간(어제) 또는 지정 날짜 — '대표보고서', '광고보고서', '어제 광고보고서', '광고일일보고서', '대표용 보고서', '광고 대시보드', '통합 광고보고서'. 주간 합본 — '주간 보고서', '주간 합본', '7일 보고서', '주간 광고보고서', '이번주 보고서'. 박상준 차장 대표보고 관련 요청 시 반드시 이 스킬을 먼저 읽고 build_report.py 또는 build_weekly_report.py 호출하세요."
---

# 하나사인몰 대표보고용 광고 보고서 빌드 스킬

박상준 차장 매일 대표보고용. 일간(전일) + 주간(7일) 두 가지 빌드 가능.

## 호출 분기

### 일간 보고서 (전일 1매)
요청 키워드: 대표보고서 / 광고보고서 / 어제 광고보고서 / 광고일일보고서 / 대표용 보고서 / 광고 대시보드 / 통합 광고보고서

```bash
python3 build_report.py            # 어제 KST 자동
python3 build_report.py 2026-04-28 # 특정 날짜
```

출력: `<WORKSPACE>/네이버광고_1차보고대시보드_YYYY-MM-DD.html` (~700~900KB)

### 주간 합본 (최근 7일)
요청 키워드: 주간 보고서 / 주간 합본 / 7일 보고서 / 주간 광고보고서 / 이번주 보고서

```bash
python3 build_weekly_report.py            # 어제 KST 종료 기준 7일
python3 build_weekly_report.py 2026-04-29 # 그 날 종료 기준 7일
```

출력: `<WORKSPACE>/광고주간보고서_대표용_YYYY-MM-DD~YYYY-MM-DD.html` (~20KB)

## 데이터 소스

- 시트: `1Yuw_8we4nEzL1nslHI66LHBBE_uWc-ErALzhn2vvLGI`
  - `01_일일수집로그` gid=1416410435 — A 광고 데이터
  - `02_전환수집로그` gid=1885328367 — A 매출 데이터
  - `상품매핑` gid=1248602534 — adId → 상품명/URL
- 네이버 A: customer_id=1728536 (스마트스토어)
- 네이버 B: customer_id=1558945 (자사몰 파워링크)
- Google Ads: customer=8156547444 / MCC=5192219711

자격증명은 환경변수 (`.secrets.env`) 또는 GitHub Secrets로 주입. **build_report.py에 평문 키 없음** (2026-05-08 정정).

필요 환경변수: `A_KEY, A_SEC, B_KEY, B_SEC, G_DEV, G_OAUTH_C, G_OAUTH_S, G_REFRESH, GITHUB_PAT, GITHUB_OWNER, GITHUB_REPO`

## 동작 흐름 — 일간

1. 어제 KST 또는 argv[1]
2. **A 데이터** = **API 직접 호출** (StatReport AD + AD_CONVERSION). 시트 캐시 안 씀 (시점 차이 제거)
3. **ADVoost 합산** = `애드부스트/result.csv` 또는 `scripts/advoost.csv` read → A_total cost/imp/clk에 합산. 차장님이 평일에 ADVoost 콘솔에서 받은 CSV를 폴더에 올리면 자동 반영. 없으면 ADVoost 미반영 ("CSV 미입력" stderr 표시)
4. **B 데이터** = 네이버 B API StatReport AD + AD_CONVERSION + 광고그룹별 광고 헤드라인/finalUrl 매핑
5. **G 데이터** = Google Ads v20 GAQL 5종 (캠페인 / 진짜매출 / 검색어 TOP10 / 디바이스 / 8일추이)
6. **HTML 빌드** — 04-27 풀빌드 템플릿 + 1차시안/참고 영역 자동 삭제 + const D 교체 + JS overlay 주입 (B 광고그룹 트리: 헤드라인+클릭 가능 finalUrl)
7. **GitHub Pages 자동 push** — `ceo-report/latest.html` (덮어씀) + `ceo-report/{날짜}.html` (백업)

## 동작 흐름 — 주간 (7일)

1. END=어제 KST (또는 argv[1]), START=END-6
2. **A 데이터** = 7일치 시트 (중복 dedupe + 시트 결측일 API 병렬 fallback)
3. **B 데이터** = 14개 StatReport (7일 × AD/AD_CONVERSION) **ThreadPoolExecutor 병렬** (3분 → 30초)
4. **G 데이터** = GAQL 단일 호출 (BETWEEN START AND END)
5. **HTML 빌드** — 단일 페이지: 7일 KPI + 일별 추이 표 + 베스트/워스트 일자 + A/B/G 매체별 7일 합계

## 비전환 광고비 정책

광고그룹 단위로 묶어 매출 0인 그룹의 광고비만 합산 (상품 단위 X).

## 시트 중복 dedupe

01_일일수집로그 / 02_전환수집로그 일부 날짜 (특히 04-19~04-23)에 5x 중복 누적 이슈. 주간 빌드에서 (수집일, 캠페인, 광고그룹, 상품ID) 키 단위 첫 행만 유지.

## ADVoost (애드부스트) 운영 정책 — 2026-05-08 확정

- **API 미제공**. 차장님이 ADVoost 콘솔에서 result.csv 다운로드 → 평일 기준 폴더에 업로드
- 폴더: `C:\Users\Administrator\Documents\Claude\Projects\단순등록자동화\애드부스트\result.csv`
- GitHub Actions용 미러: `scripts/advoost.csv` (차장님이 매일 GitHub에도 push 필요)
- CSV 컬럼: 총비용 / 노출수 / 클릭수 등 17개. 헤더명 기준 매핑 (인덱스 X)
- 합산 결과 = 콘솔 소진액(VAT 포함)과 24원 차이로 일치 검증됨 (2026-05-08)

## GitHub Actions 자동화

- 워크플로우: `.github/workflows/daily.yml`
- cron: `0 0 * * *` (UTC 00:00 = KST 09:00). 정시 부하로 자주 5~30분 지연 또는 첫날 skip 가능
- 권장 cron: `47 23 * * *` (KST 08:47, 안정)
- 환경변수: GitHub Secrets에 키 8개 등록 필요
- 결과 URL (고정): https://sangjunepark-beep.github.io/hanasignmall-ad-reports/ceo-report/latest.html

## 알려진 제약

- B AD_CONVERSION은 `purchase` 액션만 매출로 잡음 (`add_to_cart`는 추정매출이라 제외)
- Google Ads "구매" 액션 매출 0이면 GTM 결제완료 트리거 점검 필요 (코드는 정상)
- 일간: 04-27 템플릿의 키워드 TOP 20 / 시간대별 클릭은 AD_DETAIL 미연동 — 04-27 정적값 그대로 표시
- 네이버 ADVoost는 별도 customer ID(1328585, 1061674). A 키로 권한 없음 → CSV 수동 입력만 가능

## 의존성

- python3 표준 라이브러리만 (urllib/json/csv/hmac/hashlib/base64/concurrent.futures)
- 일간 빌드는 `네이버광고_1차보고대시보드_2026-04-27.html` (또는 `template_2026-04-27.html`) 템플릿 필요
- 주간 빌드는 템플릿 의존 없음
