import os
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from langchain_huggingface import HuggingFacePipeline
from huggingface_hub import login
import torch
import json
import os
import gc
# from bitsandbytes.optim import bnb_4bit_quant_type, bnb_4bit_compute_dtype

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '.'))

# # Build the path to the config file
config_file_path = os.path.join(parent_dir, 'config.json')


with open(config_file_path, 'r') as f:
    config = json.load(f)

HF_TOKEN = config.get("HF_TOKEN")



class Orchestrator:
    _model = None  # Class-level model reference
    _tokenizer = None  # Class-level tokenizer reference
    _logged_in = False  # Track login status
    model_name = "deepseek-ai/DeepSeek-R1-Distill-Llama-8B"  # Fixed model name
    model_path = "models/deepseek-ai/DeepSeek-R1-Distill-Llama-8B"  # Fixed model path
    # model_name = "meta-llama/Llama-3.1-8B-Instruct"  # Fixed model name
    # model_path = "meta-llama/Llama-3.1-8B-Instruct"  # Fixed model path




    def __init__(self):
        # Handle Hugging Face login once
        if not Orchestrator._logged_in:
            login(token=HF_TOKEN)  # HF_TOKEN from outer scope
            Orchestrator._logged_in = True

        # Load model/tokenizer if not already loaded
        if Orchestrator._model is None or Orchestrator._tokenizer is None:
            Orchestrator._model, Orchestrator._tokenizer = self._load_model()
        
        # Reference class-level assets
        self.model = Orchestrator._model
        self.tokenizer = Orchestrator._tokenizer
        self.device = self.model.device  # Track device from actual model
        self.print_gpu_usage("After model loading")
        
        
    def print_gpu_usage(self, context: str):
        if self.device == "cuda":
            allocated = torch.cuda.memory_allocated() / 1024**3
            reserved = torch.cuda.memory_reserved() / 1024**3
            print(f"[GPU Memory] {context}:")
            print(f"Allocated: {allocated:.2f}GB, Reserved: {reserved:.2f}GB")

    def _is_model_downloaded(self, model_path):
        """
        Check if the model is fully downloaded by verifying the required files.
        """
        required_files = [
            "config.json", 
            "pytorch_model.bin",  # May also be "model.safetensors" for newer models
            "tokenizer.json"
        ]
        return all(os.path.exists(os.path.join(model_path, f)) for f in required_files)

    
    def _load_model(self):
        print("Loading model...")
        
        # Configuration
        load_kwargs = {
            "trust_remote_code": True,
            "torch_dtype": torch.float16,  # FP16 for memory efficiency
            "device_map": "auto",
            # "load_in_4bit": True,
            # "bnb_4bit_compute_dtype": torch.float16,
            # "bnb_4bit_quant_type": "nf4"
        }

        # Model loading logic
        if not self._is_model_downloaded(self.model_path):
            print(f"Downloading {self.model_name}...")
            model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                cache_dir=self.model_path,
                use_auth_token=HF_TOKEN,
                **load_kwargs
            )
            tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                cache_dir=self.model_path,
                use_auth_token=HF_TOKEN
            )
        else:
            print(f"Loading from cache {self.model_path}")
            model = AutoModelForCausalLM.from_pretrained(
                self.model_path,
                **load_kwargs
            )
            tokenizer = AutoTokenizer.from_pretrained(self.model_path)

        return model, tokenizer
    
    def cleanup(self):
        if self.device == "cuda":
            del self.model  # Only do this when all agents are done
            torch.cuda.empty_cache()
            self.print_gpu_usage("After cleanup")
    
    
    
    def handle_query(self, query: str, system_prompt: str) -> str:
        formatted_prompt = (
            "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n"
            f"{system_prompt}\n"
            "<|eot_id|><|start_header_id|>user<|end_header_id|>\n"
            f"{query}\n"
            "<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n"
        )

        print("#"*40)
        print("Formatted Prompt:", formatted_prompt)
        print("#"*40)
        # Ensure model & input are on the same device
        device = self.model.device  # Ensure everything runs on the same device
        print(f"Model is running on: {device}")

        # Tokenize and move inputs to GPU
        inputs = self.tokenizer(formatted_prompt, return_tensors="pt").to(device)

        print("Tokenized Input Shape:", inputs["input_ids"].shape)
        with torch.inference_mode():  # More comprehensive than torch.no_grad()
            with torch.backends.cuda.sdp_kernel(
                enable_flash=True, 
                enable_math=False, 
                enable_mem_efficient=False
            ):  # Optimize attention computation
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=512,
                    temperature=0.6,
                    top_p=0.8,
                    do_sample=True,
                    pad_token_id=self.tokenizer.eos_token_id,
                    use_cache=True  # Enable KV caching
                )
        
        response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        assistant_response = response.split("assistant:")[-1].strip()

        return assistant_response

    def instance_creation_query_handler(self, query: str, system_prompt: str) -> str:

        formatted_prompt = (
            "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n"
            f"{system_prompt}\n"
            "<|eot_id|><|start_header_id|>user<|end_header_id|>\n"
            f"{query}\n"
            "<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n"
        )   
        print("#"*40)
        print("Formatted Prompt:", formatted_prompt)
        print("#"*40)
        # Ensure model & input are on the same device
        device = self.model.device  # Ensure everything runs on the same device
        print(f"Model is running on: {device}")

        # Tokenize and move inputs to GPU
        inputs = self.tokenizer(formatted_prompt, return_tensors="pt").to(device)

        print("Tokenized Input Shape:", inputs["input_ids"].shape)
        with torch.inference_mode():  # More comprehensive than torch.no_grad()
            with torch.backends.cuda.sdp_kernel(
                enable_flash=True, 
                enable_math=False, 
                enable_mem_efficient=False
            ):  # Optimize attention computation
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=512,
                    temperature=0.6,
                    top_p=0.8,
                    do_sample=True,
                    pad_token_id=self.tokenizer.eos_token_id,
                    use_cache=True  # Enable KV caching
                )
        
        response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        assistant_response = response.split("assistant:")[-1].strip()

        return assistant_response

    def general_handle_query(self, query: str) -> str:
            # Ensure model & input are on the same device
            device = self.model.device  # Ensure everything runs on the same device
            print(f"Model is running on: {device}")

            # Tokenize and move inputs to GPU
            inputs = self.tokenizer(query, return_tensors="pt").to(device)

            print("Tokenized Input Shape:", inputs["input_ids"].shape)
            with torch.inference_mode():  # More comprehensive than torch.no_grad()
                with torch.backends.cuda.sdp_kernel(
                    enable_flash=True, 
                    enable_math=False, 
                    enable_mem_efficient=False
                ):  # Optimize attention computation
                    outputs = self.model.generate(
                        **inputs,
                        max_new_tokens=512,
                        temperature=0.4,
                        top_p=0.8,
                        do_sample=True,
                        pad_token_id=self.tokenizer.eos_token_id,
                        use_cache=True  # Enable KV caching
                    )
            
            response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            assistant_response = response.split("assistant:")[-1].strip()

            return assistant_response






























