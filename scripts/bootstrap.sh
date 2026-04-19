#!/usr/bin/env bash
# Bootstrap the glossary-generator end-to-end:
#   1. Enable required GCP APIs
#   2. Set up application-default credentials
#   3. Install Python dependencies
#   4. Build the Vertex RAG corpus (if missing)
#   5. Create the target Dataplex glossary (if missing)
#   6. Start the FastAPI web app
#
# Every step is idempotent — safe to re-run. Use --skip-* flags to opt out
# of individual steps.
#
# Usage:
#   ./scripts/bootstrap.sh --project my-proj
#   ./scripts/bootstrap.sh --project my-proj --skip-corpus --skip-serve

set -euo pipefail

# ── defaults ────────────────────────────────────────────────────────────────
PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-}"
LOCATION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
GLOSSARY_ID="${DATAPLEX_GLOSSARY_ID:-enterprise-glossary}"
GLOSSARY_LOCATION="${DATAPLEX_GLOSSARY_LOCATION:-global}"
CORPUS_DISPLAY_NAME="${VERTEX_RAG_CORPUS_PREFIX:-industry-glossaries}"
BUCKET=""
PORT="${PORT:-8080}"

SKIP_APIS=0
SKIP_AUTH=0
SKIP_DEPS=0
SKIP_CORPUS=0
SKIP_GLOSSARY=0
SKIP_SERVE=0

REQUIRED_ROLES=(
  "roles/bigquery.dataViewer"
  "roles/bigquery.metadataViewer"
  "roles/dataplex.dataScanViewer"
  "roles/dataplex.glossaryOwner"
  "roles/aiplatform.user"
  "roles/storage.admin"
)

# ── colours ─────────────────────────────────────────────────────────────────
if [[ -t 1 ]]; then
  C_GREEN=$'\033[32m'; C_BLUE=$'\033[34m'; C_YELLOW=$'\033[33m'
  C_RED=$'\033[31m';   C_DIM=$'\033[2m';    C_RESET=$'\033[0m'
else
  C_GREEN=""; C_BLUE=""; C_YELLOW=""; C_RED=""; C_DIM=""; C_RESET=""
fi

step()  { echo "${C_BLUE}▶ $*${C_RESET}"; }
ok()    { echo "${C_GREEN}✓ $*${C_RESET}"; }
warn()  { echo "${C_YELLOW}! $*${C_RESET}"; }
die()   { echo "${C_RED}✗ $*${C_RESET}" >&2; exit 1; }
info()  { echo "${C_DIM}  $*${C_RESET}"; }

usage() {
  cat <<EOF
Usage: $0 [flags]

  --project ID            GCP project id (or env GOOGLE_CLOUD_PROJECT)
  --location REGION       Vertex / Dataplex region (default: $LOCATION)
  --glossary ID           Target Dataplex glossary id (default: $GLOSSARY_ID)
  --glossary-location L   Glossary location (default: $GLOSSARY_LOCATION)
  --corpus-name NAME      RAG corpus display-name prefix; one corpus per
                          industry is built as \${NAME}-\${domain}
                          (default: $CORPUS_DISPLAY_NAME)
  --bucket NAME           GCS bucket for RAG sources (default: \${PROJECT}-rag-sources)
  --port N                Web app port (default: $PORT)
  --skip-apis             Skip API enable
  --skip-auth             Skip ADC login
  --skip-deps             Skip pip install
  --skip-corpus           Skip RAG corpus build
  --skip-glossary         Skip glossary create
  --skip-serve            Do setup only; don't start uvicorn
  -h, --help              Show this help
EOF
  exit 0
}

