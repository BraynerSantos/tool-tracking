"""Attribute schema and attribute-value validation.

Faithful port of tool_db2's ``server/validation.js``, including its
hardening fixes (whitespace-only keys/labels, bool/NaN/Infinity rejection)
and whole-number int-ification so JSON payloads stay tidy (``6`` not ``6.0``).

Guarantees: inch-style decimal values such as ``0.250`` and ``6.35`` round-trip
exactly through both numeric strings and float inputs.
"""

import math

_TYPES = ("text", "number")


def validate_schema(schema):
    """Return None when ``schema`` is valid, else a human-readable error string."""
    if not isinstance(schema, list):
        return "Attribute schema must be an array"
    seen = set()
    for f in schema:
        if not isinstance(f, dict):
            return "Attribute schema must be an array"
        key = f.get("key")
        label = f.get("label")
        ftype = f.get("type")
        if not isinstance(key, str) or not key.strip():
            return "Every attribute needs a key"
        if not isinstance(label, str) or not label.strip():
            return "Every attribute needs a label"
        if ftype not in _TYPES:
            return f'Attribute "{key}" has invalid type (use text or number)'
        if key in seen:
            return f'Duplicate attribute key "{key}"'
        seen.add(key)
    return None


def _to_number(raw):
    """Return a finite float from raw input, or None if it isn't a number.

    Accepts int/float (never bool) and trimmed numeric strings.
    Rejects '', whitespace, NaN, +/-Infinity, and everything else.
    """
    if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
        return None
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return None
        raw = s
    try:
        n = float(raw)
    except (TypeError, ValueError, OverflowError):
        # OverflowError: a huge JSON integer cannot be represented as a float
        return None
    return n if math.isfinite(n) else None


def validate_attributes(schema, attrs):
    """Coerce incoming attributes against ``schema``.

    Returns ``{"ok": True, "clean": {...}}`` on success or
    ``{"ok": False, "errors": {key: "Must be a number"}}`` on failure.
    Unknown keys are stripped; fields absent from ``attrs`` are skipped.
    """
    source = attrs if isinstance(attrs, dict) else {}
    clean = {}
    errors = {}
    for f in schema:
        key = f["key"]
        if key not in source:
            continue
        raw = source[key]
        if f["type"] == "number":
            n = _to_number(raw)
            if n is None:
                errors[key] = "Must be a number"
                continue
            # Keep whole numbers as ints (6, not 6.0); preserve decimals exactly.
            clean[key] = int(n) if n.is_integer() and abs(n) < 1e15 else n
        else:
            clean[key] = "" if raw is None else str(raw)
    if errors:
        return {"ok": False, "errors": errors}
    return {"ok": True, "clean": clean}
