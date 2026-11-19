import json

local = json.load(open('C:/Users/Brand/MITRE-Spark-Runner/neural_retrieval_verify_results.json'))
spark = json.load(open('C:/Users/Brand/MITRE-Spark-Runner/neural_retrieval_spark_verify_results_v2.json'))

print('Dataset:', spark['dataset'])
print('Index terms:', spark['index_terms'])
print('Index build:', spark['index_build_seconds'])
print('Electrodes:', len(spark['electrodes']), spark['electrodes'][:5], '...', spark['electrodes'][-1])
print()
print('Query comparison (Local vs Spark):')
for lq, sq in zip(local['hit_queries'], spark['hit_queries']):
    match = 'MATCH' if lq['index_result_count'] == sq['index_result_count'] and lq['exact_match'] == sq['exact_match'] else 'MISMATCH'
    print(f"  {lq['query']}: local={lq['index_result_count']}/{lq['median_ms']:.3f}ms spark={sq['index_result_count']}/{sq['median_ms']:.3f}ms [{match}]")
print()
mc_local = local['miss_control']
mc_spark = spark['miss_control']
print(f"Miss control: local={mc_local['index_result_count']}/{mc_local['median_ms']:.3f}ms spark={mc_spark['index_result_count']}/{mc_spark['median_ms']:.3f}ms [{'MATCH' if mc_local['index_result_count']==mc_spark['index_result_count'] else 'MISMATCH'}]")
print()
print('Component:', spark['component'])
print('MITRE/RPR invoked:', spark['mitre_rpr_invoked'])
