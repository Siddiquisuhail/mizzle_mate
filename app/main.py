from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import APIRouter, HTTPException
from app.models.chat_models import UserQuery, ChatResponse
from app.utils.orchestrator import Orchestrator
from app.utils import response_processing
from app.agents import *
import redis
import json


orchestrator = Orchestrator()


redis_client = redis.Redis(host="localhost", port=6379, decode_responses=True)  # Update host/port as needed

# Allow all origins (not recommended for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update this with your frontend domain in production
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)


app = FastAPI()


@app.get("/")
def read_root():
    return {"message": "Welcome to Mizzle Mate!"}

@app.get("/health")
def read_root():
    return {"message": "Health is OK !!!"}


@app.post("/chat", response_model=ChatResponse)
async def chat(query: UserQuery):
    if query.tag == 'general':
        try:
            response = general_chat(query.text)
            return {"response": cleaned_response}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    elif query.tag == 'instance_creation':
        try:
            response = general_chat(query.text)
            return {"response": cleaned_response}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    else:
        return 'No context found'








