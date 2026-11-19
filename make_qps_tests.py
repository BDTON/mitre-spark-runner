#!/usr/bin/env python3
"""
MITRE QPS boundary test at 1M corpus.
Tests different QPS iteration counts to find the stack overflow threshold.
Modifies benchmark_1m.goose to test 3, 5, 7 iterations.
"""

import re
import shutil
import os

# Read the current benchmark_1m.goose
with open('/home/dev/benchmark_1m.goose', 'r') as f:
    content = f.read()

# Find the concurrent QPS test section
# We want to test different iteration counts
old_qps = '''    for _ in 0..10 {'''
new_qps_3 = '''    for _ in 0..3 {'''

# Create test versions
for iterations in [3, 5, 7]:
    test_content = content.replace('for _ in 0..10 {', f'for _ in 0..{iterations} {{')
    filename = f'/home/dev/benchmark_1m_qps{iterations}.goose'
    with open(filename, 'w') as f:
        f.write(test_content)
    print(f"Created {filename} with {iterations} QPS iterations")

print("Done. Run each with: ./build/goose run benchmark_1m_qpsN.goose")
