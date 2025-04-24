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
        
    def _flatten_dialog_nodes(self, nodes_dict):
        """
        Recursively flattens a dictionary of dialog nodes, collecting all nodes
        including those nested within 'children'.

        Args:
            nodes_dict (dict): The initial dictionary containing top-level nodes.

        Returns:
            dict: A flat dictionary containing all nodes keyed by their ID.
        """
        flat_nodes = {}
        nodes_to_visit = list(nodes_dict.values()) # Start with top-level nodes

        while nodes_to_visit:
            node_data = nodes_to_visit.pop(0)
            node_id = node_data.get("id")

            if not node_id or node_id in flat_nodes:
                # Skip if no ID or already processed
                continue

            # Add the current node
            flat_nodes[node_id] = node_data

            # Add children to the visit list
            children = node_data.get("children", {})
            if isinstance(children, dict):
                nodes_to_visit.extend(list(children.values()))
            elif isinstance(children, list): # Handle cases where children might be a list
                 nodes_to_visit.extend(children)


        return flat_nodes

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
    
    def _generate_valid_sequences(self, prioritize_approval=True, include_all_sessions=True):
        """
        Generate all valid sequences of sessions respecting constraints
        
        Args:
            prioritize_approval (bool): Whether to prioritize sessions with approval effects
            include_all_sessions (bool): Whether to try to include all possible sessions
            
        Returns:
            list: List of valid session sequences
        """
        # Start with possible sequences including all non-exclusive sessions
        all_sequences = []
        
        # Identify sessions with approval effects
        sessions_with_approval = self._identify_sessions_with_approval() if prioritize_approval else {}
        # if there are no approval nodes in the group, sort by total sessions
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
            # Sort the group based on priority
            if prioritize_approval and any(sessions_with_approval.get(s, 0) > 0 for s in group):
                # Prioritize by approval count if requested and approvals exist in the group
                group = sorted(group, key=lambda s: sessions_with_approval.get(s, 0), reverse=True)
            else:
                # Fallback: Sort by number of paths
                group = sorted(group, key=lambda s: len(self.session_path_options.get(s, [])), reverse=True)

            # Try each session in the group
            for session in group:
                new_seq = current_seq + [session]
                if self._validate_sequence(new_seq):
                    generate_sequences(new_seq, remaining_groups[1:])
            
            # Try skipping this group entirely (but only if not trying to include all sessions)
            if not include_all_sessions:
                generate_sequences(current_seq, remaining_groups[1:])
        
        generate_sequences([], choice_groups)
        
        # Sort sequences by:
        # 1. Total number of sessions (if including all sessions)
        # 2. Number of approval-affecting sessions (if prioritizing approval)
        # 3. Length of sequence
        
        def sequence_sort_key(seq):
            if include_all_sessions and prioritize_approval:
                
                # Maximize both total sessions and approval sessions
                return (
                    len(seq),  # Total number of sessions
                    sum(sessions_with_approval.get(s, 0) > 0 for s in seq),  # Number of approval-affecting sessions
                    sum(sessions_with_approval.get(s, 0) for s in seq)  # Total approval nodes
                )
            elif include_all_sessions:
                # Just maximize total sessions
                return (len(seq),)
            elif prioritize_approval:
                # Maximize approval sessions, then total sessions
                return (
                    sum(sessions_with_approval.get(s, 0) > 0 for s in seq),  # Number of approval-affecting sessions  
                    sum(sessions_with_approval.get(s, 0) for s in seq),  # Total approval nodes
                    len(seq)  # Total number of sessions
                )
            else:
                # Default sorting by sequence length
                return (len(seq),)
        
        # Final validity check and sort
        valid_sequences = [seq for seq in all_sequences if self._validate_sequence(seq)]
        valid_sequences.sort(key=sequence_sort_key, reverse=True)
        
        return valid_sequences

    def simulate_scenario(self, num_traversals=1, export_txt=False, export_json=False, 
                          min_utterances=3, prioritize_approval=True, include_all_sessions=True):
        """
        Simulate traversals through the scenario
        
        Args:
            num_traversals (int): Number of traversals to generate
            export_txt (bool): Whether to export traversals to text files
            export_json (bool): Whether to export traversals to JSON files
            min_utterances (int): Minimum number of utterances required for each session
            prioritize_approval (bool): Whether to prioritize sessions with approval effects
            include_all_sessions (bool): Whether to try to include all possible sessions
            
        Returns:
            list: List of traversal sequences (session IDs and paths)
        """
        print(f"\n{Fore.WHITE}===== SCENARIO SIMULATOR ====={Style.RESET_ALL}")
        print(f"Generating {num_traversals} traversals for scenario (min {min_utterances} utterances per session)")
        
        if prioritize_approval:
            print(f"{Fore.CYAN}Prioritizing sessions and paths with companion approval effects{Style.RESET_ALL}")
        
        if include_all_sessions:
            print(f"{Fore.CYAN}Attempting to include all possible sessions in traversals{Style.RESET_ALL}")
        
        # First, simulate all sessions to get their possible paths
        for session_id in self.session_ids:
            self._simulate_session(session_id)
        
        # Generate valid session sequences with priorities
        valid_sequences = self._generate_valid_sequences(
            prioritize_approval=prioritize_approval,
            include_all_sessions=include_all_sessions
        )
        
        # Fallback if no sequences found with prioritization enabled
        if not valid_sequences and prioritize_approval:
            print(f"{Fore.YELLOW}No valid sequences found prioritizing approval. Retrying without approval prioritization...{Style.RESET_ALL}")
            valid_sequences = self._generate_valid_sequences(
                prioritize_approval=False, # Force fallback
                include_all_sessions=include_all_sessions
            )
            # Re-check sessions_with_approval for the print statement below if needed, although prioritization is now off
            sessions_with_approval_fallback = self._identify_sessions_with_approval() if prioritize_approval else {}


        if not valid_sequences:
            print(f"{Fore.RED}No valid session sequences found even after fallback! Check constraints.{Style.RESET_ALL}")
            return []
        
        print(f"{Fore.GREEN}Found {len(valid_sequences)} valid session sequences{Style.RESET_ALL}")
        
        # Count total sessions and approval sessions in best sequence (using original prioritize_approval flag for context)
        if valid_sequences:
            best_sequence = valid_sequences[0] # After sorting, the first one is the 'best'
            total_sessions = len(best_sequence)
            # Use the initially identified approval sessions for reporting, even if fallback occurred
            sessions_with_approval_report = self._identify_sessions_with_approval() if prioritize_approval else {}
            approval_sessions = sum(1 for s in best_sequence if s in sessions_with_approval_report)
            print(f"{Fore.GREEN}Best sequence includes {total_sessions} sessions ({approval_sessions} with approval effects based on initial priority){Style.RESET_ALL}")
        
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
                path = self._choose_random_path(session_id, min_utterances=min_utterances, prioritize_approval=prioritize_approval)
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
        
        # --- Remove Diagnostic Print ---
        # if session_id == "BanditBackInteraction_Spotted":
        #     ... removed debug block ...
        # --- End Removal ---

        if not session_dialog:
            print(f"{Fore.RED}No dialog found for session {session_id}{Style.RESET_ALL}")
            return []
        
        # Flatten the extracted dialog to include all nested nodes
        flat_session_dialog = self._flatten_dialog_nodes(session_dialog)

        if not flat_session_dialog:
             print(f"{Fore.YELLOW}Flattening resulted in empty dialog for session {session_id}. Initial dialog had {len(session_dialog)} nodes.{Style.RESET_ALL}")
             # Fallback or further investigation needed here potentially
             # For now, let's try proceeding with the original session_dialog if flattening fails unexpectedly
             if not session_dialog:
                 return [] # Return if original was also empty
             flat_session_dialog = session_dialog # Use original as fallback

        # Create a temporary JSON file for this session using the flattened dialog
        temp_file = f"temp_{session_id}.json"
        temp_data = {
            "metadata": {
                "synopsis": self.metadata.get("individual_metadata", {}).get(session_id, {}).get("synopsis", ""),
                "how_to_trigger": self.metadata.get("individual_metadata", {}).get(session_id, {}).get("how_to_trigger", "")
            },
            "dialogue": flat_session_dialog # Use the flattened dictionary here
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
            test_mode=False,  # True: Ignore flag requirements for simulation
            verbose=False
        )
        
        # Store the paths for this session
        self.session_path_options[session_id] = paths
        
        # Clean up temp file
        os.remove(temp_file)
        
        print(f"{Fore.GREEN}Found {len(paths)} possible paths for session {session_id}{Style.RESET_ALL}")
        
        return paths
    
    def _find_approval_nodes(self, session_id):
        """
        Find all nodes with nonempty approval values for a session
        
        Args:
            session_id (str): The session ID to analyze
            
        Returns:
            list: List of node IDs that have approval effects
        """
        approval_nodes = []
        
        # Get the simulator for this session
        simulator = self.session_simulators.get(session_id)
        if not simulator:
            print(f"{Fore.RED}No simulator found for session {session_id}{Style.RESET_ALL}")
            return []
        
        # Check all nodes in the session
        
        for node_id, node_data in simulator.all_nodes.items():
            
            if node_data.get('approval') and len(node_data.get('approval')) > 0:
                approval_nodes.append(node_id)
        
        if approval_nodes:
            print(f"{Fore.CYAN}Found {len(approval_nodes)} nodes with approval effects in session {session_id}{Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}No approval nodes found in session {session_id}{Style.RESET_ALL}")
        return approval_nodes
    def _find_traversals_with_approval(self, session_id, min_utterances=3):
        """
        Find all possible traversals that visit nodes with approval effects
        
        Args:
            session_id (str): The session ID to analyze
            min_utterances (int): Minimum number of text utterances required in the path
            
        Returns:
            list: List of paths that visit approval-affecting nodes
        """
        # Get all available paths for this session
        paths = self.session_path_options.get(session_id, [])
        if not paths:
            # print(f"{Fore.RED}No paths available for session {session_id}{Style.RESET_ALL}")
            # Suppress print during analysis, let analysis function handle summary
            return []
        
        # Get nodes with approval effects
        approval_nodes = self._find_approval_nodes(session_id)
        if not approval_nodes:
            # print(f"{Fore.YELLOW}No approval-affecting nodes found in session {session_id}{Style.RESET_ALL}")
            # Suppress print during analysis
            return []
        
        # Get simulator for this session
        simulator = self.session_simulators.get(session_id)
        if not simulator:
            # print(f"{Fore.RED}No simulator found for session {session_id}{Style.RESET_ALL}")
            # Suppress print during analysis
            return []
        
        # Function to count utterances in a path (keep for potential reuse elsewhere)
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
        
        # Find paths that visit at least one approval node
        approval_paths_data = []
        for path in paths:
            # Check if this path visits any of the approval nodes
            visits_approval_node = any(node_id in path for node_id in approval_nodes)
            
            if visits_approval_node:
                approval_paths_data.append(path) # Just append the path itself

        return approval_paths_data # Return the raw list of paths

    def _choose_random_path(self, session_id, min_utterances=3, max_attempts=10, prioritize_approval=True):
        """
        Choose a random path from the available paths for a session,
        preferring paths with approval effects and at least min_utterances.
        
        Args:
            session_id (str): The session ID
            min_utterances (int): Minimum number of text utterances required in the path
            max_attempts (int): Maximum number of attempts to find a suitable path
            prioritize_approval (bool): Whether to prioritize paths with approval effects
            
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

        suitable_paths = []
        approval_paths = []

        # If prioritizing approval, find those paths first
        if prioritize_approval:
            approval_paths = self._find_traversals_with_approval(session_id)
            if approval_paths:
                # Filter these approval paths by min_utterances
                suitable_approval_paths_data = []
                for path in approval_paths:
                    utterances = count_utterances(path)
                    if utterances >= min_utterances:
                        is_leaf = path and simulator._is_leaf_node(path[-1])
                        suitable_approval_paths_data.append({
                            'path': path,
                            'is_leaf': is_leaf,
                            'utterances': utterances
                        })
                
                if suitable_approval_paths_data:
                    # Prefer leaf nodes among suitable approval paths
                    leaf_paths = [p for p in suitable_approval_paths_data if p['is_leaf']]
                    if leaf_paths:
                        chosen_path = random.choice(leaf_paths)
                        print(f"{Fore.GREEN}Found suitable approval leaf path for {session_id} with {chosen_path['utterances']} utterances{Style.RESET_ALL}")
                        return chosen_path['path']
                    else:
                        chosen_path = random.choice(suitable_approval_paths_data)
                        print(f"{Fore.GREEN}Found suitable approval non-leaf path for {session_id} with {chosen_path['utterances']} utterances{Style.RESET_ALL}")
                        return chosen_path['path']
                else:
                    print(f"{Fore.YELLOW}Found approval paths for {session_id}, but none met {min_utterances} utterances. Falling back...{Style.RESET_ALL}")
                    # Fall through to check all paths if no suitable approval paths found
            else:
                 print(f"{Fore.YELLOW}Prioritizing approval, but no approval paths found for {session_id}. Falling back...{Style.RESET_ALL}")
                 # Fall through if no approval paths found at all

        # Fallback: Evaluate all paths (including non-approval) if prioritization failed or wasn't requested
        all_paths_data = []
        for path in paths:
            utterances = count_utterances(path)
            is_leaf = path and simulator._is_leaf_node(path[-1])
            all_paths_data.append({
                'path': path,
                'is_leaf': is_leaf,
                'utterances': utterances
            })

        # Try to find paths that meet the minimum utterance requirement from all paths
        min_utterance_paths = [p for p in all_paths_data if p['utterances'] >= min_utterances]
        
        if min_utterance_paths:
            # Among suitable paths, prefer those that end at leaf nodes
            leaf_paths = [p for p in min_utterance_paths if p['is_leaf']]
            if leaf_paths:
                chosen_path = random.choice(leaf_paths)
                print(f"{Fore.GREEN}Found suitable leaf path for {session_id} with {chosen_path['utterances']} utterances{Style.RESET_ALL}")
                return chosen_path['path']
            else:
                chosen_path = random.choice(min_utterance_paths)
                print(f"{Fore.GREEN}Found suitable non-leaf path for {session_id} with {chosen_path['utterances']} utterances{Style.RESET_ALL}")
                return chosen_path['path']
        
        # If we couldn't find ANY path with min_utterances, log and select the one with most utterances
        print(f"{Fore.YELLOW}No paths with {min_utterances}+ utterances found for {session_id}. Using best available overall.{Style.RESET_ALL}")
        
        # Sort all paths by utterance count (descending) and then by leaf status
        all_paths_data.sort(key=lambda p: (p['utterances'], p['is_leaf']), reverse=True)
        
        if all_paths_data:
            best_path = all_paths_data[0]
            print(f"{Fore.YELLOW}Best available path has {best_path['utterances']} utterances{Style.RESET_ALL}")
            return best_path['path']
        
        # Ultimate fallback: random choice if something went very wrong
        print(f"{Fore.RED}Unexpected error in path selection for {session_id}. Choosing random path.{Style.RESET_ALL}")
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
                    approval = node.get('approval', [])
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
                    
                    if approval:
                        line += f" || [approval] {approval}"
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
                        # Create a copy of the node data
                        filtered_node = {
                            "id": node.get('id', ''),
                            "speaker": node.get('speaker', 'Unknown'),
                            "text": node.get('text', ''),
                            "node_type": node.get('node_type', 'normal'),
                            "context": node.get('context', ''),
                            "checkflags": node.get('checkflags', []),
                            "setflags": node.get('setflags', []),
                            "goto": node.get('goto', ''),
                            "link": node.get('link', ''),
                            "is_end": node.get('is_end', False),
                            "approval": node.get('approval', []),
                        
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

    def analyze_approval_paths(self):
        """
        Analyzes all sessions to find and report paths containing approval nodes.
        Ensures all sessions are simulated first.

        Returns:
            dict: A dictionary mapping session IDs to a list of their paths
                  that contain at least one approval node.
        """
        print(f"\n{Fore.WHITE}===== APPROVAL PATH ANALYSIS ====={Style.RESET_ALL}")
        all_session_approval_paths = {}

        # Ensure all sessions are simulated first to populate path options
        for session_id in self.session_ids:
            if session_id not in self.session_path_options:
                self._simulate_session(session_id)

            # Find paths with approvals for this session
            approval_paths = self._find_traversals_with_approval(session_id)
            if approval_paths:
                all_session_approval_paths[session_id] = approval_paths
                print(f"{Fore.GREEN}Session '{session_id}': Found {len(approval_paths)} paths with approval nodes.{Style.RESET_ALL}")
            else:
                # Optional: print if a session has no approval paths
                print(f"{Fore.YELLOW}Session '{session_id}': No paths with approval nodes found.{Style.RESET_ALL}")

        if not all_session_approval_paths:
            print(f"{Fore.YELLOW}No sessions with approval-containing paths were found in this scenario.{Style.RESET_ALL}")
        else:
            print(f"{Fore.GREEN}Analysis complete. Found approval paths in {len(all_session_approval_paths)} sessions.{Style.RESET_ALL}")

        return all_session_approval_paths

    def _identify_sessions_with_approval(self):
        """
        Identify which sessions contain nodes with approval effects
        
        Returns:
            dict: Dictionary mapping session IDs to number of approval nodes
        """
        sessions_with_approval = {}
        
        # Ensure all sessions are simulated first
        for session_id in self.session_ids:
            if session_id not in self.session_simulators:
                self._simulate_session(session_id)
            
            # Find approval nodes for this session
            approval_nodes = self._find_approval_nodes(session_id)
            
            # Store sessions with approval nodes
            if approval_nodes:
                sessions_with_approval[session_id] = len(approval_nodes)
                print(f"{Fore.CYAN}Session {session_id} has {len(approval_nodes)} nodes with approval effects{Style.RESET_ALL}")
        
        if not sessions_with_approval:
            print(f"{Fore.YELLOW}No sessions with approval effects found in this scenario{Style.RESET_ALL}")
        else:
            print(f"{Fore.GREEN}Found {len(sessions_with_approval)} sessions with approval effects out of {len(self.session_ids)} total sessions{Style.RESET_ALL}")
        return sessions_with_approval

def main():
    print(f"{Fore.CYAN}Baldur's Gate 3 Scenario Simulator{Style.RESET_ALL}")
    print("This tool generates traversals through scenario files, respecting ordering and exclusivity constraints.")
    
    # Check if a scenario file is provided as argument
    if len(sys.argv) > 1:
        scenario_file = sys.argv[1]
    else:
        # Default scenario file
        scenario_file = input("Enter path to scenario file [default: output_merged/Act1/Chapel/cha_outside.json]: ")
        if not scenario_file:
            scenario_file = "output_merged/Act1/Chapel/cha_outside.json"
    
    # Check if the file exists
    if not os.path.isfile(scenario_file):
        print(f"{Fore.RED}Error: File {scenario_file} not found.{Style.RESET_ALL}")
        return
    
    simulator = ScenarioSimulator(scenario_file)
    
    # --- Add Approval Path Analysis ---
    # Perform analysis after simulator init (which calls _simulate_session for all)
    approval_analysis_results = simulator.analyze_approval_paths()
    # Optional: Print detailed results if needed
    # for session_id, paths in approval_analysis_results.items():
    #     print(f"\n--- Approval Paths for Session: {session_id} ---")
    #     for i, path in enumerate(paths):
    #         print(f"  Path {i+1}: {' -> '.join(path)}")
    # --- End Analysis Call ---

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
    
    # Get prioritize approval option
    prioritize_approval = input(f"Prioritize sessions with companion approval effects? (y/n, default: y):{Style.RESET_ALL} ").lower() != 'n'
    
    # Get include all sessions option
    include_all_sessions = input(f"Try to include all possible sessions? (y/n, default: y):{Style.RESET_ALL} ").lower() != 'n'
    
    # Ask about export options
    export_txt = input(f"\n{Fore.BLUE}Export traversals to text files? (y/n, default: n):{Style.RESET_ALL} ").lower() == 'y'
    export_json = input(f"\n{Fore.BLUE}Export traversals to JSON files? (y/n, default: n):{Style.RESET_ALL} ").lower() == 'y'
    
    # Run simulation
    traversals = simulator.simulate_scenario(
        num_traversals=num_traversals,
        export_txt=export_txt,
        export_json=export_json,
        min_utterances=min_utterances,
        prioritize_approval=prioritize_approval,
        include_all_sessions=include_all_sessions
    )
    
    print(f"\n{Fore.GREEN}Simulation complete. Generated {len(traversals)} traversals.{Style.RESET_ALL}")
    
if __name__ == "__main__":
    main() 