import json
from pathlib import Path
from typing import Any

import httpx
import pytest

import jobbot.email as email_mod
from jobbot.context import RunContext, build_context
from jobbot.errors import EmailBlocked
from jobbot.http import make_client
from jobbot.log import redact
from jobbot.settings import load_settings


def ctx_with(monkeypatch: pytest.MonkeyPatch, **env: str) -> RunContext:
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return build_context(load_settings())


def test_non_prod_without_test_inbox_refuses(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = ctx_with(monkeypatch)
    with pytest.raises(EmailBlocked, match="JOBBOT_EMAIL_TEST_TO"):
        email_mod.resolve_recipient(ctx, "me@example.com")


def test_non_prod_redirects_to_test_inbox(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = ctx_with(monkeypatch, JOBBOT_EMAIL_TEST_TO="test@example.com")
    assert email_mod.resolve_recipient(ctx, "me@example.com") == (
        "test@example.com",
        "[test → me@example.com] ",
    )


def test_prod_sends_to_intended(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = ctx_with(monkeypatch, JOBBOT_ENV="prod", JOBBOT_EMAIL_TEST_TO="test@example.com")
    assert email_mod.resolve_recipient(ctx, "me@example.com") == ("me@example.com", "")


def test_to_flag_overrides_everything(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JOBBOT_ENV", "prod")
    ctx = build_context(load_settings(), to="qa@example.com")
    assert email_mod.resolve_recipient(ctx, "me@example.com") == (
        "qa@example.com",
        "[test → me@example.com] ",
    )


async def test_preview_writes_file_and_sends_nothing(tmp_path: Path) -> None:
    ctx = build_context(load_settings(), preview=tmp_path / "out.html")
    d = await email_mod.send_email(ctx, to="me@example.com", subject="s", html="<p>hi</p>")
    assert not d.sent
    assert (tmp_path / "out.html").read_text() == "<p>hi</p>"


async def test_dry_run_sends_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JOBBOT_EMAIL_TEST_TO", "test@example.com")
    ctx = build_context(load_settings(), dry_run=True)
    d = await email_mod.send_email(ctx, to="me@example.com", subject="s", html="x")
    assert not d.sent
    assert d.to == "test@example.com"


async def test_live_send_posts_to_resend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JOBBOT_EMAIL_TEST_TO", "test@example.com")
    monkeypatch.setenv("JOBBOT_RESEND_API_KEY", "re_testkey123456")
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["Authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": "email_123"})

    monkeypatch.setattr(
        email_mod, "make_client", lambda c: make_client(c, inner=httpx.MockTransport(handler))
    )
    ctx = build_context(load_settings())
    d = await email_mod.send_email(ctx, to="me@example.com", subject="Hello", html="<b>x</b>")
    assert d.sent and d.provider_id == "email_123"
    assert seen["auth"] == "Bearer re_testkey123456"
    assert seen["body"]["to"] == ["test@example.com"]
    assert seen["body"]["subject"] == "[test → me@example.com] Hello"


def test_log_redaction() -> None:
    event = redact(
        None,
        "info",
        {
            "api_key": "sk-abcdefgh12345",
            "resume_text": "my whole resume",
            "message": "calling with Bearer abc.def and re_ABCDEFGH1234",
            "count": 3,
        },
    )
    assert event["api_key"] == "[redacted]"
    assert event["resume_text"] == "[redacted]"
    assert "abc.def" not in event["message"] and "re_ABCDEFGH1234" not in event["message"]
    assert event["count"] == 3
