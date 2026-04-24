# Glossary Generator using industry and domain context

An agent that reads a BigQuery dataset, enriches it with Dataplex
data-profile / data-insights results, **auto-detects the industry**,
grounds reasoning in the matching per-domain Vertex AI RAG corpus, and
proposes business-glossary terms (with synonyms, related terms, and
metrics) plus column mappings. Approved suggestions are written back to
a Dataplex business glossary.

## Getting started (first time, new project)

For someone with a fresh GCP project and a BigQuery dataset they want
to generate a glossary for. Cloud Shell is the fastest route — no
local install, no SDK setup. ~20 minutes end-to-end the first time;
under a minute on subsequent runs.

### Prerequisites

* A GCP project with **billing enabled**.
* A BigQuery dataset loaded into that project (or plan to query one of
  the `bigquery-public-data.*` datasets for a smoke test).
* Your Google account signed in to that project with at least these
  roles — ask your admin if you don't have them:
  * `roles/bigquery.metadataViewer`
  * `roles/dataplex.dataScanViewer`
  * `roles/aiplatform.user`
  * `roles/dataplex.glossaryEditor` *(only needed when you publish)*
  * `roles/storage.admin` *(one-time, so the build script can create
    a GCS bucket for RAG source files)*

### Step 1 — Open Cloud Shell

In the GCP Console, click the Cloud Shell icon (terminal icon, top
right). A bash shell opens in your browser. All the commands below
run there.

Make sure your project is selected:

```bash
gcloud config set project MY_PROJECT_ID
```

### Step 2 — Clone the repo

```bash
git clone https://github.com/Pragati-Sharma-29/Glossary-generator-industry-domains.git
cd Glossary-generator-industry-domains
git checkout claude/glossary-generator-agent-Bkx9w
```

### Step 3 — Sign in with Application Default Credentials

```bash
unset GOOGLE_APPLICATION_CREDENTIALS
gcloud auth application-default login
# follow the browser prompt
```

This lets the agent call BigQuery, Dataplex, and Vertex AI as you.

### Step 4 — Run the bootstrap script (one command)

```bash
./scripts/bootstrap.sh --project MY_PROJECT_ID --location europe-west4
```

This is idempotent — it checks what already exists and only does work
that's missing. On a brand-new project it will:

1. Enable the BigQuery, Dataplex, Vertex AI, and Storage APIs.
2. `pip install -r requirements.txt`.
3. Create a GCS bucket `MY_PROJECT_ID-rag-sources` for RAG source files.
4. Build all **seven per-domain RAG corpora** (`industry-glossaries-<domain>`)
   from the curated `seed_docs/*.md` files. Takes ~10–15 min on the
   first run; later runs skip this entirely.
5. Create the `enterprise-glossary` Dataplex glossary.
6. Launch `uvicorn webapp:app` on port 8080.

### Step 5 — Open the web app

In the Cloud Shell toolbar (top right of the terminal panel) click the
screen icon → **Preview on port 8080**. A tunneled `https://8080-cs-…cloudshell.dev`
URL opens with the app.

### Restarting with the latest code

When you pull new changes (or come back to a disconnected Cloud Shell
session), the app needs a quick restart to pick them up. From inside
the repo:

```bash
cd ~/Glossary-generator-industry-domains
git pull origin claude/glossary-generator-agent-Bkx9w
fuser -k 8080/tcp 2>/dev/null     # free the port if uvicorn is still bound
unset GOOGLE_APPLICATION_CREDENTIALS  # Cloud Shell re-sets this per session
uvicorn webapp:app --host 0.0.0.0 --port 8080
```

Which bits require the full dance:
* **Python changes** (`glossary_generator/**`, `webapp/main.py`) — must
  restart uvicorn to reload the module (`fuser -k` + relaunch above).
* **Template / CSS / JS changes** (`webapp/templates/**`,
  `webapp/static/**`) — `git pull` is enough; hard-refresh the
  browser tab (Cmd/Ctrl+Shift+R) so it drops the cached assets.
