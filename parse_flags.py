import xml.etree.ElementTree as ET
import os
import json

usage_map = {
    "1": "unknown",
    "2": "user",
    "3": "party",
    "4": "character",
    "5": "global",
    "6": "dialog",

}
def parse_bg3_flag_file(xml_content: str) -> tuple[str | None, str | None, str | None, str | None]:
    """
    Parses the XML content of a BG3 flag file to extract UUID, Name, Description, and Usage.

    Args:
        xml_content: A string containing the XML data.

    Returns:
        A tuple containing UUID, Name, Description, and Usage.
        Returns (None, None, None, None) if parsing fails or elements are not found.
    """
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError:
        return None, None, None, None

    # Find the main Flags node
    flags_node = root.find('.//node[@id="Flags"]')
    if flags_node is None:
        # Try to find Flags node within a region if the top-level node is not "Flags"
        # This handles cases where the structure might be <save><region id="Flags"><node id="Flags">...</node></region></save>
        region_node = root.find('.//region[@id="Flags"]')
        if region_node is not None:
            flags_node = region_node.find('./node[@id="Flags"]')
        
    if flags_node is None:
        return None, None, None, None

    uuid_element = flags_node.find('./attribute[@id="UUID"]')
    uuid = uuid_element.get("value") if uuid_element is not None else None

    name_element = flags_node.find('./attribute[@id="Name"]')
    name = name_element.get("value") if name_element is not None else None

    description_element = flags_node.find('./attribute[@id="Description"]')
    description = description_element.get("value") if description_element is not None else None

    usage_element = flags_node.find('./attribute[@id="Usage"]')
    usage = usage_element.get("value") if usage_element is not None else None

    return uuid, name, description, usage

if __name__ == "__main__":
    flags_dir = "GustavDev/Flags"  # Assuming flags are in this directory
    all_flags_data = []
    output_json_file = "parsed_flags.json"

    if not os.path.exists(flags_dir):
        print(f"Error: Directory '{flags_dir}' not found. Please ensure the path is correct and the directory exists.")
    else:
        for filename in os.listdir(flags_dir):
            if filename.endswith(".lsf.lsx"):
                file_path = os.path.join(flags_dir, filename)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        file_content = f.read()
                    
                    # Skip empty or malformed files early
                    if not file_content.strip():
                        print(f"Warning: File {filename} is empty. Skipping.")
                        continue

                    uuid, name, description, usage = parse_bg3_flag_file(file_content)
                    
                    if uuid:  # Ensure we only add entries with a UUID
                        all_flags_data.append({
                            "file": filename,
                            "uuid": uuid,
                            "name": name,
                            "description": description,
                            "usage": usage_map[usage]
                        })
                    else:
                        print(f"Warning: Could not parse UUID (or main Flags node) from {filename}. Skipping.")
                except ET.ParseError as e:
                    print(f"XML Parse Error in file {filename}: {e}. Skipping.")
                except Exception as e:
                    print(f"Error processing file {filename}: {e}. Skipping.")

        if all_flags_data:
            with open(output_json_file, "w", encoding="utf-8") as outfile:
                json.dump(all_flags_data, outfile, indent=4)
            print(f"Successfully parsed {len(all_flags_data)} flag files and saved data to {output_json_file}")
        else:
            print(f"No .lsf.lsx files were successfully parsed in {flags_dir}.")

    # Example of how to use the parser with a string (for testing)
    # test_xml_data = """<?xml version="1.0" encoding="utf-8"?>
    # <save>
    #     <version major="4" minor="0" revision="9" build="2" lslib_meta="v1,bswap_guids,lsf_keys_adjacency" />
    #     <region id="Flags">
    #         <node id="Flags">
    #             <attribute id="UUID" type="guid" value="ff5cbe4e-d3a8-4cc6-86fa-f336f15e4304" />
    #             <attribute id="Name" type="FixedString" value="ORI_State_ChosePartnerOverGale" />
    #             <attribute id="Description" type="LSString" value="This player chose their romantic partner over Gale" />
    #             <attribute id="Usage" type="uint8" value="4" />
    #         </node>
    #     </region>
    # </save>"""
    # uuid, name, description, usage = parse_bg3_flag_file(test_xml_data)
    # if uuid:
    #     print("\nTest XML Data:")
    #     print(f"  UUID: {uuid}")
    #     print(f"  Name: {name}")
    #     print(f"  Description: {description}")
    #     print(f"  Usage: {usage}")
    # else:
    #     print("\nTest XML Data: Failed to parse.") 