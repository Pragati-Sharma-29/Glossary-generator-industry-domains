"""Thin wrapper over the Vertex AI Gemini + RAG engine.

The RAG corpus is expected to be populated out-of-band with glossary material
(e.g. industry-standard vocabularies: FIBO, HL7, GS1, customer internal
glossaries). Queries to the corpus are grounded into the generation call as
tool-augmented retrieval.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Optional

import vertexai
from vertexai.generative_models import GenerativeModel, Tool
from vertexai.preview import rag

logger = logging.getLogger(__name__)


@dataclass
class RagSnippet:
    source: str
    text: str


class VertexRagClient:
    def __init__(
        self,
        project_id: str,
        location: str,
        model: str = "gemini-2.5-pro",
        rag_corpus: Optional[str] = None,
    ):
        vertexai.init(project=project_id, location=location)
        self.project_id = project_id
        self.location = location
        self.model_name = model
        self.rag_corpus = rag_corpus
        self._model = self._build_model()

    # ------------------------------------------------------------------ model build

    def _build_model(self) -> GenerativeModel:
        tools = []
        if self.rag_corpus:
            retrieval = rag.Retrieval(
                source=rag.VertexRagStore(
                    rag_resources=[rag.RagResource(rag_corpus=self.rag_corpus)],
                    similarity_top_k=30,
                    vector_distance_threshold=0.7,
                ),
            )
            tools.append(Tool.from_retrieval(retrieval=retrieval))
        return GenerativeModel(self.model_name, tools=tools or None)

    # ------------------------------------------------------------------ retrieval

    def retrieve(self, query: str, top_k: int = 8) -> list[RagSnippet]:
        """Direct (non-LLM) retrieval from the RAG corpus for auditing."""
        if not self.rag_corpus:
            return []
        response = rag.retrieval_query(
            rag_resources=[rag.RagResource(rag_corpus=self.rag_corpus)],
            text=query,
            similarity_top_k=top_k,
        )
        out: list[RagSnippet] = []
        for ctx in getattr(response, "contexts", []).contexts:
            out.append(
                RagSnippet(
                    source=getattr(ctx, "source_uri", "") or getattr(ctx, "source_display_name", ""),
                    text=ctx.text,
                )
            )
        return out

    # ------------------------------------------------------------------ generation

    def generate_json(
        self,
        prompt: str,
        *,
        system_instruction: Optional[str] = None,
        response_schema: Optional[dict] = None,
        temperature: float = 0.2,
    ) -> dict:
        """Call Gemini with RAG grounding and parse a JSON response.

        ``response_schema`` is intentionally ignored: Gemini's controlled
        generation cannot be combined with RAG grounding tools, and the
        Vertex SDK's Schema proto is brittle across versions (see commit
        history). We rely on ``response_mime_type=application/json`` plus
        the explicit schema described in the prompt to keep output valid.
        """
        del response_schema  # kept in the signature for API stability
        generation_config = {
            "temperature": temperature,
            "response_mime_type": "application/json",
        }

        if system_instruction:
            model = GenerativeModel(
                self.model_name,
                tools=self._model._tools if self._model._tools else None,
                system_instruction=system_instruction,
            )
        else:
            model = self._model

        response = model.generate_content(prompt, generation_config=generation_config)
        text = response.text or "{}"
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.error("Model did not return valid JSON. Raw: %s", text[:500])
            raise
