import json
import sys
import os
import random
from colorama import init, Fore, Back, Style
# Assuming scenario_simulator and dialog_simulator are in the same directory or accessible
from scenario_simulator import ScenarioSimulator
from dialog_simulator import DialogSimulator # May not be needed directly, but ScenarioSimulator uses it

# Initialize colorama for colored terminal output
init()

class ChapterSimulator:
    """
    Simulates traversals through a chapter file containing multiple scenarios.
    Manages flag state across scenarios and respects constraints between them.
    """
    def __init__(self, chapter_directory):
        """Initialize the chapter simulator with the specified chapter directory"""
        print(f"{Fore.WHITE}===== CHAPTER SIMULATOR - INIT ====={Style.RESET_ALL}")
        if not os.path.isdir(chapter_directory):
            print(f"{Fore.RED}Error: Chapter directory not found at {chapter_directory}{Style.RESET_ALL}")
            sys.exit(1)

        # Derive chapter ID and title from the directory path
        self.chapter_directory = chapter_directory
        self.title = os.path.basename(chapter_directory)
        # Example: Get Act name from parent directory if needed
        parent_dir = os.path.dirname(chapter_directory)
        act_name = os.path.basename(parent_dir)
        self.chapter_id = f"{act_name}_{self.title}"
        # List all .json files in the directory as scenarios
        try:
            all_files = [f for f in os.listdir(chapter_directory) if f.endswith('.json')]
            self.scenario_files = [os.path.join(chapter_directory, f) for f in all_files]
        except OSError as e:
            print(f"{Fore.RED}Error reading chapter directory {chapter_directory}: {e}{Style.RESET_ALL}")
            sys.exit(1)
        if not self.scenario_files:
            print(f"{Fore.RED}Error: No scenario (.json) files found in chapter directory {chapter_directory}{Style.RESET_ALL}")
            sys.exit(1)

        # Store act name for potential use
        self.act_name = act_name
        # No constraints defined by chapter directory structure
        self.metadata = {}
        self.ordering = []
        self.exclusivity = []
        # TODO: This is a hack to get the order right for Tutorial act. Clean this up later.
        # Define specific order for Tutorial act
        if self.act_name == "Tutorial":
            self.ordering = ['tut_start', 'tut_lab', 'tut_misc', 'tut_lowerdeck', 'tut_helm', 'tut_lab', 'tut_transformchamber', 'tut_upperdeck']
            print(f"{Fore.BLUE}Detected Tutorial act. Applying specific scenario order.{Style.RESET_ALL}")
        #if self.act_name == "Act1":
        #    self.ordering = ['Crash', 'Chapel', 'DEN', 'Forest', 'Plains', 'Swamp', 'HAG', 'HagLair',  'Goblin',  'Underdark']
        self.scenario_ids = sorted([self._get_scenario_id_from_path(sf) for sf in self.scenario_files])
        self.scenario_path_map = {self._get_scenario_id_from_path(sf): sf for sf in self.scenario_files}

        print(f"Loaded chapter '{self.title}' ({self.chapter_id}) from directory {chapter_directory}")
        print(f"Found {len(self.scenario_files)} scenarios:")
        for scenario_id in self.scenario_ids:
            print(f"  - {scenario_id} ({self.scenario_path_map[scenario_id]})")
        # print(f"Ordering constraints: {self.ordering}") # Removed
        # print(f"Exclusivity constraints: {self.exclusivity}") # Removed
        
        # Chapter-level state
        self.chapter_active_flags = set() # Flags maintained across the chapter

        # Cache for ScenarioSimulator instances? Maybe not needed if created per traversal.
        self.scenario_simulators = {}

        # Storage for results
        self.chapter_traversal_results = []


    def _get_scenario_id_from_path(self, file_path):
        """Extract a unique ID from the scenario file path (e.g., filename without ext)"""
        return os.path.splitext(os.path.basename(file_path))[0]

    def _validate_scenario_sequence(self, sequence):
        """Validate that a sequence of scenario IDs respects chapter constraints.
           (Now trivial as chapters-as-directories have no constraints)"""
        # No ordering or exclusivity constraints to check
        return True

    def _generate_valid_scenario_sequences(self, include_all_scenarios=True):
        """Generate valid sequences of scenario IDs.
           Respects self.ordering if defined, otherwise generates permutations.
        """
        # Check if a specific order is defined
        if self.ordering:
            print(f"{Fore.BLUE}Using predefined scenario order: {self.ordering}{Style.RESET_ALL}")
            # Validate that all ordered scenarios exist
            missing_scenarios = [sid for sid in self.ordering if sid not in self.scenario_ids]
            if missing_scenarios:
                print(f"{Fore.RED}Error: Scenarios defined in ordering are missing from the chapter directory: {missing_scenarios}{Style.RESET_ALL}")
                # Decide how to handle this: return empty, raise error, or proceed with available?
                # For now, let's return empty to prevent invalid traversals.
                return []
            # Return the predefined order as the only valid sequence
            return [self.ordering]

        # --- Original logic if no predefined order --- 
        if not include_all_scenarios:
            # This case is less defined now. If not all included, which subset?
            # For now, let's assume include_all_scenarios is usually True for chapters.
            # If needed, could generate subsets, but skipping for now.
            print(f"{Fore.YELLOW}Warning: include_all_scenarios=False not fully handled for directory-based chapters without predefined ordering. Using all scenarios.{Style.RESET_ALL}")

        # Generate a shuffled sequence of all available scenarios
        shuffled_ids = list(self.scenario_ids)
        random.shuffle(shuffled_ids)
        valid_sequences = [shuffled_ids]

        print(f"{Fore.GREEN}Generated {len(valid_sequences)} scenario sequence(s) (shuffled order).{Style.RESET_ALL}")
        return valid_sequences


    def simulate_chapter(self, num_traversals=1, export_txt=False, export_json=False,
                         min_utterances_per_session=3, prioritize_approval=True,
                         include_all_scenarios=True, include_all_sessions=True,
                         initial_flags_set=None):
        """
        Simulate traversals through the chapter by running scenarios in sequence.

        Args:
            num_traversals (int): Number of chapter traversals to generate.
            export_txt (bool): Export each chapter traversal to a text file.
            export_json (bool): Export each chapter traversal to a JSON file.
            min_utterances_per_session (int): Min utterances for sessions within scenarios.
            prioritize_approval (bool): Prioritize approval paths within scenarios/sessions.
            include_all_scenarios (bool): Try to include all non-exclusive scenarios.
            include_all_sessions (bool): Try to include all non-exclusive sessions within scenarios.
            initial_flags_set (set, optional): A set of initial flags to start the chapter traversal with.
                                             Defaults to an empty set if None.

        Returns:
            list: List of chapter traversal results.
        """
        print(f"{Fore.WHITE}===== CHAPTER SIMULATOR - SIMULATING CHAPTER ====={Style.RESET_ALL}")
        print(f"Generating {num_traversals} chapter traversals for '{self.title}'")

        valid_scenario_sequences = self._generate_valid_scenario_sequences(
            include_all_scenarios=include_all_scenarios
        )
        if not valid_scenario_sequences:
            print(f"{Fore.RED}No valid scenario sequences found for this chapter. Check constraints.{Style.RESET_ALL}")
            return []

        self.chapter_traversal_results = []
        for i in range(num_traversals):
            if not valid_scenario_sequences: # Should not happen if checked above, but safety first
                print(f"{Fore.RED}Ran out of valid scenario sequences.{Style.RESET_ALL}")
                break

            # Choose a sequence. Since _generate_valid_scenario_sequences currently returns
            # a list containing one shuffled sequence, we just take that one.
            # If it generated multiple permutations later, random.choice would work.
            # chosen_scenario_sequence = random.choice(valid_scenario_sequences)
            if i < len(valid_scenario_sequences):
                 # Use generated sequences first if available (only 1 currently)
                 chosen_scenario_sequence = valid_scenario_sequences[i]
            else:
                 # If more traversals requested than unique sequences generated,
                 # re-shuffle and use that.
                 print(f"{Fore.YELLOW}Generating additional random sequence for traversal {i+1}{Style.RESET_ALL}")
                 chosen_scenario_sequence = list(self.scenario_ids)
                 random.shuffle(chosen_scenario_sequence)

            print(f"{Fore.CYAN}Chapter Traversal {i+1}: Using scenario sequence {chosen_scenario_sequence}{Style.RESET_ALL}")

            # Initialize flags for this specific chapter traversal run
            # Use provided initial flags if available, otherwise start empty
            current_chapter_flags = initial_flags_set.copy() if initial_flags_set is not None else set()
            print(f"{Fore.BLUE}Starting chapter traversal {i+1} with {len(current_chapter_flags)} initial flags.{Style.RESET_ALL}")

            chapter_run_data = {
                "chapter_id": self.chapter_id,
                "scenario_sequence": chosen_scenario_sequence,
                "scenario_results": {},
                "final_flags": set() # Will store the final flags after this run
            }

            # --- SIMULATION LOOP ---
            for scenario_id in chosen_scenario_sequence:
                
                scenario_file_path = self.scenario_path_map.get(scenario_id)
                if not scenario_file_path:
                    print(f"{Fore.RED}Error: Could not find file path for scenario ID '{scenario_id}'. Skipping.{Style.RESET_ALL}")
                    continue

                print(f"{Fore.YELLOW}--> Simulating Scenario: {scenario_id} ({scenario_file_path}) <--{Style.RESET_ALL}")
                print(f"{Fore.BLUE}    Current chapter flags: {len(current_chapter_flags)}{Style.RESET_ALL}") # {current_chapter_flags}

                # Instantiate ScenarioSimulator for this specific scenario
                # Ensure the scenario file exists before creating the simulator
                if not os.path.exists(scenario_file_path):
                     print(f"{Fore.RED}Error: Scenario file {scenario_file_path} not found. Skipping scenario '{scenario_id}'.{Style.RESET_ALL}")
                     continue

                try:
                    scenario_sim = ScenarioSimulator(scenario_file_path)

                    # --- THIS IS THE KEY PART REQUIRING MODIFICATION ---
                    # We need a new method in ScenarioSimulator:

                    scenario_traversal_data, scenario_final_flags = scenario_sim.simulate_single_traversal(
                        initial_flags=current_chapter_flags,
                        min_utterances=min_utterances_per_session,
                        prioritize_approval=prioritize_approval,
                        include_all_sessions=include_all_sessions
                    )
                    
                    # Placeholder until ScenarioSimulator is modified:
                    # print(f"{Fore.MAGENTA}    [Placeholder] Running scenario simulation for {scenario_id}...{Style.RESET_ALL}")
                    # Simulate scenario (using existing method for now, flags won't persist correctly yet)
                    # temp_traversals = scenario_sim.simulate_scenario(
                    #     num_traversals=1, # Simulate just one path through the scenario
                    #     export_txt=False, # Disable internal export
                    #     export_json=False,
                    #     min_utterances=min_utterances_per_session,
                    #     prioritize_approval=prioritize_approval,
                    #     include_all_sessions=include_all_sessions
                    # )

                    # Check if the scenario simulation was successful
                    if scenario_traversal_data is None:
                        print(f"{Fore.YELLOW}    Scenario '{scenario_id}' produced no valid traversal. Flags not updated.{Style.RESET_ALL}")
                        # Store an indicator that this scenario failed/was skipped in results
                        chapter_run_data["scenario_results"][scenario_id] = {"status": "skipped_no_valid_path"}
                        # Keep current flags for the next scenario
                        scenario_final_flags = current_chapter_flags
                        # We still need to update current_chapter_flags at the end of the loop iteration
                        # continue # Optional: Decide if skipping means truly no flag update. Let's assume flags pass through.
                    else:
                        # Store results for this scenario
                        chapter_run_data["scenario_results"][scenario_id] = scenario_traversal_data

                    # Extract the single traversal result (assuming num_traversals=1)
                    # scenario_traversal_data = temp_traversals[0]

                    # --- Placeholder for flag update ---
                    # scenario_final_flags = current_chapter_flags # NO CHANGE YET
                    # TODO: Replace this with the actual flags returned by the modified simulate_single_traversal
                    # scenario_final_flags = set() # Dummy value
                    # print(f"{Fore.MAGENTA}    [Placeholder] Scenario finished. Flags need proper update mechanism.{Style.RESET_ALL}")
                    # --- End Placeholder ---


                    # Store results for this scenario
                    # chapter_run_data["scenario_results"][scenario_id] = scenario_traversal_data

                    # Update chapter flags for the next scenario in the sequence
                    current_chapter_flags = scenario_final_flags # This now uses the returned flags
                    print(f"{Fore.BLUE}    Updated chapter flags after {scenario_id}: {len(current_chapter_flags)}{Style.RESET_ALL}") # {current_chapter_flags}

                except Exception as e:
                    print(f"{Fore.RED}Error simulating scenario '{scenario_id}': {e}{Style.RESET_ALL}")
                    # Optionally store error info
                    chapter_run_data["scenario_results"][scenario_id] = {"error": str(e)}
                    # Decide whether to continue chapter traversal or stop
                    print(f"{Fore.YELLOW}Continuing chapter traversal despite error in scenario '{scenario_id}'.{Style.RESET_ALL}")
                    continue # Continue to next scenario

            # --- END SIMULATION LOOP ---

            # Store the final flags for this chapter run
            chapter_run_data["final_flags"] = list(current_chapter_flags) # Convert set to list for JSON
            self.chapter_traversal_results.append(chapter_run_data)

            print(f"{Fore.GREEN}Chapter Traversal {i+1} complete.{Style.RESET_ALL}")
            print(f"Final flag count for this run: {len(current_chapter_flags)}")

            # Export this specific chapter traversal if requested
            if export_txt:
                self._export_chapter_traversal_to_txt(chapter_run_data, f"chapter_{self.chapter_id}_traversal_{i+1}.txt")
            if export_json:
                self._export_chapter_traversal_to_json(chapter_run_data, f"chapter_{self.chapter_id}_traversal_{i+1}.json")

        print(f"{Fore.GREEN}Chapter simulation finished. Generated {len(self.chapter_traversal_results)} traversals.{Style.RESET_ALL}")
        return self.chapter_traversal_results


    def _export_chapter_traversal_to_txt(self, chapter_run_data, output_file):
        """Export a single chapter traversal run to a text file."""
        print(f"{Fore.GREEN}Exporting chapter traversal to {output_file}...{Style.RESET_ALL}")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"Baldur's Gate 3 Chapter Traversal\n\n")
            f.write(f"Chapter: {self.title} ({self.chapter_id})\n")
            f.write(f"Scenario Sequence: {' -> '.join(chapter_run_data['scenario_sequence'])}\n")
            f.write(f"Final Flags: {sorted(list(chapter_run_data['final_flags']))}\n\n")
            f.write(f"--- Traversal Details ---\n")

            for scenario_id in chapter_run_data['scenario_sequence']:
                f.write(f"================ Scenario: {scenario_id} ================\n")
                scenario_result = chapter_run_data['scenario_results'].get(scenario_id)

                if scenario_result is None:
                    f.write("Scenario produced no traversal data.\n")
                    continue
                if isinstance(scenario_result, dict) and "error" in scenario_result:
                    f.write(f"Error during scenario simulation: {scenario_result['error']}\n")
                    continue
                if not isinstance(scenario_result, dict) or "session_sequence" not in scenario_result:
                    f.write("Unexpected scenario result format.\n")
                    print(f"{Fore.YELLOW}Warning: Unexpected result format for scenario {scenario_id} during TXT export.{Style.RESET_ALL}")
                    continue # Skip if format is wrong

                f.write(f"Session Sequence: {' -> '.join(scenario_result.get('session_sequence', []))}\n")

                # Extract and format dialog from the scenario's sessions
                for session_id in scenario_result.get('session_sequence', []):
                    f.write(f"----- Session: {session_id} -----\n")                    
                    node_data_list = scenario_result.get('node_data', {}).get(session_id, [])

                    # Retrieve and write synopsis
                    synopsis = scenario_result.get('session_synopses', {}).get(session_id, 'Synopsis not found')
                    f.write(f"Synopsis: {synopsis}\n\n")

                    if not node_data_list:
                        f.write("No dialog data available for this session.\n")
                        continue

                    for node in node_data_list:
                        if not isinstance(node, dict): continue

                        if node.get('special_marker'):
                            f.write(f"[{node.get('id', 'SPECIAL_MARKER')}]\n")
                            continue

                        speaker = node.get('speaker', 'Unknown')
                        text = node.get('text', '')
                        context = node.get('context', '')
                        approval = node.get('approval', [])

                        if not text and not context: continue # Skip empty nodes?

                        line = ""
                        if node.get('node_type') == 'tagcinematic':
                            line = f"[description] {text}"
                        elif text: # Ensure text exists for speaker line
                            line = f"{speaker}: {text}"
                        elif context: # If only context exists
                            line = f"[context only] {context}"
                        else: # Skip if truly empty
                            continue


                        if context and text: # Add context only if text was present
                            line += f" || [context] {context}"
                        if approval:
                            line += f" || [approval] {approval}"
                        if ": true" in line.lower() or ": false" in line.lower():
                            continue
                        f.write(f"{line}\n")
                    f.write("\n") # Newline after session dialog

        print(f"{Fore.GREEN}Chapter traversal exported successfully to {output_file}{Style.RESET_ALL}")
        return output_file

    def _export_chapter_traversal_to_json(self, chapter_run_data, output_file):
        """Export a single chapter traversal run to a JSON file."""
        print(f"{Fore.GREEN}Exporting chapter traversal to {output_file}...{Style.RESET_ALL}")

        # We already have the structure in chapter_run_data
        # Just need to ensure sets are converted to lists (already done for final_flags)
        # Need to check if any other sets exist within scenario_results

        # Deep copy or careful modification needed if chapter_run_data is reused
        export_data = json.loads(json.dumps(chapter_run_data, default=list)) # Use json cycle to convert sets

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        print(f"{Fore.GREEN}Chapter traversal exported successfully to {output_file}{Style.RESET_ALL}")
        return output_file