# class Orchestrator:
#     def __init__(self):
#         self.hf_token = HF_TOKEN 
#         login(token=self.hf_token)

#         # Model details
#         # self.model_name = "meta-llama/Llama-3.1-8B-Instruct"  
#         # self.model_path = "models/Meta-Llama-3-8B"
#         self.model_name = "deepseek-ai/DeepSeek-R1-Distill-Llama-8B"  
#         self.model_path = "models/deepseek-ai/DeepSeek-R1-Distill-Llama-8B"

#         # Load model and tokenizer
#         self.device = "cuda" if torch.cuda.is_available() else "cpu"
#         self.model, self.tokenizer = self._load_model()

#     def _is_model_downloaded(self, model_path):
#         """
#         Check if the model is fully downloaded by verifying the required files.
#         """
#         required_files = [
#             "config.json", 
#             "pytorch_model.bin",  # May also be "model.safetensors" for newer models
#             "tokenizer.json"
#         ]
#         return all(os.path.exists(os.path.join(model_path, f)) for f in required_files)

#     def _load_model(self):
#         """
#         Load the model from the local path if it exists, otherwise download it.
#         """
#         if not self._is_model_downloaded(self.model_path):
#             os.makedirs(self.model_path, exist_ok=True)
#             print(f"Downloading {self.model_name}...")

