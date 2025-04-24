import json
import sys
import os
import random
from colorama import init, Fore, Back, Style
from dialog_simulator import DialogSimulator

# Initialize colorama for colored terminal output
init()

class ScenarioSimulator:
    """
    Simulates traversals through a scenario file containing multiple sessions.
    Respects ordering constraints and exclusivity between sessions.
    """
    
    def __init__(self, scenario_file):
        """Initialize the scenario simulator with the specified scenario JSON file"""
        with open(scenario_file, 'r', encoding='utf-8') as f:
            self.scenario = json.load(f)
        self.scenario_name = scenario_file.split('/')[-1].split('.json')[0]
        # Parse metadata
        self.metadata = self.scenario["metadata"]
        self.sessions = self.metadata.get("source_files", [])
        self.session_ids = [self._get_session_id_from_filename(s) for s in self.sessions]
        
        # Parse ordering constraints
        self.ordering = []
        for order in self.metadata.get("automatic_ordering", {}).get("order", []):
            pred = order.get("predecessor", [])
            succ = order.get("successor", "")
            if pred and succ:
                for p in pred:
                    self.ordering.append((p, succ))
        
        # Parse exclusivity constraints
        self.exclusivity = []
        for excl in self.metadata.get("automatic_ordering", {}).get("exclusive", []):
            if len(excl) >= 2:
                self.exclusivity.append(excl)
        
        print(f"Loaded scenario with {len(self.sessions)} sessions")
        print(f"Ordering constraints: {self.ordering}")
        print(f"Exclusivity constraints: {self.exclusivity}")
        
        # Initialize session simulators
        self.session_simulators = {}
        self.session_path_options = {}  # Store possible paths for each session
        
        # For tracking the generated traversal
        self.traversal_sequence = []  # Sequence of session IDs
        self.traversal_paths = []     # Actual node paths for each session
        self.traversal_nodes = []     # Detailed node data from traversals
        
    def _get_session_id_from_filename(self, filename):
        """
        Extract session ID from filename
        
        Examples:
        'CHA_Outside_AD_BanditsDiscussion.json' -> 'AD_BanditsDiscussion'
        'CHA_Outside_EntranceDoor.json' -> 'EntranceDoor'
        'FOR_BottomlessWell_InteractWithWell.json' -> 'BottomlessWell_InteractWithWell'
        """
        # Remove the file extension
        basename = filename.split('.json')[0]
        scenario_name = self.scenario_name
        filename_after_scenario_name = basename[len(scenario_name)+1:]
        return filename_after_scenario_name
        # get the name of the 
    
    def _extract_session_prefix(self, node_id):
        """
        Extract the session prefix from a node ID
        Examples:
        - BanditsDiscussion_1 -> BanditsDiscussion
        - InteractWithWell_5 -> InteractWithWell
        - VB_LockpickingCrypt_1_WithShadowheart_13 -> VB_LockpickingCrypt_1_WithShadowheart
        """
        # Find the last underscore and extract everything before it
        if '_' in node_id:
            return node_id.rsplit('_', 1)[0]
        return node_id  # If no underscore, return the whole ID
    
    def _is_exclusive(self, session1, session2):
        """Check if two sessions are exclusive (cannot both be in a traversal)"""
        for excl_group in self.exclusivity:
            if session1 in excl_group and session2 in excl_group:
                return True
        return False
    
    def _get_successors(self, session):
        """Get all sessions that must come after the given session"""
        return [succ for pred, succ in self.ordering if pred == session]
    
    def _get_predecessors(self, session):
        """Get all sessions that must come before the given session"""
        return [pred for pred, succ in self.ordering if succ == session]
    
    def _validate_sequence(self, sequence):
        """Validate that a sequence of sessions respects all constraints"""
        # Check ordering constraints
        for pred, succ in self.ordering:
            if pred in sequence and succ in sequence:
                if sequence.index(pred) >= sequence.index(succ):
                    return False
        
        # Check exclusivity constraints
        for excl_group in self.exclusivity:
            count = sum(1 for s in excl_group if s in sequence)
            if count > 1:
                return False
        
        return True
    
    def _generate_valid_sequences(self):
        """Generate all valid sequences of sessions respecting constraints"""
        # Start with possible sequences including all non-exclusive sessions
        all_sequences = []
        
        # First, group sessions by exclusivity
        excl_groups = {}
        # Initialize with all sessions as their own group
        for session in self.session_ids:
            excl_groups[session] = [session]
        
        # Merge groups of exclusive sessions
        for excl_group in self.exclusivity:
            if len(excl_group) >= 2:
                # Find the first session in the group that's already in excl_groups
                base_session = None
                for s in excl_group:
                    if s in excl_groups:
                        base_session = s
                        break
                
                if base_session:
                    # Add all sessions in this exclusivity group to the same group
                    for s in excl_group:
                        if s != base_session and s in excl_groups:
                            # Merge this session's group into the base session's group
                            excl_groups[base_session].extend(excl_groups[s])
                            # Remove the merged session's group
                            del excl_groups[s]
        
        # Now we have groups of exclusive sessions
        # We'll generate all possible combinations by picking at most one session from each group
        choice_groups = list(excl_groups.values())
        
        # Generate all possible sequences
        def generate_sequences(current_seq, remaining_groups):
            if not remaining_groups:
                if self._validate_sequence(current_seq):
                    all_sequences.append(current_seq.copy())
                return
            
            group = remaining_groups[0]
            
            # Try skipping this group entirely
            generate_sequences(current_seq, remaining_groups[1:])
            
            # Try each session in the group
            for session in group:
                new_seq = current_seq + [session]
                if self._validate_sequence(new_seq):
                    generate_sequences(new_seq, remaining_groups[1:])
        
        generate_sequences([], choice_groups)
        
        # Sort sequences by topological order based on ordering constraints
        valid_sequences = []
        for seq in all_sequences:
            # Check that all ordering constraints are satisfied
            # (already checked in validate_sequence, but double-check here)
            if self._validate_sequence(seq):
                valid_sequences.append(seq)
        
        # Sort by length (prefer longer sequences)
        valid_sequences.sort(key=len, reverse=True)
        
        return valid_sequences
    
    def _simulate_session(self, session_id):
        """
        Simulate a single session dialog and return possible paths
        
        Args:
            session_id (str): The session ID to simulate
            
        Returns:
            list: List of possible dialog paths for this session
        """
        # Check if we've already simulated this session
        if session_id in self.session_path_options:
            return self.session_path_options[session_id]
        
        print(f"{Fore.YELLOW}Simulating session: {session_id}{Style.RESET_ALL}")
        
        # Extract the dialog subtree for this session from the scenario
        session_dialog = {}
        for node_id, node_data in self.scenario["dialogue"].items():
            # Check if this node belongs to the session by comparing the prefix
            node_prefix = self._extract_session_prefix(node_id)
            if node_prefix == session_id:
                session_dialog[node_id] = node_data
        
        if not session_dialog:
            print(f"{Fore.RED}No dialog found for session {session_id}{Style.RESET_ALL}")
            return []
        
        # Create a temporary JSON file for this session
        temp_file = f"temp_{session_id}.json"
        temp_data = {
            "metadata": {
                "synopsis": self.metadata.get("individual_metadata", {}).get(session_id, {}).get("synopsis", ""),
                "how_to_trigger": self.metadata.get("individual_metadata", {}).get(session_id, {}).get("how_to_trigger", "")
            },
            "dialogue": session_dialog
        }
        
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(temp_data, f, indent=2)
        
        # Create a dialog simulator for this session
        simulator = DialogSimulator(temp_file)
        self.session_simulators[session_id] = simulator
        
        # Simulate all possible paths for this session
        paths, _, _, _ = simulator.simulate_all_paths(
            max_depth=20,
            print_paths=False,
            test_mode=True,  # Ignore flag requirements for simulation
            verbose=False
        )
        
        # Store the paths for this session
        self.session_path_options[session_id] = paths
        
        # Clean up temp file
        os.remove(temp_file)
        
        print(f"{Fore.GREEN}Found {len(paths)} possible paths for session {session_id}{Style.RESET_ALL}")
        
        return paths
    
    def _choose_random_path(self, session_id, min_utterances=3, max_attempts=10):
        """
        Choose a random path from the available paths for a session,
        preferring leaf node paths (complete dialogs) with at least min_utterances.
        
        Args:
            session_id (str): The session ID
            min_utterances (int): Minimum number of text utterances required in the path
            max_attempts (int): Maximum number of attempts to find a suitable path
            
        Returns:
            list: The chosen path
        """
        paths = self.session_path_options.get(session_id, [])
        if not paths:
            print(f"{Fore.RED}No paths available for session {session_id}{Style.RESET_ALL}")
            return []
        
        # Get simulator for this session
        simulator = self.session_simulators.get(session_id)
        if not simulator:
            print(f"{Fore.RED}No simulator found for session {session_id}{Style.RESET_ALL}")
            return random.choice(paths)  # Fall back to random choice
        
        # Function to count utterances (nodes with text) in a path
        def count_utterances(path):
            if not path:
                return 0
                
            utterance_count = 0
            for node_id in path:
                if node_id in ["MAX_DEPTH_REACHED", "NODE_NOT_FOUND"]:
                    continue
                    
                node = simulator._get_node(node_id)
                if node and node.get('text'):
                    utterance_count += 1
            
            return utterance_count
        
        # Try to find paths with the required minimum utterances
        suitable_paths = []
        for path in paths:
            # Check if path ends at a leaf node (preferred)
            is_leaf = path and simulator._is_leaf_node(path[-1])
            
            # Count utterances in the path
            utterances = count_utterances(path)
            
            # Store path data for selection
            suitable_paths.append({
                'path': path,
                'is_leaf': is_leaf,
                'utterances': utterances
            })
        
        # First, try to find paths that meet the minimum utterance requirement
        min_utterance_paths = [p for p in suitable_paths if p['utterances'] >= min_utterances]
        
        if min_utterance_paths:
            # Among suitable paths, prefer those that end at leaf nodes
            leaf_paths = [p for p in min_utterance_paths if p['is_leaf']]
            if leaf_paths:
                # If we have suitable leaf paths, choose randomly from them
                chosen_path = random.choice(leaf_paths)
                print(f"{Fore.GREEN}Found suitable leaf path for {session_id} with {chosen_path['utterances']} utterances{Style.RESET_ALL}")
                return chosen_path['path']
            else:
                # Otherwise choose from any suitable path
                chosen_path = random.choice(min_utterance_paths)
                print(f"{Fore.GREEN}Found suitable non-leaf path for {session_id} with {chosen_path['utterances']} utterances{Style.RESET_ALL}")
                return chosen_path['path']
        
        # If we couldn't find any path with min_utterances, log and select the one with most utterances
        print(f"{Fore.YELLOW}No paths with {min_utterances}+ utterances found for {session_id}. Using best available.{Style.RESET_ALL}")
        
        # Sort by utterance count (descending) and then by leaf status
        suitable_paths.sort(key=lambda p: (p['utterances'], p['is_leaf']), reverse=True)
        
        if suitable_paths:
            best_path = suitable_paths[0]
            print(f"{Fore.YELLOW}Best available path has {best_path['utterances']} utterances{Style.RESET_ALL}")
            return best_path['path']
        
        # Fallback to random choice if something went wrong
        return random.choice(paths)
    
    def _traverse_session_path(self, session_id, path):
        """
        Traverse a session's dialog path node by node, simulating the dialog flow.
        
        Args:
            session_id (str): The session ID
            path (list): A list of node IDs representing the path to traverse
            
        Returns:
            list: List of detailed node data from the traversal
        """
        if not path:
            return []
        
        simulator = self.session_simulators.get(session_id)
        if not simulator:
            print(f"{Fore.RED}No simulator found for session {session_id}{Style.RESET_ALL}")
            return []
        
        print(f"{Fore.CYAN}Traversing dialog path for session {session_id} ({len(path)} nodes){Style.RESET_ALL}")
        
        # Reset the simulator's state before traversing
        simulator.reset_state()
        
        traversed_nodes = []
        for i, node_id in enumerate(path):
            if node_id in ["MAX_DEPTH_REACHED", "NODE_NOT_FOUND"]:
                traversed_nodes.append({
                    "id": node_id,
                    "special_marker": True
                })
                continue
                
            # Get the node
            current_node_id, current_node = simulator.follow_node_path(node_id)
            
            if not current_node:
                print(f"{Fore.RED}Node {node_id} not found in session {session_id}{Style.RESET_ALL}")
                continue
                
            # Display the node for visual feedback
            simulator.display_node(current_node_id, current_node)
            
            # Process approvals and flags
            simulator._process_approvals(current_node)
            simulator._process_setflags(current_node)
            
            # Add to traversed nodes
            traversed_nodes.append({
                "id": current_node_id,
                "speaker": current_node.get('speaker', 'Unknown'),
                "text": current_node.get('text', ''),
                "node_type": current_node.get('node_type', 'normal'),
                "checkflags": current_node.get('checkflags', []),
                "setflags": current_node.get('setflags', []),
                "goto": current_node.get('goto', ''),
                "link": current_node.get('link', ''),
                "is_end": current_node.get('is_end', False),
                "approval": current_node.get('approval', []),
                "context": current_node.get('context', '')
            })
            
            # If this is the last node in the path and it's an end node,
            # we've reached the end of the dialog
            if i == len(path) - 1 and current_node.get('is_end', False):
                print(f"{Fore.GREEN}Reached end node of session {session_id}{Style.RESET_ALL}")
                break
        
        # Print summary
        meaningful_nodes = [n for n in traversed_nodes if n.get('text')]
        print(f"{Fore.GREEN}Traversed {len(traversed_nodes)} nodes in session {session_id} ({len(meaningful_nodes)} with dialog){Style.RESET_ALL}")
        
        return traversed_nodes
    
    def simulate_scenario(self, num_traversals=1, export_txt=False, export_json=False, min_utterances=3):
        """
        Simulate traversals through the scenario
        
        Args:
            num_traversals (int): Number of traversals to generate
            export_txt (bool): Whether to export traversals to text files
            export_json (bool): Whether to export traversals to JSON files
            min_utterances (int): Minimum number of utterances required for each session
            
        Returns:
            list: List of traversal sequences (session IDs and paths)
        """
        print(f"\n{Fore.WHITE}===== SCENARIO SIMULATOR ====={Style.RESET_ALL}")
        print(f"Generating {num_traversals} traversals for scenario (min {min_utterances} utterances per session)")
        
        # First, simulate all sessions to get their possible paths
        for session_id in self.session_ids:
            self._simulate_session(session_id)
        
        # Generate valid session sequences
        valid_sequences = self._generate_valid_sequences()
        
        if not valid_sequences:
            print(f"{Fore.RED}No valid session sequences found!{Style.RESET_ALL}")
            return []
        
        print(f"{Fore.GREEN}Found {len(valid_sequences)} valid session sequences{Style.RESET_ALL}")
        
        traversals = []
        for i in range(num_traversals):
            # Choose a random valid sequence
            sequence = random.choice(valid_sequences)
            
            print(f"\n{Fore.CYAN}Traversal {i+1}: Using sequence {sequence}{Style.RESET_ALL}")
            
            # Generate paths for each session in the sequence
            traversal = {
                "session_sequence": sequence,
                "paths": {},
                "node_data": {}  # Store detailed node data from traversals
            }
            
            # Choose a random path and traverse through it for each session
            for session_id in sequence:
                # Choose a random path for this session with minimum utterances
                path = self._choose_random_path(session_id, min_utterances=min_utterances)
                traversal["paths"][session_id] = path
                
                # Actually traverse the path to simulate the dialog
                node_data = self._traverse_session_path(session_id, path)
                traversal["node_data"][session_id] = node_data
                
                # Count meaningful dialog nodes (nodes with text)
                meaningful_nodes = [n for n in node_data if isinstance(n, dict) and n.get('text')]
                print(f"  Session {session_id}: Traversed path with {len(path)} nodes, {len(meaningful_nodes)} dialog interactions")
            
            traversals.append(traversal)
            
            # Export if requested
            if export_txt:
                self._export_traversal_to_txt(traversal, f"scenario_traversal_{i+1}.txt")
            
            if export_json:
                self._export_traversal_to_json(traversal, f"scenario_traversal_{i+1}.json")
        
        return traversals
    
    def _export_traversal_to_txt(self, traversal, output_file):
        """Export a traversal to a text file with dialog content"""
        print(f"{Fore.GREEN}Exporting traversal to {output_file}...{Style.RESET_ALL}")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"Baldur's Gate 3 Scenario Traversal\n\n")
            
            # Write session sequence
            f.write(f"Session sequence: {' -> '.join(traversal['session_sequence'])}\n\n")
            
            # Write each session's dialog
            for session_id in traversal['session_sequence']:
                f.write(f"=== Session: {session_id} ===\n")
                f.write(f"Synopsis: {self.metadata.get('individual_metadata', {}).get(session_id, {}).get('synopsis', '')}\n\n")
                
                # Get the node data for this session
                node_data = traversal['node_data'].get(session_id, [])
                if not node_data:
                    f.write("No dialog data available for this session.\n\n")
                    continue
                
                # Format the dialog content from the node data
                for node in node_data:
                    if not isinstance(node, dict):
                        continue
                        
                    if node.get('special_marker'):
                        f.write(f"[{node.get('id', 'SPECIAL_MARKER')}]\n")
                        continue
                        
                    speaker = node.get('speaker', 'Unknown')
                    text = node.get('text', '')
                    context = node.get('context', '')
                    
                    # Skip nodes without text
                    #if not text and not context:
                    #    continue
                    
                    # Format the line
                    if node.get('node_type') == 'tagcinematic':
                        line = f"[description] {text}"
                    else:
                        line = f"{speaker}: {text}"
                    
                    # Add context if present
                    if context:
                        line += f" || [context] {context}"
                    
                    f.write(f"{line}\n")
                
                f.write("\n")
        
        print(f"{Fore.GREEN}Traversal exported successfully to {output_file}{Style.RESET_ALL}")
        return output_file
    
    def _export_traversal_to_json(self, traversal, output_file):
        """Export a traversal to a JSON file with structured data"""
        print(f"{Fore.GREEN}Exporting traversal to {output_file}...{Style.RESET_ALL}")
        
        # Create a structured representation of the traversal
        traversal_data = {
            "session_sequence": traversal['session_sequence'],
            "sessions": {}
        }
        
        # Add data for each session
        for session_id in traversal['session_sequence']:
            node_data = traversal['node_data'].get(session_id, [])
            
            session_data = {
                "synopsis": self.metadata.get('individual_metadata', {}).get(session_id, {}).get('synopsis', ''),
                "nodes": []
            }
            
            # Add node data directly from the traversal
            if node_data:
                # Filter out unnecessary fields for cleaner output
                for node in node_data:
                    if not isinstance(node, dict):
                        continue
                        
                    if node.get('special_marker'):
                        session_data["nodes"].append({
                            "id": node.get('id', 'SPECIAL_MARKER'),
                            "special_marker": True
                        })
                    else:
                        # Create a simplified copy of the node data
                        filtered_node = {
                            "id": node.get('id', ''),
                            "speaker": node.get('speaker', 'Unknown'),
                            "text": node.get('text', ''),
                            "node_type": node.get('node_type', 'normal'),
                            "context": node.get('context', '')
                        }
                        
                        # Only include text nodes in the export
                        if filtered_node.get('text'):
                            session_data["nodes"].append(filtered_node)
            
            traversal_data["sessions"][session_id] = session_data
        
        # Write to JSON file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(traversal_data, f, indent=2, ensure_ascii=False)
            
        print(f"{Fore.GREEN}Traversal exported successfully to {output_file}{Style.RESET_ALL}")
        return output_file

