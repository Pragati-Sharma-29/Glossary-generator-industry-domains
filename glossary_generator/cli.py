"""CLI entry point: ``python -m glossary_generator ...``."""
from __future__ import annotations

import argparse
import json
import logging
import sys

from .agent import GlossaryGeneratorAgent
from .config import AgentConfig


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="glossary-generator",
        description=(
            "Suggest business-glossary terms and column mappings for a "
            "BigQuery dataset using Dataplex data insights + Vertex RAG."
        ),
    )
    p.add_argument("dataset_id", help="'project.dataset' or 'dataset' id")
    p.add_argument("--instructions", default="", help="Optional user guidance")
    p.add_argument("--project", help="GCP project (overrides env)")
    p.add_argument("--location", help="Vertex location, e.g. us-central1")
    p.add_argument("--dataplex-location", help="Dataplex DataScan location")
    p.add_argument("--model", help="Vertex model, e.g. gemini-2.5-pro")
    p.add_argument("--rag-corpus", help="Full Vertex RAG corpus resource name")
    p.add_argument("--glossary-id", help="Target Dataplex glossary id")
    p.add_argument(
        "--glossary-location", help="Target glossary location (default: global)"
    )
    p.add_argument("--table", action="append", dest="tables", help="Limit to this table (repeatable)")
    p.add_argument("--max-tables", type=int, default=50)
    p.add_argument("--max-sample-rows", type=int, default=10)
    p.add_argument("--publish", action="store_true", help="Actually write to the glossary")
    p.add_argument("--verbose", "-v", action="count", default=0)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.WARNING - 10 * min(args.verbose, 2),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config = AgentConfig.from_env(
        project_id=args.project,
        location=args.location,
        vertex_model=args.model,
        vertex_rag_corpus=args.rag_corpus,
        dataplex_location=args.dataplex_location,
        glossary_id=args.glossary_id,
        glossary_location=args.glossary_location,
        max_tables=args.max_tables,
        max_sample_rows=args.max_sample_rows,
        publish=args.publish,
    )

    agent = GlossaryGeneratorAgent(config)
    result = agent.run(
        args.dataset_id,
        instructions=args.instructions,
        table_allowlist=args.tables,
        publish=args.publish,
    )
    json.dump(result, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
