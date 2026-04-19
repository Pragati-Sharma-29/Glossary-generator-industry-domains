"""Build (or update) a Vertex AI RAG corpus from industry-standard glossary sources.

Sources per domain
──────────────────
Retail / Ecommerce   : googleapis/googleapis (Cloud Retail API protos)
                       · dbt-labs/jaffle_shop · gs1/EPCIS
                       · commercetools/commercetools-api-reference
Finance / Banking    : edmcouncil/fibo · finos/common-domain-model
                       · GoogleCloudPlatform/cortex-data-foundation (SAP Finance)
Healthcare           : OHDSI/CommonDataModel (OMOP) · HL7/fhir (FHIR R4)
                       · NOTE: LOINC requires license – skipped; provide manually
ERP / Supply Chain   : GoogleCloudPlatform/cortex-data-foundation (SAP + Oracle EBS)
                       · gs1-openguild/gs1-digitallink (GS1 JSON-LD)
CRM / Marketing      : GoogleCloudPlatform/cortex-data-foundation (Salesforce, Google Ads)
                       · adswerve/dbt-hubspot (HubSpot dbt)
Telco                : tmforum-oda/open-api-table-of-contents
                       · camaraproject/Commonalities
Automotive           : edmcouncil/auto · schemaorgschemaorg (automotive subset)

Usage
─────
    # Dry-run: only list what would be fetched
    python scripts/build_rag_corpus.py --dry-run

    # Full run
    python scripts/build_rag_corpus.py \
        --project my-proj \
        --gcs-bucket my-proj-rag-sources \
        --corpus-display-name industry-glossaries \
        --domains retail finance healthcare

    # All domains
    python scripts/build_rag_corpus.py \
        --project my-proj \
        --gcs-bucket my-proj-rag-sources

    On success the script prints the full corpus resource name, which you
    set as VERTEX_RAG_CORPUS.
"""
from __future__ import annotations

import argparse
import io
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterator, Optional
from urllib.parse import urljoin

import requests
import yaml

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────── source registry

@dataclass
class GithubSource:
    """One GitHub repo + list of (glob-like) path patterns to fetch."""
    domain: str
    repo: str                          # "owner/repo"
    ref: str = "main"                  # branch or tag
    path_patterns: list[str] = field(default_factory=list)
    processor: str = "auto"            # auto | dbt_yaml | owl_ttl | fhir_json | sql_ddl | markdown
    description: str = ""


