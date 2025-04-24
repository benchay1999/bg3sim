import json
import os
from colorama import init, Fore, Style

init(autoreset=True)

class MultiFileConstrainedDialogSimulator:
    def __init__(self, json_file_path):
        """
        Initializes the simulator with the main JSON file.

        Args:
            json_file_path (str): The path to the main JSON file (e.g., 'cha_crypt.json').
        """
        self.json_file_path = json_file_path
        self.dialog_tree = self._load_dialog_file()
        self.all_nodes = self.dialog_tree.get("dialogue", {})
        self.root_nodes = self._find_root_nodes()
        self.sequence_metadata = self._collect_sequence_metadata()
        self.constraints = self._define_constraints()  # Load constraints
        self._validate_constraints()
        self.source_files = self._get_source_files()  # Get source file order
        self.sequence_to_source_file = self._map_sequences_to_source_files()  # Map sequences to source files

        print(f"Initialized with file: {json_file_path}")
        print(f"Loaded {len(self.all_nodes)} nodes.")
        print(f"Source files to cover: {', '.join(self.source_files)}")

    def _load_dialog_file(self):
        """
        Loads the main JSON file.

        Returns:
            dict: The loaded JSON data.
        """
        try:
            with open(self.json_file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"{Fore.RED}Error: JSON file not found: {self.json_file_path}{Style.RESET_ALL}")
            return {}
        except json.JSONDecodeError:
            print(f"{Fore.RED}Error: Could not decode JSON from {self.json_file_path}{Style.RESET_ALL}")
            return {}

    def _get_source_files(self):
        """
        Gets the order of source files from the metadata.

        Returns:
            list: A list of source file names.
        """
        metadata = self.dialog_tree.get("metadata", {})
        return metadata.get("source_files", [])

    def _map_sequences_to_source_files(self):
        """
        Maps sequence IDs to their source files based on metadata.

        Returns:
            dict: Dictionary mapping sequence IDs to their source files.
        """
        sequence_to_file = {}
        for seq_id, metadata in self.sequence_metadata.items():
            if 'source_file' in metadata:
                sequence_to_file[seq_id] = metadata['source_file']
        
        # Log sequences without source file information
        missing_source = set(self.sequence_metadata.keys()) - set(sequence_to_file.keys())
        if missing_source:
            print(f"{Fore.YELLOW}Warning: The following sequences are missing source file information: "
                  f"{', '.join(missing_source)}{Style.RESET_ALL}")
        
        return sequence_to_file

    def _find_root_nodes(self):
        """
        Finds all root nodes (nodes without parents) from the loaded dialog tree.

        Returns:
            dict: A dictionary of root nodes.
        """
        root_nodes = {}
        for node_id, node_data in self.all_nodes.items():
            is_root = True
            for other_node_data in self.all_nodes.values():
                if 'children' in other_node_data and node_id in other_node_data['children']:
                    is_root = False
                    break
            if is_root:
                root_nodes[node_id] = node_data
        return root_nodes

    def _collect_sequence_metadata(self):
        """
        Collects sequence metadata from the loaded dialog tree.

        Returns:
            dict: A dictionary of sequence metadata, where keys are sequence IDs.
        """
        metadata = self.dialog_tree.get("metadata", {})
        return metadata.get("individual_metadata", {})

    def _get_sequence_id_from_node_id(self, node_id):
        """
        Determines the sequence ID a node belongs to based on matching prefixes.

        Args:
            node_id (str): The ID of the node.

        Returns:
            str: The sequence ID, or None if not found.
        """
        best_match = None
        for seq_id in self.sequence_metadata.keys():
            if node_id.startswith(seq_id + '_'):
                if best_match is None or len(seq_id) > len(best_match):
                    best_match = seq_id
            elif node_id == seq_id:
                if best_match is None or len(seq_id) > len(best_match):
                    best_match = seq_id
        return best_match

    def _check_order_constraints(self, sequence_id, visited_sequences, verbose=False):
        """
        Checks if the given sequence ID violates any order constraints based on visited sequences.

        Args:
            sequence_id (str): The ID of the sequence to check.
            visited_sequences (set): The set of sequence IDs that have been visited.
            verbose (bool): If True, prints detailed logs.

        Returns:
            bool: True if constraints are met, False otherwise.
        """
        for rule in self.constraints.get('order', []):
            if sequence_id == rule.get('successor'):
                predecessors = rule.get('predecessor', [])
                if predecessors and not any(p in visited_sequences for p in predecessors):
                    if verbose:
                        print(f"{Fore.YELLOW}Order Constraint Violation: Cannot enter {sequence_id}. "
                              f"Predecessor(s) {predecessors} not visited.{Style.RESET_ALL}")
                    return False
        return True

    def _check_exclusive_constraints(self, sequence_id, visited_sequences, verbose=False):
        """
        Checks if the given sequence ID violates any exclusivity constraints.

        Args:
            sequence_id (str): The ID of the sequence to check.
            visited_sequences (set): The set of sequence IDs that have been visited.
            verbose (bool): If True, prints detailed logs.

        Returns:
            bool: True if constraints are met, False otherwise.
        """
        for group in self.constraints.get('exclusive', []):
            if sequence_id in group:
                exclusive_partner_visited = any(s in visited_sequences for s in group if s != sequence_id)
                if exclusive_partner_visited:
                    if verbose:
                        print(f"{Fore.YELLOW}Exclusivity Constraint Violation: Cannot enter {sequence_id}. "
                              f"Exclusive sequence already visited.{Style.RESET_ALL}")
                    return False
        return True

    def _validate_constraints(self):
        """
        Validates that all sequence IDs used in constraints exist in the metadata.
        """
        all_constraint_seq_ids = set()
        for rule in self.constraints.get('order', []):
            all_constraint_seq_ids.update(rule.get('predecessor', []))
            if rule.get('successor'):
                all_constraint_seq_ids.add(rule['successor'])
        for group in self.constraints.get('exclusive', []):
            all_constraint_seq_ids.update(group)

        known_seq_ids = set(self.sequence_metadata.keys())
        unknown_ids = all_constraint_seq_ids - known_seq_ids
        if unknown_ids:
            print(f"{Fore.YELLOW}Warning: The following sequence IDs used in constraints are not found "
                  f"in the file's metadata: {', '.join(unknown_ids)}{Style.RESET_ALL}")

    def _is_leaf_node(self, node_id):
        """
        Checks if a node is a leaf node (end of a dialog path).

        Args:
            node_id (str): The ID of the node to check.

        Returns:
            bool: True if the node is a leaf node, False otherwise.
        """
        node = self.all_nodes.get(node_id)
        if not node:
            return True  # Consider non-existent nodes as leaves

        if node.get('is_end', False):
            return True

        if node.get('node_type') == 'jump' and node.get('goto'):
            return False

        if not node.get('children') and (node.get('goto') or node.get('link')):
            return False

        children_exist = node.get('children', {})
        if not children_exist:
            return True

        return False

    def _simulate_paths_recursive(self, node_id, current_path, visited_sequences, covered_files, depth, max_depth, verbose=False):
        """
        Recursively simulates all possible dialog paths from a given node, respecting constraints.

        Args:
            node_id (str): The ID of the current node.
            current_path (list): The list of node IDs representing the current path.
            visited_sequences (set): The set of sequence IDs that have been visited in the current path.
            covered_files (set): The set of source files that have been covered in the current path.
            depth (int): The current depth of recursion.
            max_depth (int): The maximum depth to explore.
            verbose (bool): If True, prints detailed logs.

        Returns:
            list: A list of valid dialog paths, with metadata about covered files.
        """
        # --- Cycle and Depth Check ---
        if node_id in current_path:
            if verbose:
                print(f"{Fore.RED}Cycle detected at node {node_id}. Stopping branch.{Style.RESET_ALL}")
            return [{"path": current_path + [node_id] + ["CYCLE_DETECTED"], "covered_files": covered_files}]
        if depth >= max_depth:
            if verbose:
                print(f"{Fore.RED}Max depth reached at node {node_id}. Stopping branch.{Style.RESET_ALL}")
            return [{"path": current_path + [node_id] + ["MAX_DEPTH_REACHED"], "covered_files": covered_files}]

        node = self.all_nodes.get(node_id)
        if not node:
            if verbose:
                print(f"{Fore.RED}Node {node_id} not found. Stopping branch.{Style.RESET_ALL}")
            return [{"path": current_path + [node_id] + ["NODE_NOT_FOUND"], "covered_files": covered_files}]

        sequence_id = self._get_sequence_id_from_node_id(node_id)

        # --- Constraint Checking ---
        if sequence_id:
            if not self._check_order_constraints(sequence_id, visited_sequences, verbose) or \
               not self._check_exclusive_constraints(sequence_id, visited_sequences, verbose):
                return []  # Prune the path if constraints are violated

        # --- Track Visited Sequences and Covered Files ---
        new_visited_sequences = visited_sequences.copy()
        new_covered_files = covered_files.copy()
        
        if sequence_id:
            new_visited_sequences.add(sequence_id)
            # Add source file if this sequence is linked to one
            if sequence_id in self.sequence_to_source_file:
                source_file = self.sequence_to_source_file[sequence_id]
                if source_file in self.source_files:  # Only track files that are in our source_files list
                    new_covered_files.add(source_file)
                    if verbose and source_file not in covered_files:
                        print(f"{Fore.GREEN}New source file covered: {source_file} "
                              f"via sequence {sequence_id} at node {node_id}{Style.RESET_ALL}")

        current_path = current_path + [node_id]

        # --- Handle Jumps and Links ---
        node_type = node.get('node_type', 'normal')
        if node_type == 'jump' and node.get('goto'):
            goto_id = node.get('goto')
            if verbose:
                print(f"{Fore.MAGENTA}Following jump from {node_id} to {goto_id}{Style.RESET_ALL}")
            return self._simulate_paths_recursive(goto_id, current_path, new_visited_sequences, 
                                                 new_covered_files, depth, max_depth, verbose)

        if not node.get('children') and node.get('goto'):
            goto_id = node.get('goto')
            if verbose:
                print(f"{Fore.MAGENTA}Following goto from {node_id} to {goto_id}{Style.RESET_ALL}")
            return self._simulate_paths_recursive(goto_id, current_path, new_visited_sequences, 
                                                 new_covered_files, depth + 1, max_depth, verbose)

        if not node.get('children') and not node.get('goto') and node.get('link'):
            link_id = node.get('link')
            if verbose:
                print(f"{Fore.MAGENTA}Following link from {node_id} to {link_id}{Style.RESET_ALL}")
            return self._simulate_paths_recursive(link_id, current_path, new_visited_sequences, 
                                                 new_covered_files, depth + 1, max_depth, verbose)

        # --- Check if Leaf Node ---
        if self._is_leaf_node(node_id):
            if verbose:
                print(f"{Fore.GREEN}Reached leaf node: {node_id}. Path: {' -> '.join(current_path)}{Style.RESET_ALL}")
                print(f"{Fore.GREEN}Files covered: {new_covered_files}{Style.RESET_ALL}")
            return [{"path": current_path, "covered_files": new_covered_files}]

        # --- Explore Children ---
        options = node.get('children', {})
        if not options:
            if verbose:
                print(f"{Fore.YELLOW}Node {node_id} has no children. Ending path.{Style.RESET_ALL}")
            return [{"path": current_path, "covered_files": new_covered_files}]

        all_child_paths = []
        for child_id in options.keys():
            child_paths = self._simulate_paths_recursive(child_id, current_path, new_visited_sequences, 
                                                         new_covered_files, depth + 1, max_depth, verbose)
            all_child_paths.extend(child_paths)

        return all_child_paths

    def _filter_complete_coverage_paths(self, paths, verbose=False):
        """
        Filter paths to only include those that cover all source files.
        
        Args:
            paths (list): List of path dictionaries with 'path' and 'covered_files' keys.
            verbose (bool): If True, prints detailed logs.
            
        Returns:
            list: List of paths that cover all source files.
        """
        all_source_files = set(self.source_files)
        complete_coverage_paths = []
        
        for path_info in paths:
            if all_source_files.issubset(path_info["covered_files"]):
                complete_coverage_paths.append(path_info)
                if verbose:
                    print(f"{Fore.GREEN}Found complete coverage path: "
                          f"{' -> '.join(path_info['path'][:5])}... {Style.RESET_ALL}")
        
        return complete_coverage_paths

    def simulate_all_paths(self, max_depth=20, export_txt=False, verbose=False, complete_coverage_only=True):
        """
        Simulates all valid dialog paths from root nodes, respecting constraints.

        Args:
            max_depth (int): The maximum depth to explore in the dialog tree.
            export_txt (bool): If True, exports the valid paths to a text file.
            verbose (bool): If True, prints detailed logs.
            complete_coverage_only (bool): If True, only return paths that cover all source files.

        Returns:
            list: A list of valid dialog paths.
            str: The path to the exported text file (if export_txt is True), or None otherwise.
        """
        print(f"\n{Fore.WHITE}===== CONSTRAINED DIALOG SIMULATION =====")
        print(f"File: {self.json_file_path}")
        print(f"Constraints: {self.constraints}")
        print(f"Source Files to Cover: {', '.join(self.source_files)}")
        print(f"Max Depth: {max_depth}")
        print(f"Verbose Logging: {'ON' if verbose else 'OFF'}")
        print(f"Complete Coverage Only: {'ON' if complete_coverage_only else 'OFF'}{Style.RESET_ALL}")

        all_valid_paths = []
        total_simulated = 0

        for root_id, root_data in self.root_nodes.items():
            root_sequence_id = self._get_sequence_id_from_node_id(root_id)
            print(f"\n{Fore.CYAN}Simulating from Root Node: {root_id} "
                  f"(Sequence: {root_sequence_id if root_sequence_id else 'None'}){Style.RESET_ALL}")

            initial_visited = {root_sequence_id} if root_sequence_id else set()
            initial_covered_files = set()
            
            # Add the source file of the root sequence if applicable
            if root_sequence_id and root_sequence_id in self.sequence_to_source_file:
                source_file = self.sequence_to_source_file[root_sequence_id]
                if source_file in self.source_files:
                    initial_covered_files.add(source_file)
            
            paths_from_root = self._simulate_paths_recursive(
                node_id=root_id,
                current_path=[],
                visited_sequences=initial_visited,
                covered_files=initial_covered_files,
                depth=0,
                max_depth=max_depth,
                verbose=verbose
            )
            total_simulated += len(paths_from_root)

            valid_paths_from_root = [p for p in paths_from_root if p]
            all_valid_paths.extend(valid_paths_from_root)

            print(f"  Found {len(valid_paths_from_root)} valid paths from root {root_id}.")

        # Filter for complete coverage if requested
        if complete_coverage_only and self.source_files:
            print(f"\n{Fore.CYAN}Filtering for paths with complete source file coverage...{Style.RESET_ALL}")
            complete_paths = self._filter_complete_coverage_paths(all_valid_paths, verbose)
            print(f"  Found {len(complete_paths)} paths with complete coverage.")
            all_valid_paths = complete_paths
        
        print(f"\n{Fore.GREEN}Simulation Complete.{Style.RESET_ALL}")
        print(f"Total valid paths found: {len(all_valid_paths)}")
        print(f"(Total paths explored before filtering: {total_simulated})")

        txt_file = None
        if export_txt and all_valid_paths:
            txt_file = self.export_paths_to_txt(all_valid_paths)

        return all_valid_paths, txt_file

    def export_paths_to_txt(self, paths, output_file=None):
        """
        Exports the valid simulated paths to a text file.

        Args:
            paths (list): The list of valid dialog paths (with coverage info).
            output_file (str, optional): The name of the output text file. Defaults to None.

        Returns:
            str: The path to the exported text file.
        """
        if output_file is None:
            output_file = "constrained_dialog_paths.txt"

        print(f"\n{Fore.BLUE}Exporting {len(paths)} valid paths to {output_file}...{Style.RESET_ALL}")

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"Constrained Dialog Paths Simulation\n")
            f.write(f"Source File: {self.json_file_path}\n")
            f.write(f"Total Valid Paths: {len(paths)}\n")
            f.write(f"Required Source Files: {', '.join(self.source_files)}\n")
            f.write(f"Constraints Applied: {json.dumps(self.constraints)}\n\n")

            for i, path_info in enumerate(paths, 1):
                path = path_info["path"]
                covered_files = path_info["covered_files"]
                
                f.write(f"Path {i}: {' -> '.join(path)}\n")
                f.write("  Details:\n")
                visited_seqs_in_path = set()
                for node_id in path:
                    node = self.all_nodes.get(node_id)
                    seq_id = self._get_sequence_id_from_node_id(node_id) if node else None
                    if seq_id:
                        visited_seqs_in_path.add(seq_id)

                    if node:
                        speaker = node.get('speaker', 'Narrator')
                        text = node.get('text', '[No Text]')
                        f.write(f"    - {node_id}" + (f" (Seq: {seq_id})" if seq_id else "") +
                                f": {speaker} - {text[:80]}{'...' if len(text) > 80 else ''}\n")
                    else:
                        f.write(f"    - {node_id}\n")
                f.write(f"  Visited Sequences: {sorted(list(visited_seqs_in_path))}\n")
                f.write(f"  Covered Source Files: {sorted(list(covered_files))}\n\n")

        print(f"{Fore.GREEN}Paths exported successfully to {output_file}{Style.RESET_ALL}")
        return output_file

    def _define_constraints(self):
        """
        Defines the constraints for dialog traversal.

        Returns:
            dict: A dictionary containing 'order' and 'exclusive' constraints.
        """
        # Define constraints (Example for cha_crypt.json)
        # Ideally, load this from a separate file or configuration
        # Using sequence IDs from individual_metadata keys
        example_constraints = {
            "order": [
                {
                    'predecessor': ['VB_TakingTheArtefact_1', 'VB_TakingTheArtefact_1_WithShadowheart',
                                    'VB_TakingTheArtefact_2_WithShadowheart'],
                    'successor': 'PAD_SuccessfulGraverobbing'
                },
                {
                    'predecessor': ['AD_BanditLockpickerOpenDoor'],
                    'successor': 'AD_BanditLockpickerWander'
                }
                # Add more order rules here if needed
            ],
            "exclusive": [
                # Example: ['SequenceA', 'SequenceB']  # Cannot both appear in the same path
                # Add exclusivity rules here if needed
            ]
        }

        # Use example constraints if simulating cha_crypt.json, otherwise empty
        if "cha_crypt.json" in self.json_file_path:
            print(f"{Fore.BLUE}Applying example constraints for cha_crypt.json{Style.RESET_ALL}")
            return example_constraints
        else:
            print(f"{Fore.YELLOW}No specific constraints defined for this file, using empty constraints.{Style.RESET_ALL}")
            return {"order": [], "exclusive": []}

# --- Main Execution ---
if __name__ == "__main__":
    json_file_path = "output_merged/Act2/MoonriseTowers/moo_jailbreak.json"  # Entry point JSON file
    max_depth = 25
    verbose = True
    export = True
    complete_coverage_only = True  # Only return paths that cover all source files

    simulator = MultiFileConstrainedDialogSimulator(json_file_path)
    valid_paths, output_txt_file = simulator.simulate_all_paths(
        max_depth=max_depth,
        export_txt=export,
        verbose=verbose,
        complete_coverage_only=complete_coverage_only
    )

    if valid_paths:
        print("\n--- First 10 Valid Paths ---")
        print("Each path covers all source files:")
        for i, path_info in enumerate(valid_paths[:10]):
            path = path_info["path"]
            covered_files = path_info["covered_files"]
            print(f"{i + 1}: {' -> '.join(path[:5])}... (Covers {len(covered_files)} files)")
        if len(valid_paths) > 10:
            print("...")