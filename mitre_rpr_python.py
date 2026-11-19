#!/usr/bin/env python3
"""
MITRE/RPR Neural Retrieval — Python implementation matching frozen binary algorithms.
Builds CSR inverted index + RPR ring buffer queue for fast retrieval on neuroscience data.
"""
import sys
import time
import math
import re
from collections import defaultdict
from typing import List, Tuple, Dict, Any


# =====================================================================
# TOKENIZER
# =====================================================================

def tokenize(text: str) -> List[str]:
    """Extract tokens preserving colons and other special chars."""
    # Keep alphanumeric, colons, and hyphens as part of tokens
    return re.findall(r'[a-zA-Z0-9:_\-]+', text.lower())


# =====================================================================
# DATA STRUCTURES (matching Goose frozen binary)
# =====================================================================

class TermEntry:
    __slots__ = ('term', 'df', 'postings_start', 'postings_end')
    def __init__(self, term: str):
        self.term = term
        self.df = 0
        self.postings_start = 0
        self.postings_end = 0


class PostingEntry:
    __slots__ = ('doc_id', 'freq', 'term_idx', 'positions_start', 'positions_end')
    def __init__(self, doc_id: int, term_idx: int, pos: int):
        self.doc_id = doc_id
        self.freq = 1
        self.term_idx = term_idx
        self.positions_start = pos
        self.positions_end = pos + 1


class DocEntry:
    __slots__ = ('doc_id', 'text')
    def __init__(self, doc_id: int, text: str):
        self.doc_id = doc_id
        self.text = text


class SearchResult:
    __slots__ = ('doc_id', 'score')
    def __init__(self, doc_id: int, score: float):
        self.doc_id = doc_id
        self.score = score


class RPREvent:
    """RPR Ring Buffer Event Types"""
    SCOUT = 0
    EXPAND = 1
    EVIDENCE = 2
    PULSE = 3

    def __init__(self, event_type: int, **kwargs):
        self.event_type = event_type
        self.__dict__.update(kwargs)


# =====================================================================
# INGESTION FROM TEXT FILE
# =====================================================================

def ingest_docs_from_file(path: str) -> Tuple[List[DocEntry], Dict[str, TermEntry], List[str], Dict[str, int], List[PostingEntry], List[int], List[int]]:
    """Parse neural_docs.txt and build initial index structures."""
    doc_pool = []
    term_pool = {}
    term_list = []  # for ordered iteration
    term_to_idx = {}  # fast lookup
    posting_pool = []
    flat_postings = []
    flat_positions = []

    print(f"  Ingesting documents from {path}...")
    start = time.perf_counter()

    with open(path, 'r') as f:
        for line_num, line in enumerate(f):
            line = line.strip()
            if not line:
                continue

            # Parse doc_id \t text
            parts = line.split('\t', 1)
            if len(parts) != 2:
                continue

            doc_id_str = parts[0]
            text = parts[1]

            # Extract numeric ID from strings like "stim_0" or "event_123"
            doc_id_match = re.search(r'(\d+)$', doc_id_str)
            if doc_id_match:
                doc_id = int(doc_id_match.group(1))
            else:
                doc_id = line_num  # fallback

            # Store document
            doc_pool.append(DocEntry(doc_id, text))

            # Tokenize and index
            tokens = tokenize(text)
            seen_terms = set()
            pos = 0

            for tok in tokens:
                if tok in seen_terms:
                    pos += len(tok) + 1
                    continue
                seen_terms.add(tok)

                # Get or create term entry
                if tok not in term_pool:
                    term_pool[tok] = TermEntry(tok)
                    term_to_idx[tok] = len(term_list)
                    term_list.append(tok)

                term_idx = term_to_idx[tok]

                # Add posting
                posting = PostingEntry(doc_id, term_idx, pos)
                posting_pool.append(posting)
                flat_positions.append(pos)
                flat_postings.append(len(posting_pool) - 1)
                term_pool[tok].df += 1

                pos += len(tok) + 1

            if line_num % 5000 == 0 and line_num > 0:
                elapsed = time.perf_counter() - start
                print(f"    ...ingested {line_num} docs in {elapsed:.2f}s")

    elapsed = time.perf_counter() - start
    print(f"  Ingested {len(doc_pool)} docs in {elapsed:.2f}s ({len(doc_pool)/elapsed:.0f} docs/sec)")
    print(f"  Unique terms: {len(term_list)}")

    return doc_pool, term_pool, term_list, term_to_idx, posting_pool, flat_postings, flat_positions


