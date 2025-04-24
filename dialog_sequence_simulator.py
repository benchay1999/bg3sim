import json
import sys
import os
import itertools
from colorama import init, Fore, Back, Style
import random

# Initialize colorama for colored terminal output
init()

class DialogSessionSimulator:
    """Simulates a single dialog session from a dialog tree."""
    
    def __init__(self, session_id, dialog_data):
        """Initialize a dialog session simulator with the specified dialog data.
        
        Args:
            session_id (str): The identifier for this session
            dialog_data (dict): The dialog tree data for this session
        """
        self.session_id = session_id
        self.root_nodes = {}
        self.all_nodes = dialog_data  # All nodes including children
        
        # Extract root nodes from the dialog tree
        self.root_nodes = {node_id: node_data for node_id, node_data in dialog_data.items() 
                          if not self._is_child_node(node_id)}
        
        # Track visited nodes in a session
        self.visited_nodes = []
        
        # Track flags that have been set during playthrough
        self.active_flags = set()
    
    def _is_child_node(self, node_id):
        """Check if a node is a child node of any other node"""
        for other_id, other_data in self.all_nodes.items():
            if other_id != node_id:
                children = other_data.get('children', {})
                if node_id in children:
                    return True
        return False
    
    def _get_node(self, node_id):
        """Get a node by its ID, searching in the entire dialog tree structure"""
        # First check in top-level nodes
        if node_id in self.all_nodes:
            return self.all_nodes[node_id]
        
        # If not found at top level, search in children recursively
        for _, node_data in self.all_nodes.items():
            if 'children' in node_data:
                result = self._find_node_in_children(node_id, node_data['children'])
                if result:
                    return result
        
        return None

    def _find_node_in_children(self, node_id, children):
        """Recursively search for a node in the children dictionary"""
        if node_id in children:
            return children[node_id]
        
        for _, child_data in children.items():
            if 'children' in child_data and child_data['children']:
                result = self._find_node_in_children(node_id, child_data['children'])
                if result:
                    return result
        
        return None
    
    def _is_leaf_node(self, node_id):
        """Check if a node is a leaf node (end of dialog)"""
        node = self._get_node(node_id)
        if not node:
            return False
            
        # A node is a leaf if it's explicitly marked as an end node
        if node.get('is_end', False):
            return True
            
        # A node is NOT a leaf if it has a goto link
        if node.get('goto'):
            return False
            
        # A node is NOT a leaf if it has a link field
        if node.get('link'):
            return False
            
        # A node is a leaf if it has no valid children
        children = node.get('children', {})
        if not children:
            return True
            
        return False
    
    def _check_flags(self, node_data):
        """Check if required flags are met for a node"""
        # A simple implementation - in a real game this would be more complex
        # if checkflags is empty, return True
        if not node_data.get('checkflags', []):
            return True
        # if checkflags has a flag with " = False", check whether it is not set.
        for flag in node_data.get('checkflags', []):
            if "= False" in flag:
                if flag.split('= False')[0].strip() in self.active_flags:
                    return False
            else:
                if flag.strip() not in self.active_flags:
                    return False
        return True
    
    def _simulate_paths_from_node(self, node_id, current_path, depth, max_depth, test_mode=True):
        """Recursively simulate all paths from a node, always following jump nodes and goto for nodes without children"""
        # Prevent excessive recursion depth
        if depth >= max_depth:
            return [current_path + [node_id] + ["MAX_DEPTH_REACHED"]]
        
        node = self._get_node(node_id)
        if not node:
            return [current_path + [node_id] + ["NODE_NOT_FOUND"]]
        
        # Add current node to path
        current_path = current_path + [node_id]
        
        # ALWAYS follow jump nodes first
        node_type = node.get('node_type', 'normal')
        if node_type == 'jump' and node.get('goto'):
            goto_id = node.get('goto')
            return self._simulate_paths_from_node(goto_id, current_path, depth, max_depth, test_mode)
        
        # For nodes with goto but no children, follow the goto
        if not node.get('children') and node.get('goto'):
            goto_id = node.get('goto')
            return self._simulate_paths_from_node(goto_id, current_path, depth, max_depth, test_mode)
            
        # For nodes with link but no children and no goto, follow the link
        if not node.get('children') and not node.get('goto') and node.get('link'):
            link_id = node.get('link')
            return self._simulate_paths_from_node(link_id, current_path, depth, max_depth, test_mode)
        
        # Check if we've reached a leaf node
        if self._is_leaf_node(node_id):
            return [current_path]
        
        # In test mode, temporarily add any required flags for children
        original_flags = None
        if test_mode:
            original_flags = self.active_flags.copy()
            # Add all required flags for the child nodes
            children = node.get('children', {})
            for child_id, child_data in children.items():
                child_node = self._get_node(child_id)
                if child_node:
                    for flag in child_node.get('checkflags', []):
                        if "= False" in flag:
                            pass
                        else:
                            self.active_flags.add(flag)
        
        # Get available options based on direct children
        children = node.get('children', {})
        valid_children = {}
        for child_id, child_data in children.items():
            child_node = self._get_node(child_id)
            if child_node and (test_mode or self._check_flags(child_node)):
                valid_children[child_id] = child_node
        
        # If in test mode, restore original flags
        if test_mode and original_flags is not None:
            self.active_flags = original_flags
            
        if not valid_children:
            # This is a leaf node with no options, no goto, and no link
            return [current_path]
        
        # Explore all child paths
        all_paths = []
        for child_id in valid_children:
            child_paths = self._simulate_paths_from_node(child_id, current_path, depth + 1, max_depth, test_mode)
            all_paths.extend(child_paths)
        
        # If no children produced paths (shouldn't happen), return current path
        if not all_paths:
            return [current_path]
            
        return all_paths
    
    def simulate_all_paths(self, max_depth=20):
        """Simulate all possible dialog paths for each root node
        
        Args:
            max_depth (int): Maximum depth to traverse
            
        Returns:
            list: All paths from all root nodes
        """
        all_paths = []
        
        for root_id in self.root_nodes:
            paths = self._simulate_paths_from_node(root_id, [], 0, max_depth, test_mode=True)
            all_paths.extend(paths)
            
        return all_paths
    
    def create_traversal_data(self, all_paths):
        """Create a structured data representation of all traversals
        
        Returns:
            list: A list of traversals, each traversal is a list containing dictionaries with node data
        """
        traversals = []
        
        for path in all_paths:
            traversal = []
            for node_id in path:
                if node_id in ["MAX_DEPTH_REACHED", "NODE_NOT_FOUND"]:
                    # Add special marker nodes
                    traversal.append({
                        "id": node_id,
                        "special_marker": True,
                        "session_id": self.session_id
                    })
                    continue
                    
                node = self._get_node(node_id)
                if not node:
                    # Handle case where node isn't found
                    traversal.append({
                        "id": node_id,
                        "error": "NODE_DATA_NOT_FOUND",
                        "special_marker": True,
                        "session_id": self.session_id
                    })
                    continue

                # Create node data
                node_data = {
                    "id": node_id,
                    "speaker": node.get('speaker', 'Unknown'),
                    "text": node.get('text', ''),
                    "node_type": node.get('node_type', 'normal'),
                    "checkflags": node.get('checkflags', []),
                    "setflags": node.get('setflags', []),
                    "goto": node.get('goto', ''),
                    "link": node.get('link', ''),
                    "is_end": node.get('is_end', False),
                    "approval": node.get('approval', []),
                    "context": node.get('context', ''),
                    "session_id": self.session_id
                }
                traversal.append(node_data)
            
            traversals.append(traversal)
        
        return traversals


