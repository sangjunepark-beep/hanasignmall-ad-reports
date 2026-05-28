---
name: weekly-monthly-report
description: "하나사인몰 주간·월간 광고↔매출 통합 비교 보고서를 생성하고 GitHub Pages에 배포하는 스킬. ceo-report 일별 아카이브 + 업체계약현황 시트로 다크모드 인터랙티브 HTML 만들기. '주간 보고서', '월간 보고서', '광고 매출 비교', '주월간 비교', 'weekly-product 갱신', '주차별 매출', '주차별 광고', '실제 매출 보고서' 요청 시 반드시 이 스킬을 사용하세요."
---

# 주간·월간 광고↔매출 비교 보고서

하나사인몰 광고(네이버 검색광고)와 실제 매출(CS·영업·온라인)을 같은 주차에 묶어 보여주는 인터랙티브 다크 보고서.

## 산출물
- GitHub Pages 고정: https://sangjunepark-beep.github.io/hanasignmall-ad-reports/weekly-product/latest.html
- 스냅샷: weekly-product/YYYY-MM-DD.html
- 로컬: C:\Users\Administrator\Documents\Claude\Projects\단순등록자동화\주월보고서/

## 4섹션 구조
1. **주차별 한눈에** — 카드 5장(주차+전체). 카드 한 장에 광고(클릭/광고비/기여구매) + 매출(CS/영업/스마트스토어/자사몰/오픈마켓 가로 막대) 같이
2. **통합 비교 표** — 숫자 클릭 → 키워드 팝업 (셀 우측에 뜸·드래그·X 닫기·다중)
3. **광고 상위 30** — 탭 전환. 클릭/장바구니/직접/간접 4종
4. **매출 채널별 상위 키워드** — 전체 기간

## 데이터 처리 규칙

### 주차 = 영업일(월~금) + 공휴일 제외
```python
WEEKS = [
    ('1주차', '5/1 ~ 5/8', 4, ['2026-05-01','2026-05-04','2026-05-06','2026-05-07','2026-05-08']),
    # 5/5(어린이날) 제외
    ('2주차', '5/11 ~ 5/15', 5, [...]),
    ('3주차', '5/18 ~ 5/22', 5, [...]),
    ('4주차', '5/25 ~ 5/27', 2, ['2026-05-26','2026-05-27']),
    # 5/25(부처님오신날 대체) 제외
]
HOLIDAYS = {'1주차': '5/1 근로자의날 · 5/5 어린이날', '4주차': '5/25 부처님오신날 대체'}
```

매월 다시 만들 때 공휴일 빼고 일자 리스트 재구성. 카드 헤더에 빨간색(#f87171) 휴일 표기.

### 채널 분류 (진행자 D열 → 분류)
- `(영호)` 포함 → **영업** (광고 무관)
- `사인몰(`, `하나몰(` 시작 → **CS**
- 나머지는 진행자 그대로 → 채널명

### 채널 그룹 (스마트스토어 5개 셀러 통합 — 중요)
```python
CHANNEL_GROUPS = {
    'CS': ['CS'], '영업': ['영업'],
    '스마트스토어': ['스마트스토어','네이버페이','하나몰','더바른사인','로켓출력공장'],
    '자사몰': ['고도몰5','신규몰'],  # com·kr
    '오픈마켓': ['쿠팡(신)','G마켓','11번가','옥션'],
}
```
스마트스토어는 5/17 즈음부터 셀러별 진행자로 분리 입력됨. 합산 안 하면 폭락처럼 보임.

## 입력 데이터

1. **광고 일별 아카이브** (GitHub API contents 또는 raw):
   - `sangjunepark-beep/hanasignmall-ad-reports/ceo-report/YYYY-MM-DD.html`
   - 각 파일 `<script>` 안 `const D = {...}` JSON 추출
   - 핵심 필드: `all_rows`(pid, clk, imp, cost, name, url), `cart`/`buy`(cart_n, d_buy_n, i_buy_n, store)

2. **매출 시트** — 사용자 업로드 xlsx:
   - 시트명: `업체계약현황`
   - 컬럼: 년(0), 월(1), 일(2), 진행자(3), 품명(12), 수량(16), 총금액(17)

## 실행 흐름

1. 사용자에게 매출 xlsx 업로드 요청 (또는 최신 파일 활용)
2. ceo-report 아카이브 일괄 다운로드 (대상 기간 모든 영업일)
3. 광고/매출 집계 (영업일 기준, 공휴일 제외)
4. 키워드 추출 (`scripts/keyword_func.py` 활용 — 카테고리+수식어+사이즈)
5. 다크 HTML 빌드 (`scripts/build_report.py`)
6. GitHub API PUT으로 `weekly-product/latest.html` + 날짜 스냅샷 동시 푸시
7. Pages 빌드 트리거 (errored 자주 발생 → 재시도)

## 토큰

GitHub PAT는 `C:\Users\Administrator\Documents\Claude\Projects\단순등록자동화\ceo-ad-report\.secrets.env`의 `GITHUB_PAT` 사용. 만료 시 401 → 사용자에게 재발급 요청 (평문 노출 금지, .secrets.env 직접 수정).

## 인터랙션 (팝업)

- 클릭 가능 셀: `.clk-cell` + `data-week/data-type/data-ch`
- 위치: `getBoundingClientRect()` 셀 우측 12px. 화면 우측 부족 시 좌측, 그래도 안 되면 셀 아래
- 다중·드래그·X 닫기
- POPUP_DATA JSON 인라인:
```javascript
{
  '1주차': {
    range: '5/1 ~ 5/8',
    ad_click: [[키워드, 클릭수], ...],
    sales: {'CS': [[키워드, 건수, 금액], ...], ..., '전체': [...]}
  }, ...
}
```

## 검증 체크리스트

- [ ] 광고 합산 = `const D.total`과 일치 (clk/imp/cost 차이 0)
- [ ] 매출 = xlsx 일자별 raw 합과 일치
- [ ] 공휴일 날짜 매출 0건
- [ ] 스마트스토어 5개 셀러 합산 — 폭락 안 보이는지
- [ ] 영문 ID(nad-...) → "상품 #숫자"로 변환
- [ ] 팝업이 클릭한 셀 옆에 뜨는지

## 알려진 이슈

1. **직접구매 d_buy_n = 0 (5/7 이후)**: 원본 D.buy_total.d_n도 0. 수집 단계 직접/간접 분리 버그. 보고서엔 합산 노출, 별건 보고
2. **상품명 매핑 안 됨** — nad-a001-02-... 광고는 "상품 #(뒤9자리)"로 변환
3. **GitHub Pages 빌드 errored** 자주 → `POST /pages/builds`로 재트리거

## 자동화 (미구현)

매주 월요일 또는 매월 1일 GitHub Actions로 자동 빌드+푸시 검토.

## 관련 메모
- [project_20260528_weekly_monthly_report.md]
- [reference_channel_ad_source_mapping.md]
- [reference_sales_sheet.md]
- [project_20260528_actions_cron_target_8am.md]
- [feedback_html_js_overlay_verification.md]
