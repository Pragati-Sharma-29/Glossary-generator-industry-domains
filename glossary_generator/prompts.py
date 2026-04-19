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
  (d) For each term, populate ``related_terms`` with 2–5 entries that
      include BOTH adjacent domain entities AND 1–3 standard industry
      METRICS / KPIs commonly derived from it (e.g. for a retail Order
      term: "Average Order Value", "Gross Merchandise Value"; for a
      healthcare Encounter term: "Length of Stay", "30-day Readmission
      Rate"). Use the exact metric names that appear in the retrieved
      RAG material when available.
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
    "type": "OBJECT",
    "required": ["rationale", "terms", "mappings"],
    "properties": {
        "industry": {
            "type": "STRING",
            "description": "Inferred industry, or 'Unknown' if not confident.",
        },
        "domain": {
            "type": "STRING",
            "description": "Inferred business domain, or 'Unknown' if not confident.",
        },
        "rationale": {"type": "STRING"},
        "terms": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "required": ["display_name", "definition"],
                "properties": {
                    "display_name": {"type": "STRING"},
                    "definition": {"type": "STRING"},
                    "synonyms": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "related_terms": {"type": "ARRAY", "items": {"type": "STRING"}},
                },
            },
        },
        "mappings": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "required": [
                    "term_display_name",
                    "table_id",
                    "column_name",
                    "confidence",
                    "rationale",
                ],
                "properties": {
                    "term_display_name": {"type": "STRING"},
                    "table_id": {"type": "STRING"},
                    "column_name": {"type": "STRING"},
                    "confidence": {"type": "NUMBER"},
                    "rationale": {"type": "STRING"},
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

Return at most {max_mappings_per_table} mappings per table. When a table has
more candidate columns than that, keep the highest-confidence, most business-
meaningful ones (keys, domain-specific codes, monetary amounts, timestamps
with business meaning) and drop generic operational columns.

{dataset_summary}

Return ONLY a JSON object (no prose, no code fences) with this exact shape:

{{
  "industry": "<string, or 'Unknown'>",
  "domain": "<string, or 'Unknown'>",
  "rationale": "<string>",
  "terms": [
    {{
      "display_name": "<string>",
      "definition": "<string>",
      "synonyms": ["<string>", ...],
      "related_terms": ["<string>", ...]
    }}
  ],
  "mappings": [
    {{
      "term_display_name": "<string, matches a term.display_name>",
      "table_id": "<string>",
      "column_name": "<string>",
      "confidence": 0.0,
      "rationale": "<string>"
    }}
  ]
}}
"""
