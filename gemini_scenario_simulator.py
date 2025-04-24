import json
import sys
import os
from colorama import init, Fore, Back, Style
import random

# Initialize colorama for colored terminal output
init(autoreset=True) # Automatically reset style after each print

class DialogSimulator:
    def __init__(self, json_file='output/Act2/MoonriseTowers/MOO_Jailbreak_Wulbren.json'):
        """Initialize the dialog simulator with the specified JSON file"""
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                self.dialog_tree = json.load(f)
        except FileNotFoundError:
            print(f"{Fore.RED}Error: JSON file not found at {json_file}{Style.RESET_ALL}")
            sys.exit(1)
        except json.JSONDecodeError:
            print(f"{Fore.RED}Error: Could not decode JSON from {json_file}{Style.RESET_ALL}")
            sys.exit(1)

        self.json_file_path = json_file # Store path for reference
        self.metadata = self.dialog_tree.get("metadata", {})
        self.all_nodes = self.dialog_tree.get("dialogue", {})  # All nodes including children

        if not self.all_nodes:
             print(f"{Fore.YELLOW}Warning: No 'dialogue' section found in {json_file}. Simulator might not function correctly.{Style.RESET_ALL}")
             self.root_nodes = {}
        else:
            # Extract root nodes from the dialog tree
            self.root_nodes = {node_id: node_data for node_id, node_data in self.all_nodes.items()
                               if not self._is_child_node(node_id)}

        print(f"Loaded dialog data from {json_file} with {len(self.all_nodes)} total nodes, {len(self.root_nodes)} root nodes")

        # Companion states to track approval changes
        self.companion_approvals = {
            "Gale": 0, "Astarion": 0, "Lae'zel": 0, "Shadowheart": 0,
            "Wyll": 0, "Karlach": 0, "Halsin": 0, "Minthara": 0, "Minsc": 0
        }

        # Track history of approval changes with node IDs
        self.companion_approval_history = {name: [] for name in self.companion_approvals}

        # Track visited nodes in a session
        self.visited_nodes = []

        # Track flags that have been set during playthrough
        # Default flags might vary per game/scenario, keep it simple for now
        self.default_flags = set([
            # Example default flags - adjust as needed for BG3 context
            # "ORI_INCLUSION_GALE", "ORI_INCLUSION_ASTARION", ...
        ])
        self.active_flags = self.default_flags.copy()

    def _is_child_node(self, node_id):
        """Check if a node is a child node of any other node"""
        for other_id, other_data in self.all_nodes.items():
            if other_id != node_id:
                # Ensure 'children' exists and is a dictionary
                children = other_data.get('children', {})
                if isinstance(children, dict) and node_id in children:
                    return True
        return False

    def _get_node(self, node_id):
        """Get a node by its ID from the loaded dialog tree"""
        # Node IDs are expected to be strings
        node_id_str = str(node_id)
        return self.all_nodes.get(node_id_str)

    # Removed _find_node_in_children as _get_node directly accesses self.all_nodes

    def _process_approvals(self, node_data):
        """Process approval changes from a node"""
        node_id = node_data.get('id', 'UnknownID')
        for approval in node_data.get('approval', []):
            parts = approval.split()
            if len(parts) >= 2:
                char_name = ' '.join(parts[:-1])
                value_str = parts[-1]
                try:
                    # Handle approval values like "1" or "-1"
                    if char_name in self.companion_approvals:
                        approval_value = int(value_str)
                        # Update cumulative approval
                        self.companion_approvals[char_name] += approval_value
                        # Record in approval history with node ID
                        self.companion_approval_history[char_name].append({
                            "node_id": node_id,
                            "value": approval_value,
                            "text": node_data.get('text', ''),
                            "speaker": node_data.get('speaker', '')
                        })
                except (ValueError, KeyError):
                    print(f"{Fore.YELLOW}Warning: Could not parse approval '{approval}' for node {node_id}{Style.RESET_ALL}")
                    pass # Ignore malformed approval strings

    def _process_setflags(self, node_data):
        """Process flags that are set or unset by a node"""
        for flag in node_data.get('setflags', []):
            flag = flag.strip()
            if not flag: continue # Skip empty flags

            if flag.endswith("= False"):
                flag_name = flag[:-len("= False")].strip()
                if flag_name in self.active_flags:
                    self.active_flags.remove(flag_name)
                    # print(f"{Fore.MAGENTA}[Flag unset: {flag_name}]{Style.RESET_ALL}") # Optional debug
            elif flag.endswith("= True"): # Handle explicit "= True" just in case
                 flag_name = flag[:-len("= True")].strip()
                 self.active_flags.add(flag_name)
                 # print(f"{Fore.MAGENTA}[Flag set: {flag_name}]{Style.RESET_ALL}") # Optional debug
            else:
                # Assume flag is being set to True if no value specified
                self.active_flags.add(flag)
                # print(f"{Fore.MAGENTA}[Flag set: {flag}]{Style.RESET_ALL}") # Optional debug

    def _check_flags(self, node_data):
        """Check if required flags are met for a node"""
        required_flags = node_data.get('checkflags', [])
        if not required_flags:
            return True # No flags required

        for flag in required_flags:
            flag = flag.strip()
            if not flag: continue # Skip empty flags

            is_negation = flag.endswith("= False")
            flag_name = flag[:-len("= False")].strip() if is_negation else flag

            flag_present = flag_name in self.active_flags

            if is_negation and flag_present:
                # print(f"{Fore.RED}[Flag check failed: {flag_name} should NOT be set]{Style.RESET_ALL}") # Optional debug
                return False # Required flag negation failed (flag is present)
            if not is_negation and not flag_present:
                # print(f"{Fore.RED}[Flag check failed: {flag_name} MUST be set]{Style.RESET_ALL}") # Optional debug
                return False # Required flag is not present

        return True # All flag checks passed

    def display_metadata(self):
        """Display the metadata if available"""
        print(f"\n{Fore.WHITE}===== METADATA ({os.path.basename(self.json_file_path)}) ====={Style.RESET_ALL}")
        # Display individual metadata if present
        individual_meta = self.metadata.get('individual_metadata', {})
        if individual_meta:
             print(f"{Fore.CYAN}--- Individual Session Info ---{Style.RESET_ALL}")
             for session, meta in individual_meta.items():
                 print(f"{Fore.YELLOW}Session:{Style.RESET_ALL} {session}")
                 print(f"  Synopsis: {meta.get('synopsis', 'N/A')}")
                 print(f"  Trigger: {meta.get('how_to_trigger', 'N/A')}")
        else:
            # Fallback to older synopsis/trigger if individual metadata is missing
            print(f"Synopsis: {self.metadata.get('synopsis', 'N/A')}")
            print(f"How to trigger: {self.metadata.get('how_to_trigger', 'N/A')}")

        # Display source files if present
        source_files = self.metadata.get('source_files', [])
        if source_files:
            print(f"\n{Fore.CYAN}--- Source Files ---{Style.RESET_ALL}")
            print(", ".join(source_files))

        # Display automatic ordering if present
        ordering = self.metadata.get('automatic_ordering', {})
        if ordering:
            print(f"\n{Fore.CYAN}--- Automatic Ordering ---{Style.RESET_ALL}")
            print(f"Reasoning: {ordering.get('reasoning', 'N/A')}")
            if ordering.get('order'):
                print("Order Constraints:")
                for constraint in ordering['order']:
                    preds = ", ".join(constraint.get('predecessor', []))
                    succ = constraint.get('successor', 'N/A')
                    print(f"  [{preds}] must come before [{succ}]")
            if ordering.get('exclusive'):
                print("Exclusive Constraints:")
                for group in ordering['exclusive']:
                    print(f"  Cannot have more than one of: [{', '.join(group)}]")

    def display_node(self, node_id, node_data):
        """Display a dialog node with formatting"""
        speaker = node_data.get('speaker', 'Narrator') # Default to Narrator if speaker is empty
        text = node_data.get('text', '').replace('<br>', '\n') # Handle line breaks
        node_type = node_data.get('node_type', 'normal')

        # Show node ID and type for debugging
        # print(f"\n{Fore.BLUE}[Node ID: {node_id}, Type: {node_type}]{Style.RESET_ALL}") # Optional debug

        # Format based on speaker
        speaker_format = f"{Fore.YELLOW}{speaker}{Style.RESET_ALL}" if speaker != "Player" else f"{Fore.CYAN}{speaker}{Style.RESET_ALL}"

        # Display the dialog text if present
        if text:
            print(f"{speaker_format}: {text}")
        elif node_type == 'jump':
             print(f"{Fore.YELLOW}[Jump node {node_id} -> {node_data.get('goto', '???')}]")
        # else:
        #      print(f"{Fore.MAGENTA}[Node {node_id} ({node_type}) has no text]") # Optional debug

        # Display context if present
        context = node_data.get('context', '')
        if context and context.strip():
            print(f"{Fore.GREEN}  Context: {context}{Style.RESET_ALL}")

        # Display jump/goto/link info if relevant (mainly for debugging/interactive)
        # if node_type == 'jump' and node_data.get('goto'):
        #     print(f"{Fore.YELLOW}  [Jumps to: {node_data.get('goto')}]{Style.RESET_ALL}")
        # elif node_data.get('goto'):
        #     print(f"{Fore.MAGENTA}  [Goto: {node_data.get('goto')}]{Style.RESET_ALL}")
        # if node_data.get('link'):
        #      print(f"{Fore.MAGENTA}  [Link: {node_data.get('link')}]{Style.RESET_ALL}")

        # Display if this is an end node
        if node_data.get('is_end', False):
            print(f"{Fore.RED}  [End Node]{Style.RESET_ALL}")

        # Display rolls if present
        rolls = node_data.get('rolls', '')
        if rolls and rolls.strip():
            print(f"{Fore.MAGENTA}  [Requires roll: {rolls}]{Style.RESET_ALL}")

        # Display approval changes
        approvals = node_data.get('approval', [])
        if approvals:
            print(f"{Fore.BLUE}  [Companion reactions: {', '.join(approvals)}]{Style.RESET_ALL}")

        # Display flags set/checked (for debugging)
        # if node_data.get('checkflags'):
        #     print(f"{Fore.CYAN}  [Checks Flags: {', '.join(node_data['checkflags'])}]{Style.RESET_ALL}")
        # if node_data.get('setflags'):
        #     print(f"{Fore.CYAN}  [Sets/Unsets Flags: {', '.join(node_data['setflags'])}]{Style.RESET_ALL}")


    def get_available_options(self, node_data):
        """Get available dialog options (child nodes) that meet flag requirements"""
        children = node_data.get('children', {})
        if not isinstance(children, dict): # Ensure children is a dict
            return {}

        available_options = {}
        for child_id, child_stub in children.items(): # child_stub might be incomplete
            child_node = self._get_node(child_id) # Get full node data
            if not child_node:
                # print(f"{Fore.YELLOW}Warning: Child node {child_id} referenced but not found in main dialogue list.{Style.RESET_ALL}")
                continue

            if self._check_flags(child_node):  # Check if flags requirements are met
                available_options[child_id] = child_node

        return available_options

    def present_options(self, options):
        """Display dialog options with numbered choices for interactive mode"""
        if not options:
            print(f"\n{Fore.RED}[End of dialog - No options available]{Style.RESET_ALL}")
            return None

        print(f"\n{Fore.WHITE}Choose your response:{Style.RESET_ALL}")
        option_list = list(options.items())

        for i, (option_id, option_data) in enumerate(option_list, 1):
            speaker = option_data.get('speaker', 'Player')
            text = option_data.get('text', '').replace('<br>', ' ') # Single line for options
            node_type = option_data.get('node_type', 'normal')

            # Add visual indicators
            indicators = []
            if option_data.get('approval'): indicators.append(f"{Fore.BLUE}[Approval]{Style.RESET_ALL}")
            if option_data.get('setflags'): indicators.append(f"{Fore.GREEN}[Sets Flag]{Style.RESET_ALL}")
            if option_data.get('is_end', False): indicators.append(f"{Fore.RED}[Ends Dialog]{Style.RESET_ALL}")
            if node_type == 'jump': indicators.append(f"{Fore.YELLOW}[Jump->{option_data.get('goto', '?')}]{Style.RESET_ALL}")
            # Add more indicators (rolls, etc.) if needed

            indicator_text = " ".join(indicators)

            # Display option text or a placeholder
            if text:
                print(f"{i}. [{option_id}] {speaker}: {text} {indicator_text}")
            elif node_type == 'jump':
                print(f"{i}. [{option_id}] {Fore.YELLOW}[Jump to node {option_data.get('goto', '?')}]{Style.RESET_ALL} {indicator_text}")
            elif node_type == 'rollresult':
                 print(f"{i}. [{option_id}] {Fore.MAGENTA}[Roll Result: {option_data.get('text', '???')}]{Style.RESET_ALL} {indicator_text}")
            else:
                print(f"{i}. [{option_id}] {Fore.CYAN}[Continue... (Node without text)]{Style.RESET_ALL} {indicator_text}")

        print(f"0. {Fore.RED}[Return to start]{Style.RESET_ALL}")

        # Get user choice
        while True:
            try:
                choice_input = input("\nEnter choice: ")
                choice_num = int(choice_input)

                if choice_num == 0:
                    return "START" # Special command to go back

                if 1 <= choice_num <= len(option_list):
                    return option_list[choice_num - 1][0]  # Return the chosen node ID
                else:
                    print(f"{Fore.RED}Invalid choice number. Try again.{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED}Please enter a number.{Style.RESET_ALL}")


    def show_root_node_selection(self):
        """Show selection menu for root nodes for interactive mode"""
        print(f"\n{Fore.WHITE}===== SELECT STARTING DIALOG ====={Style.RESET_ALL}")
        if not self.root_nodes:
             print(f"{Fore.YELLOW}No root nodes identified. Cannot start interactive mode.{Style.RESET_ALL}")
             return None

        root_node_list = list(self.root_nodes.items())

        for i, (node_id, node_data) in enumerate(root_node_list, 1):
            speaker = node_data.get('speaker', 'Narrator')
            text_preview = node_data.get('text', '').replace('<br>', ' ')
            if len(text_preview) > 60: text_preview = text_preview[:57] + "..."
            if not text_preview: text_preview = f"[{node_data.get('node_type', 'node')}]" # Placeholder if no text

            print(f"{i}. [{node_id}] {speaker}: {text_preview}")

        print(f"0. {Fore.RED}[Exit simulator]{Style.RESET_ALL}")

        # Get user choice
        while True:
            try:
                choice_input = input("\nSelect a root node to start dialog: ")
                choice_num = int(choice_input)

                if choice_num == 0:
                    return None # Exit

                if 1 <= choice_num <= len(root_node_list):
                    return root_node_list[choice_num - 1][0]  # Return the chosen root node ID
                else:
                    print(f"{Fore.RED}Invalid choice number. Try again.{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED}Please enter a number.{Style.RESET_ALL}")

    def follow_node_path(self, node_id, visited_in_chain=None):
        """Follows jumps, gotos (if no children), and links (if no children/goto) recursively.
           Returns the final destination node ID and its data. Detects simple loops."""
        if visited_in_chain is None:
            visited_in_chain = set()

        if node_id in visited_in_chain:
            print(f"{Fore.RED}Error: Loop detected in jump/goto/link chain involving node {node_id}. Aborting path.{Style.RESET_ALL}")
            return node_id, None # Return last valid node before loop

        visited_in_chain.add(node_id)

        node = self._get_node(node_id)
        if not node:
            # print(f"{Fore.YELLOW}Warning: Node {node_id} not found during path following.{Style.RESET_ALL}")
            return node_id, None # Return the ID we were looking for, but indicate data is missing

        node_type = node.get('node_type', 'normal')
        children = node.get('children', {})
        goto_target = node.get('goto')
        link_target = node.get('link')

        # 1. Always follow jumps
        if node_type == 'jump' and goto_target:
            # print(f"{Fore.MAGENTA}[Following jump: {node_id} -> {goto_target}]{Style.RESET_ALL}") # Optional debug
            return self.follow_node_path(goto_target, visited_in_chain)

        # 2. Follow goto if no children
        if not children and goto_target:
            # print(f"{Fore.MAGENTA}[Following goto (no children): {node_id} -> {goto_target}]{Style.RESET_ALL}") # Optional debug
            return self.follow_node_path(goto_target, visited_in_chain)

        # 3. Follow link if no children and no goto
        if not children and not goto_target and link_target:
            # print(f"{Fore.MAGENTA}[Following link (no children/goto): {node_id} -> {link_target}]{Style.RESET_ALL}") # Optional debug
            return self.follow_node_path(link_target, visited_in_chain)

        # 4. If none of the above apply, this is the destination node
        return node_id, node


    def interactive_mode(self):
        """Start the interactive dialog mode"""
        print(f"\n{Fore.WHITE}===== DIALOG SIMULATOR - INTERACTIVE MODE ====={Style.RESET_ALL}")
        print("Explore the dialog tree by selecting options.")

        while True:
            # Reset state for each new exploration from root
            self.reset_state()

            # Show root node selection
            root_node_id = self.show_root_node_selection()
            if not root_node_id:
                break # User chose to exit

            # Start exploration from the chosen root node
            self.explore_dialog_from_node(root_node_id, interactive=True)

            # Show companion approval status at the end of the exploration
            self.show_companion_status()

    def explore_dialog_from_node(self, start_node_id, interactive=False, export_txt=False, export_json=False, export_approval=False):
        """Explore dialog starting from a specific node.
           If interactive, prompts user for choices. Otherwise, uses simulate_one_path logic.

        Args:
            start_node_id (str): The node ID to start from.
            interactive (bool): If True, prompts user for choices.
            export_txt (bool): Whether to export the traversal to a text file (only if not interactive).
            export_json (bool): Whether to export the traversal to a JSON file (only if not interactive).
            export_approval (bool): Whether to export approval history to a JSON file.

        Returns:
            tuple: (visited_nodes_ids, txt_file_path, json_file_path, approval_file_path)
                   visited_node_ids is the list of node IDs in the traversal.
                   File paths are None if not exported.
        """
        current_node_id = start_node_id
        self.visited_nodes = [] # Reset visited nodes for this run
        visited_node_details = [] # Store full data for export

        print(f"\n{Fore.CYAN}--- Starting Dialog Exploration from Node {current_node_id} ---{Style.RESET_ALL}")

        while current_node_id:
            # 1. Follow jumps/gotos/links to find the actual node to process
            effective_node_id, current_node = self.follow_node_path(current_node_id)

            if not current_node:
                print(f"{Fore.RED}Error: Could not resolve node data for {current_node_id} (or followed path led to missing node {effective_node_id}). Ending exploration.{Style.RESET_ALL}")
                break

            # Use the effective node ID from now on
            current_node_id = effective_node_id

            # Prevent re-visiting the exact same node state in non-interactive mode (simple loop break)
            # More complex state tracking (flags) would be needed for full cycle detection
            if not interactive and current_node_id in self.visited_nodes:
                 print(f"{Fore.YELLOW}Warning: Revisiting node {current_node_id}. Stopping path to prevent potential infinite loop.{Style.RESET_ALL}")
                 break
            self.visited_nodes.append(current_node_id)

            # Store details for potential export
            node_data_copy = { k: v for k, v in current_node.items() if k != 'children'} # Copy without children
            node_data_copy['id'] = current_node_id # Ensure ID is correct
            visited_node_details.append(node_data_copy)

            # 2. Display the current node
            self.display_node(current_node_id, current_node)

            # 3. Process side effects (flags, approvals)
            self._process_approvals(current_node)
            self._process_setflags(current_node)

            # 4. Check for end conditions
            if current_node.get('is_end', False):
                print(f"\n{Fore.RED}[End of dialog path - Explicit 'is_end' flag]{Style.RESET_ALL}")
                break

            # 5. Get available options (children that pass flag checks)
            options = self.get_available_options(current_node)

            if not options:
                # Check if there's a goto or link we didn't follow (e.g., because node had children initially)
                # This logic is now handled by follow_node_path, so if options is empty, it's a true end
                print(f"\n{Fore.RED}[End of dialog path - No available options or next steps]{Style.RESET_ALL}")
                break

            # 6. Choose next node
            if interactive:
                choice = self.present_options(options)
                if choice == "START": # User chose to go back to root selection
                    current_node_id = None # End this exploration loop
                else:
                    current_node_id = choice # Move to the chosen node ID
            else:
                # Non-interactive: Automatically pick the first available option
                # (Could be randomized or use other logic if needed)
                first_option_id = list(options.keys())[0]
                print(f"{Fore.MAGENTA}[Auto-selecting first option: {first_option_id}]{Style.RESET_ALL}")
                current_node_id = first_option_id

        print(f"\n{Fore.CYAN}--- Dialog Exploration Complete (Visited {len(self.visited_nodes)} nodes) ---{Style.RESET_ALL}")

        # Export results if requested (and not interactive)
        txt_file = None
        json_file = None
        approval_file = None

        if not interactive:
            if export_txt and self.visited_nodes:
                txt_file = self.export_traversal_to_txt(start_node_id, self.visited_nodes, visited_node_details)
            if export_json and self.visited_nodes:
                 json_file = self.export_traversal_to_json(start_node_id, self.visited_nodes, visited_node_details)

        # Export approval history if requested (works in both modes)
        if export_approval and any(self.companion_approval_history.values()):
            approval_file = self.export_approval_history(f'node_{start_node_id}_approvals.json')

        return self.visited_nodes, txt_file, json_file, approval_file


    # <<< NEW METHOD for non-interactive single path simulation >>>
    def simulate_one_path(self, start_node_id, max_depth=50):
        """Simulates a single, deterministic path from a start node.
           Follows jumps/gotos/links and picks the *first* valid child if choices exist.

        Args:
            start_node_id (str): The node ID to start simulation from.
            max_depth (int): Maximum number of steps to prevent infinite loops.

        Returns:
            list: A list of node IDs representing the simulated path.
                  Returns empty list if start node is invalid or max depth reached immediately.
        """
        print(f"{Fore.CYAN}--- Simulating single path from: {start_node_id} ---{Style.RESET_ALL}")
        current_node_id = start_node_id
        path_node_ids = []
        path_node_details = [] # To store data for formatting later if needed
        visited_for_loop_detection = set() # Detect loops within this simulation run

        for depth in range(max_depth):
            # 1. Follow jumps/gotos/links to find the actual node to process
            # Pass the loop detection set specific to this run
            effective_node_id, current_node = self.follow_node_path(current_node_id, visited_in_chain=set())

            if not current_node:
                print(f"{Fore.RED}Error: Could not resolve node data for {current_node_id} (or path led to missing node {effective_node_id}). Ending path simulation.{Style.RESET_ALL}")
                break

            current_node_id = effective_node_id # Update to the node we actually landed on

            # 2. Basic loop detection for this simulation run
            if current_node_id in visited_for_loop_detection:
                 print(f"{Fore.YELLOW}Warning: Loop detected! Revisiting node {current_node_id}. Stopping path simulation.{Style.RESET_ALL}")
                 break
            visited_for_loop_detection.add(current_node_id)

            # 3. Add to path and process effects (optional here, depends if flags affect path choice)
            path_node_ids.append(current_node_id)
            # Optional: Store details if needed for later formatting
            # node_data_copy = { k: v for k, v in current_node.items() if k != 'children'}
            # node_data_copy['id'] = current_node_id
            # path_node_details.append(node_data_copy)

            # Process flags *before* getting options, as they might affect availability
            self._process_setflags(current_node)
            # Process approvals (doesn't affect path, but good to track if needed later)
            # self._process_approvals(current_node)

            # Display node (optional for non-interactive simulation)
            # self.display_node(current_node_id, current_node)

            # 4. Check for end conditions
            if current_node.get('is_end', False):
                # print(f"{Fore.GREEN}[Path ended: Explicit 'is_end' flag on node {current_node_id}]{Style.RESET_ALL}")
                break

            # 5. Get available options (children that pass flag checks)
            options = self.get_available_options(current_node)

            if not options:
                # print(f"{Fore.GREEN}[Path ended: No available options from node {current_node_id}]{Style.RESET_ALL}")
                break

            # 6. Deterministically choose the next node: pick the first one
            # The order depends on how keys are stored/retrieved in the JSON/dict
            next_node_id = list(options.keys())[0]
            # print(f"{Fore.MAGENTA}[Auto-selecting first option: {next_node_id} from {current_node_id}]{Style.RESET_ALL}") # Optional debug
            current_node_id = next_node_id

        else:
            # This else block executes if the loop finished without a 'break'
            print(f"{Fore.YELLOW}Warning: Simulation stopped after reaching max depth ({max_depth}). Path may be incomplete.{Style.RESET_ALL}")
            path_node_ids.append("MAX_DEPTH_REACHED")


        print(f"{Fore.CYAN}--- Simulation finished. Path length: {len(path_node_ids)} ---{Style.RESET_ALL}")
        return path_node_ids
    # <<< END OF NEW METHOD >>>


    def _is_leaf_node(self, node_id):
        """Check if a node is effectively a leaf node in the dialog graph
           (has is_end flag, or no valid children/goto/link)."""
        node = self._get_node(node_id)
        if not node:
            return True # Non-existent node is effectively an end

        # Explicit end flag
        if node.get('is_end', False):
            return True

        # Check for potential next steps: children, goto, link
        has_goto = bool(node.get('goto'))
        has_link = bool(node.get('link'))
        # Check for *valid* children (pass flag checks)
        available_children = self.get_available_options(node)
        has_valid_children = bool(available_children)

        # It's a leaf if there are no valid children AND no goto AND no link
        if not has_valid_children and not has_goto and not has_link:
            return True

        # Special case: A node with children might still be a leaf if *none* of the children are valid due to flags
        # This is covered by checking `has_valid_children`

        # If it has valid children OR a goto OR a link, it's not a leaf
        return False


    # --- Simulation of ALL paths (kept for potential future use, but not primary for scenario simulation) ---
    def _simulate_all_paths_recursive(self, node_id, current_path, visited_in_branch, all_paths, max_depth, test_mode=False, verbose=False):
        """Recursive helper for simulating all paths."""

        # 1. Handle depth and loop detection
        if len(current_path) >= max_depth:
            all_paths.append(current_path + [node_id] + ["MAX_DEPTH_REACHED"])
            return
        if node_id in visited_in_branch:
            all_paths.append(current_path + [node_id] + ["LOOP_DETECTED"])
            return

        # 2. Follow jumps/gotos/links
        effective_node_id, node = self.follow_node_path(node_id, visited_in_chain=set()) # Use fresh chain check
        if not node:
            all_paths.append(current_path + [node_id] + ["NODE_NOT_FOUND"])
            return

        # Update current path and visited set for this branch
        current_path = current_path + [effective_node_id]
        visited_in_branch.add(effective_node_id)

        if verbose: print(f"{Fore.GREEN}Simulating from: {effective_node_id} (Depth: {len(current_path)}){Style.RESET_ALL}")

        # 3. Process flags if not in test mode
        original_flags = None
        if not test_mode:
            original_flags = self.active_flags.copy()
            self._process_setflags(node) # Apply flags for this node
        # Note: Test mode logic (ignoring flags) is handled in get_available_options if needed

        # 4. Check for end condition
        if node.get('is_end', False):
            if verbose: print(f"{Fore.RED}  Path ended (is_end): {effective_node_id}{Style.RESET_ALL}")
            all_paths.append(current_path)
            # Restore flags if modified
            if original_flags is not None: self.active_flags = original_flags
            return # Stop exploring this branch

        # 5. Get available children (respecting flags unless test_mode)
        # Modify get_available_options if test_mode needs to bypass flag checks there
        options = self.get_available_options(node)

        # 6. If no options, this path ends here
        if not options:
            if verbose: print(f"{Fore.RED}  Path ended (no options): {effective_node_id}{Style.RESET_ALL}")
            all_paths.append(current_path)
            # Restore flags if modified
            if original_flags is not None: self.active_flags = original_flags
            return # Stop exploring this branch

        # 7. Recursively explore each child option
        if verbose: print(f"{Fore.BLUE}  Options from {effective_node_id}: {list(options.keys())}{Style.RESET_ALL}")
        for child_id in options:
            # Pass a copy of the visited set to avoid interference between branches
            self._simulate_all_paths_recursive(child_id, current_path, visited_in_branch.copy(), all_paths, max_depth, test_mode, verbose)

        # 8. Restore flags after exploring all children from this node
        if original_flags is not None:
            self.active_flags = original_flags


    def simulate_all_paths(self, max_depth=50, print_paths=False, test_mode=False, export_txt=False, export_json=False, export_dict=False, verbose=False):
        """Simulate ALL possible dialog paths starting from EACH root node.

        Args:
            max_depth (int): Maximum depth for any single path.
            print_paths (bool): Whether to print each found path to the console.
            test_mode (bool): If True, attempts to ignore flag requirements (may need adjustment in _check_flags).
            export_txt (bool): Export paths to a formatted text file.
            export_json (bool): Export structured traversal data to JSON.
            export_dict (bool): Export paths to a Python dictionary file.
            verbose (bool): Print detailed simulation steps.

        Returns:
            tuple: (all_paths_list, txt_file, json_file, dict_file)
                   all_paths_list contains lists of node IDs for each path.
                   File paths are None if not exported.
        """
        print(f"\n{Fore.WHITE}===== DIALOG SIMULATOR - SIMULATING ALL PATHS ====={Style.RESET_ALL}")
        self.display_metadata()
        print(f"Simulating all dialog paths (max depth {max_depth})...")
        if test_mode: print(f"{Fore.YELLOW}Running in TEST MODE - Flag requirements might be ignored.{Style.RESET_ALL}")
        if verbose: print(f"{Fore.BLUE}Verbose mode enabled.{Style.RESET_ALL}")

        # Store original flags to restore after simulation
        initial_flags_backup = self.active_flags.copy()

        all_paths_list = []
        total_leaf_paths = 0

        if not self.root_nodes:
             print(f"{Fore.RED}Error: No root nodes found. Cannot simulate paths.{Style.RESET_ALL}")
             return [], None, None, None

        for root_id in self.root_nodes:
            print(f"\n{Fore.YELLOW}--- Simulating from Root Node: {root_id} ---{Style.RESET_ALL}")
            # Reset flags and path list for each root node simulation
            self.active_flags = initial_flags_backup.copy()
            paths_from_root = []
            self._simulate_all_paths_recursive(root_id, [], set(), paths_from_root, max_depth, test_mode, verbose)

            # Analyze paths from this root
            leaf_paths_count = 0
            if paths_from_root:
                for i, path in enumerate(paths_from_root, 1):
                    is_leaf = False
                    follow_info = ""
                    last_node_id = path[-1]

                    # Check if path ended normally or due to limit/error
                    if last_node_id in ["MAX_DEPTH_REACHED", "LOOP_DETECTED", "NODE_NOT_FOUND"]:
                        leaf_marker = f"{Fore.RED}[{last_node_id}]{Style.RESET_ALL}"
                    else:
                        # Check if the last valid node is a leaf according to game logic
                        is_leaf = self._is_leaf_node(last_node_id)
                        leaf_marker = f"{Fore.GREEN}[LEAF]{Style.RESET_ALL}" if is_leaf else ""
                        if is_leaf: leaf_paths_count += 1

                        # Check if the last node had an un-followed goto/link (informational)
                        last_node_data = self._get_node(last_node_id)
                        if last_node_data:
                            if last_node_data.get('goto'): follow_info += f" {Fore.MAGENTA}[GOTO:{last_node_data['goto']}]{Style.RESET_ALL}"
                            if last_node_data.get('link'): follow_info += f" {Fore.MAGENTA}[LINK:{last_node_data['link']}]{Style.RESET_ALL}"

                    if print_paths:
                        print(f"  Path {i}: {' -> '.join(map(str, path))} {leaf_marker}{follow_info}")

                print(f"  Paths found from root {root_id}: {len(paths_from_root)}")
                print(f"  Paths ending at leaf nodes: {leaf_paths_count}")
                all_paths_list.extend(paths_from_root)
                total_leaf_paths += leaf_paths_count
            else:
                 print(f"{Fore.YELLOW}  No paths found starting from root {root_id}.{Style.RESET_ALL}")


        print(f"\nTotal dialog paths simulated: {len(all_paths_list)}")
        print(f"Total paths ending at leaf nodes: {total_leaf_paths}")

        # Restore initial flags
        self.active_flags = initial_flags_backup

        # Export results if requested
        txt_file = None
        json_file = None
        dict_file = None

        if export_txt and all_paths_list:
            txt_file = self.export_paths_to_txt(all_paths_list)
        if export_json and all_paths_list:
            traversals = self.create_traversal_data(all_paths_list)
            json_file = self.export_traversals_to_json(traversals)
        if export_dict and all_paths_list:
             dict_file = self.export_paths_to_dict(all_paths_list)

        return all_paths_list, txt_file, json_file, dict_file
    # --- End of ALL paths simulation ---


    def show_companion_status(self):
        """Display current companion approval status"""
        print(f"\n{Fore.CYAN}===== COMPANION APPROVAL STATUS ====={Style.RESET_ALL}")
        has_changes = False
        for companion, value in self.companion_approvals.items():
            history_count = len(self.companion_approval_history[companion])
            if value != 0 or history_count > 0:
                 has_changes = True
                 status_color = Fore.GREEN if value > 0 else Fore.RED if value < 0 else Fore.WHITE
                 value_str = f"+{value}" if value > 0 else str(value)
                 print(f"{companion}: {status_color}{value_str}{Style.RESET_ALL} ({history_count} changes)")

        if not has_changes:
             print("No approval changes recorded in this session.")
             return

        # Option to show detailed history
        if any(self.companion_approval_history.values()):
            show_details = input(f"\nShow detailed approval history? (y/n): ").lower() == 'y'
            if show_details:
                self.show_approval_history()

    def show_approval_history(self):
        """Display the detailed history of approval changes"""
        print(f"\n{Fore.CYAN}===== COMPANION APPROVAL HISTORY ====={Style.RESET_ALL}")
        any_changes = False
        for companion, changes in self.companion_approval_history.items():
            if changes:
                any_changes = True
                print(f"\n{Fore.YELLOW}{companion}:{Style.RESET_ALL}")
                for i, change in enumerate(changes, 1):
                    node_id = change.get('node_id', 'UnknownID')
                    value = change.get('value', 0)
                    speaker = change.get('speaker', 'Unknown')
                    text = change.get('text', '').replace('<br>', ' ')
                    if len(text) > 70: text = text[:67] + "..."

                    value_color = Fore.GREEN if value > 0 else Fore.RED if value < 0 else Fore.WHITE
                    value_str = f"+{value}" if value > 0 else str(value)

                    print(f"  {i}. Node {node_id}: {value_color}{value_str}{Style.RESET_ALL}")
                    if text: print(f"     Trigger: {speaker}: \"{text}\"")
        if not any_changes:
            print(f"{Fore.YELLOW}No approval changes recorded.{Style.RESET_ALL}")

    def reset_state(self):
        """Reset companion approvals, history, visited nodes, and flags"""
        for companion in self.companion_approvals:
            self.companion_approvals[companion] = 0
            self.companion_approval_history[companion] = []
        self.visited_nodes = []
        self.active_flags = self.default_flags.copy()
        print(f"\n{Fore.GREEN}Simulator state reset (approvals, flags, history cleared).{Style.RESET_ALL}")


    # --- Export Functions ---
    def get_formatted_node_line(self, node_id, node_data):
         """Formats a single node into the 'Speaker: Text || [context] || [approval]' format."""
         if not node_data: return f"[Node {node_id} data not found]"

         speaker = node_data.get('speaker', 'Narrator')
         text = node_data.get('text', '').replace('<br>', '\n') # Keep line breaks for text export
         context = node_data.get('context', '')
         approvals = node_data.get('approval', [])
         node_type = node_data.get('node_type', 'normal')

         # Skip nodes without text unless they are descriptive cinematics
         if not text and node_type != 'tagcinematic':
              return None # Don't include purely structural nodes in text output

         line_parts = []

         # Handle speaker/text part
         if node_type == 'tagcinematic':
              line_parts.append(f"[description] {text}")
         else:
              line_parts.append(f"{speaker}: {text}")

         # Add context if present
         if context:
              line_parts.append(f"[context] {context}")

         # Add approval changes if present
         if approvals:
              line_parts.append(f"[approval] {', '.join(approvals)}")

         return " || ".join(line_parts)


    def export_traversal_to_txt(self, start_node_id, node_ids, node_details_list, output_dir='output_traversals'):
        """Exports a single traversal path to a text file with custom formatting."""
        if not node_ids: return None

        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, f'traversal_{start_node_id}.txt')

        print(f"{Fore.GREEN}Exporting traversal from {start_node_id} to {output_file}...{Style.RESET_ALL}")

        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"Dialog Traversal from Node {start_node_id}\n")
                f.write(f"Source JSON: {self.json_file_path}\n")
                f.write(f"Total nodes in path: {len(node_ids)}\n")
                f.write(f"Path IDs: {' -> '.join(map(str, node_ids))}\n\n")
                f.write("--- Dialog ---\n")

                # Use the detailed node data captured during traversal
                for node_data in node_details_list:
                    node_id = node_data.get('id', 'UnknownID')
                    formatted_line = self.get_formatted_node_line(node_id, node_data)
                    if formatted_line: # Only write lines with actual content
                        f.write(f"{formatted_line}\n")

            print(f"{Fore.GREEN}Traversal exported successfully.{Style.RESET_ALL}")
            return output_file
        except IOError as e:
            print(f"{Fore.RED}Error exporting traversal to text: {e}{Style.RESET_ALL}")
            return None


    def export_traversal_to_json(self, start_node_id, node_ids, node_details_list, output_dir='output_traversals'):
        """Exports a single traversal path to a JSON file."""
        if not node_ids: return None

        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, f'traversal_{start_node_id}.json')

        print(f"{Fore.GREEN}Exporting traversal data from {start_node_id} to {output_file}...{Style.RESET_ALL}")

        export_data = {
            "start_node": start_node_id,
            "source_json": self.json_file_path,
            "path_node_ids": node_ids,
            "nodes_in_path": node_details_list # Already contains simplified dicts
        }

        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)

            print(f"{Fore.GREEN}Traversal data exported successfully.{Style.RESET_ALL}")
            return output_file
        except IOError as e:
            print(f"{Fore.RED}Error exporting traversal to JSON: {e}{Style.RESET_ALL}")
            return None
        except TypeError as e:
             print(f"{Fore.RED}Error serializing traversal data to JSON: {e}{Style.RESET_ALL}")
             return None


    def export_paths_to_txt(self, all_paths, output_dir='output_traversals'):
        """Exports ALL simulated paths to a single text file."""
        if not all_paths: return None

        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, f'all_paths_{os.path.basename(self.json_file_path)}.txt')
        print(f"{Fore.GREEN}Exporting {len(all_paths)} dialog paths to {output_file}...{Style.RESET_ALL}")

        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"Baldur's Gate 3 Dialog Paths Simulation\n")
                f.write(f"Source JSON: {self.json_file_path}\n")
                f.write(f"Total paths found: {len(all_paths)}\n\n")
                if self.metadata:
                    f.write("--- Metadata ---\n")
                    # Simple JSON dump of metadata for reference
                    json.dump(self.metadata, f, indent=2)
                    f.write("\n\n---\n\n")


                for i, path in enumerate(all_paths, 1):
                    f.write(f"--- Path {i} ---\n")
                    f.write(f"Node IDs: {' -> '.join(map(str, path))}\n\n")

                    # Add custom formatted output for each node in the path
                    for node_id in path:
                        if isinstance(node_id, str) and node_id in ["MAX_DEPTH_REACHED", "LOOP_DETECTED", "NODE_NOT_FOUND"]:
                            f.write(f"[{node_id}]\n")
                            continue

                        node_data = self._get_node(node_id)
                        formatted_line = self.get_formatted_node_line(node_id, node_data)
                        if formatted_line:
                            f.write(f"{formatted_line}\n")

                    f.write("\n") # Add extra line between paths

            print(f"{Fore.GREEN}All paths exported successfully.{Style.RESET_ALL}")
            return output_file
        except IOError as e:
            print(f"{Fore.RED}Error exporting paths to text: {e}{Style.RESET_ALL}")
            return None


    def create_traversal_data(self, all_paths):
        """Creates structured data for ALL traversals (list of lists of node dicts)."""
        print(f"{Fore.GREEN}Creating structured traversal data for {len(all_paths)} paths...{Style.RESET_ALL}")
        traversals = []
        for path in all_paths:
            traversal_nodes = []
            for node_id in path:
                if isinstance(node_id, str) and node_id in ["MAX_DEPTH_REACHED", "LOOP_DETECTED", "NODE_NOT_FOUND"]:
                    traversal_nodes.append({"id": node_id, "special_marker": True})
                    continue

                node_data = self._get_node(node_id)
                if node_data:
                    # Create a simplified copy, excluding children
                    node_copy = {k: v for k, v in node_data.items() if k != 'children'}
                    node_copy['id'] = node_id # Ensure ID is present
                    traversal_nodes.append(node_copy)
                else:
                    traversal_nodes.append({"id": node_id, "error": "NODE_DATA_NOT_FOUND"})
            traversals.append(traversal_nodes)
        return traversals


    def export_traversals_to_json(self, traversals, output_dir='output_traversals'):
        """Exports structured data for ALL traversals to a JSON file."""
        if not traversals: return None

        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, f'all_traversals_{os.path.basename(self.json_file_path)}.json')
        print(f"{Fore.GREEN}Exporting {len(traversals)} traversals to {output_file}...{Style.RESET_ALL}")

        export_data = {
             "source_json": self.json_file_path,
             "metadata": self.metadata, # Include metadata for context
             "traversals": traversals
        }

        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            print(f"{Fore.GREEN}All traversals exported successfully.{Style.RESET_ALL}")
            return output_file
        except IOError as e:
             print(f"{Fore.RED}Error exporting traversals to JSON: {e}{Style.RESET_ALL}")
             return None
        except TypeError as e:
             print(f"{Fore.RED}Error serializing traversals data to JSON: {e}{Style.RESET_ALL}")
             return None


    def export_approval_history(self, output_file='approval_history.json', output_dir='output_traversals'):
        """Exports the current approval history to a JSON file."""
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        full_output_path = os.path.join(output_dir, output_file)

        print(f"{Fore.GREEN}Exporting approval history to {full_output_path}...{Style.RESET_ALL}")

        history_data = {
            "source_json": self.json_file_path,
            "current_approvals": self.companion_approvals,
            "approval_history": self.companion_approval_history
        }

        # Filter out companions with no history for cleaner output
        history_data["approval_history"] = {
             comp: hist for comp, hist in self.companion_approval_history.items() if hist
        }

        if not history_data["approval_history"] and not any(v != 0 for v in history_data["current_approvals"].values()):
             print(f"{Fore.YELLOW}No approval changes or non-zero totals to export.{Style.RESET_ALL}")
             return None

        try:
            with open(full_output_path, 'w', encoding='utf-8') as f:
                json.dump(history_data, f, indent=2, ensure_ascii=False)
            print(f"{Fore.GREEN}Approval history exported successfully.{Style.RESET_ALL}")
            return full_output_path
        except IOError as e:
             print(f"{Fore.RED}Error exporting approval history: {e}{Style.RESET_ALL}")
             return None
        except TypeError as e:
             print(f"{Fore.RED}Error serializing approval data to JSON: {e}{Style.RESET_ALL}")
             return None


    def export_paths_to_dict(self, all_paths, output_dir='output_traversals'):
        """Exports ALL simulated paths to a Python dictionary file."""
        if not all_paths: return None

        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, f'dialog_dict_{os.path.basename(self.json_file_path)}.py')
        print(f"{Fore.GREEN}Exporting {len(all_paths)} paths to Python dict in {output_file}...{Style.RESET_ALL}")

        dialog_dict = {}
        for i, path in enumerate(all_paths, 1):
            path_key = f"path_{i}"
            path_lines = []
            for node_id in path:
                if isinstance(node_id, str) and node_id in ["MAX_DEPTH_REACHED", "LOOP_DETECTED", "NODE_NOT_FOUND"]:
                    path_lines.append(f"[{node_id}]")
                    continue
                node_data = self._get_node(node_id)
                formatted_line = self.get_formatted_node_line(node_id, node_data)
                if formatted_line:
                     path_lines.append(formatted_line)
            dialog_dict[path_key] = "\n".join(path_lines)

        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("# Generated dialog paths dictionary\n")
                f.write(f"# Source: {self.json_file_path}\n\n")
                f.write("dialog_paths = {\n")
                for key, value in dialog_dict.items():
                    # Use triple quotes for multiline strings, escape existing triple quotes if necessary
                    escaped_value = value.replace("'''", "'\\''")
                    f.write(f"    '{key}': '''\n{escaped_value}\n''',\n\n")
                f.write("}\n")
            print(f"{Fore.GREEN}Dialog paths dictionary exported successfully.{Style.RESET_ALL}")
            return output_file
        except IOError as e:
            print(f"{Fore.RED}Error exporting paths to dictionary file: {e}{Style.RESET_ALL}")
            return None

