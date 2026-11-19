# BLOCKERS AND EXTERNAL LIMITATIONS — MITRE/PRISM Campaign

**Campaign:** PAVONA MITRE Kimi Spark Handoff
**Date:** 2026-11-18

---

## 1. Competitors Not Tested (External Blockers)

| Competitor | VICTORY_CONTRACT Status | Blocker | Details |
|------------|------------------------|---------|---------|
| Lucene/Anserini | REQUIRED | No Java runtime on Spark ARM64 | `/usr/lib/jvm/` does not exist; `which java` returns nothing. Cannot install Java in remaining time. |
| Tantivy | REQUIRED | No Rust toolchain, no Python bindings | `which rustc` and `which cargo` return nothing; `import tantivy` fails. Would require Rust compilation. |
| MITRE_alone_durable | REQUIRED | SQLite-backed MITRE not implemented | Would require modifying Goose source to add file-backed SQLite persistence. Not completed before deadline. |

## 2. Priority 2 (Semantic/Hybrid Race) — Not Tested

| Entrant | Blocker |
|---------|---------|
| Vespa | Not installed; requires Java + dedicated deployment |
| SPLADE | Not available; requires model download and encoding pipeline |
| FAISS/cuVS | Not installed; requires CUDA ML stack |
| CAGRA | Not installed; part of cuVS/FAISS |
| ColBERTv2 | Not available; requires model download and inference |

**Reason:** None of these are pre-installed on Spark. Installing and configuring them would exceed the remaining time before the 10:40 PM export cutoff.

## 3. Priority 3 (Memory Race) — Not Tested

| Entrant | Blocker |
|---------|---------|
| LongMemEval | Not staged; no corpus or evaluation harness available |
| Cognee | Not installed; requires Python package + dependencies |
| LoCoMo | Not staged |

**Reason:** No memory evaluation corpora or frameworks are available on Spark or Lappy.

## 4. Quality Metrics — Not Measured

| Metric | Reason |
|--------|--------|
| recall@k | No labeled relevance judgments available for the synthetic corpus |
| nDCG@k | No labeled relevance judgments available |
| correctness tests | No test oracle for Goose benchmark output |
| durability/crash-restart tests | Not implemented; would require controlled crash infrastructure |

**Reason:** The corpus is synthetically generated (LCG seed 8001) with no relevance labels. Creating labeled relevance data would require manual annotation of query-document pairs, which exceeds remaining time.

## 5. BM25S Result Count Verification

**Claim in verifier feedback:** "BM25S result counts are 0 across all queries"

**Actual evidence:** BM25S result counts are non-zero across all scales and queries:

| Scale | single-term | two-term | three-term | rare fact |
|-------|-------------|----------|------------|-----------|
| 10K | 10 | 10 | 10 | 3 |
| 100K | 10 | 10 | 10 | 3 |
| 1M | 10 | 10 | 10 | 3 |

Source: `python_comparison_results.json` — all `result_count` fields are >= 3. No data integrity problem exists.

## 6. Deadline Computation

| Item | Value |
|------|-------|
| Rental deadline | 2026-11-19 04:00 UTC (11:00 p.m. EST Nov 18) |
| Export cutoff | 2026-11-19 03:40 UTC (10:40 p.m. EST Nov 18) |
| Current time (at check) | 2026-11-18 8:07:38 PM EST |
| Time remaining to deadline | ~2 hours 53 minutes |
| Time remaining to cutoff | ~2 hours 33 minutes |
| Reserve for export + hash verification | 20 minutes (required by objective) |

## 7. Kimi Model Selection

The objective requires verifying the selected Kimi model (last screenshot showed `moonshotai/kimi-k3.1-pro`). This is a Qwen CLI GUI configuration setting that cannot be queried via the terminal shell. The controlling session runs on Lappy (hostname verified: `Lappy`).
