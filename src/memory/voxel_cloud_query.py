"""Query and search operations for VoxelCloud."""
import base64
import json
import sqlite3
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional

import numpy as np

from .voxel_helpers import compute_cosine_similarity, resize_proto
from . import voxel_cloud_collapse as collapse_ops


def find_by_frequency(
    voxel_cloud,
    query_freq: float,
    query_harmonics: np.ndarray,
    octave_tolerance: int = 1,
    harmonic_tolerance: float = 0.3,
    max_results: int = 10
) -> List:
    """
    Find proto-identities by frequency signature matching using spatial hash.
    O(k * octaves) where k = entries per voxel, not O(n).

    Args:
        voxel_cloud: VoxelCloud instance
        query_freq: Query fundamental frequency
        query_harmonics: Query harmonic coefficients (length 10)
        octave_tolerance: How many octaves to search (±1 = search 0.5x to 2x)
        harmonic_tolerance: Max harmonic difference threshold
        max_results: Maximum results to return

    Returns:
        List of matching entries, sorted by similarity
    """
    return collapse_ops.find_by_frequency_internal(
        voxel_cloud, query_freq, query_harmonics,
        octave_tolerance, harmonic_tolerance, max_results
    )


def query_by_proto_similarity(voxel_cloud, query_proto: np.ndarray, max_results: int = 10,
                             similarity_metric: str = 'l2') -> List:
    """
    Query voxel cloud by direct proto-identity similarity.

    This is the correct approach: compare query proto-identity directly to stored
    proto-identities using the standing wave representation from Gen ∪ Res.

    Args:
        voxel_cloud: VoxelCloud instance
        query_proto: Query proto-identity (standing wave from morphisms)
        max_results: Maximum number of results
        similarity_metric: 'l2' (default, FFT-friendly) or 'cosine'

    Returns:
        List of most similar proto-identities
    """
    if len(voxel_cloud.entries) == 0:
        return []

    similarities = []
    for entry in voxel_cloud.entries:
        if similarity_metric == 'cosine':
            # Cosine similarity (like gravitational collapse uses)
            sim = compute_cosine_similarity(query_proto, entry.proto_identity)
            similarities.append((sim, entry))
        else:  # L2 distance
            diff = np.linalg.norm(query_proto - entry.proto_identity)
            # Convert to similarity (higher is better)
            sim = 1.0 / (diff + 1e-6)
            similarities.append((sim, entry))

    # Sort by similarity (descending) and return top matches
    similarities.sort(key=lambda x: x[0], reverse=True)
    return [entry for _, entry in similarities[:max_results]]


def _encode_array(value: np.ndarray) -> str:
    payload = {
        "b64": base64.b64encode(value.tobytes()).decode("ascii"),
        "shape": list(value.shape),
        "dtype": str(value.dtype),
    }
    return json.dumps(payload)


def _encode_mip_levels(levels: List[np.ndarray]) -> str:
    payload = [
        {
            "b64": base64.b64encode(level.tobytes()).decode("ascii"),
            "shape": list(level.shape),
            "dtype": str(level.dtype),
        }
        for level in levels
    ]
    return json.dumps(payload)


def _create_entries_snapshot(voxel_cloud) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE entries (
            entry_index INTEGER PRIMARY KEY,
            id TEXT,
            modality TEXT,
            octave INTEGER,
            fundamental_freq REAL,
            resonance_strength INTEGER,
            frequency_band INTEGER,
            position_x REAL,
            position_y REAL,
            position_z REAL,
            coherence REAL,
            timestamp REAL,
            current_state TEXT,
            wavecube_x INTEGER,
            wavecube_y INTEGER,
            wavecube_z INTEGER,
            wavecube_w REAL,
            cross_modal_links TEXT,
            cross_modal_links_json TEXT,
            metadata_json TEXT,
            proto_identity_json TEXT,
            frequency_json TEXT,
            position_json TEXT,
            mip_levels_json TEXT
        )
        """
    )

    for entry_index, entry in enumerate(voxel_cloud.entries):
        metadata = entry.metadata or {}
        wavecube_coords = entry.wavecube_coords or (None, None, None, None)
        cross_modal_links = ",".join(entry.cross_modal_links)
        cross_modal_links_json = json.dumps(entry.cross_modal_links, default=str)
        metadata_json = json.dumps(metadata, default=str)
        proto_identity_json = _encode_array(entry.proto_identity)
        frequency_json = _encode_array(entry.frequency)
        position_json = _encode_array(entry.position)
        mip_levels_json = _encode_mip_levels(entry.mip_levels)

        cursor.execute(
            """
            INSERT INTO entries (
                entry_index,
                id,
                modality,
                octave,
                fundamental_freq,
                resonance_strength,
                frequency_band,
                position_x,
                position_y,
                position_z,
                coherence,
                timestamp,
                current_state,
                wavecube_x,
                wavecube_y,
                wavecube_z,
                wavecube_w,
                cross_modal_links,
                cross_modal_links_json,
                metadata_json,
                proto_identity_json,
                frequency_json,
                position_json,
                mip_levels_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry_index,
                metadata.get("id", str(id(entry))),
                entry.modality,
                entry.octave,
                entry.fundamental_freq,
                entry.resonance_strength,
                entry.frequency_band,
                float(entry.position[0]),
                float(entry.position[1]),
                float(entry.position[2]),
                entry.coherence_vs_core,
                metadata.get("timestamp"),
                entry.current_state.name if entry.current_state else None,
                wavecube_coords[0],
                wavecube_coords[1],
                wavecube_coords[2],
                wavecube_coords[3],
                cross_modal_links,
                cross_modal_links_json,
                metadata_json,
                proto_identity_json,
                frequency_json,
                position_json,
                mip_levels_json
            )
        )

    connection.commit()
    return connection


