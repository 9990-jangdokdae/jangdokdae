# 백엔드 아키텍처 & 폴더 구조

## 전체 아키텍처

```
클라이언트 (Next.js, 3000)
        │
        │  HTTP 요청 (JSON + JWT 쿠키)
        ▼
FastAPI 서버 (8000)
        │
        ├── api/          라우터: URL → 함수 연결
        ├── dependencies/ 인증 검증 (JWT 쿠키 확인)
        ├── schemas/      요청·응답 데이터 검증
        ├── services/     비즈니스 로직 처리
        └── models/       DB 테이블 정의
        │
        ▼
Neon PostgreSQL (클라우드)
```

---

## 기술 스택

| 분류 | 기술 | 용도 |
|------|------|------|
| 웹 프레임워크 | FastAPI | HTTP API 서버 |
| 언어 | Python 3.12 | - |
| DB | PostgreSQL (Neon) | 사용자·뉴스·기업 데이터 저장 |
| ORM | SQLAlchemy 2.0 (async) | Python ↔ DB 연결 |
| 벡터 검색 | pgvector | 뉴스 임베딩 유사도 검색 |
| 인증 | OAuth 2.0 + JWT | 카카오·구글 소셜 로그인 |
| LLM | Gemini (Google) | 뉴스 엔티티 추출 |
| 임베딩 | ko-sroberta-multitask | 한국어 뉴스 벡터화 |
| 클러스터링 | UMAP + HDBSCAN | 유사 뉴스 그룹화 |

---

## 폴더 구조

```
jangdokdae-server/
├── .env                         # 환경변수 (Git 제외)
├── .env.example                 # 환경변수 템플릿
└── apps/
    ├── main.py                  # ★ FastAPI 앱 시작점
    │                              라우터 등록, CORS 설정
    │
    ├── scripts/                 # 실행 스크립트
    │   ├── collector_pipeline.py  # 뉴스 수집 파이프라인 메인 실행 파일
    │   ├── evaluate_clusters.py   # 클러스터 품질 평가
    │   ├── visualize_clusters.py  # 클러스터 시각화
    │   └── db/
    │       ├── create_table.sql   # DB 테이블 생성 SQL
    │       ├── drop_table.sql     # 테이블 삭제 SQL
    │       └── delete.sql         # 데이터 삭제 SQL
    │
    ├── data/                    # 파이프라인 출력 데이터
    │   └── {YYYYMMDD_HHMMSS}/   # 실행 날짜별 결과 폴더
    │       ├── news_crawled.json
    │       └── clusters_final.json
    │
    └── src/
        │
        ├── api/                 # ★ HTTP 엔드포인트 (라우터 레이어)
        │   │                      URL 경로와 처리 함수를 연결하는 역할
        │   ├── auth.py          # /auth/* 엔드포인트
        │   │                      로그인, 콜백, 내 정보, 로그아웃
        │   └── users.py         # /user/* 엔드포인트
        │                          섹터 목록, 관심 프로필 조회·수정
        │
        ├── config/              # ★ 앱 전반 설정값
        │   ├── database.py      # DB 연결 설정
        │   │                      - 파이프라인용: NullPool (매번 새 연결)
        │   │                      - API용: 커넥션 풀 (pool_pre_ping 포함)
        │   ├── sectors.py       # 고정 섹터 15개 목록
        │   │                      API와 프론트 모두 이 파일을 참조
        │   ├── paths.py         # 프로젝트 경로 상수 (DATA_DIR 등)
        │   ├── dart_accounts.py # DART 재무제표 계정명 매핑
        │   └── macro_tickers.py # Yahoo Finance 거시지표 티커 목록
        │
        ├── dependencies/        # ★ FastAPI 공통 의존성
        │   └── auth.py          # get_current_user()
        │                          JWT 쿠키 검증 → User 객체 반환
        │                          인증이 필요한 모든 엔드포인트에서 재사용
        │
        ├── models/              # ★ SQLAlchemy ORM (DB 테이블 정의)
        │   │                      Python 클래스 = DB 테이블
        │   ├── base.py          # DeclarativeBase 베이스 클래스
        │   ├── user.py          # users 테이블
        │   │                      id, provider, provider_id, nickname,
        │   │                      interest_sectors[], interest_companies[]
        │   ├── article.py       # articles 테이블 (뉴스 원문)
        │   ├── cluster.py       # clusters, cluster_articles,
        │   │                      entity_extraction 테이블
        │   └── company.py       # company_master,
        │                          dart_financial_statements,
        │                          dart_document 테이블
        │
        ├── schemas/             # ★ Pydantic 스키마 (API 입출력 형태)
        │   │                      요청 데이터 검증 + 응답 데이터 직렬화
        │   └── users.py         # UserResponse       (응답: 사용자 정보)
        │                          InterestProfileBody (요청: 프로필 저장)
        │                          InterestProfileResponse (응답: 프로필 조회)
        │
        ├── services/            # ★ 비즈니스 로직
        │   │
        │   ├── auth/            # 인증 서비스
        │   │   ├── jwt.py       # JWT 토큰 생성 / 검증
        │   │   └── oauth.py     # 카카오·구글 OAuth API 호출
        │   │                      인가 URL 생성, 사용자 정보 조회
        │   │
        │   ├── collector/       # 외부 데이터 수집 (파이프라인용)
        │   │   ├── news_collector.py           # 네이버 금융 뉴스 크롤링
        │   │   ├── dart_collector.py           # DART 공시·재무제표 수집
        │   │   ├── krx_collector.py            # KRX 주가 데이터 수집
        │   │   ├── macro_collector.py          # Yahoo Finance 거시지표
        │   │   ├── company_master_collector.py # DART-KRX 기업 마스터 구축
        │   │   └── company_collector.py        # 기업 데이터 통합 수집
        │   │
        │   ├── preprocessor/    # 수집 데이터 전처리 (파이프라인용)
        │   │   ├── news_preprocessor.py        # 노이즈 제거, 중복 제거
        │   │   ├── dart_preprocessor.py        # 재무제표 정규화·피벗, 섹션 파싱
        │   │   │                                 pivot_financial_to_wide()로
        │   │   │                                 long→wide 변환 담당
        │   │   └── company_preprocessor.py     # 컬럼명 영문화, 날짜 통일
        │   │
        │   ├── embedder/        # 임베딩·클러스터링 (파이프라인용)
        │   │   ├── news_embedder.py            # ko-sroberta로 뉴스 벡터화
        │   │   └── news_clusterer.py           # UMAP + HDBSCAN 클러스터링
        │   │
        │   ├── extractor/       # LLM 정보 추출 (파이프라인용)
        │   │   └── entity_extractor.py         # Gemini로 기업·섹터·키워드 추출
        │   │
        │   └── contents/        # 콘텐츠 생성 (미구현)
        │
        ├── repositories/        # DB 직접 조작 (파이프라인용, Repository 패턴)
        │   └── pipeline_store.py  # 파이프라인 각 단계 결과 DB 저장
        │                            생성 시 NewsEmbedder 주입 필요
        │
        ├── exceptions/          # 커스텀 예외 클래스 (파이프라인용)
        │   ├── base.py          # PipelineError 베이스, ErrorCode enum
        │   ├── collector_exceptions.py
        │   ├── processing_exceptions.py
        │   ├── extraction_exceptions.py
        │   ├── pipeline_exceptions.py
        │   └── company_exceptions.py
        │
        ├── utils/               # 공통 유틸리티 함수
        │   ├── date_utils.py    # 날짜 파싱·변환
        │   ├── http_utils.py    # HTTP 재시도 데코레이터
        │   ├── json_utils.py    # JSON 저장·로드
        │   └── list_utils.py    # 리스트 유틸 (unique_by 등)
        │
        └── prompts/             # LLM 프롬프트 템플릿
            └── entity_extraction.txt  # 엔티티 추출 프롬프트
```