SOURCES: list[GithubSource] = [
    # ── Retail / Ecommerce ──────────────────────────────────────────────────────
    GithubSource(
        domain="retail_ecommerce",
        repo="googleapis/googleapis",
        ref="master",
        path_patterns=["google/cloud/retail/v2/**.proto"],
        processor="auto",
        description="Google Cloud Retail API – Product, UserEvent, PurchaseTransaction protos",
    ),
    GithubSource(
        domain="retail_ecommerce",
        repo="dbt-labs/jaffle_shop",
        ref="main",
        path_patterns=["models/**.yml", "models/**.yaml"],
        processor="dbt_yaml",
        description="Jaffle Shop – canonical dbt model with column descriptions",
    ),
    GithubSource(
        domain="retail_ecommerce",
        repo="commercetools/commercetools-api-reference",
        ref="main",
        path_patterns=[
            "api-specs/api/types/cart/**.raml",
            "api-specs/api/types/order/**.raml",
            "api-specs/api/types/product/**.raml",
            "api-specs/api/types/customer/**.raml",
        ],
        processor="auto",
        description="commercetools API – Cart/Order/Product/Customer type references",
    ),
    GithubSource(
        domain="retail_ecommerce",
        repo="gs1/EPCIS",
        ref="master",
        path_patterns=["**.md", "REST Bindings/**.json"],
        processor="auto",
        description="GS1 EPCIS – supply chain / product event vocabulary",
    ),

    # ── Finance / Banking ───────────────────────────────────────────────────────
    GithubSource(
        domain="finance_banking",
        repo="edmcouncil/fibo",
        ref="master",
        path_patterns=[
            "FBC/**.ttl", "FND/**.ttl", "SEC/**.ttl",
            "LOAN/**.ttl", "DER/**.ttl",
        ],
        processor="owl_ttl",
        description="FIBO – Financial Industry Business Ontology (OWL/Turtle)",
    ),
    GithubSource(
        domain="finance_banking",
        repo="finos/common-domain-model",
        ref="master",
        path_patterns=["rosetta-source/src/main/rosetta/**.rosetta"],
        processor="rosetta",
        description="FINOS CDM – Common Domain Model for financial products",
    ),
    GithubSource(
        domain="finance_banking",
        repo="GoogleCloudPlatform/cortex-data-foundation",
        ref="main",
        path_patterns=[
            "src/SAP/SAP_REPORTING/models/**.yml",
            "src/SAP/SAP_REPORTING/models/**.yaml",
        ],
        processor="dbt_yaml",
        description="Cortex SAP Finance – dbt column descriptions",
    ),

    # ── Healthcare ──────────────────────────────────────────────────────────────
    GithubSource(
        domain="healthcare",
        repo="OHDSI/CommonDataModel",
        ref="main",
        path_patterns=[
            "inst/ddl/5.4/**.sql",
            "Documentation/CommonDataModel_Wiki_Docs/**.md",
        ],
        processor="auto",
        description="OMOP CDM v5.4 – DDL + Wiki documentation",
    ),
    GithubSource(
        domain="healthcare",
        repo="HL7/fhir",
        ref="master",
        path_patterns=["source/**.json"],
        processor="fhir_json",
        description="HL7 FHIR R4 – resource structure definitions",
    ),

    # ── ERP / Supply Chain ──────────────────────────────────────────────────────
    GithubSource(
        domain="erp_supply_chain",
        repo="GoogleCloudPlatform/cortex-data-foundation",
        ref="main",
        path_patterns=[
            "src/SAP/SAP_REPORTING/models/**.yml",
            "src/OracleEBS/src/reporting/models/**.yml",
        ],
        processor="dbt_yaml",
        description="Cortex SAP + Oracle EBS – reporting model column descriptions",
    ),
    GithubSource(
        domain="erp_supply_chain",
        repo="gs1-openguild/gs1-digital-link-standard",
        ref="main",
        path_patterns=["**.md", "**.json"],
        processor="auto",
        description="GS1 Digital Link standard – product/supply-chain identifiers",
    ),

    # ── CRM / Marketing ─────────────────────────────────────────────────────────
    GithubSource(
        domain="crm_marketing",
        repo="GoogleCloudPlatform/cortex-data-foundation",
        ref="main",
        path_patterns=[
            "src/SFDC/src/reporting/models/**.yml",
            "src/GoogleAds/src/reporting/models/**.yml",
        ],
        processor="dbt_yaml",
        description="Cortex Salesforce + Google Ads – dbt column descriptions",
    ),
    GithubSource(
        domain="crm_marketing",
        repo="fivetran/dbt_hubspot",
        ref="main",
        path_patterns=["models/**.yml", "models/**.yaml"],
        processor="dbt_yaml",
        description="HubSpot dbt – CRM entity column descriptions",
    ),

    # ── Telco ───────────────────────────────────────────────────────────────────
    GithubSource(
        domain="telco",
        repo="tmforum-oda/open-api-table-of-contents",
        ref="master",
        path_patterns=["**.md"],
        processor="auto",
        description="TM Forum Open APIs – API catalogue and entity descriptions",
    ),
    GithubSource(
        domain="telco",
        repo="camaraproject/Commonalities",
        ref="main",
        path_patterns=["documentation/**.md", "artifacts/**.yaml"],
        processor="auto",
        description="CAMARA Commonalities – telco API common data types",
    ),

    # ── Automotive ──────────────────────────────────────────────────────────────
    GithubSource(
        domain="automotive",
        repo="edmcouncil/auto",
        ref="master",
        path_patterns=["**.ttl"],
        processor="owl_ttl",
        description="EDMC AUTO ontology – automotive industry terms",
    ),
]

# ─────────────────────────────────────────────────────────────── GitHub helpers

