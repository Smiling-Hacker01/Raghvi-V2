"""Task endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.task import (
    TaskCreateRequest,
    TaskListResponse,
    TaskResponse,
    TaskStatsResponse,
    TaskUpdateRequest,
)
from app.services.task_service import TaskService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["tasks"])

CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(
    request: TaskCreateRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> TaskResponse:
    """Create a new task."""
    try:
        task = await TaskService.create_task(
            user_id=str(current_user.id),
            title=request.title,
            description=request.description,
            priority=request.priority,
            due_date=request.due_date,
            tags=request.tags,
            session=session,
        )

        await session.commit()

        return TaskResponse(
            id=str(task.id),
            title=task.title,
            description=task.description,
            status=task.status,
            priority=task.priority,
            created_at=task.created_at.isoformat(),
            updated_at=task.updated_at.isoformat(),
            due_date=task.due_date.isoformat() if task.due_date else None,
            completed_at=task.completed_at.isoformat() if task.completed_at else None,
            tags=task.tags,
            auto_extracted=task.auto_extracted,
        )

    except ValueError as e:
        logger.error(f"Task creation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Failed to create task: {e}")
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create task",
        ) from e


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    status: str | None = None,
    current_user: CurrentUser = None,
    session: DbSession = None,
) -> TaskListResponse:
    """Get tasks for current user."""
    try:
        tasks = await TaskService.get_active_tasks(
            user_id=str(current_user.id),
            status=status,
            session=session,
        )

        stats = await TaskService.get_task_stats(
            user_id=str(current_user.id),
            session=session,
        )

        return TaskListResponse(
            tasks=[
                TaskResponse(
                    id=str(t.id),
                    title=t.title,
                    description=t.description,
                    status=t.status,
                    priority=t.priority,
                    created_at=t.created_at.isoformat(),
                    updated_at=t.updated_at.isoformat(),
                    due_date=t.due_date.isoformat() if t.due_date else None,
                    completed_at=t.completed_at.isoformat() if t.completed_at else None,
                    tags=t.tags,
                    auto_extracted=t.auto_extracted,
                )
                for t in tasks
            ],
            total=stats["total"],
            pending_count=stats["pending"],
            in_progress_count=stats["in_progress"],
            completed_count=stats["completed"],
        )

    except Exception as e:
        logger.error(f"Failed to list tasks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load tasks",
        ) from e


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    request: TaskUpdateRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> TaskResponse:
    """Update a task."""
    try:
        task = await TaskService.update_task(
            user_id=str(current_user.id),
            task_id=task_id,
            title=request.title,
            description=request.description,
            status=request.status,
            priority=request.priority,
            due_date=request.due_date,
            tags=request.tags,
            session=session,
        )

        return TaskResponse(
            id=str(task.id),
            title=task.title,
            description=task.description,
            status=task.status,
            priority=task.priority,
            created_at=task.created_at.isoformat(),
            updated_at=task.updated_at.isoformat(),
            due_date=task.due_date.isoformat() if task.due_date else None,
            completed_at=task.completed_at.isoformat() if task.completed_at else None,
            tags=task.tags,
            auto_extracted=task.auto_extracted,
        )

    except ValueError as e:
        logger.error(f"Task update error: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Failed to update task: {e}")
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update task",
        ) from e


@router.post("/{task_id}/complete", response_model=TaskResponse)
async def complete_task(
    task_id: str,
    current_user: CurrentUser,
    session: DbSession,
) -> TaskResponse:
    """Mark task as completed."""
    try:
        task = await TaskService.complete_task(
            user_id=str(current_user.id),
            task_id=task_id,
            session=session,
        )

        return TaskResponse(
            id=str(task.id),
            title=task.title,
            description=task.description,
            status=task.status,
            priority=task.priority,
            created_at=task.created_at.isoformat(),
            updated_at=task.updated_at.isoformat(),
            due_date=task.due_date.isoformat() if task.due_date else None,
            completed_at=task.completed_at.isoformat() if task.completed_at else None,
            tags=task.tags,
            auto_extracted=task.auto_extracted,
        )

    except ValueError as e:
        logger.error(f"Task completion error: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Failed to complete task: {e}")
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete task",
        ) from e


@router.delete("/{task_id}", status_code=204)
async def delete_task(
    task_id: str,
    current_user: CurrentUser,
    session: DbSession,
) -> None:
    """Delete a task."""
    try:
        await TaskService.delete_task(
            user_id=str(current_user.id),
            task_id=task_id,
            session=session,
        )

    except ValueError as e:
        logger.error(f"Task deletion error: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Failed to delete task: {e}")
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete task",
        ) from e


@router.get("/stats", response_model=TaskStatsResponse)
async def get_stats(
    current_user: CurrentUser,
    session: DbSession,
) -> TaskStatsResponse:
    """Get task statistics."""
    try:
        stats = await TaskService.get_task_stats(
            user_id=str(current_user.id),
            session=session,
        )
        return TaskStatsResponse(**stats)

    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load statistics",
        ) from e
