"""
=============================================================================
  Universal text cleaner for PDF-extracted journal manuscripts
=============================================================================

Cleans the noise that Adobe Acrobat (and similar PDF -> .txt extractors) leave
behind in journal-style proofs: margin / inline line numbers, soft-hyphen
artefacts at line-wrap boundaries, single-letter watermark lines, "Page X of
Y" markers, multi-blank gaps, redundant internal spaces, and so on.

It is built around four independent, configurable mechanisms — each can be
toggled on/off — and ends with a detailed report so you can audit what was
removed.  The defaults are tuned to be safe on a wide variety of formats
(Elsevier, T&F, AGU, Wiley, etc.) but every threshold is exposed at the top
of the file for quick adjustment.
=============================================================================
"""

import re
import os
import sys
from collections import Counter

# =============================================================================
#  CONFIGURATION  — edit these before running
# =============================================================================

INPUT_FILE = r"C:\Users\arsha\OneDrive\Desktop\content.txt"
# The cleaned file is written next to the input with "_cleaned" appended
# to the file name, e.g. "report.txt" -> "report_cleaned.txt".

# --- Mechanism 1: Sequence-style line numbers (LIS) ---
# Detects line numbers as the longest increasing sequence of integers in the
# document.  Works whether the numbers sit at column 1 of every line OR are
# embedded inside long PDF-extracted single-line paragraphs.
REMOVE_LINE_NUMBERS    = True
LINE_NUMBER_VALUE_MAX  = 9999   # ignore integers larger than this (years, DOIs)
LINE_NUMBER_MAX_GAP    = 150    # max accepted gap between consecutive line nos.
                                #   AGU proofs:    25
                                #   Elsevier:      ~150 (long paragraphs eat
                                #                  many numbers between visible
                                #                  ones)
                                #   T&F proofs:    use the dedicated tandf
                                #                  script — they use bare
                                #                  margin numbers, not LIS.
SKIP_LEADING_ZERO_NUMS = True   # skip integers like '0645' (DOI fragments)

# --- Mechanism 2: Soft-hyphen artefacts (U+00AD) ---
# PDF extractors emit U+00AD where a word was hyphenated for line-wrapping.
# At a line boundary we join the two halves with no space ("upper\u00ad\nboundary"
# -> "upperboundary"); mid-line occurrences are simply deleted.
REMOVE_SOFT_HYPHENS    = True

# --- Mechanism 3: Watermark single-letter lines ---
# Diagonal PDF watermarks ("Confidential", "For Peer Review", "Draft") are
# extracted as one isolated letter per line.  Legitimate prose never has a
# lone letter on its own line, so this is safe.
REMOVE_WATERMARK_LINES = True

# --- Mechanism 4: "Page X of Y" markers ---
# Some submission systems stamp a "Page 5 of 47" line at every page boundary.
REMOVE_PAGE_MARKERS    = True

# --- Whitespace / formatting normalisation ---
STRIP_TRAILING_WS      = True   # trim trailing spaces/tabs from every line
STRIP_LEADING_WS       = True   # trim leading spaces/tabs from every line
COLLAPSE_INNER_SPACES  = True   # "in  the  SO" -> "in the SO" (PDF justify fix)
NORMALIZE_BLANK_LINES  = True   # collapse N>=2 blank lines to a single blank

# --- Encoding detection ---
ENCODINGS = ['utf-8', 'utf-8-sig', 'cp1252', 'latin-1']

# =============================================================================
#  IMPLEMENTATION
# =============================================================================


def detect_encoding(filepath, encodings):
    """Return the first encoding that decodes the whole file without error."""
    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                f.read()
            return enc
        except (UnicodeDecodeError, LookupError):
            continue
    return None


# -----------------------------------------------------------------------------
#  Mechanism 1 — line numbers via Longest Increasing Subsequence
# -----------------------------------------------------------------------------

