from bs4 import BeautifulSoup
import re, os
import json

def parse_dialog_tree(html_file):
    """Parse the dialogue tree from an HTML file"""
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find all nodes with a node ID
    all_nodes = {}
    all_node_elements = {}
    
    metadata = {}
    # Find Synopsis
    synopsis_header = soup.find('h4', text='Synopsis:')
    if synopsis_header and synopsis_header.find_next_sibling('span', class_='synopsis'):
        metadata['synopsis'] = synopsis_header.find_next_sibling('span', class_='synopsis').text.strip()
    
    # Find How to trigger
    how_to_trigger_header = soup.find('h4', text='How to trigger:')
    if how_to_trigger_header and how_to_trigger_header.find_next_sibling('span', class_='howtotrigger'):
        metadata['how_to_trigger'] = how_to_trigger_header.find_next_sibling('span', class_='howtotrigger').text.strip()
    
    # First pass: collect all nodes with IDs
    for li in soup.select('.dialogList li'):
        node_id_span = li.select_one('.nodeid')
        if node_id_span:
            node_id = node_id_span.text.strip().replace('.', '')
            node_data = extract_node_data(li)
            
            if node_data:
                all_nodes[node_id] = node_data
                all_node_elements[node_id] = li
    
    # Second pass: build parent-child relationships
    root_nodes = {}
    
    for node_id, node_data in all_nodes.items():
        # Find this node's li element
        li = all_node_elements[node_id]
        
        # Find parent node
        parent_li = None
        parent_ul = li.find_parent('ul')
        if parent_ul:
            parent_li = parent_ul.find_parent('li')
        
        if parent_li:
            # This is a child node
            parent_id_span = parent_li.select_one('.nodeid')
            if parent_id_span:
                parent_id = parent_id_span.text.strip().replace('.', '')
                if parent_id in all_nodes:
                    # Add this node as a child of its parent
                    all_nodes[parent_id]['children'][node_id] = node_data
        else:
            # This is a root node
            root_nodes[node_id] = node_data
    
    return root_nodes, all_nodes, metadata

def extract_ruletags(element):
    """Extract rule tag information from a node"""
    ruletags = []
    
    # First find the main div of the node
    main_div = element.find('div', recursive=False)
    if not main_div:
        return ruletags
    
    # Look for ruletag spans in the main div
    ruletag_spans = main_div.find_all('span', class_='ruletag', recursive=False)
    
    for span in ruletag_spans:
        # Rule tags often have a title attribute with additional information
        rule_text = span.text.strip()
        
        # If the span is empty, try to get the rule from the title attribute
        if not rule_text and 'title' in span.attrs:
            title = span['title'].strip()
            # Title might have format '|REALLY_GALE|' or similar
            if title.startswith('|') and title.endswith('|'):
                parts = title.strip('|').split(',')
                for part in parts:
                    clean_tag = part.strip()
                    if clean_tag:
                        ruletags.append(clean_tag)
        else:
            # If there's text directly in the span
            if rule_text:
                ruletags.append(rule_text)
    
    return ruletags

def extract_node_data(li):
    """Extract data from a node"""
    # Skip if no nodeid
    node_id_span = li.select_one('.nodeid')
    if not node_id_span:
        return None
    
    node_id = node_id_span.text.strip().replace('.', '')
    
    # Determine node type
    node_type = extract_node_type(li)
    
    # Check if this node has an 'end' span directly as its own child
    # A node is ONLY an end node if it has the <span class='end'>End</span> tag
    # We'll find the main div first
    main_div = li.find('div', recursive=False)
    is_end_node = False
    if main_div:
        # Look for the end span as a direct child of this div
        end_span = main_div.find('span', class_='end', recursive=False)
        is_end_node = bool(end_span)
    
    # For alias nodes, we should not include text/speaker/context from children
    speaker = ""
    text = ""
    context = ""
    if node_type != "alias":
        speaker = extract_speaker(li)
        text = extract_text(li)
        context = extract_context(li)
    
    is_jump = node_type == "jump"
    


    # Create node data structure
    node_data = {
        'id': node_id,
        'speaker': speaker if not is_jump else "",
        'text': text if not is_jump else "",
        'context': context if not is_jump else "",
        'checkflags': extract_flags(li, 'checkflag') if not is_jump else [],
        'setflags': extract_flags(li, 'setflag') if not is_jump else [],
        'ruletags': extract_ruletags(li) if not is_jump else [],
        'approval': extract_approval(li) if not is_jump else [],
        'rolls': extract_rolls(li) if not is_jump else "",
        'goto': extract_goto(li) if not is_end_node else "",
        'link': extract_link(li) if not is_end_node else "",
        'is_end': is_end_node,
        'node_type': node_type,
        'children': {}
    }
    
    return node_data

