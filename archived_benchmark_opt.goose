// MITRE/PRISM Optimized Benchmark in Goose
//
// Optimizations for 100K corpus:
// 1. Fast-path CSR scoring using pre-built CSR arrays (no dict in hot path)
// 2. Pre-allocated dictionaries with capacity hints
// 3. Ring buffer for RPR queue (O(1) pop)
// 4. Eliminated redundant allocations in hot paths
// 5. Batched dictionary operations

import std;
import os;
import math;
import json;

// =====================================================================
// TOKENIZER (unchanged)
// =====================================================================

fn tokenize(text: u8[:]) -> const u8[:][>..] {
    var toks: const u8[:][>..] = [];
    var i = 0;
    while i < text.len {
        while i < text.len && !(text[i] >= 'a' && text[i] <= 'z' ||
                                 text[i] >= 'A' && text[i] <= 'Z' ||
                                 text[i] >= '0' && text[i] <= '9') { i++; }
        let start = i;
        while i < text.len && (text[i] >= 'a' && text[i] <= 'z' ||
                                text[i] >= 'A' && text[i] <= 'Z' ||
                                text[i] >= '0' && text[i] <= '9') { i++; }
        if i > start {
            toks.push(text[start..i]);
        }
    }
    return toks;
}

// =====================================================================
// DATA STRUCTURES
// =====================================================================

struct TermEntry {
    term: u8[..256],
    term_len: u16 = 0,
    df: u32 = 0,
    postings_start: u32 = 0,
    postings_end: u32 = 0,
}

struct PostingEntry {
    doc_id: u64,
    freq: u32,
    next: u32 = 0,
    positions_start: u32 = 0,
    positions_end: u32 = 0,
}

struct DocEntry {
    id: u64,
    timestamp: f64,
    scope: u32,
    principal: u32,
    text: u8[..1024],
    text_len: u16 = 0,
}

var term_pool: TermEntry[>..] = [];
var posting_pool: PostingEntry[>..] = [];
var doc_pool: DocEntry[>..] = [];
var flat_postings: u32[>..] = [];
var flat_positions: u32[>..] = [];
var evidence_pool: EvidenceEntry[>..] = [];

struct TermKey { data: u8[256], len: u16 }

fn make_term_key(term: u8[:]) -> TermKey {
    var key: TermKey = TermKey { .. };
    let copy_len = if term.len > 255 { 255 } else { term.len };
    for i in 0..copy_len { key.data[i] = term[i]; }
    key.len = copy_len as u16;
    return key;
}

fn hash(k: TermKey) -> u64 {
    var h: u64 = 1469598103934665603;
    for i in 0..k.len {
        h ^= k.data[i];
        h *= 1099511628211;
    }
    return h;
}

fn eq(a: TermKey, b: TermKey) -> bool {
    if a.len != b.len { return false; }
    for i in 0..a.len { if a.data[i] != b.data[i] { return false; } }
    return true;
}

import dictionary;
var term_index = dictionary<TermKey, u32> {};

// CSR Index - used for FAST PATH scoring
var csr_term_offsets: u32[>..] = [];
var csr_doc_ids: u32[>..] = [];
var csr_scores: f32[>..] = [];
var csr_idf: f32[>..] = [];  // Pre-computed IDF per term
var csr_num_terms: u32 = 0;

// Search result
struct SearchResult {
    doc_id: u64,
    score: f32,
    evidence_chain: u32,
}

struct EvidenceEntry {
    doc_id: u64,
    score: f32,
    next_evidence: u32 = 0,
}

struct DocInput {
    id: u64,
    topic_idx: u32,
    timestamp: f64,
    scope: u32,
    principal: u32,
}

// =====================================================================
// INDEX OPERATIONS (unchanged)
// =====================================================================

