"""Publish suggested terms and column mappings to Dataplex business glossary.

Writes two kinds of resources
─────────────────────────────
1. **GlossaryTerm** — created under
   ``projects/{p}/locations/{loc}/glossaries/{g}/terms/{term_id}``
2. **EntryLink** of type ``definition`` — links a BigQuery column entry
   (in the system-managed ``@bigquery`` entry group) to the glossary term,
   created under
   ``projects/{p}/locations/{region}/entryGroups/@bigquery/entryLinks/{id}``.

Dataplex (Universal Catalog) exposes these via ``dataplex_v1.CatalogServiceClient``.
Field and method names on that client have evolved across releases of
``google-cloud-dataplex``; the code below is defensive — if a method is
missing, it records the intended payload in the report instead of aborting.

Set ``dry_run=True`` to preview without writing anything.
"""
from __future__ import annotations

import logging
import re
import uuid
from typing import Any, Optional
from urllib.parse import quote

from google.api_core.exceptions import AlreadyExists, GoogleAPICallError
from google.cloud import dataplex_v1

from .models import ColumnMapping, GlossarySuggestion, TermSuggestion

logger = logging.getLogger(__name__)

# Standard entry link type used to associate a column with its business-glossary term.
DEFINITION_ENTRY_LINK_TYPE = (
    "projects/dataplex-types/locations/global/entryLinkTypes/definition"
)