class GitHubFetcher:
    API = "https://api.github.com"
    RAW = "https://raw.githubusercontent.com"

    def __init__(self, token: Optional[str] = None):
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/vnd.github.v3+json"})
        if token:
            self.session.headers["Authorization"] = f"token {token}"

    def list_files(self, repo: str, ref: str, path: str = "") -> list[dict]:
        url = f"{self.API}/repos/{repo}/git/trees/{ref}?recursive=1"
        resp = self._get(url)
        if resp is None:
            return []
        data = resp.json()
        return [
            item for item in data.get("tree", [])
            if item["type"] == "blob" and path in item["path"]
        ]

    def get_raw(self, repo: str, ref: str, path: str) -> Optional[str]:
        url = f"{self.RAW}/{repo}/{ref}/{path}"
        resp = self._get(url)
        if resp is None:
            return None
        try:
            return resp.text
        except Exception:
            return None

    def iter_matching(
        self, source: GithubSource
    ) -> Iterator[tuple[str, str]]:
        """Yield (path, content) for files matching any of source.path_patterns."""
        all_files = self.list_files(source.repo, source.ref)
        for item in all_files:
            path = item["path"]
            if any(_matches(path, pat) for pat in source.path_patterns):
                content = self.get_raw(source.repo, source.ref, path)
                if content:
                    yield path, content
                _rate_sleep()

    def _get(self, url: str) -> Optional[requests.Response]:
        for attempt in range(4):
            try:
                resp = self.session.get(url, timeout=30)
                if resp.status_code == 404:
                    logger.debug("404 %s", url)
                    return None
                if resp.status_code == 403:
                    reset = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
                    wait = max(1, reset - int(time.time()))
                    logger.warning("Rate limited; sleeping %ds", wait)
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp
            except requests.RequestException as exc:
                logger.warning("Attempt %d failed for %s: %s", attempt + 1, url, exc)
                time.sleep(2 ** attempt)
        return None


def _matches(path: str, pattern: str) -> bool:
    """Minimal glob: supports ** and * wildcards."""
    regex = re.escape(pattern).replace(r"\*\*", ".*").replace(r"\*", "[^/]*")
    return bool(re.fullmatch(regex, path))


def _rate_sleep(seconds: float = 0.25) -> None:
    time.sleep(seconds)


# ─────────────────────────────────────────────────────────────── processors

@dataclass
class Doc:
    domain: str
    source: str
    path: str
    text: str


def process_auto(path: str, content: str, source: GithubSource) -> list[Doc]:
    """Pass-through for markdown, SQL, proto, etc. – lightly cleaned."""
    text = content.strip()
    if not text or len(text) < 50:
        return []
    return [Doc(domain=source.domain, source=source.description, path=path, text=text)]


def process_dbt_yaml(path: str, content: str, source: GithubSource) -> list[Doc]:
    """Extract model + column descriptions from dbt schema YAML files."""
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError:
        return []
    if not isinstance(data, dict):
        return []

    chunks: list[str] = []
    for model in data.get("models", []):
        name = model.get("name", "?")
        desc = model.get("description", "")
        header = f"## Model: {name}\n{desc}\n\n### Columns"
        col_lines: list[str] = []
        for col in model.get("columns", []):
            col_name = col.get("name", "?")
            col_desc = col.get("description", "")
            data_type = col.get("data_type", "")
            tests = ", ".join(
                (t if isinstance(t, str) else list(t.keys())[0])
                for t in col.get("tests", [])
            )
            line = f"- **{col_name}** ({data_type}): {col_desc}"
            if tests:
                line += f" [tests: {tests}]"
            col_lines.append(line)
        if col_lines:
            chunks.append(header + "\n" + "\n".join(col_lines))
    if not chunks:
        return []
    return [
        Doc(
            domain=source.domain,
            source=source.description,
            path=path,
            text=chunk,
        )
        for chunk in chunks
    ]


