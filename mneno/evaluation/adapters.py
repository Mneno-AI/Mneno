"""Benchmark adapter protocol for external evaluation frameworks."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from mneno.evaluation.reports import EvaluationReport

if TYPE_CHECKING:
    from mneno.client import MemoryClient


@runtime_checkable
class BenchmarkAdapter(Protocol):
    """Protocol implemented by external benchmark adapters."""

    name: str

    def prepare(self, client: MemoryClient) -> None:
        """Prepare a client for benchmark execution."""

    def run(self) -> EvaluationReport:
        """Run the benchmark and return a standardized report."""
