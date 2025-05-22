import json
import sys
import os
from colorama import init, Fore, Back, Style
import random
import traceback # For error handling during rendering

# Initialize colorama for colored terminal output
init()
class DialogSimulator:
    def __init__(
            self, 
            json_file='output/Act2/MoonriseTowers/MOO_Jailbreak_Wulbren.json',
            flags_file='parsed_flags.json',
            tags_file='parsed_tags.json'
    ):
        """Initialize the dialog simulator with the specified JSON file"""
        with open(json_file, 'r', encoding='utf-8') as f:
            self.dialog_tree = json.load(f)
        
        self.root_nodes = {}
        self.metadata = self.dialog_tree["metadata"]
        self.all_nodes = self.dialog_tree["dialogue"]  # All nodes including children
        # Load the flags file if it exists
        self.entire_flags = {}
        if os.path.exists(flags_file):
            try:
                with open(flags_file, 'r', encoding='utf-8') as f:
                    self.entire_flags = json.load(f)
                self.entire_flags = {sample['name']: sample for sample in self.entire_flags}
                print(f"Loaded {len(self.entire_flags)} flags from {flags_file}")
            except Exception as e:
                print(f"Error loading flags file {flags_file}: {e}")
        # Load the tags file if it exists
        self.entire_tags = {}
        if os.path.exists(tags_file):
            try:
                with open(tags_file, 'r', encoding='utf-8') as f:
                    self.entire_tags = json.load(f)
                self.entire_tags = {sample['name']: sample for sample in self.entire_tags}
                print(f"Loaded {len(self.entire_tags)} tags from {tags_file}")
            except Exception as e:
                print(f"Error loading tags file {tags_file}: {e}")
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
    def set_initial_flags(self, flags):
        """Set the initial active flags for the simulator."""
        # Ensure flags is a set
        if isinstance(flags, set):
            self.active_flags = flags.copy() # Work with a copy
        elif isinstance(flags, (list, tuple)):
            self.active_flags = set(flags)
        else:
            print(f"{Fore.YELLOW}Warning: Invalid type for initial flags. Expected set, list, or tuple. Using defaults.{Style.RESET_ALL}")
            self.active_flags = set(self.default_flags) # Fallback
        # print(f"{Fore.BLUE}Initial flags set: {len(self.active_flags)}{Style.RESET_ALL}") # Optional debug
    
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
                            "speaker": node_data.get('speaker', ''),
                            "context": node_data.get('context', '')
                        })
                except (ValueError, KeyError):
                    pass
    
    def _process_setflags(self, node_data):
        """Process flags that are set by a node"""
        # if setflags has a flag with " = False", remove it from the active flags
        for flag in node_data.get('setflags', []):
            
            flag_ = flag.replace("= False", "").replace("= True", "").strip()
            # TODO: somehow the flagnames in the lsj files are not always the same as the flagnames in the json files
            #if flag_ not in self.entire_flags and flag_ not in self.entire_tags:
            #    continue
            if flag_ in self.entire_flags:
                flag_type = self.entire_flags[flag_]['usage']
                if flag_type.lower() not in ['global', 'dialog', 'user']:
                    continue
            if flag_ in self.entire_tags:
                if self.entire_tags[flag_]['categories'].lower() not in ['story', 'dialog', 'dialoghidden']:
                    continue
            if "= False" in flag:
                try:
                    self.active_flags.remove(flag_.strip())
                except KeyError:
                    pass
            else:
                self.active_flags.add(flag_.strip())
    def _check_flags(self, node_data):
        """Check if required flags are met for a node"""
        # A simple implementation - in a real game this would be more complex
        # if checkflags is empty, return True
        
        if not node_data.get('checkflags', []):
            return True
        # if checkflags has a flag with " = False", check whether it is not set.
        for flag in node_data.get('checkflags', []):
            flag_ = flag.replace("= False", "").replace("= True", "").strip()
            
            # TODO: somehow the flagnames in the lsj files are not always the same as the flagnames in the json files
            #if flag_ not in self.entire_flags and flag_ not in self.entire_tags:
            #    continue
            if flag_ in self.entire_flags:
                flag_type = self.entire_flags[flag_]['usage']
                if flag_type.lower() not in ['global', 'dialog', 'user']:
                    continue
            if flag_ in self.entire_tags:
                tag_categories = self.entire_tags[flag_]['categories']
                tag_category_flag = False
                for tag_category in tag_categories:
                    if tag_category.lower() in ['story', 'dialog', 'dialoghidden']:
                        tag_category_flag = True
                        break
                if not tag_category_flag:
                    continue
            if "= False" in flag:
                if flag_.strip() in self.active_flags:
                    return False
            else:
                if flag_.strip() not in self.active_flags:
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
    
    def get_available_options(self, node_data, test_mode_active=False):
        """Get available dialog options from a node's direct children"""
        children = node_data.get('children', {})
        
        meaningful_options = {}
        for child_id, child_data in children.items():
            child_node = self._get_node(child_id)
            if not child_node:
                continue
                
            # If in test mode, include all children. Otherwise, check flags.
            if test_mode_active or self._check_flags(child_node):
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
                if current_node['text'] == '':
                    current_node['text'] = current_node['context']
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
                    "approval": current_node.get('approval', []),
                    "context": current_node.get('context', '')
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
            
            options = self.get_available_options(current_node, test_mode)
                
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
                
                # Add details for each node in the path using our custom format
                f.write(f"Detailed Traversal:\n")
                for node_data in visited_node_details:
                    # Skip nodes without text
                    if not node_data['text']:
                        continue
                        
                    # Format the line according to requirements
                    line = ""
                    
                    # Handle speaker/text part based on node type
                    if node_data['node_type'] == 'tagcinematic':
                        line = f"[description] {node_data['text']}"
                    else:
                        line = f"{node_data['speaker']}: {node_data['text']}"
                    
                    # Add context if present (context isn't captured in node_data by default, so would need to be added)
                    context = node_data['context']
                    if context:
                        line += f" || [context] {context}"
                    
                    # Add approval changes if present
                    if node_data['approval']:
                        line += f" || [approval] {', '.join(node_data['approval'])}"
                    if ": true" in line.lower() or ": false" in line.lower():
                        continue
                    # Write the formatted line
                    f.write(f"{line}\n")
            
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
        """Recursively simulate all paths from a node, always following jump nodes and goto for nodes without children.
        Modifies self.active_flags based on setflags encountered and respects test_mode for flag checking via get_available_options.
        """
        if depth >= max_depth:
            return [current_path + [node_id] + ["MAX_DEPTH_REACHED"]]
        
        node = self._get_node(node_id)
        if not node:
            return [current_path + [node_id] + ["NODE_NOT_FOUND"]]
        
        current_path = current_path + [node_id]
        
        # Process setflags for the current node, modifying self.active_flags
        self._process_setflags(node)
        
        node_type = node.get('node_type', 'normal')
        if node_type == 'jump' and node.get('goto'):
            goto_id = node.get('goto')
            if verbose:
                print(f"{Fore.MAGENTA}  [During simulation: Node {node_id} is a jump node, jumping to {goto_id}]{Style.RESET_ALL}")
            return self._simulate_paths_from_node(goto_id, current_path, depth, max_depth, test_mode, verbose)
        
        if not node.get('children') and node.get('goto'):
            goto_id = node.get('goto')
            if verbose:
                print(f"{Fore.MAGENTA}  [During simulation: Node {node_id} has no children, following goto to {goto_id}]{Style.RESET_ALL}")
            return self._simulate_paths_from_node(goto_id, current_path, depth, max_depth, test_mode, verbose)
            
        if not node.get('children') and not node.get('goto') and node.get('link'):
            link_id = node.get('link')
            if verbose:
                print(f"{Fore.MAGENTA}  [During simulation: Node {node_id} has no children or goto, following link to {link_id}]{Style.RESET_ALL}")
            return self._simulate_paths_from_node(link_id, current_path, depth, max_depth, test_mode, verbose)
        
        # Check if we've reached a leaf node (that has no goto or link)
        # self._is_leaf_node internally calls get_available_options, which now needs test_mode.
        # However, the primary check for leaf status in the simulation loop is having no children from get_available_options call below.
        # For the explicit check here, we should also pass test_mode if we want it to align.
        # Let's refine _is_leaf_node or rely on the children check primarily.
        # For now, let's assume the children check below is the main gatekeeper for ending paths.

        # Get all available options based on direct children, respecting test_mode
        children = self.get_available_options(node, test_mode_active=test_mode)
            
        if not children:
            if verbose:
                print(f"{Fore.RED}  [During simulation: Node {node_id} has no valid children options (considering flags/test_mode) - ending path]{Style.RESET_ALL}")
            return [current_path]
        
        all_child_paths = []
        for child_id in children:
            # Recursive call. self.active_flags has been modified by the current 'node' (and previous nodes in DFS).
            # These modifications will persist for the child's simulation and subsequent siblings.
            child_paths_segment = self._simulate_paths_from_node(child_id, current_path, depth + 1, max_depth, test_mode, verbose)
            all_child_paths.extend(child_paths_segment)
        
        return all_child_paths if all_child_paths else [current_path]
    
    def simulate_all_paths(self, max_depth=20, print_paths=True, test_mode=False, export_txt=False, export_json=False, export_dict=False, verbose=False):
        """Simulate all possible dialog paths for each root node, processing root nodes in a random order.
        self.active_flags are initialized and then modified by the traversal process.
        Args:
            max_depth (int): Maximum depth to traverse
            print_paths (bool): Whether to print paths to console
            test_mode (bool): Whether to ignore flag requirements
            export_txt (bool): Whether to export paths to a text file
            export_json (bool): Whether to export traversals to a JSON file
            export_dict (bool): Whether to export paths to a Python dictionary file
            verbose (bool): Whether to print detailed simulation logs
            
        Returns:
            tuple: (all_paths, txt_file_path, json_file_path, dict_file_path)
        """
        print(f"\n{Fore.WHITE}===== DIALOG SIMULATOR - SIMULATION MODE ====={Style.RESET_ALL}")
        # show metadata
        self.display_metadata()
        print(f"Simulating all dialog paths (max depth {max_depth} if no leaf node found)...")
        
        if test_mode:
            print(f"{Fore.YELLOW}Running in TEST MODE - Flag requirements will be ignored{Style.RESET_ALL}")
        
        if verbose:
            print(f"{Fore.BLUE}Verbose mode enabled - Detailed simulation logs will be shown{Style.RESET_ALL}")
        
        # Initialize active_flags for this simulation run. These will be modified by _simulate_paths_from_node.
        self.active_flags = set(self.default_flags) # Or some other initial state if needed
        
        all_paths = []
        total_leaf_paths = 0
        
        # Get root node items and shuffle them
        root_node_items = list(self.root_nodes.items())
        random.shuffle(root_node_items) # Ensure random is imported

        for root_id, root_data in root_node_items: # Iterate through the shuffled list
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
            import pdb; pdb.set_trace()
        
        print(f"\nTotal dialog paths: {len(all_paths)}")
        print(f"Total paths ending at leaf nodes: {total_leaf_paths}")
        
        # Export results if requested
        txt_file = None
        json_file = None
        dict_file = None
        
        if export_txt:
            txt_file = self.export_paths_to_txt(all_paths)
            
        if export_json:
            # Create structured traversal data
            traversals = self.create_traversal_data(all_paths)
            json_file = self.export_traversals_to_json(traversals)
            
        if export_dict:
            dict_file = self.export_paths_to_dict(all_paths)
        return all_paths, txt_file, json_file, dict_file

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
        """Export all simulated dialog paths to a text file, with the custom format:
        "{speaker}: {text} || [context] {context} ||[approval] {list of approval changes, if exists}"
        For tagcinematic nodes: "[description] {text}".
        Each utterance on a separate line."""
        print(f"{Fore.GREEN}Exporting {len(all_paths)} dialog paths to {output_file}...{Style.RESET_ALL}")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"Baldur's Gate 3 Dialog Paths\n")
            f.write(f"Total paths: {len(all_paths)}\n\n")
            f.write(f"Synopsis: {self.metadata.get('synopsis', '')}\n")
            f.write(f"How to trigger: {self.metadata.get('how_to_trigger', '')}\n\n")
            
            for i, path in enumerate(all_paths, 1):
                #f.write(f"Path {i}:\n")
                
                # Add custom formatted output for each node in the path
                for node_id in path:
                    if node_id in ["MAX_DEPTH_REACHED", "NODE_NOT_FOUND"]:
                        f.write(f"[{node_id}]\n")
                        continue
                        
                    node = self._get_node(node_id)
                    if not node:
                        continue
                        
                    speaker = node.get('speaker', 'Unknown')
                    text = node.get('text', '')
                    context = node.get('context', '')
                    approvals = node.get('approval', [])
                    
                    # Skip nodes without text
                    if not text:
                        continue
                    
                    # Format the line according to requirements
                    line = ""
                    
                    # Handle speaker/text part based on node type
                    if node.get('node_type') == 'tagcinematic':
                        line = f"[description] {text}"
                    else:
                        line = f"{speaker}: {text}"
                    
                    # Add context if present
                    if context:
                        line += f" || [context] {context}"
                    
                    # Add approval changes if present
                    if approvals:
                        line += f" || [approval] {', '.join(approvals)}"
                    
                    # Write the formatted line
                    f.write(f"{line}\n")
                
                f.write("\n")  # Add extra line between paths
                
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
                        if target_node['text'] == '':
                            target_node['text'] = target_node['context']
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
                            "approval": target_node.get('approval', []),
                            "context": target_node.get('context', '')
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
                        if node['text'] == '':
                            node['text'] = node['context']
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
                            "context": node.get('context', ''),
                            "error": f"ALIAS_TARGET_NOT_FOUND ({target_id})" if target_id else "ALIAS_TARGET_MISSING"
                        }
                        traversal.append(node_data)

                else:
                    # Not an alias node, create data as before
                    if node['text'] == '':
                        node['text'] = node['context']
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
                        "context": node.get('context', '')
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

    def export_paths_to_dict(self, all_paths, output_file='dialog_dict.py'):
        """Export all simulated dialog paths to a Python dictionary
        
        This creates a Python file containing a dictionary where:
        - Keys are "path_1", "path_2", etc.
        - Values are strings with the full dialog text for each path
        
        Args:
            all_paths (list): List of node paths to export
            output_file (str): Output Python file path
            
        Returns:
            str: Path to the output file
        """
        print(f"{Fore.GREEN}Exporting {len(all_paths)} dialog paths to Python dictionary in {output_file}...{Style.RESET_ALL}")
        
        # Create the dictionary structure
        dialog_dict = {}
        
        for i, path in enumerate(all_paths, 1):
            dialog_text = []
            # Process each node in the path with custom formatting
            for node_id in path:
                if node_id in ["MAX_DEPTH_REACHED", "NODE_NOT_FOUND"]:
                    dialog_text.append(f"[{node_id}]")
                    continue
                    
                node = self._get_node(node_id)
                if not node:
                    continue
                    
                speaker = node.get('speaker', 'Unknown')
                text = node.get('text', '')
                context = node.get('context', '')
                approvals = node.get('approval', [])
                
                # Skip nodes without text
                if not text:
                    continue
                
                # Format the line according to requirements
                line = ""
                
                # Handle speaker/text part based on node type
                if node.get('node_type') == 'tagcinematic':
                    line = f"[cinematic description] {text}"
                else:
                    line = f"{speaker}: {text}"
                
                # Add context if present
                if context:
                    line += f" || [context] {context}"
                
                # Add approval changes if present
                if approvals:
                    line += f" || [approval] {', '.join(approvals)}"
                
                dialog_text.append(line)
            
            # Join all lines with newlines to create a single string for this path
            dialog_dict["appended_paths"] = "\n".join(dialog_text)
        
        # Write the dictionary to a Python file
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("# Generated dialog paths dictionary\n\n")
            f.write("dialog_paths = {\n")
            
            for key, value in dialog_dict.items():
                # Format the multiline string properly for Python
                formatted_value = value.replace("'", "\\'")  # Escape single quotes
                f.write(f"    '{key}': '''\n{formatted_value}\n''',\n\n")
            
            f.write("}\n")
        
        print(f"{Fore.GREEN}Dialog paths dictionary exported successfully to {output_file}{Style.RESET_ALL}")
        return output_file

    def execute_path(self, path, initial_flags=None):
        """
        Executes a specific dialog path, applying setflags and approvals.
        Does NOT check flags during traversal, assumes path validity.
        Resets and uses provided initial flags.

        Args:
            path (list): List of node IDs representing the path to execute.
            initial_flags (set, optional): Flags to start with. If None, uses defaults.

        Returns:
            tuple: (list_of_node_data, final_flags_set)
                   - list_of_node_data: Detailed data for each node visited.
                   - final_flags_set: The set of active flags after traversing the path.
        """
        if not path:
            return [], initial_flags if initial_flags else set(self.default_flags)

        # Reset state but keep initial flags
        if initial_flags is not None:
             self.set_initial_flags(initial_flags)
        else:
             self.active_flags = set(self.default_flags) # Ensure defaults if none provided

        # print(f"{Fore.CYAN}Executing path: {path} with initial flags: {self.active_flags}{Style.RESET_ALL}")

        traversed_nodes_data = []
        current_active_flags = self.active_flags.copy() # Work with a copy locally

        for node_id in path:
            if node_id in ["MAX_DEPTH_REACHED", "NODE_NOT_FOUND"]:
                traversed_nodes_data.append({
                    "id": node_id,
                    "special_marker": True
                })
                continue

            # Get node data directly, do not follow jumps/links here as path is pre-determined
            # However, the path provided SHOULD already have jumps/links resolved if needed.
            node_data = self._get_node(node_id)

            if not node_data:
                import pdb; pdb.set_trace()
                print(f"{Fore.RED}Node {node_id} not found during path execution. Skipping.{Style.RESET_ALL}")
                traversed_nodes_data.append({
                    "id": node_id,
                    "error": "NODE_DATA_NOT_FOUND",
                    "special_marker": True
                })
                continue

            # Process approvals (affects internal simulator state)
            self._process_approvals(node_data) # Uses self.companion_approvals etc.

            # Process setflags (affects the flags being tracked for return)
            # Logic copied and adapted from self._process_setflags
            for flag in node_data.get('setflags', []):
                if "= False" in flag:
                    flag_to_remove = flag.split('= False')[0].strip()
                    if flag_to_remove in current_active_flags:
                        current_active_flags.remove(flag_to_remove)
                else:
                    current_active_flags.add(flag.strip())

            # Store node data for the result
            # (Using the same structure as explore_dialog_from_node for consistency)
            if node_data['text'] == '':
                node_data['text'] = node_data['context']
            traversed_nodes_data.append({
                "id": node_id,
                "speaker": node_data.get('speaker', 'Unknown'),
                "text": node_data.get('text', ''),
                "node_type": node_data.get('node_type', 'normal'),
                "checkflags": node_data.get('checkflags', []), # Include for info
                "setflags": node_data.get('setflags', []),   # Include for info
                "goto": node_data.get('goto', ''),
                "link": node_data.get('link', ''),
                "is_end": node_data.get('is_end', False),
                "approval": node_data.get('approval', []),
                "context": node_data.get('context', '')
            })

            # Update the main simulator flags (might be useful if called interactively, but primary return is separate)
            self.active_flags = current_active_flags.copy()

        # print(f"{Fore.GREEN}Path execution finished. Final flags: {current_active_flags}{Style.RESET_ALL}")
        return traversed_nodes_data, current_active_flags

    def _add_nodes_to_graph(self, dot, node_id, visited, current_depth, max_depth):
        """Recursively add nodes and edges to the Graphviz graph."""
        if node_id in visited or current_depth > max_depth:
            return

        node = self._get_node(node_id)
        if not node:
            # Add a placeholder for missing nodes
            if node_id not in visited:
                 dot.node(node_id, label=f"{node_id}\n(Not Found)", shape='box', style='filled', fillcolor='red')
                 visited.add(node_id)
            return

        visited.add(node_id)

        # Node styling
        speaker = node.get('speaker', 'Unknown')
        text_preview = node.get('text', node.get('context', ''))[:40] # Limit text length
        if len(node.get('text', node.get('context', ''))) > 40:
            text_preview += "..."
        label = f"{node_id}\n{speaker}\n'{text_preview}'" # Use \n for newline in graphviz label
        shape = 'box'
        style = 'filled'
        fillcolor = 'lightgrey'
        node_color = 'black' # Border color

        if speaker == 'Player':
            fillcolor = 'lightblue'
        elif node.get('node_type') == 'jump':
            shape = 'cds'
            fillcolor = 'yellow'
        elif node.get('node_type') == 'tagcinematic':
            shape = 'note'
            fillcolor = 'lightgoldenrod'
        elif node.get('node_type') == 'alias':
            shape = 'hexagon'
            fillcolor = 'lightcoral'


        if node.get('is_end', False):
            node_color = 'red' # Red border for end nodes
            style += ',bold'

        dot.node(node_id, label=label, shape=shape, style=style, fillcolor=fillcolor, color=node_color)

        # Process children
        children = node.get('children', {})
        for child_id in children:
            # Add edge first
            dot.edge(node_id, child_id, label='child', color='black')
            # Recurse only if child node exists (avoid infinite loop on bad data)
            if self._get_node(child_id):
                 self._add_nodes_to_graph(dot, child_id, visited, current_depth + 1, max_depth)
            elif child_id not in visited: # Add error node if child doesn't exist and hasn't been added
                 dot.node(child_id, label=f"{child_id}\n(Child Not Found)", shape='box', style='filled', fillcolor='red')
                 visited.add(child_id)


        # Process goto
        goto_id = node.get('goto')
        if goto_id:
            # Add edge first
            dot.edge(node_id, goto_id, label='goto', style='dashed', color='blue')
            # Recurse only if goto node exists
            if self._get_node(goto_id):
                self._add_nodes_to_graph(dot, goto_id, visited, current_depth + 1, max_depth)
            elif goto_id not in visited: # Add error node if goto doesn't exist
                dot.node(goto_id, label=f"{goto_id}\n(Goto Target Not Found)", shape='box', style='filled', fillcolor='red')
                visited.add(goto_id)


        # Process link
        link_id = node.get('link')
        if link_id:
            # Add edge first
            dot.edge(node_id, link_id, label='link', style='dotted', color='green')
            # Recurse only if link node exists
            if self._get_node(link_id):
                self._add_nodes_to_graph(dot, link_id, visited, current_depth + 1, max_depth)
            elif link_id not in visited: # Add error node if link doesn't exist
                dot.node(link_id, label=f"{link_id}\n(Link Target Not Found)", shape='box', style='filled', fillcolor='red')
                visited.add(link_id)

    


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
    if not os.path.isfile('output/Act1/Crash/CRA_ShadowheartRecruitment_AD.json'): # 'output/Act2/MoonriseTowers/MOO_Jailbreak_Wulbren.json'
        print(f"{Fore.RED}Error: dialog_tree.json not found.{Style.RESET_ALL}")
        print("Please run the parser script first to generate the dialog tree.")
        return
    
    simulator = DialogSimulator('output/Act1/Crash/CRA_ShadowheartRecruitment_AD.json') # 'output/Act2/MoonriseTowers/MOO_Jailbreak_Wulbren.json'
    
    while True:
        print("\nSelect mode:")
        print("1. Interactive Mode - Explore dialogs with choices")
        print("2. Simulation Mode - Analyze all possible dialog paths")
        print("3. Test Specific Node - Start from a specific node ID")
        print("4. Reset state")
        print("5. View companion approval history")
        print("6. Export approval history to JSON")
        print("7. Export paths to Python dictionary")
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
                    export_dict = input(f"\n{Fore.BLUE}Export paths to Python dictionary? (y/n, default: n):{Style.RESET_ALL} ").lower() == 'y'
                    
                    # Ask about verbose mode
                    verbose = input(f"\n{Fore.BLUE}Enable verbose logging during simulation? (y/n, default: n):{Style.RESET_ALL} ").lower() == 'y'
                    
                    if sim_choice == 1:
                        # Quick simulation with limited depth
                        print("\nRunning quick simulation (max depth 5)...")
                        all_paths, txt_file, json_file, dict_file = simulator.simulate_all_paths(
                            max_depth=5, 
                            test_mode=test_mode,
                            export_txt=export_txt,
                            export_json=export_json,
                            export_dict=export_dict,
                            verbose=verbose
                        )
                        
                        if txt_file or json_file or dict_file:
                            print(f"{Fore.GREEN}Export completed:{Style.RESET_ALL}")
                            if txt_file:
                                print(f"- Text file: {txt_file}")
                            if json_file:
                                print(f"- JSON file: {json_file}")
                            if dict_file:
                                print(f"- Dictionary file: {dict_file}")
                                
                    elif sim_choice == 2:
                        # Full simulation with high max depth to ensure all paths are found
                        print("\nRunning full simulation (this may take a while)...")
                        all_paths, txt_file, json_file, dict_file = simulator.simulate_all_paths(
                            max_depth=50, 
                            test_mode=test_mode,
                            export_txt=export_txt,
                            export_json=export_json,
                            export_dict=export_dict,
                            verbose=verbose
                        )
                        
                        if txt_file or json_file or dict_file:
                            print(f"{Fore.GREEN}Export completed:{Style.RESET_ALL}")
                            if txt_file:
                                print(f"- Text file: {txt_file}")
                            if json_file:
                                print(f"- JSON file: {json_file}")
                            if dict_file:
                                print(f"- Dictionary file: {dict_file}")
                                
                    elif sim_choice == 3:
                        # Custom depth simulation
                        depth = 10  # Default
                        try:
                            depth_input = input("Maximum dialog depth to simulate (default 10): ")
                            if depth_input.strip():
                                depth = int(depth_input)
                        except ValueError:
                            print(f"{Fore.YELLOW}Using default depth of 10.{Style.RESET_ALL}")
                        
                        all_paths, txt_file, json_file, dict_file = simulator.simulate_all_paths(
                            max_depth=depth, 
                            print_paths=False, 
                            test_mode=test_mode,
                            export_txt=export_txt,
                            export_json=export_json,
                            export_dict=export_dict,
                            verbose=verbose
                        )
                        if txt_file or json_file or dict_file:
                            print(f"{Fore.GREEN}Export completed:{Style.RESET_ALL}")
                            if txt_file:
                                print(f"- Text file: {txt_file}")
                            if json_file:
                                print(f"- JSON file: {json_file}")
                            if dict_file:
                                print(f"- Dictionary file: {dict_file}")
                                
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
            elif choice == 7:
                # Export paths to Python dictionary
                print("\nSimulation Options:")
                print(f"{Fore.YELLOW}Note: We need to simulate all paths before exporting to dictionary{Style.RESET_ALL}")
                print("1. Quick simulation (max depth 5)")
                print("2. Full simulation (unlimited depth)")
                print("3. Custom depth simulation")
                
                try:
                    sim_choice = int(input("\nSelect simulation type: "))
                    
                    # Ask if test mode should be enabled
                    test_mode = input(f"\n{Fore.YELLOW}Enable test mode to ignore flag requirements? (y/n, default: n):{Style.RESET_ALL} ").lower() == 'y'
                    
                    # Customize the output filename
                    filename = input(f"\nEnter filename for export (default: dialog_dict.py): ")
                    if not filename:
                        filename = "dialog_dict.py"
                    elif not filename.endswith(".py"):
                        filename += ".py"
                    if not filename.startswith("output_json/"):
                        filename = "output_json/" + filename
                    if sim_choice == 1:
                        # Quick simulation with limited depth
                        print("\nRunning quick simulation (max depth 5)...")
                        all_paths, _, _, _ = simulator.simulate_all_paths(
                            max_depth=5, 
                            test_mode=test_mode,
                            export_txt=False,
                            export_json=False,
                            export_dict=False,
                            verbose=False
                        )
                        
                    elif sim_choice == 2:
                        # Full simulation with high max depth to ensure all paths are found
                        print("\nRunning full simulation (this may take a while)...")
                        all_paths, _, _, _ = simulator.simulate_all_paths(
                            max_depth=50, 
                            test_mode=test_mode,
                            export_txt=False,
                            export_json=False,
                            export_dict=False,
                            verbose=False
                        )
                        
                    elif sim_choice == 3:
                        # Custom depth simulation
                        depth = 10  # Default
                        try:
                            depth_input = input("Maximum dialog depth to simulate (default 10): ")
                            if depth_input.strip():
                                depth = int(depth_input)
                        except ValueError:
                            print(f"{Fore.YELLOW}Using default depth of 10.{Style.RESET_ALL}")
                        
                        all_paths, _, _, _ = simulator.simulate_all_paths(
                            max_depth=depth, 
                            print_paths=False, 
                            test_mode=test_mode,
                            export_txt=False,
                            export_json=False,
                            export_dict=False,
                            verbose=False
                        )
                    else:
                        print(f"{Fore.RED}Invalid choice. Returning to main menu.{Style.RESET_ALL}")
                        continue
                    
                    # Export paths to Python dictionary
                    if all_paths:
                        output_file = simulator.export_paths_to_dict(all_paths, filename)
                        print(f"{Fore.GREEN}Paths exported to {output_file}{Style.RESET_ALL}")
                    else:
                        print(f"{Fore.YELLOW}No paths were generated. Cannot export.{Style.RESET_ALL}")
                        
                except ValueError:
                    print(f"{Fore.RED}Please enter a number.{Style.RESET_ALL}")
        
        except ValueError:
            print(f"{Fore.RED}Please enter a number.{Style.RESET_ALL}")

if __name__ == "__main__":
    main()