def process_owl_ttl(path: str, content: str, source: GithubSource) -> list[Doc]:
    """Extract class / property definitions and their rdfs:label + rdfs:comment."""
    # Lightweight regex approach – avoids rdflib dep while still extracting
    # the human-readable definition text.
    label_re = re.compile(r'rdfs:label\s+"([^"]+)"', re.MULTILINE)
    comment_re = re.compile(r'rdfs:comment\s+"([^"\\]*(?:\\.[^"\\]*)*)"', re.DOTALL)
    # Split on blank-node / class blocks (separated by double newline + @)
    blocks = re.split(r"\n\n(?=\S)", content)
    docs: list[Doc] = []
    for block in blocks:
        labels = label_re.findall(block)
        comments = comment_re.findall(block)
        if not labels and not comments:
            continue
        label_str = " / ".join(dict.fromkeys(labels))   # deduplicate, preserve order
        comment_str = " ".join(
            c.replace("\n", " ").replace('\\"', '"').strip() for c in comments
        )
        text = f"**{label_str}**\n{comment_str}" if comment_str else f"**{label_str}**"
        if len(text) > 40:
            docs.append(
                Doc(domain=source.domain, source=source.description, path=path, text=text)
            )
    return docs


def process_fhir_json(path: str, content: str, source: GithubSource) -> list[Doc]:
    """Extract FHIR StructureDefinition resource type + element definitions."""
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return []
    if data.get("resourceType") != "StructureDefinition":
        return []
    name = data.get("name", "?")
    desc = data.get("description", "")
    chunks: list[str] = [f"## FHIR Resource: {name}\n{desc}\n\n### Elements"]
    for element in data.get("snapshot", {}).get("element", []):
        eid = element.get("id", "")
        short = element.get("short", "")
        definition = element.get("definition", "")
        if short or definition:
            chunks.append(f"- **{eid}**: {short}. {definition}")
    text = "\n".join(chunks)
    if len(text) < 100:
        return []
    return [Doc(domain=source.domain, source=source.description, path=path, text=text)]


def process_rosetta(path: str, content: str, source: GithubSource) -> list[Doc]:
    """Extract type + attribute definitions from FINOS Rosetta DSL."""
    type_re = re.compile(
        r"(?:type|enum)\s+(\w+)\s*(?:extends\s+\w+)?\s*\{([^}]+)\}", re.DOTALL
    )
    attr_re = re.compile(r"([A-Za-z]\w+)\s+<.*?>?\s*(?://\s*(.+))?$", re.MULTILINE)
    docs: list[Doc] = []
    for m in type_re.finditer(content):
        type_name = m.group(1)
        body = m.group(2)
        attrs: list[str] = []
        for am in attr_re.finditer(body):
            attr_name, comment = am.group(1), (am.group(2) or "").strip()
            attrs.append(f"  - {attr_name}: {comment}" if comment else f"  - {attr_name}")
        if attrs:
            text = f"## CDM Type: {type_name}\n" + "\n".join(attrs)
            docs.append(
                Doc(domain=source.domain, source=source.description, path=path, text=text)
            )
    return docs


PROCESSOR_MAP: dict[str, Callable[[str, str, GithubSource], list[Doc]]] = {
    "dbt_yaml": process_dbt_yaml,
    "owl_ttl": process_owl_ttl,
    "fhir_json": process_fhir_json,
    "rosetta": process_rosetta,
    "auto": process_auto,
}


def pick_processor(source: GithubSource, path: str) -> Callable:
    if source.processor != "auto":
        return PROCESSOR_MAP.get(source.processor, process_auto)
    ext = Path(path).suffix.lower()
    return {
        ".ttl": process_owl_ttl,
        ".yml": process_dbt_yaml,
        ".yaml": process_dbt_yaml,
        ".json": process_fhir_json,
        ".rosetta": process_rosetta,
    }.get(ext, process_auto)


# ─────────────────────────────────────────────────── (schema.org fetch removed)
# The automotive schema.org per-type JSON-LD endpoints (e.g.
# https://schema.org/Vehicle.jsonld) returned 404 consistently and were
# silently adding noise to the log without contributing chunks. The
# automotive seed_doc covers every type that subset used to target. Dead
# code excised on purpose — leave it dead.


# ─────────────────────────────────────────────────────────────── GCS upload

