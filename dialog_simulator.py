import json
import sys
import os
from colorama import init, Fore, Back, Style
import random

# Initialize colorama for colored terminal output
init()

class DialogSimulator:
    def __init__(self, json_file='CAMP_Ravengard.json'):
        """Initialize the dialog simulator with the specified JSON file"""
        with open(json_file, 'r', encoding='utf-8') as f:
            self.dialog_tree = json.load(f)
        
        self.root_nodes = {}
        self.metadata = self.dialog_tree["metadata"]
        self.all_nodes = self.dialog_tree["dialogue"]  # All nodes including children
        
        # Extract root nodes from the dialog tree
        self.root_nodes = {node_id: node_data for node_id, node_data in self.dialog_tree["dialogue"].items() 
                           if not self._is_child_node(node_id)}
                
        print(f"Loaded dialog tree with {len(self.all_nodes)} nodes, {len(self.root_nodes)} root nodes")
        
        # Companion states to track approval changes
        self.companion_approvals = {
            "Gale": 0,
            "Astarion": 0,
            "Lae'zel": 0,
            "Shadowheart": 0,
            "Wyll": 0,
            "Karlach": 0,
            "Halsin": 0,
            "Minthara": 0,
            "Minsc": 0
        }
        
        # Track history of approval changes with node IDs
        self.companion_approval_history = {
            "Gale": [],
            "Astarion": [],
            "Lae'zel": [],
            "Shadowheart": [],
            "Wyll": [],
            "Karlach": [],
            "Halsin": [],
            "Minthara": [],
            "Minsc": []
        }
        
        # Track visited nodes in a session
        self.visited_nodes = []
        
        # Track flags that have been set during playthrough
        self.default_flags = ["ORI_INCLUSION_GALE", "ORI_INCLUSION_ASTARION", "ORI_INCLUSION_LAEZEL", "ORI_INCLUSION_SHADOWHEART", "ORI_INCLUSION_WYLL", "ORI_INCLUSION_KARLACH", "ORI_INCLUSION_HALSIN", "ORI_INCLUSION_MINTHARA", "ORI_INCLUSION_MINSC", "ORI_INCLUSION_RANDOM"]
        self.active_flags = set(self.default_flags)
    
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
    
    def _process_approvals(self, node_data):
        """Process approval changes from a node"""
        node_id = node_data.get('id', '')
        for approval in node_data.get('approval', []):
            parts = approval.split()
            if len(parts) >= 2:
                char_name = ' '.join(parts[:-1])
                value = parts[-1]
                try:
                    # Handle approval values like "1" or "-1"
                    if char_name in self.companion_approvals:
                        approval_value = int(value)
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
                    pass
    
    def _process_setflags(self, node_data):
        """Process flags that are set by a node"""
        
        # if setflags has a flag with " = False", remove it from the active flags
        for flag in node_data.get('setflags', []):
            if "= False" in flag:
                self.active_flags.remove(flag.split('= False')[0].strip())
            else:
                self.active_flags.add(flag.strip())
    
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
    
    def display_metadata(self):
        """Display the metadata"""
        print(f"\n{Fore.WHITE}===== METADATA ====={Style.RESET_ALL}")
        print(f"Synopsis: {self.metadata.get('synopsis', '')}")
        print(f"How to trigger: {self.metadata.get('how_to_trigger', '')}")
    
    def display_node(self, node_id, node_data):
        """Display a dialog node with formatting"""
        speaker = node_data.get('speaker', 'Unknown')
        text = node_data.get('text', '')
        node_type = node_data.get('node_type', 'normal')
        
        # Show node ID and type for debugging
        print(f"\n{Fore.BLUE}[Node ID: {node_id}, Type: {node_type}]{Style.RESET_ALL}")
        
        # Format based on speaker
        if speaker == 'Player':
            speaker_format = f"{Fore.CYAN}{speaker}{Style.RESET_ALL}"
        else:
            speaker_format = f"{Fore.YELLOW}{speaker}{Style.RESET_ALL}"
        
        # Display the dialog
        if text:
            print(f"\n{speaker_format}: {text}")
        
        # Display context if present (for debug purposes)
        context = node_data.get('context', '')
        if context and context.strip():
            print(f"{Fore.GREEN}Context: {context}{Style.RESET_ALL}")
        
        # Display jump information if present
        if node_type == 'jump' and node_data.get('goto'):
            print(f"{Fore.YELLOW}[Jump node: Will jump to node {node_data.get('goto')}]{Style.RESET_ALL}")
        # Otherwise display goto if present
        elif node_data.get('goto'):
            if not node_data.get('children'):
                print(f"{Fore.MAGENTA}[Goto: {node_data.get('goto')} (will follow - no children present)]{Style.RESET_ALL}")
            else:
                print(f"{Fore.MAGENTA}[Goto: {node_data.get('goto')} (informational only - children present)]{Style.RESET_ALL}")
        # Display link if present
        if node_data.get('link'):
            if not node_data.get('children') and not node_data.get('goto'):
                print(f"{Fore.MAGENTA}[Link: {node_data.get('link')} (will follow - no children or goto present)]{Style.RESET_ALL}")
            else:
                print(f"{Fore.MAGENTA}[Link: {node_data.get('link')} (informational only)]{Style.RESET_ALL}")
        
        # Display if this is an end node
        if node_data.get('is_end', False):
            print(f"{Fore.RED}[End Node]{Style.RESET_ALL}")
        
        # Display rolls if present
        rolls = node_data.get('rolls', '')
        if rolls and rolls.strip():
            print(f"{Fore.MAGENTA}[Requires roll: {rolls}]{Style.RESET_ALL}")
        
        # Display approval changes
        approvals = node_data.get('approval', [])
        if approvals:
            print(f"{Fore.BLUE}[Companion reactions: {', '.join(approvals)}]{Style.RESET_ALL}")
    
    def get_available_options(self, node_data):
        """Get available dialog options from a node's direct children"""
        children = node_data.get('children', {})
        
        # Include all direct child nodes, not just ones with text
        meaningful_options = {}
        for child_id, child_data in children.items():
            if node_data.get('id') == "49":
                import pdb; pdb.set_trace()
            child_node = self._get_node(child_id)
            if not child_node:
                continue
                
            # Include any child node that meets flag requirements, even if it has no text
            # (such as jump nodes which might not have text)
            if self._check_flags(child_node):  # Check if flags requirements are met
                meaningful_options[child_id] = child_node
        
        return meaningful_options
    
    def present_options(self, options):
        """Display dialog options with numbered choices"""
        if not options:
            print(f"\n{Fore.RED}[End of dialog - No options available]{Style.RESET_ALL}")
            return None
        
        print(f"\n{Fore.WHITE}Choose your response:{Style.RESET_ALL}")
        option_list = list(options.items())
        
        for i, (option_id, option_data) in enumerate(option_list, 1):
            speaker = option_data.get('speaker', 'Player')
            text = option_data.get('text', '')
            node_type = option_data.get('node_type', 'normal')
            
            # Add visual indicators for options that might have special effects
            indicators = []
            if option_data.get('approval'):
                indicators.append(f"{Fore.BLUE}[Approval]{Style.RESET_ALL}")
            if option_data.get('setflags'):
                indicators.append(f"{Fore.GREEN}[Sets or Removes Flag]{Style.RESET_ALL}")
            if option_data.get('is_end', False):
                indicators.append(f"{Fore.RED}[Ends Dialog]{Style.RESET_ALL}")
            
            # Add jump node indicator
            if node_type == 'jump' and option_data.get('goto'):
                indicators.append(f"{Fore.YELLOW}[Will jump to node {option_data.get('goto')}]{Style.RESET_ALL}")
            # Otherwise add goto indicator
            elif option_data.get('goto'):
                has_children = bool(option_data.get('children', {}))
                if has_children:
                    indicators.append(f"{Fore.MAGENTA}[Info - Goto: {option_data.get('goto')} (not followed - has children)]{Style.RESET_ALL}")
                else:
                    indicators.append(f"{Fore.MAGENTA}[Info - Goto: {option_data.get('goto')} (will follow if chosen - no children)]{Style.RESET_ALL}")
            # Add link indicator if present
            if option_data.get('link'):
                has_children = bool(option_data.get('children', {}))
                has_goto = bool(option_data.get('goto', ''))
                if not has_children and not has_goto:
                    indicators.append(f"{Fore.MAGENTA}[Link: {option_data.get('link')} (will follow if chosen - no children or goto)]{Style.RESET_ALL}")
                else:
                    indicators.append(f"{Fore.MAGENTA}[Link: {option_data.get('link')} (informational only)]{Style.RESET_ALL}")
            
            indicator_text = " ".join(indicators)
            
            # Only show options that have text
            if text:
                print(f"{i}. [{option_id}] {speaker}: {text} {indicator_text}")
            else:
                # For jump nodes without text, show them as jump choices
                if node_type == 'jump':
                    print(f"{i}. [{option_id}] {Fore.YELLOW}[Jump to node {option_data.get('goto')}]{Style.RESET_ALL} {indicator_text}")
                else:
                    # For other options without text, still show them as choices
                    print(f"{i}. [{option_id}] {Fore.CYAN}[Node without text]{Style.RESET_ALL} {indicator_text}")
        
        # Add option to go back to root nodes
        print(f"0. {Fore.RED}[Return to start]{Style.RESET_ALL}")
        
        choice = None
        while choice is None:
            try:
                choice_input = input("\nEnter choice: ")
                choice_num = int(choice_input)
                
                if choice_num == 0:
                    return "START"
                
                if 1 <= choice_num <= len(option_list):
                    choice = option_list[choice_num - 1][0]  # Get the node ID
                else:
                    print(f"{Fore.RED}Invalid choice. Try again.{Style.RESET_ALL}")
                    choice = None
            except ValueError:
                print(f"{Fore.RED}Please enter a number.{Style.RESET_ALL}")
        
        return choice
    
    def show_root_node_selection(self):
        """Show selection menu for root nodes"""
        print(f"\n{Fore.WHITE}===== ROOT NODES ====={Style.RESET_ALL}")
        root_node_list = list(self.root_nodes.items())
        
        for i, (node_id, node_data) in enumerate(root_node_list, 1):
            speaker = node_data.get('speaker', 'Unknown')
            text_preview = node_data.get('text', '')[:50]
            if text_preview:
                text_preview += "..." if len(node_data.get('text', '')) > 50 else ""
                print(f"{i}. [{node_id}] {speaker}: {text_preview}")
            else:
                print(f"{i}. [{node_id}] {speaker}")
        
        print(f"0. {Fore.RED}[Exit simulator]{Style.RESET_ALL}")
        
        choice = None
        while choice is None:
            try:
                choice_input = input("\nSelect a root node to start dialog: ")
                choice_num = int(choice_input)
                
                if choice_num == 0:
                    return None
                
                if 1 <= choice_num <= len(root_node_list):
                    choice = root_node_list[choice_num - 1][0]  # Get the node ID
                else:
                    print(f"{Fore.RED}Invalid choice. Try again.{Style.RESET_ALL}")
                    choice = None
            except ValueError:
                print(f"{Fore.RED}Please enter a number.{Style.RESET_ALL}")
        
        return choice
    
    def follow_node_path(self, node_id):
        """Follow a path from a node, always following jump nodes and goto for nodes without children"""
        node = self._get_node(node_id)
        
        if not node:
            return node_id, None
        
        # ALWAYS follow jump nodes (regardless of whether they have children)
        
        node_type = node.get('node_type', 'normal')
        if node_type == 'jump' and node.get('goto'):
            goto_node_id = node.get('goto')
            if goto_node_id:
                print(f"{Fore.MAGENTA}[Following jump node link to node {goto_node_id}]{Style.RESET_ALL}")
                return self.follow_node_path(goto_node_id)  # Recursively follow jump/goto chains
        
        # For non-jump nodes, only follow goto if they have no children
        elif not node.get('children') and node.get('goto'):
            goto_node_id = node.get('goto')
            if goto_node_id:
                print(f"{Fore.MAGENTA}[Following goto link to node {goto_node_id} (no children present)]{Style.RESET_ALL}")
                return self.follow_node_path(goto_node_id)  # Recursively follow goto chains
        
        # For nodes with no children and no goto, follow link if present
        elif not node.get('children') and not node.get('goto') and node.get('link'):
            link_node_id = node.get('link')
            if link_node_id:
                print(f"{Fore.MAGENTA}[Following link to node {link_node_id} (no children or goto present)]{Style.RESET_ALL}")
                return self.follow_node_path(link_node_id)  # Recursively follow link chains
            
        # Otherwise, return the node directly
        return node_id, node
    
    def interactive_mode(self):
        """Start the interactive dialog mode"""
        print(f"\n{Fore.WHITE}===== DIALOG SIMULATOR - INTERACTIVE MODE ====={Style.RESET_ALL}")
        print("Explore the dialog tree by selecting options.")
        
        while True:
            # Show root node selection
            root_node_id = self.show_root_node_selection()
            if not root_node_id:
                break
            
            self.explore_dialog_from_node(root_node_id)
            
            # Show companion approval status
            self.show_companion_status()
    
    def explore_dialog_from_node(self, start_node_id, export_txt=False, export_json=False, export_approval=False):
        """Explore dialog starting from a specific node, always following jump nodes and traversing child nodes
        
        Args:
            start_node_id (str): The node ID to start from
            export_txt (bool): Whether to export the traversal to a text file
            export_json (bool): Whether to export the traversal to a JSON file
            export_approval (bool): Whether to export approval history to a JSON file
            
        Returns:
            tuple: (visited_nodes, txt_file_path, json_file_path, approval_file_path)
        """
        current_node_id = start_node_id
        self.visited_nodes = []
        
        # For testing purposes, capture the original active flags to restore later
        original_flags = self.active_flags.copy()
        test_mode = True  # Flag to indicate we're in test mode and should ignore flag requirements
        
        print(f"{Fore.CYAN}Starting dialog from node {current_node_id}{Style.RESET_ALL}")
        
        # Keep track of full details for each visited node
        visited_node_details = []
        
        while current_node_id:
            # First, follow any jump nodes or goto links as needed
            original_node_id = current_node_id
            current_node_id, current_node = self.follow_node_path(current_node_id)
            
            if original_node_id != current_node_id:
                if self._get_node(original_node_id).get('node_type') == 'jump':
                    print(f"{Fore.CYAN}Followed jump node from {original_node_id} to {current_node_id}{Style.RESET_ALL}")
                else:
                    print(f"{Fore.CYAN}Followed path from node {original_node_id} to {current_node_id}{Style.RESET_ALL}")
            
            if not current_node:
                print(f"{Fore.RED}Error: Node {current_node_id} not found{Style.RESET_ALL}")
                break
            
            # Add to visited nodes
            self.visited_nodes.append(current_node_id)
            
            # Also store node data for export
            if current_node:
                # Create a simplified copy of the node data
                node_data = {
                    "id": current_node_id,
                    "speaker": current_node.get('speaker', 'Unknown'),
                    "text": current_node.get('text', ''),
                    "node_type": current_node.get('node_type', 'normal'),
                    "checkflags": current_node.get('checkflags', []),
                    "setflags": current_node.get('setflags', []),
                    "goto": current_node.get('goto', ''),
                    "link": current_node.get('link', ''),
                    "is_end": current_node.get('is_end', False),
                    "approval": current_node.get('approval', [])
                }
                visited_node_details.append(node_data)
            
            # Display the current node
            self.display_node(current_node_id, current_node)
            
            # Process approvals and flags
            self._process_approvals(current_node)
            self._process_setflags(current_node)
            
            # Check if this is an end node explicitly marked as is_end
            if current_node.get('is_end', False):
                print(f"\n{Fore.RED}[End of dialog path - Explicit end node]{Style.RESET_ALL}")
                break
            
            # Get available options based on this node's direct children
            if test_mode:
                # In test mode, temporarily add all required flags for child nodes
                children = current_node.get('children', {})
                for child_id, child_data in children.items():
                    child_node = self._get_node(child_id)
                    if child_node:
                        # Add all required flags for this child
                        for flag in child_node.get('checkflags', []):
                            if "= False" in flag:
                                pass
                            else:
                                self.active_flags.add(flag)
            
            options = self.get_available_options(current_node)
                
            # If there are no options, end the dialog
            if not options:
                print(f"\n{Fore.RED}[End of dialog path - No more options]{Style.RESET_ALL}")
                break
                
            # Present options to the user
            choice = self.present_options(options)
            
            if choice == "START":
                break
            elif choice:
                current_node_id = choice
            else:
                # No valid choice returned
                print(f"\n{Fore.RED}[Dialog ended]{Style.RESET_ALL}")
                break
                
        print(f"\n{Fore.CYAN}[Dialog sequence complete - Visited {len(self.visited_nodes)} nodes]{Style.RESET_ALL}")
        
        # Restore original flags if in test mode
        if test_mode:
            self.active_flags = original_flags
            
        # Export results if requested
        txt_file = None
        json_file = None
        approval_file = None
        
        if export_txt and self.visited_nodes:
            # Export to text file
            output_file = f'node_{start_node_id}_traversal.txt'
            print(f"{Fore.GREEN}Exporting traversal to {output_file}...{Style.RESET_ALL}")
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"Dialog Traversal from Node {start_node_id}\n")
                f.write(f"Total nodes visited: {len(self.visited_nodes)}\n\n")
                f.write(f"Path: {' -> '.join(self.visited_nodes)}\n\n")
                
                # Add details for each node in the path
                f.write(f"Detailed Traversal:\n")
                for i, node_data in enumerate(visited_node_details, 1):
                    node_id = node_data['id']
                    speaker = node_data['speaker']
                    text = node_data['text']
                    node_type = node_data['node_type']
                    
                    # Format basic node info
                    f.write(f"{i}. Node {node_id} [{node_type}]: {speaker} - {text}\n")
                    
                    # Add flags and goto info if present
                    if node_data['checkflags']:
                        f.write(f"   Required flags: {', '.join(node_data['checkflags'])}\n")
                    if node_data['setflags']:
                        f.write(f"   Sets flags: {', '.join(node_data['setflags'])}\n")
                    if node_data['goto']:
                        f.write(f"   Goto: {node_data['goto']}\n")
                    if node_data['link']:
                        f.write(f"   Link: {node_data['link']}\n")
                    if node_data['approval']:
                        f.write(f"   Approval changes: {', '.join(node_data['approval'])}\n")
                    f.write("\n")
            
            txt_file = output_file
            print(f"{Fore.GREEN}Traversal exported to {txt_file}{Style.RESET_ALL}")
        
        if export_json and self.visited_nodes:
            # Export to JSON file
            output_file = f'node_{start_node_id}_traversal.json'
            print(f"{Fore.GREEN}Exporting traversal data to {output_file}...{Style.RESET_ALL}")
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "start_node": start_node_id,
                    "path": self.visited_nodes,
                    "nodes": visited_node_details
                }, f, indent=2, ensure_ascii=False)
            
            json_file = output_file
            print(f"{Fore.GREEN}Traversal data exported to {json_file}{Style.RESET_ALL}")
        
        # Export approval history if requested
        if export_approval and any(len(changes) > 0 for changes in self.companion_approval_history.values()):
            approval_file = f'node_{start_node_id}_approvals.json'
            self.export_approval_history(approval_file)
        
        return self.visited_nodes, txt_file, json_file, approval_file
    
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
        children = self.get_available_options(node)
        if not children:
            return True
            
        return False
    
    def _simulate_paths_from_node(self, node_id, current_path, depth, max_depth, test_mode=False, verbose=False):
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
            if verbose:
                print(f"{Fore.MAGENTA}  [During simulation: Node {node_id} is a jump node, jumping to {goto_id}]{Style.RESET_ALL}")
            return self._simulate_paths_from_node(goto_id, current_path, depth, max_depth, test_mode, verbose)
        
        # For nodes with goto but no children, follow the goto
        if not node.get('children') and node.get('goto'):
            goto_id = node.get('goto')
            if verbose:
                print(f"{Fore.MAGENTA}  [During simulation: Node {node_id} has no children, following goto to {goto_id}]{Style.RESET_ALL}")
            return self._simulate_paths_from_node(goto_id, current_path, depth, max_depth, test_mode, verbose)
            
        # For nodes with link but no children and no goto, follow the link
        if not node.get('children') and not node.get('goto') and node.get('link'):
            link_id = node.get('link')
            if verbose:
                print(f"{Fore.MAGENTA}  [During simulation: Node {node_id} has no children or goto, following link to {link_id}]{Style.RESET_ALL}")
            return self._simulate_paths_from_node(link_id, current_path, depth, max_depth, test_mode, verbose)
        
        # Check if we've reached a leaf node (that has no goto or link)
        # Since we've already checked for goto and link above, if it's a leaf node here, it truly is an end
        if self._is_leaf_node(node_id) and not test_mode:
            if verbose:
                print(f"{Fore.RED}  [During simulation: Node {node_id} is a true leaf node]{Style.RESET_ALL}")
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
        
        # Get all available options based on direct children
        children = self.get_available_options(node)
        
        # If in test mode, restore original flags
        if test_mode and original_flags is not None:
            self.active_flags = original_flags
            
        if not children:
            # This is a leaf node with no options, no goto, and no link (already checked above)
            if verbose:
                print(f"{Fore.RED}  [During simulation: Node {node_id} has no children, goto, or link - ending path]{Style.RESET_ALL}")
            return [current_path]
        
        # Explore all child paths
        all_paths = []
        for child_id in children:
            child_paths = self._simulate_paths_from_node(child_id, current_path, depth + 1, max_depth, test_mode, verbose)
            all_paths.extend(child_paths)
        
        # If no children produced paths (shouldn't happen), return current path
        if not all_paths:
            return [current_path]
            
        return all_paths
    
    def simulate_all_paths(self, max_depth=20, print_paths=True, test_mode=False, export_txt=False, export_json=False, verbose=False):
        """Simulate all possible dialog paths for each root node
        
        Args:
            max_depth (int): Maximum depth to traverse
            print_paths (bool): Whether to print paths to console
            test_mode (bool): Whether to ignore flag requirements
            export_txt (bool): Whether to export paths to a text file
            export_json (bool): Whether to export traversals to a JSON file
            verbose (bool): Whether to print detailed simulation logs
            
        Returns:
            tuple: (all_paths, txt_file_path, json_file_path)
        """
        print(f"\n{Fore.WHITE}===== DIALOG SIMULATOR - SIMULATION MODE ====={Style.RESET_ALL}")
        # show metadata
        self.display_metadata()
        print(f"Simulating all dialog paths (max depth {max_depth} if no leaf node found)...")
        
        if test_mode:
            print(f"{Fore.YELLOW}Running in TEST MODE - Flag requirements will be ignored{Style.RESET_ALL}")
        
        if verbose:
            print(f"{Fore.BLUE}Verbose mode enabled - Detailed simulation logs will be shown{Style.RESET_ALL}")
        
        # Store original flags to restore later if in test mode
        original_flags = self.active_flags.copy() if test_mode else None
        
        all_paths = []
        total_leaf_paths = 0
        
        for root_id, root_data in self.root_nodes.items():
            print(f"\n{Fore.YELLOW}Root Node: {root_id} - {root_data.get('speaker', 'Unknown')}{Style.RESET_ALL}")
            paths = self._simulate_paths_from_node(root_id, [], 0, max_depth, test_mode, verbose)
            
            # Count how many of these paths ended at true leaf nodes
            leaf_paths = [p for p in paths if self._is_leaf_node(p[-1])]
            total_leaf_paths += len(leaf_paths)
            
            if print_paths:
                for i, path in enumerate(paths, 1):
                    is_leaf = self._is_leaf_node(path[-1])
                    leaf_marker = f"{Fore.GREEN}[LEAF NODE]{Style.RESET_ALL}" if is_leaf else ""
                    
                    # Add goto or link marker if the last node has one
                    follow_info = ""
                    last_node_id = path[-1]
                    if last_node_id not in ["MAX_DEPTH_REACHED", "NODE_NOT_FOUND"]:
                        last_node = self._get_node(last_node_id)
                        if last_node:
                            if last_node.get('goto'):
                                follow_info = f"{Fore.MAGENTA} [GOTO: {last_node.get('goto')}]{Style.RESET_ALL}"
                            elif last_node.get('link'):
                                follow_info = f"{Fore.MAGENTA} [LINK: {last_node.get('link')}]{Style.RESET_ALL}"
                    
                    print(f"\nPath {i}: {' -> '.join(path)} {leaf_marker}{follow_info}")
            
            print(f"Total paths from root {root_id}: {len(paths)}")
            print(f"Paths ending at leaf nodes: {len(leaf_paths)}")
            all_paths.extend(paths)
        
        print(f"\nTotal dialog paths: {len(all_paths)}")
        print(f"Total paths ending at leaf nodes: {total_leaf_paths}")
        
        # Restore original flags if in test mode
        if test_mode and original_flags is not None:
            self.active_flags = original_flags
            
        # Export results if requested
        txt_file = None
        json_file = None
        
        if export_txt:
            txt_file = self.export_paths_to_txt(all_paths)
            
        if export_json:
            # Create structured traversal data
            traversals = self.create_traversal_data(all_paths)
            json_file = self.export_traversals_to_json(traversals)
            
        return all_paths, txt_file, json_file

    def show_companion_status(self):
        """Display current companion approval status"""
        print(f"\n{Fore.CYAN}===== COMPANION APPROVAL STATUS ====={Style.RESET_ALL}")
        for companion, value in self.companion_approvals.items():
            if value > 0:
                status = f"{Fore.GREEN}+{value}{Style.RESET_ALL}"
            elif value < 0:
                status = f"{Fore.RED}{value}{Style.RESET_ALL}"
            else:
                status = f"{Fore.WHITE}{value}{Style.RESET_ALL}"
            
            # Show count of changes in history
            change_count = len(self.companion_approval_history[companion])
            if change_count > 0:
                print(f"{companion}: {status} ({change_count} changes)")
            else:
                print(f"{companion}: {status}")
        
        # Option to show detailed history
        if any(len(changes) > 0 for changes in self.companion_approval_history.values()):
            show_details = input(f"\nShow approval change history? (y/n): ").lower() == 'y'
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
                    node_id = change.get('node_id', '')
                    value = change.get('value', 0)
                    speaker = change.get('speaker', '')
                    text = change.get('text', '')
                    
                    # Format the value with color
                    if value > 0:
                        value_str = f"{Fore.GREEN}+{value}{Style.RESET_ALL}"
                    elif value < 0:
                        value_str = f"{Fore.RED}{value}{Style.RESET_ALL}"
                    else:
                        value_str = f"{Fore.WHITE}{value}{Style.RESET_ALL}"
                    
                    # Truncate long dialog text
                    if len(text) > 70:
                        text = text[:67] + "..."
                    
                    # Print the change with context
                    print(f"  {i}. Node {node_id}: {value_str}")
                    print(f"     {speaker}: \"{text}\"")
        
        if not any_changes:
            print(f"{Fore.YELLOW}No approval changes recorded in this session.{Style.RESET_ALL}")

    def reset_state(self):
        """Reset the simulator state"""
        for companion in self.companion_approvals:
            self.companion_approvals[companion] = 0
            self.companion_approval_history[companion] = []
        self.visited_nodes = []
        self.active_flags = set(self.default_flags)
        print(f"\n{Fore.GREEN}Simulator state reset.{Style.RESET_ALL}")

    def export_paths_to_txt(self, all_paths, output_file='dialog_paths.txt'):
        """Export all simulated dialog paths to a text file"""
        print(f"{Fore.GREEN}Exporting {len(all_paths)} dialog paths to {output_file}...{Style.RESET_ALL}")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"Baldur's Gate 3 Dialog Paths\n")
            f.write(f"Total paths: {len(all_paths)}\n\n")
            f.write(f"Synopsis: {self.metadata.get('synopsis', '')}\n")
            f.write(f"How to trigger: {self.metadata.get('how_to_trigger', '')}\n\n")
            
            for i, path in enumerate(all_paths, 1):
                # Mark if the path ends at a leaf node
                last_node_id = path[-1]
                is_leaf = (last_node_id not in ["MAX_DEPTH_REACHED", "NODE_NOT_FOUND"]) and self._is_leaf_node(last_node_id)
                leaf_marker = "[LEAF NODE]" if is_leaf else ""
                
                # Check if the last node has a goto or link that could be followed
                follow_info = ""
                if last_node_id not in ["MAX_DEPTH_REACHED", "NODE_NOT_FOUND"]:
                    last_node = self._get_node(last_node_id)
                    if last_node:
                        if last_node.get('goto'):
                            follow_info = f" [GOTO: {last_node.get('goto')}]"
                        elif last_node.get('link'):
                            follow_info = f" [LINK: {last_node.get('link')}]"
                
                f.write(f"Path {i}: {' -> '.join(path)} {leaf_marker}{follow_info}\n")
                
                # Add details for each node in the path
                f.write(f"  Detailed Path {i}:\n")
                for node_id in path:
                    if node_id in ["MAX_DEPTH_REACHED", "NODE_NOT_FOUND"]:
                        f.write(f"  - {node_id}\n")
                        continue
                        
                    node = self._get_node(node_id)
                    if node:
                        speaker = node.get('speaker', 'Unknown')
                        text = node.get('text', '(No text)')
                        node_type = node.get('node_type', 'normal')
                        
                        # Format basic node info
                        f.write(f"  - Node {node_id} [{node_type}]: {speaker} - {text}\n")
                        
                        # Add flags and goto info if present
                        if node.get('checkflags'):
                            f.write(f"    Required flags: {', '.join(node.get('checkflags', []))}\n")
                        if node.get('setflags'):
                            f.write(f"    Sets flags: {', '.join(node.get('setflags', []))}\n")
                        if node.get('goto'):
                            f.write(f"    Goto: {node.get('goto')}\n")
                        if node.get('link'):
                            f.write(f"    Link: {node.get('link')}\n")
                f.write("\n")
                
        print(f"{Fore.GREEN}Paths exported successfully to {output_file}{Style.RESET_ALL}")
        return output_file
        
    def create_traversal_data(self, all_paths):
        """Create a structured data representation of all traversals
        
        Returns:
            list: A list of traversals, each traversal is a list containing dictionaries with node data
        """
        print(f"{Fore.GREEN}Creating structured traversal data for {len(all_paths)} paths...{Style.RESET_ALL}")
        
        traversals = []
        
        for path in all_paths:
            traversal = []
            for node_id in path:
                if node_id in ["MAX_DEPTH_REACHED", "NODE_NOT_FOUND"]:
                    # Add special marker nodes
                    traversal.append({
                        "id": node_id,
                        "special_marker": True
                    })
                    continue
                    
                node = self._get_node(node_id)
                if not node:
                    # Handle case where node isn't found (e.g., broken link in path)
                    traversal.append({
                        "id": node_id,
                        "error": "NODE_DATA_NOT_FOUND",
                        "special_marker": True # Mark as special for easier filtering downstream
                    })
                    continue

                # Check if it's an alias node
                if node.get("node_type") == "alias":
                    target_id = node.get('link') # Assuming 'link' holds the target ID for aliases
                    target_node = self._get_node(target_id) if target_id else None

                    if target_node:
                        # Start with target node data, copying relevant fields
                        node_data = {
                            "id": node_id, # Use the original alias node ID for the path
                            "speaker": target_node.get('speaker', 'Unknown'),
                            "text": target_node.get('text', ''),
                            "node_type": target_node.get('node_type', 'normal'), # Use target's type initially
                            "checkflags": target_node.get('checkflags', []),
                            "setflags": target_node.get('setflags', []),
                            "goto": target_node.get('goto', ''),
                            "link": target_node.get('link', ''), # Target's link, might be overridden
                            "is_end": target_node.get('is_end', False),
                            "approval": target_node.get('approval', [])
                            # Add any other relevant fields from the node structure if needed
                        }
                        # Add a marker indicating resolution
                        node_data['resolved_from_alias'] = target_id

                        # Override with non-empty values from the alias node itself
                        override_fields = ['speaker', 'text', 'checkflags', 'setflags', 'goto', 'link', 'is_end', 'approval'] # Add 'rolls' etc. if needed
                        for field in override_fields:
                            alias_value = node.get(field)
                            is_non_empty = False
                            if isinstance(alias_value, (str, list)):
                                if alias_value: # Checks for non-empty string or list
                                    is_non_empty = True
                            elif field == 'is_end' and isinstance(alias_value, bool): # Override boolean if explicitly present in alias
                                is_non_empty = True # The presence of the boolean key itself is information
                            # Add checks for other types if necessary (e.g., int 0 might be a valid override)

                            if is_non_empty:
                                node_data[field] = alias_value
                                # If alias overrides the type-defining fields, reflect that? For now, keeps target type.

                        traversal.append(node_data)

                    else:
                        # Target node not found or no target_id, append raw alias info with an error
                        node_data = {
                            "id": node_id,
                            "speaker": node.get('speaker', 'Unknown'),
                            "text": node.get('text', ''),
                            "node_type": node.get('node_type', 'alias'), # Keep type as alias
                            "checkflags": node.get('checkflags', []),
                            "setflags": node.get('setflags', []),
                            "goto": node.get('goto', ''),
                            "link": node.get('link', ''), # This is the target_id
                            "is_end": node.get('is_end', False),
                            "approval": node.get('approval', []),
                            "error": f"ALIAS_TARGET_NOT_FOUND ({target_id})" if target_id else "ALIAS_TARGET_MISSING"
                        }
                        traversal.append(node_data)

                else:
                    # Not an alias node, create data as before
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
                        "approval": node.get('approval', [])
                    }
                    traversal.append(node_data)
            
            traversals.append(traversal)
        
        return traversals
        
    def export_traversals_to_json(self, traversals, output_file='traversals/dialog_traversals.json'):
        """Export structured traversal data to a JSON file"""
        print(f"{Fore.GREEN}Exporting {len(traversals)} traversals to {output_file}...{Style.RESET_ALL}")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(traversals, f, indent=2, ensure_ascii=False)
            
        print(f"{Fore.GREEN}Traversals exported successfully to {output_file}{Style.RESET_ALL}")
        return output_file

    def export_approval_history(self, output_file='approval_history.json'):
        """Export the approval history to a JSON file"""
        print(f"{Fore.GREEN}Exporting approval history to {output_file}...{Style.RESET_ALL}")
        
        # Create a structured version of the approval history
        history_data = {
            "companions": {},
            "summary": {}
        }
        
        for companion, changes in self.companion_approval_history.items():
            if changes:
                history_data["companions"][companion] = changes
                history_data["summary"][companion] = self.companion_approvals[companion]
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(history_data, f, indent=2, ensure_ascii=False)
            
        print(f"{Fore.GREEN}Approval history exported successfully to {output_file}{Style.RESET_ALL}")
        return output_file