# ── parse args ──────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --project)            PROJECT_ID="$2"; shift 2 ;;
    --location)           LOCATION="$2"; shift 2 ;;
    --glossary)           GLOSSARY_ID="$2"; shift 2 ;;
    --glossary-location)  GLOSSARY_LOCATION="$2"; shift 2 ;;
    --corpus-name)        CORPUS_DISPLAY_NAME="$2"; shift 2 ;;
    --bucket)             BUCKET="$2"; shift 2 ;;
    --port)               PORT="$2"; shift 2 ;;
    --skip-apis)          SKIP_APIS=1; shift ;;
    --skip-auth)          SKIP_AUTH=1; shift ;;
    --skip-deps)          SKIP_DEPS=1; shift ;;
    --skip-corpus)        SKIP_CORPUS=1; shift ;;
    --skip-glossary)      SKIP_GLOSSARY=1; shift ;;
    --skip-serve)         SKIP_SERVE=1; shift ;;
    -h|--help)            usage ;;
    *) die "Unknown flag: $1 (see --help)" ;;
  esac
done

# ── prereqs ─────────────────────────────────────────────────────────────────
command -v gcloud >/dev/null 2>&1 || die "gcloud is not installed"
command -v python3 >/dev/null 2>&1 || die "python3 is not installed"
command -v pip >/dev/null 2>&1 || command -v pip3 >/dev/null 2>&1 \
  || die "pip is not installed"

if [[ -z "$PROJECT_ID" ]]; then
  PROJECT_ID="$(gcloud config get-value project 2>/dev/null || true)"
fi
[[ -n "$PROJECT_ID" ]] || die "Project id is required: pass --project or set GOOGLE_CLOUD_PROJECT"
BUCKET="${BUCKET:-${PROJECT_ID}-rag-sources}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

cat <<EOF
${C_DIM}──────────────────────────────────────────────${C_RESET}
 project           : $PROJECT_ID
 location          : $LOCATION
 glossary          : $GLOSSARY_ID (@ $GLOSSARY_LOCATION)
 RAG corpus name   : $CORPUS_DISPLAY_NAME
 GCS bucket        : $BUCKET
 web port          : $PORT
${C_DIM}──────────────────────────────────────────────${C_RESET}
EOF

gcloud config set project "$PROJECT_ID" --quiet >/dev/null

# ── 1. Enable APIs ──────────────────────────────────────────────────────────
if [[ $SKIP_APIS -eq 0 ]]; then
  step "Enabling required APIs"
  gcloud services enable \
    bigquery.googleapis.com \
    dataplex.googleapis.com \
    aiplatform.googleapis.com \
    storage.googleapis.com \
    --project "$PROJECT_ID"
  ok "APIs enabled"
else
  info "Skipping API enable"
fi

# ── 2. Application-default credentials ──────────────────────────────────────
if [[ $SKIP_AUTH -eq 0 ]]; then
  step "Checking application-default credentials"
  if gcloud auth application-default print-access-token >/dev/null 2>&1; then
    ok "ADC already configured"
  else
    warn "No ADC found — launching login flow"
    gcloud auth application-default login --quiet
    ok "ADC configured"
  fi
  ACTIVE_USER="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null | head -n1 || true)"
  if [[ -n "$ACTIVE_USER" ]]; then
    info "Active account: $ACTIVE_USER"
    info "Required roles (grant manually if missing):"
    for r in "${REQUIRED_ROLES[@]}"; do info "  - $r"; done
  fi
else
  info "Skipping auth"
fi

# ── 3. Install Python deps ──────────────────────────────────────────────────
if [[ $SKIP_DEPS -eq 0 ]]; then
  step "Installing Python dependencies"
  if python3 -c "import fastapi, uvicorn, google.cloud.aiplatform, google.cloud.dataplex" \
       >/dev/null 2>&1; then
    ok "Dependencies already installed"
  else
    PIP=$(command -v pip3 || command -v pip)
    "$PIP" install -r requirements.txt
    ok "Dependencies installed"
  fi
else
  info "Skipping dependency install"
fi