---

## 레이어별 역할 요약

| 폴더 | 한 줄 역할 | 주요 질문 |
|------|-----------|----------|
| `api/` | URL ↔ 함수 연결 | "어떤 URL로 들어오면 무엇을 처리하나?" |
| `schemas/` | 요청·응답 형태 정의 | "API가 무엇을 받고 무엇을 돌려주나?" |
| `models/` | DB 테이블 구조 | "DB에 어떻게 저장되나?" |
| `dependencies/` | 공통 인증·검증 | "로그인 확인은 어떻게 하나?" |
| `services/auth/` | JWT·OAuth 처리 | "토큰 생성·검증, 소셜 로그인 처리" |
| `services/collector~extractor/` | 뉴스 파이프라인 | "뉴스를 어떻게 수집·분석하나?" |
| `repositories/` | DB 읽기·쓰기 (Repository 패턴) | "파이프라인 결과를 DB에 어떻게 저장하나?" |
| `config/` | 환경·DB·상수 설정 | "DB 연결, 섹터 목록은 어디서?" |
| `utils/` | 재사용 유틸 함수 | "자주 쓰는 도구 함수들" |

---

## 요청 처리 흐름 예시

`GET /user/profile` 요청이 처리되는 순서:

```
1. 요청 도착
        ↓
2. api/users.py  get_profile()
        ↓
3. dependencies/auth.py  get_current_user()
   - 쿠키에서 access_token 읽기
   - services/auth/jwt.py  decode_access_token()
   - DB에서 User 조회
        ↓
4. models/user.py  User 객체
        ↓
5. schemas/users.py  InterestProfileResponse 직렬화
        ↓
6. JSON 응답 반환
   { "sectors": [...], "companies": [...] }
```

---

## 서버 실행

```bash
cd jangdokdae-server

# 환경변수 설정 (최초 1회)
cp .env.example .env
# .env 파일 편집하여 API 키 입력

# 가상환경 활성화
source .venv/bin/activate

# 서버 실행
uvicorn apps.main:app --reload --port 8000
```

Swagger UI: http://localhost:8000/docs
