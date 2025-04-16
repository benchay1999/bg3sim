import os
import json
from dialog_simulator import DialogSimulator
from colorama import init, Fore, Style

# Initialize colorama
init()

def run_simulations(input_dir='output/', output_dir='traversals/', max_depth=50, test_mode=False):
    """
    Finds all JSON dialog files in the input directory, runs simulations,
    and saves the traversal data to the output directory.
    """
    print(f"{Fore.CYAN}Starting batch simulation process...{Style.RESET_ALL}")
    print(f"Input directory: {input_dir}")
    print(f"Output directory: {output_dir}")
    print(f"Max simulation depth: {max_depth}")
    print(f"Test mode (ignore flags): {'Enabled' if test_mode else 'Disabled'}")

    # Ensure the base output directory exists
    os.makedirs(output_dir, exist_ok=True)

    json_files_found = []
    for root, _, files in os.walk(input_dir):
        for file in files:
            if file.lower().endswith('.json'):
                # get the name of the subfolder too e.g., output/Act1/Chapel/CHA_BronzePlaque_AD_FL1Mural.json
                subfolder_name = os.path.basename(root)
                json_files_found.append(os.path.join(root, file))
                

    if not json_files_found:
        print(f"{Fore.YELLOW}No JSON files found in {input_dir}. Exiting.{Style.RESET_ALL}")
        return

    print(f"{Fore.GREEN}Found {len(json_files_found)} JSON files to process.{Style.RESET_ALL}")
    processed_count = 0
    error_count = 0

    for input_file_path in json_files_found:
        
        relative_path = os.path.relpath(input_file_path, input_dir)
        if "/Crimes/" in input_file_path:
            continue
        #output_file_path = os.path.join(output_dir, relative_path)

        if "Act" in relative_path:
            place_name = relative_path.split('_')[0]
            session_group_name = relative_path.split('_')[1]
        else:
            place_name = session_group_name = ""            
            subfolder_name = relative_path.split('/')[0]
            if ".json" not in subfolder_name:
                os.makedirs(os.path.join(output_dir, subfolder_name), exist_ok=True)
        # Ensure the specific output subdirectory exists
        output_file_dir = os.path.join(output_dir, place_name, session_group_name)
        os.makedirs(output_file_dir, exist_ok=True)
        output_file_path = os.path.join(output_file_dir, relative_path)
        print(f"{Fore.WHITE}Processing: {input_file_path} -> {output_file_path}{Style.RESET_ALL}")

        try:
            # Instantiate the simulator for the current file
            simulator = DialogSimulator(input_file_path)

            # Run the simulation without printing paths or doing internal exports
            # We capture the paths to manually export later
            all_paths, _, _ = simulator.simulate_all_paths(
                max_depth=max_depth,
                print_paths=False,       # Disable console path printing
                test_mode=test_mode,
                export_txt=False,        # Disable internal txt export
                export_json=False,       # Disable internal json export
                verbose=False            # Disable verbose logging
            )

            if not all_paths:
                print(f"{Fore.YELLOW}  No simulation paths generated for {input_file_path}. Skipping export.{Style.RESET_ALL}")
                continue

            # Create the structured data
            traversals = simulator.create_traversal_data(all_paths)

            # Export the traversals to the calculated output path
            simulator.export_traversals_to_json(traversals, output_file=output_file_path)
            
            print(f"{Fore.GREEN}  Successfully simulated and saved results to: {output_file_path}{Style.RESET_ALL}")
            processed_count += 1

        except json.JSONDecodeError as e:
            print(f"{Fore.RED}  Error processing {input_file_path}: Invalid JSON - {e}{Style.RESET_ALL}")
            error_count += 1
        except FileNotFoundError:
            print(f"{Fore.RED}  Error processing {input_file_path}: File not found (unexpected).{Style.RESET_ALL}")
            error_count += 1
        except Exception as e:
            print(f"{Fore.RED}  An unexpected error occurred while processing {input_file_path}: {e}{Style.RESET_ALL}")
            error_count += 1

    print(f"{Fore.CYAN}Batch simulation complete.{Style.RESET_ALL}")
    print(f"Successfully processed: {processed_count} files")
    print(f"Errors encountered: {error_count} files")

if __name__ == "__main__":
    # You can customize parameters here if needed
    run_simulations(
        input_dir='output/', 
        output_dir='traversals/', 
        max_depth=20,  # Adjust depth as needed, 100 is a reasonable default for full simulation
        test_mode=False # Set to True to ignore flag requirements during simulation
    ) 