def upload_docs_to_gcs(
    docs: list[Doc],
    bucket_name: str,
    prefix: str = "rag-sources",
    project_id: Optional[str] = None,
) -> list[str]:
    """Upload docs as .txt files; return GCS URIs."""
    from google.cloud import storage  # lazy import

    client = storage.Client(project=project_id)
    try:
        bucket = client.get_bucket(bucket_name)
    except Exception:
        logger.info("Creating GCS bucket gs://%s", bucket_name)
        bucket = client.create_bucket(bucket_name, location="US")

    uris: list[str] = []
    for i, doc in enumerate(docs):
        safe_path = re.sub(r"[^\w/.\-]", "_", doc.path)
        blob_name = f"{prefix}/{doc.domain}/{i:06d}_{safe_path}.txt"
        blob = bucket.blob(blob_name)
        content = (
            f"Source: {doc.source}\n"
            f"Domain: {doc.domain}\n"
            f"Path: {doc.path}\n"
            f"---\n{doc.text}"
        )
        blob.upload_from_string(content, content_type="text/plain")
        uris.append(f"gs://{bucket_name}/{blob_name}")
    return uris


# ─────────────────────────────────────────────────────────────── RAG corpus

def create_or_get_corpus(
    project_id: str,
    location: str,
    display_name: str,
) -> str:
    """Return existing corpus resource name or create a new one.

    ``us-central1``, ``us-east1``, and ``us-east4`` restrict Spanner (ANN)
    mode to allowlisted projects for new tenants. In those regions the
    function forces RAG Engine **Serverless (KNN)** mode via
    ``rag.RagManagedDb(retrieval_strategy=KNN)``. If the installed SDK
    doesn't expose that class, it raises with a concrete remediation
    pointing either at an SDK upgrade or a region switch.
    """
    import vertexai
    from vertexai.preview import rag

    vertexai.init(project=project_id, location=location)

    for corpus in rag.list_corpora():
        if corpus.display_name == display_name:
            logger.info("Reusing existing corpus: %s", corpus.name)
            return corpus.name

    serverless_required_regions = {"us-central1", "us-east1", "us-east4"}
    RagManagedDb = getattr(rag, "RagManagedDb", None)
    needs_serverless = location in serverless_required_regions

    if needs_serverless and RagManagedDb is None:
        raise RuntimeError(
            f"Region '{location}' requires RAG Engine Serverless (KNN) mode "
            "for new projects, but this google-cloud-aiplatform SDK doesn't "
            "expose rag.RagManagedDb. Two ways forward:\n"
            "  1) Upgrade the SDK so RagManagedDb is available:\n"
            "       pip install --upgrade 'google-cloud-aiplatform[rag]'\n"
            "  2) Or rerun in a region that allows Spanner mode, e.g.\n"
            "       ./scripts/build_rag_corpus.py --location europe-west4 ...\n"
            "       (also pass --location europe-west4 to bootstrap.sh)"
        )

    backend_kwargs = {
        "rag_embedding_model_config": rag.RagEmbeddingModelConfig(
            vertex_prediction_endpoint=rag.VertexPredictionEndpoint(
                publisher_model="publishers/google/models/text-embedding-005"
            )
        )
    }
    if needs_serverless:
        logger.info(
            "Forcing RAG Engine Serverless (KNN) mode for region %s", location
        )
        backend_kwargs["rag_managed_db"] = RagManagedDb(
            retrieval_strategy=RagManagedDb.RetrievalStrategy.KNN
        )

    logger.info("Creating RAG corpus '%s' in %s", display_name, location)
    try:
        corpus = rag.create_corpus(
            display_name=display_name,
            backend_config=rag.RagVectorDbConfig(**backend_kwargs),
        )
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        if "Spanner mode" in msg and "restricted" in msg:
            raise RuntimeError(
                f"RAG Engine rejected the create_corpus call in '{location}':\n"
                f"  {msg}\n\n"
                "The installed SDK likely does not honour the Serverless "
                "(KNN) directive. Rerun in a different region, e.g.:\n"
                "  ./scripts/bootstrap.sh --project {} --location europe-west4\n"
                "Supported regions: "
                "https://cloud.google.com/vertex-ai/generative-ai/docs/"
                "rag-engine/rag-overview#supported-regions".format(project_id)
            ) from exc
        raise
    return corpus.name


