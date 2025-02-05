# from app.utils.orchestrator import Orchestrator
import redis
from app.models.chat_models import UserQuery, ChatResponse
from app.models.instance_models import InstanceRequest
from app.utils.instance_creation_utils.instance_data_cache import fetch_allowed_values
import json
import re
import requests
from typing import Dict



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


    # def ask_for_database(self, state):
    #     databases = [db["name"] for db in self.allowed_values["allowed_packages"]["databases"]]
    #     print("#########################")
    #     print("databases: ", databases)
    #     print("#########################")  
    #     state.response = f"Install database? (No/{'/'.join(databases)})"
    #     state.current_step = "ask_for_database"
    #     return state

    # def ask_for_database_version(self, state):
    #     current_db = next(
    #         (db for db in self.allowed_values["allowed_packages"]["databases"]
    #          if db["name"].lower() == state.instance_data["packages"]["databases"]["name"].lower()),
    #         None
    #     )
    #     if current_db:
    #         versions = ", ".join(current_db["versions"])
    #         state.response = f"Available versions for {current_db['name']}: {versions}"
    #         state.current_step = "ask_for_database_version"
    #     return state

    # def ask_for_cms(self, state):
    #     cms_list = [cms["name"] for cms in self.allowed_values["allowed_packages"]["cms"]]
    #     state.response = f"Install CMS? (No/{'/'.join(cms_list)})"
    #     state.current_step = "ask_for_cms"
    #     return state

    # def ask_for_cms_version(self, state):
    #     current_cms = next(
    #         (cms for cms in self.allowed_values["allowed_packages"]["cms"]
    #          if cms["name"].lower() == state.instance_data["packages"]["cms"]["name"].lower()),
    #         None
    #     )
    #     if current_cms:
    #         versions = ", ".join(current_cms["versions"])
    #         state.response = f"Available versions for {current_cms['name']}: {versions}"
    #         state.current_step = "ask_for_cms_version"
    #     return state

    # def ask_for_language(self, state):
    #     langs = [lang["name"] for lang in self.allowed_values["allowed_packages"]["programming_languages"]]
    #     state.response = f"Install language? (No/{'/'.join(langs)})"
    #     state.current_step = "ask_for_language"
    #     return state

    # def ask_for_language_version(self, state):
    #     current_lang = next(
    #         (lang for lang in self.allowed_values["allowed_packages"]["programming_languages"]
    #          if lang["name"].lower() == state.instance_data["packages"]["programming_languages"]["name"].lower()),
    #         None
    #     )
    #     if current_lang:
    #         versions = ", ".join(current_lang["versions"])
    #         state.response = f"Available versions for {current_lang['name']}: {versions}"
    #         state.current_step = "ask_for_language_version"
    #     return state

    def ask_for_instance_count(self, state):
        state.response = "How many instances do you need?"
        state.current_step = "instance_count"
        return state
    
    
    
    def ask_for_public_key(self, state):
        keypairs = [zone["name"] for zone in self.allowed_values["allowed_keypairs"]]
        state.response = f"You can either select from the list or create a new one? (No/{'/'.join(keypairs)}).\n \n If you want to create a new one, please provide a name for the new keypair:"
        state.current_step = "public_key"
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
                print("#########################")
                print("before_os_version_data: ", data)
                print("#########################")
                data["platform"]["version"] = user_input.strip()
                print("#########################")
                print("after_os_version_data: ", data)
                print("#########################")
                
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
                print("#########################")
                print("before_database_version_data: ", data)
                print("#########################")
                data["packages"]["databases"]["version"] = user_input.strip()
                print("#########################")
                print("after_database_version_data: ", data)
                print("#########################")
                
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
                
            elif step == "ask_for_instance_count":
                data["instance_count"] = int(user_input.strip())
                
            elif step == "keypair":
                data["public_key"] = user_input.strip()
                
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
                "cms_version" if     instance_data.get("packages").get("cms")
                else "language"
            ),
            "cms_version": "language",
            "language": lambda: (
                # "language_version" if "programming_languages" in instance_data["packages"]["programming_languages"]
                "language_version" if instance_data.get("packages").get("programming_languages")
                else "instance_count"
            ),
            "language_version": "instance_count",
            "instance_count": "public_key"
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

    def run_chat(self, query: UserQuery):
        result = self.run_workflow(query.session_id, query.text)
        print("#########################")
        print("Intermediate result: ", result)
        print("#########################")
        
        if "Instance configuration complete!" in result["response"]:
            print("#########################")
            print("result: ", result)
            print("#########################")
            api_response = self.trigger_instance_creation_api(result["data"])
            print("#########################")
            print("api_response: ", api_response)
            print("#########################")
            return {"response": api_response}
            
        return {"response": result["response"]}












##################################################################################################
################################### Early Version ##################################################
##################################################################################################


# from app.utils.orchestrator import Orchestrator
# import redis
# from app.utils.response_processing import clean_response
# from app.utils.prompt_selector import prompt_selector 
# from app.models.chat_models import UserQuery, ChatResponse
# from app.models.instance_models import InstanceRequest
# from app.utils.instance_creation_utils.instance_data_cache import fetch_allowed_values

# import json
# from pydantic import BaseModel, Field, ValidationError
# from typing import List, Optional, Dict
# import re
# from langchain.chains import LLMChain
# from langchain.prompts import PromptTemplate
# # from langchain_community.llms import HuggingFacePipeline
# from langgraph.graph import Graph
# from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
# import torch
# import requests

# # Initialize the Orchestrator
# orchestrator = Orchestrator()

