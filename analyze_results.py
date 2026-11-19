#!/usr/bin/env python3
"""
Analyze locked test results v2: combine BM25S + RPR Mite (Goose) data with 3 reps,
compute paired 95% CIs, recall@10, failed queries, and assess the pass rule.
Usage: analyze_results.py [goose_results_file]  (default: goose_locked_results_v2.txt)
"""
import json
import math
import statistics
import sys
from collections import defaultdict
from scipy import stats

# Optional input file argument
goose_results_file = sys.argv[1] if len(sys.argv) > 1 else 'goose_locked_results_v2.txt'

# =====================================================================
# LOAD BM25S RESULTS
# =====================================================================

with open('locked_test_results.json', 'r') as f:
    bm25s_data = json.load(f)

bm25s_results = bm25s_data['bm25s_results']
print(f"BM25S results: {len(bm25s_results)} queries")

# Build BM25S lookup by query text
bm25s_by_query = {}
for r in bm25s_results:
    key = r['query'] + '\t' + str(r['k'])
    bm25s_by_query[key] = r

# Load question map for relevant docs
with open('question_map.json', 'r') as f:
    question_map = json.load(f)

# =====================================================================
# LOAD GOOSE (RPR MITE) RESULTS - 3 reps per query
# =====================================================================

goose_reps = defaultdict(list)  # key=(query, k) -> list of rep results

with open(goose_results_file, 'r') as f:
    lines = f.readlines()

# Skip header lines until we find the data header
data_start = 0
for i, line in enumerate(lines):
    if line.startswith('rep\tquery\tk\t'):
        data_start = i + 1
        break

for line in lines[data_start:]:
    line = line.strip()
    if not line or line.startswith('DEBUG') or line.startswith('Total') or line.startswith('Done'):
        continue
    parts = line.split('\t')
    if len(parts) < 12:
        continue

    rep = int(parts[0])
    query = parts[1]
    k = int(parts[2])
    csr_median_ms = float(parts[3])
    csr_p95_ms = float(parts[4])
    rpr_median_ms = float(parts[5])
    rpr_p95_ms = float(parts[6])
    csr_n_returned = int(parts[7])
    rpr_n_returned = int(parts[8])
    csr_failed = int(parts[9])
    rpr_failed = int(parts[10])
    rpr_events = int(parts[11])

    # Detect profiling columns: when RPR_PROFILE=1, 5 extra columns
    # (rpr_setup_ms, rpr_scorebuf_ms, rpr_eventq_ms, rpr_sort_ms, passage_ms)
    # are inserted between rpr_events (11) and csr_doc_ids.
    profiling = len(parts) > 15
    if profiling:
        csr_doc_ids_idx = 17
        rpr_doc_ids_idx = 18
    else:
        csr_doc_ids_idx = 12
        rpr_doc_ids_idx = 13

    # CSR doc IDs
    csr_doc_ids = []
    if len(parts) > csr_doc_ids_idx and parts[csr_doc_ids_idx]:
        csr_doc_ids = [int(x) for x in parts[csr_doc_ids_idx].split(',') if x]

    # RPR doc IDs (top-10)
    rpr_doc_ids = []
    if len(parts) > rpr_doc_ids_idx and parts[rpr_doc_ids_idx]:
        rpr_doc_ids = [int(x) for x in parts[rpr_doc_ids_idx].split(',') if x]

    # Profiling breakdown
    rpr_setup_ms = None
    rpr_scorebuf_ms = None
    rpr_eventq_ms = None
    rpr_sort_ms = None
    passage_ms = None
    if profiling:
        rpr_setup_ms = float(parts[12]) if parts[12] else None
        rpr_scorebuf_ms = float(parts[13]) if parts[13] else None
        rpr_eventq_ms = float(parts[14]) if parts[14] else None
        rpr_sort_ms = float(parts[15]) if parts[15] else None
        passage_ms = float(parts[16]) if parts[16] else None

    key = (query, k)
    goose_reps[key].append({
        'rep': rep,
        'query': query,
        'k': k,
        'csr_median_ms': csr_median_ms,
        'csr_p95_ms': csr_p95_ms,
        'rpr_median_ms': rpr_median_ms,
        'rpr_p95_ms': rpr_p95_ms,
        'csr_n_returned': csr_n_returned,
        'rpr_n_returned': rpr_n_returned,
        'csr_failed': csr_failed,
        'rpr_failed': rpr_failed,
        'rpr_events': rpr_events,
        'rpr_setup_ms': rpr_setup_ms,
        'rpr_scorebuf_ms': rpr_scorebuf_ms,
        'rpr_eventq_ms': rpr_eventq_ms,
        'rpr_sort_ms': rpr_sort_ms,
        'passage_ms': passage_ms,
        'csr_doc_ids': csr_doc_ids,
        'rpr_doc_ids': rpr_doc_ids,
    })

