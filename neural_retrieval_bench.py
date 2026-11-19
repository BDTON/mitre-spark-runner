#!/usr/bin/env python3
"""
Neural MITRE Retrieval Benchmark
Reads fs437_package.hdf5, builds inverted index, runs conjunctive AND queries.
Pure Python implementation - no AdaptiveMiteMemory dependency.
"""
import h5py
import time
import re
import json
import sys
import os
from collections import defaultdict


def tokenize(text: str):
    """Tokenize text into terms (alphanumeric + colon-separated attribute:value pairs)."""
    terms = re.findall(r'[a-zA-Z0-9_:.\-]+', text.lower())
    return terms


def build_inverted_index(docs):
    """
    Build inverted index: term -> sorted list of doc_ids.
    docs: list of (doc_id, text) tuples.
    Returns (index, doc_texts).
    """
    index = defaultdict(set)
    doc_texts = {}
    for doc_id, text in docs:
        doc_texts[doc_id] = text
        terms = tokenize(text)
        for term in terms:
            index[term].add(doc_id)
    return index, doc_texts


def conjunctive_and(index, query_terms):
    """
    Conjunctive AND retrieval: intersect posting lists for all query terms.
    Returns sorted list of matching doc_ids.
    """
    if not query_terms:
        return []
    posting_lists = []
    for term in query_terms:
        if term in index:
            posting_lists.append(index[term])
        else:
            return []
    posting_lists.sort(key=len)
    result = posting_lists[0].copy()
    for pl in posting_lists[1:]:
        result = result.intersection(pl)
        if not result:
            break
    return sorted(result)


def ingest_events(hdf5_path, key, max_events=None, batch_size=50000):
    """Ingest spike events as documents."""
    docs = []
    with h5py.File(hdf5_path, 'r') as f:
        ds = f[key]
        n = min(ds.shape[0], max_events) if max_events else ds.shape[0]
        for i in range(0, n, batch_size):
            end = min(i + batch_size, n)
            batch = ds[i:end]
            for row in batch:
                idx = int(row['index'])
                voltage = float(row['values_block_0'][0])
                timestamp = int(row['time_of_event'])
                electrode = int(row['electrode'])
                text = f"electrode:{electrode} voltage:{voltage:.2f} timestamp:{timestamp} event_idx:{idx}"
                doc_id = f"event_{idx}"
                docs.append((doc_id, text))
    return docs


def ingest_stimulations(hdf5_path, key, max_stims=None):
    """Ingest stimulation records as documents."""
    docs = []
    with h5py.File(hdf5_path, 'r') as f:
        ds = f[key]
        n = min(ds.shape[0], max_stims) if max_stims else ds.shape[0]
        for i in range(n):
            row = ds[i]
            idx = int(row['index'])
            stim_params = row['values_block_0']
            timestamp = int(row['time_of_stim'])
            electrode = int(row['electrode'])
            # Use first 4 stim params as named parameters
            params_str = ",".join([f"p{j}={v:.2f}" for j, v in enumerate(stim_params[:4])])
            text = f"stimulation electrode:{electrode} timestamp:{timestamp} params:[{params_str}] stim_idx:{idx}"
            doc_id = f"stim_{idx}"
            docs.append((doc_id, text))
    return docs