# # Redis client for conversation history
# redis_client = redis.Redis(host="localhost", port=6379, decode_responses=True)



# class WorkflowState:        
#     def __init__(self):
#         self.instance_data = {}
#         self.current_step = "start"
#         self.next_step = None
#         self.response = None

# class Instance_Creation:
#     def __init__(self, query: UserQuery):
#         self.redis_client = redis_client
#         self.llm = orchestrator.instance_creation_query_handler()
#         self.allowed_values = fetch_allowed_values(query.jwt_token)
#         self.query = query
#         self.jwt_token = query.jwt_token

#     def ask_for_instance_name(self, state):
#         state.response = "Please provide the instance name:"
#         state.current_step = "instance_name"
#         state.next_step = "location"
#         return state

#     def ask_for_location(self, state):
#         zones = [zone["zone"] for zone in self.allowed_values["allowed_zones"]]
#         state.response = "Please specify the location. Allowed options: " + ", ".join(zones)
#         try:
#             if state.response in zones:
#                 for zone in self.allowed_values["allowed_zones"]:
#                     if zone['zone'].lower() == state.response.lower():
#                         state.response =  zone['zone_code']
#                 state.current_step = "location"
#                 state.next_step = "prepackage_or_custom"
#         except:
#             state.response = "Please select a valid location. Allowed options: " + ", ".join([zone["name"] for zone in self.allowed_values["allowed_zones"]])
#             state.current_step = "location"
#             state.next_step = "location"
#         return state

#     def ask_for_prepackage_or_custom(self, state):
#         state.response = "Do you want a prepackage or custom instance? (Prepackage/Custom):"
#         state.current_step = "prepackage_or_custom"
#         return state

#     def ask_for_instance_type(self, state):
#         state.response = "Choose an instance type. Allowed options: " + ", ".join([f"{instance['name']} (Price: {instance['price']} {instance['periodicity']}, Memory: {instance['memmory_size']}, Storage: {instance['storage_size']}, vCPU: {instance['vcpu']})" for instance in self.allowed_values["instance_types"]])
#         try:
#             if state.response.lower() in [instance['name'].lower() for instance in self.allowed_values["instance_types"]]:
#                 state.current_step = "instance_type"
#                 state.next_step = "platform"
#         except:
#             state.response = "Please select a valid instance type. Allowed options: " + ", ".join([f"{instance['name']} (Price: {instance['price']} {instance['periodicity']}, Memory: {instance['memmory_size']}, Storage: {instance['storage_size']}, vCPU: {instance['vcpu']})" for instance in self.allowed_values["instance_types"]])
#             state.current_step = "instance_type"    
#             state.next_step = "instance_type"
#         return state

#     def ask_for_custom_instance_details(self, state):
#         state.response = "Please provide the memory size (in GB), storage size (in GB), and vCPU count (comma-separated):"
#         state.current_step = "custom_instance_details"
#         state.next_step = "platform"
#         return state

#     def ask_for_security_group(self, state):
#         state.response = "Please specify the security group:"
#         state.current_step = "security_group"
#         state.next_step = "platform"
#         return state

#     def ask_for_platform_os(self, state):
#         state.response = "Please specify the OS you want to install. Allowed options: " + ", ".join([f"{os_item['name']}" for os_item in self.allowed_values["allowed_packages"][-1]["os"]])
#         try:
#             if state.response.lower() in [os_item['name'].lower() for os_item in self.allowed_values["allowed_packages"][-1]["os"]]:
#                 state.current_step = "platform_os"
#                 state.next_step = "platform_os_version"
#         except:
#             state.response = "Please select a valid OS. Allowed options: " + ", ".join([f"{os_item['name']}" for os_item in self.allowed_values["allowed_packages"][-1]["os"]])
#             state.current_step = "platform_os"
#             state.next_step = "platform_os"
#         return state
    
#     def ask_for_platform_os_version(self, state):
#         state.response = "Please specify the version of the OS you want to install. Allowed options: " + ", ".join([f"{os_item['name']}-{', '.join(os_item['versions'])}" for os_item in self.allowed_values["allowed_packages"][-1]["os"]])
#         try:
#             if state.response.lower() in [os_item['versions'].lower() for os_item in self.allowed_values["allowed_packages"][-1]["os"]]:
#                 state.current_step = "platform_os_version"
#                 state.next_step = "ask_for_database"
#         except:
#             state.response = "Please select a valid OS version. Allowed options: " + ", ".join([f"{os_item['name']}-{', '.join(os_item['versions'])}" for os_item in self.allowed_values["allowed_packages"][-1]["os"]])
#             state.current_step = "platform_os_version"
#             state.next_step = "platform_os_version"
#         return state
    
    
    
    
    
    
    
    
    
    
#     # def ask_for_packages(self, state):
#     #     state.response = "Do you want to install any packages? (Yes/No). Allowed options: " + ", ".join([f"{pkg_item['name']}" for pkg_item in self.allowed_values["allowed_packages"][-1]["packages"]])
#     #     state.current_step = "ask_for_packages"
#     #     return state
    
    
#     def ask_for_database(self, state):
#         state.response = "Do you want to install a database?. Allowed options: " + ", ".join([f"{db_item['name']}" for db_item in self.allowed_values["allowed_packages"][-1]["databases"]])
#         if state.response.lower() not in ["no"]:
#             try:
#                 if state.response.lower() in [db_item['name'].lower() for db_item in self.allowed_values["allowed_packages"][-1]["databases"]]:
#                         state.current_step = "ask_for_database"
#                         state.next_step = "ask_for_database_version"
#             except:
#                 state.response = "Please select a valid Database. Allowed options: " + ", ".join([f"{db_item['name']}" for db_item in self.allowed_values["allowed_packages"][-1]["databases"]])
#                 state.current_step = "ask_for_database"
#                 state.next_step = "ask_for_database"
#         return state
    
