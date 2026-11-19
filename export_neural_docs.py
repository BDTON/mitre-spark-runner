#!/usr/bin/env python3
"""
Export neuroscience documents from HDF5 as text for MITRE/RPR Goose ingestion.
Output format: doc_id\ttext (one document per line)
"""
import h5py
import sys
import os


def export_stimulations(hdf5_path, key, output_file, max_stims=None):
    """Export stimulation records as documents."""
    count = 0
    with h5py.File(hdf5_path, 'r') as f:
        ds = f[key]
        n = min(ds.shape[0], max_stims) if max_stims else ds.shape[0]
        with open(output_file, 'a') as out:
            for i in range(n):
                row = ds[i]
                idx = int(row['index'])
                stim_params = row['values_block_0']
                timestamp = int(row['time_of_stim'])
                electrode = int(row['electrode'])
                params_str = ",".join([f"p{j}={v:.2f}" for j, v in enumerate(stim_params[:4])])
                text = f"stimulation electrode:{electrode} timestamp:{timestamp} params:[{params_str}] stim_idx:{idx}"
                out.write(f"stim_{idx}\t{text}\n")
                count += 1
    return count


def export_events(hdf5_path, key, output_file, max_events=None):
    """Export spike events as documents."""
    count = 0
    with h5py.File(hdf5_path, 'r') as f:
        ds = f[key]
        n = min(ds.shape[0], max_events) if max_events else ds.shape[0]
        with open(output_file, 'a') as out:
            for i in range(n):
                row = ds[i]
                idx = int(row['index'])
                voltage = float(row['values_block_0'][0])
                timestamp = int(row['time_of_event'])
                electrode = int(row['electrode'])
                text = f"electrode:{electrode} voltage:{voltage:.2f} timestamp:{timestamp} event_idx:{idx}"
                out.write(f"event_{idx}\t{text}\n")
                count += 1
    return count


def main():
    hdf5_path = sys.argv[1] if len(sys.argv) > 1 else "/home/dev/fs437data/fs437_export/fs437_package.hdf5"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "/home/dev/neural_docs.txt"

    # Remove existing output
    if os.path.exists(output_file):
        os.remove(output_file)

    print(f"Exporting stimulations from {hdf5_path}...")
    stim_count = export_stimulations(hdf5_path, "fs437_wholelife_stimulations/table", output_file, max_stims=10000)
    print(f"  Exported {stim_count} stimulations")

    print(f"Exporting events from {hdf5_path}...")
    event_count = export_events(hdf5_path, "fs437_wholelife_events/table", output_file, max_events=20000)
    print(f"  Exported {event_count} events")

    total = stim_count + event_count
    print(f"Total documents exported: {total} -> {output_file}")


if __name__ == "__main__":
    main()
