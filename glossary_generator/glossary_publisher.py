"""Publish suggested terms and column mappings to Dataplex business glossary.

Writes two kinds of resources
─────────────────────────────
1. **GlossaryTerm** — created under
   ``projects/{p}/locations/{loc}/glossaries/{g}/terms/{term_id}``
2. **EntryLink** of type ``definition`` — links a BigQuery column entry
   (in the system-managed ``@bigquery`` entry group) to the glossary term,
   created under
   ``projects/{p}/locations/{region}/entryGroups/@bigquery/entryLinks/{id}``.

Dataplex (Universal Catalog) exposes these via the ``dataplex_v1``
SDK client, but ``create_glossary_term`` / ``create_entry_link`` are not
yet shipped in every release of ``google-cloud-dataplex``. To stay
version-independent we call the Dataplex **REST API** directly using
ADC for auth — the REST surface is stable across SDK versions and its
request shape matches the proto one-for-one.

Set ``dry_run=True`` to preview without writing anything.
"""
from __future__ import annotations

import logging
import re
import uuid
from typing import Any, Optional

import google.auth
import google.auth.transport.requests
import requests

from .models import ColumnMapping, GlossarySuggestion, TermSuggestion

logger = logging.getLogger(__name__)

# Standard entry link types (see cloud.google.com/dataplex/docs/manage-glossaries).
DEFINITION_ENTRY_LINK_TYPE = (
    "projects/dataplex-types/locations/global/entryLinkTypes/definition"
)
SYNONYM_ENTRY_LINK_TYPE = (
    "projects/dataplex-types/locations/global/entryLinkTypes/synonym"
)
RELATED_ENTRY_LINK_TYPE = (
    "projects/dataplex-types/locations/global/entryLinkTypes/related"
)

_TERM_LINK_TYPES = {
    "synonym": SYNONYM_ENTRY_LINK_TYPE,
    # Accept the adjective form the UI historically emitted.
    "synonymous": SYNONYM_ENTRY_LINK_TYPE,
    "related": RELATED_ENTRY_LINK_TYPE,
}

_DATAPLEX_REST = "https://dataplex.googleapis.com/v1"
_AUTH_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