def extract_node_type(li):
    """Determine the type of node"""
    # Find the main div first (direct child of li)
    main_div = li.find('div', recursive=False)
    if not main_div:
        return "normal"
    
    # Get only the direct text of this div, not including children's text
    div_text = ''.join(text for text in main_div.find_all(string=True, recursive=False))
    
    # Check for specific node type markers in the direct text
    if '[Jump]' in div_text:
        return "jump"
    elif '[Alias]' in div_text:
        return "alias"
    elif '[RollResult]' in div_text:
        return "rollresult"
    elif '[Visual State]' in div_text:
        return "visualstate"
    elif '[Trade]' in div_text:
        return "trade"
    
    return "normal"

def extract_speaker(element):
    """Extract the speaker name from a node"""
    # Get node ID for reference
    node_id_span = element.select_one('.nodeid')
    node_id = ""
    if node_id_span:
        node_id = node_id_span.text.strip().replace('.', '')
    
    # Special case for node 92 which has a known issue

    
    # First, find the main div that is a direct child of the element
    main_div = element.find('div', recursive=False)
    if not main_div:
        return ""
    
    # Make sure we don't include child nodes in our search - only look at direct children
    # or elements within the current node's structure

    # Check for player dialog (.npcplayer)
    # Use find with recursive=False to only check direct children of main_div
    player = main_div.find('span', class_='npcplayer', recursive=False)
    if player:
        return "Player"
    
    # Check for direct NPC span (as a direct child)
    npc = main_div.find('span', class_='npc', recursive=False)
    if npc:
        return npc.text.strip()
    
    # Check for first-level nested div.npc
    # First look for the inline-block container
    speaker_container = main_div.find('div', style='display:inline-block;', recursive=False)
    if speaker_container:
        # Look for an NPC div inside this container
        nested_npc = speaker_container.find('div', class_='npc')
        if nested_npc:
            return nested_npc.text.strip()
    
    # As a last resort, look for any div.npc directly within main_div
    # but avoid going into child <ul> elements
    all_children = [c for c in main_div.children if c.name and c.name != 'ul']
    for child in all_children:
        if child.name == 'div' and 'npc' in child.get('class', []):
            return child.text.strip()
        # Check one level deeper for a div.npc
        if hasattr(child, 'find'):
            npc_div = child.find('div', class_='npc')
            if npc_div:
                return npc_div.text.strip()
    
    
    return ""

def extract_text(element):
    """Extract dialogue text from a node"""
    dialog = element.select_one('.dialog')
    if dialog:
        return dialog.text.strip()
    return ""

def extract_context(element):
    """Extract context notes from a node"""
    context = element.select_one('.context')
    if context and 'title' in context.attrs:
        return context['title'].strip()
    return ""

def extract_flags(element, flag_type):
    """Extract flag information from a node"""
    flags = []
    
    # First find the main div of the node
    main_div = element.find('div', recursive=False)
    if not main_div:
        return flags
    
    # Look for the span with the specified flag class as a direct child of the main div
    flag_span = main_div.find('span', class_=flag_type, recursive=False)
    
    if flag_span:
        # Extract the text directly from this span
        flag_text = flag_span.text.strip()
        
        # Sometimes the text might be in the form "[Flag] flag_name1, flag_name2"
        # Remove the "[Flag]" prefix if present
        if flag_text.startswith('['):
            bracket_end = flag_text.find(']')
            if bracket_end != -1:
                flag_text = flag_text[bracket_end + 1:].strip()
        
        # Split by comma and add each flag to the list
        if flag_text:
            for f in flag_text.split(','):
                clean_flag = f.strip()
                if clean_flag:
                    flags.append(clean_flag)
    
    return flags