def main():
    print(f"{Fore.CYAN}Baldur's Gate 3 Scenario Simulator{Style.RESET_ALL}")
    print("This tool generates traversals through scenario files, respecting ordering and exclusivity constraints.")
    
    # Check if a scenario file is provided as argument
    if len(sys.argv) > 1:
        scenario_file = sys.argv[1]
    else:
        # Default scenario file
        scenario_file = input("Enter path to scenario file [default: output_merged/Act1/Forest/for_bottomlesswell.json]: ")
        if not scenario_file:
            scenario_file = "output_merged/Act1/Forest/for_bottomlesswell.json"
    
    # Check if the file exists
    if not os.path.isfile(scenario_file):
        print(f"{Fore.RED}Error: File {scenario_file} not found.{Style.RESET_ALL}")
        return
    
    simulator = ScenarioSimulator(scenario_file)
    
    # Get simulation options
    num_traversals = 1
    try:
        num_input = input(f"Number of traversals to generate [default: 1]: ")
        if num_input:
            num_traversals = int(num_input)
    except ValueError:
        print(f"{Fore.YELLOW}Invalid input. Using default value of 1.{Style.RESET_ALL}")
    
    # Get minimum utterances option
    min_utterances = 3
    try:
        min_utterances_input = input(f"Minimum utterances per session [default: 3]: ")
        if min_utterances_input:
            min_utterances = int(min_utterances_input)
    except ValueError:
        print(f"{Fore.YELLOW}Invalid input. Using default value of 3.{Style.RESET_ALL}")
    
    # Ask about export options
    export_txt = input(f"\n{Fore.BLUE}Export traversals to text files? (y/n, default: n):{Style.RESET_ALL} ").lower() == 'y'
    export_json = input(f"\n{Fore.BLUE}Export traversals to JSON files? (y/n, default: n):{Style.RESET_ALL} ").lower() == 'y'
    
    # Run simulation
    traversals = simulator.simulate_scenario(
        num_traversals=num_traversals,
        export_txt=export_txt,
        export_json=export_json,
        min_utterances=min_utterances
    )
    
    print(f"\n{Fore.GREEN}Simulation complete. Generated {len(traversals)} traversals.{Style.RESET_ALL}")
    
if __name__ == "__main__":
    main() 