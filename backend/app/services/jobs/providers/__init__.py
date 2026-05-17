"""Job board provider adapters.

Each provider exposes:
    fetch(external_org: str) -> list[RawJob]

RawJob is a small dict the normalizer can consume. Adding a new provider
means dropping a new module here and registering it in PROVIDERS below.
"""
from __future__ import annotations

from typing import Callable, Iterable

from . import greenhouse, lever, ashby

# (source_name, fetch_fn)
PROVIDERS: dict[str, Callable[[str], Iterable[dict]]] = {
    "greenhouse": greenhouse.fetch,
    "lever": lever.fetch,
    "ashby": ashby.fetch,
}
