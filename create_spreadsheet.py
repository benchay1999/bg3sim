import os
import json
import csv
import re
import pandas as pd  # Added pandas for Excel writing

# --- Configuration ---
# Removed Google API constants
SOURCE_DIR = 'output_merged'
OUTPUT_XLSX_FILE = 'bg3_dialogue_sources.xlsx'
OUTPUT_CSV_BASENAME = 'bg3_dialogue_sources' # CSV files will be named like bg3_dialogue_sources_Act1.csv
# --- End Configuration ---

# Removed authenticate_google_sheets function

def process_files(source_directory):
    """Processes JSON files in the source directory and organizes data by sheet."""
    sheet_data = {} # { 'SheetName': [ [row1_col1, row1_col2,...], [row2_col1, row2_col2,...] ] }

    if not os.path.isdir(source_directory):
        print(f"Error: Source directory '{source_directory}' not found.")
        return sheet_data

    for root_dir_name in os.listdir(source_directory):
        # Skip files like .DS_Store
        if root_dir_name.startswith('.'):
            continue
        root_dir_path = os.path.join(source_directory, root_dir_name)
        if os.path.isdir(root_dir_path):
            # Sanitize sheet name for file naming conventions if needed later
            sheet_name = re.sub(r'[\/*?:"<>|]', '_', root_dir_name) # Basic sanitization
            if sheet_name not in sheet_data:
                sheet_data[sheet_name] = []

            for subdir, _, files in os.walk(root_dir_path):
                for filename in files:
                    if filename.lower().endswith('.json'):
                        file_path = os.path.join(subdir, filename)
                        base_name_no_ext = os.path.splitext(filename)[0]
                        # Column 1: lowercase filename without extension
                        col1_name = base_name_no_ext.lower()
                        # Prefix to remove: filename without extension + underscore
                        # Make prefix check case-insensitive just in case filenames vary
                        prefix_to_remove_lower = base_name_no_ext.lower() + "_"

                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                data = json.load(f)

                            source_files = data.get('metadata', {}).get('source_files', [])
                            if source_files:
                                row = [col1_name]
                                for source_file in source_files:
                                    # Remove prefix (case-insensitive) and .json extension
                                    derived_name = source_file
                                    prefix_actual = ""
                                    # Find the actual prefix used (handling case variations)
                                    if derived_name.lower().startswith(prefix_to_remove_lower):
                                        prefix_actual = derived_name[:len(prefix_to_remove_lower)]
                                        derived_name = derived_name[len(prefix_actual):]

                                    if derived_name.lower().endswith('.json'):
                                        derived_name = os.path.splitext(derived_name)[0]
                                    row.append(derived_name)
                                sheet_data[sheet_name].append(row)
                            else:
                                # Handle cases where source_files might be missing or empty
                                print(f"Warning: No 'source_files' found or empty in {file_path}. Adding placeholder row.")
                                sheet_data[sheet_name].append([col1_name, "N/A - No source files found"])

                        except json.JSONDecodeError:
                            print(f"Warning: Could not decode JSON from {file_path}")
                            sheet_data[sheet_name].append([col1_name, f"Error reading file"])
                        except KeyError as e:
                            print(f"Warning: Key {e} not found in {file_path}")
                            sheet_data[sheet_name].append([col1_name, f"Error - Missing key {e} in JSON"])
                        except Exception as e:
                            print(f"Warning: An error occurred processing {file_path}: {e}")
                            sheet_data[sheet_name].append([col1_name, f"Error - {e}"])

            # Sort rows within the sheet alphabetically based on the first column
            if sheet_name in sheet_data and sheet_data[sheet_name]: # Check if list is not empty
                 sheet_data[sheet_name].sort(key=lambda x: x[0].lower() if x and x[0] else "")


    return sheet_data

# Removed create_or_update_spreadsheet function

def write_to_csv(data, base_filename):
    """Writes the processed data to multiple CSV files, one per sheet."""
    print("\nWriting data to CSV files...")
    output_dir = os.path.dirname(base_filename) or "." # Get directory part or use current dir
    base = os.path.basename(base_filename)

    for sheet_name, rows in data.items():
        if not rows:
            print(f"Skipping empty sheet for CSV: {sheet_name}")
            continue

        # Sanitize sheet name for filename
        safe_sheet_name = re.sub(r'[\/*?:"<>|]', '_', sheet_name)
        csv_filename = os.path.join(output_dir, f"{base}_{safe_sheet_name}.csv")

        try:
            with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                # Optional: Write a header row
                # max_cols = max(len(r) for r in rows) if rows else 1
                # header = ["Merged File Base Name"] + [f"Source {i+1}" for i in range(max_cols - 1)]
                # writer.writerow(header)
                writer.writerows(rows)
            print(f"Successfully wrote {len(rows)} rows to {csv_filename}")
        except Exception as e:
            print(f"Error writing to CSV file {csv_filename}: {e}")

def write_to_xlsx(data, filename):
    """Writes the processed data to an XLSX file with multiple sheets using pandas."""
    print(f"\nWriting data to XLSX file: {filename}...")
    try:
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            for sheet_name, rows in data.items():
                if not rows:
                    print(f"Skipping empty sheet for XLSX: {sheet_name}")
                    continue

                 # Create DataFrame - handle potential empty rows/data issues
                try:
                    df = pd.DataFrame(rows)
                    # Optional: Add header row to DataFrame
                    # max_cols = df.shape[1]
                    # df.columns = ["Merged File Base Name"] + [f"Source {i+1}" for i in range(max_cols - 1)]

                    # Sanitize sheet name for Excel (max 31 chars, avoid certain chars)
                    safe_sheet_name = re.sub(r'[\/*?:\[\]]', '_', sheet_name)[:31]
                    if safe_sheet_name != sheet_name:
                         print(f"Adjusted sheet name from '{sheet_name}' to '{safe_sheet_name}' for Excel.")

                    df.to_excel(writer, sheet_name=safe_sheet_name, index=False, header=False) # Write data without index and header
                    print(f"Successfully wrote {len(rows)} rows to sheet '{safe_sheet_name}' in {filename}")
                except Exception as e:
                     print(f"Error creating DataFrame or writing sheet '{sheet_name}': {e}")
                     print(f"Problematic data sample: {rows[:5]}") # Print first few rows for debugging

    except Exception as e:
        print(f"Error writing to XLSX file {filename}: {e}")


if __name__ == "__main__":
    # Removed Google authentication call
    print(f"Processing JSON files in '{SOURCE_DIR}'...")
    organized_data = process_files(SOURCE_DIR)

    if organized_data:
        print("\nProcessing complete. Writing output files...")
        # Write to CSV files
        write_to_csv(organized_data, OUTPUT_CSV_BASENAME)
        # Write to XLSX file
        write_to_xlsx(organized_data, OUTPUT_XLSX_FILE)
        print(f"\nOutput files generated:")
        print(f"- XLSX: {OUTPUT_XLSX_FILE}")
        print(f"- CSVs: {OUTPUT_CSV_BASENAME}_<SheetName>.csv")
    else:
        print("No data processed. No output files created.") 