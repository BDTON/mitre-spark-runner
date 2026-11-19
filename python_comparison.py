#!/usr/bin/env python3
"""
MITRE/PRISM Retrieval Race - Python Comparison Script
Compares BM25S and rank_bm25 against Goose MITRE results.
Uses the same deterministic corpus generation as benchmark.goose (seed 8001).
"""

import bm25s
from rank_bm25 import BM25Okapi
import numpy as np
import time
import json
import re
import sys

# =====================================================================
# CORPUS GENERATION (matches benchmark.goose generate_corpus)
# =====================================================================

TOPICS_NAMES = ["egypt", "greece", "mesopotamia", "persia", "rome"]

def generate_corpus(n, seed=8001):
    """Generate corpus matching Goose's generate_corpus with LCG."""
    docs = []
    rng_state = seed
    
    for i in range(n):
        rng_state = (rng_state * 1664525 + 1013904223) & 0xFFFFFFFF
        topic_idx = rng_state % 5
        ts = 1.0 + (i * 0.001)
        
        num = i  # doc.id - 1
        num_str = str(num)
        topic_name = TOPICS_NAMES[topic_idx]
        text = f"test document {num_str} with {topic_name} terms nile river pharaoh ziggurat cyrus legion"
        
        docs.append({
            "id": i + 1,
            "text": text,
            "topic_idx": topic_idx,
            "timestamp": ts,
            "scope": 1,
            "principal": 1,
        })
    
    return docs

# =====================================================================
# BENCHMARK QUERIES (matches benchmark.goose BENCH_QUERIES)
# =====================================================================

BENCH_QUERIES = [
    ("nile", 10, "single-term high freq"),
    ("pharaoh", 10, "single-term med freq"),
    ("ziggurat", 10, "single-term low freq"),
    ("nile pharaoh", 10, "two-term"),
    ("egypt greece rome", 10, "three-term"),
    ("orphan-fact-nile-decree", 3, "rare fact"),
]

# =====================================================================
# BM25S BENCHMARK
# =====================================================================

def benchmark_bm25s(corpus_size, seed=8001):
    """Run BM25S benchmark."""
    print(f"\n=== BM25S: {corpus_size} docs ===")
    
    docs = generate_corpus(corpus_size, seed)
    texts = [d["text"] for d in docs]
    
    # Tokenize corpus with bm25s (all at once)
    print("  Tokenizing corpus...")
    tok_start = time.time()
    corpus_tok = bm25s.tokenize(texts)
    tok_time = (time.time() - tok_start) * 1000
    print(f"  Tokenization: {tok_time:.1f} ms")
    
    # Index
    print("  Indexing with BM25S...")
    idx_start = time.time()
    retriever = bm25s.BM25()
    retriever.index(corpus_tok)
    idx_time = (time.time() - idx_start) * 1000
    print(f"  Indexing: {idx_time:.1f} ms")
    
    # Tokenize queries - keep as Tokenized objects for retrieve()
    query_toks = []
    for q_str, k, desc in BENCH_QUERIES:
        q_tok = bm25s.tokenize([q_str])
        query_toks.append(q_tok)
    
    # Warm-up
    for q_tok in query_toks:
        retriever.retrieve(q_tok, k=10)
    
    # Measure query latencies
    print("  Running queries...")
    query_results = []
    for i, (q_str, k, desc) in enumerate(BENCH_QUERIES):
        q_tok = query_toks[i]
        latencies = []
        result_count = 0
        for _ in range(10):
            q_start = time.time()
            results = retriever.retrieve(q_tok, k=k)
            q_end = time.time()
            latencies.append((q_end - q_start) * 1000)
            if hasattr(results, 'documents'):
                result_count = len(results.documents[0])
        
        latencies.sort()
        median = latencies[len(latencies) // 2]
        p95 = latencies[int(len(latencies) * 0.95)]
        
        query_results.append({
            "desc": desc,
            "median_ms": round(median, 2),
            "p95_ms": round(p95, 2),
            "result_count": result_count,
        })
        print(f"  {desc}: median={median:.2f}ms, p95={p95:.2f}ms, results={result_count}")
    
    return {
        "corpus_size": corpus_size,
        "tokenize_ms": round(tok_time, 1),
        "index_ms": round(idx_time, 1),
        "queries": query_results,
    }

# =====================================================================
# RANK_BM25 BENCHMARK
# =====================================================================

def benchmark_rank_bm25(corpus_size, seed=8001):
    """Run rank_bm25 benchmark."""
    print(f"\n=== rank_bm25: {corpus_size} docs ===")
    
    docs = generate_corpus(corpus_size, seed)
    texts = [d["text"] for d in docs]
    
    # Tokenize with simple regex
    print("  Tokenizing corpus...")
    tok_start = time.time()
    corpus_tokens = [re.findall(r'[a-zA-Z0-9]+', t.lower()) for t in texts]
    tok_time = (time.time() - tok_start) * 1000
    print(f"  Tokenization: {tok_time:.1f} ms")
    
    # Index
    print("  Indexing with rank_bm25...")
    idx_start = time.time()
    bm25 = BM25Okapi(corpus_tokens)
    idx_time = (time.time() - idx_start) * 1000
    print(f"  Indexing: {idx_time:.1f} ms")
    
    # Tokenize queries
    query_tokens_list = [re.findall(r'[a-zA-Z0-9]+', q[0].lower()) for q in BENCH_QUERIES]
    
    # Warm-up
    for qt in query_tokens_list:
        bm25.get_top_n(qt, texts, n=10)
    
    # Measure query latencies
    print("  Running queries...")
    query_results = []
    for i, (q_str, k, desc) in enumerate(BENCH_QUERIES):
        qt = query_tokens_list[i]
        latencies = []
        for _ in range(10):
            q_start = time.time()
            results = bm25.get_top_n(qt, texts, n=k)
            q_end = time.time()
            latencies.append((q_end - q_start) * 1000)
        
        latencies.sort()
        median = latencies[len(latencies) // 2]
        p95 = latencies[int(len(latencies) * 0.95)]
        
        query_results.append({
            "desc": desc,
            "median_ms": round(median, 2),
            "p95_ms": round(p95, 2),
            "result_count": len(results),
        })
        print(f"  {desc}: median={median:.2f}ms, p95={p95:.2f}ms, results={len(results)}")
    
    return {
        "corpus_size": corpus_size,
        "tokenize_ms": round(tok_time, 1),
        "index_ms": round(idx_time, 1),
        "queries": query_results,
    }

if __name__ == "__main__":
    results = {}
    
    for size in [10000, 100000, 1000000]:
        if size == 1000000:
            results[size] = {"bm25s": benchmark_bm25s(size)}
        else:
            results[size] = {
                "bm25s": benchmark_bm25s(size),
                "rank_bm25": benchmark_rank_bm25(size),
            }
    
    # Save results
    with open('python_comparison_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    print("\nResults saved to python_comparison_results.json")