#     def ask_for_database_version(self, state):
#         state.response = "Please specify the version of the Database you want to install. Allowed options: " + ", ".join([f"{db_item['name']}-{', '.join(db_item['versions'])}" for db_item in self.allowed_values["allowed_packages"][-1]["databases"]])
#         try:
#             if state.response.lower() in [os_item['versions'].lower() for os_item in self.allowed_values["allowed_packages"][-1]["databases"]]:
#                 state.current_step = "ask_for_database_version"
#                 state.next_step = "ask_for_cms"
#         except:
#             state.response = "Please select a valid Database version. Allowed options: " + ", ".join([f"{db_item['name']}-{', '.join(db_item['versions'])}" for db_item in self.allowed_values["allowed_packages"][-1]["databases"]])
#             state.current_step = "ask_for_database_version"
#             state.next_step = "ask_for_database_version"
#         return state
    
    
    
    
#     def ask_for_cms(self, state):
#         state.response = "Do you want to install a database?. Allowed options: " + ", ".join([f"{db_item['name']}" for db_item in self.allowed_values["allowed_packages"][-1]["cms"]])
#         if state.response.lower() not in ["no"]:
#             try:
#                 if state.response.lower() in [db_item['name'].lower() for db_item in self.allowed_values["allowed_packages"][-1]["cms"]]:
#                         state.current_step = "ask_for_cms"
#                         state.next_step = "ask_for_cms_version"
#             except:
#                 state.response = "Please select a valid Database. Allowed options: " + ", ".join([f"{db_item['name']}" for db_item in self.allowed_values["allowed_packages"][-1]["cms"]])
#                 state.current_step = "ask_for_cms"
#                 state.next_step = "ask_for_cms"
#         return state
    
#     def ask_for_cms_version(self, state):
#         state.response = "Please specify the version of the Database you want to install. Allowed options: " + ", ".join([f"{db_item['name']}-{', '.join(db_item['versions'])}" for db_item in self.allowed_values["allowed_packages"][-1]["cms"]])
#         try:
#             if state.response.lower() in [os_item['versions'].lower() for os_item in self.allowed_values["allowed_packages"][-1]["cms"]]:
#                 state.current_step = "ask_for_cms_version"
#                 state.next_step = "ask_for_langauge"
#         except:
#             state.response = "Please select a valid Database version. Allowed options: " + ", ".join([f"{db_item['name']}-{', '.join(db_item['versions'])}" for db_item in self.allowed_values["allowed_packages"][-1]["cms"]])
#             state.current_step = "ask_for_cms_version"
#             state.next_step = "ask_for_cms_version"
#         return state
    
    
    


#     def ask_for_langauge(self, state):
#         state.response = "Do you want to install a database?. Allowed options: " + ", ".join([f"{db_item['name']}" for db_item in self.allowed_values["allowed_packages"][-1]["programming_languages"]])
#         if state.response.lower() not in ["no"]:
#             try:
#                 if state.response.lower() in [db_item['name'].lower() for db_item in self.allowed_values["allowed_packages"][-1]["programming_languages"]]:
#                         state.current_step = "ask_for_langauge"
#                         state.next_step = "ask_for_langauge_version"
#             except:
#                 state.response = "Please select a valid Database. Allowed options: " + ", ".join([f"{db_item['name']}" for db_item in self.allowed_values["allowed_packages"][-1]["programming_languages"]])
#                 state.current_step = "ask_for_langauge"
#                 state.next_step = "ask_for_langauge"
#         return state
    
#     def ask_for_langauge_version(self, state):
#         state.response = "Please specify the version of the Database you want to install. Allowed options: " + ", ".join([f"{db_item['name']}-{', '.join(db_item['versions'])}" for db_item in self.allowed_values["allowed_packages"][-1]["databases"]])
#         try:
#             if state.response.lower() in [os_item['versions'].lower() for os_item in self.allowed_values["allowed_packages"][-1]["programming_languages"]]:
#                 state.current_step = "ask_for_langauge_version"
#                 state.next_step = "instance_count"
#         except:
#             state.response = "Please select a valid Database version. Allowed options: " + ", ".join([f"{db_item['name']}-{', '.join(db_item['versions'])}" for db_item in self.allowed_values["allowed_packages"][-1]["programming_languages"]])
#             state.current_step = "ask_for_langauge_version"
#             state.next_step = "ask_for_langauge_version"
#         return state
    
    
    
#     def instance_count(self, state):
#         state.response = "Please specify the number of instances you want to create."
#         state.current_step = "instance_count"
#         state.next_step = "finalize"
#         return state   

    
    
    
    
    
    
    
    
    
    

#     # def ask_for_packages(self, state):
#     #     # state.response = "Please specify the packages. Allowed options: " + json.dumps(self.allowed_values["allowed_packages"], indent=2)
#     #     state.response = "Please specify the packages. Allowed options: " + ", ".join([ f"{category.capitalize()}: " + ", ".join([f"{pkg['name']} (Versions: {', '.join(pkg['versions'])})" for pkg in category_list]) for category, category_list in self.allowed_values["allowed_packages"][0].items() if category != "os" ])
#     #     state.current_step = "packages"
#     #     state.next_step = "finalize"
#     #     return state

