"""사용자 관련 Pydantic 스키마."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, field_serializer, field_validator

from apps.src.config.sectors import SECTORS

# 종목 최대 선택 개수
MAX_COMPANIES = 50


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nickname: str
    provider: str

    @field_serializer("id")
    def serialize_id(self, v: int) -> str:
        """프론트엔드에서 id를 문자열로 기대하므로 직렬화 시 변환한다."""
        return str(v)


class InterestProfileBody(BaseModel):
    sectors: list[str]
    companies: Annotated[list[str], ...]

    @field_validator("sectors")
    @classmethod
    def validate_sectors(cls, v: list[str]) -> list[str]:
        """sectors.py에 정의된 목록만 허용한다."""
        invalid = set(v) - set(SECTORS)
        if invalid:
            raise ValueError(f"유효하지 않은 섹터: {sorted(invalid)}")
        return v

    @field_validator("companies")
    @classmethod
    def validate_companies(cls, v: list[str]) -> list[str]:
        """최대 {MAX_COMPANIES}개까지만 허용한다."""
        if len(v) > MAX_COMPANIES:
            raise ValueError(f"종목은 최대 {MAX_COMPANIES}개까지 선택할 수 있습니다")
        return v


class InterestProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sectors: list[str]
    companies: list[str]