* **RAG seed-doc changes** (`seed_docs/*.md`) — re-run
  `python scripts/build_rag_corpus.py --domains <domain>` to re-index
  before restarting the app.

### Step 6 — Generate your first glossary

1. **Project id** — type your project id → click **Load datasets**.
2. **BigQuery dataset** — pick the dataset from the dropdown.
3. **Tables to include** — leave all checked, or narrow to a few.
4. **Instructions** *(optional)* — e.g. `"retail loyalty marts"`.
5. **Reference PDF** *(optional)* — upload an internal glossary or spec
   up to 10 MB if you have one.
6. Click **Generate suggestions**. A loader overlay appears for 20–60 s.
7. On the **Review page**:
   * Confirm the detected industry card (expected domain should appear
     with a confidence score and short reasoning).
   * Expand each term to see proposed synonyms and related terms
     (including metrics/KPIs) — tick any you want to promote into
     standalone glossary terms.
   * In the Column mappings table, tick the ones you want to publish
     (defaults to all approved). Low-confidence rows are highlighted.
8. Scroll to the bottom and click **Publish approved mappings**.

### Step 7 — Verify in the Dataplex Catalog UI

In the GCP Console, navigate to **Dataplex → Business glossaries**,
open `enterprise-glossary`. You should see:
* The approved terms, each with a definition (plus *"Also known as"* and
  *"Related"* lines if synonyms/related were carried over).
* Clicking a term shows the BigQuery columns linked to it via
  `definition` entry links.
* Promoted synonyms/related appear as their own terms in the same
  glossary, linked back to the parent via `synonym` / `related`
  entry links.

### Tips for better results

* **Run a Dataplex DATA_PROFILE scan** on your tables before generating.
  The agent uses the resulting statistics (null %, distinct %, top
  values) as evidence — mapping confidence climbs noticeably with a
  scan in place.
* **Mention the industry in Instructions** if auto-detection misfires
  on an unusual schema.