#     def finalize_state(self, state):
#         state.response = "Instance creation details collected successfully."
#         state.current_step = "finalize"
#         return state

#     # def workflow_builder(self):
#     #     workflow = Graph()

#     #     # Add nodes to the graph
#     #     workflow.add_node("ask_for_instance_name", self.ask_for_instance_name)
#     #     workflow.add_node("ask_for_location", self.ask_for_location)
#     #     workflow.add_node("ask_for_prepackage_or_custom", self.ask_for_prepackage_or_custom)
#     #     workflow.add_node("ask_for_instance_type", self.ask_for_instance_type)
#     #     workflow.add_node("ask_for_custom_instance_details", self.ask_for_custom_instance_details)
#     #     workflow.add_node("ask_for_security_group", self.ask_for_security_group)
#     #     workflow.add_node("ask_for_platform", self.ask_for_platform)
#     #     workflow.add_node("ask_for_packages", self.ask_for_packages)
#     #     workflow.add_node("finalize_state", self.finalize_state)

#     #     # Define the edges
#     #     workflow.add_edge("ask_for_instance_name", "ask_for_location")
#     #     workflow.add_edge("ask_for_location", "ask_for_prepackage_or_custom")
#     #     workflow.add_conditional_edges(
#     #         "ask_for_prepackage_or_custom",
#     #         lambda state: "ask_for_instance_type" if state.instance_data.get("prepackage_or_custom") == "Prepackage" else "ask_for_custom_instance_details"
#     #     )
#     #     # workflow.add_edge("ask_for_instance_type", "ask_for_security_group")
#     #     # workflow.add_edge("ask_for_custom_instance_details", "ask_for_security_group")
#     #     # workflow.add_edge("ask_for_security_group", "ask_for_platform")
#     #     workflow.add_edge("ask_for_instance_type", "ask_for_platform")
#     #     workflow.add_edge("ask_for_custom_instance_details", "ask_for_platform")
#     #     workflow.add_edge("ask_for_platform", "ask_for_packages")
#     #     workflow.add_edge("ask_for_packages", "finalize_state")

#     #     # Set the entry point
#     #     workflow.set_entry_point("ask_for_instance_name")

#     #     # Compile the graph
#     #     app = workflow.compile()
#     #     return app

#     # def run_workflow(self, session_id: str, user_input: str) -> Dict:
#     #     state = WorkflowState()
#     #     state_key = f"workflow_state:{session_id}"
#     #     data_key = f"instance_data:{session_id}"

#     #     # Load the current state and data from Redis
#     #     current_state = self.redis_client.get(state_key)
#     #     instance_data = self.redis_client.get(data_key)

#     #     if instance_data:
#     #         state.instance_data = json.loads(instance_data)
#     #     if current_state:
#     #         state.current_step = current_state

#     #     # Run the workflow
#     #     app = self.workflow_builder()
#     #     app.invoke(state)

#     #     # Save the updated state and data to Redis
#     #     self.redis_client.set(state_key, state.current_step)
#     #     self.redis_client.set(data_key, json.dumps(state.instance_data))

#     #     return {"response": state.response, "data": state.instance_data}
    
#     def process_input(self, state: WorkflowState, user_input: str):
#         """Process user input based on current step"""
#         if state.current_step == "instance_name":
#             state.instance_data["instance_name"] = user_input
#         elif state.current_step == "location":
#             state.instance_data["location"] = user_input
#         elif state.current_step == "prepackage_or_custom":
#             state.instance_data["type"] = user_input.lower()
#         elif state.current_step == "instance_type":
#             state.instance_data["instance_type"] = user_input
#         elif state.current_step == "custom_instance_details":
#             # Add validation for custom details
#             try:
#                 memory, storage, vcpu = map(float, user_input.split(','))
#                 state.instance_data.update({
#                     "memmory_size": memory,
#                     "storage_size": storage,
#                     "vcpu": vcpu
#                 })
#             except:
#                 state.response = "Invalid format. Please try again."
#                 state.next_step = "custom_instance_details"
#                 return state
#         elif state.current_step == "platform_os":
#             state.instance_data["platform"] = {"name": user_input}
#         elif state.current_step == "platform_os_version":
#             state.instance_data["platform"]  = {"name": state.instance_data["platform"]["name"], "version": user_input}
            
#         elif state.current_step == "ask_for_packages":
#             state.instance_data["package_type"] = user_input.lower()
            
#         elif state.current_step == "ask_for_database":
#             if user_input.lower() not in ["no"]:
#                 state.instance_data["packages"]["databases"] = {"name": user_input}
#         elif state.current_step == "ask_for_database_version":
#             state.instance_data["packages"]["databases"]  = {"name": state.instance_data["packages"]["databases"]["name"], "version": user_input}
            
#         elif state.current_step == "ask_for_cms":
#             if user_input.lower() not in ["no"]:
#                 state.instance_data["packages"]["cms"] = {"name": user_input}
#         elif state.current_step == "ask_for_cms_version":
#             state.instance_data["packages"]["cms"]  = {"name": state.instance_data["packages"]["cms"]["name"], "version": user_input}
        
#         elif state.current_step == "ask_for_language":
#             if user_input.lower() not in ["no"]:
#                 state.instance_data["packages"]["programming_languages"] = {"name": user_input}
#         elif state.current_step == "ask_for_language_version":
#             state.instance_data["packages"]["programming_languages"]  = {"name": state.instance_data["packages"]["programming_languages"]["name"], "version": user_input}
            
