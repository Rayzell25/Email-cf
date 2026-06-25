"""Structured logging setup.

A secret-redaction filter ensures tokens / API keys never leak into logs.
"""
from __future__ import annotations

import logging
import re
import sys

# Patterns that look like secrets are redacted from every log record.
# Each entry: (compiled pattern with one capture group for the prefix to keep).
_SECRET_PATTERNS = [
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]{8,}"),
    re.compile(r"(?i)(api[_-]?token[\"'=:\s]+)[A-Za-z0-9._\-]{8,}"),
    re.compile(r"(?i)(api[_-]?hash[\"'=:\s]+)[A-Za-z0-9._\-]{8,}"),
    re.compile(r"(\b\d{6,}:)[A-Za-z0-9_\-]{30,}\b"),  # telegram bot token shape
]

_REDACTED = "***REDACTED***"


class SecretRedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return True
        redacted = msg
        for pattern in _SECRET_PATTERNS:
            redacted = pattern.sub(lambda m: (m.group(1) or "") + _REDACTED, redacted)
        if redacted != msg:
            record.msg = redacted
            record.args = ()
        return True


def setup_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    handler.addFilter(SecretRedactionFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # aiogram / httpx can be noisy; keep them at WARNING unless debugging.
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
