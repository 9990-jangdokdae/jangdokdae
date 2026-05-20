# 로그인 · 온보딩 구현 문서

## 개요

구현한 기능은 다음 세 가지입니다.

1. **소셜 로그인** — 카카오·구글 OAuth 2.0으로 로그인
2. **JWT 인증** — Access Token + Refresh Token 이중 쿠키로 세션 유지
3. **관심 프로필** — 사용자별 관심 섹터·종목을 DB에 저장하고 온보딩으로 수집

---

## 인증 흐름

```
[로그인]
OAuth 콜백 → Access Token(15분) + Refresh Token(7일) 동시 발급
           → 각각 별도 httpOnly 쿠키로 설정
           → Refresh Token은 SHA-256 해시 후 DB(refresh_tokens) 저장

[API 요청]
클라이언트 → Access Token 쿠키 자동 전송 → 서버 검증

[토큰 만료]
Access Token 401 → 클라이언트 자동으로 POST /auth/refresh 호출
                 → Refresh Token으로 새 토큰 쌍 발급 (Rotation)
                 → 원래 요청 재시도

[로그아웃]
POST /auth/logout → DB에서 Refresh Token 폐기 → 양쪽 쿠키 삭제
```

---

## 주요 기술 결정

### 1. Access Token + Refresh Token 분리 (보안 강화)

단일 30일짜리 Access Token 대신 만료 시간이 짧은 두 토큰을 조합합니다.

| 토큰 | 저장 위치 | 만료 |
|------|----------|------|
| Access Token | httpOnly 쿠키 (session) | **15분** |
| Refresh Token | httpOnly 쿠키 (session) + DB | **7일** |

Access Token이 탈취되어도 15분 후에 무효화됩니다.
Refresh Token은 DB에 저장되어 있어 서버에서 언제든 즉시 폐기할 수 있습니다.

### 2. Refresh Token Rotation (탈취 감지)

Refresh Token을 사용할 때마다 새 토큰으로 교체합니다.
이미 사용(폐기)된 토큰이 다시 들어오면 탈취로 판단해 해당 유저의 **모든 토큰을 즉시 폐기**합니다.

```python
if db_token.revoked:
    # 탈취 감지 → 전체 세션 강제 종료
    await refresh_token_repo.revoke_all_for_user(session, db_token.user_id)
```

클라이언트는 이 응답을 받으면 "보안 위협이 감지되었습니다" 배너를 사용자에게 표시합니다.

### 3. Refresh Token은 해시 후 저장 (DB 유출 대비)

토큰 원문 대신 SHA-256 해시값을 DB에 저장합니다.
DB가 유출되어도 해시에서 원문을 복원할 수 없습니다.

```python
def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
```

### 4. httpOnly 쿠키 (XSS 방어)

두 토큰 모두 httpOnly 쿠키로 설정해 JavaScript에서 접근할 수 없습니다.
`max_age` 없는 session cookie이므로 브라우저를 완전히 닫으면 자동 삭제됩니다.

```python
response.set_cookie(
    key="access_token",
    httponly=True,
    samesite="none" if is_prod else "lax",  # 크로스도메인 프로덕션은 None 필수
    secure=is_prod,
    # max_age 없음 → 브라우저 종료 시 자동 삭제
)
```

### 5. 만료 토큰 자동 정리

Refresh Token rotation 시 해당 유저의 만료된 토큰을 동일 트랜잭션에서 함께 삭제합니다.
별도 배치 없이 테이블이 무한정 누적되지 않도록 합니다.

```python
await refresh_token_repo.revoke(session, token_hash)
await refresh_token_repo.delete_expired_for_user(session, user_id)
```

### 6. CSRF 방지 state 파라미터 (RFC 6749 §10.12)

OAuth 로그인 시작 시 무작위 `state` 값을 생성해 쿠키에 저장하고,
콜백에서 OAuth 제공자가 돌려준 `state`와 대조합니다.
불일치하면 400 오류를 반환해 CSRF 공격을 방지합니다.

```python
state = secrets.token_urlsafe(32)   # 로그인 시작
# 콜백에서 검증
if request.cookies.get("oauth_state") != state:
    raise HTTPException(400)
```

### 7. 오픈 리다이렉트 방지 (return_url)

