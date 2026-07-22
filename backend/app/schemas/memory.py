"""Pydantic schemas for memory API requests and responses."""

from pydantic import BaseModel, Field


class MemoryCreateRequest(BaseModel):
    """Request to create a new memory.
    
    The backend will analyze content and auto-approve if safe,
    or flag for user approval if sensitive/critical.
    """
    
    content: str = Field(
        ...,
        min_length=3,
        max_length=5000,
        description="Memory content (what Raghvi should remember)",
        json_schema_extra={"example": "I'm a software engineer at Google"},
    )


class MemoryResponse(BaseModel):
    """Response model for a single memory."""
    
    id: str = Field(..., description="Memory UUID")
    content: str = Field(..., description="Memory content")
    is_sensitive: bool = Field(..., description="True if contains PII")
    is_approved: bool = Field(..., description="True if approved")
    created_at: str = Field(..., description="Creation timestamp (ISO 8601)")
    updated_at: str = Field(..., description="Last update timestamp (ISO 8601)")


class MemoryDetectionResponse(BaseModel):
    """Response after memory creation with sensitivity analysis."""
    
    memory: MemoryResponse
    is_auto_approved: bool = Field(
        ...,
        description="True if auto-approved, False if pending user approval"
    )
    severity_level: str = Field(
        ...,
        description="Severity level: 'public', 'sensitive', or 'critical'",
        json_schema_extra={"example": "public"},
    )
    is_sensitive: bool = Field(..., description="True if sensitive or critical")
    requires_approval: bool = Field(
        ...,
        description="True if user must approve"
    )
    total_score: int = Field(
        ...,
        description="Sensitivity score (higher = more sensitive)"
    )
    matched_rules: list[str] = Field(
        ...,
        description="Rules that matched (e.g., ['email', 'phone'])"
    )
    reason: str = Field(
        ...,
        description="User-friendly explanation if sensitive"
    )


class MemoryApprovalRequest(BaseModel):
    """Request to approve or reject a pending memory."""
    
    approved: bool = Field(
        ...,
        description="True to approve, False to reject"
    )


class MemoryListResponse(BaseModel):
    """Response for listing memories with statistics."""
    
    memories: list[MemoryResponse] = Field(..., description="List of memories")
    total: int = Field(..., description="Total memories (including deleted)")
    approved_count: int = Field(..., description="Approved and active memories")
    pending_count: int = Field(..., description="Pending approval")
    deleted_count: int = Field(..., description="Soft-deleted memories")


class MemoryStatsResponse(BaseModel):
    """Response for memory statistics."""
    
    total: int = Field(..., description="Total memories")
    approved: int = Field(..., description="Approved and active")
    pending: int = Field(..., description="Pending approval")
    deleted: int = Field(..., description="Soft-deleted")