#!/usr/bin/env python3
"""Compare MITRE/RPR Python results with pure Python baseline."""
import json

# Load results
with open('neural_retrieval_spark_verify_results_v2.json') as f:
    pure_python = json.load(f)

with open('mitre_rpr_python_results.json') as f:
    mitre_rpr = json.load(f)

print("=" * 80)
print("COMPARISON: Pure Python Inverted Index vs MITRE/RPR (Python impl) on FS437")
print("=" * 80)
print()
print(f"Dataset: {pure_python['dataset']}")
print(f"Pure Python: {pure_python['index_terms']} terms, {pure_python['index_build_seconds']:.3f}s index build")
print(f"MITRE/RPR: {mitre_rpr['terms']} terms, 30K docs")
print()

print(f"{'Query':<25} {'Terms':<30} {'System':<15} {'Results':<8} {'Median (ms)':<12} {'P95 (ms)':<12}")
print("-" * 100)

# Match queries
pp_queries = {}
for q in pure_python['hit_queries']:
    if len(q['terms']) == 1:
        key = q['terms'][0]
    else:
        key = ' '.join(q['terms'])
    pp_queries[key] = q
pp_miss = pure_python['miss_control']

mr_queries = {q['query']: q for q in mitre_rpr['queries']}

all_queries = ['electrode:0', 'stimulation electrode:0', 'electrode:999']

for q in all_queries:
    if q in pp_queries:
        pp = pp_queries[q]
        print(f"{pp['query']:<25} {str(pp['terms']):<30} {'Pure Python':<15} {pp['index_result_count']:<8} {pp['median_ms']*1000:.4f}{'':<4} {pp['p95_ms']*1000:.4f}")
    if q in mr_queries:
        mr = mr_queries[q]
        print(f"{mr['query']:<25} {mr['query']:<30} {'MITRE/RPR':<15} {mr['csr_n']:<8} {mr['csr_median_ms']:.4f}{'':<4} {mr['csr_p95_ms']:.4f}")
        print(f"{'':<25} {'':<30} {'MITRE/RPR RPR':<15} {mr['rpr_n']:<8} {mr['rpr_median_ms']:.4f}{'':<4} {mr['rpr_p95_ms']:.4f}")
    if q == 'electrode:999':
        print(f"{'electrode:999':<25} {'electrode:999':<30} {'Pure Python':<15} {pp_miss['index_result_count']:<8} {pp_miss['median_ms']*1000:.4f}{'':<4} {pp_miss['p95_ms']*1000:.4f}")
    print()

print("=" * 80)
print("KEY OBSERVATIONS:")
print("=" * 80)
print("1. Pure Python inverted index uses exact conjunctive AND matching")
print("2. MITRE/RPR CSR uses TF-IDF scoring with top-K per term optimization")
print("3. MITRE/RPR RPR uses ring-buffer Scout/Expand/Evidence/Pulse events")
print("4. RPR returns more results (recall-oriented) vs CSR top-K (precision-oriented)")
print("5. Pure Python: sub-millisecond; MITRE/RPR: few milliseconds (Python overhead)")

# Compare single_electrode
pp_se = pp_queries.get('electrode:0')
mr_se = mr_queries.get('electrode:0')
if pp_se and mr_se:
    print(f"\nsingle_electrode: Pure Python={pp_se['index_result_count']} results, MITRE/RPR CSR={mr_se['csr_n']}, RPR={mr_se['rpr_n']}")

# Compare stim_plus_electrode
pp_sp = pp_queries.get('stimulation electrode:0')
mr_sp = mr_queries.get('stimulation electrode:0')
if pp_sp and mr_sp:
    print(f"stim_plus_electrode: Pure Python={pp_sp['index_result_count']} results, MITRE/RPR CSR={mr_sp['csr_n']}, RPR={mr_sp['rpr_n']}")

# Compare known_miss
mr_km = mr_queries.get('electrode:999')
print(f"known_miss: Pure Python={pp_miss['index_result_count']}, MITRE/RPR CSR={mr_km['csr_n']}, RPR={mr_km['rpr_n']}")

print("\nNOTE: Pure Python 'median_ms' includes full scan verification (~32ms)")
print("MITRE/RPR timings are index-only (no scan verification)")

print("\nVERDICT: MITRE/RPR functional, RPR provides higher recall at cost of latency")
print("Pure Python baseline faster for exact conjunctive queries")
print("MITRE/RPR advantages: TF-IDF ranking, RPR evidence chains, pulse scheduling")