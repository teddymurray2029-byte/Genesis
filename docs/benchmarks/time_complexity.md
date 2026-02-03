# Wavecube Time Complexity & Execution Benchmarks

## Scope
This report benchmarks Wavecube interpolation and save/load operations and documents their expected time complexity. The measurements are intentionally lightweight to run in constrained environments.

## Method
Benchmarks are run via `scripts/benchmark_time_complexity.py`, which:
- Builds a sparse `WavetableMatrix` with a 4×4×4 grid and 25% fill.
- Measures interpolation latency for 200 random samples.
- Measures save/load performance using the existing `benchmark_save_load` utility.

## Time Complexity Summary
| Operation | Expected Complexity | Notes |
| --- | --- | --- |
| Single-sample interpolation | **O(H × W × C)** | Trilinear interpolation blends 8 wavetables with elementwise operations across the wavetable resolution (H×W) and channels (C). |
| Batch interpolation | **O(N × H × W × C)** | Repeats single-sample interpolation for N coordinates. |
| Save/load (NPZ) | **O(K × H × W × C)** | Serializes K populated nodes, each containing a full wavetable array. |

## Execution Results (Local)
Command:

```bash
PYTHONPATH=lib python scripts/benchmark_time_complexity.py
```

### Interpolation Benchmark
| Resolution | Samples | Total Time (s) | Avg Time (ms) | Samples/sec |
| --- | --- | --- | --- | --- |
| 32 | 200 | 0.0109 | 0.0543 | 18422.5 |
| 64 | 200 | 0.0176 | 0.0881 | 11349.7 |

### Save/Load Benchmark
| Resolution | Nodes | Avg Save (ms) | Avg Load (ms) | Avg File Size (MB) |
| --- | --- | --- | --- | --- |
| 32 | 16 | 7.51 | 4.91 | 0.24 |
| 64 | 16 | 37.91 | 11.83 | 0.93 |

## Notes
- Results scale with wavetable resolution because interpolation and serialization operate on the full H×W×C array.
- Measurements are intended for relative comparisons; exact timings vary by hardware.
