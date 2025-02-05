from fastapi import FastAPI
# from app.routers import chat, agent
from fastapi.middleware.cors import CORSMiddleware
from fastapi import APIRouter, HTTPException
from app.models.chat_models import UserQuery, ChatResponse
# from app.utils.orchestrator import Orchestrator
from app.utils.response_processing import clean_response
from app.agents.instance_creation_chat  import Instance_Creation
from app.agents.general_chat import General_Chat
import redis
import json


# orchestrator = Orchestrator()


redis_client = redis.Redis(host="localhost", port=6379, decode_responses=True)  # Update host/port as needed




app = FastAPI()

# Allow all origins (not recommended for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update this with your frontend domain in production
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

@app.get("/")
def read_root():
    return {"message": "Welcome to Mizzle Mate!"}




@app.get("/health")
def read_root():
    return {"message": "Health is Good!"}


@app.post("/chat", response_model=ChatResponse)
async def chat(query: UserQuery):
    print(f"Received tag: {query.tag}") 
    if query.tag == 'general':
        try:
            chat = General_Chat()
            response = chat.general_chat(query)
            print('#'*40)
            print(response)
            print('#'*40)
            return {"response": response}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        
        
    # elif query.tag == 'instance_creation':
    #     try:
    #         chat = Instance_Creation()
    #         response = chat.instance_creation(query)
    #         return {"response": response}
    #     except Exception as e:
    #         raise HTTPException(status_code=500, detail=str(e))
        
    elif query.tag == 'instance_creation':
        print(f"Handling instance_creation for query: {query}") 
        try:
            chat = Instance_Creation(query)
            response = chat.run_chat(query)
            return response
            # return 'You are at the instance creation page'
        except Exception as e: 
            raise HTTPException(status_code=500, detail=str(e))

    # elif query.tag == 'instance_creation':
    #     try:  
    #         chat = Instance_Creation()
    #         response = chat.instance_creation(query)
    #         return {"response": response}
    #     except Exception as e:
    #         raise HTTPException(status_code=500, detail=str(e))
    else:
        return 'No context found'