print(f"Goose result groups: {len(goose_reps)} (each with up to 3 reps)")
total_reps = sum(len(v) for v in goose_reps.values())
print(f"Total Goose reps: {total_reps}")

# =====================================================================
# AGGREGATE ACROSS REPS - take median of medians per query
# =====================================================================

goose_agg = {}
for key, reps in goose_reps.items():
    reps_sorted = sorted(reps, key=lambda r: r['rep'])
    n_reps = len(reps_sorted)

    # Median of median latencies across reps
    csr_medians = [r['csr_median_ms'] for r in reps_sorted]
    rpr_medians = [r['rpr_median_ms'] for r in reps_sorted]
    csr_p95s = [r['csr_p95_ms'] for r in reps_sorted]
    rpr_p95s = [r['rpr_p95_ms'] for r in reps_sorted]
    rpr_events_list = [r['rpr_events'] for r in reps_sorted]

    # Use the median rep's doc IDs for recall computation
    median_rep_idx = n_reps // 2
    median_rep = reps_sorted[median_rep_idx]

    # Failed if any rep failed
    csr_failed_any = max(r['csr_failed'] for r in reps_sorted)
    rpr_failed_any = max(r['rpr_failed'] for r in reps_sorted)

    goose_agg[key] = {
        'query': key[0],
        'k': key[1],
        'n_reps': n_reps,
        'csr_median_ms': statistics.median(csr_medians),
        'csr_p95_ms': statistics.median(csr_p95s),
        'rpr_median_ms': statistics.median(rpr_medians),
        'rpr_p95_ms': statistics.median(rpr_p95s),
        'rpr_events_median': statistics.median(rpr_events_list),
        'csr_n_returned': median_rep['csr_n_returned'],
        'rpr_n_returned': median_rep['rpr_n_returned'],
        'csr_failed': csr_failed_any,
        'rpr_failed': rpr_failed_any,
        'rpr_setup_ms_median': statistics.median([r['rpr_setup_ms'] for r in reps_sorted if r['rpr_setup_ms'] is not None]) if any(r['rpr_setup_ms'] is not None for r in reps_sorted) else None,
        'rpr_scorebuf_ms_median': statistics.median([r['rpr_scorebuf_ms'] for r in reps_sorted if r['rpr_scorebuf_ms'] is not None]) if any(r['rpr_scorebuf_ms'] is not None for r in reps_sorted) else None,
        'rpr_eventq_ms_median': statistics.median([r['rpr_eventq_ms'] for r in reps_sorted if r['rpr_eventq_ms'] is not None]) if any(r['rpr_eventq_ms'] is not None for r in reps_sorted) else None,
        'rpr_sort_ms_median': statistics.median([r['rpr_sort_ms'] for r in reps_sorted if r['rpr_sort_ms'] is not None]) if any(r['rpr_sort_ms'] is not None for r in reps_sorted) else None,
        'passage_ms_median': statistics.median([r['passage_ms'] for r in reps_sorted if r['passage_ms'] is not None]) if any(r['passage_ms'] is not None for r in reps_sorted) else None,
        'csr_doc_ids': median_rep['csr_doc_ids'],
        'rpr_doc_ids': median_rep['rpr_doc_ids'],
    }

print(f"Goose aggregated queries: {len(goose_agg)}")

# =====================================================================
# MATCH QUERIES
# =====================================================================

