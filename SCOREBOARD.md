# SCOREBOARD — MITRE/PRISM Retrieval Race Results

**Campaign:** PAVONA MITRE Kimi Spark Handoff
**Date:** 2026-11-18
**Controller:** Lappy | **Compute:** Spark (axforge @ 178.105.204.56:22081, DGX Spark GB10, 20-core Cortex-X925/A725, 121Gi RAM, Ubuntu 24.04.3 LTS)
**Corpus:** Deterministic LCG, seed 8001 (Development split per VICTORY_CONTRACT)
**Queries:** 6 benchmark queries (nile, pharaoh, ziggurat, nile pharaoh, egypt greece rome, orphan-fact-nile-decree)

---

## RACE 1 — 10K Corpus (10,000 docs)

| Comparator | Version | Ingest (ms) | Index Build (ms) | Query Median (ms) | Query p95 (ms) | QPS | Memory (MB) | Status |
|------------|---------|-------------|------------------|-------------------|----------------|-----|-------------|--------|
| MITRE (optimized, CSR) | Goose b66f0f86 | 62 | 58 | 0.32–0.49 | — | ~2840 | 18 | ✅ Complete |
| BM25S | bm25s 0.3.16 | 25.3 | 60.2 | 0.04–0.05 | ~0.05 | — | — | ✅ Complete |
| rank_bm25 | rank-bm25 0.2.2 | 12.1 | 17.6 | 0.60–1.66 | ~1.66 | — | — | ✅ Complete |
| SQLite FTS5 | SQLite 3.x | 23.9 | — | 4.74 (single-term) | ~4.93 | — | — | ✅ Complete* |

*\*SQLite FTS5 multi-term phrase queries return 0 results due to FTS5 phrase-matching limitation.*

**Query latency breakdown (median ms, 10 iterations):**

| Query | MITRE | BM25S | rank_bm25 | SQLite FTS5 |
|-------|-------|-------|-----------|-------------|
| nile (high freq) | 0.32–0.49 | 0.04 | 0.60 | 4.74 |
| pharaoh (med freq) | 0.32–0.49 | 0.04 | 0.60 | 4.74 |
| ziggurat (low freq) | 0.32–0.49 | 0.04 | 0.63 | 4.74 |
| nile pharaoh (2-term) | 0.32–0.49 | 0.04 | 1.02 | 0.50* |
| egypt greece rome (3-term) | 0.32–0.49 | 0.04 | 1.51 | 0.09* |
| orphan-fact-nile-decree | 0.32–0.49 | 0.04 | 1.65 | 0.01* |

*\*FTS5 phrase matching — returns 0 results.*

---

## RACE 2 — 100K Corpus (100,000 docs) — CLAIM SCOPE

| Comparator | Version | Ingest (ms) | Index Build (ms) | Query Median (ms) | Query p95 (ms) | QPS | Memory (MB) | Status |
|------------|---------|-------------|------------------|-------------------|----------------|-----|-------------|--------|
| MITRE (optimized, CSR) | Goose b66f0f86 | 344 | 651 | 3.25–4.88 | ~4.88 | ~2810 | 182 | ✅ Complete |
| BM25S | bm25s 0.3.16 | 260.3 | 601.0 | 0.14–0.15 | ~0.15 | — | — | ✅ Complete |
| rank_bm25 | rank-bm25 0.2.2 | 139.0 | 209.4 | 6.9–25 | ~25 | — | — | ✅ Complete |
| SQLite FTS5 | SQLite 3.x | 277.3 | — | 49 (single-term) | ~52 | — | — | ✅ Complete* |

**Query latency breakdown (median ms, 10 iterations):**

| Query | MITRE | BM25S | rank_bm25 | SQLite FTS5 |
|-------|-------|-------|-----------|-------------|
| nile (high freq) | 3.25–4.88 | 0.14 | 6.91 | 49.03 |
| pharaoh (med freq) | 3.25–4.88 | 0.14 | 6.98 | 49.11 |
| ziggurat (low freq) | 3.25–4.88 | 0.14 | 8.27 | 49.15 |
| nile pharaoh (2-term) | 3.25–4.88 | 0.14 | 13.41 | 4.96* |
| egypt greece rome (3-term) | 3.25–4.88 | 0.14 | 23.71 | 0.70* |
| orphan-fact-nile-decree | 3.25–4.88 | 0.14 | 20.28 | 0.01* |

**100K index build comparison:**
- MITRE baseline (pre-optimization): 37.7s → Optimized: 0.65s (57x speedup)
- MITRE query (pre-optimization): 1.23s → Optimized: 3–5ms (~375x speedup)

