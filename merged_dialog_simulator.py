# Filename: merged_dialog_simulator.py

import json
import sys
import os
from colorama import init, Fore, Back, Style
import random
import itertools # Added for permutations
import re # Added for splitting node IDs

# Initialize colorama for colored terminal output
init()

class MergedDialogSimulator:
    def __init__(self, json_file):
        """Initialize the merged dialog simulator with the specified JSON file"""
        print(f"Loading merged dialog file: {json_file}")
        with open(json_file, 'r', encoding='utf-8') as f:
            self.dialog_tree = json.load(f)

        self.metadata = self.dialog_tree["metadata"]
        self.all_nodes = self.dialog_tree["dialogue"]  # All nodes from all sessions

        self.sessions = {} # Store nodes grouped by session prefix
        self.session_roots = {} # Store root nodes for each session
        self.session_prefixes = set() # Store unique session prefixes

        # --- Identify sessions and their nodes ---
        print("Identifying sessions and nodes...")
        for node_id, node_data in self.all_nodes.items():
            # Extract session prefix (part before the last underscore and digit)
            match = re.match(r'^(.*?)_(\d+)$', node_id)
            if match:
                session_prefix = match.group(1)
                self.session_prefixes.add(session_prefix)
                if session_prefix not in self.sessions:
                    self.sessions[session_prefix] = {}
                self.sessions[session_prefix][node_id] = node_data
                # Ensure node_data has its original ID if it wasn't explicitly set
                if 'id' not in node_data or not node_data['id']:
                     node_data['id'] = node_id
            else:
                print(f"{Fore.YELLOW}Warning: Node ID '{node_id}' does not match expected pattern '<prefix>_<number>'. Skipping session assignment.{Style.RESET_ALL}")


        print(f"Identified {len(self.session_prefixes)} sessions: {', '.join(list(self.session_prefixes))}")

        # --- Identify root nodes for each session ---
        print("Identifying root nodes per session...")
        all_child_ids_in_merged_file = set()
        for node_id, node_data in self.all_nodes.items():
             # Use .get() with default empty dict/list
            children_dict = node_data.get('children', {})
            all_child_ids_in_merged_file.update(children_dict.keys())

        for prefix in self.session_prefixes:
            self.session_roots[prefix] = []
            for node_id in self.sessions.get(prefix, {}):
                # A node is a root for its session if it's not a child of *any* node in the merged file
                if node_id not in all_child_ids_in_merged_file:
                    self.session_roots[prefix].append(node_id)
            print(f"  Session '{prefix}': Found {len(self.session_roots[prefix])} root nodes: {', '.join(self.session_roots[prefix])}")

        print(f"Loaded merged dialog tree with {len(self.all_nodes)} total nodes across {len(self.session_prefixes)} sessions.")

        # --- State Tracking (Similar to original) ---
        self.companion_approvals = { "Gale": 0, "Astarion": 0, "Lae'zel": 0, "Shadowheart": 0, "Wyll": 0, "Karlach": 0, "Halsin": 0, "Minthara": 0, "Minsc": 0 }
        self.companion_approval_history = { name: [] for name in self.companion_approvals }
        self.visited_nodes = []
        self.default_flags = ["ORI_INCLUSION_GALE", "ORI_INCLUSION_ASTARION", "ORI_INCLUSION_LAEZEL", "ORI_INCLUSION_SHADOWHEART", "ORI_INCLUSION_WYLL", "ORI_INCLUSION_KARLACH", "ORI_INCLUSION_HALSIN", "ORI_INCLUSION_MINTHARA", "ORI_INCLUSION_MINSC", "ORI_INCLUSION_RANDOM", "ORI_STATE_RECRUITED"]
        self.active_flags = set(self.default_flags)


    def _get_node(self, node_id):
        """Get a node by its full ID from the merged dialog tree"""
        # The node structure is flat in the merged file, so direct lookup works.
        # We need to handle potential nested children if the structure were different,
        # but based on cha_bronzeplaque.json, children are referenced by ID.
        return self.all_nodes.get(node_id)

    # --- Reusing helper methods from original simulator ---
    # (Include _process_approvals, _process_setflags, _check_flags,
    #  display_node, get_available_options, present_options, follow_node_path,
    #  _is_leaf_node, show_companion_status, show_approval_history, reset_state,
    #  export functions etc., directly copied or adapted slightly if needed
    #  for the merged context, though many should work as-is because _get_node
    #  handles the lookup)

    # --- Copied/Adapted Helper Methods ---

    def _process_approvals(self, node_data):
        """Process approval changes from a node"""
        node_id = node_data.get('id', '') # Ensure node_data has 'id'
        for approval in node_data.get('approval', []):
            parts = approval.split()
            if len(parts) >= 2:
                char_name = ' '.join(parts[:-1])
                value = parts[-1]
                try:
                    if char_name in self.companion_approvals:
                        approval_value = int(value)
                        self.companion_approvals[char_name] += approval_value
                        self.companion_approval_history[char_name].append({
                            "node_id": node_id,
                            "value": approval_value,
                            "text": node_data.get('text', ''),
                            "speaker": node_data.get('speaker', '')
                        })
                except (ValueError, KeyError):
                    pass # Ignore malformed approval strings

    def _process_setflags(self, node_data):
        """Process flags that are set by a node"""
        for flag in node_data.get('setflags', []):
            flag_cleaned = flag.strip()
            if "= False" in flag_cleaned:
                flag_to_remove = flag_cleaned.split('= False')[0].strip()
                if flag_to_remove in self.active_flags:
                     self.active_flags.remove(flag_to_remove)
            elif flag_cleaned: # Ensure flag is not empty
                self.active_flags.add(flag_cleaned)

    def _check_flags(self, node_data):
        """Check if required flags are met for a node"""
        required_flags = node_data.get('checkflags', [])
        if not required_flags:
            return True

        for flag in required_flags:
            flag_cleaned = flag.strip()
            if "= False" in flag_cleaned:
                flag_to_check = flag_cleaned.split('= False')[0].strip()
                if flag_to_check in self.active_flags:
                    return False # Condition "flag = False" is not met if flag is active
            elif flag_cleaned: # Ensure flag is not empty
                if flag_cleaned not in self.active_flags:
                    return False # Required flag is not active
        return True

    def display_node(self, node_id, node_data):
        """Display a dialog node with formatting"""
        if not node_data: # Handle case where node data might be missing
            print(f"\n{Fore.RED}[Error: Node data for ID {node_id} not found]{Style.RESET_ALL}")
            return

        speaker = node_data.get('speaker', 'Unknown')
        text = node_data.get('text', '')
        node_type = node_data.get('node_type', 'normal')

        print(f"\n{Fore.BLUE}[Node ID: {node_id}, Type: {node_type}]{Style.RESET_ALL}")

        if speaker == 'Player':
            speaker_format = f"{Fore.CYAN}{speaker}{Style.RESET_ALL}"
        else:
            speaker_format = f"{Fore.YELLOW}{speaker}{Style.RESET_ALL}"

        if text:
            print(f"\n{speaker_format}: {text}")

        context = node_data.get('context', '')
        if context and context.strip():
            print(f"{Fore.GREEN}Context: {context}{Style.RESET_ALL}")

        # Display jump/goto/link information
        if node_type == 'jump' and node_data.get('goto'):
             print(f"{Fore.YELLOW}[Jump node: Will jump to node {node_data.get('goto')}]{Style.RESET_ALL}")
        elif node_data.get('goto'):
             has_children = bool(node_data.get('children', {})) # Check if children dict exists and is not empty
             if not has_children:
                 print(f"{Fore.MAGENTA}[Goto: {node_data.get('goto')} (will follow - no children present)]{Style.RESET_ALL}")
             else:
                 print(f"{Fore.MAGENTA}[Goto: {node_data.get('goto')} (informational only - children present)]{Style.RESET_ALL}")
        if node_data.get('link'):
             has_children = bool(node_data.get('children', {}))
             has_goto = bool(node_data.get('goto', ''))
             if not has_children and not has_goto:
                 print(f"{Fore.MAGENTA}[Link: {node_data.get('link')} (will follow - no children or goto present)]{Style.RESET_ALL}")
             else:
                 print(f"{Fore.MAGENTA}[Link: {node_data.get('link')} (informational only)]{Style.RESET_ALL}")

        if node_data.get('is_end', False):
            print(f"{Fore.RED}[End Node]{Style.RESET_ALL}")

        rolls = node_data.get('rolls', '')
        if rolls and rolls.strip():
            print(f"{Fore.MAGENTA}[Requires roll: {rolls}]{Style.RESET_ALL}")

        approvals = node_data.get('approval', [])
        if approvals:
            print(f"{Fore.BLUE}[Companion reactions: {', '.join(approvals)}]{Style.RESET_ALL}")

    def get_available_options(self, node_data, test_mode=False):
        """Get available dialog options from a node's direct children"""
        if not node_data: return {}
        children = node_data.get('children', {})
        available_options = {}

        original_flags = None
        if test_mode: # Temporarily modify flags only for checking children
            original_flags = self.active_flags.copy()
            for child_id in children:
                child_node = self._get_node(child_id)
                if child_node:
                    for flag in child_node.get('checkflags', []):
                         flag_cleaned = flag.strip()
                         if "= False" not in flag_cleaned and flag_cleaned:
                             self.active_flags.add(flag_cleaned)
                         # Don't need to handle "= False" here, _check_flags does that

        # Now check flags with potentially modified set
        for child_id, child_data_ref in children.items(): # child_data_ref might be minimal in source JSON
            child_node = self._get_node(child_id) # Get full node data
            if not child_node:
                print(f"{Fore.YELLOW}Warning: Child node {child_id} referenced but not found in dialogue data.{Style.RESET_ALL}")
                continue

            if self._check_flags(child_node):  # Check if flags requirements are met
                available_options[child_id] = child_node # Store full node data

        # Restore original flags if they were modified
        if test_mode and original_flags is not None:
            self.active_flags = original_flags

        return available_options

    def present_options(self, options):
        """Display dialog options with numbered choices"""
        if not options:
            print(f"\n{Fore.RED}[End of dialog - No options available]{Style.RESET_ALL}")
            return None

        print(f"\n{Fore.WHITE}Choose your response:{Style.RESET_ALL}")
        option_list = list(options.items()) # List of (id, node_data) tuples

        for i, (option_id, option_data) in enumerate(option_list, 1):
            speaker = option_data.get('speaker', 'Player')
            text = option_data.get('text', '')
            node_type = option_data.get('node_type', 'normal')

            indicators = []
            if option_data.get('approval'): indicators.append(f"{Fore.BLUE}[Approval]{Style.RESET_ALL}")
            if option_data.get('setflags'): indicators.append(f"{Fore.GREEN}[Sets Flag]{Style.RESET_ALL}")
            if option_data.get('is_end', False): indicators.append(f"{Fore.RED}[Ends Dialog]{Style.RESET_ALL}")
            if node_type == 'jump' and option_data.get('goto'): indicators.append(f"{Fore.YELLOW}[Jump->{option_data.get('goto')}]{Style.RESET_ALL}")
            elif option_data.get('goto'): indicators.append(f"{Fore.MAGENTA}[Goto->{option_data.get('goto')}]{Style.RESET_ALL}")
            if option_data.get('link'): indicators.append(f"{Fore.MAGENTA}[Link->{option_data.get('link')}]{Style.RESET_ALL}")

            indicator_text = " ".join(indicators)

            if text:
                print(f"{i}. [{option_id}] {speaker}: {text} {indicator_text}")
            elif node_type == 'jump':
                 print(f"{i}. [{option_id}] {Fore.YELLOW}[Jump to node {option_data.get('goto')}]{Style.RESET_ALL} {indicator_text}")
            else: # Option without text (rare, but possible)
                 print(f"{i}. [{option_id}] {Fore.CYAN}[Node without text]{Style.RESET_ALL} {indicator_text}")

        # Add option to go back (useful in interactive mode, maybe less in simulation)
        # print(f"0. {Fore.RED}[Return to start/cancel]{Style.RESET_ALL}") # Keep or remove based on usage

        choice = None
        while choice is None:
            try:
                choice_input = input(f"\nEnter choice (1-{len(option_list)}): ")
                choice_num = int(choice_input)

                # if choice_num == 0: return "START" # Or "CANCEL"

                if 1 <= choice_num <= len(option_list):
                    choice = option_list[choice_num - 1][0]  # Get the node ID
                else:
                    print(f"{Fore.RED}Invalid choice. Try again.{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED}Please enter a number.{Style.RESET_ALL}")

        return choice

    def follow_node_path(self, node_id):
        """Follow a path from a node, handling jumps, goto, and links recursively"""
        visited_in_follow = set() # Prevent infinite loops in jump/goto/link chains
        current_id = node_id

        while current_id not in visited_in_follow:
            visited_in_follow.add(current_id)
            node = self._get_node(current_id)

            if not node:
                # Node ID in path (e.g., from goto) doesn't exist
                return current_id, None # Return the problematic ID

            node_type = node.get('node_type', 'normal')
            children = node.get('children', {})
            goto = node.get('goto')
            link = node.get('link')

            follow_target = None

            # 1. Jumps take precedence
            if node_type == 'jump' and goto:
                 follow_target = goto
                 # print(f"{Fore.MAGENTA}[Following jump: {current_id} -> {goto}]{Style.RESET_ALL}")

            # 2. Goto if no children
            elif not children and goto:
                 follow_target = goto
                 # print(f"{Fore.MAGENTA}[Following goto (no children): {current_id} -> {goto}]{Style.RESET_ALL}")

            # 3. Link if no children and no goto
            elif not children and not goto and link:
                 follow_target = link
                 # print(f"{Fore.MAGENTA}[Following link (no children/goto): {current_id} -> {link}]{Style.RESET_ALL}")

            # If we found a target to follow, update current_id and loop
            if follow_target:
                current_id = follow_target
                continue # Go to next iteration of the while loop
            else:
                # No jump/goto/link to follow, this is the node to process
                return current_id, node

        # If loop terminates due to revisited node, indicates a cycle
        print(f"{Fore.RED}Error: Detected cycle in jump/goto/link path involving node {current_id}. Path: {' -> '.join(list(visited_in_follow))}{Style.RESET_ALL}")
        return current_id, self._get_node(current_id) # Return the node where cycle detected


    def _is_leaf_node(self, node_id):
        """Check if a node is effectively a leaf in the traversal logic."""
        node = self._get_node(node_id)
        if not node:
            return True # Non-existent node acts as a leaf

        # Explicit end nodes are leaves
        if node.get('is_end', False):
            return True

        # Nodes that jump/goto/link are NOT leaves *unless* the target doesn't exist
        node_type = node.get('node_type', 'normal')
        children = node.get('children', {})
        goto = node.get('goto')
        link = node.get('link')

        if node_type == 'jump' and goto and self._get_node(goto): return False
        if not children and goto and self._get_node(goto): return False
        if not children and not goto and link and self._get_node(link): return False

        # Nodes with available options (children passing flag checks) are not leaves
        # Use test_mode=False for accurate leaf check based on current flags
        options = self.get_available_options(node, test_mode=False)
        if options:
            return False

        # If none of the above, it's a leaf
        return True


    def _simulate_paths_recursive(self, node_id, current_path, visited_in_path, all_paths, depth, max_depth, test_mode, verbose):
        """Recursive helper for simulating paths."""

        if depth >= max_depth:
            all_paths.append(current_path + [node_id, "MAX_DEPTH_REACHED"])
            return

        # Follow jumps/gotos/links first to find the *actual* node to process
        effective_node_id, node = self.follow_node_path(node_id)

        if not node:
            all_paths.append(current_path + [node_id, "NODE_NOT_FOUND"])
            return

        # Prevent cycles within a single path simulation
        if effective_node_id in visited_in_path:
             all_paths.append(current_path + [effective_node_id, "CYCLE_DETECTED"])
             return

        # Add the *effective* node to the path and visited set for this recursion
        new_path = current_path + [effective_node_id]
        new_visited = visited_in_path | {effective_node_id}


        # Check if this effective node is an end point
        # We need to check available options *from this effective node*
        # Use test_mode for option checking consistent with the simulation mode
        options = self.get_available_options(node, test_mode=test_mode)

        is_end_node = node.get('is_end', False)
        is_effectively_leaf = not options # No valid children to proceed to

        if is_end_node or is_effectively_leaf:
            if verbose:
                reason = "explicit end node" if is_end_node else "no valid options"
                print(f"{Fore.GREEN}  Ending path at {effective_node_id} ({reason}){Style.RESET_ALL}")
            all_paths.append(new_path)
            return

        # If not an end point, recurse for each valid option
        if verbose:
             print(f"{'  ' * depth}Node {effective_node_id}: Exploring {len(options)} options...")

        for child_id in options:
             self._simulate_paths_recursive(child_id, new_path, new_visited, all_paths, depth + 1, max_depth, test_mode, verbose)


    def simulate_all_paths_from_root(self, root_node_id, max_depth=50, test_mode=False, verbose=False):
        """Simulate all possible dialog paths starting from a specific root node."""
        if verbose:
            print(f"\n{Fore.CYAN}Simulating paths from root: {root_node_id} (Test Mode: {test_mode}){Style.RESET_ALL}")

        all_paths = []
        initial_visited = set() # Keep track of visited nodes within a single path simulation

        # Need to handle the case where the root itself might immediately jump/goto
        # Use the recursive helper directly
        self._simulate_paths_recursive(root_node_id, [], initial_visited, all_paths, 0, max_depth, test_mode, verbose)

        if verbose:
             print(f"{Fore.CYAN}Finished simulation for root {root_node_id}. Found {len(all_paths)} paths.{Style.RESET_ALL}")

        return all_paths


    # --- New Simulation Logic for Merged Files ---

    def simulate_session_sequences(self, max_depth=50, test_mode=False, verbose=False, export_combined_txt=False, export_combined_json=False):
        """
        Simulates paths for each session, generates permutations, and combines paths.
        Now stores permutation info with each combined path.
        """
        print(f"\n{Fore.WHITE}===== MERGED DIALOG SIMULATOR - SESSION SEQUENCE MODE ====={Style.RESET_ALL}")
        print(f"Simulating individual session paths (max depth {max_depth}, Test Mode: {test_mode})...")

        # 1. Simulate paths for each session individually (Code remains the same)
        session_paths_map = {}
        total_individual_paths = 0
        session_list = sorted(list(self.session_prefixes))
        original_flags_backup = self.active_flags.copy() if test_mode else None

        for session_prefix in session_list:
            session_paths_map[session_prefix] = []
            if not self.session_roots.get(session_prefix):
                print(f"{Fore.YELLOW}  Session '{session_prefix}': No root nodes found, skipping simulation.{Style.RESET_ALL}")
                continue
            print(f"  Simulating for session: {session_prefix}")
            if test_mode and original_flags_backup:
                 self.active_flags = original_flags_backup.copy()
            for root_id in self.session_roots[session_prefix]:
                paths = self.simulate_all_paths_from_root(root_id, max_depth, test_mode, verbose)
                session_paths_map[session_prefix].extend(paths)
            count = len(session_paths_map[session_prefix])
            total_individual_paths += count
            print(f"    Found {count} paths for session '{session_prefix}'")

        if test_mode and original_flags_backup:
            self.active_flags = original_flags_backup
        print(f"\nTotal individual paths across all sessions: {total_individual_paths}")

        # 2. Generate permutations of sessions (Code remains the same)
        print(f"\nGenerating permutations for {len(session_list)} sessions...")
        session_permutations = list(itertools.permutations(session_list))
        print(f"Generated {len(session_permutations)} session permutations.")

        # 3. Combine paths for each permutation
        print("\nCombining paths for each permutation...")
        # *** CHANGE: Store tuples of (permutation, path) ***
        all_combined_traversals_with_perms = []
        skipped_permutations = 0

        for i, perm in enumerate(session_permutations):
            if verbose: print(f"  Processing permutation {i+1}/{len(session_permutations)}: {perm}")
            current_permutation_combinations = [[]]
            possible_permutation = True # Flag to track if this permutation is possible

            for session_name in perm:
                paths_for_session = session_paths_map.get(session_name)
                if not paths_for_session:
                    if verbose: print(f"{Fore.YELLOW}    Skipping permutation {perm} because session '{session_name}' has no paths.{Style.RESET_ALL}")
                    possible_permutation = False
                    skipped_permutations += 1
                    break # Stop processing this permutation

                new_combinations = []
                for existing_combo in current_permutation_combinations:
                    for session_path in paths_for_session:
                        new_combinations.append(existing_combo + session_path)
                current_permutation_combinations = new_combinations
                if verbose: print(f"    After adding session '{session_name}', have {len(current_permutation_combinations)} combined paths.")

            # *** CHANGE: Add paths WITH permutation info if possible ***
            if possible_permutation:
                 for combo_path in current_permutation_combinations:
                      all_combined_traversals_with_perms.append((perm, combo_path)) # Store as tuple

        print(f"\nFinished combining paths.")
        if skipped_permutations > 0:
             print(f"{Fore.YELLOW}Skipped {skipped_permutations} permutations due to sessions with no paths.{Style.RESET_ALL}")
        # *** CHANGE: Report count based on the new list structure ***
        print(f"Total combined 'super-traversals' generated: {len(all_combined_traversals_with_perms)}")

        # 4. Export combined results (optional)
        txt_file = None
        json_file = None
         # *** CHANGE: Pass the list of tuples to export functions ***
        if export_combined_txt and all_combined_traversals_with_perms:
             txt_file = self.export_paths_to_txt(all_combined_traversals_with_perms, output_file='combined_dialog_paths.txt', is_combined=True)
        if export_combined_json and all_combined_traversals_with_perms:
             # Note: JSON export might need adjustment if you want permutation info there too
             # For now, it exports paths; create_traversal_data needs path list only
             paths_only = [item[1] for item in all_combined_traversals_with_perms]
             json_file = self.export_traversals_to_json(paths_only, output_file='combined_dialog_traversals.json', is_combined=True)


        # *** CHANGE: Return the list containing tuples ***
        return all_combined_traversals_with_perms, txt_file, json_file

    # --- Export Functions (Adapted slightly for potentially combined paths) ---

    def export_paths_to_txt(self, paths_list_with_perms, output_file='dialog_paths.txt', is_combined=False):
        """
        Export dialog paths to a text file with custom formatting.
        If is_combined is True, expects paths_list_with_perms to be a list of (permutation, path) tuples.
        """
        title = "Combined Sequential Dialog Paths" if is_combined else "Dialog Paths"
        print(f"{Fore.GREEN}Exporting {len(paths_list_with_perms)} {('combined ' if is_combined else '')}dialog paths to {output_file}...{Style.RESET_ALL}")

        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
             os.makedirs(output_dir)

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"Baldur's Gate 3 - {title}\n")
            f.write(f"Total paths: {len(paths_list_with_perms)}\n\n")

            # *** CHANGE: Iterate through list of tuples ***
            for i, item in enumerate(paths_list_with_perms, 1):
                # Unpack tuple if combined, otherwise assume item is just the path
                if is_combined:
                    perm, path = item
                else:
                    perm, path = None, item # Handle non-combined case if needed

                f.write(f"--- Path {i} ---\n")
                # *** CHANGE: Add Session Order line if available ***
                if perm:
                     f.write(f"Session Order: {' -> '.join(perm)}\n")
                f.write(f"Node Count: {len(path)}\n") # Add node count for context
                f.write("---\n") # Separator

                current_speaker = None
                for node_id in path:
                    # (Rest of the node processing and writing logic remains the same)
                    if node_id in ["MAX_DEPTH_REACHED", "NODE_NOT_FOUND", "CYCLE_DETECTED"]:
                        f.write(f"[{node_id}]\n")
                        current_speaker = None
                        continue

                    node = self._get_node(node_id)
                    if not node:
                        f.write(f"[Error: Node data missing for {node_id}]\n")
                        current_speaker = None
                        continue

                    speaker = node.get('speaker', 'Unknown')
                    text = node.get('text', '').strip()
                    context = node.get('context', '').strip()
                    approvals = node.get('approval', [])
                    node_type = node.get('node_type', 'normal')

                    line = ""
                    if node_type == 'tagcinematic':
                        line = f"[description] {text}" if text else "[description]"
                    elif text:
                         line = f"{speaker}: {text}"
                    else:
                        continue

                    extra_info = []
                    if context: extra_info.append(f"[context] {context}")
                    if approvals: extra_info.append(f"[approval] {', '.join(approvals)}")
                    if extra_info: line += f" || {' || '.join(extra_info)}"

                    f.write(f"{line}\n")

                f.write(f"--- End Path {i} ---\n\n")

        print(f"{Fore.GREEN}Paths exported successfully to {output_file}{Style.RESET_ALL}")
        return output_file
        
    def create_traversal_data(self, paths_list):
        """Create structured data for traversals (list of lists of node dicts)."""
        print(f"{Fore.GREEN}Creating structured traversal data for {len(paths_list)} paths...{Style.RESET_ALL}")
        traversals = []

        for path in paths_list:
            traversal_nodes = []
            for node_id in path:
                if node_id in ["MAX_DEPTH_REACHED", "NODE_NOT_FOUND", "CYCLE_DETECTED"]:
                    traversal_nodes.append({"id": node_id, "special_marker": True})
                    continue

                node = self._get_node(node_id)
                if not node:
                    traversal_nodes.append({"id": node_id, "error": "NODE_DATA_NOT_FOUND", "special_marker": True})
                    continue

                # Simplified node data for export
                node_data = {
                    "id": node_id, # Use the actual node ID from the path
                    "speaker": node.get('speaker', 'Unknown'),
                    "text": node.get('text', ''),
                    "node_type": node.get('node_type', 'normal'),
                    "checkflags": node.get('checkflags', []),
                    "setflags": node.get('setflags', []),
                    "goto": node.get('goto', ''),
                    "link": node.get('link', ''),
                    "is_end": node.get('is_end', False),
                    "approval": node.get('approval', []),
                    "context": node.get('context', '')
                }
                # Add alias resolution info if needed (logic would go here)

                traversal_nodes.append(node_data)
            traversals.append(traversal_nodes)
        return traversals


    def export_traversals_to_json(self, paths_list, output_file='dialog_traversals.json', is_combined=False):
        """Export structured traversal data to a JSON file."""
        print(f"{Fore.GREEN}Exporting {len(paths_list)} {('combined ' if is_combined else '')}traversals to {output_file}...{Style.RESET_ALL}")

        # Ensure the output directory exists
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Create the structured data first
        traversal_data = self.create_traversal_data(paths_list)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(traversal_data, f, indent=2, ensure_ascii=False)

        print(f"{Fore.GREEN}Traversals exported successfully to {output_file}{Style.RESET_ALL}")
        return output_file


