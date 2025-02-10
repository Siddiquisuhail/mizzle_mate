from fuzzywuzzy import process
import redis
from app.models.chat_models import UserQuery, ChatResponse
from app.agents.instance_creation.utils.instance_data_cache import fetch_allowed_values
import json
import re
import requests
from typing import Dict
# from app.utils.response_processing import clean_response
# from app.utils.orchestrator import Orchestrator
# from app.utils.prompt_selector import prompt_selector
from    log.logging_config import logger



# Redis client initialization
redis_client = redis.Redis(host="localhost", port=6379, decode_responses=True)


# orchestrator = Orchestrator()


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

# WorkflowState class to manage the state of the workflow
class WorkflowState:
    def __init__(self):
        self.instance_data = {"packages": {}}
        self.current_step = "start"
        self.next_step = None
        self.response = None
        self.retry_count = 0  # Track retries for fallback mechanism


# Instance_Creation class to handle the instance creation workflow
class Instance_Creation:
    def __init__(self, query: UserQuery):
        self.redis_client = redis_client
        self.allowed_values = fetch_allowed_values(query.jwt_token)
        self.query = query
        self.jwt_token = query.jwt_token
        self.public_key_name = None
        self.public_key_download = None
        self.cms = None
        self.database = None
        self.language = None
        self.platform = None
    # Step Handlers ----------------------------------------------------------

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

    # Input Processing --------------------------------------------------------

    def fuzzy_match(self, input_value, allowed_values):
        """Fuzzy match input value to allowed values."""
        matches = process.extract(input_value, allowed_values, limit=1)
        return matches[0][0] if matches else None

    def process_input(self, state: WorkflowState, user_input: str):
        step = state.current_step
        data = state.instance_data

        try:
            if step == "instance_name":
                if not user_input.strip():
                    raise ValueError("Instance name cannot be empty.")
                data["instance_name"] = user_input.strip()

            elif step == "project":
                projects = [p["name"] for p in self.allowed_values["allowed_projects"]]
                matched_project = self.fuzzy_match(user_input, projects)
                if matched_project:
                    selected = next(p for p in self.allowed_values["allowed_projects"]
                                   if p["name"].lower() == matched_project.lower())
                    data["project"] = selected["id"]
                else:
                    raise ValueError(f"No match found for '{user_input}'. Allowed projects: {', '.join(projects)}")

            elif step == "location":
                zones = [z["zone"] for z in self.allowed_values["allowed_zones"]]
                matched_zone = self.fuzzy_match(user_input, zones)
                if matched_zone:
                    selected = next(z for z in self.allowed_values["allowed_zones"]
                                   if z["zone"].lower() == matched_zone.lower())
                    data["server_zone_code"] = selected["zone_code"]
                else:
                    raise ValueError(f"No match found for '{user_input}'. Allowed zones: {', '.join(zones)}")

            elif step == "prepackage_or_custom":
                if user_input.lower() not in ["prepackage", "custom"]:
                    raise ValueError("Invalid choice. Choose 'Prepackage' or 'Custom'.")
                data["type"] = user_input.lower()

            elif step == "instance_type":
                instances = [i["name"] for i in self.allowed_values["instance_types"]]
                matched_instance = self.fuzzy_match(user_input, instances)
                if matched_instance:
                    selected = next(i for i in self.allowed_values["instance_types"]
                                   if i["name"].lower() == matched_instance.lower())
                    data["instance_type"] = selected["name"]
                else:
                    raise ValueError(f"No match found for '{user_input}'. Allowed instances: {', '.join(instances)}")

            elif step == "custom_instance_details":
                parts = [float(x.strip()) for x in user_input.split(",")]
                if len(parts) != 3:
                    raise ValueError("Need 3 values: memory(GB), storage(GB), vCPU.")
                data["custom_instance_type"] = {
                    "memmory_size": parts[0],
                    "storage_size": parts[1],
                    "vcpu": parts[2]
                }

            elif step == "platform_os":
                os_list = [os["name"] for os in self.allowed_values["allowed_packages"][-1]["os"]]
                matched_os = self.fuzzy_match(user_input, os_list)
                if matched_os:
                    selected = next(os for os in self.allowed_values["allowed_packages"][-1]["os"]
                                   if os["name"].lower() == matched_os.lower())
                    data["platform"] = {"name": selected["name"]}
                    self.platform = selected["name"]
                else:
                    raise ValueError(f"No match found for '{user_input}'. Allowed OS: {', '.join(os_list)}")
                
            
                
            elif step == "platform_os_version":
                current_os = None
                for package in self.allowed_values["allowed_packages"]:
                    if "os" in package:
                        current_os = next(
                            (os for os in package["os"]
                            if os["name"].lower() == data["platform"]["name"].lower()),
                            None
                        )
                        if current_os:
                            break
                print("current_os: ", current_os)
                print("content of current_os: ", current_os.get("versions", []))
                if current_os and user_input.strip() in current_os.get("versions", []):
                    data["platform"]["version"] = user_input.strip()
                else:
                    raise ValueError(f"Invalid version. Allowed versions for {self.database}: {', '.join(current_db.get('versions', []))}")
                
            
                
            elif step == "database":
                print("user_input: ", user_input)
                if "no" not in user_input.lower().strip().split():
                    databases = []
                    for package in self.allowed_values["allowed_packages"]:
                        if "databases" in package:
                            databases.extend(package["databases"])

                    print("databases: ", databases)
                    matched_db = self.fuzzy_match(user_input, [db["name"] for db in databases])
                    print("matched_db: ", matched_db)
                    
                    # if matched_db:
                    #     data["packages"]["databases"][0]["name"] = matched_db
                    #     data["packages"].get("databases").append({"name": selected})
                    
                    
                    if matched_db:
                        # Ensure "databases" key exists
                        if "databases" not in data["packages"]:
                            data["packages"]["databases"] = []

                        # Append the matched database to the list
                        data["packages"]["databases"].append({"name": matched_db})
                        print("#"*100)
                        print("Data after database selection: ", data)
                        print("#"*100)
                        self.database = matched_db 
                    else:   
                        allowed_databases = ', '.join([db["name"] for db in databases])
                        raise ValueError(f"No match found for '{user_input}'. Allowed databases: {allowed_databases}")

            elif step == "database_version":
                current_db = None
                for package in self.allowed_values["allowed_packages"]:
                    if "databases" in package:
                        current_db = next(
                            (db for db in package["databases"]
                             if db["name"].lower() == data["packages"]["databases"][0]["name"].lower()),
                            None
                        )
                        if current_db:
                            break
                print("current_db: ", current_db)
                print("content of current_db: ", current_db.get("versions", []))
                if current_db and user_input.strip() in current_db.get("versions", []):
                    # data["packages"]["databases"][0]["version"] = user_input.strip()
                    data["packages"].get("databases")[0]['version'] = user_input.strip()
                    print("#"*100)
                    print("Data after database version selection: ", data)
                    print("#"*100)
                else:
                    raise ValueError(f"Invalid version. Allowed versions for {self.database}: {', '.join(current_db.get('versions', []))}")

            elif step == "cms":
                if "no" not in user_input.lower().strip().split():
                    cms_list = []
                    for package in self.allowed_values["allowed_packages"]:
                        if "cms" in package:
                            cms_list.extend([cms["name"] for cms in package["cms"]])
                    matched_cms = self.fuzzy_match(user_input, cms_list)
                    
                    if matched_cms:
                        # Ensure "cms" key exists
                        if "cms" not in data["packages"]:
                            data["packages"]["cms"] = []

                        # Append the matched database to the list
                        data["packages"]["cms"].append({"name": matched_cms})
                        print("#"*100)
                        print("Data after cms selection: ", data)
                        print("#"*100)
                        self.cms = matched_cms
                    
                    
                    
                    
                    # if matched_cms:
                    #     data["packages"].get("cms").append({"name": matched_cms})
                    #     self.cms = matched_cms
                    else:   
                        allowed_cms = ', '.join([cms["name"] for cms in cms_list])
                        raise ValueError(f"No match found for '{user_input}'. Allowed CMS: {allowed_cms}")
                    
                    
            elif step == "cms_version":
                current_cms = None
                for package in self.allowed_values["allowed_packages"]:
                    if "cms" in package:
                        current_cms = next(
                            (cms for cms in package["cms"]
                             if cms["name"].lower() == data["packages"]["cms"][0]["name"].lower()),
                            None
                        )   
                        if current_cms:
                            break
                if current_cms and user_input.strip() in current_cms.get("versions", []):
                    data["packages"].get("cms")[0]['version'] = user_input.strip()
                    print("#"*100)
                    print("Data after cms version selection: ", data)
                    print("#"*100)
                else:
                    raise ValueError(f"Invalid version. Allowed versions for {current_cms['name']}: {', '.join(current_cms.get('versions', []))}")
                    

            elif step == "language":
                if "no" not in user_input.lower().strip().split():
                    langs = []
                    for package in self.allowed_values["allowed_packages"]:
                        if "programming_languages" in package:
                            langs.extend([lang["name"] for lang in package["programming_languages"]])
                    matched_lang = self.fuzzy_match(user_input, langs)
                    if matched_lang:
                        # Ensure "programming_languages" key exists
                        if "programming_languages" not in data["packages"]:
                            data["packages"]["programming_languages"] = []

                        # Append the matched language to the list
                        data["packages"]["programming_languages"].append({"name": matched_lang})
                        print("#"*100)
                        print("Data after language selection: ", data)
                        print("#"*100)
                    else:   
                        allowed_langs = ', '.join([lang["name"] for lang in langs])
                        raise ValueError(f"No match found for '{user_input}'. Allowed languages: {allowed_langs}")
            
            
            elif step == "language_version":
                current_lang = None
                for package in self.allowed_values["allowed_packages"]:
                    if "programming_languages" in package:
                        current_lang = next(
                            (lang for lang in package["programming_languages"]
                             if lang["name"].lower() == data["packages"]["programming_languages"][0]["name"].lower()),
                            None
                        )
                        if current_lang:
                            break
                if current_lang and user_input.strip() in current_lang["versions"]:
                    data["packages"].get("programming_languages")[0]['version'] = user_input.strip()
                    print("#"*100)
                    print("Data after language version selection: ", data)
                    print("#"*100)
                else:
                    raise ValueError(f"Invalid version. Allowed versions for {current_lang['name']}: {', '.join(current_lang['versions'])}")
        
            
            
            elif step == "public_key":
                if ['new'] not in user_input.lower().strip().split():
                    keypairs = [k["name"] for k in self.allowed_values["allowed_keypairs"]]
                    matched_keypair = self.fuzzy_match(user_input, keypairs)
                    if matched_keypair:
                        selected = next(k for k in self.allowed_values["allowed_keypairs"]
                                        if k["name"].lower() == user_input.lower())
                        data["public_key"] = selected['name']
                        logger.info({"event": "instance_creation", "message": f"Instance creation triggered with data: {data}"})
                    else:
                        allowed_keypairs = ', '.join([k["name"] for k in keypairs])
                        raise ValueError(f"No match found for '{user_input}'. Allowed keypairs: {allowed_keypairs}")

            elif step == "keypair_creation":
                if not user_input.strip():
                    raise ValueError("Keypair name cannot be empty.")
                data["new_publickey_name"] = user_input.strip()
                data["public_key"] = user_input.strip()  # Update instance['public_key'] with the new key name
                state.current_step = "keypair_creation_download"

            elif step == "instance_count":  
                data["instance_count"] = int(user_input.strip())

            elif step == "validation":
                if user_input.lower() == "confirm":
                    state.response = "Instance configuration complete!"
                    state.current_step = "finalize"
                elif user_input.lower() == "restart":
                    state = WorkflowState()  # Restart the workflow
                    state.response = "Restarting the workflow. Please provide the project name."
                else:
                    raise ValueError("Invalid input. Type 'confirm' or 'restart'.")

            # Reset retry count on successful input
            state.retry_count = 0

        except (ValueError, StopIteration) as e:
            state.retry_count += 1
            if state.retry_count >= 3:
                state = WorkflowState()  # Restart the workflow
                state.response = "Maximum retries reached. Restarting the workflow. Please provide the project name."
            else:
                state.response = f"**Invalid input:** {str(e)}\n\nPlease try again. You have {3 - state.retry_count} retries left."

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
                "database_version" if instance_data.get("packages").get("databases")
                else "cms"
            ),
            "database_version": "cms",
            "cms": lambda: (
                "cms_version" if instance_data.get("packages").get("cms")
                else "language"
            ),
            "cms_version": "language",
            "language": lambda: (
                "language_version" if instance_data.get("packages").get("programming_languages")
                else "public_key"
            ),
            "language_version": "public_key",
            "public_key":lambda: (
                "instance_count" if instance_data.get("public_key")
                else "keypair_creation"
            ),
            "keypair_creation": "keypair_creation_download",
            "keypair_creation_download": "instance_count",
            "instance_count": "validation",
            "validation": "finalize"
        }
         
        next_step = transitions.get(current_step, "finalize")
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
        state.current_step = next_step

        # Generate response
        handler = getattr(self, f"ask_for_{next_step}", None)
        if handler is not None:
            state = handler(state)
        else:
            state.response = "Instance configuration complete!"
            
        # system_prompt = prompt_selector("general")
        
        

        # llm_response = orchestrator.handle_query(state.response, system_prompt)
        # cleaned_llm_response = clean_response(llm_response, query.text,)

        # Save state
        self.redis_client.set(state_key, state.current_step)
        self.redis_client.set(data_key, json.dumps(state.instance_data))
        logger.info({"event": "instance_creation", "message": f"response for {session_id}: {state.response} and data: {state.instance_data}"})
        return {"response": state.response, "data": state.instance_data}

    # API Integration ---------------------------------------------------------
    def trigger_instance_creation_api(self, instance_data: Dict) -> str:
        # Clean up instance type data
        if "custom_instance_type" in instance_data:
            instance_data.pop("type", None)
            
        

            
        # Remove the "type" key from instance_data
        instance_data.pop("type", None)
        
        # Remove the "new_publickey_name" key from instance_data
        instance_data.pop("new_publickey_name", None)
        
        # Remove the "public_key_download" key from instance_data
        instance_data.pop("public_key_download", None)
            
        # Add hardcoded security group
        instance_data["custom_security_group"] = HARDCODED_SECURITY_GROUP
        
        # # Ensure array formats
        # for pkg_type in ["databases", "cms", "programming_languages"]:
        #     instance_data["packages"][pkg_type] = instance_data["packages"].get(pkg_type, [])
        
        # package_list = []
        # for pkg_type in ["databases", "cms", "programming_languages", "applications"]:
        #     for pkg in instance_data.get("packages", {}).get(pkg_type, []):
        #         package_list.append({
        #             "category": pkg_type,
        #             "name": pkg["name"],
        #             "version": pkg["version"]
        #         })
                
        package_dict = {"packages": {}}

        for pkg_type in ["databases", "cms", "programming_languages", "applications"]:
            package_list = []
            for pkg in instance_data.get("packages", {}).get(pkg_type, []):
                package_list.append({
                    "name": pkg["name"],
                    "version": pkg["version"]
                })
            
            if package_list:  # Only add non-empty categories
                package_dict["packages"][pkg_type] = package_list
                
                
        
        
        # Replace the "packages" structure with the list format
        instance_data["packages"] = package_dict
        
        if instance_data.get("packages") == {}:
            instance_data.pop("packages")
            
        # Add default public key if missing
        instance_data.setdefault("public_key", "DefaultKey")
        
        
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
        return response
        
        # if response.message == "success":
        # # # Assuming the API returns the file content directly
        # #     file_content = response.text
        # #     file_name = f"{payload['keypair_name']}.pem"
        # #     with open(file_name, "w") as file:
        # #         file.write(file_content)
        # #     self.public_key_download = file_name
        # #     return file_name
        #     return response
        # else:
        #     return "Failed to create keypair. Please try again."

    def run_chat(self, query: UserQuery):
        result = self.run_workflow(query.session_id, query.text)
        logger.info({"event": "instance_creation", "message": f"Instance intermediate collected data for {query.session_id}: {result['data']}"})

        if "new_publickey_name" in result["data"]:
            try:
                api_response = self.trigger_keypair_creation_api(result["data"] )
            except Exception as e:
                api_response = "Failed to create keypair. Please try again."
            return {"response": api_response}
        
        if "Instance configuration complete!" in result["response"]:
            logger.info({"event": "instance_creation", "message": f"Instance creation triggered with data: {result['data']}"})
            api_response = self.trigger_instance_creation_api(result["data"])
            return {"response": api_response}
            
        return {"response": result["response"]}
