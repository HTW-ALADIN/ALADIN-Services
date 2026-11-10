"""Adapter for author search, author-ID lookup, and "papers by this author"
retrieval.

None of `scimesh`'s typed `Provider` classes expose author-level endpoints
(only paper `search`/`get`/`citations`), and `academic-mcp`'s searchers only
accept a free-text query string with no author-identity concept at all. So
this adapter talks directly to the two backends that already have a
credential shape declared in `core/provider_registry.py` (OpenAlex,
Semantic Scholar) plus Scopus, reusing each backend's own paper-parsing logic
(`Provider._parse_work` / `_parse_paper` / `_parse_entry`) so that a paper
returned from an author lookup normalizes into this service's canonical
`Paper` shape identically to `adapters/scimesh_adapter.py`'s paper-search path.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence

import httpx
from scimesh.providers.openalex import OpenAlex
from scimesh.providers.scopus import Scopus
from scimesh.providers.semantic_scholar import API_FIELDS as _S2_PAPER_FIELDS
from scimesh.providers.semantic_scholar import SemanticScholar

from adapters.scimesh_adapter import _normalize as _normalize_scimesh_paper
from core.author import AuthorProfile, AuthorQuery
from core.paper import Paper

_TIMEOUT = httpx.Timeout(30.0)


_ID_PATH_SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")


def _require_id_path_segment(value: str, field_name: str) -> str:
    """Validate an author-ID/ORCID value before it is interpolated directly
    into a request path or into a backend query-filter DSL where structural
    characters (e.g. OpenAlex's `,`/`|` filter separators, a URL path's `/`)
    would otherwise be interpreted rather than treated as literal ID text.

    Real IDs from every provider used here (OpenAlex `A...`, Semantic
    Scholar's numeric author ID, Scopus's numeric author ID, ORCID's
    `0000-0002-1825-0097`) only ever contain letters, digits, `.`, `_`, `-`,
    so this is not overly restrictive for legitimate input.
    """
    if not _ID_PATH_SEGMENT.match(value):
        raise ValueError(f"Invalid {field_name}: must contain only letters, digits, '.', '_', '-'")
    return value


def _orcid_url(orcid: str) -> str:
    bare_orcid = orcid.replace("https://orcid.org/", "")
    bare_orcid = _require_id_path_segment(bare_orcid, "orcid")
    return f"https://orcid.org/{bare_orcid}"


def _pick_best_author(candidates: Sequence, key: Callable[[object], int]):
    """Pick the single best-matching candidate from a name-based author search.

    Used to resolve a bare `AuthorQuery.name` to one specific author before
    fetching "papers by this author" -- every provider's author-search
    endpoint can return multiple loosely-matching results, so this is the one
    place that decides which candidate is authoritative. Kept as a single
    shared helper (rather than duplicated per-provider) so the tie-break rule
    (highest score wins; `None`/missing scores treated as zero) stays
    consistent across providers.
    """
    if not candidates:
        return None
    return max(candidates, key=lambda c: key(c) or 0)


# --------------------------------------------------------------------------- #
# OpenAlex
# --------------------------------------------------------------------------- #

_OPENALEX_AUTHORS_URL = "https://api.openalex.org/authors"
_OPENALEX_WORKS_URL = "https://api.openalex.org/works"


def _parse_openalex_author(data: dict) -> AuthorProfile:
    external_ids: dict[str, str] = {}
    oa_id = data.get("id")
    if oa_id:
        external_ids["openalex"] = oa_id.rsplit("/", 1)[-1]

    orcid = data.get("orcid")
    if orcid:
        orcid = orcid.replace("https://orcid.org/", "")
        external_ids["orcid"] = orcid

    affiliations: list[str] = []
    for inst in data.get("last_known_institutions") or []:
        name = inst.get("display_name")
        if name:
            affiliations.append(name)
    if not affiliations:
        inst = data.get("last_known_institution") or {}
        if inst.get("display_name"):
            affiliations.append(inst["display_name"])

    summary = data.get("summary_stats") or {}

    return AuthorProfile(
        provider="openalex",
        name=data.get("display_name") or "",
        external_ids=external_ids,
        orcid=orcid,
        affiliations=affiliations,
        paper_count=data.get("works_count"),
        citation_count=data.get("cited_by_count"),
        h_index=summary.get("h_index"),
        homepage_url=oa_id,
        raw=data,
    )


async def _openalex_search_authors(
    client: httpx.AsyncClient,
    query: AuthorQuery,
    mailto: str | None,
    max_results: int,
) -> list[AuthorProfile]:
    params: dict[str, str | int] = {"per_page": min(max_results, 200)}
    if mailto:
        params["mailto"] = mailto

    ids = query.ids
    if ids and ids.openalex_author_id:
        author_id = _require_id_path_segment(ids.openalex_author_id, "openalex_author_id")
        resp = await client.get(f"{_OPENALEX_AUTHORS_URL}/{author_id}", params=params)
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        return [_parse_openalex_author(resp.json())]

    if ids and ids.orcid:
        params["filter"] = f"orcid:{_orcid_url(ids.orcid)}"
    elif query.name:
        params["search"] = query.name
    else:
        return []

    resp = await client.get(_OPENALEX_AUTHORS_URL, params=params)
    resp.raise_for_status()
    results = resp.json().get("results", [])
    return [_parse_openalex_author(a) for a in results[:max_results]]


async def _openalex_papers_by_author(
    client: httpx.AsyncClient,
    query: AuthorQuery,
    mailto: str | None,
    max_results: int,
) -> list[Paper]:
    ids = query.ids
    if ids and ids.orcid:
        filter_str = f"author.orcid:{_orcid_url(ids.orcid)}"
    elif ids and ids.openalex_author_id:
        author_id = _require_id_path_segment(ids.openalex_author_id, "openalex_author_id")
        filter_str = f"author.id:{author_id}"
    elif query.name:
        candidates = await _openalex_search_authors(
            client, AuthorQuery(name=query.name), mailto, 25
        )
        best = _pick_best_author(candidates, lambda a: a.citation_count)
        if best is None:
            return []
        author_id = best.external_ids.get("openalex")
        if not author_id:
            return []
        filter_str = f"author.id:{author_id}"
    else:
        return []

    provider = OpenAlex(mailto=mailto)
    papers: list[Paper] = []
    cursor: str | None = "*"
    while cursor and len(papers) < max_results:
        params: dict[str, str | int] = {
            "filter": filter_str,
            "per_page": min(max_results, 200),
            "cursor": cursor,
        }
        if mailto:
            params["mailto"] = mailto
        resp = await client.get(_OPENALEX_WORKS_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
        for work in data.get("results", []):
            scimesh_paper = provider._parse_work(work)
            if scimesh_paper is not None:
                papers.append(_normalize_scimesh_paper(scimesh_paper, "openalex"))
            if len(papers) >= max_results:
                break
        cursor = data.get("meta", {}).get("next_cursor")
    return papers


# --------------------------------------------------------------------------- #
# Semantic Scholar
# --------------------------------------------------------------------------- #

_S2_BASE = "https://api.semanticscholar.org/graph/v1"
_S2_AUTHOR_FIELDS = (
    "authorId,name,affiliations,paperCount,citationCount,hIndex,externalIds,homepage"
)


def _s2_headers(api_key: str | None) -> dict[str, str]:
    return {"x-api-key": api_key} if api_key else {}


def _parse_s2_author(data: dict) -> AuthorProfile:
    external_ids: dict[str, str] = {}
    author_id = data.get("authorId")
    if author_id:
        external_ids["semantic_scholar"] = author_id
    orcid = (data.get("externalIds") or {}).get("ORCID")
    if orcid:
        external_ids["orcid"] = orcid

    return AuthorProfile(
        provider="semantic_scholar",
        name=data.get("name") or "",
        external_ids=external_ids,
        orcid=orcid,
        affiliations=data.get("affiliations") or [],
        paper_count=data.get("paperCount"),
        citation_count=data.get("citationCount"),
        h_index=data.get("hIndex"),
        homepage_url=data.get("homepage"),
        raw=data,
    )


async def _s2_search_authors(
    client: httpx.AsyncClient,
    query: AuthorQuery,
    api_key: str | None,
    max_results: int,
) -> list[AuthorProfile]:
    headers = _s2_headers(api_key)
    ids = query.ids
    if ids and ids.semantic_scholar_author_id:
        author_id = _require_id_path_segment(
            ids.semantic_scholar_author_id, "semantic_scholar_author_id"
        )
        resp = await client.get(
            f"{_S2_BASE}/author/{author_id}",
            params={"fields": _S2_AUTHOR_FIELDS},
            headers=headers,
        )
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        return [_parse_s2_author(resp.json())]

    if not query.name:
        return []

    resp = await client.get(
        f"{_S2_BASE}/author/search",
        params={"query": query.name, "limit": min(max_results, 100), "fields": _S2_AUTHOR_FIELDS},
        headers=headers,
    )
    resp.raise_for_status()
    return [_parse_s2_author(a) for a in resp.json().get("data", [])[:max_results]]


async def _s2_papers_by_author(
    client: httpx.AsyncClient,
    query: AuthorQuery,
    api_key: str | None,
    max_results: int,
) -> list[Paper]:
    headers = _s2_headers(api_key)
    ids = query.ids
    author_id = (
        _require_id_path_segment(ids.semantic_scholar_author_id, "semantic_scholar_author_id")
        if ids and ids.semantic_scholar_author_id
        else None
    )

    if not author_id:
        if not query.name:
            return []
        resp = await client.get(
            f"{_S2_BASE}/author/search",
            params={"query": query.name, "limit": 10, "fields": "authorId,citationCount"},
            headers=headers,
        )
        resp.raise_for_status()
        candidates = resp.json().get("data", [])
        best = _pick_best_author(candidates, lambda a: a.get("citationCount"))
        if best is None:
            return []
        author_id = best.get("authorId")
        if not author_id:
            return []

    provider = SemanticScholar()
    papers: list[Paper] = []
    offset = 0
    page_size = min(100, max_results)
    while len(papers) < max_results:
        resp = await client.get(
            f"{_S2_BASE}/author/{author_id}/papers",
            params={"offset": offset, "limit": page_size, "fields": _S2_PAPER_FIELDS},
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
        if not data:
            break
        for paper_data in data:
            scimesh_paper = provider._parse_paper(paper_data)
            if scimesh_paper is not None:
                papers.append(_normalize_scimesh_paper(scimesh_paper, "semantic_scholar"))
            if len(papers) >= max_results:
                break
        if len(data) < page_size:
            break
        offset += page_size
    return papers


# --------------------------------------------------------------------------- #
# Scopus
# --------------------------------------------------------------------------- #

_SCOPUS_AUTHOR_SEARCH_URL = "https://api.elsevier.com/content/search/author"
_SCOPUS_WORKS_URL = "https://api.elsevier.com/content/search/scopus"


def _scopus_headers(api_key: str) -> dict[str, str]:
    return {"X-ELS-APIKey": api_key, "Accept": "application/json"}


def _require_scopus_api_key(api_key: str | None) -> str:
    if not api_key:
        raise ValueError("Scopus requires an API key. Pass credentials.scopus.api_key")
    return api_key


# Scopus's query DSL treats `(`, `)`, `"`, and the bare words AND/OR/NOT/AND NOT
# as syntax, not literal text. Values interpolated into a query string (author
# name, an author ID sourced from `AuthorIdentifier`) must have those stripped
# so a crafted value can't change the query's structure (e.g. close the
# function early and append an unrelated clause).
_SCOPUS_DSL_METACHARACTERS = re.compile(r'[()"]')
_SCOPUS_DSL_BOOLEAN_OPERATORS = re.compile(r"\b(AND NOT|AND|OR|NOT)\b", re.IGNORECASE)


def _scopus_query_literal(value: str) -> str:
    """Strip Scopus query-DSL syntax characters/operators from a value that
    must be treated as a literal search term rather than parsed as part of
    the query's structure."""
    value = _SCOPUS_DSL_METACHARACTERS.sub("", value)
    value = _SCOPUS_DSL_BOOLEAN_OPERATORS.sub("", value)
    return value.strip()