#         elif state.current_step == "instance_count":
#             state.instance_data["instance_count"] = user_input    
            
        
#         # elif state.current_step == "packages":
#         #     state.instance_data["packages"] = user_input.split(',')
        
#         return state

#     def run_workflow(self, session_id: str, user_input: str) -> Dict:
#         state = WorkflowState()
#         state_key = f"workflow_state:{session_id}"
#         data_key = f"instance_data:{session_id}"

#         # Load existing state from Redis
#         if self.redis_client.exists(state_key):
#             state.current_step = self.redis_client.get(state_key)
#             state.instance_data = json.loads(self.redis_client.get(data_key) or "{}")

#         # Process user input if provided
#         if user_input and state.current_step != "start":
#             print("#########################")
#             print("State: ", state)
#             print("#########################")
#             state = self.process_input(state, user_input)

#         # Determine next step
#         transitions = {
#             "start": self.ask_for_instance_name,
#             "instance_name": self.ask_for_location,
#             "location": self.ask_for_prepackage_or_custom,
#             "prepackage_or_custom": lambda s: (
#                 self.ask_for_instance_type(s) 
#                 if s.instance_data.get("type") == "prepackage" 
#                 else self.ask_for_custom_instance_details(s)
#             ),
#             "instance_type": self.ask_for_database,
#             "custom_instance_details": self.ask_for_database,
            
            
#             "ask_for_database": lambda s: (
#                 self.ask_for_language(s) 
#                 if s.instance_data.get("package")['database'] is None 
#                 else self.ask_for_database_version(s)
#             ),
            
#             "ask_for_language": lambda s: (
#                 self.ask_for_cms(s) 
#                 if s.instance_data.get("package")['programming_languages'] is None 
#                 else self.ask_for_language_version(s)
#             ),

#             "ask_for_cms": lambda s: (
#                 self.instance_count(s) 
#                 if s.instance_data.get("package")['cms'] is None 
#                 else self.ask_for_cms_version(s)
#             ),
            
#             "ask_for_cms_version": self.instance_count,
            
#             # "platform": self.ask_for_packages,
#             "instance_count": self.finalize_state
#         }

#         # Execute current step
#         if state.current_step in transitions:
#             state = transitions[state.current_step](state)

#         # Save state
#         self.redis_client.set(state_key, state.current_step)
#         self.redis_client.set(data_key, json.dumps(state.instance_data))
#         print("#########################")
#         print("state.instance_data: ", state.instance_data)
#         print("#########################")

#         return {"response": state.response, "data": state.instance_data}


#     def trigger_instance_creation_api(self, instance_data: Dict) -> str:
#         headers = {
#             "Authorization": f"Bearer {self.jwt_token}",
#             "Content-Type": "application/json"
#         }

#         # Replace with your API endpoint
#         api_url = "https://enterprisepythonbackend.mizzle.io/api/instance/create-instance"
#         response = requests.post(api_url, json=instance_data, headers=headers)
#         if response.status_code == 200:
#             return "Instance created successfully."
#         else:
#             return f"Failed to create instance. Error: {response.text}"

#     def run_chat(self, query: UserQuery):
#         # print("#########################")
#         # print(self.allowed_values)
#         # print("#########################")
#         session_id = query.session_id
#         user_input = query.text
#         result = self.run_workflow(session_id, user_input)
#         print(result["response"])
#         if result["data"]:
#             print("Collected data:", result["data"])
#         if result["response"] == "Instance creation details collected successfully.":
#             api_response = self.trigger_instance_creation_api(result["data"])
#             print(api_response)
#             return {"response": api_response}
#         return {"response": result["response"]}
    
    
            



    






##################################################################################################
################################### Early Version ##################################################
##################################################################################################











# from app.utils.orchestrator import Orchestrator
# import redis
# from app.utils.response_processing import clean_response
# from app.utils.prompt_selector import prompt_selector
# from app.models.chat_models import UserQuery, ChatResponse
# from app.models.instance_models import InstanceRequest
# from app.utils.instance_creation_utils.instance_data_cache import fetch_allowed_values
# import json 
# from pydantic import BaseModel, Field, ValidationError
# from typing import List, Optional, Dict
# import re
# from langchain.chains import LLMChain
# from langchain.prompts import PromptTemplate
# from langgraph.graph import Graph


# # Initialize the Orchestrator
# orchestrator = Orchestrator()

# # Redis client for conversation history
# redis_client = redis.Redis(host="localhost", port=6379, decode_responses=True)

# class Instance_Creation:
#     def __init__(self):
#         self.redis_client = redis_client
#         self.llm = orchestrator.instance_creation_query_handler()
        

#     def instance_creation(self, query: UserQuery) -> str:
#         self.query = query
#         self.allowed_values = fetch_allowed_values(query.jwt_token)
#         session_id = query.session_id   
#         history_key = f"conversation:{session_id}"
#         conversation_history = self.redis_client.get(history_key)

#         # Parse history or initialize empty list
#         if conversation_history:
#             conversation_history = json.loads(conversation_history)
#         else:
#             conversation_history = []

#         # Append the current user query to the history
#         conversation_history.append({"role": "user", "content": query.text})

#         # Initialize the InstanceRequest model with partial data
#         instance_data = self._extract_instance_data(conversation_history)

