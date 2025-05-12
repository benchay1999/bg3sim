import json
import os

def get_flags_from_node(node, flags_set):
    """Recursively extracts flags from a single node and its children."""
    if isinstance(node, dict):
        if "setflags" in node and isinstance(node["setflags"], list):
            for flag in node["setflags"]:
                flags_set.add(flag.strip())
        if "checkflags" in node and isinstance(node["checkflags"], list):
            for flag in node["checkflags"]:
                flag_cleaned = flag.strip().split('=')[0].strip()
                if flag_cleaned:
                    flags_set.add(flag_cleaned)

        if "children" in node and isinstance(node["children"], dict):
            for child_node in node["children"].values():
                get_flags_from_node(child_node, flags_set)

def parse_dialogue_flags(file_path):
    """Parses the dialogue data from a JSON file and extracts all unique flags."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
        return set()
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {file_path}")
        return set()
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return set()

    unique_flags = set()

    if "dialogue" in data and isinstance(data["dialogue"], dict):
        for node_id, node_content in data["dialogue"].items():
            get_flags_from_node(node_content, unique_flags)

    return unique_flags

if __name__ == "__main__":
    output_dir = "output/"
    all_files_flags = {}

    if not os.path.isdir(output_dir):
        print(f"Error: Directory '{output_dir}' not found.")
    else:
        for root, dirs, files in os.walk(output_dir):
            for filename in files:
                if filename.endswith(".json"):
                    full_path = os.path.join(root, filename)
                    relative_path = os.path.relpath(full_path, '.')
                    print(f"Processing: {relative_path}")
                    flags_in_file = parse_dialogue_flags(full_path)
                    if flags_in_file:
                        all_files_flags[relative_path] = sorted(list(flags_in_file))

        if all_files_flags:
            print("\n--- All Flags Found ---")
            print(json.dumps(all_files_flags, indent=2))
            with open("all_flags.json", "w", encoding="utf-8") as f:
                json.dump(all_files_flags, f, indent=2, ensure_ascii=False)
        else:
            print(f"No JSON files with flags found in '{output_dir}' or errors occurred.")