def _parse_scopus_author_entry(entry: dict) -> AuthorProfile:
    """Parse one `search-results.entry` element from the Scopus **Author
    Search** API (`GET /content/search/author`) -- a flat shape, distinct
    from the Author Retrieval API's response (see
    `_parse_scopus_author_retrieval` below)."""
    external_ids: dict[str, str] = {}
    identifier = entry.get("dc:identifier", "")
    if identifier.startswith("AUTHOR_ID:"):
        external_ids["scopus"] = identifier.replace("AUTHOR_ID:", "")

    preferred = entry.get("preferred-name") or {}
    name = " ".join(p for p in (preferred.get("given-name"), preferred.get("surname")) if p)

    affiliation = entry.get("affiliation-current") or {}
    affiliations = [affiliation["affiliation-name"]] if affiliation.get("affiliation-name") else []

    doc_count = entry.get("document-count")
    return AuthorProfile(
        provider="scopus",
        name=name or identifier,
        external_ids=external_ids,
        affiliations=affiliations,
        paper_count=int(doc_count) if doc_count else None,
        raw=entry,
    )


def _parse_scopus_author_retrieval(entry: dict) -> AuthorProfile:
    """Parse one `author-retrieval-response` element from the Scopus
    **Author Retrieval** API (`GET /content/author/author_id/{id}`).

    Unlike the Author Search API's flat entry shape, identity/affiliation
    data here is nested under `coredata` and `author-profile` -- reusing
    `_parse_scopus_author_entry` against this shape would silently read
    missing top-level keys and produce an empty profile.
    """
    coredata = entry.get("coredata") or {}
    profile = entry.get("author-profile") or {}

    external_ids: dict[str, str] = {}
    identifier = coredata.get("dc:identifier", "")
    if identifier.startswith("AUTHOR_ID:"):
        external_ids["scopus"] = identifier.replace("AUTHOR_ID:", "")

    preferred = profile.get("preferred-name") or {}
    name = " ".join(p for p in (preferred.get("given-name"), preferred.get("surname")) if p)

    affiliations: list[str] = []
    affiliation = (profile.get("affiliation-current") or {}).get("affiliation")
    affiliation_entries = (
        affiliation if isinstance(affiliation, list) else [affiliation] if affiliation else []
    )
    for aff in affiliation_entries:
        if not isinstance(aff, dict):
            continue
        aff_name = (aff.get("ip-doc") or {}).get("afdispname") or aff.get("affiliation-name")
        if aff_name:
            affiliations.append(aff_name)

    doc_count = coredata.get("document-count")
    return AuthorProfile(
        provider="scopus",
        name=name or identifier,
        external_ids=external_ids,
        affiliations=affiliations,
        paper_count=int(doc_count) if doc_count else None,
        raw=entry,
    )


