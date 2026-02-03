"""
Benchmark time complexity and execution time for wavecube operations.

Runs lightweight benchmarks suitable for CI and local runs with limited
resources. Results are printed as Markdown tables.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterable, List

import numpy as np

from wavecube.core.matrix import WavetableMatrix
from wavecube.utils import benchmarks as wave_benchmarks


@dataclass
class InterpolationResult:
    resolution: int
    num_samples: int
    total_time_s: float
    avg_time_ms: float
    samples_per_second: float


@dataclass
class SaveLoadResult:
    resolution: int
    num_nodes: int
    avg_save_time_ms: float
    avg_load_time_ms: float
    avg_file_size_mb: float


def _make_matrix(resolution: int, grid_size: int, fill_ratio: float = 0.25) -> WavetableMatrix:
    matrix = WavetableMatrix(width=grid_size, height=grid_size, depth=grid_size, resolution=resolution, sparse=True)
    num_nodes = int((grid_size ** 3) * fill_ratio)

    rng = np.random.default_rng(42)
    populated = 0

    while populated < num_nodes:
        x, y, z = rng.integers(0, grid_size, size=3)
        if not matrix.has_node(int(x), int(y), int(z)):
            wavetable = rng.standard_normal((resolution, resolution, 4), dtype=np.float32)
            matrix.set_node(int(x), int(y), int(z), wavetable)
            populated += 1

    return matrix


def benchmark_interpolation(matrix: WavetableMatrix, num_samples: int) -> InterpolationResult:
    rng = np.random.default_rng(123)
    coords = rng.random((num_samples, 3))
    coords[:, 0] *= matrix.width
    coords[:, 1] *= matrix.height
    coords[:, 2] *= matrix.depth

    # Warm-up
    for i in range(min(5, num_samples)):
        x, y, z = coords[i]
        try:
            matrix.sample(float(x), float(y), float(z))
        except RuntimeError:
            pass

    start = time.perf_counter()
    for i in range(num_samples):
        x, y, z = coords[i]
        try:
            matrix.sample(float(x), float(y), float(z))
        except RuntimeError:
            pass
    elapsed = time.perf_counter() - start

    return InterpolationResult(
        resolution=matrix.resolution[0],
        num_samples=num_samples,
        total_time_s=elapsed,
        avg_time_ms=(elapsed / num_samples) * 1000,
        samples_per_second=num_samples / elapsed,
    )


def benchmark_save_load(matrix: WavetableMatrix) -> SaveLoadResult:
    results = wave_benchmarks.benchmark_save_load(matrix)
    return SaveLoadResult(
        resolution=matrix.resolution[0],
        num_nodes=matrix._stats["num_nodes"],
        avg_save_time_ms=results["avg_save_time_ms"],
        avg_load_time_ms=results["avg_load_time_ms"],
        avg_file_size_mb=results["avg_file_size_mb"],
    )


def print_table(headers: List[str], rows: Iterable[Iterable[str]]) -> None:
    header_line = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"
    print(header_line)
    print(separator)
    for row in rows:
        print("| " + " | ".join(row) + " |")


if __name__ == "__main__":
    resolutions = [32, 64]
    grid_size = 4
    num_samples = 200

    interpolation_results: List[InterpolationResult] = []
    save_load_results: List[SaveLoadResult] = []

    for resolution in resolutions:
        matrix = _make_matrix(resolution=resolution, grid_size=grid_size)
        interpolation_results.append(benchmark_interpolation(matrix, num_samples=num_samples))
        save_load_results.append(benchmark_save_load(matrix))

    print("## Interpolation Benchmark")
    print_table(
        ["Resolution", "Samples", "Total Time (s)", "Avg Time (ms)", "Samples/sec"],
        [
            [
                str(r.resolution),
                str(r.num_samples),
                f"{r.total_time_s:.4f}",
                f"{r.avg_time_ms:.4f}",
                f"{r.samples_per_second:.1f}",
            ]
            for r in interpolation_results
        ],
    )

    print("\n## Save/Load Benchmark")
    print_table(
        ["Resolution", "Nodes", "Avg Save (ms)", "Avg Load (ms)", "Avg File Size (MB)"],
        [
            [
                str(r.resolution),
                str(r.num_nodes),
                f"{r.avg_save_time_ms:.2f}",
                f"{r.avg_load_time_ms:.2f}",
                f"{r.avg_file_size_mb:.2f}",
            ]
            for r in save_load_results
        ],
    )
