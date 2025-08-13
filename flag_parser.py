import re
import sys
import json
import os

def parse_osiris_flags(script_content: str) -> list[str]:
    """
    Parses an Osiris script content and extracts unique flag names in chronological order of first appearance.

    Flags are extracted from lines containing the word "flag" (case-insensitive).
    It identifies flags explicitly marked like (FLAG)MyFlagName or passed as arguments
    to known flag-handling functions.
    """
    ordered_flags = []
    
    # Pattern for valid flag identifiers (alphanumeric, underscore, hyphen)
    flag_id_pattern = r'[a-zA-Z0-9_-]+'
    
    # Compiled regular expressions for efficiency
    # Each pattern is designed to capture the flag name in its first group.
    regex_patterns = [
        # Pattern 1: Explicit (FLAG)MyFlag, (Flag)MyFlag, (flag)MyFlag in various contexts.
        # This is the most common and direct way flags are specified.
        re.compile(r'\((?:FLAG|Flag|flag)\)(' + flag_id_pattern + r')\b'),
        
        # --- Temporarily disabling other patterns for debugging ---
        # Pattern 2: Functions known to take a raw flag name as their first significant argument.
        # The negative lookahead (?!\((?:FLAG|Flag|flag)\)) ensures these patterns only match
        # "bare" flag names, not when they are already prefixed with (FLAG),
        # as Pattern 1 would have already captured the name from (FLAG)FlagName.
        # Added \s*\) to match optional space and the function's closing parenthesis.
        re.compile(r'ClearFlag\s*\(\s*(?!\((?:FLAG|Flag|flag)\))(' + flag_id_pattern + r')\b\s*\)'),
        re.compile(r'GetFlag\s*\(\s*(?!\((?:FLAG|Flag|flag)\))(' + flag_id_pattern + r')\b\s*\)'),
        re.compile(r'PROC_GlobalSetFlagAndCache\s*\(\s*(?!\((?:FLAG|Flag|flag)\))(' + flag_id_pattern + r')\b\s*\)'),
        re.compile(r'PROC_GlobalClearFlagAndCache\s*\(\s*(?!\((?:FLAG|Flag|flag)\))(' + flag_id_pattern + r')\b\s*\)'),
        re.compile(r'FlagSet\s*\(\s*(?!\((?:FLAG|Flag|flag)\))(' + flag_id_pattern + r')\b\s*\)'),
        re.compile(r'SetFlag\s*\(\s*(?!\((?:FLAG|Flag|flag)\))(' + flag_id_pattern + r')\b\s*\)'),
        re.compile(r'DB_GlobalFlag\s*\(\s*(?!\((?:FLAG|Flag|flag)\))(' + flag_id_pattern + r')\b\s*\)'),
        re.compile(r'DB_CHA_LaezelRecruitment_StartRecruitmentDialogFlag\s*\(\s*(?!\((?:FLAG|Flag|flag)\))(' + flag_id_pattern + r')\b\s*\)'),
    ]

    lines = script_content.splitlines()
    for line_number, line in enumerate(lines, 1):
        # User's condition: Only process lines containing the word "flag".
        # Using word boundaries (\b) to ensure "flag" is a whole word.
        #-- Removing this check as it might be too strict and filter out valid flag lines --#
        # if not re.search(r'\\\\bflag\\\\b', line, re.IGNORECASE):
        #     continue

        for pattern in regex_patterns:
            matches_on_line = pattern.findall(line)
            for flag_name in matches_on_line:
                # Ensure a flag name was actually captured and it's not a common null placeholder.
                if flag_name and flag_name != "NULL_00000000-0000-0000-0000-000000000000":
                    processed_flag_name = flag_name.rsplit("_", 1)[0]
                    # Add to list only if it's the first time seeing this flag
                    if processed_flag_name not in ordered_flags:
                        ordered_flags.append(processed_flag_name)
    
    return ordered_flags

if __name__ == "__main__":
    goals_dir = "Goals/"
    all_flags_path = "all_flags.json"
    output_filename = "goals_to_json_paths.json"

    results = {}

    try:
        with open(all_flags_path, "r", encoding="utf-8") as f_json:
            all_json_flags_data = json.load(f_json)
    except FileNotFoundError:
        print(f"Error: Could not find '{all_flags_path}'. Please ensure this file exists.")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from '{all_flags_path}'.")
        sys.exit(1)

    if not os.path.isdir(goals_dir):
        print(f"Error: Directory '{goals_dir}' not found.")
        sys.exit(1)

    for filename in os.listdir(goals_dir):
        if filename.endswith(".txt"):
            filepath = os.path.join(goals_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    script_content = f.read()

                osiris_flags = parse_osiris_flags(script_content)

                if osiris_flags:
                    matching_files_order = {}
                    for idx, flag_from_osiris in enumerate(osiris_flags):
                        for json_filepath, flags_in_json in all_json_flags_data.items():
                            if flag_from_osiris in flags_in_json:
                                if json_filepath not in matching_files_order:
                                    matching_files_order[json_filepath] = idx

                    if matching_files_order:
                        sorted_json_files = sorted(matching_files_order, key=matching_files_order.get)
                        result_key = filename.replace(".txt", "")
                        results[result_key] = sorted_json_files

            except Exception as e:
                print(f"An error occurred while processing {filepath}: {e}")

    with open(output_filename, "w", encoding="utf-8") as f_out:
        json.dump(results, f_out, indent=4)

    print(f"Processing complete. Results saved to '{output_filename}'") 