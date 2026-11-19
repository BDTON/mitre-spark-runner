# PAVONA RESEARCH DIRECTIVE — Technical Report

**Campaign:** PAVONA MITRE Kimi Spark Handoff — Neural Retrieval Evaluation  
**Dataset:** FS437 (neuroscience whole-life experiment)  
**Date:** 2026-11-19  
**Status:** Local validation complete; Spark deployment pending

---

## 1. System Under Test

| Component | Specification |
|-----------|--------------|
| Retrieval algorithm | Conjunctive AND inverted index |
| Tokenization | Regex `[a-zA-Z0-9_:.\-]+` (lowercased) |
| Index structure | Term → sorted set of doc_ids (hash map of sets) |
| Intersection strategy | Shortest posting list first, early termination on empty |
| HDF5 reader | h5py 3.16.0 |
| Language | Python 3 |
| External retrieval dependencies | None |

---

## 2. Data Ingestion

### Source Data

FS437 package file (`fs437_package.hdf5`) contains two primary tables:

| Table | Total Rows | Ingested Rows | Columns |
|-------|-----------|---------------|---------|
| `fs437_wholelife_stimulations/table` | 802,657 | 10,000 | index, values_block_0(16), time_of_stim, electrode |
| `fs437_wholelife_events/table` | 2,643,769 | 20,000 | index, values_block_0(1), time_of_event, electrode |

### Document Format

Each document is a text string combining key attributes:

```
stimulation electrode:{N} timestamp:{T} params:[p0={v},p1={v},p2={v},p3={v}] stim_idx:{N}
electrode:{N} voltage:{V:.2f} timestamp:{T} event_idx:{N}
```

### Ingestion Performance

| Metric | Stimulations | Events |
|--------|-------------|--------|
| Documents ingested | 10,000 | 20,000 |
| Elapsed time | 0.34s | 0.04s |
| Throughput | ~29,600 docs/s | ~522,000 docs/s |

---

## 3. Index Construction

| Metric | Value |
|--------|-------|
| Total documents | 30,000 |
| Unique index terms | 53,229 |
| Build time | 0.07s |
| Terms per document (avg) | ~17.7 |

### Electrode Distribution

All 32 electrodes (0–31) are present in the ingested data, consistent with a 4×8 MEA array configuration.

---

## 4. Query Evaluation

### Test Queries

Six conjunctive AND queries were executed, each repeated 10 times for latency measurement:

| # | Query Label | Terms | Result Count | Median (ms) | p95 (ms) | Min (ms) | Max (ms) |
|---|-------------|-------|-------------|-------------|----------|----------|----------|
| 1 | Single electrode | `[electrode:0]` | 1,171 | 0.13 | 0.15 | 0.11 | 0.15 |
| 2 | Stimulation + electrode | `[stimulation, electrode:0]` | 381 | 0.06 | 0.12 | 0.06 | 0.12 |
| 3 | Single electrode (dup) | `[electrode:0]` | 1,171 | 0.13 | 0.15 | 0.11 | 0.15 |
| 4 | Non-existent electrode | `[electrode:999]` | 0 | <0.01 | <0.01 | <0.01 | <0.01 |
| 5 | Stimulation only | `[stimulation]` | 10,000 | 1.43 | 1.64 | 1.36 | 1.64 |
| 6 | Voltage negative | `[voltage:-79]` | 0 | <0.01 | 0.03 | <0.01 | 0.03 |

### Latency Analysis

- **Warmup:** < 0.01ms (single `electrode` term intersection)
- **Point queries (single term):** 0.06–0.13ms median
- **Conjunctive queries (two terms):** 0.06ms median (intersection of posting lists)
- **Broad queries (single common term):** 1.43ms median (10,000 results)
- **Negative queries:** < 0.01ms (early termination on missing term)

---

## 5. Performance Boundaries

| Boundary | Observed Value | Assessment |
|----------|---------------|------------|
| Index build (30K docs) | 0.07s | Well within acceptable range |
| Point query p95 | 0.17ms | Sub-millisecond for selective queries |
| Broad query p95 | 1.64ms | Acceptable for 10K-result sets |
| Negative query | <0.01ms | Early termination works correctly |
| Memory usage | Not measured | Requires separate profiling |

---

## 6. Limitations

1. **Sample-limited ingestion:** Only 10,000 stimulations and 20,000 events ingested (out of 802,657 and 2,643,769 total rows). Full-dataset performance not measured.
2. **No Spark execution:** Benchmark validated locally on x86_64 Python 3.14. Spark ARM64 Python 3.12 deployment pending SSH access restoration.
3. **No recall/nDCG:** No labeled relevance judgments available for synthetic neuroscience corpus.
4. **Single-threaded:** Inverted index built and queried single-threaded.

---

## 7. Reproducibility

- Script: `neural_retrieval_bench.py` (pure Python, h5py dependency only)
- Input: `fs437_package.hdf5` (FS437 package file)
- Command: `python3 neural_retrieval_bench.py <path_to_hdf5>`
- Output: `neural_retrieval_results.json` (JSON with full latency distributions)