def extract_approval(element):
    """Extract companion approval changes"""
    # Look for the approval span only as a direct child of the element's div
    # We first find the div that contains this node's data
    main_div = element.find('div', recursive=False)
    if not main_div:
        return []
    
    # Look for approval span as a direct child of this div
    approval_span = main_div.find('span', class_='approval', recursive=False)
    if not approval_span:
        return []
    
    approvals = []
    approval_text = approval_span.text.strip()
    
    # The format is usually ['Gale 1', 'Lae'zel 1', 'Astarion 1', ...]
    if approval_text.startswith('[') and approval_text.endswith(']'):
        # Remove the brackets
        approval_text = approval_text[1:-1]
        
        # Split by commas followed by a space and a quote
        parts = approval_text.split("', '")
        
        # Process the first and last parts specially to remove extra quotes
        if parts:
            parts[0] = parts[0].lstrip("'")
            parts[-1] = parts[-1].rstrip("'")
        
        for part in parts:
            # Check if it's a valid approval format (name followed by a number)
            # The number is usually the last token after a space
            tokens = part.split()
            if tokens and tokens[-1].strip('-').isdigit():
                # The value is the last token, and the name is everything before
                value = tokens[-1]
                char_name = ' '.join(tokens[:-1])
                approvals.append(f"{char_name} {value}")
    
    return approvals

def extract_rolls(element):
    """Extract skill roll information"""
    rolls_span = element.find('span', class_='rolls', recursive=False)
    if rolls_span:
        return rolls_span.text.strip()
    return ""

def extract_goto(element):
    """Extract goto information"""
    # First, find the div that is a direct child of the element
    main_div = element.find('div', recursive=False)
    if not main_div:
        return ""
    
    # Look for goto span as a direct child of this div
    goto_span = main_div.find('span', class_='goto', recursive=False)
    if goto_span and 'data-id' in goto_span.attrs:
        return goto_span['data-id']
    
    return ""

def extract_link(element):
    """Extract link information from a node.
    This is for <li class='goto'> elements which are direct links to other nodes.
    Or for nodes that have child <li class='goto'> elements.
    """
    # Check if this element itself is a goto link (not its children)
    if element.has_attr('class') and 'goto' in element['class']:
        goto_span = element.find('span', class_='goto')
        if goto_span and 'data-id' in goto_span.attrs:
            return goto_span['data-id']
    
    # Method 1: Check for ul > li.goto pattern
    # This search looks for any ul element within this node
    # and then for li.goto elements within those uls
    goto_li_elements = element.select('ul > li.goto')
    for goto_li in goto_li_elements:
        goto_span = goto_li.find('span', class_='goto', recursive=False)
        if goto_span and 'data-id' in goto_span.attrs:
            return goto_span['data-id']
    
    # Method 2: Direct CSS selector for nested goto links
    # If method 1 fails, try a more direct approach
    #goto_spans = element.select('ul li.goto span.goto[data-id]')
    #if goto_spans:
    #    return goto_spans[0]['data-id']
    
    return ""

def process_all_html_files(root_folder):
    """
    Recursively find and process all HTML files in the root folder and its subfolders.
    
    Args:
        root_folder: The path to the root folder containing HTML files.
    """
    # Count processed files
    file_count = 0
    errors = []
    
    # Walk through all directories and files
    for dirpath, dirnames, filenames in os.walk(root_folder):
        # Process HTML files in the current directory
        for filename in filenames:
            if filename.endswith('.html'):
                try:
                    # Get the full path to the HTML file
                    html_file = os.path.join(dirpath, filename)
                    print(f"Processing: {html_file}")
                    
                    # Parse the dialog tree
                    root_nodes, all_nodes, metadata = parse_dialog_tree(html_file)
                    output_data = {
                        'metadata': metadata,
                        'dialogue': root_nodes
                    }
                    # Create output file path (same structure but with .json extension)
                    output_file = html_file.replace('.html', '.json')
                    output_file = output_file.split('Dialogs/')[-1]
                    
                    output_root_path = "output"
                    output_file = os.path.join(output_root_path, output_file)
                    # Create directories if they don't exist
                    os.makedirs(os.path.dirname(output_file), exist_ok=True)
                    
                    # Output in JSON format
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(output_data, f, indent=2)
                    
                    # Increment counter
                    file_count += 1
                    
                    # Optional: Print some stats
                    print(f"  Total nodes: {len(all_nodes)}")
                    print(f"  Root nodes: {len(root_nodes)}")
                    print("-" * 50)
                    
                except Exception as e:
                    # Log any errors that occur
                    error_message = f"Error processing {filename}: {str(e)}"
                    print(f"ERROR: {error_message}")
                    errors.append(error_message)
    # Print summary
    print(f"\nProcessing complete!")
    print(f"Processed {file_count} HTML files")
    
    if errors:
        print(f"Encountered {len(errors)} errors:")
        for error in errors:
            print(f"  - {error}")
