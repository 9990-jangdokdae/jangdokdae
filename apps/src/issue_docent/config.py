from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]

load_dotenv(REPO_ROOT / ".env", override=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        extra="ignore",
    )

    main_model: str = Field(default="gemini-3-flash-preview", alias="MAIN_MODEL")
    llm_thinking_level: str = Field(default="medium", alias="LLM_THINKING_LEVEL")
    llm_timeout_seconds: int = Field(default=600, alias="LLM_TIMEOUT_SECONDS")
    llm_transport_max_retries: int = Field(default=2, alias="LLM_TRANSPORT_MAX_RETRIES")
    google_api_key: SecretStr | None = Field(default=None, alias="GOOGLE_API_KEY")
    gemini_api_key: SecretStr | None = Field(default=None, alias="GEMINI_API_KEY")
    langsmith_project: str = Field(default="issue-docent", alias="LANGSMITH_PROJECT")

    @property
    def google_genai_api_key(self) -> SecretStr | None:
        return self.google_api_key or self.gemini_api_key


@lru_cache
def get_settings() -> Settings:
    return Settings()

