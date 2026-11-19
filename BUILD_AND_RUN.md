# BUILD_AND_RUN — MITRE/PRISM Goose Benchmark on Spark

**Campaign:** PAVONA MITRE Kimi Spark Handoff
**Target:** Spark (axforge @ 178.105.204.56:22081, user: dev)
**Snapshot:** `C:\Users\Brand\MITRE-Spark-Runner\snapshot\goose\` (894 files, SHA256-verified)

---

## 1. Prerequisites on Spark

```bash
# Toolchain (verified working)
gcc-13, cc, make, cmake 3.27+, libc6-dev
Python 3.12.3, pip
TinyCC 0.9.28rc (third_party/tinycc/)

# PATH (required for cmake to find compiler/make)
export PATH=/usr/bin:/bin:/home/dev/.local/bin

# Python packages (for comparison scripts)
pip install bm25s==0.3.16 rank-bm25==0.2.2 numpy
```

---

## 2. Transfer Snapshot to Spark

```bash
# From Lappy
scp -r C:\Users\Brand\MITRE-Spark-Runner\snapshot\goose\ dev@178.105.204.56:/home/dev/
# 894 files, ~34MB via tar-over-SSH (resumable)
```

---

## 3. Build Goose Compiler

```bash
cd /home/dev/snapshot/goose

# Configure
cmake -S . -B build

# Build (parallel)
cmake --build build -j $(nproc)

# Binary: /home/dev/snapshot/goose/build/goose
```

**Build output:** `build/goose` compiler binary (v2026.4-55-g007843c7-dirty), TinyCC JIT backend.

---

## 4. Run Benchmarks

### MITRE Optimized (10K + 100K)

```bash
cd /home/dev/snapshot/goose
./build/goose run mitre/benchmark_opt.goose
```

**Expected output (optimized):**
```
=== MITRE/PRISM Goose Benchmark (Optimized): 10000 docs ===
  Ingest: 62 ms, CSR build: 58 ms
  Query medians: 0.32-0.49 ms
  QPS: ~2840
  Mem: 18 MB

=== MITRE/PRISM Goose Benchmark (Optimized): 100000 docs ===
  Ingest: 344 ms, CSR build: 651 ms
  Query medians: 3.25-4.88 ms
  QPS: ~2810
  Mem: 182 MB
```

### MITRE at 1M Corpus

```bash
cd /home/dev
./build/goose run benchmark_1m.goose
```

**Note:** `benchmark_1m.goose` is a copy of `benchmark_opt.goose` with concurrent QPS iterations reduced from 10 → 3 to avoid data stack overflow at 1M scale.

**Expected output:**
```
  Ingest: 3480 ms, CSR build: 7347 ms
  Query medians: 35.85-52.18 ms
  Concurrent QPS: CRASHES (data stack overflow > 2GB reserve)
```

---

## 5. Run Python Comparisons (BM25S, rank_bm25)

```bash
cd /home/dev
python3 python_comparison.py
```

**Output:** `/home/dev/python_comparison_results.json`

### Run SQLite FTS5 Comparison

```bash
cd /home/dev
python3 sqlite_fts5_bench.py
```

**Output:** `/home/dev/sqlite_fts5_results.json`

---

## 6. Export Results to Lappy

```bash
# From Lappy
scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -P 22081 \
  dev@178.105.204.56:/home/dev/python_comparison_results.json \
  dev@178.105.204.56:/home/dev/sqlite_fts5_results.json \
  dev@178.105.204.56:/home/dev/snapshot/SHA256SUMS \
  dev@178.105.204.56:/home/dev/snapshot-manifest.txt \
  C:\Users\Brand\MITRE-Spark-Runner\

# Verify hashes
cd C:\Users\Brand\MITRE-Spark-Runner\snapshot
sed 's/\r$//' ../SHA256SUMS > SHA256SUMS_fixed.txt
sha256sum -c SHA256SUMS_fixed.txt  # 893 OK, 0 FAILED
```

---

## 7. Known Issues

| Issue | Impact | Workaround |
|-------|--------|------------|
| Data stack overflow at 1M concurrent QPS | Crash during concurrent QPS test | Reduce iterations to 3; query benchmarks complete fine |
| `unified_bench.goose` won't run on Spark | Hardcoded `D:\MITRE` paths | Use `benchmark_opt.goose` / `benchmark_1m.goose` instead |
| Tantivy unavailable | No Python bindings, needs Rust compilation | Marked UNAVAILABLE in VICTORY_CONTRACT |
| Dense retriever unavailable | No embedding model authorized | Marked UNAVAILABLE in VICTORY_CONTRACT |

---

## 8. Deliverables

| File | Description |
|------|-------------|
| `RECOMMENDED_CONFIG.md` | Recommended MITRE/PRISM configuration |
| `BUILD_AND_RUN.md` | This file — build and run instructions |
| `PROTOCOL.md` | Benchmark protocol and methodology |
| `OPTIMIZATION_LOG.md` | Optimization changes and measured impact |
| `SCOREBOARD.md` | Per-race scoreboard (10K / 100K / 1M) |
| `python_comparison_results.json` | BM25S / rank_bm25 raw results |
| `sqlite_fts5_results.json` | SQLite FTS5 raw results |
| `SHA256SUMS` | Snapshot file integrity manifest |
| `snapshot-manifest.txt` | Snapshot contents and provenance |