* **Use the PDF upload** for company-specific vocabulary that isn't in
  the seed docs (e.g. a proprietary CDM, a regulator's glossary) — its
  text is folded into the prompt so definitions echo your terminology.

### If something doesn't work

| Symptom | Fix |
|---|---|
| "service account info is missing in the 'email' field" on **Load datasets** | `unset GOOGLE_APPLICATION_CREDENTIALS && gcloud auth application-default login`, then restart uvicorn. |
| Detected industry card says "no per-domain corpus available" | One of the seven corpora failed to build. Re-run `./scripts/bootstrap.sh …`; it will build only the missing ones. |
| Cloud Shell disconnects and the app dies | Re-run the bootstrap, or wrap the uvicorn launch in `tmux new -s app` so it survives disconnects. |
| Publish shows "HTTP 403 permission denied" | You're missing `roles/dataplex.glossaryEditor` on the project. Ask your admin. |

The deeper sections below cover the architecture, extension points,
and alternative deployment shapes (shared hub project, centrally
hosted service) once you're past the first run.

## Pipeline

```
BigQuery ─┐
          │
Dataplex ─┼─▶ DatasetContext ─▶ industry_detector ─▶ per-domain corpus ─▶ Gemini (RAG-grounded)
          │                     (no-RAG Gemini pass)                               │
Operator ─┘                                                                        ▼
  (optional instructions                                       GlossarySuggestion (terms + mappings)
   + PDF reference doc)                                                            │
                                                                                   ▼
                                                                     Dataplex glossary
                                                                     (REST API: terms +
                                                                      column↔term +
                                                                      term↔term links)
```

## Components

| Module                                          | Responsibility                                                                                             |
|-------------------------------------------------|------------------------------------------------------------------------------------------------------------|
| `bigquery_client.BigQueryCollector`             | List tables, pull schema (no row samples).                                                                 |
| `dataplex_client.DataplexInsightsCollector`     | Fold Dataplex `DATA_PROFILE` stats and `DATA_INSIGHTS` summaries onto tables that have a scan. Fail-soft.  |
| `industry_detector.detect_domain`               | One short Gemini call, no RAG, classifies the dataset into one of seven industries (or `unknown`).         |
| `vertex_rag.VertexRagClient`                    | Gemini call with a Vertex RAG retrieval tool bound to the detected domain's corpus.                        |
| `glossary_publisher.GlossaryPublisher`          | Create glossary terms and entry links (column↔term + term↔term) via the Dataplex **REST** API.             |
| `agent.GlossaryGeneratorAgent`                  | Orchestrates collection → detection → corpus resolution → generation → publish.                            |

## Seven supported industries

Each has its own RAG corpus with display name `industry-glossaries-<domain>`:

| Key                | Covers                                                                                |
|--------------------|----------------------------------------------------------------------------------------|
| `retail_ecommerce` | Cloud Retail API, GS1 (GTIN/GLN/SSCC), schema.org commerce, commercetools, TheLook     |
| `finance_banking`  | FIBO concepts, FINOS CDM, ISO identifiers (LEI/IBAN/ISIN/CUSIP), ACORD insurance       |
| `healthcare`       | FHIR R4, OMOP CDM, IDMP (MPID/PhPID/substance), ICD-10 / CPT / LOINC / SNOMED          |
| `erp_supply_chain` | SAP / Oracle EBS master + transactional, GS1 EPCIS events                              |
| `crm_marketing`    | Salesforce / HubSpot objects, GA4, UTM + attribution                                   |
| `telco`            | TM Forum SID, 3GPP (MSISDN / IMSI / Cell / Bearer / PDU Session), FCAPS OSS vocabulary |
| `automotive`       | schema.org Vehicle subtree, VIN (ISO 3779), EDM Council AUTO, NHTSA FARS, OBD-II DTCs  |

Every domain also carries a **Metrics & KPIs** section (~15 per domain — e.g.
retail GMV/AOV/CVR, finance NIM/ROA/NPL, healthcare LOS/30-day Readmit,
ERP DIO/Perfect Order, CRM CAC/NRR, telco ARPU/Churn, automotive
Gross-per-Vehicle/CSI) so the agent can surface metrics under each term.

## Inputs

* `project_id` — GCP project hosting BigQuery, Dataplex, and RAG corpora
* `dataset_id` — `"project.dataset"` or `"dataset"`
* `instructions` *(optional)* — free-form guidance, e.g. "P&C insurance
  claims mart; prefer ACORD vocabulary." Use this to nudge industry
  detection or vocabulary preference.
* `reference_pdf` *(optional, web only)* — attach an internal glossary,
  style guide, or spec PDF. Text is extracted (up to 50 000 chars) and
  folded into the instructions so both detection and generation see it.

The agent **auto-detects the industry** from table/column names — you
never need to pick it manually. The detector returns a confidence score
and reasoning, both shown in the UI.

## Prerequisites

1. ADC or service account with:
   * `roles/bigquery.dataViewer`, `roles/bigquery.metadataViewer`
   * `roles/dataplex.dataScanViewer`
   * `roles/aiplatform.user`
   * `roles/dataplex.glossaryEditor` (publish only)
2. Dataplex `DATA_PROFILE` (and optionally `DATA_INSIGHTS`) scans on the
   target tables — strongly recommended for higher-confidence mappings.
   Tables without a scan are processed schema-only; their names surface
   in a warning banner on the Review page.
3. **Seven per-domain Vertex AI RAG corpora** with display names
   `industry-glossaries-<domain>` — built by
   `scripts/build_rag_corpus.py` from the curated `seed_docs/*.md` files.

## Install

```bash
pip install -r requirements.txt
# or
pip install -e .
```

Key dep: `pypdf` for reference-PDF extraction in the web app.

## Quick start (one command)

```bash
./scripts/bootstrap.sh --project my-gcp-project
```

Enables required APIs, does `gcloud auth application-default login` if
needed, installs deps, checks for the seven per-domain corpora and
builds any that are missing (~1–3 min each from seed_docs only),
creates the `enterprise-glossary` Dataplex glossary if absent, then
launches `uvicorn webapp:app` on port 8080.

Every step is idempotent — re-runs are safe. Useful flags:

```
--location REGION        Vertex / Dataplex region (default: europe-west4)
--glossary ID            Target Dataplex glossary id (default: enterprise-glossary)
--corpus-name PREFIX     Display-name prefix; per-domain corpora become <prefix>-<domain>
--bucket NAME            GCS bucket for RAG sources
--skip-apis / --skip-auth / --skip-deps / --skip-corpus / --skip-glossary / --skip-serve
--port N                 Web app port (default: 8080)
```

## Manual launch

```bash
export GOOGLE_CLOUD_PROJECT=my-proj
export GOOGLE_CLOUD_LOCATION=europe-west4          # default; Vertex RAG region
export DATAPLEX_GLOSSARY_ID=enterprise-glossary
export VERTEX_RAG_CORPUS_PREFIX=industry-glossaries # optional; match the build

uvicorn webapp:app --host 0.0.0.0 --port 8080
```

Dataplex scan location (`DATAPLEX_LOCATION`) stays independent — set
it to the dataset's BigQuery region (e.g. `us-central1` for US-hosted
data) even if the Vertex corpus lives elsewhere.

