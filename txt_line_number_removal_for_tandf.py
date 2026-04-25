import re
import os
import sys
from collections import Counter

# =============================================================================
#  CONFIGURATION  — edit these before running
# =============================================================================

INPUT_FILE = r"C:\Users\arsha\OneDrive\Desktop\content.txt"

# --- Mechanism 1: Margin line numbers ---
# A standalone integer must appear this many times to be flagged as a margin
# number. For multi-page documents each margin number repeats once per page,
# so 2 is a safe default. For short files set to 1.
MIN_OCCURRENCES = 2

# Manual override: set both to force a specific range (e.g. FORCE_MIN=1,
# FORCE_MAX=60). Leave as None to use auto-detection.
FORCE_MIN = None
FORCE_MAX = None

# --- Mechanism 2: Watermark single-character lines ---
# Removes lines whose ENTIRE content is a single letter (A–Z / a–z).
# These are fragments of diagonal PDF watermarks ("For Peer Review",
# "Confidential", "Draft", etc.). Set False if your doc uses lone letters.
REMOVE_WATERMARK = True

# --- Mechanism 3: Page marker lines ---
# Removes lines matching "Page X of Y" (case-insensitive).
REMOVE_PAGE_MARKERS = True

# --- Mechanism 4: Blank line normalisation ---
# Collapses mid-paragraph blank gaps (detected by the next line starting with
# a lowercase letter) and normalises all remaining multi-blank runs to exactly
# one blank line.
NORMALIZE_BLANK_LINES = True

# --- Encodings to try, in order ---
ENCODINGS = ['utf-8', 'utf-8-sig', 'cp1252', 'latin-1']

# =============================================================================


def detect_encoding(filepath, encodings):
    """Try each encoding in order; return the first one that works."""
    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                f.read()
            return enc
        except (UnicodeDecodeError, LookupError):
            continue
    return None


def detect_margin_number_range(lines, min_occurrences):
    """
    Auto-detects the range [range_min, range_max] of margin line numbers.

    In a paginated document each margin number repeats once per page
    (e.g. "1" appears ~47 times as a bare standalone line in a 47-page paper),
    whereas in-text numbers almost never appear as a completely bare line.

    Steps
    -----
    1. Count how often each integer appears as a COMPLETE standalone line.
    2. Keep integers that appear >= min_occurrences times.
    3. Find the longest contiguous run starting from 1 (or the lowest found).
       Stopping at the first gap is intentionally conservative: it prevents
       accidentally flagging an in-text number that happened to appear alone.
    """
    value_counts = Counter()
    for line in lines:
        stripped = line.strip()
        if re.fullmatch(r'\d+', stripped):
            value_counts[int(stripped)] += 1

    if not value_counts:
        return None, None

    frequent = {v for v, cnt in value_counts.items() if cnt >= min_occurrences}
    if not frequent:
        return None, None

    range_min = 1 if 1 in frequent else min(frequent)
    range_max = range_min
    while (range_max + 1) in frequent:
        range_max += 1

    return range_min, range_max


def is_watermark_line(stripped):
    """
    True if the line is a single alphabetic character — the hallmark of a
    diagonal PDF watermark fragment.

    Why safe: legitimate prose never has a lone letter on its own line.
    Covers any watermark text: "For Peer Review", "Confidential", "Draft",
    "Do Not Distribute", etc. — they all produce isolated single characters.
    """
    return bool(re.fullmatch(r'[A-Za-z]', stripped))


def is_page_marker_line(stripped):
    """
    True for lines like "Page 5 of 47", "page 12 of 100", "PAGE 3 OF 20".
    Anchored to the full line, so "described on Page 5 of 47" is kept.
    """
    return bool(re.fullmatch(r'page\s+\d+\s+of\s+\d+', stripped, re.IGNORECASE))


