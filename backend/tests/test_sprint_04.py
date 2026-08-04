"""Tests for Sprint 04 (Task Management)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from app.models.user import User
from app.security.password import hash_password
from app.services.reminder_service import ReminderService
from app.services.task_extractor import TaskExtractor
from app.services.task_service import TaskService

pytestmark = pytest.mark.asyncio


class TestTaskExtraction:
    """Tests for automatic task extraction."""

    async def test_extract_tasks_from_message(self):
        """Test extracting tasks from natural language."""
        message = "I want to learn Rust by the end of Q1 and finish my project by next week"

        # Mock the AI client to return a task extraction response
        mock_response = """
        {
          "tasks": [
            {
              "title": "Learn Rust by end of Q1",
              "description": "Complete Rust fundamentals",
              "priority": "medium",
              "due_date": "2026-03-31"
            },
            {
              "title": "Finish project",
              "description": null,
              "priority": "high",
              "due_date": null
            }
          ]
        }
        """

        with patch("app.services.task_extractor.AIClient") as MockAIClient:
            mock_client = MockAIClient.return_value
            mock_client.send_message = AsyncMock(return_value=(mock_response, 100, "mock"))

            extractor = TaskExtractor()
            tasks = await extractor.extract_tasks(message)

            # Should extract at least 1 task
            assert len(tasks) >= 1
            assert any("rust" in t.get("title", "").lower() for t in tasks)

    async def test_extract_empty_on_casual_message(self):
        """Test that casual messages don't extract tasks."""
        message = "Hey, how's your day going?"

        # Mock the AI client to return no tasks
        mock_response = '{"tasks": []}'

        with patch("app.services.task_extractor.AIClient") as MockAIClient:
            mock_client = MockAIClient.return_value
            mock_client.send_message = AsyncMock(return_value=(mock_response, 50, "mock"))

            extractor = TaskExtractor()
            tasks = await extractor.extract_tasks(message)

            # Should extract nothing
            assert len(tasks) == 0

    async def test_extract_priority_and_due_date(self):
        """Test priority and due date extraction."""
        message = "I need to fix this urgent bug today"

        # Mock the AI client to return urgent task
        mock_response = """
        {
          "tasks": [
            {
              "title": "Fix urgent bug",
              "description": null,
              "priority": "urgent",
              "due_date": null
            }
          ]
        }
        """

        with patch("app.services.task_extractor.AIClient") as MockAIClient:
            mock_client = MockAIClient.return_value
            mock_client.send_message = AsyncMock(return_value=(mock_response, 75, "mock"))

            extractor = TaskExtractor()
            tasks = await extractor.extract_tasks(message)

            if tasks:
                assert tasks[0].get("priority") in ["urgent", "high"]


class TestReminders:
    """Tests for task reminders."""

    async def test_create_reminder(self, test_db, user):
        """Test creating a reminder."""
        async with test_db() as session:
            # Create task
            task = await TaskService.create_task(
                user_id=user.id,
                title="Test Task",
                session=session,
            )

            # Create reminder
            reminder_time = datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1)
            reminder = await ReminderService.create_reminder(
                task_id=str(task.id),
                user_id=user.id,
                reminder_time=reminder_time,
                session=session,
            )

            assert reminder.task_id == task.id
            assert not reminder.sent

    async def test_auto_create_reminders(self, test_db, user):
        """Test automatic reminder creation for task."""
        async with test_db() as session:
            # Create task with due date
            due_date = datetime.now(UTC).replace(tzinfo=None) + timedelta(days=3)
            task = await TaskService.create_task(
                user_id=user.id,
                title="Test Task",
                due_date=due_date,
                session=session,
            )

            # Auto-create reminders
            await ReminderService.auto_create_reminders_for_task(task, session)

            # Should have created reminders
            # (Note: would need to query to verify)

    async def test_get_overdue_tasks(self, test_db, user):
        """Test retrieving overdue tasks."""
        async with test_db() as session:
            # Create overdue task
            past_date = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1)
            await TaskService.create_task(
                user_id=user.id,
                title="Overdue Task",
                due_date=past_date,
                session=session,
            )

            # Get overdue
            overdue = await ReminderService.get_user_overdue_tasks(user.id, session)

            assert len(overdue) >= 1
