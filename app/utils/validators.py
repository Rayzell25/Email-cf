"""Validation + normalization helpers for email local parts and names."""
from __future__ import annotations

import re
from dataclasses import dataclass

# Allowed characters in a local-part: a-z 0-9 . _ -
_LOCAL_PART_RE = re.compile(r"^[a-z0-9._-]+$")
MAX_LOCAL_PART_LENGTH = 64


@dataclass
class ValidationResult:
    ok: bool
    value: str = ""
    error: str = ""


def normalize_name(value: str) -> str:
    """Lowercase + strip. Used for global uniqueness comparison of random names.

    Only alphanumerics are kept for the *normalized* form so that "CasterBington"
    and "casterbington" compare equal. (Display form keeps original casing.)
    """
    return re.sub(r"[^a-z0-9]", "", (value or "").strip().lower())


def normalize_local_part(value: str) -> str:
    """Lowercase + strip for the local part actually sent to Cloudflare."""
    return (value or "").strip().lower()


def validate_local_part(raw: str) -> ValidationResult:
    """Validate a manually entered email local part (the bit before '@')."""
    if raw is None:
        return ValidationResult(False, error="Empty input.")

    value = raw.strip().lower()

    if not value:
        return ValidationResult(False, error="Email name cannot be empty.")
    if " " in value or "\t" in value or "\n" in value:
        return ValidationResult(False, error="Email name cannot contain spaces.")
    if "@" in value:
        return ValidationResult(
            False, error="Just type the name, without @ or domain."
        )
    if len(value) > MAX_LOCAL_PART_LENGTH:
        return ValidationResult(
            False, error=f"Email name can be at most {MAX_LOCAL_PART_LENGTH} characters."
        )
    if not _LOCAL_PART_RE.match(value):
        return ValidationResult(
            False,
            error="Invalid characters. Allowed: a-z 0-9 dot underscore hyphen.",
        )
    # cosmetic rules: must not start/end with a separator or have doubled dots
    if value[0] in "._-" or value[-1] in "._-":
        return ValidationResult(
            False, error="Name cannot start or end with a dot, hyphen, or underscore."
        )
    if ".." in value:
        return ValidationResult(False, error="Two consecutive dots are not allowed.")

    return ValidationResult(True, value=value)
