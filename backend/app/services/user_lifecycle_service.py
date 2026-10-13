"""User lifecycle service — GDPR data export and permanent account deletion (M7)."""

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.action import ActionProposal
from app.models.conversation import Conversation
from app.models.memory import Memory
from app.models.message import Message
from app.models.payment import PaymentTransaction
from app.models.refresh_token import RefreshToken
from app.models.reminder import Reminder
from app.models.subscription import UserSubscription
from app.models.task import Task
from app.models.user import User
from app.models.voice import UserVoice

logger = logging.getLogger(__name__)


class UserLifecycleService:
    """Manages privacy compliance, data export, and full account erasure."""

    @staticmethod
    async def export_user_data(user: User, session: AsyncSession) -> dict[str, Any]:
        """Generate structured JSON export of all user-owned data."""
        user_id_str = str(user.id)

        # 1. Profile
        profile_data = {
            "id": user_id_str,
            "username": user.username,
            "email": user.email,
            "name": user.name,
            "phone": user.phone,
            "preferences": user.preferences or {},
            "created_at": user.created_at.isoformat()
            if hasattr(user, "created_at") and user.created_at
            else None,
        }

        # 2. Conversations & Messages
        conversations_res = await session.scalars(
            select(Conversation).where(Conversation.user_id == user_id_str)
        )
        conversations = conversations_res.all()

        exported_conversations = []
        for conv in conversations:
            messages_res = await session.scalars(
                select(Message)
                .where(Message.conversation_id == conv.id)
                .order_by(Message.created_at.asc())
            )
            exported_conversations.append(
                {
                    "id": str(conv.id),
                    "title": conv.title,
                    "created_at": conv.created_at.isoformat(),
                    "messages": [
                        {
                            "id": str(m.id),
                            "role": m.role,
                            "content": m.content,
                            "tokens_used": m.tokens_used,
                            "created_at": m.created_at.isoformat(),
                        }
                        for m in messages_res.all()
                    ],
                }
            )

        # 3. Memories
        memories_res = await session.scalars(select(Memory).where(Memory.user_id == user_id_str))
        exported_memories = [
            {
                "id": str(mem.id),
                "content": mem.content,
                "is_sensitive": mem.is_sensitive,
                "is_approved": mem.is_approved,
                "created_at": mem.created_at.isoformat(),
            }
            for mem in memories_res.all()
            if mem.deleted_at is None
        ]

        # 4. Tasks & Reminders
        tasks_res = await session.scalars(select(Task).where(Task.user_id == user_id_str))
        exported_tasks = [
            {
                "id": str(t.id),
                "title": t.title,
                "description": t.description,
                "status": t.status,
                "priority": t.priority,
                "due_date": t.due_date.isoformat() if t.due_date else None,
                "completed_at": t.completed_at.isoformat() if t.completed_at else None,
            }
            for t in tasks_res.all()
            if t.deleted_at is None
        ]

        reminders_res = await session.scalars(
            select(Reminder).where(Reminder.user_id == user_id_str)
        )
        exported_reminders = [
            {
                "id": str(r.id),
                "task_id": str(r.task_id),
                "reminder_type": str(r.reminder_type),
                "reminder_time": r.reminder_time.isoformat(),
                "sent": r.sent,
            }
            for r in reminders_res.all()
        ]

        # 5. Subscriptions & Payments
        subs_res = await session.scalars(
            select(UserSubscription).where(UserSubscription.user_id == user_id_str)
        )
        exported_subs = [
            {
                "tier": s.tier,
                "status": s.status,
                "current_period_end": s.current_period_end.isoformat()
                if s.current_period_end
                else None,
            }
            for s in subs_res.all()
        ]

        tx_res = await session.scalars(
            select(PaymentTransaction).where(PaymentTransaction.user_id == user_id_str)
        )
        exported_txs = [
            {
                "id": str(tx.id),
                "provider": tx.provider_name,
                "amount": tx.amount,
                "currency": tx.currency,
                "status": tx.status,
                "created_at": tx.created_at.isoformat(),
            }
            for tx in tx_res.all()
        ]

        logger.info(f"Generated user data export bundle for user {user_id_str}")

        return {
            "export_version": "1.0",
            "exported_at": datetime.now(UTC).isoformat(),
            "profile": profile_data,
            "conversations": exported_conversations,
            "memories": exported_memories,
            "tasks": exported_tasks,
            "reminders": exported_reminders,
            "subscriptions": exported_subs,
            "transactions": exported_txs,
        }

    @staticmethod
    async def delete_user_account(user: User, session: AsyncSession) -> None:
        """Permanently delete user account and cascade delete all associated data."""
        user_id_str = str(user.id)
        logger.warning(f"Initiating permanent deletion for user account {user_id_str}")

        # 1. Delete messages in user conversations
        conv_ids_res = await session.scalars(
            select(Conversation.id).where(Conversation.user_id == user_id_str)
        )
        conv_ids = conv_ids_res.all()
        if conv_ids:
            await session.execute(delete(Message).where(Message.conversation_id.in_(conv_ids)))
        await session.execute(delete(Conversation).where(Conversation.user_id == user_id_str))

        # 2. Delete memories
        await session.execute(delete(Memory).where(Memory.user_id == user_id_str))

        # 3. Delete tasks and reminders
        await session.execute(delete(Reminder).where(Reminder.user_id == user_id_str))
        await session.execute(delete(Task).where(Task.user_id == user_id_str))

        # 4. Delete action proposals
        await session.execute(delete(ActionProposal).where(ActionProposal.user_id == user_id_str))

        # 5. Delete custom voices
        await session.execute(delete(UserVoice).where(UserVoice.user_id == user_id_str))

        # 6. Delete subscriptions & transactions
        await session.execute(
            delete(UserSubscription).where(UserSubscription.user_id == user_id_str)
        )
        await session.execute(
            delete(PaymentTransaction).where(PaymentTransaction.user_id == user_id_str)
        )

        # 7. Delete refresh tokens (revoking all sessions)
        await session.execute(delete(RefreshToken).where(RefreshToken.user_id == user_id_str))

        # 8. Delete user record
        await session.delete(user)
        await session.commit()

        logger.info(f"User account {user_id_str} and all associated records permanently erased.")
