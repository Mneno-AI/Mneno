"""Prompts for optional LLM-assisted extraction and compaction."""

EXTRACTION_PROMPT_VERSION = "mneno.memory_extraction.v1"
COMPACTION_MERGE_PROMPT_VERSION = "mneno.compaction_merge.v1"

EXTRACTION_SYSTEM_PROMPT = (
    "You extract durable AI memory as strict JSON only. Do not include markdown or prose outside JSON."
)


def build_extraction_prompt(text: str) -> str:
    """Build a strict JSON extraction prompt."""
    return f"""
{EXTRACTION_PROMPT_VERSION}

Extract durable facts, preferences, goals, constraints, and project information from the source text.
Avoid trivial small talk. Avoid sensitive information unless explicitly useful and appropriate.

Return JSON only as an array of objects with:
- content: string
- memory_type: one of episodic, semantic, operational, preference
- importance: number from 0 to 1
- tags: array of strings
- metadata: object
- reason: string

Source text:
{text}
""".strip()


def build_compaction_merge_prompt(contents: list[str]) -> str:
    """Build a strict JSON merge prompt for already-selected duplicate memories."""
    joined = "\n".join(f"- {content}" for content in contents)
    return f"""
{COMPACTION_MERGE_PROMPT_VERSION}

Merge these duplicate or near-duplicate memories into one concise durable memory.
The deterministic compaction engine has already selected these memories for merging.
Return JSON only as an object with a single field:
- content: string

Memories:
{joined}
""".strip()