matched = []
for key, agg in goose_agg.items():
    query, k = key
    bm_key = query + '\t' + str(k)
    if bm_key in bm25s_by_query:
        bm = bm25s_by_query[bm_key]

        # Get relevant docs for this query
        qmap_entry = question_map.get(bm_key, {})
        relevant_docs = set(qmap_entry.get('relevant_docs', []))

        # Compute recall@10 for Goose RPR (top-10)
        rpr_returned = set(agg['rpr_doc_ids'][:10])
        rpr_recall = len(rpr_returned & relevant_docs) / len(relevant_docs) if relevant_docs else 1.0

        # Compute recall@10 for BM25S
        bm_recall = bm.get('recall_at_10', 0.0)

        matched.append({
            'query': query,
            'k': k,
            'bm25s_median_ms': bm['median_ms'],
            'bm25s_p95_ms': bm['p95_ms'],
            'bm25s_failed': bm['failed'],
            'bm25s_recall_at_10': bm_recall,
            'goose_csr_median_ms': agg['csr_median_ms'],
            'goose_csr_p95_ms': agg['csr_p95_ms'],
            'goose_csr_failed': agg['csr_failed'],
            'goose_rpr_median_ms': agg['rpr_median_ms'],
            'goose_rpr_p95_ms': agg['rpr_p95_ms'],
            'goose_rpr_failed': agg['rpr_failed'],
            'goose_rpr_recall_at_10': rpr_recall,
            'goose_rpr_events': agg['rpr_events_median'],
            'goose_rpr_setup_ms': agg['rpr_setup_ms_median'],
            'goose_rpr_scorebuf_ms': agg['rpr_scorebuf_ms_median'],
            'goose_rpr_eventq_ms': agg['rpr_eventq_ms_median'],
            'goose_rpr_sort_ms': agg['rpr_sort_ms_median'],
            'goose_passage_ms': agg['passage_ms_median'],
        })

print(f"Matched queries: {len(matched)}")

# Check for unmatched
bm_keys = set(bm25s_by_query.keys())
goose_keys = set(goose_agg.keys())
unmatched_bm = bm_keys - { (q, k) for q, k in goose_keys }
unmatched_goose = { (q, k) for q, k in goose_keys } - bm_keys
if unmatched_bm:
    print(f"Unmatched BM25S queries: {len(unmatched_bm)}")
if unmatched_goose:
    print(f"Unmatched Goose queries: {len(unmatched_goose)}")

# =====================================================================
# PAIRED 95% CIs (RPR vs BM25S - the product path comparison)
# =====================================================================

bm_latencies = [m['bm25s_median_ms'] for m in matched]
goose_rpr_latencies = [m['goose_rpr_median_ms'] for m in matched]

diffs = [b - g for b, g in zip(bm_latencies, goose_rpr_latencies)]

n = len(diffs)
mean_diff = statistics.mean(diffs)
std_diff = statistics.stdev(diffs)
se = std_diff / math.sqrt(n)
t_val = stats.t.ppf(0.975, n - 1)
margin = t_val * se

ci_lower = mean_diff - margin
ci_upper = mean_diff + margin
median_diff = statistics.median(diffs)

bm_median_overall = statistics.median(bm_latencies)
goose_median_overall = statistics.median(goose_rpr_latencies)
speedup = bm_median_overall / goose_median_overall if goose_median_overall > 0 else float('inf')

print("\n" + "=" * 70)
print("PAIRED 95% CI: BM25S vs RPR Mite (median latency difference)")
print("=" * 70)
print(f"  n = {n}")
print(f"  BM25S median latency: {bm_median_overall:.4f}ms")
print(f"  RPR Mite median latency: {goose_median_overall:.4f}ms")
print(f"  Mean difference (BM25S - RPR Mite): {mean_diff:.4f}ms")
print(f"  Median difference: {median_diff:.4f}ms")
print(f"  95% CI: [{ci_lower:.4f}, {ci_upper:.4f}]ms")
print(f"  Speedup ratio (median): {speedup:.1f}x")
print(f"  Threshold: 1.05x (5% faster)")
speed_pass = speedup >= 1.05
print(f"  SPEED CLAIM: {'PASS' if speed_pass else 'FAIL'}")

# Speedup CI via log transform
log_diffs = [math.log(b / g) for b, g in zip(bm_latencies, goose_rpr_latencies) if g > 0]
mean_log_diff = statistics.mean(log_diffs)
std_log_diff = statistics.stdev(log_diffs)
se_log = std_log_diff / math.sqrt(len(log_diffs))
t_val_log = stats.t.ppf(0.975, len(log_diffs) - 1)
margin_log = t_val_log * se_log
ci_lower_log = mean_log_diff - margin_log
ci_upper_log = mean_log_diff + margin_log
ci_lower_speedup = math.exp(ci_lower_log)
ci_upper_speedup = math.exp(ci_upper_log)
print(f"  Speedup 95% CI: [{ci_lower_speedup:.1f}x, {ci_upper_speedup:.1f}x]")

