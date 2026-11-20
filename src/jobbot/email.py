from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from jobbot.context import RunContext
from jobbot.errors import EmailBlocked
from jobbot.http import make_client
from jobbot.log import get_logger

RESEND_URL = "https://api.resend.com/emails"
log = get_logger(__name__)


@dataclass
class Delivery:
    to: str | None
    subject: str
    sent: bool
    provider_id: str | None = None
    preview_path: Path | None = None


def resolve_recipient(ctx: RunContext, intended: str) -> tuple[str, str]:
    """Returns (recipient, subject_prefix). Outside prod, mail only ever goes to the test inbox."""
    if ctx.email_to:
        return ctx.email_to, f"[test → {intended}] " if ctx.email_to != intended else ""
    if ctx.settings.env == "prod":
        return intended, ""
    test_to = ctx.settings.email_test_to
    if not test_to:
        raise EmailBlocked(
            f"Not sending to {intended}: JOBBOT_ENV={ctx.settings.env} only sends to JOBBOT_EMAIL_TEST_TO, "
            "which is not set. Set it, pass --to, or use --preview."
        )
    return test_to, "" if test_to == intended else f"[test → {intended}] "


async def send_email(
    ctx: RunContext, *, to: str, subject: str, html: str, text: str | None = None
) -> Delivery:
    if ctx.preview_path:
        ctx.preview_path.parent.mkdir(parents=True, exist_ok=True)
        ctx.preview_path.write_text(html)
        log.info("email written to preview", path=str(ctx.preview_path), subject=subject)
        return Delivery(to=None, subject=subject, sent=False, preview_path=ctx.preview_path)

    recipient, prefix = resolve_recipient(ctx, to)
    subject = prefix + subject
    if ctx.dry_run:
        log.info("dry run: email not sent", to=recipient, subject=subject)
        return Delivery(to=recipient, subject=subject, sent=False)

    key = ctx.settings.resend_api_key
    if key is None:
        raise EmailBlocked("JOBBOT_RESEND_API_KEY is not set")
    payload: dict[str, object] = {
        "from": ctx.settings.email_from,
        "to": [recipient],
        "subject": subject,
        "html": html,
    }
    if text:
        payload["text"] = text
    async with make_client(ctx) as client:
        resp = await client.post(
            RESEND_URL, json=payload, headers={"Authorization": f"Bearer {key.get_secret_value()}"}
        )
    if resp.status_code >= 400:
        raise EmailBlocked(f"Resend rejected the email ({resp.status_code}): {resp.text}")
    provider_id = resp.json().get("id")
    log.info("email sent", to=recipient, subject=subject, provider_id=provider_id)
    return Delivery(to=recipient, subject=subject, sent=True, provider_id=provider_id)
