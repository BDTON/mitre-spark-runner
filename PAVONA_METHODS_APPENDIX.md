# PAVONA Methods Appendix
## MITRE/RPR Retrieval Study on FinalSpark FS437 Neuroscience Data

**Classification:** PRIVATE — FinalSpark Internal Review Only  
**Date:** 2026-11-19

---

## A. Data Provenance and Preprocessing

### A.1 Source Dataset (FS437)

| Property | Value |
|----------|-------|
| Archive | `fs437.zip` (~1.7 GB) |
| Package file | `fs437_export/fs437_package.hdf5` (211 MB) |
| Raw file | `fs437_export/fs437_raw.hdf5` (7.6 GB) |
| Segment index | `fs437_export/fs437_segment_index.parquet` |
| Format | HDF5 (Hierarchical Data Format v5) |

### A.2 Table Schemas

#### `fs437_wholelife_stimulations/table` (802,657 rows)
| Column | Type | Description |
|--------|------|-------------|
| `index` | int64 | Sequential row index |
| `values_block_0` | float64[16] | Stimulation parameters (16 channels) |
| `time_of_stim` | int64 | Timestamp (microseconds since epoch) |
| `electrode` | int32 | Electrode ID (0–31) |

#### `fs437_wholelife_events/table` (2,643,769 rows)
| Column | Type | Description |
|--------|------|-------------|
| `index` | int64 | Sequential row index |
| `values_block_0` | float64[1] | Voltage amplitude (µV) |
| `time_of_event` | int64 | Timestamp (microseconds since epoch) |
| `electrode` | int32 | Electrode ID (0–31) |

### A.3 Export to Text Corpus (for MITRE/RPR ingestion)

**Script:** `export_neural_docs.py`

**Output format:** `doc_id<TAB>text` (one document per line)

**Stimulation documents (10,000 sampled):**
```
stim_0	stimulation electrode:5 timestamp:1234567890 params:[p0=1.23,p1=2.34,p2=3.45,p3=4.56] stim_idx:0
```

**Event documents (20,000 sampled):**
```
event_1234	electrode:3 voltage:-79.45 timestamp:1234567891 event_idx:1234
```

**Total corpus:** 30,000 documents, 52,746 unique terms

### A.4 Sampling Methodology

| Table | Total Rows | Sampled | Method |
|-------|-----------|---------|--------|
| stimulations | 802,657 | 10,000 | First N rows |
| events | 2,643,769 | 20,000 | First N rows |

> **Limitation:** First-N sampling may not represent full temporal distribution. Random sampling with fixed seed recommended for future work.

---

## B. Retrieval Systems

### B.1 Pure Python Inverted Index (Baseline)

**File:** `neural_retrieval_bench_fixed.py`

**Algorithm:**
1. Tokenize document text → terms
2. Build `term → sorted set of doc_ids` hash map
3. Query: intersect posting lists (shortest first, early termination)
4. Verify against full scan for correctness

**Tokenization regex:** `[a-zA-Z0-9_:.\-]+` (lowercased)

**Complexity:**
- Build: O(N · T) where N=docs, T=terms/doc
- Query: O(min(|P₁|, |P₂|, ...)) where Pᵢ=posting list size

### B.2 MITRE/RPR (Python Implementation)

**File:** `mitre_rpr_python.py`

**Algorithm (matching frozen Goose binary):**

**Phase 1: Ingestion**
- Tokenize each document
- Build term dictionary with document frequency (DF)
- Accumulate postings: (doc_id, term_idx, position)

**Phase 2: Rebuild Flat Postings (CSR preparation)**
- Group postings by term into contiguous flat array
- Set `postings_start`/`postings_end` on each TermEntry

**Phase 3: CSR Index Build**
- Compute IDF = log((N+1)/(DF+0.5)) per term
- Aggregate postings by doc_id → TF
- Store CSR: `term_offsets`, `doc_ids`, `scores` (TF), `idf`
- Precompute top-K (K=10) per term by TF × IDF

**Phase 4: Query Execution**

**CSR Fast Path (single term):**
- Return precomputed top-K directly (O(K))

**CSR General (multi-term):**
- Accumulate TF × IDF scores per doc_id
- Select top-K by score

**RPR Ring Buffer:**
1. **Scout:** Enqueue Expand events for each query term's postings (budget=1000)
2. **Expand:** Convert posting → Evidence event
3. **Evidence:** Accumulate score per doc_id
4. **Pulse:** Process up to `max_events` (10,000)
5. Return sorted results by score

**Tokenization regex:** `[a-zA-Z0-9:_\-]+` (lowercased, preserves colons)

