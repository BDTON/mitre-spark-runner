# NEXT EXPERIMENT — MITRE/PRISM Retrieval Campaign

**Campaign:** PAVONA MITRE Kimi Spark Handoff
**Date:** 2026-11-18

---

## 1. Next Experiment Most Likely to Change the Conclusion

**Experiment:** Replace the flat `doc_scores` array in `score_query_fast` with a sparse hash-map accumulator to eliminate the 1M concurrent QPS stack overflow.

**File:** `mitre/benchmark_opt.goose` (function `score_query_fast`)

**Current code (problematic):**
```goose
var doc_scores: f32[>..] = [];
for _ in 0..max_docs + 1 { doc_scores.push(0.0); }
var active_docs: u32[>..] = [];
// ... score_query_fast iterates all query terms, accumulates into doc_scores[doc_id]
```

**At 1M corpus:** `max_docs + 1 = 1,000,001` f32 entries = ~4MB for doc_scores alone. Combined with `evidence_pool`, `active_docs`, and RPR event processing, this exceeds the 2GB `GS_STACK_RESERVE` during concurrent QPS.

**Proposed change:** Use a dictionary-based accumulator (sparse) instead of a flat array, only allocating entries for docs that actually receive scores. This reduces memory from O(max_doc_id) to O(docs_with_scores) and eliminates the stack overflow.

**Hypothesis:** With a sparse accumulator, concurrent QPS at 1M will complete without stack overflow, and query latency at 100K will remain comparable (the hot path only touches docs that match query terms, which is typically a small fraction of the corpus).

**Success criteria:**
1. Concurrent QPS test at 1M completes without stack overflow (10 iterations × 6 queries)
2. Query median latency at 100K remains within 10% of current 3.25–4.88ms
3. QPS at 1M is measurable and > 0

**Risk:** Dictionary lookups in the hot path may increase per-query latency vs the flat array. The optimization loop (Priority 1) requires measuring this tradeoff.

---

## 2. Secondary Experiments (if time permits)

| Experiment | Description | Priority |
|------------|-------------|----------|
| Durable MITRE (SQLite-backed) | Benchmark MITRE with file-backed persistent storage per VICTORY_CONTRACT required competitor arm | High |
| Baseline re-verification | Re-run unoptimized `benchmark.goose` at 100K to confirm 37.7s CSR / 1.23s query baseline numbers | Medium |
| 1M QPS with workaround | Run `benchmark_1m.goose` with 3 QPS iterations to confirm stable concurrent throughput | Medium |

---

## 3. Files to Modify

- `/home/dev/snapshot/goose/mitre/benchmark_opt.goose` — `score_query_fast` function
- `/home/dev/benchmark_1m.goose` — restore QPS iterations to 10 after fix