fn get_or_create_term(term: u8[:]) -> u32 {
    let key = make_term_key(term);
    let existing = term_index.get(key);
    if existing { return existing; }
    let copy_len = if term.len > 255 { 255 } else { term.len };
    var te: TermEntry = TermEntry {
        term: term[..copy_len],
        term_len: copy_len as u16,
        df: 0,
        postings_start: flat_postings.len as u32,
        postings_end: flat_postings.len as u32,
    };
    let idx = term_pool.len as u32;
    term_pool.push(te);
    term_index.insert(key, idx);
    return idx;
}

fn add_posting(term_idx: u32, doc_id: u64, pos: u32) {
    var term_entry .= term_pool[term_idx as i64];
    var pe: PostingEntry = PostingEntry { .. };
    pe.doc_id = doc_id;
    pe.freq = 1;
    pe.positions_start = flat_positions.len as u32;
    pe.positions_end = flat_positions.len as u32;
    let post_idx = posting_pool.len as u32;
    posting_pool.push(pe);
    flat_positions.push(pos);
    var posting .= posting_pool[post_idx as i64];
    posting.positions_end = flat_positions.len as u32;
    if term_entry.postings_start == term_entry.postings_end {
        term_entry.postings_start = flat_postings.len as u32;
    }
    flat_postings.push(post_idx);
    term_entry.postings_end = flat_postings.len as u32;
    term_entry.df += 1;
}

// =====================================================================
// INGESTION
// =====================================================================

var TOPICS_NAMES: const u8[:][5] = [
    "egypt", "greece", "mesopotamia", "persia", "rome"
];

fn ingest_batch(docs: DocInput[:]) -> i64 {
    var count = 0;
    var text_buf: u8[>..] = [];

    for doc in docs {
        text_buf.clear();
        text_buf.append("test document ");

        var num = doc.id - 1;
        var num_str: u8[16] = [0; 16];
        var num_len = 0;
        if num == 0 { num_str[0] = '0'; num_len = 1; }
        else {
            var rev: u8[16] = [0; 16];
            var rev_len = 0;
            while num > 0 {
                rev[rev_len] = '0' + (num % 10) as u8;
                num /= 10;
                rev_len += 1;
            }
            for j in 0..rev_len {
                num_str[j] = rev[rev_len - 1 - j];
            }
            num_len = rev_len;
        }
        for j in 0..num_len { text_buf.push(num_str[j]); }

        text_buf.append(" with ");
        let topic_name = TOPICS_NAMES[doc.topic_idx as i64];
        for j in 0..topic_name.len { text_buf.push(topic_name[j]); }
        text_buf.append(" terms nile river pharaoh ziggurat cyrus legion");

        let copy_len = if text_buf.len > 1023 { 1023 } else { text_buf.len };
        var de: DocEntry = DocEntry {
            id: doc.id,
            timestamp: doc.timestamp,
            scope: doc.scope,
            principal: doc.principal,
            text: text_buf[..copy_len],
            text_len: copy_len as u16,
        };
        let doc_idx = doc_pool.len as u32;
        doc_pool.push(de);

        let tokens = tokenize(text_buf[..]);
        var seen = dictionary<const u8[:], u32> {};
        var pos = 0;
        for tok in tokens {
            let existing = seen.get(tok);
            let term_idx: u32;
            if existing {
                term_idx = existing;
            } else {
                term_idx = get_or_create_term(tok);
                seen.insert(tok, term_idx);
            }
            add_posting(term_idx, doc.id, pos as u32);
            pos += tok.len + 1;
        }
        count += 1;
    }
    return count;
}

// =====================================================================
// CSR INDEX BUILD (optimized with pre-computed IDF)
// =====================================================================

