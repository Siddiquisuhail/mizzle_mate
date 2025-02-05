import json
from typing import List




def clean_allowed_zones(json_input: dict) -> list:
    """
    Extracts relevant fields from the allowed_zones data and returns a cleaned dictionary.
    """
    cleaned_data = []
    
    # Ensure the input structure is correct
    # if not json_input.get("allowed_zones") or not json_input["allowed_zones"].get("data"):
    #     return {"allowed_zones": []}
    
    # Extract relevant fields
    for zone in json_input["data"]:
        cleaned_data.append({
            "name": zone.get("name"),
            "country": zone.get("country"),
            "zone": zone.get("zone"),
            "zone_code": zone.get("zone_code")
        })
    
    return  cleaned_data


def clean_allowed_projects(json_input: dict) -> list:
    """
    Extracts relevant fields from the allowed_zones data and returns a cleaned dictionary.
    """
    cleaned_data = []
    
    # Ensure the input structure is correct
    # if not json_input.get("allowed_zones") or not json_input["allowed_zones"].get("data"):
    #     return {"allowed_zones": []}
    
    # Extract relevant fields
    for zone in json_input["data"]:
        cleaned_data.append({
            "name": zone.get("name"),
            "id": zone.get("uuid")
        })
    
    return  cleaned_data


def clean_allowed_packages(json_input: dict) -> list:
    """
    Extracts relevant fields from databases, programming_languages, cms, and os,
    and returns a cleaned list of dictionaries.
    """
    cleaned_data = []
    
    if not json_input.get("data"):
        return []
    
    data_sections = {
        "databases": ["name", "db_type", "versions"],
        "programming_languages": ["name", "versions"],
        "cms": ["name"],
        "os": ["name", "versions"]
    }
    
    for section, fields in data_sections.items():
        if section in json_input["data"]:
            extracted_section = []
            for item in json_input["data"][section]:
                clean_item = {
                    field: ([v["version"] for v in item.get("versions", [])] if field == "versions" else item.get(field))
                    for field in fields
                }
                extracted_section.append(clean_item)
            cleaned_data.append({section: extracted_section})
    
    return cleaned_data



def clean_instance_types(json_input: dict) -> list:
    cleaned_data = []
    for item in json_input.get("data", []):
        cleaned_data.append({
            "name": item["name"],
            "price": item["price"],
            "periodicity": item["periodicity"],
            "memmory_size": f"{item['memmory_size']} {item['memmory_unit']}",
            "storage_size": f"{item['storage_size']} {item['storage_unit']}",
            "vcpu": str(item["vcpu"])
        })
    return cleaned_data


def clean_allowed_security_groups(json_input: dict) -> list:
    return json_input

def clean_key_pair_names(json_input: dict) -> list:
    cleaned_data = []
    if json_input is not None:
        for item in json_input.get("data", []):
            cleaned_data.append({
                "name": item["keypair_name"]
                
                
            })
        return cleaned_data
    else:
        return []
    
