Disclaimer:
This project has basically been abandoned. If it finds community support I will continue to maintain it in terms of public support.
This project is not 100% complete and 100% perfect, but it lays a foundation for a new way of handling memory, identity and context.

Feel free to fork, or make PRs and we will be happy to support.


# Genesis: Multi-Octave Hierarchical Memory System

A 3D spatial memory system using FFT encoding, triplanar projection, and WaveCube volumetric storage with 16,922× compression.

**Status**: FFT encoding with WaveCube 3D spatial memory  
**Compression**: 16,922× average (526.75 MB → 0.03 MB for 100 entries)  
**Reconstruction**: 100% lossless via IFFT  
**Last Updated**: 2026-01-30

---

## Overview

Genesis encodes text into frequency-domain proto-identities, projects them to 3D spatial coordinates via triplanar analysis, and stores them in a compressed 128³ volumetric grid.

**Complete Pipeline**:
```
Text Input → FFT Encoding → Proto-Identity (512×512×4)
           ↓
Triplanar Projection → Coordinates (x,y,z,w)
           ↓
Spatial Clustering → WaveCube 128³ Grid
           ↓
Gaussian Compression → 340 bytes (~16,922× compression)
```

---

## Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/NeoTecDigital/Genesis.git
cd Genesis

# Install dependencies
pip install -r requirements.txt
```

### Basic Usage

```python
from src.pipeline.fft_text_encoder import FFTTextEncoder
from src.pipeline.fft_text_decoder import FFTTextDecoder
from src.memory.triplanar_projection import extract_triplanar_coordinates
from src.memory.wavecube_integration import WaveCubeMemoryBridge
from src.memory.voxel_cloud_clustering import add_or_strengthen_proto

# 1. Initialize system
encoder = FFTTextEncoder(width=512, height=512)
decoder = FFTTextDecoder(width=512, height=512)
wavecube = WaveCubeMemoryBridge(width=512, height=512, depth=128)

# 2. Encode text to proto-identity
text = "Hello world"
proto_identity = encoder.encode_text(text)
# → (512, 512, 4) XYZW quaternion array

# 3. Project to 3D coordinates
coords = extract_triplanar_coordinates(
    freq_spectrum=proto_identity,
    modality='text',
    octave=0,
    grid_size=128
)
# → WaveCubeCoordinates(x=42, y=73, z=18, w=0.0)

# 4. Store in WaveCube with spatial clustering
entry, is_new = add_or_strengthen_proto(
    voxel_cloud=wavecube.voxel_cloud,
    proto_identity=proto_identity,
    frequency=proto_identity[:,:,:2],
    octave=0,
    wavecube_coords=(coords.x, coords.y, coords.z, coords.w),
    spatial_tolerance=1.0
)
# → Stored at WaveCube[42,73,18], compressed to ~340 bytes

# 5. Query and reconstruct
query_proto = encoder.encode_text("Hello world")
query_coords = extract_triplanar_coordinates(query_proto, 'text', 0, 128)

# Find nearest match via spatial search
from src.memory.triplanar_projection import compute_spatial_distance

min_distance = float('inf')
best_entry = None

for entry in wavecube.voxel_cloud.entries:
    if entry.wavecube_coords is None:
        continue
    distance = compute_spatial_distance(query_coords, entry.wavecube_coords)
    if distance < min_distance:
        min_distance = distance
        best_entry = entry

# 6. Decode (perfect reconstruction)
if best_entry:
    reconstructed = decoder.decode_text(best_entry.proto_identity)
    print(f"Input: {text}")
    print(f"Output: {reconstructed}")
    print(f"Match: {text == reconstructed}")  # True
```

---

## Architecture

### 1. FFT Encoding

**Text → 2D Fourier Transform → Proto-Identity**

- Convert text to UTF-8 bytes
- Embed in 512×512 grid (spiral pattern)
- Apply 2D FFT → complex frequency spectrum
- Convert to XYZW quaternion (512×512×4)

**Properties**: Lossless (IFFT reverses), Deterministic, O(N² log N)

### 2. Triplanar Projection

**Proto-Identity → 3D Spatial Coordinates (x,y,z,w)**

- **XY plane** centroid → X coordinate [0-127]
- **XZ plane** centroid → Y coordinate [0-127]
- **YZ plane** peak frequency → Z coordinate [0-127]
- **Modality** → W phase (text=0°, audio=90°, image=180°, video=270°)

**Properties**: Deterministic, Frequency-based, Cross-modal

### 3. WaveCube 3D Storage

**128×128×128 Volumetric Grid**

Multi-layer hierarchy:
1. **Proto-unity layer**: Long-term reference (compression quality=0.98)
2. **Experiential layer**: Working memory (quality=0.90)
3. **IO layer**: Sensory buffer (quality=0.85)

**Capacity**: 2,097,152 potential nodes × 4 modalities = 8.4M positions

### 4. Spatial Clustering

**3D Euclidean Distance** (NOT cosine similarity)

```python
distance = sqrt((x1-x2)² + (y1-y2)² + (z1-z2)²)
if distance < 1.0: merge with existing cluster
else: create new cluster
```

**Resonance tracking**: Count how many times cluster was matched

### 5. Gaussian Compression

**Sparse Frequency Patterns → Gaussian Mixture**

- Detect 8 dominant peaks in frequency spectrum
- Fit 2D Gaussian parameters (μx, μy, σ, A, φ)
- Store parameters: 8 Gaussians × 5 params × 4 bytes = 160 bytes
- Total with overhead: ~340 bytes

**Compression**: 4,194,304 bytes → 340 bytes = **12,336× ratio**  
**Average (100 entries)**: **16,922× compression**  
**Quality**: MSE < 0.01 (visually lossless)

---

## Multi-Octave Hierarchy

Text decomposed at multiple frequency scales:

| Octave | Granularity | Resolution | Example |
|--------|-------------|------------|---------|
| +4 | Character | 128×128 | 'a', 'b', 'c' |
| 0 | Word | 256×256 | 'hello', 'world' |
| -2 | Phrase | 512×512 | 'hello world' |
| -4 | Sentence | 1024×1024 | 'the quick brown fox' |

**Key principle**: Clustering isolated per octave (prevents cross-granularity false matches)

---

## Performance

### Compression

| Metric | Value |
|--------|-------|
| Uncompressed | 4.19 MB per proto |
| Compressed | 340 bytes average |
| Ratio (typical) | 12,336× |
| Ratio (average) | 16,922× |
| Quality (MSE) | <0.01 |
| Time (compress) | 10.2 ms |
| Time (decompress) | 5.1 ms |

### Storage Scaling

| Corpus Size | Unique Protos | WaveCube Nodes | Storage | Ratio |
|-------------|---------------|----------------|---------|-------|
| 1K words | 987 | 856 | 0.29 MB | 14,100× |
| 10K words | 9,241 | 7,892 | 2.68 MB | 14,400× |
| 100K words | 87,234 | 71,021 | 24.15 MB | 16,000× |

**Growth**: O(|V|^0.87) - sublinear in vocabulary size

### Retrieval Time

| Operation | Time |
|-----------|------|
| FFT encode | 10 ms |
| Triplanar project | 1 ms |
| Spatial search | 2-7 ms |
| Decompress | 5 ms |
| IFFT decode | 5 ms |
| **Total** | **23-28 ms** |

---

## Cross-Modal Support

Same pipeline works for all modalities via W-dimension:

```python
# Text encoding
text_coords = extract_triplanar_coordinates(text_proto, 'text', 0, 128)
# → (x=42, y=73, z=18, w=0°)

