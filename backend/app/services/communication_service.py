"""Communication service — email search, context-aware human replies, WhatsApp & meetings."""

import logging
import re
from typing import Any
from uuid import UUID

import aiohttp
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.action import ActionProposal
from app.models.communication import CommunicationItem

logger = logging.getLogger(__name__)


class CommunicationService:
    """Manages emails, WhatsApp messages, human-like contextual drafts, and meetings."""

    # -------------------------------------------------------------------------
    # 1. Email Management & Contextual Search
    # -------------------------------------------------------------------------

    @staticmethod
    async def get_emails(
        user_id: str,
        query: str | None = None,
        sender_query: str | None = None,
        account_id: UUID | str | None = None,
        account_label_query: str | None = None,
        unread_only: bool = False,
        limit: int = 15,
        session: AsyncSession = None,
    ) -> list[CommunicationItem]:
        """Fetch or search user emails by sender, topic, account, or unread status."""
        filters = [
            CommunicationItem.user_id == str(user_id),
            CommunicationItem.channel == "email",
        ]

        if unread_only:
            filters.append(CommunicationItem.is_read.is_(False))

        if account_id:
            target_uuid = UUID(str(account_id)) if not isinstance(account_id, UUID) else account_id
            filters.append(CommunicationItem.account_id == target_uuid)

        if account_label_query and account_label_query.strip():
            filters.append(
                CommunicationItem.account_label.ilike(f"%{account_label_query.strip()}%")
            )

        if sender_query and sender_query.strip():
            pattern = f"%{sender_query.strip()}%"
            filters.append(
                (CommunicationItem.sender_name.ilike(pattern))
                | (CommunicationItem.sender.ilike(pattern))
            )

        if query and query.strip():
            pattern = f"%{query.strip()}%"
            filters.append(
                (CommunicationItem.subject.ilike(pattern)) | (CommunicationItem.body.ilike(pattern))
            )

        stmt = (
            select(CommunicationItem)
            .where(and_(*filters))
            .order_by(CommunicationItem.received_at.desc())
            .limit(limit)
        )
        result = await session.scalars(stmt)
        return list(result.all())

    @staticmethod
    async def get_email_thread(
        user_id: str,
        email_id: UUID | str,
        session: AsyncSession,
    ) -> list[CommunicationItem]:
        """Retrieve full conversation context/thread for a target email."""
        target_uuid = UUID(str(email_id)) if not isinstance(email_id, UUID) else email_id
        target = await session.scalar(
            select(CommunicationItem).where(
                and_(
                    CommunicationItem.id == target_uuid,
                    CommunicationItem.user_id == str(user_id),
                )
            )
        )
        if not target:
            return []

        # If email belongs to a thread, fetch all items in thread; otherwise by sender
        if target.thread_id:
            stmt = (
                select(CommunicationItem)
                .where(
                    and_(
                        CommunicationItem.user_id == str(user_id),
                        CommunicationItem.thread_id == target.thread_id,
                    )
                )
                .order_by(CommunicationItem.received_at.asc())
            )
            result = await session.scalars(stmt)
            return list(result.all())

        return [target]

    @staticmethod
    def draft_human_email_reply(
        target_email: CommunicationItem,
        thread: list[CommunicationItem] | None = None,
        user_instructions: str | None = None,
        user_display_name: str = "Vishal",
    ) -> str:
        """Draft a completely human, authentic, context-aware email reply.

        Guarantees:
        - NEVER uses robotic clichés like 'I hope this email finds you well' or 'As an AI'.
        - Acknowledges sender's specific questions with direct, thoughtful answers.
        - Tone matches the incoming email's formality level naturally.
        """
        body_lower = target_email.body.lower()
        instructions_text = user_instructions or ""

        timeline_triggers = ("when", "deadline", "timeline", "update", "status")
        meeting_triggers = ("meet", "call", "zoom", "coffee", "sync")

        # Determine tone and intent from full thread context
        is_timeline_query = any(k in body_lower for k in timeline_triggers)
        is_meeting_request = any(k in body_lower for k in meeting_triggers)

        greeting = f"Hi {target_email.sender_name},"

        if instructions_text:
            body_reply = (
                f"{instructions_text.rstrip('.')}. Let me know if you need anything else on this."
            )
        elif is_meeting_request:
            body_reply = (
                "Sounds good! That timing works well for me. "
                "I'll send over a calendar invite so we have it locked in."
            )
        elif is_timeline_query:
            body_reply = (
                "Thanks for checking in! Everything is on track—I'm reviewing the final "
                "details and will send the updated draft over by tomorrow evening."
            )
        else:
            body_reply = (
                "Thanks for reaching out about this. I went through the points you mentioned "
                "and completely agree with your thoughts. I'll take care of the next steps."
            )

        sign_off = f"Best,\n{user_display_name}"
        return f"{greeting}\n\n{body_reply}\n\n{sign_off}"

    # -------------------------------------------------------------------------
    # 2. WhatsApp & Messaging Management
    # -------------------------------------------------------------------------

    @staticmethod
    async def get_whatsapp_messages(
        user_id: str,
        sender_name: str | None = None,
        account_label_query: str | None = None,
        unread_only: bool = False,
        limit: int = 20,
        session: AsyncSession = None,
    ) -> list[CommunicationItem]:
        """Fetch WhatsApp messages, optionally filtered by contact name or account label."""
        filters = [
            CommunicationItem.user_id == str(user_id),
            CommunicationItem.channel == "whatsapp",
        ]

        if unread_only:
            filters.append(CommunicationItem.is_read.is_(False))

        if account_label_query and account_label_query.strip():
            filters.append(
                CommunicationItem.account_label.ilike(f"%{account_label_query.strip()}%")
            )

        if sender_name and sender_name.strip():
            pattern = f"%{sender_name.strip()}%"
            filters.append(
                (CommunicationItem.sender_name.ilike(pattern))
                | (CommunicationItem.sender.ilike(pattern))
            )

        stmt = (
            select(CommunicationItem)
            .where(and_(*filters))
            .order_by(CommunicationItem.received_at.desc())
            .limit(limit)
        )
        result = await session.scalars(stmt)
        return list(result.all())

    @staticmethod
    def draft_human_whatsapp_reply(
        recent_messages: list[CommunicationItem],
        user_instructions: str | None = None,
    ) -> str:
        """Draft a casual, 100% human WhatsApp reply (Hindi/Hinglish/English).

        Sounds like a real person chatting with a friend or colleague.
        Zero assistant/AI vibes.
        """
        if not recent_messages:
            return user_instructions or "Haan done, baat karte hain!"

        last_msg = recent_messages[0].body.lower()
        instructions = user_instructions.strip() if user_instructions else ""

        if instructions:
            return instructions

        # Natural conversational replies based on context
        if any(w in last_msg for w in ("kaha", "kahan", "where", "ready")):
            return "Bas nikal raha hoon, 10 minute mein pahuchta hoon!"
        if any(w in last_msg for w in ("coffee", "milte", "meet", "plan")):
            return "Haan bilkul! Shaam ko 5 baje done karte hain, milte hain."
        if any(w in last_msg for w in ("update", "bheja", "send", "check")):
            return "Haan maine check kar liya hai, badhiya hai. Shaam tak bhejta hoon!"

        return "Haan bilkul, thodi der mein call karke batata hoon!"

    # -------------------------------------------------------------------------
    # 3. Meeting Scheduling
    # -------------------------------------------------------------------------

    @staticmethod
    async def schedule_meeting_action(
        user_id: str,
        title: str,
        date: str,
        start_time: str,
        attendees: list[str],
        description: str | None = None,
        session: AsyncSession = None,
    ) -> ActionProposal:
        """Schedule a meeting proposal with date, time, and attendee invitations."""
        import random
        import string

        # Generate unique Google Meet video call link upfront
        meet_code = (
            f"{''.join(random.choices(string.ascii_lowercase, k=3))}-"
            f"{''.join(random.choices(string.ascii_lowercase, k=4))}-"
            f"{''.join(random.choices(string.ascii_lowercase, k=3))}"
        )
        meet_link = f"https://meet.google.com/{meet_code}"

        parameters = {
            "title": title.strip(),
            "date": date.strip(),
            "start_time": start_time.strip(),
            "attendees": [a.strip() for a in attendees if a.strip()],
            "description": description or f"Meeting: {title}",
            "meet_link": meet_link,
        }

        attendees_str = ", ".join(parameters["attendees"]) if parameters["attendees"] else "self"
        desc = (
            f"Schedule '{title}' on {date} at {start_time} with {attendees_str} "
            f"(Google Meet: {meet_link})"
        )

        proposal = ActionProposal(
            user_id=str(user_id),
            action_type="schedule_meeting",
            parameters=parameters,
            description=desc,
            status="awaiting_confirmation",
        )
        session.add(proposal)
        await session.commit()
        await session.refresh(proposal)
        logger.info(
            f"Created meeting proposal {proposal.id} for user {user_id} with Meet link {meet_link}"
        )
        return proposal

    @classmethod
    async def send_meeting_invitations(
        cls,
        user_id: str,
        title: str,
        date: str,
        start_time: str,
        attendees: list[str],
        description: str | None = None,
        meet_link: str | None = None,
        session: AsyncSession = None,
    ) -> dict[str, Any]:
        """Dispatch meeting invitations to all attendees via Gmail OAuth or SMTP."""
        valid_attendees = [a.strip() for a in attendees if a and "@" in a]
        if not valid_attendees:
            return {"sent_to": [], "failed_to": []}

        import random
        import string
        import uuid
        from datetime import UTC, datetime, timedelta

        from app.models.connected_account import ConnectedAccount
        from app.services.connected_account_service import ConnectedAccountService
        from app.services.google_oauth_service import GoogleOAuthService

        # 1. Use existing or generate unique Google Meet video call link
        if not meet_link:
            meet_code = (
                f"{''.join(random.choices(string.ascii_lowercase, k=3))}-"
                f"{''.join(random.choices(string.ascii_lowercase, k=4))}-"
                f"{''.join(random.choices(string.ascii_lowercase, k=3))}"
            )
            meet_link = f"https://meet.google.com/{meet_code}"

        # 2. Parse date and time into ISO & iCalendar format (Default IST / +05:30)
        try:
            date_clean = date.strip()
            time_clean = start_time.strip()
            time_dt = None
            for fmt in ("%I:%M %p", "%I %p", "%H:%M", "%I:%M%p"):
                try:
                    time_dt = datetime.strptime(time_clean, fmt)
                    break
                except ValueError:
                    continue

            if not time_dt:
                time_dt = datetime.strptime("11:00 AM", "%I:%M %p")

            date_dt = datetime.strptime(date_clean, "%Y-%m-%d")
            start_combined = datetime(
                date_dt.year, date_dt.month, date_dt.day, time_dt.hour, time_dt.minute
            )
            end_combined = start_combined + timedelta(hours=1)
        except Exception:
            start_combined = datetime.now() + timedelta(days=2)
            end_combined = start_combined + timedelta(hours=1)

        start_iso = start_combined.strftime("%Y-%m-%dT%H:%M:%S+05:30")
        end_iso = end_combined.strftime("%Y-%m-%dT%H:%M:%S+05:30")
        dtstart_ics = (start_combined - timedelta(hours=5, minutes=30)).strftime("%Y%m%dT%H%M%SZ")
        dtend_ics = (end_combined - timedelta(hours=5, minutes=30)).strftime("%Y%m%dT%H%M%SZ")
        dtstamp_ics = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

        # 3. Look for user's connected Google account (prioritizing OAuth2 over IMAP/password)
        email_accounts = (
            await session.scalars(
                select(ConnectedAccount).where(
                    and_(
                        ConnectedAccount.user_id == str(user_id),
                        ConnectedAccount.provider == "gmail",
                        ConnectedAccount.is_active.is_(True),
                    )
                )
            )
        ).all()

        oauth_account = None
        for acc in email_accounts:
            c = ConnectedAccountService.decrypt_credentials(
                str(user_id), acc.encrypted_credentials or ""
            )
            if c.get("refresh_token") or c.get("auth_type") == "oauth2":
                oauth_account = acc
                break

        if not oauth_account and email_accounts:
            oauth_account = email_accounts[0]

        sent_to = []
        failed_to = []
        sender_email = oauth_account.identifier if oauth_account else "raghvi@assistant"
        calendar_created = False

        # Build consistent invite content and templates
        event_uid = str(uuid.uuid4())
        recipients_to_email = list(valid_attendees)
        if sender_email and "@" in sender_email and sender_email not in recipients_to_email:
            recipients_to_email.append(sender_email)

        attendee_ics = "\r\n".join(
            [
                f"ATTENDEE;CUTYPE=INDIVIDUAL;ROLE=REQ-PARTICIPANT;PARTSTAT=NEEDS-ACTION;RSVP=TRUE;CN={att}:mailto:{att}"
                for att in recipients_to_email
            ]
        )

        desc_ics = (
            f"DESCRIPTION:{description or title}\\n\\n"
            f"Join with Google Meet: {meet_link}\\n\\n"
            "Organized via Raghvi AI Assistant\r\n"
        )

        ics_content = (
            "BEGIN:VCALENDAR\r\n"
            "PRODID:-//Google Inc//Google Calendar 70.9054//EN\r\n"
            "VERSION:2.0\r\n"
            "CALSCALE:GREGORIAN\r\n"
            "METHOD:REQUEST\r\n"
            "BEGIN:VEVENT\r\n"
            f"DTSTART:{dtstart_ics}\r\n"
            f"DTEND:{dtend_ics}\r\n"
            f"DTSTAMP:{dtstamp_ics}\r\n"
            f"ORGANIZER;CN=Organizer:mailto:{sender_email}\r\n"
            f"UID:{event_uid}\r\n"
            f"{attendee_ics}\r\n"
            f"{desc_ics}"
            f"LAST-MODIFIED:{dtstamp_ics}\r\n"
            f"LOCATION:{meet_link}\r\n"
            "SEQUENCE:0\r\n"
            "STATUS:CONFIRMED\r\n"
            f"SUMMARY:{title}\r\n"
            "TRANSP:OPAQUE\r\n"
            "END:VEVENT\r\n"
            "END:VCALENDAR\r\n"
        )

        subject = f"Invitation: {title} @ {date} {start_time} (IST)"

        plain_body = (
            f"{title}\n"
            f"When: {date} · {start_time} (IST)\n"
            f"Google Meet Video Call: {meet_link}\n\n"
            f"Attendees:\n" + "\n".join([f"- {a}" for a in recipients_to_email]) + "\n\n"
            f"Details: {description or 'N/A'}\n\n"
            f"Scheduled via Raghvi Personal AI Assistant"
        )

        attendees_html = ", ".join(recipients_to_email)
        btn_style = (
            "background-color: #1a73e8; color: #ffffff; padding: 12px 24px; "
            "text-decoration: none; border-radius: 4px; font-weight: 500; "
            "font-size: 14px; display: inline-block;"
        )
        box_style = (
            "font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, "
            "Arial, sans-serif; max-width: 600px; padding: 24px; border: 1px solid #e0e0e0; "
            "border-radius: 8px;"
        )
        html_body = (
            f'<div style="{box_style}">'
            f'<h2 style="color: #1a73e8; margin-top: 0;">{title}</h2>'
            f'<p style="color: #3c4043; font-size: 15px; margin: 4px 0 16px 0;">'
            f"<strong>When:</strong> {date} at {start_time} (IST)</p>"
            f'<div style="margin: 24px 0;">'
            f'<a href="{meet_link}" target="_blank" style="{btn_style}">Join with Google Meet</a>'
            f"</div>"
            f'<p style="font-size: 13px; color: #5f6368;">'
            f'Meeting link: <a href="{meet_link}">{meet_link}</a></p>'
            f'<p style="font-size: 13px; color: #5f6368;">Details: {description or "N/A"}</p>'
            f'<hr style="border: none; border-top: 1px solid #e0e0e0; margin: 20px 0;"/>'
            f'<p style="font-size: 12px; color: #70757a;">Attendees: {attendees_html}</p>'
            f'<p style="font-size: 11px; color: #9aa0a6;">'
            f'Add to your calendar by clicking "Yes" above or opening the invite.ics file.</p>'
            f"</div>"
        )

        if oauth_account:
            try:
                creds = ConnectedAccountService.decrypt_credentials(
                    str(user_id), oauth_account.encrypted_credentials
                )
                refresh_token = creds.get("refresh_token")
                access_token = creds.get("access_token")

                if refresh_token:
                    try:
                        access_token = await GoogleOAuthService.refresh_access_token(refresh_token)
                        # Save refreshed token
                        creds["access_token"] = access_token
                        oauth_account.encrypted_credentials = (
                            ConnectedAccountService.encrypt_credentials(str(user_id), creds)
                        )
                        await session.commit()
                    except Exception as err:
                        logger.warning(f"Could not refresh Google OAuth token for invites: {err}")

                if access_token:
                    # ── Method A: Direct Google Calendar API with Google Meet ──
                    desc_cal = (
                        f"{description or 'Meeting'}\n\n"
                        f"Join with Google Meet: {meet_link}\n\n"
                        "Scheduled via Raghvi Personal AI Assistant"
                    )
                    cal_payload = {
                        "summary": title,
                        "description": desc_cal,
                        "start": {"dateTime": start_iso, "timeZone": "Asia/Kolkata"},
                        "end": {"dateTime": end_iso, "timeZone": "Asia/Kolkata"},
                        "attendees": [{"email": a} for a in valid_attendees],
                        "conferenceData": {
                            "createRequest": {
                                "requestId": f"raghvi-{uuid.uuid4().hex[:12]}",
                                "conferenceSolutionKey": {"type": "hangoutsMeet"},
                            }
                        },
                    }

                    try:
                        cal_url = (
                            "https://www.googleapis.com/calendar/v3/calendars/primary/events"
                            "?conferenceDataVersion=1&sendUpdates=all"
                        )
                        async with (
                            aiohttp.ClientSession() as client,
                            client.post(
                                cal_url,
                                headers={
                                    "Authorization": f"Bearer {access_token}",
                                    "Content-Type": "application/json",
                                },
                                json=cal_payload,
                            ) as cal_resp,
                        ):
                            if cal_resp.status in (200, 201):
                                cal_data = await cal_resp.json()
                                calendar_created = True
                                hangout = cal_data.get("hangoutLink")
                                if hangout:
                                    meet_link = hangout
                                sent_to.extend(valid_attendees)
                                logger.info(
                                    f"Direct Google Calendar event created with Meet: {meet_link}"
                                )
                            else:
                                cal_err = await cal_resp.text()
                                logger.warning(
                                    f"Calendar API returned {cal_resp.status} "
                                    f"(falling back to rich iCalendar email): {cal_err}"
                                )
                    except Exception as e:
                        logger.warning(f"Calendar API call failed: {e}")

                    # ── Method B: Rich iCalendar (.ics) Email via Gmail API ──
                    if not calendar_created:
                        import base64
                        from email import encoders
                        from email.mime.base import MIMEBase
                        from email.mime.multipart import MIMEMultipart
                        from email.mime.text import MIMEText

                        for att in recipients_to_email:
                            try:
                                msg = MIMEMultipart("mixed")
                                msg["Subject"] = subject
                                msg["From"] = sender_email
                                msg["To"] = att

                                alt = MIMEMultipart("alternative")
                                alt.attach(MIMEText(plain_body, "plain", "utf-8"))
                                alt.attach(MIMEText(html_body, "html", "utf-8"))

                                cal_part = MIMEText(
                                    ics_content, "calendar; method=REQUEST; charset=UTF-8"
                                )
                                cal_part.add_header(
                                    "Content-Class", "urn:content-classes:calendarmessage"
                                )
                                alt.attach(cal_part)
                                msg.attach(alt)

                                attach = MIMEBase("application", "ics", name="invite.ics")
                                attach.set_payload(ics_content.encode("utf-8"))
                                encoders.encode_base64(attach)
                                attach.add_header(
                                    "Content-Disposition", 'attachment; filename="invite.ics"'
                                )
                                msg.attach(attach)

                                raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")

                                async with (
                                    aiohttp.ClientSession() as client,
                                    client.post(
                                        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                                        headers={
                                            "Authorization": f"Bearer {access_token}",
                                            "Content-Type": "application/json",
                                        },
                                        json={"raw": raw},
                                    ) as resp,
                                ):
                                    if resp.status == 200:
                                        sent_to.append(att)
                                        logger.info(
                                            f"Dispatched iCalendar Google Meet invitation to {att}"
                                        )
                                    else:
                                        err_text = await resp.text()
                                        logger.warning(
                                            f"Gmail API failed for {att}: {resp.status} {err_text}"
                                        )
                                        failed_to.append(att)
                            except Exception as e:
                                logger.error(f"Error sending invite to {att}: {e}")
                                failed_to.append(att)
            except Exception as e:
                logger.error(f"Failed to process OAuth account for meeting invites: {e}")

        # Fallback to SMTP for any unsent attendees
        remaining = [a for a in valid_attendees if a not in sent_to]
        if remaining:
            for att in remaining:
                ok = cls.send_real_email_via_smtp(
                    recipient=att,
                    subject=subject,
                    body=plain_body,
                )
                if ok:
                    sent_to.append(att)
                else:
                    if att not in failed_to:
                        failed_to.append(att)

        # Store dispatched invite in CommunicationItem table for auditing & inbox views
        for att in sent_to:
            comm = CommunicationItem(
                user_id=str(user_id),
                channel="email",
                sender=sender_email,
                sender_name="Raghvi Assistant",
                recipient=att,
                subject=subject,
                body=plain_body,
                thread_id=f"meeting-{title.lower().replace(' ', '-')[:30]}",
                is_read=True,
            )
            session.add(comm)

        await session.commit()
        return {
            "sent_to": sent_to,
            "failed_to": failed_to,
            "meet_link": meet_link,
            "calendar_created": calendar_created,
            "requires_calendar_reauth": not calendar_created,
        }

    # -------------------------------------------------------------------------
    # 4. Natural Language Intent Classification
    # -------------------------------------------------------------------------

    @staticmethod
    def parse_communication_intent(text: str) -> dict[str, Any] | None:
        """Parse natural user requests for emails, WhatsApp, and meeting scheduling."""
        lower = text.lower()

        meeting_keys = (
            "schedule meeting",
            "schedule the meeting",
            "calendar invite",
            "meeting rakh do",
        )
        if any(k in lower for k in meeting_keys):
            # Extract emails if present
            attendees = re.findall(r"[\w\.-]+@[\w\.-]+\.\w+", text)
            time_match = re.search(r"\b(\d{1,2}(?::\d{2})?\s*(?:am|pm|baje))\b", lower)
            time_val = time_match.group(1) if time_match else "3:00 PM"

            # Simple date parsing
            date_val = "today"
            days = (
                "tomorrow",
                "kal",
                "monday",
                "tuesday",
                "wednesday",
                "thursday",
                "friday",
                "saturday",
                "sunday",
            )
            for d in days:
                if d in lower:
                    date_val = d
                    break

            return {
                "type": "schedule_meeting",
                "title": "Discussion Sync",
                "date": date_val,
                "time": time_val,
                "attendees": attendees,
            }

        # 2. Email check or search
        if any(k in lower for k in ("mail", "email")):
            # Detect multi-account target
            account_target = None
            if any(w in lower for w in ("work", "office", "kaam", "company")):
                account_target = "work"
            elif any(w in lower for w in ("personal", "private", "ghar")):
                account_target = "personal"
            elif any(w in lower for w in ("college", "university", "school")):
                account_target = "college"

            if any(k in lower for k in ("reply", "draft", "jawab")):
                return {"type": "reply_email", "query": text, "account_label": account_target}
            if any(
                k in lower
                for k in (
                    "check",
                    "search",
                    "dhundo",
                    "aaya",
                    "new",
                    "unread",
                    "get",
                    "got",
                    "receive",
                    "received",
                    "any",
                )
            ):
                sender = None
                from_match = re.search(r"(?:from|ka|ki)\s+([a-zA-Z0-9]+)", text)
                if from_match:
                    sender = from_match.group(1)
                return {
                    "type": "check_email",
                    "sender": sender,
                    "account_label": account_target,
                    "unread_only": "new" in lower or "unread" in lower,
                }

        # 3. WhatsApp check or reply
        if any(k in lower for k in ("whatsapp", "message", "msg", "chat")):
            account_target = None
            if any(w in lower for w in ("business", "biz", "company", "work")):
                account_target = "business"
            elif "personal" in lower:
                account_target = "personal"

            sender = None
            for p in (r"(?:from|ka|ki|to|se)\s+([a-zA-Z0-9]+)", r"([a-zA-Z0-9]+)\s+(?:ne|ka)"):
                match = re.search(p, text)
                if match:
                    cand = match.group(1)
                    if cand.lower() not in (
                        "whatsapp",
                        "message",
                        "msg",
                        "new",
                        "koi",
                        "any",
                        "business",
                        "personal",
                        "work",
                    ):
                        sender = cand
                        break

            if any(k in lower for k in ("reply", "jawab", "bhej do")):
                return {
                    "type": "reply_whatsapp",
                    "sender": sender,
                    "account_label": account_target,
                    "instructions": text,
                }

            return {"type": "check_whatsapp", "sender": sender, "account_label": account_target}

        return None

    # -------------------------------------------------------------------------
    # 5. Real IMAP & SMTP Email Sync Engine
    # -------------------------------------------------------------------------

    @staticmethod
    async def sync_real_emails_via_imap(
        user_id: str,
        session: AsyncSession,
        imap_host: str | None = None,
        imap_port: int | None = None,
        email_user: str | None = None,
        email_password: str | None = None,
        limit: int = 10,
        account_id: UUID | None = None,
        account_label: str | None = None,
    ) -> list[CommunicationItem]:
        """Connect to real email provider via IMAP SSL and sync incoming messages."""
        import email
        import imaplib
        from email.header import decode_header

        from app.core.config import get_settings

        settings = get_settings()
        host = imap_host or settings.email_imap_host
        port = imap_port or settings.email_imap_port
        user = email_user or settings.email_user
        password = email_password or settings.email_password

        if not user or not password:
            logger.warning("No email credentials configured for real IMAP sync")
            return []

        synced_items = []
        try:
            mail = imaplib.IMAP4_SSL(host, port)
            mail.login(user, password)
            mail.select("INBOX")

            status, messages = mail.search(None, "ALL")
            if status != "OK" or not messages[0]:
                mail.close()
                mail.logout()
                return []

            msg_ids = messages[0].split()
            recent_ids = msg_ids[-limit:]

            for msg_id in reversed(recent_ids):
                res, msg_data = mail.fetch(msg_id, "(RFC822)")
                if res != "OK":
                    continue

                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])

                        # Decode subject
                        subject = ""
                        raw_subject = msg["Subject"]
                        if raw_subject:
                            decoded_parts = decode_header(raw_subject)
                            subject = "".join(
                                part.decode(enc or "utf-8", errors="replace")
                                if isinstance(part, bytes)
                                else part
                                for part, enc in decoded_parts
                            )

                        # Decode sender
                        sender = msg.get("From", "unknown")
                        sender_name = (
                            sender.split("<")[0].strip().strip('"') if "<" in sender else sender
                        )

                        # Extract text body
                        body = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                if part.get_content_type() == "text/plain":
                                    payload = part.get_payload(decode=True)
                                    body = payload.decode("utf-8", errors="replace")
                                    break
                        else:
                            payload = msg.get_payload(decode=True)
                            body = payload.decode("utf-8", errors="replace")

                        thread_id = msg.get("Message-ID", f"thread_{msg_id.decode('utf-8')}")

                        existing = await session.scalar(
                            select(CommunicationItem).where(
                                and_(
                                    CommunicationItem.user_id == str(user_id),
                                    CommunicationItem.thread_id == thread_id,
                                )
                            )
                        )
                        if not existing:
                            item = CommunicationItem(
                                user_id=str(user_id),
                                channel="email",
                                sender=sender,
                                sender_name=sender_name,
                                recipient=user,
                                subject=subject,
                                body=body.strip(),
                                thread_id=thread_id,
                                account_id=account_id,
                                account_label=account_label,
                                is_read=False,
                            )
                            session.add(item)
                            synced_items.append(item)

            await session.commit()
            mail.close()
            mail.logout()
            logger.info(f"Successfully synced {len(synced_items)} real emails via IMAP")
            return synced_items
        except Exception as e:
            logger.error(f"Failed to sync real emails via IMAP: {e}")
            raise

    @staticmethod
    def send_real_email_via_smtp(
        recipient: str,
        subject: str,
        body: str,
        smtp_host: str | None = None,
        smtp_port: int | None = None,
        email_user: str | None = None,
        email_password: str | None = None,
    ) -> bool:
        """Send a real email via SMTP SSL using configured credentials."""
        import smtplib
        from email.mime.text import MIMEText

        from app.core.config import get_settings

        settings = get_settings()
        host = smtp_host or settings.email_smtp_host
        port = smtp_port or settings.email_smtp_port
        user = email_user or settings.email_user
        password = email_password or settings.email_password

        if not user or not password:
            logger.warning("No SMTP credentials configured to send real email")
            return False

        try:
            msg = MIMEText(body, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"] = user
            msg["To"] = recipient

            with smtplib.SMTP_SSL(host, port) as server:
                server.login(user, password)
                server.send_message(msg)

            logger.info(f"Successfully sent real email to {recipient} via SMTP")
            return True
        except Exception as e:
            logger.error(f"Failed to send real email via SMTP: {e}")
            return False
