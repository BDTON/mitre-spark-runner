#!/usr/bin/env python3
"""
Analyze locked test results: combine BM25S + Goose data, compute paired 95% CIs,
recall@10, failed queries, and assess the pass rule.
"""
import json
import math
import statistics
from collections import defaultdict
from scipy import stats

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
# LOAD GOOSE RESULTS
# =====================================================================

goose_results = []
with open('goose_locked_results.txt', 'r') as f:
    lines = f.readlines()

# Skip header lines until we find the data header
data_start = 0
for i, line in enumerate(lines):
    if line.startswith('query\tk\t'):
        data_start = i + 1
        break

for line in lines[data_start:]:
    line = line.strip()
    if not line or line.startswith('Total') or line.startswith('Done'):
        continue
    parts = line.split('\t')
    if len(parts) < 12:
        continue
    csr_doc_ids = []
    if len(parts) > 10 and parts[10]:
        csr_doc_ids = [int(x) for x in parts[10].split(',') if x]
    rpr_doc_ids = []
    if len(parts) > 11 and parts[11]:
        rpr_doc_ids = [int(x) for x in parts[11].split(',') if x]
    goose_results.append({
        'query': parts[0],
        'k': int(parts[1]),
        'csr_median_ms': float(parts[2]),
        'csr_p95_ms': float(parts[3]),
        'rpr_median_ms': float(parts[4]),
        'rpr_p95_ms': float(parts[5]),
        'csr_n_returned': int(parts[6]),
        'rpr_n_returned': int(parts[7]),
        'csr_failed': int(parts[8]),
        'rpr_failed': int(parts[9]),
        'csr_doc_ids': csr_doc_ids,
        'rpr_doc_ids': rpr_doc_ids,
    })

print(f"Goose results: {len(goose_results)} queries")

# Build Goose lookup by query text
goose_by_query = {}
for r in goose_results:
    key = r['query'] + '\t' + str(r['k'])
    goose_by_query[key] = r

# =====================================================================
# MATCH QUERIES
# =====================================================================

matched = []
for key, bm in bm25s_by_query.items():
    if key in goose_by_query:
        goose = goose_by_query[key]
        # Get relevant docs for this query
        qmap_entry = question_map.get(key, {})
        relevant_docs = set(qmap_entry.get('relevant_docs', []))
        
        # Compute recall@10 for Goose CSR (top-10)
        csr_returned = set(goose['csr_doc_ids'][:10])
        csr_recall = len(csr_returned & relevant_docs) / len(relevant_docs) if relevant_docs else 1.0
        
        # Compute recall@10 for Goose RPR (top-10)
        rpr_returned = set(goose['rpr_doc_ids'][:10])
        rpr_recall = len(rpr_returned & relevant_docs) / len(relevant_docs) if relevant_docs else 1.0
        
        matched.append({
            'query': bm['query'],
            'k': bm['k'],
            'type': bm['type'],
            'bm25s_median_ms': bm['median_ms'],
            'bm25s_p95_ms': bm['p95_ms'],
            'bm25s_failed': bm['failed'],
            'bm25s_recall_at_10': bm['recall_at_10'],
            'goose_csr_median_ms': goose['csr_median_ms'],
            'goose_csr_p95_ms': goose['csr_p95_ms'],
            'goose_csr_recall_at_10': csr_recall,
            'goose_csr_failed': goose['csr_failed'],
            'goose_rpr_median_ms': goose['rpr_median_ms'],
            'goose_rpr_p95_ms': goose['rpr_p95_ms'],
            'goose_rpr_recall_at_10': rpr_recall,
            'goose_rpr_failed': goose['rpr_failed'],
        })

print(f"Matched queries: {len(matched)}")

# Check for unmatched
bm_keys = set(bm25s_by_query.keys())
goose_keys = set(goose_by_query.keys())
unmatched_bm = bm_keys - goose_keys
unmatched_goose = goose_keys - bm_keys
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
print("PAIRED 95% CI: BM25S vs Goose RPR (median latency difference)")
print("=" * 70)
print(f"  n = {n}")
print(f"  BM25S median latency: {bm_median_overall:.4f}ms")
print(f"  Goose RPR median latency: {goose_median_overall:.4f}ms")
print(f"  Mean difference (BM25S - Goose): {mean_diff:.4f}ms")
print(f"  Median difference: {median_diff:.4f}ms")
print(f"  95% CI: [{ci_lower:.4f}, {ci_upper:.4f}]ms")
print(f"  Speedup ratio (median): {speedup:.1f}x")
print(f"  Threshold: 1.05x (5% faster)")
speed_pass = speedup >= 1.05
print(f"  SPEED CLAIM: {'PASS' if speed_pass else 'FAIL'}")

