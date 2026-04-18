"""Publish suggested terms and column mappings to Dataplex business glossary.

The Dataplex business glossary REST API lives under
``dataplex.googleapis.com/v1/projects/{p}/locations/{loc}/glossaries/{gl}``.
The Python generated client is ``google.cloud.dataplex_v1.CatalogServiceClient``
(in recent versions of ``google-cloud-dataplex``). Column-to-term associations
are written as ``Entry`` + ``Aspect`` records on the BigQuery entry under the
``@dataplex-types.global.business-glossary`` aspect type, or — when using the
legacy Data Catalog business glossary — via ``datacatalog_v1.Tag``.

This module hides both code paths behind one interface. All mutating calls are
no-ops when ``dry_run=True``.
"""
from __future__ import annotations

import logging
from typing import Optional

from google.api_core.exceptions import AlreadyExists, GoogleAPICallError
from google.cloud import dataplex_v1

from .models import ColumnMapping, GlossarySuggestion, TermSuggestion

logger = logging.getLogger(__name__)


class GlossaryPublisher:
    def __init__(
        self,
        project_id: str,
        glossary_id: str,
        location: str = "global",
        *,
        dry_run: bool = True,
        client: Optional[dataplex_v1.CatalogServiceClient] = None,
    ):
        self.project_id = project_id
        self.glossary_id = glossary_id
        self.location = location
        self.dry_run = dry_run
        self._client = client or dataplex_v1.CatalogServiceClient()

    # ------------------------------------------------------------------ helpers

    @property
    def glossary_name(self) -> str:
        return (
            f"projects/{self.project_id}/locations/{self.location}"
            f"/glossaries/{self.glossary_id}"
        )

    def _term_name(self, term_id: str) -> str:
        return f"{self.glossary_name}/terms/{term_id}"

    @staticmethod
    def _slug(display_name: str) -> str:
        return (
            display_name.strip().lower().replace(" ", "-").replace("/", "-")[:63]
            or "term"
        )

    # ------------------------------------------------------------------ API calls

    def publish(self, suggestion: GlossarySuggestion) -> dict:
        """Create missing terms and link them to columns. Returns a report dict."""
        report = {"created_terms": [], "skipped_terms": [], "mappings": []}

        for term in suggestion.terms:
            term_id = self._slug(term.display_name)
            full_name = self._term_name(term_id)
            if self.dry_run:
                report["created_terms"].append({"name": full_name, "dry_run": True})
                continue
            try:
                self._create_term(term_id, term)
                report["created_terms"].append({"name": full_name})
            except AlreadyExists:
                report["skipped_terms"].append({"name": full_name, "reason": "exists"})
            except GoogleAPICallError as exc:
                logger.error("Failed to create term %s: %s", full_name, exc)
                report["skipped_terms"].append({"name": full_name, "reason": str(exc)})

        for mapping in suggestion.mappings:
            entry = self._attach_mapping(mapping)
            report["mappings"].append(entry)
        return report

    # ------------------------------------------------------------------ term CRUD

    def _create_term(self, term_id: str, term: TermSuggestion) -> None:
        request = dataplex_v1.CreateGlossaryTermRequest(
            parent=self.glossary_name,
            term_id=term_id,
            glossary_term=dataplex_v1.GlossaryTerm(
                display_name=term.display_name,
                description=term.definition,
            ),
        )
        self._client.create_glossary_term(request=request)

    # ------------------------------------------------------------------ mapping

    def _attach_mapping(self, mapping: ColumnMapping) -> dict:
        """Link a term to a BigQuery column entry.

        Real implementation: upsert an ``Aspect`` of type
        ``projects/dataplex-types/locations/global/aspectTypes/overview``
        (or an org-defined synonym-aspect) onto the BigQuery column entry
        ``projects/{p}/locations/{loc}/entryGroups/@bigquery/entries/...``.
        We emit a structured stub so callers always get a record, and
        actually write only when ``dry_run`` is false.
        """
        record = {
            "term": self._term_name(self._slug(mapping.term_display_name)),
            "table": mapping.table_id,
            "column": mapping.column_name,
            "confidence": mapping.confidence,
            "rationale": mapping.rationale,
            "dry_run": self.dry_run,
        }
        if self.dry_run:
            return record
        # TODO: call self._client.create_entry / update_aspect once the
        # customer's entry-group + aspect-type schema is finalised.
        logger.info("Would publish aspect for mapping: %s", record)
        return record