---

## RACE 3 — 1M Corpus (1,000,000 docs) — STRESS TEST

| Comparator | Version | Ingest (ms) | Index Build (ms) | Query Median (ms) | Query p95 (ms) | QPS | Memory (MB) | Status |
|------------|---------|-------------|------------------|-------------------|----------------|-----|-------------|--------|
| MITRE (optimized, CSR) | Goose b66f0f86 | 3480 | 7347 | 35.85–52.18 | ~52.18 | — | — | ⚠️ Query OK, Concurrent QPS CRASH |
| BM25S | bm25s 0.3.16 | 2988.7 | 6094.0 | 1.14–1.19 | ~1.19 | — | — | ✅ Complete |
| rank_bm25 | rank-bm25 0.2.2 | 1906.3 | 2217.5 | 84.31–279.35 | ~279.35 | — | — | ✅ Complete |
| SQLite FTS5 | SQLite 3.x | 3730.9 | — | 554 (single-term) | ~557 | — | — | ✅ Complete* |

**1M query latency breakdown (median ms, 10 iterations):**

| Query | MITRE | BM25S | rank_bm25 | SQLite FTS5 |
|-------|-------|-------|-----------|-------------|
| nile (high freq) | 35.85–52.18 | 1.16 | 84.31 | 553.95 |
| pharaoh (med freq) | 35.85–52.18 | 1.15 | 88.13 | 553.85 |
| ziggurat (low freq) | 35.85–52.18 | 1.15 | 108.84 | 554.67 |
| nile pharaoh (2-term) | 35.85–52.18 | 1.14 | 149.68 | 50.21* |
| egypt greece rome (3-term) | 35.85–52.18 | 1.14 | 279.35 | 6.60* |
| orphan-fact-nile-decree | 35.85–52.18 | 1.14 | 266.50 | 0.02* |

**1M issue:** MITRE concurrent QPS test crashes with data stack overflow (2GB GS_STACK_RESERVE exceeded). Query benchmarks complete successfully.

---

## RACE 4 — 100M Corpus (100,000,000 docs) — STRESS LIMIT

| Comparator | Version | Status | Failure Mode |
|------------|---------|--------|--------------|
| MITRE (optimized, CSR) | Goose b66f0f86 | ❌ Failed | Data stack overflow during corpus generation (2GB GS_STACK_RESERVE exceeded). Error: "a value on main's data stacks grew past the 2 GB reserved for it; --stack-reserve or -DGS_STACK_RESERVE raises the reservation, up to 256 TB" |
| BM25S | bm25s 0.3.16 | ❌ Failed | Process exited during Compute Scores at ~96% completion (~87% RAM usage, ~105Gi of 121Gi). No results file produced. Likely OOM. |
| rank_bm25 | rank-bm25 0.2.2 | ❌ Not tested | Would require even more memory and time than BM25S at 100M |
| SQLite FTS5 | SQLite 3.x | ❌ Not tested | 100M individual INSERT statements would take hours |

**100M conclusion:** No comparator can complete the 100M corpus race within the resource constraints of this hardware (2GB stack reserve for MITRE, ~121Gi RAM for Python comparators). Both MITRE and BM25S — the two strongest performers at 10K–1M — fail at 100M. There is no conclusive best performer at 100M scale because no entrant finishes.

---

## SUMMARY — CLAIM SCOPE (100K)

| Rank | Comparator | Query Median (ms) | Index Build (ms) | Memory (MB) | Verdict |
|------|-----------|-------------------|------------------|-------------|---------|
| 1 | BM25S | 0.14–0.15 | 601.0 | — | Fastest pure BM25 scorer |
| 2 | MITRE (optimized) | 3.25–4.88 | 651 | 182 | Full RPR + PRISM evidence chain; 23–35x slower queries than BM25S |
| 3 | SQLite FTS5 | 49 (single-term) | — | — | Phrase matching limitation |
| 4 | rank_bm25 | 6.9–25 | 209.4 | — | Query latency grows with term count |

---

## Raw Result Files

| File | Description |
|------|-------------|
| `python_comparison_results.json` | BM25S + rank_bm25 results (10K/100K/1M) |
| `sqlite_fts5_results.json` | SQLite FTS5 results (10K/100K/1M) |
| `bm25s_100m.log` | BM25S 100M failure log (crashed at ~96% Compute Scores) |
| `SHA256SUMS` | Snapshot file integrity manifest (893 verified OK) |
| `snapshot-manifest.txt` | Snapshot provenance and contents |
