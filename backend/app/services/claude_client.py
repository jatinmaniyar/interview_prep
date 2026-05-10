"""Anthropic client wrapper with prompt caching + spend tracking.

Uses the latest Anthropic Python SDK. Defaults to claude-opus-4-7. Prompt caching is
enabled by passing `cache_control={"type": "ephemeral"}` on stable system blocks; cache
is per-message-prefix and lives ~5 minutes. Cache reads cost 10% of normal input tokens.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Iterable

from anthropic import Anthropic
from sqlalchemy import func, select

from app.config import settings
from app.db import SessionLocal
from app.models import SpendLog

# Per-million-token pricing (USD) for claude-opus-4-7.
# Update via env if/when pricing changes; this is a hard-coded ballpark for the local cap.
PRICE_INPUT = 15.0
PRICE_OUTPUT = 75.0
PRICE_CACHE_WRITE = 18.75  # 1.25x input
PRICE_CACHE_READ = 1.5     # 0.10x input

DEFAULT_MODEL = "claude-opus-4-7"


def _client() -> Anthropic:
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set in .env")
    return Anthropic(api_key=settings.anthropic_api_key)


def _today_spend(db) -> float:
    today = date.today()
    total = db.execute(
        select(func.coalesce(func.sum(SpendLog.estimated_usd), 0.0)).where(
            func.date(SpendLog.occurred_at) == today
        )
    ).scalar_one()
    return float(total or 0.0)


def _record_usage(component: str, usage: dict, note: str | None = None) -> float:
    inp = usage.get("input_tokens", 0)
    out = usage.get("output_tokens", 0)
    cw = usage.get("cache_creation_input_tokens", 0)
    cr = usage.get("cache_read_input_tokens", 0)
    cost = (
        inp * PRICE_INPUT
        + out * PRICE_OUTPUT
        + cw * PRICE_CACHE_WRITE
        + cr * PRICE_CACHE_READ
    ) / 1_000_000
    db = SessionLocal()
    try:
        db.add(
            SpendLog(
                occurred_at=datetime.utcnow(),
                component=component,
                input_tokens=inp,
                output_tokens=out,
                cache_read_tokens=cr,
                cache_write_tokens=cw,
                estimated_usd=cost,
                note=note,
            )
        )
        db.commit()
    finally:
        db.close()
    return cost


def check_budget() -> None:
    db = SessionLocal()
    try:
        spent = _today_spend(db)
    finally:
        db.close()
    if spent >= settings.max_daily_spend_usd:
        raise RuntimeError(
            f"Daily spend cap hit: ${spent:.2f} >= ${settings.max_daily_spend_usd:.2f}"
        )


def message(
    component: str,
    system_blocks: list[dict],
    messages: list[dict],
    *,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 4096,
    note: str | None = None,
) -> tuple[str, float]:
    """Send a single message turn. Returns (text_response, cost_usd).

    `system_blocks`: list of {type:"text", text:"...", cache_control?: {"type":"ephemeral"}}.
                     The first 1-2 blocks should be cached for repeat calls.
    """
    check_budget()
    client = _client()
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_blocks,
        messages=messages,
    )
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    cost = _record_usage(component, resp.usage.model_dump() if hasattr(resp.usage, "model_dump") else dict(resp.usage), note=note)
    return text, cost