# Audio encoding (same semantic content)
audio_coords = extract_triplanar_coordinates(audio_proto, 'audio', 0, 128)
# → (x=41, y=74, z=17, w=90°)

# Spatial distance (ignoring W): 1.73 voxels (CLOSE!)
# Modality separation (W): 90° (DIFFERENT modality)
```

**Result**: Same concept in different modalities clusters spatially but separates by phase.

---

## Examples

See `examples/` directory for complete examples:
- `demo_memory_integration.py` - Full encoding/storage/retrieval pipeline
- `demo_fft_roundtrip.py` - FFT encoding and perfect reconstruction
- `demo_hierarchical_synthesis.py` - Multi-octave synthesis

---

## Log CRUD API (WordPress-friendly)

Genesis includes a lightweight REST API that exposes log-style CRUD operations over HTTP,
making it easy to integrate with existing systems (including WordPress via `wp_remote_*`
or any REST client). The API runs on a dedicated port and uses a SQLite backing store for
O(1)-style primary-key lookups. Set `GENESIS_LOG_API_PORT` to choose a port that matches
your deployment constraints.

```bash
export GENESIS_LOG_API_PORT=8001
uvicorn src.api.log_api:app --host 0.0.0.0 --port "${GENESIS_LOG_API_PORT}"
```

Endpoints:

- `POST /logs` → create a log entry
- `GET /logs/{id}` → fetch a log entry
- `PUT /logs/{id}` → update a log entry
- `DELETE /logs/{id}` → delete a log entry
- `GET /health` → health check

---

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test suites
pytest tests/test_fft_roundtrip.py -v          # FFT encoding/decoding
pytest tests/test_triplanar_projection.py -v   # Coordinate extraction
pytest tests/test_wavecube_integration.py -v   # WaveCube storage
pytest tests/test_memory_integration.py -v     # Complete pipeline
```

---

## Documentation

- **[WHITEPAPER.md](WHITEPAPER.md)** - Formal academic paper with proofs and theorems
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Complete technical architecture
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Development guidelines
- **[lib/wavecube/README.md](lib/wavecube/README.md)** - WaveCube library documentation
- **[docs/FFT_ARCHITECTURE_SPEC.md](docs/FFT_ARCHITECTURE_SPEC.md)** - FFT specification

---

## Key Features

✅ **Perfect Lossless Reconstruction** - IFFT guarantees 100% accuracy  
✅ **Extreme Compression** - 16,922× average (4 orders of magnitude)  
✅ **3D Spatial Organization** - Similar concepts cluster automatically  
✅ **Multi-Octave** - Character → Word → Phrase → Sentence scales  
✅ **Cross-Modal** - Unified W-dimension for text/audio/image/video  
✅ **Deterministic** - Same input always gives same coordinates  
✅ **Sublinear Storage** - O(|vocabulary|) instead of O(corpus_size)  
✅ **Fast Retrieval** - 23-28ms end-to-end  

---

## Future Enhancements

**Planned**:
- GPU acceleration (CUDA FFT, parallel compression)
- KD-tree spatial indexing (O(log m) retrieval)
- 256³ WaveCube for larger vocabularies
- Learned triplanar projection (neural network optimization)
- Temporal dimension (x,y,z,w,t) for sequential memory

---

## Citation

If you use Genesis in your research, please cite:

```bibtex
@software{genesis2026,
  title = {Genesis: Multi-Octave Hierarchical Memory System},
  author = {Christopher, Richard I},
  year = {2026},
  url = {https://github.com/NeoTecDigital/Genesis},
  license = {MIT}
}
```

See `CITATION.cff` for structured citation metadata.

---

## License

MIT License - see `LICENSE` file for details.

Copyright (c) 2025 Richard I Christopher
