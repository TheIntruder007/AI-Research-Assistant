"""Orchestrates the full run: query gen → multi-source search → dedupe/rank → analysis."""

from __future__ import annotations

import asyncio
import datetime
import math
from typing import AsyncIterator

import httpx

from . import fulltext
from .analysis import (analyze_gaps, economy_model, generate_queries,
                       mine_future_research, model)
from .models import Paper, PipelineError, normalize_title
from .sources import SOURCES, openalex

FULLTEXT_MAX_ATTEMPTS = 40   # papers we try to fetch full text for
FULLTEXT_CONCURRENCY = 8
VERIFY_RESULTS_PER_CANDIDATE = 8
MAX_CANDIDATES_FOR_ANALYSIS = 5  # caps final-synthesis output size; see D-009


def _merge(existing: Paper, incoming: Paper) -> None:
    """Fold a duplicate into the paper we already have, keeping the richer fields."""
    if not existing.abstract and incoming.abstract:
        existing.abstract = incoming.abstract
    if (incoming.citations or 0) > (existing.citations or 0):
        existing.citations = incoming.citations
    if not existing.doi and incoming.doi:
        existing.doi = incoming.doi
    if not existing.url and incoming.url:
        existing.url = incoming.url
    if not existing.venue and incoming.venue:
        existing.venue = incoming.venue
    if not existing.pdf_url and incoming.pdf_url:
        existing.pdf_url = incoming.pdf_url
    if not existing.pmcid and incoming.pmcid:
        existing.pmcid = incoming.pmcid
    if not existing.year and incoming.year:
        existing.year = incoming.year
    if len(incoming.authors) > len(existing.authors):
        existing.authors = incoming.authors
    existing.relevance_rank = min(existing.relevance_rank, incoming.relevance_rank)
    if incoming.source not in existing.source:
        existing.source = f"{existing.source}, {incoming.source}"


def dedupe(papers: list[Paper]) -> list[Paper]:
    """Collapse duplicates, matching on DOI *or* normalized title.

    A paper can arrive with a DOI from one source (OpenAlex/S2) and without one
    from another (arXiv always has doi=None), so we index every kept paper by
    both keys and check both — otherwise the same work survives twice and the
    model double-counts its evidence.
    """
    by_doi: dict[str, Paper] = {}
    by_title: dict[str, Paper] = {}
    kept: list[Paper] = []

    def index(p: Paper) -> None:
        if p.doi:
            by_doi.setdefault(p.doi, p)
        tkey = normalize_title(p.title)
        if tkey:
            by_title.setdefault(tkey, p)

    for p in papers:
        tkey = normalize_title(p.title)
        existing = (by_doi.get(p.doi) if p.doi else None) or (by_title.get(tkey) if tkey else None)
        if existing is not None:
            _merge(existing, p)
            index(existing)  # a merged-in DOI/title makes `existing` findable both ways
        else:
            kept.append(p)
            index(p)
    return kept


def rank(papers: list[Paper], per_source_limit: int) -> list[Paper]:
    this_year = datetime.date.today().year

    def score(p: Paper) -> float:
        s = 0.0
        if p.abstract:
            s += 4.0  # the analysis reads abstracts; papers without one are near-useless
        # Cap the citation term so hyper-cited classics can't outrank topical papers.
        s += min(math.log1p(p.citations or 0), 8.0) * 0.6
        if p.year:
            s += max(0.0, min(1.0, (p.year - (this_year - 15)) / 15)) * 2.0
        s += (1.0 - p.relevance_rank / max(per_source_limit, 1)) * 4.0
        return s

    return sorted(papers, key=score, reverse=True)


async def _collect_fulltext(corpus: list[Paper]) -> AsyncIterator[dict]:
    """Fetch Discussion/Future sections for the best full-text candidates."""
    targets = [p for p in corpus if fulltext.is_candidate(p)][:FULLTEXT_MAX_ATTEMPTS]
    if not targets:
        return
    sem = asyncio.Semaphore(FULLTEXT_CONCURRENCY)
    done = ok = 0

    async def one(p: Paper) -> bool:
        async with sem:
            return await fulltext.fetch_future_sections(http, p)

    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as http:
        tasks = [asyncio.create_task(one(p)) for p in targets]
        try:
            for fut in asyncio.as_completed(tasks):
                ok += 1 if await fut else 0
                done += 1
                if done % 5 == 0 or done == len(targets):
                    yield {"type": "fulltext_progress", "done": done,
                           "ok": ok, "total": len(targets)}
        finally:
            # If the client disconnected mid-stage, don't leave tasks running
            # against a client that's about to close.
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)


