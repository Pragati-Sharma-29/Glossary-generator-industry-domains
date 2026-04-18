"""Build (or update) a Vertex AI RAG corpus from industry-standard glossary sources.

Sources per domain
──────────────────
Retail / Ecommerce   : google/retail-data-model · dbt-labs/jaffle_shop
                       · GoogleCloudPlatform/thelook-ecommerce
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
        repo="google/retail-data-model",
        ref="main",
        path_patterns=["**.proto", "**.md"],
        processor="auto",
        description="Google Retail Data Model – protobuf entity definitions",
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
        repo="GoogleCloudPlatform/thelook-ecommerce",
        ref="main",
        path_patterns=["**.md", "**.sql"],
        processor="auto",
        description="TheLook Ecommerce – sample schema documentation",
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

# schema.org automotive subset – fetched directly from schema.org JSON-LD release
SCHEMA_ORG_AUTOMOTIVE_TYPES = [
    "Vehicle", "Car", "BusOrCoach", "Motorcycle", "MotorizedBicycle",
    "BicycleStore", "AutoWash", "AutoDealer", "AutoPartsStore",
    "AutoRepair", "AutoRental",
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


# ─────────────────────────────────────────────────── schema.org automotive fetch

def fetch_schema_org_automotive() -> list[Doc]:
    """Fetch schema.org JSON-LD for the automotive type subset."""
    docs: list[Doc] = []
    session = requests.Session()
    for stype in SCHEMA_ORG_AUTOMOTIVE_TYPES:
        url = f"https://schema.org/{stype}.jsonld"
        try:
            resp = session.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            name = data.get("rdfs:label", stype)
            comment = data.get("rdfs:comment", "")
            props: list[str] = []
            for item in data.get("@graph", []):
                if item.get("@type") in ("rdf:Property", "rdfs:Property"):
                    prop_name = item.get("rdfs:label", "")
                    prop_comment = item.get("rdfs:comment", "")
                    if prop_name:
                        props.append(f"  - **{prop_name}**: {prop_comment}")
            text = f"## schema.org: {name}\n{comment}"
            if props:
                text += "\n### Properties\n" + "\n".join(props)
            docs.append(
                Doc(
                    domain="automotive",
                    source="schema.org automotive",
                    path=f"schema.org/{stype}",
                    text=text,
                )
            )
            _rate_sleep(0.5)
        except Exception as exc:
            logger.warning("schema.org fetch failed for %s: %s", stype, exc)
    return docs


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
    """Return existing corpus resource name or create a new one."""
    import vertexai
    from vertexai.preview import rag

    vertexai.init(project=project_id, location=location)

    for corpus in rag.list_corpora():
        if corpus.display_name == display_name:
            logger.info("Reusing existing corpus: %s", corpus.name)
            return corpus.name

    logger.info("Creating new RAG corpus '%s'", display_name)
    corpus = rag.create_corpus(
        display_name=display_name,
        backend_config=rag.RagVectorDbConfig(
            rag_embedding_model_config=rag.RagEmbeddingModelConfig(
                vertex_prediction_endpoint=rag.VertexPredictionEndpoint(
                    publisher_model="publishers/google/models/text-embedding-005"
                )
            )
        ),
    )
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


# ─────────────────────────────────────────────────────────────── main

def collect_docs(
    domains: Optional[list[str]],
    github_token: Optional[str],
    include_schema_org: bool,
    dry_run: bool,
) -> list[Doc]:
    fetcher = GitHubFetcher(token=github_token)
    active_sources = [
        s for s in SOURCES if domains is None or s.domain in domains
    ]
    logger.info("Fetching from %d sources", len(active_sources))
    all_docs: list[Doc] = []

    for src in active_sources:
        logger.info("[%s] %s / %s", src.domain, src.repo, src.ref)
        if dry_run:
            print(f"  DRY-RUN: would fetch {src.repo} ({src.description})")
            continue
        count = 0
        for path, content in fetcher.iter_matching(src):
            processor = pick_processor(src, path)
            docs = processor(path, content, src)
            all_docs.extend(docs)
            count += len(docs)
        logger.info("  → %d chunks extracted", count)

    if include_schema_org and (domains is None or "automotive" in domains):
        logger.info("Fetching schema.org automotive types")
        if not dry_run:
            schema_docs = fetch_schema_org_automotive()
            all_docs.extend(schema_docs)
            logger.info("  → %d schema.org chunks", len(schema_docs))
        else:
            print("  DRY-RUN: would fetch schema.org automotive types")

    return all_docs


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
    p.add_argument("--no-schema-org", action="store_true", help="Skip schema.org fetch")
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

    # ── 1. Collect and process docs ──────────────────────────────────────────
    docs = collect_docs(
        domains=args.domains,
        github_token=github_token,
        include_schema_org=not args.no_schema_org,
        dry_run=args.dry_run,
    )

    if args.dry_run:
        print(f"\n{len(SOURCES)} sources would be processed.")
        return 0

    print(f"Collected {len(docs)} document chunks across all domains.")

    if not docs:
        print("No documents collected – check source connectivity.", file=sys.stderr)
        return 1

    # ── 2. Optionally save locally ───────────────────────────────────────────
    if args.save_local:
        local_dir = Path(args.save_local)
        local_dir.mkdir(parents=True, exist_ok=True)
        for i, doc in enumerate(docs):
            out = local_dir / f"{doc.domain}_{i:06d}.txt"
            out.write_text(
                f"Source: {doc.source}\nDomain: {doc.domain}\nPath: {doc.path}\n---\n{doc.text}",
                encoding="utf-8",
            )
        print(f"Saved {len(docs)} files to {args.save_local}")

    if args.skip_upload:
        return 0

    # ── 3. Upload to GCS ─────────────────────────────────────────────────────
    if not args.gcs_bucket:
        print("ERROR: --gcs-bucket is required to upload", file=sys.stderr)
        return 2

    print(f"Uploading to gs://{args.gcs_bucket}/{args.gcs_prefix} …")
    upload_docs_to_gcs(
        docs,
        bucket_name=args.gcs_bucket,
        prefix=args.gcs_prefix,
        project_id=project_id,
    )

    # ── 4. Create / update RAG corpus ────────────────────────────────────────
    print(f"Creating / updating Vertex RAG corpus '{args.corpus_display_name}' …")
    corpus_name = create_or_get_corpus(project_id, args.location, args.corpus_display_name)
    gcs_uri = f"gs://{args.gcs_bucket}/{args.gcs_prefix}/"
    import_from_gcs(corpus_name, gcs_uri)

    print("\n✓ Done.")
    print(f"  Corpus resource name: {corpus_name}")
    print(f"\nSet this in your environment:")
    print(f"  export VERTEX_RAG_CORPUS={corpus_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