#         # Check if all required fields are filled
#         missing_fields = self._get_missing_fields(instance_data)
#         if missing_fields:
#             # Use LangGraph to handle the workflow for missing fields
#             response = self._handle_missing_fields(missing_fields, instance_data)
#         else:
#             # All fields are filled, validate the final data
#             try:
#                 instance_request = InstanceRequest(**instance_data)
#                 response = f"Instance creation request received with the following details:\n{instance_request.json(indent=2)}"
#             except ValidationError as e:
#                 # Handle validation errors
#                 error_message = f"Validation error: {e.errors()[0]['msg']}. Please correct the input."
#                 response = error_message

#         # Append the assistant's response to the conversation history
#         conversation_history.append({"role": "assistant", "content": response})

#         # Save updated history back to Redis
#         self.redis_client.set(history_key, json.dumps(conversation_history))

#         # Return the cleaned response
#         cleaned_response = clean_response(response, query.text)
#         return cleaned_response

#     def _extract_instance_data(self, conversation_history: List[Dict]) -> Dict:
#         """
#         Extract instance data from the conversation history using allowed values.
#         """
#         instance_data = {}
#         for msg in conversation_history:
#             if msg["role"] == "user":
#                 user_input = msg["content"].lower()

#                 # Extract instance_count
#                 if "instance count" in user_input or "number of instances" in user_input:
#                     try:
#                         instance_data["instance_count"] = int(
#                             "".join(filter(str.isdigit, user_input))
#                         )
#                     except ValueError:
#                         pass  # Skip invalid input

#                 # Extract server_zone_code
#                 if "server zone" in user_input or "zone code" in user_input:
#                     for zone in self.allowed_values["allowed_zones"]:
#                         if zone["name"].lower() in user_input:
#                             instance_data["server_zone_code"] = zone["zone_code"]
#                             break

#                 # Extract public_key
#                 if "public key" in user_input or "ssh key" in user_input:
#                     # Assume the user provides the key directly
#                     instance_data["public_key"] = user_input.strip()

#                 # Extract instance_name
#                 if "instance name" in user_input or "name of the instance" in user_input:
#                     # Extract the name after the keyword
#                     instance_data["instance_name"] = user_input.split("name")[-1].strip()

#                 # Extract security_group
#                 if "security group" in user_input:
#                     for group in self.allowed_values["allowed_security_groups"]:
#                         if group.lower() in user_input:
#                             instance_data["security_group"] = group
#                             break

#                 # Extract platform
#                 if "platform" in user_input:
#                     for platform in self.allowed_values["allowed_platforms"]:
#                         if (
#                             platform["name"].lower() in user_input
#                             and platform["version"].lower() in user_input
#                         ):
#                             instance_data["platform"] = platform
#                             break

#                 # Extract packages
#                 if "packages" in user_input or "software" in user_input:
#                     packages = {}
#                     for category in self.allowed_values["allowed_packages"]:
#                         category_name = category["category"]
#                         category_packages = []
#                         for item in category["items"]:
#                             if item["name"].lower() in user_input:
#                                 # Extract version if provided
#                                 version = None
#                                 version_pattern = rf"{item['name']}\s*(\d+\.\d+(\.\d+)?)"
#                                 match = re.search(version_pattern, user_input)
#                                 if match:
#                                     version = match.group(1)
#                                 category_packages.append({"name": item["name"], "version": version})
#                         if category_packages:
#                             packages[category_name] = category_packages
#                     if packages:
#                         instance_data["packages"] = packages

#         return instance_data

#     def _get_missing_fields(self, instance_data: Dict) -> List[str]:
#         """
#         Determine which fields are still missing in the instance_data.
#         """
#         missing_fields = []
#         for field_name in InstanceRequest.model_fields:
#             if field_name not in instance_data:
#                 missing_fields.append(field_name)
#         return missing_fields

#     def _handle_missing_fields(self, missing_fields: List[str], instance_data: Dict) -> str:
#         """
#         Use LangGraph to handle the workflow for missing fields with suggestions.
#         """
#         # Define the state for LangGraph
#         class WorkflowState:
#             def __init__(self):
#                 self.missing_fields = missing_fields
#                 self.instance_data = instance_data
#                 self.current_field = None
#                 self.response = None

#         # Define the nodes for the LangGraph
#         def ask_for_input(state):
#             state.current_field = state.missing_fields.pop(0)
#             field_info = InstanceRequest.model_fields[state.current_field]
#             allowed_options = self._get_allowed_options(state.current_field)
#             if allowed_options:
#                 prompt = f"Please provide the value for '{state.current_field}' ({field_info.description}). Allowed options: {', '.join(allowed_options)}: "
#             else:
#                 prompt = f"Please provide the value for '{state.current_field}' ({field_info.description}): "
#             state.response = prompt
#             return state

#         def validate_input(state):
#             user_input = input(state.response).strip()
#             if self._validate_field(state.current_field, user_input):
#                 state.instance_data[state.current_field] = user_input
#                 state.response = f"Value for '{state.current_field}' accepted."
#             else:
#                 state.response = f"Invalid value for '{state.current_field}'. Please try again."
#                 state.missing_fields.append(state.current_field)
#             return state

#         def finalize_state(state):
#             state.response = "All required fields have been filled."
#             return state

#         # Build the LangGraph
#         workflow = Graph()

#         # Add nodes to the graph
#         workflow.add_node("ask_for_input", ask_for_input)
#         workflow.add_node("validate_input", validate_input)
#         workflow.add_node("finalize_state", finalize_state)

#         # Define the edges
#         workflow.add_edge("ask_for_input", "validate_input")
#         workflow.add_edge("validate_input", "finalize_state")

#         # Set the entry point
#         workflow.set_entry_point("ask_for_input")