async def _verify_candidates(candidates: list[dict], corpus: list[Paper]) -> tuple[list[Paper], list[dict]]:
    """Search the literature for each candidate question; return new verification
    papers (with ids continuing after the corpus) and per-candidate warnings."""
    # Index the corpus by both DOI and title so a verification hit that lacks a
    # DOI still matches a DOI-keyed corpus paper (and vice versa) instead of being
    # re-added as a duplicate reference.
    known_by_doi: dict[str, Paper] = {p.doi: p for p in corpus if p.doi}
    known_by_title: dict[str, Paper] = {normalize_title(p.title): p for p in corpus
                                        if normalize_title(p.title)}
    verification_papers: list[Paper] = []
    warnings: list[dict] = []
    next_id = max((p.id for p in corpus), default=0) + 1
    sem = asyncio.Semaphore(4)

    async def search_one(cand: dict) -> list[Paper]:
        async with sem:
            # require_abstract=False: an answering paper must not be hidden just
            # because OpenAlex has no indexed abstract for it.
            return await openalex.search(http, {"keyword": cand["question"]},
                                         VERIFY_RESULTS_PER_CANDIDATE,
                                         require_abstract=False)

    async with httpx.AsyncClient(timeout=45, follow_redirects=True) as http:
        results = await asyncio.gather(*[search_one(c) for c in candidates],
                                       return_exceptions=True)

    for cand, result in zip(candidates, results):
        cand["evidence_paper_ids"] = []
        if isinstance(result, BaseException):
            warnings.append({"type": "source_error", "source": "Verification search",
                             "message": f"Verification search failed for one candidate "
                                        f"({type(result).__name__}) — it will be judged "
                                        "on the main corpus only."})
            continue
        for p in result:
            tkey = normalize_title(p.title)
            existing = (known_by_doi.get(p.doi) if p.doi else None) or \
                (known_by_title.get(tkey) if tkey else None)
            if existing is not None:
                if existing.id and existing.id not in cand["evidence_paper_ids"]:
                    cand["evidence_paper_ids"].append(existing.id)
                continue
            p.id = next_id
            p.role = "verification"
            next_id += 1
            if p.doi:
                known_by_doi.setdefault(p.doi, p)
            if tkey:
                known_by_title.setdefault(tkey, p)
            verification_papers.append(p)
            cand["evidence_paper_ids"].append(p.id)
    return verification_papers, warnings


def _models(quality: str) -> tuple[str, str]:
    """(fast model for queries+mining, premium model for the gap analysis)."""
    premium, economy = model(), economy_model()
    return {
        "best": (premium, premium),
        "budget": (economy, economy),
    }.get(quality, (economy, premium))  # "balanced" default


