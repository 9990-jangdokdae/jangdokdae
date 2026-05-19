# 데이터 수집 파이프라인

## 개요

네이버 금융 뉴스를 수집·분석해 클러스터(이슈 묶음)와 기업·섹터 정보를 DB에 저장하는 8단계 파이프라인입니다.

---

## 실행 방법

```bash
cd jangdokdae-server

# 기본 실행 (오늘 날짜, 최대 50개 기사)
uv run python -m apps.scripts.collector_pipeline

# 날짜 지정
uv run python -m apps.scripts.collector_pipeline --date 20260514

# 수집 기사 수 조정
uv run python -m apps.scripts.collector_pipeline --date 20260514 --limit 100
```

> ⚠️ **KRX 장중 실행 금지**: KRX 데이터는 15:30 이후에 수집하세요.

---

## 8단계 흐름도

```
① 뉴스 수집    ② 전처리      ③ 임베딩       ④ 클러스터링
  [필수 중단]    [필수 중단]   [필수 중단]     [필수 중단]
     │              │              │               │
     ▼              ▼              ▼               ▼
뉴스 크롤링  → 노이즈 제거  → 벡터 변환  → 유사 뉴스 묶기
     │
     ▼ DB 저장: articles

⑤ 엔티티 추출  ⑥ 기업 수집   ⑦ 기업 전처리  ⑧ 거시지표
   [계속 진행]   [계속 진행]   [계속 진행]    [계속 진행]
     │               │              │               │
     ▼               ▼              ▼               ▼
기업·섹터·키워드  KRX·DART    데이터 정제    환율·지수·금
추출 (Gemini)    데이터 수집   + DB 저장       수집

DB 저장: entity_extraction    company_master, dart_*
DB 저장: clusters, cluster_articles
```

**필수 중단**: 해당 단계 실패 시 파이프라인 전체 중단
**계속 진행**: 실패해도 로그만 남기고 다음 단계 계속 실행

---

## 단계별 상세 설명

| 단계 | 파일 | 입력 | 출력 | 필수 환경변수 |
|------|------|------|------|--------------|
| ① 뉴스 수집 | `collector/news_collector.py` | 날짜, 최대 기사 수 | `news_crawled.json` | - |
| ② 전처리 | `preprocessor/news_preprocessor.py` | 수집 기사 | 정제된 기사 + DB 저장 | - |
| ③ 임베딩 | `embedder/news_embedder.py` | 기사 본문 | 768차원 벡터 | `EMBED_MODEL` |
| ④ 클러스터링 | `embedder/news_clusterer.py` | 임베딩 벡터 | `news_clusters.json` + DB | - |
| ⑤ 엔티티 추출 | `extractor/entity_extractor.py` | 클러스터 기사 | 기업·섹터·키워드 + DB | `LLM_MODEL` + `GOOGLE_APPLICATION_CREDENTIALS` |
| ⑥ 기업 수집 | `collector/company_collector.py` | 기업명 목록 | KRX 시세, DART 공시·재무 | `OPENDART_API_KEY` |
| ⑦ 기업 전처리 | `preprocessor/company_preprocessor.py` | 원시 기업 데이터 | 정제 + DB 저장 | - |

> **⑦ DB 저장 상세**: `repositories/pipeline_store.py`의 `PipelineStore`가 저장을 담당합니다.
> - 재무제표 long→wide 피벗: `preprocessor/dart_preprocessor.py`의 `pivot_financial_to_wide()` 호출
> - 사업보고서 임베딩: 파이프라인 시작 시 생성된 `NewsEmbedder` 인스턴스를 `PipelineStore(embedder=...)` 형태로 주입받아 사용
| ⑧ 거시지표 | `collector/macro_collector.py` | - | `clusters_final.json` | - |

---

## 환경변수 설정

```bash
# .env 파일에 추가

# ③ 임베딩 모델 (변경 금지 — 기존 벡터 무효화됨)
EMBED_MODEL=jhgan/ko-sroberta-multitask

# ⑤ Gemini LLM — Vertex AI (Google Cloud 크레딧 적용)
# 사전 조건: Google Cloud 서비스 계정 키 파일(JSON) 발급 필요
GOOGLE_APPLICATION_CREDENTIALS=credentials/vertex_key.json
GOOGLE_CLOUD_PROJECT=<Google Cloud 프로젝트 ID>
GOOGLE_CLOUD_LOCATION=asia-northeast3
VERTEX_MODEL=gemini-2.5-flash
LLM_MODEL=gemini-2.5-flash

# ⑥ DART 공시 API
OPENDART_API_KEY=<DART 오픈 API에서 발급>

# ⑥ KRX (선택, 없으면 기본 OHLCV만 수집)
KRX_ID=<KRX 로그인 ID>
KRX_PW=<KRX 로그인 비밀번호>
```

---

## 출력 파일 구조

파이프라인 실행 결과는 `apps/data/` 하위에 실행 시각별 폴더로 저장됩니다.

```
apps/data/
└── 20260514_153000/           # YYYYMMDD_HHMMSS
    ├── news_crawled.json       # ① 수집 원본
    ├── news_clusters.json      # ④ 클러스터링 결과
    ├── clusters_extracted.json # ⑤ 엔티티 추출 결과
    └── clusters_final.json     # ⑧ 최종 결과 (거시지표 포함)
```

---

## DB 테이블 저장 시점

| 단계 | 저장 테이블 | 설명 |
|------|------------|------|
| ② 전처리 | `articles` | 뉴스 원문 저장 |
| ④ 클러스터링 | `clusters` | 클러스터 메타 (날짜, 크기) |
| ④ 클러스터링 | `cluster_articles` | 클러스터-기사 연결 |
| ⑤ 엔티티 추출 | `entity_extraction` | 기업명, 섹터, 키워드 |
| ⑦ 기업 전처리 | `company_master` | 기업 기본정보 (KRX·DART) |
| ⑦ 기업 전처리 | `dart_financial_statements` | 재무제표 |
| ⑦ 기업 전처리 | `dart_document` | 사업보고서 섹션 (pgvector 임베딩 포함) |

---

## 주의사항

| 항목 | 내용 |
|------|------|
| KRX 실행 시간 | 장중(9:00~15:30) 실행 금지. 데이터 오류 발생 가능 |
| 임베딩 모델 변경 금지 | `EMBED_MODEL` 변경 시 기존 벡터 DB가 무효화됨. 변경 시 전체 재임베딩 필요 |
| LLM 검증 | 전체 실행 전 소량 샘플로 먼저 검증 (`--limit 5` 로 테스트) |
| LLM 원문 외 추가 금지 | Gemini가 뉴스에 없는 내용을 생성하지 않도록 프롬프트가 설계됨 |