### B.3 Frozen Goose Binary (Reference)

**Path:** `/home/dev/candidate_benchmark_opt_frozen` on Spark

**Characteristics:**
- Compiled from Goose source (`candidate_benchmark_opt_frozen.goose`)
- Generates synthetic corpus (10K/100K docs)
- Does not ingest external data
- Used for algorithmic validation only

---

## C. Experimental Protocol

### C.1 Query Set

| Query | Terms | Type | Expected |
|-------|-------|------|----------|
| single_electrode | `electrode:0` | Point | ~1,171 hits |
| stim_plus_electrode | `stimulation electrode:0` | Conjunctive | ~381 hits |
| known_miss | `electrode:999` | Negative | 0 hits |

### C.2 Timing Methodology

- **Repetitions:** 10 per query per system
- **Timer:** `time.perf_counter()` (Python) / `clock_ns()` (Goose)
- **Reported:** Median and P95 of 10 runs
- **Boundary:** Index-only (no I/O, no scan verification)

### C.3 Execution Environments

| Environment | OS | CPU | RAM | Python/Goose |
|-------------|-----|-----|-----|--------------|
| Local | Windows 10 x86_64 | Intel i7 | 32 GB | Python 3.14 |
| Spark | Ubuntu ARM64 | NVIDIA Grace | 121 GB | Python 3.12 / Goose |

---

## D. Ground Truth Construction

### D.1 Independent Oracle

For each query, expected results derived from **direct scan of HDF5 source**:

```python
# Electrode:0 stimulation hits
stim_hits = [r for r in stim_table if r['electrode'] == 0]

# Electrode:0 event hits  
event_hits = [r for r in event_table if r['electrode'] == 0]

# Combined (stimulation + electrode:0)
combined = [r for r in stim_table if r['electrode'] == 0]
```

### D.2 Verification Results

| Query | Oracle Count | Pure Python | MITRE/RPR CSR | MITRE/RPR RPR |
|-------|-------------|-------------|---------------|---------------|
| electrode:0 | 1,171 | 1,171 ✓ | 10 (top-K) | 957 (81%) |
| stim electrode:0 | 381 | 381 ✓ | 10 (top-K) | 1,701* |
| electrode:999 | 0 | 0 ✓ | 0 ✓ | 0 ✓ |

*RPR returns superset due to TF-IDF scoring on partial matches.

---

## E. Statistical Analysis

### E.1 Latency Distributions

For each system × query × repetition:
- Record latency in milliseconds
- Compute: median, P95, min, max
- No outlier removal (n=10 too small)

### E.2 Comparison Framework

| Comparison | Metric | Method |
|------------|--------|--------|
| Pure Python vs MITRE/RPR | Latency ratio | Median(MITRE) / Median(Pure) |
| CSR vs RPR | Recall ratio | RPR_count / CSR_count |
| Correctness | Match rate | \|Index_count - Oracle_count\| / Oracle_count |

---

## F. Reproducibility Artifacts

| Artifact | Location | Description |
|----------|----------|-------------|
| Pure Python benchmark | `neural_retrieval_bench_fixed.py` | Baseline inverted index |
| MITRE/RPR Python | `mitre_rpr_python.py` | CSR + RPR implementation |
| Export script | `export_neural_docs.py` | HDF5 → text corpus |
| Comparison script | `compare_mitre_rpr.py` | Cross-system comparison |
| Pure Python results | `neural_retrieval_spark_verify_results_v2.json` | Spark ARM64 baseline |
| MITRE/RPR results | `mitre_rpr_python_results.json` | Spark ARM64 MITRE/RPR |
| Aggregate CSV | `PAVONA_AGGREGATE_RESULTS.csv` | All systems × queries |

---

## G. Deviations from Locked Protocol

1. **FS369 not tested** — Transfer incomplete (60 GB over SSH)
2. **Full FS437 not tested** — Only 30K/3.4M records sampled
3. **Frozen Goose binary not adapted** — Uses synthetic data only
6. **PRISM not evaluated** — Requires Goose recompilation with flags
7. **Cold-start not measured** — Only warm runs after index build

---

## H. Compute Resource Accounting

| Phase | Duration | Spark CPU-hours | Local CPU-hours |
|-------|----------|-----------------|-----------------|
| fs437.zip transfer | ~5 min | — | — |
| Pure Python benchmark | 2 min | 0.03 | 0.03 |
| MITRE/RPR Python | 3 min | 0.05 | 0.05 |
| Comparison/analysis | 1 min | 0.02 | 0.02 |
| **Total** | **~11 min** | **~0.1** | **~0.1** |

---

**End of Methods Appendix**