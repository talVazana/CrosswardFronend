"""Runtime limits for image parsing, Gemini extraction, and uploads.

Every value has a safe default and can be overridden with an environment
variable or at runtime through the GOD window. Overrides are kept in this
process for now; they will move to shared Firestore settings when the database
becomes the source of truth. Missing or invalid configuration always falls back
to the default, never to unlimited usage.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, fields
from typing import Any

_MB = 1024 * 1024


@dataclass(frozen=True)
class LimitSpec:
    key: str
    env: str
    label: str
    kind: str
    default: int | bool
    minimum: int | None = None
    maximum: int | None = None
    unit: str = ""


LIMIT_SPECS: tuple[LimitSpec, ...] = (
    LimitSpec(
        "parser_timeout_seconds",
        "IMAGE_PARSER_TIMEOUT_SECONDS",
        "Local parser timeout",
        "int",
        30,
        5,
        300,
        "seconds",
    ),
    LimitSpec(
        "image_processing_timeout_seconds",
        "IMAGE_PROCESSING_TIMEOUT_SECONDS",
        "Whole image job timeout",
        "int",
        120,
        15,
        900,
        "seconds",
    ),
    LimitSpec(
        "gemini_timeout_seconds",
        "GEMINI_TIMEOUT_SECONDS",
        "Gemini timeout per attempt",
        "int",
        45,
        5,
        300,
        "seconds",
    ),
    LimitSpec(
        "gemini_max_attempts",
        "GEMINI_MAX_ATTEMPTS",
        "Gemini attempts",
        "int",
        2,
        1,
        2,
        "attempts",
    ),
    LimitSpec(
        "max_grid_size",
        "MAX_GRID_SIZE",
        "Maximum grid size",
        "int",
        20,
        5,
        50,
        "cells",
    ),
    LimitSpec(
        "max_clues",
        "MAX_CLUES",
        "Maximum clues",
        "int",
        500,
        1,
        2000,
        "clues",
    ),
    LimitSpec(
        "max_clue_length",
        "MAX_CLUE_LENGTH",
        "Maximum clue length",
        "int",
        500,
        10,
        5000,
        "characters per clue",
    ),
    LimitSpec(
        "max_total_clue_chars",
        "MAX_TOTAL_CLUE_CHARS",
        "Maximum total clue text",
        "int",
        20000,
        1000,
        100000,
        "characters",
    ),
    LimitSpec(
        "max_upload_bytes",
        "MAX_UPLOAD_BYTES",
        "Maximum upload size",
        "int",
        10 * _MB,
        1 * _MB,
        50 * _MB,
        "bytes",
    ),
    LimitSpec(
        "max_image_dimension",
        "MAX_IMAGE_DIMENSION",
        "Maximum image dimension",
        "int",
        8000,
        500,
        20000,
        "pixels",
    ),
    LimitSpec(
        "gemini_max_per_hour",
        "GEMINI_MAX_PER_HOUR",
        "Extractions per hour",
        "int",
        5,
        1,
        100,
        "jobs",
    ),
    LimitSpec(
        "gemini_max_per_day",
        "GEMINI_MAX_PER_DAY",
        "Extractions per day",
        "int",
        10,
        1,
        500,
        "jobs",
    ),
    LimitSpec(
        "image_parser_enabled",
        "IMAGE_PARSER_ENABLED",
        "Image parser enabled",
        "bool",
        True,
    ),
    LimitSpec(
        "gemini_extraction_enabled",
        "GEMINI_EXTRACTION_ENABLED",
        "Gemini extraction enabled",
        "bool",
        True,
    ),
    LimitSpec(
        "telegram_notifications_enabled",
        "TELEGRAM_NOTIFICATIONS_ENABLED",
        "Telegram notifications enabled",
        "bool",
        True,
    ),
)

_SPECS_BY_KEY = {spec.key: spec for spec in LIMIT_SPECS}
_OVERRIDES: dict[str, Any] = {}


def _int_env(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    if value < minimum or value > maximum:
        return default
    return value


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _resolve(spec: LimitSpec) -> int | bool:
    if spec.key in _OVERRIDES:
        return _OVERRIDES[spec.key]
    if spec.kind == "bool":
        return _bool_env(spec.env, bool(spec.default))
    return _int_env(spec.env, int(spec.default), spec.minimum or 0, spec.maximum or 0)


@dataclass(frozen=True)
class Limits:
    parser_timeout_seconds: int
    image_processing_timeout_seconds: int
    gemini_timeout_seconds: int
    gemini_max_attempts: int
    max_grid_size: int
    max_clues: int
    max_clue_length: int
    max_total_clue_chars: int
    max_upload_bytes: int
    max_image_dimension: int
    gemini_max_per_hour: int
    gemini_max_per_day: int
    image_parser_enabled: bool
    gemini_extraction_enabled: bool
    telegram_notifications_enabled: bool


def get_limits() -> Limits:
    return Limits(**{spec.key: _resolve(spec) for spec in LIMIT_SPECS})


def _coerce(spec: LimitSpec, value: Any) -> int | bool:
    if spec.kind == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
        raise ValueError(f"{spec.label} must be a boolean")
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError(f"{spec.label} must be a number")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{spec.label} must be a number") from exc
    if spec.minimum is not None and number < spec.minimum:
        raise ValueError(f"{spec.label} must be at least {spec.minimum}")
    if spec.maximum is not None and number > spec.maximum:
        raise ValueError(f"{spec.label} must be at most {spec.maximum}")
    return number


def set_overrides(updates: dict[str, Any]) -> dict[str, int | bool]:
    """Validate and apply runtime overrides. Raises ValueError on bad input."""
    cleaned: dict[str, int | bool] = {}
    for key, value in updates.items():
        spec = _SPECS_BY_KEY.get(key)
        if spec is None:
            raise ValueError(f"Unknown setting: {key}")
        cleaned[key] = _coerce(spec, value)
    _OVERRIDES.update(cleaned)
    return {key: _resolve(spec) for key, spec in _SPECS_BY_KEY.items()}


def reset_overrides() -> None:
    _OVERRIDES.clear()


def current_overrides() -> dict[str, Any]:
    """Return a copy of the active runtime overrides."""
    return dict(_OVERRIDES)


def restore_overrides(values: dict[str, Any]) -> None:
    """Apply previously saved overrides. Invalid entries are skipped."""
    cleaned: dict[str, int | bool] = {}
    for key, value in (values or {}).items():
        spec = _SPECS_BY_KEY.get(key)
        if spec is None:
            continue
        try:
            cleaned[key] = _coerce(spec, value)
        except ValueError:
            continue
    _OVERRIDES.update(cleaned)


def limit_snapshot() -> list[dict[str, Any]]:
    """Return every setting with its current and default value for the GOD UI."""
    snapshot = []
    for spec in LIMIT_SPECS:
        snapshot.append(
            {
                "key": spec.key,
                "env": spec.env,
                "label": spec.label,
                "kind": spec.kind,
                "unit": spec.unit,
                "value": _resolve(spec),
                "default": spec.default,
                "minimum": spec.minimum,
                "maximum": spec.maximum,
                "overridden": spec.key in _OVERRIDES,
            }
        )
    return snapshot


def limit_field_names() -> set[str]:
    return {field.name for field in fields(Limits)}
