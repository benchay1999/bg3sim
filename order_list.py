import json, os
from tqdm import tqdm
root_dir = "output_merged/Act1"

for merged_session_folder_path in tqdm(os.listdir(root_dir)):
    merged_session_folder = f"{root_dir}/{merged_session_folder_path}"
    if merged_session_folder_path != "Forest":
        continue
    print(merged_session_folder)
    
    for merged_session_path in os.listdir(merged_session_folder):
        merged_session_path = f"{merged_session_folder}/{merged_session_path}"
        print(merged_session_path)
        if not merged_session_path.endswith(".json"):
            continue
        with open(merged_session_path, 'r') as f:
            merged_session = json.load(f)

        automatic_ordering = merged_session["metadata"]["automatic_ordering"]
        print(automatic_ordering)
        import pdb; pdb.set_trace()