#         # Compile the graph
#         app = workflow.compile()

#         # Run the workflow
#         state = WorkflowState()
#         while state.missing_fields:
#             app.invoke(state)

#         return state.response

#     def _get_allowed_options(self, field_name: str) -> List[str]:
#         """
#         Get allowed options for a specific field based on allowed_values.
#         """
#         if field_name == "server_zone_code":
#             return [zone["zone_code"] for zone in self.allowed_values["allowed_zones"]]
#         elif field_name == "platform":
#             return [f"{platform['name']} {platform['version']}" for platform in self.allowed_values["allowed_platforms"]]
#         elif field_name == "security_group":
#             return self.allowed_values["allowed_security_groups"]
#         # Add more fields as needed
#         return []

#     def _validate_field(self, field_name: str, value: str) -> bool:
#         """
#         Validate a specific field based on allowed values.
#         """
#         if field_name == "server_zone_code":
#             return value in [zone["zone_code"] for zone in self.allowed_values["allowed_zones"]]
#         elif field_name == "platform":
#             return value in [f"{platform['name']} {platform['version']}" for platform in self.allowed_values["allowed_platforms"]]
#         elif field_name == "security_group":
#             return value in self.allowed_values["allowed_security_groups"]
#         # Add more validation rules as needed
#         return True








































# from app.utils.orchestrator import Orchestrator
# import redis
# from app.utils.response_processing import clean_response
# from app.utils.prompt_selector import prompt_selector
# from app.models.chat_models import UserQuery, ChatResponse
# from app.models.instance_models import InstanceRequest
# from app.utils.instance_creation_utils.instance_data_cache import fetch_allowed_values
# import json
# from pydantic import BaseModel, Field, ValidationError
# from typing import List, Optional, Dict
# import re
# from langchain.chains import LLMChain
# from langchain.prompts import PromptTemplate
# from langchain.llms import HuggingFacePipeline
# from langgraph.graph import Graph





# orchestrator = Orchestrator()



# # redis_client = redis.Redis(host="localhost", port=6379, decode_responses=True)


# class Instance_Creation:
    
#     def __init__(self, query: UserQuery):
#         # Initialize Redis client
#         self.redis_client = redis.Redis(host="localhost", port=6379, decode_responses=True)
#         self.allowed_values = self._load_allowed_values()
#         self.llm = orchestrator.instance_creation_query_handler()
#         self.allowed_values = fetch_allowed_values(self.query.jwt_token)

#     def instance_creation(self, query: UserQuery) -> str:
#         session_id = query.session_id
#         history_key = f"conversation:{session_id}"
#         conversation_history = self.redis_client.get(history_key)

#         # Parse history or initialize empty list
#         if conversation_history:
#             conversation_history = json.loads(conversation_history)
#         else:
#             conversation_history = []

#         # Append the current user query to the history
#         conversation_history.append({"role": "user", "content": query.text})
        
        
        
        
#         print("#"*40)
#         print(f'conversation_history ----- {conversation_history}')
#         print("#"*40)
#         # Initialize the InstanceRequest model with partial data
#         instance_data = self._extract_instance_data(conversation_history)
#         print("#"*40)
#         print(f'instance_data ----- {instance_data}')
#         print("#"*40)

#         # Check if all required fields are filled
#         missing_fields = self._get_missing_fields(instance_data)
#         print("#"*40)
#         print(f'missing_fields ----- {missing_fields}')
#         print("#"*40)
#         if missing_fields:
#             # Prompt the user for the next missing field
#             next_field = missing_fields[0]
#             print(f'next_field ----- {next_field}')
#             field_info = InstanceRequest.model_fields[next_field]
#             print(f'field_info ----- {field_info}')
#             prompt = f"Please provide the value for '{next_field}' ({field_info.description}): "
#             response = prompt
#             print(f'response ----- {response}')
#         else:
#             # All fields are filled, validate the final data
#             try:
#                 instance_request = InstanceRequest(**instance_data)
#                 response = f"Instance creation request received with the following details:\n{instance_request.json(indent=2)}"
#                 print(f'response ----- {response}')
#             except ValidationError as e:
#                 # Handle validation errors
#                 error_message = f"Validation error: {e.errors()[0]['msg']}. Please correct the input."
#                 response = error_message

#         # Append the assistant's response to the conversation history
#         conversation_history.append({"role": "assistant", "content": response})

#         # Save updated history back to Redis
#         self.redis_client.set(history_key, json.dumps(conversation_history))

#         # Return the cleaned response
#         print(response)
#         cleaned_response = clean_response(response, query.text)
#         return response

#     # def _extract_instance_data(self, conversation_history: List[Dict]) -> Dict:
#         """
#         Extract instance data from the conversation history.
#             """
#         # instance_data = {}
#         # for msg in conversation_history:
#         #     if msg["role"] == "user":
#         #         # Parse user input and update instance_data (this is a simplified example)
#         #         # In a real implementation, you would use NLP or structured parsing to extract field values
#         #         pass  # Add logic to extract field values from user input
        
        
    
#     def _extract_instance_data(self, conversation_history: List[Dict]) -> Dict:
#         """
#         Extract instance data from the conversation history using allowed values.
#         """
#         instance_data = {}
#         for msg in conversation_history:
#             if msg["role"] == "user":
#                 user_input = msg["content"].lower()

#                 # Extract instance_count
#                 if "instance count" in user_input or "number of instances" in user_input:
#                     try:
#                         instance_data["instance_count"] = int(
#                             "".join(filter(str.isdigit, user_input))
#                         )
#                     except ValueError:
#                         pass  # Skip invalid input

