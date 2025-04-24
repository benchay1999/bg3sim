import json
import sys
import os
import random # Keep random in case we need to select *one* fallback later, though currently listing all
from colorama import init, Fore, Style
# Assuming dialog_simulator.py is in the same directory or accessible
try:
    from dialog_simulator import DialogSimulator
except ImportError:
    print(f"{Fore.RED}Error: dialog_simulator.py not found. Make sure it's in the same directory or Python path.{Style.RESET_ALL}")
    sys.exit(1)

# Initialize colorama for colored terminal output
init(autoreset=True)

class ScenarioApprovalExplorer:
    """
    Explores a scenario file to find all valid session sequences.
    For each session, it lists all dialogue paths containing approval nodes.
    If no approval paths exist for a session, it lists paths meeting a
    minimum utterance requirement as a fallback.
    """

    def __init__(self, scenario_file):
        """Initialize the scenario explorer with the specified scenario JSON file"""
        try:
            with open(scenario_file, 'r', encoding='utf-8') as f:
                self.scenario = json.load(f)
        except FileNotFoundError:
            print(f"{Fore.RED}Error: Scenario file not found at {scenario_file}{Style.RESET_ALL}")
            sys.exit(1)
        except json.JSONDecodeError:
            print(f"{Fore.RED}Error: Invalid JSON format in {scenario_file}{Style.RESET_ALL}")
            sys.exit(1)

        self.scenario_name = os.path.basename(scenario_file).split('.json')[0]
        self.metadata = self.scenario.get("metadata", {})
        self.sessions = self.metadata.get("source_files", [])
        if not self.sessions:
            print(f"{Fore.YELLOW}Warning: No 'source_files' found in metadata for {scenario_file}. Cannot identify sessions.{Style.RESET_ALL}")
            self.session_ids = []
        else:
            self.session_ids = [self._get_session_id_from_filename(s) for s in self.sessions]

        # Parse ordering constraints
        self.ordering = []
        for order in self.metadata.get("automatic_ordering", {}).get("order", []):
            pred = order.get("predecessor", [])
            succ = order.get("successor", "")
            if pred and succ:
                for p in pred:
                    # Ensure predecessor and successor exist in identified sessions
                    if p in self.session_ids and succ in self.session_ids:
                         self.ordering.append((p, succ))

        # Parse exclusivity constraints
        self.exclusivity = []
        for excl_group in self.metadata.get("automatic_ordering", {}).get("exclusive", []):
            valid_excl_group = [s for s in excl_group if s in self.session_ids]
            if len(valid_excl_group) >= 2:
                self.exclusivity.append(valid_excl_group)

        print(f"Loaded scenario '{self.scenario_name}' with {len(self.session_ids)} sessions.")
        if self.ordering:
            print(f"Ordering constraints: {self.ordering}")
        if self.exclusivity:
            print(f"Exclusivity constraints: {self.exclusivity}")

        self.session_simulators = {}
        self.session_all_paths = {} # Store ALL possible paths for each session
        self.session_approval_paths = {} # Store paths with approvals for each session
        self.session_approval_nodes = {} # Store approval nodes for each session
        self.session_path_utterances = {} # Store utterance count per path {session_id: {path_tuple: count}}


    def _flatten_dialog_nodes(self, nodes_dict):
        """Flattens nested dialog nodes into a single dictionary."""
        flat_nodes = {}
        nodes_to_visit = list(nodes_dict.values())
        processed_ids = set()

        while nodes_to_visit:
            node_data = nodes_to_visit.pop(0)
            node_id = node_data.get("id")

            if not node_id or node_id in processed_ids:
                continue

            processed_ids.add(node_id)
            flat_nodes[node_id] = node_data

            children = node_data.get("children", {})
            if isinstance(children, dict):
                nodes_to_visit.extend(list(children.values()))
            elif isinstance(children, list):
                nodes_to_visit.extend(children)

        return flat_nodes

    def _get_session_id_from_filename(self, filename):
        """Extract session ID from filename relative to scenario name."""
        basename = filename.split('.json')[0]
        parts = basename.replace('\\', '/').split('/')
        try:
            # Try finding the scenario name part and taking the next part
            scenario_index = parts.index(self.scenario_name)
            if scenario_index + 1 < len(parts):
                return parts[scenario_index + 1]
            else: # Scenario name is last part, fallback to just the name
                return parts[-1]
        except ValueError:
            # Scenario name not found, fallback to just the filename part
            # This might happen if structure is different (e.g., Flat_*.json)
            # Use the last part as the most likely session identifier
             # Example: FOR_BottomlessWell_InteractWithWell.json -> InteractWithWell (if scenario is FOR_BottomlessWell)
             # Example: CHA_Outside_AD_BanditsDiscussion.json -> AD_BanditsDiscussion (if scenario is CHA_Outside)
            if len(parts) > 1 and parts[-2] == self.scenario_name: # Check if scenario name is the second to last part
                 return parts[-1]

             # Fallback: Try to remove a common prefix pattern like XXX_YYY_
            potential_id = parts[-1]
            id_parts = potential_id.split('_')
            # Simple heuristic: if first few parts match known area codes (like CHA_, FOR_, etc.) remove them
            # This is brittle and depends on naming conventions
            known_prefixes = ["ADV", "CAMP", "CHA", "CRE", "DEN", "END", "FOR", "GBL", "GOB", "GRY", "HAG", "LOW", "MH", "MYR", "OUT", "PRO", "RIS", "ROS", "SHA", "SUN", "TUT", "UND", "UNK"]
            if len(id_parts) > 2 and id_parts[0] in known_prefixes and id_parts[1].isupper(): # e.g., CHA_Outside_Something -> Something
                potential_id = '_'.join(id_parts[2:])

            # If still contains the scenario name, remove it
            if self.scenario_name in potential_id:
                potential_id = potential_id.replace(f"{self.scenario_name}_", "")


            if potential_id != parts[-1]:
                print(f"{Fore.YELLOW}Warning: Guessed Session ID '{potential_id}' from '{parts[-1]}' based on patterns.{Style.RESET_ALL}")

            return potential_id


    def _extract_session_prefix(self, node_id):
        """Extract the session prefix from a node ID."""
        parts = node_id.split('_')
        if len(parts) > 1 and parts[-1].isdigit():
            return '_'.join(parts[:-1])
        return node_id


    def _validate_sequence(self, sequence):
        """Validate sequence against ordering and exclusivity."""
        # Check ordering
        for pred, succ in self.ordering:
            if pred in sequence and succ in sequence:
                pred_indices = [i for i, s in enumerate(sequence) if s == pred]
                succ_indices = [i for i, s in enumerate(sequence) if s == succ]
                if not pred_indices or not succ_indices or max(pred_indices) >= min(succ_indices):
                    return False

        # Check exclusivity
        for excl_group in self.exclusivity:
            count = sum(1 for s in excl_group if s in sequence)
            if count > 1:
                return False

        return True

    def _generate_all_valid_sequences(self):
        """Generate all valid sequences respecting constraints."""
        valid_sequences = []
        active_sessions = list(self.session_simulators.keys()) # Use only successfully simulated sessions

        # Group sessions by exclusivity constraints
        exclusive_groups_processed = set()
        independent_sessions = list(active_sessions)
        grouped_choices = []

        # Use the class's exclusivity list
        for group in self.exclusivity:
             # Filter group based on currently active sessions
            current_group_valid_sessions = [s for s in group if s in active_sessions]
            if not current_group_valid_sessions: continue

            grouped_choices.append(current_group_valid_sessions)
            for session in current_group_valid_sessions:
                if session in independent_sessions:
                    independent_sessions.remove(session)
                exclusive_groups_processed.add(session)

        all_choices = grouped_choices + [[s] for s in independent_sessions]

        # Recursive function to build combinations
        def find_combinations(index, current_combination):
            if index == len(all_choices):
                if current_combination:
                    yield current_combination[:]
                return

            group = all_choices[index]
            # Option 1: Skip this group
            yield from find_combinations(index + 1, current_combination)
            # Option 2: Choose one session from this group
            for session in group:
                current_combination.append(session)
                yield from find_combinations(index + 1, current_combination)
                current_combination.pop()

        potential_combinations = list(find_combinations(0, []))
        # print(f"Generated {len(potential_combinations)} potential session combinations respecting exclusivity.")

        final_valid_sequences = []
        processed_permutations = set()
        from itertools import permutations

        for combo in potential_combinations:
            if not combo: continue
            for seq_tuple in permutations(combo):
                 seq = list(seq_tuple)
                 seq_key = tuple(seq)
                 if seq_key in processed_permutations: continue

                 # Use the class's ordering list for validation
                 if self._validate_sequence(seq):
                    final_valid_sequences.append(seq)
                    processed_permutations.add(seq_key)

        final_valid_sequences.sort(key=len, reverse=True)
        print(f"Found {len(final_valid_sequences)} valid session sequences after checking ordering.")
        return final_valid_sequences

    def _count_utterances(self, session_id, path):
         """Counts nodes with non-empty 'text' in a given path for a session."""
         # Check cache first
         path_tuple = tuple(path) # Use tuple as dict key
         if session_id in self.session_path_utterances and path_tuple in self.session_path_utterances[session_id]:
             return self.session_path_utterances[session_id][path_tuple]

         simulator = self.session_simulators.get(session_id)
         if not simulator or not path:
             return 0

         utterance_count = 0
         for node_id in path:
             if not isinstance(node_id, str) or node_id in ["MAX_DEPTH_REACHED", "NODE_NOT_FOUND"]:
                 continue

             # Use simulator's internal method if available, otherwise access all_nodes
             node = simulator._get_node(node_id) # Assuming _get_node exists and is safe
             # node = simulator.all_nodes.get(node_id) # Alternative if _get_node is not reliable

             if node and node.get('text', '').strip(): # Count nodes with actual text content
                 utterance_count += 1

         # Cache the result
         if session_id not in self.session_path_utterances:
             self.session_path_utterances[session_id] = {}
         self.session_path_utterances[session_id][path_tuple] = utterance_count

         return utterance_count


    def _prepare_session_simulation(self, session_id):
        """Prepares and runs the simulation for a single session."""
        if session_id in self.session_simulators:
            return self.session_simulators[session_id]

        print(f"{Fore.YELLOW}Preparing simulation for session: {session_id}{Style.RESET_ALL}")

        session_dialog = {}
        dialog_nodes = self.scenario.get("dialogue", {})
        if not dialog_nodes:
             print(f"{Fore.RED}Error: No 'dialogue' key found.{Style.RESET_ALL}")
             return None

        found_nodes = False
        for node_id, node_data in dialog_nodes.items():
             # Adjust matching logic if necessary based on observed node IDs
            if node_id.startswith(session_id + '_') or node_id == session_id:
                session_dialog[node_id] = node_data
                found_nodes = True
            # Fallback check using prefix extraction (might be less precise)
            elif self._extract_session_prefix(node_id) == session_id:
                 session_dialog[node_id] = node_data
                 found_nodes = True

        if not found_nodes:
            print(f"{Fore.RED}No dialog nodes found matching session '{session_id}'. Check naming convention.{Style.RESET_ALL}")
            return None

        flat_session_dialog = self._flatten_dialog_nodes(session_dialog)
        if not flat_session_dialog: flat_session_dialog = session_dialog # Fallback
        if not flat_session_dialog:
            print(f"{Fore.RED}Error: No dialog data for session {session_id}{Style.RESET_ALL}")
            return None

        temp_dir = "temp_sim_files"
        os.makedirs(temp_dir, exist_ok=True)
        temp_file = os.path.join(temp_dir, f"temp_{session_id}.json")
        temp_data = {
            "metadata": {}, # Minimal metadata
            "dialogue": flat_session_dialog
        }

        try:
            with open(temp_file, 'w', encoding='utf-8') as f: json.dump(temp_data, f, indent=2)
        except IOError as e:
             print(f"{Fore.RED}Error writing temp file {temp_file}: {e}{Style.RESET_ALL}"); return None

        try:
            simulator = DialogSimulator(temp_file)
            self.session_simulators[session_id] = simulator
        except Exception as e:
            print(f"{Fore.RED}Error initializing DialogSimulator for {session_id}: {e}{Style.RESET_ALL}")
            try: os.remove(temp_file)
            except OSError: pass
            return None

        try:
            paths, _, _, _ = simulator.simulate_all_paths(max_depth=30, print_paths=False, test_mode=True, verbose=False)
            self.session_all_paths[session_id] = paths
            # Pre-calculate utterances for all paths now
            if session_id not in self.session_path_utterances: self.session_path_utterances[session_id] = {}
            for path in paths:
                self._count_utterances(session_id, path) # This will calculate and cache

            print(f"  Found {len(paths)} total paths for session {session_id}.")
        except Exception as e:
             print(f"{Fore.RED}Error during simulate_all_paths for {session_id}: {e}{Style.RESET_ALL}")
             self.session_all_paths[session_id] = []

        try:
            os.remove(temp_file)
            if not os.listdir(temp_dir): os.rmdir(temp_dir)
        except OSError: pass # Ignore cleanup errors

        return simulator

    def _find_session_approval_details(self, session_id):
        """Finds approval nodes and paths for a given session."""
        if session_id in self.session_approval_paths:
            return self.session_approval_paths[session_id], self.session_approval_nodes.get(session_id, [])

        simulator = self.session_simulators.get(session_id)
        if not simulator:
            print(f"{Fore.RED}Simulator not ready for {session_id}.{Style.RESET_ALL}")
            return [], []

        approval_nodes = []
        for node_id, node_data in simulator.all_nodes.items():
            if node_data.get('approval'):
                approval_nodes.append(node_id)
        self.session_approval_nodes[session_id] = approval_nodes

        if not approval_nodes:
             # print(f"  No approval nodes found in session {session_id}.") # Reduce noise
             self.session_approval_paths[session_id] = []
             return [], approval_nodes

        all_paths = self.session_all_paths.get(session_id, [])
        approval_paths_list = []
        for path in all_paths:
            if any(node_id in approval_nodes for node_id in path if isinstance(node_id, str)):
                approval_paths_list.append(path)

        self.session_approval_paths[session_id] = approval_paths_list
        if approval_paths_list:
            print(f"  Session {session_id}: Found {len(approval_nodes)} approval nodes and {len(approval_paths_list)} approval paths.")
        # else: # Should not happen if approval_nodes is non-empty, but safeguard
             # print(f"  Session {session_id}: Found approval nodes but no paths visiting them?")

        return approval_paths_list, approval_nodes


    def explore_scenario_approvals(self, output_json_file=None, min_utterances=3):
        """
        Explore the scenario, finding valid sequences and their paths.
        Prioritizes approval paths, falls back to paths meeting min_utterances.

        Args:
            output_json_file (str, optional): Path to export JSON. Defaults to None.
            min_utterances (int): Minimum utterances for fallback paths. Defaults to 3.

        Returns:
            list: A list of dictionaries, each representing a valid trajectory.
                  Each trajectory contains 'sequence' and 'session_paths' (dict mapping
                  session ID to {'type': 'approval'|'fallback', 'paths': [...]}).
        """
        print(f"\n{Fore.CYAN}===== SCENARIO APPROVAL EXPLORER (with Fallback) ====={Style.RESET_ALL}")
        print(f"Analyzing scenario: {self.scenario_name}")
        print(f"Minimum utterances for fallback: {min_utterances}")

        # 1. Prepare simulation & find approvals for all sessions
        for session_id in self.session_ids:
            simulator = self._prepare_session_simulation(session_id)
            if simulator:
                self._find_session_approval_details(session_id)
            else:
                 print(f"{Fore.RED}Failed to prepare simulation for session: {session_id}. It will be excluded.{Style.RESET_ALL}")

        # 2. Generate all valid session sequences based on successfully simulated sessions
        valid_sequences = self._generate_all_valid_sequences()

        if not valid_sequences:
            print(f"{Fore.RED}No valid session sequences found respecting constraints.{Style.RESET_ALL}")
            return []

        print(f"\nFound {len(valid_sequences)} valid session sequences.")

        # 3. Collect paths (approval or fallback) for each session in each valid sequence
        all_trajectories = []

        for i, seq in enumerate(valid_sequences):
            trajectory_data = {
                "sequence": seq,
                "session_paths": {} # Changed key name
            }
            is_valid_trajectory = True # Assume valid until a session has NO suitable paths

            # print(f"\nProcessing Sequence {i+1}/{len(valid_sequences)}: {seq}")

            for session_id in seq:
                approval_paths = self.session_approval_paths.get(session_id, [])

                if approval_paths:
                    # Priority: Use approval paths
                    trajectory_data["session_paths"][session_id] = {
                        "type": "approval",
                        "paths": approval_paths
                    }
                    # print(f"  Session {session_id}: Using {len(approval_paths)} approval paths.")
                else:
                    # Fallback: Find paths meeting min_utterances
                    all_paths = self.session_all_paths.get(session_id, [])
                    fallback_paths = []
                    if all_paths: # Only search if paths were generated
                        for path in all_paths:
                            # Use the pre-calculated/cached utterance count
                            utterance_count = self._count_utterances(session_id, path)
                            if utterance_count >= min_utterances:
                                fallback_paths.append(path)

                    if fallback_paths:
                        trajectory_data["session_paths"][session_id] = {
                            "type": "fallback",
                            "paths": fallback_paths
                        }
                        # print(f"  Session {session_id}: No approval paths. Using {len(fallback_paths)} fallback paths (>= {min_utterances} utterances).")
                    else:
                         # Critical: No approval paths AND no fallback paths found
                         trajectory_data["session_paths"][session_id] = {
                            "type": "none",
                            "paths": []
                         }
                         print(f"  {Fore.YELLOW}Warning: Session {session_id} in sequence {seq} has NO approval paths and NO fallback paths meeting min utterances.{Style.RESET_ALL}")
                         # Optionally, decide if this makes the whole trajectory invalid
                         # is_valid_trajectory = False
                         # break # Stop processing this sequence if one session fails

            # Add the trajectory regardless of whether all sessions had paths,
            # unless you specifically want to exclude sequences where some sessions fail
            # if is_valid_trajectory:
            all_trajectories.append(trajectory_data)

        print(f"\nGenerated {len(all_trajectories)} potential trajectories.")
        # Filter out trajectories where *all* sessions ended up with "none" type? Maybe not necessary.

        # 4. Export results if requested
        if output_json_file:
            print(f"\nExporting results to {output_json_file}...")
            try:
                # Export all collected trajectories
                with open(output_json_file, 'w', encoding='utf-8') as f:
                    json.dump(all_trajectories, f, indent=2, ensure_ascii=False)
                print(f"{Fore.GREEN}Successfully exported {len(all_trajectories)} trajectories to {output_json_file}{Style.RESET_ALL}")
            except IOError as e:
                print(f"{Fore.RED}Error exporting results to JSON: {e}{Style.RESET_ALL}")
            except TypeError as e:
                 print(f"{Fore.RED}Error serializing results to JSON: {e}{Style.RESET_ALL}")


        return all_trajectories

