"""환경변수 중앙 관리 모듈. load_dotenv()는 여기서 한 번만 호출합니다."""

import os

from dotenv import load_dotenv

load_dotenv()

# Database
DATABASE_URL: str = os.environ.get("DATABASE_URL", "")

# Gemini (Google AI Studio)
GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL: str = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

# Vertex AI
GOOGLE_APPLICATION_CREDENTIALS: str = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
GOOGLE_CLOUD_PROJECT: str = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
GOOGLE_CLOUD_LOCATION: str = os.environ.get("GOOGLE_CLOUD_LOCATION", "asia-northeast3")
VERTEX_MODEL: str = os.environ.get("VERTEX_MODEL", "gemini-2.5-flash")

# LLM (IssueDocent / Analyzer)
LLM_MODEL: str = os.environ.get("LLM_MODEL", "gemini-2.5-flash-lite")
MAIN_MODEL: str = os.environ.get("MAIN_MODEL", "gemini-3-flash-preview")
LLM_THINKING_LEVEL: str = os.environ.get("LLM_THINKING_LEVEL", "medium")
LLM_TIMEOUT_SECONDS: int = int(os.environ.get("LLM_TIMEOUT_SECONDS", "600"))
LLM_TRANSPORT_MAX_RETRIES: int = int(os.environ.get("LLM_TRANSPORT_MAX_RETRIES", "2"))

# Embedding
EMBED_MODEL: str = os.environ.get("EMBED_MODEL", "")

# DART
OPENDART_API_KEY: str = os.environ.get("OPENDART_API_KEY", "")

# KIS (한국투자증권)
KIS_APP_KEY: str = os.environ.get("KIS_APP_KEY", "")
KIS_APP_SECRET: str = os.environ.get("KIS_APP_SECRET", "")
KIS_BASE_URL: str = os.environ.get("KIS_BASE_URL", "https://openapi.koreainvestment.com:9443")
KIS_TIMEOUT_SEC: float = float(os.environ.get("KIS_TIMEOUT_SEC", "3"))
YAHOO_TIMEOUT_SEC: float = float(os.environ.get("YAHOO_TIMEOUT_SEC", "3"))

# OAuth
KAKAO_CLIENT_ID: str = os.environ.get("KAKAO_CLIENT_ID", "")
KAKAO_CLIENT_SECRET: str = os.environ.get("KAKAO_CLIENT_SECRET", "")
GOOGLE_CLIENT_ID: str = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET: str = os.environ.get("GOOGLE_CLIENT_SECRET", "")

# JWT / API
JWT_SECRET: str = os.environ.get("JWT_SECRET", "")
CLIENT_URL: str = os.environ.get("CLIENT_URL", "http://localhost:3000")
APP_ENV: str = os.environ.get("APP_ENV", "development")
