# 로그인 · 온보딩 구현 문서

## 개요

구현한 기능은 다음 세 가지입니다.

1. **소셜 로그인** — 카카오·구글 OAuth 2.0으로 로그인
2. **JWT 인증** — 로그인 상태를 httpOnly 쿠키로 유지
3. **관심 프로필** — 사용자별 관심 섹터·종목을 DB에 저장하고 온보딩으로 수집
---

## 주요 기술 결정

### 1. httpOnly 쿠키 (XSS 방어)
JWT를 `localStorage`가 아닌 httpOnly 쿠키에 저장합니다.
JavaScript에서 쿠키를 읽을 수 없어 XSS 공격으로 토큰을 탈취할 수 없습니다.

```python
response.set_cookie(
    key="access_token",
    httponly=True,          # JS 접근 불가
    samesite="lax",         # CSRF 방어
    secure=_is_production() # 프로덕션에서만 HTTPS 전용
)
```

### 2. CSRF 방지 state 파라미터 (RFC 6749 §10.12)
OAuth 로그인 시작 시 무작위 `state` 값을 생성해 쿠키에 저장하고,
콜백에서 OAuth 제공자가 돌려준 `state`와 대조합니다.
불일치하면 400 오류를 반환해 CSRF 공격을 방지합니다.

```python
state = secrets.token_urlsafe(32)   # 로그인 시작
# 콜백에서 검증
if request.cookies.get("oauth_state") != state:
    raise HTTPException(400)
```

### 3. INSERT ON CONFLICT (동시 로그인 안전)
같은 사용자가 두 탭에서 동시에 로그인해도 DB 오류가 발생하지 않도록
`SELECT → INSERT` 대신 PostgreSQL의 `ON CONFLICT DO UPDATE`를 사용합니다.

```sql
INSERT INTO users (provider, provider_id, nickname)
VALUES (...)
ON CONFLICT (provider, provider_id)
DO UPDATE SET nickname = EXCLUDED.nickname
```

### 4. pool_pre_ping (Neon 유휴 연결 복구)
Neon PostgreSQL은 서버리스 DB라 일정 시간 유휴 상태면 연결을 끊습니다.
`pool_pre_ping=True`로 쿼리 전 연결 상태를 확인해 끊긴 경우 자동으로 재연결합니다.

```python
create_async_engine(url, pool_pre_ping=True, pool_recycle=300)
```

---

## DB 스키마 — users 테이블

```sql
CREATE TABLE users (
  id                 BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  provider           VARCHAR(10)  NOT NULL,           -- 'kakao' | 'google'
  provider_id        VARCHAR(100) NOT NULL,            -- OAuth 제공자 내 사용자 ID
  nickname           VARCHAR(100) NOT NULL,
  interest_sectors   TEXT[] NOT NULL DEFAULT '{}',    -- 관심 섹터 목록
  interest_companies TEXT[] NOT NULL DEFAULT '{}',    -- 관심 종목 목록
  created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (provider, provider_id)                      -- 같은 제공자 내 ID 중복 불가
);
```

**interest_sectors / interest_companies** 컬럼은 온보딩에서 사용자가 선택한
섹터·종목을 배열로 저장합니다. 빈 배열(`{}`)이면 아직 온보딩을 완료하지 않은 신규 사용자입니다.

---

## 섹터 목록 관리

섹터는 **`apps/src/config/sectors.py`** 파일 하나에서 관리합니다.
API 응답(`GET /user/sectors`)과 온보딩 UI 모두 이 파일을 단일 진실 소스로 사용합니다.

```python
SECTORS: list[str] = [
    "반도체", "자동차/모빌리티", "2차전지", "바이오/제약",
    "금융", "통신", "에너지/화학", "조선", "방산", "철강/소재",
    "유통/소비재", "부동산/건설", "IT/소프트웨어", "엔터테인먼트/미디어", "기타"
]
```

섹터를 추가·수정할 때는 이 파일만 편집하면 됩니다.

---

## 관련 파일

| 역할 | 파일 |
|------|------|
| OAuth 엔드포인트 | `apps/src/api/auth.py` |
| 프로필 엔드포인트 | `apps/src/api/users.py` |
| JWT 생성·검증 | `apps/src/services/auth/jwt.py` |
| OAuth API 호출 | `apps/src/services/auth/oauth.py` |
| JWT 인증 의존성 | `apps/src/dependencies/auth.py` |
| User ORM 모델 | `apps/src/models/user.py` |
| 요청·응답 스키마 | `apps/src/schemas/users.py` |
| 섹터 목록 | `apps/src/config/sectors.py` |
