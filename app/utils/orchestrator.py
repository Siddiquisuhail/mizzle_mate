import os
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
from langchain_huggingface import HuggingFacePipeline
from huggingface_hub import login
import torch
import json
import os

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '.'))

# # Build the path to the config file
config_file_path = os.path.join(parent_dir, 'config.json')


with open(config_file_path, 'r') as f:
    config = json.load(f)

HF_TOKEN = config.get("HF_TOKEN")


class Orchestrator:
    def __init__(self):
        self.hf_token = HF_TOKEN 
        login(token=self.hf_token)

        # Model details
        # self.model_name = "meta-llama/Llama-3.1-8B-Instruct"  
        # self.model_path = "models/Meta-Llama-3-8B"
        self.model_name = "deepseek-ai/DeepSeek-R1-Distill-Llama-8B"  
        self.model_path = "models/deepseek-ai/DeepSeek-R1-Distill-Llama-8B"

        # Load model and tokenizer
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model, self.tokenizer = self._load_model()

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
        """
        Load the model from the local path if it exists, otherwise download it.
        """
        if not self._is_model_downloaded(self.model_path):
            os.makedirs(self.model_path, exist_ok=True)
            print(f"Downloading {self.model_name}...")

            # Download fresh copy
            model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                cache_dir=self.model_path,
                use_auth_token=self.hf_token,
                trust_remote_code=True,
                torch_dtype=torch.float16,  # Use FP16 to reduce memory usage
                device_map="auto"  # Automatically distribute across available GPUs
            )
            tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                cache_dir=self.model_path,
                use_auth_token=self.hf_token,
                trust_remote_code=True
            )
        else:
            print(f"Loading {self.model_name} from cache...")
            model = AutoModelForCausalLM.from_pretrained(
                self.model_path, 
                trust_remote_code=True, 
                torch_dtype=torch.float16,  
                device_map="auto"
            )
            tokenizer = AutoTokenizer.from_pretrained(self.model_path, trust_remote_code=True)

        return model, tokenizer

    
    def handle_query(self, query: str, system_prompt: str) -> str:

        formatted_prompt = (
            "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n"
            f"{system_prompt}\n"
            "<|eot_id|><|start_header_id|>user<|end_header_id|>\n"
            f"{query}\n"
            "<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n"
        )

        # print("#"*40)
        # print("Formatted Prompt:", formatted_prompt)

        # Ensure model & input are on the same device
        device = self.model.device  # Ensure everything runs on the same device
        print(f"Model is running on: {device}")

        # Tokenize and move inputs to GPU
        inputs = self.tokenizer(formatted_prompt, return_tensors="pt").to(device)

        print("Tokenized Input Shape:", inputs["input_ids"].shape)

        # Generate response
        with torch.no_grad():  # Disables gradient calculation for efficiency
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=256,  
                temperature=0.6,  
                top_p=0.8,  
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id
            )
        torch.cuda.empty_cache()
        # Decode response
        response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        assistant_response = response.split("assistant:")[-1].strip()

        return assistant_response
    
    
    def instance_creation_query_handler(self):
        pipe = pipeline("text-generation", model=self.model, tokenizer=self.tokenizer, max_length=100)
        llm = HuggingFacePipeline(pipeline=pipe)
        return llm
    
    
    
    
    
