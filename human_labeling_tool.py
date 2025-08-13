import os
import json
import re
import webbrowser
from pathlib import Path
from dialog_simulator import DialogSimulator
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
        browser = webbrowser.get('chrome')
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

def print_synopses(data, short_names):
    """Prints the synopsis for each source file."""
    print("\nFile Synopses:")
    individual_metadata = data.get("metadata", {}).get("individual_metadata", {})
    for i, name in enumerate(short_names):
        synopsis = individual_metadata.get(name, {}).get("synopsis", "No synopsis available.")
        print(f"  {i+1}: {name}")
        print(f"    Synopsis: {synopsis}")
    print("-" * 20)


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
            succ_idx_str = input(f"Enter successor number (1-{len(short_names)}) (or 'q' to go back): ")
            if not succ_idx_str or succ_idx_str.lower() in ['q', 'back']: return
            succ_idx = int(succ_idx_str) - 1
            if not 0 <= succ_idx < len(short_names):
                print("Invalid number.")
                continue

            pred_idx_str = input(f"Enter predecessor numbers (e.g., 1,2,3) (or 'q' to go back): ")
            if not pred_idx_str or pred_idx_str.lower() in ['q', 'back']: return
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
            group_idx_str = input(f"Enter numbers for exclusive group (e.g., 1,2,3) (or 'q' to go back): ")
            if not group_idx_str or group_idx_str.lower() in ['q', 'back']: return
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
            idx_str = input(f"Enter number of {rule_type} rule to delete (or 'q' to go back): ")
            if not idx_str or idx_str.lower() in ['q', 'back']: return
            idx = int(idx_str) - 1
            if 0 <= idx < len(labels[key]):
                del labels[key][idx]
                print(f"{rule_type.capitalize()} rule deleted.")
                break
            else:
                print("Invalid number.")
        except ValueError:
            print("Invalid input. Please use a number.")

def process_file(json_file, file_index, total_files):
    """Main interactive loop for labeling a single JSON file."""
    print("\n" + "="*50)
    print(f"Processing file {file_index + 1} of {total_files}: {json_file}")
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
    labels = data.get("metadata", {}).get("human_labels", {"order": [], "exclusive": []})
    
    if "human_labels" in data.get("metadata", {}):
        print("Existing human labels found.")
        print_labels(labels, short_names)
        return -1

    while True:
        print("\nMenu:")
        print("1. Add ordering rule")
        print("2. Add exclusive group")
        print("3. Delete ordering rule")
        print("4. Delete exclusive group")
        print("5. Show current labels")
        print("f. Show available source files")
        print("p. Show file synopses")
        print("v. View HTML in default browser")
        print("c. View HTML in Chrome (requires local setup)")
        print("t. Traverse this file")
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
        elif choice == 'p':
            print_synopses(data, short_names)
        elif choice == 'v':
            open_html_files_default(html_files)
        elif choice == 'c':
            open_in_chrome(html_files)
        elif choice == 't':
            traverse_file(json_file, source_files)
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


def traverse_file(json_file, source_files):
    """Allows the user to select a source file to traverse using the dialog simulator."""
    print("\nSelect a source file to traverse:")
    for i, src_file in enumerate(source_files, 1):
        print(f"  {i}: {src_file}")
    
    while True:
        try:
            choice_str = input(f"Enter number (1-{len(source_files)}) or 'q' to return: ")
            if not choice_str or choice_str.lower() == 'q':
                return
            
            choice_idx = int(choice_str) - 1
            if not 0 <= choice_idx < len(source_files):
                print("Invalid number.")
                continue
            
            selected_file = source_files[choice_idx]
            
            # Construct the path to the individual JSON file
            relative_dir = Path(json_file).relative_to('output_merged').parent
            target_file = Path('output') / relative_dir / selected_file
            
            if not target_file.exists():
                print(f"Error: Could not find the file: {target_file}")
                print("Please ensure the file exists in the 'output' directory.")
                continue

            print(f"Attempting to run simulator on: {target_file}")
            
            try:
                simulator = DialogSimulator(str(target_file))
                simulator.interactive_mode()
            except Exception as e:
                print(f"Error running dialog simulator: {e}")

            break # Exit loop after successful run or error
            
        except ValueError:
            print("Invalid input. Please use numbers.")

def main():
    """Main function to run the labeling tool."""
    output_dir = 'output_merged'
    json_files = find_json_files(output_dir)

    if not json_files:
        print(f"No JSON files found in '{output_dir}'.")
        return
    
    total_files = len(json_files)
    print(f"Found {total_files} JSON files to process.")

    for i, json_file in enumerate(json_files):
        process_file_return_value = process_file(json_file, i, total_files)
        if process_file_return_value == -1:
            continue
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
