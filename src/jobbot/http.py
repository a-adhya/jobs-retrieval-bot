from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from aiolimiter import AsyncLimiter
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_exponential

from jobbot.context import RunContext
from jobbot.errors import FixtureMissing

SECRET_PARAMS = {"api_key", "apikey", "key", "token", "access_token", "client_secret"}
SECRET_HEADERS = {"authorization", "x-api-key", "api-key", "x-subscription-token", "cookie", "set-cookie"}
REDACTED = "REDACTED"
Mode = Literal["live", "record", "replay"]


def redact_url(url: str) -> str:
    parts = urlsplit(url)
    query = [(k, REDACTED if k.lower() in SECRET_PARAMS else v) for k, v in parse_qsl(parts.query, True)]
    return urlunsplit(parts._replace(query=urlencode(sorted(query))))


def fixture_path(root: Path, request: httpx.Request) -> Path:
    """Keyed on method, secret-free URL and body, so the same request always maps to the same file."""
    url = redact_url(str(request.url))
    digest = hashlib.sha1(request.method.encode() + url.encode() + (request.content or b"")).hexdigest()
    return root / (request.url.host or "unknown-host") / f"{digest}.json"


def _dump(request: httpx.Request, response: httpx.Response) -> dict[str, object]:
    body = response.content
    try:
        body_field: dict[str, str] = {"text": body.decode("utf-8")}
    except UnicodeDecodeError:
        body_field = {"base64": base64.b64encode(body).decode()}
    return {
        "request": {"method": request.method, "url": redact_url(str(request.url))},
        "response": {
            "status": response.status_code,
            "headers": {
                k: v
                for k, v in response.headers.items()
                if k.lower() not in SECRET_HEADERS and k.lower() not in {"content-encoding", "content-length"}
            },
            **body_field,
        },
    }


def _load(data: dict[str, dict[str, object]], request: httpx.Request) -> httpx.Response:
    resp = data["response"]
    content = (
        base64.b64decode(str(resp["base64"])) if "base64" in resp else str(resp.get("text", "")).encode()
    )
    headers = resp.get("headers") or {}
    assert isinstance(headers, dict)
    return httpx.Response(int(str(resp["status"])), headers=headers, content=content, request=request)


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    return isinstance(exc, httpx.HTTPStatusError) and (
        exc.response.status_code == 429 or exc.response.status_code >= 500
    )


class RecordReplayTransport(httpx.AsyncBaseTransport):
    """live: network with per-host rate limits and retries on 429/5xx/connection errors.
    record: live, plus every response saved under `root` with secrets stripped.
    replay: saved responses only; a request with no saved response raises FixtureMissing."""

    def __init__(
        self,
        mode: Mode,
        root: Path | None = None,
        inner: httpx.AsyncBaseTransport | None = None,
        requests_per_second: float = 5,
        max_retries: int = 4,
    ) -> None:
        if mode != "live" and root is None:
            raise ValueError(f"{mode} mode needs a fixtures directory")
        self.mode = mode
        self.root = root
        self.inner = inner or httpx.AsyncHTTPTransport()
        self.rps = requests_per_second
        self.max_retries = max_retries
        self._limiters: dict[str, AsyncLimiter] = {}

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if self.mode == "replay":
            assert self.root is not None
            path = fixture_path(self.root, request)
            if not path.exists():
                raise FixtureMissing(
                    f"No saved response for {request.method} {redact_url(str(request.url))} (expected {path})"
                )
            return _load(json.loads(path.read_text()), request)

        response = await self._send_live(request)
        if self.mode == "record":
            assert self.root is not None
            await response.aread()
            path = fixture_path(self.root, request)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(_dump(request, response), indent=2, sort_keys=True))
        return response

    async def _send_live(self, request: httpx.Request) -> httpx.Response:
        host = request.url.host or ""
        limiter = self._limiters.setdefault(host, AsyncLimiter(self.rps, 1))
        response: httpx.Response | None = None
        async for attempt in AsyncRetrying(
            retry=retry_if_exception(_retryable),
            stop=stop_after_attempt(self.max_retries + 1),
            wait=wait_exponential(multiplier=0.5, max=30),
            reraise=True,
        ):
            with attempt:
                async with limiter:
                    response = await self.inner.handle_async_request(request)
                if response.status_code == 429 or response.status_code >= 500:
                    await response.aread()
                    raise httpx.HTTPStatusError("retryable status", request=request, response=response)
        assert response is not None
        return response

    async def aclose(self) -> None:
        await self.inner.aclose()


def make_client(ctx: RunContext, *, inner: httpx.AsyncBaseTransport | None = None) -> httpx.AsyncClient:
    http = ctx.settings.http
    transport = RecordReplayTransport(
        ctx.http_mode,
        root=ctx.fixtures_dir or ctx.record_dir,
        inner=inner,
        requests_per_second=http.requests_per_second_per_host,
        max_retries=http.max_retries,
    )
    return httpx.AsyncClient(
        transport=transport,
        timeout=http.timeout_seconds,
        headers={"User-Agent": "jobbot/0.1"},
        follow_redirects=True,
    )
