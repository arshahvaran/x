import re
import os

# ==========================================
# --- SET YOUR PARAMETERS HERE ---
# ==========================================
INPUT_FILE = r"C:\Users\arsha\OneDrive\Desktop\content.txt"
LAST_LINE_NUMBER = 995
MAX_GAP = 25  # Maximum expected missing consecutive line numbers (e.g., due to figures/tables)
# ==========================================

def remove_line_numbers_dp(text: str, max_line_number: int, max_gap: int) -> str:
    """
    Removes sequence-based line numbers from a document using Dynamic Programming 
    to find the Longest Increasing Subsequence (LIS) of numeric candidates.
    """
    # 1. Extract all numeric candidates <= the max line number
    # \b ensures we get distinct integers, even if attached to soft hyphens
    pattern = r'\b\d+\b'
    candidates = []
    for match in re.finditer(pattern, text):
        val = int(match.group())
        if 1 <= val <= max_line_number:
            candidates.append({
                'start': match.start(),
                'end': match.end(),
                'val': val
            })
    
    if not candidates:
        print("No numeric candidates found in the document.")
        return text
        
    n = len(candidates)
    dp = [1] * n
    parent = [-1] * n
    
    # 2. Dynamic Programming to map the optimal sequence path
    for i in range(1, n):
        for j in range(i):
            val_diff = candidates[i]['val'] - candidates[j]['val']
            
            # Valid connection: Strictly increasing, but within the expected gap tolerance
            if 0 < val_diff <= max_gap:
                if dp[j] + 1 > dp[i]:
                    dp[i] = dp[j] + 1
                    parent[i] = j
                # Tie-breaker: If sequence lengths are equal, prefer the one with the smaller numerical gap
                elif dp[j] + 1 == dp[i]:
                    old_val_diff = candidates[i]['val'] - candidates[parent[i]]['val']
                    if val_diff < old_val_diff:
                        parent[i] = j

    # 3. Find the endpoint of the longest valid sequence
    max_len = 0
    best_end = -1
    for i in range(n):
        if dp[i] > max_len:
            max_len = dp[i]
            best_end = i
            
    # 4. Reconstruct the sequence mathematically
    seq_indices = []
    curr = best_end
    while curr != -1:
        seq_indices.append(curr)
        curr = parent[curr]
        
    seq_indices.reverse()
    
    identified_numbers = [candidates[idx]['val'] for idx in seq_indices]
    
    # --- QA/QC Built-in Checks ---
    print("\n--- QA/QC Report ---")
    print(f"Total line numbers identified and flagged for removal: {len(identified_numbers)}")
    print(f"Sequence span: {identified_numbers[0]} to {identified_numbers[-1]}")
    
    if identified_numbers[-1] < max_line_number * 0.9:
        print(f"WARNING: Sequence ended at {identified_numbers[-1]}, which is significantly lower than your target of {max_line_number}.")
        
    missing = []
    for k in range(1, len(identified_numbers)):
        if identified_numbers[k] - identified_numbers[k-1] > 1:
            missing.extend(list(range(identified_numbers[k-1] + 1, identified_numbers[k])))
    if missing:
        print(f"Note: {len(missing)} line numbers were skipped/missing in the sequence (likely obscured by figures or poor PDF extraction).")
    print("--------------------\n")

    # 5. Remove the identified numbers safely
    # We delete from back to front so character indices don't shift during processing
    spans_to_remove = [(candidates[idx]['start'], candidates[idx]['end']) for idx in seq_indices]
    spans_to_remove.sort(key=lambda x: x[0], reverse=True)
    
    clean_text = text
    for start, end in spans_to_remove:
        remove_start = start
        remove_end = end
        
        # Context-aware space removal:
        # Prevent leaving behind double spaces if the number was surrounded by spaces
        if remove_end < len(clean_text) and clean_text[remove_end] in (' ', '\t'):
            remove_end += 1
        elif remove_start > 0 and clean_text[remove_start - 1] in (' ', '\t'):
            remove_start -= 1
            
        clean_text = clean_text[:remove_start] + clean_text[remove_end:]
        
    return clean_text

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    
    try:
        with open(INPUT_FILE, 'r', encoding='utf-8') as file:
            raw_text = file.read()
    except UnicodeDecodeError:
        with open(INPUT_FILE, 'r', encoding='cp1252') as file:
            raw_text = file.read()
    except FileNotFoundError:
        print(f"Error: Could not find the file at {INPUT_FILE}")
        exit()

    print(f"Processing file to extract line sequence up to {LAST_LINE_NUMBER}...")

    cleaned_text = remove_line_numbers_dp(raw_text, LAST_LINE_NUMBER, MAX_GAP)

    output_file = INPUT_FILE.replace(".txt", "_cleaned.txt")
    
    with open(output_file, 'w', encoding='utf-8', errors='ignore') as file:
        file.write(cleaned_text)
        
    print(f"Done! Cleaned text saved to: {output_file}")