def main():
    # Root folder containing HTML files
    root_folder = 'data/BG3 - parsed dialogue (1.7)/Dialogs'
    
    # Process all HTML files
    process_all_html_files(root_folder)

if __name__ == "__main__":
    main()
'''
def main():
    # Parse the dialogue tree
    root_path = 'data/BG3 - parsed dialogue (1.7)/Dialogs'
    # iterate over all files in the root_path

    
    html_file = 'CHA_BronzePlaque_AD_FL1Mural.html'#'data/LOW_BhaalApproach_PAD_FarslayerReaction.html'#'data/MOO_Jailbreak_Wulbren.html'
    root_nodes, all_nodes = parse_dialog_tree(html_file)
    
    # Output in JSON format
    with open(f'{html_file.replace(".html", "")}.json', 'w', encoding='utf-8') as f:
        json.dump(root_nodes, f, indent=2)
    
    # Check node 20 as an example
    if '20' in all_nodes:
        print("Node 20 data:")
        node_20 = all_nodes['20']
        print(f"  Speaker: {node_20['speaker']}")
        print(f"  Text: {node_20['text'][:50]}...")
        print(f"  Checkflags: {node_20['checkflags']}")
        print(f"  Setflags: {node_20['setflags']}")
    
    # Print some stats
    print(f"\nTotal nodes: {len(all_nodes)}")
    print(f"Root nodes: {len(root_nodes)}")
    
    # Print a sample of root nodes
    print("\nRoot node IDs:")
    for i, node_id in enumerate(sorted(root_nodes.keys(), key=int)):
        print(f"  {node_id}")
        if i >= 40:  # Show only first 40
            print("  ...")
            break
    
    # Check node 206 specifically for approval
    if '206' in all_nodes:
        print(f"\nNode 206 approval data: {all_nodes['206']['approval']}")
    
    # Check a node with approvals (for testing)
    for node_id, node_data in all_nodes.items():
        if node_data['approval']:
            print(f"\nNode {node_id} has approvals: {node_data['approval']}")
            break
            
    # Validation: Count and check speaker types
    validate_speakers(all_nodes)

def validate_speakers(all_nodes):
    """Validate that speakers are correctly identified"""
    player_nodes = []
    npc_nodes = {}
    
    for node_id, node_data in all_nodes.items():
        speaker = node_data.get('speaker', '')
        
        if speaker == 'Player':
            player_nodes.append(node_id)
        elif speaker:
            if speaker not in npc_nodes:
                npc_nodes[speaker] = []
            npc_nodes[speaker].append(node_id)
    
    print("\nSpeaker validation:")
    print(f"  Player nodes: {len(player_nodes)}")
    print(f"  Sample player nodes: {player_nodes[:5]}")
    
    print(f"  NPC speakers: {len(npc_nodes)}")
    for speaker, nodes in list(npc_nodes.items())[:3]:  # Show first 3 NPC types
        print(f"    {speaker}: {len(nodes)} nodes (e.g., {nodes[:3]})")
    
    # Check node 92 specifically
    if '92' in all_nodes:
        print(f"\nNode 92 speaker: {all_nodes['92']['speaker']}")
    
    # Check some known player nodes
    known_player_nodes = ['57', '258', '30', '206']
    for node_id in known_player_nodes:
        if node_id in all_nodes:
            print(f"Node {node_id} speaker: {all_nodes[node_id]['speaker']}")
'''
if __name__ == "__main__":
    main()