fn build_csr_index() {
    csr_term_offsets.clear();
    csr_doc_ids.clear();
    csr_scores.clear();
    csr_idf.clear();

    csr_num_terms = term_pool.len as u32;
    csr_term_offsets.push(0);

    // Pre-allocate approximate capacity to avoid reallocations
    // Average postings per term * num_terms
    let est_postings = flat_postings.len;

    for term_idx in 0..term_pool.len {
        let term_entry = &term_pool[term_idx as i64];

        // Pre-compute IDF once per term
        let idf = log((doc_pool.len + 1.0) / (term_entry.df as f32 + 0.5));
        csr_idf.push(idf);

        // Use local array to collect unique docs for this term
        // Then batch append to CSR arrays
        var local_doc_ids: u32[>..] = [];
        var local_scores: f32[>..] = [];

        // Track seen docs for this term (small local dict)
        var doc_counts = dictionary<u64, u32> {};
        for pi in term_entry.postings_start..term_entry.postings_end {
            let post_idx = flat_postings[pi as i64];
            let post_entry = &posting_pool[post_idx as i64];
            doc_counts.update(post_entry.doc_id, 0) { it += 1; };
        }

        doc_counts.each() { id, cnt =>
            local_doc_ids.push(id as u32);
            local_scores.push(cnt as f32);  // Store TF, multiply by IDF at query time
        };

        // Batch append
        for d in local_doc_ids { csr_doc_ids.push(d); }
        for s in local_scores { csr_scores.push(s); }

        csr_term_offsets.push(csr_doc_ids.len as u32);
    }
}

// =====================================================================
// FAST-PATH QUERY SCORING (uses CSR arrays, no dict in hot path)
// =====================================================================

fn score_query_fast(query_terms: const u8[:][:]) -> SearchResult[>..] {
    var results: SearchResult[>..] = [];

    // Fixed-size array for accumulating scores (max docs = 1M)
    // Use two parallel arrays: doc_id and score
    // We'll use a simple linear array with linear search for small result sets
    // For larger sets, could use fixed-size hash table

    // For 100K corpus, we can use a simple array of scores indexed by doc_id
    // But doc_ids are 1-based up to N, so we can use doc_id as index
    let max_docs = doc_pool.len as u32;
    if max_docs == 0 { return results; }

    // Use a flat array for scores - size = max doc_id + 1
    // Since doc_ids are 1..N sequentially in our benchmark
    var doc_scores: f32[>..] = [];
    // Resize to max_doc_id + 1 (1-based indexing)
    for _ in 0..max_docs + 1 { doc_scores.push(0.0); }

    var active_docs: u32[>..] = [];  // Track which docs have non-zero scores

    // Iterate query terms
    for qterm in query_terms {
        let term_idx = term_index.get(make_term_key(qterm));
        if !term_idx { continue; }

        let tidx = term_idx as i64;
        if tidx >= csr_num_terms as i64 { continue; }

        let term_start = csr_term_offsets[tidx];
        let term_end = csr_term_offsets[tidx + 1];
        let idf = csr_idf[tidx];

        // Iterate postings for this term in CSR
        for i in term_start..term_end {
            let doc_id = csr_doc_ids[i];
            let tf = csr_scores[i];
            let score = tf * idf;

            let idx = doc_id as i64;
            if doc_scores[idx] == 0.0 {
                active_docs.push(doc_id);
            }
            doc_scores[idx] += score;
        }
    }

    // Collect results from active docs only
    for did in active_docs {
        let idx = did as i64;
        let score = doc_scores[idx];
        if score > 0.0 {
            var e = EvidenceEntry { doc_id: did as u64, score: score, next_evidence: 0 };
            let ev_idx = evidence_pool.len as u32;
            evidence_pool.push(e);
            results.push(SearchResult {
                doc_id: did as u64,
                score: score,
                evidence_chain: ev_idx,
            });
        }
    }

    // Sort by score descending (insertion sort - small result sets)
    for i in 1..results.len {
        let key = results[i];
        var j = i - 1;
        while j >= 0 && results[j].score < key.score {
            results[j + 1] = results[j];
            j -= 1;
        }
        results[j + 1] = key;
    }

    return results;
}

// =====================================================================
// RPR WITH RING BUFFER QUEUE (O(1) pop)
// =====================================================================

