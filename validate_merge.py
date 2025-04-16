import os
import json
import sys

# --- Copied from merge_dialogues.py for consistent parsing ---
def extract_parts_from_filename(filename):
    """
    Extracts the acronym, scenario, and suffix from a JSON filename.
    Example: FOR_ApothecaryGoblins_AD_Boss.json -> ('FOR', 'ApothecaryGoblins', 'AD_Boss')
    Example: QST_FindMol_AD_TieflingKids.json -> ('QST', 'FindMol', 'AD_TieflingKids')
    Example: DEN_DenOfSevenBones_PAD_MeetingEnverGortash.json -> ('DEN', 'DenOfSevenBones', 'PAD_MeetingEnverGortash')
    
    This function preserves the original case of each part.
    
    Returns None if the pattern doesn't match.
    """
    base_name = os.path.splitext(filename)[0]
    
    # Special case handling for known problematic files with LaeZel vs Laezel
    if "LaeZel" in base_name or "Laezel" in base_name:
        # Normalize to Laezel for all LaeZel variants
        normalized_name = base_name.replace("LaeZel", "Laezel")
        parts = normalized_name.split('_', 2) # Split into max 3 parts
    else:
        parts = base_name.split('_', 2) # Split into max 3 parts
    
    if len(parts) == 3:
        acronym, scenario, suffix = parts
        if acronym and scenario and suffix: # Ensure all parts are non-empty
            return acronym, scenario, suffix
    elif len(parts) == 2:
         acronym, scenario = parts
         if acronym and scenario:
             return acronym, scenario, "" # Return empty string for suffix

    # Return None if parsing failed for validation purposes
    return None, None, None
# --- End of copied function ---

def validate_merge(original_dir="output", merged_dir="output_merged"):
    """
    Validates the merge process by comparing original files and merged file contents.
    """
    print(f"""Starting validation...
Original directory: {original_dir}
Merged directory:   {merged_dir}\n""")

    original_files = set()
    unparseable_original_files = []
    errors = []

    # 1. Scan original directory
    print(f"Scanning original directory '{original_dir}'...")
    if not os.path.isdir(original_dir):
        print(f"ERROR: Original directory '{original_dir}' not found.")
        return False

    for dirpath, _, filenames in os.walk(original_dir):
        for filename in filenames:
            if filename.endswith('.json'):
                relative_dir = os.path.relpath(dirpath, original_dir)
                # Handle root case where relative_dir is '.'
                relative_path = os.path.join(relative_dir, filename) if relative_dir != '.' else filename
                original_files.add(relative_path)
                # Check if original filename itself is parseable
                o_acronym, o_scenario, o_suffix = extract_parts_from_filename(filename)
                if o_acronym is None:
                    unparseable_original_files.append(relative_path)

    print(f"Found {len(original_files)} original JSON files.")
    if unparseable_original_files:
        print(f"Warning: Found {len(unparseable_original_files)} original files with names that don't match the expected format:")
        for f in unparseable_original_files:
            print(f"  - {f}")
    print("---")

    # 2. Scan merged directory and validate contents
    print(f"Scanning merged directory '{merged_dir}' and validating...")
    if not os.path.isdir(merged_dir):
        print(f"ERROR: Merged directory '{merged_dir}' not found.")
        return False

    reported_source_files = set()
    processed_merged_files = 0

    for dirpath, _, filenames in os.walk(merged_dir):
        for merged_filename in filenames:
            if merged_filename.endswith('.json'):
                processed_merged_files += 1
                merged_filepath = os.path.join(dirpath, merged_filename)
                relative_merged_dir = os.path.relpath(dirpath, merged_dir)

                # Parse the MERGED filename itself to get expected group identity
                # Example: CHA_BronzePlaque.json -> ('CHA', 'BronzePlaque', '')
                expected_acronym, expected_scenario, _ = extract_parts_from_filename(merged_filename)

                if expected_acronym is None:
                    errors.append(f"Incorrect Merge Filename Format: Merged file '{merged_filepath}' has an unparseable name.")
                    continue # Cannot validate contents if name is wrong

                try:
                    with open(merged_filepath, 'r', encoding='utf-8') as f:
                        merged_data = json.load(f)
                except json.JSONDecodeError:
                    errors.append(f"JSON Error: Failed to decode JSON for merged file '{merged_filepath}'.")
                    continue
                except Exception as e:
                    errors.append(f"File Read Error: Failed to read merged file '{merged_filepath}': {e}")
                    continue

                # Check metadata structure
                metadata = merged_data.get('metadata')
                if not metadata or not isinstance(metadata, dict):
                    errors.append(f"Metadata Error: Missing or invalid 'metadata' in '{merged_filepath}'.")
                    continue
                source_files_list = metadata.get('source_files')
                if source_files_list is None or not isinstance(source_files_list, list):
                    errors.append(f"Metadata Error: Missing or invalid 'source_files' list in '{merged_filepath}'.")
                    continue # Cannot proceed without source_files list

                # Validate each source file listed
                if not source_files_list:
                     errors.append(f"Metadata Warning: 'source_files' list is empty in '{merged_filepath}'.")

                for source_filename in source_files_list:
                    # Reconstruct relative path for comparison with original_files
                    source_relative_path = os.path.join(relative_merged_dir, source_filename) if relative_merged_dir != '.' else source_filename
                    reported_source_files.add(source_relative_path)

                    # Correctness Check: Parse source filename and compare parts
                    s_acronym, s_scenario, s_suffix = extract_parts_from_filename(source_filename)

                    if s_acronym is None:
                        errors.append(f"Incorrect Source Filename: Source file '{source_filename}' listed in '{merged_filepath}' has unparseable name.")
                        continue

                    if s_acronym != expected_acronym or s_scenario != expected_scenario:
                        errors.append(f"Incorrect Merge Grouping: File '{source_filename}' (Acronym: {s_acronym}, Scenario: {s_scenario}) in merged file '{merged_filepath}' does not match expected group (Acronym: {expected_acronym}, Scenario: {expected_scenario}).")

    print(f"Processed {processed_merged_files} merged JSON files.")
    print("---")

    # 3. Completeness Check
    print("Performing completeness check...")
    missing_files = original_files - reported_source_files
    extra_files = reported_source_files - original_files

    if missing_files:
        errors.append(f"Completeness Error: {len(missing_files)} original files were NOT found in any merged 'source_files' list:")
        for f in sorted(list(missing_files)):
            errors.append(f"  - {f}")

    if extra_files:
        # This indicates a source file listed in a merge file doesn't exist in the original output dir
        errors.append(f"Completeness Error: {len(extra_files)} files listed in merged 'source_files' do NOT exist in the original directory '{original_dir}':")
        for f in sorted(list(extra_files)):
            errors.append(f"  - {f}")

    print("---")

    # 4. Final Report
    if not errors:
        print("Validation Successful: All checks passed.")
        return True
    else:
        print(f"Validation FAILED with {len(errors)} errors:")
        for i, error in enumerate(errors):
            print(f"{i+1}. {error}")
        return False

if __name__ == "__main__":
    if validate_merge():
        print("\nMerge process appears sane.")
        sys.exit(0)
    else:
        print("\nMerge process validation failed. Please review the errors above.")
        sys.exit(1) 