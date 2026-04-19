"""Enrich tables with Dataplex data profile / data insights results.

Two relevant DataScan types are consulted:

* ``DATA_PROFILE`` — column-level statistics (null %, distinct %, top values,
  min/max).
* ``DATA_INSIGHTS`` — Gemini-generated natural-language summaries.

The collector first does a single ``list_data_scans`` call to learn which
tables in the dataset already have a published scan. For every table it
then **only** calls ``get_data_scan`` when a matching scan exists — tables
without a scan trigger no API calls and are recorded in
``DatasetContext.tables_without_scans`` so the agent and UI can warn the
user that those recommendations will be schema-only.

Enrichment is fail-soft: if the listing call itself errors (e.g. missing
permission), the collector logs and returns ``ctx`` unchanged.
"""
from __future__ import annotations

import logging
from typing import Optional

from google.api_core.exceptions import GoogleAPICallError, NotFound
from google.cloud import dataplex_v1

from .models import ColumnProfile, DatasetContext, TableProfile

logger = logging.getLogger(__name__)


class DataplexInsightsCollector:
    def __init__(
        self,
        project_id: str,
        location: str,
        client: Optional[dataplex_v1.DataScanServiceClient] = None,
    ):
        self.project_id = project_id
        self.location = location
        self._client_factory = lambda: client or dataplex_v1.DataScanServiceClient()
        self._client: Optional[dataplex_v1.DataScanServiceClient] = client

    def enrich(self, ctx: DatasetContext) -> DatasetContext:
        """Attach data-profile/insights to tables that have scans.

        Tables without a scan are skipped — no per-table API call is made —
        and recorded in ``ctx.tables_without_scans``.
        """
        scans = self._list_scans()
        if not scans:
            ctx.tables_without_scans = [t.table_id for t in ctx.tables]
            logger.info(
                "No Dataplex scans found in %s/%s; proceeding with schema only.",
                self.project_id, self.location,
            )
            return ctx

        for table in ctx.tables:
            resource_name = (
                f"//bigquery.googleapis.com/projects/{ctx.project_id}/"
                f"datasets/{ctx.dataset_id}/tables/{table.table_id}"
            )
            profile_scan = scans.get(("DATA_PROFILE", resource_name))
            insights_scan = scans.get(("DATA_INSIGHTS", resource_name))

            if not profile_scan and not insights_scan:
                ctx.tables_without_scans.append(table.table_id)
                continue

            if profile_scan:
                self._apply_profile(table, profile_scan)
            if insights_scan:
                table.dataplex_insights = self._fetch_insights(insights_scan)

        if ctx.tables_without_scans:
            logger.warning(
                "Schema-only (no Dataplex scan) for %d table(s): %s",
                len(ctx.tables_without_scans),
                ", ".join(ctx.tables_without_scans),
            )
        return ctx

    # ------------------------------------------------------------------ scan listing

    def _get_client(self) -> dataplex_v1.DataScanServiceClient:
        if self._client is None:
            self._client = self._client_factory()
        return self._client

    def _list_scans(self) -> dict[tuple[str, str], str]:
        """Return a ``(scan_type, resource_name) -> scan_name`` lookup.

        Returns an empty dict on any failure — enrichment then becomes a
        no-op rather than blocking the agent.
        """
        parent = f"projects/{self.project_id}/locations/{self.location}"
        scans: dict[tuple[str, str], str] = {}
        try:
            for scan in self._get_client().list_data_scans(parent=parent):
                scan_type = dataplex_v1.DataScanType(scan.type_).name
                resource = scan.data.resource if scan.data else ""
                if resource:
                    scans[(scan_type, resource)] = scan.name
        except GoogleAPICallError as exc:
            logger.warning("Unable to list Dataplex scans: %s", exc)
        return scans

    # ------------------------------------------------------------------ data profile

    def _apply_profile(self, table: TableProfile, scan_name: str) -> None:
        try:
            scan = self._get_client().get_data_scan(
                name=scan_name,
                view=dataplex_v1.GetDataScanRequest.DataScanView.FULL,
            )
        except NotFound:
            return
        latest = getattr(scan.data_profile_result, "profile", None)
        if latest is None:
            return

        by_name: dict[str, ColumnProfile] = {c.name: c for c in table.columns}
        for field in getattr(latest, "fields", []):
            col = by_name.get(field.name)
            if not col:
                continue
            stats = field.profile
            col.null_ratio = getattr(stats, "null_ratio", None)
            col.distinct_ratio = getattr(stats, "distinct_ratio", None)
            col.top_values = [
                {"value": tv.value, "count": tv.count}
                for tv in getattr(stats, "top_n_values", [])
            ]
            for sub in ("integer_profile", "double_profile", "string_profile"):
                info = getattr(stats, sub, None)
                if info is None:
                    continue
                col.min_value = getattr(info, "min", col.min_value)
                col.max_value = getattr(info, "max", col.max_value)

    # ------------------------------------------------------------------ data insights

    def _fetch_insights(self, scan_name: str) -> Optional[dict]:
        try:
            scan = self._get_client().get_data_scan(
                name=scan_name,
                view=dataplex_v1.GetDataScanRequest.DataScanView.FULL,
            )
        except NotFound:
            return None
        result = getattr(scan, "data_discovery_result", None) or getattr(
            scan, "data_insights_result", None
        )
        if result is None:
            return None
        try:
            from google.protobuf.json_format import MessageToDict

            return MessageToDict(result._pb, preserving_proto_field_name=True)
        except Exception:  # noqa: BLE001
            return {"raw": str(result)}
