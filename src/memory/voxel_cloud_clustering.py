"""Dynamic clustering operations for multi-octave proto-identities.

This module implements the similarity-based clustering mechanism that enables
shared proto-identities across documents at each octave level.

Architecture:
    - Similarity Wells: Proto-identities cluster when similarity ≥ 0.90
    - Resonance Tracking: Shared protos strengthen with each occurrence
    - Octave Isolation: Clustering only occurs within same octave level
    - Weighted Averaging: New protos blend via constructive interference

Core Functions:
    - find_nearest_proto(): Find matching proto at same octave
    - add_or_strengthen_proto(): Core clustering - add new or strengthen existing
    - compute_proto_similarity(): Cosine similarity calculation
    - query_by_octave(): Query for similar protos at specific octave
    - get_octave_statistics(): Statistics about clustering behavior

Storage Efficiency:
    - Character level: ~82.5% compression (e.g., 27 protos for 154 occurrences)
    - Word level: ~16.1% compression (e.g., 26 protos for 31 occurrences)
    - O(vocabulary_size) instead of O(corpus_size)

Example:
    # Add text units with automatic clustering
    for unit in units:
        entry, is_new = add_or_strengthen_proto(
            voxel_cloud, proto, freq, octave, unit
        )
        # is_new=True: new proto created
        # is_new=False: existing proto strengthened (resonance += 1)
"""

import math
import numpy as np
from typing import List, Optional, Tuple
from .voxel_cloud import VoxelCloud, ProtoIdentityEntry
from .triplanar_projection import compute_spatial_distance


class VoxelCloudClustering:
    """Simple clustering wrapper used by component tests."""

    def __init__(self) -> None:
        self.voxel_cloud = VoxelCloud()

    def get_stats(self) -> dict:
        entries = self.voxel_cloud.entries
        avg_resonance = float(np.mean([entry.resonance_strength for entry in entries])) if entries else 0.0
        return {
            "num_protos": len(entries),
            "avg_resonance": avg_resonance,
        }


def _adaptive_spatial_tolerance(octave: int, base_tolerance: float = 1.0) -> float:
    """Scale spatial tolerance based on octave level."""
    octave_scale = 1.0 + (abs(octave) * 0.15)
    return min(4.0, max(0.5, base_tolerance * octave_scale))