async def run_pipeline(question: str, source_keys: list[str],
                       per_source: int, corpus_size: int,
                       fulltext_enabled: bool = True,
                       quality: str = "balanced") -> AsyncIterator[dict]:
    selected = [(k, *SOURCES[k]) for k in source_keys if k in SOURCES]
    if not selected:
        raise PipelineError("Select at least one literature source.")

    fast_model, analysis_model = _models(quality)
    yield {"type": "log",
           "message": f"Models — queries & mining: {fast_model}; "
                      f"gap analysis: {analysis_model}"}

    all_papers: list[Paper] = []
    if selected:
        yield {"type": "status", "stage": "queries", "state": "running",
               "message": "Generating search queries with the local model…"}
        queries = await generate_queries(question, fast_model)
        yield {"type": "queries", "queries": queries}
        yield {"type": "status", "stage": "queries", "state": "done",
               "message": f"Search queries ready — “{queries['keyword']}”"}

        yield {"type": "status", "stage": "search", "state": "running",
               "message": f"Searching {len(selected)} database(s)…"}
        async with httpx.AsyncClient(timeout=45, follow_redirects=True) as http:
            results = await asyncio.gather(
                *[fn(http, queries, per_source) for _, _, fn in selected],
                return_exceptions=True,
            )
        for (key, label, _), result in zip(selected, results):
            if isinstance(result, BaseException):
                yield {"type": "source_error", "source": label,
                       "message": f"{label} search failed ({type(result).__name__}) — continuing without it."}
            else:
                all_papers.extend(result)
                yield {"type": "source_result", "source": label, "count": len(result)}

    if not all_papers:
        raise PipelineError("No papers found in any source. Try rephrasing the question "
                            "or enabling more sources.")

    unique = dedupe(all_papers)
    corpus = rank(unique, per_source)[:corpus_size]
    for i, p in enumerate(corpus, start=1):
        p.id = i
    yield {"type": "status", "stage": "search", "state": "done",
           "message": f"Found {len(all_papers)} papers → {len(unique)} unique → "
                      f"analyzing top {len(corpus)}"}
    yield {"type": "corpus", "total_found": len(all_papers), "unique": len(unique),
           "analyzed": len(corpus), "papers": [p.to_client_dict() for p in corpus]}

    candidates: list[dict] = []
    verification_papers: list[Paper] = []
    if fulltext_enabled:
        yield {"type": "status", "stage": "fulltext", "state": "running",
               "message": "Retrieving full texts (open access)…"}
        async for event in _collect_fulltext(corpus):
            yield {"type": "status", "stage": "fulltext", "state": "running",
                   "message": f"Retrieving full texts… {event['ok']} of {event['done']} "
                              f"tried (of {event['total']} candidates)"}
        with_text = [p for p in corpus if p.future_text]
        yield {"type": "status", "stage": "fulltext", "state": "done",
               "message": f"Discussion/Future-research sections retrieved for "
                          f"{len(with_text)} papers"}
        yield {"type": "fulltext_done",
               "paper_ids": [p.id for p in with_text]}

        # --- Stage: mine author-flagged future-research statements ----------
        if with_text:
            yield {"type": "status", "stage": "mine", "state": "running",
                   "message": "Extracting author-flagged future-research statements…"}
            try:
                candidates, mine_warning = await mine_future_research(with_text, fast_model)
                # Every candidate gets a full entry in the final gap-analysis
                # JSON (question/status/verdict/evidence/recommendation), so an
                # uncapped candidate count scales the final synthesis call's
                # output size directly. Mining already orders candidates most-
                # to-least substantive, so keep the strongest ones.
                candidates = candidates[:MAX_CANDIDATES_FOR_ANALYSIS]
            except PipelineError as e:
                # Mining is best-effort. A rate-limit/connection error to the
                # local model here must not discard the search/full-text work
                # already done — fall through to the main gap analysis with
                # no author-flagged candidates.
                candidates = []
                yield {"type": "source_error", "source": "Full-text mining",
                       "message": f"{e} Continuing without author-flagged analysis."}
                yield {"type": "status", "stage": "mine", "state": "skipped",
                       "message": "Full-text mining unavailable — skipped"}
            else:
                if mine_warning:
                    yield {"type": "source_error", "source": "Full-text mining",
                           "message": mine_warning}
                if candidates:
                    yield {"type": "status", "stage": "mine", "state": "done",
                           "message": f"Found {len(candidates)} author-flagged candidate(s)"}
                    yield {"type": "candidates",
                           "candidates": [{"question": c["question"],
                                           "source_paper_ids": c["source_paper_ids"]}
                                          for c in candidates]}
                else:
                    yield {"type": "status", "stage": "mine", "state": "done",
                           "message": "No substantive author-flagged statements found"}
        else:
            yield {"type": "status", "stage": "mine", "state": "skipped",
                   "message": "Skipped — no full texts retrieved"}

        # --- Stage: verify candidates against the wider literature ----------
        if candidates:
            yield {"type": "status", "stage": "verify", "state": "running",
                   "message": f"Checking whether {len(candidates)} candidate(s) have "
                              "already been answered…"}
            verification_papers, warnings = await _verify_candidates(candidates, corpus)
            for w in warnings:
                yield w
            if verification_papers:
                yield {"type": "verification_corpus",
                       "papers": [p.to_client_dict() for p in verification_papers]}
            yield {"type": "status", "stage": "verify", "state": "done",
                   "message": f"Verification searches added {len(verification_papers)} "
                              "papers to check against"}
        else:
            yield {"type": "status", "stage": "verify", "state": "skipped",
                   "message": "Skipped — no candidates to verify"}

    yield {"type": "status", "stage": "analyze", "state": "running",
           "message": "Synthesizing the corpus and identifying gaps (this takes a few minutes)…"}
    async for event in analyze_gaps(question, corpus, candidates, verification_papers,
                                    analysis_model):
        yield event
    yield {"type": "status", "stage": "analyze", "state": "done", "message": "Analysis complete."}