# --- Main execution block (for running dialog_simulator.py directly) ---
def main():
    print(f"{Fore.CYAN}Baldur's Gate 3 Dialog Simulator{Style.RESET_ALL}")
    print("Modes: Interactive exploration or full path simulation.")

    # --- Argument Parsing ---
    import argparse
    parser = argparse.ArgumentParser(description="Simulate or explore Baldur's Gate 3 dialog trees from JSON.")
    parser.add_argument("json_file", help="Path to the dialog JSON file to load.")
    parser.add_argument("-m", "--mode", choices=['interactive', 'simulate', 'testnode'], default='interactive',
                        help="Operation mode: interactive exploration, simulate all paths, or test a specific node.")
    parser.add_argument("-n", "--node", help="Node ID to start from in 'testnode' mode.")
    parser.add_argument("-d", "--depth", type=int, default=50, help="Maximum simulation depth for 'simulate' mode.")
    parser.add_argument("--test", action='store_true', help="Enable test mode (ignore flag checks) for simulation.")
    parser.add_argument("--verbose", action='store_true', help="Enable verbose logging during simulation.")
    parser.add_argument("--export-txt", action='store_true', help="Export results to a text file.")
    parser.add_argument("--export-json", action='store_true', help="Export results to a JSON file.")
    parser.add_argument("--export-dict", action='store_true', help="Export simulation paths to a Python dict file.")
    parser.add_argument("--export-approval", action='store_true', help="Export approval history to a JSON file.")
    parser.add_argument("--output-dir", default='output_traversals', help="Directory to save export files.")

    args = parser.parse_args()

    # --- Initialization ---
    if not os.path.isfile(args.json_file):
        print(f"{Fore.RED}Error: JSON file not found at '{args.json_file}'{Style.RESET_ALL}")
        sys.exit(1)

    simulator = DialogSimulator(args.json_file)
    os.makedirs(args.output_dir, exist_ok=True) # Ensure output dir exists

    # --- Mode Execution ---
    if args.mode == 'interactive':
        simulator.interactive_mode()
    elif args.mode == 'simulate':
        all_paths, txt_file, json_file, dict_file = simulator.simulate_all_paths(
            max_depth=args.depth,
            print_paths=True, # Always print paths in direct simulation mode
            test_mode=args.test,
            export_txt=args.export_txt,
            export_json=args.export_json,
            export_dict=args.export_dict,
            verbose=args.verbose
            # Approval export doesn't make sense for simulate all, as state resets
        )
        # Report exports
        if txt_file or json_file or dict_file:
            print(f"{Fore.GREEN}\nExport completed to directory: {args.output_dir}{Style.RESET_ALL}")
            if txt_file: print(f"- Text: {os.path.basename(txt_file)}")
            if json_file: print(f"- JSON: {os.path.basename(json_file)}")
            if dict_file: print(f"- Dict: {os.path.basename(dict_file)}")

    elif args.mode == 'testnode':
        if not args.node:
            print(f"{Fore.RED}Error: Please specify a node ID using -n or --node for 'testnode' mode.{Style.RESET_ALL}")
            sys.exit(1)
        if args.node not in simulator.all_nodes:
             print(f"{Fore.RED}Error: Node ID '{args.node}' not found in {args.json_file}.{Style.RESET_ALL}")
             # Maybe list root nodes as suggestions?
             if simulator.root_nodes:
                  print(f"{Fore.YELLOW}Available root nodes: {list(simulator.root_nodes.keys())}{Style.RESET_ALL}")
             sys.exit(1)

        print(f"\n--- Testing single path from Node: {args.node} ---")
        # Run non-interactively, like simulate_one_path, but use explore_dialog_from_node structure
        # Test mode is implicitly ON when exploring a single node this way (to see the path)
        print(f"{Fore.YELLOW}Note: Flag requirements are ignored in single node test mode.{Style.RESET_ALL}")
        simulator.reset_state() # Reset state before test
        visited_ids, txt_file, json_file, approval_file = simulator.explore_dialog_from_node(
            args.node,
            interactive=False, # Run automatically
            export_txt=args.export_txt,
            export_json=args.export_json,
            export_approval=args.export_approval
        )
        simulator.show_companion_status() # Show status after the run

        # Report exports
        if txt_file or json_file or approval_file:
            print(f"{Fore.GREEN}\nExport completed to directory: {args.output_dir}{Style.RESET_ALL}")
            if txt_file: print(f"- Text: {os.path.basename(txt_file)}")
            if json_file: print(f"- JSON: {os.path.basename(json_file)}")
            if approval_file: print(f"- Approval: {os.path.basename(approval_file)}")

if __name__ == "__main__":
    main()