# =====================================================================
# RECALL@10
# =====================================================================

bm_recalls = [m['bm25s_recall_at_10'] for m in matched]
goose_rpr_recalls = [m['goose_rpr_recall_at_10'] for m in matched]

bm_mean_recall = statistics.mean(bm_recalls)
goose_rpr_mean_recall = statistics.mean(goose_rpr_recalls)

rpr_recall_drop = bm_mean_recall - goose_rpr_mean_recall

print("\n" + "=" * 70)
print("RECALL@10")
print("=" * 70)
print(f"  BM25S mean recall@10: {bm_mean_recall:.4f}")
print(f"  RPR Mite mean recall@10: {goose_rpr_mean_recall:.4f} (drop: {rpr_recall_drop:.4f})")
print(f"  Threshold: <=1pp drop (0.01)")
rpr_recall_pass = rpr_recall_drop <= 0.01
print(f"  RPR RECALL CLAIM: {'PASS' if rpr_recall_pass else 'FAIL'}")

# =====================================================================
# FAILED QUERIES
# =====================================================================

bm_failed = sum(1 for m in matched if m['bm25s_failed'])
goose_rpr_failed = sum(1 for m in matched if m['goose_rpr_failed'])
goose_csr_failed = sum(1 for m in matched if m['goose_csr_failed'])

print("\n" + "=" * 70)
print("FAILED QUERIES")
print("=" * 70)
print(f"  BM25S failed: {bm_failed}/{n}")
print(f"  RPR Mite failed: {goose_rpr_failed}/{n}")
print(f"  CSR diagnostic failed: {goose_csr_failed}/{n}")
failed_pass = goose_rpr_failed <= bm_failed
print(f"  RPR FAILED QUERIES CLAIM: {'PASS' if failed_pass else 'FAIL'}")

# =====================================================================
# P95 REPORTING
# =====================================================================

bm_p95s = [m['bm25s_p95_ms'] for m in matched]
goose_rpr_p95s = [m['goose_rpr_p95_ms'] for m in matched]

print("\n" + "=" * 70)
print("P95 SLOWEST 5% (REPORTING ONLY, NOT A GATE)")
print("=" * 70)
print(f"  BM25S p95 median: {statistics.median(bm_p95s):.4f}ms")
print(f"  BM25S p95 max: {max(bm_p95s):.4f}ms")
print(f"  RPR Mite p95 median: {statistics.median(goose_rpr_p95s):.4f}ms")
print(f"  RPR Mite p95 max: {max(goose_rpr_p95s):.4f}ms")

# RPR events reporting
goose_events = [m['goose_rpr_events'] for m in matched]
print(f"  RPR Mite events median: {statistics.median(goose_events):.0f}")
print(f"  RPR Mite events max: {max(goose_events):.0f}")

# Profiling breakdown (only when profiling data available)
profiling_available = any(m['goose_rpr_setup_ms'] is not None for m in matched)
if profiling_available:
    print("\n" + "=" * 70)
    print("RPR PROFILING BREAKDOWN (median ms per component)")
    print("=" * 70)
    setup = [m['goose_rpr_setup_ms'] for m in matched if m['goose_rpr_setup_ms'] is not None]
    scorebuf = [m['goose_rpr_scorebuf_ms'] for m in matched if m['goose_rpr_scorebuf_ms'] is not None]
    eventq = [m['goose_rpr_eventq_ms'] for m in matched if m['goose_rpr_eventq_ms'] is not None]
    sort = [m['goose_rpr_sort_ms'] for m in matched if m['goose_rpr_sort_ms'] is not None]
    passage = [m['goose_passage_ms'] for m in matched if m['goose_passage_ms'] is not None]
    print(f"  rpr_search setup (Scout pushes): median={statistics.median(setup):.4f}ms, max={max(setup):.4f}ms")
    print(f"  rpr_pulse score-buffer init:    median={statistics.median(scorebuf):.4f}ms, max={max(scorebuf):.4f}ms")
    print(f"  rpr_pulse event-queue work:     median={statistics.median(eventq):.4f}ms, max={max(eventq):.4f}ms")
    print(f"  rpr_pulse candidate sort:       median={statistics.median(sort):.4f}ms, max={max(sort):.4f}ms")
    print(f"  passage fetch (doc lookup):     median={statistics.median(passage):.4f}ms, max={max(passage):.4f}ms")
    total_profile = statistics.median(setup) + statistics.median(scorebuf) + statistics.median(eventq) + statistics.median(sort)
    print(f"  Sum of rpr_pulse components:    median={total_profile:.4f}ms")

