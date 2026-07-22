"""Tests for MemoryService."""

import pytest
from sqlalchemy import select

from app.models.memory import Memory
from app.models.user import User
from app.security.password import hash_password
from app.services.memory.service import MemoryService

pytestmark = pytest.mark.asyncio


class TestMemoryService:
    """Tests for MemoryService."""

    @pytest.fixture
    async def user(self, test_db):
        """Create a test user."""
        async with test_db() as session:
            user = User(
                id="550e8400-e29b-41d4-a716-446655440000",
                username="memorytest",
                email="memorytest@example.com",
                password_hash=hash_password("TestPassword123"),
                name="Memory Test User",
                phone="1234567890",
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user

    async def test_create_public_memory_auto_approved(self, test_db, user):
        """Test that public content is auto-approved at creation."""
        async with test_db() as session:
            memory, is_auto_approved, detection = await MemoryService.create_memory(
                user_id=user.id,
                content="I'm a software engineer at Google",
                session=session,
            )
            
            assert is_auto_approved is True
            assert memory.is_approved is True
            assert memory.approved_at is not None
            assert detection["severity_level"] == "public"
            assert not detection["is_sensitive"]

    async def test_create_sensitive_memory_pending_approval(self, test_db, user):
        """Test that sensitive content is pending approval at creation."""
        async with test_db() as session:
            memory, is_auto_approved, detection = await MemoryService.create_memory(
                user_id=user.id,
                content="My email is alice@example.com",
                session=session,
            )
            
            assert is_auto_approved is False
            assert memory.is_approved is False
            assert memory.approved_at is None
            assert detection["severity_level"] == "sensitive"
            assert detection["is_sensitive"]
            assert detection["requires_approval"]

    async def test_create_critical_memory_never_approved(self, test_db, user):
        """Test that critical content is never auto-approved."""
        async with test_db() as session:
            memory, is_auto_approved, detection = await MemoryService.create_memory(
                user_id=user.id,
                content="password: MySecret123",
                session=session,
            )
            
            assert is_auto_approved is False
            assert not memory.is_approved
            assert detection["severity_level"] == "critical"
            assert detection["total_score"] >= 1000

    async def test_create_memory_invalid_content(self, test_db, user):
        """Test that invalid content raises ValueError."""
        async with test_db() as session:
            invalid_inputs = [
                None,
                "",
                "   ",
                "ab",  # Too short
                "x" * 6000,  # Too long
            ]
            
            for invalid in invalid_inputs:
                with pytest.raises(ValueError):
                    await MemoryService.create_memory(
                        user_id=user.id,
                        content=invalid,
                        session=session,
                    )

    async def test_approve_memory(self, test_db, user):
        """Test approving a pending memory."""
        async with test_db() as session:
            # Create pending memory
            memory, _, _ = await MemoryService.create_memory(
                user_id=user.id,
                content="My email is test@example.com",
                session=session,
            )
            memory_id = str(memory.id)
            
            # Approve it
            approved = await MemoryService.approve_memory(
                user_id=user.id,
                memory_id=memory_id,
                session=session,
            )
            
            assert approved.is_approved
            assert approved.approved_at is not None

    async def test_approve_already_approved_memory_fails(self, test_db, user):
        """Test that approving already-approved memory raises error."""
        async with test_db() as session:
            # Create auto-approved memory (public)
            memory, _, _ = await MemoryService.create_memory(
                user_id=user.id,
                content="I love hiking",
                session=session,
            )
            memory_id = str(memory.id)
            
            # Try to approve again
            with pytest.raises(ValueError, match="already approved"):
                await MemoryService.approve_memory(
                    user_id=user.id,
                    memory_id=memory_id,
                    session=session,
                )

    async def test_reject_memory(self, test_db, user):
        """Test rejecting a pending memory."""
        async with test_db() as session:
            # Create pending memory
            memory, _, _ = await MemoryService.create_memory(
                user_id=user.id,
                content="My phone: 415-555-1234",
                session=session,
            )
            memory_id = str(memory.id)
            
            # Reject it
            await MemoryService.reject_memory(
                user_id=user.id,
                memory_id=memory_id,
                session=session,
            )
            
            # Verify it's soft-deleted
            rejected = await session.scalar(
                select(Memory).where(Memory.id == memory.id)
            )
            assert rejected.deleted_at is not None

    async def test_get_approved_memories(self, test_db, user):
        """Test retrieving approved memories."""
        async with test_db() as session:
            # Create multiple memories
            public1, _, _ = await MemoryService.create_memory(
                user_id=user.id,
                content="I love hiking",
                session=session,
            )
            public2, _, _ = await MemoryService.create_memory(
                user_id=user.id,
                content="I'm a Python developer",
                session=session,
            )
            sensitive, _, _ = await MemoryService.create_memory(
                user_id=user.id,
                content="Email: test@example.com",
                session=session,
            )
            
            # Approve the sensitive one
            await MemoryService.approve_memory(
                user_id=user.id,
                memory_id=str(sensitive.id),
                session=session,
            )
            
            # Get approved memories
            approved = await MemoryService.get_approved_memories(
                user_id=user.id,
                session=session,
            )
            
            # Should have 3 approved (2 auto-approved + 1 manually approved)
            assert len(approved) == 3

    async def test_get_pending_memories(self, test_db, user):
        """Test retrieving pending memories."""
        async with test_db() as session:
            # Create public (auto-approved)
            await MemoryService.create_memory(
                user_id=user.id,
                content="I love hiking",
                session=session,
            )
            
            # Create sensitive (pending)
            memory1, _, _ = await MemoryService.create_memory(
                user_id=user.id,
                content="Email: test1@example.com",
                session=session,
            )
            
            # Create another sensitive (pending)
            memory2, _, _ = await MemoryService.create_memory(
                user_id=user.id,
                content="Phone: 415-555-1234",
                session=session,
            )
            
            # Get pending
            pending = await MemoryService.get_pending_memories(
                user_id=user.id,
                session=session,
            )
            
            # Should have 2 pending (only sensitive ones)
            assert len(pending) == 2

    async def test_get_memory_stats(self, test_db, user):
        """Test memory statistics."""
        async with test_db() as session:
            # Create memories
            public, _, _ = await MemoryService.create_memory(
                user_id=user.id,
                content="I love hiking",
                session=session,
            )
            sensitive, _, _ = await MemoryService.create_memory(
                user_id=user.id,
                content="Email: test@example.com",
                session=session,
            )
            
            # Approve sensitive
            await MemoryService.approve_memory(
                user_id=user.id,
                memory_id=str(sensitive.id),
                session=session,
            )
            
            # Delete public
            await MemoryService.delete_memory(
                user_id=user.id,
                memory_id=str(public.id),
                session=session,
            )
            
            # Get stats
            stats = await MemoryService.get_memory_stats(
                user_id=user.id,
                session=session,
            )
            
            assert stats["total"] == 2
            assert stats["approved"] == 1
            assert stats["pending"] == 0
            assert stats["deleted"] == 1

    async def test_delete_memory(self, test_db, user):
        """Test deleting an approved memory."""
        async with test_db() as session:
            # Create and auto-approve public memory
            memory, _, _ = await MemoryService.create_memory(
                user_id=user.id,
                content="I love hiking",
                session=session,
            )
            memory_id = str(memory.id)
            
            # Delete it
            await MemoryService.delete_memory(
                user_id=user.id,
                memory_id=memory_id,
                session=session,
            )
            
            # Verify soft delete
            deleted = await session.scalar(
                select(Memory).where(Memory.id == memory.id)
            )
            assert deleted.deleted_at is not None

    async def test_cannot_delete_pending_memory(self, test_db, user):
        """Test that pending memories cannot be deleted (must be rejected)."""
        async with test_db() as session:
            # Create pending memory
            memory, _, _ = await MemoryService.create_memory(
                user_id=user.id,
                content="Email: test@example.com",
                session=session,
            )
            memory_id = str(memory.id)
            
            # Try to delete pending memory
            with pytest.raises(ValueError, match="pending"):
                await MemoryService.delete_memory(
                    user_id=user.id,
                    memory_id=memory_id,
                    session=session,
                )

    async def test_get_memory_by_id(self, test_db, user):
        """Test retrieving a specific memory by ID."""
        async with test_db() as session:
            memory, _, _ = await MemoryService.create_memory(
                user_id=user.id,
                content="I love hiking",
                session=session,
            )
            memory_id = str(memory.id)
            
            # Get it back
            retrieved = await MemoryService.get_memory_by_id(
                user_id=user.id,
                memory_id=memory_id,
                session=session,
            )
            
            assert retrieved.id == memory.id
            assert retrieved.content == "I love hiking"

    async def test_cannot_access_other_users_memory(self, test_db, user):
        """Test that users cannot access other users' memories."""
        async with test_db() as session:
            # Create memory for user1
            memory, _, _ = await MemoryService.create_memory(
                user_id=user.id,
                content="My secret",
                session=session,
            )
            memory_id = str(memory.id)
            
            # Try to access with different user ID
            with pytest.raises(ValueError, match="not found"):
                await MemoryService.get_memory_by_id(
                    user_id="999e8400-e29b-41d4-a716-446655440999",
                    memory_id=memory_id,
                    session=session,
                )