#             # Download fresh copy
#             model = AutoModelForCausalLM.from_pretrained(
#                 self.model_name,
#                 cache_dir=self.model_path,
#                 use_auth_token=self.hf_token,
#                 trust_remote_code=True,
#                 torch_dtype=torch.float16,  # Use FP16 to reduce memory usage
#                 device_map="auto"  # Automatically distribute across available GPUs
#             )
#             tokenizer = AutoTokenizer.from_pretrained(
#                 self.model_name,
#                 cache_dir=self.model_path,
#                 use_auth_token=self.hf_token,
#                 trust_remote_code=True
#             )
#         else:
#             print(f"Loading {self.model_name} from cache...")
#             model = AutoModelForCausalLM.from_pretrained(
#                 self.model_path, 
#                 trust_remote_code=True, 
#                 torch_dtype=torch.float16,  
#                 device_map="auto"
#             )
#             tokenizer = AutoTokenizer.from_pretrained(self.model_path, trust_remote_code=True)

#         return model, tokenizer

    
#     def handle_query(self, query: str, system_prompt: str) -> str:

#         formatted_prompt = (
#             "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n"
#             f"{system_prompt}\n"
#             "<|eot_id|><|start_header_id|>user<|end_header_id|>\n"
#             f"{query}\n"
#             "<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n"
#         )

#         # print("#"*40)
#         # print("Formatted Prompt:", formatted_prompt)

#         # Ensure model & input are on the same device
#         device = self.model.device  # Ensure everything runs on the same device
#         print(f"Model is running on: {device}")

#         # Tokenize and move inputs to GPU
#         inputs = self.tokenizer(formatted_prompt, return_tensors="pt").to(device)

#         print("Tokenized Input Shape:", inputs["input_ids"].shape)

#         # Generate response
#         with torch.no_grad():  # Disables gradient calculation for efficiency
#             outputs = self.model.generate(
#                 **inputs,
#                 max_new_tokens=256,  
#                 temperature=0.6,  
#                 top_p=0.8,  
#                 do_sample=True,
#                 pad_token_id=self.tokenizer.eos_token_id
#             )
#         torch.cuda.empty_cache()
#         # Decode response
#         response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
#         assistant_response = response.split("assistant:")[-1].strip()

#         return assistant_response
    
    
#     def instance_creation_query_handler(self, query: str):
#         device = self.model.device  # Ensure everything runs on the same device
#         print(f"Model is running on: {device}")

#         # Tokenize and move inputs to GPU
#         inputs = self.tokenizer(query, return_tensors="pt").to(device)

#         print("Tokenized Input Shape:", inputs["input_ids"].shape)

#         # Generate response
#         with torch.no_grad():  # Disables gradient calculation for efficiency
#             outputs = self.model.generate(
#                 **inputs,
#                 max_new_tokens=256,  
#                 temperature=0.6,  
#                 top_p=0.8,  
#                 do_sample=True,
#                 pad_token_id=self.tokenizer.eos_token_id
#             )
#         torch.cuda.empty_cache()
#         # Decode response
#         response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
#         # assistant_response = response.split("assistant:")[-1].strip()

#         return response
    
    
    
    
    
