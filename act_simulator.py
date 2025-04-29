import json
import sys
import os
import random
from colorama import init, Fore, Back, Style
# Assuming chapter_simulator is in the same directory or accessible
from chapter_simulator import ChapterSimulator

# Initialize colorama
init()

class ActSimulator:
    """
    Simulates traversals through an Act directory containing multiple Chapters.
    Manages flag state across chapters.
    """
    def __init__(self, act_directory):
        """Initialize the Act simulator with the specified Act directory"""
        print(f"{Fore.WHITE}===== ACT SIMULATOR - INIT ====={Style.RESET_ALL}")
        if not os.path.isdir(act_directory):
            print(f"{Fore.RED}Error: Act directory not found at {act_directory}{Style.RESET_ALL}")
            sys.exit(1)

        self.act_directory = act_directory
        self.act_id = os.path.basename(act_directory) # e.g., Act1
        self.title = self.act_id # Simple title for now

        # Find all subdirectories, assuming they are chapters
        try:
            potential_chapters = [d for d in os.listdir(act_directory)
                                 if os.path.isdir(os.path.join(act_directory, d))]
            self.chapter_paths = {
                chapter_id: os.path.join(act_directory, chapter_id)
                for chapter_id in sorted(potential_chapters) # Sort chapters alphabetically by directory name
            }
            self.chapter_ids = list(self.chapter_paths.keys())
        except OSError as e:
            print(f"{Fore.RED}Error reading Act directory {act_directory}: {e}{Style.RESET_ALL}")
            sys.exit(1)

        if not self.chapter_ids:
            print(f"{Fore.RED}Error: No chapter directories found in Act directory {act_directory}{Style.RESET_ALL}")
            sys.exit(1)

        # Special handling for Act1 order
        if self.act_id == "Act1":
            fixed_prefix = ['Crash', 'Chapel', 'DEN']
            # Get the original list of all found chapter IDs
            all_found_chapters = self.chapter_ids # Keep a reference before modifying

            actual_fixed = [ch for ch in fixed_prefix if ch in all_found_chapters]
            # Optional: Add warning if not all fixed chapters are found
            # It might be better to raise an error if required chapters are missing.
            if len(actual_fixed) != len(fixed_prefix):
                missing = [ch for ch in fixed_prefix if ch not in actual_fixed]
                print(f"{Fore.YELLOW}Warning: Required fixed chapters for Act1 not found: {missing}. Using available ones: {actual_fixed}{Style.RESET_ALL}")
                # Decide if this should be a fatal error or just a warning. For now, warning.

            remaining_chapters = [ch for ch in all_found_chapters if ch not in actual_fixed]
            random.shuffle(remaining_chapters) # Shuffle the remaining ones in place

            self.chapter_ids = actual_fixed + remaining_chapters # Set the final order
            print(f"{Fore.BLUE}Applying special chapter order for Act1.{Style.RESET_ALL}")
        # For other acts, self.chapter_ids remains the default sorted list.
        print(f"Loaded Act '{self.title}' ({self.act_id}) from directory {act_directory}")
        print(f"Found {len(self.chapter_ids)} chapters:")
        for chapter_id in self.chapter_ids:
            print(f"  - {chapter_id} ({self.chapter_paths[chapter_id]})")

        # Act-level state
        self.act_active_flags = set() # Flags maintained across the entire act

        # Storage for results
        self.act_traversal_results = []

    def _get_chapter_id_from_path(self, dir_path):
        """Extract chapter ID (directory name) from path."""
        return os.path.basename(dir_path)

    def simulate_act(self, num_traversals=1, export_txt=False, export_json=False,
                       initial_flags_set=None, final_flags_export_dir=None,
                       # --- Chapter Simulation Args ---
                       min_utterances_per_session=3,
                       prioritize_approval=True,
                       include_all_scenarios=True,
                       include_all_sessions=True,
                       chapter_export_txt=False, # Option to export individual chapters?
                       chapter_export_json=False): # Option to export individual chapters?
        """
        Simulate traversals through the Act by running chapters in sequence.

        Args:
            num_traversals (int): Number of Act traversals to generate.
            export_txt (bool): Export each Act traversal to a text file.
            export_json (bool): Export each Act traversal to a JSON file.
            initial_flags_set (set, optional): Initial flags for the Act. Defaults to empty set.
            final_flags_export_dir (str, optional): Directory to export the final flags JSON file for each traversal.
            min_utterances_per_session (int): Passed to ChapterSimulator.
            prioritize_approval (bool): Passed to ChapterSimulator.
            include_all_scenarios (bool): Passed to ChapterSimulator.
            include_all_sessions (bool): Passed to ChapterSimulator.
            chapter_export_txt (bool): Whether to trigger TXT export within each ChapterSimulator run.
            chapter_export_json (bool): Whether to trigger JSON export within each ChapterSimulator run.

        Returns:
            list: List of Act traversal results.
        """
        print(f"\n{Fore.WHITE}===== ACT SIMULATOR - SIMULATING ACT ====={Style.RESET_ALL}")
        print(f"Generating {num_traversals} Act traversals for '{self.title}'")

        self.act_traversal_results = []

        for i in range(num_traversals):
            # For now, always simulate chapters in fixed (alphabetical) order.
            # Could add random shuffling here if needed for variation between traversals.
            # random.shuffle(self.chapter_ids) # Example if shuffling needed
            chosen_chapter_sequence = self.chapter_ids # Use the sorted list

            print(f"\n{Fore.CYAN}Act Traversal {i+1}: Using chapter sequence {chosen_chapter_sequence}{Style.RESET_ALL}")

            # Initialize flags for this specific Act traversal run
            current_act_flags = initial_flags_set.copy() if initial_flags_set is not None else set()
            print(f"{Fore.BLUE}Starting Act traversal {i+1} with {len(current_act_flags)} initial flags.{Style.RESET_ALL}")

            act_run_data = {
                "act_id": self.act_id,
                "chapter_sequence": chosen_chapter_sequence,
                "chapter_results": {},
                "final_flags": [] # Will store the final flags (as list) after this run
            }

            # --- SIMULATION LOOP ---
            for chapter_id in chosen_chapter_sequence:
                chapter_directory_path = self.chapter_paths.get(chapter_id)
                if not chapter_directory_path:
                    print(f"{Fore.RED}Error: Could not find path for chapter ID '{chapter_id}'. Skipping.{Style.RESET_ALL}")
                    continue

                print(f"\n{Fore.YELLOW}---> Simulating Chapter: {chapter_id} ({chapter_directory_path}) <---{Style.RESET_ALL}")
                print(f"{Fore.BLUE}    Current Act flags: {len(current_act_flags)}{Style.RESET_ALL}")

                try:
                    # Instantiate ChapterSimulator for this specific chapter
                    chapter_sim = ChapterSimulator(chapter_directory_path)

                    # Simulate ONE traversal through this chapter, passing current act flags
                    chapter_results_list = chapter_sim.simulate_chapter(
                        num_traversals=1, # Crucial: Only one traversal per chapter within an act run
                        export_txt=chapter_export_txt,   # Pass down export flags if needed
                        export_json=chapter_export_json,
                        min_utterances_per_session=min_utterances_per_session,
                        prioritize_approval=prioritize_approval,
                        include_all_scenarios=include_all_scenarios,
                        include_all_sessions=include_all_sessions,
                        initial_flags_set=current_act_flags # Pass current flags
                    )

                    # Check if the chapter simulation produced a result
                    if chapter_results_list:
                        # Get the single traversal result for this chapter
                        single_chapter_run_data = chapter_results_list[0]
                        # Extract the final flags from this chapter run (convert list back to set)
                        chapter_final_flags = set(single_chapter_run_data.get("final_flags", []))

                        # Store the detailed results for this chapter
                        act_run_data["chapter_results"][chapter_id] = single_chapter_run_data

                        # Update the act's flags for the next chapter
                        current_act_flags = chapter_final_flags
                        print(f"{Fore.BLUE}    Updated Act flags after {chapter_id}: {len(current_act_flags)}{Style.RESET_ALL}")

                    else:
                        print(f"{Fore.YELLOW}    Chapter '{chapter_id}' produced no valid traversal result. Flags not updated.{Style.RESET_ALL}")
                        # Store an indicator that this chapter failed/was skipped
                        act_run_data["chapter_results"][chapter_id] = {"status": "skipped_no_valid_path", "final_flags": list(current_act_flags)}
                        # Keep current flags for the next chapter (no change)

                except SystemExit:
                     # Intercept SystemExit from ChapterSimulator init errors
                     print(f"{Fore.RED}Chapter '{chapter_id}' initialization failed. Stopping Act traversal.{Style.RESET_ALL}")
                     # Optionally mark this run as incomplete or handle differently
                     # For now, let's just stop this traversal attempt
                     act_run_data["status"] = f"error_initializing_chapter_{chapter_id}"
                     break # Stop processing chapters for this act traversal
                except Exception as e:
                    print(f"{Fore.RED}Error simulating chapter '{chapter_id}': {e}{Style.RESET_ALL}")
                    # Optionally store error info
                    act_run_data["chapter_results"][chapter_id] = {"error": str(e), "final_flags": list(current_act_flags)}
                    # Decide whether to continue act traversal or stop
                    print(f"{Fore.YELLOW}Continuing Act traversal despite error in chapter '{chapter_id}'.{Style.RESET_ALL}")
                    continue # Continue to next chapter

            # --- END CHAPTER SIMULATION LOOP ---

            # Store the final flags for this Act run
            act_run_data["final_flags"] = sorted(list(current_act_flags)) # Convert set to sorted list for JSON
            self.act_traversal_results.append(act_run_data)

            print(f"\n{Fore.GREEN}Act Traversal {i+1} complete.{Style.RESET_ALL}")
            print(f"Final flag count for this run: {len(current_act_flags)}")

            # Export this specific Act traversal's final flags if requested
            if final_flags_export_dir:
                try:
                    os.makedirs(final_flags_export_dir, exist_ok=True) # Ensure directory exists
                    flags_filename = os.path.join(final_flags_export_dir, f"final_flags_{self.act_id}_run_{i+1}.json")
                    self._export_final_flags(current_act_flags, flags_filename)
                except Exception as e:
                    print(f"{Fore.RED}Error exporting flags for run {i+1}: {e}{Style.RESET_ALL}")

            # Export the full traversal data (dialog, etc.) if requested
            if export_txt:
                if not os.path.exists("simulation_results"):
                    os.makedirs("simulation_results")
                self._export_act_traversal_to_txt(act_run_data, f"simulation_results/act_{self.act_id}_traversal_{i+1}.txt")
            if export_json:
                if not os.path.exists("simulation_results"):
                    os.makedirs("simulation_results")
                self._export_act_traversal_to_json(act_run_data, f"simulation_results/act_{self.act_id}_traversal_{i+1}.json")

        print(f"\n{Fore.GREEN}Act simulation finished. Generated {len(self.act_traversal_results)} traversals.{Style.RESET_ALL}")
        return self.act_traversal_results


    def _export_act_traversal_to_txt(self, act_run_data, output_file):
        """Export a single Act traversal run to a text file."""
        print(f"{Fore.GREEN}Exporting Act traversal to {output_file}...{Style.RESET_ALL}")
        # TODO: Implement TXT export logic
        # Should include Act ID, chapter sequence, final flags,
        # and summaries/details from each chapter's result.
        # This might require accessing nested data from act_run_data["chapter_results"].
        # For simplicity, could just print the chapter IDs and their final flag counts initially.
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"Baldur's Gate 3 Act Traversal\n\n")
            f.write(f"Act: {self.title} ({self.act_id})\n")
            f.write(f"Chapter Sequence: {' -> '.join(act_run_data['chapter_sequence'])}\n")
            f.write(f"Final Act Flags ({len(act_run_data['final_flags'])}): {act_run_data['final_flags']}\n\n") # Already sorted list
            f.write(f"--- Traversal Details ---\n")

            for chapter_id in act_run_data['chapter_sequence']:
                f.write(f"\n################ Chapter: {chapter_id} ################\n")
                chapter_result = act_run_data['chapter_results'].get(chapter_id)

                if chapter_result is None:
                    f.write("Chapter data missing.\n")
                    continue
                if isinstance(chapter_result, dict) and "error" in chapter_result:
                    f.write(f"Error during chapter simulation: {chapter_result['error']}\n")
                    f.write(f"Flags at end of chapter (before error): {sorted(list(chapter_result.get('final_flags', [])))}\n")
                    continue
                if isinstance(chapter_result, dict) and chapter_result.get("status") == "skipped_no_valid_path":
                     f.write(f"Chapter skipped: No valid scenario traversal found.\n")
                     f.write(f"Flags passed through: {sorted(list(chapter_result.get('final_flags', [])))}\n")
                     continue
                if not isinstance(chapter_result, dict) or "scenario_sequence" not in chapter_result:
                    f.write("Unexpected chapter result format.\n")
                    print(f"{Fore.YELLOW}Warning: Unexpected result format for chapter {chapter_id} during TXT export.{Style.RESET_ALL}")
                    continue

                f.write(f"Scenario Sequence: {' -> '.join(chapter_result.get('scenario_sequence', []))}\n")
                chapter_final_flags = sorted(list(chapter_result.get('final_flags', [])))
                f.write(f"Flags at end of Chapter ({len(chapter_final_flags)}): {chapter_final_flags}\n\n")

                # --- Include Scenario/Session Details (optional, can be verbose) ---
                f.write("--- Scenario Details ---\n")
                for scenario_id in chapter_result.get('scenario_sequence', []):
                    f.write(f"======== Scenario: {scenario_id} ========\n")
                    scenario_data = chapter_result.get('scenario_results', {}).get(scenario_id)

                    if scenario_data is None:
                        f.write("Scenario data missing.\n")
                        continue
                    if isinstance(scenario_data, dict) and "error" in scenario_data:
                         f.write(f"Error during scenario simulation: {scenario_data['error']}\n")
                         continue
                    if isinstance(scenario_data, dict) and scenario_data.get("status") == "skipped_no_valid_path":
                         f.write(f"Scenario skipped: No valid session traversal found.\n")
                         continue
                    if not isinstance(scenario_data, dict) or "session_sequence" not in scenario_data:
                         f.write("Unexpected scenario result format.\n")
                         continue

                    f.write(f"Session Sequence: {' -> '.join(scenario_data.get('session_sequence', []))}\n")
                    # Optionally add session dialog here if needed, but might be too much detail
                    # Example: Iterate through sessions and their node_data like in chapter_simulator export
                    for session_id in scenario_data.get('session_sequence', []):
                        f.write(f"----- Session: {session_id} -----\n")
                        synopsis = scenario_data.get('session_synopses', {}).get(session_id, 'Synopsis not found')
                        f.write(f"Synopsis: {synopsis}\n\n")
                        node_data_list = scenario_data.get('node_data', {}).get(session_id, [])
                        if not node_data_list:
                             f.write("No dialog data available for this session.\n")
                        else:
                            # Simplified dialog export for Act level
                            dialog_lines = 0
                            for node in node_data_list:
                                if not isinstance(node, dict): continue
                                if node.get('special_marker'): continue # Skip markers

                                speaker = node.get('speaker', 'Unknown')
                                text = node.get('text', '')
                                context = node.get('context', '')
                                approval = node.get('approval', [])
                                node_type = node.get('node_type', 'normal')

                                if not text and not context: continue # Skip if truly empty

                                line = ""
                                if node_type == 'tagcinematic':
                                    line = f"[desc] {text}"
                                elif text:
                                    line = f"{speaker}: {text}"
                                elif context: # Handle case with only context
                                    line = f"[context only] {context}"
                                else: # Should not happen due to check above, but safety
                                     continue

                                # Add context only if text was also present for the main line
                                if context and text:
                                    line += f" || [context] {context}"
                                if approval:
                                    line += f" || [approval] {approval}"

                                f.write(f"{line}\n")
                                dialog_lines += 1

                            if dialog_lines == 0:
                                f.write("(Session contained no nodes with text or context)\n")
                        f.write("\n") # Newline after session

        print(f"{Fore.GREEN}Act traversal exported successfully to {output_file}{Style.RESET_ALL}")
        return output_file


    def _export_act_traversal_to_json(self, act_run_data, output_file):
        """Export a single Act traversal run to a JSON file."""
        print(f"{Fore.GREEN}Exporting Act traversal to {output_file}...{Style.RESET_ALL}")
        # Ensure all sets within the structure are converted to lists for JSON serialization.
        # The final_flags are already lists. Need to check nested structures.
        # Using json.loads(json.dumps(...)) is a robust way to handle nested sets.
        try:
            # Convert sets to lists recursively (simple approach using json cycle)
            export_data = json.loads(json.dumps(act_run_data, default=list))
        except TypeError as e:
             print(f"{Fore.RED}Error preparing data for JSON export: {e}. Check for non-serializable types.{Style.RESET_ALL}")
             return None

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        print(f"{Fore.GREEN}Act traversal exported successfully to {output_file}{Style.RESET_ALL}")
        return output_file

    def _export_final_flags(self, final_flags_set, output_file):
        """Export the final set of flags to a JSON file."""
        print(f"{Fore.GREEN}Exporting final flags ({len(final_flags_set)}) to {output_file}...{Style.RESET_ALL}")
        flags_list = sorted(list(final_flags_set)) # Convert set to sorted list

        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(flags_list, f, indent=2, ensure_ascii=False)
            print(f"{Fore.GREEN}Final flags exported successfully.{Style.RESET_ALL}")
            return output_file
        except Exception as e:
             print(f"{Fore.RED}Error exporting final flags to {output_file}: {e}{Style.RESET_ALL}")
             return None