class GlossaryPublisher:
    def __init__(
        self,
        project_id: str,
        glossary_id: str,
        location: str = "global",
        *,
        bq_region: str = "us",
        dry_run: bool = True,
        client: Optional[Any] = None,  # kept for test injection / future use
    ):
        self.project_id = project_id
        self.glossary_id = glossary_id
        self.location = location
        self.bq_region = bq_region
        self.dry_run = dry_run
        self._client = client  # unused; Dataplex calls go through REST
        self._creds = None
        self._session = requests.Session()

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

    def _dataplex_entry_group(self) -> str:
        """System entry group that owns glossary terms as Entries."""
        return (
            f"projects/{self.project_id}/locations/{self.location}"
            f"/entryGroups/@dataplex"
        )

    def _bigquery_column_entry(self, dataset_id: str, table_id: str) -> str:
        """Resource name of the BigQuery table entry.

        The column itself is referenced via the ``path`` field on the
        ``EntryReference`` (``Schema.<column_name>``). For Google Cloud
        resources, Dataplex uses the full resource name minus the leading
        ``//`` as the entry id, with literal slashes preserved in the
        JSON body (URL-encoding is only required when embedding this id
        in a URL path).
        """
        entry_id = (
            f"bigquery.googleapis.com/projects/{self.project_id}"
            f"/datasets/{dataset_id}/tables/{table_id}"
        )
        return f"{self._bigquery_entry_group()}/entries/{entry_id}"

    def _term_entry(self, term_id: str) -> str:
        """Resource name of a glossary term as an Entry under ``@dataplex``.

        Dataplex exposes each GlossaryTerm as an Entry whose id is the
        term's full resource name (literal slashes). Entry links must
        reference terms via this Entry form, not the term resource name.
        """
        return f"{self._dataplex_entry_group()}/entries/{self._term_name(term_id)}"

    @staticmethod
    def _slug(display_name: str) -> str:
        cleaned = re.sub(r"[^a-z0-9\-]+", "-", display_name.strip().lower())
        return cleaned.strip("-")[:63] or "term"

    # ─────────────────────────────────────────────────────────── auth / REST

    def _access_token(self) -> str:
        if self._creds is None:
            self._creds, _ = google.auth.default(scopes=_AUTH_SCOPES)
        if not self._creds.valid:
            self._creds.refresh(google.auth.transport.requests.Request())
        return self._creds.token

    def _rest(
        self,
        method: str,
        url: str,
        *,
        params: Optional[dict] = None,
        json_body: Optional[dict] = None,
    ) -> requests.Response:
        return self._session.request(
            method,
            url,
            params=params,
            json=json_body,
            headers={
                "Authorization": f"Bearer {self._access_token()}",
                "Content-Type": "application/json",
            },
            timeout=30,
        )

    # ────────────────────────────────────────────────────────────────── public

    def publish(
        self,
        suggestion: GlossarySuggestion,
        *,
        dataset_id: Optional[str] = None,
        term_links: Optional[list[dict]] = None,
    ) -> dict:
        """Create approved terms, column→term links, and term-to-term links.

        ``term_links`` is an optional list of dicts shaped like
        ``{"parent": <display>, "child": <display>, "kind":
        "synonym" | "related"}`` used to emit structured entry links
        between two terms in this glossary (e.g. when the operator has
        promoted a synonym into its own standalone term).

        Returns a structured report.
        """
        report: dict = {
            "created_terms": [],
            "skipped_terms": [],
            "mappings": [],
            "term_links": [],
        }

        # 1) Ensure each referenced term exists.
        for term in suggestion.terms:
            self._ensure_term(term, report)

        # 2) Create one EntryLink per column mapping.
        for mapping in suggestion.mappings:
            record = self._create_entry_link(
                mapping, dataset_id=dataset_id or self._infer_dataset(mapping)
            )
            report["mappings"].append(record)

        # 3) Create term-to-term entry links (synonymous / related).
        for link in term_links or []:
            report["term_links"].append(self._create_term_link(link))

        return report

    # ──────────────────────────────────────────────────── term creation

    def _ensure_term(self, term: TermSuggestion, report: dict) -> None:
        term_id = self._slug(term.display_name)
        full_name = self._term_name(term_id)
        if self.dry_run:
            report["created_terms"].append({"name": full_name, "dry_run": True})
            return

        url = f"{_DATAPLEX_REST}/{self.glossary_name}/terms"
        body = {
            # Dataplex's GlossaryTerm proto declares `parent` as a
            # required field on the resource itself, so the path-encoded
            # parent isn't enough — it must also appear in the body or
            # the API rejects the request with
            # "Term.parent field should be of the format ...".
            "parent": self.glossary_name,
            "displayName": term.display_name,
            "description": _term_description(term),
        }
        try:
            resp = self._rest("POST", url, params={"termId": term_id}, json_body=body)
        except requests.RequestException as exc:
            logger.error("create_glossary_term network error for %s: %s", full_name, exc)
            report["skipped_terms"].append({"name": full_name, "reason": str(exc)})
            return

        if resp.status_code in (200, 201):
            report["created_terms"].append({"name": full_name})
        elif resp.status_code == 409:
            report["skipped_terms"].append({"name": full_name, "reason": "exists"})
        else:
            logger.error(
                "create_glossary_term HTTP %d for %s: %s",
                resp.status_code, full_name, resp.text[:300],
            )
            report["skipped_terms"].append(
                {"name": full_name, "reason": f"HTTP {resp.status_code}: {resp.text[:200]}"}
            )

    # ──────────────────────────────────────────────────── entry link creation

    def _create_entry_link(
        self, mapping: ColumnMapping, *, dataset_id: str
    ) -> dict:
        term_id = self._slug(mapping.term_display_name)
        term_entry = self._term_entry(term_id)
        column_entry = self._bigquery_column_entry(dataset_id, mapping.table_id)
        link_id = f"gg-{uuid.uuid4().hex[:12]}"
        parent = self._bigquery_entry_group()
        entry_link_name = f"{parent}/entryLinks/{link_id}"

        payload = {
            "term": self._term_name(term_id),
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

        url = f"{_DATAPLEX_REST}/{parent}/entryLinks"
        body = {
            "entryLinkType": DEFINITION_ENTRY_LINK_TYPE,
            "entryReferences": [
                {
                    "name": column_entry,
                    "type": "SOURCE",
                    "path": f"Schema.{mapping.column_name}",
                },
                {"name": term_entry, "type": "TARGET"},
            ],
        }
        try:
            resp = self._rest("POST", url, params={"entryLinkId": link_id}, json_body=body)
        except requests.RequestException as exc:
            logger.error("create_entry_link network error for %s: %s", payload, exc)
            payload["status"] = f"error: {exc}"
            return payload

        if resp.status_code in (200, 201):
            payload["status"] = "created"
        elif resp.status_code == 409:
            payload["status"] = "exists"
        else:
            logger.error(
                "create_entry_link HTTP %d for %s: %s",
                resp.status_code, payload, resp.text[:300],
            )
            payload["status"] = f"error: HTTP {resp.status_code}: {resp.text[:200]}"
        return payload

    # ──────────────────────────────────────────────────── term-to-term links

    def _create_term_link(self, link: dict) -> dict:
        """Create a ``synonym`` or ``related`` entry link between two terms.

        Both endpoints are terms inside ``self.glossary_name``. Dataplex
        exposes each term as an Entry under the system-managed
        ``@dataplex`` entry group at the glossary's location, and entry
        links between terms are also created under that same group. Both
        relations are non-directional, so each EntryReference carries
        ``type: UNSPECIFIED`` per the Dataplex proto.

        ``link`` shape: ``{"parent": <display>, "child": <display>,
        "kind": "synonym" | "related"}`` (``synonymous`` is accepted as
        an alias for ``synonym``).
        """
        parent_display = link["parent"]
        child_display = link["child"]
        raw_kind = link.get("kind", "related")
        link_type = _TERM_LINK_TYPES.get(raw_kind)
        if link_type is None:
            return {
                "kind": raw_kind,
                "parent": parent_display,
                "child": child_display,
                "status": f"error: unsupported term link kind {raw_kind!r}",
            }
        kind = "synonym" if link_type == SYNONYM_ENTRY_LINK_TYPE else "related"
        parent_entry = self._term_entry(self._slug(parent_display))
        child_entry = self._term_entry(self._slug(child_display))
        link_id = f"gg-{kind}-{uuid.uuid4().hex[:10]}"
        entry_group = self._dataplex_entry_group()
        entry_link_name = f"{entry_group}/entryLinks/{link_id}"

        record = {
            "kind": kind,
            "parent": parent_display,
            "child": child_display,
            "entry_link": entry_link_name,
            "dry_run": self.dry_run,
        }

        if self.dry_run:
            record["status"] = "dry-run"
            return record

        url = f"{_DATAPLEX_REST}/{entry_group}/entryLinks"
        body = {
            "entryLinkType": link_type,
            "entryReferences": [
                {"name": parent_entry, "type": "UNSPECIFIED"},
                {"name": child_entry, "type": "UNSPECIFIED"},
            ],
        }
        try:
            resp = self._rest("POST", url, params={"entryLinkId": link_id}, json_body=body)
        except requests.RequestException as exc:
            logger.error("create_term_link network error %s: %s", record, exc)
            record["status"] = f"error: {exc}"
            return record

        if resp.status_code in (200, 201):
            record["status"] = "created"
        elif resp.status_code == 409:
            record["status"] = "exists"
        else:
            logger.error(
                "create_term_link HTTP %d for %s: %s",
                resp.status_code, record, resp.text[:300],
            )
            record["status"] = (
                f"error: HTTP {resp.status_code}: {resp.text[:200]}"
            )
        return record

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


def _term_description(term: TermSuggestion) -> str:
    """Render a TermSuggestion into a Dataplex term description.

    Dataplex's GlossaryTerm proto only carries ``displayName`` and
    ``description`` fields — no dedicated synonym / related-term
    structures. To avoid losing that signal we append them to the
    description so they're visible in the Catalog UI and searchable.
    """
    parts = [term.definition.strip()]
    synonyms = _format_related(term.synonyms)
    if synonyms:
        parts.append("**Also known as:** " + synonyms)
    related = _format_related(term.related_terms)
    if related:
        parts.append("**Related:** " + related)
    return "\n\n".join(p for p in parts if p)


def _format_related(items: list) -> str:
    """Render synonyms / related_terms into a comma-joined string.

    ``TermSuggestion`` stores these as ``list[dict]`` of
    ``{"name": str, "description": str}``, but tolerate plain strings
    too so legacy callers keep working.
    """
    names: list[str] = []
    for item in items or []:
        if isinstance(item, dict):
            name = (item.get("name") or "").strip()
        else:
            name = str(item).strip()
        if name:
            names.append(name)
    return ", ".join(names)
