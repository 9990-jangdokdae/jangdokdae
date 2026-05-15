CREATE TABLE issue_docent (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  cluster_id BIGINT NOT NULL UNIQUE REFERENCES clusters(id),
  title TEXT NOT NULL,
  teaser TEXT NOT NULL,
  summary TEXT NOT NULL,
  explanation JSONB NOT NULL DEFAULT '[]'::jsonb,
  quizzes JSONB NOT NULL DEFAULT '[]'::jsonb,
  created_at TIMESTAMP NOT NULL DEFAULT now(),
  updated_at TIMESTAMP NOT NULL DEFAULT now()
);
