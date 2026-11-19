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
                if p.wave_id == 0 { break; }
            },
        }
    }

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

    // Output header - no {} placeholders (Goose print/format don't substitute in AOT)
    var hdr: u8[>..] = [];
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
    hdr.push('\n');
    print(hdr);

    var query_count: u32 = 0;
    var line_start: u32 = 0;
    var i: u32 = 0;

    while i <= content.len {
        if i == content.len || content[i] == '\n' {
            if i > line_start {
                // Find tab in this line
                var tab_pos: u32 = 0;
                var found_tab = false;
                for j in line_start..i {
                    if content[j] == '\t' { tab_pos = j; found_tab = true; break; }
                    if content[j] == '\r' { break; }
                }
                if found_tab {
                    query_count += 1;

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

                    // Warm-up: first 3 queries untimed
                    if query_count <= 3 {
                        score_query_fast(qterms, k_val);
                        rpr_search(qterms, 10000);
                        evidence_pool.clear();
                    } else {
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

                        // Output result line - concatenate values without {} placeholders
                        var out: u8[>..] = [];
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
                        out.push('\n');
                        print(out);

                        evidence_pool.clear();
                    }
                }
            }
            line_start = i + 1;
        }
        i += 1;
    }

    var done_msg: u8[>..] = [];
    format(done_msg, "\nTotal queries processed: ");
    format(done_msg, query_count);
    done_msg.push('\n');
    print(done_msg);
    print("Done.\n");
}
