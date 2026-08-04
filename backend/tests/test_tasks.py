"""Tests for task endpoints and service."""

import pytest

from app.services.task_service import TaskService

pytestmark = pytest.mark.asyncio


class TestTaskService:
    """Tests for TaskService."""

    async def test_create_task(self, test_db, user):
        """Test creating a task."""
        async with test_db() as session:
            task = await TaskService.create_task(
                user_id=user.id,
                title="Learn Rust by Q1",
                description="Complete Rust fundamentals course",
                priority="high",
                session=session,
            )

            assert task.title == "Learn Rust by Q1"
            assert task.priority == "high"
            assert task.status == "pending"

    async def test_get_active_tasks(self, test_db, user):
        """Test retrieving active tasks."""
        async with test_db() as session:
            # Create tasks
            await TaskService.create_task(
                user_id=user.id,
                title="Task 1",
                session=session,
            )
            await TaskService.create_task(
                user_id=user.id,
                title="Task 2",
                session=session,
            )

            # Get tasks
            tasks = await TaskService.get_active_tasks(
                user_id=user.id,
                session=session,
            )

            assert len(tasks) == 2

    async def test_update_task(self, test_db, user):
        """Test updating a task."""
        async with test_db() as session:
            task = await TaskService.create_task(
                user_id=user.id,
                title="Original",
                session=session,
            )

            updated = await TaskService.update_task(
                user_id=user.id,
                task_id=str(task.id),
                title="Updated",
                session=session,
            )

            assert updated.title == "Updated"

    async def test_complete_task(self, test_db, user):
        """Test completing a task."""
        async with test_db() as session:
            task = await TaskService.create_task(
                user_id=user.id,
                title="Task",
                session=session,
            )

            completed = await TaskService.complete_task(
                user_id=user.id,
                task_id=str(task.id),
                session=session,
            )

            assert completed.status == "completed"
            assert completed.completed_at is not None

    async def test_get_task_stats(self, test_db, user):
        """Test task statistics."""
        async with test_db() as session:
            # Create tasks
            task1 = await TaskService.create_task(
                user_id=user.id,
                title="Task 1",
                session=session,
            )
            await TaskService.create_task(
                user_id=user.id,
                title="Task 2",
                session=session,
            )

            # Complete one
            await TaskService.complete_task(
                user_id=user.id,
                task_id=str(task1.id),
                session=session,
            )

            # Get stats
            stats = await TaskService.get_task_stats(
                user_id=user.id,
                session=session,
            )

            assert stats["total"] == 2
            assert stats["completed"] == 1
            assert stats["pending"] == 1