# Also compute CI for speedup ratio
# Speedup CI: use ratio of medians, approximate via log transform
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
goose_csr_recalls = [m['goose_csr_recall_at_10'] for m in matched]
goose_rpr_recalls = [m['goose_rpr_recall_at_10'] for m in matched]

bm_mean_recall = statistics.mean(bm_recalls)
goose_csr_mean_recall = statistics.mean(goose_csr_recalls)
goose_rpr_mean_recall = statistics.mean(goose_rpr_recalls)

# Recall drop: BM25S - Goose (positive = Goose has lower recall)
csr_recall_drop = bm_mean_recall - goose_csr_mean_recall
rpr_recall_drop = bm_mean_recall - goose_rpr_mean_recall

print("\n" + "=" * 70)
print("RECALL@10")
print("=" * 70)
print(f"  BM25S mean recall@10: {bm_mean_recall:.4f}")
print(f"  Goose CSR mean recall@10: {goose_csr_mean_recall:.4f} (drop: {csr_recall_drop:.4f})")
print(f"  Goose RPR mean recall@10: {goose_rpr_mean_recall:.4f} (drop: {rpr_recall_drop:.4f})")
print(f"  Threshold: <=1pp drop (0.01)")
rpr_recall_pass = rpr_recall_drop <= 0.01
csr_recall_pass = csr_recall_drop <= 0.01
print(f"  RPR RECALL CLAIM: {'PASS' if rpr_recall_pass else 'FAIL'}")
print(f"  CSR RECALL CLAIM: {'PASS' if csr_recall_pass else 'FAIL'}")

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
print(f"  Goose RPR failed: {goose_rpr_failed}/{n}")
print(f"  Goose CSR failed: {goose_csr_failed}/{n}")
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
print(f"  Goose RPR p95 median: {statistics.median(goose_rpr_p95s):.4f}ms")
print(f"  Goose RPR p95 max: {max(goose_rpr_p95s):.4f}ms")

# =====================================================================
# TYPE BREAKDOWN
# =====================================================================

print("\n" + "=" * 70)
print("TYPE BREAKDOWN (RPR vs BM25S)")
print("=" * 70)
types = defaultdict(list)
for m in matched:
    types[m['type']].append(m)
for t in sorted(types.keys()):
    tm = types[t]
    bm_med = statistics.median([m['bm25s_median_ms'] for m in tm])
    goose_med = statistics.median([m['goose_rpr_median_ms'] for m in tm])
    bm_rec = statistics.mean([m['bm25s_recall_at_10'] for m in tm])
    goose_rec = statistics.mean([m['goose_rpr_recall_at_10'] for m in tm])
    print(f"  {t}: n={len(tm)}, BM25S median={bm_med:.2f}ms, Goose RPR median={goose_med:.2f}ms, "
          f"speedup={bm_med/goose_med:.1f}x, BM25S recall={bm_rec:.3f}, Goose recall={goose_rec:.3f}")

# =====================================================================
# PASS RULE ASSESSMENT
# =====================================================================

print("\n" + "=" * 70)
print("PASS RULE ASSESSMENT (Goose RPR vs BM25S)")
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
    "goose_csr_mean_recall_at_10": goose_csr_mean_recall,
    "rpr_recall_drop": rpr_recall_drop,
    "csr_recall_drop": csr_recall_drop,
    "recall_pass": rpr_recall_pass,
    "bm25s_failed": bm_failed,
    "goose_rpr_failed": goose_rpr_failed,
    "goose_csr_failed": goose_csr_failed,
    "failed_pass": failed_pass,
    "bm25s_p95_median": statistics.median(bm_p95s),
    "goose_rpr_p95_median": statistics.median(goose_rpr_p95s),
    "bm25s_p95_max": max(bm_p95s),
    "goose_rpr_p95_max": max(goose_rpr_p95s),
    "overall_pass": overall,
    "matched_queries": matched,
}

with open('locked_test_analysis.json', 'w') as f:
    json.dump(output, f, indent=2, default=str)

print("\nResults saved to locked_test_analysis.json")
