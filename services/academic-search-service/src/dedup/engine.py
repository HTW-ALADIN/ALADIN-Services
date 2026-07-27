"""Cross-provider deduplication engine.

Tiered matching, in priority order:

1. Exact identifier match -- papers whose canonical `Paper.id` (computed via the
   identifier-priority chain: DOI -> arXiv ID -> PMID -> Semantic Scholar ID)
   already collapsed to the same value during normalization.
2. Fuzzy title+year match -- normalized-title similarity >= threshold, same
   year, used when `strategy` is "auto" or "aggressive".
3. Fuzzy title-only match -- same similarity check without the year
   constraint, higher threshold, used only when `strategy == "aggressive"`.

Uses stdlib `difflib.SequenceMatcher` for fuzzy similarity rather than adding a
third-party fuzzy-matching dependency -- adequate for title-level comparisons.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Literal

from core.paper import Paper, normalize_title

Strategy = Literal["auto", "strict", "aggressive"]

TITLE_YEAR_THRESHOLD = 0.92
TITLE_ONLY_THRESHOLD = 0.97


@dataclass
class ClusterMember:
    id: str
    provider: str


@dataclass
class DedupCluster:
    canonical_id: str
    match_tier: str
    members: list[ClusterMember]


@dataclass
class DedupReport:
    input_count: int
    output_count: int
    duplicates_removed: int
    clusters: list[DedupCluster] = field(default_factory=list)
    by_tier: dict[str, int] = field(default_factory=dict)
    by_provider_pair: dict[str, int] = field(default_factory=dict)


def _title_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize_title(a), normalize_title(b)).ratio()


def _merge(papers: list[Paper], match_tier: str) -> tuple[Paper, DedupCluster]:
    """Pick the most-complete paper as canonical, union metadata from the rest."""

    def completeness(p: Paper) -> tuple[int, int, int]:
        return (
            1 if p.abstract else 0,
            1 if p.doi else 0,
            len(p.authors),
        )

    base = max(papers, key=completeness)
    others = [p for p in papers if p is not base]

    external_ids = dict(base.external_ids)
    urls = list(base.urls)
    field_sources = {
        k: base.provider for k in base.model_dump(exclude_none=True) if k not in ("raw",)
    }
    citation_count = base.citation_count
    reference_count = base.reference_count

    # Abstract: longest non-null wins (mirrors scimesh's own merge_papers
    # policy), not simply "base's abstract if present".
    abstract = base.abstract
    abstract_source = base.provider
    for other in others:
        if other.abstract and len(other.abstract) > len(abstract or ""):
            abstract = other.abstract
            abstract_source = other.provider
    if abstract != base.abstract:
        field_sources["abstract"] = abstract_source

    for other in others:
        external_ids.update({k: v for k, v in other.external_ids.items() if k not in external_ids})
        for u in other.urls:
            if u not in urls:
                urls.append(u)
        if other.citation_count is not None and (
            citation_count is None or other.citation_count > citation_count
        ):
            citation_count = other.citation_count
            field_sources["citation_count"] = other.provider
        if other.reference_count is not None and (
            reference_count is None or other.reference_count > reference_count
        ):
            reference_count = other.reference_count
            field_sources["reference_count"] = other.provider

    merged = base.model_copy(
        update={
            "external_ids": external_ids,
            "urls": urls,
            "citation_count": citation_count,
            "reference_count": reference_count,
            "abstract": abstract,
            "merged_from": [p.id for p in others],
            "field_sources": field_sources,
        }
    )
    cluster = DedupCluster(
        canonical_id=merged.id,
        match_tier=match_tier,
        members=[ClusterMember(id=p.id, provider=p.provider) for p in papers],
    )
    return merged, cluster


def deduplicate(
    papers: list[Paper], strategy: Strategy = "auto"
) -> tuple[list[Paper], DedupReport]:
    input_count = len(papers)
    clusters: list[DedupCluster] = []

    # Tier 1: exact identifier match. Normalization already assigns the same
    # `Paper.id` to papers that share a strong identifier, so this is a
    # straight group-by.
    by_id: dict[str, list[Paper]] = defaultdict(list)
    for p in papers:
        by_id[p.id].append(p)

    stage_one: list[Paper] = []
    for _pid, group in by_id.items():
        if len(group) == 1:
            stage_one.append(group[0])
        else:
            merged, cluster = _merge(group, "exact_doi")
            clusters.append(cluster)
            stage_one.append(merged)

    if strategy == "strict":
        result = stage_one
    else:
        # Tier 2 (+ tier 3 if aggressive): fuzzy matching among the remaining
        # (already exact-deduped) representatives. O(n^2) title comparisons;
        # acceptable at typical per-request result-set sizes (<= a few
        # thousand papers per the graph/search bounds elsewhere in this
        # service).
        result = _fuzzy_merge(stage_one, clusters, strategy)

    by_tier: dict[str, int] = defaultdict(int)
    by_provider_pair: dict[str, int] = defaultdict(int)
    for cluster in clusters:
        by_tier[cluster.match_tier] += 1
        providers = sorted({m.provider for m in cluster.members})
        for i in range(len(providers)):
            for j in range(i + 1, len(providers)):
                by_provider_pair[f"{providers[i]}+{providers[j]}"] += 1

    report = DedupReport(
        input_count=input_count,
        output_count=len(result),
        duplicates_removed=input_count - len(result),
        clusters=clusters,
        by_tier=dict(by_tier),
        by_provider_pair=dict(by_provider_pair),
    )
    return result, report


def _fuzzy_merge(
    papers: list[Paper], clusters: list[DedupCluster], strategy: Strategy
) -> list[Paper]:
    """Cluster papers via fuzzy title (+year) matching.

    Under `strategy="auto"`, the only fuzzy tier is `fuzzy_title_year`, which
    requires an exact year match -- so candidates can safely be bucketed by
    year first, turning the O(n^2) comparison into O(sum(bucket_size^2)),
    which is far cheaper whenever results span many years (the common case).
    `strategy="aggressive"` additionally allows cross-year title-only matches,
    so it falls back to comparing every pair once (bucketing would miss
    legitimate cross-year duplicates).
    """
    if strategy == "aggressive":
        return _fuzzy_merge_pairs(papers, clusters, strategy)

    buckets: dict[int | None, list[Paper]] = {}
    for paper in papers:
        buckets.setdefault(paper.year, []).append(paper)

    result: list[Paper] = []
    for bucket in buckets.values():
        result.extend(_fuzzy_merge_pairs(bucket, clusters, strategy))
    return result


def _fuzzy_merge_pairs(
    papers: list[Paper], clusters: list[DedupCluster], strategy: Strategy
) -> list[Paper]:
    remaining = list(papers)
    result: list[Paper] = []

    while remaining:
        anchor = remaining.pop(0)
        matches = [anchor]
        match_tiers: list[str] = []
        still_remaining: list[Paper] = []

        for candidate in remaining:
            tier = _fuzzy_tier(anchor, candidate, strategy)
            if tier is not None:
                matches.append(candidate)
                match_tiers.append(tier)
            else:
                still_remaining.append(candidate)

        remaining = still_remaining

        if len(matches) == 1:
            result.append(anchor)
        else:
            tier_name = "fuzzy_title_year" if "fuzzy_title_year" in match_tiers else "fuzzy_title"
            merged, cluster = _merge(matches, tier_name)
            clusters.append(cluster)
            result.append(merged)

    return result


def _fuzzy_tier(a: Paper, b: Paper, strategy: Strategy) -> str | None:
    similarity = _title_similarity(a.title, b.title)

    if a.year is not None and b.year is not None and a.year == b.year:
        if similarity >= TITLE_YEAR_THRESHOLD:
            return "fuzzy_title_year"

    if strategy == "aggressive" and similarity >= TITLE_ONLY_THRESHOLD:
        return "fuzzy_title"

    return None
