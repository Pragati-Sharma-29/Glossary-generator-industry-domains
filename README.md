# Glossary Generator for BigQuery + Dataplex + Vertex

An agent that reads a BigQuery dataset, enriches it with Dataplex
data-profile / data-insights results, grounds its reasoning in a Vertex AI
RAG corpus of industry vocabularies, and proposes business-glossary terms
plus column mappings. Suggestions can be written back to a Dataplex
business glossary.

## Pipeline

```
BigQuery ─┐
          ├─▶ DatasetContext ─▶ Gemini (Vertex) ─▶ GlossarySuggestion ─▶ Dataplex glossary
Dataplex ─┘          (schema + profile + insights)   │
                                                     └ RAG retrieval (FIBO, HL7, GS1, internal…)
```

Components:

| Module                              | Responsibility                                                    |
|-------------------------------------|-------------------------------------------------------------------|
| `bigquery_client.BigQueryCollector` | List tables, pull schema + small row samples.                     |
| `dataplex_client.DataplexInsightsCollector` | Fold Dataplex `DATA_PROFILE` stats and `DATA_INSIGHTS` summaries onto each table. |
| `vertex_rag.VertexRagClient`        | Gemini call with a Vertex RAG retrieval tool attached.            |
| `glossary_publisher.GlossaryPublisher` | Create glossary terms and attach column mappings in Dataplex.   |
| `agent.GlossaryGeneratorAgent`      | Orchestrates the above and renders the result.                    |

## Inputs

* `dataset_id` — `"project.dataset"` or `"dataset"` (project from env)
* `instructions` *(optional)* — free-form guidance, e.g. `"this is a P&C
  insurance claims mart; prefer ACORD vocabulary."`

## Prerequisites

1. Service account / ADC with roles:
   * `roles/bigquery.dataViewer`, `roles/bigquery.metadataViewer`
   * `roles/dataplex.dataScanViewer`
   * `roles/aiplatform.user`
   * `roles/dataplex.glossaryEditor` (only when publishing)
2. Dataplex `DATA_PROFILE` and/or `DATA_INSIGHTS` scans already run against
   the target tables (the agent reads their latest results).
3. A Vertex AI RAG corpus populated with the glossary material you want the
   agent to ground against (FIBO, HL7, GS1, internal stewardship PDFs, …).

## Install

```bash
pip install -e .
# or
pip install -r requirements.txt
```

## Run

```bash
export GOOGLE_CLOUD_PROJECT=my-proj
export GOOGLE_CLOUD_LOCATION=us-central1
export VERTEX_RAG_CORPUS=projects/my-proj/locations/us-central1/ragCorpora/1234
export DATAPLEX_GLOSSARY_ID=enterprise-glossary       # for --publish

# dry-run: print JSON suggestions only
python -m glossary_generator my_dataset \
    --instructions "retail loyalty marts; grounded in GS1 + NRF ARTS"

# publish to the glossary
python -m glossary_generator my_dataset --publish
```

## Output

```json
{
  "suggestion": {
    "industry": "Retail",
    "domain": "Customer Loyalty",
    "rationale": "...",
    "terms": [
      {"display_name": "Loyalty Member", "definition": "...", "synonyms": ["Rewards Member"]}
    ],
    "mappings": [
      {
        "term_display_name": "Loyalty Member",
        "table_id": "members",
        "column_name": "member_id",
        "confidence": 0.93,
        "rationale": "Primary key; unique per customer; matches GS1 GLN pattern."
      }
    ]
  },
  "publish_report": { "...": "..." }
}
```

## Web app

A small FastAPI UI is included for the interactive flow — submit a dataset,
review each mapping, then publish only the ones you approve.

```bash
export GOOGLE_CLOUD_PROJECT=my-proj
export DATAPLEX_GLOSSARY_ID=enterprise-glossary
# Optional: override the default corpus display name
# export VERTEX_RAG_CORPUS_DISPLAY_NAME=industry-glossaries

uvicorn webapp:app --reload --port 8080
# open http://localhost:8080
```

The web app **always** grounds suggestions in the corpus built by
`scripts/build_rag_corpus.py` (display name `industry-glossaries` by default).
Users cannot supply an alternative corpus from the UI — it is resolved
automatically by display name from the project they enter.

Flow:

1. **Home** – enter project id, dataset id, and optional instructions.
2. **Review** – the agent runs; each suggested term+mapping is displayed
   with an approve checkbox (low-confidence rows are highlighted).
3. **Publish** – approved mappings are written to Dataplex:
   - A `GlossaryTerm` is created under `projects/{p}/locations/{loc}/glossaries/{g}/terms/{slug}`.
   - An `EntryLink` of type `definition` is created in the `@bigquery`
     entry group linking the column to the term.

Session state is held in-process; swap `_SESSIONS` in `webapp/main.py`
for Redis/Firestore to run multi-instance.

## Extending

* **Swap in another vocabulary**: add files to your RAG corpus and re-index.
  No code change needed.
* **Add detectors**: extend `DataplexInsightsCollector` to also call
  `DATA_QUALITY` or Sensitive Data Protection results for PII-aware mappings.
* **Custom aspect schema**: edit `GlossaryPublisher._attach_mapping` to upsert
  whatever aspect type your org uses for term-to-column linkage.

## Branch

All development happens on `claude/glossary-generator-agent-Bkx9w`.
