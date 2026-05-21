import os
import csv
from datetime import datetime

# ============================================================
# CONFIG - EDIT THESE
# ============================================================
TARGET_DIR = r"E:\publications\bhaleka_3\data\2026-04-06\processed_2_random_validation\downloaded_papers"

# Max filename length INCLUDING the .pdf extension.
# 100 chars is descriptive but safe for any zip recipient.
MAX_FILENAME_LENGTH = 60

# When trimming, prefer to cut at a space (word boundary) within this
# many chars before the hard cutoff. Prevents mid-word cuts.
WORD_BOUNDARY_LOOKBACK = 15

# DRY_RUN = True  -> only preview, NO files touched
# DRY_RUN = False -> actually perform the renames
DRY_RUN = False

# Where to save the rename log (so renames are reversible)
LOG_CSV = r"E:\publications\bhaleka_3\data\2026-04-06\processed_2_random_validation\rename_log.csv"

# ============================================================
# HELPERS
# ============================================================
def trim_filename(original_name, max_length):
    """Trim filename to max_length chars (incl ext), preferring word boundary."""
    if len(original_name) <= max_length:
        return original_name

    base, ext = os.path.splitext(original_name)
    max_base = max_length - len(ext)

    # Hard cut at max_base
    trimmed_base = base[:max_base]

    # Try to back up to a space within WORD_BOUNDARY_LOOKBACK chars
    space_pos = trimmed_base.rfind(' ')
    if space_pos != -1 and (len(trimmed_base) - space_pos) <= WORD_BOUNDARY_LOOKBACK:
        trimmed_base = trimmed_base[:space_pos]

    # Clean up trailing punctuation/whitespace that would look weird
    trimmed_base = trimmed_base.rstrip(' .,;:-—–_(')

    return trimmed_base + ext


def make_unique(target_name, taken_names, max_length):
    """If target_name already taken, append _2, _3, ... before extension."""
    if target_name not in taken_names:
        return target_name

    base, ext = os.path.splitext(target_name)
    counter = 2
    while counter < 1000:
        suffix = f"_{counter}"
        max_base = max_length - len(ext) - len(suffix)
        candidate_base = base[:max_base].rstrip(' .,;:-—–_(')
        candidate = candidate_base + suffix + ext
        if candidate not in taken_names:
            return candidate
        counter += 1
    raise RuntimeError(f"Could not generate unique name for {target_name}")


# ============================================================
# START
# ============================================================
print("=" * 80)
print("PDF FILENAME RENAME TOOL")
print("=" * 80)
print(f"Mode: {'*** DRY RUN *** (no files will be touched)' if DRY_RUN else '!!! LIVE - FILES WILL BE RENAMED !!!'}")
print(f"Target directory:     {TARGET_DIR}")
print(f"Max filename length:  {MAX_FILENAME_LENGTH} chars (including .pdf)")
print(f"Word boundary lookback: {WORD_BOUNDARY_LOOKBACK} chars")
print(f"Log file:             {LOG_CSV}")
print("=" * 80)
print()

if not os.path.isdir(TARGET_DIR):
    print(f"ERROR: directory does not exist: {TARGET_DIR}")
    raise SystemExit(1)

# ============================================================
# SCAN
# ============================================================
print("Scanning directory...")
all_files = sorted([
    f for f in os.listdir(TARGET_DIR)
    if os.path.isfile(os.path.join(TARGET_DIR, f))
])
print(f"Total files found: {len(all_files)}")
print()

# ============================================================
# PARTITION
# ============================================================
untouched = [f for f in all_files if len(f) <= MAX_FILENAME_LENGTH]
needs_rename = [f for f in all_files if len(f) > MAX_FILENAME_LENGTH]

print(f"Files already within {MAX_FILENAME_LENGTH} chars (will NOT be touched): {len(untouched)}")
print(f"Files OVER {MAX_FILENAME_LENGTH} chars (will be trimmed):              {len(needs_rename)}")
print()

# ============================================================
# BUILD RENAME PLAN
# ============================================================
print("-" * 80)
print("BUILDING RENAME PLAN")
print("-" * 80)

taken_names = set(untouched)  # already-claimed names
rename_plan = []  # list of (old_name, new_name)

# Process longest-first so the most-trimmed files get first dibs on clean names
for old in sorted(needs_rename, key=lambda x: -len(x)):
    proposed = trim_filename(old, MAX_FILENAME_LENGTH)
    final = make_unique(proposed, taken_names, MAX_FILENAME_LENGTH)
    taken_names.add(final)
    rename_plan.append((old, final))

# ============================================================
# PRINT PLAN
# ============================================================
print()
print("-" * 80)
print("RENAME PLAN (preview)")
print("-" * 80)
for i, (old, new) in enumerate(rename_plan, 1):
    saved = len(old) - len(new)
    print(f"#{i:>3}  {len(old):>3} -> {len(new):>3} chars  (saved {saved})")
    print(f"      OLD: {old}")
    print(f"      NEW: {new}")
    print()

# ============================================================
# SANITY CHECKS
# ============================================================
print("-" * 80)
print("SANITY CHECKS")
print("-" * 80)
final_all_names = set(untouched) | {new for _, new in rename_plan}
print(f"  Total files after rename:        {len(untouched) + len(rename_plan)}")
print(f"  Unique final names:              {len(final_all_names)}")
print(f"  No collisions:                   {len(final_all_names) == len(untouched) + len(rename_plan)}")
new_lengths = [len(new) for _, new in rename_plan]
if new_lengths:
    print(f"  New filename length range:       {min(new_lengths)} - {max(new_lengths)} chars")
    print(f"  All new names within limit:      {max(new_lengths) <= MAX_FILENAME_LENGTH}")
print()

# ============================================================
# EXECUTE (or skip)
# ============================================================
if DRY_RUN:
    print("=" * 80)
    print("DRY RUN - nothing was renamed.")
    print("Review the plan above. If it looks good, set DRY_RUN = False and run again.")
    print("=" * 80)
else:
    print("=" * 80)
    print("EXECUTING RENAMES")
    print("=" * 80)

    # Write CSV log FIRST (before any rename, so we always have the mapping)
    os.makedirs(os.path.dirname(LOG_CSV), exist_ok=True)
    with open(LOG_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['timestamp', 'old_name', 'new_name', 'old_length', 'new_length'])
        ts = datetime.now().isoformat()
        for old, new in rename_plan:
            writer.writerow([ts, old, new, len(old), len(new)])
    print(f"Log saved: {LOG_CSV}")
    print()

    success = 0
    failed = []
    for i, (old, new) in enumerate(rename_plan, 1):
        old_path = os.path.join(TARGET_DIR, old)
        new_path = os.path.join(TARGET_DIR, new)
        try:
            os.rename(old_path, new_path)
            success += 1
            print(f"  [{i:>3}/{len(rename_plan)}] OK")
        except Exception as e:
            failed.append((old, new, str(e)))
            print(f"  [{i:>3}/{len(rename_plan)}] FAIL: {e}")
            print(f"        OLD: {old}")
            print(f"        NEW: {new}")

    print()
    print("=" * 80)
    print(f"DONE. Renamed: {success}  |  Failed: {len(failed)}")
    print("=" * 80)
    if failed:
        print("Failures:")
        for old, new, err in failed:
            print(f"  {err}")
            print(f"    {old} -> {new}")