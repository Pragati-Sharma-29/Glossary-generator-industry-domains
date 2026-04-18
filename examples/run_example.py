"""Example: generate glossary suggestions for a BigQuery dataset.

Usage::

    export GOOGLE_CLOUD_PROJECT=my-proj
    export VERTEX_RAG_CORPUS=projects/my-proj/locations/us-central1/ragCorpora/123
    python examples/run_example.py my_dataset
"""
from __future__ import annotations

import json
import sys

from glossary_generator import GlossaryGeneratorAgent
from glossary_generator.config import AgentConfig


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: run_example.py <dataset_id> [instructions...]")
        raise SystemExit(2)

    dataset_id = sys.argv[1]
    instructions = " ".join(sys.argv[2:])

    config = AgentConfig.from_env()
    agent = GlossaryGeneratorAgent(config)

    result = agent.run(dataset_id, instructions=instructions)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
