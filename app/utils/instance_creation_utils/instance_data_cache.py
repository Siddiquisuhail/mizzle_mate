import redis
import requests
import json
from app.utils.instance_creation_utils.cleanup_functions import clean_allowed_zones, clean_allowed_packages, \
            clean_instance_types, clean_allowed_security_groups, clean_key_pair_names, clean_allowed_projects
# from cleanup_functions import clean_allowed_zones, clean_allowed_packages, clean_instance_types, clean_allowed_security_groups


# Connect to Redis (or use an in-memory dictionary for testing)
try:
    cache = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)
except Exception:
    cache = {}
    
# cache = {}


API_ENDPOINTS = {
    "allowed_zones": "https://enterprisepythonbackend.mizzle.io/api/instance/server-zone",
    "allowed_packages" : "https://enterprisepythonbackend.mizzle.io/api/common/tech-stack",
    "instance_types" : "https://enterprisepythonbackend.mizzle.io/api/billing/instance-subscriptions",
    "allowed_security_groups": "https://enterprisepythonbackend.mizzle.io/api/instance/security-groups",
    "allowed_keypairs": "https://enterprisepythonbackend.mizzle.io/api/instance/keypair",
    "allowed_projects": "https://enterprisepythonbackend.mizzle.io/api/collab/projects"
    
}

API_ENDPOINTS_TEST = {
    "instance_types" : "https://enterprisepythonbackend.mizzle.io/api/billing/instance-subscriptions"}






clean_function_map = {
    "allowed_zones": clean_allowed_zones,
    "allowed_packages": clean_allowed_packages,
    "instance_types": clean_instance_types,
    "allowed_security_groups": clean_allowed_security_groups,
    "allowed_keypairs": clean_key_pair_names,
    "allowed_projects": clean_allowed_projects
}


def fetch_allowed_values(token: str):
    headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"}

    """Fetch allowed values from API using JWT authentication and cache them."""
    # if cache.exists("allowed_values"):
    #     return json.loads(cache.get("allowed_values"))

    allowed_values = {}
    # count = 0
    # print(API_ENDPOINTS.items())
    for key, url in API_ENDPOINTS.items():
        try:
            
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            func = clean_function_map.get(key) 
            try:    
                allowed_values[key] = func(response.json())
                # print("#########################")
                # print("key: ", key)
                # print("url: ", url)
                # print("allowed_values: ", allowed_values[key])
                # print("#########################")

            except Exception as e:
                print(f"Error cleaning {key}: {e}")
                allowed_values[key] = []
            # count += 1
            # print("count: ", count)
        
        except requests.RequestException as e:
            print(f"Error fetching {key}: {e}")
            allowed_values[key] = [] 
     
    # print("#"*40)
    # print("#"*40)
    # print(f'allowed_values: {allowed_values}')       
    # return allowed_values[key]
        

    
    # cache.set("allowed_values", json.dumps(allowed_values)) 
    # print("count: ", count)# Cache for 1 hour
    return allowed_values

a = fetch_allowed_values("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoyMDUzOTMwNDA1LCJpYXQiOjE3Mzg1NzA0MDUsImp0aSI6IjQ0NTQ2ZDViNjA5MTQ3OTc5NDJlOTk4NzRlYTI0OTllIiwidXVpZCI6IjlmZjc4OGUyLTk4YTgtNDA0NC04ZTAwLWZkOTMyZWNiODY1YiJ9.wU7FUvHlU9wEW6huyWXZa9eoXPBSa2qAcbnpc4GR1nU")
print('final allowed values: ', a)