class DialogSequenceSimulator:
    """Simulates sequences of dialog sessions from a merged dialog file."""
    
    def __init__(self, json_file):
        """Initialize the dialog sequence simulator with the specified merged JSON file
        
        Args:
            json_file (str): Path to the merged JSON file
        """
        with open(json_file, 'r', encoding='utf-8') as f:
            self.merged_dialog = json.load(f)
        
        self.metadata = self.merged_dialog["metadata"]
        self.dialog_nodes = self.merged_dialog["dialogue"]
        
        # Get source files if available
        self.source_files = self.metadata.get("source_files", [])
        self.individual_metadata = self.metadata.get("individual_metadata", {})
        
        # Group nodes by session ID
        self.sessions = self._group_nodes_by_session()
        
        # Create a simulator for each session
        self.session_simulators = {}
        for session_id, session_nodes in self.sessions.items():
            if session_nodes:  # Only create simulators for sessions with nodes
                self.session_simulators[session_id] = DialogSessionSimulator(session_id, session_nodes)
        
        print(f"Loaded merged dialog with {len(self.dialog_nodes)} total nodes across {len(self.sessions)} sessions")
        
    def _extract_session_id_from_filename(self, filename):
        """Extract session ID from a source filename
        
        Args:
            filename (str): Source filename like "CHA_BronzePlaque_AD_SanctumStatue.json"
            
        Returns:
            str: Extracted session ID like "AD_SanctumStatue"
        """
        # Remove file extension
        name_without_ext = os.path.splitext(filename)[0]
        
        # Split by underscore
        parts = name_without_ext.split('_')
        
        # For filenames like "CHA_BronzePlaque_AD_SanctumStatue.json", 
        # the session ID would be "AD_SanctumStatue"
        if len(parts) >= 3:
            return '_'.join(parts[2:])
        
        return None
    
    def _group_nodes_by_session(self):
        """Group nodes by their session ID
        
        Uses both node ID prefixes and source files to identify sessions
        
        Returns:
            dict: Mapping of session ID to nodes belonging to that session
        """
        sessions = {}
        
        # First, initialize sessions from source_files and individual_metadata
        # These are the officially defined sessions we want to ensure are included
        for session_id in self.individual_metadata.keys():
            sessions[session_id] = {}
            
        # Also try to extract session IDs from source filenames if available
        for filename in self.source_files:
            session_id = self._extract_session_id_from_filename(filename)
            if session_id and session_id not in sessions:
                sessions[session_id] = {}
        
        # Now group nodes by inspecting their IDs
        for node_id, node_data in self.dialog_nodes.items():
            assigned = False
            
            # Check if this node belongs to a known session based on prefix
            for session_id in sessions.keys():
                if node_id.startswith(session_id + "_"):
                    sessions[session_id][node_id] = node_data
                    assigned = True
                    break
            
            # If not assigned yet, try to extract session from node ID itself
            if not assigned and '_' in node_id:
                # Try to get the session ID from the node ID
                parts = node_id.split('_')
                if len(parts) >= 2:
                    # First part could be the session ID prefix
                    potential_session_id = parts[0]
                    
                    # If this is a new session ID, add it
                    if potential_session_id not in sessions:
                        sessions[potential_session_id] = {}
                    
                    # Add node to this session
                    sessions[potential_session_id][node_id] = node_data
                    assigned = True
            
            # If still not assigned, put in an "UNIDENTIFIED" bucket
            if not assigned:
                if "UNIDENTIFIED" not in sessions:
                    sessions["UNIDENTIFIED"] = {}
                sessions["UNIDENTIFIED"][node_id] = node_data
        
        # Remove empty sessions
        return {sid: nodes for sid, nodes in sessions.items() if nodes}
    
    def display_sessions(self):
        """Display information about all sessions in the merged dialog"""
        print(f"\n{Fore.WHITE}===== DIALOG SESSIONS ====={Style.RESET_ALL}")
        
        # Display session info
        for i, (session_id, nodes) in enumerate(self.sessions.items(), 1):
            if session_id in self.session_simulators:
                root_count = len(self.session_simulators[session_id].root_nodes)
                total_count = len(nodes)
                
                # Get session metadata if available
                synopsis = ""
                if session_id in self.individual_metadata:
                    synopsis = self.individual_metadata[session_id].get("synopsis", "")
                
                print(f"{i}. {Fore.YELLOW}{session_id}{Style.RESET_ALL}: {total_count} nodes, {root_count} root nodes")
                if synopsis:
                    print(f"   Synopsis: {synopsis}")
            else:
                print(f"{i}. {Fore.YELLOW}{session_id}{Style.RESET_ALL}: Empty session (no nodes found)")
        
        # Also display source files for reference
        if self.source_files:
            print(f"\n{Fore.WHITE}Source Files:{Style.RESET_ALL}")
            for i, source_file in enumerate(self.source_files, 1):
                session_id = self._extract_session_id_from_filename(source_file)
                print(f"{i}. {source_file} → Session: {session_id or 'Unknown'}")
    
    def simulate_session_sequences(self, max_sequences=100, max_depth=20, export_txt=False, export_json=False, use_all_paths=False):
        """Simulate all possible sequences of dialog sessions
        
        This creates traversals that go through different session combinations
        
        Args:
            max_sequences (int): Maximum number of sequences to generate
            max_depth (int): Maximum depth to traverse within each session
            export_txt (bool): Whether to export to text file
            export_json (bool): Whether to export to JSON file
            use_all_paths (bool): Whether to use all possible paths instead of random selection
            
        Returns:
            tuple: (all_sequence_traversals, txt_file_path, json_file_path)
        """
        print(f"\n{Fore.WHITE}===== DIALOG SEQUENCE SIMULATION ====={Style.RESET_ALL}")
        
        # Filter out sessions that don't have simulators (empty sessions)
        valid_sessions = [sid for sid in self.sessions.keys() if sid in self.session_simulators]
        
        print(f"Simulating sequences across {len(valid_sessions)} valid dialog sessions (max {max_sequences} sequences)")
        
        # Check if we have valid sessions
        if not valid_sessions:
            print(f"{Fore.RED}No valid sessions with nodes found. Cannot simulate sequences.{Style.RESET_ALL}")
            return [], None, None
        
        # Get all paths for each session
        session_paths = {}
        for session_id in valid_sessions:
            simulator = self.session_simulators[session_id]
            print(f"Simulating all paths for session {session_id}...")
            session_paths[session_id] = simulator.simulate_all_paths(max_depth=max_depth)
            print(f"  Found {len(session_paths[session_id])} possible paths")
        
        # Generate all possible session permutations
        print(f"Generating session sequences...")
        
        # Generate sequences of sessions (permutations)
        all_sequences = list(itertools.permutations(valid_sessions))
        
        # Limit the number of sequences if needed
        if len(all_sequences) > max_sequences:
            print(f"{Fore.YELLOW}Limiting to {max_sequences} sequences out of {len(all_sequences)} possible permutations{Style.RESET_ALL}")
            all_sequences = all_sequences[:max_sequences]
        
        # For each sequence, create combined traversals
        all_sequence_traversals = []
        
        for sequence in all_sequences:
            sequence_traversals = []
            
            if use_all_paths:
                # Create one traversal for each possible combination of paths
                path_combinations = []
                for session_id in sequence:
                    if not path_combinations:
                        # Initialize with first session's paths
                        path_combinations = [[path] for path in session_paths[session_id]]
                    else:
                        # Extend with each subsequent session's paths
                        new_combinations = []
                        for combo in path_combinations:
                            for path in session_paths[session_id]:
                                new_combinations.append(combo + [path])
                        path_combinations = new_combinations
                
                # Limit combinations if there are too many
                max_combinations = 10  # Adjust as needed
                if len(path_combinations) > max_combinations:
                    print(f"{Fore.YELLOW}Limiting to {max_combinations} path combinations out of {len(path_combinations)} possible{Style.RESET_ALL}")
                    path_combinations = path_combinations[:max_combinations]
                
                # Create traversals for each combination
                for combination in path_combinations:
                    # Build combined traversal
                    combined_traversal = []
                    for i, path in enumerate(combination):
                        session_id = sequence[i]
                        traversal = self.session_simulators[session_id].create_traversal_data([path])[0]
                        combined_traversal.extend(traversal)
                    
                    sequence_traversals.append({
                        "sequence": list(sequence),
                        "traversal": combined_traversal
                    })
            else:
                # Just pick one random path from each session
                sequence_traversal = []
                for session_id in sequence:
                    # Pick a random path from this session
                    if session_paths[session_id]:
                        path = random.choice(session_paths[session_id])
                        
                        # Create traversal data for this path
                        traversal = self.session_simulators[session_id].create_traversal_data([path])[0]
                        
                        # Add to the sequence traversal
                        sequence_traversal.extend(traversal)
                
                # Add the combined traversal
                sequence_traversals.append({
                    "sequence": list(sequence),
                    "traversal": sequence_traversal
                })
            
            # Add all traversals for this sequence
            all_sequence_traversals.extend(sequence_traversals)
        
        print(f"Generated {len(all_sequence_traversals)} sequence traversals")
        
        # Export results if requested
        txt_file = None
        json_file = None
        
        if export_txt:
            txt_file = self._export_sequences_to_txt(all_sequence_traversals)
        
        if export_json:
            json_file = self._export_sequences_to_json(all_sequence_traversals)
        
        return all_sequence_traversals, txt_file, json_file
    
    def _export_sequences_to_txt(self, all_sequence_traversals, output_file='dialog_sequences.txt'):
        """Export all sequence traversals to a text file
        
        Args:
            all_sequence_traversals (list): List of sequence traversals
            output_file (str): Output file path
            
        Returns:
            str: Path to the output file
        """
        print(f"{Fore.GREEN}Exporting {len(all_sequence_traversals)} sequence traversals to {output_file}...{Style.RESET_ALL}")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"Baldur's Gate 3 Dialog Sequence Traversals\n")
            f.write(f"Total sequences: {len(all_sequence_traversals)}\n\n")
            
            for i, sequence_data in enumerate(all_sequence_traversals, 1):
                sequence = sequence_data["sequence"]
                traversal = sequence_data["traversal"]
                
                f.write(f"Sequence {i}: {' -> '.join(sequence)}\n")
                f.write(f"Traversal:\n")
                
                for node in traversal:
                    # Skip special marker nodes
                    if node.get("special_marker", False):
                        continue
                    
                    speaker = node.get("speaker", "Unknown")
                    text = node.get("text", "")
                    context = node.get("context", "")
                    approvals = node.get("approval", [])
                    session_id = node.get("session_id", "Unknown")
                    
                    # Skip nodes without text
                    if not text:
                        continue
                    
                    # Format the line according to requirements
                    line = f"[{session_id}] "
                    
                    # Handle speaker/text part based on node type
                    if node.get('node_type') == 'tagcinematic':
                        line += f"[description] {text}"
                    else:
                        line += f"{speaker}: {text}"
                    
                    # Add context if present
                    if context:
                        line += f" || [context] {context}"
                    
                    # Add approval changes if present
                    if approvals:
                        line += f" || [approval] {', '.join(approvals)}"
                    
                    # Write the formatted line
                    f.write(f"{line}\n")
                
                f.write("\n")  # Add extra line between sequences
        
        print(f"{Fore.GREEN}Sequence traversals exported successfully to {output_file}{Style.RESET_ALL}")
        return output_file
    
    def _export_sequences_to_json(self, all_sequence_traversals, output_file='dialog_sequences.json'):
        """Export all sequence traversals to a JSON file
        
        Args:
            all_sequence_traversals (list): List of sequence traversals
            output_file (str): Output file path
            
        Returns:
            str: Path to the output file
        """
        print(f"{Fore.GREEN}Exporting {len(all_sequence_traversals)} sequence traversals to {output_file}...{Style.RESET_ALL}")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_sequence_traversals, f, indent=2, ensure_ascii=False)
        
        print(f"{Fore.GREEN}Sequence traversals exported successfully to {output_file}{Style.RESET_ALL}")
        return output_file


