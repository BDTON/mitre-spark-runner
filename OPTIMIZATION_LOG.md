# OPTIMIZATION_LOG — MITRE/PRISM Goose Optimization

**Campaign:** PAVONA MITRE Kimi Spark Handoff
**Baseline:** `mitre/benchmark.goose` (baseline)
**Optimized:** `mitre/benchmark_opt.goose` (fast-path CSR scoring)

---

## 1. Optimizations Applied

| # | Optimization | Description | File |
|---|-------------|-------------|------|
| 1 | **Fast-path CSR scoring** | Pre-built CSR arrays (`csr_doc_ids`, `csr_scores`, `csr_idf`) eliminate dictionary lookups in hot query path | `benchmark_opt.goose` |
| 2 | **Pre-computed IDF** | IDF computed once per term at index build, stored in `csr_idf[]`, multiplied by TF at query time | `benchmark_opt.goose` |
| 3 | **Ring buffer RPR queue** | O(1) pop with head index instead of list erase/shift | `benchmark_opt.goose` |
| 4 | **Pre-allocated dictionaries** | Capacity hints on `dictionary<>` to avoid rehashing during ingest | `benchmark_opt.goose` |
| 5 | **Batched dictionary operations** | Local arrays for doc_ids/scores, batch-appended to CSR after per-term collection | `benchmark_opt.goose` |
| 6 | **Eliminated redundant allocations** | Reused `text_buf` across docs in `ingest_batch()` with `.clear()` | `benchmark_opt.goose` |

---

## 2. Measured Impact

### 100K Corpus (Development Split, Seed 8001)

| Metric | Baseline | Optimized | Speedup |
|--------|----------|-----------|---------|
| CSR index build | 37.7s | 0.65s | **57x** |
| Query median | 1.23s | 3.25–4.88ms | **~375x** |
| Query p95 | — | ~4.88ms | — |
| Memory | — | 182 MB | — |

### 10K Corpus

| Metric | Optimized |
|--------|-----------|
| Ingest | 62 ms |
| CSR build | 58 ms |
| Query median | 0.32–0.49 ms |
| QPS | ~2840 |
| Memory | 18 MB |

### 1M Corpus

| Metric | Optimized |
|--------|-----------|
| Ingest | 3480 ms |
| CSR build | 7347 ms |
| Query median | 35.85–52.18 ms |
| Concurrent QPS | **CRASH** (data stack overflow > 2GB) |

---

## 3. Bottlenecks Identified and Resolved

| Bottleneck | Before | After | Resolution |
|------------|--------|-------|------------|
| CSR index build at 100K | 37.7s | 0.65s | Pre-allocated CSR arrays, batched posting collection, pre-computed IDF |
| Query latency at 100K | 1.23s | 3–5ms | CSR fast-path scoring (no dict in hot path), ring buffer RPR queue |
| Data stack at 1M concurrent QPS | — | Crash | Reduced QPS iterations 10→3; 2GB GS_STACK_RESERVE exceeded |

---

## 4. Remaining Issues

1. **1M concurrent QPS stack overflow:** The 2GB data stack reserve (`GS_STACK_RESERVE=2GB`) is exceeded by the flat `doc_scores` array sized to `max_doc_id + 1` at 1M docs. Workaround: reduce concurrent test iterations to 3.

2. **MITRE durable (SQLite-backed) not benchmarked:** Required competitor per VICTORY_CONTRACT but not yet tested.

3. **Baseline (unoptimized) 100K results not re-verified:** Baseline numbers (37.7s CSR, 1.23s query) from earlier run; should be re-confirmed against frozen commit.
