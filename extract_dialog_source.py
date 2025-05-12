import os
import re
import json

def extract_dialog_resources_with_filenames():
    goals_dir = "RawFiles/Goals/"
    all_dialog_entries = [] # Use a list to store dictionaries

    # Regex to find (DIALOGRESOURCE) followed by the resource name.
    # The resource name consists of alphanumeric characters, underscores, and hyphens.
    regex = r"\(DIALOGRESOURCE\)([a-zA-Z0-9_-]+)"

    if not os.path.isdir(goals_dir):
        print(f"Error: Directory '{goals_dir}' not found.")
        return

    for filename in os.listdir(goals_dir):
        if filename.endswith(".txt"):
            filepath = os.path.join(goals_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    matches = re.findall(regex, content)
                    for entity_name in matches:
                        all_dialog_entries.append({
                            "entity": entity_name,
                            "filename": filename
                        })
            except Exception as e:
                print(f"Error processing file {filepath}: {e}")

    output_filename = "dialog_resources_with_filenames.json"
    try:
        with open(output_filename, 'w', encoding='utf-8') as outfile:
            json.dump(all_dialog_entries, outfile, indent=4)
        print(f"Successfully extracted {len(all_dialog_entries)} dialog resource entries to {output_filename}")
    except Exception as e:
        print(f"Error writing to JSON file {output_filename}: {e}")

if __name__ == "__main__":
    extract_dialog_resources_with_filenames()