-- 전체 데이터 삭제 (테이블 구조 유지, auto-increment 시퀀스 초기화)
TRUNCATE refresh_tokens            RESTART IDENTITY CASCADE;
TRUNCATE cluster_articles          RESTART IDENTITY CASCADE;
TRUNCATE entity_extraction         RESTART IDENTITY CASCADE;
TRUNCATE issue_docent              RESTART IDENTITY CASCADE;
TRUNCATE article_analysis          RESTART IDENTITY CASCADE;
TRUNCATE dart_financial_statements RESTART IDENTITY CASCADE;
TRUNCATE dart_document             RESTART IDENTITY CASCADE;
TRUNCATE clusters                  RESTART IDENTITY CASCADE;
TRUNCATE articles                  RESTART IDENTITY CASCADE;
TRUNCATE company_master            RESTART IDENTITY CASCADE;
TRUNCATE users                     RESTART IDENTITY CASCADE;
