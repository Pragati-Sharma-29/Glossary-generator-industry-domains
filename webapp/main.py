"""FastAPI web app for the glossary generator.

Flow
────
  GET  /              → input form
  POST /suggest       → runs the agent, shows each mapping with an approve checkbox
  POST /publish       → publishes approved mappings to the Dataplex glossary

The Vertex RAG corpus is **not** user-supplied. The app resolves it on demand
by looking up a corpus by display name (default ``industry-glossaries``, the
name produced by ``scripts/build_rag_corpus.py``). Override the display name
with ``VERTEX_RAG_CORPUS_DISPLAY_NAME`` if you built the corpus under a
different name.

Session state (generated suggestions) is kept in-process keyed by a cookie.
Swap ``_SESSIONS`` for Redis / Firestore to run multi-instance in production.
"""
from __future__ import annotations

import io
import logging
import os
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Optional

from fastapi import Cookie, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from google.cloud import bigquery

from glossary_generator.agent import GlossaryGeneratorAgent
from glossary_generator.config import AgentConfig
from glossary_generator.glossary_publisher import GlossaryPublisher
from glossary_generator.models import ColumnMapping, GlossarySuggestion, TermSuggestion

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent

RAG_CORPUS_PREFIX = os.environ.get("VERTEX_RAG_CORPUS_PREFIX", "industry-glossaries")

# Upload limits for the optional reference PDF attached to an /suggest
# request. The text we extract is folded into the agent's ``instructions``
# blob, which both the industry detector and the main LLM call see. 50k
# characters ≈ 12k Gemini tokens — well under the 1M context window but
# keeps the detection prompt from blowing up.
MAX_PDF_BYTES = 10 * 1024 * 1024
MAX_PDF_EXTRACTED_CHARS = 50_000

DOMAIN_CHOICES = [
    ("retail_ecommerce", "Retail / E-commerce"),
    ("finance_banking", "Finance / Banking"),
    ("healthcare", "Healthcare"),
    ("erp_supply_chain", "ERP / Supply Chain"),
    ("crm_marketing", "CRM / Marketing"),
    ("telco", "Telco"),
    ("automotive", "Automotive"),
]
DOMAIN_LABELS = dict(DOMAIN_CHOICES)

app = FastAPI(title="Glossary Generator")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# ── In-memory session store ─────────────────────────────────────────────────
_SESSIONS: dict[str, dict] = {}


# ── RAG corpus resolver ─────────────────────────────────────────────────────

@lru_cache(maxsize=64)
def _resolve_domain_corpus(project_id: str, location: str, domain: str) -> str:
    """Resolve the RAG corpus for a single industry domain.

    Looks up a corpus with display name ``{RAG_CORPUS_PREFIX}-{domain}``
    (the convention produced by ``scripts/build_rag_corpus.py``). Cached
    per (project, location, domain). Raises ``RuntimeError`` if the
    per-domain corpus isn't found.
    """
    import vertexai
    from vertexai.preview import rag

    display_name = f"{RAG_CORPUS_PREFIX}-{domain}"
    vertexai.init(project=project_id, location=location)
    for corpus in rag.list_corpora():
        if corpus.display_name == display_name:
            logger.info("Resolved RAG corpus '%s' → %s", display_name, corpus.name)
            return corpus.name
    raise RuntimeError(
        f"RAG corpus with display_name='{display_name}' not found in "
        f"{project_id}/{location}. Build it with:\n"
        f"  python scripts/build_rag_corpus.py --project {project_id} "
        f"--location {location} --domains {domain} --gcs-bucket <your-bucket>"
    )