def query_by_sql_with_columns(
    voxel_cloud,
    sql: str,
    params: Optional[Iterable[Any]] = None
) -> tuple[List[Dict[str, Any]], List[str]]:
    """
    Query voxel cloud metadata using SQL against an in-memory snapshot.

    Args:
        voxel_cloud: VoxelCloud instance
        sql: SQL query string targeting the "entries" table
        params: Optional query parameters for sqlite placeholders

    Returns:
        Tuple of result rows as dictionaries and column names.
    """
    connection = _create_entries_snapshot(voxel_cloud)
    cursor = connection.cursor()
    cursor.execute(sql, params or ())
    rows = [dict(row) for row in cursor.fetchall()]
    columns = [column[0] for column in cursor.description] if cursor.description else []
    connection.close()
    return rows, columns


def query_by_sql(
    voxel_cloud,
    sql: str,
    params: Optional[Iterable[Any]] = None
) -> List[Dict[str, Any]]:
    """
    Query voxel cloud metadata using SQL against an in-memory snapshot.

    Args:
        voxel_cloud: VoxelCloud instance
        sql: SQL query string targeting the "entries" table
        params: Optional query parameters for sqlite placeholders

    Returns:
        List of result rows as dictionaries
    """
    rows, _ = query_by_sql_with_columns(voxel_cloud, sql, params)
    return rows


def query_viewport(voxel_cloud, query_freq: np.ndarray, radius: float = 50.0,
                  max_results: int = 10, use_frequency_matching: bool = False,
                  query_proto: np.ndarray = None) -> List:
    """
    Query voxel cloud with a viewport centered on query frequency.

    Args:
        voxel_cloud: VoxelCloud instance
        query_freq: Query frequency spectrum
        radius: Viewport radius in voxel space
        max_results: Maximum number of results
        use_frequency_matching: If True, use frequency-based matching instead of spatial
        query_proto: If provided, use proto-identity similarity matching (RECOMMENDED)

    Returns:
        List of visible proto-identities within viewport
    """
    # NEW: Proto-identity similarity matching (the correct approach!)
    if query_proto is not None:
        return query_by_proto_similarity(voxel_cloud, query_proto, max_results, similarity_metric='cosine')

    if use_frequency_matching:
        # Use frequency-based matching
        from src.memory.octave_frequency import extract_fundamental, extract_harmonics
        f0 = extract_fundamental(query_freq)
        harmonics = extract_harmonics(query_freq, f0)
        return find_by_frequency(voxel_cloud, f0, harmonics, max_results=max_results)
    else:
        # Existing spatial query code
        query_pos = voxel_cloud._frequency_to_position(query_freq)

        # Find entries within radius
        visible = []
        distances = []

        for entry in voxel_cloud.entries:
            dist = np.linalg.norm(entry.position - query_pos)
            if dist <= radius:
                visible.append(entry)
                distances.append(dist)

        # Sort by distance and limit results
        if visible:
            sorted_indices = np.argsort(distances)[:max_results]
            visible = [visible[i] for i in sorted_indices]

        return visible


def query_multi_octave(voxel_cloud, query_quaternions: Dict[int, np.ndarray],
                      top_k: int = 10,
                      octave_weights: Optional[Dict[int, float]] = None) -> List:
    """Query using multi-octave quaternions.

    Args:
        voxel_cloud: VoxelCloud instance
        query_quaternions: Dict mapping octave → query quaternion
        top_k: Number of results to return
        octave_weights: Optional weights for each octave

    Returns:
        List of matching proto-identities with distances
    """
    return voxel_cloud.octave_hierarchy.multi_octave_query(
        query_quaternions, top_k, octave_weights
    )