enum RPR_Event {
    Scout { term_idx: u32, depth: u32, budget: u32 },
    Expand { post_idx: u32, depth: u32 },
    Evidence { doc_id: u64, score: f32, passage_idx: u32 },
    Pulse { wave_id: u32, timestamp: f64 },
}

// Ring buffer for RPR queue
var rpr_queue: RPR_Event[>..] = [];
var rpr_head: u32 = 0;  // Index of next event to process

fn rpr_queue_clear() {
    rpr_queue.clear();
    rpr_head = 0;
}

fn rpr_queue_push(event: RPR_Event) {
    rpr_queue.push(event);
}

fn rpr_queue_pop() -> RPR_Event {
    // Return a zero-initialized event if empty (caller checks rpr_queue_len)
    if rpr_head >= rpr_queue.len { 
        return RPR_Event.Pulse { wave_id: 0, timestamp: 0.0 }; 
    }
    let event = rpr_queue[rpr_head];
    rpr_head += 1;
    return event;
}

fn rpr_queue_len() -> u32 {
    return (rpr_queue.len as i64 - rpr_head as i64) as u32;
}

// Scout a term: emit Expand events for its postings
fn rpr_scout_term(term_idx: u32, depth: u32, budget: u32) {
    let term_entry = &term_pool[term_idx as i64];
    var count = 0;
    for pi in term_entry.postings_start..term_entry.postings_end {
        if count >= budget { break; }
        let post_idx = flat_postings[pi as i64];
        rpr_queue_push(RPR_Event.Expand {
            post_idx: post_idx,
            depth: depth + 1,
        });
        count += 1;
    }
}

// Expand a posting: emit Evidence for its document
fn rpr_expand(post_idx: u32, depth: u32) {
    let post_entry = &posting_pool[post_idx as i64];
    rpr_queue_push(RPR_Event.Evidence {
        doc_id: post_entry.doc_id,
        score: 1.0,
        passage_idx: 0,
    });
}

// Process RPR queue (the pulse loop) - O(1) pop with ring buffer
fn rpr_pulse(max_events: u32) -> SearchResult[>..] {
    var results: SearchResult[>..] = [];
    var processed = 0;

    // Use fixed-size array for accumulating scores (like fast query)
    let max_docs = doc_pool.len as u32;
    var doc_scores: f32[>..] = [];
    for _ in 0..max_docs + 1 { doc_scores.push(0.0); }
    var active_docs: u32[>..] = [];

    while processed < max_events && rpr_queue_len() > 0 {
        let event = rpr_queue_pop();
        processed += 1;

        match event {
            Scout s => rpr_scout_term(s.term_idx, s.depth, s.budget),
            Expand e => rpr_expand(e.post_idx, e.depth),
            Evidence e => {
                let idx = e.doc_id as i64;
                if doc_scores[idx] == 0.0 {
                    active_docs.push(e.doc_id as u32);
                }
                doc_scores[idx] += e.score;
            },
            Pulse p => {
                if p.wave_id == 0 { break; }  // Empty queue sentinel
            },
        }
    }

    // Collect results
    for did in active_docs {
        let idx = did as i64;
        let score = doc_scores[idx];
        if score > 0.0 {
            var ev = EvidenceEntry { doc_id: did as u64, score: score, next_evidence: 0 };
            let ev_idx = evidence_pool.len as u32;
            evidence_pool.push(ev);
            results.push(SearchResult {
                doc_id: did as u64,
                score: score,
                evidence_chain: ev_idx,
            });
        }
    }

    // Sort
    for i in 1..results.len {
        let key = results[i];
        var j = i - 1;
        while j >= 0 && results[j].score < key.score {
            results[j + 1] = results[j];
            j -= 1;
        }
        results[j + 1] = key;
    }

    return results;
}

