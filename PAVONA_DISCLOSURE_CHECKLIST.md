# PAVONA RESEARCH DIRECTIVE — Disclosure Checklist

**Campaign:** PAVONA MITRE Kimi Spark Handoff — Neural Retrieval Evaluation  
**Date:** 2026-11-19

---

## 1. Data Provenance

| Item | Status | Notes |
|------|--------|-------|
| FS437 package file on Spark | ✅ Available | `/home/dev/fs437data/fs437_export/fs437_package.hdf5` |
| FS437 local copy | ✅ Available | Extracted from `fs437.zip` (1.7GB) |
| FS369 package file | ⚠️ Local only | `fs369.zip` (60GB) not transferred to Spark |
| FS369 raw file | ⚠️ Local only | 270GB; not extracted |
| Local HDF5 inspection | ✅ Complete | h5py 3.16.0 installed on Lappy |

---

## 2. Execution Environment

| Item | Local (Lappy) | Spark (DGX GB10) |
|------|--------------|------------------|
| OS | Windows 11 | Ubuntu 24.04.3 LTS (ARM64) |
| Python | 3.14 | 3.12 |
| h5py | 3.16.0 | 3.16.0 |
| Benchmark status | ✅ Validated | ⏳ Pending SSH access |
| Benchmark script | `neural_retrieval_bench.py` | Same script, not yet deployed |

---

## 3. Known Limitations

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| Sample-limited ingestion (10K stim + 20K events out of 802K + 2.6M) | Full-dataset performance not measured | Ingest parameters configurable via `max_stims`/`max_events` |
| No Spark execution | Results reflect x86_64 Python 3.14, not ARM64 Python 3.12 | Deploy to Spark once SSH access is restored |
| No recall/nDCG metrics | Quality of retrieval not measured against relevance judgments | No labeled relevance data available for neuroscience corpus |
| Single-threaded | No parallel ingestion or query execution | Could be extended with multiprocessing |
| Memory usage not measured | Resident memory not profiled | Requires separate profiling run |
| fs369 not transferred to Spark | 60GB dataset cannot be evaluated on Spark | Local extraction in progress; transfer impractical via SSH |

---

## 4. Sanitization Verification

| Check | Status |
|-------|--------|
| No raw spike voltages in exports | ✅ Verified |
| No raw timestamps in exports | ✅ Verified |
| No raw electrode recordings in exports | ✅ Verified |
| No raw stimulation parameters in exports | ✅ Verified |
| No document text in exports | ✅ Verified |
| Only aggregate statistics in CSV | ✅ Verified |
| Only derived metrics in reports | ✅ Verified |

---

## 5. Deviations from Directive

| Directive Requirement | Status | Explanation |
|----------------------|--------|-------------|
| 27 gated phases | Not all phases completed | Benchmark validation complete; Spark deployment pending |
| Sanitized export packet | ✅ Complete | All exports contain aggregate statistics only |
| Executive summary | ✅ Complete | `PAVONA_EXECUTIVE_SUMMARY.md` |
| Technical report | ✅ Complete | `PAVONA_TECHNICAL_REPORT.md` |
| Aggregate CSV | ✅ Complete | `PAVONA_AGGREGATE_RESULTS.csv` |
| Charts | ⏳ Pending | Not yet generated |
| Methods appendix | ✅ Complete | `PAVONA_METHODS_APPENDIX.md` |
| Disclosure checklist | ✅ Complete | `PAVONA_DISCLOSURE_CHECKLIST.md` |

---

## 6. Next Steps

1. Restore SSH/SFTP access to Spark (authorized_keys command= restriction needs removal)
2. Deploy `neural_retrieval_bench.py` to Spark
3. Run benchmark on Spark ARM64 Python 3.12
4. Compare local vs. Spark results
5. Generate charts from benchmark results
6. Evaluate fs369 dataset (local extraction in progress)
7. Finalize all PAVONA deliverables