def find_line_number_spans(text, value_max, max_gap, skip_leading_zero):
    """
    Identify the character spans that correspond to sequence-style line
    numbers using a Longest Increasing Subsequence (LIS) over all integer
    candidates.

    Why LIS works
    -------------
    Real line numbers form a long, mostly-monotone sequence in document
    order.  Years, DOI fragments, page numbers, equation numbers, etc. do
    NOT — they're scattered, repeated, and form only short sequences.  By
    asking "what is the longest path through these candidates such that
    each step is a small forward jump?" we naturally isolate the line
    numbers and ignore the rest.

    Parameters
    ----------
    value_max          : ignore any integer > this (filters years/DOIs early)
    max_gap            : the largest tolerated jump between consecutive line
                         numbers in the recovered sequence (figures, tables
                         and long absorbed paragraphs cause natural gaps)
    skip_leading_zero  : skip candidates like '0645' that come from DOI strings

    Returns
    -------
    spans              : list of (start, end) char offsets to delete
    values             : the line-number values found, in order
    """
    # An integer can be considered a line-number candidate ONLY if it stands
    # by itself between whitespace boundaries (or text start/end).  This is
    # what cleanly separates real line numbers ("100  Figure 1", " 44 1.") from
    # the noise that would otherwise sneak in:
    #   * decimals       — the "98" in "R2 = 0.98"   (preceded by '.')
    #                      the "30" in "MAPE = 30.5%" (followed by '.')
    #   * IDs / DOIs     — the "58567" in "ECOLIND-58567" (preceded by '-')
    #   * citation years — the "2015" in "(2015)"        (followed by ')')
    #   * section bullets— the "1" in "1." for Highlights (followed by '.')
    # The lookarounds (?<![\S]) and (?![\S]) succeed at start/end of string
    # and at any whitespace boundary including '\n' and '\t'.
    candidates = []
    for m in re.finditer(r'(?<![\S])\d+(?![\S])', text):
        s = m.group()
        if skip_leading_zero and len(s) > 1 and s[0] == '0':
            continue
        v = int(s)
        if 1 <= v <= value_max:
            candidates.append({'start': m.start(), 'end': m.end(), 'val': v})

    if not candidates:
        return [], []

    n = len(candidates)
    dp     = [1] * n
    parent = [-1] * n

    for i in range(1, n):
        for j in range(i):
            d = candidates[i]['val'] - candidates[j]['val']
            if 0 < d <= max_gap:
                if dp[j] + 1 > dp[i]:
                    dp[i]     = dp[j] + 1
                    parent[i] = j
                # tie-break: prefer the smaller numeric jump
                elif dp[j] + 1 == dp[i] and parent[i] != -1:
                    old_d = candidates[i]['val'] - candidates[parent[i]]['val']
                    if d < old_d:
                        parent[i] = j

    # endpoint of the longest path
    best_end = max(range(n), key=lambda k: dp[k])

    seq = []
    cur = best_end
    while cur != -1:
        seq.append(cur)
        cur = parent[cur]
    seq.reverse()

    spans  = [(candidates[i]['start'], candidates[i]['end']) for i in seq]
    values = [candidates[i]['val'] for i in seq]
    return spans, values


def remove_spans(text, spans):
    """
    Delete each (start, end) span from `text` along with its trailing
    horizontal whitespace.  Processed back-to-front so earlier offsets stay
    valid as later text shrinks.

    We deliberately consume only TRAILING spaces/tabs (not the preceding
    space): when the number is at column 1 of a line the preceding char
    is '\\n' (untouched), and when the number is inline like
    "line 138 denotes", removing "138 " (number + one trailing space)
    leaves the natural "line denotes".
    """
    for start, end in sorted(spans, key=lambda s: s[0], reverse=True):
        e = end
        while e < len(text) and text[e] in (' ', '\t'):
            e += 1
        text = text[:start] + text[e:]
    return text


# -----------------------------------------------------------------------------
#  Mechanism 2 — soft hyphens
# -----------------------------------------------------------------------------

