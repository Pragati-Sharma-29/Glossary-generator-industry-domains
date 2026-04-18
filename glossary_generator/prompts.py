"""Prompt templates and response schemas used by the agent."""
from __future__ import annotations

SYSTEM_INSTRUCTION = """\
You are a senior data steward building a business glossary for a BigQuery
dataset. You combine:

1. The dataset's schema, Dataplex data-profile statistics (null %, distinct
   %, top values, min/max), and Dataplex data-insights summaries.
2. Industry-standard vocabularies retrieved from a Vertex RAG corpus (FIBO,
   HL7 FHIR, GS1, ACORD, IAB, internal company glossaries, …).
3. Any operator-provided instructions that pin the industry or domain.

Your objectives, in order:
  (a) If possible, identify the most likely INDUSTRY (e.g. Retail, Healthcare
      Payer, Capital Markets) and DOMAIN (e.g. Customer, Claims, Trade
      Lifecycle). Provide either, both, or neither — return "Unknown" for a
      field you cannot confidently infer. Do NOT block term/mapping
      generation on identifying these.
  (b) Propose a concise set of BUSINESS TERMS grounded in retrieved material;
      cite concepts from the RAG corpus when applicable. Always produce
      terms and mappings even when industry or domain is "Unknown".
  (c) Map each term to specific dataset columns with a confidence score.
Be conservative: only propose mappings you can justify from the evidence.
Always return valid JSON matching the requested schema.
"""


DATASET_SUMMARY_TEMPLATE = """\
## Dataset
project: {project_id}
dataset: {dataset_id}
location: {location}
description: {description}

## Operator instructions
{user_instructions}

## Tables
{tables_block}
"""


TABLE_BLOCK_TEMPLATE = """\
### {table_id}  (rows≈{row_count})
description: {description}
{insights}
columns:
{columns}
"""


RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["rationale", "terms", "mappings"],
    "properties": {
        "industry": {
            "type": "string",
            "description": "Inferred industry, or 'Unknown' if not confident.",
        },
        "domain": {
            "type": "string",
            "description": "Inferred business domain, or 'Unknown' if not confident.",
        },
        "rationale": {"type": "string"},
        "terms": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["display_name", "definition"],
                "properties": {
                    "display_name": {"type": "string"},
                    "definition": {"type": "string"},
                    "synonyms": {"type": "array", "items": {"type": "string"}},
                    "related_terms": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "mappings": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "term_display_name",
                    "table_id",
                    "column_name",
                    "confidence",
                    "rationale",
                ],
                "properties": {
                    "term_display_name": {"type": "string"},
                    "table_id": {"type": "string"},
                    "column_name": {"type": "string"},
                    "confidence": {"type": "number"},
                    "rationale": {"type": "string"},
                },
            },
        },
    },
}


USER_PROMPT_TEMPLATE = """\
Use the retrieval tool to look up industry-standard definitions before you
answer. Ground every term you propose in evidence from the dataset AND — when
possible — in retrieved glossary material. For each proposed mapping, cite the
column evidence (name, type, profile stat, top values) that justifies it.

{dataset_summary}

Return a JSON object with keys: industry, domain, rationale, terms, mappings.
"""