# Save detailed results - add profiling fields
for m in matched:
    if m['goose_rpr_setup_ms'] is not None:
        m['rpr_setup_ms'] = m['goose_rpr_setup_ms']
        m['rpr_scorebuf_ms'] = m['goose_rpr_scorebuf_ms']
        m['rpr_eventq_ms'] = m['goose_rpr_eventq_ms']
        m['rpr_sort_ms'] = m['goose_rpr_sort_ms']
        m['passage_ms'] = m['goose_passage_ms']

# =====================================================================
# TYPE BREAKDOWN
# =====================================================================

print("\n" + "=" * 70)
print("TYPE BREAKDOWN (RPR Mite vs BM25S)")
print("=" * 70)
types = defaultdict(list)
for m in matched:
    qmap_entry = question_map.get(m['query'] + '\t' + str(m['k']), {})
    t = qmap_entry.get('type', 'unknown')
    types[t].append(m)
for t in sorted(types.keys()):
    tm = types[t]
    bm_med = statistics.median([m['bm25s_median_ms'] for m in tm])
    goose_med = statistics.median([m['goose_rpr_median_ms'] for m in tm])
    bm_rec = statistics.mean([m['bm25s_recall_at_10'] for m in tm])
    goose_rec = statistics.mean([m['goose_rpr_recall_at_10'] for m in tm])
    print(f"  {t}: n={len(tm)}, BM25S median={bm_med:.2f}ms, RPR Mite median={goose_med:.2f}ms, "
          f"speedup={bm_med/goose_med:.1f}x, BM25S recall={bm_rec:.3f}, RPR recall={goose_rec:.3f}")

# =====================================================================
# PASS RULE ASSESSMENT
# =====================================================================

print("\n" + "=" * 70)
print("PASS RULE ASSESSMENT (RPR Mite vs BM25S)")
print("=" * 70)
print(f"  1. Speed (>=5% faster median, paired 95% CI): {'PASS' if speed_pass else 'FAIL'} "
      f"(speedup={speedup:.1f}x, CI=[{ci_lower_speedup:.1f}x, {ci_upper_speedup:.1f}x])")
print(f"  2. Recall@10 (<=1pp drop): {'PASS' if rpr_recall_pass else 'FAIL'} "
      f"(drop={rpr_recall_drop:.4f})")
print(f"  3. Failed queries (no increase): {'PASS' if failed_pass else 'FAIL'} "
      f"({goose_rpr_failed} vs {bm_failed})")

overall = speed_pass and rpr_recall_pass and failed_pass
print(f"\n  OVERALL: {'PASS' if overall else 'FAIL'}")

# Save detailed results
output = {
    "n_matched": n,
    "n_reps_per_query": 3,
    "bm25s_median_ms": bm_median_overall,
    "goose_rpr_median_ms": goose_median_overall,
    "mean_diff_ms": mean_diff,
    "median_diff_ms": median_diff,
    "ci_lower_ms": ci_lower,
    "ci_upper_ms": ci_upper,
    "speedup_ratio": speedup,
    "speedup_ci_lower": ci_lower_speedup,
    "speedup_ci_upper": ci_upper_speedup,
    "speed_pass": speed_pass,
    "bm25s_mean_recall_at_10": bm_mean_recall,
    "goose_rpr_mean_recall_at_10": goose_rpr_mean_recall,
    "rpr_recall_drop": rpr_recall_drop,
    "recall_pass": rpr_recall_pass,
    "bm25s_failed": bm_failed,
    "goose_rpr_failed": goose_rpr_failed,
    "goose_csr_failed": goose_csr_failed,
    "failed_pass": failed_pass,
    "bm25s_p95_median": statistics.median(bm_p95s),
    "goose_rpr_p95_median": statistics.median(goose_rpr_p95s),
    "bm25s_p95_max": max(bm_p95s),
    "goose_rpr_p95_max": max(goose_rpr_p95s),
    "rpr_events_median": statistics.median(goose_events),
    "rpr_events_max": max(goose_events),
    "overall_pass": overall,
    "matched_queries": matched,
}

with open('locked_test_analysis_v2.json', 'w') as f:
    json.dump(output, f, indent=2, default=str)

print("\nResults saved to locked_test_analysis_v2.json")
