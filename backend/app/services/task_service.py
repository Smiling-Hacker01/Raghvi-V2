"""Task service — business logic for task operations."""

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task, TaskPriority, TaskStatus

logger = logging.getLogger(__name__)


class TaskService:
    """Service for task operations."""

    @staticmethod
    async def create_task(
        user_id: str,
        title: str,
        description: str | None = None,
        priority: str = "medium",
        due_date: datetime | None = None,
        tags: str | None = None,
        auto_extracted: bool = False,
        session: AsyncSession = None,
    ) -> Task:
        """Create a new task.

        Args:
            user_id: User's UUID
            title: Task title
            description: Detailed description (optional)
            priority: Priority level (low, medium, high, urgent)
            due_date: Due date (optional)
            tags: Comma-separated tags (optional)
            auto_extracted: True if extracted from chat
            session: Database session

        Returns:
            Created Task object

        Raises:
            ValueError: If title is empty or invalid priority
        """
        # Validate
        if not title or not title.strip():
            raise ValueError("Task title cannot be empty")

        if priority not in [p.value for p in TaskPriority]:
            raise ValueError(f"Invalid priority: {priority}")

        # Create task
        task = Task(
            user_id=user_id,
            title=title.strip(),
            description=description,
            priority=priority,
            due_date=due_date,
            tags=tags,
            auto_extracted=auto_extracted,
        )

        session.add(task)
        await session.flush()
        await session.refresh(task)

        logger.info(
            f"Task created for user {user_id}: "
            f"id={task.id}, title={title}, auto_extracted={auto_extracted}"
        )

        return task

    @staticmethod
    async def get_active_tasks(
        user_id: str,
        status: str | None = None,
        session: AsyncSession = None,
    ) -> list[Task]:
        """Get active tasks for a user.

        Args:
            user_id: User's UUID
            status: Filter by status (optional)
            session: Database session

        Returns:
            List of Task objects
        """
        query = select(Task).where(
            and_(
                Task.user_id == user_id,
                Task.deleted_at.is_(None),
            )
        )

        if status:
            query = query.where(Task.status == status)

        query = query.order_by(Task.priority, Task.due_date)

        tasks = await session.scalars(query)
        return tasks.all()

    @staticmethod
    async def update_task(
        user_id: str,
        task_id: str,
        title: str | None = None,
        description: str | None = None,
        status: str | None = None,
        priority: str | None = None,
        due_date: datetime | None = None,
        tags: str | None = None,
        session: AsyncSession = None,
    ) -> Task:
        """Update a task.

        Args:
            user_id: User's UUID
            task_id: Task UUID (as string)
            title: New title (optional)
            description: New description (optional)
            status: New status (optional)
            priority: New priority (optional)
            due_date: New due date (optional)
            tags: New tags (optional)
            session: Database session

        Returns:
            Updated Task object

        Raises:
            ValueError: If task not found or invalid data
        """
        try:
            task_uuid = UUID(task_id)
        except ValueError as e:
            raise ValueError(f"Invalid task ID: {task_id}") from e

        task = await session.scalar(
            select(Task).where(
                and_(
                    Task.id == task_uuid,
                    Task.user_id == user_id,
                )
            )
        )

        if not task:
            raise ValueError(f"Task {task_id} not found")

        # Update fields
        if title is not None:
            task.title = title.strip()
        if description is not None:
            task.description = description
        if status is not None:
            task.status = status
            if status == TaskStatus.COMPLETED:
                task.completed_at = datetime.now(UTC).replace(tzinfo=None)
        if priority is not None:
            task.priority = priority
        if due_date is not None:
            task.due_date = due_date
        if tags is not None:
            task.tags = tags

        task.updated_at = datetime.now(UTC).replace(tzinfo=None)

        await session.commit()

        logger.info(f"Task {task_id} updated for user {user_id}")

        return task

    @staticmethod
    async def complete_task(
        user_id: str,
        task_id: str,
        session: AsyncSession = None,
    ) -> Task:
        """Mark task as completed.

        Args:
            user_id: User's UUID
            task_id: Task UUID (as string)
            session: Database session

        Returns:
            Updated Task object
        """
        return await TaskService.update_task(
            user_id=user_id,
            task_id=task_id,
            status=TaskStatus.COMPLETED,
            session=session,
        )

    @staticmethod
    async def delete_task(
        user_id: str,
        task_id: str,
        session: AsyncSession = None,
    ) -> None:
        """Soft delete a task.

        Args:
            user_id: User's UUID
            task_id: Task UUID (as string)
            session: Database session

        Raises:
            ValueError: If task not found
        """
        try:
            task_uuid = UUID(task_id)
        except ValueError as e:
            raise ValueError(f"Invalid task ID: {task_id}") from e

        task = await session.scalar(
            select(Task).where(
                and_(
                    Task.id == task_uuid,
                    Task.user_id == user_id,
                )
            )
        )

        if not task:
            raise ValueError(f"Task {task_id} not found")

        task.deleted_at = datetime.now(UTC).replace(tzinfo=None)
        await session.commit()

        logger.info(f"Task {task_id} deleted for user {user_id}")

    @staticmethod
    async def get_task_stats(
        user_id: str,
        session: AsyncSession = None,
    ) -> dict[str, int]:
        """Get task statistics for a user.

        Args:
            user_id: User's UUID
            session: Database session

        Returns:
            Dict with task counts by status
        """
        # Active tasks only
        where_clause = and_(
            Task.user_id == user_id,
            Task.deleted_at.is_(None),
        )

        total = await session.scalar(select(func.count(Task.id)).where(where_clause)) or 0

        pending = (
            await session.scalar(
                select(func.count(Task.id)).where(
                    and_(where_clause, Task.status == TaskStatus.PENDING)
                )
            )
            or 0
        )

        in_progress = (
            await session.scalar(
                select(func.count(Task.id)).where(
                    and_(where_clause, Task.status == TaskStatus.IN_PROGRESS)
                )
            )
            or 0
        )

        completed = (
            await session.scalar(
                select(func.count(Task.id)).where(
                    and_(where_clause, Task.status == TaskStatus.COMPLETED)
                )
            )
            or 0
        )

        # Overdue tasks (due_date < now and not completed)
        now = datetime.now(UTC).replace(tzinfo=None)
        overdue = (
            await session.scalar(
                select(func.count(Task.id)).where(
                    and_(
                        where_clause,
                        Task.due_date < now,
                        Task.status != TaskStatus.COMPLETED,
                    )
                )
            )
            or 0
        )

        return {
            "total": total,
            "pending": pending,
            "in_progress": in_progress,
            "completed": completed,
            "overdue": overdue,
        }