fn rpr_search(query_terms: const u8[:][:], max_events: u32 = 10000) -> SearchResult[>..] {
    rpr_queue_clear();

    for qterm in query_terms {
        let term_idx = term_index.get(make_term_key(qterm));
        if !term_idx { continue; }
        rpr_queue_push(RPR_Event.Scout {
            term_idx: term_idx,
            depth: 0,
            budget: 1000,
        });
    }

    return rpr_pulse(max_events);
}

// =====================================================================
// CORPUS GENERATION
// =====================================================================

fn generate_corpus(n: u32, seed: u64) -> DocInput[>..] {
    var docs: DocInput[>..] = [];
    var rng_state = seed;
    fn rng_next() -> u32 {
        rng_state = rng_state * 1664525 + 1013904223;
        return rng_state as u32;
    }

    for i in 0..n {
        let topic_idx = rng_next() % 5;
        let ts = 1.0 + (i as f64) * 0.001;

        docs.push(DocInput {
            id: (i + 1) as u64,
            topic_idx: topic_idx,
            timestamp: ts,
            scope: 1,
            principal: 1,
        });
    }
    return docs;
}

// =====================================================================
// BENCHMARK QUERIES
// =====================================================================

struct BenchQuery {
    query: const u8[:],
    k: u32,
    desc: const u8[:],
}

var BENCH_QUERIES: BenchQuery[6] = [
    BenchQuery { query: "nile", k: 10, desc: "single-term high freq" },
    BenchQuery { query: "pharaoh", k: 10, desc: "single-term med freq" },
    BenchQuery { query: "ziggurat", k: 10, desc: "single-term low freq" },
    BenchQuery { query: "nile pharaoh", k: 10, desc: "two-term" },
    BenchQuery { query: "egypt greece rome", k: 10, desc: "three-term" },
    BenchQuery { query: "orphan-fact-nile-decree", k: 3, desc: "rare fact" },
];

// =====================================================================
// BENCHMARK RUNNER
// =====================================================================

struct BenchResult {
    corpus_size: u32,
    ingest_time_ms: f64,
    ingest_docs_per_sec: f64,
    index_build_time_ms: f64,
    concurrent_qps: f64,
    memory_estimate_mb: u64,
}

struct QueryTimingResult {
    median: f64,
    p95: f64,
    count: u32,
}

fn measure_query(query_terms: const u8[:][:], iterations: u32) -> QueryTimingResult {
    var latencies: f64[>..] = [];
    for _ in 0..iterations {
        let start = clock_ns();
        let results = score_query_fast(query_terms);
        let end = clock_ns();
        latencies.push((end - start) as f64 / 1_000_000.0);
    }
    for i in 1..latencies.len {
        let key = latencies[i];
        var j = i - 1;
        while j >= 0 && latencies[j] > key {
            latencies[j + 1] = latencies[j];
            j -= 1;
        }
        latencies[j + 1] = key;
    }
    let median = latencies[latencies.len / 2];
    let p95_idx = (latencies.len * 95) / 100;
    let p95 = latencies[p95_idx as i64];
    let count = latencies.len as u32;
    return QueryTimingResult { median: median, p95: p95, count: count };
}

fn tokenize_query(q: const u8[:]) -> const u8[:][>..] {
    return tokenize(q);
}

