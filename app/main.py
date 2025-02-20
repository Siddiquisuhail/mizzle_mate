from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import HTTPException
from app.models.chat_models import UserQuery, ChatResponse
from app.agents.instance_creation.instance_creation_chat import Instance_Creation
from app.agents.instance_creation.model import LLMEnhancedWorkflow
from app.agents.general_chat.general_chat import General_Chat
import redis
from log.middleware import LoggingMiddleware
from log.exception_handler import exception_handler
from log.logging_config import logger
from app.agents.compute_functionality.compute import ComputeChat




#redis_client = redis.Redis(host="localhost", port=6379, decode_responses=True)  





app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)


# Attach Logging Middleware
app.add_middleware(LoggingMiddleware)

# Attach Exception Handler
app.add_exception_handler(Exception, exception_handler)




@app.get("/")
async def read_root():
    return {"message": "Welcome to Mizzle Mate!"}




@app.get("/health")
async def read_root():
    return {"message": "Health is Good!"}


@app.post("/chat", response_model=ChatResponse)
async def chat(query: UserQuery):
    if query.tag == 'general':
        logger.info({"event": "general_chat", "message": "General cgeneral chat accessed"})
        try:
            chat = General_Chat()
            response = chat.general_chat_2(query)
            # print('#'*40)
            # print(response)
            # print('#'*40)
            return {"response": response}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        
    #     logger.info({"event": "instance_creation", "message": "Instance creation endpoint accessed"})
    #     try:
    #         chat = Instance_Creation(query)
    #         response = chat.run_chat(query)
    #         return response
    #     except Exception as e: 
    #         raise HTTPException(status_code=500, detail=str(e))
    
    
    elif query.tag == 'instance_creation_chat':
        logger.info({"event": "instance_creation", "message": "Instance creation endpoint accessed"})
        try:    
            workflow = Instance_Creation(query)
            response = workflow.run_chat(query)
            return response
        except Exception as e: 
            raise HTTPException(status_code=500, detail=str(e))
    
    
    elif query.tag == 'compute_chat':
        logger.info({"event": "general_chat", "message": "General cgeneral chat accessed"})
        try:
            chat = ComputeChat()
            response = chat.compute_chat(query)
            # print('#'*40)
            # print(response)
            # print('#'*40)
            return {"response": response}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


    else:
        return 'No context found'