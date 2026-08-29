"""Regression tests for DECISIONS.md D-028's Discovery-stage resilience fix.

Root cause: `arxiv.py` and `pubmed.py` had NO retry logic at all (a single
GET, immediate `raise_for_status()`), and `semantic_scholar.py` only
retried a narrower 429-only case — while `openalex.py` already had solid,
general retry-on-transient-error logic. A real diagnostic run observed 3 of
4 sources failing simultaneously on the same query (HTTPStatusError from
each), producing a total Discovery-stage failure ("No papers found in any
source") twice in a row for one research question.

Fix: extracted OpenAlex's approach into a shared `_http_retry.get_with_retry()`
helper, now used by all four sources.
"""

import asyncio
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "research-discovery"))

from discovery.sources._http_retry import get_with_retry  # noqa: E402


def _transport(status_sequence: list[int], body: bytes = b"{}") -> httpx.MockTransport:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        status = status_sequence[min(calls["n"], len(status_sequence) - 1)]
        calls["n"] += 1
        return httpx.Response(status, content=body)

    transport = httpx.MockTransport(handler)
    transport.call_count = lambda: calls["n"]  # type: ignore[attr-defined]
    return transport


async def _run(status_sequence, **kwargs):
    transport = _transport(status_sequence)
    async with httpx.AsyncClient(transport=transport, base_url="https://example.test") as client:
        resp = await get_with_retry(client, "https://example.test/x", {"q": "1"}, **kwargs)
        return resp, transport.call_count()


def test_immediate_success_makes_exactly_one_request():
    resp, calls = asyncio.run(_run([200]))
    assert resp.status_code == 200
    assert calls == 1


def test_a_single_transient_5xx_recovers_on_retry():
    resp, calls = asyncio.run(_run([503, 200], max_wait_seconds=0.01))
    assert resp.status_code == 200
    assert calls == 2


def test_429_is_retried_the_same_as_5xx():
    resp, calls = asyncio.run(_run([429, 429, 200], max_wait_seconds=0.01))
    assert resp.status_code == 200
    assert calls == 3


def test_a_non_retryable_status_returns_immediately_without_delay():
    resp, calls = asyncio.run(_run([404], max_wait_seconds=0.01))
    assert resp.status_code == 404
    assert calls == 1  # never retried — a real client error, not transient


def test_exhausting_all_attempts_returns_the_last_response_not_an_exception():
    resp, calls = asyncio.run(_run([503, 503, 503, 503, 503], attempts=3, max_wait_seconds=0.01))
    assert resp.status_code == 503
    assert calls == 3  # bounded — never loops past `attempts`


def test_retry_after_header_is_honored_over_the_default_backoff():
    seen_delays = []
    real_sleep = asyncio.sleep

    async def fake_sleep(seconds):
        seen_delays.append(seconds)
        await real_sleep(0)

    def handler(request: httpx.Request) -> httpx.Response:
        if handler.calls == 0:
            handler.calls += 1
            return httpx.Response(429, headers={"Retry-After": "0.05"})
        return httpx.Response(200)
    handler.calls = 0

    async def go():
        import discovery.sources._http_retry as retry_module
        original = retry_module.asyncio.sleep
        retry_module.asyncio.sleep = fake_sleep
        try:
            transport = httpx.MockTransport(handler)
            async with httpx.AsyncClient(transport=transport, base_url="https://example.test") as client:
                return await get_with_retry(client, "https://example.test/x", {})
        finally:
            retry_module.asyncio.sleep = original

    resp = asyncio.run(go())
    assert resp.status_code == 200
    assert seen_delays == [0.05]