# =====================================================================
# REBUILD FLAT POSTINGS (matching Goose)
# =====================================================================

def rebuild_flat_postings(term_list: List[str], term_pool: Dict[str, TermEntry],
                          posting_pool: List[PostingEntry], flat_postings: List[int]):
    """Rebuild flat_postings grouped by term, set postings_start/end on TermEntry."""
    print("  Rebuilding flat postings...")
    start = time.perf_counter()

    num_terms = len(term_list)

    # Compute term start offsets
    term_starts = [0] * num_terms
    running = 0
    for i in range(num_terms):
        term = term_list[i]
        term_starts[i] = running
        running += term_pool[term].df

    # Cursor for each term
    cursor = term_starts.copy()

    # New flat_postings array
    new_flat_postings = [0] * len(flat_postings)

    # Place each posting in its term's section
    for pi in range(len(posting_pool)):
        posting = posting_pool[pi]
        t = posting.term_idx
        pos = cursor[t]
        new_flat_postings[pos] = pi
        cursor[t] += 1

    # Update term_pool with postings_start/end
    for i in range(num_terms):
        term = term_list[i]
        te = term_pool[term]
        te.postings_start = term_starts[i]
        te.postings_end = term_starts[i] + te.df

    flat_postings[:] = new_flat_postings

    elapsed = time.perf_counter() - start
    print(f"  Rebuild time: {elapsed*1000:.2f}ms")


# =====================================================================
# CSR INDEX BUILD (matching frozen binary)
# =====================================================================

def build_csr_index(doc_pool: List[DocEntry], term_list: List[str], term_to_idx: Dict[str, int],
                    term_pool: Dict[str, TermEntry], posting_pool: List[PostingEntry],
                    flat_postings: List[int]) -> Tuple[List[int], List[int], List[float], List[float], List[int], List[int], List[float]]:
    """Build CSR index from flat postings."""
    print("  Building CSR index...")
    start = time.perf_counter()

    num_docs = len(doc_pool)
    num_terms = len(term_list)

    # Term offsets in CSR
    csr_term_offsets = [0] * (num_terms + 1)
    csr_doc_ids = []
    csr_scores = []
    csr_idf = []

    # First pass: compute IDF and collect postings per term
    term_postings = [[] for _ in range(num_terms)]

    for posting_idx in flat_postings:
        posting = posting_pool[posting_idx]
        term_postings[posting.term_idx].append(posting)

    # Build CSR arrays
    for term_idx, term in enumerate(term_list):
        term_entry = term_pool[term]
        idf = math.log((num_docs + 1.0) / (term_entry.df + 0.5))
        csr_idf.append(idf)

        # Aggregate by doc_id
        doc_counts = defaultdict(int)
        for posting in term_postings[term_idx]:
            doc_counts[posting.doc_id] += 1

        # Add to CSR
        csr_term_offsets[term_idx + 1] = csr_term_offsets[term_idx] + len(doc_counts)
        for doc_id, cnt in doc_counts.items():
            csr_doc_ids.append(doc_id)
            csr_scores.append(float(cnt))

    elapsed = time.perf_counter() - start
    print(f"  CSR build time: {elapsed*1000:.2f}ms")

    # Build Top-K per term (CSR_MAX_K = 10)
    CSR_MAX_K = 10
    csr_topk_offsets = [0] * (num_terms + 1)
    csr_topk_doc_ids = []
    csr_topk_scores = []

    for term_idx in range(num_terms):
        term_start = csr_term_offsets[term_idx]
        term_end = csr_term_offsets[term_idx + 1]
        idf = csr_idf[term_idx]
        num_postings = term_end - term_start

        # Collect (doc_id, tf) pairs
        local_docs = []
        local_tfs = []
        for i in range(num_postings):
            local_docs.append(csr_doc_ids[term_start + i])
            local_tfs.append(csr_scores[term_start + i])

        # Select top-K by TF
        topk_count = min(num_postings, CSR_MAX_K)
        for _ in range(topk_count):
            best_j = 0
            best_tf = 0.0
            for j in range(len(local_tfs)):
                if local_tfs[j] > best_tf:
                    best_tf = local_tfs[j]
                    best_j = j
            if best_tf <= 0.0:
                break
            csr_topk_doc_ids.append(local_docs[best_j])
            csr_topk_scores.append(best_tf * idf)
            local_tfs[best_j] = -1.0

        csr_topk_offsets[term_idx + 1] = csr_topk_offsets[term_idx] + len(csr_topk_doc_ids) - csr_topk_offsets[term_idx]

    return csr_term_offsets, csr_doc_ids, csr_scores, csr_idf, csr_topk_offsets, csr_topk_doc_ids, csr_topk_scores