def main():
    print(f"{Fore.CYAN}Baldur's Gate 3 Dialog Sequence Simulator{Style.RESET_ALL}")
    print("This tool allows you to explore sequences of dialog trees from the game.")
    
    # Check command line arguments
    if len(sys.argv) > 1:
        merged_file = sys.argv[1]
    else:
        merged_file = input("Enter path to merged dialog file (default: output_merged/Act1/Chapel/cha_bronzeplaque.json): ")
        if not merged_file:
            merged_file = 'output_merged/Act1/Chapel/cha_bronzeplaque.json'
    
    # Check if the file exists
    if not os.path.isfile(merged_file):
        print(f"{Fore.RED}Error: File {merged_file} not found.{Style.RESET_ALL}")
        return
    
    # Create simulator
    simulator = DialogSequenceSimulator(merged_file)
    
    while True:
        print("\nSelect mode:")
        print("1. Display Sessions - Show information about all sessions")
        print("2. Simulate Sequences - Generate and display dialog sequence traversals")
        print("3. Export Sequences - Generate and export dialog sequence traversals")
        print("4. Simulate All Path Combinations - Generate all possible path combinations")
        print("0. Exit")
        
        try:
            choice = int(input("\nEnter choice: "))
            
            if choice == 0:
                break
            elif choice == 1:
                simulator.display_sessions()
            elif choice == 2 or choice == 3 or choice == 4:
                # Get max sequences
                max_sequences = 100
                try:
                    max_input = input(f"Maximum number of sequences to generate (default {max_sequences}): ")
                    if max_input.strip():
                        max_sequences = int(max_input)
                except ValueError:
                    print(f"{Fore.YELLOW}Using default max sequences: {max_sequences}{Style.RESET_ALL}")
                
                # Get max depth
                max_depth = 20
                try:
                    depth_input = input(f"Maximum dialog depth (default {max_depth}): ")
                    if depth_input.strip():
                        max_depth = int(depth_input)
                except ValueError:
                    print(f"{Fore.YELLOW}Using default max depth: {max_depth}{Style.RESET_ALL}")
                
                # Export options for choice 3 and 4
                export_txt = False
                export_json = False
                if choice == 3 or choice == 4:
                    export_txt = input(f"Export to text file? (y/n, default: y): ").lower() != 'n'
                    export_json = input(f"Export to JSON file? (y/n, default: y): ").lower() != 'n'
                
                # Run simulation
                traversals, txt_file, json_file = simulator.simulate_session_sequences(
                    max_sequences=max_sequences,
                    max_depth=max_depth,
                    export_txt=export_txt,
                    export_json=export_json,
                    use_all_paths=(choice == 4)  # Use all paths for option 4
                )
                
                # Display summary
                print(f"\n{Fore.GREEN}Simulation complete.{Style.RESET_ALL}")
                if txt_file:
                    print(f"Text file exported to: {txt_file}")
                if json_file:
                    print(f"JSON file exported to: {json_file}")
                
                # For choice 2, display a sample
                if choice == 2 and traversals:
                    print(f"\n{Fore.WHITE}Sample Sequence Traversal:{Style.RESET_ALL}")
                    sample = traversals[0]
                    sequence = sample["sequence"]
                    traversal = sample["traversal"]
                    
                    print(f"Sequence: {' -> '.join(sequence)}")
                    print(f"Traversal (showing max 10 nodes):")
                    
                    # Display up to 10 nodes
                    count = 0
                    for node in traversal:
                        if not node.get("special_marker", False) and node.get("text", ""):
                            speaker = node.get("speaker", "Unknown")
                            text = node.get("text", "")
                            session_id = node.get("session_id", "Unknown")
                            
                            print(f"[{session_id}] {speaker}: {text}")
                            
                            count += 1
                            if count >= 10:
                                print("...")
                                break
            else:
                print(f"{Fore.RED}Invalid choice. Try again.{Style.RESET_ALL}")
        except ValueError:
            print(f"{Fore.RED}Please enter a number.{Style.RESET_ALL}")

if __name__ == "__main__":
    main() 