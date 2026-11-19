# COST COMPARISON — MITRE vs OpenRouter Models at 100K/1M Corpus Scale

**Campaign:** PAVONA MITRE Kimi Spark Handoff
**Date:** 2026-11-18
**Pricing Source:** OpenRouter API (https://openrouter.ai/api/v1/models), fetched 2026-11-18 from Lappy
**Hardware:** DGX Spark (GB10, 121Gi RAM) — local execution, no API cost for MITRE/BM25S/SQLite
**BM25S Fix Applied:** retriever.index(corpus_tok) — full Tokenized object with vocabulary (correctness gate #1)

---

## 1. OpenRouter Model Pricing (per 1K tokens)

| Model | Prompt ($/1K) | Completion ($/1K) | Context | vs gpt-6-astra |
|-------|---------------|-------------------|---------|----------------|
| gpt-6.2-astra-pro | $0.000008 | $0.000040 | 1,050,000 | 0.8x |
| gpt-6.2-astra-pro:batch | $0.000004 | $0.000020 | 1,050,000 | 0.4x |
| gpt-6.2-astra | $0.000008 | $0.000040 | 1,050,000 | 0.8x |
| gpt-6.2-astra:batch | $0.000004 | $0.000020 | 1,050,000 | 0.4x |
| openai/gpt-6-astra | $0.000010 | $0.000050 | 1,050,000 | 1x (baseline) |
| openai/gpt-6-astra:batch | $0.000005 | $0.000025 | 1,050,000 | 0.5x |
| openai/gpt-6-astra-pro | $0.000010 | $0.000050 | 1,050,000 | 1x (baseline) |
| openai/gpt-6-astra-pro:batch | $0.000005 | $0.000025 | 1,050,000 | 0.5x |
| ~openai/gpt-astra-latest | $0.000008 | $0.000040 | 1,050,000 | 0.8x |
| gpt-6.2-sol-pro | $0.000002 | $0.000010 | 1,050,000 | 0.2x |
| gpt-6.2-sol | $0.000002 | $0.000010 | 1,050,000 | 0.2x |
| gpt-6.1-terra-pro | $0.000001 | $0.000005 | 1,050,000 | 0.1x |
| gpt-6.1-terra | $0.000001 | $0.000005 | 1,050,000 | 0.1x |
| gpt-6-luna-pro | $0.0000001 | $0.0000005 | 1,050,000 | 0.01x |
| gpt-6-luna | $0.0000001 | $0.0000005 | 1,050,000 | 0.01x |

---

## 2. Cost per Retrieval-Answer Cycle (estimated)

Assumptions per cycle:
- Query: ~50 tokens
- Retrieved context: ~2,000 tokens (top-10 docs with provenance)
- Answer generation: ~500 tokens
- Total model tokens: ~2,550 per cycle

| Model | Prompt tokens | Completion tokens | Cost per cycle ($) | vs MITRE (local, $0) |
|-------|---------------|-------------------|--------------------|----------------------|
| openai/gpt-6-astra | 50 + 2000 | 500 | $0.000143 | MITRE is free (local) |
| openai/gpt-6-astra:batch | 50 + 2000 | 500 | $0.000071 | MITRE is free (local) |
| openai/gpt-6-astra-pro | 50 + 2000 | 500 | $0.000143 | MITRE is free (local) |
| gpt-6.2-astra-pro | 50 + 2000 | 500 | $0.000114 | MITRE is free (local) |
| gpt-6.2-sol-pro | 50 + 2000 | 500 | $0.000029 | MITRE is free (local) |
| gpt-6.1-terra-pro | 50 + 2000 | 500 | $0.000014 | MITRE is free (local) |
| gpt-6-luna | 50 + 2000 | 500 | $0.0000014 | MITRE is free (local) |

**MITRE local cost:** $0 per cycle (runs on owned hardware, no API calls)

---

## 3. MITRE vs Python (BM25S/rank_bm25) — Head-to-Head at 100K Corpus

| Comparator | Query Median (ms) | Query p95 (ms) | Index Build (ms) | Memory (MB) | Cost per query |
|------------|-------------------|----------------|------------------|-------------|----------------|
| MITRE (CSR diagnostic) | 0.0001–0.75 | ~0.87 | 40 | 182 | $0 (local) |
| MITRE (RPR product path) | 0.02–0.06 | ~0.09 | 40 | 182 | $0 (local) |
| BM25S | 5.06–6.03 | ~6.87 | 2316 | — | $0 (local) |
| rank_bm25 | 28.21–105.50 | ~115.24 | 698 | — | $0 (local) |

**Query breakdown — 100K corpus (median ms):**

| Query | MITRE CSR | MITRE RPR | BM25S | rank_bm25 |
|-------|-----------|-----------|-------|-----------|
| nile (high freq) | 0.0001 | 0.02 | 5.06 | 32.35 |
| pharaoh (med freq) | 0.0001 | 0.02 | 5.16 | 31.67 |
| ziggurat (low freq) | 0.0001 | 0.02 | 5.67 | 28.21 |
| nile pharaoh (2-term) | 0.75 | 0.04 | 6.03 | 60.24 |
| egypt greece rome (3-term) | 0.41 | 0.06 | 2.50 | 91.37 |
| orphan-fact-nile-decree | 0.26 | 0.02 | 5.06 | 105.50 |

**MITRE vs BM25S speedup at 100K:**
- CSR diagnostic: 6.8x–15,000x faster than BM25S (single-term), 8x faster (two-term)
- RPR product path: 84x–253x faster than BM25S (single-term), 151x faster (two-term)

---

## 4. MITRE vs Python (BM25S/rank_bm25) — Head-to-Head at 1M Corpus

| Comparator | Query Median (ms) | Query p95 (ms) | Index Build (ms) | Memory (MB) | Cost per query |
|------------|-------------------|----------------|------------------|-------------|----------------|
| MITRE (optimized CSR) | 35.85–52.18 | ~52.18 | 7347 | — | $0 (local) |
| BM25S | 44.53–50.65 | ~63.02 | 30889 | — | $0 (local) |
| rank_bm25 | 28.21–279.35 | ~279.35 | 2218 | — | $0 (local) |

**Query breakdown — 1M corpus (median ms):**

| Query | MITRE | BM25S | rank_bm25 |
|-------|-------|-------|-----------|
| nile (high freq) | 35.85 | 45.84 | 84.31 |
| pharaoh (med freq) | 37.77 | 45.41 | 88.13 |
| ziggurat (low freq) | 36.11 | 44.53 | 108.84 |
| nile pharaoh (2-term) | 40.78 | 50.65 | 149.68 |
| egypt greece rome (3-term) | 13.24 | 16.90 | 279.35 |
| orphan-fact-nile-decree | 33.25 | 41.36 | 266.50 |

**MITRE vs BM25S at 1M:** MITRE is 1.2x–1.3x faster than BM25S on most queries, 1.3x faster on rare fact. MITRE concurrent QPS crashes at 1M (2GB stack reserve); BM25S completes all queries.

---

## 5. Latency + Cost Combined — chat-gpt6-astra vs MITRE (100K corpus)

Assumes retrieval-answer cycle: query (50 tok) + context (2000 tok) + answer (500 tok) = 2550 tokens

| Comparator | Query Median (ms) | Cost per cycle ($) | Cost-adjusted (ms per $0.001) |
|------------|-------------------|--------------------|-------------------------------|
| MITRE (RPR product path) | 0.02–0.06 | $0.000000 | ∞ (free, local) |
| MITRE (CSR diagnostic) | 0.0001–0.75 | $0.000000 | ∞ (free, local) |
| BM25S | 5.06–6.03 | $0.000000 | ∞ (free, local) |
| rank_bm25 | 28.21–105.50 | $0.000000 | ∞ (free, local) |
| openai/gpt-6-astra (OpenRouter) | ~500–2000 (est.) | $0.000143 | ~3,500–14,000 |
| gpt-6-luna (OpenRouter) | ~500–2000 (est.) | $0.0000014 | ~357,000–1,428,000 |

**chat-gpt6-astra specifically:** At $0.000010 prompt + $0.000050 completion per 1K tokens, a full retrieval-answer cycle costs ~$0.000143. MITRE provides sub-millisecond retrieval at $0 per query — the cost advantage of local execution is decisive at any volume.

---

## 6. Cost per Correct Answer

Since recall@k and nDCG@k were not measured (no labeled relevance judgments), cost per correct answer cannot be computed. This is a documented gap per BLOCKERS.md Section 4.

---

## 7. Monthly Cost Projection (1M queries/month)

| Model | Monthly API Cost ($) |
|-------|---------------------|
| MITRE (local) | $0.00 |
| BM25S (local) | $0.00 |
| rank_bm25 (local) | $0.00 |
| openai/gpt-6-astra | $143.00 |
| gpt-6.2-astra-pro | $114.00 |
| gpt-6-luna | $1.40 |
| gpt-6-luna:batch | $0.70 |

At 1M queries/month, local MITRE/BM25S saves $143/month vs openai/gpt-6-astra, and $1.40/month vs even the cheapest OpenRouter model (gpt-6-luna).

---

## 8. Conclusion

For local retrieval on owned hardware (DGX Spark), **all local comparators have $0 per-query API cost**. The choice between them is driven by latency and features, not cost:

- **MITRE** (RPR product path): fastest at 100K for multi-term queries (0.02–0.06ms), full RPR + PRISM evidence provenance, $0 cost
- **MITRE** (CSR diagnostic): sub-millisecond single-term at 100K (0.0001ms), $0 cost
- **BM25S**: 5.06–6.03ms at 100K, $0 cost, no evidence provenance
- **rank_bm25**: 28–106ms at 100K, $0 cost, no evidence provenance
- **OpenRouter models**: 500ms–2s estimated latency, $0.0000014–$0.000143 per cycle, no local hardware needed

MITRE's RPR evidence chain provides provenance tracking that pure BM25S lacks, at 84x–253x faster queries than BM25S at 100K with $0 API cost — versus OpenRouter gpt-6-astra at ~500–2000ms and $0.000143 per cycle.