# =====================================================================
# FAST-PATH CSR QUERY SCORING
# =====================================================================

def score_query_csr(query_terms: List[str], k: int,
                    term_list: List[str], term_to_idx: Dict[str, int], term_pool: Dict[str, TermEntry],
                    csr_term_offsets: List[int], csr_doc_ids: List[int],
                    csr_scores: List[float], csr_idf: List[float],
                    csr_topk_offsets: List[int], csr_topk_doc_ids: List[int],
                    csr_topk_scores: List[float]) -> List[SearchResult]:
    """Fast CSR single-term and multi-term query scoring."""
    max_docs = max(csr_doc_ids) + 1 if csr_doc_ids else 0
    if max_docs == 0:
        return []

    # Map query terms to term indices
    term_indices = []
    for qterm in query_terms:
        if qterm in term_pool:
            term_indices.append(term_to_idx[qterm])

    if not term_indices:
        return []

    # Single term fast path: use precomputed top-K
    if len(term_indices) == 1:
        tidx = term_indices[0]
        start = csr_topk_offsets[tidx]
        end = csr_topk_offsets[tidx + 1]
        num_results = min(end - start, k)
        results = []
        for i in range(num_results):
            doc_id = csr_topk_doc_ids[start + i]
            score = csr_topk_scores[start + i]
            results.append(SearchResult(doc_id, score))
        return results

    # Multi-term: accumulate scores
    doc_scores = [0.0] * (max_docs + 1)
    active_docs = []

    for tidx in term_indices:
        term_start = csr_term_offsets[tidx]
        term_end = csr_term_offsets[tidx + 1]
        idf = csr_idf[tidx]

        for i in range(term_start, term_end):
            doc_id = csr_doc_ids[i]
            tf = csr_scores[i]
            score = tf * idf

            if doc_scores[doc_id] == 0.0:
                active_docs.append(doc_id)
            doc_scores[doc_id] += score

    # Select top-K
    selected = []
    for _ in range(k):
        best_doc = -1
        best_score = 0.0
        for doc_id in active_docs:
            s = doc_scores[doc_id]
            if s > best_score:
                best_score = s
                best_doc = doc_id
        if best_doc == -1:
            break
        selected.append(SearchResult(best_doc, best_score))
        doc_scores[best_doc] = -1.0

    return selected


# =====================================================================
# RPR RING BUFFER SEARCH (matching frozen binary)
# =====================================================================

