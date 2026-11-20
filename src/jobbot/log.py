from __future__ import annotations

import logging
import re
from collections.abc import MutableMapping
from typing import Any

import structlog

SENSITIVE_KEYS = re.compile(
    r"(api[_-]?key|authorization|token|secret|password|resume_text|resume_bytes|cookie)", re.I
)
SENSITIVE_VALUES = re.compile(r"\b(sk-[A-Za-z0-9_\-]{8,}|re_[A-Za-z0-9_]{8,}|Bearer\s+\S+)")
REDACTED = "[redacted]"


def redact(_: Any, __: str, event_dict: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    for key, value in list(event_dict.items()):
        if SENSITIVE_KEYS.search(key):
            event_dict[key] = REDACTED
        elif isinstance(value, str):
            event_dict[key] = SENSITIVE_VALUES.sub(REDACTED, value)
    return event_dict


def configure_logging(fmt: str = "console", level: int = logging.INFO) -> None:
    renderer: Any = (
        structlog.processors.JSONRenderer() if fmt == "json" else structlog.dev.ConsoleRenderer(colors=False)
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            redact,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=False,
    )


def get_logger(name: str | None = None) -> Any:
    return structlog.get_logger(name)
