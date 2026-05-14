from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def latest_processed_received_at(rows: list[Any]) -> str | None:
    timestamps = [_parse_datetime(_received_at(row)) for row in rows]
    timestamps = [timestamp for timestamp in timestamps if timestamp is not None]
    if not timestamps:
        return None
    return max(timestamps).isoformat()


def filter_new_threads(
    fetched_threads: list[dict[str, Any]],
    *,
    since_received_at: str | None,
    processed_source_refs: set[str],
) -> list[dict[str, Any]]:
    cutoff = _parse_datetime(since_received_at)
    rows: list[dict[str, Any]] = []
    for thread in fetched_threads:
        source_ref = str(thread.get("source_ref") or "")
        if source_ref in processed_source_refs:
            continue
        received_at = _parse_datetime(thread.get("received_at"))
        if cutoff and received_at and received_at <= cutoff:
            continue
        if cutoff and received_at is None:
            continue
        rows.append(thread)
    rows.sort(key=lambda item: str(item.get("received_at") or ""), reverse=True)
    return rows


def _received_at(row: Any) -> Any:
    if isinstance(row, dict):
        return row.get("received_at")
    return getattr(row, "received_at", None)


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
