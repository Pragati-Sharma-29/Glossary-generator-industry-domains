"""Enrich tables with Dataplex data profile / data insights results.

Dataplex exposes two relevant DataScan types:

* ``DATA_PROFILE`` — column-level statistics (null %, distinct %, top values,
  min/max).
* ``DATA_INSIGHTS`` — Gemini-generated natural-language insights and sample
  questions about the table.

The collector fetches the most recent successful job for any scan whose
source resource matches a BigQuery table in the supplied
:class:`DatasetContext` and folds the statistics back onto the
``ColumnProfile`` / ``TableProfile`` objects.

If **no** scans of either type are found for any of the requested tables,
:class:`MissingDataplexScansError` is raised — the agent treats high-quality
suggestions as dependent on profile/insight context and refuses to run
blind.
"""
from __future__ import annotations

import logging
from typing import Optional

from google.api_core.exceptions import GoogleAPICallError, NotFound
from google.cloud import dataplex_v1

from .models import ColumnProfile, DatasetContext, TableProfile

logger = logging.getLogger(__name__)


class MissingDataplexScansError(Exception):
    """No Dataplex profile or insights scans exist for the requested tables.

    The web app catches this and renders a remediation page with the exact
    ``gcloud dataplex datascans`` commands to run.
    """

    def __init__(
        self,
        project_id: str,
        dataset_id: str,
        region: str,
        tables: list[str],
    ):
        self.project_id = project_id
        self.dataset_id = dataset_id
        self.region = region
        self.tables = tables
        super().__init__(
            f"No Dataplex DATA_PROFILE or DATA_INSIGHTS scans found for any "
            f"of the {len(tables)} selected tables in "
            f"{project_id}.{dataset_id} (region={region})."
        )

    def remediation_commands(self) -> list[str]:
        """Return ``gcloud`` commands the operator should run."""
        out: list[str] = []
        for table in self.tables:
            scan_id = f"profile-{self.dataset_id}-{table}"[:63]
            insights_id = f"insights-{self.dataset_id}-{table}"[:63]
            resource = (
                f"//bigquery.googleapis.com/projects/{self.project_id}"
                f"/datasets/{self.dataset_id}/tables/{table}"
            )
            out.append(
                f"gcloud dataplex datascans create data-profile {scan_id} "
                f"--project={self.project_id} --location={self.region} "
                f"--data-source-resource='{resource}'"
            )
            out.append(
                f"gcloud dataplex datascans run {scan_id} "
                f"--project={self.project_id} --location={self.region}"
            )
            out.append(
                f"gcloud dataplex datascans create data-discovery {insights_id} "
                f"--project={self.project_id} --location={self.region} "
                f"--data-source-resource='{resource}'"
            )
        return out


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
        """Attach data-profile/insights results to every table in ``ctx``.

        Raises
        ------
        MissingDataplexScansError
            If none of the tables in ``ctx`` have a profile or insights scan.
        """
        scans = self._list_scans()
        tables_with_scan: list[str] = []
        for table in ctx.tables:
            resource_name = (
                f"//bigquery.googleapis.com/projects/{ctx.project_id}/"
                f"datasets/{ctx.dataset_id}/tables/{table.table_id}"
            )
            profile_scan = scans.get(("DATA_PROFILE", resource_name))
            insights_scan = scans.get(("DATA_INSIGHTS", resource_name))
            if not profile_scan and not insights_scan:
                continue
            if profile_scan:
                self._apply_profile(table, profile_scan)
            if insights_scan:
                table.dataplex_insights = self._fetch_insights(insights_scan)
            tables_with_scan.append(table.table_id)

        if not tables_with_scan and ctx.tables:
            raise MissingDataplexScansError(
                project_id=ctx.project_id,
                dataset_id=ctx.dataset_id,
                region=self.location,
                tables=[t.table_id for t in ctx.tables],
            )

        skipped = [t.table_id for t in ctx.tables if t.table_id not in tables_with_scan]
        if skipped:
            logger.warning(
                "Proceeding without Dataplex context for %d table(s): %s",
                len(skipped), ", ".join(skipped),
            )
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
        try:
            from google.protobuf.json_format import MessageToDict

            return MessageToDict(result._pb, preserving_proto_field_name=True)
        except Exception:  # noqa: BLE001
            return {"raw": str(result)}