def _extract_pdf_text(upload: Optional[UploadFile]) -> str:
    """Return text extracted from an uploaded PDF, or ``""``.

    Best-effort: failures (encrypted PDF, malformed file, empty pages,
    unsupported type) return an empty string with a logged warning, so
    the request continues without the reference material rather than
    failing outright. Enforces a 10 MB upload cap and truncates the
    extracted text at 50 000 chars to keep the prompt bounded.

    Raises ``ValueError`` for uploads that explicitly exceed the size
    cap or are obviously not PDFs — those bubble up as 400s.
    """
    if upload is None or not upload.filename:
        return ""

    content_type = (upload.content_type or "").lower()
    if content_type and "pdf" not in content_type and content_type != "application/octet-stream":
        raise ValueError(
            f"Reference document must be a PDF; got content-type {content_type!r}."
        )

    contents = upload.file.read(MAX_PDF_BYTES + 1)
    if len(contents) > MAX_PDF_BYTES:
        raise ValueError(
            f"PDF exceeds the {MAX_PDF_BYTES // 1024 // 1024} MB upload limit."
        )
    if not contents:
        return ""

    try:
        from pypdf import PdfReader
    except ImportError as exc:  # defensive: requirement is declared
        logger.error("pypdf not installed: %s", exc)
        return ""

    try:
        reader = PdfReader(io.BytesIO(contents))
        pages_text = [(p.extract_text() or "") for p in reader.pages]
    except Exception as exc:  # noqa: BLE001
        logger.warning("PDF extraction failed for %s: %s", upload.filename, exc)
        return ""

    text = "\n\n".join(t.strip() for t in pages_text if t.strip())
    if not text:
        return ""
    if len(text) > MAX_PDF_EXTRACTED_CHARS:
        text = text[:MAX_PDF_EXTRACTED_CHARS] + "\n\n[... PDF truncated ...]"
    logger.info(
        "Extracted %d chars from %s (%d pages)",
        len(text), upload.filename, len(pages_text),
    )
    return text


def _friendlier_bq_error(exc: Exception, project_id: str) -> str:
    """Translate common BigQuery client errors into a useful short message.

    Anything that doesn't match a known pattern is returned verbatim so
    the raw SDK message still reaches the browser — never swallow the
    underlying cause.
    """
    msg = str(exc)
    cls = type(exc).__name__

    # Caller not authenticated or ADC missing
    if "DefaultCredentialsError" in cls or "Could not automatically determine credentials" in msg:
        return (
            "No Application Default Credentials found. On Cloud Shell, run "
            "`gcloud auth application-default login` or redeploy in an "
            "environment with ADC set up."
        )

    # Malformed service-account JSON (empty / wrong-type ADC file, or a stray
    # GOOGLE_APPLICATION_CREDENTIALS env var pointing to something bogus).
    if (
        "service account info" in msg.lower()
        or "was not in the expected format" in msg
        or "is missing" in msg.lower()
        and "email" in msg.lower()
    ):
        return (
            "ADC loaded a credentials file but it isn't a valid "
            "service-account key (missing required fields). On Cloud Shell, "
            "run:\n"
            "  unset GOOGLE_APPLICATION_CREDENTIALS\n"
            "  gcloud auth application-default login\n"
            "then restart uvicorn. If you intended to use a service account, "
            "check that $GOOGLE_APPLICATION_CREDENTIALS points at a real key "
            "JSON from IAM → Service Accounts → Keys."
        )

    # Project doesn't exist OR caller doesn't have access to it
    if "404" in msg or "NotFound" in cls:
        return (
            f"BigQuery did not find project '{project_id}'. Double-check the "
            "id (not the project *name* or number), and confirm the signed-in "
            "account has access to it."
        )

    # IAM / permission
    if "403" in msg or "Forbidden" in cls or "permission" in msg.lower():
        return (
            f"The signed-in account can list the project '{project_id}' but "
            "lacks `bigquery.datasets.list` permission on it. Grant "
            "roles/bigquery.metadataViewer (or higher) and retry."
        )

    # API not enabled
    if "has not been used" in msg or "is disabled" in msg:
        return (
            f"The BigQuery API is not enabled on project '{project_id}'. "
            "Enable it: `gcloud services enable bigquery.googleapis.com "
            f"--project {project_id}`"
        )

    # Billing
    if "billing" in msg.lower():
        return (
            f"Project '{project_id}' has no active billing account, which "
            "BigQuery requires for metadata listing. Link a billing account "
            "in the Cloud Console and retry."
        )

    return f"{cls}: {msg}"


