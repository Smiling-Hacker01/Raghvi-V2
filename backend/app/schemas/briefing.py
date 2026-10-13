"""Briefing schemas."""

from pydantic import BaseModel, Field


class BriefingPreferences(BaseModel):
    opt_in: bool = Field(default=False)
    quiet_hours_start: int = Field(default=22, ge=0, le=23)  # 10 PM
    quiet_hours_end: int = Field(default=7, ge=0, le=23)  # 7 AM
    morning_time: str = Field(default="08:00")


class BriefingResponse(BaseModel):
    date: str
    greeting: str
    summary: str
    pending_tasks_count: int
    overdue_tasks_count: int
    tasks: list[dict]
    is_quiet_hours: bool = False
    opted_in: bool = True