## Building the RAG corpora

```bash
python scripts/build_rag_corpus.py \
    --project my-proj \
    --location europe-west4 \
    --gcs-bucket my-proj-rag-sources
```

Creates (or appends to) all seven corpora. Flags:

```
--domains retail_ecommerce finance_banking …  # limit to specific industries
--corpus-display-name PREFIX                  # default: industry-glossaries
--gcs-prefix PATH                             # default: rag-sources
--dry-run                                     # list sources, don't fetch/upload
--skip-upload                                 # fetch + process but don't touch GCS/Vertex
-vv                                           # verbose logging
```

### Grounding primary source: `seed_docs/*.md`

Each seed doc is hand-curated markdown with `## Term` headers — one
chunk per term in the RAG corpus. Each term entry carries:

* a definition paragraph
* **Synonyms** (alternative names the same concept is called across
  systems) — feeds retrieval and the model's output synonyms
* **Typical columns** (column-name hints) — lets retrieval match a
  column like `msisdn` or `icd_code` to the right concept
* **Related terms** — adjacent entities and standard metrics/KPIs

Because the content is in-repo and static, every corpus build produces
identical, deterministic grounding — no reliance on live external URLs.

### Optional GitHub augmentation

Set `GITHUB_TOKEN` (PAT with `public_repo` scope) before running
`build_rag_corpus.py` to also pull content from live repos (FIBO, FHIR,
commercetools, cortex-data-foundation, edmcouncil/auto, …). Without a
token the build uses seed_docs only and still produces a usable corpus
— that's the primary path.

## Web app flow

1. **Home** — enter GCP project id → click **Load datasets** → pick a
   dataset → optionally narrow to specific tables → optionally type
   instructions or attach a reference PDF → click **Generate
   suggestions**. A loader overlay stays up while the agent runs
   (typically 20–60 s).
2. **Review** — shows:
   - **Detected industry** card with confidence + reasoning; warning
     if no corpus was resolved for the detected domain.
   - **Proposed terms** — each with its definition. Expand to see the
     term's synonyms and related terms (including metrics); each has
     a 1-line description explaining what it is and how it maps.
     Tick any to promote them into standalone glossary terms on
     publish.
   - **Column mappings** table — approve/decline each; low-confidence
     rows highlighted; bulk Approve-all / Decline-all.