def _get_or_create_session_id(session_id: Optional[str], response: Response) -> str:
    if session_id and session_id in _SESSIONS:
        return session_id
    new_id = uuid.uuid4().hex
    _SESSIONS[new_id] = {}
    response.set_cookie(
        "glossary_session", new_id, httponly=True, samesite="lax", max_age=3600
    )
    return new_id


# ── Routes ──────────────────────────────────────────────────────────────────

# ── JSON endpoints for progressive form loading ─────────────────────────────

@app.get("/api/datasets")
def api_datasets(project_id: str) -> JSONResponse:
    """List BigQuery datasets visible in a project."""
    project_id = project_id.strip()
    if not project_id:
        return JSONResponse(
            {"error": "Project id is required."}, status_code=400
        )
    try:
        client = bigquery.Client(project=project_id)
        datasets = [
            {
                "dataset_id": ds.dataset_id,
                "full_id": f"{ds.project}.{ds.dataset_id}",
                "location": getattr(ds, "location", None),
            }
            for ds in client.list_datasets(project=project_id)
        ]
    except Exception as exc:  # noqa: BLE001
        logger.exception("list_datasets failed for %s", project_id)
        return JSONResponse(
            {"error": _friendlier_bq_error(exc, project_id)}, status_code=400
        )
    return JSONResponse({"datasets": datasets})


@app.get("/api/tables")
def api_tables(project_id: str, dataset_id: str) -> JSONResponse:
    """List tables in a dataset. ``dataset_id`` may be ``project.dataset``."""
    project_id = project_id.strip()
    dataset_id = dataset_id.strip()
    if not project_id or not dataset_id:
        return JSONResponse(
            {"error": "Project id and dataset id are required."},
            status_code=400,
        )
    try:
        client = bigquery.Client(project=project_id)
        ref = dataset_id if "." in dataset_id else f"{project_id}.{dataset_id}"
        tables = [
            {"table_id": t.table_id, "type": t.table_type}
            for t in client.list_tables(ref)
        ]
    except Exception as exc:  # noqa: BLE001
        logger.exception("list_tables failed for %s / %s", project_id, dataset_id)
        return JSONResponse(
            {"error": _friendlier_bq_error(exc, project_id)},
            status_code=400,
        )
    return JSONResponse({"tables": tables})


# ── HTML routes ─────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "default_project": os.environ.get("GOOGLE_CLOUD_PROJECT", ""),
            "default_glossary": os.environ.get("DATAPLEX_GLOSSARY_ID", ""),
            "default_location": os.environ.get("GOOGLE_CLOUD_LOCATION", "europe-west4"),
            "rag_corpus_prefix": RAG_CORPUS_PREFIX,
            "domain_choices": DOMAIN_CHOICES,
        },
    )