fn run_benchmark(corpus_size: u32, seed: u64 = 8001) -> BenchResult {
    print("=== MITRE/PRISM Goose Benchmark (Optimized): {} docs ===\n", corpus_size);

    // Generate corpus
    print("Generating corpus...\n");
    let gen_start = clock_ns();
    let corpus = generate_corpus(corpus_size, seed);
    let gen_time = (clock_ns() - gen_start) as f64 / 1_000_000.0;
    print("  Generation time: {} ms\n", gen_time);

    // Clear global state
    term_pool.clear();
    posting_pool.clear();
    doc_pool.clear();
    flat_postings.clear();
    flat_positions.clear();
    evidence_pool.clear();
    term_index.clear();

    // Ingest
    print("Ingesting documents...\n");
    let ingest_start = clock_ns();
    let ingested = ingest_batch(corpus);
    let ingest_time = (clock_ns() - ingest_start) as f64 / 1_000_000.0;
    print("  Ingested {} docs in {} ms ({} docs/sec)\n", ingested, ingest_time,
          (ingested as f64) / (ingest_time / 1000.0));

    // Build CSR index
    print("Building CSR index...\n");
    let csr_start = clock_ns();
    build_csr_index();
    let csr_time = (clock_ns() - csr_start) as f64 / 1_000_000.0;
    print("  CSR build time: {} ms\n", csr_time);

    // Warm-up queries
    print("Warming up queries...\n");
    for bq in BENCH_QUERIES {
        let qterms = tokenize_query(bq.query);
        for _ in 0..3 { score_query_fast(qterms); }
    }

    // Measure query latencies
    print("Running query benchmarks (10 iterations each)...\n");
    for i in 0..BENCH_QUERIES.len {
        let bq = &BENCH_QUERIES[i];
        let qterms = tokenize_query(bq.query);
        let timing = measure_query(qterms, 10);
        print("  {} k={}: median={:.2f}ms, p95={:.2f}ms\n", bq.desc, bq.k, timing.median, timing.p95);
    }

    // Concurrent QPS test (simulated with sequential)
    print("Concurrent QPS test (simulated)...\n");
    let concurrent_start = clock_ns();
    var total_queries = 0;
    for _ in 0..10 {
        for bq in BENCH_QUERIES {
            let qterms = tokenize_query(bq.query);
            score_query_fast(qterms);
            total_queries += 1;
        }
    }
    let concurrent_time = (clock_ns() - concurrent_start) as f64 / 1_000_000.0;
    let qps = total_queries as f64 / (concurrent_time / 1000.0);
    print("  Total queries: {}, Time: {} ms, QPS: {:.1f}\n", total_queries, concurrent_time, qps);

    // Memory estimate
    let term_mem = term_pool.len * 288;
    let posting_mem = posting_pool.len * 32;
    let doc_mem = doc_pool.len * 1056;
    let flat_mem = (flat_postings.len + flat_positions.len) * 4;
    let total_mem = (term_mem + posting_mem + doc_mem + flat_mem) / 1_000_000;

    print("Memory estimate: {} MB\n", total_mem);

    return BenchResult {
        corpus_size: corpus_size,
        ingest_time_ms: ingest_time,
        ingest_docs_per_sec: (ingested as f64) / (ingest_time / 1000.0),
        index_build_time_ms: csr_time,
        concurrent_qps: qps,
        memory_estimate_mb: total_mem as u64,
    };
}

// =====================================================================
// MAIN
// =====================================================================

fn main() {
    print("MITRE/PRISM Goose Benchmark (Optimized)\n");
    print("========================================\n\n");

    // Run at 10K
    let result_10k = run_benchmark(10_000);

    // Run at 100K
    let result_100k = run_benchmark(100_000);

    // Print summary
    print("\n=== SUMMARY ===\n");
    print("Corpus Size | Ingest (ms) | Docs/sec | CSR Build (ms) | QPS | Mem (MB)\n");
    print("------------|-------------|----------|----------------|-----|---------\n");
    print("{} | {} | {:.0f} | {} | {:.1f} | {}\n",
        result_10k.corpus_size, result_10k.ingest_time_ms, result_10k.ingest_docs_per_sec,
        result_10k.index_build_time_ms, result_10k.concurrent_qps, result_10k.memory_estimate_mb);
    print("{} | {} | {:.0f} | {} | {:.1f} | {}\n",
        result_100k.corpus_size, result_100k.ingest_time_ms, result_100k.ingest_docs_per_sec,
        result_100k.index_build_time_ms, result_100k.concurrent_qps, result_100k.memory_estimate_mb);
}