3. **Publish** — writes to the Dataplex glossary using the REST API:
   - `POST /glossaries/{g}/terms` — one per approved + promoted term
   - `POST /entryGroups/@bigquery/entryLinks` — one `definition` link
     per approved column↔term mapping
   - `POST /entryGroups/@dataplex/entryLinks` — one
     `synonym` or `related` link per promoted-term relationship,
     wiring the new term to its parent structurally

The result page lists all three sections with per-row status (created /
exists / error). Session state is held in-process; swap `_SESSIONS` in
`webapp/main.py` for Redis/Firestore to run multi-instance.

## Output (JSON mode)

```json
{
  "suggestion": {
    "industry": "Retail",
    "domain": "Customer Loyalty",
    "rationale": "…",
    "terms": [
      {
        "display_name": "Loyalty Member",
        "definition": "A Customer enrolled in the retailer's rewards program…",
        "synonyms": [
          {"name": "Rewards Member", "description": "Alternative name used on the member-facing portal."}
        ],
        "related_terms": [
          {"name": "Redemption Rate", "description": "Share of earned loyalty points that members redeem; derived from member_id × points_earned × points_redeemed."}
        ]
      }
    ],
    "mappings": [
      {
        "term_display_name": "Loyalty Member",
        "table_id": "members",
        "column_name": "member_id",
        "confidence": 0.93,
        "rationale": "Primary key; matches GS1 GLN pattern; referenced by orders.member_id."
      }
    ]
  },
  "detected_industry": {
    "domain": "retail_ecommerce",
    "confidence": 0.91,
    "reasoning": "Tables members, orders, events with columns like loyalty_tier, order_id, event_type=cart are characteristic of retail loyalty.",
    "corpus_used": "projects/…/ragCorpora/…"
  },
  "tables_without_scans": [],
  "publish_report": {
    "created_terms": [ … ],
    "mappings":      [ … ],
    "term_links":    [ … ]
  }
}
```

## Publishing behaviour

* **Terms** are created (or skipped as "exists") under the configured
  glossary. A promoted synonym/related term goes into the **same
  glossary** as the canonical one. Before creating, the publisher
  lists the glossary's existing terms and matches by display name —
  an already-present term (including one created manually under a
  different id) is reused, and new column↔term / term↔term links
  point at its existing id instead of minting a duplicate term.
* **Synonyms and related terms** of any created term are also folded
  into that term's description (as `**Also known as:** …` and
  `**Related:** …`) so they're visible in the Dataplex UI even when
  not promoted.
* **Column↔term links** are `definition`-type EntryLinks in the
  system-managed `@bigquery` entry group.
* **Term↔term links** (when the operator promotes synonyms/related)
  are `synonym`- or `related`-type EntryLinks in the system-managed
  `@dataplex` entry group, keeping the relationship structurally
  queryable.

## Default region: `europe-west4`

Vertex AI RAG Engine's Spanner-mode corpora are allowlisted in
`europe-west4` without extra opt-in, whereas `us-central1` (and
certain other US regions) require forcing Serverless (KNN) mode for
new projects. The default of `europe-west4` avoids that friction.

BigQuery datasets in any region are still queryable — metadata reads
don't depend on Vertex's region. Dataplex scans live alongside the
data (US datasets → US scans), so `DATAPLEX_LOCATION` is decoupled
from `GOOGLE_CLOUD_LOCATION`.

## Extending

* **New vocabulary**: add or extend a `seed_docs/<domain>.md` —
  `## <Term>` sections become one indexed chunk each. Re-run
  `build_rag_corpus.py --domains <domain>` to index.
* **New detectors**: extend `DataplexInsightsCollector` to pull
  `DATA_QUALITY` or Sensitive Data Protection signals for PII-aware
  mappings.
* **Custom aspect schema**: edit `GlossaryPublisher._create_entry_link`
  to emit whatever aspect type your org uses for column↔term linkage.

## Branch

All development happens on `claude/glossary-generator-agent-Bkx9w`.