def main():
    pkg_path = sys.argv[1] if len(sys.argv) > 1 else "fs437_package.hdf5"

    results = {
        "dataset": "fs437",
        "package_file": pkg_path,
    }

    # Phase 1: Ingest stimulations (10k)
    print("[1] Ingesting stimulations...")
    t0 = time.perf_counter()
    stim_docs = ingest_stimulations(pkg_path, "fs437_wholelife_stimulations/table", max_stims=10000)
    t_ingest_stim = time.perf_counter() - t0
    print(f"  Ingested {len(stim_docs)} stimulations in {t_ingest_stim:.2f}s ({len(stim_docs)/t_ingest_stim:.0f} docs/s)")
    results["stimulations_ingested"] = len(stim_docs)
    results["stim_ingest_seconds"] = t_ingest_stim

    # Phase 2: Ingest events (20k)
    print("[2] Ingesting events...")
    t0 = time.perf_counter()
    event_docs = ingest_events(pkg_path, "fs437_wholelife_events/table", max_events=20000)
    t_ingest_event = time.perf_counter() - t0
    print(f"  Ingested {len(event_docs)} events in {t_ingest_event:.2f}s ({len(event_docs)/t_ingest_event:.0f} docs/s)")
    results["events_ingested"] = len(event_docs)
    results["event_ingest_seconds"] = t_ingest_event

    # Phase 3: Build inverted index
    all_docs = stim_docs + event_docs
    print(f"\n[3] Building inverted index on {len(all_docs)} documents...")
    t0 = time.perf_counter()
    index, doc_texts = build_inverted_index(all_docs)
    t_index = time.perf_counter() - t0
    print(f"  Index built in {t_index:.2f}s ({len(index)} unique terms)")
    results["total_documents"] = len(all_docs)
    results["index_terms"] = len(index)
    results["index_build_seconds"] = t_index

    # Diagnostic: electrode distribution
    electrodes = set()
    for doc_id, text in all_docs:
        for term in tokenize(text):
            if term.startswith("electrode:"):
                electrodes.add(int(term.split(":")[1]))
    sorted_electrodes = sorted(electrodes)
    print(f"\n[Diagnostics] Unique electrodes in ingested data: {sorted_electrodes}")
    results["electrodes"] = sorted_electrodes

    # Diagnostic: sample documents
    print("\n[Diagnostics] Sample documents:")
    for doc_id in list(doc_texts.keys())[:3]:
        print(f"  {doc_id}: {doc_texts[doc_id][:100]}")

    # Phase 4: Warmup query
    print("\n[4] Warming up...")
    t0 = time.perf_counter()
    _ = conjunctive_and(index, tokenize("electrode"))
    t_warmup = time.perf_counter() - t0
    print(f"  Warmup done in {t_warmup*1000:.1f}ms")
    results["warmup_ms"] = t_warmup * 1000

    # Phase 5: Test queries using actual electrode values from data
    sample_electrode = sorted_electrodes[0] if sorted_electrodes else 0
    queries = [
        (f"electrode:{sample_electrode}", [f"electrode:{sample_electrode}"]),
        ("stimulation + electrode", ["stimulation", f"electrode:{sample_electrode}"]),
        ("single electrode", [f"electrode:{sample_electrode}"]),
        ("non-existent electrode", ["electrode:999"]),
        ("stimulation only", ["stimulation"]),
        ("voltage negative", ["voltage:-79"]),
    ]

    print("\n[5] Testing queries (10 repetitions each)...")
    query_results = []
    for label, terms in queries:
        lats = []
        for rep in range(10):
            t0 = time.perf_counter()
            matches = conjunctive_and(index, terms)
            elapsed = (time.perf_counter() - t0) * 1000
            lats.append(elapsed)

        lats.sort()
        median_ms = lats[len(lats)//2]
        p95_ms = lats[int(len(lats)*0.95)]
        min_ms = lats[0]
        max_ms = lats[-1]

        print(f"  '{label}' -> {len(matches)} results, median={median_ms:.1f}ms, p95={p95_ms:.1f}ms, range=[{min_ms:.1f},{max_ms:.1f}]ms")
        for doc_id in matches[:2]:
            print(f"    {doc_id}: {doc_texts[doc_id][:90]}...")

        query_results.append({
            "query": label,
            "terms": terms,
            "result_count": len(matches),
            "median_ms": median_ms,
            "p95_ms": p95_ms,
            "min_ms": min_ms,
            "max_ms": max_ms,
            "all_latencies_ms": lats,
        })

    results["queries"] = query_results

    # Summary
    print("\n" + "=" * 60)
    print("NEURAL MITRE RETRIEVAL BENCHMARK - FS437 - COMPLETE")
    print("=" * 60)
    print(f"  Documents: {results['total_documents']} ({results['stimulations_ingested']} stim + {results['events_ingested']} events)")
    print(f"  Index terms: {results['index_terms']}")
    print(f"  Ingest (stim): {results['stim_ingest_seconds']:.2f}s")
    print(f"  Ingest (event): {results['event_ingest_seconds']:.2f}s")
    print(f"  Index build: {results['index_build_seconds']:.2f}s")
    print(f"  Warmup: {results['warmup_ms']:.1f}ms")

    output_path = "neural_retrieval_results.json"
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    main()
