#!/usr/bin/env python3
"""
BM25S benchmark at 100M corpus scale.
Tests whether BM25S can handle 100M docs and measures performance.
"""

import bm25s
import numpy as np
import time
import json
import re
import sys

TOPICS_NAMES = ["egypt", "greece", "mesopotamia", "persia", "rome"]

BENCH_QUERIES = [
    ("nile", 10, "single-term high freq"),
    ("pharaoh", 10, "single-term med freq"),
    ("ziggurat", 10, "single-term low freq"),
    ("nile pharaoh", 10, "two-term"),
    ("egypt greece rome", 10, "three-term"),
    ("orphan-fact-nile-decree", 3, "rare fact"),
]

def generate_corpus(n, seed=8001):
    """Generate corpus matching Goose's generate_corpus with LCG."""
    docs = []
    rng_state = seed
    for i in range(n):
        rng_state = (rng_state * 1664525 + 1013904223) & 0xFFFFFFFF
        topic_idx = rng_state % 5
        ts = 1.0 + (i * 0.001)
        num = i
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

def benchmark_bm25s_100m():
    corpus_size = 100_000_000
    print(f"=== BM25S: {corpus_size} docs ===")
    
    docs = generate_corpus(corpus_size)
    texts = [d["text"] for d in docs]
    
    # Tokenize corpus with bm25s (all at once)
    print("  Tokenizing corpus...")
    tok_start = time.time()
    corpus_tok = bm25s.tokenize(texts)
    tok_time = (time.time() - tok_start) * 1000
    print(f"  Tokenization: {tok_time:.1f} ms ({tok_time/1000:.1f} s)")
    
    # Index
    print("  Indexing with BM25S...")
    idx_start = time.time()
    retriever = bm25s.BM25()
    retriever.index(corpus_tok.ids)
    idx_time = (time.time() - idx_start) * 1000
    print(f"  Indexing: {idx_time:.1f} ms ({idx_time/1000:.1f} s)")
    
    # Tokenize queries
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

if __name__ == "__main__":
    result = benchmark_bm25s_100m()
    
    with open('/home/dev/bm25s_100m_results.json', 'w') as f:
        json.dump(result, f, indent=2)
    print(f"\nResults saved to /home/dev/bm25s_100m_results.json")
