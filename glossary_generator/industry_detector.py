"""LLM-based industry detection from dataset schema signals.

The agent calls :func:`detect_domain` once per dataset to pick which of the
seven supported industries best matches the schema. The chosen domain key
drives per-domain RAG corpus selection downstream.

Design notes
────────────
* The detection call runs **without RAG grounding** — it only sees the
  table/column signals. That keeps it cheap (single short prompt, no
  retrieval) and prevents circular dependencies (we can't ground a
  detection on a corpus we haven't chosen yet).
* Output is parsed from JSON; a malformed response falls back to
  ``unknown`` rather than raising, so the agent degrades to schema-only
  operation instead of erroring out.
* The optional ``instructions`` blob is included so an operator hint
  ("P&C insurance claims mart") can override ambiguous signals.
"""
from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import DatasetContext
    from .vertex_rag import VertexRagClient

logger = logging.getLogger(__name__)

SUPPORTED_DOMAINS = (
    "retail_ecommerce",
    "finance_banking",
    "healthcare",
    "erp_supply_chain",
    "crm_marketing",
    "telco",
    "automotive",
)

DOMAIN_DESCRIPTIONS = {
    "retail_ecommerce": "Retail / E-commerce — products, orders, carts, SKUs, loyalty, storefront events",
    "finance_banking": "Finance / Banking — accounts, transactions, trades, instruments, FIBO concepts, insurance policies and claims",
    "healthcare": "Healthcare — patients, encounters, conditions, medications, claims, FHIR/OMOP/IDMP vocabulary",
    "erp_supply_chain": "ERP / Supply Chain — materials, plants, vendors, purchase orders, inventory, SAP-style master data, GS1 EPCIS events",
    "crm_marketing": "CRM / Marketing — leads, opportunities, campaigns, cases, Salesforce/HubSpot objects, marketing attribution",
    "telco": "Telco — subscribers, CDRs, cells/eNodeBs, network alarms, KPIs, 4G/5G core functions, billing plans",
    "automotive": "Automotive — vehicles (VIN), makes/models, dealers, sales, service, warranty, telematics, DTCs",
}

_DETECTION_PROMPT = """\
You are classifying a BigQuery dataset into ONE of seven industry domains.
Choose the single best match based on the table and column names, the
dataset description, and any operator hint. If the signals are weak or
conflicting, return "unknown" — do NOT guess.

## Domains
{domain_list}

## Dataset signals
{dataset_summary}

## Operator hint
{instructions}

Return ONLY valid JSON of the form:

{{
  "domain": "<one of: {domain_keys}, unknown>",
  "confidence": <number 0.0-1.0>,
  "reasoning": "<one-sentence justification citing specific column or table names>"
}}
"""


def _summarise_for_detection(ctx: "DatasetContext") -> str:
    """Compact schema summary for the detection call.

    Uses just table_id + first 15 column names per table. Full profile
    stats would bloat the prompt and aren't needed for detection — the
    table/column names alone carry the industry signal.
    """
    lines: list[str] = []
    if ctx.description:
        lines.append(f"Dataset description: {ctx.description}")
    lines.append(f"Dataset id: {ctx.dataset_id}")
    lines.append("")
    lines.append("Tables:")
    for t in ctx.tables:
        col_names = [c.name for c in t.columns[:15]]
        extra = f" (+{len(t.columns) - 15} more)" if len(t.columns) > 15 else ""
        lines.append(f"- {t.table_id}: {', '.join(col_names)}{extra}")
    return "\n".join(lines)


def detect_domain(
    vertex: "VertexRagClient",
    ctx: "DatasetContext",
    instructions: str = "",
) -> tuple[str, float, str]:
    """Classify a dataset into one of the seven industries.

    Returns ``(domain_key, confidence, reasoning)``. ``domain_key`` is
    always a member of :data:`SUPPORTED_DOMAINS` or the literal
    ``"unknown"``. Confidence is 0.0 when the call fails.
    """
    domain_list = "\n".join(
        f"- {key}: {desc}" for key, desc in DOMAIN_DESCRIPTIONS.items()
    )
    prompt = _DETECTION_PROMPT.format(
        domain_list=domain_list,
        domain_keys=", ".join(SUPPORTED_DOMAINS),
        dataset_summary=_summarise_for_detection(ctx),
        instructions=instructions.strip() or "(none provided)",
    )

    try:
        raw = vertex.generate_json(prompt, temperature=0.0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Domain detection call failed: %s", exc)
        return "unknown", 0.0, f"detection call failed: {exc}"

    domain = str(raw.get("domain", "unknown")).strip()
    if domain not in SUPPORTED_DOMAINS and domain != "unknown":
        logger.warning("Detector returned unsupported domain %r; treating as unknown", domain)
        domain = "unknown"

    try:
        confidence = float(raw.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    reasoning = str(raw.get("reasoning", ""))

    logger.info(
        "Detected domain=%s confidence=%.2f reasoning=%r",
        domain, confidence, reasoning[:200],
    )
    return domain, confidence, reasoning
