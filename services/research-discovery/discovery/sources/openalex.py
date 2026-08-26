"""OpenAlex API connector (free, no key; a mailto gets the faster polite pool)."""

from __future__ import annotations

import asyncio
import os

import httpx

from ..models import Paper, normalize_doi

SEARCH_URL = "https://api.openalex.org/works"
RETRY_STATUSES = {429, 500, 502, 503, 504}


def _reconstruct_abstract(inverted_index: dict | None) -> str | None:
    """OpenAlex stores abstracts as {word: [positions]}; rebuild the plain text."""
    if not inverted_index:
        return None
    positions: dict[int, str] = {}
    for word, indices in inverted_index.items():
        for i in indices:
            positions[i] = word
    return " ".join(positions[i] for i in sorted(positions)) or None


def _retry_after_seconds(resp: httpx.Response) -> float | None:
    value = resp.headers.get("Retry-After")
    if not value:
        return None
    try:
        return float(value)  # delta-seconds form
    except ValueError:
        return None  # HTTP-date form — fall back to our own backoff


async def _get(http: httpx.AsyncClient, params: dict, attempts: int = 4) -> httpx.Response:
    """GET with bounded exponential backoff on rate-limit / 5xx, honoring
    Retry-After. OpenAlex is the sole backend for the per-candidate verification
    searches, so a transient 429 must not silently lose a candidate's evidence."""
    delay = 1.0
    resp = await http.get(SEARCH_URL, params=params)
    for _ in range(attempts - 1):
        if resp.status_code not in RETRY_STATUSES:
            return resp
        wait = _retry_after_seconds(resp)
        await asyncio.sleep(min(wait if wait is not None else delay, 30.0))
        delay *= 2
        resp = await http.get(SEARCH_URL, params=params)
    return resp


async def search(http: httpx.AsyncClient, queries: dict, limit: int,
                 require_abstract: bool = True) -> list[Paper]:
    params = {
        "search": queries["keyword"],
        "per-page": min(limit, 100),
    }
    if require_abstract:
        # Corpus papers with no indexed abstract are near-useless to the analysis,
        # but a *verification* search must not hide an answering paper merely because
        # OpenAlex lacks its abstract — callers pass require_abstract=False there.
        params["filter"] = "has_abstract:true"
    email = os.getenv("CONTACT_EMAIL")
    if email:
        params["mailto"] = email

    resp = await _get(http, params)
    resp.raise_for_status()

    papers = []
    for rank, work in enumerate(resp.json().get("results") or []):
        title = work.get("display_name")
        if not title:
            continue
        venue = None
        primary = work.get("primary_location") or {}
        if primary.get("source"):
            venue = primary["source"].get("display_name")

        best_oa = work.get("best_oa_location") or {}
        pmcid = None
        pmcid_url = (work.get("ids") or {}).get("pmcid")  # e.g. ".../articles/PMC123/"
        if pmcid_url:
            digits = "".join(ch for ch in pmcid_url.rsplit("PMC", 1)[-1] if ch.isdigit())
            if digits:
                pmcid = f"PMC{digits}"
        papers.append(Paper(
            title=title,
            abstract=_reconstruct_abstract(work.get("abstract_inverted_index")),
            year=work.get("publication_year"),
            venue=venue,
            authors=[
                name
                for a in (work.get("authorships") or [])
                # authorship["author"] can be present but null — `.get("author", {})`
                # would then return None and crash; coerce None → {} first.
                if (name := (a.get("author") or {}).get("display_name"))
            ],
            citations=work.get("cited_by_count"),
            doi=normalize_doi(work.get("doi")),
            url=(primary.get("landing_page_url") or work.get("id")),
            source="OpenAlex",
            relevance_rank=rank,
            pdf_url=best_oa.get("pdf_url"),
            pmcid=pmcid,
        ))
    return papers
