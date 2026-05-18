# 🏺 장독대 — 시장 독해를 대신 해드립니다

> 오늘의 시장 이슈를 쉽게 읽고 익히며 주식 시장의 감각을 키워주는 주린이 주식 큐레이션 웹 서비스 플랫폼

[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=white)](https://reactjs.org)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)](https://postgresql.org)
[![LangChain](https://img.shields.io/badge/LangChain-0.3-1C3C3C?logo=langchain&logoColor=white)](https://langchain.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🗂 목차

- [서비스 소개](#-서비스-소개)
- [주요 기능](#-주요-기능)
- [시스템 아키텍처](#-시스템-아키텍처)
- [프로젝트 구조](#-프로젝트-구조)
- [기술 스택 및 선택 이유](#-기술-스택-및-선택-이유)
- [시작하기](#-시작하기)
- [API 명세](#-api-명세)
- [데이터 파이프라인](#-데이터-파이프라인)
- [환경 변수](#-환경-변수)
- [기여하기](#-기여하기)

---

## 🎯 서비스 소개

**장독대**는 주식 입문자(주린이)가 복잡한 시장 뉴스를 쉽게 소화할 수 있도록 돕는 AI 큐레이션 서비스입니다.

> 장독대는 한국인에게 매일매일 들여다보고 정성껏 발효시키는 보관 공간. 매일 숙성되는 정보를 차곡차곡 모아두는 이 서비스의 철학을 담았습니다.

매일 쏟아지는 금융 뉴스 · 재무제표 · DART 공시를 자동으로 수집·분석하고, 초보자도 이해할 수 있는 학습 콘텐츠와 퀴즈로 변환해 제공합니다. 어렵게만 느껴지던 시장 독해, 장독대가 대신 해드립니다.

---

## ✨ 주요 기능

| 기능 | 설명 |
|------|------|
| **데이터 수집** | 주식 뉴스 자동 수집, 기업 재무제표, DART 사업보고서, 주가 & 거래량 수집 |
| **전처리** | HTML 클리닝, 한국어 키워드 추출, 중복 제거 |
| **임베딩 & 클러스터링** | 뉴스 벡터화, 섹터별 기사 군집화 |
| **분석(요약)** | Gemini 기반 뉴스 기사 본문 분석 및 3줄 요약 |
| **학습 콘텐츠 생성** | 주린이 눈높이에 맞는 해설, 주식 용어 설명, 퀴즈 자동 생성 |

---

## 🏗 시스템 아키텍처

```
┌──────────────────────────────────────────────────────────┐
│          React SPA  (Frontend)                           │
│   뉴스 카드 │ 마켓 지표 │ 학습 콘텐츠 │ 퀴즈 팝업          │
└───────────────────────┬──────────────────────────────────┘
                        │ REST API
┌───────────────────────▼──────────────────────────────────┐
│                   FastAPI  (API Server)                  │
│       /news    /analysis    /content    /search          │
└──────────────┬───────────────────────┬───────────────────┘
               │                       │
   ┌───────────▼──────────┐ ┌──────────▼──────────┐
   │  SQLite  (개발)       │ │  Qdrant             │
   │  PostgreSQL  (운영)   │ │  (임베딩 / 클러스터링)   │
   └──────────────────────┘ └─────────────────────┘
               │
┌──────────────▼───────────────────────────────────────────┐
│      LangGraph AI 파이프라인                                │
│                                                          │
│  Collector → Preprocessor → Embedder                    │
│           → Analyzer (Gemini) → ContentGenerator        │
└──────────────────────────┬───────────────────────────────┘
                           │
               ┌───────────▼─────────┐
               │    Redis  (Broker)   │
               └─────────────────────┘
```

---

## 📁 프로젝트 구조

```
jangdokdae-server/
├── pyproject.toml                       # Python 의존성 및 pytest 설정
├── uv.lock                              # 잠금 의존성
├── .env.example                         # 환경 변수 예시
│
├── apps/
│   ├── main.py                          # FastAPI 앱 엔트리포인트
│   ├── scripts/
│   │   ├── collector_pipeline.py        # 데이터 수집 파이프라인 실행
│   │   ├── generate_issue_docents.py    # Issue Docent 생성 wrapper
│   │   └── db/
│   │       └── create_issue_docent.sql  # Parent DB 수동 반영 SQL
│   │
│   └── src/
│       ├── api/                         # HTTP 라우터
│       │   ├── auth.py
│       │   ├── users.py
│       │   └── issue_docent.py
│       ├── config/                      # DB, 경로, 외부 설정
│       ├── dependencies/                # FastAPI 의존성
│       ├── models/                      # ORM 모델
│       ├── repositories/                # DB 조회/저장 계층
│       ├── schemas/                     # API 및 LLM 출력 스키마
│       ├── services/
│       │   ├── collector/
│       │   ├── preprocessor/
│       │   ├── embedder/
│       │   ├── extractor/
│       │   ├── analyzer/
│       │   ├── auth/
│       │   └── issue_docent/            # Issue Docent 읽기/생성 서비스
│       └── issue_docent/                # Issue Docent 전용 도메인
│           ├── graphs/                  # LangGraph 워크플로우
│           ├── llm/                     # LLM client 및 prompt loader
│           ├── prompts/                 # article brief / summary / quiz prompt
│           └── scripts/                 # 실제 생성 스크립트 구현
│
├── docs/
│   ├── AUTH_ONBOARDING.md
│   ├── BE_ARCHITECTURE.md
│   └── issue_docent_upload_to_neon.md
│
└── tests/
    ├── api/
    └── unit/
```

---

## 🛠 기술 스택 및 선택 이유

### 1. Frontend — React, JavaScript

| 항목 | 내용 |
|------|------|
| **선택 기술** | React 18, JavaScript |
| **주요 역할** | 뉴스 카드, 마켓 지표, 학습 콘텐츠, 퀴즈 팝업 등 UI 구성 |

**① 컴포넌트 기반 재사용성**
뉴스 카드, 오늘의 마켓 지표, 퀴즈 팝업 등 화면의 각 요소를 레고 블록처럼 컴포넌트화하여 재사용할 수 있습니다. 반복되는 UI 요소를 한 번만 만들어두고 여러 곳에서 쓸 수 있어 개발 속도를 높이고 유지보수가 용이합니다.

**② SPA로 매끄러운 UX 제공**
매일 접속해 가볍게 글을 읽어야 하는 서비스 특성상, 페이지 이동 시 깜빡임 없이 부드럽게 화면이 전환되는 SPA 환경이 필수였습니다. React는 이를 자연스럽게 구현할 수 있는 가장 성숙한 생태계를 갖추고 있습니다.

---

### 2. Backend — Python, FastAPI

| 항목 | 내용 |
|------|------|
| **선택 기술** | Python 3.12, FastAPI |
| **주요 역할** | REST API 서버, 비동기 데이터 처리, AI 파이프라인 오케스트레이션 |

**① 비동기 처리로 서버 병목 최소화**
AI 모델(Gemini)에 요약을 요청하고 응답을 기다리거나, 외부 DART 및 뉴스 API에서 데이터를 가져오는 과정에는 필연적으로 대기 시간이 발생합니다. FastAPI는 `async/await` 기반의 비동기 처리를 네이티브로 지원하여, 대기 중인 다른 요청도 동시에 처리할 수 있어 서버 병목 현상을 효과적으로 줄여줍니다.

**② 데이터·AI 생태계와의 완벽한 호환성**
Python은 데이터 수집(httpx, feedparser), 전처리(KoNLPy), AI 프레임워크 연동(LangChain, Gemini SDK) 등 이 프로젝트의 핵심 기능 전반에서 압도적인 생태계를 보유한 언어입니다. 특히 Gemini, LangChain 등의 공식 Python SDK가 잘 지원되어 통합 비용을 최소화할 수 있습니다.

---

### 3. AI & Framework — Gemini API, LangChain, LangGraph

| 항목 | 내용 |
|------|------|
| **선택 기술** | Google Gemini API, LangChain, LangGraph |
| **주요 역할** | 뉴스 요약, 학습 콘텐츠 생성, AI 워크플로우 자동화 |

**① Gemini — 복잡한 금융 문맥의 쉬운 번역**
어려운 금융 용어와 복잡한 거시 경제 지표를 주식 초보자의 눈높이에 맞게 풀어내는 핵심 엔진입니다. 긴 뉴스 본문을 한 번에 처리할 수 있는 큰 컨텍스트 윈도우와 뛰어난 한국어 성능, 그리고 비교적 저렴한 API 비용을 고려해 채택했습니다.

**② LangChain + LangGraph — 체계적인 AI 파이프라인 관리**
단순한 일회성 질문-답변을 넘어, 아래와 같이 여러 단계로 이어지는 복잡한 작업을 안정적으로 자동화하기 위해 채택했습니다.

```
[1단계: 뉴스 수집 및 검색]
        ↓
[2단계: 중요도에 따른 필터링]
        ↓
[3단계: Gemini API를 통한 요약 및 콘텐츠 재작성]
```

LangGraph의 상태 기반 워크플로우를 사용하면 각 단계의 실행 흐름을 명시적으로 정의하고, 실패 시 재시도하거나 조건에 따라 분기하는 견고한 파이프라인을 구성할 수 있습니다.

---

### 4. Database — SQLite / PostgreSQL

| 항목 | 내용 |
|------|------|
| **선택 기술** | SQLite (개발), PostgreSQL (운영) |
| **주요 역할** | 뉴스, 분석 결과, 학습 콘텐츠, 사용자 데이터 저장 |

**① SQLite — 설정 없는 빠른 프로토타이핑**
별도의 DB 서버 설치 없이 파일 하나로 즉시 개발을 시작할 수 있습니다. 초기 개발 단계에서 데이터 구조를 빠르게 검증하고 반복하는 데 최적화되어 있습니다.

**② PostgreSQL — 신뢰할 수 있는 프로덕션 DB**
실제 서비스 환경에서 사용자 정보, 스크랩 기사, 읽기 달성 기록 등 복잡하게 얽힌 관계형 데이터를 안전하고 무결하게 관리합니다. SQLAlchemy ORM을 사용하기 때문에 SQLite ↔ PostgreSQL 전환 시 비즈니스 로직 코드 변경이 최소화되는 것도 큰 장점입니다.

---

### 5. 사용 도구

| 분류 | 도구 | 용도 |
|------|------|------|
| **화면 설계** | Figma | UI/UX 와이어프레임 및 프로토타입 |
| **문서화** | Notion | 기획 문서 및 스케줄 관리 |
| **버전 관리** | GitHub | 코드 버전 관리 및 협업 |

---

## 🚀 시작하기

### 사전 준비

- Python 3.12+
- Google Gemini API Key
- OpenAI API Key (임베딩용)
- 네이버 개발자 앱 (Client ID / Secret)
- DART OpenAPI 인증키

### 1. 저장소 클론

```bash
git clone https://github.com/9990-jangdokdae/jangdokdae-server.git
cd jangdokdae-server
```

### 2. 환경변수 설정

```bash
cp .env.example .env
# .env 파일을 열어 API 키 등 설정값 입력
```

### 3. 백엔드 실행

```bash
# 의존성 설치
uv sync

# API 서버 실행
uv run uvicorn apps.main:app --reload --port 8000

# Celery Worker 실행 (별도 터미널)
celery -A apps.tasks.celery_app worker --loglevel=info

# Celery Beat 실행 (스케줄러, 별도 터미널)
celery -A apps.tasks.celery_app beat --loglevel=info
```

`issue_docent` 테이블을 Parent DB에 수동 반영해야 하면 [docs/issue_docent_upload_to_neon.md](docs/issue_docent_upload_to_neon.md)를 참고합니다.

### 4. 프론트엔드

프론트엔드는 별도 저장소 `jangdokdae-client`에서 관리합니다.

### 5. API 문서 확인

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## 📡 API 명세

### 공통

| 항목 | 내용 |
|------|------|
| Base URL | `http://localhost:8000/api/v1` |
| 응답 형식 | JSON |
| 인증 | Bearer Token (추후 적용) |

### 🗞 뉴스 (`/news`)

| Method | Endpoint | 설명 |
|--------|----------|------|
| `GET` | `/news/` | 뉴스 목록 조회 (페이지네이션, 키워드 / 감성 필터) |
| `GET` | `/news/{id}` | 뉴스 상세 조회 |
| `GET` | `/news/search/similar?query=...` | 벡터 유사도 기반 유사 뉴스 검색 |

**Query Parameters**

| 파라미터 | 타입 | 설명 |
|----------|------|------|
| `page` | int | 페이지 번호 (기본값: 1) |
| `size` | int | 페이지 크기 (기본값: 20, 최대: 100) |
| `keyword` | string | 키워드 필터 |
| `sentiment` | string | 감성 필터 (`positive` / `negative` / `neutral`) |
| `sector` | string | 섹터 필터 (e.g. `반도체`, `바이오`) |

### 📊 분석 (`/analysis`)

| Method | Endpoint | 설명 |
|--------|----------|------|
| `GET` | `/analysis/{article_id}` | 특정 뉴스의 분석 결과 조회 |
| `POST` | `/analysis/trigger/{article_id}` | 특정 뉴스 재분석 요청 (비동기) |

**응답 예시**

```json
{
  "article_id": "uuid",
  "summary": "삼성전자가 3분기 영업이익 10조 원을 기록하며 시장 예상치를 상회...",
  "key_points": ["영업이익 전분기 대비 30% 증가", "HBM 수요 확대 수혜"],
  "related_stocks": ["삼성전자", "SK하이닉스"],
  "market_impact": "positive",
  "impact_reason": "반도체 업황 회복 기대감 확산"
}
```

### 📚 학습 콘텐츠 (`/content`)

| Method | Endpoint | 설명 |
|--------|----------|------|
| `GET` | `/content/` | 학습 콘텐츠 목록 조회 |
| `GET` | `/content/{id}` | 콘텐츠 상세 조회 (퀴즈 + 용어 포함) |

**응답 예시**

```json
{
  "id": "uuid",
  "title": "삼성전자 실적이 좋으면 내 주식도 오를까? 🤔",
  "body": "## 오늘의 핵심\n...",
  "terms": [
    { "word": "영업이익", "definition": "회사가 물건을 팔고 남긴 순수한 이익이에요." }
  ],
  "quiz": [
    {
      "question": "영업이익이 증가하면 주가는 어떻게 될 가능성이 높을까요?",
      "options": ["상승", "하락", "변화 없음", "알 수 없음"],
      "answer": 0,
      "explanation": "영업이익 증가는 기업 가치 상승을 의미해 투자자들이 더 많이 사려 하기 때문입니다."
    }
  ],
  "difficulty": "beginner"
}
```

### 🧭 Issue Docent (`/contents/issue-docent`)

Issue Docent는 클러스터 1개를 하나의 주린이 학습 콘텐츠로 생성하고 조회하는 API입니다.

| Method | Endpoint | 설명 |
|--------|----------|------|
| `GET` | `/contents/issue-docent?limit=20&offset=0` | Issue Docent 목록 조회 |
| `GET` | `/contents/issue-docent/{id}` | Issue Docent 상세 조회 |

상세 응답은 본문(`summary`), 원문 기사 목록(`articles`), 저장된 퀴즈(`quizzes`), 본문 용어 매칭 결과(`matched_terms`)를 포함합니다. `summary`는 DB에 `TEXT`로 저장되며 API 서버가 문단별 응답 객체로 변환하고 `stock_terms`를 동적으로 매칭합니다.

생성 스크립트는 다음 wrapper로 실행합니다.

```bash
uv run python apps/scripts/generate_issue_docents.py --limit 5
uv run python apps/scripts/generate_issue_docents.py --cluster-id 14 --force
```

Parent DB에 `issue_docent` 테이블을 수동 생성해야 하는 경우 [docs/issue_docent_upload_to_neon.md](docs/issue_docent_upload_to_neon.md)를 따릅니다.

---

## 🔄 데이터 파이프라인

뉴스 수집부터 학습 콘텐츠 생성까지 전 과정이 **LangGraph + Celery**로 자동화됩니다.

```
[주기마다]
        │
        ▼
  1. 수집 (NewsCollector)
     ├─ Naver News API (주식 관련 뉴스)
     ├─ RSS 피드 (한경, 머니투데이, 연합인포맥스)
     ├─ DART OpenAPI (기업 공시, 사업보고서)
     └─ KRX / 야후 파이낸스 (주가 & 거래량)
        │
        ▼
  2. 전처리 (Preprocessor)
     ├─ HTML / 특수문자 / URL 제거
     ├─ KoNLPy(Okt) 명사 추출 & 키워드 가중치 부여
     └─ 중요도에 따른 필터링 및 중복 제거
        │
        ▼
  3. 임베딩 & 클러스터링 (EmbeddingService)
     ├─ text-embedding-3-small 벡터화
     ├─ Qdrant 저장
     ├─ 코사인 유사도 기반 중복 감지 (threshold: 0.95)
     └─ 섹터별 군집화
        │
        ▼
  4. 분석 (LangGraph + Gemini)
     ├─ [Node 1] 뉴스 검색 및 수집
     ├─ [Node 2] 중요도에 따른 필터링
     ├─ [Node 3] Gemini API를 통한 요약 및 재작성
     ├─ 핵심 포인트 추출 & 관련 종목 태깅
     └─ 시장 영향도 분류 (positive / negative / neutral)
        │
        ▼
  5. 학습 콘텐츠 생성 (ContentGenerator)
     ├─ 주린이 맞춤 해설 (마크다운)
     ├─ 주식 용어 설명 리스트
     ├─ 4지선다 퀴즈 생성
     └─ 난이도 설정 (beginner / intermediate / advanced)
```

---

## ⚙️ 환경 변수

`.env.example`을 복사해 `.env`를 만들고 아래 값을 채워주세요.

| 변수명 | 설명 | 필수 |
|--------|------|:----:|
| `DATABASE_URL` | DB 연결 문자열 (개발: `sqlite:///./dev.db`, 운영: PostgreSQL URL) | ✅ |
| `REDIS_URL` | Redis 연결 URL | ✅ |
| `GEMINI_API_KEY` | Google Gemini API 키 (LLM 분석용) | ✅ |
| `OPENAI_API_KEY` | OpenAI API 키 (임베딩용) | ✅ |
| `NAVER_CLIENT_ID` | 네이버 개발자 앱 Client ID | ✅ |
| `NAVER_CLIENT_SECRET` | 네이버 개발자 앱 Secret | ✅ |
| `DART_API_KEY` | DART OpenAPI 인증키 | ✅ |
| `QDRANT_HOST` | Qdrant 호스트 (기본: localhost) | ✅ |
| `QDRANT_PORT` | Qdrant 포트 (기본: 6333) | — |
| `QDRANT_COLLECTION` | 컬렉션명 (기본: jangdokdae_news) | — |
| `DEBUG` | 디버그 모드 (기본: False) | — |

---

## 🤝 기여하기

```bash
# 1. 이슈 생성 또는 기존 이슈 확인
# 2. feature 브랜치 생성
git switch -c feature/your-feature-name

# 3. 변경사항 커밋
git commit -m "feat: 기능 설명"

# 4. PR 생성 → main 브랜치로 머지 요청
```

**커밋 컨벤션**

| 태그 | 설명 |
|------|------|
| `feat` | 새로운 기능 추가 |
| `fix` | 버그 수정 |
| `refactor` | 코드 리팩토링 |
| `docs` | 문서 수정 |
| `test` | 테스트 추가/수정 |
| `chore` | 빌드, 패키지 설정 변경 |

---

## 📄 라이선스

© 2026 jangdokdae contributors
