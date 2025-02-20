import re
import json

def clean_response(response: str, prompt: str) -> str:
    """
    Cleans the AI response by removing system, user, and assistant labels,
    keeping only the assistant's meaningful response.
    """

    ##############################################
    
    if "assistant" not in response:
        lines = response.split("\n")
        
        # Initialize variables
        assistant_response = []
        is_assistant = False
    
        for line in lines:
            line = line.strip()
            if line.lower() == "mate":  
                is_assistant = True
                continue

            if is_assistant: 
                assistant_response.append(line)
        response = "\n".join(assistant_response).strip()
        response = response.split('mate: ')[-1].replace(prompt , "").replace("</think>", "")
    else:
        response = response.split("</think>")[-1]

    # response = "\n".join(assistant_response).strip()
    # response = response.split('user: ')[-1].replace(prompt , "").replace("</think>", "")
    response = response.split("assistant")[-1].replace(prompt , "").replace("</think>", "")
    print(response)
    return response

def clean_instance_creation_response(response: str, prompt: str) -> str:
    """
    Cleans the AI response by removing system, user, and assistant labels,
    keeping only the assistant's meaningful response.
    """

    ##############################################
    
    response = response.split("</think>")[-1]
    response = response.replace("<|begin_of_text|>system", "").replace(prompt , "").replace("</think>", "")
    # response = response.split("<option>")[-1]
    # response = "\n".join(assistant_response).strip()
    # response = response.split('user: ')[-1].replace(prompt , "").replace("</think>", "")
    # response = response.split("nassistant")[-1].replace(prompt , "").replace("</think>", "")
    print(response)
    return response