로그인 후 돌아갈 경로를 `return_url` 파라미터로 받습니다.
상대 경로(`/`)만 허용하고, 외부 URL은 홈(`/`)으로 강제합니다.

```python
def _safe_return_url(url: str) -> str:
    if url.startswith("/") and not url.startswith("//"):
        return url
    return "/"
```

### 8. INSERT ON CONFLICT (동시 로그인 안전)

같은 사용자가 두 탭에서 동시에 로그인해도 DB 오류가 발생하지 않도록
`SELECT → INSERT` 대신 PostgreSQL의 `ON CONFLICT DO UPDATE`를 사용합니다.

```sql
INSERT INTO users (provider, provider_id, nickname)
VALUES (...)
ON CONFLICT (provider, provider_id)
DO UPDATE SET nickname = EXCLUDED.nickname
```

### 9. pool_pre_ping (Neon 유휴 연결 복구)

Neon PostgreSQL은 서버리스 DB라 일정 시간 유휴 상태면 연결을 끊습니다.
`pool_pre_ping=True`로 쿼리 전 연결 상태를 확인해 끊긴 경우 자동으로 재연결합니다.

```python
create_async_engine(url, pool_pre_ping=True, pool_recycle=300)
```

---

## DB 스키마

### users 테이블

```sql
CREATE TABLE users (
  id                 BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  provider           VARCHAR(10)  NOT NULL,           -- 'kakao' | 'google'
  provider_id        VARCHAR(100) NOT NULL,
  nickname           VARCHAR(100) NOT NULL,
  interest_sectors   TEXT[] NOT NULL DEFAULT '{}',
  interest_companies TEXT[] NOT NULL DEFAULT '{}',
  created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (provider, provider_id)
);
```

### refresh_tokens 테이블

```sql
CREATE TABLE refresh_tokens (
  id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id     BIGINT      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash  VARCHAR(64) NOT NULL UNIQUE,  -- SHA-256 hexdigest
  expires_at  TIMESTAMPTZ NOT NULL,
  revoked     BOOLEAN     NOT NULL DEFAULT FALSE,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX idx_refresh_tokens_expires_at ON refresh_tokens(expires_at) WHERE revoked = FALSE;
```

**interest_sectors / interest_companies** 컬럼은 온보딩에서 사용자가 선택한
섹터·종목을 배열로 저장합니다. 빈 배열(`{}`)이면 아직 온보딩을 완료하지 않은 신규 사용자입니다.

---

## 섹터 목록 관리

섹터는 **`apps/src/config/sectors.py`** 파일 하나에서 관리합니다.
API 응답(`GET /api/v1/user/sectors`)과 온보딩 UI 모두 이 파일을 단일 진실 소스로 사용합니다.

```python
SECTORS: list[str] = [
    "반도체", "자동차/모빌리티", "2차전지", "바이오/제약",
    "금융", "통신", "에너지/화학", "조선", "방산", "철강/소재",
    "유통/소비재", "부동산/건설", "IT/소프트웨어", "엔터테인먼트/미디어", "기타"
]
```

섹터를 추가·수정할 때는 이 파일만 편집하면 됩니다.

---

## 클라이언트 동작

### 자동 토큰 갱신 (`src/lib/api.ts`)

모든 API 요청은 `apiFetchJson`을 통해 이루어집니다.
401 응답 시 자동으로 `/auth/refresh`를 호출하고 원래 요청을 재시도합니다.
동시에 여러 요청이 401을 받아도 refresh 요청은 한 번만 나갑니다 (singleton 패턴).

### 보안 위협 알림 (`src/hooks/useAuth.tsx`)

서버가 토큰 탈취를 감지해 401 + "보안 위협" 메시지를 반환하면,
`auth:security-threat` CustomEvent가 발생하고
AuthProvider가 화면 상단에 빨간 배너로 사용자에게 알립니다.

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
| RefreshToken ORM 모델 | `apps/src/models/refresh_token.py` |
| RefreshToken CRUD | `apps/src/repositories/refresh_token.py` |
| 요청·응답 스키마 | `apps/src/schemas/users.py` |
| 섹터 목록 | `apps/src/config/sectors.py` |
| API 클라이언트 (토큰 갱신) | `src/lib/api.ts` (클라이언트) |
| 인증 컨텍스트 | `src/hooks/useAuth.tsx` (클라이언트) |
