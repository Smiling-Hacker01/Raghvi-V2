"""Memory endpoints — CRUD operations and approval workflow."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.memory import (
    MemoryApprovalRequest,
    MemoryCreateRequest,
    MemoryDetectionResponse,
    MemoryListResponse,
    MemoryResponse,
    MemoryStatsResponse,
)
from app.services.memory.service import MemoryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memories", tags=["memories"])

# Type aliases for dependency injection
CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.post("", response_model=MemoryDetectionResponse, status_code=201)
async def create_memory(
    request: MemoryCreateRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> MemoryDetectionResponse:
    """Create a new memory.

    Auto-approval logic:
    - PUBLIC (non-sensitive): Auto-approved immediately
    - SENSITIVE (email, phone, address): Pending user approval
    - CRITICAL (password, card, SSN): Never auto-approved, flagged

    Returns detection analysis along with created memory.
    """
    try:
        memory, is_auto_approved, detection = await MemoryService.create_memory(
            user_id=str(current_user.id),
            content=request.content,
            session=session,
        )

        # Commit to database
        await session.commit()

        logger.info(
            f"Memory created for user {current_user.id}: "
            f"id={memory.id}, auto_approved={is_auto_approved}"
        )

        return MemoryDetectionResponse(
            memory=MemoryResponse(
                id=str(memory.id),
                content=memory.content,
                is_sensitive=memory.is_sensitive,
                is_approved=memory.is_approved,
                created_at=memory.created_at.isoformat(),
                updated_at=memory.updated_at.isoformat(),
            ),
            is_auto_approved=is_auto_approved,
            severity_level=detection["severity_level"],
            is_sensitive=detection["is_sensitive"],
            requires_approval=detection["requires_approval"],
            total_score=detection["total_score"],
            matched_rules=detection["matched_rules"],
            reason=detection["reason"],
        )

    except ValueError as e:
        logger.warning(f"Memory creation validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Memory creation error: {e}", exc_info=True)
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create memory",
        ) from e


@router.get("", response_model=MemoryListResponse)
async def list_approved_memories(
    limit: int = 50,
    current_user: CurrentUser = None,
    session: DbSession = None,
) -> MemoryListResponse:
    """Get approved (active) memories for current user.

    Query parameters:
    - limit: Max memories to return (default 50, max 1000)
    """
    try:
        limit = min(limit, 1000)

        memories = await MemoryService.get_approved_memories(
            user_id=str(current_user.id),
            limit=limit,
            session=session,
        )

        stats = await MemoryService.get_memory_stats(
            user_id=str(current_user.id),
            session=session,
        )

        return MemoryListResponse(
            memories=[
                MemoryResponse(
                    id=str(m.id),
                    content=m.content,
                    is_sensitive=m.is_sensitive,
                    is_approved=m.is_approved,
                    created_at=m.created_at.isoformat(),
                    updated_at=m.updated_at.isoformat(),
                )
                for m in memories
            ],
            total=stats["total"],
            approved_count=stats["approved"],
            pending_count=stats["pending"],
            deleted_count=stats["deleted"],
        )

    except Exception as e:
        logger.error(f"Failed to list memories: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load memories",
        ) from e


@router.get("/pending", response_model=MemoryListResponse)
async def list_pending_memories(
    current_user: CurrentUser,
    session: DbSession,
) -> MemoryListResponse:
    """Get pending memories awaiting user approval.

    These are sensitive memories that Raghvi learned but user must approve
    before they're stored.
    """
    try:
        memories = await MemoryService.get_pending_memories(
            user_id=str(current_user.id),
            session=session,
        )

        stats = await MemoryService.get_memory_stats(
            user_id=str(current_user.id),
            session=session,
        )

        return MemoryListResponse(
            memories=[
                MemoryResponse(
                    id=str(m.id),
                    content=m.content,
                    is_sensitive=m.is_sensitive,
                    is_approved=False,  # All pending are unapproved
                    created_at=m.created_at.isoformat(),
                    updated_at=m.updated_at.isoformat(),
                )
                for m in memories
            ],
            total=stats["total"],
            approved_count=stats["approved"],
            pending_count=stats["pending"],
            deleted_count=stats["deleted"],
        )

    except Exception as e:
        logger.error(f"Failed to list pending memories: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load pending memories",
        ) from e


@router.post("/{memory_id}/approve", response_model=MemoryResponse)
async def approve_or_reject_memory(
    memory_id: str,
    request: MemoryApprovalRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> MemoryResponse:
    """Approve or reject a pending memory.

    Path parameters:
    - memory_id: UUID of memory to approve/reject

    Body:
    - approved: true to approve, false to reject
    """
    try:
        if request.approved:
            # Approve the memory
            memory = await MemoryService.approve_memory(
                user_id=str(current_user.id),
                memory_id=memory_id,
                session=session,
            )
            logger.info(f"Memory {memory_id} approved by user {current_user.id}")

            return MemoryResponse(
                id=str(memory.id),
                content=memory.content,
                is_sensitive=memory.is_sensitive,
                is_approved=memory.is_approved,
                created_at=memory.created_at.isoformat(),
                updated_at=memory.updated_at.isoformat(),
            )
        else:
            # Reject the memory (soft delete)
            await MemoryService.reject_memory(
                user_id=str(current_user.id),
                memory_id=memory_id,
                session=session,
            )
            logger.info(f"Memory {memory_id} rejected by user {current_user.id}")

            raise HTTPException(
                status_code=status.HTTP_204_NO_CONTENT,
            )

    except ValueError as e:
        logger.warning(f"Memory approval error: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to approve memory: {e}", exc_info=True)
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to approve memory",
        ) from e


@router.delete("/{memory_id}", status_code=204)
async def delete_memory(
    memory_id: str,
    current_user: CurrentUser,
    session: DbSession,
) -> None:
    """Delete an approved memory.

    Only approved memories can be deleted. To reject a pending memory,
    use the /memories/{memory_id}/approve endpoint with approved=false.
    """
    try:
        await MemoryService.delete_memory(
            user_id=str(current_user.id),
            memory_id=memory_id,
            session=session,
        )
        logger.info(f"Memory {memory_id} deleted by user {current_user.id}")

    except ValueError as e:
        logger.warning(f"Memory deletion error: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Failed to delete memory: {e}", exc_info=True)
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete memory",
        ) from e


@router.get("/stats", response_model=MemoryStatsResponse)
async def get_memory_stats(
    current_user: CurrentUser,
    session: DbSession,
) -> MemoryStatsResponse:
    """Get memory statistics for current user.

    Returns:
    - total: All memories (including soft-deleted)
    - approved: Active, approved memories
    - pending: Pending user approval
    - deleted: Soft-deleted memories
    """
    try:
        stats = await MemoryService.get_memory_stats(
            user_id=str(current_user.id),
            session=session,
        )
        return MemoryStatsResponse(**stats)

    except Exception as e:
        logger.error(f"Failed to get memory stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load memory stats",
        ) from e
