#!/usr/bin/env python3
"""
Build a "unique values per column" CSV from any input CSV, with progress bars.

What it does
------------
- Set INPUT_CSV below to your file path (e.g., r"C:\path\to\file.csv").
- Auto-detects text encoding (utf-8-sig, utf-8, cp1252, latin-1).
- Detects delimiter (csv.Sniffer + fallback).
- Streams the file in chunks (so huge files are OK).
- Shows detailed tqdm progress bars:
    1) Optional fast pass to count total rows (by counting newlines).
    2) Main pass that processes rows in chunks and updates progress.
- Writes an output CSV in the same folder with suffix "_unique_values",
  preserving original headers; each column lists only its unique values.
- Uses the input delimiter for the output as well.

Notes
-----
- Everything is read as text (dtype=str) to preserve formatting like leading zeros.
- Blank/NA values are normalized to empty string and included at most once per column.
- Row counting is based on newline characters; if your CSV contains embedded newlines
  inside quoted fields, the pre-count may be approximate (progress still works).
"""

from __future__ import annotations

import os
import sys
import io
import csv
from pathlib import Path
from typing import Dict, List, Tuple

try:
    import pandas as pd
except ImportError:
    print("This script requires the 'pandas' package. Install it with: pip install pandas")
    sys.exit(1)

try:
    from tqdm import tqdm
except ImportError:
    print("This script requires the 'tqdm' package for progress bars. Install it with: pip install tqdm")
    sys.exit(1)

# ========= USER PARAMETER: set your input CSV path here =========
INPUT_CSV = r"C:\Users\arsha\Desktop\idea_20\data\process_3_merged_unified_crs\observations_1901_2025_all_unified_crs.csv"
# ================================================================

# ---------- Configs you can tweak if needed ----------
CHUNK_ROWS = 200_000                       # streaming chunk size
DELIMITER_CANDIDATES = [",", "\t", ";", "|", "^", "~"]
ENCODING_CANDIDATES = ["utf-8-sig", "utf-8", "cp1252", "latin-1"]
COUNT_TOTAL_ROWS = True                    # set False to skip pre-count pass
ROWCOUNT_READ_BLOCK_BYTES = 64 * 1024 * 1024  # 64 MiB blocks for fast counting
# ----------------------------------------------------


def detect_encoding(file_path: Path, max_bytes: int = 2_000_000) -> str:
    """Best-effort encoding detection by trial decoding."""
    with file_path.open("rb") as f:
        sample = f.read(max_bytes)
    for enc in ENCODING_CANDIDATES:
        try:
            sample.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue
    return "latin-1"


def get_sample_text(file_path: Path, encoding: str, max_bytes: int = 2_000_000) -> str:
    """Decode a small sample for delimiter sniffing."""
    with file_path.open("rb") as f:
        sample = f.read(max_bytes)
    try:
        return sample.decode(encoding, errors="strict")
    except UnicodeDecodeError:
        return sample.decode("latin-1", errors="replace")


def sniff_delimiter(sample_text: str) -> str:
    """Use csv.Sniffer to detect delimiter; fall back to best-count heuristic, then comma."""
    try:
        dialect = csv.Sniffer().sniff(sample_text, delimiters="".join(DELIMITER_CANDIDATES))
        if dialect.delimiter:
            return dialect.delimiter
    except Exception:
        pass
    counts = {d: sample_text.count(d) for d in DELIMITER_CANDIDATES}
    best = max(counts, key=counts.get)
    return best if counts[best] > 0 else ","


def normalize_value(x) -> str:
    """Normalize values (treat None/NaN/whitespace-only as empty string)."""
    if x is None:
        return ""
    s = str(x).strip()
    return s


def fast_count_rows(file_path: Path) -> int:
    """
    Fast row count based on newline characters.
    Returns total lines in file (including header line, if present).
    """
    file_size = file_path.stat().st_size
    total_newlines = 0
    with file_path.open("rb") as f, tqdm(
        total=file_size,
        unit="B",
        unit_scale=True,
        unit_divisor=1024,
        desc="Counting rows (fast pass)",
        leave=False,
    ) as pbar:
        while True:
            chunk = f.read(ROWCOUNT_READ_BLOCK_BYTES)
            if not chunk:
                break
            total_newlines += chunk.count(b"\n")
            pbar.update(len(chunk))
    # If the file doesn't end with a newline, we may have one more row
    # Most CSV writers end with newline; keep the simple count.
    return total_newlines


def read_headers(file_path: Path, delimiter: str, encoding: str) -> List[str]:
    """Read only the header row to get column names."""
    try:
        df = pd.read_csv(
            file_path,
            sep=delimiter,
            encoding=encoding,
            nrows=0,
            dtype=str,
            engine="python",
            on_bad_lines="skip",
        )
    except TypeError:
        df = pd.read_csv(
            file_path,
            sep=delimiter,
            encoding=encoding,
            nrows=0,
            dtype=str,
            engine="python",
        )
    cols = list(df.columns)
    if not cols:
        raise ValueError("No columns detected in the input CSV (empty header).")
    return cols