def normalize_blank_lines(lines):
    """
    Mechanism 4 — fix the blank lines left behind after mechanisms 1–3.

    Core insight
    ------------
    A blank run between two text lines is a MID-PARAGRAPH split if and only
    if the first non-blank line that follows starts with a LOWERCASE letter.

    This is the most reliable signal in English prose:
      - A sentence continuing within a paragraph starts with lowercase
        ("suffer from...", "et al., 2025", "optical imagery...", etc.)
      - A new paragraph, heading, figure caption, reference entry, or formula
        always starts with an uppercase letter.

    The one natural exception is URLs ("https://...") — but joining a
    reference line with its own DOI URL is actually CORRECT behaviour, because
    in a reference list the DOI immediately follows the citation details.

    Algorithm
    ---------
    Scan linearly; when a blank run is encountered:
      • Next line starts LOWERCASE  →  remove all blanks, join the previous
        content line and the next line with a single space (cascades correctly
        because after joining, i advances to the NEXT blank/content, so a
        chain of split lines gets progressively merged in one pass).
      • Next line starts UPPERCASE  →  keep exactly ONE blank line.
    Trailing blank lines at the end of the file are discarded.
    Leading blank lines at the top of the file are discarded.
    """
    result = []
    i = 0

    while i < len(lines):
        line = lines[i]

        if line.strip() == '':
            # ── Collect the entire consecutive blank run ──
            while i < len(lines) and lines[i].strip() == '':
                i += 1

            if i >= len(lines):
                # Trailing blanks — discard silently
                break

            next_line  = lines[i]
            next_strip = next_line.strip()

            if next_strip and next_strip[0].islower():
                # ── Mid-paragraph continuation ──
                # Join the previous content line with next_line, no blank between.
                if result and result[-1].strip():
                    prev   = result.pop()
                    joined = prev.rstrip('\n').rstrip() + ' ' + next_line.lstrip()
                    result.append(joined)
                    i += 1  # next_line has been consumed into the join
                else:
                    # Nothing to join to (e.g. blank at top of file) —
                    # keep one blank and let next_line be processed normally.
                    result.append('\n')
                    # Do NOT advance i; next_line is processed next iteration.
            else:
                # ── Legitimate paragraph / section break ──
                # Collapse the entire blank run to exactly one blank line.
                result.append('\n')
                # Do NOT advance i; next_line is processed next iteration.

        else:
            result.append(line)
            i += 1

    # Remove any blank lines that remain at the very top of the document
    while result and result[0].strip() == '':
        result.pop(0)

    return result