def import_from_gcs(corpus_name: str, gcs_prefix_uri: str) -> None:
    """Import all .txt files under a GCS prefix into the corpus."""
    from vertexai.preview import rag

    logger.info("Importing from %s into corpus", gcs_prefix_uri)
    rag.import_files(
        corpus_name,
        paths=[gcs_prefix_uri],
        transformation_config=rag.TransformationConfig(
            chunking_config=rag.ChunkingConfig(chunk_size=512, chunk_overlap=64)
        ),
    )


# ─────────────────────────────────────────────────────────────── seed_docs

ALL_DOMAINS = [
    "retail_ecommerce",
    "finance_banking",
    "healthcare",
    "erp_supply_chain",
    "crm_marketing",
    "telco",
    "automotive",
]


def load_seed_docs(domain: str, repo_root: Path) -> list[Doc]:
    """Split ``seed_docs/<domain>.md`` on ``## `` headers into one Doc per term.

    Seed docs are hand-curated term definitions — always available, always
    high signal, and immune to upstream repo churn.
    """
    path = repo_root / "seed_docs" / f"{domain}.md"
    if not path.exists():
        logger.warning("No seed_docs/%s.md — skipping seed for %s", domain, domain)
        return []
    text = path.read_text(encoding="utf-8")

    # Split on lines that start with "## " (but keep the header line).
    sections = re.split(r"\n(?=## )", text)
    docs: list[Doc] = []
    for section in sections:
        if not section.startswith("## "):
            continue  # drop the intro / title block before the first H2
        header, _, body = section.partition("\n")
        term = header.removeprefix("## ").strip()
        chunk = f"{header}\n{body.strip()}"
        if len(chunk) < 40:
            continue
        docs.append(
            Doc(
                domain=domain,
                source=f"seed_docs/{domain}.md",
                path=f"seed_docs/{domain}.md#{term}",
                text=chunk,
            )
        )
    return docs


# ─────────────────────────────────────────────────────────────── main

