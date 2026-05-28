"""LLM-assisted memory extraction."""

from __future__ import annotations

import json

from pydantic import ValidationError

from mneno.extraction.base import ExtractedMemory, ExtractionResult
from mneno.extraction.prompts import EXTRACTION_PROMPT_VERSION, EXTRACTION_SYSTEM_PROMPT, build_extraction_prompt
from mneno.providers.llm import LLMProvider


class LLMMemoryExtractor:
    """Extract memories with an LLMProvider."""

    def __init__(self, llm_provider: LLMProvider) -> None:
        self.llm_provider = llm_provider

    def extract(self, text: str) -> ExtractionResult:
        """Extract structured memories using strict JSON output."""
        prompt = build_extraction_prompt(text)
        raw = self.llm_provider.generate(prompt, system_prompt=EXTRACTION_SYSTEM_PROMPT, temperature=0.0)
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            return ExtractionResult(
                source_text=text,
                mode="llm",
                errors=[f"LLM extraction output was not valid JSON: {exc}"],
                provider_name=self.llm_provider.name,
                prompt_version=EXTRACTION_PROMPT_VERSION,
            )

        raw_items = payload.get("memories", payload) if isinstance(payload, dict) else payload
        if not isinstance(raw_items, list):
            return ExtractionResult(
                source_text=text,
                mode="llm",
                errors=["LLM extraction JSON must be an array or an object with a memories array"],
                provider_name=self.llm_provider.name,
                prompt_version=EXTRACTION_PROMPT_VERSION,
            )

        extracted: list[ExtractedMemory] = []
        errors: list[str] = []
        for index, item in enumerate(raw_items):
            try:
                extracted.append(ExtractedMemory.model_validate(item))
            except ValidationError as exc:
                errors.append(f"Extracted memory at index {index} failed validation: {exc}")

        return ExtractionResult(
            source_text=text,
            mode="llm",
            extracted=extracted,
            errors=errors,
            provider_name=self.llm_provider.name,
            prompt_version=EXTRACTION_PROMPT_VERSION,
        )