def main():
    print(f"{Fore.CYAN}Baldur's Gate 3 Dialog Simulator{Style.RESET_ALL}")
    print("This tool allows you to explore the dialog trees from the game.")
    print(f"{Fore.GREEN}TRAVERSAL MODE: Complete dialog tree traversal{Style.RESET_ALL}")
    print(f"- Displays and traverses all child nodes")
    print(f"- Automatically follows jump nodes to their destinations")
    print(f"- Follows goto links for nodes without children")
    print(f"- Follows link fields for nodes without children and goto")
    print(f"{Fore.YELLOW}Test mode is available to bypass flag requirements{Style.RESET_ALL}")
    print(f"{Fore.BLUE}Export options: Save dialog paths to text and JSON files{Style.RESET_ALL}")
    
    # Check if dialog_tree.json exists
    if not os.path.isfile('output/Companions/ORI_Gale_DeathFlute.json'):
        print(f"{Fore.RED}Error: dialog_tree.json not found.{Style.RESET_ALL}")
        print("Please run the parser script first to generate the dialog tree.")
        return
    
    simulator = DialogSimulator('output/Companions/ORI_Gale_DeathFlute.json')
    
    while True:
        print("\nSelect mode:")
        print("1. Interactive Mode - Explore dialogs with choices")
        print("2. Simulation Mode - Analyze all possible dialog paths")
        print("3. Test Specific Node - Start from a specific node ID")
        print("4. Reset state")
        print("5. View companion approval history")
        print("6. Export approval history to JSON")
        print("0. Exit")
        
        try:
            choice = int(input("\nEnter choice: "))
            
            if choice == 0:
                break
            elif choice == 1:
                simulator.interactive_mode()
            elif choice == 2:
                print("\nSimulation Options:")
                print(f"{Fore.YELLOW}Note: Simulation traverses all dialog paths including child nodes, jump nodes, goto links, and link fields{Style.RESET_ALL}")
                print("1. Quick simulation (max depth 5)")
                print("2. Full simulation (unlimited depth)")
                print("3. Custom depth simulation")
                
                try:
                    sim_choice = int(input("\nSelect simulation type: "))
                    
                    # Ask if test mode should be enabled
                    test_mode = input(f"\n{Fore.YELLOW}Enable test mode to ignore flag requirements? (y/n, default: n):{Style.RESET_ALL} ").lower() == 'y'
                    
                    # Ask about export options
                    export_txt = input(f"\n{Fore.BLUE}Export dialog paths to text file? (y/n, default: n):{Style.RESET_ALL} ").lower() == 'y'
                    export_json = input(f"\n{Fore.BLUE}Export traversal data to JSON file? (y/n, default: n):{Style.RESET_ALL} ").lower() == 'y'
                    
                    # Ask about verbose mode
                    verbose = input(f"\n{Fore.BLUE}Enable verbose logging during simulation? (y/n, default: n):{Style.RESET_ALL} ").lower() == 'y'
                    
                    if sim_choice == 1:
                        # Quick simulation with limited depth
                        print("\nRunning quick simulation (max depth 5)...")
                        _, txt_file, json_file = simulator.simulate_all_paths(
                            max_depth=5, 
                            test_mode=test_mode,
                            export_txt=export_txt,
                            export_json=export_json,
                            verbose=verbose
                        )
                        
                        if txt_file or json_file:
                            print(f"{Fore.GREEN}Export completed:{Style.RESET_ALL}")
                            if txt_file:
                                print(f"- Text file: {txt_file}")
                            if json_file:
                                print(f"- JSON file: {json_file}")
                                
                    elif sim_choice == 2:
                        # Full simulation with high max depth to ensure all paths are found
                        print("\nRunning full simulation (this may take a while)...")
                        _, txt_file, json_file = simulator.simulate_all_paths(
                            max_depth=50, 
                            test_mode=test_mode,
                            export_txt=export_txt,
                            export_json=export_json,
                            verbose=verbose
                        )
                        
                        if txt_file or json_file:
                            print(f"{Fore.GREEN}Export completed:{Style.RESET_ALL}")
                            if txt_file:
                                print(f"- Text file: {txt_file}")
                            if json_file:
                                print(f"- JSON file: {json_file}")
                                
                    elif sim_choice == 3:
                        # Custom depth simulation
                        depth = 10  # Default
                        try:
                            depth_input = input("Maximum dialog depth to simulate (default 10): ")
                            if depth_input.strip():
                                depth = int(depth_input)
                        except ValueError:
                            print(f"{Fore.YELLOW}Using default depth of 10.{Style.RESET_ALL}")
                        
                        print_detailed = input("Print all paths? (y/n, default n): ").lower() == 'y'
                        
                        _, txt_file, json_file = simulator.simulate_all_paths(
                            max_depth=depth, 
                            print_paths=print_detailed, 
                            test_mode=test_mode,
                            export_txt=export_txt,
                            export_json=export_json,
                            verbose=verbose
                        )
                        
                        if txt_file or json_file:
                            print(f"{Fore.GREEN}Export completed:{Style.RESET_ALL}")
                            if txt_file:
                                print(f"- Text file: {txt_file}")
                            if json_file:
                                print(f"- JSON file: {json_file}")
                                
                    else:
                        print(f"{Fore.RED}Invalid choice. Returning to main menu.{Style.RESET_ALL}")
                except ValueError:
                    print(f"{Fore.RED}Please enter a number.{Style.RESET_ALL}")
            elif choice == 3:
                try:
                    node_id = input("\nEnter node ID to test (e.g., 134): ")
                    
                    if node_id and node_id in simulator.all_nodes:
                        # Ask about export options
                        export_txt = input(f"\n{Fore.BLUE}Export traversal to text file? (y/n, default: n):{Style.RESET_ALL} ").lower() == 'y'
                        export_json = input(f"\n{Fore.BLUE}Export traversal data to JSON file? (y/n, default: n):{Style.RESET_ALL} ").lower() == 'y'
                        export_approval = input(f"\n{Fore.BLUE}Export approval history to JSON file? (y/n, default: n):{Style.RESET_ALL} ").lower() == 'y'
                        
                        # Test mode is automatically enabled in explore_dialog_from_node
                        print(f"\n{Fore.GREEN}Testing node {node_id}... (traversing complete dialog tree with test mode ON){Style.RESET_ALL}")
                        print(f"{Fore.YELLOW}Test mode is enabled - flag requirements will be ignored{Style.RESET_ALL}")
                        
                        # Run the exploration with export options
                        _, txt_file, json_file, approval_file = simulator.explore_dialog_from_node(
                            node_id,
                            export_txt=export_txt,
                            export_json=export_json,
                            export_approval=export_approval
                        )
                        
                        # Show status after traversal
                        simulator.show_companion_status()
                        
                        # Report on exports if any
                        if txt_file or json_file or approval_file:
                            print(f"{Fore.GREEN}Export completed:{Style.RESET_ALL}")
                            if txt_file:
                                print(f"- Text file: {txt_file}")
                            if json_file:
                                print(f"- JSON file: {json_file}")
                            if approval_file:
                                print(f"- Approval history: {approval_file}")
                    else:
                        print(f"{Fore.RED}Invalid node ID. Node {node_id} not found in the dialog tree.{Style.RESET_ALL}")
                except ValueError:
                    print(f"{Fore.RED}Please enter a valid node ID.{Style.RESET_ALL}")
            elif choice == 4:
                simulator.reset_state()
            elif choice == 5:
                # Display approval history
                simulator.show_approval_history()
            elif choice == 6:
                # Export approval history to JSON
                if any(len(changes) > 0 for changes in simulator.companion_approval_history.values()):
                    # Customize the output filename
                    filename = input(f"\nEnter filename for export (default: approval_history.json): ")
                    if not filename:
                        filename = "approval_history.json"
                    elif not filename.endswith(".json"):
                        filename += ".json"
                    
                    # Export approval history
                    output_file = simulator.export_approval_history(filename)
                    print(f"{Fore.GREEN}Approval history exported to {output_file}{Style.RESET_ALL}")
                else:
                    print(f"{Fore.YELLOW}No approval changes to export. Try exploring some dialogs first.{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}Invalid choice. Try again.{Style.RESET_ALL}")
        except ValueError:
            print(f"{Fore.RED}Please enter a number.{Style.RESET_ALL}")

if __name__ == "__main__":
    main()