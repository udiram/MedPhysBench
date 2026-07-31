"""Strict JSON decoding and stable hashing helpers for benchmark artifacts."""

from __future__ import annotations

import json
from hashlib import sha256
from typing import Any


class StrictJsonError(ValueError):
    """Raised when provider output violates the benchmark JSON contract."""


class _DuplicateKeyError(StrictJsonError):
    """Raised when a decoded object repeats the same key."""


def decode_strict_json_object(content: str) -> dict[str, Any]:
    """Decode exactly one JSON object with no wrappers, repairs, or duplicate keys."""
    candidate = content.strip()
    if not candidate:
        raise StrictJsonError("empty_response")

    decoder = json.JSONDecoder(
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_non_finite_constant,
    )
    try:
        parsed, end = decoder.raw_decode(candidate)
    except json.JSONDecodeError as error:
        raise StrictJsonError(f"invalid_json:{error.msg}") from error
    except _DuplicateKeyError as error:
        raise StrictJsonError(str(error)) from error
    except ValueError as error:
        raise StrictJsonError(str(error)) from error

    if candidate[end:].strip():
        raise StrictJsonError("trailing_content")
    if not isinstance(parsed, dict):
        raise StrictJsonError(f"decoded_type:{type(parsed).__name__}")
    return parsed


def hash_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def stable_hash(value: Any) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return sha256(canonical.encode("utf-8")).hexdigest()


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    decoded: dict[str, Any] = {}
    for key, value in pairs:
        if key in decoded:
            raise _DuplicateKeyError(f"duplicate_key:{key}")
        decoded[key] = value
    return decoded


def _reject_non_finite_constant(value: str) -> None:
    raise StrictJsonError(f"non_finite_number:{value}")
