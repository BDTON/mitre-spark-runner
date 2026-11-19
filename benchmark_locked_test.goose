// MITRE/PRISM Locked Test - Goose benchmark on labeled questions
// Processes queries one at a time from goose_queries.txt, outputs CSR + RPR timings.

import std;
import os;
import math;

// =====================================================================
// TOKENIZER
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
    term_idx: u32 = 0,
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

var csr_term_offsets: u32[>..] = [];
var csr_doc_ids: u32[>..] = [];
var csr_scores: f32[>..] = [];
var csr_idf: f32[>..] = [];
var csr_num_terms: u32 = 0;

var csr_topk_offsets: u32[>..] = [];
var csr_topk_doc_ids: u32[>..] = [];
var csr_topk_scores: f32[>..] = [];
const CSR_MAX_K: u32 = 10;

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
// INDEX OPERATIONS
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
    pe.term_idx = term_idx;
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

fn rebuild_flat_postings() {
    let num_terms = term_pool.len as u32;
    if num_terms == 0 { return; }

    var term_starts: u32[>..] = [];
    var running: u32 = 0;
    for i in 0..num_terms {
        term_starts.push(running);
        running += term_pool[i as i64].df;
    }

    var cursor: u32[>..] = [];
    for i in 0..num_terms {
        cursor.push(term_starts[i]);
    }

    var new_flat_postings: u32[>..] = [];
    for _ in 0..flat_postings.len {
        new_flat_postings.push(0);
    }

    for pi in 0..posting_pool.len {
        let post_entry = &posting_pool[pi as i64];
        let t = post_entry.term_idx as i64;
        let pos = cursor[t] as i64;
        new_flat_postings[pos] = pi as u32;
        cursor[t] += 1;
    }

    flat_postings.clear();
    for p in new_flat_postings {
        flat_postings.push(p);
    }

    for i in 0..num_terms {
        let start = term_starts[i];
        let end = start + term_pool[i as i64].df;
        var te .= term_pool[i as i64];
        te.postings_start = start;
        te.postings_end = end;
    }
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
// CSR INDEX BUILD
// =====================================================================

fn build_csr_index() {
    csr_term_offsets.clear();
    csr_doc_ids.clear();
    csr_scores.clear();
    csr_idf.clear();

    csr_num_terms = term_pool.len as u32;
    csr_term_offsets.push(0);

    for term_idx in 0..term_pool.len {
        let term_entry = &term_pool[term_idx as i64];
        let idf = log((doc_pool.len + 1.0) / (term_entry.df as f32 + 0.5));
        csr_idf.push(idf);

        var local_doc_ids: u32[>..] = [];
        var local_scores: f32[>..] = [];

        var doc_counts = dictionary<u64, u32> {};
        for pi in term_entry.postings_start..term_entry.postings_end {
            let post_idx = flat_postings[pi as i64];
            let post_entry = &posting_pool[post_idx as i64];
            doc_counts.update(post_entry.doc_id, 0) { it += 1; };
        }

        doc_counts.each() { id, cnt =>
            local_doc_ids.push(id as u32);
            local_scores.push(cnt as f32);
        };

        for d in local_doc_ids { csr_doc_ids.push(d); }
        for s in local_scores { csr_scores.push(s); }

        csr_term_offsets.push(csr_doc_ids.len as u32);
    }

    csr_topk_offsets.clear();
    csr_topk_doc_ids.clear();
    csr_topk_scores.clear();
    csr_topk_offsets.push(0);

    for term_idx in 0..term_pool.len {
        let term_start = csr_term_offsets[term_idx as i64];
        let term_end = csr_term_offsets[term_idx as i64 + 1];
        let idf = csr_idf[term_idx as i64];
        let num_postings = term_end - term_start;

        var local_doc_ids: u32[>..] = [];
        var local_tfs: f32[>..] = [];
        for i in 0..num_postings {
            local_doc_ids.push(csr_doc_ids[term_start + i]);
            local_tfs.push(csr_scores[term_start + i]);
        }

        let topk_count = if num_postings < CSR_MAX_K { num_postings } else { CSR_MAX_K };
        for _ in 0..topk_count {
            var best_j: u32 = 0;
            var best_tf: f32 = 0.0;
            for j in 0..num_postings {
                let t = local_tfs[j];
                if t > best_tf {
                    best_tf = t;
                    best_j = j as u32;
                }
            }
            if best_tf <= 0.0 { break; }
            csr_topk_doc_ids.push(local_doc_ids[best_j]);
            csr_topk_scores.push(best_tf * idf);
            local_tfs[best_j as i64] = -1.0;
        }

        csr_topk_offsets.push(csr_topk_doc_ids.len as u32);
    }
}

// =====================================================================
// FAST-PATH QUERY SCORING (CSR diagnostic)
// =====================================================================

fn score_query_fast(query_terms: const u8[:][:], k: u32) -> SearchResult[>..] {
    var results: SearchResult[>..] = [];

    let max_docs = doc_pool.len as u32;
    if max_docs == 0 { return results; }

    if query_terms.len == 1 {
        let term_idx = term_index.get(make_term_key(query_terms[0]));
        if term_idx {
            let tidx = term_idx as i64;
            if tidx < csr_num_terms as i64 {
                let start = csr_topk_offsets[tidx];
                let end = csr_topk_offsets[tidx + 1];
                let num_results = if (end - start) < k { end - start } else { k };
                for i in 0..num_results {
                    let doc_id = csr_topk_doc_ids[start + i];
                    let score = csr_topk_scores[start + i];
                    var ev = EvidenceEntry { doc_id: doc_id, score: score, next_evidence: 0 };
                    let ev_idx = evidence_pool.len as u32;
                    evidence_pool.push(ev);
                    results.push(SearchResult {
                        doc_id: doc_id,
                        score: score,
                        evidence_chain: ev_idx,
                    });
                }
                return results;
            }
        }
        return results;
    }

    var doc_scores: f32[>..] = [];
    for _ in 0..max_docs + 1 { doc_scores.push(0.0); }

    var active_docs: u32[>..] = [];

    for qterm in query_terms {
        let term_idx = term_index.get(make_term_key(qterm));
        if !term_idx { continue; }

        let tidx = term_idx as i64;
        if tidx >= csr_num_terms as i64 { continue; }

        let term_start = csr_term_offsets[tidx];
        let term_end = csr_term_offsets[tidx + 1];
        let idf = csr_idf[tidx];

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

    var selected_docs: u32[>..] = [];
    var selected_scores: f32[>..] = [];
    for _ in 0..k {
        var best_doc: u32 = 0;
        var best_score: f32 = 0.0;
        for did in active_docs {
            let idx = did as i64;
            let s = doc_scores[idx];
            if s > best_score || (s == best_score && did < best_doc) {
                best_score = s;
                best_doc = did;
            }
        }
        if best_doc == 0 { break; }
        selected_docs.push(best_doc);
        selected_scores.push(best_score);
        doc_scores[best_doc as i64] = -1.0;
    }

    for i in 0..selected_docs.len {
        let did = selected_docs[i];
        let score = selected_scores[i];
        var ev = EvidenceEntry { doc_id: did, score: score, next_evidence: 0 };
        let ev_idx = evidence_pool.len as u32;
        evidence_pool.push(ev);
        results.push(SearchResult {
            doc_id: did,
            score: score,
            evidence_chain: ev_idx,
        });
    }

    return results;
}

// =====================================================================
// RPR WITH RING BUFFER QUEUE
// =====================================================================

enum RPR_Event {
    Scout { term_idx: u32, depth: u32, budget: u32 },
    Expand { post_idx: u32, depth: u32 },
    Evidence { doc_id: u64, score: f32, passage_idx: u32 },
    Pulse { wave_id: u32, timestamp: f64 },
}

var rpr_queue: RPR_Event[>..] = [];
var rpr_head: u32 = 0;
var rpr_events_processed: u32 = 0;

// Profiling instrumentation (enabled via RPR_PROFILE=1 env var)
var profiling_enabled: bool = false;
var rpr_setup_lats: f64[>..] = [];    // rpr_search queue setup (Scout pushes)
var rpr_scorebuf_lats: f64[>..] = []; // rpr_pulse score-buffer init
var rpr_eventq_lats: f64[>..] = [];   // rpr_pulse event-queue processing
var rpr_sort_lats: f64[>..] = [];     // rpr_pulse candidate sorting
var compare_mismatches: u32 = 0;      // bounded top-k vs full sort mismatches
var compare_debug_count: u32 = 0;     // debug counter for first few mismatches

fn rpr_queue_clear() {
    rpr_queue.clear();
    rpr_head = 0;
}

fn rpr_queue_push(event: RPR_Event) {
    rpr_queue.push(event);
}

fn rpr_queue_pop() -> RPR_Event {
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

fn rpr_expand(post_idx: u32, depth: u32) {
    let post_entry = &posting_pool[post_idx as i64];
    rpr_queue_push(RPR_Event.Evidence {
        doc_id: post_entry.doc_id,
        score: 1.0,
        passage_idx: 0,
    });
}

fn rpr_pulse(max_events: u32) -> SearchResult[>..] {
    var results: SearchResult[>..] = [];
    var processed = 0;

    // Score-buffer initialization timing
    var sb_start: f64 = 0.0;
    if profiling_enabled { sb_start = clock_ns(); }

    let max_docs = doc_pool.len as u32;
    var doc_scores: f32[>..] = [];
    for _ in 0..max_docs + 1 { doc_scores.push(0.0); }
    var active_docs: u32[>..] = [];

    if profiling_enabled {
        let sb_end = clock_ns();
        rpr_scorebuf_lats.push((sb_end - sb_start) as f64 / 1_000_000.0);
    }

    // Event-queue processing timing
    var eq_start: f64 = 0.0;
    if profiling_enabled { eq_start = clock_ns(); }

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
                if p.wave_id == 0 { break; }
            },
        }
    }

    if profiling_enabled {
        let eq_end = clock_ns();
        rpr_eventq_lats.push((eq_end - eq_start) as f64 / 1_000_000.0);
    }

    rpr_events_processed = processed as u32;

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

    // Candidate sorting timing
    var sort_start: f64 = 0.0;
    if profiling_enabled { sort_start = clock_ns(); }

    for i in 1..results.len {
        let key = results[i];
        var j = i - 1;
        while j >= 0 && results[j].score < key.score {
            results[j + 1] = results[j];
            j -= 1;
        }
        results[j + 1] = key;
    }

    if profiling_enabled {
        let sort_end = clock_ns();
        rpr_sort_lats.push((sort_end - sort_start) as f64 / 1_000_000.0);
    }

    return results;
}

