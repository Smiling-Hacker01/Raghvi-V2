"""Memory service — business logic for memory operations with sensitivity detection."""

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import Memory
from app.services.memory.rules.engine import get_sensitivity_engine

logger = logging.getLogger(__name__)


def get_utc_now():
    return datetime.now(UTC).replace(tzinfo=None)


class MemoryService:
    """Service for memory operations with automatic approval logic.

    Features:
    - Automatic approval for non-sensitive content
    - User approval required for sensitive content
    - Critical content flagged and never auto-approved
    - Soft deletes (data retention)
    - Statistics and filtering
    """

    @staticmethod
    async def create_memory(
        user_id: str,
        content: str,
        user_password: str | None = None,
        session: AsyncSession = None,
    ) -> tuple[Memory, bool, dict]:
        """Create a new memory with automatic approval and optional encryption.

        Auto-approval logic:
        - PUBLIC (score < 50): Auto-approved immediately
        - SENSITIVE (50 <= score < 100): Pending user approval
        - CRITICAL (score >= 100): Flagged, never auto-approved

        Auto-encryption logic:
        - CRITICAL + user_password provided: Content is AES-256-GCM encrypted

        Args:
            user_id: User's UUID as string
            content: Memory content
            user_password: Optional password for encrypting critical data
            session: Database session

        Returns:
            Tuple of (Memory, is_auto_approved, detection_result)

        Raises:
            ValueError: If content is invalid
        """
        from app.services.memory.encryption import get_encryption_service

        # Analyze content for sensitivity
        engine = get_sensitivity_engine()

        try:
            detection = engine.analyze(content)
        except ValueError as e:
            logger.warning(f"Memory content validation failed: {e}")
            raise ValueError(f"Invalid memory content: {e}") from e

        logger.info(
            f"Memory analysis for user {user_id}: "
            f"severity={detection.severity_level}, "
            f"score={detection.total_score}, "
            f"rules_matched={len(detection.matched_rules)}"
        )

        # Encrypt critical content if password provided
        stored_content = content
        is_encrypted = False

        if detection.severity_level == "critical" and user_password is not None:
            try:
                encryption_service = get_encryption_service()
                stored_content = encryption_service.encrypt_to_storage(content, user_password)
                is_encrypted = True
                logger.info(f"Memory for user {user_id}: critical data auto-encrypted")
            except Exception as e:
                logger.error(f"Encryption failed, storing unencrypted: {e}")
                is_encrypted = False

        # Create memory object
        # approved_at is set immediately for public (non-sensitive) content
        # approved_at is NULL (pending) for sensitive/critical content
        memory = Memory(
            user_id=user_id,
            content=stored_content,
            is_sensitive=detection.is_sensitive,
            is_encrypted=is_encrypted,
            approved_at=(get_utc_now() if not detection.requires_approval else None),
        )

        session.add(memory)
        await session.flush()  # Get the ID without committing
        await session.refresh(memory)

        is_auto_approved = not detection.requires_approval

        # Build detection result dict for API response
        detection_result = {
            "severity_level": detection.severity_level,
            "is_sensitive": detection.is_sensitive,
            "requires_approval": detection.requires_approval,
            "total_score": detection.total_score,
            "matched_rules": [r.rule_name for r in detection.matched_rules],
            "reason": detection.reason,
            "is_encrypted": is_encrypted,
        }

        logger.info(
            f"Memory {memory.id} created: "
            f"auto_approved={is_auto_approved}, "
            f"severity={detection.severity_level}, "
            f"score={detection.total_score}"
        )

        return memory, is_auto_approved, detection_result

    @staticmethod
    async def approve_memory(
        user_id: str,
        memory_id: str,
        session: AsyncSession,
    ) -> Memory:
        """Approve a pending memory.

        Args:
            user_id: User's UUID
            memory_id: Memory UUID to approve (as string)
            session: Database session

        Returns:
            Approved Memory object

        Raises:
            ValueError: If memory not found, already approved, or doesn't belong to user
        """
        try:
            memory_uuid = UUID(memory_id)
        except ValueError as e:
            raise ValueError(f"Invalid memory ID format: {memory_id}") from e

        # Fetch memory (must exist and belong to user)
        memory = await session.scalar(
            select(Memory).where(
                and_(
                    Memory.id == memory_uuid,
                    Memory.user_id == user_id,
                )
            )
        )

        if not memory:
            raise ValueError(f"Memory {memory_id} not found")

        if memory.is_approved:
            raise ValueError(f"Memory {memory_id} is already approved")

        if memory.deleted_at is not None:
            raise ValueError(f"Cannot approve a deleted memory {memory_id}")

        # Approve it
        memory.approved_at = get_utc_now()
        await session.commit()

        logger.info(f"Memory {memory_id} approved by user {user_id}")

        return memory

    @staticmethod
    async def reject_memory(
        user_id: str,
        memory_id: str,
        session: AsyncSession,
    ) -> None:
        """Reject (soft-delete) a pending memory.

        The memory is not hard-deleted (soft delete via deleted_at timestamp)
        so it can be recovered if needed.

        Args:
            user_id: User's UUID
            memory_id: Memory UUID to reject (as string)
            session: Database session

        Raises:
            ValueError: If memory not found, already approved, or doesn't belong to user
        """
        try:
            memory_uuid = UUID(memory_id)
        except ValueError as e:
            raise ValueError(f"Invalid memory ID format: {memory_id}") from e

        memory = await session.scalar(
            select(Memory).where(
                and_(
                    Memory.id == memory_uuid,
                    Memory.user_id == user_id,
                )
            )
        )

        if not memory:
            raise ValueError(f"Memory {memory_id} not found")

        if memory.is_approved:
            raise ValueError(
                f"Cannot reject an already-approved memory {memory_id}. "
                f"Use delete endpoint instead."
            )

        # Soft delete by setting deleted_at
        memory.deleted_at = get_utc_now()
        await session.commit()

        logger.info(f"Memory {memory_id} rejected by user {user_id}")

    @staticmethod
    async def get_approved_memories(
        user_id: str,
        limit: int = 50,
        session: AsyncSession = None,
    ) -> list[Memory]:
        """Get all approved (active) memories for a user.

        Returns only:
        - approved_at is NOT NULL (user approved)
        - deleted_at is NULL (not soft-deleted)

        Ordered newest first.

        Args:
            user_id: User's UUID
            limit: Max memories to retrieve (capped at 1000)
            session: Database session

        Returns:
            List of approved Memory objects
        """
        limit = min(limit, 1000)  # Cap to prevent abuse

        memories = await session.scalars(
            select(Memory)
            .where(
                and_(
                    Memory.user_id == user_id,
                    Memory.approved_at.is_not(None),  # Approved
                    Memory.deleted_at.is_(None),  # Not deleted
                )
            )
            .order_by(Memory.created_at.desc())
            .limit(limit)
        )

        return memories.all()

    @staticmethod
    async def get_pending_memories(
        user_id: str,
        session: AsyncSession,
    ) -> list[Memory]:
        """Get all pending memories awaiting user approval.

        Returns only:
        - approved_at is NULL (pending approval)
        - deleted_at is NULL (not rejected)

        Ordered newest first.

        Args:
            user_id: User's UUID
            session: Database session

        Returns:
            List of pending Memory objects
        """
        memories = await session.scalars(
            select(Memory)
            .where(
                and_(
                    Memory.user_id == user_id,
                    Memory.approved_at.is_(None),  # Not approved
                    Memory.deleted_at.is_(None),  # Not rejected/deleted
                )
            )
            .order_by(Memory.created_at.desc())
        )

        return memories.all()

    @staticmethod
    async def get_memory_stats(
        user_id: str,
        session: AsyncSession,
    ) -> dict[str, int]:
        """Get memory statistics for a user.

        Args:
            user_id: User's UUID
            session: Database session

        Returns:
            Dict with counts:
                - total: All memories (including deleted)
                - approved: Approved and active
                - pending: Pending approval
                - deleted: Soft-deleted memories
        """
        total = (
            await session.scalar(select(func.count(Memory.id)).where(Memory.user_id == user_id))
            or 0
        )

        approved = (
            await session.scalar(
                select(func.count(Memory.id)).where(
                    and_(
                        Memory.user_id == user_id,
                        Memory.approved_at.is_not(None),
                        Memory.deleted_at.is_(None),
                    )
                )
            )
            or 0
        )

        pending = (
            await session.scalar(
                select(func.count(Memory.id)).where(
                    and_(
                        Memory.user_id == user_id,
                        Memory.approved_at.is_(None),
                        Memory.deleted_at.is_(None),
                    )
                )
            )
            or 0
        )

        deleted = (
            await session.scalar(
                select(func.count(Memory.id)).where(
                    and_(
                        Memory.user_id == user_id,
                        Memory.deleted_at.is_not(None),
                    )
                )
            )
            or 0
        )

        return {
            "total": total,
            "approved": approved,
            "pending": pending,
            "deleted": deleted,
        }

    @staticmethod
    async def delete_memory(
        user_id: str,
        memory_id: str,
        session: AsyncSession,
    ) -> None:
        """Soft-delete an approved memory.

        User can only delete memories they've already approved.
        Uses soft delete (deleted_at timestamp) for audit trail.

        Args:
            user_id: User's UUID
            memory_id: Memory UUID to delete (as string)
            session: Database session

        Raises:
            ValueError: If memory not found, not approved, or doesn't belong to user
        """
        try:
            memory_uuid = UUID(memory_id)
        except ValueError as e:
            raise ValueError(f"Invalid memory ID format: {memory_id}") from e

        memory = await session.scalar(
            select(Memory).where(
                and_(
                    Memory.id == memory_uuid,
                    Memory.user_id == user_id,
                )
            )
        )

        if not memory:
            raise ValueError(f"Memory {memory_id} not found")

        if not memory.is_approved:
            raise ValueError(
                f"Cannot delete a pending memory {memory_id}. Use reject endpoint instead."
            )

        if memory.deleted_at is not None:
            raise ValueError(f"Memory {memory_id} is already deleted")

        # Soft delete
        memory.deleted_at = get_utc_now()
        await session.commit()

        logger.info(f"Memory {memory_id} deleted by user {user_id}")

    @staticmethod
    async def get_memory_by_id(
        user_id: str,
        memory_id: str,
        session: AsyncSession,
    ) -> Memory:
        """Get a single memory by ID (must belong to user).

        Args:
            user_id: User's UUID
            memory_id: Memory UUID (as string)
            session: Database session

        Returns:
            Memory object

        Raises:
            ValueError: If memory not found or doesn't belong to user
        """
        try:
            memory_uuid = UUID(memory_id)
        except ValueError as e:
            raise ValueError(f"Invalid memory ID format: {memory_id}") from e

        memory = await session.scalar(
            select(Memory).where(
                and_(
                    Memory.id == memory_uuid,
                    Memory.user_id == user_id,
                )
            )
        )

        if not memory:
            raise ValueError(f"Memory {memory_id} not found")

        return memory
