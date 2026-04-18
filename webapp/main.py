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

import logging
import os
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Optional

from fastapi import Cookie, FastAPI, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from google.cloud import bigquery

from glossary_generator.agent import GlossaryGeneratorAgent
from glossary_generator.config import AgentConfig
from glossary_generator.dataplex_client import MissingDataplexScansError
from glossary_generator.glossary_publisher import GlossaryPublisher
from glossary_generator.models import ColumnMapping, GlossarySuggestion, TermSuggestion

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent

RAG_CORPUS_DISPLAY_NAME = os.environ.get(
    "VERTEX_RAG_CORPUS_DISPLAY_NAME", "industry-glossaries"
)

app = FastAPI(title="Glossary Generator")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# ── In-memory session store ─────────────────────────────────────────────────
_SESSIONS: dict[str, dict] = {}


# ── RAG corpus resolver ─────────────────────────────────────────────────────

@lru_cache(maxsize=16)
def _resolve_rag_corpus(project_id: str, location: str) -> str:
    """Look up the built-in RAG corpus resource name by display name.

    Cached per (project, location) so we pay the list_corpora cost once per
    process. Raises ``RuntimeError`` with a clear pointer to the build script
    if the corpus is missing.
    """
    import vertexai
    from vertexai.preview import rag

    vertexai.init(project=project_id, location=location)
    for corpus in rag.list_corpora():
        if corpus.display_name == RAG_CORPUS_DISPLAY_NAME:
            logger.info("Resolved RAG corpus '%s' → %s",
                        RAG_CORPUS_DISPLAY_NAME, corpus.name)
            return corpus.name
    raise RuntimeError(
        f"RAG corpus with display_name='{RAG_CORPUS_DISPLAY_NAME}' not found "
        f"in project {project_id} / {location}. "
        "Run `python scripts/build_rag_corpus.py --project {project_id} "
        "--gcs-bucket ...` to create it."
    )


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
        return JSONResponse({"error": str(exc)}, status_code=400)
    return JSONResponse({"datasets": datasets})


@app.get("/api/tables")
def api_tables(project_id: str, dataset_id: str) -> JSONResponse:
    """List tables in a dataset. ``dataset_id`` may be ``project.dataset``."""
    try:
        client = bigquery.Client(project=project_id)
        ref = dataset_id if "." in dataset_id else f"{project_id}.{dataset_id}"
        tables = [
            {"table_id": t.table_id, "type": t.table_type}
            for t in client.list_tables(ref)
        ]
    except Exception as exc:  # noqa: BLE001
        logger.exception("list_tables failed for %s / %s", project_id, dataset_id)
        return JSONResponse({"error": str(exc)}, status_code=400)
    return JSONResponse({"tables": tables})


# ── HTML routes ─────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "default_project": os.environ.get("GOOGLE_CLOUD_PROJECT", ""),
            "default_glossary": os.environ.get("DATAPLEX_GLOSSARY_ID", ""),
            "default_location": os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
            "rag_corpus_display_name": RAG_CORPUS_DISPLAY_NAME,
        },
    )


@app.post("/suggest", response_class=HTMLResponse)
async def suggest(
    request: Request,
    response: Response,
    project_id: str = Form(...),
    dataset_id: str = Form(...),
    instructions: str = Form(""),
    location: str = Form("us-central1"),
    glossary_id: str = Form(""),
    glossary_location: str = Form("global"),
    session_id: Optional[str] = Cookie(None, alias="glossary_session"),
) -> HTMLResponse:
    sid = _get_or_create_session_id(session_id, response)

    form = await request.form()
    table_allowlist = [v for v in form.getlist("tables") if v]

    try:
        rag_corpus = _resolve_rag_corpus(project_id, location)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Could not resolve RAG corpus")
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "error": str(exc)},
            status_code=500,
        )

    config = AgentConfig.from_env(
        project_id=project_id,
        location=location,
        vertex_rag_corpus=rag_corpus,
        glossary_id=glossary_id or None,
        glossary_location=glossary_location,
    )

    try:
        agent = GlossaryGeneratorAgent(config)
        result = agent.run(
            dataset_id,
            instructions=instructions,
            table_allowlist=table_allowlist or None,
            publish=False,
        )
    except MissingDataplexScansError as exc:
        return templates.TemplateResponse(
            "needs_scans.html",
            {
                "request": request,
                "project_id": exc.project_id,
                "dataset_id": exc.dataset_id,
                "region": exc.region,
                "tables": exc.tables,
                "commands": exc.remediation_commands(),
            },
            status_code=412,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Agent failed")
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "error": str(exc)},
            status_code=500,
        )

    _SESSIONS[sid] = {
        "config": {
            "project_id": project_id,
            "location": location,
            "glossary_id": glossary_id,
            "glossary_location": glossary_location,
        },
        "dataset_id": dataset_id,
        "instructions": instructions,
        "suggestion": result["suggestion"],
    }

    html = templates.TemplateResponse(
        "suggestions.html",
        {
            "request": request,
            "dataset_id": dataset_id,
            "instructions": instructions,
            "glossary_id": glossary_id,
            "suggestion": result["suggestion"],
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
        bq_region=cfg.get("location", "us-central1"),
        dry_run=False,
    )
    report = publisher.publish(filtered, dataset_id=bare_dataset)

    return templates.TemplateResponse(
        "result.html",
        {
            "request": request,
            "report": report,
            "approved_count": len(approved),
            "total_count": len(all_mappings),
            "glossary_id": cfg["glossary_id"],
            "project_id": cfg["project_id"],
        },
    )


# ── helpers ─────────────────────────────────────────────────────────────────


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