# --- Main Function (Example Usage) ---
def main():
    print(f"{Fore.CYAN}Baldur's Gate 3 Act Simulator{Style.RESET_ALL}")
    print("This tool simulates traversals through Act directories.")

    # Get Act directory path from arguments or input
    if len(sys.argv) > 1:
        act_dir = sys.argv[1]
    else:
        default_act = "output_merged/Act1" # Example path - ADJUST AS NEEDED
        act_dir = input(f"Enter path to Act directory [default: {default_act}]: ")
        if not act_dir:
            act_dir = default_act
    if not os.path.isdir(act_dir):
        print(f"{Fore.RED}Error: Act directory not found: {act_dir}{Style.RESET_ALL}")
        return

    # Instantiate the simulator
    try:
        act_simulator = ActSimulator(act_dir)
    except SystemExit: # Catch exits from init errors
        return
    except Exception as e:
        print(f"{Fore.RED}Error initializing ActSimulator: {e}{Style.RESET_ALL}")
        return

    # --- Get Simulation Options ---
    num_traversals = 1
    try:
        num_input = input(f"Number of Act traversals to generate [default: 1]: ")
        if num_input:
            num_traversals = int(num_input)
    except ValueError:
        print(f"{Fore.YELLOW}Invalid input. Using default value of 1.{Style.RESET_ALL}")

    # Options passed down to ChapterSimulator
    min_utterances = 3
    try:
        min_utterances_input = input(f"Minimum utterances per session (for chapters) [default: 3]: ")
        if min_utterances_input:
            min_utterances = int(min_utterances_input)
    except ValueError:
        print(f"{Fore.YELLOW}Invalid input. Using default value of 3.{Style.RESET_ALL}")

    prioritize_approval = input(f"Prioritize approval paths (for chapters)? (y/n, default: y): ").lower() != 'n'
    include_all_scenarios = input(f"Try to include all scenarios (for chapters)? (y/n, default: y): ").lower() != 'n'
    include_all_sessions = input(f"Try to include all sessions (for scenarios within chapters)? (y/n, default: y): ").lower() != 'n'

    # Act level export options
    export_txt = input(f"{Fore.BLUE}Export Act traversals to text files? (y/n, default: n):{Style.RESET_ALL} ").lower() == 'y'
    export_json = input(f"{Fore.BLUE}Export Act traversals to JSON files? (y/n, default: n):{Style.RESET_ALL} ").lower() == 'y'

    # Optional: Ask if individual chapter exports should be triggered (can be noisy)
    # chapter_export_txt = input(f"Also export individual Chapter TXT files? (y/n, default: n): ").lower() == 'y'
    # chapter_export_json = input(f"Also export individual Chapter JSON files? (y/n, default: n): ").lower() == 'y'
    chapter_export_txt = False # Defaulting to off for less clutter
    chapter_export_json = False

    # Ask for initial flags file
    initial_flags = None
    load_flags_choice = input(f"{Fore.BLUE}Load initial Act flags from a JSON file? (y/n, default: n):{Style.RESET_ALL} ").lower() == 'y'
    if load_flags_choice:
        flags_file_path = input(f"Enter path to initial flags JSON file (must contain a list of strings): ")
        if flags_file_path and os.path.isfile(flags_file_path):
            try:
                with open(flags_file_path, 'r', encoding='utf-8') as f_flags:
                    flags_list = json.load(f_flags)
                    if isinstance(flags_list, list):
                        initial_flags = set(flags_list)
                        print(f"{Fore.GREEN}Successfully loaded {len(initial_flags)} initial flags from {flags_file_path}{Style.RESET_ALL}")
                    else:
                        print(f"{Fore.RED}Error: JSON file {flags_file_path} does not contain a list.{Style.RESET_ALL}")
            except json.JSONDecodeError:
                print(f"{Fore.RED}Error: Could not decode JSON from {flags_file_path}{Style.RESET_ALL}")
            except Exception as e:
                print(f"{Fore.RED}Error reading flags file {flags_file_path}: {e}{Style.RESET_ALL}")
        elif flags_file_path:
            print(f"{Fore.RED}Error: Initial flags file not found: {flags_file_path}{Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}No flags file specified. Starting with default (empty) flags.{Style.RESET_ALL}")

    # Ask for final flags export path
    export_final_flags_path = None
    save_flags_choice = input(f"{Fore.BLUE}Save final flags of *each* traversal to JSON files? (y/n, default: n):{Style.RESET_ALL} ").lower() == 'y'
    if save_flags_choice:
        default_flags_dir = "simulation_results/flags" # Suggest a directory
        final_flags_dir_path = input(f"Enter directory for final flags JSON files [default: {default_flags_dir}]: ")
        if not final_flags_dir_path:
            final_flags_dir_path = default_flags_dir
        export_final_flags_path = final_flags_dir_path # Store the directory path


    # --- Run Simulation ---
    print(f"\n{Fore.GREEN}Running Act simulation...{Style.RESET_ALL}")

    results = act_simulator.simulate_act(
        num_traversals=num_traversals,
        export_txt=export_txt,
        export_json=export_json,
        initial_flags_set=initial_flags,
        final_flags_export_dir=export_final_flags_path, # Pass the directory path
        # Chapter Sim Args
        min_utterances_per_session=min_utterances,
        prioritize_approval=prioritize_approval,
        include_all_scenarios=include_all_scenarios,
        include_all_sessions=include_all_sessions,
        chapter_export_txt=chapter_export_txt,
        chapter_export_json=chapter_export_json
    )

    print(f"\n{Fore.GREEN}Act simulation run complete. Generated {len(results)} traversals.{Style.RESET_ALL}")
    if export_final_flags_path:
        print(f"Final flags for each run (if generated) saved in directory: {export_final_flags_path}") # Updated confirmation message


if __name__ == "__main__":
    # Ensure the referenced chapter directories exist and contain scenario JSON files.
    # Example structure:
    # output_merged/
    #   Act1/
    #     Chapel/
    #       cha_outside.json
    #       cha_crypt.json
    #     Wilderness/
    #       wild_encounter.json
    #       ...
    main() 