// =====================================================================
// RPR WITH BOUNDED TOP-K SELECTION (optimization candidate)
// =====================================================================
// Replaces full insertion sort (O(n^2)) with bounded top-k selection (O(n*k)),
// preserving exact results and tie-breaking (score desc, doc_id asc for ties).

var rpr_bounded_sort_lats: f64[>..] = [];

fn rpr_pulse_bounded(max_events: u32, top_k: u32) -> SearchResult[>..] {
    var results: SearchResult[>..] = [];
    var processed = 0;

    // Score-buffer initialization
    let max_docs = doc_pool.len as u32;
    var doc_scores: f32[>..] = [];
    for _ in 0..max_docs + 1 { doc_scores.push(0.0); }
    var active_docs: u32[>..] = [];

    // Event-queue processing
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
                if p.wave_id == 0 { break; }
            },
        }
    }

    rpr_events_processed = processed as u32;

    // Build unsorted results
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

    // Bounded top-k selection sort (O(n*k) instead of O(n^2)),
    // preserves insertion order for tied scores (matches stable sort).
    var sort_start: f64 = 0.0;
    if profiling_enabled { sort_start = clock_ns(); }

    let n: u32 = results.len as u32;
    let limit: u32 = if top_k < n { top_k } else { n };
    var used: bool[>..] = [];
    for _ in 0..n { used.push(false); }
    var bounded: SearchResult[>..] = [];
    for i in 0..limit {
        var best_idx: i64 = -1;
        var j: i64 = 0;
        while j < n as i64 {
            if !used[j] {
                if best_idx == -1 || results[j].score > results[best_idx].score {
                    best_idx = j;
                }
                // Equal scores: keep earlier index (lower j) = insertion order
            }
            j += 1;
        }
        if best_idx == -1 { break; }
        used[best_idx] = true;
        bounded.push(results[best_idx]);
    }

    if profiling_enabled {
        let sort_end = clock_ns();
        rpr_bounded_sort_lats.push((sort_end - sort_start) as f64 / 1_000_000.0);
    }

    return bounded;
}

