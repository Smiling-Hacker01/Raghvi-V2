"""Reminder service — task notifications and due date alerts."""

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reminder import Reminder, ReminderType
from app.models.task import Task, TaskStatus

logger = logging.getLogger(__name__)


class ReminderService:
    """Service for task reminders."""

    @staticmethod
    async def create_reminder(
        task_id: str | UUID,
        user_id: str | UUID,
        reminder_time: datetime,
        reminder_type: str = ReminderType.DUE_SOON,
        session: AsyncSession = None,
    ) -> Reminder:
        """Create a reminder for a task.

        Args:
            task_id: Task UUID
            user_id: User UUID
            reminder_time: When to remind
            reminder_type: Type of reminder
            session: Database session

        Returns:
            Created Reminder
        """
        task_uuid = UUID(str(task_id)) if not isinstance(task_id, UUID) else task_id
        user_id_str = str(user_id)

        reminder = Reminder(
            task_id=task_uuid,
            user_id=user_id_str,
            reminder_time=reminder_time,
            reminder_type=reminder_type,
        )

        session.add(reminder)
        await session.flush()

        logger.info(f"Created reminder for task {task_uuid}")

        return reminder

    @staticmethod
    async def auto_create_reminders_for_task(
        task: Task,
        session: AsyncSession,
    ) -> None:
        """Auto-create reminders for a task based on due date.

        Creates:
        - 1 day before due date
        - On due date

        Args:
            task: Task object
            session: Database session
        """
        if not task.due_date or task.is_completed:
            return

        now = datetime.now(UTC).replace(tzinfo=None)

        # Reminder 1 day before
        one_day_before = task.due_date - timedelta(days=1)
        if one_day_before > now:
            await ReminderService.create_reminder(
                task_id=str(task.id),
                user_id=str(task.user_id),
                reminder_time=one_day_before,
                reminder_type=ReminderType.DUE_SOON,
                session=session,
            )

        # Reminder on due date
        if task.due_date > now:
            await ReminderService.create_reminder(
                task_id=str(task.id),
                user_id=str(task.user_id),
                reminder_time=task.due_date,
                reminder_type=ReminderType.DUE_SOON,
                session=session,
            )

    @staticmethod
    async def get_pending_reminders(
        session: AsyncSession,
    ) -> list[Reminder]:
        """Get reminders that should be sent now.

        Returns:
            List of unsent reminders past their reminder_time
        """
        now = datetime.now(UTC).replace(tzinfo=None)

        reminders = await session.scalars(
            select(Reminder).where(
                and_(
                    ~Reminder.sent,
                    Reminder.reminder_time <= now,
                )
            )
        )

        return reminders.all()

    @staticmethod
    async def mark_reminder_sent(
        reminder: Reminder,
        session: AsyncSession,
    ) -> None:
        """Mark reminder as sent.

        Args:
            reminder: Reminder object
            session: Database session
        """
        reminder.sent = True
        reminder.sent_at = datetime.now(UTC).replace(tzinfo=None)
        await session.commit()

        logger.info(f"Reminder {reminder.id} marked as sent")

    @staticmethod
    async def get_user_overdue_tasks(
        user_id: str | UUID,
        session: AsyncSession,
    ) -> list[Task]:
        """Get overdue tasks for a user.

        Args:
            user_id: User UUID
            session: Database session

        Returns:
            List of overdue Task objects
        """
        now = datetime.now(UTC).replace(tzinfo=None)
        user_id_str = str(user_id)

        tasks = await session.scalars(
            select(Task).where(
                and_(
                    Task.user_id == user_id_str,
                    Task.due_date < now,
                    Task.status != TaskStatus.COMPLETED,
                    Task.deleted_at.is_(None),
                )
            )
        )

        return tasks.all()
