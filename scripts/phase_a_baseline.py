"""Bounded, local Phase A baseline; outputs JSON, never touches user storage."""

from __future__ import annotations

import json
import os
import platform
import statistics
import subprocess
import tempfile
import time
import tracemalloc
from pathlib import Path

from mneno import MemoryClient
from mneno.models import Memory
from mneno.storage import InMemoryStorage, JSONFileStorage, SQLiteStorage

REPEATS = 5


def measure(operation):
    operation()  # Warm up caches and imports outside the measured distribution.
    samples = []
    for _ in range(REPEATS):
        started = time.perf_counter()
        operation()
        samples.append((time.perf_counter() - started) * 1000)
    return {
        "samples_ms": samples,
        "median_ms": statistics.median(samples),
        "min_ms": min(samples),
        "max_ms": max(samples),
    }


def main() -> None:
    output = {
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "logical_cpus": os.cpu_count(),
            "hardware": subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"], text=True).strip(),
        },
        "repeats": REPEATS,
        "rows": [],
    }
    with tempfile.TemporaryDirectory(prefix="mneno-phase-a-") as directory:
        root = Path(directory)
        for count in (100, 1000, 10000):
            tracemalloc.start()
            memories = [
                Memory(
                    id=f"memory-{index:05}",
                    content=f"Python project component {index} uses local SQLite storage",
                    tags=["project"],
                    importance=0.5,
                )
                for index in range(count)
            ]
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            for backend in ("memory", "sqlite", "json"):
                if backend == "json" and count == 10000:
                    continue  # Bound whole-file write amplification; measure JSON through 1,000 records.
                storage = (
                    InMemoryStorage()
                    if backend == "memory"
                    else SQLiteStorage(root / f"{count}.db")
                    if backend == "sqlite"
                    else JSONFileStorage(root / f"{count}.json")
                )
                started = time.perf_counter()
                for memory in memories:
                    storage.add(memory.model_copy(deep=True))
                insertion_ms = (time.perf_counter() - started) * 1000
                assert len(storage.list()) == count
                client = MemoryClient(storage=storage, auto_detect_conflicts=False)
                row = {
                    "count": count,
                    "backend": backend,
                    "model_heap_peak_bytes": peak,
                    "store_population_ms": insertion_ms,
                    "store_population_per_second": count / (insertion_ms / 1000),
                    "search": measure(lambda client=client: client.search("Python SQLite", limit=10)),
                    "context": measure(lambda client=client: client.build_context("Python SQLite", budget=120)),
                }
                client.trace_enabled = True
                from mneno.observability import TraceRecorder

                client.trace_recorder = TraceRecorder()

                def traced_search(client=client):
                    client.clear_traces()
                    client.search("Python SQLite", limit=10)

                row["traced_search"] = measure(traced_search)
                trace = client.get_trace(client.last_trace_id)
                assert trace.status == "success"
                row["trace_event_count"] = len(trace.events)
                row["trace_json_bytes"] = len(json.dumps(client.export_trace(trace.id)).encode())
                assert len(client.search("Python SQLite", limit=10)) == 10
                output["rows"].append(row)

        # Public add includes automatic pairwise conflict detection; measure separately.
        def sdk_insert():
            client = MemoryClient()
            for index in range(100):
                client.add(f"Component {index} stores a local project fact number {index}.")
            assert len(client.list()) == 100

        output["sdk_add_100"] = measure(sdk_insert)
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
