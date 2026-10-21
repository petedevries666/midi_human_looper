"""Versioned, UI-neutral native expressive transformer patch contract.

This module validates the data *before* it crosses into a JACK worker.
It does not imply these types are registered in the production EEL engine.
"""
from __future__ import annotations

import copy
import math

VERSION = 1
MAX_POINTS = 16
DEFAULT_HUMANIZER = {
    "version": VERSION, "type": "humanizer", "enabled": False,
    "timingMs": 0.0, "biasMs": 0.0, "velocityPercent": 0.0,
    "distribution": "gaussian", "variation": "fixed",
    "scope": "group", "seed": 1,
}
DEFAULT_VELOCITY_CURVES = {
    "version": VERSION, "type": "velocity_curves", "enabled": True,
    "amount": 100.0, "points": [[1, 1], [127, 127]],
}
DEFAULTS = {
    "humanizer": DEFAULT_HUMANIZER,
    "velocity_curves": DEFAULT_VELOCITY_CURVES,
}


def _number(value, low, high, field):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{field}: expected finite number")
    if not low <= value <= high:
        raise ValueError(f"{field}: out of range [{low}, {high}]")
    return float(value)


def validate(value):
    """Strict validation, with stable defaults and no silent key dropping."""
    if not isinstance(value, dict):
        raise ValueError("transformer must be an object")
    kind = value.get("type")
    if kind not in DEFAULTS:
        raise ValueError("unsupported transformer")
    result = copy.deepcopy(DEFAULTS[kind])
    if set(value) - set(result):
        raise ValueError("unknown transformer fields")
    if value.get("version", VERSION) != VERSION or type(value.get("version", VERSION)) is not int:
        raise ValueError("unsupported transformer version")
    result.update(copy.deepcopy(value))
    if type(result["enabled"]) is not bool:
        raise ValueError("enabled must be a boolean")
    if kind == "humanizer":
        for field, lo, hi in (
            ("timingMs", 0, 2000), ("biasMs", -2000, 2000),
            ("velocityPercent", 0, 100),
        ):
            result[field] = _number(result[field], lo, hi, field)
        for field, choices in (
            ("distribution", ("gaussian", "uniform")),
            ("variation", ("fixed", "evolving")),
            ("scope", ("group", "notes")),
        ):
            if result[field] not in choices:
                raise ValueError(f"{field}: invalid choice")
        if type(result["seed"]) is not int or not 0 <= result["seed"] <= 4294967295:
            raise ValueError("seed: expected unsigned 32-bit integer")
    else:
        result["amount"] = _number(result["amount"], 0, 100, "amount")
        points = result["points"]
        if not isinstance(points, list) or not 2 <= len(points) <= MAX_POINTS:
            raise ValueError("points: expected 2..16 points")
        last_x = 0
        for point in points:
            if not isinstance(point, list) or len(point) != 2:
                raise ValueError("point: expected [x, y]")
            x, y = point
            if type(x) is not int or type(y) is not int:
                raise ValueError("point coordinates must be integers")
            if not (1 <= x <= 127 and 1 <= y <= 127 and x > last_x):
                raise ValueError("points must have increasing x, within 1..127")
            last_x = x
        if points[0][0] != 1 or points[-1][0] != 127:
            raise ValueError("curve endpoints must cover 1..127")
    return result


def defaults(kind):
    if kind not in DEFAULTS:
        raise ValueError("unknown transformer")
    return copy.deepcopy(DEFAULTS[kind])


def validate_patch(patch):
    """Validate isolated editor patch; never rewrite existing chain presets."""
    if not isinstance(patch, dict) or set(patch) != {"expressiveVersion", "modules"}:
        raise ValueError("expected expressiveVersion and modules")
    if type(patch["expressiveVersion"]) is not int or patch["expressiveVersion"] != VERSION:
        raise ValueError("unsupported patch version")
    if not isinstance(patch["modules"], list) or len(patch["modules"]) > 6:
        raise ValueError("modules must be an array of up to six entries")
    return {"expressiveVersion": VERSION,
            "modules": [validate(item) for item in patch["modules"]]}
