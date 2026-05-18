# Analyzer 통합 가이드

## 개요

Analyzer는 수집된 뉴스 클러스터를 바탕으로,

- 대표 기사 중심의 분석 본문 생성
- 관련 기업 주가 / 시장 지표 보강
- 기사 숫자 기반 비교 포인트 생성

을 담당하는 모듈입니다.

현재 방향은 다음과 같습니다.

- 왼쪽 본문: 이슈를 3~4개 관점으로 풀어주는 메인 분석
- 오른쪽 사이드바: 관련 기업 주가, 기사 숫자 기반 비교 포인트, 시장/섹터 한마디

즉 본문은 해석 중심, 사이드바는 빠르게 훑는 근거와 맥락 중심으로 역할을 나눕니다.

---

## 현재 위치

서버 기준 주요 파일:

```text
apps/src/api/analyzer.py
apps/src/models/analyzer_dto.py
apps/src/services/analyzer/analyzer_service.py
apps/src/services/analyzer/db_cluster_loader.py
apps/src/services/analyzer/issue_based_analyzer.py
apps/src/services/analyzer/workflow.py
```

역할 요약:

- `api/analyzer.py`
  - analyzer API 엔드포인트 제공
- `models/analyzer_dto.py`
  - analyzer 요청 / 응답 스키마 정의
- `analyzer_service.py`
  - analyzer 진입 서비스
- `db_cluster_loader.py`
  - DB에서 클러스터 / 기사 / 기업 / 시장 데이터 로드
- `issue_based_analyzer.py`
  - LLM 분석 및 사이드바 데이터 조립
- `workflow.py`
  - cluster payload -> representative -> request -> analyze 흐름 관리

---

## 데이터 흐름

현재 analyzer 흐름은 아래와 같습니다.

```text
clusters / cluster_articles / articles / entity_extraction / company_master / dart_financial_statements
        ↓
db_cluster_loader.py
        ↓
representative 기사 선택
        ↓
AnalysisRequest 변환
        ↓
LLM 분석 (analysis_sections 생성)
        ↓
사이드바용 정형 데이터 조립
        ↓
AnalysisResponse 반환
```

대표 기사 선택 기준:

- `cluster_articles.similarity_to_centroid DESC`
- 즉 centroid와 가장 유사한 기사를 대표 기사로 사용

---

## 분석 본문 원칙

메인 분석 본문은 이슈별로 맞는 관점 제목을 잡고, 3~4개 이내로 구성합니다.

예:

- 실적 기사
  - 주요 실적 변화
  - 다음 분기와 성장 전략
  - 주의할 점
- 시장 급락 기사
  - 시장 변동성이 커진 배경
  - 수급이 보여준 시각 차이
  - 주의할 점

프롬프트 규칙:

- 분석 섹션은 3~4개로 나눔
- 번호 없음
- 직접 투자판단 금지
- 섹션 간 역할 분리
- 중복 서술 금지

중요:

- 설명문 fallback은 사용하지 않음
- LLM이 만든 `analysis_sections`를 그대로 사용
- 코드에서는 중복 제거 / 형식 정리만 수행

---

## 사이드바 원칙

사이드바는 세 블록으로 구성합니다.

1. 관련 기업 주가
2. 기사 숫자 기반 비교 포인트
3. 시장/섹터 한마디 인사이트

### 1. 관련 기업 주가

관련 기업 카드에는:

- 기업명
- 티커
- 기업 정체성(예: 메모리 반도체, 완성차)
- 현재가
- 등락률

를 표시합니다.

여기서 주가 / 등락률은 `pykrx`를 통해 보강합니다.

### 2. 기사 숫자 기반 비교 포인트

지표 카드는:

- 기사에서 직접 언급한 핵심 숫자를 본값으로 사용
- 가능한 경우에만 비교 해석을 파란 문구로 추가

예:

- `5.26% → 9.10%`
  - `+3.84%p 변화`
- `1개 → 5개`
  - `약 5.0배 확대`
- `1분기 영업이익 1조6737억원`
  - `전년 동기 대비 +32.9%`

비교 문구는 다음 데이터와 연결될 수 있습니다.

- 기사 본문 자체 비교
- `pykrx` 시세 데이터
- DART 재무 데이터

원칙:

- 모든 카드에 억지 비교를 붙이지 않음
- 비교가 자연스럽고 근거가 있을 때만 사용

### 3. 시장/섹터 한마디 인사이트

이 블록은 해당 이슈를 읽고 난 뒤,

- 이 섹터를 어떤 시선으로 봐야 하는지
- 앞으로 뭘 같이 봐야 하는지

를 한 줄로 정리하는 영역입니다.

너무 상투적이지 않게, 기사 맥락과 연결되는 문장으로 정리하는 방향을 사용합니다.

---

## `pykrx` 사용 방식

`pykrx`의 역할은 기사 해석 본문 생성이 아니라,

- 관련 기업 현재가 / 등락률
- 시장 지표

