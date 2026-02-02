"""Entropy-based indexing utilities for voxel cloud clustering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

import numpy as np


@dataclass(frozen=True)
class EntropyMetrics:
    entropy: float
    normalized_entropy: float
    cluster_id: int
    octave: int


def compute_spectrum_entropy(frequency_spectrum: np.ndarray) -> float:
    """Compute Shannon entropy of a frequency spectrum."""
    if frequency_spectrum.size == 0:
        return 0.0
    magnitude = np.sqrt(frequency_spectrum[..., 0] ** 2 + frequency_spectrum[..., 1] ** 2)
    total = magnitude.sum()
    if total <= 0:
        return 0.0
    probabilities = magnitude.flatten() / total
    probabilities = probabilities[probabilities > 0]
    return float(-np.sum(probabilities * np.log2(probabilities)))


def normalize_entropy(entropy: float, num_bins: int) -> float:
    """Normalize entropy into [0, 1] using a log2 bucket count."""
    if num_bins <= 1:
        return 0.0
    max_entropy = np.log2(num_bins)
    if max_entropy <= 0:
        return 0.0
    return float(min(max(entropy / max_entropy, 0.0), 1.0))


def get_entropy_cluster(entropy: float, octave: int, num_clusters: int = 10) -> int:
    """Assign a cluster id based on entropy with octave separation."""
    normalized = normalize_entropy(entropy, num_clusters)
    bucket = min(int(normalized * num_clusters), num_clusters - 1)
    return octave * num_clusters + bucket


def analyze_proto_entropy(
    proto_identity: np.ndarray,
    frequency_spectrum: np.ndarray,
    octave: int,
    num_clusters: int = 10,
) -> EntropyMetrics:
    """Analyze proto entropy and return metrics."""
    entropy = compute_spectrum_entropy(frequency_spectrum)
    normalized = normalize_entropy(entropy, num_clusters)
    cluster_id = get_entropy_cluster(entropy, octave, num_clusters)
    return EntropyMetrics(
        entropy=entropy,
        normalized_entropy=normalized,
        cluster_id=cluster_id,
        octave=octave,
    )


def get_entropy_neighbors(
    metrics: Iterable[EntropyMetrics],
    target: EntropyMetrics,
    tolerance: float = 0.05,
) -> List[EntropyMetrics]:
    """Return metrics with similar entropy within tolerance and same octave."""
    neighbors: List[EntropyMetrics] = []
    for metric in metrics:
        if metric.octave != target.octave:
            continue
        if abs(metric.normalized_entropy - target.normalized_entropy) <= tolerance:
            neighbors.append(metric)
    return neighbors