def clean_document(
    input_file,
    output_file=None,
    min_occurrences=MIN_OCCURRENCES,
    force_min=None,
    force_max=None,
    remove_watermark=REMOVE_WATERMARK,
    remove_page_markers=REMOVE_PAGE_MARKERS,
    normalize_blanks=NORMALIZE_BLANK_LINES,
    encodings=None,
    verbose=True,
):
    """
    Clean a plain-text document by applying four independent mechanisms:

      1. Margin / sidebar line numbers  — bare integers repeating each page
      2. PDF watermark character lines  — lone letters like w, e, R, F
      3. Page marker lines              — "Page 5 of 47"
      4. Blank line normalisation       — mid-paragraph gaps collapsed & joined;
                                          paragraph breaks normalised to one blank

    Parameters
    ----------
    input_file        : str        Path to the input .txt file.
    output_file       : str|None   Output path. Defaults to <stem>_clean<ext>.
    min_occurrences   : int        Minimum standalone appearances to flag a
                                   number as a margin number (default 2).
    force_min/max     : int|None   Override auto-detected margin number bounds.
    remove_watermark  : bool       Strip single-letter watermark lines.
    remove_page_markers: bool      Strip "Page X of Y" lines.
    normalize_blanks  : bool       Run mechanism 4.
    encodings         : list|None  Encodings to attempt in order.
    verbose           : bool       Print a detailed summary report.
    """

    if encodings is None:
        encodings = ENCODINGS

    # ── Resolve output path ──
    if output_file is None:
        base, ext = os.path.splitext(input_file)
        output_file = f"{base}_clean{ext}"

    # ── Detect encoding ──
    enc = detect_encoding(input_file, encodings)
    if enc is None:
        print("ERROR: Could not decode the file with any of the tried encodings:", encodings)
        sys.exit(1)
    if verbose:
        print(f"Encoding detected        : {enc!r}")

    # ── Read file ──
    with open(input_file, 'r', encoding=enc, errors='replace') as f:
        lines = f.readlines()

    if verbose:
        print(f"Total lines read         : {len(lines)}")

    # ── Mechanism 1: detect margin line number range ──
    if force_min is not None and force_max is not None:
        range_min, range_max = force_min, force_max
        if verbose:
            print(f"Margin range (manual)    : {range_min} – {range_max}")
    else:
        range_min, range_max = detect_margin_number_range(lines, min_occurrences)
        if range_min is None:
            if verbose:
                print("Margin numbers           : none detected "
                      "(check MIN_OCCURRENCES or use FORCE_MIN/FORCE_MAX)")
        else:
            if force_min is not None: range_min = force_min
            if force_max is not None: range_max = force_max
            if verbose:
                print(f"Margin range (auto)      : {range_min} – {range_max}")

    # ── Mechanisms 1–3: line-by-line filtering ──
    output_lines = []
    counts = {
        'margin_numbers':  0,
        'watermark_chars': 0,
        'page_markers':    0,
        'blank_lines':     0,
    }
    removed_margin_values = Counter()

    for line in lines:
        stripped = line.strip()

        # Mechanism 1 — margin line number
        if range_min is not None and re.fullmatch(r'\d+', stripped):
            val = int(stripped)
            if range_min <= val <= range_max:
                counts['margin_numbers'] += 1
                removed_margin_values[val] += 1
                continue

        # Mechanism 2 — watermark single-character line
        if remove_watermark and is_watermark_line(stripped):
            counts['watermark_chars'] += 1
            continue

        # Mechanism 3 — page marker
        if remove_page_markers and is_page_marker_line(stripped):
            counts['page_markers'] += 1
            continue

        output_lines.append(line)

    # ── Mechanism 4: blank line normalisation ──
    if normalize_blanks:
        lines_before = len(output_lines)
        output_lines  = normalize_blank_lines(output_lines)
        counts['blank_lines'] = lines_before - len(output_lines)

    # ── Write output ──
    with open(output_file, 'w', encoding='utf-8') as f:
        f.writelines(output_lines)

    # ── Verbose report ──
    if verbose:
        print(f"\n{'─' * 48}")
        print(f"  CLEANING REPORT")
        print(f"{'─' * 48}")
        print(f"  Margin line numbers removed  : {counts['margin_numbers']}")
        if range_min is not None:
            unique   = len(removed_margin_values)
            expected = range_max - range_min + 1
            print(f"    Unique values removed      : {unique} of {expected} expected")
            missing  = [v for v in range(range_min, range_max + 1)
                        if v not in removed_margin_values]
            if missing:
                preview = missing[:10]
                dots    = '...' if len(missing) > 10 else ''
                print(f"    Never seen as standalone   : {preview}{dots} "
                      f"(always inside text — correct)")
        print(f"  Watermark chars removed      : {counts['watermark_chars']}"
              + ("  (disabled)" if not remove_watermark else ""))
        print(f"  Page markers removed         : {counts['page_markers']}"
              + ("  (disabled)" if not remove_page_markers else ""))
        print(f"  Blank lines removed/merged   : {counts['blank_lines']}"
              + ("  (disabled)" if not normalize_blanks else ""))
        print(f"{'─' * 48}")
        total = sum(counts.values())
        print(f"  Total lines removed          : {total}")
        print(f"  Lines in output              : {len(output_lines)}")
        print(f"{'─' * 48}")
        print(f"\n  Output saved to: {output_file}")
        print("  Done.\n")


# =============================================================================
#  Entry point
# =============================================================================

if __name__ == "__main__":
    clean_document(
        input_file=INPUT_FILE,
        min_occurrences=MIN_OCCURRENCES,
        force_min=FORCE_MIN,
        force_max=FORCE_MAX,
        remove_watermark=REMOVE_WATERMARK,
        remove_page_markers=REMOVE_PAGE_MARKERS,
        normalize_blanks=NORMALIZE_BLANK_LINES,
        verbose=True,
    )
