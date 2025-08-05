import os
import json
import re
import webbrowser
from pathlib import Path

def find_json_files(root_dir):
    """Find all JSON files in a directory and its subdirectories."""
    json_files = []
    if not os.path.isdir(root_dir):
        print(f"Error: Directory '{root_dir}' not found.")
        return json_files
    for root, _, files in os.walk(root_dir):
        for file in files:
            if file.endswith('.json'):
                json_files.append(os.path.join(root, file))
    return sorted(json_files)

def get_short_name(filename, prefix):
    """Generate a short name from a filename by removing prefix and extension."""
    if filename.lower().startswith(prefix.lower()):
        base_name = filename[len(prefix):]
    else:
        base_name = filename
    return os.path.splitext(base_name)[0]

def get_prefix_from_filename(json_file_path):
    """Derive the source file prefix from the JSON file's name."""
    file_name = os.path.basename(json_file_path)
    base_name = os.path.splitext(file_name)[0]
    
    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    source_files = data.get("metadata", {}).get("source_files")
    
    if not source_files or len(source_files) < 2:
        parts = base_name.split('_')
        prefix = "".join([p.capitalize() for p in parts]) + '_'
        return prefix

    common_prefix = os.path.commonprefix(source_files)
    
    if '_' in common_prefix:
        return common_prefix.rsplit('_', 1)[0] + '_'
    
    if common_prefix:
        return common_prefix

    parts = base_name.split('_')
    prefix = "".join([p.capitalize() for p in parts]) + '_'
    return prefix

def find_html_files(source_files, json_file_path, prefix):
    """Find the corresponding HTML files for the given source files."""
    html_files = []
    dialog_dir = Path("data/Dialogs")
    json_path = Path(json_file_path)
    try:
        relative_path = json_path.relative_to("output_merged")
        search_dir = dialog_dir / relative_path.parent
    except ValueError:
        search_dir = dialog_dir

    if not search_dir.is_dir():
        print(f"Warning: Could not find corresponding dialog directory: {search_dir}")
        return []

    all_html_files = {f.name.lower(): f for f in search_dir.glob('*.html')}
    
    for source_file in source_files:
        base_source_name = os.path.splitext(source_file)[0]
        potential_name = f"{base_source_name}.html"
        
        if potential_name.lower() in all_html_files:
            html_files.append(all_html_files[potential_name.lower()])
            continue

        target_html_name = f"{os.path.splitext(source_file)[0]}.html".lower()

        if target_html_name in all_html_files:
             html_files.append(all_html_files[target_html_name])
        else:
            print(f"Could not find HTML file for: {source_file}")

    return html_files

def open_html_files_default(html_files):
    """Opens a list of HTML files in the default web browser."""
    if not html_files:
        print("No HTML files to open.")
        return
    
    for html_file in html_files:
        try:
            abs_path = html_file.resolve()
            webbrowser.open(abs_path.as_uri())
            print(f"Opened {abs_path} in default browser.")
        except Exception as e:
            print(f"Error opening {html_file}: {e}")

def open_in_chrome(html_files):
    """Attempts to open a list of HTML files in Google Chrome."""
    if not html_files:
        print("No HTML files to open.")
        return

    try:
        browser = webbrowser.get('google-chrome')
    except webbrowser.Error:
        print("Could not find Google Chrome. Ensure it's installed and in your PATH.")
        print("Alternatively, your environment may not support remote browser opening.")
        return

    for html_file in html_files:
        try:
            abs_path = html_file.resolve()
            browser.open(abs_path.as_uri())
            print(f"Attempting to open {abs_path} in Google Chrome.")
        except Exception as e:
            print(f"Error opening {html_file} in Chrome: {e}")

def print_labels(labels, short_names):
    """Prints the current labels."""
    print("\nCurrent ordering rules:")
    if not labels["order"]:
        print("  None")
    else:
        for i, rule in enumerate(labels["order"]):
            predecessors = ", ".join(rule["predecessor"])
            print(f"  {i+1}: [{predecessors}] -> {rule['successor']}")

    print("\nCurrent exclusive groups:")
    if not labels["exclusive"]:
        print("  None")
    else:
        for i, group in enumerate(labels["exclusive"]):
            print(f"  {i+1}: [{', '.join(group)}]")
    print("-" * 20)

def show_source_files(short_names):
    """Prints the available source files."""
    print("\nAvailable source files:")
    for i, name in enumerate(short_names):
        print(f"  {i+1}: {name}")
    print("-" * 20)

