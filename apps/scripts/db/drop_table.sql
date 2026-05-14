-- FK 의존 순서 역순으로 DROP (CASCADE로 인덱스·제약 자동 제거)
DROP TABLE IF EXISTS cluster_articles          CASCADE;
DROP TABLE IF EXISTS entity_extraction         CASCADE;
DROP TABLE IF EXISTS dart_financial_statements CASCADE;
DROP TABLE IF EXISTS dart_document             CASCADE;
DROP TABLE IF EXISTS clusters                  CASCADE;
DROP TABLE IF EXISTS articles                  CASCADE;
DROP TABLE IF EXISTS company_master            CASCADE;
