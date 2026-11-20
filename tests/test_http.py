import json
from pathlib import Path

import httpx
import pytest

from jobbot.context import build_context
from jobbot.errors import FixtureMissing
from jobbot.http import RecordReplayTransport, make_client, redact_url
from jobbot.settings import load_settings


class Counting(httpx.MockTransport):
    def __init__(self, statuses: list[int], body: dict[str, object] | None = None) -> None:
        self.calls = 0
        self.statuses = statuses

        def handler(request: httpx.Request) -> httpx.Response:
            status = self.statuses[min(self.calls, len(self.statuses) - 1)]
            self.calls += 1
            return httpx.Response(
                status, json=body or {"ok": True}, headers={"Set-Cookie": "session=abc", "X-Ok": "1"}
            )

        super().__init__(handler)


def test_redact_url_strips_secret_params() -> None:
    url = "https://api.example.com/v1/search?q=ml&api_key=sk-secret&token=t"
    assert redact_url(url) == "https://api.example.com/v1/search?api_key=REDACTED&q=ml&token=REDACTED"


async def test_record_then_replay(tmp_path: Path) -> None:
    inner = Counting([200], {"jobs": [1, 2]})
    record_ctx = build_context(load_settings(), record_fixtures=tmp_path)
    url = "https://boards-api.greenhouse.io/v1/boards/acme/jobs?content=true&api_key=sk-shh"
    async with make_client(record_ctx, inner=inner) as client:
        live = await client.get(url, headers={"Authorization": "Bearer sk-shh"})
    assert live.json() == {"jobs": [1, 2]}

    saved = list(tmp_path.rglob("*.json"))
    assert len(saved) == 1
    raw = saved[0].read_text()
    assert "sk-shh" not in raw
    assert "session=abc" not in raw
    assert json.loads(raw)["response"]["headers"]["x-ok"] == "1"

    replay_ctx = build_context(load_settings(), fixtures=tmp_path)
    async with make_client(replay_ctx) as client:
        replayed = await client.get(url)
    assert replayed.status_code == 200
    assert replayed.json() == {"jobs": [1, 2]}
    assert inner.calls == 1, "replay must not touch the network"


async def test_replay_missing_fixture_fails_loudly(tmp_path: Path) -> None:
    ctx = build_context(load_settings(), fixtures=tmp_path)
    async with make_client(ctx) as client:
        with pytest.raises(FixtureMissing, match=r"api\.lever\.co"):
            await client.get("https://api.lever.co/v0/postings/acme")


async def test_retries_on_5xx_then_succeeds() -> None:
    inner = Counting([503, 200])
    transport = RecordReplayTransport("live", inner=inner, requests_per_second=100, max_retries=2)
    async with httpx.AsyncClient(transport=transport) as client:
        resp = await client.get("https://example.com/x")
    assert resp.status_code == 200
    assert inner.calls == 2


async def test_404_is_not_retried() -> None:
    inner = Counting([404])
    transport = RecordReplayTransport("live", inner=inner, requests_per_second=100, max_retries=3)
    async with httpx.AsyncClient(transport=transport) as client:
        resp = await client.get("https://example.com/missing")
    assert resp.status_code == 404
    assert inner.calls == 1


async def test_gives_up_after_max_retries() -> None:
    inner = Counting([500])
    transport = RecordReplayTransport("live", inner=inner, requests_per_second=100, max_retries=1)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await client.get("https://example.com/down")
    assert inner.calls == 2


def test_record_and_replay_need_a_directory() -> None:
    with pytest.raises(ValueError):
        RecordReplayTransport("replay")