def display_help():
     print("\nUsage: python merged_dialog_simulator.py <merged_json_file> [options]")
     print("\nExample: python merged_dialog_simulator.py output_merged/cha_bronzeplaque.json --test --export-txt --verbose")
     print("\nOptions:")
     print("  --test           Run simulation in Test Mode (ignores flag requirements)")
     print("  --depth <N>      Set maximum simulation depth (default: 50)")
     print("  --export-txt     Export combined paths to combined_dialog_paths.txt")
     print("  --export-json    Export combined paths to combined_dialog_traversals.json")
     print("  --verbose        Enable verbose logging during simulation")
     print("  -h, --help       Show this help message")


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ['-h', '--help']:
        display_help()
        return

    json_file = sys.argv[1]
    if not os.path.isfile(json_file):
        print(f"{Fore.RED}Error: Merged JSON file not found: {json_file}{Style.RESET_ALL}")
        return

    # Default settings
    test_mode = False
    max_depth = 50
    export_txt = False
    export_json = False
    verbose = False

    # --- Argument Parsing ---
    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == '--test':
            test_mode = True
            i += 1
        elif arg == '--depth':
            if i + 1 < len(sys.argv):
                try:
                    max_depth = int(sys.argv[i+1])
                    i += 2
                except ValueError:
                    print(f"{Fore.RED}Error: Invalid value for --depth. Must be an integer.{Style.RESET_ALL}")
                    return
            else:
                print(f"{Fore.RED}Error: --depth option requires a number.{Style.RESET_ALL}")
                return
        elif arg == '--export-txt':
             export_txt = True
             i += 1
        elif arg == '--export-json':
             export_json = True
             i += 1
        elif arg == '--verbose':
            verbose = True
            i += 1
        else:
            print(f"{Fore.RED}Error: Unknown option '{arg}'{Style.RESET_ALL}")
            display_help()
            return

    # --- Run Simulation ---
    try:
        simulator = MergedDialogSimulator(json_file)

        combined_traversals, txt_file, json_file = simulator.simulate_session_sequences(
            max_depth=max_depth,
            test_mode=test_mode,
            verbose=verbose,
            export_combined_txt=export_txt,
            export_combined_json=export_json
        )

        # Optionally, print summary or details of combined traversals here
        print("\n--- Simulation Summary ---")
        print(f"Input file: {json_file}")
        print(f"Test Mode: {'Enabled' if test_mode else 'Disabled'}")
        print(f"Max Depth: {max_depth}")
        print(f"Total Combined Traversals Found: {len(combined_traversals)}")
        if txt_file:
             print(f"Combined paths exported to: {txt_file}")
        if json_file:
             print(f"Combined traversals exported to: {json_file}")


    except FileNotFoundError:
        print(f"{Fore.RED}Error: Input file not found at {json_file}{Style.RESET_ALL}")
    except json.JSONDecodeError:
         print(f"{Fore.RED}Error: Failed to decode JSON from {json_file}. Check file format.{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}An unexpected error occurred: {e}{Style.RESET_ALL}")
        # Consider adding traceback printing for debugging
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()