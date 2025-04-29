import json, os
import langchain_openai
import langchain_core
from langchain_core.output_parsers import JsonOutputParser
from tqdm import tqdm
root_dir = "output_merged/Tutorial"

for merged_session_folder_path in tqdm(os.listdir(root_dir)):
    merged_session_path = f"{root_dir}/{merged_session_folder_path}"
    
    
    print(merged_session_path)
    if not merged_session_path.endswith(".json"):
        continue
    with open(merged_session_path, 'r') as f:
        merged_session = json.load(f)

    metadata = merged_session["metadata"]
    dialogue = merged_session["dialogue"]
    individual_metadata = metadata["individual_metadata"]
    chat = langchain_openai.ChatOpenAI(model="o3-mini", api_key="")

    chain = chat | JsonOutputParser()
    prompt_path = "automatic_ordering.txt"
    with open(prompt_path, 'r') as f:
        prompt = f.read()

    prompt = prompt.format(individual_metadata=individual_metadata)

    response = chain.invoke(prompt)
    # update the merged_session with the response
    merged_session["metadata"]["automatic_ordering"] = response
    with open(merged_session_path, 'w') as f:
        json.dump(merged_session, f, indent=2)
