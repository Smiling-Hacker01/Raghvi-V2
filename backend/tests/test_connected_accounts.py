"""Tests for Connected Accounts — multi-user, multi-account isolation and tagging."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.connected_account import ConnectedAccount
from app.models.user import User
from app.services.communication_service import CommunicationService
from app.services.connected_account_service import ConnectedAccountService
from app.services.user_lifecycle_service import UserLifecycleService


@pytest.mark.asyncio
async def test_connected_account_encryption_and_user_isolation(
    test_session: AsyncSession, test_user: User
):
    """Verify AES-256-GCM encryption of credentials and per-user cryptographic isolation."""
    user_id = str(test_user.id)
    credentials = {
        "imap_host": "imap.gmail.com",
        "imap_port": 993,
        "username": "saransh@company.com",
        "password": "super-secret-app-password-1234",
    }

    # Encrypt
    encrypted_str = ConnectedAccountService.encrypt_credentials(user_id, credentials)
    assert encrypted_str != ""
    assert "super-secret-app-password-1234" not in encrypted_str

    # Decrypt with correct user_id
    decrypted = ConnectedAccountService.decrypt_credentials(user_id, encrypted_str)
    assert decrypted["password"] == "super-secret-app-password-1234"
    assert decrypted["username"] == "saransh@company.com"

    # Attempt decrypt with different user_id (cryptographic boundary)
    tampered_decrypted = ConnectedAccountService.decrypt_credentials(
        "other-user-9999", encrypted_str
    )
    assert tampered_decrypted == {}


@pytest.mark.asyncio
async def test_multi_account_crud_and_presets(
    client: AsyncClient,
    test_session: AsyncSession,
    test_user: User,
    auth_headers: dict[str, str],
):
    """Test connecting multiple email and WhatsApp accounts, presets, and updates."""
    # 1. Fetch presets
    res = await client.get("/connected-accounts/presets", headers=auth_headers)
    assert res.status_code == 200
    presets = res.json()
    preset_providers = [p["provider"] for p in presets]
    assert "gmail" in preset_providers
    assert "outlook" in preset_providers
    assert "whatsapp_companion" in preset_providers

    # 2. Connect Account 1: Work Gmail
    res1 = await client.post(
        "/connected-accounts",
        headers=auth_headers,
        json={
            "account_type": "email",
            "provider": "gmail",
            "account_label": "Work Gmail",
            "identifier": "saransh@workcorp.com",
            "credentials": {"password": "work-app-pwd"},
            "is_primary": True,
        },
    )
    assert res1.status_code == 201
    acc1 = res1.json()
    assert acc1["account_label"] == "Work Gmail"
    assert acc1["is_primary"] is True
    # Ensure credentials are NOT leaked in response
    assert "credentials" not in acc1
    assert "work-app-pwd" not in str(acc1)

    # 3. Connect Account 2: Personal Outlook
    res2 = await client.post(
        "/connected-accounts",
        headers=auth_headers,
        json={
            "account_type": "email",
            "provider": "outlook",
            "account_label": "Personal Outlook",
            "identifier": "saransh@outlook.com",
            "credentials": {"password": "personal-app-pwd"},
            "is_primary": True,  # should demote Account 1 from primary
        },
    )
    assert res2.status_code == 201
    acc2 = res2.json()
    assert acc2["account_label"] == "Personal Outlook"
    assert acc2["is_primary"] is True

    # 4. Connect Account 3: WhatsApp Business
    res3 = await client.post(
        "/connected-accounts",
        headers=auth_headers,
        json={
            "account_type": "whatsapp",
            "provider": "whatsapp_companion",
            "account_label": "WhatsApp Business",
            "identifier": "+1987654321",
            "credentials": {},
            "is_primary": False,
        },
    )
    assert res3.status_code == 201
    acc3 = res3.json()
    assert acc3["account_label"] == "WhatsApp Business"

    # 5. List all connected accounts
    list_res = await client.get("/connected-accounts", headers=auth_headers)
    assert list_res.status_code == 200
    all_accs = list_res.json()
    assert len(all_accs) >= 3

    # Verify Account 1 is no longer primary because Account 2 became primary
    acc1_refreshed = next(a for a in all_accs if a["id"] == acc1["id"])
    assert acc1_refreshed["is_primary"] is False

    # 6. Filter by account_type
    wa_list = await client.get("/connected-accounts?account_type=whatsapp", headers=auth_headers)
    assert wa_list.status_code == 200
    assert all(a["account_type"] == "whatsapp" for a in wa_list.json())

    # 7. Update account label
    up_res = await client.put(
        f"/connected-accounts/{acc1['id']}",
        headers=auth_headers,
        json={"account_label": "Official Work Gmail"},
    )
    assert up_res.status_code == 200
    assert up_res.json()["account_label"] == "Official Work Gmail"

    # 8. Delete account
    del_res = await client.delete(f"/connected-accounts/{acc3['id']}", headers=auth_headers)
    assert del_res.status_code == 200


@pytest.mark.asyncio
async def test_multi_account_communication_tagging_and_filtering(
    client: AsyncClient,
    test_session: AsyncSession,
    test_user: User,
    auth_headers: dict[str, str],
):
    """Verify that incoming communications are tagged by account and can be filtered."""
    # Seed an email under Work account
    seed1 = await client.post(
        "/communications/seed",
        headers=auth_headers,
        json={
            "channel": "email",
            "sender": "sarah@workcorp.com",
            "sender_name": "Sarah Connor",
            "recipient": "saransh@workcorp.com",
            "subject": "Q4 Budget Review",
            "body": "Here is the proposed budget for next quarter.",
            "account_label": "Work Gmail",
        },
    )
    assert seed1.status_code == 201

    # Seed an email under Personal account
    seed2 = await client.post(
        "/communications/seed",
        headers=auth_headers,
        json={
            "channel": "email",
            "sender": "order-update@amazon.com",
            "sender_name": "Amazon",
            "recipient": "saransh@personal.com",
            "subject": "Your package has shipped",
            "body": "Your headphones are arriving tomorrow.",
            "account_label": "Personal Outlook",
        },
    )
    assert seed2.status_code == 201

    # Seed WhatsApp Personal vs Business
    seed_wa1 = await client.post(
        "/communications/seed",
        headers=auth_headers,
        json={
            "channel": "whatsapp",
            "sender": "+1111111111",
            "sender_name": "Mom",
            "recipient": "me",
            "body": "Call me when you reach home.",
            "account_label": "WhatsApp (Personal)",
        },
    )
    assert seed_wa1.status_code == 201

    seed_wa2 = await client.post(
        "/communications/seed",
        headers=auth_headers,
        json={
            "channel": "whatsapp",
            "sender": "+2222222222",
            "sender_name": "Client Acme",
            "recipient": "me",
            "body": "Can you share the updated contract?",
            "account_label": "WhatsApp (Business)",
        },
    )
    assert seed_wa2.status_code == 201

    # 1. Filter emails by Work
    work_emails_res = await client.get(
        "/communications/emails?account_label=work", headers=auth_headers
    )
    assert work_emails_res.status_code == 200
    work_emails = work_emails_res.json()
    assert len(work_emails) == 1
    assert work_emails[0]["account_label"] == "Work Gmail"
    assert "Budget" in work_emails[0]["subject"]

    # 2. Filter emails by Personal
    personal_emails_res = await client.get(
        "/communications/emails?account_label=personal", headers=auth_headers
    )
    assert personal_emails_res.status_code == 200
    personal_emails = personal_emails_res.json()
    assert len(personal_emails) == 1
    assert personal_emails[0]["account_label"] == "Personal Outlook"

    # 3. Filter WhatsApp by Business
    biz_wa_res = await client.get(
        "/communications/whatsapp?account_label=business", headers=auth_headers
    )
    assert biz_wa_res.status_code == 200
    biz_msgs = biz_wa_res.json()
    assert len(biz_msgs) == 1
    assert biz_msgs[0]["sender_name"] == "Client Acme"
    assert biz_msgs[0]["account_label"] == "WhatsApp (Business)"


@pytest.mark.asyncio
async def test_intent_parsing_detects_account_targeting():
    """Verify natural language requests extract account target labels."""
    # Work email
    intent1 = CommunicationService.parse_communication_intent(
        "Check my work email for any new updates"
    )
    assert intent1 is not None
    assert intent1["type"] == "check_email"
    assert intent1["account_label"] == "work"

    # Personal email
    intent2 = CommunicationService.parse_communication_intent(
        "Raghvi did I get any mail on my personal account?"
    )
    assert intent2 is not None
    assert intent2["type"] == "check_email"
    assert intent2["account_label"] == "personal"

    # Business WhatsApp
    intent3 = CommunicationService.parse_communication_intent(
        "Check business whatsapp messages from Acme"
    )
    assert intent3 is not None
    assert intent3["type"] == "check_whatsapp"
    assert intent3["account_label"] == "business"


@pytest.mark.asyncio
async def test_user_deletion_gdpr_cascades_connected_accounts(
    test_session: AsyncSession,
    test_user: User,
):
    """Verify GDPR account erasure deletes connected accounts and credentials."""
    user_id = str(test_user.id)

    # Create connected account in DB
    acc = ConnectedAccount(
        user_id=user_id,
        account_type="email",
        provider="gmail",
        account_label="Old Work Email",
        identifier="old@work.com",
        encrypted_credentials=ConnectedAccountService.encrypt_credentials(
            user_id, {"password": "xyz"}
        ),
    )
    test_session.add(acc)
    await test_session.commit()

    # Verify exists
    existing = await test_session.scalar(
        select(ConnectedAccount).where(ConnectedAccount.user_id == user_id)
    )
    assert existing is not None

    # Execute user deletion
    await UserLifecycleService.delete_user_account(test_user, test_session)

    # Verify connected accounts are wiped
    erased = await test_session.scalar(
        select(ConnectedAccount).where(ConnectedAccount.user_id == user_id)
    )
    assert erased is None
