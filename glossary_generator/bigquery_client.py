"""Collect schema, descriptions, and small samples from BigQuery."""
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
        max_sample_rows: int = 10,
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
                ctx.tables.append(
                    self._profile_table(
                        dataset_ref, item.table_id, max_sample_rows=max_sample_rows
                    )
                )
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
        *,
        max_sample_rows: int,
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
        profile = TableProfile(
            table_id=table.table_id,
            description=table.description,
            row_count=table.num_rows,
            columns=columns,
        )
        if max_sample_rows > 0:
            self._attach_samples(table, profile, max_sample_rows)
        return profile

    def _attach_samples(
        self, table: bigquery.Table, profile: TableProfile, max_sample_rows: int
    ) -> None:
        """Pull a tiny sample of rows so the LLM can reason about content."""
        try:
            rows = self._client.list_rows(table, max_results=max_sample_rows)
            sample_map: dict[str, list] = {c.name: [] for c in profile.columns}
            for row in rows:
                for name in sample_map:
                    sample_map[name].append(row.get(name))
            for col in profile.columns:
                col.sample_values = sample_map.get(col.name, [])
        except Exception as exc:  # noqa: BLE001
            logger.debug("Could not sample %s: %s", table.table_id, exc)