# ── 4. Build per-domain RAG corpora if any are missing ──────────────────────
if [[ $SKIP_CORPUS -eq 0 ]]; then
  step "Checking for per-domain RAG corpora with prefix '$CORPUS_DISPLAY_NAME'"
  set +e
  MISSING_DOMAINS=$(python3 - "$PROJECT_ID" "$LOCATION" "$CORPUS_DISPLAY_NAME" <<'PYEOF'
import sys
import vertexai
from vertexai.preview import rag

project, location, prefix = sys.argv[1:4]
domains = [
    "retail_ecommerce", "finance_banking", "healthcare",
    "erp_supply_chain", "crm_marketing", "telco", "automotive",
]
vertexai.init(project=project, location=location)
present = {c.display_name for c in rag.list_corpora()}
missing = [d for d in domains if f"{prefix}-{d}" not in present]
print(" ".join(missing))
PYEOF
  )
  set -e

  if [[ -z "${MISSING_DOMAINS// }" ]]; then
    ok "All 7 per-domain corpora already exist — skipping build"
  else
    warn "Missing domains: $MISSING_DOMAINS — building (~1-3 min each with seed_docs only)"
    # Ensure the bucket exists (idempotent)
    if ! gcloud storage buckets describe "gs://${BUCKET}" \
           --project "$PROJECT_ID" >/dev/null 2>&1; then
      step "Creating GCS bucket gs://$BUCKET"
      gcloud storage buckets create "gs://${BUCKET}" \
        --project "$PROJECT_ID" --location="$LOCATION" --uniform-bucket-level-access
    fi
    python3 -u scripts/build_rag_corpus.py \
      --project "$PROJECT_ID" \
      --location "$LOCATION" \
      --gcs-bucket "$BUCKET" \
      --corpus-display-name "$CORPUS_DISPLAY_NAME" \
      --domains $MISSING_DOMAINS \
      -vv
    ok "Per-domain corpora built"
  fi
else
  info "Skipping RAG corpus build"
fi

# ── 5. Create glossary if missing ───────────────────────────────────────────
if [[ $SKIP_GLOSSARY -eq 0 ]]; then
  step "Checking for Dataplex glossary '$GLOSSARY_ID'"
  if gcloud dataplex glossaries describe "$GLOSSARY_ID" \
       --project "$PROJECT_ID" --location "$GLOSSARY_LOCATION" \
       >/dev/null 2>&1; then
    ok "Glossary already exists"
  else
    warn "Glossary not found — creating"
    gcloud dataplex glossaries create "$GLOSSARY_ID" \
      --project "$PROJECT_ID" \
      --location "$GLOSSARY_LOCATION" \
      --display-name "${GLOSSARY_ID//-/ }"
    ok "Glossary created"
  fi
else
  info "Skipping glossary create"
fi

# ── 6. Launch web app ───────────────────────────────────────────────────────
export GOOGLE_CLOUD_PROJECT="$PROJECT_ID"
export GOOGLE_CLOUD_LOCATION="$LOCATION"
export DATAPLEX_GLOSSARY_ID="$GLOSSARY_ID"
export DATAPLEX_GLOSSARY_LOCATION="$GLOSSARY_LOCATION"
export VERTEX_RAG_CORPUS_PREFIX="$CORPUS_DISPLAY_NAME"

if [[ $SKIP_SERVE -eq 1 ]]; then
  ok "Setup complete. To start the web app:"
  cat <<EOF

  export GOOGLE_CLOUD_PROJECT=$PROJECT_ID
  export GOOGLE_CLOUD_LOCATION=$LOCATION
  export DATAPLEX_GLOSSARY_ID=$GLOSSARY_ID
  export VERTEX_RAG_CORPUS_PREFIX=$CORPUS_DISPLAY_NAME

  uvicorn webapp:app --reload --port $PORT

EOF
  exit 0
fi

step "Starting web app on http://localhost:$PORT"
exec python3 -m uvicorn webapp:app --reload --port "$PORT"