def add_ordering_rule(labels, short_names):
    """Adds a new ordering rule."""
    while True:
        try:
            succ_idx_str = input(f"Enter successor number (1-{len(short_names)}): ")
            if not succ_idx_str: return
            succ_idx = int(succ_idx_str) - 1
            if not 0 <= succ_idx < len(short_names):
                print("Invalid number.")
                continue

            pred_idx_str = input(f"Enter predecessor numbers (e.g., 1,2,3): ")
            if not pred_idx_str: return
            pred_indices = [int(x.strip()) - 1 for x in pred_idx_str.split(',')]
            
            if any(not (0 <= i < len(short_names)) for i in pred_indices):
                print("Invalid number in predecessors.")
                continue

            successor = short_names[succ_idx]
            predecessors = [short_names[i] for i in pred_indices]
            
            if successor in predecessors:
                print("Successor cannot be in its own predecessors.")
                continue

            labels["order"].append({"predecessor": predecessors, "successor": successor})
            print("Rule added.")
            break
        except ValueError:
            print("Invalid input. Please use numbers.")

def add_exclusive_group(labels, short_names):
    """Adds a new exclusive group."""
    while True:
        try:
            group_idx_str = input(f"Enter numbers for exclusive group (e.g., 1,2,3): ")
            if not group_idx_str: return
            group_indices = [int(x.strip()) - 1 for x in group_idx_str.split(',')]

            if any(not (0 <= i < len(short_names)) for i in group_indices):
                print("Invalid number in group.")
                continue
            
            if len(group_indices) < 2:
                print("Exclusive group must contain at least 2 files.")
                continue

            group = [short_names[i] for i in group_indices]
            labels["exclusive"].append(group)
            print("Group added.")
            break
        except ValueError:
            print("Invalid input. Please use numbers.")

def delete_rule(labels, rule_type):
    """Deletes an ordering rule or exclusive group."""
    key = "order" if rule_type == "ordering" else "exclusive"
    if not labels[key]:
        print(f"No {rule_type} rules to delete.")
        return

    while True:
        try:
            idx_str = input(f"Enter number of {rule_type} rule to delete: ")
            if not idx_str: return
            idx = int(idx_str) - 1
            if 0 <= idx < len(labels[key]):
                del labels[key][idx]
                print(f"{rule_type.capitalize()} rule deleted.")
                break
            else:
                print("Invalid number.")
        except ValueError:
            print("Invalid input. Please use a number.")

def process_file(json_file):
    """Main interactive loop for labeling a single JSON file."""
    print("\n" + "="*50)
    print(f"Processing: {json_file}")
    print("="*50)

    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error reading {json_file}: {e}")
        return

    source_files = data.get("metadata", {}).get("source_files")
    if not source_files:
        print("No 'source_files' found in this file. Skipping.")
        return

    prefix = get_prefix_from_filename(json_file)
    short_names = [get_short_name(f, prefix) for f in source_files]
    html_files = find_html_files(source_files, json_file, prefix)

    show_source_files(short_names)

    labels = data.get("human_labels", {"order": [], "exclusive": []})
    
    if "human_labels" in data:
        print("Existing human labels found.")
        print_labels(labels, short_names)

    while True:
        print("\nMenu:")
        print("1. Add ordering rule")
        print("2. Add exclusive group")
        print("3. Delete ordering rule")
        print("4. Delete exclusive group")
        print("5. Show current labels")
        print("f. Show available source files")
        print("v. View HTML in default browser")
        print("c. View HTML in Chrome (requires local setup)")
        print("s. Save and continue to next file")
        print("q. Quit without saving")

        choice = input("Enter your choice: ").lower()

        if choice == '1':
            add_ordering_rule(labels, short_names)
        elif choice == '2':
            add_exclusive_group(labels, short_names)
        elif choice == '3':
            delete_rule(labels, "ordering")
        elif choice == '4':
            delete_rule(labels, "exclusive")
        elif choice == '5':
            print_labels(labels, short_names)
        elif choice == 'f':
            show_source_files(short_names)
        elif choice == 'v':
            open_html_files_default(html_files)
        elif choice == 'c':
            open_in_chrome(html_files)
        elif choice == 's':
            if "metadata" not in data:
                data["metadata"] = {}
            data["metadata"]["human_labels"] = labels
            try:
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)
                print(f"Labels saved to {json_file}")
            except IOError as e:
                print(f"Error saving file: {e}")
            break
        elif choice == 'q':
            print("Skipping file, no changes saved.")
            break
        else:
            print("Invalid choice. Please try again.")


def main():
    """Main function to run the labeling tool."""
    output_dir = 'output_merged'
    json_files = find_json_files(output_dir)

    if not json_files:
        print(f"No JSON files found in '{output_dir}'.")
        return
    
    print(f"Found {len(json_files)} JSON files to process.")

    for json_file in json_files:
        process_file(json_file)
        
        while True:
            cont = input("\nProceed to next file? (y/n) or 'q' to quit: ").lower()
            if cont in ['y', 'yes', '']:
                break
            elif cont in ['n', 'no', 'q', 'quit']:
                print("Exiting tool.")
                return
        
    print("\nAll files processed.")

if __name__ == "__main__":
    main()
