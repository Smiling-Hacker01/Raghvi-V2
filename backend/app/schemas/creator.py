"""Schemas for creator profile."""

from pydantic import BaseModel, Field


class CreatorProfileResponse(BaseModel):
    """Creator profile information."""

    name: str
    father_name: str
    mother_name: str
    girlfriend_name: str
    birthplace: str
    hometown: str
    education_background: str | None
    graduation_year: str
    graduation_degree: str
    hobbies: str | None
    dreams: str | None
    linkedin_url: str | None
    github_url: str | None
    instagram_url: str | None


class CreatorStoryRequest(BaseModel):
    """Request to generate creator story."""

    user_tone: str | None = Field(
        None, description="Suggested tone: formal, casual, warm, protective, poetic"
    )


class CreatorStoryResponse(BaseModel):
    """Response with creator story."""

    story: str
    tone: str
