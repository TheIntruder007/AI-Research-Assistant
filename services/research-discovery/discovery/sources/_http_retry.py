"""Shared bounded exponential-backoff GET, honoring `Retry-After`.

Root cause fixed here (see PAPER_OUTPUT_FINAL_DIAGNOSTIC.md finding #3 /
DECISIONS.md D-028): `openalex.py` already had solid retry-on-transient-error
logic, but `arxiv.py` and `pubmed.py` had NONE at all (a single GET,
`raise_for_status()` immediately), and `semantic_scholar.py` only retried a
narrower 429-only case with its own separate loop. When multiple sources hit
a transient error (rate limiting, a 5xx) on the same run, one or more
sources with no retry at all would fail outright — and a real diagnostic run
observed 3 of 4 sources failing simultaneously, producing zero papers and
aborting the whole Discovery stage, twice in a row, for one research
question. This extracts OpenAlex's already-proven approach into one shared
helper so every source gets the same resilience, rather than three
different, inconsistent (or absent) implementations.
"""

from __future__ import annotations

import asyncio

import httpx

DEFAULT_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})


def _retry_after_seconds(resp: httpx.Response) -> float | None:
    value = resp.headers.get("Retry-After")
    if not value:
        return None
    try:
        return float(value)  # delta-seconds form; an HTTP-date form falls through
    except ValueError:
        return None  # to our own backoff below


async def get_with_retry(
    http: httpx.AsyncClient,
    url: str,
    params: dict,
    *,
    headers: dict | None = None,
    attempts: int = 4,
    retry_statuses: frozenset[int] = DEFAULT_RETRY_STATUSES,
    max_wait_seconds: float = 30.0,
) -> httpx.Response:
    """GET with bounded exponential backoff on rate-limit/5xx responses,
    honoring a `Retry-After` header when present. Never retries on a
    successful response or a non-retryable error status (e.g. 400/404) —
    those are returned immediately so the caller's own `raise_for_status()`
    reports the real, non-transient problem without a pointless delay."""

    delay = 1.0
    resp = await http.get(url, params=params, headers=headers)
    for _ in range(attempts - 1):
        if resp.status_code not in retry_statuses:
            return resp
        wait = _retry_after_seconds(resp)
        await asyncio.sleep(min(wait if wait is not None else delay, max_wait_seconds))
        delay *= 2
        resp = await http.get(url, params=params, headers=headers)
    return resp
