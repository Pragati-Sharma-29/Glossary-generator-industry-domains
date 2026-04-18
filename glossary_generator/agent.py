"""Top-level orchestration for the glossary generator agent."""
from __future__ import annotations

import json
import logging
from typing import Iterable, Optional

from .bigquery_client import BigQueryCollector
from .config import AgentConfig
from .dataplex_client import DataplexInsightsCollector
from .glossary_publisher import GlossaryPublisher
from .models import (
    ColumnMapping,
    ColumnProfile,
    DatasetContext,
    GlossarySuggestion,
    TableProfile,
    TermSuggestion,
)
from .prompts import (
    DATASET_SUMMARY_TEMPLATE,
    RESPONSE_SCHEMA,
    SYSTEM_INSTRUCTION,
    TABLE_BLOCK_TEMPLATE,
    USER_PROMPT_TEMPLATE,
)
from .vertex_rag import VertexRagClient

logger = logging.getLogger(__name__)


class GlossaryGeneratorAgent:
    """Entry point combining collection → LLM reasoning → publishing."""

    def __init__(
        self,
        config: AgentConfig,
        *,
        bq: Optional[BigQueryCollector] = None,
        dataplex: Optional[DataplexInsightsCollector] = None,
        vertex: Optional[VertexRagClient] = None,
        publisher: Optional[GlossaryPublisher] = None,
    ):
        self.config = config
        self.bq = bq or BigQueryCollector(config.project_id)
        self.dataplex = dataplex or DataplexInsightsCollector(
            config.project_id, config.dataplex_location
        )
        self.vertex = vertex or VertexRagClient(
            config.project_id,
            config.location,
            model=config.vertex_model,
            rag_corpus=config.vertex_rag_corpus,
        )
        self._publisher = publisher

    # ------------------------------------------------------------------ main API

    def run(
        self,
        dataset_id: str,
        *,
        instructions: str = "",
        table_allowlist: Optional[Iterable[str]] = None,
        publish: Optional[bool] = None,
    ) -> dict:
        """Generate glossary suggestions for ``dataset_id``.

        Returns a dict with keys ``suggestion`` (:class:`GlossarySuggestion`
        as a plain dict) and, when publishing is enabled, ``publish_report``.
        """
        logger.info("Collecting BigQuery schema for %s", dataset_id)
        ctx = self.bq.collect(
            dataset_id,
            max_tables=self.config.max_tables,
            table_allowlist=table_allowlist,
        )

        logger.info("Enriching with Dataplex data insights")
        ctx = self.dataplex.enrich(ctx)

        logger.info("Prompting Vertex (%s) with RAG grounding", self.config.vertex_model)
        suggestion = self._invoke_llm(ctx, instructions)

        result: dict = {
            "suggestion": suggestion.to_dict(),
            "tables_without_scans": list(ctx.tables_without_scans),
        }

        publish = self.config.publish if publish is None else publish
        if publish:
            result["publish_report"] = self._publish(suggestion, dataset_id)
        return result

    # ------------------------------------------------------------------ LLM step

    def _invoke_llm(
        self, ctx: DatasetContext, instructions: str
    ) -> GlossarySuggestion:
        summary = self._summarise_dataset(ctx, instructions)
        prompt = USER_PROMPT_TEMPLATE.format(dataset_summary=summary)
        raw = self.vertex.generate_json(
            prompt,
            system_instruction=SYSTEM_INSTRUCTION,
            response_schema=RESPONSE_SCHEMA,
        )
        return self._parse_response(raw)

    @staticmethod
    def _parse_response(raw: dict) -> GlossarySuggestion:
        terms = [
            TermSuggestion(
                display_name=t["display_name"],
                definition=t["definition"],
                synonyms=t.get("synonyms", []),
                related_terms=t.get("related_terms", []),
            )
            for t in raw.get("terms", [])
        ]
        mappings = [
            ColumnMapping(
                term_display_name=m["term_display_name"],
                table_id=m["table_id"],
                column_name=m["column_name"],
                confidence=float(m.get("confidence", 0.0)),
                rationale=m.get("rationale", ""),
            )
            for m in raw.get("mappings", [])
        ]
        return GlossarySuggestion(
            industry=raw.get("industry", "Unknown"),
            domain=raw.get("domain", "Unknown"),
            rationale=raw.get("rationale", ""),
            terms=terms,
            mappings=mappings,
        )

    # ------------------------------------------------------------------ prompt build

    def _summarise_dataset(self, ctx: DatasetContext, instructions: str) -> str:
        tables_block = "\n\n".join(
            self._summarise_table(t) for t in ctx.tables
        )
        instr = instructions.strip() or "(none)"
        if ctx.tables_without_scans:
            instr += (
                "\n\nNOTE: the following table(s) have no Dataplex DATA_PROFILE "
                "or DATA_INSIGHTS scan available, so only their schema (no "
                "statistics) is provided. Be more conservative in confidence "
                f"scores for mappings on them: {', '.join(ctx.tables_without_scans)}."
            )
        return DATASET_SUMMARY_TEMPLATE.format(
            project_id=ctx.project_id,
            dataset_id=ctx.dataset_id,
            location=ctx.location or "",
            description=ctx.description or "(no description)",
            user_instructions=instr,
            tables_block=tables_block,
        )

    @staticmethod
    def _summarise_table(table: TableProfile) -> str:
        insights_line = ""
        if table.dataplex_insights:
            insights_line = (
                "dataplex_insights: "
                + json.dumps(table.dataplex_insights)[:1500]
            )
        columns = "\n".join(
            GlossaryGeneratorAgent._summarise_column(c) for c in table.columns
        )
        return TABLE_BLOCK_TEMPLATE.format(
            table_id=table.table_id,
            row_count=table.row_count or "?",
            description=table.description or "(none)",
            insights=insights_line,
            columns=columns,
        )

    @staticmethod
    def _summarise_column(col: ColumnProfile) -> str:
        parts = [f"  - {col.name} :: {col.data_type} ({col.mode})"]
        if col.description:
            parts.append(f"      desc: {col.description}")
        if col.null_ratio is not None or col.distinct_ratio is not None:
            parts.append(
                f"      null_ratio={col.null_ratio}, distinct_ratio={col.distinct_ratio}"
            )
        if col.top_values:
            parts.append(f"      top_values: {col.top_values[:5]}")
        if col.min_value is not None or col.max_value is not None:
            parts.append(f"      min={col.min_value}, max={col.max_value}")
        return "\n".join(parts)

    # ------------------------------------------------------------------ publishing

    def _publish(self, suggestion: GlossarySuggestion, dataset_id: str) -> dict:
        if not self.config.glossary_id:
            raise ValueError(
                "publish=True but no glossary_id set (DATAPLEX_GLOSSARY_ID)"
            )
        publisher = self._publisher or GlossaryPublisher(
            project_id=self.config.project_id,
            glossary_id=self.config.glossary_id,
            location=self.config.glossary_location,
            bq_region=self.config.dataplex_location,
            dry_run=False,
        )
        bare_dataset = dataset_id.split(".", 1)[-1]
        return publisher.publish(suggestion, dataset_id=bare_dataset)