def _wavecube_bucket(
    wavecube_coords: Tuple[int, int, int, float],
    bucket_size: int
) -> Tuple[int, int, int]:
    """Compute WaveCube spatial hash bucket."""
    return (
        int(wavecube_coords[0] // bucket_size),
        int(wavecube_coords[1] // bucket_size),
        int(wavecube_coords[2] // bucket_size)
    )


def _iter_wavecube_candidates(
    voxel_cloud: VoxelCloud,
    wavecube_coords: Tuple[int, int, int, float],
    spatial_tolerance: float
) -> Optional[List[ProtoIdentityEntry]]:
    """Collect candidate entries using WaveCube spatial hashing."""
    if not hasattr(voxel_cloud, "wavecube_index") or not voxel_cloud.wavecube_index:
        return None

    bucket_size = max(1, getattr(voxel_cloud, "wavecube_bucket_size", 1))
    bucket = _wavecube_bucket(wavecube_coords, bucket_size)
    radius = int(math.ceil(spatial_tolerance / bucket_size))

    candidate_indices: List[int] = []
    for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
            for dz in range(-radius, radius + 1):
                neighbor = (bucket[0] + dx, bucket[1] + dy, bucket[2] + dz)
                candidate_indices.extend(voxel_cloud.wavecube_index.get(neighbor, []))

    if not candidate_indices:
        return None

    return [voxel_cloud.entries[idx] for idx in candidate_indices]


def find_nearest_proto(
    voxel_cloud: VoxelCloud,
    proto_identity: np.ndarray,
    octave: int,
    similarity_threshold: float = 0.90,
    wavecube_coords: Optional[Tuple[int, int, int, float]] = None,
    spatial_tolerance: Optional[float] = 1.0
) -> Optional[ProtoIdentityEntry]:
    """Find nearest existing proto-identity at specified octave using 3D spatial distance.

    This implements spatial clustering - if wavecube_coords are provided, uses
    3D Euclidean distance. Otherwise falls back to cosine similarity.

    Args:
        voxel_cloud: VoxelCloud instance
        proto_identity: Proto-identity to find match for (H, W, 4)
        octave: Octave level to search at
        similarity_threshold: Minimum similarity for cosine matching (0.90 = 90%)
        wavecube_coords: Optional WaveCube coordinates (x, y, z, w) for spatial clustering
        spatial_tolerance: Maximum distance for spatial match (None = adaptive)

    Returns:
        Matching ProtoIdentityEntry or None if no match found
    """
    best_match = None

    # Use spatial distance if coordinates available
    if wavecube_coords is not None:
        if spatial_tolerance is None:
            spatial_tolerance = _adaptive_spatial_tolerance(octave)

        best_distance = float('inf')

        # Create coordinate object for distance computation
        from collections import namedtuple
        WaveCubeCoordinates = namedtuple('WaveCubeCoordinates', ['x', 'y', 'z', 'w'])
        query_coords = WaveCubeCoordinates(*wavecube_coords)

        candidates = _iter_wavecube_candidates(
            voxel_cloud, wavecube_coords, spatial_tolerance
        ) or voxel_cloud.entries

        # Search only entries at the same octave with coordinates
        for entry in candidates:
            if entry.octave != octave or entry.wavecube_coords is None:
                continue

            # Convert entry coords to namedtuple
            entry_coords = WaveCubeCoordinates(*entry.wavecube_coords)

            # Compute 3D Euclidean distance
            distance = compute_spatial_distance(query_coords, entry_coords)

            if distance < best_distance:
                best_distance = distance
                best_match = entry

        # Return match only if within spatial tolerance
        if best_distance < spatial_tolerance:
            return best_match

    else:
        # Fallback to cosine similarity matching
        best_similarity = 0.0

        # Search only entries at the same octave
        for entry in voxel_cloud.entries:
            if entry.octave != octave:
                continue

            # Compute similarity
            similarity = compute_proto_similarity(proto_identity, entry.proto_identity)

            if similarity > best_similarity:
                best_similarity = similarity
                best_match = entry

        # Return match only if above threshold
        if best_similarity >= similarity_threshold:
            return best_match

    return None


def add_or_strengthen_proto(
    voxel_cloud: VoxelCloud,
    proto_identity: np.ndarray,
    frequency: np.ndarray,
    octave: int,
    unit: Optional[str] = None,
    unit_hash: Optional[str] = None,
    modality: str = 'text',
    similarity_threshold: float = 0.90,
    wavecube_coords: Optional[Tuple[int, int, int, float]] = None,
    spatial_tolerance: Optional[float] = 1.0
) -> Tuple[ProtoIdentityEntry, bool]:
    """Add new proto or strengthen existing one via spatial clustering.

    This is the core of the multi-octave clustering mechanism:
    1. Search for nearest proto at this octave (spatial distance if coords available)
    2. If found → strengthen resonance (clustering)
    3. If not → create new proto

    Args:
        voxel_cloud: VoxelCloud instance
        proto_identity: Proto-identity to add (H, W, L) - THIS IS THE UNIQUE FINGERPRINT
        frequency: Frequency spectrum (H, W, 2)
        octave: Octave level
        unit: Original unit text (optional)
        unit_hash: Hash identifier for unit (optional)
        modality: Modality type
        similarity_threshold: Clustering threshold for cosine similarity
        wavecube_coords: Optional WaveCube coordinates for spatial clustering
        spatial_tolerance: Maximum distance for spatial match (None = adaptive)

    Returns:
        (entry, is_new) tuple
        - entry: The ProtoIdentityEntry (new or existing)
        - is_new: True if new proto created, False if existing strengthened
    """
    # Search for existing similar proto (uses spatial distance if coords available)
    existing = find_nearest_proto(
        voxel_cloud,
        proto_identity,
        octave,
        similarity_threshold,
        wavecube_coords,
        spatial_tolerance
    )

    if existing:
        # Strengthen existing proto (clustering!)
        existing.resonance_strength += 1

        # Update proto via weighted average (constructive interference)
        # New contribution weighted by 1/N where N is resonance strength
        weight_new = 1.0 / existing.resonance_strength
        weight_old = 1.0 - weight_new

        existing.proto_identity = (
            weight_old * existing.proto_identity +
            weight_new * proto_identity
        )

        return existing, False

    else:
        # Create new proto-identity
        metadata = {
            'modality': modality,
            'octave': octave
        }
        if unit is not None:
            metadata['unit'] = unit
        if unit_hash is not None:
            metadata['unit_hash'] = unit_hash

        # Extract frequency signature for indexing
        from src.memory.octave_frequency import extract_fundamental, extract_harmonics
        fundamental = extract_fundamental(frequency)
        harmonics = extract_harmonics(frequency, fundamental)

        entry = voxel_cloud._create_new_entry(
            proto_identity,
            frequency,
            metadata,
            fundamental,
            harmonics
        )

        entry.octave = octave  # Set octave level
        entry.resonance_strength = 1  # Initial resonance

        # Store WaveCube coordinates if provided
        if wavecube_coords is not None:
            entry.wavecube_coords = wavecube_coords

        # Add to voxel cloud
        voxel_cloud.entries.append(entry)
        entry_idx = len(voxel_cloud.entries) - 1

        # Update spatial index
        position = entry.position
        grid_pos = tuple((position / [voxel_cloud.width, voxel_cloud.height, voxel_cloud.depth] * 10).astype(int))
        if grid_pos not in voxel_cloud.spatial_index:
            voxel_cloud.spatial_index[grid_pos] = []
        voxel_cloud.spatial_index[grid_pos].append(entry_idx)

        # Update frequency index
        freq_bin = voxel_cloud._get_frequency_bin(fundamental)
        if freq_bin not in voxel_cloud.frequency_index:
            voxel_cloud.frequency_index[freq_bin] = []
        voxel_cloud.frequency_index[freq_bin].append(entry_idx)

        # Update WaveCube spatial index
        if entry.wavecube_coords is not None:
            if hasattr(voxel_cloud, "_wavecube_bucket"):
                wavecube_bucket = voxel_cloud._wavecube_bucket(entry.wavecube_coords)
            else:
                bucket_size = max(1, getattr(voxel_cloud, "wavecube_bucket_size", 1))
                wavecube_bucket = _wavecube_bucket(entry.wavecube_coords, bucket_size)
            if wavecube_bucket not in voxel_cloud.wavecube_index:
                voxel_cloud.wavecube_index[wavecube_bucket] = []
            voxel_cloud.wavecube_index[wavecube_bucket].append(entry_idx)

        return entry, True


def compute_proto_similarity(
    proto1: np.ndarray,
    proto2: np.ndarray
) -> float:
    """Compute similarity between two proto-identities.

    Uses cosine similarity in flattened proto space.

    NOTE: This function is retained for backward compatibility.
    Consider using spatial distance clustering with WaveCube coordinates instead.

    Args:
        proto1: First proto (H, W, 4)
        proto2: Second proto (H, W, 4)

    Returns:
        Similarity score [0, 1]
    """
    # Flatten and normalize
    v1 = proto1.flatten()
    v2 = proto2.flatten()

    # Cosine similarity
    dot_product = np.dot(v1, v2)
    norm1 = np.linalg.norm(v1) + 1e-8
    norm2 = np.linalg.norm(v2) + 1e-8

    similarity = dot_product / (norm1 * norm2)

    # Map to [0, 1]
    return (similarity + 1.0) / 2.0


def query_by_octave(
    voxel_cloud: VoxelCloud,
    query_proto: np.ndarray,
    octave: int,
    max_results: int = 10,
    use_spatial_distance: bool = True,
    wavecube_coords: Optional[Tuple[int, int, int, float]] = None
) -> List[Tuple[ProtoIdentityEntry, float]]:
    """Query for similar protos at specific octave level.

    Args:
        voxel_cloud: VoxelCloud instance
        query_proto: Query proto-identity (H, W, 4)
        octave: Octave level to search
        max_results: Maximum number of results
        use_spatial_distance: If True and coords available, use spatial distance
        wavecube_coords: Optional WaveCube coordinates for spatial queries

    Returns:
        List of (entry, score) tuples
        - For spatial distance: sorted by distance (ascending, lower is better)
        - For proto similarity: sorted by similarity (descending, higher is better)
    """
    results = []

    # Use spatial distance if requested and coordinates available
    if use_spatial_distance and wavecube_coords is not None:
        # Create coordinate object for distance computation
        from collections import namedtuple
        WaveCubeCoordinates = namedtuple('WaveCubeCoordinates', ['x', 'y', 'z', 'w'])
        query_coords = WaveCubeCoordinates(*wavecube_coords)

        for entry in voxel_cloud.entries:
            if entry.octave != octave or entry.wavecube_coords is None:
                continue

            # Convert entry coords to namedtuple
            entry_coords = WaveCubeCoordinates(*entry.wavecube_coords)

            # Compute 3D Euclidean distance
            distance = compute_spatial_distance(query_coords, entry_coords)
            results.append((entry, distance))

        # Sort by distance ascending (lower is better)
        results.sort(key=lambda x: x[1])
    else:
        # Fallback to cosine similarity
        for entry in voxel_cloud.entries:
            if entry.octave != octave:
                continue

            similarity = compute_proto_similarity(query_proto, entry.proto_identity)
            results.append((entry, similarity))

        # Sort by similarity descending (higher is better)
        results.sort(key=lambda x: x[1], reverse=True)

    return results[:max_results]


def get_octave_statistics(voxel_cloud: VoxelCloud) -> dict:
    """Get statistics about proto-identities at each octave level.

    Returns:
        Dictionary with octave-level statistics
    """
    from collections import defaultdict

    stats = {
        'octave_counts': defaultdict(int),
        'octave_resonance': defaultdict(float),
        'octave_units': defaultdict(set)
    }

    for entry in voxel_cloud.entries:
        octave = entry.octave
        stats['octave_counts'][octave] += 1
        stats['octave_resonance'][octave] += entry.resonance_strength

    # Compute averages
    for octave in stats['octave_counts']:
        count = stats['octave_counts'][octave]
        stats['octave_resonance'][octave] /= count

    return stats
