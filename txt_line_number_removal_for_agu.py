import re
import os

# ==========================================
# --- SET YOUR PARAMETERS HERE ---
# ==========================================
INPUT_FILE = r"C:\Users\arsha\OneDrive\Desktop\review_1\4ea0e7b2-225c-4daa-9ab4-26f516cf2796.txt"
LAST_LINE_NUMBER = 1335
# ==========================================

def remove_inline_line_numbers(text, last_line_num, max_missing_tolerance=5):
    """
    Removes embedded line numbers by searching backward from the last_line_num.
    """
    spans_to_remove = []
    current_target = last_line_num
    search_end_idx = len(text)
    
    consecutive_misses = 0
    
    while current_target > 0:
        # \b ensures we match the exact whole number
        pattern = r'\b' + str(current_target) + r'\b'
        
        # Search for occurrences BEFORE our current boundary
        matches = list(re.finditer(pattern, text[:search_end_idx]))
        
        if matches:
            # Grab the LAST occurrence (closest to the previous number)
            best_match = matches[-1]
            spans_to_remove.append(best_match.span())
            
            # Move the boundary back
            search_end_idx = best_match.start()
            consecutive_misses = 0
        else:
            consecutive_misses += 1
            if consecutive_misses > max_missing_tolerance:
                print(f"Stopping search at {current_target}. Assuming beginning of document.")
                break
        
        current_target -= 1

    # Sort spans in reverse order so deleting them doesn't shift the text index
    spans_to_remove.sort(key=lambda x: x[0], reverse=True)
    
    clean_text = text
    for start, end in spans_to_remove:
        clean_text = clean_text[:start] + clean_text[end:]
        
    # Clean up any double spaces left behind by deleted numbers
    clean_text = re.sub(r' {2,}', ' ', clean_text)
    
    return clean_text.strip()

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    
    # 1. Read the raw text from your specific file path
    try:
        # First attempt: standard utf-8
        with open(INPUT_FILE, 'r', encoding='utf-8') as file:
            raw_text = file.read()
    except UnicodeDecodeError:
        # Second attempt: Fallback for PDF conversions with Windows special characters (like smart quotes)
        with open(INPUT_FILE, 'r', encoding='cp1252') as file:
            raw_text = file.read()
    except FileNotFoundError:
        print(f"Error: Could not find the file at {INPUT_FILE}")
        exit()

    print(f"Processing file starting backwards from line {LAST_LINE_NUMBER}...")

    # 2. Run the cleaning function
    # NOTE: The function definition remains exactly the same as before
    cleaned_text = remove_inline_line_numbers(raw_text, LAST_LINE_NUMBER)

    # 3. Save the output to a new file in the same directory
    output_file = INPUT_FILE.replace(".txt", "_cleaned.txt")
    
    # Saving as utf-8 ensures the output is clean and standard
    with open(output_file, 'w', encoding='utf-8', errors='ignore') as file:
        file.write(cleaned_text)
        
    print(f"Done! Cleaned text saved to: {output_file}")