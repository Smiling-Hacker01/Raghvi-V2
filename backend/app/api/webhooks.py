"""Provider-neutral payment webhook endpoint."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.payments.adapter_builder import get_payment_provider
from app.payments.base import PaymentProviderError
from app.payments.webhook_service import PaymentWebhookService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/{provider_name}")
async def payment_webhook(
    provider_name: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict:
    """Verify and dispatch a payment provider webhook."""
    try:
        provider = get_payment_provider(provider_name)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment provider is not registered",
        ) from exc

    try:
        event = await provider.verify_webhook_signature(
            await request.body(),
            request.headers,
        )
    except PaymentProviderError as exc:
        logger.warning("Rejected %s webhook: %s", provider_name, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook signature or payload",
        ) from exc

    logger.info("Received %s webhook: %s", provider.provider_name, event.event_type)
    result = await PaymentWebhookService.handle(provider.provider_name, event, session)
    return {"status": result.get("status", "success"), **result}