def fix_soft_hyphens(text):
    """
    Two-step rule that mirrors how PDFs actually use U+00AD:

    1. Word-wrap hyphenation only — when the soft hyphen is sandwiched
       between two real word characters with a line break in the middle:
            "upper\\u00ad\\n[ws]boundary"  ->  "upperboundary"
       The lookarounds ensure we DO NOT silently concatenate distinct items
       like "Manuscript Draft-\\u00ad\\nManuscript Number..." (preceded by
       '-', not a word char) which should remain on two lines.

    2. Any soft hyphen still left in the text — mid-line strays or the
       stylistic ones we deliberately skipped in step 1 — is simply removed.
       Line breaks that follow them survive as legitimate breaks.
    """
    text = re.sub(r'(?<=\w)\u00ad[ \t]*\n[ \t]*(?=\w)', '', text)
    text = text.replace('\u00ad', '')
    return text


# -----------------------------------------------------------------------------
#  Mechanism 3/4 — line-level filters
# -----------------------------------------------------------------------------

def is_watermark_line(stripped):
    """A line whose entire content is a single A–Z / a–z character."""
    return bool(re.fullmatch(r'[A-Za-z]', stripped))


def is_page_marker_line(stripped):
    """Lines like 'Page 5 of 47', case-insensitive, full-line only."""
    return bool(re.fullmatch(r'page\s+\d+\s+of\s+\d+', stripped, re.IGNORECASE))


# -----------------------------------------------------------------------------
#  Whitespace + blank-line normalisation
# -----------------------------------------------------------------------------

def normalize_lines(
    text,
    *,
    strip_trailing,
    strip_leading,
    collapse_inner,
    drop_watermark,
    drop_page_markers,
):
    """One linear pass that performs the per-line cleaning steps and the
    line-level filters in a single traversal."""
    counts = {'watermark_chars': 0, 'page_markers': 0}
    out = []
    for line in text.split('\n'):
        if strip_trailing:
            line = line.rstrip(' \t')
        if strip_leading:
            line = line.lstrip(' \t')
        if collapse_inner:
            line = re.sub(r'[ \t]{2,}', ' ', line)

        s = line.strip()
        if drop_watermark and is_watermark_line(s):
            counts['watermark_chars'] += 1
            continue
        if drop_page_markers and is_page_marker_line(s):
            counts['page_markers'] += 1
            continue

        out.append(line)

    return '\n'.join(out), counts


def collapse_blank_runs(text):
    """Collapse any run of >=2 blank lines down to exactly one blank line.
    Also strips leading and trailing blank lines from the document."""
    lines = text.split('\n')

    # strip leading blanks
    while lines and lines[0].strip() == '':
        lines.pop(0)
    # strip trailing blanks
    while lines and lines[-1].strip() == '':
        lines.pop()

    out = []
    prev_blank = False
    removed = 0
    for line in lines:
        blank = (line.strip() == '')
        if blank and prev_blank:
            removed += 1
            continue
        out.append(line)
        prev_blank = blank
    return '\n'.join(out), removed


# =============================================================================
#  Top-level orchestration
# =============================================================================

