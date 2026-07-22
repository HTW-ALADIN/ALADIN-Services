"""Static provider -> backend routing table.

Maps each provider name this service exposes to the backend library that
serves it (``scimesh`` or ``academic_mcp``), plus the credential fields that
backend/provider combination accepts and whether it supports citation-graph
expansion (`Provider.citations()` in scimesh; academic-mcp's searchers only
expose citation *counts*, not a citation graph, so none of them support
graph expansion as of the installed version).

Verified against the actually-installed versions of both libraries
(``scimesh==0.3.0``, ``academic-mcp==0.1.9``) rather than assumed from
documentation, since installed provider coverage can differ from a library's
README (e.g. scimesh 0.3.0 does not yet ship a CrossRef provider, unlike what
the initial research overview implied).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Backend = Literal["scimesh", "academic_mcp"]


@dataclass(frozen=True)
class CredentialField:
    name: str
    required: bool = False
    description: str = ""


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    backend: Backend
    credential_fields: tuple[CredentialField, ...] = field(default_factory=tuple)
    supports_citations: bool = False
    notes: str = ""

    @property
    def required_credential_names(self) -> tuple[str, ...]:
        return tuple(f.name for f in self.credential_fields if f.required)


PROVIDER_REGISTRY: dict[str, ProviderSpec] = {
    "arxiv": ProviderSpec(
        name="arxiv",
        backend="scimesh",
        notes="No auth required. academic-mcp also has an arxiv searcher; "
        "scimesh's typed provider is preferred.",
    ),
    "openalex": ProviderSpec(
        name="openalex",
        backend="scimesh",
        credential_fields=(
            CredentialField("mailto", required=False, description="Polite-pool contact email"),
        ),
        supports_citations=True,
    ),
    "semantic_scholar": ProviderSpec(
        name="semantic_scholar",
        backend="scimesh",
        credential_fields=(
            CredentialField("api_key", required=False, description="Raises rate limits"),
        ),
        supports_citations=True,
    ),
    "scopus": ProviderSpec(
        name="scopus",
        backend="scimesh",
        credential_fields=(
            CredentialField("api_key", required=True, description="Elsevier/Scopus API key"),
        ),
        supports_citations=True,
    ),
    "crossref": ProviderSpec(
        name="crossref",
        backend="academic_mcp",
        notes="No auth required. Not routed through scimesh: the installed "
        "scimesh version (0.3.0) does not ship a CrossRef provider.",
    ),
    "pubmed": ProviderSpec(name="pubmed", backend="academic_mcp"),
    "pmc": ProviderSpec(name="pmc", backend="academic_mcp"),
    "biorxiv": ProviderSpec(name="biorxiv", backend="academic_mcp"),
    "medrxiv": ProviderSpec(name="medrxiv", backend="academic_mcp"),
    "google_scholar": ProviderSpec(
        name="google_scholar",
        backend="academic_mcp",
        notes="Unofficial scraper, no auth. Fragile/blockable without proxies; "
        "opt-in only, documented with caveats.",
    ),
    "iacr": ProviderSpec(name="iacr", backend="academic_mcp"),
    "core": ProviderSpec(
        name="core",
        backend="academic_mcp",
        credential_fields=(CredentialField("api_key", required=False),),
    ),
    "ieee": ProviderSpec(
        name="ieee",
        backend="academic_mcp",
        credential_fields=(CredentialField("api_key", required=True),),
    ),
    "springer": ProviderSpec(
        name="springer",
        backend="academic_mcp",
        credential_fields=(CredentialField("api_key", required=True),),
    ),
    "sciencedirect": ProviderSpec(
        name="sciencedirect",
        backend="academic_mcp",
        credential_fields=(CredentialField("api_key", required=True),),
    ),
    "wos": ProviderSpec(
        name="wos",
        backend="academic_mcp",
        credential_fields=(CredentialField("api_key", required=True),),
    ),
    "acm": ProviderSpec(name="acm", backend="academic_mcp"),
    "jstor": ProviderSpec(name="jstor", backend="academic_mcp"),
    "researchgate": ProviderSpec(name="researchgate", backend="academic_mcp"),
}


def get_provider_spec(provider: str) -> ProviderSpec:
    spec = PROVIDER_REGISTRY.get(provider)
    if spec is None:
        available = ", ".join(sorted(PROVIDER_REGISTRY))
        raise KeyError(f"Unknown provider '{provider}'. Available providers: {available}")
    return spec


def providers_supporting_citations() -> list[str]:
    return [name for name, spec in PROVIDER_REGISTRY.items() if spec.supports_citations]
