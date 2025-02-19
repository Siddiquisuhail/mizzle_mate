from fuzzywuzzy import process
import redis
import json
import re
import requests
from app.models.chat_models import UserQuery
from app.agents.instance_creation.utils.instance_data_cache import fetch_allowed_values
from log.logging_config import logger
from app.utils.response_processing import clean_response
from app.utils.orchestrator import Orchestrator
from app.utils.prompt_selector import prompt_selector
from typing import Dict, List, Optional




orchestrator = Orchestrator()

# Redis client initialization
redis_client = redis.Redis(host="localhost", port=6379, decode_responses=True)

# Hardcoded security group
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
        self.instance_data = {"packages": {'cms': [], 'databases': [], 'programming_languages': []}}
        self.current_step = "start"
        self.next_step = None
        self.response = None
        self.retry_count = 0

class LLMEnhancedWorkflow:
    def __init__(self, query: UserQuery):
        self.redis_client = redis_client
        self.allowed_values = fetch_allowed_values(query.jwt_token)
        self.query = query
        self.jwt_token = query.jwt_token
        # self.llm_model = llm_model
        self.validation_retries = 3
        print("*"*40)
        print("self.allowed_values: ", self.allowed_values)
        print("*"*40)

    def generate_step_prompt(self, state: WorkflowState) -> str:
        print("*"*40)
        print("state.current_step: ", state.current_step)
        print("state.instance_data: ", state.instance_data)
        
        print("*"*40)
        step_prompts = {
            "start": "Let's begin creating your instance! First, please choose a project.",
             "project": (
                "The user needs to choose a project. Available options: {options}.\n"
                "Extract the project name from this response. Return JSON with 'project' field or 'error' if unclear.\n"
                "For example if the user wants to create a project called 'test', you will return: \n"
                "{'project': 'test'}"
            ),
            "instance_name": (
                "Extract the instance name from this message. "
                "Return JSON with 'instance_name' field. Names should be 3-64 alphanumeric chars.\n"
                "For example if the user wants to create a instance called 'test', you will return: \n"
                "{'instance_name': 'test'}"
            ),
            "location": (
                "User needs to select a zone. Available options: {options}.\n"
                "Extract the zone name. Return JSON with 'location' field or 'error'.\n"
                "For example if the user wants to create a instance in the zone called 'test', you will return: \n"
                "{'location': 'test'}"
            ),
            "prepackage_or_custom": (
                "User needs to if he wants to use a preconfigured configuration or create a custom instance.\n"
                "Return JSON with 'type' field as 'prepackage_or_custom' or 'custom' or 'error'.\n"
                "For example if the user wants to create a custom instance, you will return: \n"
                "{'type': 'custom'}"
            ),
            "prepackage": (
                "User needs to select a preconfigured configuration. Available options: {options}.\n"
                "Extract the preconfiguration 'name'. Return JSON with 'instance_name' field or 'error'.\n"
                "For example if the user wants to create a instance type called 'test', you will return: \n"
                "{'instance_name': 'test'}"
            ),
            "ram": (
                "User needs to select how much ram in GB does he need.\n"
                "Extract the ram size in GB. Return JSON with 'memmory_size' field or 'error'.\n"
                "For example if the user wants to create a instance with 1GB of ram, you will return: \n"
                "{'memmory_size': '1'}"
            ),
            "storage": (
                "User needs to select how much storage in GB does he need.\n"
                "Extract the storage size in GB. Return JSON with 'storage_size' field or 'error'.\n"
                "For example if the user wants to create a instance with 1GB of storage, you will return: \n"
                "{'storage_size': '1'}"
            ),
            "vcpu": (
                "User needs to select how much vcpu cores does he need.\n"
                "Extract the cpu cores. Return JSON with 'vcpu' field or 'error'.\n"
                "For example if the user wants to create a instance with 1 vcpu, you will return: \n"
                "{'vcpu': '1'}"
            ),
            "platform_os": (
                "User needs to select which OS he wants to install on the instance. Available options: {options}.\n"
                "Extract the zone name. Return JSON with 'platform_os' field or 'error'.\n"
                "For example if the user wants to create a instance with the OS called 'test', you will return: \n"
                "{'platform_os': 'test'}"
            ),
            "platform_os_version": (
                "User needs to select a OS version. Available options: {options}.\n"
                "Extract the OS Version name. Return JSON with 'platform_os_version' field or 'error'.\n"
                "For example if the user wants to create a instance with the OS version called 'test', you will return: \n"
                "{'platform_os_version': 'test'}"
            ),
            "platform_db": (
                "User needs to select if he wants to install a database on the instance.\n "
                "If he wants to install, then the available options are. Available options: {options}.\n"
                "Extract the either the database name or return None if he doesn't want to install.\n"
                "Return JSON with 'platform_db' field or 'error' or 'None'\n"
                "For example if the user wants to create a instance with the database called 'test', you will return: \n"
                "{'platform_db': 'test'}"
            ),
            "platform_db_version": (
                "User needs to select a Database Version. Available options: {options}.\n"
                "Extract the Database Version name. Return JSON with 'platform_db_version' field or 'error'.\n"
                "For example if the user wants to create a instance with the database version called 'test', you will return: \n"
                "{'platform_db_version': 'test'}"
            ),
            
            "platform_cms": (
                "User needs to select if he wants to install a Content Management System (CMS) on the instance.\n "
                "If he wants to install, then the available options are. Available options: {options}.\n"
                "Extract the either the CMS name or return None if he doesn't want to install.\n"
                "Return JSON with 'platform_cms' field or 'error' or 'None'\n"
                "For example if the user wants to create a instance with the CMS called 'test', you will return: \n"
                "{'platform_cms': 'test'}"
            ),
            "platform_cms_version": (
                "User needs to select a CMS Version. Available options: {options}.\n"
                "Extract the CMS Version name. Return JSON with 'platform_cms_version' field or 'error'.\n"
                "For example if the user wants to create a instance with the CMS version called 'test', you will return: \n"
                "{'platform_cms_version': 'test'}"
            ),
            
            "platform_language": (
                "User needs to select if he wants to install a language on the instance.\n "
                "If he wants to install, then the available options are. Available options: {options}.\n"
                "Extract the either the language name or return None if he doesn't want to install.\n"
                "Return JSON with 'platform_language' field or 'error' or 'None'\n"
                "For example if the user wants to create a instance with the language called 'test', you will return: \n"
                "{'platform_language': 'test'}"
            ),
            
            "platform_language_version": (
                "User needs to select a language Version. Available options: {options}.\n"
                "Extract the language Version name. Return JSON with 'platform_language_version' field or 'error'.\n"
                "For example if the user wants to create a instance with the language version called 'test', you will return: \n"
                "{'platform_language_version': 'test'}"
            ),
            
            
            "public_key": (
                "User needs to select an existing keypair or create a new one.\n"
                "Extract either an existing key name, or the name of the new key.\n"
                "Return JSON with 'public_key' field as the name and 'new_key' field as True if he wants a new key or False if he wants an existing key.\n"
                "For example if the user wants to create a instance with the existing key called 'test', you will return: \n"
                "{'public_key': 'test', 'new_key': False}"
                        #    "If he wants an existing key then return 'new_key' field as False and 'public_key' field as the name"
            ),
            "instance_count": (
                "User needs to specify the number of instances. \n"
                "Return JSON with 'instance_count' field or 'error'\n"
                "For example if the user wants to create 1 instance, you will return: \n"
                "{'instance_count': '1'}"
                               ),
            "validation": (
                "User needs to confirm the configuration details before proceeding.\n"
                "Return JSON with 'confirmation' field as True if user confirms or return False\n"
                "For example if the user confirms the configuration, you will return: \n"
                "{'confirmation': True}"
                           ),
        }
        base_prompt = step_prompts.get(state.current_step, "Extract relevant information from this message.")
        if "{options}" in base_prompt:
            options = self.get_current_options(state)
            base_prompt = base_prompt.format(options=", ".join(options) if options else "none available")
        print("*"*40)
        print("base_prompt: ", base_prompt)
        print("*"*40)
        return base_prompt
    
    
    
    def ask_for_project(self, state):
        projects = [project["name"] for project in self.allowed_values["allowed_projects"]]
        if len(projects) < 1:
            state.response = f"**You need to create a project first. Please create a project and then come back to create the instance.**"
        else:
            state.response = f"**In which project do you want to create the instance?**\n\nAvailable projects you have access to are: \n\n**{', '.join(projects)}**"
        state.current_step = "project"
        return state

    def ask_for_instance_name(self, state):
        state.response = "**What would you like to name your instance?**"
        state.current_step = "instance_name"
        return state

    def ask_for_location(self, state):
        zones = [zone["zone"] for zone in self.allowed_values["allowed_zones"]]
        state.response = f"**Choose a location for your instance. The available locations are:**\n\n**{', '.join(zones)}**"
        state.current_step = "location"
        return state

    def ask_for_prepackage_or_custom(self, state):
        state.response = "**Would you like to use a pre-configured instance (Prepackage) or customize it?**\n\n- **Prepackage**\n- **Custom**"
        state.current_step = "prepackage_or_custom" 
        return state

    def ask_for_instance_type(self, state):
        instances = "\n".join([
            f"- **{i['name']}** "
            f"{i['memmory_size']}GB RAM, {i['storage_size']}GB Storage, "
            f"{i['vcpu']} vCPU)"
            f"Price: ${i['price']}/{i['periodicity']}"
            for i in self.allowed_values["instance_types"]  
        ])
        state.response = f"**Choose one of the following instances pre-configured available for you:**\n\n{instances}"
        state.current_step = "instance_type"
        return state

    def ask_for_custom_instance_details(self, state):
        state.response = "**What specifications do you need for your instance?**\n\n- RAM (GB)\n- Storage (GB)\n- vCPU. \n\nPlease enter the specifications in the following format: **RAM, Storage, vCPU**"
        state.current_step = "custom_instance_details"
        return state

    def ask_for_platform_os(self, state):
        os_list = [os["name"] for os in self.allowed_values["allowed_packages"][-1]["os"]]
        state.response = f"**Choose one of the following OS available for you:**\n\n**{', '.join(os_list)}**"
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
            state.response = f"**Which version would you like to install for {current_os['name']}?**\n\n**{versions}**"
            state.current_step = "platform_os_version"
        return state

    def ask_for_database(self, state):
        databases = []
        for package in self.allowed_values["allowed_packages"]:
            if "databases" in package:
                databases.extend([db["name"] for db in package["databases"]])
        state.response = f"**Would you like to install a database?**\n\n**If yes, choose one of the following databases available for you:**\n\n**{'/ '.join(databases)}**"
        state.current_step = "database"
        return state

    def ask_for_database_version(self, state):
        current_db = None
        for package in self.allowed_values["allowed_packages"]:
            if "databases" in package:
                current_db = next(
                    (db for db in package["databases"]
                     if db["name"].lower() == state.instance_data["packages"]["databases"][0]["name"].lower()),
                    None
                )
                if current_db:
                    break
        if current_db:
            versions = ", ".join(current_db["versions"])
            state.response = f"**Choose one of the following versions available for {current_db['name']}:**\n\n**{versions}**"
            state.current_step = "database_version"
        return state

    def ask_for_cms(self, state):
        cms_list = []
        for package in self.allowed_values["allowed_packages"]:
            if "cms" in package:
                cms_list.extend([cms["name"] for cms in package["cms"]])
        state.response = f"**Would you like to install a CMS?**\n\n**If yes, choose one of the following CMS available for you:**\n\n**{'/ '.join(cms_list)}**"
        state.current_step = "cms"
        return state

    def ask_for_cms_version(self, state):
        current_cms = None
        for package in self.allowed_values["allowed_packages"]:
            if "cms" in package:
                current_cms = next(
                    (cms for cms in package["cms"]
                     if cms["name"].lower() == state.instance_data["packages"]["cms"][0]["name"].lower()),
                    None
                )
                if current_cms:
                    break
        if current_cms:
            versions = ", ".join(current_lang["versions"])  # Default if versions are not specified
            state.response = f"**Choose one of the following versions available for {current_cms['name']}:**\n\n**{versions}**"
            state.current_step = "cms_version"
        return state

    def ask_for_language(self, state):
        langs = []
        for package in self.allowed_values["allowed_packages"]:
            if "programming_languages" in package:
                langs.extend([lang["name"] for lang in package["programming_languages"]])
        state.response = f"**Would you like to install a programming language?**\n\n**If yes, choose one of the following programming languages available for you:**\n\n**{'/ '.join(langs)}**"
        state.current_step = "language"
        return state

    def ask_for_language_version(self, state):
        current_lang = None
        for package in self.allowed_values["allowed_packages"]:
            if "programming_languages" in package:
                current_lang = next(
                    (lang for lang in package["programming_languages"]
                     if lang["name"].lower() == state.instance_data["packages"]["programming_languages"][0]["name"].lower()),
                    None
                )
                if current_lang:
                    break
        if current_lang:
            versions = ", ".join(current_lang["versions"])
            state.response = f"**Choose one of the following versions available for {current_lang['name']}:**\n\n**{versions}**"
            state.current_step = "language_version"
        return state

    def ask_for_instance_count(self, state):
        state.response = "**How many instances do you need?**"
        state.current_step = "instance_count"
        return state

    def ask_for_public_key(self, state):
        keypairs = [zone["name"] for zone in self.allowed_values["allowed_keypairs"]]
        state.response = f"**Do you wan to create a new keypair or use an existing one?**\n\n**Available options for existing keys:**\n\n**{'/  '.join(keypairs)}**"
        state.current_step = "public_key"
        return state

    def ask_for_keypair_creation(self, state):
        state.response = "**Please provide a name for the new keypair:**"
        state.current_step = "keypair_creation"
        return state

    def ask_for_keypair_creation_download(self, state):
        state.response = f"**Please download the keypair and save it in the root directory of the instance.**\n\n**{self.public_key_download}**"
        state.current_step = "keypair_creation_download"
        return state

    def ask_for_validation(self, state):
        state.response = "**Here are you final specifications. Please review them and confirm or restart:**\n\n"
        for key, value in state.instance_data.items():
            state.response += f"- **{key}**: {value}\n"
        state.response += "\nType **'confirm'** to proceed or **'restart'** to start over."
        state.current_step = "validation"
        return state

    
    
    def get_current_options(self, state: WorkflowState) -> list:
        selected_os = state.instance_data.get("platform", {}).get("name", "")
        selected_db = state.instance_data.get("databases", [{}])[0].get("name", "")
        selected_cms = state.instance_data.get("cms", [{}])[0].get("name", "")
        selected_lang = state.instance_data.get("programming_languages", [{}])[0].get("name", "")
        
        # allowed_packages = self.allowed_values["allowed_packages"]
        
        options_map = {
            "project": [p["name"] for p in self.allowed_values["allowed_projects"]],
            "location": [z["zone"] for z in self.allowed_values["allowed_zones"]],
            "instance_type": [i["name"] for i in self.allowed_values["instance_types"]],
            "platform_os": [os["name"] for os in self.allowed_values["allowed_packages"][-1]["os"]],
            "platform_os_version": [os["versions"] for os in self.allowed_values["allowed_packages"][-1]["os"] if os["name"] == selected_os][0] if selected_os else [],
            "database": [db["name"] for p in self.allowed_values["allowed_packages"] for db in p.get("databases", [])],
            "database_version": [db["versions"] for p in self.allowed_values["allowed_packages"] for db in p.get("databases", []) if db["name"] == selected_db][0] if selected_db else [],
            "cms": [cms["name"] for p in self.allowed_values["allowed_packages"] for cms in p.get("cms", [])],
            "cms_version": [cms["versions"] for p in self.allowed_values["allowed_packages"] for cms in p.get("cms", []) if cms["name"] == selected_cms][0] if selected_cms else [],
            "language": [lang["name"] for p in self.allowed_values["allowed_packages"] for lang in p.get("programming_languages", [])],
            "language_version": [lang["versions"] for p in self.allowed_values["allowed_packages"] for lang in p.get("programming_languages", []) if lang["name"] == selected_lang][0] if selected_lang else [],
            "public_key": [k["name"] for k in self.allowed_values["allowed_keypairs"]],
        }
        
        print(f"allowed_packages_dict: {options_map}")
        print(f"allowed_packages_dict.get(state.current_step, []): {options_map.get(state.current_step, [])}")

        return options_map.get(state.current_step, [])
       
       
        
    def extract_value(self, prompt: str, user_input: str) -> dict:
        # full_prompt = f"{prompt} '{user_input}'"
        system_prompt = prompt_selector("instance_creation")
        print("*"*40)
        print("system_prompt: ", system_prompt)
        print("*"*40)
        full_prompt = f"{system_prompt}\n{prompt}\nUser Input: "
        print("*"*40)
        print("full_prompt: ", full_prompt)
        print("*"*40)
        llm_response = orchestrator.instance_creation_query_handler(user_input, full_prompt)
        print("*"*40)
        print("llm_response: ", llm_response)
        print("*"*40)
        try:
            print("*"*40)
            print("llm_response: ", llm_response)
            print("*"*40)
            json_text = re.search(r'```json(.*?)```', llm_response, re.DOTALL)
            print("*"*40)
            print("json_text: ", json_text)
            print("*"*40)
            if json_text:
                print("*"*40)
                print("json_text.group(1).strip(): ", json_text.group(1).strip())
                print("*"*40)
                return json.loads(json_text.group(1).strip())
            else:
                return {"error": "Invalid JSON format"}
        except json.JSONDecodeError:
            return {"error": "Failed to parse response"}

        # try:
        #     print(f"llm_response: {llm_response}")
        #     print(f"llm_response.split('```json')[1].split('```')[0]: {llm_response.split('```json')[1].split('```')[0]}")
        #     return json.loads(llm_response.split("```json")[1].split("```")[0])
        # except (json.JSONDecodeError, IndexError):
        #     return {"error": "Invalid format"}

    def handle_extraction_error(self, state: WorkflowState) -> WorkflowState:
        state.retry_count += 1
        if state.retry_count >= self.validation_retries:
            state.response = "Maximum retries reached. Restarting workflow..."
            state.current_step = "start"
            state.retry_count = 0
            state.instance_data = WorkflowState().instance_data
        else:
            state.response = (
                f"Please try again. {self.get_validation_hint(state.current_step)} "
                f"({self.validation_retries - state.retry_count} attempts remaining)"
            )
        return state

    def process_step(self, state: WorkflowState, user_input: str) -> WorkflowState:
        prompt = self.generate_step_prompt(state)
        extraction = self.extract_value(prompt, user_input)
        print("*"*40)
        print("prompt: ", prompt)
        print("user_input: ", user_input)
        print("extraction: ", extraction)
        print("*"*40)
        if "error" in extraction:
            state.retry_count += 1
            if state.retry_count >= self.validation_retries:
                
                return self.handle_extraction_error(state)  # Ensure returning state
        else:
            state.response = (
                f"Sorry, I didn't understand that. {self.get_validation_hint(state.current_step)}"
                f"({self.validation_retries - state.retry_count} attempts remaining)"
            )
            return state
            #     state.response = "Maximum retries reached. Restarting..."
            #     state.retry_count = 0
            # else:
            #     state.response = "Invalid input, please try again."
            # return state
        
        #####
        validation_error = self.validate_extracted_value(
            state.current_step, 
            extraction,
            state.instance_data
        )
        
        # self.validate_extracted_value(
        #     state.current_step, 
        #     extraction,
        #     state.instance_data
        # )
        
        if validation_error:
            state.retry_count += 1
            state.response = validation_error
            return self.handle_validation_failure(state) 
        
        #######
        print(f"extraction: {extraction}")
        # state.instance_data.update(extraction)
        self._update_instance_data(state, extraction)
        print(f"state.instance_data: {state.instance_data}")
        state.retry_count = 0
        state.response = None
        return state
    
    
    
    def _update_instance_data(self, state: WorkflowState, extraction: Dict) -> None:
        if state.current_step == "platform_os":
            state.instance_data["platform"]["os"] = extraction["platform_os"]
        elif state.current_step == "platform_os_version":
            state.instance_data["platform"]["os_version"] = extraction["platform_os_version"]
        elif state.current_step == "database":
            state.instance_data["databases"] = [{"name": extraction["database"]}]
        elif state.current_step == "database_version":
            state.instance_data["databases"][0]["version"] = extraction["database_version"]
        elif state.current_step == "cms":
            state.instance_data["cms"] = [{"name": extraction["cms"]}]
        elif state.current_step == "cms_version":
            state.instance_data["cms"][0]["version"] = extraction["cms_version"]
        elif state.current_step == "language":
            state.instance_data["programming_languages"] = [{"name": extraction["language"]}]   
        elif state.current_step == "language_version":
            state.instance_data["programming_languages"][0]["version"] = extraction["language_version"]
        elif state.current_step == "public_key":
            state.instance_data["public_key"] = extraction["public_key"]
        elif state.current_step == "keypair_creation":
            state.instance_data["new_key"] = extraction["new_key"]
        elif state.current_step == "instance_count":
            state.instance_data["instance_count"] = extraction["instance_count"]
        else:
            state.instance_data.update(extraction)
    
        
    def get_next_step(self, state: WorkflowState) -> str:
        transitions = {
            "start": "project",
            "project": "instance_name",
            "instance_name": "location",
            "location": "prepackage_or_custom",
            "prepackage_or_custom": "instance_type" if state.instance_data.get("type") == "prepackage" else "platform_os",
            "instance_type": "platform_os",
            "platform_os": "platform_os_version",
            "platform_os_version": "database",
            "database": "database_version" if state.instance_data.get("platform_db") else "cms",
            "database_version": "cms",
            "cms": "cms_version" if state.instance_data.get("platform_cms") else "language",
            "cms_version": "language",
            "language": "language_version" if state.instance_data.get("platform_language") else "public_key",
            "language_version": "public_key",
            "public_key": "keypair_creation" if state.instance_data.get("new_key") is True else "instance_count",
            "keypair_creation": "instance_count",
            "instance_count": "validation",
            "validation": "finalize"
        }
        return transitions.get(state.current_step, "unknown_step")
  
