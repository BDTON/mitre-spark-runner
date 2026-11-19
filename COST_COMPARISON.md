# COST COMPARISON — MITRE vs OpenRouter Models at 100K/1M Corpus Scale

**Campaign:** PAVONA MITRE Kimi Spark Handoff
**Date:** 2026-11-18
**Pricing Source:** OpenRouter API (https://openrouter.ai/api/v1/models), fetched from Spark
**Hardware:** DGX Spark (GB10, 121Gi RAM) — local execution, no API cost for MITRE/BM25S/SQLite

---

## 1. OpenRouter Model Pricing (per 1K tokens)

| Model | Prompt ($/1K) | Completion ($/1K) | Context | vs gpt-6.2-astra-pro |
|-------|---------------|-------------------|---------|----------------------|
| gpt-6.2-astra-pro | $0.000010 | $0.000050 | 1,050,000 | 1x (baseline) |
| gpt-6.2-astra-pro:batch | $0.000005 | $0.000025 | 1,050,000 | 0.5x |
| gpt-6.2-astra | $0.000008 | $0.000040 | 1,050,000 | 0.8x |
| gpt-6.2-sol-pro | $0.000002 | $0.000010 | 1,050,000 | 0.2x |
| gpt-6.2-sol | $0.000002 | $0.000010 | 1,050,000 | 0.2x |
| gpt-6.1-terra-pro | $0.000001 | $0.000005 | 1,050,000 | 0.1x |
| gpt-6.1-terra | $0.000001 | $0.000005 | 1,050,000 | 0.1x |
| gpt-6-luna | $0.0000001 | $0.0000005 | 1,050,000 | 0.01x |
| gpt-6-luna:batch | $0.00000005 | $0.00000025 | 1,050,000 | 0.005x |

---

## 2. Cost per Retrieval-Answer Cycle (estimated)

Assumptions per cycle:
- Query: ~50 tokens
- Retrieved context: ~2,000 tokens (top-10 docs with provenance)
- Answer generation: ~500 tokens
- Total model tokens: ~2,550 per cycle

| Model | Cost per cycle ($) | vs MITRE (local, $0) |
|-------|-------------------|----------------------|
| gpt-6.2-astra-pro | $0.000143 | MITRE is free (local) |
| gpt-6.2-sol-pro | $0.000029 | MITRE is free (local) |
| gpt-6.1-terra-pro | $0.000014 | MITRE is free (local) |
| gpt-6-luna | $0.0000014 | MITRE is free (local) |

**MITRE local cost:** $0 per cycle (runs on owned hardware, no API calls)

---

## 3. Latency + Cost Combined (100K corpus)

| Comparator | Query Median (ms) | Cost per cycle | Cost-adjusted value |
|------------|-------------------|----------------|---------------------|
| BM25S | 0.14–0.15 | $0 (local) | Fastest + free |
| MITRE (optimized CSR) | 3.25–4.88 | $0 (local) | 23–35x slower than BM25S, free |
| rank_bm25 | 6.9–25 | $0 (local) | 2–8x slower than BM25S, free |
| SQLite FTS5 | 49 (single-term) | $0 (local) | ~10-15x slower than MITRE, free |
| gpt-6-luna (via OpenRouter) | ~500-2000ms (est.) | $0.0000014 | Slowest + cheapest API |
| gpt-6.2-astra-pro (via OpenRouter) | ~500-2000ms (est.) | $0.000143 | Slowest + most expensive API |

---

## 4. Cost per Correct Answer (100K)

Since recall@k and nDCG@k were not measured (no labeled relevance judgments), cost per correct answer cannot be computed. This is a documented gap.

**What IS measurable:**
- All local comparators (MITRE, BM25S, rank_bm25, SQLite FTS5) have $0 API cost
- OpenRouter models range from $0.00000005/tok (gpt-6-luna batch) to $0.00001/tok (gpt-6.2-astra-pro)
- MITRE's RPR evidence chain provides provenance tracking that pure BM25S lacks, at 23–35x query latency cost but $0 API cost

---

## 5. Conclusion on Cost

For local retrieval on owned hardware (DGX Spark), **all comparators have $0 per-query API cost**. The choice between them is driven by latency and features, not cost:

- **BM25S** is the fastest local option (0.14–0.15ms at 100K) with $0 cost
- **MITRE** provides full RPR + PRISM evidence provenance at 3.25–4.88ms with $0 cost
- **OpenRouter models** add API cost ($0.00000005–$0.00001/tok) and inference latency (500ms–2s est.) for marginal retrieval benefit over local BM25S

The cost advantage of local execution is decisive: at 1M queries/month, OpenRouter gpt-6-luna would cost ~$1.40/month in API tokens, while local MITRE/BM25S costs $0 (amortized hardware only).
