# PAVONA RESEARCH DIRECTIVE — Methods Appendix

**Campaign:** PAVONA MITRE Kimi Spark Handoff — Neural Retrieval Evaluation  
**Date:** 2026-11-19

---

## A1. Tokenization

Text documents are lowercased and split into tokens using the regex:

```
[a-zA-Z0-9_:.\-]+
```

This produces alphanumeric tokens plus colon-separated attribute:value pairs (e.g., `electrode:0`, `voltage:-79.56`, `p0=10.00`). Brackets, commas, equals signs, and other punctuation serve as token boundaries.

## A2. Inverted Index Construction

For each document `(doc_id, text)`:

1. Tokenize the text into a set of unique terms
2. For each term, add `doc_id` to the term's posting list (a set of document IDs)
3. After all documents are processed, posting lists are stored as sorted sets

Data structure: `Dict[str, Set[int]]` mapping term → set of doc_ids.

## A3. Conjunctive AND Retrieval

For a query with terms `t1, t2, ..., tn`:

1. Look up the posting list for each term
2. If any term has no posting list, return empty result (early termination)
3. Sort posting lists by length (ascending)
4. Start with the shortest list as the initial result set
5. Intersect with each subsequent list, terminating early if the result becomes empty
6. Return the sorted intersection

Complexity: O(min(|L1|, ..., |Ln|) × n) where Li is the posting list for term i.

## A4. Document Generation

### Stimulation Documents

Read from `fs437_wholelife_stimulations/table`:
- `index` → document ID suffix (`stim_{index}`)
- `electrode` → `electrode:{N}`
- `time_of_stim` → `timestamp:{T}`
- `values_block_0[0:4]` → `params:[p0={v:.2f},p1={v:.2f},p2={v:.2f},p3={v:.2f}]`
- Document text: `stimulation electrode:{N} timestamp:{T} params:[...] stim_idx:{index}`

### Event Documents

Read from `fs437_wholelife_events/table`:
- `index` → document ID suffix (`event_{index}`)
- `electrode` → `electrode:{N}`
- `values_block_0[0]` → `voltage:{V:.2f}`
- `time_of_event` → `timestamp:{T}`
- Document text: `electrode:{N} voltage:{V:.2f} timestamp:{T} event_idx:{index}`

## A5. Latency Measurement

Each query was executed 10 times. Latencies were measured using `time.perf_counter()` around the `conjunctive_and()` call. Reported statistics:
- Median: 6th value of sorted latencies
- p95: value at index `int(10 * 0.95)` = 9th value
- Min/max: first/last values of sorted latencies

## A6. Sanitization Protocol

All exported files contain aggregate statistics only:
- Document counts (integers)
- Latency measurements (milliseconds, derived from timing)
- Index term counts (integers)
- Electrode distributions (ranges and counts)

No raw neuroscience data (spike voltages, timestamps, electrode recordings, stimulation parameter values, or document text) is included in any exported file.
