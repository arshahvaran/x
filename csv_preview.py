#!/usr/bin/env python3
"""
Create a CSV "preview" file (header + first N data rows) with robust handling and progress bars.

What it does
------------
- Set INPUT_CSV below to your file path (e.g., r"C:\path\to\file.csv").
- Auto-detects text encoding (BOM-aware; utf-8, cp1252; latin-1 fallback).
- Detects delimiter/quoting via csv.Sniffer with smart fallbacks.
- Streams the file safely (handles huge CSVs, embedded newlines, very wide fields).
- Writes a preview CSV in the same folder with suffix "_preview" before the extension.
- Keeps original header (if present) and writes up to PREVIEW_ROWS data rows.
- Shows a tqdm progress bar over rows written, with live byte progress in the postfix.

Notes
-----
- Writer uses the *detected input dialect* so the delimiter/quoting match the source.
- Output is encoded as UTF-8 with BOM ("utf-8-sig") for Excel compatibility.
- If the file ends before PREVIEW_ROWS, the progress bar is finalized to the actual total.
"""

from __future__ import annotations

import csv
import io
import os
import sys
from pathlib import Path
from typing import Optional

# Progress bars
try:
    from tqdm import tqdm
except ImportError:
    print("This script requires 'tqdm'. Install it with: pip install tqdm")
    sys.exit(1)

# ========= USER PARAMETER: set your input CSV path here (only this line) =========
INPUT_CSV = r"C:\Users\arsha\Desktop\idea_20\data\process_3_merged_unified_crs\observations_1901_2025_all_unified_crs.csv"
# ================================================================================

# ---------- Tweaks (optional) ----------
PREVIEW_ROWS = 1000  # number of data rows to include in the preview (header not counted)
SNIFF_SAMPLE_BYTES = 2_000_000
ENCODING_SAMPLE_BYTES = 2_000_000
DELIMITER_CANDIDATES = [",", "\t", ";", "|", "^", "~"]
ROWCOUNT_READ_BLOCK_BYTES = 64 * 1024 * 1024  # used only for optional fast row counting (currently not used)
# --------------------------------------


def build_output_path(input_path: Path) -> Path:
    """Same folder, add '_preview' before the full extension chain."""
    stem = input_path.stem
    suffix = "".join(input_path.suffixes) or ".csv"
    return input_path.with_name(f"{stem}_preview{suffix}")


def detect_encoding(path: Path, sample_bytes: int = ENCODING_SAMPLE_BYTES) -> str:
    """
    Detect a reasonable text encoding for CSV reading.
    Priority:
      1) BOM-based detection (UTF-8-SIG, UTF-16 LE/BE, UTF-32 LE/BE)
      2) Try 'utf-8'
      3) Try 'cp1252'
      4) Fallback 'latin-1'
    """
    with open(path, "rb") as fb:
        raw = fb.read(sample_bytes)

    # BOM checks
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    if raw.startswith(b"\xff\xfe\x00\x00"):
        return "utf-32-le"
    if raw.startswith(b"\x00\x00\xfe\xff"):
        return "utf-32-be"
    if raw.startswith(b"\xff\xfe"):
        return "utf-16-le"
    if raw.startswith(b"\xfe\xff"):
        return "utf-16-be"

    # Try utf-8 strict
    try:
        raw.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        pass

    # Try cp1252
    try:
        raw.decode("cp1252")
        return "cp1252"
    except UnicodeDecodeError:
        pass

    # Last resort
    return "latin-1"


def sniff_dialect_and_header(path: Path, encoding: str, sample_bytes: int = SNIFF_SAMPLE_BYTES) -> tuple[csv.Dialect, bool]:
    """
    Sniff CSV dialect and whether a header likely exists.
    Falls back to csv.excel dialect and assumes header if sniffing fails.
    """
    try:
        with open(path, "r", encoding=encoding, errors="replace", newline="") as f:
            sample = f.read(sample_bytes)
            # Prefer candidate delimiters to guide the sniffer
            dialect = csv.Sniffer().sniff(sample, delimiters="".join(DELIMITER_CANDIDATES))
            has_header = False
            try:
                has_header = csv.Sniffer().has_header(sample)
            except Exception:
                has_header = True
            return dialect, has_header
    except Exception:
        # Fallbacks
        return csv.excel, True