def clean_document(
    input_file,
    output_file,
    *,
    remove_line_numbers    = REMOVE_LINE_NUMBERS,
    line_number_value_max  = LINE_NUMBER_VALUE_MAX,
    line_number_max_gap    = LINE_NUMBER_MAX_GAP,
    skip_leading_zero_nums = SKIP_LEADING_ZERO_NUMS,
    remove_soft_hyphens    = REMOVE_SOFT_HYPHENS,
    remove_watermark_lines = REMOVE_WATERMARK_LINES,
    remove_page_markers    = REMOVE_PAGE_MARKERS,
    strip_trailing_ws      = STRIP_TRAILING_WS,
    strip_leading_ws       = STRIP_LEADING_WS,
    collapse_inner_spaces  = COLLAPSE_INNER_SPACES,
    normalize_blank_lines  = NORMALIZE_BLANK_LINES,
    encodings              = None,
    verbose                = True,
):
    if encodings is None:
        encodings = ENCODINGS

    # ---- Read ---------------------------------------------------------------
    enc = detect_encoding(input_file, encodings)
    if enc is None:
        sys.exit(f"ERROR: Could not decode {input_file!r} with any of {encodings}")
    with open(input_file, 'r', encoding=enc, errors='replace') as f:
        text = f.read()

    original_chars  = len(text)
    original_lines  = text.count('\n') + (0 if text.endswith('\n') else 1)

    # ---- Normalise newlines -------------------------------------------------
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # ---- 1. Line numbers ----------------------------------------------------
    line_no_spans, line_no_values = [], []
    if remove_line_numbers:
        line_no_spans, line_no_values = find_line_number_spans(
            text,
            value_max         = line_number_value_max,
            max_gap           = line_number_max_gap,
            skip_leading_zero = skip_leading_zero_nums,
        )
        text = remove_spans(text, line_no_spans)

    # ---- 2. Soft hyphens ----------------------------------------------------
    soft_hyphen_count = 0
    if remove_soft_hyphens:
        soft_hyphen_count = text.count('\u00ad')
        text = fix_soft_hyphens(text)

    # ---- 3+4 + per-line cleanup --------------------------------------------
    text, line_filter_counts = normalize_lines(
        text,
        strip_trailing    = strip_trailing_ws,
        strip_leading     = strip_leading_ws,
        collapse_inner    = collapse_inner_spaces,
        drop_watermark    = remove_watermark_lines,
        drop_page_markers = remove_page_markers,
    )

    # ---- Blank-line normalisation ------------------------------------------
    blanks_collapsed = 0
    if normalize_blank_lines:
        text, blanks_collapsed = collapse_blank_runs(text)

    if not text.endswith('\n'):
        text += '\n'

    # ---- Write --------------------------------------------------------------
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(text)

    # ---- Report -------------------------------------------------------------
    if verbose:
        final_lines = text.count('\n')
        bar = '─' * 60
        print(bar)
        print(f"  Input  : {input_file}")
        print(f"  Output : {output_file}")
        print(f"  Encoding detected : {enc!r}")
        print(bar)
        print(f"  Original size           : {original_chars:>7} chars,"
              f" {original_lines:>4} lines")
        print(f"  Line numbers removed    : {len(line_no_values):>7}"
              + (f"   (range {line_no_values[0]} – {line_no_values[-1]})"
                 if line_no_values else ""))
        if line_no_values and len(line_no_values) >= 2:
            gaps = [line_no_values[i+1] - line_no_values[i]
                    for i in range(len(line_no_values) - 1)]
            big = [(line_no_values[i], line_no_values[i+1], gaps[i])
                   for i in range(len(gaps)) if gaps[i] > 5]
            if big:
                preview = ', '.join(f"{a}->{b}(+{g})" for a, b, g in big[:5])
                more = f" ... (+{len(big)-5} more)" if len(big) > 5 else ""
                print(f"    notable gaps in sequence: {preview}{more}")
        print(f"  Soft hyphens removed    : {soft_hyphen_count:>7}")
        print(f"  Watermark letters       : {line_filter_counts['watermark_chars']:>7}")
        print(f"  'Page X of Y' lines     : {line_filter_counts['page_markers']:>7}")
        print(f"  Blank lines collapsed   : {blanks_collapsed:>7}")
        print(bar)
        print(f"  Final size              : {len(text):>7} chars,"
              f" {final_lines:>4} lines")
        print(bar)
        print("  Done.")


# =============================================================================
#  Entry point
# =============================================================================

if __name__ == "__main__":
    base, ext = os.path.splitext(INPUT_FILE)
    output_file = f"{base}_cleaned{ext}"
    clean_document(INPUT_FILE, output_file)