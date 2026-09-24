"""Shared helpers for routers."""


def _clean(value):
    """Coerce a request field to a trimmed string ('' when absent/None)."""
    return str(value).strip() if value is not None else ""
