#!/usr/bin/env python3
"""
SQLite FTS5 benchmark - required competitor per VICTORY_CONTRACT.
Uses the same deterministic corpus generation as benchmark.goose (seed 8001).
Config: WAL mode, synchronous=OFF, cache_size=256MB (per contract).
"""

import sqlite3
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

def benchmark_sqlite_fts5(corpus_size, seed=8001):
    print(f"\n=== SQLite FTS5: {corpus_size} docs ===")
    
    docs = generate_corpus(corpus_size, seed)
    
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA cache_size=262144")  # 256MB in pages
    
    # Create FTS5 table (standalone, per contract config)
    conn.execute("CREATE VIRTUAL TABLE docs USING fts5(doc_id, text, topic_idx, timestamp, scope, principal)")
    
    # Ingest
    print("  Ingesting docs...")
    ingest_start = time.time()
    for d in docs:
        conn.execute("INSERT INTO docs(doc_id, text, topic_idx, timestamp, scope, principal) VALUES (?, ?, ?, ?, ?, ?)",
                     (d["id"], d["text"], d["topic_idx"], d["timestamp"], d["scope"], d["principal"]))
    conn.commit()
    ingest_time = (time.time() - ingest_start) * 1000
    print(f"  Ingest: {ingest_time:.1f} ms")
    
    # Escape FTS5 special characters in query
    def escape_fts5(q):
        # Wrap in quotes to treat as phrase; escape internal double quotes
        return '"' + q.replace('"', '""') + '"'

    # Warm-up
    for q_str, k, desc in BENCH_QUERIES:
        conn.execute("SELECT doc_id FROM docs WHERE docs MATCH ? LIMIT ?", (escape_fts5(q_str), k))
    
    # Measure query latencies
    print("  Running queries...")
    query_results = []
    for q_str, k, desc in BENCH_QUERIES:
        latencies = []
        result_count = 0
        for _ in range(10):
            q_start = time.time()
            cur = conn.execute("SELECT doc_id FROM docs WHERE docs MATCH ? ORDER BY rank LIMIT ?", (escape_fts5(q_str), k))
            rows = cur.fetchall()
            q_end = time.time()
            latencies.append((q_end - q_start) * 1000)
            result_count = len(rows)
        
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
    
    conn.close()
    
    return {
        "corpus_size": corpus_size,
        "ingest_ms": round(ingest_time, 1),
        "queries": query_results,
    }

if __name__ == "__main__":
    results = {}
    for size in [10000, 100000, 1000000]:
        results[size] = benchmark_sqlite_fts5(size)
    
    with open('/home/dev/sqlite_fts5_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    print("\nResults saved to /home/dev/sqlite_fts5_results.json")
