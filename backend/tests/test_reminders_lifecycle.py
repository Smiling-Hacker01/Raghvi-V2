"""Tests for reminder lifecycle, snooze, dismiss, and completed/deleted task suppression."""

from datetime import UTC, datetime, timedelta

import pytest

from app.models.reminder import Reminder
from app.models.task import Task, TaskStatus
from app.services.reminder_service import ReminderService


@pytest.mark.asyncio
async def test_pending_reminders_filters_completed_and_deleted_tasks(test_db, user):
    """Verify completed or deleted tasks do not trigger pending reminders."""
    async with test_db() as session:
        now = datetime.now(UTC).replace(tzinfo=None)
        past_time = now - timedelta(hours=1)

        # 1. Create active task with reminder
        active_task = Task(
            user_id=str(user.id),
            title="Active Task",
            status=TaskStatus.PENDING,
            due_date=now + timedelta(days=1),
        )
        session.add(active_task)
        await session.flush()

        active_reminder = Reminder(
            task_id=active_task.id,
            user_id=str(user.id),
            reminder_time=past_time,
            sent=False,
        )
        session.add(active_reminder)

        # 2. Create completed task with reminder
        completed_task = Task(
            user_id=str(user.id),
            title="Completed Task",
            status=TaskStatus.COMPLETED,
            due_date=now + timedelta(days=1),
        )
        session.add(completed_task)
        await session.flush()

        completed_reminder = Reminder(
            task_id=completed_task.id,
            user_id=str(user.id),
            reminder_time=past_time,
            sent=False,
        )
        session.add(completed_reminder)

        # 3. Create deleted task with reminder
        deleted_task = Task(
            user_id=str(user.id),
            title="Deleted Task",
            status=TaskStatus.PENDING,
            deleted_at=now,
        )
        session.add(deleted_task)
        await session.flush()

        deleted_reminder = Reminder(
            task_id=deleted_task.id,
            user_id=str(user.id),
            reminder_time=past_time,
            sent=False,
        )
        session.add(deleted_reminder)

        await session.commit()

        # Fetch pending reminders
        pending = await ReminderService.get_pending_reminders(session)
        pending_task_ids = [r.task_id for r in pending]

        # Only active task reminder should be pending
        assert active_task.id in pending_task_ids
        assert completed_task.id not in pending_task_ids
        assert deleted_task.id not in pending_task_ids


@pytest.mark.asyncio
async def test_snooze_and_dismiss_reminder(test_db, user):
    """Verify snoozing extends reminder time and dismissing marks it sent."""
    async with test_db() as session:
        now = datetime.now(UTC).replace(tzinfo=None)
        task = Task(
            user_id=str(user.id),
            title="Test Task for Snooze",
            status=TaskStatus.PENDING,
        )
        session.add(task)
        await session.flush()

        reminder = Reminder(
            task_id=task.id,
            user_id=str(user.id),
            reminder_time=now - timedelta(minutes=5),
            sent=False,
        )
        session.add(reminder)
        await session.commit()

        # 1. Snooze for 15 minutes
        snoozed = await ReminderService.snooze_reminder(reminder.id, minutes=15, session=session)
        assert snoozed is not None
        assert snoozed.reminder_time > now
        assert snoozed.sent is False

        # 2. Dismiss reminder
        dismissed = await ReminderService.dismiss_reminder(reminder.id, session=session)
        assert dismissed is True

        refreshed = await session.get(Reminder, reminder.id)
        assert refreshed.sent is True
        assert refreshed.sent_at is not None