@app.post("/suggest", response_class=HTMLResponse)
async def suggest(
    request: Request,
    response: Response,
    project_id: str = Form(...),
    dataset_id: str = Form(...),
    instructions: str = Form(""),
    location: str = Form("europe-west4"),
    glossary_id: str = Form(""),
    glossary_location: str = Form("global"),
    reference_pdf: Optional[UploadFile] = File(None),
    session_id: Optional[str] = Cookie(None, alias="glossary_session"),
) -> HTMLResponse:
    sid = _get_or_create_session_id(session_id, response)

    # Strip whitespace on every string the form collected — a stray
    # trailing space on project_id hits BigQuery as projects/foo%20/...
    # and comes back as an unhelpful 400 "Invalid resource name".
    project_id = project_id.strip()
    dataset_id = dataset_id.strip()
    location = location.strip() or "europe-west4"
    glossary_id = glossary_id.strip()
    glossary_location = glossary_location.strip() or "global"

    form = await request.form()
    table_allowlist = [v.strip() for v in form.getlist("tables") if v.strip()]

    if not project_id or not dataset_id:
        return templates.TemplateResponse(
            request,
            "error.html",
            {"error": "Project id and dataset id are required."},
            status_code=400,
        )

    try:
        pdf_text = _extract_pdf_text(reference_pdf)
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "error.html",
            {"error": str(exc)},
            status_code=400,
        )
    if pdf_text:
        instructions = (
            f"{instructions}\n\n"
            f"## Reference document: {reference_pdf.filename}\n\n"
            f"{pdf_text}"
        ).strip()

    # A corpus resolver closure is passed to the agent — when the agent's
    # detector picks a domain, this callable returns the matching per-domain
    # corpus resource name (or None if there isn't one). Detection failures
    # propagate here as a skipped corpus, not an error response, so the
    # agent can still produce schema-only suggestions.
    def corpus_resolver(detected_domain: str) -> Optional[str]:
        if detected_domain not in DOMAIN_LABELS:
            return None
        try:
            return _resolve_domain_corpus(project_id, location, detected_domain)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "No corpus for detected domain %s: %s", detected_domain, exc
            )
            return None

    config = AgentConfig.from_env(
        project_id=project_id,
        location=location,
        vertex_rag_corpus=None,  # resolved at runtime via corpus_resolver
        glossary_id=glossary_id or None,
        glossary_location=glossary_location,
    )

    try:
        agent = GlossaryGeneratorAgent(config, corpus_resolver=corpus_resolver)
        result = agent.run(
            dataset_id,
            instructions=instructions,
            table_allowlist=table_allowlist or None,
            publish=False,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Agent failed")
        return templates.TemplateResponse(
            request,
            "error.html",
            {"error": f"{type(exc).__name__}: {exc}"},
            status_code=500,
        )

    detected = result.get("detected_industry") or {}
    if detected.get("domain") in DOMAIN_LABELS:
        detected["domain_label"] = DOMAIN_LABELS[detected["domain"]]

    _SESSIONS[sid] = {
        "config": {
            "project_id": project_id,
            "location": location,
            "glossary_id": glossary_id,
            "glossary_location": glossary_location,
            # BigQuery dataset region — used later as bq_region on the
            # publisher so @bigquery entry-group URLs resolve against
            # the dataset's own location, not the Vertex location.
            "dataset_location": (result.get("dataset_location") or "us").lower(),
        },
        "dataset_id": dataset_id,
        "instructions": instructions,
        "suggestion": result["suggestion"],
        "detected_industry": detected,
    }

    html = templates.TemplateResponse(
        request,
        "suggestions.html",
        {
            "dataset_id": dataset_id,
            "instructions": instructions,
            "glossary_id": glossary_id,
            "suggestion": result["suggestion"],
            "detected_industry": detected,
            "tables_without_scans": result.get("tables_without_scans", []),
            "graph_data": _graph_data_from_suggestion(result["suggestion"]),
        },
    )
    # Preserve cookie set by _get_or_create_session_id
    for k, v in response.headers.items():
        if k.lower() == "set-cookie":
            html.headers.append(k, v)
    return html


@app.post("/publish", response_class=HTMLResponse)
async def publish(
    request: Request,
    session_id: Optional[str] = Cookie(None, alias="glossary_session"),
) -> HTMLResponse:
    if not session_id or session_id not in _SESSIONS:
        return RedirectResponse("/", status_code=303)

    form = await request.form()
    approved_ids = set(form.getlist("approved_mapping"))
    promoted_synonyms = form.getlist("promote_synonym")
    promoted_related = form.getlist("promote_related")

    session = _SESSIONS[session_id]
    suggestion_dict = session["suggestion"]
    cfg = session["config"]

    if not cfg.get("glossary_id"):
        raise HTTPException(400, "No glossary_id was supplied; cannot publish.")

    # Filter the suggestion down to approved mappings and the terms they reference.
    all_mappings = suggestion_dict["mappings"]
    approved = [
        _mapping_from_dict(m)
        for i, m in enumerate(all_mappings)
        if str(i) in approved_ids
    ]
    needed_term_names = {m.term_display_name for m in approved}
    approved_terms = [
        _term_from_dict(t)
        for t in suggestion_dict["terms"]
        if t["display_name"] in needed_term_names
    ]

    # Promoted synonyms / related terms become their own standalone
    # GlossaryTerms plus structured term-to-term entry links of type
    # "synonym" or "related". Dedupe against names we're already
    # publishing so the API doesn't 409-loop if the user ticks the same
    # name twice or ticks something that's already a top-level term.
    existing_names = {t.display_name.lower() for t in approved_terms}
    term_links: list[dict] = []
    for term, links in _build_promoted_terms(
        promoted_synonyms, kind="synonym", existing=existing_names
    ):
        approved_terms.append(term)
        term_links.extend(links)
    for term, links in _build_promoted_terms(
        promoted_related, kind="related", existing=existing_names
    ):
        approved_terms.append(term)
        term_links.extend(links)

    filtered = GlossarySuggestion(
        industry=suggestion_dict.get("industry", ""),
        domain=suggestion_dict.get("domain", ""),
        rationale=suggestion_dict.get("rationale", ""),
        terms=approved_terms,
        mappings=approved,
    )

    dataset_id = session["dataset_id"]
    # `dataset_id` may be "project.dataset" – use the bare name for Dataplex.
    bare_dataset = dataset_id.split(".", 1)[-1]

    publisher = GlossaryPublisher(
        project_id=cfg["project_id"],
        glossary_id=cfg["glossary_id"],
        location=cfg.get("glossary_location", "global"),
        # bq_region = the BigQuery dataset's own region (picked up by the
        # agent via dataset.location). This is where @bigquery entries
        # for that dataset's tables live; using the Vertex region instead
        # was the cause of 400 "invalid entry reference" on publish.
        bq_region=cfg.get("dataset_location") or "us",
        dry_run=False,
    )
    report = publisher.publish(
        filtered, dataset_id=bare_dataset, term_links=term_links
    )

    return templates.TemplateResponse(
        request,
        "result.html",
        {
            "report": report,
            "approved_count": len(approved),
            "total_count": len(all_mappings),
            "glossary_id": cfg["glossary_id"],
            "project_id": cfg["project_id"],
            "graph_data": _graph_data_from_report(report),
        },
    )


# ── helpers ─────────────────────────────────────────────────────────────────


def _graph_data_from_suggestion(suggestion) -> dict:
    """Build a vis-network ``{nodes, edges}`` payload from a suggestion.

    ``suggestion`` is the dict produced by ``GlossarySuggestion.to_dict()``.

    Initial view: **terms ↔ tables**, plus term↔term synonym/related links.
    Column mappings are aggregated into a ``definition`` edge per
    (table, term) pair carrying a ``count`` label; the full column
    list is attached to the table node as ``columns`` and the
    frontend expands it on click.

    Edge ``group`` values drive colour:
      - ``definition``   table → term (aggregated from column mappings)
      - ``contains``     table → column (only added client-side on expand)
      - ``synonym``      term ↔ term
      - ``related``      term ↔ term
    """
    nodes: list[dict] = []
    edges: list[dict] = []
    seen: set[str] = set()

    def add_node(node_id: str, label: str, group: str, **extra) -> None:
        if node_id in seen:
            return
        seen.add(node_id)
        node = {"id": node_id, "label": label, "group": group}
        node.update(extra)
        nodes.append(node)

    terms = (suggestion or {}).get("terms") or []
    mappings = (suggestion or {}).get("mappings") or []

    term_ids: dict[str, str] = {}
    for i, term in enumerate(terms):
        display_name = (term.get("display_name") or "").strip()
        if not display_name:
            continue
        node_id = f"term:{i}"
        term_ids[display_name.lower()] = node_id
        definition = (term.get("definition") or "").strip()
        add_node(
            node_id, display_name, "term",
            title=definition[:240],
            description=definition,
        )

    # Group mappings by table and by (table, term) for aggregation.
    table_columns: dict[str, list[dict]] = {}
    agg_counts: dict[tuple[str, str], int] = {}
    for m in mappings:
        table = (m.get("table_id") or "").strip()
        column = (m.get("column_name") or "").strip()
        term_name = (m.get("term_display_name") or "").strip()
        if not (table and column and term_name):
            continue
        table_id = f"table:{table}"
        col_id = f"col:{table}.{column}"
        tid = term_ids.get(term_name.lower())
        if not tid:
            tid = f"term:{term_name}"
            term_ids[term_name.lower()] = tid
            add_node(tid, term_name, "term")
        table_columns.setdefault(table_id, []).append(
            {"id": col_id, "name": column, "term_id": tid, "term_label": term_name},
        )
        agg_counts[(table_id, tid)] = agg_counts.get((table_id, tid), 0) + 1

    for table_id, cols in table_columns.items():
        label = table_id.removeprefix("table:")
        add_node(table_id, label, "table", columns=cols)

    for (table_id, term_id), count in agg_counts.items():
        edges.append({
            "id": f"agg:{table_id}->{term_id}",
            "from": table_id, "to": term_id,
            "group": "definition", "count": count,
            "label": str(count),
        })

    for term in terms:
        display_name = (term.get("display_name") or "").strip()
        src_id = term_ids.get(display_name.lower())
        if not src_id:
            continue
        for kind, items in (("synonym", term.get("synonyms") or []),
                            ("related", term.get("related_terms") or [])):
            for ref in items:
                name = ref.get("name") if isinstance(ref, dict) else str(ref)
                name = (name or "").strip()
                if not name:
                    continue
                dst_id = term_ids.get(name.lower())
                if not dst_id:
                    dst_id = f"ref:{name.lower()}"
                    term_ids[name.lower()] = dst_id
                    add_node(dst_id, name, "term-ref")
                edges.append({"from": src_id, "to": dst_id, "group": kind})

    return {"nodes": nodes, "edges": edges}


def _graph_data_from_report(report: dict) -> dict:
    """Build the same graph shape from a publish report.

    Initial view: term + table nodes, with table→term definition edges
    aggregated per (table, term) pair and labelled with the count. The
    per-column detail — including each column's publish status — is
    attached to the table node and revealed when the user clicks a
    table in the UI.

    Term↔term entry links from ``report.term_links`` emit synonym /
    related / error edges between term nodes.
    """
    nodes: list[dict] = []
    edges: list[dict] = []
    seen: set[str] = set()

    def add_node(node_id: str, label: str, group: str, **extra) -> None:
        if node_id in seen:
            return
        seen.add(node_id)
        node = {"id": node_id, "label": label, "group": group}
        node.update(extra)
        nodes.append(node)

    table_columns: dict[str, list[dict]] = {}
    agg_counts: dict[tuple[str, str, bool], int] = {}  # (table, term, any_error)

    for m in report.get("mappings") or []:
        tname = (m.get("term") or "").strip()
        table = (m.get("table") or "").strip()
        col = (m.get("column") or "").strip()
        if not (tname and table and col):
            continue
        tid = f"term:{tname.lower()}"
        table_id = f"table:{table}"
        col_id = f"col:{table}.{col}"
        add_node(tid, tname, "term")
        status = str(m.get("status") or "")
        is_error = status.startswith("error") or status.startswith("HTTP")
        table_columns.setdefault(table_id, []).append({
            "id": col_id, "name": col, "term_id": tid, "term_label": tname,
            "status": status, "is_error": is_error,
        })
        # Aggregate edge carries the *worst* status: any failed column
        # under this (table, term) flips the whole edge to error colour.
        key = (table_id, tid)
        prev = agg_counts.get(key, (0, False))
        agg_counts[key] = (prev[0] + 1, prev[1] or is_error)

    for table_id, cols in table_columns.items():
        label = table_id.removeprefix("table:")
        add_node(table_id, label, "table", columns=cols)

    for (table_id, term_id), (count, any_error) in agg_counts.items():
        edges.append({
            "id": f"agg:{table_id}->{term_id}",
            "from": table_id, "to": term_id,
            "group": "error" if any_error else "definition",
            "count": count, "label": str(count),
        })

    for link in report.get("term_links") or []:
        parent = (link.get("parent") or "").strip()
        child = (link.get("child") or "").strip()
        kind = link.get("kind") or "related"
        if not (parent and child):
            continue
        pid = f"term:{parent.lower()}"
        cid = f"term:{child.lower()}"
        add_node(pid, parent, "term")
        add_node(cid, child, "term")
        status = str(link.get("status") or "")
        is_error = status.startswith("error") or status.startswith("HTTP")
        edges.append({
            "from": pid, "to": cid,
            "group": "error" if is_error else kind,
            "title": status or "created",
        })

    return {"nodes": nodes, "edges": edges}


def _mapping_from_dict(d: dict) -> ColumnMapping:
    return ColumnMapping(
        term_display_name=d["term_display_name"],
        table_id=d["table_id"],
        column_name=d["column_name"],
        confidence=float(d.get("confidence", 0.0)),
        rationale=d.get("rationale", ""),
    )


def _term_from_dict(d: dict) -> TermSuggestion:
    return TermSuggestion(
        display_name=d["display_name"],
        definition=d["definition"],
        synonyms=d.get("synonyms", []),
        related_terms=d.get("related_terms", []),
    )


def _build_promoted_terms(
    values: list[str],
    *,
    kind: str,
    existing: set[str],
):
    """Yield ``(TermSuggestion, [link_request, …])`` for promoted values.

    Form values are formatted as
    ``"<derived_name>|<parent_display_name>|<optional_description>"``
    (see suggestions.html). Each unique derived name is emitted once —
    even if ticked under multiple parents, we still only create one
    term. The first non-empty description seen for that name is used as
    the promoted term's definition; the parent linkage is encoded in
    the description as well and materialised as entry links so Dataplex
    carries structured relationships.

    ``kind`` is ``"synonym"`` or ``"related"``; that value is passed
    through to the publisher unchanged and maps 1:1 to the Dataplex
    system entry-link types ``/synonym`` and ``/related``.
    """
    seen: dict[str, dict] = {}  # name -> {parents: [...], description: "..."}
    for raw in values:
        parts = raw.split("|", 2)
        if len(parts) < 2:
            continue
        name = parts[0].strip()
        parent = parts[1].strip()
        description = parts[2].strip() if len(parts) == 3 else ""
        if not name or name.lower() in existing:
            continue
        slot = seen.setdefault(name, {"parents": [], "description": ""})
        slot["parents"].append(parent)
        if description and not slot["description"]:
            slot["description"] = description

    prefix = "Synonym of" if kind == "synonym" else "Related to"
    # Dataplex system entry-link types are named 'synonym' and 'related'
    # (singular) — pass ``kind`` straight through as the link_type.
    link_type = kind if kind in ("synonym", "related") else "related"
    for name, slot in seen.items():
        dedup_parents = list(dict.fromkeys(slot["parents"]))
        parent_ref = ", ".join(dedup_parents)
        relationship_line = f"{prefix} {parent_ref}."
        if slot["description"]:
            definition = f"{slot['description']}\n\n{relationship_line}"
        else:
            definition = relationship_line
        term = TermSuggestion(
            display_name=name,
            definition=definition,
            synonyms=[],
            related_terms=[{"name": p, "description": ""} for p in dedup_parents],
        )
        links = [
            {"parent": parent, "child": name, "kind": link_type}
            for parent in dedup_parents
        ]
        yield term, links
        existing.add(name.lower())
