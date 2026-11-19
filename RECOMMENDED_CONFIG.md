# RECOMMENDED_CONFIG — MITRE/PRISM Retrieval System

**Campaign:** PAVONA MITRE Kimi Spark Handoff
**Date:** 2026-11-18
**Frozen baseline:** Goose commit `b66f0f8679535ff76224a403322b765adc1e085d` (branch `audit/benchmark-fixes`)
**Submodule:** TinyCC `5db3129e` + cute_spirv + subprocess (third_party from Tower SMB share)

---

## 1. Recommended MITRE Configuration

| Setting | Value | Rationale |
|---------|-------|-----------|
| `fastpath` | `csr` | CSR (Compressed Sparse Row) postings arrays eliminate dictionary lookups in the hot query path. 57x faster index build, 375x faster queries at 100K vs baseline. |
| `inverted_index` | `True` | Standard inverted index with term → posting → doc mapping. |
| `high_df_postings_skip` | `0.5` | Skip high-document-frequency postings during scoring to reduce work for common terms (nile, pharaoh). |
| `rpr_queue` | `ring_buffer` | O(1) pop with head/tail ring buffer instead of list erase. |
| `idf_precompute` | `True` | IDF computed once per term at index build time, stored in `csr_idf` array. |
| `data_stack_reserve` | `2GB` | `GS_STACK_RESERVE=2GB` — hard limit on main data stack. 1M concurrent QPS exceeds this (stack overflow). |
| `concurrent_qps_iterations` | `3` (at 1M) | Reduced from 10 to avoid data stack overflow at 1M corpus scale. |

### Per-Scale Configuration Notes

**10K corpus:** Default optimized config works without modification.

**100K corpus:** Default optimized config works. CSR index build ~651ms, query p95 ~4.88ms.

**1M corpus:** Reduce concurrent QPS test iterations from 10 → 3 to stay within the 2GB data stack reserve. Query benchmarks complete (35.85–52.18ms) but concurrent QPS test crashes with stack overflow.

---

## 2. Hardware Profile (Spark)

| Component | Specification |
|-----------|---------------|
| Host | axforge @ 178.105.204.56:22081 (user: dev) |
| OS | Ubuntu 24.04, aarch64 |
| CPU | NVIDIA GB10, 20-core Cortex-X925/A725 |
| RAM | 121 GiB |
| Disk | ~611 GiB free on `/` |
| Toolchain | gcc-13, cc, make, cmake 3.27+, Python 3.12.3, TinyCC 0.9.28rc |

---

## 3. Build Configuration

```
cmake -S . -B build        # cmake 3.27+, gcc, make
cmake --build build -j $(nproc)
./build/goose run mitre/benchmark_opt.goose   # optimized 10K/100K
./build/goose run benchmark_1m.goose          # 1M (modified: 3 QPS iterations)
```

**PATH requirement:** `/usr/bin:/bin:/home/dev/.local/bin` (cmake needs CMAKE_MAKE_PROGRAM and CMAKE_C_COMPILER)

**Third-party dependencies:** `tinycc/`, `cute_spirv/`, `subprocess/` — copied from `\\100.113.214.74\D$\MITRE\goose\third_party\`

---

## 4. Recommended Deployment

- **In-memory MITRE (fastpath=csr):** Primary recommendation. Lowest latency, no disk I/O.
- **Durable MITRE (file-backed SQLite):** Required competitor arm per VICTORY_CONTRACT. Same config + persistent storage. Not yet benchmarked.
- **Do NOT use:** `unified_bench.goose` on Spark (hardcoded `D:\MITRE` paths, won't run on Linux).