#                 # Extract server_zone_code
#                 if "server zone" in user_input or "zone code" in user_input:
#                     for zone in allowed_values["allowed_zones"]:
#                         if zone.lower() in user_input:
#                             instance_data["server_zone_code"] = zone
#                             break

#                 # Extract public_key
#                 if "public key" in user_input or "ssh key" in user_input:
#                     # Assume the user provides the key directly
#                     instance_data["public_key"] = user_input.strip()

#                 # Extract instance_name
#                 if "instance name" in user_input or "name of the instance" in user_input:
#                     # Extract the name after the keyword
#                     instance_data["instance_name"] = user_input.split("name")[-1].strip()

#                 # Extract security_group
#                 if "security group" in user_input:
#                     for group in allowed_values["allowed_security_groups"]:
#                         if group.lower() in user_input:
#                             instance_data["security_group"] = group
#                             break
                
#                 if "custom security group" in user_input:
#                     for group in allowed_values["allowed_security_groups"]:
#                         if group.lower() in user_input:
#                             instance_data["custom_security_group"] = group
#                             break

#                 # Extract platform
#                 if "platform" in user_input:
#                     for platform in allowed_values["allowed_platforms"]:
#                         if (
#                             platform["name"].lower() in user_input
#                             and platform["version"].lower() in user_input
#                         ):
#                             instance_data["platform"] = platform
#                             break

#                 # Extract packages
#                 if "packages" in user_input or "software" in user_input:
#                     packages = {}
#                     for category in allowed_values["allowed_packages"]:
#                         category_name = category["category"]
#                         category_packages = []
#                         for item in category["items"]:
#                             if item["name"].lower() in user_input:
#                                 # Extract version if provided
#                                 version = None
#                                 version_pattern = rf"{item['name']}\s*(\d+\.\d+(\.\d+)?)"
#                                 match = re.search(version_pattern, user_input)
#                                 if match:
#                                     version = match.group(1)
#                                 category_packages.append({"name": item["name"], "version": version})
#                         if category_packages:
#                             packages[category_name] = category_packages
#                     if packages:
#                         instance_data["packages"] = packages

#         return instance_data

#     def _get_missing_fields(self, instance_data: Dict) -> List[str]:
#         """
#         Determine which fields are still missing in the instance_data.
#         """
#         missing_fields = []
#         for field_name in InstanceRequest.model_fields:
#             if field_name not in instance_data:
#                 missing_fields.append(field_name)
#         return missing_fields

    
#     # def instance_creation(self, query : UserQuery) -> str: 
#     #         session_id = query.session_id
#     #         history_key = f"conversation:{session_id}"
#     #         conversation_history = redis_client.get(history_key)

#     #         # Parse history or initialize empty list
#     #         if conversation_history:
#     #             conversation_history = json.loads(conversation_history)
#     #         else:
#     #             conversation_history = []

#     #         # Append the current user query to the history
#     #         conversation_history.append({"role": "user", "content": query.text})

#     #         # Pass conversation history to the orchestrator for better context
#     #         model_input = "\n".join(
#     #             [f"{msg['role']}: {msg['content']}" for msg in conversation_history]
#     #         )

#     #         system_prompt = prompt_selector('instance_creation')
#     #         system_prompt = system_prompt + InstanceRequest.model_fields
#     #         print("#"*40)
#     #         print(system_prompt)
            
#     """
#     Added the code below
#     """
            
#             # data = {}
#             # model_fields = InstanceRequest.model_fields

#             # print("Welcome! Let's collect your system configuration.")
#             # print("You can provide all details at once or one by one. What would you prefer?")
#             # print("1. Provide all details at once")
#             # print("2. Provide details one by one")
#             # choice = input("Enter your choice (1 or 2): ").strip()

#             # if choice == "1":
#             #     # Collect all details at once
#             #     print("Please provide all details in the following format (key: value):")
#             #     for field_name, field in model_fields.items():
#             #         value = input(f"{field.description}: ").strip()
#             #         data[field_name] = value

#             #     try:
#             #         # Validate the data
#             #         user_data = UserData(**data)
#             #         print("Validation successful! Here's your configuration:")
#             #         return user_data.json(indent=2)
#             #     except ValidationError as e:
#             #         print(f"Validation failed: {e}")
#             #         return None

#             # elif choice == "2":
#             #     # Collect details one by one
#             #     for field_name, field in model_fields.items():
#             #         while True:
#             #             value = input(f"{field.description}: ").strip()
#             #             if not value and field.default is None and field.required:
#             #                 print("This field is required. Please provide a value.")
#             #                 continue
#             #             data[field_name] = value
#             #             break

#             #     try:
#             #         # Validate the data
#             #         user_data = UserData(**data)
#             #         print("Validation successful! Here's your configuration:")
#             #         return user_data.json(indent=2)
#             #     except ValidationError as e:
#             #         print(f"Validation failed: {e}")
#             #         return None

#             # else:
#             #     print("Invalid choice. Please try again.")
#             #     return None
        
#     """
#     End
#     """
            
            
            
            
#             # response = orchestrator.handle_query(model_input, system_prompt)
#             # print("#"*40)
#             # print(response)

#             # # Append the model's response to the history
#             # conversation_history.append({"role": "assistant", "content": response})

#             # # Save updated history back to Redis
#             # redis_client.set(history_key, json.dumps(conversation_history))
            

#             # # Return the cleaned response
#             # cleaned_response = clean_response(response, query.text,)
#             # return cleaned_response