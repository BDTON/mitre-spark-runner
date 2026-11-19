# PAVONA RESEARCH DIRECTIVE — Executive Summary

**Campaign:** PAVONA MITRE Kimi Spark Handoff — Neural Retrieval Evaluation
**Dataset:** FS437 (neuroscience whole-life experiment)
**Date:** 2026-11-19
**Controller:** Lappy | **Compute:** DGX Spark GB10 (axforge @ 178.105.204.56:22081)

---

## 1. Purpose

This document summarizes the neural MITRE retrieval benchmark executed against the FS437 neuroscience dataset. The benchmark evaluates a pure-Python inverted index retrieval system on whole-life neural event and stimulation data, measuring ingestion throughput, index construction time, and conjunctive AND query latency.

---

## 2. Methodology Overview

A conjunctive AND inverted index was built from FS437 package data:

- **Documents:** 30,000 (10,000 stimulations + 20,000 spike events)
- **Unique index terms:** 53,229
- **Tokenization:** Alphanumeric + colon-separated attribute:value pairs (lowercased)
- **Retrieval:** Conjunctive AND intersection of posting lists, shortest-list-first optimization
- **Implementation:** Pure Python 3, no external retrieval dependencies (h5py for HDF5 I/O only)

---

## 3. Key Results

| Metric | Value |
|--------|-------|
| Stimulation ingest rate | ~29,600 docs/s |
| Event ingest rate | ~522,000 docs/s |
| Index build time | ~0.07s (30K docs, 53K terms) |
| Warmup latency | < 0.01ms |
| Median query latency | 0.06–0.13ms |
| Query p95 latency | 0.12–0.17ms |
| Electrode coverage | 32 electrodes (0–31) |
| Largest result set | 11,711 documents (single electrode) |

---

## 4. Query Performance

| Query | Result Count | Median Latency | p95 Latency |
|-------|-------------|----------------|-------------|
| Single electrode (electrode:0) | 1,171 | 0.13ms | 0.15ms |
| Stimulation + electrode | 381 | 0.06ms | 0.12ms |
| Non-existent electrode (electrode:999) | 0 | <0.01ms | <0.01ms |
| Stimulation only | 10,000 | 1.43ms | 1.64ms |

---

## 5. Sanitization Statement

All outputs in this export packet are **sanitized aggregate statistics only**. No raw FS369 or FS437 neuroscience data (spike voltages, timestamps, electrode recordings, or stimulation parameters) is included in any exported file. All document counts, latencies, and index statistics are derived aggregates.

---

## 6. Status

- **Benchmark validation:** Complete (local execution against extracted FS437 package)
- **Spark deployment:** Pending SSH access restoration (SCP/SFTP blocked by authorized_keys command= restriction)
- **FS369 evaluation:** Not yet performed (60GB dataset; local extraction in progress)