def rpr_search(query_terms: List[str], max_events: int,
               term_list: List[str], term_to_idx: Dict[str, int], term_pool: Dict[str, TermEntry],
               posting_pool: List[PostingEntry], flat_postings: List[int]) -> List[SearchResult]:
    """RPR ring buffer queue search: Scout -> Expand -> Evidence -> Pulse."""
    # Map query terms to term indices
    term_indices = []
    for qterm in query_terms:
        if qterm in term_pool:
            term_indices.append(term_to_idx[qterm])

    if not term_indices:
        return []

    # Ring buffer queue
    queue = []
    head = 0

    def queue_push(event):
        queue.append(event)

    def queue_pop():
        nonlocal head
        if head >= len(queue):
            return None
        event = queue[head]
        head += 1
        return event

    def queue_len():
        return len(queue) - head

    # Initialize with Scout events for each query term
    for tidx in term_indices:
        term = term_list[tidx]
        term_entry = term_pool[term]
        budget = 1000
        count = 0
        for pi in range(term_entry.postings_start, term_entry.postings_end):
            if count >= budget:
                break
            post_idx = flat_postings[pi]
            queue_push(RPREvent(RPREvent.EXPAND, post_idx=post_idx, depth=1))
            count += 1

    # Process events
    max_docs = max(p.doc_id for p in posting_pool) + 1 if posting_pool else 0
    doc_scores = [0.0] * (max_docs + 1)
    active_docs = []
    processed = 0

    while processed < max_events and queue_len() > 0:
        event = queue_pop()
        if event is None:
            break
        processed += 1

        if event.event_type == RPREvent.EXPAND:
            posting = posting_pool[event.post_idx]
            queue_push(RPREvent(RPREvent.EVIDENCE, doc_id=posting.doc_id, score=1.0, passage_idx=0))
        elif event.event_type == RPREvent.EVIDENCE:
            doc_id = event.doc_id
            if doc_scores[doc_id] == 0.0:
                active_docs.append(doc_id)
            doc_scores[doc_id] += event.score
        elif event.event_type == RPREvent.PULSE:
            if event.wave_id == 0:
                break

    # Collect results
    results = []
    for doc_id in active_docs:
        score = doc_scores[doc_id]
        if score > 0.0:
            results.append(SearchResult(doc_id, score))

    # Sort by score descending
    results.sort(key=lambda r: r.score, reverse=True)
    return results


# =====================================================================
# TIMING HELPERS
# =====================================================================

