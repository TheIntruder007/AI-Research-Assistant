"""Semantic Scholar Graph API connector (free; optional API key raises rate limits)."""

from __future__ import annotations

import asyncio
import os

import httpx

from ..models import Paper, normalize_doi

SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
FIELDS = "title,abstract,year,venue,citationCount,authors,externalIds,url,openAccessPdf"


async def search(http: httpx.AsyncClient, queries: dict, limit: int) -> list[Paper]:
    headers = {}
    api_key = os.getenv("S2_API_KEY")
    if api_key:
        headers["x-api-key"] = api_key

    params = {"query": queries["keyword"], "limit": min(limit, 100), "fields": FIELDS}

    # The shared unauthenticated pool 429s often; be patient before giving up.
    for backoff in (2, 5, 10, None):
        resp = await http.get(SEARCH_URL, params=params, headers=headers)
        if resp.status_code != 429 or backoff is None:
            break
        await asyncio.sleep(backoff)
    resp.raise_for_status()

    papers = []
    for rank, item in enumerate(resp.json().get("data") or []):
        if not item.get("title"):
            continue
        external_ids = item.get("externalIds") or {}
        papers.append(Paper(
            title=item["title"],
            abstract=item.get("abstract"),
            year=item.get("year"),
            venue=item.get("venue") or None,
            authors=[a.get("name", "") for a in (item.get("authors") or []) if a.get("name")],
            citations=item.get("citationCount"),
            doi=normalize_doi(external_ids.get("DOI")),
            url=item.get("url"),
            source="Semantic Scholar",
            relevance_rank=rank,
            pdf_url=(item.get("openAccessPdf") or {}).get("url"),
        ))
    return papers
