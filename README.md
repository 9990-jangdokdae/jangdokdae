# ⚱️ㄴ 장독대 — 시장 독해를 대신 해드립니다

> 오늘의 시장 이슈를 쉽게 읽고 익히며 주식 시장의 감각을 키워주는 주린이 주식 큐레이션

---

## 🗂 목차

- [서비스 소개](#-서비스-소개)
- [주요 기능](#-주요-기능)
- [시스템 아키텍처](#-시스템-아키텍처)
- [프로젝트 구조](#-프로젝트-구조)
- [기술 스택](#-기술-스택)
- [시작하기](#-시작하기)
- [API 명세](#-api-명세)
- [데이터 파이프라인](#-데이터-파이프라인)
- [환경 변수](#-환경-변수)

---

## 🎯 서비스 소개

장독대는 주식 입문자(주린이)가 복잡한 시장 뉴스를 쉽게 소화할 수 있도록 돕는 AI 큐레이션 서비스입니다.
매일 쏟아지는 금융 뉴스를 자동으로 수집·분석하고, 초보자도 이해할 수 있는 학습 콘텐츠와 퀴즈로 변환해 제공합니다.

---

## ✨ 주요 기능

| 기능 | 설명 |
|------|------|
| **데이터 수집** | 주식 뉴스 자동 수집, 기업 재무재표, DART 사업보고서, 주가&거래량 수집 |
| **전처리** | HTML 클리닝, 한국어 키워드 추출, 중복 제거 |
| **임베딩 & 클러스터링** | 섹터별 기사 군집화|
| **분석(요약)** | 뉴스 기사 본문 분석 및 요약 |
| **학습 콘텐츠 생성** | 주린이 눈높이에 맞는 해설, 주식 용어 설명, 퀴즈 자동 생성 |

---

## 🏗 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│                      Client / Frontend                  │
└───────────────────────┬─────────────────────────────────┘
                        │ REST API
┌───────────────────────▼─────────────────────────────────┐
│                   FastAPI (API Server)                  │
│  /news  /analysis  /content  /search                    │
└───────────────────────┬─────────────────────────────────┘
                        │
          ┌─────────────┴──────────────┐
          │                            │
┌─────────▼──────────┐     ┌──────────▼──────────┐
│   PostgreSQL        │     │   Qdrant            │
│  (뉴스, 분석, 콘텐츠)  │     │  (임베딩 검색)        │
└────────────────────┘     └─────────────────────┘
          │
┌─────────▼──────────────────────────────────────────────┐
│               Celery Worker + Beat (비동기 파이프라인)     │
│                                                         │
│  Collector → Preprocessor → Embedder → Analyzer        │
│                                      → ContentGenerator │
└────────────────────────┬───────────────────────────────┘
                         │
              ┌──────────▼──────────┐
              │    Redis (Broker)    │
              └─────────────────────┘
```

---

## 📁 프로젝트 구조

```
jangdokdae/
├── main.py                        # FastAPI 앱 엔트리포인트
├── requirements.txt
├── .env.example
│
├── app/
│   ├── api/
│   │   └── v1/
│   │       └── endpoints/
│   │           ├── health.py      # 헬스체크
│   │           ├── news.py        # 뉴스 조회/검색 API
│   │           ├── analysis.py    # 분석 결과 API
│   │           └── content.py     # 학습 콘텐츠 API
│   │
│   ├── core/
│   │   └── config.py              # 환경변수 및 설정
│   │
│   ├── db/
│   │   ├── base.py                
│   │   └── session.py             # DB 세션 관리
│   │
│   ├── models/
│   │   └── models.py              # ORM 모델 (뉴스, 분석, 학습콘텐츠)
│   │
│   ├── schemas/
│   │   └── news.py                # Pydantic 스키마
│   │
│   ├── services/
│   │   ├── collector/
│   │   │   └── news_collector.py  # 뉴스 수집 (크롤링, RSS)
│   │   ├── embedder/
│   │   │   └── embedding_service.py # OpenAI 임베딩
│   │   ├── preprocessor/
│   │   │   └── preprocessor.py    # 텍스트 전처리
│   │   ├── analyzer/
│   │   │   └── analyzer_service.py # GPT-4o 요약/분석
│   │   └── content_generator/
│   │       └── content_generator.py # 학습 콘텐츠 생성
│
│
│
├── scripts/                       # 마이그레이션, 데이터 초기화 스크립트
└── docs/                          # API 문서, ERD
```

---

## 🛠 기술 스택

| 분류 | 기술 |
|------|------|
| **언어** | Python 3.12 |
| **웹 프레임워크** | FastAPI |
| **ORM / DB** | PostgreSQL |
| **캐시 / 메시지 브로커** | Redis |
| **비동기 작업** | Celery + Celery Beat |
| **LLM** | Gemini|
| **임베딩** | OpenAI text-embedding-3-small |
| **한국어 NLP** | KoNLPy (Okt) |
| **컨테이너** | Docker + Docker Compose |

---

## 🚀 시작하기

### 1. 저장소 클론

```bash
git clone https://github.com/your-org/stockcuration.git
cd stockcuration
```

### 2. 환경변수 설정

```bash
cp .env.example .env
# .env 파일을 열어 API 키 등 설정값 입력
```

### 3. Docker로 전체 실행 (권장)

```bash
docker-compose up --build
```

### 4. 로컬 개발 환경 실행

```bash
# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt

# DB 마이그레이션
alembic upgrade head

# API 서버 실행
uvicorn main:app --reload

# Celery Worker 실행 (별도 터미널)
celery -A app.tasks.celery_app worker --loglevel=info

# Celery Beat 실행 (스케줄러, 별도 터미널)
celery -A app.tasks.celery_app beat --loglevel=info
```

### 5. API 문서 확인

서버 실행 후 브라우저에서 확인:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## 📡 API 명세

### 뉴스

| Method | Endpoint | 설명 |
|--------|----------|------|
| `GET` | `/api/v1/news/` | 뉴스 목록 조회 (페이지네이션, 필터) |
| `GET` | `/api/v1/news/{id}` | 뉴스 상세 조회 |
| `GET` | `/api/v1/news/search/similar?query=...` | 벡터 유사도 기반 뉴스 검색 |

### 분석

| Method | Endpoint | 설명 |
|--------|----------|------|
| `GET` | `/api/v1/analysis/{article_id}` | 뉴스 분석 결과 조회 |
| `POST` | `/api/v1/analysis/trigger/{article_id}` | 특정 뉴스 재분석 요청 |

### 학습 콘텐츠

| Method | Endpoint | 설명 |
|--------|----------|------|
| `GET` | `/api/v1/content/` | 학습 콘텐츠 목록 조회 |
| `GET` | `/api/v1/content/{id}` | 콘텐츠 상세 (퀴즈, 용어 포함) |

---

## 🔄 데이터 파이프라인

뉴스 수집부터 학습 콘텐츠 생성까지 전 과정이 Celery로 자동화됩니다.

```
[Celery Beat: 30분마다]
        │
        ▼
  1. 수집 (NewsCollector)
     - Naver News API
     - RSS 피드 (한경, MT, 연합인포맥스)
        │
        ▼
  2. 전처리 (Preprocessor)
     - HTML/노이즈 제거
     - KoNLPy 키워드 추출
     - 감성 분석 (-1.0 ~ 1.0)
     - 중요도 스코어링 (0.0 ~ 1.0)
        │
        ▼
  3. 임베딩 (EmbeddingService)
     - text-embedding-3-small 벡터화
     - Qdrant 저장
     - 코사인 유사도 중복 감지 (threshold: 0.95)
        │
        ▼
  4. 분석 (AnalyzerService)
     - GPT-4o 3줄 요약
     - 핵심 포인트 추출
     - 관련 종목 추출
     - 시장 영향도 (positive/negative/neutral)
        │
        ▼
  5. 학습 콘텐츠 생성 (ContentGenerator)
     - 주린이 맞춤 해설 (마크다운)
     - 주식 용어 설명
     - 4지선다 퀴즈 생성
     - 난이도 설정 (beginner/intermediate/advanced)
```

---