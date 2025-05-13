import json
from pathlib import Path

def find_json_files(root_dir: Path) -> list[str]:
    """Finds all JSON files recursively in a directory."""
    return [str(p) for p in root_dir.rglob('*.json')]

def main():
    output_dir = Path('output')
    all_json_files = find_json_files(output_dir)
    output_filename = 'all_sessions.json'

    try:
        with open(output_filename, 'w') as f:
            json.dump(all_json_files, f, indent=4)
        print(f"Successfully saved {len(all_json_files)} file paths to {output_filename}")
    except IOError as e:
        print(f"Error writing to {output_filename}: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main() 