def collect_docs_for_domain(
    domain: str,
    repo_root: Path,
    fetcher: Optional[GitHubFetcher],
    dry_run: bool,
) -> list[Doc]:
    """Collect all Docs for a single domain.

    Ordering: seed_docs first (primary), then optional GitHub augmentation
    (best-effort; logs but never raises on failure). Returns whatever was
    successfully extracted.
    """
    docs: list[Doc] = []

    # 1. Seed docs — primary grounding, always runs
    seed = load_seed_docs(domain, repo_root)
    if dry_run:
        print(f"  DRY-RUN [{domain}]: {len(seed)} seed_doc chunks")
    else:
        docs.extend(seed)
        logger.info("[%s] seed_docs → %d chunks", domain, len(seed))

    # 2. GitHub augmentation — only if token present
    if fetcher is not None:
        for src in [s for s in SOURCES if s.domain == domain]:
            logger.info("[%s] github %s / %s", domain, src.repo, src.ref)
            if dry_run:
                print(f"  DRY-RUN [{domain}]: would fetch {src.repo}")
                continue
            count = 0
            try:
                for path, content in fetcher.iter_matching(src):
                    processor = pick_processor(src, path)
                    chunks = processor(path, content, src)
                    docs.extend(chunks)
                    count += len(chunks)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "  github fetch failed for %s: %s (continuing)",
                    src.repo, exc,
                )
            if count == 0:
                logger.warning(
                    "  ⚠ %s yielded 0 chunks (repo/path/ref drift?)",
                    src.repo,
                )
            else:
                logger.info("  → %d chunks from github", count)

    return docs


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Populate a Vertex AI RAG corpus from industry glossary sources."
    )
    p.add_argument("--project", help="GCP project id (or GOOGLE_CLOUD_PROJECT)")
    p.add_argument("--location", default="us-central1", help="Vertex AI location")
    p.add_argument("--gcs-bucket", help="GCS bucket for staging (will be created if absent)")
    p.add_argument("--gcs-prefix", default="rag-sources", help="GCS object prefix")
    p.add_argument(
        "--corpus-display-name",
        default="industry-glossaries",
        help="Vertex RAG corpus display name",
    )
    p.add_argument(
        "--domains",
        nargs="+",
        choices=[
            "retail_ecommerce",
            "finance_banking",
            "healthcare",
            "erp_supply_chain",
            "crm_marketing",
            "telco",
            "automotive",
        ],
        help="Limit to specific domains (default: all)",
    )
    p.add_argument("--github-token", help="GitHub PAT to increase rate limits (or GITHUB_TOKEN)")
    p.add_argument("--dry-run", action="store_true", help="Print sources; do not fetch or upload")
    p.add_argument("--save-local", metavar="DIR", help="Also save docs as .txt files locally")
    p.add_argument("--skip-upload", action="store_true", help="Fetch + process but skip GCS/RAG")
    p.add_argument("-v", "--verbose", action="count", default=0)
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.WARNING - 10 * min(args.verbose, 2),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    project_id = args.project or os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    github_token = args.github_token or os.environ.get("GITHUB_TOKEN")

    if not project_id and not args.dry_run and not args.skip_upload:
        print("ERROR: --project / GOOGLE_CLOUD_PROJECT is required", file=sys.stderr)
        return 2

    repo_root = Path(__file__).resolve().parent.parent
    target_domains = args.domains or ALL_DOMAINS

    # GitHub fetcher is opt-in via GITHUB_TOKEN to avoid the 60-req/hr
    # anonymous ceiling that was silently corrupting earlier builds.
    if github_token:
        fetcher: Optional[GitHubFetcher] = GitHubFetcher(token=github_token)
        logger.info("GitHub augmentation enabled (token present — 5000 req/hr)")
    else:
        fetcher = None
        logger.info(
            "GitHub augmentation disabled (no GITHUB_TOKEN). Using seed_docs/ only."
        )

    results: dict[str, tuple[Optional[str], int]] = {}

    for domain in target_domains:
        print(f"\n=== {domain} ===")
        docs = collect_docs_for_domain(
            domain=domain,
            repo_root=repo_root,
            fetcher=fetcher,
            dry_run=args.dry_run,
        )

        if args.dry_run:
            print(f"  DRY-RUN: {len(docs)} chunks would be indexed for {domain}")
            continue

        print(f"  Collected {len(docs)} chunks")

        if args.save_local:
            local_dir = Path(args.save_local) / domain
            local_dir.mkdir(parents=True, exist_ok=True)
            for i, doc in enumerate(docs):
                out = local_dir / f"{i:06d}.txt"
                out.write_text(
                    f"Source: {doc.source}\nDomain: {doc.domain}\n"
                    f"Path: {doc.path}\n---\n{doc.text}",
                    encoding="utf-8",
                )
            print(f"  Saved {len(docs)} files to {local_dir}")

        if args.skip_upload:
            results[domain] = (None, len(docs))
            continue

        if not docs:
            logger.warning("No docs for %s — skipping corpus create", domain)
            results[domain] = (None, 0)
            continue

        if not args.gcs_bucket:
            print("ERROR: --gcs-bucket is required to upload", file=sys.stderr)
            return 2

        prefix = f"{args.gcs_prefix}/{domain}"
        print(f"  Uploading to gs://{args.gcs_bucket}/{prefix}/ …")
        upload_docs_to_gcs(
            docs,
            bucket_name=args.gcs_bucket,
            prefix=prefix,
            project_id=project_id,
        )

        corpus_display = f"{args.corpus_display_name}-{domain}"
        print(f"  Creating / updating corpus '{corpus_display}' …")
        corpus_name = create_or_get_corpus(project_id, args.location, corpus_display)
        gcs_uri = f"gs://{args.gcs_bucket}/{prefix}/"
        import_from_gcs(corpus_name, gcs_uri)
        results[domain] = (corpus_name, len(docs))

    if args.dry_run:
        return 0

    # ── Summary ──────────────────────────────────────────────────────────────
    print("\n✓ Done. Per-domain corpora:")
    for domain in target_domains:
        if domain not in results:
            continue
        name, count = results[domain]
        shown = name or "(skip-upload)"
        print(f"  {domain:20s}  {count:4d} chunks  {shown}")

    any_built = any(n for n, _ in results.values())
    if any_built:
        print(
            "\nThe web app resolves domain corpora automatically by display "
            f"name prefix '{args.corpus_display_name}'. You can also set:"
        )
        print(
            f"  export VERTEX_RAG_CORPUS_PREFIX={args.corpus_display_name}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
