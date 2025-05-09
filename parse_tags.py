import xml.etree.ElementTree as ET
import os
import json

def parse_bg3_tag_file(xml_content: str) -> tuple[str | None, str | None, list[str]]:
    """
    Parses the XML content of a BG3 tag file to extract the UUID, Name, and categories.

    Args:
        xml_content: A string containing the XML data.

    Returns:
        A tuple containing the UUID (str), Name (str), and a list of category names (list[str]).
        Returns (None, None, []) if parsing fails or elements are not found.
    """
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError:
        return None, None, []

    # Find the main Tags node
    tags_node = root.find('.//node[@id="Tags"]')
    if tags_node is None:
        return None, None, []

    uuid_element = tags_node.find('./attribute[@id="UUID"]')
    uuid = uuid_element.get("value") if uuid_element is not None else None

    name_element = tags_node.find('./attribute[@id="Name"]')
    name = name_element.get("value") if name_element is not None else None

    categories = []
    category_nodes = tags_node.findall('.//node[@id="Categories"]//node[@id="Category"]')
    for category_node in category_nodes:
        name_attribute = category_node.find('./attribute[@id="Name"]')
        if name_attribute is not None:
            category_name = name_attribute.get("value")
            if category_name:
                categories.append(category_name)

    return uuid, name, categories

if __name__ == "__main__":
    # xml_data = """<?xml version="1.0" encoding="utf-8"?>
    # <save>
    #     <version major="4" minor="0" revision="9" build="306" lslib_meta="v1,bswap_guids,lsf_keys_adjacency" />
    #     <region id="Tags">
    #         <node id="Tags">
    #             <attribute id="UUID" type="guid" value="f4d1035b-5d77-411a-85fb-c9bdfeb00e8b" />
    #             <attribute id="Name" type="FixedString" value="PRESET_HIRELING_DRUID" />
    #             <attribute id="DisplayName" type="TranslatedString" handle="ls::TranslatedStringRepository::s_HandleUnknown" version="0" />
    #             <attribute id="DisplayDescription" type="TranslatedString" handle="ls::TranslatedStringRepository::s_HandleUnknown" version="0" />
    #             <attribute id="Icon" type="FixedString" value="" />
    #             <attribute id="Description" type="LSString" value="Tag for a specific hireling companion" />
    #             <children>
    #                 <node id="Categories">
    #                     <children>
    #                         <node id="Category">
    #                             <attribute id="Name" type="LSString" value="Code" />
    #                         </node>
    #                         <node id="Category">
    #                             <attribute id="Name" type="LSString" value="Dialog" />
    #                         </node>
    #                         <node id="Category">
    #                             <attribute id="Name" type="LSString" value="Story" />
    #                         </node>
    #                         <node id="Category">
    #                             <attribute id="Name" type="LSString" value="DialogHidden" />
    #                         </node>
    #                     </children>
    #                 </node>
    #                 <node id="Properties" />
    #             </children>
    #         </node>
    #     </region>
    # </save>
    # """
    # uuid, name, category_list = parse_bg3_tag_file(xml_data)
    # print(f"UUID: {uuid}")
    # print(f"Name: {name}")
    # print(f"Categories: {category_list}")

    tags_dir = "GustavDev/Tags"
    all_tags_data = []
    output_json_file = "parsed_tags.json"

    if not os.path.exists(tags_dir):
        print(f"Error: Directory '{tags_dir}' not found. Please ensure the path is correct.")
    else:
        for filename in os.listdir(tags_dir):
            if filename.endswith(".lsf.lsx"): # Corrected extension check
                file_path = os.path.join(tags_dir, filename)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        file_content = f.read()
                    uuid, name, categories = parse_bg3_tag_file(file_content)
                    if uuid: # Ensure we only add entries with a UUID
                        all_tags_data.append({
                            "file": filename,
                            "uuid": uuid,
                            "name": name,
                            "categories": categories
                        })
                    else:
                        print(f"Warning: Could not parse UUID from {filename}. Skipping.")
                except Exception as e:
                    print(f"Error processing file {filename}: {e}")

        with open(output_json_file, "w", encoding="utf-8") as outfile:
            json.dump(all_tags_data, outfile, indent=4)

        print(f"Successfully parsed {len(all_tags_data)} files and saved data to {output_json_file}")

    # Example with a file path (assuming the file is in the same directory)
    # try:
    #     with open("bg3sim/GustavDev/Tags/f4d1035b-5d77-411a-85fb-c9bdfeb00e8b.lsf.lsx", "r", encoding="utf-8") as f:
    #         file_content = f.read()
    #     uuid_from_file, name_from_file, categories_from_file = parse_bg3_tag_file(file_content)
    #     print(f"UUID from file: {uuid_from_file}")
    #     print(f"Name from file: {name_from_file}")
    #     print(f"Categories from file: {categories_from_file}")
    # except FileNotFoundError:
    #     print("\nCould not find the specified XML file.")
    # except Exception as e:
    #     print(f"\nAn error occurred: {e}")
