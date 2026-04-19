"""Runtime configuration for the glossary generator agent."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AgentConfig:
    """Configuration values resolved from env vars or explicit overrides.

    Any field left as ``None`` falls back to the matching ``GOOGLE_*`` /
    ``VERTEX_*`` environment variable at construction time.
    """

    project_id: str
    location: str = "us-central1"

    # Vertex AI
    vertex_model: str = "gemini-2.5-pro"
    vertex_rag_corpus: Optional[str] = None  # full resource name

    # Dataplex
    dataplex_location: str = "us-central1"
    glossary_id: Optional[str] = None  # target glossary to publish into
    glossary_location: str = "global"

    # Behaviour
    max_tables: int = 50
    max_mappings_per_table: int = 50
    publish: bool = False  # dry-run by default

    extra: dict = field(default_factory=dict)

    @classmethod
    def from_env(cls, **overrides) -> "AgentConfig":
        values = {
            "project_id": os.environ.get("GOOGLE_CLOUD_PROJECT", ""),
            "location": os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
            "vertex_model": os.environ.get("VERTEX_MODEL", "gemini-2.5-pro"),
            "vertex_rag_corpus": os.environ.get("VERTEX_RAG_CORPUS"),
            "dataplex_location": os.environ.get("DATAPLEX_LOCATION", "us-central1"),
            "glossary_id": os.environ.get("DATAPLEX_GLOSSARY_ID"),
            "glossary_location": os.environ.get("DATAPLEX_GLOSSARY_LOCATION", "global"),
        }
        values.update({k: v for k, v in overrides.items() if v is not None})
        if not values["project_id"]:
            raise ValueError(
                "project_id is required (set GOOGLE_CLOUD_PROJECT or pass explicitly)"
            )
        return cls(**values)
