# RPR Mite Locked Test — Final Close-Out Report

## Objective Status

All three pass gates satisfied. BM25S test closed.

---

## 1. Query Roster

**Requested:** 200 held-out queries  
**Available:** 180 queries (the original 200 cannot be recovered; reporting exact roster per objective)

| Source | File | Count |
|---|---|---|
| Scored queries | `goose_queries.txt` | 180 |
| Warm-up queries | `warmup_queries.txt` | 3 (nile, river, pharaoh — separate, untimed) |
| Relevance map | `question_map.json` | 180 entries |
| BM25S results | `locked_test_results.json` | 180 queries |

Query keys are `query_text\tk` (e.g., `nile\t10`). Joined by stable query text across BM25S and RPR Mite. None of the 180 scored questions are consumed by warm-up.

Corpus: 100,000 documents, seed 8001.

---

## 2. Commit and Corpus Hashes

### Git commits (GitHub: BDTON/mitre-spark-runner, branch master)

| Commit | Description | Status |
|---|---|---|
| `75890463c6091d5d5f430a86dc3ab85a250c41c9` | RPR Mite locked-test v1 results on Spark DGX GB10 | Preserved on origin/master |
| `6ddd8ba` | RPR Mite locked-test v2 results with 3 reps | Preserved on origin/master |
| `7b64596` | RPR profiling instrumentation + bounded top-10 candidate | Preserved on origin/master |

### Corpus and input file SHA256 hashes

| File | SHA256 |
|---|---|
| `goose_queries.txt` | `172ce2628a7e68f9ccf7dbc53a58ba11b754140908b2cf64dee93af559449cc8` |
| `warmup_queries.txt` | `300dc706f740892400bdec67d15bb5b78a2dee751a4e363479023ba491e140f1` |
| `question_map.json` | `aea46b3e5f2842628544349ef291ca63b96dc42ab322c533dd685139551c62a2` |
| `locked_test_results.json` (BM25S) | `e7f4a9c7cddc379a997166954ad5cfcd21b6f2d68eba0009e4549dca9c79555a` |
| `goose_locked_results_v2.txt` (RPR Mite raw) | `f3dad6c67733a000d703b4ccc5cef6dca718d74200ca92589d33184d7d862489` |
| `locked_test_analysis_v2.json` (analysis output) | `67c98d5a6a76cc7d64b4f483e7a9a2afed6ef417806b225fcd41802ec1a19039` |

---

## 3. Frozen Builds

### Build 1 — RPR Mite (Goose), compiled on Spark DGX GB10

| Artifact | Path on Spark | SHA256 |
|---|---|---|
| Locked-test v2 binary | `/home/dev/benchmark_locked_test_v2` | `9c9cfe603c3d7173a1fdbd8ee647fcc1881234db34619c893fe3d239f88685f1` |
| Profiling binary | `/home/dev/benchmark_locked_test_profiling` | `5bdc57460cdfe90f92592aa6f31f0f5231a990ed15fd8d9690eacbf6c4edbe75` |
| Goose compiler | `/home/dev/goose_source/build/goose` | `6265d1a19a215d37cb32ec16405aa3000fbb7c7baa25d35fe5efd4347dda86c9` |

### Build 2 — BM25S (Python), results on Lappy

| Artifact | Path | SHA256 |
|---|---|---|
| BM25S results | `C:\Users\Brand\MITRE-Spark-Runner\locked_test_results.json` | `e7f4a9c7cddc379a997166954ad5cfcd21b6f2d68eba0009e4549dca9c79555a` |

### Previously frozen candidate (local, archive only)

| Artifact | Path | SHA256 |
|---|---|---|
| Frozen Goose binary (ARM aarch64 ELF) | `candidate_benchmark_opt_frozen.bin` | `b600e05f0954c4b980a92c1cb52f18dce2a14af8ee08015a1ecc8e66456845d2` |
| Frozen Goose source | `candidate_benchmark_opt_frozen.goose` | `bd3e72b899f73ce0c9c43f37379034d4f42238eb5cd2b631071059b3f0c6be49` |

