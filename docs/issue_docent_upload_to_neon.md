# Issue Docent Neon 반영 절차

이 문서는 Child Branch에서 검증한 `issue_docent` 테이블을 Parent DB에 수동 반영하는 절차다.

`apps/scripts/db/create_issue_docent.sql`을 기준 SQL로 사용한다. 이 문서에 포함된 SQL은 실행 편의를 위한 복사본이며, 수정이 필요하면 SQL 파일을 먼저 수정한다.

## 범위

이번 문서에서 생성하는 테이블은 `issue_docent` 하나다.

다음 테이블은 이미 Parent DB에 존재한다고 전제한다.

- `articles`
- `clusters`
- `cluster_articles`
- `entity_extraction`
- `company_master`
- `stock_terms`

`stock_terms` 생성/적재는 이 문서 범위에 포함하지 않는다.

## 1. Neon SQL Editor 열기

1. Neon Console에 접속한다.
2. Parent DB에 해당하는 Project와 Branch를 선택한다.
3. SQL Editor를 연다.
4. 아래 확인 쿼리를 먼저 실행한다.

운영 DB에 바로 적용하기 전에 Child Branch 또는 staging branch에서 동일 절차를 검증하는 것을 권장한다.

## 2. 기존 테이블 확인

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN (
    'articles',
    'clusters',
    'cluster_articles',
    'entity_extraction',
    'company_master',
    'stock_terms',
    'issue_docent'
  )
ORDER BY table_name;
```

`issue_docent`가 이미 있으면 바로 생성하지 않는다. 기존 용도와 데이터를 확인한 뒤 유지, 백업 후 교체, 또는 별도 migration 계획 중 하나를 선택한다.

## 3. 테이블 생성

기준 파일: `apps/scripts/db/create_issue_docent.sql`

```sql
CREATE TABLE issue_docent (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  cluster_id BIGINT NOT NULL UNIQUE REFERENCES clusters(id),
  title TEXT NOT NULL,
  teaser TEXT NOT NULL,
  summary TEXT NOT NULL,
  explanation JSONB NOT NULL DEFAULT '[]'::jsonb,
  quizzes JSONB NOT NULL DEFAULT '[]'::jsonb,
  created_at TIMESTAMP NOT NULL DEFAULT now()
);
```

현재 정책은 클러스터 1개가 Issue Docent 콘텐츠 1개를 가진다는 것이다. 따라서 `cluster_id`는 `UNIQUE`로 둔다.

향후 프롬프트 버전 비교, A/B 테스트, 생성 이력 저장이 필요하면 `version` 컬럼을 추가하고 unique 기준을 `(cluster_id, version)`으로 변경하는 별도 migration을 설계한다.

## 4. 구조 검증

```sql
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'issue_docent'
ORDER BY ordinal_position;
```

```sql
SELECT
  tc.constraint_name,
  tc.constraint_type,
  kcu.column_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name = kcu.constraint_name
WHERE tc.table_schema = 'public'
  AND tc.table_name = 'issue_docent'
ORDER BY tc.constraint_type, tc.constraint_name;
```

## 5. API/생성 전 확인

```sql
SELECT COUNT(*) FROM clusters;
```

```sql
SELECT COUNT(*) FROM stock_terms;
```

```sql
SELECT COUNT(*) FROM issue_docent;
```

`stock_terms`가 비어 있으면 Issue Docent 본문 생성은 가능하지만 용어 매칭과 용어 기반 퀴즈 품질이 낮아질 수 있다.
