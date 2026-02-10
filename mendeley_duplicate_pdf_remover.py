import os

# Directory containing your PDF files.
directory = r"C:\Users\alire\OneDrive\Desktop\lake_ontario"
extension = ".pdf"  # we're working with PDF files

# List all PDF files in the directory.
files = [f for f in os.listdir(directory) if f.lower().endswith(extension.lower())]

# Group files by their "base key" (filename without extension and with last 20 characters removed)
groups = {}
for filename in files:
    base, ext = os.path.splitext(filename)
    # Remove the last 20 characters (if the base name is long enough)
    key = base[:-20] if len(base) > 20 else base
    groups.setdefault(key, []).append(filename)

# Process each group: if more than one file share the same key, keep one and delete the rest.
for key, file_list in groups.items():
    if len(file_list) > 1:
        print(f"Found duplicates for key:\n  {key}\nFiles: {file_list}")
        file_to_keep = file_list[0]  # Choose the first file to keep.
        print(f"Keeping: {file_to_keep}")
        # Delete the rest of the files.
        for file_to_delete in file_list[1:]:
            file_path = os.path.join(directory, file_to_delete)
            try:
                os.remove(file_path)
                print(f"Deleted: {file_to_delete}")
            except Exception as e:
                print(f"Error deleting {file_to_delete}: {e}")
    else:
        # No duplicates for this key.
        print(f"Unique file for key '{key}': {file_list[0]}")
