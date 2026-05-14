# 백엔드 API 추가 가이드

---

## API를 추가하려면 어떤 파일을 건드려야 하나요?

새 API를 하나 추가할 때 수정하는 파일은 보통 **2개**입니다.

```
① schemas/ 하위 파일   ← 응답 데이터 형태 정의
② api/ 하위 파일       ← URL과 처리 로직 작성
```

DB에 새 테이블이나 컬럼이 필요한 경우에만 `models/`도 함께 수정합니다.

---

## 예시로 배우기: "뉴스 리스트 가져오기 API" 추가하기

> `GET /news` — DB에 저장된 뉴스 기사 목록을 최신순으로 반환하는 API

뉴스 기사는 파이프라인이 수집해 `articles` 테이블에 저장해 둡니다.
이 테이블에서 데이터를 읽어 클라이언트에 전달하는 API를 추가합니다.

---

### Step 1. 응답 형태 정의

먼저 API가 **돌려줄 데이터의 형태**를 정의합니다.
`apps/src/schemas/` 아래에 `news.py` 파일을 새로 만듭니다.

```python
# apps/src/schemas/news.py  (새 파일 생성)

from datetime import datetime
from pydantic import BaseModel


class ArticleResponse(BaseModel):
    """뉴스 기사 한 건의 응답 형태"""
    id: int
    title: str             # 기사 제목
    press: str | None      # 언론사 (없을 수도 있어서 | None)
    published_date: datetime  # 발행 일시
    url: str               # 기사 원문 링크


class ArticleListResponse(BaseModel):
    """뉴스 리스트 응답 형태"""
    articles: list[ArticleResponse]   # 기사 목록
    total: int                        # 전체 기사 수
```

---

### Step 2. 라우터 파일 추가

`apps/src/api/` 아래에 `news.py` 파일을 새로 만듭니다.

```python
# apps/src/api/news.py  (새 파일 생성)

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.src.config.database import get_db
from apps.src.models.article import Article
from apps.src.schemas.news import ArticleListResponse, ArticleResponse

router = APIRouter()


@router.get("", response_model=ArticleListResponse)
async def get_news_list(
    session: AsyncSession = Depends(get_db),   # DB 연결 (로그인 불필요)
):
    """DB에서 뉴스 기사를 최신순으로 가져온다."""

    # 전체 기사 수 조회
    count_result = await session.execute(select(func.count()).select_from(Article))
    total = count_result.scalar_one()

    # 기사 목록 조회 (최신순, 최대 50개)
    result = await session.execute(
        select(Article)
        .order_by(Article.published_date.desc())
        .limit(50)
    )
    articles = result.scalars().all()

    return ArticleListResponse(
        articles=[
            ArticleResponse(
                id=a.id,
                title=a.title,
                press=a.press,
                published_date=a.published_date,
                url=a.url,
            )
            for a in articles
        ],
        total=total,
    )
```

---

### Step 3. 앱에 라우터 등록

`apps/main.py`에 새 라우터를 등록합니다.

```python
# apps/main.py

from apps.src.api.news import router as news_router   # 추가

app.include_router(news_router, prefix="/news", tags=["news"])  # 추가
```

---

### Step 4. 확인

서버를 재시작하고 Swagger UI에서 새 API가 나타나는지 확인합니다.

```bash
uvicorn apps.main:app --reload --port 8000
# 브라우저에서 http://localhost:8000/docs 열기
```

`GET /news` 항목이 생기고 실행했을 때 기사 목록이 반환되면 성공입니다.

```json
{
  "articles": [
    {
      "id": 1,
      "title": "삼성전자, 2분기 실적 발표",
      "press": "한국경제",
      "published_date": "2026-05-14T09:00:00",
      "url": "https://..."
    }
  ],
  "total": 217
}
```

---

## 파일별 역할 한눈에 보기

### `schemas/` — 데이터 형태 정의

"어떤 데이터를 주고받을지" 계약서입니다.
잘못된 데이터가 들어오면 FastAPI가 자동으로 400 오류를 반환합니다.

```
클라이언트 → [Body 클래스 검증] → API 함수
API 함수  → [Response 클래스 직렬화] → 클라이언트
```

### `api/` — URL과 처리 로직

`@router.get("/경로")` 또는 `@router.put("/경로")` 데코레이터로 URL을 등록합니다.

| 데코레이터 | 용도 |
|-----------|------|
| `@router.get("/...")` | 데이터 조회 |
| `@router.put("/...")` | 데이터 수정 (전체 교체) |
| `@router.post("/...")` | 새 데이터 생성 |
| `@router.delete("/...")` | 데이터 삭제 |

### `models/` — DB 테이블

DB에 새 테이블이나 컬럼이 필요할 때만 수정합니다.
뉴스 리스트 예시처럼 **기존 테이블에서 읽기만 하는 경우에는 수정하지 않습니다.**
컬럼을 추가할 때는 반드시 DB 마이그레이션 SQL도 함께 실행해야 합니다.

```python
# 컬럼 추가 예시
bio: Mapped[str | None] = mapped_column(String(200), nullable=True)
```

---

## 자주 나오는 패턴

### 로그인이 필요한 API

```python
async def my_endpoint(
    user: User = Depends(get_current_user),  # 이 줄 추가
    ...
):
```

`get_current_user`가 JWT 쿠키를 검증합니다.
로그인하지 않은 사용자가 호출하면 자동으로 401 오류를 반환합니다.

### DB에서 데이터 읽기

```python
result = await session.execute(select(User).where(User.id == user.id))
db_user = result.scalar_one()        # 정확히 1개 가져오기
# db_user = result.scalar_one_or_none()  # 없으면 None 반환
```

### DB에 데이터 저장

```python
db_user.nickname = "새 닉네임"    # 값 변경
await session.commit()             # 반드시 commit 해야 DB에 저장됨
```

---

## 주의사항

| 항목 | 내용 |
|------|------|
| `await session.commit()` 누락 | DB에 저장되지 않음. 변경 후 반드시 호출 |
| `get_current_user` 누락 | 로그인 없이 누구나 호출 가능해짐 |
| schemas 정의 누락 | 응답 형태가 없으면 FastAPI가 딕셔너리를 그대로 반환 (검증 없음) |
| 서버 재시작 필수 | 코드 변경 후 `--reload` 옵션이 없으면 직접 재시작 필요 |
