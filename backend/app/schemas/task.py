"""Pydantic schemas for task operations."""

from datetime import datetime

from pydantic import BaseModel, Field


class TaskCreateRequest(BaseModel):
    """Request to create a new task."""

    title: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Task title",
        json_schema_extra={"example": "Learn Rust by end of Q1"},
    )
    description: str | None = Field(None, max_length=2000, description="Detailed task description")
    priority: str = Field("medium", description="Task priority: low, medium, high, urgent")
    due_date: datetime | None = Field(None, description="Due date (ISO 8601)")
    tags: str | None = Field(None, description="Comma-separated tags")


class TaskResponse(BaseModel):
    """Response model for a task."""

    id: str
    title: str
    description: str | None
    status: str
    priority: str
    created_at: str
    updated_at: str
    due_date: str | None
    completed_at: str | None
    tags: str | None
    auto_extracted: bool


class TaskListResponse(BaseModel):
    """Response for listing tasks."""

    tasks: list[TaskResponse]
    total: int
    pending_count: int
    in_progress_count: int
    completed_count: int


class TaskUpdateRequest(BaseModel):
    """Request to update a task."""

    title: str | None = None
    description: str | None = None
    status: str | None = None
    priority: str | None = None
    due_date: datetime | None = None
    tags: str | None = None


class TaskStatsResponse(BaseModel):
    """Task statistics."""

    total: int
    pending: int
    in_progress: int
    completed: int
    overdue: int
