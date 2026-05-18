CREATE TABLE article_analysis (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  cluster_id BIGINT NOT NULL UNIQUE REFERENCES clusters(id),
  analysis_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
  market_context JSONB NOT NULL DEFAULT '{}'::jsonb,
  sidebar_context JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMP NOT NULL DEFAULT now(),
  updated_at TIMESTAMP NOT NULL DEFAULT now()
);
