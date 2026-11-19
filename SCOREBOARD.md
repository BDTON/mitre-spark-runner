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
| BM25S | bm25s 0.3.16 | 45.7 | 89.4 | 0.54–0.58 | ~0.61 | — | — | ✅ Complete |
| rank_bm25 | rank-bm25 0.2.2 | 15.0 | 22.6 | 1.00–2.79 | ~3.52 | — | — | ✅ Complete |
| SQLite FTS5 | SQLite 3.x | 23.9 | — | 4.74 (single-term) | ~4.93 | — | — | ✅ Complete* |

*\*SQLite FTS5 multi-term phrase queries return 0 results due to FTS5 phrase-matching limitation.*

**Query latency breakdown (median ms, 10 iterations):**

| Query | MITRE | BM25S | rank_bm25 | SQLite FTS5 |
|-------|-------|-------|-----------|-------------|
| nile (high freq) | 0.32–0.49 | 0.56 | 1.02 | 4.74 |
| pharaoh (med freq) | 0.32–0.49 | 0.58 | 1.30 | 4.74 |
| ziggurat (low freq) | 0.32–0.49 | 0.56 | 1.00 | 4.74 |
| nile pharaoh (2-term) | 0.32–0.49 | 0.00 | 1.39 | 0.50* |
| egypt greece rome (3-term) | 0.32–0.49 | 0.00 | 2.24 | 0.09* |
| orphan-fact-nile-decree | 0.32–0.49 | 0.54 | 2.79 | 0.01* |

*\*FTS5 phrase matching — returns 0 results.*

---

## RACE 2 — 100K Corpus (100,000 docs) — CLAIM SCOPE

| Comparator | Version | Ingest (ms) | Index Build (ms) | Query Median (ms) | Query p95 (ms) | QPS | Memory (MB) | Status |
|------------|---------|-------------|------------------|-------------------|----------------|-----|-------------|--------|
| MITRE (optimized, CSR) | Goose b66f0f86 | 144 | 40 | 0.0001–0.75 | ~0.87 | 4077 | 182 | ✅ Complete |
| MITRE (RPR product path) | Goose b66f0f86 | — | — | 0.02–0.06 | ~0.09 | — | 182 | ✅ Complete |
| BM25S | bm25s 0.3.16 | 379.1 | 855.0 | 0.80–2.12 | ~3.86 | — | — | ✅ Complete |
| rank_bm25 | rank-bm25 0.2.2 | 157.3 | 270.6 | 11.39–86.18 | ~87.27 | — | — | ✅ Complete |
| SQLite FTS5 | SQLite 3.x | 277.3 | — | 49 (single-term) | ~52 | — | — | ✅ Complete* |

**Query latency breakdown (median ms, 10 iterations):**

| Query | MITRE CSR (diagnostic) | MITRE RPR (product) | BM25S | rank_bm25 | SQLite FTS5 |
|-------|-----------------------|---------------------|-------|-----------|-------------|
| nile (high freq) | 0.0001 | 0.02 | 1.94 | 11.39 | 49.03 |
| pharaoh (med freq) | 0.0001 | 0.02 | 1.52 | 27.27 | 49.11 |
| ziggurat (low freq) | 0.0001 | 0.02 | 1.68 | 20.01 | 49.15 |
| nile pharaoh (2-term) | 0.75 | 0.04 | 1.75 | 44.67 | 4.96* |
| egypt greece rome (3-term) | 0.41 | 0.06 | 0.80 | 73.55 | 0.70* |
| orphan-fact-nile-decree | 0.26 | 0.02 | 1.79 | 86.18 | 0.01* |

**100K index build comparison:**
- MITRE ingest: 144ms, flat postings rebuild: 4ms, CSR build: 40ms
- MITRE baseline (pre-optimization): 37.7s → Optimized: 0.04s CSR build (900x+ speedup)
- MITRE query (pre-optimization): 1.23s → Optimized CSR: ~0.0001–0.75ms (~1600x+ speedup)
- RPR product path adds Scout/Expand/Evidence pulse loop on top of CSR

---

## RACE 3 — 1M Corpus (1,000,000 docs) — STRESS TEST

| Comparator | Version | Ingest (ms) | Index Build (ms) | Query Median (ms) | Query p95 (ms) | QPS | Memory (MB) | Status |
|------------|---------|-------------|------------------|-------------------|----------------|-----|-------------|--------|
| MITRE (optimized, CSR) | Goose b66f0f86 | 3480 | 7347 | 35.85–52.18 | ~52.18 | — | — | ⚠️ Query OK, Concurrent QPS CRASH |
| BM25S | bm25s 0.3.16 | 6500.8 | 20160.3 | 13.24–40.78 | ~46.16 | — | — | ✅ Complete |
| rank_bm25 | rank-bm25 0.2.2 | 1906.3 | 2217.5 | 84.31–279.35 | ~279.35 | — | — | ✅ Complete |
| SQLite FTS5 | SQLite 3.x | 3730.9 | — | 554 (single-term) | ~557 | — | — | ✅ Complete* |

**1M query latency breakdown (median ms, 10 iterations):**

| Query | MITRE | BM25S | rank_bm25 | SQLite FTS5 |
|-------|-------|-------|-----------|-------------|
| nile (high freq) | 35.85–52.18 | 35.70 | 84.31 | 553.95 |
| pharaoh (med freq) | 35.85–52.18 | 37.77 | 88.13 | 553.85 |
| ziggurat (low freq) | 35.85–52.18 | 36.11 | 108.84 | 554.67 |
| nile pharaoh (2-term) | 35.85–52.18 | 40.78 | 149.68 | 50.21* |
| egypt greece rome (3-term) | 35.85–52.18 | 13.24 | 279.35 | 6.60* |
| orphan-fact-nile-decree | 35.85–52.18 | 33.25 | 266.50 | 0.02* |

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
| 1 | MITRE (RPR product) | 0.02–0.06 | — | 182 | Qualifying product path; fastest at 100K for multi-term |
| 2 | MITRE (CSR diagnostic) | 0.0001–0.75 | 40 | 182 | CSR fast-path scorer; sub-ms single-term at 100K |
| 3 | BM25S | 0.80–2.12 | 855.0 | — | Fastest pure BM25 scorer |
| 4 | SQLite FTS5 | 49 (single-term) | — | — | Phrase matching limitation |
| 5 | rank_bm25 | 11.39–86.18 | 270.6 | — | Query latency grows with term count |

---

## Raw Result Files

| File | Description |
|------|-------------|
| `python_comparison_results.json` | BM25S + rank_bm25 results (10K/100K/1M) |
| `sqlite_fts5_results.json` | SQLite FTS5 results (10K/100K/1M) |
| `bm25s_100m.log` | BM25S 100M failure log (crashed at ~96% Compute Scores) |
| `SHA256SUMS` | Snapshot file integrity manifest (893 verified OK) |
| `snapshot-manifest.txt` | Snapshot provenance and contents |
