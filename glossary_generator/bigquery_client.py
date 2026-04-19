"""Collect schema and descriptions from BigQuery.

The collector intentionally does **not** sample table rows. Statistical
context (distinct ratio, top values, etc.) must be supplied by Dataplex
``DATA_PROFILE`` and ``DATA_INSIGHTS`` scans — see
:mod:`glossary_generator.dataplex_client`.
"""
from __future__ import annotations

import logging
from typing import Iterable, Optional

from google.cloud import bigquery

from .models import ColumnProfile, DatasetContext, TableProfile

logger = logging.getLogger(__name__)


class BigQueryCollector:
    def __init__(self, project_id: str, client: Optional[bigquery.Client] = None):
        self.project_id = project_id
        self._client = client or bigquery.Client(project=project_id)

    def collect(
        self,
        dataset_id: str,
        *,
        max_tables: int = 50,
        table_allowlist: Optional[Iterable[str]] = None,
    ) -> DatasetContext:
        """Return a populated DatasetContext for the requested dataset."""
        dataset_ref = self._resolve_dataset(dataset_id)
        dataset = self._client.get_dataset(dataset_ref)
        ctx = DatasetContext(
            project_id=dataset.project,
            dataset_id=dataset.dataset_id,
            location=dataset.location,
            description=dataset.description,
        )

        allow = set(table_allowlist) if table_allowlist else None
        tables = list(self._client.list_tables(dataset_ref, max_results=max_tables))
        for item in tables:
            if allow and item.table_id not in allow:
                continue
            try:
                ctx.tables.append(self._profile_table(dataset_ref, item.table_id))
            except Exception as exc:  # noqa: BLE001 - surface but don't abort
                logger.warning("Skipping %s: %s", item.table_id, exc)
        return ctx

    def _resolve_dataset(self, dataset_id: str) -> bigquery.DatasetReference:
        if "." in dataset_id:
            project, dataset = dataset_id.split(".", 1)
            return bigquery.DatasetReference(project, dataset)
        return bigquery.DatasetReference(self.project_id, dataset_id)

    def _profile_table(
        self,
        dataset_ref: bigquery.DatasetReference,
        table_id: str,
    ) -> TableProfile:
        table = self._client.get_table(dataset_ref.table(table_id))
        columns = [
            ColumnProfile(
                name=field.name,
                data_type=field.field_type,
                mode=field.mode or "NULLABLE",
                description=field.description,
            )
            for field in table.schema
        ]
        return TableProfile(
            table_id=table.table_id,
            description=table.description,
            row_count=table.num_rows,
            columns=columns,
        )