# Example usage (if run directly)
def main():
    print(f"{Fore.CYAN}Baldur's Gate 3 Chapter Simulator{Style.RESET_ALL}")
    print("This tool simulates traversals through chapter files.")

    # Get chapter file path from arguments or input
    if len(sys.argv) > 1:
        chapter_folder = sys.argv[1]
    else:
        default_chapter = "output_merged/Act1/Chapel" # Example path - ADJUST AS NEEDED
        chapter_folder = input(f"Enter path to chapter definition file [default: {default_chapter}]: ")
        if not chapter_folder:
            chapter_folder = default_chapter
    if not os.path.exists(chapter_folder):
        print(f"{Fore.RED}Error: Chapter file not found: {chapter_folder}{Style.RESET_ALL}")
        return

    # Instantiate the simulator
    try:
        chapter_simulator = ChapterSimulator(chapter_folder)
    except SystemExit: # Catch exits from init errors
        return
    except Exception as e:
        print(f"{Fore.RED}Error initializing ChapterSimulator: {e}{Style.RESET_ALL}")
        return

    # --- Get Simulation Options ---
    num_traversals = 1
    try:
        num_input = input(f"Number of chapter traversals to generate [default: 1]: ")
        if num_input:
            num_traversals = int(num_input)
    except ValueError:
        print(f"{Fore.YELLOW}Invalid input. Using default value of 1.{Style.RESET_ALL}")

    min_utterances = 3
    try:
        min_utterances_input = input(f"Minimum utterances per session within scenarios [default: 3]: ")
        if min_utterances_input:
            min_utterances = int(min_utterances_input)
    except ValueError:
        print(f"{Fore.YELLOW}Invalid input. Using default value of 3.{Style.RESET_ALL}")

    prioritize_approval = input(f"Prioritize approval paths within scenarios? (y/n, default: y): ").lower() != 'n'
    include_all_scenarios = input(f"Try to include all possible scenarios in chapter? (y/n, default: y): ").lower() != 'n'
    include_all_sessions = input(f"Try to include all possible sessions within scenarios? (y/n, default: y): ").lower() != 'n'

    export_txt = input(f"{Fore.BLUE}Export chapter traversals to text files? (y/n, default: n):{Style.RESET_ALL} ").lower() == 'y'
    export_json = input(f"{Fore.BLUE}Export chapter traversals to JSON files? (y/n, default: n):{Style.RESET_ALL} ").lower() == 'y'

    # Ask for initial flags file
    initial_flags = None
    load_flags_choice = input(f"{Fore.BLUE}Load initial flags from a JSON file? (y/n, default: n):{Style.RESET_ALL} ").lower() == 'y'
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

    # --- Run Simulation ---
    # IMPORTANT: This will run with placeholder logic until ScenarioSimulator/DialogSimulator are modified
    # print(f"{Back.RED}{Fore.WHITE}WARNING: Running simulation with PLACEHOLDER flag logic.{Back.RESET}{Style.RESET_ALL}")
    # print(f"{Fore.YELLOW}Flags will NOT persist correctly between scenarios until modifications are made.{Style.RESET_ALL}")
    print(f"{Fore.GREEN}Running simulation with updated flag persistence logic.{Style.RESET_ALL}")

    results = chapter_simulator.simulate_chapter(
        num_traversals=num_traversals,
        export_txt=export_txt,
        export_json=export_json,
        min_utterances_per_session=min_utterances,
        prioritize_approval=prioritize_approval,
        include_all_scenarios=include_all_scenarios,
        include_all_sessions=include_all_sessions,
        initial_flags_set=initial_flags # Pass the loaded flags here
    )

    print(f"{Fore.GREEN}Chapter simulation run complete. Generated {len(results)} traversals.{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Remember to implement the flag passing modifications in ScenarioSimulator and DialogSimulator for correct behavior.{Style.RESET_ALL}")


if __name__ == "__main__":
    # Need a sample chapter definition file to run this main section
    # Example: chapters/Act1/ChapelExploration.json
    # {
    #   "chapter_id": "Act1_ChapelExploration",
    #   "title": "Exploring the Chapel Ruins",
    #   "scenarios": [
    #     "output_merged/Act1/Chapel/cha_outside.json",
    #     "output_merged/Act1/Chapel/cha_crypt.json"
    #   ],
    #   "metadata": {
    #     "automatic_ordering": {
    #       "order": [
    #         {"predecessor": ["output_merged/Act1/Chapel/cha_outside.json"], "successor": "output_merged/Act1/Chapel/cha_crypt.json"}
    #       ],
    #       "exclusive": []
    #     }
    #   }
    # }
    # Ensure the referenced scenario JSON files exist.
    # You might need to create the 'chapters/Act1' directory.
    main() 