def unique_values_per_column(
    file_path: Path,
    encoding: str,
    delimiter: str,
    columns: List[str],
    total_rows_no_header: int | None,
) -> Dict[str, List[str]]:
    """
    Stream the CSV and collect unique values per column (order of first appearance).
    Shows a tqdm progress bar for processed data rows.
    """
    seen: Dict[str, set] = {col: set() for col in columns}
    values: Dict[str, List[str]] = {col: [] for col in columns}

    read_kwargs = dict(
        sep=delimiter,
        encoding=encoding,
        dtype=str,
        engine="python",
    )

    # Build chunk iterator (compat across pandas versions)
    try:
        iterator = pd.read_csv(
            file_path,
            chunksize=CHUNK_ROWS,
            keep_default_na=False,
            na_filter=False,
            on_bad_lines="skip",
            **read_kwargs,
        )
    except TypeError:
        iterator = pd.read_csv(
            file_path,
            chunksize=CHUNK_ROWS,
            keep_default_na=False,
            na_filter=False,
            **read_kwargs,
        )

    # Progress bar over rows (excluding header)
    desc = "Processing rows"
    total = total_rows_no_header if (isinstance(total_rows_no_header, int) and total_rows_no_header >= 0) else None
    with tqdm(total=total, unit="rows", desc=desc) as row_bar:
        processed = 0
        for chunk in iterator:
            # Ensure all expected columns exist
            missing = [c for c in columns if c not in chunk.columns]
            for c in missing:
                chunk[c] = ""

            for col in columns:
                for raw in chunk[col]:
                    val = normalize_value(raw)
                    if val not in seen[col]:
                        seen[col].add(val)
                        values[col].append(val)

            # update progress
            n = len(chunk.index)
            processed += n
            row_bar.update(n)

        # If total was unknown and we finished, make the bar complete for neatness
        if total is None:
            row_bar.total = processed
            row_bar.refresh()

    return values


def write_unique_values_csv(
    output_path: Path,
    values: Dict[str, List[str]],
    columns: List[str],
    delimiter: str,
    encoding: str = "utf-8-sig",
) -> None:
    """Write the wide CSV where each column contains only its unique values."""
    max_len = max((len(values[c]) for c in columns), default=0)
    data = {}
    for col in columns:
        col_vals = values[col]
        if len(col_vals) < max_len:
            col_vals = col_vals + [""] * (max_len - len(col_vals))
        data[col] = col_vals

    df_out = pd.DataFrame(data, columns=columns)
    df_out.to_csv(output_path, index=False, sep=delimiter, encoding=encoding)


def build_output_path(input_path: Path) -> Path:
    """Same folder, add '_unique_values' before the original extension(s)."""
    stem = input_path.stem
    suffix = "".join(input_path.suffixes) or ".csv"
    return input_path.with_name(f"{stem}_unique_values{suffix}")


def main():
    if not INPUT_CSV:
        print("ERROR: Please set INPUT_CSV at the top of this script to your CSV path.")
        sys.exit(1)

    raw_path = INPUT_CSV.strip()
    if (raw_path.startswith('"') and raw_path.endswith('"')) or (raw_path.startswith("'") and raw_path.endswith("'")):
        raw_path = raw_path[1:-1]

    in_path = Path(raw_path).expanduser()
    if not in_path.exists():
        print(f"ERROR: File not found:\n  {in_path}")
        sys.exit(1)

    # Detect encoding & delimiter
    encoding = detect_encoding(in_path)
    sample_text = get_sample_text(in_path, encoding=encoding)
    delimiter = sniff_delimiter(sample_text)
    out_path = build_output_path(in_path)

    print("------------------------------------------------------------")
    print(f"Input file        : {in_path}")
    print(f"Detected encoding : {encoding}")
    print(f"Detected delimiter: {repr(delimiter)}")
    print(f"Output file       : {out_path}")
    print("------------------------------------------------------------")

    # Read headers
    columns = read_headers(in_path, delimiter, encoding)

    # Optional: fast row count pass (to display a determinate progress bar)
    total_rows_no_header = None
    if COUNT_TOTAL_ROWS:
        total_lines_including_header = fast_count_rows(in_path)
        total_rows_no_header = max(0, total_lines_including_header - 1)

    # Main pass
    try:
        values = unique_values_per_column(
            in_path,
            encoding=encoding,
            delimiter=delimiter,
            columns=columns,
            total_rows_no_header=total_rows_no_header,
        )
        write_unique_values_csv(out_path, values, columns, delimiter=delimiter, encoding="utf-8-sig")
    except Exception as e:
        tqdm.write("Failed to build unique-values CSV.")
        tqdm.write(f"Reason: {e}")
        sys.exit(1)

    # Summary
    tqdm.write("Done.")
    tqdm.write("Unique counts per column:")
    for col in columns:
        tqdm.write(f"  - {col}: {len(values[col])} unique value(s)")


if __name__ == "__main__":
    main()
