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

import hashlib
import logging
import re
import time
import uuid
from typing import Any, Optional
from urllib.parse import quote

import google.auth
import google.auth.transport.requests
import requests

from .models import ColumnMapping, GlossarySuggestion, TermSuggestion

logger = logging.getLogger(__name__)

# Standard entry link type used to associate a column with its business-glossary term.
DEFINITION_ENTRY_LINK_TYPE = (
    "projects/dataplex-types/locations/global/entryLinkTypes/definition"
)

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
        """Resource name of a glossary term (used for create + GET)."""
        return f"{self.glossary_name}/terms/{term_id}"

    def _term_entry_name(self, term_id: str) -> str:
        """Entry-form name of a glossary term (used in EntryReferences).

        Dataplex rejects a raw ``projects/…/glossaries/{g}/terms/{t}`` as
        an EntryReference.name with HTTP 400 "invalid format". Glossary
        terms are catalogued in the system-managed ``@dataplex`` entry
        group at location ``global``; references must be the entry form.
        """
        term_resource = self._term_name(term_id)
        entry_group = (
            f"projects/{self.project_id}/locations/global"
            f"/entryGroups/@dataplex"
        )
        return f"{entry_group}/entries/{quote(term_resource, safe='')}"

    def _bigquery_entry_group(self) -> str:
        return (
            f"projects/{self.project_id}/locations/{self.bq_region}"
            f"/entryGroups/@bigquery"
        )

    def _bigquery_column_entry(self, dataset_id: str, table_id: str) -> str:
        """Resource name of the BigQuery table entry.

        Dataplex's auto-catalogued ``@bigquery`` entries use the URL-encoded
        form of ``bigquery.googleapis.com/projects/<p>/datasets/<d>/tables/<t>``
        as the entry id — **no** leading ``//``. Using ``//bigquery.googleapis.com``
        here produced an HTTP 400 ``entry name reference invalid`` from
        Dataplex.

        The column itself is referenced via the ``path`` field on the
        ``EntryReference`` (``Schema.<column_name>``).
        """
        bq_resource = (
            f"bigquery.googleapis.com/projects/{self.project_id}"
            f"/datasets/{dataset_id}/tables/{table_id}"
        )
        return f"{self._bigquery_entry_group()}/entries/{quote(bq_resource, safe='')}"

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
            "glossary": None,
            "created_terms": [],
            "skipped_terms": [],
            "mappings": [],
            "term_links": [],
        }

        # 0) Ensure the target glossary itself exists — create at ``global``
        #    if it doesn't, per spec. Without this every term create would
        #    404 on a glossary-id that the operator typed but never created.
        if not self._ensure_glossary(report):
            return report

        # 1) Ensure each referenced term exists.
        for term in suggestion.terms:
            self._ensure_term(term, report)

        # 2) Create one EntryLink per column mapping.
        for mapping in suggestion.mappings:
            record = self._create_entry_link(
                mapping, dataset_id=dataset_id or self._infer_dataset(mapping)
            )
            report["mappings"].append(record)

        # 3) Create term-to-term entry links (synonym / related).
        for link in term_links or []:
            report["term_links"].append(self._create_term_link(link))

        return report

    # ──────────────────────────────────────────────────── glossary creation

    def _ensure_glossary(self, report: dict) -> bool:
        """Check the target glossary exists; auto-create at ``global`` if not.

        Workflow
        --------
        1. GET ``projects/{p}/locations/{self.location}/glossaries/{id}``.
           If 200 → recorded as "exists", proceed.
        2. On 404 we re-pin ``self.location`` to ``global`` and POST
           ``projects/{p}/locations/global/glossaries?glossaryId={id}``.
           All downstream term + link URLs rebuild from ``self.glossary_name``
           (a property) so they automatically use the new location.
        3. The create response is a Google LRO; if so, poll briefly until it
           reports done so the term creates that follow don't race.

        Returns ``True`` if the glossary exists (or was successfully
        created), ``False`` if publish should abort.
        """
        if self.dry_run:
            report["glossary"] = {
                "name": self.glossary_name,
                "status": "dry-run",
            }
            return True

        get_url = f"{_DATAPLEX_REST}/{self.glossary_name}"
        try:
            resp = self._rest("GET", get_url)
        except requests.RequestException as exc:
            report["glossary"] = {
                "name": self.glossary_name,
                "status": f"GET error: {exc}",
            }
            return False

        if resp.status_code == 200:
            report["glossary"] = {"name": self.glossary_name, "status": "exists"}
            return True

        if resp.status_code != 404:
            logger.error(
                "GET glossary %s unexpectedly returned %d: %s",
                self.glossary_name, resp.status_code, resp.text[:300],
            )
            report["glossary"] = {
                "name": self.glossary_name,
                "status": f"GET HTTP {resp.status_code}: {resp.text[:200]}",
            }
            return False

        # 404 — pin to global and create.
        previous_location = self.location
        self.location = "global"
        logger.info(
            "Glossary '%s' not found at '%s'; auto-creating at 'global'",
            self.glossary_id, previous_location,
        )

        create_url = (
            f"{_DATAPLEX_REST}/projects/{self.project_id}"
            f"/locations/global/glossaries"
        )
        body = {
            "displayName": self.glossary_id.replace("-", " ").replace("_", " "),
            "description": (
                "Auto-created by the Glossary Generator when an operator-"
                "supplied glossary id was not found."
            ),
        }
        try:
            cresp = self._rest(
                "POST", create_url,
                params={"glossaryId": self.glossary_id},
                json_body=body,
            )
        except requests.RequestException as exc:
            report["glossary"] = {
                "name": self.glossary_name,
                "status": f"create error: {exc}",
            }
            return False

        if cresp.status_code == 409:
            report["glossary"] = {
                "name": self.glossary_name,
                "status": "exists at global (409 on create)",
            }
            return True

        if cresp.status_code not in (200, 201, 202):
            logger.error(
                "create_glossary HTTP %d for %s: %s",
                cresp.status_code, self.glossary_name, cresp.text[:500],
            )
            report["glossary"] = {
                "name": self.glossary_name,
                "status": (
                    f"create failed HTTP {cresp.status_code}: "
                    f"{cresp.text[:300]}"
                ),
            }
            return False

        # Created. Wait briefly if Dataplex returned an LRO envelope.
        try:
            body = cresp.json()
        except ValueError:
            body = {}
        op_name = body.get("name", "")
        if op_name.startswith(
            f"projects/{self.project_id}/locations/global/operations/"
        ):
            self._wait_for_lro(op_name, timeout_s=30)

        report["glossary"] = {
            "name": self.glossary_name,
            "status": f"auto-created at global (was missing at '{previous_location}')",
        }
        return True

    def _wait_for_lro(self, operation_name: str, *, timeout_s: int = 30) -> None:
        """Best-effort poll of a Dataplex long-running operation.

        Returns when the LRO reports ``done=true`` or the timeout elapses;
        errors are logged but never raised, since the caller already
        reported the create as successful. Subsequent term creates will
        fail loudly if the glossary didn't actually materialise.
        """
        url = f"{_DATAPLEX_REST}/{operation_name}"
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            try:
                resp = self._rest("GET", url)
            except requests.RequestException:
                time.sleep(2)
                continue
            if resp.status_code == 200:
                data = resp.json() if resp.content else {}
                if data.get("done"):
                    if "error" in data:
                        logger.warning(
                            "LRO %s reported error: %s", operation_name, data["error"],
                        )
                    return
            time.sleep(2)
        logger.warning("LRO %s did not complete within %ds", operation_name, timeout_s)

    # ──────────────────────────────────────────────────── term creation

    def _ensure_term(self, term: TermSuggestion, report: dict) -> None:
        term_id = self._slug(term.display_name)
        full_name = self._term_name(term_id)
        if self.dry_run:
            report["created_terms"].append({"name": full_name, "dry_run": True})
            return

        url = f"{_DATAPLEX_REST}/{self.glossary_name}/terms"
        body = {
            # Dataplex uniquely requires the parent glossary resource name
            # echoed in the body even though it's already in the URL path.
            # Without it the API rejects the create with HTTP 400
            # "'Term.parent' field should be of the format …".
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
        elif resp.status_code == 404:
            logger.error(
                "create_glossary_term 404 for %s (URL=%s): %s",
                full_name, url, resp.text[:500],
            )
            report["skipped_terms"].append({
                "name": full_name,
                "reason": (
                    f"HTTP 404 — glossary '{self.glossary_id}' not found at "
                    f"location '{self.location}'. Verify with:\n"
                    f"  gcloud dataplex glossaries describe {self.glossary_id} "
                    f"--project {self.project_id} --location {self.location}\n"
                    "If the glossary lives in another location, update the "
                    "'Glossary location' field under Advanced on the home "
                    "page. Raw Dataplex error: "
                    f"{resp.text[:200]}"
                ),
            })
        else:
            logger.error(
                "create_glossary_term HTTP %d for %s (URL=%s): %s",
                resp.status_code, full_name, url, resp.text[:500],
            )
            report["skipped_terms"].append(
                {"name": full_name, "reason": f"HTTP {resp.status_code}: {resp.text[:300]}"}
            )

    # ──────────────────────────────────────────────────── entry link creation

    def _create_entry_link(
        self, mapping: ColumnMapping, *, dataset_id: str
    ) -> dict:
        term_slug = self._slug(mapping.term_display_name)
        # Reference the term in its entry form (inside @dataplex), not
        # its raw glossary-term resource path — Dataplex 400s on the
        # latter as "invalid EntryReference format".
        term_resource = self._term_entry_name(term_slug)
        column_entry = self._bigquery_column_entry(dataset_id, mapping.table_id)
        # Deterministic id so re-publishing the same (term, table, column)
        # triple produces the same link id → Dataplex 409 → we mark
        # "exists" and skip, rather than minting a fresh UUID each run
        # and accumulating duplicate links.
        link_id = _deterministic_link_id(
            "def", term_slug, dataset_id, mapping.table_id, mapping.column_name,
        )
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

        url = f"{_DATAPLEX_REST}/{parent}/entryLinks"
        body = {
            "entryLinkType": DEFINITION_ENTRY_LINK_TYPE,
            "entryReferences": [
                {
                    "name": column_entry,
                    "type": "SOURCE",
                    "path": f"Schema.{mapping.column_name}",
                },
                {"name": term_resource, "type": "TARGET"},
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
        elif resp.status_code == 400 and "entry reference" in resp.text.lower():
            logger.error(
                "create_entry_link 400 for %s (URL=%s, body=%s): %s",
                payload, url, body, resp.text[:500],
            )
            payload["status"] = (
                f"HTTP 400 — Dataplex rejected the EntryReference. The most "
                f"common cause is the BigQuery table '{dataset_id}.{mapping.table_id}' "
                f"not yet being present in the @bigquery entry group at "
                f"{self.bq_region}. Dataplex auto-discovery usually populates "
                f"it within minutes of a scan; run a DATA_PROFILE scan on the "
                f"table first, wait a few minutes, then retry. Raw: "
                f"{resp.text[:250]}"
            )
        else:
            logger.error(
                "create_entry_link HTTP %d for %s (URL=%s, body=%s): %s",
                resp.status_code, payload, url, body, resp.text[:500],
            )
            payload["status"] = f"error: HTTP {resp.status_code}: {resp.text[:300]}"
        return payload

    # ──────────────────────────────────────────────────── term-to-term links

    def _create_term_link(self, link: dict) -> dict:
        """Create a ``synonym`` or ``related`` entry link between two terms.

        Per the Dataplex ``manage-glossaries`` reference, term↔term links
        are written under the system-managed ``@dataplex`` entry group
        in the same project and location as the glossary itself — not
        ``@dataplex-glossary``, which Dataplex rejects with HTTP 400
        ``entry group @dataplex-glossary is not allowed``.

        ``link`` shape: ``{"parent": <display>, "child": <display>,
        "kind": "synonym" | "related"}``.
        """
        parent_display = link["parent"]
        child_display = link["child"]
        kind = link.get("kind", "related")
        parent_slug = self._slug(parent_display)
        child_slug = self._slug(child_display)
        parent_resource = self._term_entry_name(parent_slug)
        child_resource = self._term_entry_name(child_slug)

        safe_kind = kind if kind in ("synonym", "related") else "related"
        link_type = (
            f"projects/dataplex-types/locations/global/entryLinkTypes/{safe_kind}"
        )
        link_id = _deterministic_link_id(safe_kind, parent_slug, child_slug)
        entry_group = (
            f"projects/{self.project_id}/locations/{self.location}"
            f"/entryGroups/@dataplex"
        )
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
            # ``related`` is an undirected link type: both references
            # must be ``UNSPECIFIED``. Using SOURCE/TARGET is the
            # pattern required for directed types (e.g. ``definition``);
            # Dataplex returns 400 "EntryLink must have SOURCE and TARGET
            # reference types for directed entry links, and UNSPECIFIED
            # reference" otherwise.
            "entryReferences": [
                {"name": parent_resource, "type": "UNSPECIFIED"},
                {"name": child_resource, "type": "UNSPECIFIED"},
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

    ``synonyms`` / ``related_terms`` are ``list[dict]`` with
    ``{"name": str, "description": str}`` shape (see TermSuggestion
    docstring). We render just the names inline; any per-ref
    descriptions the model supplied are available through the promoted-
    term flow on the review page.
    """
    parts = [term.definition.strip()]
    syn_names = _ref_names(term.synonyms)
    if syn_names:
        parts.append("**Also known as:** " + ", ".join(syn_names))
    rel_names = _ref_names(term.related_terms)
    if rel_names:
        parts.append("**Related:** " + ", ".join(rel_names))
    return "\n\n".join(p for p in parts if p)


def _ref_names(items) -> list[str]:
    """Pull display names out of a synonym / related_term list.

    Accepts either the new ``{"name": ..., "description": ...}`` dict
    form or plain strings (legacy / test-harness input), never raises
    on a malformed entry.
    """
    out: list[str] = []
    for item in items or []:
        if isinstance(item, dict):
            name = str(item.get("name", "")).strip()
        else:
            name = str(item).strip()
        if name:
            out.append(name)
    return out


def _deterministic_link_id(kind: str, *parts: str) -> str:
    """Stable entry-link id derived from its semantic content.

    Dataplex EntryLink ids are the primary key; two POSTs with the same
    id on the same entry group collide with HTTP 409, which our publish
    path already interprets as "exists" and skips. By deriving the id
    from a hash of the link's kind + ordered parts (term slug, dataset,
    table, column — or kind + parent + child for term-to-term), we get
    idempotent re-publishes without having to GET-then-POST.

    The sha1 is truncated to 16 hex chars; the ``{prefix}-{hash}``
    layout stays under Dataplex's entry-link id length limit.
    """
    prefix_map = {"def": "def", "synonym": "syn", "related": "rel"}
    prefix = prefix_map.get(kind, "gg")
    payload = "|".join([kind, *parts]).encode("utf-8")
    digest = hashlib.sha1(payload).hexdigest()[:16]
    return f"{prefix}-{digest}"