같은 정형 데이터를 보강하는 것입니다.

현재 원칙:

- 분석 결과는 Neon DB `article_analysis` 테이블에 저장형으로 관리
- Gemini 분석은 저장 단계에서만 수행
- 메인 분석 본문은 저장된 결과를 조회해 반환
- 사이드바 숫자 데이터는 조회 시점 기준으로 다시 계산해 반환
- 새 `issue_docent`가 저장될 때 같은 `cluster_id`의 analyzer 결과도 함께 저장

현재 관련 endpoint:

- `GET /api/v1/analysis/sidebar-context/{cluster_id}`
- `GET /api/v1/analysis/detail/{cluster_id}`
- `POST /api/v1/analysis/persist/{cluster_id}`

역할:

- `sidebar-context/{cluster_id}`
  - 저장된 analyzer 결과를 기준으로 하되, 주가/등락률/시장 지표 같은 숫자 데이터는 조회 시점 기준으로 다시 계산해 반환
- `detail/{cluster_id}`
  - 저장된 analyzer 결과만 조회해 반환
- `persist/{cluster_id}`
  - Gemini 분석을 수행하고 `article_analysis` 테이블에 저장

---

## API

현재 analyzer 관련 API:

- `GET /api/v1/analysis/health`
- `POST /api/v1/analysis/analyze-cluster`
- `POST /api/v1/analysis/analyze-clusters`
- `POST /api/v1/analysis/persist/{cluster_id}`
- `GET /api/v1/analysis/detail/{cluster_id}`
- `GET /api/v1/analysis/sidebar-context/{cluster_id}`

역할:

- `analyze-cluster`
  - cluster payload 또는 단일 cluster 분석
- `analyze-clusters`
  - batch 분석
- `persist/{cluster_id}`
  - cluster_id 기준으로 Gemini 분석을 실행하고 결과를 DB에 저장
- `detail/{cluster_id}`
  - 상세 페이지에서 저장된 메인 분석 섹션을 가져올 때 사용
- `sidebar-context/{cluster_id}`
  - 상세 페이지에서 실시간 수치가 반영된 사이드바 데이터를 가져올 때 사용

자동 저장 기준:

- `issue_docent` 생성 서비스가 `issue_docent`를 저장한 직후
- 같은 `cluster_id`로 analyzer를 실행
- 결과를 `article_analysis` 테이블에 함께 저장

---

## 프론트 연동 기준

프론트는 `jangdokdae-client`에서 연결합니다.

현재 상세 연동 흐름은 아래와 같습니다.

```text
GET /api/v1/contents/issue-docent/{id}
        ↓
요약 본문 / 용어 / 퀴즈 / cluster_id 확보
        ↓
GET /api/v1/analysis/detail/{cluster_id}
        ↓
analysis_sections 렌더링
        ↓
GET /api/v1/analysis/sidebar-context/{cluster_id}
        ↓
실시간 관련 기업 / 시장 지표 / 지표 카드 조회
```

저장 시점은 프론트 상세 진입 시점이 아니라, `issue_docent` 생성 시점입니다.

즉 요약/퀴즈는 `issue-docent`,
분석 본문과 사이드바는 `analyzer`가 맡고,
프론트 상세 페이지에서 `cluster_id` 기준으로 둘을 붙이는 구조입니다.

상세 페이지 기준 구조:

- 왼쪽:
  - 번역 본문
  - analyzer `analysis_sections`
  - 퀴즈
- 오른쪽:
  - `sidebar_context.related_companies`
  - `sidebar_context.key_metrics`
  - `sidebar_context.related_markets`

즉 analyzer는 번역 / 퀴즈를 대체하지 않고,
상세 페이지에 추가되는 분석 레이어라고 보면 됩니다.

---

## 현재 설계 원칙 요약

- 대표 기사 기준으로 분석한다
- 본문 분석은 3~4개 관점으로 나눈다
- 번호형 문단은 쓰지 않는다
- 직접 투자판단은 하지 않는다
- 기사 숫자를 우선 보여주고, 비교는 필요한 경우에만 붙인다
- 설명문 / 지표 카드 fallback은 사용하지 않는다
- 없으면 안 보여주고, 보이는 것은 기사나 근거 데이터에서 직접 나온 것만 쓴다
- 프론트 상세는 `cluster_id`를 기준으로 analyzer와 연결한다

---

## 남아 있는 정리 포인트

현재는 메인 브랜치 병합을 위한 1차 이식 상태이며, 아래는 후속 정리 후보입니다.

- `config/cofig.py` 네이밍 정리
- `models/analyzer_dto.py`를 `schemas`로 옮길지 검토
- `db_cluster_loader.py`를 `repositories` 성격으로 분리할지 검토
- analyzer API 응답을 `issue-readings` 상세 응답과 어떻게 합칠지 정리

즉 현재 상태는:

- 기능적으로는 연결 가능
- 구조적으로는 1차 병합 가능
- 메인 스타일에 맞춘 추가 리팩터링 여지는 남아 있음
