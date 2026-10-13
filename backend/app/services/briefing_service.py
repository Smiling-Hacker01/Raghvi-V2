"""Briefing service — synthesizes proactive daily briefings."""

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.briefing import BriefingPreferences, BriefingResponse
from app.services.reminder_service import ReminderService
from app.services.task_service import TaskService

logger = logging.getLogger(__name__)


class BriefingService:
    """Generates proactive morning briefings respecting opt-in and quiet hours."""

    @staticmethod
    def is_in_quiet_hours(
        current_hour: int,
        quiet_start: int = 22,
        quiet_end: int = 7,
    ) -> bool:
        """Determine if current_hour is in quiet hours interval."""
        if quiet_start > quiet_end:
            # Over midnight: e.g. 22 to 7 -> hour >= 22 or hour < 7
            return current_hour >= quiet_start or current_hour < quiet_end
        else:
            return quiet_start <= current_hour < quiet_end

    @staticmethod
    async def get_daily_briefing(
        user: User,
        session: AsyncSession,
        current_dt: datetime | None = None,
    ) -> BriefingResponse:
        """Compile today's proactive briefing for user."""
        dt = current_dt or datetime.now(UTC)
        prefs = user.preferences or {}

        opt_in = prefs.get("briefing_opt_in", False)
        quiet_start = prefs.get("quiet_hours_start", 22)
        quiet_end = prefs.get("quiet_hours_end", 7)

        is_quiet = BriefingService.is_in_quiet_hours(
            dt.hour, quiet_start=quiet_start, quiet_end=quiet_end
        )

        user_name = user.name or user.username
        date_str = dt.strftime("%Y-%m-%d")

        if not opt_in:
            return BriefingResponse(
                date=date_str,
                greeting=f"Good day, {user_name}!",
                summary="Daily proactive briefings are disabled. Enable them in settings anytime.",
                pending_tasks_count=0,
                overdue_tasks_count=0,
                tasks=[],
                is_quiet_hours=is_quiet,
                opted_in=False,
            )

        # Retrieve active and overdue tasks
        pending_tasks = await TaskService.get_active_tasks(
            user_id=str(user.id),
            status="pending",
            session=session,
        )
        overdue_tasks = await ReminderService.get_user_overdue_tasks(
            user_id=str(user.id),
            session=session,
        )

        overdue_count = len(overdue_tasks)
        pending_count = len(pending_tasks)

        # Synthesize friendly Raghvi greeting
        time_greeting = (
            "Good morning"
            if 5 <= dt.hour < 12
            else "Good afternoon"
            if 12 <= dt.hour < 17
            else "Good evening"
        )
        greeting = f"{time_greeting}, {user_name}!"

        if pending_count == 0 and overdue_count == 0:
            summary = (
                "Your schedule is clear! You have no pending tasks right now. "
                "Enjoy your day or let me know if you want to plan something new."
            )
        else:
            summary_parts = []
            if overdue_count > 0:
                s_sfx = "s" if overdue_count > 1 else ""
                summary_parts.append(
                    f"You have {overdue_count} overdue task{s_sfx} that may need your attention."
                )
            if pending_count > 0:
                p_sfx = "s" if pending_count > 1 else ""
                summary_parts.append(f"You have {pending_count} pending task{p_sfx} on your list.")
            summary = " ".join(summary_parts)

        task_summaries: list[dict[str, Any]] = [
            {
                "id": str(t.id),
                "title": t.title,
                "priority": t.priority,
                "due_date": t.due_date.isoformat() if t.due_date else None,
            }
            for t in pending_tasks[:10]
        ]

        return BriefingResponse(
            date=date_str,
            greeting=greeting,
            summary=summary,
            pending_tasks_count=pending_count,
            overdue_tasks_count=overdue_count,
            tasks=task_summaries,
            is_quiet_hours=is_quiet,
            opted_in=True,
        )

    @staticmethod
    async def update_preferences(
        user: User,
        prefs: BriefingPreferences,
        session: AsyncSession,
    ) -> BriefingPreferences:
        """Update briefing opt-in and quiet hours preferences."""
        current_prefs = dict(user.preferences or {})
        current_prefs["briefing_opt_in"] = prefs.opt_in
        current_prefs["quiet_hours_start"] = prefs.quiet_hours_start
        current_prefs["quiet_hours_end"] = prefs.quiet_hours_end
        current_prefs["morning_time"] = prefs.morning_time

        user.preferences = current_prefs
        await session.commit()
        return prefs