async def _scopus_search_authors(
    client: httpx.AsyncClient,
    query: AuthorQuery,
    api_key: str | None,
    max_results: int,
) -> list[AuthorProfile]:
    headers = _scopus_headers(_require_scopus_api_key(api_key))
    ids = query.ids
    if ids and ids.scopus_author_id:
        scopus_author_id = _require_id_path_segment(ids.scopus_author_id, "scopus_author_id")
        resp = await client.get(
            f"https://api.elsevier.com/content/author/author_id/{scopus_author_id}",
            headers=headers,
        )
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        entries = resp.json().get("author-retrieval-response") or []
        return [_parse_scopus_author_retrieval(e) for e in entries]

    if not query.name:
        return []

    resp = await client.get(
        _SCOPUS_AUTHOR_SEARCH_URL,
        params={
            "query": f"AUTHLASTNAME({_scopus_query_literal(query.name)})",
            "count": min(max_results, 25),
        },
        headers=headers,
    )
    resp.raise_for_status()
    entries = resp.json().get("search-results", {}).get("entry", [])
    return [_parse_scopus_author_entry(e) for e in entries[:max_results] if "error" not in e]


async def _scopus_resolve_author_id(
    client: httpx.AsyncClient, query: AuthorQuery, api_key: str
) -> str | None:
    ids = query.ids
    if ids and ids.scopus_author_id:
        return _require_id_path_segment(ids.scopus_author_id, "scopus_author_id")
    if not query.name:
        return None
    candidates = await _scopus_search_authors(client, AuthorQuery(name=query.name), api_key, 25)
    best = _pick_best_author(candidates, lambda a: a.paper_count)
    return best.external_ids.get("scopus") if best is not None else None


