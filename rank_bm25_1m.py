#!/usr/bin/env python3
"""
rank_bm25 benchmark at 1M corpus - filling the gap from the original run.
"""

import re
import time
import json

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

def benchmark_rank_bm25_1m():
    corpus_size = 1000000
    print(f"=== rank_bm25: {corpus_size} docs ===")
    
    docs = generate_corpus(corpus_size)
    texts = [d["text"] for d in docs]
    
    # Tokenize with simple regex
    print("  Tokenizing corpus...")
    tok_start = time.time()
    corpus_tokens = [re.findall(r'[a-zA-Z0-9]+', t.lower()) for t in texts]
    tok_time = (time.time() - tok_start) * 1000
    print(f"  Tokenization: {tok_time:.1f} ms")
    
    # Index
    print("  Indexing with rank_bm25...")
    from rank_bm25 import BM25Okapi
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
    result = benchmark_rank_bm25_1m()
    
    # Load existing results and merge
    try:
        with open('/home/dev/python_comparison_results.json', 'r') as f:
            results = json.load(f)
    except:
        results = {}
    
    results["1000000"]["rank_bm25"] = result
    
    with open('/home/dev/python_comparison_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    print("\nUpdated /home/dev/python_comparison_results.json with rank_bm25 at 1M")