def query_by_raycast(voxel_cloud, projection_matrix, max_results: int = 10) -> List:
    """
    Query using raycast-based frustum culling (Phase 5).

    Replaces simple radius queries with frustum-based visibility testing.

    Args:
        voxel_cloud: VoxelCloud instance
        projection_matrix: ProjectionMatrix instance with camera setup
        max_results: Maximum number of results

    Returns:
        List of visible proto-identities within frustum
    """
    visible = []

    for entry in voxel_cloud.entries:
        # Test if voxel is visible in frustum
        if projection_matrix.is_voxel_visible(entry.position, voxel_size=5.0):
            # Compute LOD level based on distance
            lod_level = projection_matrix.compute_lod_level(entry.position)

            # Add to visible set with LOD info
            visible.append((entry, lod_level))

    # Sort by distance from camera (closest first)
    camera_pos = projection_matrix.position
    visible.sort(key=lambda x: np.linalg.norm(x[0].position - camera_pos))

    # Return top results
    return [entry for entry, _ in visible[:max_results]]


def query_by_frequency_band(voxel_cloud, band: int, max_results: int = 10) -> List:
    """
    Query by frequency band (Phase 5).

    Args:
        voxel_cloud: VoxelCloud instance
        band: Frequency band (0=LOW, 1=MID, 2=HIGH)
        max_results: Maximum number of results

    Returns:
        List of proto-identities in specified band
    """
    from .frequency_bands import FrequencyBand

    # Validate band
    if band not in [0, 1, 2]:
        raise ValueError(f"Invalid band {band}. Must be 0 (LOW), 1 (MID), or 2 (HIGH)")

    # Filter entries by band
    band_enum = FrequencyBand(band)
    results = voxel_cloud.frequency_bands.cluster_by_band(voxel_cloud, band_enum)

    # Sort by resonance strength (most resonant first)
    results.sort(key=lambda x: x.resonance_strength, reverse=True)

    return results[:max_results]


def find_cross_modal_links(voxel_cloud, entry) -> List:
    """
    Find cross-modal linked proto-identities.

    Args:
        voxel_cloud: VoxelCloud instance
        entry: Proto-identity to find links for

    Returns:
        List of linked proto-identities from other modalities
    """
    linked = []
    entry_id = entry.metadata.get('id', str(id(entry)))

    for other in voxel_cloud.entries:
        if other.modality != entry.modality:
            other_id = other.metadata.get('id', str(id(other)))
            if other_id in entry.cross_modal_links or entry_id in other.cross_modal_links:
                linked.append(other)

    return linked


def link_cross_modal_protos(voxel_cloud, phase_coherence_threshold: float = 0.1) -> int:
    """
    Link proto-identities across modalities via phase coherence.

    Protos with same fundamental frequency (within threshold)
    across different modalities are automatically linked.

    Args:
        voxel_cloud: VoxelCloud instance
        phase_coherence_threshold: Max frequency difference for linking

    Returns:
        Number of cross-modal links established
    """
    # Group by modality
    by_modality = defaultdict(list)
    for entry in voxel_cloud.entries:
        by_modality[entry.modality].append(entry)

    links_created = 0

    # For each text proto, find matching image/audio protos
    for text_proto in by_modality.get('text', []):
        f0_text = text_proto.fundamental_freq
        text_id = text_proto.metadata.get('id', str(id(text_proto)))

        # Find images with matching frequency
        for img_proto in by_modality.get('image', []):
            img_id = img_proto.metadata.get('id', str(id(img_proto)))
            freq_diff = abs(img_proto.fundamental_freq - f0_text)

            if freq_diff < phase_coherence_threshold:
                # Phase-locked: link them
                if img_id not in text_proto.cross_modal_links:
                    text_proto.cross_modal_links.append(img_id)
                    links_created += 1
                if text_id not in img_proto.cross_modal_links:
                    img_proto.cross_modal_links.append(text_id)

        # Find audio with matching frequency
        for audio_proto in by_modality.get('audio', []):
            audio_id = audio_proto.metadata.get('id', str(id(audio_proto)))
            freq_diff = abs(audio_proto.fundamental_freq - f0_text)

            if freq_diff < phase_coherence_threshold:
                if audio_id not in text_proto.cross_modal_links:
                    text_proto.cross_modal_links.append(audio_id)
                    links_created += 1
                if text_id not in audio_proto.cross_modal_links:
                    audio_proto.cross_modal_links.append(text_id)

    return links_created