async def _scopus_papers_by_author(
    client: httpx.AsyncClient,
    query: AuthorQuery,
    api_key: str | None,
    max_results: int,
) -> list[Paper]:
    key = _require_scopus_api_key(api_key)
    author_id = await _scopus_resolve_author_id(client, query, key)
    if not author_id:
        return []

    headers = _scopus_headers(key)
    provider = Scopus()
    papers: list[Paper] = []
    start = 0
    page_size = 25
    while len(papers) < max_results:
        resp = await client.get(
            _SCOPUS_WORKS_URL,
            params={
                "query": f"AU-ID({_scopus_query_literal(author_id)})",
                "count": page_size,
                "start": start,
                "view": "COMPLETE",
            },
            headers=headers,
        )
        resp.raise_for_status()
        entries = resp.json().get("search-results", {}).get("entry", [])
        if not entries:
            break
        for entry in entries:
            if "error" in entry:
                continue
            scimesh_paper = provider._parse_entry(entry)
            if scimesh_paper is not None:
                papers.append(_normalize_scimesh_paper(scimesh_paper, "scopus"))
            if len(papers) >= max_results:
                break
        if len(entries) < page_size:
            break
        start += page_size
    return papers


# --------------------------------------------------------------------------- #
# Public adapter interface
# --------------------------------------------------------------------------- #


