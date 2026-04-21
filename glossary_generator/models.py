"""Shared dataclasses describing inputs and outputs of the agent."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ColumnProfile:
    """Profile for one column, assembled from BigQuery schema + Dataplex insights.

    Statistical fields are populated only when a Dataplex DATA_PROFILE scan
    has run against the table.
    """

    name: str
    data_type: str
    mode: str = "NULLABLE"
    description: Optional[str] = None
    null_ratio: Optional[float] = None
    distinct_ratio: Optional[float] = None
    top_values: list[Any] = field(default_factory=list)
    min_value: Optional[Any] = None
    max_value: Optional[Any] = None


@dataclass
class TableProfile:
    table_id: str
    description: Optional[str] = None
    row_count: Optional[int] = None
    columns: list[ColumnProfile] = field(default_factory=list)
    dataplex_insights: Optional[dict] = None  # raw Dataplex data-insights payload


@dataclass
class DatasetContext:
    project_id: str
    dataset_id: str
    location: Optional[str] = None
    description: Optional[str] = None
    tables: list[TableProfile] = field(default_factory=list)
    # Populated by DataplexInsightsCollector.enrich() — tables that the
    # collector skipped because no DATA_PROFILE / DATA_INSIGHTS scan existed.
    tables_without_scans: list[str] = field(default_factory=list)


@dataclass
class TermSuggestion:
    """A proposed business glossary term.

    ``synonyms`` and ``related_terms`` are lists of dicts shaped
    ``{"name": str, "description": str}``. The description is a one-line
    explanation of the secondary term and why it relates to this term —
    used in the review UI and, if the operator promotes it, as the
    definition of the new standalone GlossaryTerm.
    """

    display_name: str
    definition: str
    synonyms: list[dict] = field(default_factory=list)
    related_terms: list[dict] = field(default_factory=list)


@dataclass
class ColumnMapping:
    """A proposed mapping between a term and one or more columns."""

    term_display_name: str
    table_id: str
    column_name: str
    confidence: float
    rationale: str


@dataclass
class GlossarySuggestion:
    """Full agent output."""

    industry: str
    domain: str
    rationale: str
    terms: list[TermSuggestion] = field(default_factory=list)
    mappings: list[ColumnMapping] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "industry": self.industry,
            "domain": self.domain,
            "rationale": self.rationale,
            "terms": [t.__dict__ for t in self.terms],
            "mappings": [m.__dict__ for m in self.mappings],
        }
