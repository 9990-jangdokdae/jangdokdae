# 🏺 장독대

> 주린이를 위한 AI 주식 뉴스 큐레이션 · 학습 서비스

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Neon-4169E1?logo=postgresql&logoColor=white)](https://neon.tech)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.3-1C3C3C?logo=langchain&logoColor=white)](https://langchain.com)

매일 쏟아지는 금융 뉴스·재무제표·DART 공시를 자동 수집·분석하고, 초보자도 이해할 수 있는 학습 콘텐츠와 퀴즈로 변환합니다.

---

## 기술 스택

| 분류 | 기술 |
|------|------|
| 백엔드 | Python 3.12, FastAPI, SQLAlchemy 2.0 (async) |
| DB | PostgreSQL (Neon) + pgvector |
| 인증 | 카카오·구글 OAuth 2.0, JWT + Refresh Token Rotation |
| LLM | Gemini (Google AI Studio / Vertex AI), LangGraph |
| 임베딩·클러스터링 | ko-sroberta-multitask, UMAP + HDBSCAN |
| 패키지 관리 | uv |

---

## 시작하기

```bash
# 1. 클론
git clone https://github.com/9990-jangdokdae/jangdokdae-server.git
cd jangdokdae-server

# 2. 환경변수
cp .env.example .env  # .env 파일에 값 입력

# 3. 의존성 설치
uv sync

# 4. DB 테이블 생성
psql $DATABASE_URL -f apps/scripts/db/create_table.sql

# 5. 서버 실행
uv run uvicorn apps.main:app --reload --port 8000
```

API 문서: http://localhost:8000/docs

> 프론트엔드는 별도 저장소 `jangdokdae-client`에서 관리합니다.

---

## API

Base URL: `http://localhost:8000/api/v1` · 인증: `access_token` httpOnly 쿠키 (JWT, 15분)

### 인증 `/auth`

| Method | Endpoint | 설명 |
|--------|----------|------|
| `GET` | `/auth/kakao/login` | 카카오 로그인 시작 |
| `GET` | `/auth/kakao/callback` | 카카오 콜백 |
| `GET` | `/auth/google/login` | 구글 로그인 시작 |
| `GET` | `/auth/google/callback` | 구글 콜백 |
| `GET` | `/auth/me` ✅ | 현재 사용자 정보 |
| `POST` | `/auth/refresh` | 토큰 갱신 (Rotation) |
| `POST` | `/auth/logout` | 로그아웃 |

> 로그인 → Access Token (15분) + Refresh Token (7일, DB 저장) 발급. 재사용 감지 시 해당 유저 전체 토큰 폐기.

### 사용자 `/user`

| Method | Endpoint | 설명 |
|--------|----------|------|
| `GET` | `/user/sectors` | 전체 섹터 목록 |
| `GET` | `/user/profile` ✅ | 관심 섹터·종목 조회 |
| `PUT` | `/user/profile` ✅ | 관심 섹터·종목 수정 |

### 분석 `/analysis`

| Method | Endpoint | 설명 |
|--------|----------|------|
| `GET` | `/analysis/sidebar-context/{cluster_id}` | 사이드바 컨텍스트 조회 |
| `GET` | `/analysis/detail/{cluster_id}` | 분석 상세 조회 |
| `POST` | `/analysis/persist/{cluster_id}` | 분석 결과 DB 저장 |
| `POST` | `/analysis/analyze-cluster` | 단일 클러스터 즉시 분석 |
| `POST` | `/analysis/analyze-clusters` | 복수 클러스터 즉시 분석 |

### Issue Docent `/contents/issue-docent`

클러스터 1개를 주린이 학습 콘텐츠(요약·퀴즈·용어 해설)로 변환한 결과물입니다.

| Method | Endpoint | 설명 |
|--------|----------|------|
| `GET` | `/contents/issue-docent` | 목록 조회 (`limit`, `offset`) |
| `GET` | `/contents/issue-docent/{id}` | 상세 조회 |

```bash
# Issue Docent 생성
uv run python apps/scripts/generate_issue_docents.py --limit 5
uv run python apps/scripts/generate_issue_docents.py --cluster-id 14 --force
```

---

## 데이터 파이프라인

```
수집 → 전처리 → 임베딩·클러스터링 → 엔티티 추출 → 분석 → Issue Docent 생성
```

```bash
uv run python apps/scripts/collector_pipeline.py
```

| 단계 | 내용 |
|------|------|
| 수집 | 네이버 뉴스 크롤링, DART 공시·사업보고서, KRX 주가·거시 지표 |
| 전처리 | HTML·특수문자 제거, 중복 제거 |
| 임베딩·클러스터링 | ko-sroberta-multitask 벡터화, UMAP 축소, HDBSCAN 군집화 |
| 엔티티 추출 | Gemini로 기업명·섹터·키워드 추출 |
| 분석 | 클러스터별 분석 본문·사이드바 생성 |
| Issue Docent | LangGraph로 요약·퀴즈·용어 해설 생성 |

---

## 환경 변수

`.env.example` 참고. 필수 항목은 아래와 같습니다.

| 변수 | 설명 |
|------|------|
| `DATABASE_URL` | PostgreSQL 연결 문자열 |
| `GEMINI_API_KEY` | Google Gemini API 키 |
| `OPENAI_API_KEY` | OpenAI API 키 |
| `OPENDART_API_KEY` | DART OpenAPI 인증키 |
| `KRX_ID` / `KRX_PW` | KRX 로그인 계정 |
| `KAKAO_CLIENT_ID` / `KAKAO_CLIENT_SECRET` | 카카오 OAuth |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | 구글 OAuth |
| `JWT_SECRET` | JWT 서명 시크릿 |
| `CLIENT_URL` | 프론트엔드 URL (기본: `http://localhost:3000`) |

---

## 프로젝트 구조

```
apps/
├── main.py               # FastAPI 진입점
├── scripts/              # CLI 스크립트 (파이프라인, Issue Docent 생성, DB)
├── data/                 # 파이프라인 출력 (날짜별 JSON)
└── src/
    ├── api/              # 라우터 (auth, users, analyzer, issue_docent)
    ├── config/           # DB·환경변수·섹터·경로 설정
    ├── dependencies/     # FastAPI 의존성 (JWT 검증)
    ├── models/           # SQLAlchemy ORM 모델
    ├── repositories/     # DB 조회·저장 계층
    ├── schemas/          # Pydantic 스키마
    ├── services/         # 비즈니스 로직 (auth·collector·analyzer·issue_docent 등)
    ├── issue_docent/     # LangGraph 워크플로우·프롬프트
    └── utils/
docs/                     # 상세 설계 문서
tests/                    # API·유닛 테스트
```

---

## 기여하기

```bash
git switch -c feature/my-feature
git commit -m "feat: 기능 설명"
# PR → master
```

커밋 컨벤션: `feat` `fix` `refactor` `docs` `test` `chore`

---

© 2026 jangdokdae contributors