###############################################################################################  

    def validate_extracted_value(self, step: str, value: dict, instance_data: dict) -> str:
        """Business logic validation"""
        
        def get_allowed_values(key, nested_key=None):
            """Helper function to retrieve allowed values"""
            if nested_key:
                return [item[nested_key] for package in self.allowed_values["allowed_packages"] for item in package.get(key, [])]
            return [item[key] for item in self.allowed_values["allowed_" + key]]

        if step == "project":
            projects = get_allowed_values("projects", "name")
            if value["project"] not in projects:
                return f"Invalid project. Valid options: {', '.join(projects)}"

        elif step == "instance_name":
            if not re.match(r"^[a-zA-Z0-9-]{3,64}$", value["instance_name"]):
                return "Invalid name. Must be 3-64 alphanumeric characters."

        elif step == "location":
            zones = get_allowed_values("zones", "zone")
            if value["location"] not in zones:
                return f"Invalid zone. Valid options: {', '.join(zones)}"

        elif step == "prepackage_custom":
            if value["type"] not in ["prepackage", "custom"]:
                return "Invalid type. Valid options: prepackage, custom"

        elif step == "instance_type":
            instance_types = get_allowed_values("instance_types", "name")
            if value["instance_type"] not in instance_types:
                return f"Invalid instance type. Valid options: {', '.join(instance_types)}"

        elif step == "platform_os":
            os_list = get_allowed_values("os", "name")
            if value["platform_os"] not in os_list:
                return f"Invalid OS. Valid options: {', '.join(os_list)}"

        elif step == "platform_os_version":
            os_versions = next((os["versions"] for os in get_allowed_values("os") if os["name"] == value["platform_os"]), [])
            if value["platform_os_version"] not in os_versions:
                return f"Invalid OS version. Valid options: {', '.join(os_versions)}"

        elif step == "database":
            databases = get_allowed_values("databases", "name")
            if value["database"] not in databases:
                return f"Invalid database. Valid options: {', '.join(databases)}"

        elif step == "database_version":
            db_versions = next((db["versions"] for db in get_allowed_values("databases") if db["name"] == value["database"]), [])
            if value["database_version"] not in db_versions:
                return f"Invalid database version. Valid options: {', '.join(db_versions)}"

        elif step == "cms":
            cms_list = get_allowed_values("cms", "name")
            if value["cms"] not in cms_list:
                return f"Invalid CMS. Valid options: {', '.join(cms_list)}"

        elif step == "cms_version":
            cms_versions = next((cms["versions"] for cms in get_allowed_values("cms") if cms["name"] == value["cms"]), [])
            if value["cms_version"] not in cms_versions:
                return f"Invalid CMS version. Valid options: {', '.join(cms_versions)}"

        elif step == "language":
            languages = get_allowed_values("programming_languages", "name")
            if value["language"] not in languages:
                return f"Invalid language. Valid options: {', '.join(languages)}"

        elif step == "language_version":
            lang_versions = next((lang["versions"] for lang in get_allowed_values("programming_languages") if lang["name"] == value["language"]), [])
            if value["language_version"] not in lang_versions:
                return f"Invalid language version. Valid options: {', '.join(lang_versions)}"

        elif step == "public_key":
            keypairs = get_allowed_values("keypairs", "name")
            if value["public_key"] not in keypairs:
                return f"Invalid public key. Valid options: {', '.join(keypairs)}"

        return ""
    


    def get_validation_hint(self, step: str) -> str:
        """Help users provide correct input"""
        hints = {
            "project": "Please choose from available projects.",
            "instance_name": "Please provide a name containing only letters, numbers and hyphens.",
            "location": "The location must be one of our available zones.",
        }
        return hints.get(step, "Please check your input and try again.")

    def handle_validation_failure(self, state: WorkflowState) -> WorkflowState:
        """Reset step after too many failures"""
        state.response = (
            "Let's try again. " + self.get_validation_hint(state.current_step)
        )
        state.retry_count = 0
        return state

    
    def run_workflow(self, session_id: str, user_input: str) -> dict:

        try:
            # Load or initialize state
            if self.redis_client.exists(f"workflow_state:{session_id}"):
                state = WorkflowState.parse_raw(self.redis_client.get(f"workflow_state:{session_id}"))
            else:
                state = WorkflowState()
                
            # Process user input if provided
            if user_input.strip():
                state = self.process_step(state, user_input)
                
            # Generate next prompt if no response
            # if not state.response:
            next_step = self.get_next_step(state)
            print("*"*40)
            print("next_step_run_workflow: ", next_step)
            print("*"*40)
            state.current_step = next_step
            
            handler = getattr(self, f"ask_for_{next_step}", None)
            if handler is not None:
                state = handler(state)
            
            print("*"*40)
            print("state.response: ", state.response)
            print("*"*40)
            # state.response = self.generate_step_prompt(state)
                
            # Persist state
            self.redis_client.set(f"workflow_state:{session_id}", state.json())
            return {
                "response": state.response,
                "data": state.instance_data,
                "current_step": state.current_step
            }
        except Exception as e:
            logger.exception("Workflow execution failed:")
            return {"response": "An error occurred in the workflow", "data": {}, "current_step": "error"}

    def trigger_keypair_creation_api(self, instance_data: dict) -> str:
        payload = {
            "keypair_name": instance_data["new_publickey_name"],
            "keypair_type": "RSA",
            "keypair_file_format": "pem"
        }
        headers = {"Authorization": f"Bearer {self.jwt_token}"}
        response = requests.post(
            "https://enterprisepythonbackend.mizzle.io/api/instance/keypair",
            json=payload,
            headers=headers
        )
        return response.text

    def trigger_instance_creation_api(self, instance_data: dict) -> str:
        instance_data.pop("type", None)
        instance_data["custom_security_group"] = HARDCODED_SECURITY_GROUP
        headers = {"Authorization": f"Bearer {self.jwt_token}", "Content-Type": "application/json"}
        response = requests.post(
            "https://enterprisepythonbackend.mizzle.io/api/instance/create-instance",
            json=instance_data,
            headers=headers
        )
        return response.text
    
    
    def run_chat(self, query: UserQuery):
        try:
            print("*"*40)
            print("query.text: ", query.text)
            print("*"*40)
            response_data = self.run_workflow(
                session_id=query.session_id,
                user_input=query.text or ""  # Handle empty initial input
            )
            
            # Handle initial empty input
            if not query.text.strip() and response_data["current_step"] == "start":
                response_data = self.run_workflow(
                    session_id=query.session_id,
                    user_input="init"  # Special initialization trigger
                )
                
            logger.info(f"Workflow state: {response_data}")
            
            if response_data["data"]["new_key"] and response_data["current_step"] == "keypair_creation":
                try:
                    api_response = self.trigger_keypair_creation_api(response_data["data"]["public_key"])
                except Exception as e:
                    api_response = "Failed to create keypair. Please try again."
                return {"response": api_response}
            
            # Handle finalization
            if response_data["current_step"] == "finalize":
                return self.finalize_creation(response_data["data"])
                
            return {"response": response_data["response"]}
        except Exception as e:
            logger.exception("Chat execution failed:")
            return {"response": "An error occurred during instance creation"}
        
        
        
        
        
        
        
        
        
        
        
        # print("*"*40)
        # print("query.text: ", query.text)
        # print("*"*40)
        # response, data, current_step = self.run_workflow(session_id=query.session_id, user_input=query.text)
        # print("*"*40)
        # print("response: ", response)
        # print("data: ", data)
        # print("current_step: ", current_step)
        # print("*"*40)
        
        # logger.info({"event": "instance_creation", "message": f"Instance intermediate collected data for {query.session_id}: {data}"})

        # if data["new_key"] and current_step == "keypair_creation":
        #     try:
        #         api_response = self.trigger_keypair_creation_api(data['public_key'])
        #     except Exception as e:
        #         api_response = "Failed to create keypair. Please try again."
        #     return {"response": api_response}
        
        # if "Instance configuration complete!" in response:
        #     logger.info({"event": "instance_creation", "message": f"Instance creation triggered with data: {data}"})
        #     api_response = self.trigger_instance_creation_api(data)
        #     return {"response": api_response}
            
        # return {"response": response}