def increase_field_size_limit() -> None:
    """Increase csv field size limit for very wide rows."""
    try:
        csv.field_size_limit(10**9)
    except OverflowError:
        csv.field_size_limit(2_147_483_647)


def create_csv_preview(input_csv_path: Path, preview_rows: int = PREVIEW_ROWS) -> Path:
    """
    Create a CSV preview with the same header/columns (if present), limited to `preview_rows` data rows.
    Writes to <same folder>/<original_stem>_preview<original_suffix>.
    Returns the output path.
    """
    if not input_csv_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_csv_path}")

    output_path = build_output_path(input_csv_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Bump field size limit
    increase_field_size_limit()

    # Detect encoding & dialect
    enc = detect_encoding(input_csv_path)
    dialect, has_header = sniff_dialect_and_header(input_csv_path, enc)

    # File size for byte progress (best-effort)
    try:
        file_size = os.path.getsize(input_csv_path)
    except OSError:
        file_size = 0

    # Open raw binary for accurate byte tracking; layer buffering + text decoding
    raw = open(input_csv_path, "rb")
    try:
        buffered = io.BufferedReader(raw)
        text = io.TextIOWrapper(buffered, encoding=enc, errors="replace", newline="")

        # Use utf-8-sig for output to maximize Excel compatibility
        with text, open(output_path, "w", encoding="utf-8-sig", newline="") as fout:
            reader = csv.reader(text, dialect)
            writer = csv.writer(fout, dialect)

            rows_written = 0

            # Handle header if present
            first_row = next(reader, None)
            if first_row is None:
                # Empty file: write nothing and return
                return output_path

            if has_header:
                writer.writerow(first_row)
            else:
                # No header detected—treat first row as data
                writer.writerow(first_row)
                rows_written += 1

            # TQDM over data rows to write (determinate up to preview_rows)
            limit = int(preview_rows)
            remaining = limit - rows_written if has_header else limit - rows_written
            remaining = max(0, remaining)

            desc = "Writing preview"
            with tqdm(total=limit, unit="row", desc=desc, leave=True) as pbar:
                # If we already wrote one data row (no header case), update bar
                if not has_header and rows_written > 0:
                    pbar.update(rows_written)

                for row in reader:
                    if rows_written >= limit:
                        break
                    writer.writerow(row)
                    rows_written += 1
                    pbar.update(1)

                    # Update byte-based postfix periodically (every 200 rows or at end)
                    if rows_written % 200 == 0 or rows_written == limit:
                        try:
                            bytes_read = raw.tell()
                        except Exception:
                            bytes_read = 0
                        pct = f"{(bytes_read / file_size * 100):.1f}%" if file_size else "NA"
                        pbar.set_postfix(
                            rows=rows_written,
                            bytes=f"{bytes_read/1e6:.1f}/{(file_size or 1)/1e6:.1f} MB",
                            pct=pct,
                        )

                # If file ended before reaching limit, finalize the bar neatly
                if rows_written < limit:
                    pbar.total = rows_written
                    pbar.refresh()

    finally:
        raw.close()

    return output_path


def main():
    # Only input is the CSV path constant at the top
    raw_path = INPUT_CSV.strip()
    if (raw_path.startswith('"') and raw_path.endswith('"')) or (raw_path.startswith("'") and raw_path.endswith("'")):
        raw_path = raw_path[1:-1]
    in_path = Path(raw_path).expanduser()

    print("------------------------------------------------------------")
    print(f"Input file        : {in_path}")
    if not in_path.exists():
        print("ERROR: File not found.")
        sys.exit(1)

    enc = detect_encoding(in_path)
    dialect, has_header = sniff_dialect_and_header(in_path, enc)
    out_path = build_output_path(in_path)

    print(f"Detected encoding : {enc}")
    try:
        delimiter = getattr(dialect, "delimiter", ",")
    except Exception:
        delimiter = ","
    print(f"Detected delimiter: {repr(delimiter)}")
    print(f"Has header?       : {has_header}")
    print(f"Preview rows      : {PREVIEW_ROWS}")
    print(f"Output file       : {out_path}")
    print("------------------------------------------------------------")

    try:
        result = create_csv_preview(in_path, preview_rows=PREVIEW_ROWS)
    except Exception as e:
        tqdm.write("Failed to create preview.")
        tqdm.write(f"Reason: {e}")
        sys.exit(1)

    print(f"Preview written: {result}")


if __name__ == "__main__":
    main()
