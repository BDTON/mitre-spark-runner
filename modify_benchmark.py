import sys

with open('/home/dev/benchmark_1m.goose', 'r') as f:
    content = f.read()

# Replace the summary section to add 1M
old = '''    print("{} | {} | {:.0f} | {} | {:.1f} | {}\\n",
        result_100k.corpus_size, result_100k.ingest_time_ms, result_100k.ingest_docs_per_sec,
        result_100k.index_build_time_ms, result_100k.concurrent_qps, result_100k.memory_estimate_mb);'''

new = '''    print("{} | {} | {:.0f} | {} | {:.1f} | {}\\n",
        result_100k.corpus_size, result_100k.ingest_time_ms, result_100k.ingest_docs_per_sec,
        result_100k.index_build_time_ms, result_100k.concurrent_qps, result_100k.memory_estimate_mb);
    print("{} | {} | {:.0f} | {} | {:.1f} | {}\\n",
        result_1m.corpus_size, result_1m.ingest_time_ms, result_1m.ingest_docs_per_sec,
        result_1m.index_build_time_ms, result_1m.concurrent_qps, result_1m.memory_estimate_mb);'''

if old in content:
    content = content.replace(old, new)
    with open('/home/dev/benchmark_1m.goose', 'w') as f:
        f.write(content)
    print("Successfully modified benchmark_1m.goose")
else:
    print("Could not find target string")
    # Debug: show the area around result_100k.memory_estimate_mb
    idx = content.find('result_100k.memory_estimate_mb')
    if idx >= 0:
        print("Found at:", idx)
        print("Context:", repr(content[idx-100:idx+100]))