def _build_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=_TIMEOUT)


async def search_authors(
    provider: str,
    query: AuthorQuery,
    credentials: dict[str, str],
    max_results: int,
) -> list[AuthorProfile]:
    async with _build_client() as client:
        if provider == "openalex":
            return await _openalex_search_authors(
                client, query, credentials.get("mailto"), max_results
            )
        if provider == "semantic_scholar":
            return await _s2_search_authors(client, query, credentials.get("api_key"), max_results)
        if provider == "scopus":
            return await _scopus_search_authors(
                client, query, credentials.get("api_key"), max_results
            )
    raise KeyError(f"author adapter does not handle provider '{provider}'")


async def papers_by_author(
    provider: str,
    query: AuthorQuery,
    credentials: dict[str, str],
    max_results: int,
) -> list[Paper]:
    async with _build_client() as client:
        if provider == "openalex":
            return await _openalex_papers_by_author(
                client, query, credentials.get("mailto"), max_results
            )
        if provider == "semantic_scholar":
            return await _s2_papers_by_author(
                client, query, credentials.get("api_key"), max_results
            )
        if provider == "scopus":
            return await _scopus_papers_by_author(
                client, query, credentials.get("api_key"), max_results
            )
    raise KeyError(f"author adapter does not handle provider '{provider}'")