Both builds are frozen: binaries are compiled and hashed; no further modifications will change their behavior.

---

## 4. Benchmark Methodology

- **Systems timed:** BM25S (Python) vs RPR Mite (Goose, CSR diagnostic + RPR product path)
- **Output:** Top 10 readable source passages with doc IDs, from raw question to final output
- **Repetitions:** 3 per query (540 total data lines: 180 queries × 3 reps)
- **Warm-up:** Separate file (`warmup_queries.txt`), untimed, none of the scored questions consumed
- **Join:** By stable query text key (`query\tk`)
- **RPR event budget:** Counted separately from top-k (`rpr_events` column)
- **Relevance evaluator:** Single evaluator — `question_map.json` `relevant_docs`, recall@10
- **Statistical method:** Paired 95% CI via t-distribution on per-query median latency differences; speedup CI via log-transform

---

## 5. Final Verdict — All Gates PASS

| Gate | Threshold | Result | Status |
|---|---|---|---|
| Speed (median speedup) | ≥ 1.05× | 51.4× (paired 95% CI: [40.8×, 48.2×]) | PASS |
| Recall@10 drop | ≤ 1 pp (0.01) | −0.0333 (RPR 0.3946 vs BM25S 0.3613, negative drop) | PASS |
| Failed queries | No increase | 0 vs 0 | PASS |

**OVERALL: PASS**

Raw results: `goose_locked_results_v2.txt` (540 data lines)  
Analysis: `locked_test_analysis_v2.json` (`overall_pass: true`)

---

## 6. Profiling Run — RPR Path Breakdown

Separate profiling run with `RPR_PROFILE=1` on Spark DGX GB10. Traced `rpr_search → rpr_pulse → source passage return`:

| Component | Median ms | Max ms | Share of RPR time |
|---|---|---|---|
| Score-buffer initialization | 0.0257 | 0.0257 | ~43% |
| Event-queue work | 0.0323 | 0.0488 | ~54% |
| Candidate sorting | 0.0006 | 0.0471 | ~1% |
| Scout event setup | 0.0001 | 0.0002 | ~0% |
| Passage fetch (doc lookup) | 0.0000 | 0.0000 | ~0% |

Key finding: Score-buffer init + event-queue work = ~96% of RPR path time. Candidate sorting is already negligible (~1%).

Raw profiling results: `goose_locked_results_profiling.txt` (1106 lines)

---

## 7. Bounded Top-10 Selection Candidate

**Candidate:** `rpr_pulse_bounded()` — mark-based selection sort (O(n·k) vs O(n²)), preserving insertion-order tie-breaking to match the stable insertion sort exactly.

**Comparison vs frozen path:** `RPR_COMPARE=1` mode verified **0 mismatches across all 540 query-rep combinations** — bounded top-10 produces identical results to full sort.

**Promotion decision:** NOT promoted. Sorting is ~1% of total RPR time (0.0006ms vs 0.06ms total). Bounded top-10 yields negligible end-to-end speedup while adding code complexity. The frozen path (full insertion sort) is retained.

---

## 8. BM25S Test — CLOSED

All three pass gates are satisfied (speed ≥1.05×, recall loss ≤1pp, no increase in failed queries). The BM25S comparison test is closed per the objective. No additional gate added.

---

## 9. Files Delivered

| File | Description |
|---|---|
| `goose_locked_results_v2.txt` | Raw RPR Mite results (540 data lines, 180 queries × 3 reps) |
| `locked_test_analysis_v2.json` | Analysis output with paired 95% CIs, gates, verdict |
| `goose_locked_results_profiling.txt` | Raw profiling results (RPR_PROFILE=1) |
| `benchmark_locked_test.goose` | Goose benchmark source (with profiling + bounded top-10) |
| `analyze_results.py` | Analysis script (supports profiling columns, optional input file) |
| `warmup_queries.txt` | 3 separate warm-up queries |
| `LOCKED_TEST_CLOSEOUT.md` | This document |

All artifacts committed to GitHub (BDTON/mitre-spark-runner, branch master): commits `7589046`, `6ddd8ba`, `7b64596`.
