"""Connected accounts API — manage multiple email & messaging accounts with per-user encryption."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.connected_account import (
    ConnectedAccountCreate,
    ConnectedAccountResponse,
    ConnectedAccountUpdate,
    GoogleOAuthAuthorizeResponse,
    GoogleOAuthExchangeRequest,
    ProviderPresetResponse,
    SyncAccountResult,
)
from app.services.connected_account_service import ConnectedAccountService
from app.services.google_oauth_service import GoogleOAuthService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/connected-accounts", tags=["connected-accounts"])

CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("/presets", response_model=list[ProviderPresetResponse])
async def get_provider_presets() -> list[ProviderPresetResponse]:
    """Get list of supported providers and default settings."""
    return ConnectedAccountService.get_presets()


@router.get("", response_model=list[ConnectedAccountResponse])
async def list_connected_accounts(
    current_user: CurrentUser,
    session: DbSession,
    account_type: Annotated[
        str | None, Query(description="Filter by type: email or whatsapp")
    ] = None,
) -> list[ConnectedAccountResponse]:
    """List all connected accounts for the authenticated user (credentials sanitized)."""
    accounts = await ConnectedAccountService.list_accounts(
        user_id=str(current_user.id),
        account_type=account_type,
        session=session,
    )
    return [ConnectedAccountService.to_response(acc) for acc in accounts]


@router.post("", response_model=ConnectedAccountResponse, status_code=status.HTTP_201_CREATED)
async def connect_account(
    request: ConnectedAccountCreate,
    current_user: CurrentUser,
    session: DbSession,
) -> ConnectedAccountResponse:
    """Connect a new email or WhatsApp account with AES-256-GCM credential encryption."""
    account = await ConnectedAccountService.create_account(
        user_id=str(current_user.id),
        data=request,
        session=session,
    )
    return ConnectedAccountService.to_response(account)


@router.get("/{account_id}", response_model=ConnectedAccountResponse)
async def get_connected_account(
    account_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> ConnectedAccountResponse:
    """Get details for a specific connected account."""
    account = await ConnectedAccountService.get_account(
        user_id=str(current_user.id),
        account_id=account_id,
        session=session,
    )
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connected account not found or access denied.",
        )
    return ConnectedAccountService.to_response(account)


@router.put("/{account_id}", response_model=ConnectedAccountResponse)
async def update_connected_account(
    account_id: UUID,
    request: ConnectedAccountUpdate,
    current_user: CurrentUser,
    session: DbSession,
) -> ConnectedAccountResponse:
    """Update connected account label, active state, or credentials."""
    account = await ConnectedAccountService.update_account(
        user_id=str(current_user.id),
        account_id=account_id,
        data=request,
        session=session,
    )
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connected account not found or access denied.",
        )
    return ConnectedAccountService.to_response(account)


@router.delete("/{account_id}", status_code=status.HTTP_200_OK)
async def disconnect_account(
    account_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> dict[str, str]:
    """Disconnect and delete a connected email or messaging account."""
    deleted = await ConnectedAccountService.delete_account(
        user_id=str(current_user.id),
        account_id=account_id,
        session=session,
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connected account not found or access denied.",
        )
    return {"status": "deleted", "account_id": str(account_id)}


@router.post("/{account_id}/sync", response_model=SyncAccountResult)
async def sync_single_account(
    account_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
    limit: Annotated[int, Query(ge=1, le=50)] = 15,
) -> SyncAccountResult:
    """Manually trigger synchronization for a specific connected email account."""
    result = await ConnectedAccountService.sync_account(
        user_id=str(current_user.id),
        account_id=account_id,
        session=session,
        limit=limit,
    )
    return result


@router.post("/sync-all", response_model=list[SyncAccountResult])
async def sync_all_user_accounts(
    current_user: CurrentUser,
    session: DbSession,
    limit: Annotated[int, Query(ge=1, le=50)] = 15,
) -> list[SyncAccountResult]:
    """Manually trigger synchronization across all active email accounts for this user."""
    results = await ConnectedAccountService.sync_all_accounts(
        user_id=str(current_user.id),
        session=session,
        limit=limit,
    )
    return results


# -------------------------------------------------------------------------
# Google OAuth 2.0 (1-Click Google Account & Gmail Sync)
# -------------------------------------------------------------------------


@router.get("/oauth/google/connect")
async def start_google_oauth_browser(
    session: DbSession,
    user_id: Annotated[str | None, Query(description="User ID to link account to")] = None,
    account_label: Annotated[str, Query()] = "Personal Gmail",
):
    """Browser-accessible 1-click endpoint to initiate Google OAuth consent flow."""
    from fastapi.responses import RedirectResponse
    from sqlalchemy import select

    target_user_id = user_id
    if not target_user_id:
        user = await session.scalar(
            select(User).where(User.email.ilike("%vishal%"))
        )
        if not user:
            user = await session.scalar(select(User))
        if user:
            target_user_id = str(user.id)
        else:
            raise HTTPException(status_code=400, detail="No registered user found")

    auth_url, _, _ = GoogleOAuthService.get_authorization_url(
        user_id=target_user_id,
        account_label=account_label,
    )
    return RedirectResponse(url=auth_url)


@router.get("/oauth/google/authorize", response_model=GoogleOAuthAuthorizeResponse)
async def get_google_oauth_authorize_url(
    current_user: CurrentUser,
    account_label: Annotated[str, Query(description="Label for this account")] = "Personal Gmail",
    redirect_uri: Annotated[str | None, Query(description="Custom redirect URI if needed")] = None,
) -> GoogleOAuthAuthorizeResponse:
    """Generate 1-click Google OAuth 2.0 authorization URL for connecting Gmail."""
    auth_url, state, configured = GoogleOAuthService.get_authorization_url(
        user_id=str(current_user.id),
        account_label=account_label,
        redirect_uri=redirect_uri,
    )

    instructions = None
    if not configured:
        instructions = (
            "To enable 1-click Google OAuth in production: create OAuth 2.0 credentials "
            "in Google Cloud Console (console.cloud.google.com), set Authorized redirect URI to "
            "/connected-accounts/oauth/google/callback, and configure "
            "GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET in backend .env."
        )

    return GoogleOAuthAuthorizeResponse(
        authorization_url=auth_url,
        state=state,
        configured=configured,
        instructions=instructions,
    )


@router.get("/oauth/google/callback")
async def handle_google_oauth_callback(
    code: Annotated[str, Query(description="Google authorization code")],
    state: Annotated[str, Query(description="OAuth state token for verification")],
    session: DbSession,
    redirect_uri: Annotated[str | None, Query()] = None,
) -> dict:
    """OAuth callback endpoint: exchanges Google code for tokens and registers connected account."""
    try:
        user_id, account_label = GoogleOAuthService.verify_oauth_state(state)
        tokens = await GoogleOAuthService.exchange_auth_code(code=code, redirect_uri=redirect_uri)
        user_info = await GoogleOAuthService.get_google_userinfo(tokens["access_token"])
        email = user_info.get("email")

        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unable to retrieve verified email from Google profile.",
            )

        account = await ConnectedAccountService.connect_google_oauth(
            user_id=user_id,
            email=email,
            tokens=tokens,
            account_label=account_label,
            session=session,
        )

        return {
            "status": "connected",
            "provider": "gmail",
            "account_id": str(account.id),
            "email": email,
            "account_label": account.account_label,
            "message": f"Successfully connected {email} with 1-click Google OAuth!",
        }

    except ValueError as e:
        logger.error(f"Google OAuth callback error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Google OAuth connection failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to connect Google account: {str(e)}",
        ) from e


@router.post("/oauth/google/exchange", response_model=ConnectedAccountResponse)
async def exchange_google_oauth_code(
    request: GoogleOAuthExchangeRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> ConnectedAccountResponse:
    """Exchange Google auth code directly from mobile app or frontend SDK."""
    try:
        tokens = await GoogleOAuthService.exchange_auth_code(
            code=request.auth_code,
            redirect_uri=request.redirect_uri,
        )
        user_info = await GoogleOAuthService.get_google_userinfo(tokens["access_token"])
        email = user_info.get("email")

        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unable to retrieve email from Google profile.",
            )

        account = await ConnectedAccountService.connect_google_oauth(
            user_id=str(current_user.id),
            email=email,
            tokens=tokens,
            account_label=request.account_label,
            session=session,
        )

        return ConnectedAccountService.to_response(account)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Google OAuth direct exchange failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to exchange Google OAuth code: {str(e)}",
        ) from e

