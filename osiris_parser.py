import re
import os

def extract_dialog_resources(file_path):
    """
    Extracts all lines containing '(DIALOGRESOURCE)' from an Osiris script file.

    Args:
        file_path (str): The path to the Osiris script file (.txt).

    Returns:
        list[str]: A list of lines containing '(DIALOGRESOURCE)'.
                   Returns an empty list if the file is not found or
                   if no matching lines are found.
    """
    dialog_lines = []
    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        return dialog_lines

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                # Using simple string search for efficiency as requested
                if "(DIALOGRESOURCE)" in line:
                    dialog_lines.append(line.strip()) # strip() removes leading/trailing whitespace
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")

    return dialog_lines

# Example usage with the provided file path
file_to_process = "RawFiles/Goals/Act1b_CRE_YouthTraining.txt"
extracted_lines = extract_dialog_resources(file_to_process)

if extracted_lines:
    print(f"Found {len(extracted_lines)} lines with (DIALOGRESOURCE) in {file_to_process}:")
    for line in extracted_lines:
        print(line)
else:
    print(f"No lines containing '(DIALOGRESOURCE)' found in {file_to_process}.")

def process_directory(directory_path):
    """
    Processes all .txt files in a directory to extract dialog resource lines.
    """
    all_results = {}
    if not os.path.isdir(directory_path):
        print(f"Error: Directory not found at {directory_path}")
        return all_results

    for filename in os.listdir(directory_path):
        if filename.endswith(".txt"):
            file_path = os.path.join(directory_path, filename)
            print(f"\n--- Processing {filename} ---")
            lines = extract_dialog_resources(file_path)
            if lines:
                all_results[filename] = lines
                print(f"Found {len(lines)} lines.")
                # for line in lines:
                #     print(line) # Uncomment to print lines for each file
            else:
                print("No matching lines found.")
    return all_results

# Example usage for a directory
# target_directory = "path/to/your/osiris/scripts"
# directory_results = process_directory(target_directory)
# print("\n--- Summary ---")
# for filename, lines in directory_results.items():
#      print(f"{filename}: {len(lines)} lines")