def median_of(latencies: List[float]) -> float:
    if not latencies:
        return 0.0
    sorted_lats = sorted(latencies)
    return sorted_lats[len(sorted_lats) // 2]


def p95_of(latencies: List[float]) -> float:
    if not latencies:
        return 0.0
    sorted_lats = sorted(latencies)
    idx = int(len(sorted_lats) * 0.95)
    return sorted_lats[idx]


# =====================================================================
# VERIFY QUERY (CSR + RPR)
# =====================================================================

def verify_query(query_text: str, k: int, label: str,
                 term_list: List[str], term_to_idx: Dict[str, int], term_pool: Dict[str, TermEntry],
                 posting_pool: List[PostingEntry], flat_postings: List[int],
                 csr_term_offsets: List[int], csr_doc_ids: List[int],
                 csr_scores: List[float], csr_idf: List[float],
                 csr_topk_offsets: List[int], csr_topk_doc_ids: List[int],
                 csr_topk_scores: List[float]):
    """Run CSR and RPR benchmarks for a query."""
    query_terms = tokenize(query_text)

    # CSR timing (10 reps)
    csr_lats = []
    csr_n = 0
    for _ in range(10):
        t0 = time.perf_counter()
        results = score_query_csr(query_terms, k, term_list, term_to_idx, term_pool,
                                   csr_term_offsets, csr_doc_ids, csr_scores, csr_idf,
                                   csr_topk_offsets, csr_topk_doc_ids, csr_topk_scores)
        t1 = time.perf_counter()
        csr_lats.append((t1 - t0) * 1000)  # ms
        csr_n = len(results)

    # RPR timing (10 reps)
    rpr_lats = []
    rpr_n = 0
    for _ in range(10):
        t0 = time.perf_counter()
        results = rpr_search(query_terms, 10000, term_list, term_to_idx, term_pool, posting_pool, flat_postings)
        t1 = time.perf_counter()
        rpr_lats.append((t1 - t0) * 1000)  # ms
        rpr_n = len(results)

    csr_median = median_of(csr_lats)
    csr_p95 = p95_of(csr_lats)
    rpr_median = median_of(rpr_lats)
    rpr_p95 = p95_of(rpr_lats)

    print(f"{label}\t{query_text}\t{k}\t{csr_median:.4f}\t{csr_p95:.4f}\t{csr_n}\t{rpr_median:.4f}\t{rpr_p95:.4f}\t{rpr_n}\t{processed if 'processed' in locals() else 0}")

    return {
        'label': label,
        'query': query_text,
        'k': k,
        'csr_median_ms': csr_median,
        'csr_p95_ms': csr_p95,
        'csr_n': csr_n,
        'rpr_median_ms': rpr_median,
        'rpr_p95_ms': rpr_p95,
        'rpr_n': rpr_n,
    }


# =====================================================================
# MAIN
# =====================================================================

def main():
    data_path = sys.argv[1] if len(sys.argv) > 1 else "/home/dev/neural_docs.txt"

    print("MITRE/RPR Neural Retrieval — Python on FS437 neuroscience data")
    print("=" * 60)
    print()

    # Ingest
    doc_pool, term_pool, term_list, term_to_idx, posting_pool, flat_postings, flat_positions = ingest_docs_from_file(data_path)

    # Rebuild flat postings (group by term, set postings_start/end)
    rebuild_flat_postings(term_list, term_pool, posting_pool, flat_postings)

    # Build CSR index
    (csr_term_offsets, csr_doc_ids, csr_scores, csr_idf,
     csr_topk_offsets, csr_topk_doc_ids, csr_topk_scores) = build_csr_index(
        doc_pool, term_list, term_to_idx, term_pool, posting_pool, flat_postings)

    print()
    print("label\tquery\tk\tcsr_median_ms\tcsr_p95_ms\tcsr_n\trpr_median_ms\trpr_p95_ms\trpr_n")

    # Run verification queries (same as Python baseline and Goose)
    results = []

    # Query 1: single electrode
    results.append(verify_query(
        "electrode:0", 10, "single_electrode",
        term_list, term_to_idx, term_pool, posting_pool, flat_postings,
        csr_term_offsets, csr_doc_ids, csr_scores, csr_idf,
        csr_topk_offsets, csr_topk_doc_ids, csr_topk_scores
    ))

    # Query 2: stimulation + electrode
    results.append(verify_query(
        "stimulation electrode:0", 10, "stim_plus_electrode",
        term_list, term_to_idx, term_pool, posting_pool, flat_postings,
        csr_term_offsets, csr_doc_ids, csr_scores, csr_idf,
        csr_topk_offsets, csr_topk_doc_ids, csr_topk_scores
    ))

    # Query 3: known miss
    results.append(verify_query(
        "electrode:999", 10, "known_miss",
        term_list, term_to_idx, term_pool, posting_pool, flat_postings,
        csr_term_offsets, csr_doc_ids, csr_scores, csr_idf,
        csr_topk_offsets, csr_topk_doc_ids, csr_topk_scores
    ))

    print()
    print("MITRE/RPR neural retrieval benchmark complete.")

    # Save results
    import json
    with open('mitre_rpr_python_results.json', 'w') as f:
        json.dump({
            'dataset': 'fs437',
            'documents': len(doc_pool),
            'terms': len(term_list),
            'queries': results
        }, f, indent=2)

    return results


if __name__ == "__main__":
    main()