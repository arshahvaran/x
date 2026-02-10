import os
import re
import sys

# ——— USER PARAMETERS ———
# 1) Path to your input text file:
input_file_path = r"C:\Users\arsha\Desktop\ENVSOFT-D-25-01040_reviewer.txt"
# 2) How many spaces follow each line-number:
spaces_count = 2
# 3) List of encodings to try, in order:
encodings_to_try = ['utf-8', 'utf-8-sig', 'cp1252', 'latin-1']
# ————————————————————

# Derive output path
base, ext = os.path.splitext(input_file_path)
output_file_path = f"{base}_no_line_number{ext}"

# Compile regex to strip: start‑of‑line, digits, then exactly spaces_count spaces
pattern = re.compile(rf'^\d+\s{{{spaces_count}}}')

# Find a working encoding
for enc in encodings_to_try:
    try:
        # Try opening just to check if encoding works
        with open(input_file_path, 'r', encoding=enc) as f:
            f.readline()
        chosen_encoding = enc
        break
    except UnicodeDecodeError:
        continue
else:
    print("Error: could not decode file with any of the fallback encodings.", file=sys.stderr)
    sys.exit(1)

print(f"Using encoding: {chosen_encoding!r}")

# Process and write out
with open(input_file_path,  'r', encoding=chosen_encoding, errors='replace') as infile, \
     open(output_file_path, 'w', encoding='utf-8') as outfile:
    for line in infile:
        # strip leading "123   " (digits + spaces_count spaces)
        cleaned = pattern.sub('', line)
        outfile.write(cleaned)

print(f"\n✔ Stripped line numbers. Output saved to:\n  {output_file_path}")