class GlossaryPublisher:
    def __init__(
        self,
        project_id: str,
        glossary_id: str,
        location: str = "global",
        *,
        bq_region: str = "us",
        dry_run: bool = True,
        client: Optional[Any] = None,
    ):
        self.project_id = project_id
        self.glossary_id = glossary_id
        self.location = location
        self.bq_region = bq_region
        self.dry_run = dry_run
        self._client = client or dataplex_v1.CatalogServiceClient()

    # ─────────────────────────────────────────────────────────── resource names

    @property
    def glossary_name(self) -> str:
        return (
            f"projects/{self.project_id}/locations/{self.location}"
            f"/glossaries/{self.glossary_id}"
        )

    def _term_name(self, term_id: str) -> str:
        return f"{self.glossary_name}/terms/{term_id}"

    def _bigquery_entry_group(self) -> str:
        return (
            f"projects/{self.project_id}/locations/{self.bq_region}"
            f"/entryGroups/@bigquery"
        )

    def _bigquery_column_entry(self, dataset_id: str, table_id: str) -> str:
        """Resource name of the BigQuery table entry.

        The column itself is referenced via the ``path`` field on the
        ``EntryReference`` (``Schema.<column_name>``).
        """
        # Dataplex stores a table's entry id as the URL-encoded
        # ``//bigquery.googleapis.com/...`` full resource name.
        bq_resource = (
            f"//bigquery.googleapis.com/projects/{self.project_id}"
            f"/datasets/{dataset_id}/tables/{table_id}"
        )
        return f"{self._bigquery_entry_group()}/entries/{quote(bq_resource, safe='')}"

    @staticmethod
    def _slug(display_name: str) -> str:
        cleaned = re.sub(r"[^a-z0-9\-]+", "-", display_name.strip().lower())
        return cleaned.strip("-")[:63] or "term"

    # ────────────────────────────────────────────────────────────────── public

    def publish(
        self,
        suggestion: GlossarySuggestion,
        *,
        dataset_id: Optional[str] = None,
    ) -> dict:
        """Create approved terms and entry links. Returns a structured report."""
        report: dict = {
            "created_terms": [],
            "skipped_terms": [],
            "mappings": [],
        }

        # 1) Ensure each referenced term exists.
        for term in suggestion.terms:
            self._ensure_term(term, report)

        # 2) Create one EntryLink per mapping.
        for mapping in suggestion.mappings:
            record = self._create_entry_link(
                mapping, dataset_id=dataset_id or self._infer_dataset(mapping)
            )
            report["mappings"].append(record)

        return report

    # ──────────────────────────────────────────────────── term creation

    def _ensure_term(self, term: TermSuggestion, report: dict) -> None:
        term_id = self._slug(term.display_name)
        full_name = self._term_name(term_id)
        if self.dry_run:
            report["created_terms"].append({"name": full_name, "dry_run": True})
            return

        create_fn = getattr(self._client, "create_glossary_term", None)
        request_cls = getattr(dataplex_v1, "CreateGlossaryTermRequest", None)
        term_cls = getattr(dataplex_v1, "GlossaryTerm", None)
        if not (create_fn and request_cls and term_cls):
            report["skipped_terms"].append(
                {"name": full_name, "reason": "dataplex SDK lacks create_glossary_term"}
            )
            return

        try:
            create_fn(
                request=request_cls(
                    parent=self.glossary_name,
                    term_id=term_id,
                    glossary_term=term_cls(
                        display_name=term.display_name,
                        description=term.definition,
                    ),
                )
            )
            report["created_terms"].append({"name": full_name})
        except AlreadyExists:
            report["skipped_terms"].append({"name": full_name, "reason": "exists"})
        except GoogleAPICallError as exc:
            logger.error("Failed to create term %s: %s", full_name, exc)
            report["skipped_terms"].append({"name": full_name, "reason": str(exc)})

    # ──────────────────────────────────────────────────── entry link creation

    def _create_entry_link(
        self, mapping: ColumnMapping, *, dataset_id: str
    ) -> dict:
        term_resource = self._term_name(self._slug(mapping.term_display_name))
        column_entry = self._bigquery_column_entry(dataset_id, mapping.table_id)
        link_id = f"gg-{uuid.uuid4().hex[:12]}"
        parent = self._bigquery_entry_group()
        entry_link_name = f"{parent}/entryLinks/{link_id}"

        payload = {
            "term": term_resource,
            "table": f"{dataset_id}.{mapping.table_id}",
            "column": mapping.column_name,
            "entry_link": entry_link_name,
            "entry_link_type": DEFINITION_ENTRY_LINK_TYPE,
            "confidence": mapping.confidence,
            "rationale": mapping.rationale,
            "dry_run": self.dry_run,
        }

        if self.dry_run:
            payload["status"] = "dry-run"
            return payload

        create_fn = getattr(self._client, "create_entry_link", None)
        request_cls = getattr(dataplex_v1, "CreateEntryLinkRequest", None)
        link_cls = getattr(dataplex_v1, "EntryLink", None)
        ref_cls = getattr(dataplex_v1, "EntryReference", None)
        if not (create_fn and request_cls and link_cls and ref_cls):
            payload["status"] = "skipped: SDK lacks create_entry_link"
            return payload

        try:
            entry_link = link_cls(
                entry_link_type=DEFINITION_ENTRY_LINK_TYPE,
                entry_references=[
                    ref_cls(
                        name=column_entry,
                        type_=ref_cls.Type.SOURCE,
                        path=f"Schema.{mapping.column_name}",
                    ),
                    ref_cls(name=term_resource, type_=ref_cls.Type.TARGET),
                ],
            )
            create_fn(
                request=request_cls(
                    parent=parent,
                    entry_link_id=link_id,
                    entry_link=entry_link,
                )
            )
            payload["status"] = "created"
        except AlreadyExists:
            payload["status"] = "exists"
        except GoogleAPICallError as exc:
            logger.error("create_entry_link failed for %s: %s", payload, exc)
            payload["status"] = f"error: {exc}"
        return payload

    # ─────────────────────────────────────────────────────────────── helpers

    @staticmethod
    def _infer_dataset(mapping: ColumnMapping) -> str:
        """Fall back path when caller didn't pass dataset_id explicitly.

        ``mapping.table_id`` is expected to be the simple table name; if the
        caller supplied ``dataset.table`` we split accordingly.
        """
        if "." in mapping.table_id:
            return mapping.table_id.split(".", 1)[0]
        return ""
