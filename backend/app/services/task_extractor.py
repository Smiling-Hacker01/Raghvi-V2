"""Automatic task extraction from chat messages using LLM."""

import json
import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task
from app.services.ai.client import AIClient

logger = logging.getLogger(__name__)


class TaskExtractor:
    """Extract tasks from user messages using LLM.

    Features:
    - Understands natural language goals
    - Extracts title, description, priority, due dates
    - Lightweight and fast (temperature=0, 200 tokens)
    - Graceful failures (returns empty list if no tasks found)
    """

    EXTRACTION_PROMPT = """You are an expert at identifying goals and tasks from conversations.

Analyze the user's message and extract any tasks, goals, or action items they want to accomplish.

For each task found, return a JSON object with:
{{
  "tasks": [
    {{
      "title": "Brief task name (max 100 chars)",
      "description": "Detailed description if mentioned",
      "priority": "low|medium|high|urgent",
      "due_date": "YYYY-MM-DD or null if not mentioned"
    }}
  ]
}}

Guidelines:
- Extract only explicit goals/tasks, not casual mentions
- Priority: high for "urgent/ASAP/immediately", urgent for "today/tomorrow",
  medium for "soon", low for "eventually/when I have time"
- Due dates: Parse natural language ("end of Q1" → March 31, "next month" → +30 days)
- Return empty tasks list if no goals mentioned
- Be conservative: only extract if clearly stated

User message: "{user_message}"

Return ONLY valid JSON, no other text."""

    @staticmethod
    async def extract_tasks(
        user_message: str,
        session: AsyncSession = None,
    ) -> list[dict]:
        """Extract tasks from user message.

        Args:
            user_message: User's chat message
            session: Database session (for storing)

        Returns:
            List of extracted task dicts
        """
        if not user_message or len(user_message) < 10:
            return []

        try:
            # Create extraction prompt
            prompt = TaskExtractor.EXTRACTION_PROMPT.format(user_message=user_message)

            # Call LLM with temperature=0 for deterministic extraction
            client = AIClient()
            response, _, _ = await client.send_message(
                messages=[{"role": "user", "content": prompt}],
                system_prompt="You are a task extraction system. Return only valid JSON.",
            )

            # Parse JSON response
            response = response.strip()

            # Extract JSON from response (in case there's extra text)
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()

            extracted = json.loads(response)
            tasks = extracted.get("tasks", [])

            logger.info(f"Extracted {len(tasks)} tasks from message")

            return tasks

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse task extraction JSON: {e}")
            return []
        except Exception as e:
            logger.error(f"Task extraction failed: {e}")
            return []

    @staticmethod
    async def create_tasks_from_extraction(
        user_id: str,
        extracted_tasks: list[dict],
        session: AsyncSession,
    ) -> list[Task]:
        """Create Task records from extracted data.

        Args:
            user_id: User's UUID
            extracted_tasks: List of task dicts from extractor
            session: Database session

        Returns:
            List of created Task objects
        """
        from app.services.reminder_service import ReminderService
        from app.services.task_service import TaskService

        created_tasks = []

        for task_data in extracted_tasks:
            try:
                # Parse due date
                due_date = None
                if task_data.get("due_date"):
                    try:
                        due_date = datetime.fromisoformat(task_data["due_date"])
                    except ValueError:
                        logger.warning(f"Invalid due date format: {task_data['due_date']}")

                # Create task
                task = await TaskService.create_task(
                    user_id=user_id,
                    title=task_data.get("title", "Untitled Task"),
                    description=task_data.get("description"),
                    priority=task_data.get("priority", "medium"),
                    due_date=due_date,
                    auto_extracted=True,
                    session=session,
                )

                if task.due_date:
                    await ReminderService.auto_create_reminders_for_task(task, session)

                created_tasks.append(task)
                logger.info(f"Created task: {task.title}")

            except Exception as e:
                logger.error(f"Failed to create task: {e}")
                continue

        # Commit all at once
        if created_tasks:
            await session.commit()

        return created_tasks


def get_task_extractor() -> TaskExtractor:
    """Get task extractor instance."""
    return TaskExtractor()
