"""Enrich tables with Dataplex data profile / data insights results.

Dataplex exposes two relevant DataScan types:

* ``DATA_PROFILE`` — column-level statistics (null %, distinct %, top values,
  min/max).
* ``DATA_INSIGHTS`` — Gemini-generated natural-language insights and sample
  questions about the table.

We fetch the most recent successful job for any scan whose source resource
matches the BigQuery table, and fold the statistics back onto the
``ColumnProfile`` / ``TableProfile`` objects produced by ``BigQueryCollector``.
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
        self._client = client or dataplex_v1.DataScanServiceClient()

    def enrich(self, ctx: DatasetContext) -> DatasetContext:
        """Attach data-profile/insights results to every table in ``ctx``."""
        scans = self._list_scans()
        for table in ctx.tables:
            resource_name = (
                f"//bigquery.googleapis.com/projects/{ctx.project_id}/"
                f"datasets/{ctx.dataset_id}/tables/{table.table_id}"
            )
            profile_scan = scans.get(("DATA_PROFILE", resource_name))
            insights_scan = scans.get(("DATA_INSIGHTS", resource_name))
            if profile_scan:
                self._apply_profile(table, profile_scan)
            if insights_scan:
                table.dataplex_insights = self._fetch_insights(insights_scan)
        return ctx

    # ------------------------------------------------------------------ scan listing

    def _list_scans(self) -> dict[tuple[str, str], str]:
        """Return a ``(scan_type, resource_name) -> scan_name`` lookup."""
        parent = f"projects/{self.project_id}/locations/{self.location}"
        scans: dict[tuple[str, str], str] = {}
        try:
            for scan in self._client.list_data_scans(parent=parent):
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
            scan = self._client.get_data_scan(
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
            # Numeric/string profile sub-messages are union-typed; read defensively.
            for sub in ("integer_profile", "double_profile", "string_profile"):
                info = getattr(stats, sub, None)
                if info is None:
                    continue
                col.min_value = getattr(info, "min", col.min_value)
                col.max_value = getattr(info, "max", col.max_value)

    # ------------------------------------------------------------------ data insights

    def _fetch_insights(self, scan_name: str) -> Optional[dict]:
        try:
            scan = self._client.get_data_scan(
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
        # The result proto differs between preview/GA; serialise to dict best-effort.
        try:
            from google.protobuf.json_format import MessageToDict

            return MessageToDict(result._pb, preserving_proto_field_name=True)
        except Exception:  # noqa: BLE001
            return {"raw": str(result)}
