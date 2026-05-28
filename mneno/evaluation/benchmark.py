"""Benchmark runner helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from mneno.evaluation.adapters import BenchmarkAdapter
from mneno.evaluation.reports import EvaluationReport

if TYPE_CHECKING:
    from mneno.client import MemoryClient


def run_benchmark(adapter: BenchmarkAdapter, client: MemoryClient) -> EvaluationReport:
    """Run a benchmark adapter against a client."""
    adapter.prepare(client)
    return adapter.run()