def main():
    print(f"{Fore.CYAN}Baldur's Gate 3 Scenario Approval Explorer (with Fallback){Style.RESET_ALL}")
    print("Finds all valid sequences; lists approval paths or fallback paths meeting min utterances.")

    if len(sys.argv) > 1:
        scenario_file = sys.argv[1]
    else:
        scenario_file = input("Enter path to scenario JSON file: ")
        if not scenario_file:
             default_file = "output_merged/Act1/Chapel/cha_outside.json" # Example default
             print(f"No file entered, attempting default: {default_file}")
             scenario_file = default_file


    if not os.path.isfile(scenario_file):
        print(f"{Fore.RED}Error: File not found: {scenario_file}{Style.RESET_ALL}")
        return

    # Get minimum utterances option
    min_utterances = 3
    try:
        min_utterances_input = input(f"Minimum utterances for fallback paths [default: 3]: ")
        if min_utterances_input:
            min_utterances = int(min_utterances_input)
            if min_utterances < 0: min_utterances = 0
    except ValueError:
        print(f"{Fore.YELLOW}Invalid input. Using default value of 3.{Style.RESET_ALL}")


    output_filename_default = f"{os.path.basename(scenario_file).split('.')[0]}_all_trajectories.json"
    output_json = input(f"Enter output JSON filename [default: {output_filename_default}]: ")
    if not output_json:
        output_json = output_filename_default

    explorer = ScenarioApprovalExplorer(scenario_file)
    results = explorer.explore_scenario_approvals(
        output_json_file=output_json,
        min_utterances=min_utterances
        )

    if results:
        # Check if any session actually used fallback paths
        fallbacks_used = any(
            details['type'] == 'fallback'
            for traj in results
            for session_id, details in traj['session_paths'].items()
        )
        none_found = any(
             details['type'] == 'none'
            for traj in results
            for session_id, details in traj['session_paths'].items()
        )

        print(f"\n{Fore.GREEN}Exploration complete. Found {len(results)} trajectories.{Style.RESET_ALL}")
        if fallbacks_used:
             print(f"{Fore.CYAN}Fallback paths (min {min_utterances} utterances) were used for some sessions without approval paths.{Style.RESET_ALL}")
        if none_found:
             print(f"{Fore.YELLOW}Warning: Some sessions had neither approval nor suitable fallback paths.{Style.RESET_ALL}")

    else:
        print(f"\n{Fore.YELLOW}Exploration complete. No valid trajectories were generated.{Style.RESET_ALL}")

if __name__ == "__main__":
    main()