# from app.utils.orchestrator import Orchestrator
import redis
from app.models.chat_models import UserQuery, ChatResponse
from app.models.instance_models import InstanceRequest
from app.utils.instance_creation_utils.instance_data_cache import fetch_allowed_values
import json
import re
import requests
from typing import Dict
# import text


# orchestrator = Orchestrator()
redis_client = redis.Redis(host="localhost", port=6379, decode_responses=True)

HARDCODED_SECURITY_GROUP = {
    "name": "default",
    "description": "default description",
    "rules": [
        {
            "bound_type": "In bound",
            "description": "sample description",
            "rule_type": "SSH",
            "protocol": "TCP",
            "port_range": "22",
            "destination_type": "AnywhereIPv4",
            "destination_group": "CIDR blocks",
            "destination": "0.0.0.0/0"
        }
    ]
}

class WorkflowState:
    def __init__(self):
        self.instance_data = {"packages": {}}
        self.current_step = "start"
        self.next_step = None
        self.response = None

class Instance_Creation:
    def __init__(self, query: UserQuery):
        self.redis_client = redis_client
        # self.llm = orchestrator.instance_creation_query_handler()
        self.allowed_values = fetch_allowed_values(query.jwt_token)
        self.query = query
        self.jwt_token = query.jwt_token
        self.public_key_name = None
        self.public_key_download = None

    # Step Handlers ----------------------------------------------------------
    
    def ask_for_project(self, state):
        projects = [project["name"] for project in self.allowed_values["allowed_projects"]]
        print("#########################")
        print("projects: ", projects)
        print("#########################")
        state.response = f"In which project do you want to create the instance? Allowed projects: {', '.join(projects)}"
        state.current_step = "project"
        return state
    
    
    def ask_for_instance_name(self, state):
        state.response = "Please provide the instance name:"
        state.current_step = "instance_name"
        return state

    def ask_for_location(self, state):
        zones = [zone["zone"] for zone in self.allowed_values["allowed_zones"]]
        state.response = f"Allowed locations: {', '.join(zones)}"
        state.current_step = "location"
        return state

    def ask_for_prepackage_or_custom(self, state):
        state.response = "Choose instance type (Prepackage/Custom):"
        state.current_step = "prepackage_or_custom"
        return state

    def ask_for_instance_type(self, state):
        instances = "\n".join([
            f"- {i['name']} (${i['price']}/{i['periodicity']}, "
            f"{i['memmory_size']}GB RAM, {i['storage_size']}GB Storage, "
            f"{i['vcpu']} vCPU)"
            for i in self.allowed_values["instance_types"]
        ])
        state.response = f"Available instances:\n{instances}"
        state.current_step = "instance_type"
        return state

    def ask_for_custom_instance_details(self, state):
        state.response = "Enter memory(GB), storage(GB), vCPU (comma-separated):"
        state.current_step = "custom_instance_details"
        return state

    def ask_for_platform_os(self, state):
        os_list = [os["name"] for os in self.allowed_values["allowed_packages"][-1]["os"]]
        state.response = f"Available OS: {', '.join(os_list)}"
        state.current_step = "platform_os"
        return state

    def ask_for_platform_os_version(self, state):
        current_os = next(
            (os for os in self.allowed_values["allowed_packages"][-1]["os"] 
             if os["name"].lower() == state.instance_data["platform"]["name"].lower()),
            None
        )
        if current_os:
            versions = ", ".join(current_os["versions"])
            state.response = f"Available versions for {current_os['name']}: {versions}"
            state.current_step = "platform_os_version"
        return state
    
    
    def ask_for_database(self, state):
        # Collect all database names
        databases = []
        for package in self.allowed_values["allowed_packages"]:
            if "databases" in package:
                databases.extend([db["name"] for db in package["databases"]])

        print("#########################")
        print("databases: ", databases)
        print("#########################")
        state.response = f"Install database? (No/{'/'.join(databases)})"
        state.current_step = "database"
        return state

    def ask_for_database_version(self, state):
        current_db = None
        # Search for the selected database and fetch available versions
        for package in self.allowed_values["allowed_packages"]:
            if "databases" in package:
                current_db = next(
                    (db for db in package["databases"]
                    if db["name"].lower() == state.instance_data["packages"]["databases"]["name"].lower()),
                    None
                )
                if current_db:
                    break

        if current_db:
            versions = ", ".join(current_db["versions"])
            state.response = f"Available versions for {current_db['name']}: {versions}"
            state.current_step = "database_version"
        return state

    def ask_for_cms(self, state):
        # Collect all CMS names
        cms_list = []
        for package in self.allowed_values["allowed_packages"]:
            if "cms" in package:
                cms_list.extend([cms["name"] for cms in package["cms"]])

        state.response = f"Install CMS? (No/{'/'.join(cms_list)})"
        state.current_step = "cms"
        return state

    def ask_for_cms_version(self, state):
        current_cms = None
        # Search for the selected CMS
        for package in self.allowed_values["allowed_packages"]:
            if "cms" in package:
                current_cms = next(
                    (cms for cms in package["cms"]
                    if cms["name"].lower() == state.instance_data["packages"]["cms"]["name"].lower()),
                    None
                )
                if current_cms:
                    break

        if current_cms:
            # Assuming 'versions' key might be missing for CMS
            versions = "No versions available"  # Default if versions are not specified
            state.response = f"Available versions for {current_cms['name']}: {versions}"
            state.current_step = "cms_version"
        return state

    def ask_for_language(self, state):
        # Collect all programming language names
        langs = []
        for package in self.allowed_values["allowed_packages"]:
            if "programming_languages" in package:
                langs.extend([lang["name"] for lang in package["programming_languages"]])

        state.response = f"Install language? (No/{'/'.join(langs)})"
        state.current_step = "language"
        return state

    def ask_for_language_version(self, state):
        current_lang = None
        # Search for the selected programming language
        for package in self.allowed_values["allowed_packages"]:
            if "programming_languages" in package:
                current_lang = next(
                    (lang for lang in package["programming_languages"]
                    if lang["name"].lower() == state.instance_data["packages"]["programming_languages"]["name"].lower()),
                    None
                )
                if current_lang:
                    break

        if current_lang:
            versions = ", ".join(current_lang["versions"])
            state.response = f"Available versions for {current_lang['name']}: {versions}"
            state.current_step = "language_version"
        return state


    def ask_for_instance_count(self, state):
        state.response = "How many instances do you need?"
        state.current_step = "instance_count"
        return state
    
    
    
    def ask_for_public_key(self, state):
        keypairs = [zone["name"] for zone in self.allowed_values["allowed_keypairs"]]
        state.response = f"Available options existing keys are {'/  '.join(keypairs)}).\n \n If you want to create a new one, please provide a name for the new keypair:"
        state.current_step = "public_key"
        return state

    def ask_for_keypair_creation(self, state):
        state.response = "Please provide a name for the new keypair:"
        state.current_step = "keypair_creation"
        return state
    
    def ask_for_keypair_creation_download(self, state):
        state.response = f"Please download the keypair and save it in the root directory of the instance.\n\n {self.public_key_download}"
        state.current_step = "keypair_creation_download"
        return state
    
    
    # Input Processing --------------------------------------------------------
    def process_input(self, state: WorkflowState, user_input: str):
        step = state.current_step
        data = state.instance_data

        try:
            if step == "instance_name":
                data["instance_name"] = user_input.strip()
                
            elif step == "project":
                selected = next(p for p in self.allowed_values["allowed_projects"]
                               if p["name"].lower() == user_input.lower())
                data["project"] = selected["id"]
                
            elif step == "location":
                selected = next(z for z in self.allowed_values["allowed_zones"] 
                               if z["zone"].lower() == user_input.lower())
                data["server_zone_code"] = selected["zone_code"]
                
            elif step == "project":
                selected = next(z for z in self.allowed_values["allowed_projects"] 
                               if z["name"].lower() == user_input.lower())
                data["project"] = selected["id"]
                
            elif step == "prepackage_or_custom":
                if user_input.lower() not in ["prepackage", "custom"]:
                    raise ValueError("Invalid choice")
                data["type"] = user_input.lower()
                
            elif step == "instance_type":
                selected = next(i for i in self.allowed_values["instance_types"]
                               if i["name"].lower() == user_input.lower())
                data["instance_type"] = selected["name"]
                
            elif step == "custom_instance_details":
                parts = [float(x.strip()) for x in user_input.split(",")]
                if len(parts) != 3:
                    raise ValueError("Need 3 values")
                data["custom_instance_type"] = {
                    "memmory_size": parts[0],
                    "storage_size": parts[1],
                    "vcpu": parts[2]
                }
                
            elif step == "platform_os":
                selected = next(os for os in self.allowed_values["allowed_packages"][-1]["os"]
                               if os["name"].lower() == user_input.lower())
                data["platform"] = {"name": selected["name"]}
                
            elif step == "platform_os_version":
                
                data["platform"]["version"] = user_input.strip()
                
                
            elif step == "ask_for_database":
                if user_input.lower() != "no":
                    databases = []
                    for package in self.allowed_values["allowed_packages"]:
                        if "databases" in package:
                            databases.extend([db["name"] for db in package["databases"]])
                    selected = next(db for db in databases
                                   if db.lower() == user_input.lower())
                    data["packages"].setdefault("databases", []).append({"name": selected})
                    
            elif step == "ask_for_database_version":
                data["packages"]["databases"]["version"] = user_input.strip()
                
                
            elif step == "ask_for_cms":
                if user_input.lower() != "no":
                    cms_list = []
                    for package in self.allowed_values["allowed_packages"]:
                        if "cms" in package:
                            cms_list.extend([cms["name"] for cms in package["cms"]])
                    selected = next(cms for cms in cms_list
                                   if cms.lower() == user_input.lower())
                    data["packages"].setdefault("cms", []).append({"name": selected})
                    
            elif step == "ask_for_cms_version":
                data["packages"]["cms"]["version"] = user_input.strip()
                
            elif step == "ask_for_language":
                if user_input.lower() !=  "no":
                    langs = []
                    for package in self.allowed_values["allowed_packages"]:
                        if "programming_languages" in package:
                            langs.extend([lang["name"] for lang in package["programming_languages"]])
                    selected = next(lang for lang in langs
                                   if lang.lower() == user_input.lower())
                    data["packages"].setdefault("programming_languages", []).append({"name": selected})
                    
            elif step == "ask_for_language_version":
                data["packages"]["programming_languages"]["version"] = user_input.strip()
                
                
            elif step == "ask_for_public_key":
                try:
                    print("#########################")
                    print("keypairs: ", self.allowed_values["allowed_keypairs"])
                    print("#########################")
                    selected = next(p for p in self.allowed_values["allowed_keypairs"]
                                if p["name"].strip().lower() == user_input.strip().lower())
                    print("#########################")
                    print("Selected: ", selected)
                    print("#########################")
                    data["public_key"] = selected
                except StopIteration:
                    pass
    
            elif step == "ask_for_keypair_creation":
                print("#########################")
                print("data before public key: ", data)
                print("#########################")
                data["new_publickey_name"] = user_input.strip()
                data["public_key"] = user_input.strip()
                print("#########################")
                print("data after public key: ", data)
                print("#########################")
                    
            elif step == "ask_for_instance_count":
                data["instance_count"] = int(user_input.strip())
                
            
                
        except (ValueError, StopIteration) as e:
            state.response = f"Invalid input: {str(e)}. Please try again."
            return state

        return state

    # Workflow Management -----------------------------------------------------
    
    
    def get_next_step(self, current_step, instance_data):
        transitions = {
            "start": "project",
            "project": "instance_name",
            "instance_name": "location",
            "location": "prepackage_or_custom",
            "prepackage_or_custom": lambda: (
                "instance_type" if instance_data.get("type") == "prepackage"
                else "custom_instance_details"
            ),
            "instance_type": "platform_os",
            "custom_instance_details": "platform_os",
            "platform_os": "platform_os_version",   
            "platform_os_version": "database",
            "database": lambda: (
                # "database_version" if "databases" in instance_data["packages"]["databases"]
                "database_version" if instance_data.get("packages").get("databases")
                else "cms"  
            ),  
            "database_version": "cms",
            "cms": lambda: (
                # "cms_version" if "cms" in instance_data["packages"]["cms"]
                "cms_version" if instance_data.get("packages").get("cms")
                else "language"
            ),
            "cms_version": "language",
            "language": lambda: (
                # "language_version" if "programming_languages" in instance_data["packages"]["programming_languages"]
                "language_version" if instance_data.get("packages").get("programming_languages")
                else "public_key"
            ),
            "language_version": "public_key",
            "public_key":lambda: (
                "instance_count" if instance_data.get("public_key")
                else "keypair_creation"
            ),
            "keypair_creation": "keypair_creation_download",
            "keypair_creation_download": "instance_count"
        }
        print("#########################")
        print("current_step: ", current_step)
        print("#########################")  
        next_step = transitions.get(current_step, "finalize")
        print("#########################")
        print("next_step: ", next_step)
        print("#########################")
        if callable(next_step):
            return next_step()
        return next_step

    def run_workflow(self, session_id: str, user_input: str) -> Dict:
        state_key = f"workflow_state:{session_id}"
        data_key = f"instance_data:{session_id}"

        # Load state
        state = WorkflowState()
        if self.redis_client.exists(state_key):
            state.current_step = self.redis_client.get(state_key)
            state.instance_data = json.loads(self.redis_client.get(data_key) or "{}")

        # Process input if provided
        if user_input and state.current_step != "start":
            state = self.process_input(state, user_input)

        # Determine next step
        next_step = self.get_next_step(state.current_step, state.instance_data)
        print("#########################")
        print("next_step: ", next_step)
        print("#########################")
        state.current_step = next_step

        # Generate response
        handler = getattr(self, f"ask_for_{next_step}", None)
        print("#########################")
        print("handler: ", handler)
        print("#########################")
        if handler is not None:
            state = handler(state)
            print("#########################")
            print("state: ", state)
            print("#########################")  
        else:
            state.response = "Instance configuration complete!"

        # Save state
        self.redis_client.set(state_key, state.current_step)
        self.redis_client.set(data_key, json.dumps(state.instance_data))

        return {"response": state.response, "data": state.instance_data}

    # API Integration ---------------------------------------------------------
    def trigger_instance_creation_api(self, instance_data: Dict) -> str:
        # Clean up instance type data
        if "custom_instance_type" in instance_data:
            instance_data.pop("instance_type", None)
            
        instance_data.pop("type", None)
        instance_data.pop("new_publickey_name", None)
        instance_data.pop("public_key_download", None)
            
        # Add hardcoded security group
        instance_data["custom_security_group"] = HARDCODED_SECURITY_GROUP
        
        # Ensure array formats
        for pkg_type in ["databases", "cms", "programming_languages"]:
            instance_data["packages"][pkg_type] = instance_data["packages"].get(pkg_type, [])
            
        # Add default public key if missing
        instance_data.setdefault("public_key", "DefaultKey")
        
        print("#########################")
        print("instance_data: ", instance_data)
        print("#########################")
        
        headers = {
            "Authorization": f"Bearer {self.jwt_token}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            "https://enterprisepythonbackend.mizzle.io/api/instance/create-instance",
            json=instance_data,
            headers=headers
        )
        
        return response.text
    
    
    def trigger_keypair_creation_api(self, instance_data: Dict) -> str:
        
        payload = {
                        "keypair_name": instance_data["new_publickey_name"],
                        "keypair_type": "RSA",
                        "keypair_file_format": "pem"
                        }
        
        print("#########################")
        print("public_key_data: ", payload)
        print("#########################")
        
        headers = {
            "Authorization": f"Bearer {self.jwt_token}",
            "Content-Type": "application/json"
        }
        instance_data['public_key'] = payload['keypair_name']
        response = requests.post(
            "https://enterprisepythonbackend.mizzle.io/api/instance/keypair",
            json=payload,
            headers=headers
        )
        
        print("#########################")
        print("keypair_response: ", response)
        print("#########################")
        
        self.public_key_download = response.text
        return response.text

    def run_chat(self, query: UserQuery):
        result = self.run_workflow(query.session_id, query.text)
        print("#########################")
        print("Intermediate result: ", result)
        print("#########################")
        
        if "new_publickey_name" in result["data"]:
            print("#########################")
            print("Creating keypair: ", result["data"]["new_publickey_name"])
            print("#########################")
            api_response = self.trigger_keypair_creation_api(result["data"]['new_publickey_name'])
            print("#########################")
            print("api_response: ", api_response)
            print("#########################")
            return {"response": api_response}
        
        if "Instance configuration complete!" in result["response"]:
            print("#########################")
            print("result: ", result)
            print("#########################")
            api_response = self.trigger_instance_creation_api(result["data"])
            print("api_response: ", api_response)
            print("#########################")
            return {"response": api_response}
            
        return {"response": result["response"]}