fn rpr_search(query_terms: const u8[:][:], max_events: u32 = 10000) -> SearchResult[>..] {
    var setup_start: f64 = 0.0;
    if profiling_enabled { setup_start = clock_ns(); }

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

    if profiling_enabled {
        let setup_end = clock_ns();
        rpr_setup_lats.push((setup_end - setup_start) as f64 / 1_000_000.0);
    }

    return rpr_pulse(max_events);
}

fn rpr_search_bounded(query_terms: const u8[:][:], max_events: u32 = 10000, top_k: u32 = 10) -> SearchResult[>..] {
    var setup_start: f64 = 0.0;
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

    if profiling_enabled {
        let setup_end = clock_ns();
        rpr_setup_lats.push((setup_end - setup_start) as f64 / 1_000_000.0);
    }

    return rpr_pulse_bounded(max_events, top_k);
}

// =====================================================================
// CORPUS GENERATION
// =====================================================================

fn generate_corpus(n: u32, seed: u64) -> DocInput[>..] {
    var docs: DocInput[>..] = [];
    var rng_state = seed;

    for i in 0..n {
        rng_state = rng_state * 1664525 + 1013904223;
        let topic_idx = rng_state as u32 % 5;
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
// TIMING HELPERS
// =====================================================================

fn median_of(latencies: f64[>..]) -> f64 {
    if latencies.len == 0 { return 0.0; }
    var sorted: f64[>..] = [];
    for l in latencies { sorted.push(l); }
    for a in 1..sorted.len {
        let key = sorted[a];
        var b = a - 1;
        while b >= 0 && sorted[b] > key {
            sorted[b + 1] = sorted[b];
            b -= 1;
        }
        sorted[b + 1] = key;
    }
    return sorted[sorted.len / 2];
}

fn p95_of(latencies: f64[>..]) -> f64 {
    if latencies.len == 0 { return 0.0; }
    var sorted: f64[>..] = [];
    for l in latencies { sorted.push(l); }
    for a in 1..sorted.len {
        let key = sorted[a];
        var b = a - 1;
        while b >= 0 && sorted[b] > key {
            sorted[b + 1] = sorted[b];
            b -= 1;
        }
        sorted[b + 1] = key;
    }
    let idx = (sorted.len * 95) / 100;
    return sorted[idx as i64];
}

// =====================================================================
// MAIN - process queries one at a time from file
// =====================================================================

fn main() {
    print("MITRE/PRISM Locked Test — Goose on labeled questions\n");
    print("====================================================\n\n");

    // Check for profiling mode
    var prof_buf: u8[>..] = [];
    if env("RPR_PROFILE", prof_buf) {
        profiling_enabled = true;
        print("Profiling mode enabled\n");
    }

    // Check for compare mode (bounded top-k vs full sort)
    var cmp_buf: u8[>..] = [];
    var compare_enabled: bool = false;
    if env("RPR_COMPARE", cmp_buf) {
        compare_enabled = true;
        print("Compare mode enabled\n");
    }

    // Generate corpus
    print("Generating corpus (100K, seed 8001)...\n");
    let corpus = generate_corpus(100_000, 8001);
    var gen_msg: u8[>..] = [];
    format(gen_msg, "  Generated ");
    format(gen_msg, corpus.len);
    gen_msg.push('\n');
    print(gen_msg);

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
    let ingested = ingest_batch(corpus);
    var ing_msg: u8[>..] = [];
    format(ing_msg, "  Ingested ");
    format(ing_msg, ingested);
    ing_msg.push('\n');
    print(ing_msg);

    // Rebuild flat_postings
    print("Rebuilding flat postings...\n");
    rebuild_flat_postings();

    // Build CSR index
    print("Building CSR index...\n");
    build_csr_index();

    // Read query file
    var content: u8[>..] = [];
    if !read_file("goose_queries.txt", content) {
        print("ERROR: cannot read goose_queries.txt\n");
        return;
    }

    // Warm-up queries (untimed) - separate file so none of the scored
    // questions are consumed by warm-up
    var warmup_content: u8[>..] = [];
    if read_file("warmup_queries.txt", warmup_content) {
        var ws: u32 = 0;
        var wi: u32 = 0;
        while wi <= warmup_content.len {
            if wi == warmup_content.len || warmup_content[wi] == '\n' {
                if wi > ws {
                    var wtab: u32 = 0;
                    var wfound = false;
                    for j in ws..wi {
                        if warmup_content[j] == '\t' { wtab = j; wfound = true; break; }
                        if warmup_content[j] == '\r' { continue; }
                    }
                    if wfound {
                        var wqtext: u8[>..] = [];
                        for j in ws..wtab {
                            if warmup_content[j] != '\r' { wqtext.push(warmup_content[j]); }
                        }
                        var wk_val: u32 = 0;
                        for j in (wtab + 1)..wi {
                            let c = warmup_content[j];
                            if c >= '0' && c <= '9' { wk_val = wk_val * 10 + (c - '0') as u32; }
                        }
                        var wqbuf: u8[>..] = [];
                        for j in 0..wqtext.len { wqbuf.push(wqtext[j]); }
                        let wqterms = tokenize(wqbuf[..]);
                        score_query_fast(wqterms, wk_val);
                        rpr_search(wqterms, 10000);
                        evidence_pool.clear();
                    }
                }
                ws = wi + 1;
            }
            wi += 1;
        }
    }

    // Output header - no {} placeholders (Goose print/format don't substitute in AOT)
    var hdr: u8[>..] = [];
    format(hdr, "rep");
    hdr.push('\t');
    format(hdr, "query");
    hdr.push('\t');
    format(hdr, "k");
    hdr.push('\t');
    format(hdr, "csr_median_ms");
    hdr.push('\t');
    format(hdr, "csr_p95_ms");
    hdr.push('\t');
    format(hdr, "rpr_median_ms");
    hdr.push('\t');
    format(hdr, "rpr_p95_ms");
    hdr.push('\t');
    format(hdr, "csr_n_returned");
    hdr.push('\t');
    format(hdr, "rpr_n_returned");
    hdr.push('\t');
    format(hdr, "csr_failed");
    hdr.push('\t');
    format(hdr, "rpr_failed");
    hdr.push('\t');
    format(hdr, "rpr_events");
    if profiling_enabled {
        hdr.push('\t');
        format(hdr, "rpr_setup_ms");
        hdr.push('\t');
        format(hdr, "rpr_scorebuf_ms");
        hdr.push('\t');
        format(hdr, "rpr_eventq_ms");
        hdr.push('\t');
        format(hdr, "rpr_sort_ms");
        hdr.push('\t');
        format(hdr, "passage_ms");
    }
    hdr.push('\n');
    print(hdr);

    var rep_count: u32 = 3;
    var line_start: u32 = 0;

    for rep in 0..rep_count {
        var i: u32 = 0;
        line_start = 0;

        while i <= content.len {
            if i < content.len && content[i] == '\r' {
                i += 1;
                continue;
            }
            if i == content.len || content[i] == '\n' {
                if i > line_start {
                    // Find tab in this line
                    var tab_pos: u32 = 0;
                    var found_tab = false;
                    for j in line_start..i {
                        if content[j] == '\t' { tab_pos = j; found_tab = true; break; }
                        if content[j] == '\r' { continue; }
                    }
                    if found_tab {

                        // Build query text
                        var qtext: u8[>..] = [];
                        for j in line_start..tab_pos {
                            if content[j] != '\r' { qtext.push(content[j]); }
                        }
                        // Parse k
                        var k_val: u32 = 0;
                        for j in (tab_pos + 1)..i {
                            let c = content[j];
                            if c >= '0' && c <= '9' {
                                k_val = k_val * 10 + (c - '0') as u32;
                            }
                        }

                        // Tokenize
                        var qbuf: u8[>..] = [];
                        for j in 0..qtext.len { qbuf.push(qtext[j]); }
                        let qterms = tokenize(qbuf[..]);

                        // Clear per-query profiling arrays
                        if profiling_enabled {
                            rpr_setup_lats.clear();
                            rpr_scorebuf_lats.clear();
                            rpr_eventq_lats.clear();
                            rpr_sort_lats.clear();
                        }

                        // CSR diagnostic - 10 iterations
                        var csr_lats: f64[>..] = [];
                        var csr_doc_ids: u64[>..] = [];
                        var csr_failed = false;
                        for _ in 0..10 {
                            let start = clock_ns();
                            let results = score_query_fast(qterms, k_val);
                            let end = clock_ns();
                            csr_lats.push((end - start) as f64 / 1_000_000.0);
                            if results.len == 0 { csr_failed = true; }
                            csr_doc_ids.clear();
                            for r in results { csr_doc_ids.push(r.doc_id); }
                        }
                        let csr_median = median_of(copy(csr_lats));
                        let csr_p95 = p95_of(copy(csr_lats));

                        // RPR product path - 10 iterations
                        var rpr_lats: f64[>..] = [];
                        var rpr_doc_ids: u64[>..] = [];
                        var rpr_failed = false;
                        var passage_lats: f64[>..] = [];
                        for _ in 0..10 {
                            let start = clock_ns();
                            let results = rpr_search(qterms, 10000);
                            let end = clock_ns();
                            rpr_lats.push((end - start) as f64 / 1_000_000.0);
                            if results.len == 0 { rpr_failed = true; }
                            rpr_doc_ids.clear();
                            for r in results { rpr_doc_ids.push(r.doc_id); }
                        }
                        let rpr_median = median_of(copy(rpr_lats));
                        let rpr_p95 = p95_of(copy(rpr_lats));

                        // Profiling medians
                        var rpr_setup_median: f64 = 0.0;
                        var rpr_scorebuf_median: f64 = 0.0;
                        var rpr_eventq_median: f64 = 0.0;
                        var rpr_sort_median: f64 = 0.0;
                        var passage_median: f64 = 0.0;
                        if profiling_enabled {
                            rpr_setup_median = median_of(copy(rpr_setup_lats));
                            rpr_scorebuf_median = median_of(copy(rpr_scorebuf_lats));
                            rpr_eventq_median = median_of(copy(rpr_eventq_lats));
                            rpr_sort_median = median_of(copy(rpr_sort_lats));
                            passage_median = median_of(copy(passage_lats));
                        }

                        // Compare mode: bounded top-10 vs full sort
                        if compare_enabled {
                            let bounded_results = rpr_search_bounded(qterms, 10000, 10);
                            var mismatch = false;
                            let n_bound: u32 = bounded_results.len as u32;
                            let n_full: u32 = rpr_doc_ids.len as u32;
                            let cmp_count = if n_bound < n_full { n_bound } else { n_full };
                            for ci in 0..cmp_count {
                                if bounded_results[ci as i64].doc_id != rpr_doc_ids[ci] {
                                    mismatch = true;
                                    if compare_debug_count < 5 {
                                        compare_debug_count += 1;
                                        var dbg: u8[>..] = [];
                                        format(dbg, "  DEBUG ci=");
                                        format(dbg, ci);
                                        format(dbg, " bounded=");
                                        format(dbg, bounded_results[ci as i64].doc_id);
                                        format(dbg, " full=");
                                        format(dbg, rpr_doc_ids[ci]);
                                        format(dbg, "\n");
                                        print(dbg);
                                    }
                                    break;
                                }
                            }
                            if mismatch {
                                compare_mismatches += 1;
                            }
                            evidence_pool.clear();
                        }

                        // Output result line - concatenate values without {} placeholders
                        var out: u8[>..] = [];
                        format(out, rep);
                        out.push('\t');
                        format(out, qtext);
                        out.push('\t');
                        format(out, k_val);
                        out.push('\t');
                        format(out, csr_median);
                        out.push('\t');
                        format(out, csr_p95);
                        out.push('\t');
                        format(out, rpr_median);
                        out.push('\t');
                        format(out, rpr_p95);
                        out.push('\t');
                        format(out, csr_doc_ids.len);
                        out.push('\t');
                        format(out, rpr_doc_ids.len);
                        out.push('\t');
                        format(out, if csr_failed { 1 } else { 0 });
                        out.push('\t');
                        format(out, if rpr_failed { 1 } else { 0 });
                        out.push('\t');
                        format(out, rpr_events_processed);
                        // Profiling breakdown (only when RPR_PROFILE=1)
                        if profiling_enabled {
                            out.push('\t');
                            format(out, rpr_setup_median);
                            out.push('\t');
                            format(out, rpr_scorebuf_median);
                            out.push('\t');
                            format(out, rpr_eventq_median);
                            out.push('\t');
                            format(out, rpr_sort_median);
                            out.push('\t');
                            format(out, passage_median);
                        }
                        // CSR doc IDs (top-k, comma-separated)
                        out.push('\t');
                        for di in 0..csr_doc_ids.len {
                            if di > 0 { out.push(','); }
                            format(out, csr_doc_ids[di]);
                        }
                        // RPR doc IDs (top-10, comma-separated)
                        out.push('\t');
                        let rpr_top10 = if rpr_doc_ids.len < 10 { rpr_doc_ids.len } else { 10 };
                        for di in 0..rpr_top10 {
                            if di > 0 { out.push(','); }
                            format(out, rpr_doc_ids[di]);
                        }
                        // Passage text: top 10 readable source passages with IDs (| separated)
                        var passage_start: f64 = 0.0;
                        if profiling_enabled { passage_start = clock_ns(); }
                        out.push('\t');
                        let passage_count = if rpr_top10 < 10 { rpr_top10 } else { 10 };
                        for di in 0..passage_count {
                            let doc_id = rpr_doc_ids[di];
                            if di > 0 { out.push('|'); }
                            format(out, doc_id);
                            out.push(':');
                            // Find doc text in doc_pool
                            var found = false;
                            for di2 in 0..doc_pool.len {
                                let de = &doc_pool[di2 as i64];
                                if de.id == doc_id {
                                    let text = de.text;
                                    let text_len = if text.len > 200 { 200 } else { text.len };
                                    for j in 0..text_len { out.push(text[j]); }
                                    found = true;
                                    break;
                                }
                            }
                            if !found {
                                format(out, "MISSING");
                            }
                        }
                        if profiling_enabled {
                            let passage_end = clock_ns();
                            passage_lats.push((passage_end - passage_start) as f64 / 1_000_000.0);
                        }
                        out.push('\n');
                        print(out);

                        evidence_pool.clear();
                    }
                }
                line_start = i + 1;
            }
            i += 1;
        }
    }

    var done_msg: u8[>..] = [];
    format(done_msg, "\nTotal repetitions: ");
    format(done_msg, rep_count);
    done_msg.push('\n');
    print(done_msg);
    print("Done.\n");

    if compare_enabled {
        var cmp_msg: u8[>..] = [];
        format(cmp_msg, "\nCompare mode: bounded top-10 vs full sort\n");
        format(cmp_msg, "  Mismatches: ");
        format(cmp_msg, compare_mismatches);
        cmp_msg.push('\n');
        print(cmp_msg);
    }
}
